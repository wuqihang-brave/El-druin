"""
Central Processor: Orchestrate ontology-grounded analysis pipeline

新闻处理流程：
1. 提取新闻中的关键实体
2. 从 KuzuDB 获取本体上下文
3. 将本体上下文作为前提传给 LLM
4. LLM 基于本体进行推理
5. 返回有前提支撑的分析结果
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class NewsProcessorWithOntology:
    """Core news processor that grounds all analysis in ontology."""

    def __init__(
        self,
        llm_service: Any,
        kuzu_conn: Any,
        entity_extractor: Any,
        grounded_analyzer: Any,
    ) -> None:
        """Initialise processor with all required components.

        Args:
            llm_service:       LLM service with a ``call`` method.
            kuzu_conn:         Open ``kuzu.Connection`` instance.
            entity_extractor:  Engine with an ``extract(text, request_id)`` method
                               that returns a list of ``OntologicalEntity`` objects.
            grounded_analyzer: ``OntologyGroundedAnalyzer`` instance.
        """
        self.llm = llm_service
        self.kuzu = kuzu_conn
        self.extractor = entity_extractor
        self.grounded_analyzer = grounded_analyzer

    def process_news(self, news_fragment: str, claim: str) -> Dict[str, Any]:
        """Run the full ontology-grounded news processing pipeline.

        Steps:
        1. Extract key entities with three-layer labels.
        2. For each entity, extract ontological context (1-hop + 2-hop).
        3. Run ontology-grounded analysis.
        4. Return a result dict with all extracted information.

        Args:
            news_fragment: Raw news text.
            claim:         Claim / hypothesis to evaluate against the news.

        Returns:
            Dictionary containing extracted entities, ontological grounding,
            LLM analysis, and metadata.
        """
        logger.info("Processing news: %s...", news_fragment[:100])

        # STEP 1: Extract entities with three-layer labels
        logger.info("Step 1: Extracting entities…")
        request_id = f"process_news_{datetime.now().timestamp()}"
        entities = self.extractor.extract(news_fragment, request_id)
        entity_names: List[str] = [e.name for e in entities]
        logger.info("Extracted %d entities: %s", len(entity_names), entity_names)

        # STEP 2: Analyse with ontological grounding
        logger.info("Step 2: Running ontology-grounded analysis…")
        analysis_result = self.grounded_analyzer.analyze_with_ontological_grounding(
            news_fragment=news_fragment,
            seed_entities=entity_names,
            claim=claim,
        )

        # STEP 3: Compile final result
        final_result: Dict[str, Any] = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "news_fragment": news_fragment[:200],
            "claim": claim,
            "entities_extracted": {
                "count": len(entities),
                "entities": [
                    {
                        "name": e.name,
                        "type": e.physical_type,
                        "role": e.structural_roles,
                        "virtue": e.philosophical_nature,
                    }
                    for e in entities
                ],
            },
            "ontological_grounding": analysis_result["ontological_grounding"],
            "analysis": {
                "llm_response": analysis_result["llm_grounded_analysis"][:500],
                "overall_confidence": 0.8,  # Placeholder
            },
        }

        logger.info("News processing complete.")
        return final_result
