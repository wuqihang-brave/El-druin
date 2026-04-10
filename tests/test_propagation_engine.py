"""
tests/test_propagation_engine.py
=================================
Unit tests for PropagationEngine (PR-7).

Validates:
- Sequence ordering (steps in ascending time-bucket order)
- At least 2 domains appear in any sequence
- time_bucket values are from the allowed set
- Bottlenecks list is non-empty
- Second-order effects list is non-empty
- Graceful fallback when engine errors
- At least 3 steps returned for a standard context
- PRD vocabulary: no raw model notation in output strings
- Each step references an allowed domain
"""

from __future__ import annotations

import asyncio
import os
import re
import sys

import pytest

# Make backend importable from the tests directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.propagation_engine import (
    PropagationEngine,
    _ALLOWED_DOMAINS,
    _TIME_BUCKET_ORDER,
    _domain_coupling_strength,
)
from app.schemas.structural_forecast import PropagationOutput, PropagationStep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


_DEMO_CONTEXT = {
    "domain_tags": ["military", "energy", "sanctions", "finance"],
    "events": [
        {
            "name": "Naval incident in contested strait",
            "text": "Naval forces block tanker transit; energy spot prices spike.",
            "domains": ["military", "energy", "insurance", "finance"],
            "source_reliability": 0.88,
            "causal_weight": 0.82,
            "confidence": 0.81,
        },
        {
            "name": "Secondary sanctions package announced",
            "text": "Administration announces secondary sanctions on financial institutions.",
            "domains": ["sanctions", "finance", "energy", "trade"],
            "source_reliability": 0.78,
            "causal_weight": 0.65,
            "confidence": 0.68,
        },
    ],
    "kg_paths": [
        {
            "from_entity": "Naval Forces",
            "to_entity": "Energy Corridor",
            "relation": "BLOCKS",
            "domain": "energy",
            "strength": 0.85,
        },
        {
            "from_entity": "Energy Corridor",
            "to_entity": "Insurance Markets",
            "relation": "AFFECTS",
            "domain": "insurance",
            "strength": 0.72,
        },
    ],
    "velocity_data": {
        "military": 0.85,
        "energy": 0.60,
        "sanctions": 0.45,
        "finance": 0.35,
    },
    "regime_state": {
        "regime": "Nonlinear Escalation",
        "damping_capacity": 0.29,
        "reversibility_index": 0.31,
        "threshold_distance": 0.18,
    },
}

_EMPTY_CONTEXT: dict = {}

_MINIMAL_CONTEXT = {
    "domain_tags": ["military"],
}


# ---------------------------------------------------------------------------
# A. Schema contract
# ---------------------------------------------------------------------------

class TestPropagationOutputSchema:
    def setup_method(self):
        self.engine = PropagationEngine()

    def test_returns_propagation_output(self):
        result = _run(self.engine.compute_propagation("ae-204", _DEMO_CONTEXT))
        assert isinstance(result, PropagationOutput)

    def test_assessment_id_preserved(self):
        result = _run(self.engine.compute_propagation("ae-204", _DEMO_CONTEXT))
        assert result.assessment_id == "ae-204"

    def test_sequence_is_list(self):
        result = _run(self.engine.compute_propagation("ae-204", _DEMO_CONTEXT))
        assert isinstance(result.sequence, list)

    def test_bottlenecks_is_list(self):
        result = _run(self.engine.compute_propagation("ae-204", _DEMO_CONTEXT))
        assert isinstance(result.bottlenecks, list)

    def test_second_order_effects_is_list(self):
        result = _run(self.engine.compute_propagation("ae-204", _DEMO_CONTEXT))
        assert isinstance(result.second_order_effects, list)

    def test_each_step_is_propagation_step(self):
        result = _run(self.engine.compute_propagation("ae-204", _DEMO_CONTEXT))
        for step in result.sequence:
            assert isinstance(step, PropagationStep)


# ---------------------------------------------------------------------------
# B. Acceptance criteria
# ---------------------------------------------------------------------------

