"""
tests/test_delta_engine.py
==========================

Tests for backend/app/services/delta_engine.py

Validates all acceptance criteria from PR-8:
- First-run returns stable delta with empty change lists
- regime_changed True when regimes differ
- threshold_direction "narrowing" / "widening" / "stable" computed correctly
- trigger_ranking_changes populated when rank changes
- attractor_pull_changes populated when pull_strength changes > 0.05
- summary is a non-empty string using PRD vocabulary
- No banned model notation in any output string
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone

import pytest

# Make backend importable when running from repo root
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.services.delta_engine import AssessmentSnapshot, DeltaEngine  # noqa: E402
from app.schemas.structural_forecast import DeltaField, DeltaOutput  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


def _make_snapshot(**overrides) -> AssessmentSnapshot:
    """Return a minimal AssessmentSnapshot with sensible defaults."""
    defaults = dict(
        assessment_id="ae-test",
        regime="Stress Accumulation",
        threshold_distance=0.45,
        damping_capacity=0.60,
        confidence=0.70,
        trigger_rankings=[
            {"name": "Formal Attribution", "rank": 1, "amplification_factor": 0.80},
            {"name": "Sanctions Coordination", "rank": 2, "amplification_factor": 0.65},
        ],
        attractor_rankings=[
            {"name": "Sanctions Cascade", "rank": 1, "pull_strength": 0.72},
            {"name": "Proxy Escalation", "rank": 2, "pull_strength": 0.55},
        ],
        evidence_count=4,
        captured_at=datetime(2026, 4, 10, 0, 0, 0, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return AssessmentSnapshot(**defaults)


# Banned vocabulary – must never appear in any output string
_BANNED_TERMS = [
    "bayesian p=",
    "sigma",
    "manifold",
    "generator",
    "commutator",
    "p=",
    "σ",
]


def _assert_no_banned_terms(text: str) -> None:
    low = text.lower()
    for term in _BANNED_TERMS:
        assert term not in low, f"Banned term '{term}' found in: {text!r}"


# ---------------------------------------------------------------------------
# DeltaEngine – import and instantiation
# ---------------------------------------------------------------------------

class TestDeltaEngineImport:
    def test_importable(self):
        assert DeltaEngine is not None

    def test_instantiate_no_args(self):
        engine = DeltaEngine()
        assert engine is not None

    def test_snapshot_store_initially_empty(self):
        engine = DeltaEngine()
        assert engine._snapshot_store == {}


# ---------------------------------------------------------------------------
# First-run behaviour
# ---------------------------------------------------------------------------

class TestFirstRun:
    def test_first_run_returns_delta_output(self):
        engine = DeltaEngine()
        snap = _make_snapshot()
        result = _run(engine.compute_delta("ae-test", snap))
        assert isinstance(result, DeltaOutput)

    def test_first_run_regime_changed_false(self):
        engine = DeltaEngine()
        snap = _make_snapshot()
        result = _run(engine.compute_delta("ae-test", snap))
        assert result.regime_changed is False

    def test_first_run_threshold_direction_stable(self):
        engine = DeltaEngine()
        snap = _make_snapshot()
        result = _run(engine.compute_delta("ae-test", snap))
        assert result.threshold_direction == "stable"

    def test_first_run_trigger_changes_empty(self):
        engine = DeltaEngine()
        snap = _make_snapshot()
        result = _run(engine.compute_delta("ae-test", snap))
        assert result.trigger_ranking_changes == []

    def test_first_run_attractor_changes_empty(self):
        engine = DeltaEngine()
        snap = _make_snapshot()
        result = _run(engine.compute_delta("ae-test", snap))
        assert result.attractor_pull_changes == []

    def test_first_run_numeric_deltas_zero(self):
        engine = DeltaEngine()
        snap = _make_snapshot()
        result = _run(engine.compute_delta("ae-test", snap))
        assert result.damping_capacity_delta == 0.0
        assert result.confidence_delta == 0.0
        assert result.new_evidence_count == 0

    def test_first_run_summary_contains_first_assessment(self):
        engine = DeltaEngine()
        snap = _make_snapshot()
        result = _run(engine.compute_delta("ae-test", snap))
        assert "First assessment run" in result.summary

    def test_first_run_records_snapshot(self):
        engine = DeltaEngine()
        snap = _make_snapshot()
        _run(engine.compute_delta("ae-test", snap))
        assert "ae-test" in engine._snapshot_store


# ---------------------------------------------------------------------------
# regime_changed
# ---------------------------------------------------------------------------

class TestRegimeChanged:
    def test_regime_changed_true_when_regimes_differ(self):
        engine = DeltaEngine()
        prior = _make_snapshot(regime="Stress Accumulation")
        current = _make_snapshot(regime="Nonlinear Escalation")
        _run(engine.compute_delta("ae-test", prior))
        result = _run(engine.compute_delta("ae-test", current))
        assert result.regime_changed is True

    def test_regime_changed_false_when_same(self):
        engine = DeltaEngine()
        snap1 = _make_snapshot(regime="Linear")
        snap2 = _make_snapshot(regime="Linear")
        _run(engine.compute_delta("ae-test", snap1))
        result = _run(engine.compute_delta("ae-test", snap2))
        assert result.regime_changed is False

    def test_regime_changed_correct_assessment_id(self):
        engine = DeltaEngine()
        snap_a1 = _make_snapshot(assessment_id="ae-A", regime="Linear")
        snap_b1 = _make_snapshot(assessment_id="ae-B", regime="Cascade Risk")
        snap_a2 = _make_snapshot(assessment_id="ae-A", regime="Stress Accumulation")
        _run(engine.compute_delta("ae-A", snap_a1))
        _run(engine.compute_delta("ae-B", snap_b1))
        result = _run(engine.compute_delta("ae-A", snap_a2))
        assert result.regime_changed is True


# ---------------------------------------------------------------------------
# threshold_direction
# ---------------------------------------------------------------------------

class TestThresholdDirection:
    def test_narrowing_when_distance_decreases_more_than_band(self):
        engine = DeltaEngine()
        prior = _make_snapshot(threshold_distance=0.50)
        current = _make_snapshot(threshold_distance=0.47)  # delta = -0.03 → narrowing
        _run(engine.compute_delta("ae-test", prior))
        result = _run(engine.compute_delta("ae-test", current))
        assert result.threshold_direction == "narrowing"

    def test_widening_when_distance_increases_more_than_band(self):
        engine = DeltaEngine()
        prior = _make_snapshot(threshold_distance=0.50)
        current = _make_snapshot(threshold_distance=0.53)  # delta = +0.03 → widening
        _run(engine.compute_delta("ae-test", prior))
        result = _run(engine.compute_delta("ae-test", current))
        assert result.threshold_direction == "widening"

    def test_stable_when_change_within_band(self):
        engine = DeltaEngine()
        prior = _make_snapshot(threshold_distance=0.50)
        current = _make_snapshot(threshold_distance=0.51)  # delta = +0.01 → stable
        _run(engine.compute_delta("ae-test", prior))
        result = _run(engine.compute_delta("ae-test", current))
        assert result.threshold_direction == "stable"

    def test_stable_when_exactly_at_band_boundary(self):
        engine = DeltaEngine()
        prior = _make_snapshot(threshold_distance=0.50)
        current = _make_snapshot(threshold_distance=0.52)  # delta = +0.02 → stable (not strict >)
        _run(engine.compute_delta("ae-test", prior))
        result = _run(engine.compute_delta("ae-test", current))
        assert result.threshold_direction == "stable"

    def test_threshold_direction_one_of_valid_values(self):
        engine = DeltaEngine()
        snap1 = _make_snapshot()
        snap2 = _make_snapshot()
        _run(engine.compute_delta("ae-test", snap1))
        result = _run(engine.compute_delta("ae-test", snap2))
        assert result.threshold_direction in {"narrowing", "widening", "stable"}


# ---------------------------------------------------------------------------
# trigger_ranking_changes
# ---------------------------------------------------------------------------

class TestTriggerRankingChanges:
    def test_trigger_changes_populated_when_rank_changes(self):
        engine = DeltaEngine()
        prior = _make_snapshot(trigger_rankings=[
            {"name": "Formal Attribution", "rank": 1, "amplification_factor": 0.80},
            {"name": "Sanctions Coordination", "rank": 2, "amplification_factor": 0.65},
        ])
        current = _make_snapshot(trigger_rankings=[
            {"name": "Formal Attribution", "rank": 2, "amplification_factor": 0.80},
            {"name": "Sanctions Coordination", "rank": 1, "amplification_factor": 0.65},
        ])
        _run(engine.compute_delta("ae-test", prior))
        result = _run(engine.compute_delta("ae-test", current))
        names = [f.field for f in result.trigger_ranking_changes]
        assert any("Formal Attribution" in n for n in names)

    def test_trigger_changes_empty_when_ranks_unchanged(self):
        engine = DeltaEngine()
        triggers = [
            {"name": "Formal Attribution", "rank": 1, "amplification_factor": 0.80},
        ]
        snap1 = _make_snapshot(trigger_rankings=triggers)
        snap2 = _make_snapshot(trigger_rankings=triggers)
        _run(engine.compute_delta("ae-test", snap1))
        result = _run(engine.compute_delta("ae-test", snap2))
        assert result.trigger_ranking_changes == []

    def test_trigger_changes_populated_when_amplification_changes_materially(self):
        engine = DeltaEngine()
        prior = _make_snapshot(trigger_rankings=[
            {"name": "Shipping Incident", "rank": 1, "amplification_factor": 0.50},
        ])
        current = _make_snapshot(trigger_rankings=[
            {"name": "Shipping Incident", "rank": 1, "amplification_factor": 0.60},  # delta=0.10 > 0.05
        ])
        _run(engine.compute_delta("ae-test", prior))
        result = _run(engine.compute_delta("ae-test", current))
        assert any("Shipping Incident" in f.field for f in result.trigger_ranking_changes)

    def test_trigger_changes_empty_when_amplification_change_immaterial(self):
        engine = DeltaEngine()
        prior = _make_snapshot(trigger_rankings=[
            {"name": "Shipping Incident", "rank": 1, "amplification_factor": 0.50},
        ])
        current = _make_snapshot(trigger_rankings=[
            {"name": "Shipping Incident", "rank": 1, "amplification_factor": 0.53},  # delta=0.03 ≤ 0.05
        ])
        _run(engine.compute_delta("ae-test", prior))
        result = _run(engine.compute_delta("ae-test", current))
        assert result.trigger_ranking_changes == []

    def test_trigger_change_direction_decreased_when_rank_increases(self):
        """Higher rank number = lower position = "decreased" importance."""
        engine = DeltaEngine()
        prior = _make_snapshot(trigger_rankings=[
            {"name": "Proxy Strike", "rank": 1, "amplification_factor": 0.70},
        ])
        current = _make_snapshot(trigger_rankings=[
            {"name": "Proxy Strike", "rank": 3, "amplification_factor": 0.70},
        ])
        _run(engine.compute_delta("ae-test", prior))
        result = _run(engine.compute_delta("ae-test", current))
        rank_change = next(
            f for f in result.trigger_ranking_changes if "rank" in f.field
        )
        assert rank_change.direction == "decreased"


# ---------------------------------------------------------------------------
# attractor_pull_changes
# ---------------------------------------------------------------------------

class TestAttractorPullChanges:
    def test_attractor_changes_populated_when_pull_strength_changes(self):
        engine = DeltaEngine()
        prior = _make_snapshot(attractor_rankings=[
            {"name": "Sanctions Cascade", "rank": 1, "pull_strength": 0.60},
        ])
        current = _make_snapshot(attractor_rankings=[
            {"name": "Sanctions Cascade", "rank": 1, "pull_strength": 0.70},  # delta=0.10 > 0.05
        ])
        _run(engine.compute_delta("ae-test", prior))
        result = _run(engine.compute_delta("ae-test", current))
        assert any("Sanctions Cascade" in f.field for f in result.attractor_pull_changes)

    def test_attractor_changes_empty_when_pull_change_immaterial(self):
        engine = DeltaEngine()
        prior = _make_snapshot(attractor_rankings=[
            {"name": "Sanctions Cascade", "rank": 1, "pull_strength": 0.60},
        ])
        current = _make_snapshot(attractor_rankings=[
            {"name": "Sanctions Cascade", "rank": 1, "pull_strength": 0.63},  # delta=0.03 ≤ 0.05
        ])
        _run(engine.compute_delta("ae-test", prior))
        result = _run(engine.compute_delta("ae-test", current))
        assert result.attractor_pull_changes == []

    def test_attractor_change_direction_increased(self):
        engine = DeltaEngine()
        prior = _make_snapshot(attractor_rankings=[
            {"name": "Proxy Escalation", "rank": 2, "pull_strength": 0.40},
        ])
        current = _make_snapshot(attractor_rankings=[
            {"name": "Proxy Escalation", "rank": 2, "pull_strength": 0.55},
        ])
        _run(engine.compute_delta("ae-test", prior))
        result = _run(engine.compute_delta("ae-test", current))
        change = result.attractor_pull_changes[0]
        assert change.direction == "increased"

    def test_attractor_change_direction_decreased(self):
        engine = DeltaEngine()
        prior = _make_snapshot(attractor_rankings=[
            {"name": "Proxy Escalation", "rank": 2, "pull_strength": 0.70},
        ])
        current = _make_snapshot(attractor_rankings=[
            {"name": "Proxy Escalation", "rank": 2, "pull_strength": 0.55},
        ])
        _run(engine.compute_delta("ae-test", prior))
        result = _run(engine.compute_delta("ae-test", current))
        change = result.attractor_pull_changes[0]
        assert change.direction == "decreased"


# ---------------------------------------------------------------------------
# Numeric delta fields
# ---------------------------------------------------------------------------

class TestNumericDeltas:
    def test_damping_capacity_delta_is_float(self):
        engine = DeltaEngine()
        snap1 = _make_snapshot(damping_capacity=0.70)
        snap2 = _make_snapshot(damping_capacity=0.58)
        _run(engine.compute_delta("ae-test", snap1))
        result = _run(engine.compute_delta("ae-test", snap2))
        assert isinstance(result.damping_capacity_delta, float)
        assert abs(result.damping_capacity_delta - (-0.12)) < 1e-4

    def test_confidence_delta_is_float(self):
        engine = DeltaEngine()
        snap1 = _make_snapshot(confidence=0.65)
        snap2 = _make_snapshot(confidence=0.72)
        _run(engine.compute_delta("ae-test", snap1))
        result = _run(engine.compute_delta("ae-test", snap2))
        assert isinstance(result.confidence_delta, float)
        assert abs(result.confidence_delta - 0.07) < 1e-4

    def test_new_evidence_count_is_non_negative(self):
        engine = DeltaEngine()
        snap1 = _make_snapshot(evidence_count=10)
        snap2 = _make_snapshot(evidence_count=6)  # fewer → clamped to 0
        _run(engine.compute_delta("ae-test", snap1))
        result = _run(engine.compute_delta("ae-test", snap2))
        assert result.new_evidence_count == 0

    def test_new_evidence_count_positive_when_evidence_added(self):
        engine = DeltaEngine()
        snap1 = _make_snapshot(evidence_count=4)
        snap2 = _make_snapshot(evidence_count=7)
        _run(engine.compute_delta("ae-test", snap1))
        result = _run(engine.compute_delta("ae-test", snap2))
        assert result.new_evidence_count == 3


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class TestSummary:
    def test_summary_is_non_empty_string(self):
        engine = DeltaEngine()
        snap1 = _make_snapshot()
        snap2 = _make_snapshot(regime="Nonlinear Escalation")
        _run(engine.compute_delta("ae-test", snap1))
        result = _run(engine.compute_delta("ae-test", snap2))
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    def test_summary_mentions_regime_transition(self):
        engine = DeltaEngine()
        snap1 = _make_snapshot(regime="Linear")
        snap2 = _make_snapshot(regime="Cascade Risk")
        _run(engine.compute_delta("ae-test", snap1))
        result = _run(engine.compute_delta("ae-test", snap2))
        assert "Regime" in result.summary or "regime" in result.summary

    def test_summary_no_changes_message(self):
        engine = DeltaEngine()
        snap1 = _make_snapshot()
        snap2 = _make_snapshot()
        _run(engine.compute_delta("ae-test", snap1))
        result = _run(engine.compute_delta("ae-test", snap2))
        assert "No material structural changes" in result.summary

    def test_first_run_summary_specific_message(self):
        engine = DeltaEngine()
        snap = _make_snapshot()
        result = _run(engine.compute_delta("ae-test", snap))
        assert result.summary == "First assessment run. No prior state available for comparison."


# ---------------------------------------------------------------------------
# Vocabulary / banned notation
# ---------------------------------------------------------------------------

class TestNoBannedNotation:
    def test_no_banned_terms_in_summary(self):
        engine = DeltaEngine()
        snap1 = _make_snapshot(regime="Linear")
        snap2 = _make_snapshot(
            regime="Cascade Risk",
            threshold_distance=0.25,
            damping_capacity=0.40,
            confidence=0.85,
            evidence_count=8,
        )
        _run(engine.compute_delta("ae-test", snap1))
        result = _run(engine.compute_delta("ae-test", snap2))
        _assert_no_banned_terms(result.summary)

    def test_no_banned_terms_in_first_run_summary(self):
        engine = DeltaEngine()
        snap = _make_snapshot()
        result = _run(engine.compute_delta("ae-test", snap))
        _assert_no_banned_terms(result.summary)

    def test_no_banned_terms_in_trigger_field_names(self):
        engine = DeltaEngine()
        snap1 = _make_snapshot(trigger_rankings=[
            {"name": "Formal Attribution", "rank": 1, "amplification_factor": 0.50},
        ])
        snap2 = _make_snapshot(trigger_rankings=[
            {"name": "Formal Attribution", "rank": 2, "amplification_factor": 0.50},
        ])
        _run(engine.compute_delta("ae-test", snap1))
        result = _run(engine.compute_delta("ae-test", snap2))
        for change in result.trigger_ranking_changes:
            _assert_no_banned_terms(change.field)

    def test_no_banned_terms_in_attractor_field_names(self):
        engine = DeltaEngine()
        snap1 = _make_snapshot(attractor_rankings=[
            {"name": "Sanctions Cascade", "rank": 1, "pull_strength": 0.50},
        ])
        snap2 = _make_snapshot(attractor_rankings=[
            {"name": "Sanctions Cascade", "rank": 1, "pull_strength": 0.65},
        ])
        _run(engine.compute_delta("ae-test", snap1))
        result = _run(engine.compute_delta("ae-test", snap2))
        for change in result.attractor_pull_changes:
            _assert_no_banned_terms(change.field)


# ---------------------------------------------------------------------------
# DeltaOutput schema conformance
# ---------------------------------------------------------------------------

class TestDeltaOutputSchema:
    def test_delta_output_has_required_fields(self):
        engine = DeltaEngine()
        snap = _make_snapshot()
        result = _run(engine.compute_delta("ae-test", snap))
        assert hasattr(result, "assessment_id")
        assert hasattr(result, "regime_changed")
        assert hasattr(result, "threshold_direction")
        assert hasattr(result, "trigger_ranking_changes")
        assert hasattr(result, "attractor_pull_changes")
        assert hasattr(result, "damping_capacity_delta")
        assert hasattr(result, "confidence_delta")
        assert hasattr(result, "new_evidence_count")
        assert hasattr(result, "summary")
        assert hasattr(result, "updated_at")

    def test_assessment_id_preserved_in_output(self):
        engine = DeltaEngine()
        snap = _make_snapshot(assessment_id="ae-999")
        result = _run(engine.compute_delta("ae-999", snap))
        assert result.assessment_id == "ae-999"

    def test_multiple_independent_assessment_ids(self):
        engine = DeltaEngine()
        snap_a = _make_snapshot(assessment_id="ae-A", regime="Linear")
        snap_b = _make_snapshot(assessment_id="ae-B", regime="Cascade Risk")
        result_a = _run(engine.compute_delta("ae-A", snap_a))
        result_b = _run(engine.compute_delta("ae-B", snap_b))
        assert result_a.assessment_id == "ae-A"
        assert result_b.assessment_id == "ae-B"
        assert result_a.regime_changed is False
        assert result_b.regime_changed is False
