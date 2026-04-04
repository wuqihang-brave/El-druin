"""
tests/test_pipeline_schema_contract.py
=======================================
Schema-contract tests for the v3 Evented Ontological Reasoning Pipeline.

These tests verify that the JSON keys returned by ``run_evented_pipeline``
always satisfy the backward-compatible contract expected by the frontend
(``frontend/app.py``).  Any future refactor that renames internal fields must
either keep the alias keys or update both backend serialization AND these
tests simultaneously.

Backward-compat key mapping
----------------------------
Backend v3 field       | Frontend alias  | Rationale
-----------------------|-----------------|-----------------------------
EventNode.event_type   | "type"          | frontend: ``_ev.get("type")``
PatternNode.pattern_name | "pattern"     | frontend: ``_ap["pattern"]``
PatternNode.confidence_prior | "confidence" | frontend: ``_ap.get("confidence")``
PatternNode.source_event | "from_event"  | frontend: ``_ap.get("from_event")``
TransitionEdge.to_pattern | "derived"    | frontend: ``_dp["derived"]``
TransitionEdge.to_pattern | "pattern"    | frontend: ``_dp.get("pattern")``
"""

from __future__ import annotations

import sys
import os

import pytest

# Make backend importable when running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from intelligence.evented_pipeline import run_evented_pipeline  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures – short representative texts that reliably produce events
# ---------------------------------------------------------------------------

_FIXTURE_GEOPOLITICS = (
    "The United States announced new sanctions against Russia following "
    "continued military operations in eastern Ukraine.  Treasury Secretary "
    "confirmed the measures target energy exports and financial institutions."
)

_FIXTURE_TARIFF_TRADE = (
    "Washington imposed 25% tariffs on Chinese steel and aluminium imports, "
    "escalating the trade dispute between the world's two largest economies.  "
    "Beijing warned of retaliatory measures affecting agricultural exports."
)


# ===========================================================================
# Event dict contract
# ===========================================================================

class TestEventDictContract:
    """Verify keys of each event dict returned by run_evented_pipeline."""

    def _events(self, text: str) -> list:
        return run_evented_pipeline(text, llm_service=None).events

    def test_event_has_type_alias(self):
        """'type' backward-compat alias must be present and equal event_type."""
        events = self._events(_FIXTURE_GEOPOLITICS)
        for evt in events:
            assert "type" in evt, f"Event missing 'type' alias: {evt}"
            assert evt.get("type") == evt.get("event_type"), (
                f"'type' must equal 'event_type'. Got: {evt}"
            )

    def test_event_type_not_unknown(self):
        """'type' must not fall back to 'unknown' when events are present."""
        events = self._events(_FIXTURE_GEOPOLITICS)
        for evt in events:
            val = evt.get("type", "unknown")
            assert val != "unknown", f"event['type'] is 'unknown': {evt}"
            assert val, f"event['type'] is empty: {evt}"

    def test_event_has_confidence(self):
        """Events must carry 'confidence' > 0."""
        events = self._events(_FIXTURE_GEOPOLITICS)
        for evt in events:
            assert "confidence" in evt, f"Event missing 'confidence': {evt}"
            assert evt["confidence"] > 0, f"event confidence == 0: {evt}"


# ===========================================================================
# Active-pattern dict contract
# ===========================================================================

class TestActivePatternDictContract:
    """Verify keys of each active-pattern dict."""

    def _patterns(self, text: str) -> list:
        return run_evented_pipeline(text, llm_service=None).active_patterns

    def test_has_pattern_alias(self):
        """'pattern' backward-compat key must equal 'pattern_name'."""
        for ap in self._patterns(_FIXTURE_GEOPOLITICS):
            assert "pattern" in ap, f"Active pattern missing 'pattern': {ap}"
            assert ap.get("pattern") == ap.get("pattern_name"), (
                f"'pattern' must equal 'pattern_name'. Got: {ap}"
            )

    def test_has_confidence_alias(self):
        """'confidence' backward-compat key must be present."""
        for ap in self._patterns(_FIXTURE_GEOPOLITICS):
            assert "confidence" in ap, f"Active pattern missing 'confidence': {ap}"

    def test_has_from_event_alias(self):
        """'from_event' backward-compat key must be present."""
        for ap in self._patterns(_FIXTURE_GEOPOLITICS):
            assert "from_event" in ap, f"Active pattern missing 'from_event': {ap}"


# ===========================================================================
# Derived-pattern dict contract
# ===========================================================================

class TestDerivedPatternDictContract:
    """Verify keys of each derived-pattern dict."""

    def _derived(self, text: str) -> list:
        return run_evented_pipeline(text, llm_service=None).derived_patterns

    def test_has_derived_alias(self):
        """'derived' backward-compat key must be present."""
        for dp in self._derived(_FIXTURE_TARIFF_TRADE):
            assert "derived" in dp, f"Derived pattern missing 'derived': {dp}"

    def test_has_pattern_alias(self):
        """'pattern' backward-compat key must be present."""
        for dp in self._derived(_FIXTURE_TARIFF_TRADE):
            assert "pattern" in dp, f"Derived pattern missing 'pattern': {dp}"

    def test_has_derived_confidence(self):
        """'derived_confidence' key must be present."""
        for dp in self._derived(_FIXTURE_TARIFF_TRADE):
            assert "derived_confidence" in dp, (
                f"Derived pattern missing 'derived_confidence': {dp}"
            )

    def test_has_rule(self):
        """'rule' key must be present (maps to transition_type)."""
        for dp in self._derived(_FIXTURE_TARIFF_TRADE):
            assert "rule" in dp, f"Derived pattern missing 'rule': {dp}"


# ===========================================================================
# v3 new fields on PipelineResult
# ===========================================================================

class TestV3NewFieldsContract:
    """Verify that v3-specific fields are exposed on PipelineResult."""

    def test_has_top_transitions(self):
        """PipelineResult must expose 'top_transitions' as a list."""
        result = run_evented_pipeline(_FIXTURE_GEOPOLITICS, llm_service=None)
        assert hasattr(result, "top_transitions"), (
            "PipelineResult missing 'top_transitions'"
        )
        assert isinstance(result.top_transitions, list)

    def test_has_state_vector(self):
        """PipelineResult must expose 'state_vector' as a dict."""
        result = run_evented_pipeline(_FIXTURE_GEOPOLITICS, llm_service=None)
        assert hasattr(result, "state_vector"), (
            "PipelineResult missing 'state_vector'"
        )
        assert isinstance(result.state_vector, dict)

    def test_has_driving_factors(self):
        """PipelineResult must expose 'driving_factors' as a list."""
        result = run_evented_pipeline(_FIXTURE_GEOPOLITICS, llm_service=None)
        assert hasattr(result, "driving_factors"), (
            "PipelineResult missing 'driving_factors'"
        )
        assert isinstance(result.driving_factors, list)
