"""Multi-agent consensus engine."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.agents.base_agent import AgentResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ConsensusResult:
    """Aggregated consensus from all participating agents.

    Attributes:
        final_prediction: Synthesized narrative prediction.
        consensus_confidence: Weighted consensus confidence score.
        agreement_score: Inter-agent agreement metric [0.0, 1.0].
        dissenting_agents: Agent types with significantly different views.
        key_insights: Top insights extracted across all agents.
        uncertainty_factors: Factors introducing uncertainty.
        agent_breakdown: Per-agent confidence scores.
    """

    final_prediction: str
    consensus_confidence: float
    agreement_score: float
    dissenting_agents: list[str]
    key_insights: list[str]
    uncertainty_factors: list[str]
    agent_breakdown: dict[str, float]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class ConsensusEngine:
    """Multi-agent fusion and consensus building.

    Combines per-agent :class:`~app.agents.base_agent.AgentResult` instances
    into a single :class:`ConsensusResult` using weighted averaging and
    disagreement detection.

    Attributes:
        AGENT_WEIGHTS: Relative weights applied to each agent type.
        DISSENT_THRESHOLD: Confidence delta that flags an agent as dissenting.
    """

    AGENT_WEIGHTS: dict[str, float] = {
        "historical": 0.25,
        "causal": 0.25,
        "sentiment": 0.15,
        "economic": 0.20,
        "geopolitical": 0.15,
    }

    DISSENT_THRESHOLD: float = 0.20

    def get_consensus(
        self, agent_results: list[AgentResult]
    ) -> ConsensusResult:
        """Build a consensus result from a list of agent results.

        Args:
            agent_results: List of :class:`AgentResult` instances.

        Returns:
            :class:`ConsensusResult` with synthesized prediction and
            confidence metrics.
        """
        if not agent_results:
            return ConsensusResult(
                final_prediction="Insufficient data for prediction.",
                consensus_confidence=0.0,
                agreement_score=0.0,
                dissenting_agents=[],
                key_insights=[],
                uncertainty_factors=["No agent results available"],
                agent_breakdown={},
            )

        weighted_confidence = self._calculate_weighted_confidence(agent_results)
        agreement_score = self._calculate_agreement_score(agent_results)
        dissenting_agents = self._detect_disagreements(
            agent_results, weighted_confidence
        )
        key_insights = self._extract_key_insights(agent_results)
        uncertainty_factors = self._identify_uncertainty_factors(
            agent_results, agreement_score
        )
        final_prediction = self._resolve_conflicts(agent_results)
        agent_breakdown = {r.agent_type: r.confidence for r in agent_results}

        return ConsensusResult(
            final_prediction=final_prediction,
            consensus_confidence=round(weighted_confidence, 4),
            agreement_score=round(agreement_score, 4),
            dissenting_agents=dissenting_agents,
            key_insights=key_insights,
            uncertainty_factors=uncertainty_factors,
            agent_breakdown=agent_breakdown,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _calculate_weighted_confidence(
        self, results: list[AgentResult]
    ) -> float:
        """Compute the weighted average confidence across agents.

        Args:
            results: Agent result list.

        Returns:
            Weighted confidence score in [0.0, 1.0].
        """
        total_weight = 0.0
        weighted_sum = 0.0
        for result in results:
            weight = self.AGENT_WEIGHTS.get(result.agent_type, 0.1)
            weighted_sum += result.confidence * weight
            total_weight += weight
        if total_weight == 0:
            return 0.0
        return weighted_sum / total_weight

    def _calculate_agreement_score(
        self, results: list[AgentResult]
    ) -> float:
        """Calculate inter-agent agreement using confidence variance.

        Lower variance → higher agreement score.

        Args:
            results: Agent result list.

        Returns:
            Agreement score in [0.0, 1.0].
        """
        if len(results) < 2:
            return 1.0
        confidences = [r.confidence for r in results]
        mean = sum(confidences) / len(confidences)
        variance = sum((c - mean) ** 2 for c in confidences) / len(confidences)
        # Map variance to [0, 1] agreement (max variance ≈ 0.25 for binary opinions)
        agreement = max(0.0, 1.0 - variance * 4)
        return min(1.0, agreement)

    def _detect_disagreements(
        self,
        results: list[AgentResult],
        weighted_confidence: float,
    ) -> list[str]:
        """Identify agents whose confidence deviates significantly.

        Args:
            results: Agent result list.
            weighted_confidence: Consensus confidence to compare against.

        Returns:
            List of dissenting agent type strings.
        """
        dissenting: list[str] = []
        for result in results:
            delta = abs(result.confidence - weighted_confidence)
            if delta >= self.DISSENT_THRESHOLD:
                dissenting.append(result.agent_type)
        return dissenting

    def _extract_key_insights(
        self, results: list[AgentResult]
    ) -> list[str]:
        """Extract and deduplicate key insights from all agents.

        Args:
            results: Agent result list.

        Returns:
            Deduplicated list of insight strings (up to 10).
        """
        insights: list[str] = []
        seen: set[str] = set()
        for result in results:
            # Use the first two sentences of each agent's analysis
            analysis = result.analysis or ""
            sentences = [s.strip() for s in analysis.split(".") if len(s.strip()) > 20]
            for sentence in sentences[:2]:
                key = sentence[:60].lower()
                if key not in seen:
                    seen.add(key)
                    insights.append(f"[{result.agent_type}] {sentence}.")
        return insights[:10]

    def _identify_uncertainty_factors(
        self,
        results: list[AgentResult],
        agreement_score: float,
    ) -> list[str]:
        """Identify factors that increase prediction uncertainty.

        Args:
            results: Agent result list.
            agreement_score: Pre-computed agreement score.

        Returns:
            List of uncertainty factor strings.
        """
        factors: list[str] = []
        if agreement_score < 0.6:
            factors.append("Low inter-agent agreement")
        avg_confidence = sum(r.confidence for r in results) / max(1, len(results))
        if avg_confidence < 0.6:
            factors.append("Low average agent confidence")
        low_evidence = [r.agent_type for r in results if len(r.evidence) == 0]
        if low_evidence:
            factors.append(
                f"Missing evidence from: {', '.join(low_evidence)}"
            )
        stub_agents = [
            r.agent_type
            for r in results
            if "LLM unavailable" in r.analysis
        ]
        if stub_agents:
            factors.append(
                f"LLM unavailable for: {', '.join(stub_agents)}"
            )
        return factors

    def _resolve_conflicts(self, results: list[AgentResult]) -> str:
        """Build a synthesized prediction narrative.

        Uses the highest-weight agent's analysis as the primary narrative
        and appends a confidence summary.

        Args:
            results: Agent result list.

        Returns:
            Synthesized prediction string.
        """
        if not results:
            return "No prediction available."

        # Sort by weight then by confidence
        sorted_results = sorted(
            results,
            key=lambda r: (
                self.AGENT_WEIGHTS.get(r.agent_type, 0.1),
                r.confidence,
            ),
            reverse=True,
        )

        primary = sorted_results[0]
        narrative = primary.analysis or "Analysis pending."
        avg_conf = sum(r.confidence for r in results) / len(results)

        return (
            f"{narrative}\n\n"
            f"[Consensus: avg confidence {avg_conf:.0%} across "
            f"{len(results)} agents]"
        )
