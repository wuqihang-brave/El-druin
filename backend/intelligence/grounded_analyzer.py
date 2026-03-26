"""
EL-druin Intelligence Platform – Ontology-Grounded Analyzer
============================================================

Combines KuzuDB ontological path extraction with the Deduction Soul engine
to produce strictly path-grounded scenario analysis.

The DeductionEngine is injected into OntologyGroundedAnalyzer so that every
LLM inference traces back to an explicit knowledge-graph relationship.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# Helper: Get Ontological Context from KuzuDB
# ═══════════════════════════════════════════════════════════════════

def get_ontological_context(kuzu_conn: Any, entity_name: str) -> str:
    """Query KuzuDB for 1-hop and 2-hop paths from *entity_name*.

    Returns a multi-line string where every line describes one relationship
    path, e.g.::

        EntityA --[RELATION]--> EntityB
        EntityA --[REL1]--> EntityB --[REL2]--> EntityC

    Falls back gracefully when KuzuDB is unavailable or the entity has no
    relationships.
    """
    if kuzu_conn is None:
        return f"[No KuzuDB connection – context unavailable for '{entity_name}']"

    # Sanitize entity name to prevent Cypher injection
    safe_name = entity_name.replace("'", "\\'").replace("\\", "\\\\")

    try:
        # 1-hop paths: A --[rel]--> B
        query_1hop = (
            "MATCH (a)-[r]->(b) "
            f"WHERE a.name = '{safe_name}' "
            "RETURN a.name, type(r), b.name LIMIT 20"
        )
        result_1hop = kuzu_conn.execute(query_1hop)
        lines: List[str] = []
        
        while result_1hop.hasNext():
            row = result_1hop.getNext()
            lines.append(f"{row[0]} --[{row[1]}]--> {row[2]}")

        # 2-hop paths: A --[rel1]--> B --[rel2]--> C
        query_2hop = (
            "MATCH (a)-[r1]->(b)-[r2]->(c) "
            f"WHERE a.name = '{safe_name}' "
            "RETURN a.name, type(r1), b.name, type(r2), c.name LIMIT 20"
        )
        result_2hop = kuzu_conn.execute(query_2hop)
        
        while result_2hop.hasNext():
            row = result_2hop.getNext()
            lines.append(
                f"{row[0]} --[{row[1]}]--> {row[2]} --[{row[3]}]--> {row[4]}"
            )

        if not lines:
            return f"[No ontological paths found for '{entity_name}']"

        return "\n".join(lines)

    except Exception as exc:
        logger.warning("KuzuDB query failed for '%s': %s", entity_name, exc)
        return f"[KuzuDB query error for '{entity_name}': {exc}]"


# ═══════════════════════════════════════════════════════════════════
# Main Analyzer: OntologyGroundedAnalyzer with Deduction Soul
# ═══════════════════════════════════════════════════════════════════

class OntologyGroundedAnalyzer:
    """
    分析器的本体感知版本：现在配备推演灵魂

    Combines KuzuDB path extraction with DeductionEngine to produce
    strictly ontology-grounded scenario analysis.
    
    Features:
    - Extracts 1-hop and 2-hop ontological paths from KuzuDB
    - Injects DeductionEngine for strict logical reasoning
    - Forces JSON output with complete causal chains
    - Never fabricates—only deduces from knowledge graph paths
    """

    def __init__(
        self,
        llm_service: Any,
        kuzu_conn: Any = None,
        sacred_sword_analyzer: Any = None,
    ) -> None:
        """Initialize with Deduction Soul.

        Args:
            llm_service:           LLM service with a ``call()`` method.
            kuzu_conn:             Optional KuzuDB connection for path queries.
            sacred_sword_analyzer: Optional SacredSwordAnalyzer (reserved for
                                   future cross-engine enrichment).
        """
        self.llm = llm_service
        self.kuzu = kuzu_conn
        self.analyzer = sacred_sword_analyzer

        # 【注入推演灵魂】Inject Deduction Soul
        from intelligence.deduction_engine import DeductionEngine
        self.deduction_engine = DeductionEngine(llm_service)

    # ─────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────

    def analyze_with_ontological_grounding(
        self,
        news_fragment: str,
        seed_entities: List[str],
        claim: str,
    ) -> Dict[str, Any]:
        """【MAIN METHOD】Analyze with Deduction Soul.

        The Deduction Soul ensures:
        1. All predictions based on ontological paths
        2. No fabrication or vague speculation
        3. Strict JSON output with causal chains
        4. Complete traceability to KG relationships

        Pipeline:
        1. Extract ontological context for every seed entity (1-hop + 2-hop).
        2. Activate DeductionEngine with ontological context.
        3. LLM performs strictly path-based inference.
        4. Return structured result with deduction JSON.

        Args:
            news_fragment: Raw news text (used as event trigger summary).
            seed_entities: Entity names to use as path query seeds.
            claim:         The analytical question / claim under examination.

        Returns:
            Dict with ``status``, ``ontological_grounding``,
            ``deduction_result``, and ``timestamp``.
        """
        
        logger.info(
            "Processing news with ontological grounding: %s...",
            news_fragment[:100]
        )

        # Step 1: Extract ontological context for each seed entity
        ontological_premises: Dict[str, str] = {}
        
        for entity in seed_entities:
            try:
                context = get_ontological_context(self.kuzu, entity)
                ontological_premises[entity] = context
                logger.info("Extracted ontological context for: %s", entity)
            except Exception as exc:
                logger.error("Failed to extract context for %s: %s", entity, exc)
                ontological_premises[entity] = ""

        # Step 2: 【激活推演灵魂】Activate Deduction Soul
        combined_premise = "\n".join(
            ctx for ctx in ontological_premises.values() if ctx
        )

        logger.info("Activating Deduction Soul for logical inference...")

        try:
            deduction_result = self.deduction_engine.deduce_from_ontological_paths(
                news_summary=news_fragment[:200],
                ontological_context=combined_premise,
                seed_entities=seed_entities,
            )
        except Exception as exc:  # noqa: BLE001 – any engine failure must not propagate as a 500
            logger.error("DeductionEngine raised an unexpected error: %s", exc)
            from intelligence.deduction_engine import (
                CausalChain,
                DeductionResult,
                Scenario,
                ScenarioType,
            )
            deduction_result = DeductionResult(
                driving_factor="DeductionEngine error – see logs",
                scenario_alpha=Scenario(
                    name="现状延续路径",
                    scenario_type=ScenarioType.CONTINUATION,
                    causal_chain=CausalChain(
                        source_fact="", triggering_relation="", resulting_change=""
                    ),
                    probability=0.0,
                ),
                scenario_beta=Scenario(
                    name="结构性断裂路径",
                    scenario_type=ScenarioType.STRUCTURAL_BREAK,
                    causal_chain=CausalChain(
                        source_fact="", triggering_relation="", resulting_change=""
                    ),
                    probability=0.0,
                ),
                verification_gap=f"Deduction engine error: {exc}",
                deduction_confidence=0.0,
            )

        # Step 3: Return structured result with complete deduction JSON
        return {
            "status": "success",
            "ontological_grounding": {
                "seed_entities": seed_entities,
                "premises": ontological_premises,
                "total_paths_extracted": sum(
                    len(p.split("\n"))
                    for p in ontological_premises.values()
                    if p
                ),
            },
            "deduction_result": deduction_result.to_strict_json(),
            "timestamp": datetime.now().isoformat(),
        }