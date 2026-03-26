"""
Analysis Service – Graph-Grounded Deduction Pipeline

Provides the ``perform_deduction`` async function that orchestrates:
1. Entity extraction from raw news text
2. KuzuDB ontological context retrieval (1-hop + 2-hop paths)
3. LLM-based structured deduction grounded in graph evidence
4. Confidence scoring with evidence-richness boost
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Known high-signal terms that the general capitalised-word regex often
# misses (acronyms, lower-case variants, multi-word phrases).
_KNOWN_KEYWORDS: List[str] = [
    # Geopolitical actors & regions
    "Israel", "Israeli", "Iran", "Iranian", "IRGC",
    "Gaza", "Palestinian", "Hamas", "Hezbollah",
    "Lebanon", "Lebanese", "Syria", "Syrian",
    "Russia", "Russian", "Ukraine", "Ukrainian",
    "China", "Chinese", "USA", "EU", "NATO",
    # Tech / economy
    "AI", "OpenAI", "Google", "Microsoft", "Apple",
    "startup", "chip", "semiconductor", "GPU", "data center",
    "Fed", "ECB", "inflation", "tariff", "trade", "currency",
    "OPEC", "sanctioned", "sanctions",
]


def _ensure_backend_on_path() -> None:
    """Add backend root to sys.path so internal packages are importable."""
    here = os.path.abspath(__file__)
    # Walk up: analysis_service.py → services → app → backend
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)


async def extract_entities_from_text(text: str) -> List[str]:
    """Extract named entities from news text using lightweight heuristics.

    Combines a curated keyword list covering geopolitical, technology and
    economic domains with a general capitalised-phrase pattern so that the
    pipeline never hard-fails even without spaCy/NER.

    Args:
        text: Raw news text to extract entities from.

    Returns:
        List of up to 8 unique entity name strings (keyword hits first).
    """
    # Known high-signal terms that the general capitalised-word regex often
    # misses (acronyms, lower-case variants, multi-word phrases).

    def _extract(t: str) -> List[str]:
        entities: List[str] = []
        seen: set = set()

        # 1) Keyword scan (case-insensitive, whole-word)
        for kw in _KNOWN_KEYWORDS:
            pattern = re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE)
            if pattern.search(t):
                canonical = kw  # keep the canonical form
                if canonical not in seen:
                    entities.append(canonical)
                    seen.add(canonical)

        # 2) General capitalised-phrase fallback
        cap_pattern = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4})\b")
        for match in cap_pattern.finditer(t):
            token = match.group(1).strip()
            if token not in seen and len(token) > 2:
                entities.append(token)
                seen.add(token)

        return entities[:8]

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _extract, text)


def get_graph_context(kuzu_conn: Any, entities: List[str]) -> str:
    """Retrieve ontological context paths from KuzuDB for a list of entities.

    Queries 1-hop and 2-hop paths for each entity and concatenates the
    results into a single prompt-ready string.

    Args:
        kuzu_conn: Open KuzuDB connection (may be ``None`` when unavailable).
        entities:  List of entity names to query.

    Returns:
        Formatted context string, or empty string when graph is unavailable.
    """
    if kuzu_conn is None or not entities:
        return "【知识图谱暂无数据】将基于新闻内容和通用领域知识进行推演"

    _ensure_backend_on_path()

    try:
        from ontology.kuzu_context_extractor import get_ontological_context  # type: ignore
    except ImportError:
        logger.warning("ontology.kuzu_context_extractor not importable; skipping graph context")
        return ""

    context_parts: List[str] = []
    for entity in entities[:4]:  # cap at 4 entities to keep prompt size manageable
        try:
            part = get_ontological_context(kuzu_conn, entity)
            if part.strip():
                context_parts.append(part)
        except Exception as exc:
            logger.debug("Could not get context for %s: %s", entity, exc)

    return "\n".join(context_parts)


async def perform_deduction(news_content: str, kuzu_conn: Any) -> Dict[str, Any]:
    """Full Graph-Grounded Deduction pipeline with fallback and confidence boost."""
    _ensure_backend_on_path()

    # Step 1 – Extract entities
    entities = await extract_entities_from_text(news_content)
    logger.info("Extracted entities for deduction: %s", entities)

    # Step 2 – Get graph context from KuzuDB
    graph_context = get_graph_context(kuzu_conn, entities)
    path_count = graph_context.count("\n") + 1 if graph_context.strip() else 0
    logger.info("GraphContext retrieved: %d paths", path_count)

    # Step 2b – Fallback logic: if graph context is empty
    if not graph_context.strip():
        graph_context = "注意：当前知识图谱库中暂无直接关联路径，请基于通用本体逻辑进行推演。"
        logger.info("GraphContext empty; using fallback instruction")

    logger.info(
        "Final graph_context length: %d chars | starts with: %s",
        len(graph_context),
        graph_context[:80],
    )

    # Step 3 – Build LLM service
    try:
        from app.api.routes.analysis import _get_llm_service
        llm_service = _get_llm_service()
    except Exception as exc:
        logger.warning("Could not obtain LLM service: %s", exc)
        class _StubLLM:
            def call(self, **kwargs: Any) -> str:
                return "{}"
        llm_service = _StubLLM()

    # Step 4 – Run OntologyGroundedAnalyzer
    from intelligence.grounded_analyzer import OntologyGroundedAnalyzer
    try:
        analyzer = OntologyGroundedAnalyzer(
            llm_service=llm_service,
            kuzu_conn=kuzu_conn,
        )
        result = analyzer.analyze_with_ontological_grounding(
            news_fragment=news_content,
            seed_entities=entities if entities else ["系统要素"],
            claim="此事件对现有秩序及相关实体的潜在连锁影响是什么？",
        )

        deduction: Dict[str, Any] = result.get("deduction_result", {})

        # Step 5 – Confidence boost based on graph evidence richness
        evidence_boost = 0
        if graph_context.startswith("事实:") or graph_context.startswith("推演:"):
            evidence_boost = 20
            logger.info("Graph evidence detected; applying +%d%% confidence boost", evidence_boost)

        current_conf = deduction.get("confidence", 0.5)
        boosted_conf = min(0.95, current_conf + (evidence_boost / 100.0))
        deduction["confidence"] = boosted_conf

        # Attach graph evidence for frontend display
        deduction["graph_evidence"] = graph_context
        logger.info("Deduction completed with confidence: %.2f", boosted_conf)
        return deduction

    except Exception as e:
        logger.error("Deduction failed: %s", e)
        return {
            "driving_factor": "系统暂时无法提取驱动因素",
            "scenario_alpha": "推演引擎响应异常",
            "scenario_beta": "请检查后端日志",
            "verification_gap": str(e),
            "confidence": 0.0,
            "graph_evidence": ""
        }
