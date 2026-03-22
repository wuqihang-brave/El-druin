"""Multi-agent prediction orchestrator."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class HistoricalContext:
    """Historical context retrieved to support a prediction.

    Attributes:
        similar_events: List of historically similar event summaries.
        patterns: Identified recurring patterns.
        precedents: Documented historical precedents.
    """

    similar_events: list[dict] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    precedents: list[str] = field(default_factory=list)


@dataclass
class Scenario:
    """Alternative future scenario.

    Attributes:
        title: Short scenario title.
        description: Narrative description.
        probability: Estimated probability [0.0, 1.0].
        key_drivers: Factors that would drive this scenario.
        timeline: Expected time to materialise.
    """

    title: str
    description: str
    probability: float
    key_drivers: list[str] = field(default_factory=list)
    timeline: str = "unknown"


@dataclass
class AccuracyMetrics:
    """Historical accuracy metrics for a prediction type.

    Attributes:
        prediction_type: The type evaluated.
        total_predictions: Total historical predictions of this type.
        correct: Number that were accurate.
        accuracy_rate: Fraction correct.
        avg_confidence: Mean confidence of predictions.
        calibration_score: Calibration quality (ECE).
    """

    prediction_type: str
    total_predictions: int = 0
    correct: int = 0
    accuracy_rate: float = 0.0
    avg_confidence: float = 0.0
    calibration_score: float = 0.0


@dataclass
class PredictionResult:
    """Full multi-agent prediction result.

    Attributes:
        prediction_id: Unique prediction identifier.
        final_prediction: Synthesized narrative prediction.
        confidence: Consensus confidence score.
        agent_results: Per-agent result dicts.
        consensus: ConsensusResult instance.
        scenarios: Generated alternative scenarios.
        historical_context: Historical context used.
    """

    prediction_id: str
    final_prediction: str
    confidence: float
    agent_results: list[Any] = field(default_factory=list)
    consensus: Optional[Any] = None
    scenarios: list[Scenario] = field(default_factory=list)
    historical_context: Optional[HistoricalContext] = None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class PredictionOrchestrator:
    """Multi-agent prediction orchestrator.

    Runs all five intelligence agents concurrently, then feeds their
    results through the :class:`ConsensusEngine` to produce a unified
    prediction.

    Args:
        settings: Application settings instance.

    Attributes:
        _agents: Lazily initialised list of agent instances.
        _consensus_engine: ConsensusEngine instance.
    """

    def __init__(self) -> None:
        self._agents: Optional[list] = None
        self._consensus_engine: Optional[Any] = None

    # ------------------------------------------------------------------
    # Lazy initialisation
    # ------------------------------------------------------------------

    def _get_agents(self) -> list:
        """Lazily construct and return the list of agents."""
        if self._agents is None:
            from app.config import settings as _settings
            from app.agents.historical_analyst import HistoricalAnalystAgent
            from app.agents.causal_analyst import CausalAnalystAgent
            from app.agents.social_sentiment_agent import SocialSentimentAgent
            from app.agents.economic_agent import EconomicAgent
            from app.agents.geopolitical_agent import GeopoliticalAgent

            self._agents = [
                HistoricalAnalystAgent(_settings),
                CausalAnalystAgent(_settings),
                SocialSentimentAgent(_settings),
                EconomicAgent(_settings),
                GeopoliticalAgent(_settings),
            ]
        return self._agents

    def _get_consensus_engine(self) -> Any:
        if self._consensus_engine is None:
            from app.agents.consensus_engine import ConsensusEngine

            self._consensus_engine = ConsensusEngine()
        return self._consensus_engine

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def predict(
        self,
        event_data: dict,
        prediction_type: str,
    ) -> PredictionResult:
        """Run multi-agent analysis and produce a consensus prediction.

        Args:
            event_data: Event dict to analyse.
            prediction_type: Type of prediction requested.

        Returns:
            :class:`PredictionResult` with per-agent results and consensus.
        """
        import uuid

        prediction_id = str(uuid.uuid4())
        context = await self._get_historical_context(event_data)

        agent_results = await self._run_agents_parallel(
            event_data, {"prediction_type": prediction_type, "context": context}
        )

        consensus = self._get_consensus_engine().get_consensus(agent_results)

        return PredictionResult(
            prediction_id=prediction_id,
            final_prediction=consensus.final_prediction,
            confidence=consensus.consensus_confidence,
            agent_results=agent_results,
            consensus=consensus,
            historical_context=context,
        )

    async def _run_agents_parallel(
        self, event_data: dict, context: dict
    ) -> list:
        """Run all agents concurrently with asyncio.gather.

        Args:
            event_data: Event dict.
            context: Shared context passed to each agent.

        Returns:
            List of :class:`AgentResult` instances (errors are excluded).
        """
        agents = self._get_agents()
        tasks = [
            agent.analyze(event_data, context) for agent in agents
        ]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        results = []
        for agent, result in zip(agents, raw_results):
            if isinstance(result, Exception):
                logger.error(
                    "Agent %s failed: %s",
                    agent.get_agent_type(),
                    result,
                )
            else:
                results.append(result)
        return results

    async def _get_historical_context(
        self, event_data: dict
    ) -> HistoricalContext:
        """Retrieve historical context relevant to the event.

        Args:
            event_data: Event dict.

        Returns:
            :class:`HistoricalContext` populated with similar events.
        """
        try:
            from app.core.embeddings import embedding_engine
            from app.db.pinecone_client import pinecone_client

            embedding = await embedding_engine.encode_event(event_data)
            matches = await pinecone_client.query_similar(embedding, top_k=5)
            similar = [
                {"id": m["id"], "score": m["score"], "metadata": m["metadata"]}
                for m in matches
            ]
            return HistoricalContext(similar_events=similar)
        except Exception as exc:
            logger.warning("Could not fetch historical context: %s", exc)
            return HistoricalContext()

    async def generate_scenarios(
        self,
        prediction_id: str,
        num_scenarios: int = 3,
    ) -> list[Scenario]:
        """Generate alternative future scenarios for a prediction.

        Args:
            prediction_id: Reference prediction ID.
            num_scenarios: Number of scenarios to generate.

        Returns:
            List of :class:`Scenario` instances.
        """
        scenarios = [
            Scenario(
                title="Optimistic Scenario",
                description="Diplomatic resolution leads to de-escalation.",
                probability=0.35,
                key_drivers=["international mediation", "economic incentives"],
                timeline="30d",
            ),
            Scenario(
                title="Status Quo Scenario",
                description="Situation remains stable with no significant change.",
                probability=0.45,
                key_drivers=["political inertia", "strategic ambiguity"],
                timeline="90d",
            ),
            Scenario(
                title="Pessimistic Scenario",
                description="Escalation leading to broader conflict.",
                probability=0.20,
                key_drivers=["nationalist pressure", "resource scarcity"],
                timeline="60d",
            ),
        ]
        return scenarios[:num_scenarios]

    async def get_accuracy_metrics(
        self, prediction_type: str
    ) -> AccuracyMetrics:
        """Return historical accuracy metrics for a prediction type.

        Args:
            prediction_type: Prediction type string.

        Returns:
            :class:`AccuracyMetrics` populated from stored data (stub).
        """
        # In production this would query the predictions table
        return AccuracyMetrics(
            prediction_type=prediction_type,
            total_predictions=0,
            correct=0,
            accuracy_rate=0.0,
            avg_confidence=0.0,
            calibration_score=0.0,
        )


# Module-level singleton
prediction_orchestrator = PredictionOrchestrator()