class TestAcceptanceCriteria:
    def setup_method(self):
        self.engine = PropagationEngine()

    def test_at_least_3_steps(self):
        result = _run(self.engine.compute_propagation("ae-204", _DEMO_CONTEXT))
        assert len(result.sequence) >= 3, (
            f"Expected at least 3 steps, got {len(result.sequence)}"
        )

    def test_at_least_2_distinct_domains(self):
        result = _run(self.engine.compute_propagation("ae-204", _DEMO_CONTEXT))
        domains = {s.domain for s in result.sequence}
        assert len(domains) >= 2, (
            f"Expected at least 2 distinct domains, got: {domains}"
        )

    def test_steps_are_in_ascending_time_order(self):
        """Steps must be in non-decreasing time-bucket order."""
        result = _run(self.engine.compute_propagation("ae-204", _DEMO_CONTEXT))
        bucket_indices = [
            _TIME_BUCKET_ORDER.index(s.time_bucket) for s in result.sequence
        ]
        assert bucket_indices == sorted(bucket_indices), (
            f"Steps not in ascending time order: {[s.time_bucket for s in result.sequence]}"
        )

    def test_time_bucket_values_from_allowed_set(self):
        allowed = set(_TIME_BUCKET_ORDER)
        result = _run(self.engine.compute_propagation("ae-204", _DEMO_CONTEXT))
        for step in result.sequence:
            assert step.time_bucket in allowed, (
                f"Invalid time_bucket '{step.time_bucket}' for step {step.step}"
            )

    def test_each_step_domain_is_from_allowed_list(self):
        result = _run(self.engine.compute_propagation("ae-204", _DEMO_CONTEXT))
        for step in result.sequence:
            assert step.domain in _ALLOWED_DOMAINS, (
                f"Domain '{step.domain}' not in allowed domain list"
            )

    def test_bottlenecks_non_empty(self):
        result = _run(self.engine.compute_propagation("ae-204", _DEMO_CONTEXT))
        assert len(result.bottlenecks) > 0, "bottlenecks list must not be empty"

    def test_second_order_effects_non_empty(self):
        result = _run(self.engine.compute_propagation("ae-204", _DEMO_CONTEXT))
        assert len(result.second_order_effects) > 0, (
            "second_order_effects list must not be empty"
        )

    def test_step_numbers_start_at_1(self):
        result = _run(self.engine.compute_propagation("ae-204", _DEMO_CONTEXT))
        assert result.sequence[0].step == 1

    def test_step_numbers_are_sequential(self):
        result = _run(self.engine.compute_propagation("ae-204", _DEMO_CONTEXT))
        for idx, step in enumerate(result.sequence):
            assert step.step == idx + 1, (
                f"Step {idx} has step number {step.step}, expected {idx + 1}"
            )

    def test_first_step_is_t_plus_0(self):
        """The initiating domain step should be T+0."""
        result = _run(self.engine.compute_propagation("ae-204", _DEMO_CONTEXT))
        assert result.sequence[0].time_bucket == "T+0", (
            f"First step should be T+0, got {result.sequence[0].time_bucket}"
        )


# ---------------------------------------------------------------------------
# C. Graceful fallback
# ---------------------------------------------------------------------------

class TestGracefulFallback:
    def setup_method(self):
        self.engine = PropagationEngine()

    def test_empty_context_still_returns_output(self):
        """Engine must return a valid PropagationOutput for empty context."""
        result = _run(self.engine.compute_propagation("ae-204", _EMPTY_CONTEXT))
        assert isinstance(result, PropagationOutput)

    def test_empty_context_returns_at_least_3_steps(self):
        result = _run(self.engine.compute_propagation("ae-204", _EMPTY_CONTEXT))
        assert len(result.sequence) >= 3

    def test_empty_context_bottlenecks_non_empty(self):
        result = _run(self.engine.compute_propagation("ae-204", _EMPTY_CONTEXT))
        assert len(result.bottlenecks) > 0

    def test_empty_context_second_order_non_empty(self):
        result = _run(self.engine.compute_propagation("ae-204", _EMPTY_CONTEXT))
        assert len(result.second_order_effects) > 0

    def test_minimal_context_returns_valid_output(self):
        result = _run(self.engine.compute_propagation("ae-204", _MINIMAL_CONTEXT))
        assert isinstance(result, PropagationOutput)
        assert len(result.sequence) >= 3

    def test_unknown_assessment_id_still_works(self):
        """Engine does not raise on unknown assessment IDs."""
        result = _run(self.engine.compute_propagation("unknown-id", _DEMO_CONTEXT))
        assert isinstance(result, PropagationOutput)


