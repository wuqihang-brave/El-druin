"""
tests/test_trigger_engine.py
============================
Unit tests for the TriggerAmplificationEngine (PR-5).

Validates:
- Schema compliance (amplification_factor and confidence bounded [0.0, 1.0])
- jump_potential 4-level taxonomy
- Structural ranking: triggers sorted by amplification_factor descending
- Graceful behaviour with empty context
- PRD vocabulary enforcement (no raw probability notation)
- Each helper method in isolation
"""

from __future__ import annotations

import asyncio
import os
import sys
import re

import pytest

# Make backend importable from the tests directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.trigger_engine import (
    TriggerAmplificationEngine,
    _jump_potential,
    _primary_domain,
    _DOMAIN_LAG_HOURS,
    _DOMAIN_WATCH_SIGNALS,
    _DOMAIN_DAMPING,
)
from app.schemas.structural_forecast import TriggerOutput, TriggersOutput


# ---------------------------------------------------------------------------
# A. _jump_potential unit tests
# ---------------------------------------------------------------------------

class TestJumpPotential:
    def test_below_0_3_is_low(self):
        assert _jump_potential(0.0) == "Low"
        assert _jump_potential(0.1) == "Low"
        assert _jump_potential(0.29) == "Low"

    def test_0_3_is_medium(self):
        assert _jump_potential(0.3) == "Medium"
        assert _jump_potential(0.49) == "Medium"

    def test_0_5_is_high(self):
        assert _jump_potential(0.5) == "High"
        assert _jump_potential(0.74) == "High"

    def test_above_0_75_is_critical(self):
        assert _jump_potential(0.76) == "Critical"
        assert _jump_potential(1.0) == "Critical"

    def test_exact_boundary_0_75_is_high(self):
        assert _jump_potential(0.75) == "High"


# ---------------------------------------------------------------------------
# B. _primary_domain helper
# ---------------------------------------------------------------------------

class TestPrimaryDomain:
    def test_returns_first_domain(self):
        assert _primary_domain({"domains": ["military", "energy"]}) == "military"

    def test_empty_domains_returns_empty_string(self):
        assert _primary_domain({"domains": []}) == ""
        assert _primary_domain({}) == ""


# ---------------------------------------------------------------------------
# C. TriggerAmplificationEngine – core contract
# ---------------------------------------------------------------------------

