"""
Analysis Service – Graph-Grounded Deduction Layer
==================================================

Provides the core KuzuDB → LLM → Structured-JSON pipeline:

  * ``get_graph_context()``        – query KuzuDB for 1-hop and 2-hop paths
  * ``extract_entities_from_text()`` – extract key entities from raw news text
  * ``perform_deduction()``        – full graph-grounded deduction pipeline
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════

def _ensure_backend_on_path() -> None:
    """Ensure the ``backend/`` directory is importable."""
    here = os.path.abspath(__file__)
    # backend/app/services/analysis_service.py → backend/
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)


# ═══════════════════════════════════════════════════════════════════
# 1.  get_graph_context
# ═══════════════════════════════════════════════════════════════════

def get_graph_context(kuzu_conn: Any, entity_names: List[str]) -> str:
    """Query KuzuDB for 1-hop and 2-hop relationship paths for a list of entities.

    Each path is formatted as a human-readable fact string so that an LLM
    can directly reference it as grounding evidence.

    Examples::

        事实: [美国联邦储备] --(INFLUENCES)--> [科技股 (类型:Concept)]
        推演: [美国联邦储备] --(INFLUENCES)--> [科技股] --(CAUSES)--> [市场恐慌]

    Args:
        kuzu_conn:    Active KuzuDB connection.  Pass ``None`` for graceful
                      degradation (returns an empty string).
        entity_names: List of entity names to use as graph query seeds.

    Returns:
        Multi-line string of relationship facts, deduplicated.
        Empty string when the connection is unavailable or no paths exist.
    """
    if kuzu_conn is None:
        return ""

    all_paths: List[str] = []

    for entity in entity_names:
        # Sanitise to prevent Cypher injection
        safe = entity.replace("\\", "\\\\").replace("'", "\\'")

        # ── 1-hop: (a)-[r1]->(b) ──────────────────────────────────────
        query_1hop = (
            f"MATCH (a)-[r1]->(b) "
            f"WHERE a.name = '{safe}' "
            "RETURN a.name, type(r1), b.name, label(b) "
            "LIMIT 5"
        )
        b_nodes: List[tuple] = []
        try:
            result_1hop = kuzu_conn.execute(query_1hop)
            while result_1hop.hasNext():
                row = result_1hop.getNext()
                a_name = row[0] or entity
                r1_type = row[1] or "RELATED_TO"
                b_name = row[2] or ""
                b_type = row[3] or ""
                if b_name:
                    path = (
                        f"事实: [{a_name}] --({r1_type})--> "
                        f"[{b_name} (类型:{b_type})]"
                    )
                    all_paths.append(path)
                    b_nodes.append((b_name, r1_type))
        except Exception as exc:
            logger.warning("KuzuDB 1-hop query failed for '%s': %s", entity, exc)

        # ── 2-hop: (b)-[r2]->(c) for every b found above ──────────────
        for b_name, r1_type in b_nodes:
            safe_b = b_name.replace("\\", "\\\\").replace("'", "\\'")
            query_2hop = (
                f"MATCH (b)-[r2]->(c) "
                f"WHERE b.name = '{safe_b}' "
                "RETURN b.name, type(r2), c.name "
                "LIMIT 3"
            )
            try:
                result_2hop = kuzu_conn.execute(query_2hop)
                while result_2hop.hasNext():
                    row2 = result_2hop.getNext()
                    c_name = row2[2] or ""
                    if c_name:
                        path_2hop = (
                            f"推演: [{entity}] --({r1_type})--> "
                            f"[{b_name}] --({row2[1]})--> [{c_name}]"
                        )
                        all_paths.append(path_2hop)
            except Exception as exc:
                logger.debug(
                    "KuzuDB 2-hop query failed for intermediate '%s': %s",
                    b_name,
                    exc,
                )

    # Deduplicate while preserving insertion order
    seen: set = set()
    unique: List[str] = []
    for p in all_paths:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    return "\n".join(unique)


# ═══════════════════════════════════════════════════════════════════
# 2.  extract_entities_from_text
# ═══════════════════════════════════════════════════════════════════

async def extract_entities_from_text(news_content: str) -> List[str]:
    """Extract 1–3 key named entities from news text.

    Tries an LLM-based extraction first; falls back to a simple regex
    heuristic when the LLM is unavailable.

    Args:
        news_content: Raw news article text.

    Returns:
        List of 1–3 entity name strings.
    """
    if not news_content:
        return []

    _ensure_backend_on_path()

    # ── LLM-based extraction ───────────────────────────────────────
    try:
        from app.core.config import get_settings  # type: ignore[import]

        settings = get_settings()
        if getattr(settings, "llm_enabled", False):
            from intelligence.sacred_sword_analyzer import SacredSwordAnalyzer  # type: ignore[import]

            analyzer = SacredSwordAnalyzer(settings=settings)
            prompt = (
                "Extract 1-3 key named entities (organizations, people, places, "
                "or concepts) from this news text. "
                'Return ONLY a JSON array of strings, e.g. ["Entity1", "Entity2"].\n\n'
                f"News: {news_content[:500]}"
            )
            # _llm_call is the internal method used consistently throughout the
            # codebase (e.g. in analysis.py's _LLMAdapter) for direct LLM calls.
            raw = analyzer._llm_call(prompt, temperature=0.0)
            if raw:
                match = re.search(r"\[.*?\]", raw, re.DOTALL)
                if match:
                    parsed = json.loads(match.group())
                    if isinstance(parsed, list):
                        return [str(e) for e in parsed[:3] if e]
    except Exception as exc:
        logger.debug(
            "LLM entity extraction failed, falling back to heuristic: %s", exc
        )

    # ── Heuristic fallback: capitalised noun-phrase runs ──────────
    _STOP = {
        "The", "A", "An", "In", "On", "At", "Of", "For",
        "To", "From", "And", "Or", "Is", "Are", "Was", "Were",
    }
    candidates: List[str] = re.findall(
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", news_content[:800]
    )
    seen: set = set()
    unique: List[str] = []
    for c in candidates:
        if c not in _STOP and len(c) > 3 and c not in seen:
            seen.add(c)
            unique.append(c)

    return unique[:3] if unique else []


# ═══════════════════════════════════════════════════════════════════
# 3.  perform_deduction
# ═══════════════════════════════════════════════════════════════════

async def perform_deduction(
    news_content: str,
    kuzu_conn: Any,
) -> Dict[str, Any]:
    """Full Graph-Grounded Deduction pipeline.

    Steps:
        1. Extract 1–3 key entities from the news text.
        2. Query KuzuDB for 1-hop and 2-hop relationship paths (GraphContext).
        3. Build an RAG-enhanced prompt with the GraphContext as grounding.
        4. Invoke the DeductionEngine (LLM) for strict logical inference.
        5. Return a structured dict including ``graph_evidence``.

    Args:
        news_content: Raw news text to analyse.
        kuzu_conn:    Active KuzuDB connection (may be ``None``).

    Returns:
        Dict with keys: ``driving_factor``, ``scenario_alpha``,
        ``scenario_beta``, ``verification_gap``, ``confidence``,
        ``graph_evidence``.
    """
    _ensure_backend_on_path()

    # Step 1 – entity extraction
    entities = await extract_entities_from_text(news_content)
    logger.info("Extracted entities for deduction: %s", entities)

    # Step 2 – graph context from KuzuDB
    graph_context = get_graph_context(kuzu_conn, entities)
    path_count = graph_context.count("\n") + 1 if graph_context.strip() else 0
    logger.info("GraphContext retrieved: %d paths", path_count)

    # Step 3 – build LLM service
    try:
        from app.api.routes.analysis import _get_llm_service  # type: ignore[import]

        llm_service = _get_llm_service()
    except Exception as exc:
        logger.warning("Could not obtain LLM service: %s", exc)

        class _StubLLM:
            def call(self, **kwargs: Any) -> str:  # noqa: D102
                return "{}"

        llm_service = _StubLLM()

    # Step 4 – run OntologyGroundedAnalyzer (DeductionEngine injected internally)
    from intelligence.grounded_analyzer import OntologyGroundedAnalyzer  # type: ignore[import]

    analyzer = OntologyGroundedAnalyzer(
        llm_service=llm_service,
        kuzu_conn=kuzu_conn,
    )
    result = analyzer.analyze_with_ontological_grounding(
        news_fragment=news_content,
        seed_entities=entities if entities else ["Unknown"],
        claim="What will be the impact of this event?",
    )

    # Step 5 – attach graph_evidence and return
    deduction: Dict[str, Any] = result.get("deduction_result", {})
    deduction["graph_evidence"] = graph_context
    return deduction
