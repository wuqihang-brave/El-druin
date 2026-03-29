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

try:
    from ontology.kuzu_context_extractor import get_ontological_context as _get_ontological_context  # type: ignore
except ImportError:
    _get_ontological_context = None  # type: ignore[assignment]


# ═════════════════════════════════════════════════════════════════════
# Main Analyzer: OntologyGroundedAnalyzer with Deduction Soul
# ════════════════════════════════════════════════════════════════════
class OntologyGroundedAnalyzer:
    """
    分析器的本体感知版本：现在配备推演灵魂

    Combines KuzuDB path extraction with DeductionEngine to produce
    strictly ontology-grounded scenario analysis.
    """
    def __init__(
        self,
        llm_service: Any,
        kuzu_conn: Any = None,
        sacred_sword_analyzer: Any = None,
        entity_extractor: Any = None   # 支持外部注入实体抽取器（可选）
    ) -> None:
        self.llm = llm_service
        self.kuzu = kuzu_conn
        self.analyzer = sacred_sword_analyzer

        # 实体抽取器注入点：如外部未注入则自动按标准依赖引入（兜底）
        if entity_extractor is not None:
            self.entity_extractor = entity_extractor
        else:
            try:
                from intelligence.entity_extraction import EntityExtractionEngine
                # 此处用本地 LLM（如果需要 LLM 调用可按需求调整参数）
                self.entity_extractor = EntityExtractionEngine()
            except Exception as exc:
                self.entity_extractor = None
                logger.error(f"无法实例化 EntityExtractionEngine: {exc}")

        # 注入推演灵魂
        from intelligence.deduction_engine import DeductionEngine
        self.deduction_engine = DeductionEngine(llm_service)

    def analyze_with_ontological_grounding(
        self,
        news_fragment: str,
        seed_entities: List[str],
        claim: str,
    ) -> Dict[str, Any]:
        """
        【MAIN METHOD】Detect empty seed_entities, auto NER if needed, then run normal chain
        """
        logger.info("======== OntologyGroundedAnalyzer 调用追踪 ========")
        logger.info("输入 news_fragment: %s", news_fragment)
        logger.info("输入 seed_entities: %s", seed_entities)
        logger.info("输入 claim: %s", claim)

        # ====== 步骤1：兜底实体补全 ======
        if not seed_entities:
            logger.warning("seed_entities 为空！自动触发实体抽取兜底。")
            if self.entity_extractor is not None:
                try:
                    # 如你的抽取器需要第二个参数（task名），可按需添加
                    # entities = self.entity_extractor.extract(news_fragment, "sacred_sword_analysis")
                    entities = self.entity_extractor.extract(news_fragment)
                    # 自动兼容对象或字典返回
                    if isinstance(entities, list):
                        # 如果结果为实体对象或字典列表
                        temp_seed = []
                        for ent in entities:
                            # 对象型
                            if hasattr(ent, 'name'):
                                temp_seed.append(ent.name)
                            # 字典型
                            elif isinstance(ent, dict) and "name" in ent:
                                temp_seed.append(ent["name"])
                        seed_entities = [e for e in temp_seed if e]
                    elif isinstance(entities, dict) and "entities" in entities:
                        temp_seed = []
                        for ent in entities["entities"]:
                            if isinstance(ent, dict) and "name" in ent:
                                temp_seed.append(ent["name"])
                            elif hasattr(ent, 'name'):
                                temp_seed.append(ent.name)
                        seed_entities = [e for e in temp_seed if e]
                    logger.info(f"兜底提取完成，获得实体: {seed_entities}")
                except Exception as exc:
                    logger.exception(f"实体抽取兜底失败: {exc}")
            else:
                logger.error("未能注入 entity_extractor，无法自动补全 seed_entities！")

        # ====== 后续原有流程 ======
        logger.info("Processing news with ontological grounding: %s...", news_fragment[:100])

        ontological_premises: Dict[str, str] = {}
        if _get_ontological_context is None:
            logger.warning("ontology.kuzu_context_extractor not importable; skipping graph context")

        for entity in seed_entities:
            try:
                if _get_ontological_context is not None:
                    context = _get_ontological_context(self.kuzu, entity)
                else:
                    context = ""
                ontological_premises[entity] = context
                logger.info("Extracted ontological context for: %s", entity)
            except Exception as exc:
                logger.error("Failed to extract context for %s: %s", entity, exc)
                ontological_premises[entity] = ""

        combined_premise = "\n".join(ctx for ctx in ontological_premises.values() if ctx)
        logger.info("每个实体的本体context（行数/长度）: %s", {k: len(v.splitlines()) for k, v in ontological_premises.items()})
        for entity, ctx in ontological_premises.items():
            logger.debug("实体[%s]本体context示例: %s...", entity, ctx[:150])
        logger.info("合并后总本体context长度: %d", len(combined_premise))
        if not combined_premise.strip():
            logger.error("⚠️ context=0：本体context合并后为空，请检查seed_entities与数据库中的实体路径是否匹配！")
        logger.info("Activating Deduction Soul for logical inference...")

        try:
            deduction_result = self.deduction_engine.deduce_from_ontological_paths(
                news_summary=news_fragment[:200],
                ontological_context=combined_premise,
                seed_entities=seed_entities,
            )
            deduction_result.graph_evidence = combined_premise
        except Exception as exc:
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
        logger.info("======== OntologyGroundedAnalyzer 调用追踪 ========")
        logger.info("输入 news_fragment: %s", news_fragment)
        logger.info("输入 seed_entities: %s", seed_entities)
        logger.info("输入 claim: %s", claim)
        logger.info(
            "Processing news with ontological grounding: %s...",
            news_fragment[:100]
        )

        # Step 1: Extract ontological context for each seed entity
        ontological_premises: Dict[str, str] = {}

        if _get_ontological_context is None:
            logger.warning("ontology.kuzu_context_extractor not importable; skipping graph context")

        for entity in seed_entities:
            try:
                if _get_ontological_context is not None:
                    context = _get_ontological_context(self.kuzu, entity)
                else:
                    context = ""
                ontological_premises[entity] = context
                logger.info("Extracted ontological context for: %s", entity)
            except Exception as exc:
                logger.error("Failed to extract context for %s: %s", entity, exc)
                ontological_premises[entity] = ""

        # Step 2: 【激活推演灵魂】Activate Deduction Soul
        combined_premise = "\n".join(
            ctx for ctx in ontological_premises.values() if ctx
        )
        logger.info("每个实体的本体context（行数/长度）: %s", 
            {k: len(v.splitlines()) for k, v in ontological_premises.items()})
        for entity, ctx in ontological_premises.items():
            logger.debug("实体[%s]本体context示例: %s...", entity, ctx[:150])
        combined_premise = "\n".join(
            ctx for ctx in ontological_premises.values() if ctx
        )
        logger.info("合并后总本体context长度: %d", len(combined_premise))
        if not combined_premise.strip():
            logger.error("⚠️ context=0：本体context合并后为空，请检查seed_entities与数据库中的实体路径是否匹配！")
        logger.info("Activating Deduction Soul for logical inference...")

        try:
            deduction_result = self.deduction_engine.deduce_from_ontological_paths(
                news_summary=news_fragment[:200],
                ontological_context=combined_premise,
                seed_entities=seed_entities,
            )
            # Attach raw GraphContext so callers can expose it as graph_evidence
            deduction_result.graph_evidence = combined_premise
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