_DEMO_CONTEXT = {
    "events": [
        {
            "name": "Naval incident in contested strait",
            "text": (
                "Naval forces have deployed assets that block tanker transit, "
                "triggering insurance withdrawal and causing energy price escalation."
            ),
            "domains": ["military", "energy", "insurance", "finance"],
            "entities": ["Naval Forces", "Contested Strait"],
            "source_reliability": 0.88,
            "causal_weight": 0.82,
            "confidence": 0.81,
        },
        {
            "name": "Secondary sanctions package announced",
            "text": (
                "Administration announces secondary sanctions targeting financial "
                "institutions that facilitate corridor transit payments."
            ),
            "domains": ["sanctions", "finance", "energy", "trade"],
            "entities": ["Administration", "Financial Institutions"],
            "source_reliability": 0.78,
            "causal_weight": 0.55,
            "confidence": 0.68,
        },
        {
            "name": "Minor diplomatic protest filed",
            "text": "Ambassador filed diplomatic protest note via standard channels.",
            "domains": ["political"],
            "source_reliability": 0.55,
            "causal_weight": 0.15,
            "confidence": 0.35,
        },
    ],
    "kg_paths": [
        {"from_entity": "Naval Forces", "to_entity": "Energy Corridor", "domain": "energy", "strength": 0.85},
    ],
    "causal_weights": {
        "Naval incident in contested strait": 0.82,
        "Secondary sanctions package announced": 0.55,
        "Minor diplomatic protest filed": 0.15,
    },
    "velocity_data": {"military": 0.85, "sanctions": 0.45, "political": 0.10},
    "ontology_activations": {"Naval Coercion Pattern": 0.70, "Financial Isolation Pattern": 0.65},
    "regime_state": {"reversibility_index": 0.31, "damping_capacity": 0.29},
}


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestComputeTriggers:
    def setup_method(self):
        self.engine = TriggerAmplificationEngine()

    def test_returns_triggers_output_instance(self):
        result = _run(self.engine.compute_triggers("ae-204", _DEMO_CONTEXT))
        assert isinstance(result, TriggersOutput)

    def test_assessment_id_preserved(self):
        result = _run(self.engine.compute_triggers("ae-204", _DEMO_CONTEXT))
        assert result.assessment_id == "ae-204"

    def test_trigger_count_matches_events(self):
        result = _run(self.engine.compute_triggers("ae-204", _DEMO_CONTEXT))
        assert len(result.triggers) == len(_DEMO_CONTEXT["events"])

    def test_amplification_factor_bounded(self):
        result = _run(self.engine.compute_triggers("ae-204", _DEMO_CONTEXT))
        for t in result.triggers:
            assert 0.0 <= t.amplification_factor <= 1.0, (
                f"amplification_factor={t.amplification_factor} out of [0,1]"
            )

    def test_confidence_bounded(self):
        result = _run(self.engine.compute_triggers("ae-204", _DEMO_CONTEXT))
        for t in result.triggers:
            assert 0.0 <= t.confidence <= 1.0, f"confidence={t.confidence} out of [0,1]"

    def test_jump_potential_valid_values(self):
        result = _run(self.engine.compute_triggers("ae-204", _DEMO_CONTEXT))
        valid = {"Low", "Medium", "High", "Critical"}
        for t in result.triggers:
            assert t.jump_potential in valid, f"Unexpected jump_potential: {t.jump_potential}"

    def test_sorted_by_amplification_factor_descending(self):
        result = _run(self.engine.compute_triggers("ae-204", _DEMO_CONTEXT))
        amps = [t.amplification_factor for t in result.triggers]
        assert amps == sorted(amps, reverse=True), (
            f"Triggers not sorted by amplification_factor descending: {amps}"
        )

    def test_each_trigger_has_watch_signals(self):
        result = _run(self.engine.compute_triggers("ae-204", _DEMO_CONTEXT))
        for t in result.triggers:
            assert len(t.watch_signals) > 0, f"No watch_signals for trigger: {t.name}"

    def test_each_trigger_has_damping_opportunities(self):
        result = _run(self.engine.compute_triggers("ae-204", _DEMO_CONTEXT))
        for t in result.triggers:
            assert len(t.damping_opportunities) > 0, f"No damping_opportunities for {t.name}"

    def test_each_trigger_has_impacted_domains(self):
        result = _run(self.engine.compute_triggers("ae-204", _DEMO_CONTEXT))
        for t in result.triggers:
            assert len(t.impacted_domains) > 0, f"No impacted_domains for {t.name}"

    def test_expected_lag_hours_positive(self):
        result = _run(self.engine.compute_triggers("ae-204", _DEMO_CONTEXT))
        for t in result.triggers:
            assert t.expected_lag_hours >= 1, f"lag_hours < 1 for {t.name}: {t.expected_lag_hours}"

    def test_empty_context_returns_empty_triggers(self):
        result = _run(self.engine.compute_triggers("ae-204", {}))
        assert result.triggers == []
        assert result.assessment_id == "ae-204"

    def test_high_causal_weight_triggers_higher_amplification(self):
        result = _run(self.engine.compute_triggers("ae-204", _DEMO_CONTEXT))
        # Naval incident (causal_weight=0.82) should have higher amp than protest (0.15)
        naval = next(t for t in result.triggers if "Naval" in t.name)
        protest = next(t for t in result.triggers if "protest" in t.name.lower())
        assert naval.amplification_factor > protest.amplification_factor


# ---------------------------------------------------------------------------
# D. PRD vocabulary enforcement
# ---------------------------------------------------------------------------

# Patterns that must NOT appear in watch_signals or damping_opportunities
_FORBIDDEN_PATTERNS = [
    re.compile(r"[Bb]ayesian\s+p\s*="),
    re.compile(r"\bsigma\b"),
    re.compile(r"\bp\s*=\s*0\.\d+"),      # raw probability "p=0.xx"
    re.compile(r"\bposterior\b"),
    re.compile(r"\blambda\s*="),           # lambda = 0.x notation
]


class TestPRDVocabulary:
    def setup_method(self):
        self.engine = TriggerAmplificationEngine()

    def _all_string_fields(self, result: TriggersOutput) -> list[str]:
        strings = []
        for t in result.triggers:
            strings.extend(t.watch_signals)
            strings.extend(t.damping_opportunities)
        return strings

    def test_no_raw_probability_notation(self):
        result = _run(self.engine.compute_triggers("ae-204", _DEMO_CONTEXT))
        all_strings = self._all_string_fields(result)
        for text in all_strings:
            for pattern in _FORBIDDEN_PATTERNS:
                assert not pattern.search(text), (
                    f"Forbidden pattern '{pattern.pattern}' found in: {text!r}"
                )

    def test_watch_signals_use_prd_vocabulary(self):
        """At least one PRD keyword appears in watch_signals."""
        prd_keywords = [
            "regime", "threshold", "coupling", "damping", "amplification",
            "attractor", "propagation", "attribution", "escalation",
        ]
        result = _run(self.engine.compute_triggers("ae-204", _DEMO_CONTEXT))
        for t in result.triggers:
            text = " ".join(t.watch_signals).lower()
            assert any(kw in text for kw in prd_keywords), (
                f"No PRD keyword found in watch_signals for {t.name!r}: {t.watch_signals}"
            )

    def test_damping_opportunities_use_prd_vocabulary(self):
        """At least one PRD keyword appears in damping_opportunities."""
        prd_keywords = [
            "regime", "threshold", "coupling", "damping", "amplification",
            "attractor", "propagation", "attribution", "escalation",
        ]
        result = _run(self.engine.compute_triggers("ae-204", _DEMO_CONTEXT))
        for t in result.triggers:
            text = " ".join(t.damping_opportunities).lower()
            assert any(kw in text for kw in prd_keywords), (
                f"No PRD keyword in damping_opportunities for {t.name!r}: {t.damping_opportunities}"
            )