# ---------------------------------------------------------------------------
# D. PRD vocabulary enforcement
# ---------------------------------------------------------------------------

_FORBIDDEN = [
    re.compile(r"[Bb]ayesian\s+p\s*="),
    re.compile(r"\bsigma\b"),
    re.compile(r"\bp\s*=\s*0\.\d+"),
    re.compile(r"\bmanifold\b"),
    re.compile(r"\bgenerator\b"),
    re.compile(r"\bcommutator\b"),
    re.compile(r"\bposterior\b"),
]


class TestPRDVocabulary:
    def setup_method(self):
        self.engine = PropagationEngine()

    def _collect_strings(self, output: PropagationOutput) -> list[str]:
        strings: list[str] = []
        for step in output.sequence:
            strings.append(step.event)
        strings.extend(output.bottlenecks)
        strings.extend(output.second_order_effects)
        return strings

    def test_no_forbidden_patterns_in_output(self):
        result = _run(self.engine.compute_propagation("ae-204", _DEMO_CONTEXT))
        texts = self._collect_strings(result)
        for text in texts:
            for pattern in _FORBIDDEN:
                assert not pattern.search(text), (
                    f"Forbidden pattern '{pattern.pattern}' found in: {text!r}"
                )

    def test_event_strings_non_empty(self):
        result = _run(self.engine.compute_propagation("ae-204", _DEMO_CONTEXT))
        for step in result.sequence:
            assert step.event.strip(), f"Empty event string for step {step.step}"

    def test_bottleneck_strings_non_empty(self):
        result = _run(self.engine.compute_propagation("ae-204", _DEMO_CONTEXT))
        for b in result.bottlenecks:
            assert b.strip(), "Empty bottleneck string found"

    def test_second_order_strings_non_empty(self):
        result = _run(self.engine.compute_propagation("ae-204", _DEMO_CONTEXT))
        for s in result.second_order_effects:
            assert s.strip(), "Empty second_order_effect string found"


# ---------------------------------------------------------------------------
# E. _build_causal_chain unit tests
# ---------------------------------------------------------------------------

class TestBuildCausalChain:
    def setup_method(self):
        self.engine = PropagationEngine()

    def test_chain_starts_with_seed(self):
        chain = self.engine._build_causal_chain(["military"])
        assert chain[0] == "military"

    def test_chain_has_minimum_length(self):
        chain = self.engine._build_causal_chain(["military"])
        assert len(chain) >= 4

    def test_chain_has_no_duplicates(self):
        chain = self.engine._build_causal_chain(["military"])
        assert len(chain) == len(set(chain)), f"Duplicates found in chain: {chain}"

    def test_all_domains_in_allowed_set(self):
        chain = self.engine._build_causal_chain(["energy"])
        for domain in chain:
            assert domain in _ALLOWED_DOMAINS, f"'{domain}' not in allowed domains"

    def test_multiple_seeds_both_present(self):
        chain = self.engine._build_causal_chain(["military", "energy"])
        assert "military" in chain
        assert "energy" in chain


# ---------------------------------------------------------------------------
# F. _assign_time_bucket unit tests
# ---------------------------------------------------------------------------

