"""
Ontology-Grounded Analysis

LLM 推理必须以本体路径为前提，而非原始文本。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class GroundedAnalysisPrompt:
    """LLM prompt that includes ontological context as an absolute premise."""

    ontological_premise: str
    news_fragment: str
    analysis_claim: str

    def to_llm_prompt(self) -> str:
        """Convert to LLM prompt with ontological grounding."""
        return (
            "你是一个本体推理专家。\n\n"
            "【绝对前提：已验证的本体路径】\n"
            f"{self.ontological_premise}\n\n"
            "【新信息】\n"
            f"{self.news_fragment}\n\n"
            "【分析任务】\n"
            "基于上述本体前提，分析以下命题的合理性：\n"
            f"{self.analysis_claim}\n\n"
            "要求：\n"
            "1. 首先说明新信息如何与已知本体路径相符（或冲突）\n"
            "2. 如果冲突，指出矛盾点\n"
            "3. 基于本体路径给出 0.0-1.0 的可信度评分\n"
            "4. 说明需要什么额外信息来验证新信息\n"
        )


class OntologyGroundedAnalyzer:
    """Analyzer that always grounds LLM reasoning in the knowledge graph."""

    def __init__(
        self,
        llm_service: Any,
        kuzu_conn: Any,
        sacred_sword_analyzer: Optional[Any] = None,
    ) -> None:
        """Initialise with ontology-aware components.

        Args:
            llm_service:           Any object with a ``call(prompt, **kwargs)`` method.
            kuzu_conn:             Open ``kuzu.Connection`` instance.
            sacred_sword_analyzer: Optional existing analyzer for extra context.
        """
        self.llm = llm_service
        self.kuzu = kuzu_conn
        self.analyzer = sacred_sword_analyzer

        # Import here to keep the dependency on kuzu_context_extractor localised
        # so the module can be imported even in environments without KuzuDB.
        from ontology.kuzu_context_extractor import KuzuContextExtractor

        self.context_extractor = KuzuContextExtractor(kuzu_conn)

    def analyze_with_ontological_grounding(
        self,
        news_fragment: str,
        seed_entities: List[str],
        claim: str,
    ) -> Dict[str, Any]:
        """Analyze news grounded in ontology.

        Pipeline:
        1. Extract ontological context for every seed entity (1-hop + 2-hop).
        2. Build a grounded LLM prompt that contains the ontological premise.
        3. Call the LLM and return the grounded result.

        Args:
            news_fragment:  Raw news text to analyse.
            seed_entities:  List of entity names to ground the analysis on.
            claim:          The claim / hypothesis to evaluate.

        Returns:
            Dictionary with status, ontological grounding metadata, LLM response,
            and a timestamp.
        """
        # Step 1: extract ontological context per entity
        ontological_premises: Dict[str, str] = {}
        for entity in seed_entities:
            try:
                from ontology.kuzu_context_extractor import get_ontological_context

                context = get_ontological_context(self.kuzu, entity)
                ontological_premises[entity] = context
                logger.info("Extracted ontological context for: %s", entity)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to extract context for %s: %s", entity, exc)
                ontological_premises[entity] = ""

        # Step 2: build grounded prompt
        combined_premise = "\n".join(ontological_premises.values())
        grounded_prompt = GroundedAnalysisPrompt(
            ontological_premise=combined_premise,
            news_fragment=news_fragment,
            analysis_claim=claim,
        )

        # Step 3: call LLM
        llm_response = self.llm.call(
            grounded_prompt.to_llm_prompt(),
            temperature=0.3,
            max_tokens=1000,
        )

        # Step 4: return grounded result
        return {
            "status": "success",
            "ontological_grounding": {
                "seed_entities": seed_entities,
                "premises": ontological_premises,
                "total_paths_extracted": sum(
                    len(p.splitlines()) for p in ontological_premises.values()
                ),
            },
            "llm_grounded_analysis": llm_response,
            "timestamp": datetime.now().isoformat(),
        }