# ---------------------------------------------------------------------------
# E. _score_amplification unit tests
# ---------------------------------------------------------------------------

class TestScoreAmplification:
    def setup_method(self):
        self.engine = TriggerAmplificationEngine()

    def test_result_bounded_0_1(self):
        event = {"name": "Test", "domains": ["military"], "source_reliability": 0.9}
        score = self.engine._score_amplification(event, {}, causal_branch_weight=0.9)
        assert 0.0 <= score <= 1.0

    def test_high_causal_weight_gives_high_amplification(self):
        event = {"name": "Test", "domains": ["military"], "source_reliability": 0.9}
        score = self.engine._score_amplification(
            event, {"Test": 0.85}, causal_branch_weight=0.7
        )
        assert score > 0.7

    def test_military_domain_boost_applied(self):
        event_mil = {"name": "A", "domains": ["military"]}
        event_gen = {"name": "A", "domains": ["general"]}
        score_mil = self.engine._score_amplification(event_mil, {}, 0.5)
        score_gen = self.engine._score_amplification(event_gen, {}, 0.5)
        assert score_mil > score_gen

    def test_does_not_exceed_1_0(self):
        event = {"name": "Test", "domains": ["military"], "source_reliability": 1.0}
        score = self.engine._score_amplification(event, {"Test": 1.0}, causal_branch_weight=1.0)
        assert score <= 1.0


# ---------------------------------------------------------------------------
# F. _identify_impacted_domains tests
# ---------------------------------------------------------------------------

class TestIdentifyImpactedDomains:
    def setup_method(self):
        self.engine = TriggerAmplificationEngine()

    def test_explicit_domains_preserved(self):
        trigger = {"domains": ["military", "energy"]}
        domains = self.engine._identify_impacted_domains(trigger, [])
        assert domains == ["military", "energy"]

    def test_kg_paths_add_domains(self):
        trigger = {"domains": ["military"], "entities": ["NavyA"]}
        kg_paths = [{"from_entity": "NavyA", "to_entity": "EnergyB", "domain": "energy", "strength": 0.5}]
        domains = self.engine._identify_impacted_domains(trigger, kg_paths)
        assert "energy" in domains

    def test_no_domains_returns_general(self):
        domains = self.engine._identify_impacted_domains({}, [])
        assert domains == ["general"]

    def test_no_duplicates(self):
        trigger = {"domains": ["energy", "energy"]}
        domains = self.engine._identify_impacted_domains(trigger, [])
        assert domains.count("energy") == 1


# ---------------------------------------------------------------------------
# G. _estimate_lag_hours tests
# ---------------------------------------------------------------------------

class TestEstimateLagHours:
    def setup_method(self):
        self.engine = TriggerAmplificationEngine()

    def test_default_military_lag(self):
        lag = self.engine._estimate_lag_hours({"domains": ["military"]}, {})
        assert lag == _DOMAIN_LAG_HOURS["military"]

    def test_high_velocity_shortens_lag(self):
        lag_fast = self.engine._estimate_lag_hours({"domains": ["military"]}, {"military": 0.9})
        lag_slow = self.engine._estimate_lag_hours({"domains": ["military"]}, {"military": 0.1})
        assert lag_fast < lag_slow

    def test_lag_never_below_1(self):
        lag = self.engine._estimate_lag_hours({"domains": ["military"]}, {"military": 1.0})
        assert lag >= 1

    def test_unknown_domain_defaults_48h(self):
        lag = self.engine._estimate_lag_hours({"domains": ["unknown_domain"]}, {})
        assert lag == 48


# ---------------------------------------------------------------------------
# H. _compute_tree_scores tests
# ---------------------------------------------------------------------------

class TestComputeTreeScores:
    def setup_method(self):
        self.engine = TriggerAmplificationEngine()

    def test_returns_two_floats(self):
        w, c = self.engine._compute_tree_scores("Test event text", 0.8)
        assert isinstance(w, float)
        assert isinstance(c, float)

    def test_empty_text_returns_defaults(self):
        w, c = self.engine._compute_tree_scores("", 0.8)
        assert w == 0.5
        assert c == pytest.approx(0.8 * 0.7, abs=0.01)

    def test_weights_bounded(self):
        w, c = self.engine._compute_tree_scores(
            "The crisis triggers escalation and impacts markets causing price hike.", 0.9
        )
        assert 0.0 <= w <= 1.0
        assert 0.0 <= c <= 1.0