class TestAssignTimeBucket:
    def setup_method(self):
        self.engine = PropagationEngine()

    def test_step_0_is_always_t_plus_0(self):
        assert self.engine._assign_time_bucket(0, "military", 0.5) == "T+0"
        assert self.engine._assign_time_bucket(0, "energy", 0.9) == "T+0"

    def test_result_is_valid_bucket(self):
        for domain in ["military", "diplomatic", "sanctions", "energy", "finance"]:
            bucket = self.engine._assign_time_bucket(1, domain, 0.5)
            assert bucket in _TIME_BUCKET_ORDER, f"Invalid bucket '{bucket}' for domain '{domain}'"

    def test_high_velocity_promotes_bucket(self):
        bucket_fast = self.engine._assign_time_bucket(1, "diplomatic", 0.9)
        bucket_slow = self.engine._assign_time_bucket(1, "diplomatic", 0.1)
        fast_idx = _TIME_BUCKET_ORDER.index(bucket_fast)
        slow_idx = _TIME_BUCKET_ORDER.index(bucket_slow)
        assert fast_idx <= slow_idx, (
            f"High velocity should give earlier or equal bucket: fast={bucket_fast} slow={bucket_slow}"
        )


# ---------------------------------------------------------------------------
# G. _detect_bottlenecks unit tests
# ---------------------------------------------------------------------------

class TestDetectBottlenecks:
    def setup_method(self):
        self.engine = PropagationEngine()

    def _make_sequence(self, domains: list[str]) -> list[PropagationStep]:
        return [
            PropagationStep(step=i + 1, domain=d, event="test", time_bucket="T+0")
            for i, d in enumerate(domains)
        ]

    def test_non_empty_result(self):
        seq = self._make_sequence(["military", "energy", "insurance"])
        bottlenecks = self.engine._detect_bottlenecks(seq, {})
        assert len(bottlenecks) > 0

    def test_high_strength_kg_path_adds_bottleneck(self):
        seq = self._make_sequence(["energy"])
        graph = {"kg_paths": [{"domain": "energy", "strength": 0.9}]}
        bottlenecks = self.engine._detect_bottlenecks(seq, graph)
        assert len(bottlenecks) > 0

    def test_no_duplicates_in_bottlenecks(self):
        seq = self._make_sequence(["energy", "insurance", "market"])
        bottlenecks = self.engine._detect_bottlenecks(seq, {})
        assert len(bottlenecks) == len(set(bottlenecks)), "Duplicate bottlenecks found"


# ---------------------------------------------------------------------------
# H. _extract_second_order unit tests
# ---------------------------------------------------------------------------

class TestExtractSecondOrder:
    def setup_method(self):
        self.engine = PropagationEngine()

    def _make_sequence(self, domains: list[str]) -> list[PropagationStep]:
        return [
            PropagationStep(step=i + 1, domain=d, event="test", time_bucket="T+0")
            for i, d in enumerate(domains)
        ]

    def test_non_empty_result(self):
        seq = self._make_sequence(["military", "energy"])
        effects = self.engine._extract_second_order(seq, {})
        assert len(effects) >= 2

    def test_no_duplicates(self):
        seq = self._make_sequence(["military", "energy", "finance"])
        effects = self.engine._extract_second_order(seq, {})
        assert len(effects) == len(set(effects)), "Duplicate second-order effects found"

    def test_all_strings_non_empty(self):
        seq = self._make_sequence(["military", "energy", "finance"])
        effects = self.engine._extract_second_order(seq, {})
        for e in effects:
            assert e.strip(), "Empty second-order effect string found"


# ---------------------------------------------------------------------------
# I. _resolve_seed_domains tests
# ---------------------------------------------------------------------------

class TestResolveSeedDomains:
    def setup_method(self):
        self.engine = PropagationEngine()

    def test_domain_tags_used_when_available(self):
        seeds = self.engine._resolve_seed_domains(["energy", "finance"], [])
        assert "energy" in seeds

    def test_invalid_domain_tags_filtered(self):
        seeds = self.engine._resolve_seed_domains(["notadomain", "energy"], [])
        assert "notadomain" not in seeds

    def test_fallback_to_events_when_no_tags(self):
        events = [{"domains": ["sanctions"], "causal_weight": 0.7}]
        seeds = self.engine._resolve_seed_domains([], events)
        assert seeds == ["sanctions"]

    def test_default_military_when_nothing(self):
        seeds = self.engine._resolve_seed_domains([], [])
        assert seeds == ["military"]
