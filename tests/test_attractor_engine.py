"""
tests/test_attractor_engine.py
================================
Tests for backend/app/services/attractor_engine.py

Validates that AttractorEngine returns valid AttractorsOutput satisfying
the acceptance criteria in PR-6.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import List

import pytest

# Make backend importable when running from repo root
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.services.attractor_engine import (  # noqa: E402
    AttractorEngine,
    _CANONICAL_ATTRACTORS,
    _match_canonical,
    _pull_strength_history,
)
from app.schemas.structural_forecast import AttractorOutput, AttractorsOutput  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FULL_CONTEXT = {
    "assessment_id": "ae-204",
    "title": "Black Sea Energy Corridor – Structural Watch",
    "domain_tags": ["energy", "military", "sanctions", "finance"],
    "region_tags": ["Eastern Europe", "Black Sea"],
    "evidence_count": 4,
}

_MINIMAL_CONTEXT: dict = {}

_ENERGY_ONLY_CONTEXT = {
    "domain_tags": ["energy"],
    "evidence_count": 2,
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# AttractorEngine – import and instantiation
# ---------------------------------------------------------------------------

class TestAttractorEngineImport:
    def test_importable(self):
        """AttractorEngine must be importable from app.services."""
        assert AttractorEngine is not None

    def test_instantiate_no_args(self):
        """AttractorEngine() must instantiate without required arguments."""
        engine = AttractorEngine()
        assert engine is not None

    def test_instantiate_with_args(self):
        """AttractorEngine accepts optional injected engines."""
        engine = AttractorEngine(
            ontology_forecaster=None,
            evented_pipeline=None,
            probability_tree=None,
        )
        assert engine is not None


# ---------------------------------------------------------------------------
# compute_attractors – return type and schema contract
# ---------------------------------------------------------------------------

class TestComputeAttractorsReturn:
    def test_returns_attractors_output(self):
        """compute_attractors must return an AttractorsOutput instance."""
        engine = AttractorEngine()
        result = _run(engine.compute_attractors("ae-204", _FULL_CONTEXT))
        assert isinstance(result, AttractorsOutput)

    def test_assessment_id_preserved(self):
        """assessment_id in result must match the input."""
        engine = AttractorEngine()
        result = _run(engine.compute_attractors("ae-204", _FULL_CONTEXT))
        assert result.assessment_id == "ae-204"

    def test_updated_at_present(self):
        """updated_at must be set."""
        engine = AttractorEngine()
        result = _run(engine.compute_attractors("ae-204", _FULL_CONTEXT))
        assert result.updated_at is not None

    def test_attractors_is_list(self):
        """attractors must be a list."""
        engine = AttractorEngine()
        result = _run(engine.compute_attractors("ae-204", _FULL_CONTEXT))
        assert isinstance(result.attractors, list)


# ---------------------------------------------------------------------------
# Acceptance criteria
# ---------------------------------------------------------------------------

class TestAcceptanceCriteria:
    def test_at_least_two_attractors_full_context(self):
        """Must return >= 2 attractors when context is available."""
        engine = AttractorEngine()
        result = _run(engine.compute_attractors("ae-204", _FULL_CONTEXT))
        assert len(result.attractors) >= 2, (
            f"Expected >= 2 attractors, got {len(result.attractors)}"
        )

    def test_at_least_two_attractors_empty_context(self):
        """Must return >= 2 attractors even when context is empty (fallback)."""
        engine = AttractorEngine()
        result = _run(engine.compute_attractors("ae-204", _MINIMAL_CONTEXT))
        assert len(result.attractors) >= 2

    def test_sorted_by_pull_strength_descending(self):
        """Attractors must be sorted by pull_strength descending."""
        engine = AttractorEngine()
        result = _run(engine.compute_attractors("ae-204", _FULL_CONTEXT))
        pulls = [a.pull_strength for a in result.attractors]
        assert pulls == sorted(pulls, reverse=True), (
            f"Attractors not sorted by pull_strength: {pulls}"
        )

    def test_pull_strength_bounded(self):
        """pull_strength must be in [0.0, 1.0] for every attractor."""
        engine = AttractorEngine()
        result = _run(engine.compute_attractors("ae-204", _FULL_CONTEXT))
        for a in result.attractors:
            assert 0.0 <= a.pull_strength <= 1.0, (
                f"pull_strength {a.pull_strength} out of [0.0, 1.0] for {a.name}"
            )

    def test_trend_valid_values(self):
        """trend must be one of 'up', 'down', 'stable'."""
        engine = AttractorEngine()
        result = _run(engine.compute_attractors("ae-204", _FULL_CONTEXT))
        for a in result.attractors:
            assert a.trend in ("up", "down", "stable"), (
                f"Invalid trend '{a.trend}' for {a.name}"
            )

    def test_counterforces_non_empty(self):
        """Each attractor must have at least one counterforce."""
        engine = AttractorEngine()
        result = _run(engine.compute_attractors("ae-204", _FULL_CONTEXT))
        for a in result.attractors:
            assert len(a.counterforces) >= 1, (
                f"No counterforces for attractor '{a.name}'"
            )

    def test_invalidation_conditions_non_empty(self):
        """Each attractor must have at least one invalidation condition."""
        engine = AttractorEngine()
        result = _run(engine.compute_attractors("ae-204", _FULL_CONTEXT))
        for a in result.attractors:
            assert len(a.invalidation_conditions) >= 1, (
                f"No invalidation conditions for attractor '{a.name}'"
            )

    def test_supporting_evidence_count_positive(self):
        """supporting_evidence_count must be >= 1."""
        engine = AttractorEngine()
        result = _run(engine.compute_attractors("ae-204", _FULL_CONTEXT))
        for a in result.attractors:
            assert a.supporting_evidence_count >= 1

    def test_no_raw_model_notation(self):
        """Generated strings must not contain raw model notation."""
        engine = AttractorEngine()
        result = _run(engine.compute_attractors("ae-204", _FULL_CONTEXT))
        banned_terms = ["bayesian", "p=", "sigma", "manifold", "posterior"]
        for a in result.attractors:
            text = " ".join(
                [a.name] + a.counterforces + a.invalidation_conditions
            ).lower()
            for term in banned_terms:
                assert term not in text, (
                    f"Banned term '{term}' found in attractor '{a.name}'"
                )

    def test_no_duplicate_attractor_names(self):
        """Attractor names must be unique in a single result."""
        engine = AttractorEngine()
        result = _run(engine.compute_attractors("ae-204", _FULL_CONTEXT))
        names = [a.name for a in result.attractors]
        assert len(names) == len(set(names)), f"Duplicate names: {names}"

    def test_no_placeholder_names(self):
        """Attractor names must not be unresolved placeholders."""
        engine = AttractorEngine()
        result = _run(engine.compute_attractors("ae-204", _FULL_CONTEXT))
        for a in result.attractors:
            assert not a.name.startswith("("), (
                f"Unresolved placeholder name: {a.name}"
            )
            assert a.name != "unknown", f"Generic 'unknown' name found"


# ---------------------------------------------------------------------------
# Trend tracking
# ---------------------------------------------------------------------------

class TestTrendTracking:
    def test_first_run_stable(self):
        """On first run, trend must default to 'stable'."""
        engine = AttractorEngine()
        # Use a unique assessment_id to avoid history contamination
        result = _run(engine.compute_attractors("trend-test-001", _FULL_CONTEXT))
        for a in result.attractors:
            assert a.trend == "stable", (
                f"First run should be 'stable', got '{a.trend}' for {a.name}"
            )

    def test_trend_up_when_pull_increases(self):
        """trend should be 'up' when pull_strength increased by > 0.05."""
        engine = AttractorEngine()
        aid = "trend-test-up"
        r1 = _run(engine.compute_attractors(aid, _FULL_CONTEXT))
        # Artificially lower stored history to simulate prior was lower
        for a in r1.attractors:
            _pull_strength_history[f"{aid}:{a.name}"] = max(0.0, a.pull_strength - 0.15)
        r2 = _run(engine.compute_attractors(aid, _FULL_CONTEXT))
        assert any(a.trend == "up" for a in r2.attractors), (
            "Expected at least one 'up' trend after pull strength increase"
        )

    def test_trend_down_when_pull_decreases(self):
        """trend should be 'down' when pull_strength decreased by > 0.05."""
        engine = AttractorEngine()
        aid = "trend-test-down"
        r1 = _run(engine.compute_attractors(aid, _FULL_CONTEXT))
        # Artificially raise stored history to simulate prior was higher
        for a in r1.attractors:
            _pull_strength_history[f"{aid}:{a.name}"] = min(1.0, a.pull_strength + 0.15)
        r2 = _run(engine.compute_attractors(aid, _FULL_CONTEXT))
        assert any(a.trend == "down" for a in r2.attractors), (
            "Expected at least one 'down' trend after pull strength decrease"
        )


# ---------------------------------------------------------------------------
# Canonical taxonomy matching
# ---------------------------------------------------------------------------

class TestCanonicalMatching:
    def test_sanctions_match(self):
        """'Financial Isolation / SWIFT Cut-Off' should match Sanctions Cascade."""
        match = _match_canonical("Financial Isolation / SWIFT Cut-Off", "economics")
        assert match is not None
        assert match["name"] == "Sanctions Cascade"

    def test_transport_match(self):
        """Energy/corridor-related names should match Transport Disruption."""
        match = _match_canonical("Energy Transit Corridor", "energy")
        assert match is not None
        assert match["name"] == "Transport Disruption"

    def test_no_match_for_generic(self):
        """Purely generic names with no keyword overlap should return None."""
        match = _match_canonical("Gamma Burst", "unknown_domain")
        assert match is None

    def test_all_canonical_attractors_have_required_fields(self):
        """Every canonical attractor must have name, keywords, counterforces, invalidation_conditions."""
        for c in _CANONICAL_ATTRACTORS:
            assert "name" in c
            assert "keywords" in c
            assert "counterforces" in c, f"Missing counterforces in {c['name']}"
            assert "invalidation_conditions" in c, f"Missing invalidation_conditions in {c['name']}"
            assert len(c["counterforces"]) >= 1
            assert len(c["invalidation_conditions"]) >= 1


# ---------------------------------------------------------------------------
# _compute_pull_strength
# ---------------------------------------------------------------------------

class TestComputePullStrength:
    def test_pull_bounded_low(self):
        """pull_strength must not go below 0.05."""
        engine = AttractorEngine()
        pull = engine._compute_pull_strength({"final_probability": 0.0}, 0.0)
        assert pull >= 0.05

    def test_pull_bounded_high(self):
        """pull_strength must not exceed 0.95."""
        engine = AttractorEngine()
        pull = engine._compute_pull_strength({"final_probability": 1.0}, 1.0)
        assert pull <= 0.95

    def test_pull_increases_with_alignment(self):
        """Higher structural_alignment should yield higher pull_strength."""
        engine = AttractorEngine()
        scenario = {"final_probability": 0.6}
        low = engine._compute_pull_strength(scenario, 0.0)
        high = engine._compute_pull_strength(scenario, 1.0)
        assert high > low


# ---------------------------------------------------------------------------
# _estimate_horizon
# ---------------------------------------------------------------------------

class TestEstimateHorizon:
    def test_early_step_returns_days(self):
        """first_step <= 2 should return a day-scale horizon."""
        engine = AttractorEngine()
        horizon = engine._estimate_horizon({"first_step": 1}, velocity=0.5)
        assert "d" in horizon

    def test_mid_step_returns_weeks(self):
        """first_step in 3-4 range should return a week-scale horizon."""
        engine = AttractorEngine()
        horizon = engine._estimate_horizon({"first_step": 3}, velocity=0.5)
        assert "w" in horizon

    def test_late_step_returns_weeks(self):
        """first_step > 4 should return a week-scale horizon."""
        engine = AttractorEngine()
        horizon = engine._estimate_horizon({"first_step": 5}, velocity=0.5)
        assert "w" in horizon

    def test_format_is_range(self):
        """Horizon must be in 'N-Mu' or 'N-Md' format."""
        engine = AttractorEngine()
        for first_step in [1, 2, 3, 4, 5]:
            horizon = engine._estimate_horizon({"first_step": first_step}, velocity=0.5)
            assert "-" in horizon, f"Horizon '{horizon}' has no range separator"
