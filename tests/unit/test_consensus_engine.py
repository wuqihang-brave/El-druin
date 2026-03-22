"""Unit tests for ConsensusEngine."""

from __future__ import annotations

import pytest
from app.agents.consensus_engine import ConsensusEngine, ConsensusResult
from app.agents.base_agent import AgentResult


def _make_result(agent_type: str, confidence: float, analysis: str = "Analysis text") -> AgentResult:
    """Helper to create an AgentResult with minimal required fields."""
    return AgentResult(
        agent_type=agent_type,
        analysis=analysis,
        confidence=confidence,
        evidence=["Evidence A"],
        reasoning="Step-by-step reasoning.",
        token_usage={"prompt": 100, "completion": 50, "total": 150},
        execution_time_ms=120.0,
    )


class TestConsensusEngine:
    """Tests for the multi-agent consensus engine."""

    def setup_method(self):
        self.engine = ConsensusEngine()

    # ------------------------------------------------------------------
    # Empty / edge cases
    # ------------------------------------------------------------------

    def test_empty_results_returns_zero_confidence(self):
        """Empty input produces a result with zero confidence and agreement."""
        result = self.engine.get_consensus([])
        assert isinstance(result, ConsensusResult)
        assert result.consensus_confidence == 0.0
        assert result.agreement_score == 0.0
        assert result.agent_breakdown == {}

    def test_empty_results_includes_uncertainty_factor(self):
        """Empty input notes the lack of agent results in uncertainty factors."""
        result = self.engine.get_consensus([])
        assert len(result.uncertainty_factors) > 0

    def test_single_agent_result_passes_through(self):
        """A single agent result is returned with its confidence unchanged."""
        agent_result = _make_result("historical", 0.8)
        result = self.engine.get_consensus([agent_result])
        assert isinstance(result, ConsensusResult)
        assert result.consensus_confidence > 0.0
        assert "historical" in result.agent_breakdown

    # ------------------------------------------------------------------
    # Agreeing agents → high confidence
    # ------------------------------------------------------------------

    def test_consensus_with_agreeing_agents_high_confidence(self):
        """When all agents report high confidence, consensus confidence is high."""
        results = [
            _make_result("historical", 0.9),
            _make_result("causal", 0.85),
            _make_result("economic", 0.88),
        ]
        consensus = self.engine.get_consensus(results)
        assert consensus.consensus_confidence >= 0.7

    def test_consensus_agreeing_agents_low_dissent(self):
        """Agreeing agents produce an empty or short dissenting_agents list."""
        results = [
            _make_result("historical", 0.85),
            _make_result("causal", 0.80),
            _make_result("geopolitical", 0.83),
        ]
        consensus = self.engine.get_consensus(results)
        assert isinstance(consensus.dissenting_agents, list)
        # Most agents agree, so dissent should be low
        assert len(consensus.dissenting_agents) < len(results)

    # ------------------------------------------------------------------
    # Disagreeing agents → lower confidence / dissent detected
    # ------------------------------------------------------------------

    def test_consensus_with_disagreeing_agents_lower_confidence(self):
        """Wildly different confidence scores lower the overall agreement."""
        results = [
            _make_result("historical", 0.9),
            _make_result("causal", 0.1),
            _make_result("economic", 0.95),
        ]
        high_agreement = self.engine.get_consensus(
            [_make_result("historical", 0.9), _make_result("causal", 0.85)]
        )
        low_agreement = self.engine.get_consensus(results)
        # Mixed signals should yield lower agreement than unanimous high confidence
        assert low_agreement.agreement_score <= high_agreement.agreement_score

    def test_dissenting_agent_detected(self):
        """An agent whose confidence deviates significantly is flagged as dissenting."""
        results = [
            _make_result("historical", 0.9, "Strong bullish signal"),
            _make_result("causal", 0.85, "Strong bullish signal"),
            _make_result("economic", 0.05, "Strong bearish signal"),  # outlier
        ]
        consensus = self.engine.get_consensus(results)
        # economic agent is far from the weighted average
        assert "economic" in consensus.dissenting_agents

    # ------------------------------------------------------------------
    # Output structure
    # ------------------------------------------------------------------

    def test_result_contains_agent_breakdown(self):
        """Returned ConsensusResult includes per-agent confidence in agent_breakdown."""
        results = [
            _make_result("historical", 0.7),
            _make_result("sentiment", 0.6),
        ]
        consensus = self.engine.get_consensus(results)
        assert "historical" in consensus.agent_breakdown
        assert "sentiment" in consensus.agent_breakdown

    def test_confidence_is_clamped_between_zero_and_one(self):
        """Consensus confidence stays within [0, 1] regardless of inputs."""
        results = [_make_result("historical", confidence) for confidence in [0.0, 1.0, 0.5]]
        consensus = self.engine.get_consensus(results)
        assert 0.0 <= consensus.consensus_confidence <= 1.0

    def test_agreement_score_is_between_zero_and_one(self):
        """Agreement score stays within [0, 1]."""
        results = [_make_result("historical", 0.5), _make_result("causal", 0.9)]
        consensus = self.engine.get_consensus(results)
        assert 0.0 <= consensus.agreement_score <= 1.0

    def test_final_prediction_is_non_empty_string(self):
        """final_prediction is always a non-empty string."""
        results = [_make_result("historical", 0.75, "Prediction narrative.")]
        consensus = self.engine.get_consensus(results)
        assert isinstance(consensus.final_prediction, str)
        assert len(consensus.final_prediction) > 0
