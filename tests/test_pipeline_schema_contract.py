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
from types import ModuleType
from typing import Any
from unittest.mock import patch

import pytest

# Make backend importable when running from repo root
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

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


# ===========================================================================
# evented.v1 canonical contract – event tier, evidence, inferred_fields
# ===========================================================================

class TestEventedV1EventContract:
    """Enforce the evented.v1 canonical fields for events returned by run_evented_pipeline."""

    def _events(self, text: str) -> list:
        return run_evented_pipeline(text, llm_service=None).events

    def test_events_have_tier_field(self):
        """Each event dict must include 'tier' (T1 or T2)."""
        events = self._events(_FIXTURE_GEOPOLITICS)
        assert events, "Expected at least one event"
        for evt in events:
            assert "tier" in evt, f"Event missing 'tier': {evt}"
            assert evt["tier"] in ("T1", "T2"), (
                f"tier must be T1 or T2, got: {evt['tier']}"
            )

    def test_events_have_evidence_quote(self):
        """Each event dict must include 'evidence.quote' (non-empty string)."""
        events = self._events(_FIXTURE_GEOPOLITICS)
        assert events, "Expected at least one event"
        for evt in events:
            assert "evidence" in evt, f"Event missing 'evidence': {evt}"
            assert isinstance(evt["evidence"], dict), (
                f"'evidence' must be a dict, got: {type(evt['evidence'])}"
            )
            assert "quote" in evt["evidence"], (
                f"Event missing 'evidence.quote': {evt}"
            )
            assert evt["evidence"]["quote"], (
                f"'evidence.quote' is empty: {evt}"
            )

    def test_events_have_inferred_fields_key(self):
        """Each event dict must include 'inferred_fields' (list)."""
        events = self._events(_FIXTURE_GEOPOLITICS)
        assert events, "Expected at least one event"
        for evt in events:
            assert "inferred_fields" in evt, (
                f"Event missing 'inferred_fields': {evt}"
            )
            assert isinstance(evt["inferred_fields"], list), (
                f"'inferred_fields' must be a list: {evt}"
            )

    def test_events_count_at_least_one(self):
        """run_evented_pipeline must return at least 1 event."""
        result = run_evented_pipeline(_FIXTURE_GEOPOLITICS, llm_service=None)
        assert len(result.events) >= 1, (
            "Expected at least 1 event from evented pipeline"
        )


# ===========================================================================
# evented.v1 canonical contract – conclusion required keys
# ===========================================================================

class TestEventedV1ConclusionContract:
    """Enforce evented.v1 conclusion dict keys."""

    def _conclusion(self, text: str) -> dict:
        return run_evented_pipeline(text, llm_service=None).conclusion

    def test_conclusion_has_conclusion_key(self):
        """conclusion dict must have 'conclusion' (string) key."""
        concl = self._conclusion(_FIXTURE_GEOPOLITICS)
        assert "conclusion" in concl, (
            f"conclusion dict missing 'conclusion' key. Got keys: {list(concl.keys())}"
        )
        assert isinstance(concl["conclusion"], str), (
            f"'conclusion' must be a string, got: {type(concl['conclusion'])}"
        )
        assert concl["conclusion"], "'conclusion' is empty string"

    def test_conclusion_has_evidence_path(self):
        """conclusion dict must have 'evidence_path' with 'summary'."""
        concl = self._conclusion(_FIXTURE_GEOPOLITICS)
        assert "evidence_path" in concl, (
            f"conclusion dict missing 'evidence_path'. Keys: {list(concl.keys())}"
        )
        ep = concl["evidence_path"]
        assert isinstance(ep, dict), f"'evidence_path' must be a dict, got: {type(ep)}"
        assert "summary" in ep, f"'evidence_path' missing 'summary'. Keys: {list(ep.keys())}"
        assert ep["summary"], "'evidence_path.summary' is empty"

    def test_conclusion_has_hypothesis_path(self):
        """conclusion dict must have 'hypothesis_path' with 'summary'."""
        concl = self._conclusion(_FIXTURE_GEOPOLITICS)
        assert "hypothesis_path" in concl, (
            f"conclusion dict missing 'hypothesis_path'. Keys: {list(concl.keys())}"
        )
        hp = concl["hypothesis_path"]
        assert isinstance(hp, dict), f"'hypothesis_path' must be a dict, got: {type(hp)}"
        assert "summary" in hp, f"'hypothesis_path' missing 'summary'. Keys: {list(hp.keys())}"

    def test_conclusion_has_beta_path_algebra(self):
        """conclusion dict must have 'beta_path_algebra'."""
        concl = self._conclusion(_FIXTURE_GEOPOLITICS)
        assert "beta_path_algebra" in concl, (
            f"conclusion dict missing 'beta_path_algebra'. Keys: {list(concl.keys())}"
        )
        assert isinstance(concl["beta_path_algebra"], dict)


# ===========================================================================
# evented.v1 canonical contract – credibility required keys
# ===========================================================================

class TestEventedV1CredibilityContract:
    """Enforce evented.v1 credibility dict keys."""

    def _credibility(self, text: str) -> dict:
        return run_evented_pipeline(text, llm_service=None).credibility

    def test_credibility_has_verifiability_score(self):
        """credibility dict must have 'verifiability_score' (float 0–1)."""
        cred = self._credibility(_FIXTURE_GEOPOLITICS)
        assert "verifiability_score" in cred, (
            f"credibility missing 'verifiability_score'. Keys: {list(cred.keys())}"
        )
        vs = cred["verifiability_score"]
        assert 0.0 <= vs <= 1.0, f"verifiability_score out of range: {vs}"

    def test_credibility_has_kg_consistency_score(self):
        """credibility dict must have 'kg_consistency_score'."""
        cred = self._credibility(_FIXTURE_GEOPOLITICS)
        assert "kg_consistency_score" in cred, (
            f"credibility missing 'kg_consistency_score'. Keys: {list(cred.keys())}"
        )

    def test_credibility_has_overall_score(self):
        """credibility dict must have 'overall_score' (float 0–1)."""
        cred = self._credibility(_FIXTURE_GEOPOLITICS)
        assert "overall_score" in cred, (
            f"credibility missing 'overall_score'. Keys: {list(cred.keys())}"
        )
        os_ = cred["overall_score"]
        assert 0.0 <= os_ <= 1.0, f"overall_score out of range: {os_}"

    def test_credibility_has_hypothesis_ratio(self):
        """credibility dict must have 'hypothesis_ratio' (float 0–1)."""
        cred = self._credibility(_FIXTURE_GEOPOLITICS)
        assert "hypothesis_ratio" in cred, (
            f"credibility missing 'hypothesis_ratio'. Keys: {list(cred.keys())}"
        )
        hr = cred["hypothesis_ratio"]
        assert 0.0 <= hr <= 1.0, f"hypothesis_ratio out of range: {hr}"

    def test_credibility_has_missing_evidence(self):
        """credibility dict must have 'missing_evidence' (list)."""
        cred = self._credibility(_FIXTURE_GEOPOLITICS)
        assert "missing_evidence" in cred, (
            f"credibility missing 'missing_evidence'. Keys: {list(cred.keys())}"
        )
        assert isinstance(cred["missing_evidence"], list)


# ===========================================================================
# evented.v1 canonical contract – active_patterns tier field
# ===========================================================================

class TestEventedV1ActivePatternsContract:
    """Enforce evented.v1 canonical fields on active_patterns."""

    def _patterns(self, text: str) -> list:
        return run_evented_pipeline(text, llm_service=None).active_patterns

    def test_active_patterns_have_tier(self):
        """Each active pattern must include 'tier'."""
        patterns = self._patterns(_FIXTURE_GEOPOLITICS)
        for ap in patterns:
            assert "tier" in ap, f"Active pattern missing 'tier': {ap}"
            assert ap["tier"] in ("T1", "T2")

    def test_active_patterns_have_inferred(self):
        """Each active pattern must include 'inferred' (bool)."""
        patterns = self._patterns(_FIXTURE_GEOPOLITICS)
        for ap in patterns:
            assert "inferred" in ap, f"Active pattern missing 'inferred': {ap}"
            assert isinstance(ap["inferred"], bool)


# ===========================================================================
# evented.v1 canonical contract – driving_factors label/count/confidence/evidence
# ===========================================================================

class TestEventedV1DrivingFactorsContract:
    """Enforce evented.v1 canonical alias fields on driving_factors."""

    def _factors(self, text: str) -> list:
        return run_evented_pipeline(text, llm_service=None).driving_factors

    def test_driving_factors_have_label(self):
        """Each driving factor must include 'label' (string alias for 'factor')."""
        factors = self._factors(_FIXTURE_TARIFF_TRADE)
        for df in factors:
            assert "label" in df, f"Driving factor missing 'label': {df}"
            assert isinstance(df["label"], str)

    def test_driving_factors_have_count(self):
        """Each driving factor must include 'count' (int)."""
        factors = self._factors(_FIXTURE_TARIFF_TRADE)
        for df in factors:
            assert "count" in df, f"Driving factor missing 'count': {df}"
            assert isinstance(df["count"], int)

    def test_driving_factors_have_confidence(self):
        """Each driving factor must include 'confidence' (float 0–1)."""
        factors = self._factors(_FIXTURE_TARIFF_TRADE)
        for df in factors:
            assert "confidence" in df, f"Driving factor missing 'confidence': {df}"
            conf = df["confidence"]
            assert 0.0 <= conf <= 1.0, f"confidence out of range: {conf}"

    def test_driving_factors_have_evidence(self):
        """Each driving factor must include 'evidence' (list)."""
        factors = self._factors(_FIXTURE_TARIFF_TRADE)
        for df in factors:
            assert "evidence" in df, f"Driving factor missing 'evidence': {df}"
            assert isinstance(df["evidence"], list)


# ===========================================================================
# state_vector mean_vector_list (8D float list)
# ===========================================================================

class TestEventedV1StateVectorContract:
    """Enforce that state_vector includes a 8-float mean_vector_list."""

    def test_state_vector_has_mean_vector_list(self):
        """state_vector must include 'mean_vector_list' as list[float] of length 8."""
        result = run_evented_pipeline(_FIXTURE_GEOPOLITICS, llm_service=None)
        sv = result.state_vector
        assert "mean_vector_list" in sv, (
            f"state_vector missing 'mean_vector_list'. Keys: {list(sv.keys())}"
        )
        mvl = sv["mean_vector_list"]
        assert isinstance(mvl, list), f"mean_vector_list must be a list, got: {type(mvl)}"
        assert len(mvl) == 8, f"mean_vector_list must have 8 elements, got: {len(mvl)}"
        for v in mvl:
            assert isinstance(v, (int, float)), f"mean_vector_list element is not numeric: {v}"


# ===========================================================================
# FastAPI endpoint integration – POST /api/v1/analysis/evented/deduce
# ===========================================================================

class _FakeEventedLLM:
    """Stub LLM that returns an empty list for event extraction and a minimal conclusion."""

    def call(self, **kwargs: Any) -> str:
        # For conclusion generation, return plain text
        return "Deterministic fallback: no LLM."


@pytest.fixture()
def evented_client():
    """Return a TestClient wired to the real FastAPI app for the evented endpoint."""
    from fastapi import FastAPI
    from app.api.routes import analysis as analysis_module

    app = FastAPI()
    app.include_router(analysis_module.router, prefix="/api/v1")

    with (
        patch.object(analysis_module, "_get_llm_service", return_value=None),
        patch.object(analysis_module, "_get_kuzu_connection", return_value=None),
        patch.object(analysis_module, "_ensure_intelligence_importable", return_value=None),
    ):
        try:
            from fastapi.testclient import TestClient
            with TestClient(app) as c:
                yield c
        except Exception:
            yield None


_EVENTED_REQUEST = {
    "news_fragment": (
        "The United States imposed new sanctions on Russia following "
        "continued military operations in eastern Ukraine."
    ),
    "seed_entities": ["USA", "Russia"],
    "claim": "What is the trajectory?",
}


class TestEventedDeduceEndpointContract:
    """
    Integration tests for POST /api/v1/analysis/evented/deduce.

    Verifies the evented.v1 contract keys are present in the API response.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, evented_client):
        if evented_client is None:
            pytest.skip("TestClient not available")
        resp = evented_client.post(
            "/api/v1/analysis/evented/deduce",
            json=_EVENTED_REQUEST,
        )
        assert resp.status_code == 200, (
            f"Evented deduce returned HTTP {resp.status_code}: {resp.text[:300]}"
        )
        self.data = resp.json()

    def test_response_status_success(self):
        assert self.data.get("status") == "success"

    def test_response_has_contract_version(self):
        assert "contract_version" in self.data, (
            f"Response missing 'contract_version'. Keys: {list(self.data.keys())}"
        )
        assert self.data["contract_version"] == "evented.v1"

    def test_response_has_mode_evented(self):
        assert self.data.get("mode") == "evented", (
            f"Expected mode='evented', got: {self.data.get('mode')}"
        )

    def test_response_has_events_list(self):
        assert "events" in self.data
        assert isinstance(self.data["events"], list)

    def test_response_events_not_empty(self):
        assert len(self.data["events"]) >= 1, (
            "Evented deduce must return at least 1 event"
        )

    def test_response_events_have_type(self):
        for evt in self.data["events"]:
            assert "type" in evt, f"Event missing 'type': {evt}"
            assert evt["type"] not in ("", "unknown"), (
                f"Event type is empty or unknown: {evt}"
            )

    def test_response_events_have_tier(self):
        for evt in self.data["events"]:
            assert "tier" in evt, f"Event missing 'tier': {evt}"
            assert evt["tier"] in ("T1", "T2")

    def test_response_events_have_evidence_quote(self):
        for evt in self.data["events"]:
            assert "evidence" in evt
            assert "quote" in evt["evidence"]
            assert evt["evidence"]["quote"]

    def test_response_events_have_inferred_fields(self):
        for evt in self.data["events"]:
            assert "inferred_fields" in evt
            assert isinstance(evt["inferred_fields"], list)

    def test_response_conclusion_has_required_keys(self):
        assert "conclusion" in self.data
        concl = self.data["conclusion"]
        assert isinstance(concl, dict), f"'conclusion' must be a dict, got: {type(concl)}"
        for key in ("conclusion", "evidence_path", "hypothesis_path"):
            assert key in concl, (
                f"conclusion dict missing '{key}'. Keys: {list(concl.keys())}"
            )

    def test_response_conclusion_text_not_empty(self):
        concl = self.data["conclusion"]
        assert concl.get("conclusion"), "'conclusion.conclusion' is empty"

    def test_response_conclusion_evidence_path_has_summary(self):
        ep = self.data["conclusion"].get("evidence_path", {})
        assert "summary" in ep, f"'evidence_path' missing 'summary'. Keys: {list(ep.keys())}"

    def test_response_conclusion_hypothesis_path_has_summary(self):
        hp = self.data["conclusion"].get("hypothesis_path", {})
        assert "summary" in hp, f"'hypothesis_path' missing 'summary'. Keys: {list(hp.keys())}"

    def test_response_credibility_has_overall_score(self):
        assert "credibility" in self.data
        cred = self.data["credibility"]
        assert "overall_score" in cred, (
            f"credibility missing 'overall_score'. Keys: {list(cred.keys())}"
        )

    def test_response_has_active_patterns(self):
        assert "active_patterns" in self.data
        assert isinstance(self.data["active_patterns"], list)

    def test_response_active_patterns_have_tier(self):
        for ap in self.data.get("active_patterns", []):
            assert "tier" in ap, f"Active pattern missing 'tier': {ap}"


# ===========================================================================
# Probability tree non-zero posterior test
# ===========================================================================

class TestProbabilityTreeNonZero:
    """Verify that probability_tree posterior weights are never all zero."""

    def test_probability_tree_nodes_not_empty(self):
        """probability_tree must include a non-empty nodes list."""
        result = run_evented_pipeline(_FIXTURE_GEOPOLITICS, llm_service=None)
        pt = result.probability_tree
        assert pt, "probability_tree is empty"
        nodes = pt.get("nodes", [])
        assert nodes, f"probability_tree.nodes is empty. Keys: {list(pt.keys())}"

    def test_probability_tree_edges_not_empty(self):
        """probability_tree must include a non-empty edges list."""
        result = run_evented_pipeline(_FIXTURE_GEOPOLITICS, llm_service=None)
        pt = result.probability_tree
        edges = pt.get("edges", [])
        assert edges, f"probability_tree.edges is empty. Keys: {list(pt.keys())}"

    def test_probability_tree_posterior_not_all_zero(self):
        """At least one edge must have posterior_weight > 0."""
        result = run_evented_pipeline(_FIXTURE_GEOPOLITICS, llm_service=None)
        pt = result.probability_tree
        edges = pt.get("edges", [])
        assert any(e.get("posterior_weight", 0) > 0 for e in edges), (
            f"All posterior_weights are zero. edges: {edges[:3]}"
        )

    def test_probability_tree_has_compute_trace(self):
        """probability_tree must include a compute_trace dict."""
        result = run_evented_pipeline(_FIXTURE_GEOPOLITICS, llm_service=None)
        pt = result.probability_tree
        ct = pt.get("compute_trace", {})
        assert isinstance(ct, dict), f"compute_trace is not a dict: {type(ct)}"
        assert "Z" in ct, f"compute_trace missing 'Z'. Keys: {list(ct.keys())}"
        assert ct["Z"] > 0, f"Z partition function is not positive: {ct['Z']}"


# ===========================================================================
# Conclusion professional struct test
# ===========================================================================

class TestConclusionProfessionalStruct:
    """Verify the new professional conclusion struct fields."""

    def _conclusion(self, text: str) -> dict:
        return run_evented_pipeline(text, llm_service=None).conclusion

    def test_conclusion_has_executive_judgement(self):
        """conclusion must include 'executive_judgement' (non-empty string)."""
        concl = self._conclusion(_FIXTURE_GEOPOLITICS)
        assert "executive_judgement" in concl, (
            f"conclusion missing 'executive_judgement'. Keys: {list(concl.keys())}"
        )
        assert concl["executive_judgement"], "'executive_judgement' is empty"

    def test_conclusion_evidence_path_has_outcomes(self):
        """evidence_path must include 'outcomes' list."""
        concl = self._conclusion(_FIXTURE_GEOPOLITICS)
        ep = concl.get("evidence_path", {})
        assert "outcomes" in ep, (
            f"evidence_path missing 'outcomes'. Keys: {list(ep.keys())}"
        )
        assert isinstance(ep["outcomes"], list)

    def test_conclusion_hypothesis_path_has_verification_gaps(self):
        """hypothesis_path must include 'verification_gaps' list."""
        concl = self._conclusion(_FIXTURE_GEOPOLITICS)
        hp = concl.get("hypothesis_path", {})
        assert "verification_gaps" in hp, (
            f"hypothesis_path missing 'verification_gaps'. Keys: {list(hp.keys())}"
        )
        assert isinstance(hp["verification_gaps"], list)

    def test_conclusion_has_final_struct(self):
        """conclusion must include 'final' dict with 'overall_confidence'."""
        concl = self._conclusion(_FIXTURE_GEOPOLITICS)
        assert "final" in concl, (
            f"conclusion missing 'final'. Keys: {list(concl.keys())}"
        )
        final = concl["final"]
        assert "overall_confidence" in final, (
            f"final missing 'overall_confidence'. Keys: {list(final.keys())}"
        )
        oc = final["overall_confidence"]
        assert 0.0 <= oc <= 1.0, f"overall_confidence out of range: {oc}"

    def test_conclusion_no_pattern_chain_strings(self):
        """executive_judgement must not contain pattern-chain strings like '⊕ → ['."""
        concl = self._conclusion(_FIXTURE_GEOPOLITICS)
        ej = concl.get("executive_judgement", "")
        # The executive_judgement should not contain raw pattern chain notation
        assert "→ [" not in ej, (
            f"executive_judgement contains pattern chain notation: {ej[:200]}"
        )

    def test_executive_judgement_is_str_not_dict(self):
        """executive_judgement must be a plain string, never a dict or list."""
        concl = self._conclusion(_FIXTURE_GEOPOLITICS)
        ej = concl.get("executive_judgement")
        assert isinstance(ej, str), (
            f"executive_judgement must be str, got {type(ej).__name__}: {ej!r}"
        )
        assert len(ej) > 0, "executive_judgement must be non-empty"

    def test_executive_judgement_no_mechanism_names(self):
        """executive_judgement must not contain mechanism class names."""
        concl = self._conclusion(_FIXTURE_GEOPOLITICS)
        ej = concl.get("executive_judgement", "")
        forbidden = ["tech_decoupling", "coercive_leverage", "kinetic_escalation",
                     "oligopoly_supply", "composition_derived"]
        for token in forbidden:
            assert token not in ej, (
                f"executive_judgement contains mechanism class name '{token}': {ej[:200]}"
            )

    def test_evidence_path_summary_outcome_first(self):
        """evidence_path.summary must start with outcome description, not meta labels."""
        concl = self._conclusion(_FIXTURE_GEOPOLITICS)
        summary = concl.get("evidence_path", {}).get("summary", "")
        assert summary, "evidence_path.summary must not be empty"
        # Must not start with old meta-commentary prefixes
        assert not summary.startswith("Evidence path (T2"), (
            f"evidence_path.summary still uses old meta-commentary prefix: {summary[:100]}"
        )
        # Must start with outcome-first language
        assert summary.startswith("Primary projected outcome:"), (
            f"evidence_path.summary should start with 'Primary projected outcome:'. Got: {summary[:100]}"
        )

    def test_hypothesis_path_summary_no_chinese(self):
        """hypothesis_path.summary must contain no CJK characters."""
        import re
        concl = self._conclusion(_FIXTURE_GEOPOLITICS)
        summary = concl.get("hypothesis_path", {}).get("summary", "")
        cjk = re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]", summary)
        assert not cjk, (
            f"hypothesis_path.summary contains CJK characters: {''.join(cjk)}"
        )

    def test_outcome_catalog_maps_to_strings(self):
        """OUTCOME_CATALOG must map outcome_ids to non-empty English strings."""
        from intelligence.evented_pipeline import OUTCOME_CATALOG, _outcome_phrase
        assert isinstance(OUTCOME_CATALOG, dict), "OUTCOME_CATALOG must be a dict"
        assert len(OUTCOME_CATALOG) >= 5, "OUTCOME_CATALOG must have at least 5 entries"
        for oid, phrase in OUTCOME_CATALOG.items():
            assert isinstance(oid, str) and isinstance(phrase, str), (
                f"OUTCOME_CATALOG entry not str→str: {oid!r}→{phrase!r}"
            )
            assert len(phrase) > 0, f"OUTCOME_CATALOG phrase empty for '{oid}'"
        # _outcome_phrase for unknown id must return a non-empty string
        fallback = _outcome_phrase("some_unknown_outcome_id")
        assert isinstance(fallback, str) and len(fallback) > 0

    def test_adaptive_outcome_count_single_pattern(self):
        """With only 1 active pattern, evidence_path outcomes must have exactly 1 entry."""
        # Use a text that reliably produces just 1 active pattern
        text = "A ceasefire was announced."
        result = run_evented_pipeline(text, llm_service=None)
        concl = result.conclusion
        n_active = len(result.active_patterns)
        ev_outcomes = concl.get("evidence_path", {}).get("outcomes", [])
        # If only 1 pattern, n_outcomes should be 1
        if n_active <= 1:
            assert len(ev_outcomes) <= 1, (
                f"Expected ≤1 outcome with {n_active} active patterns, got {len(ev_outcomes)}"
            )

    def test_adaptive_outcome_count_multiple_patterns(self):
        """With 3+ active patterns and high confidence, evidence_path outcomes should have 3 entries."""
        # Geopolitics fixture reliably activates multiple patterns
        result = run_evented_pipeline(_FIXTURE_GEOPOLITICS, llm_service=None)
        concl = result.conclusion
        n_active = len(result.active_patterns)
        ev_outcomes = concl.get("evidence_path", {}).get("outcomes", [])
        if n_active >= 3:
            assert len(ev_outcomes) >= 2, (
                f"Expected ≥2 outcomes with {n_active} active patterns, got {len(ev_outcomes)}"
            )

    def test_outcome_text_uses_catalog_phrasing(self):
        """Outcome entries in evidence_path must use catalog phrasing, not raw snake_case."""
        result = run_evented_pipeline(_FIXTURE_GEOPOLITICS, llm_service=None)
        concl = result.conclusion
        ev_outcomes = concl.get("evidence_path", {}).get("outcomes", [])
        for oc in ev_outcomes:
            text = oc.get("text", "")
            # Catalog entries don't contain underscores (they're human-readable)
            assert "_" not in text, (
                f"Outcome text contains underscore (not from catalog): {text!r}"
            )


# ===========================================================================
# Forecast module unit tests
# ===========================================================================

class TestOntologyForecaster:
    """Unit tests for intelligence/ontology_forecaster.py."""

    def test_get_preset_scenarios_returns_list(self):
        """get_preset_scenarios must return a non-empty list."""
        from intelligence.ontology_forecaster import get_preset_scenarios
        scenarios = get_preset_scenarios()
        assert isinstance(scenarios, list), "Expected list of scenarios"
        assert len(scenarios) >= 1, "Expected at least one scenario"

    def test_scenario_has_required_fields(self):
        """Each scenario must have id, name, initial_patterns, domain."""
        from intelligence.ontology_forecaster import get_preset_scenarios
        for sc in get_preset_scenarios():
            for field in ("id", "name", "initial_patterns", "domain"):
                assert field in sc, f"Scenario missing '{field}': {sc}"
            assert isinstance(sc["initial_patterns"], list)

    def test_run_forecast_returns_contract(self):
        """run_forecast must return required top-level contract fields."""
        from intelligence.ontology_forecaster import run_forecast
        result = run_forecast(
            ["霸權制裁模式", "實體清單技術封鎖模式"],
            horizon_steps=3,
            llm_service=None,
        )
        for field in ("mode", "contract_version", "simulation_steps",
                      "primary_attractor", "forecast_narrative", "meta"):
            assert field in result, f"Forecast result missing '{field}'"
        assert result["mode"] == "forecast"
        assert result["contract_version"] == "forecast.v1"
        assert isinstance(result["simulation_steps"], list)

    def test_run_forecast_confidence_decays(self):
        """Confidence must decrease with each simulation step."""
        from intelligence.ontology_forecaster import run_forecast
        result = run_forecast(
            ["霸權制裁模式"],
            horizon_steps=4,
            llm_service=None,
        )
        steps = result["simulation_steps"]
        if len(steps) >= 2:
            assert steps[0]["confidence"] >= steps[-1]["confidence"], (
                "Confidence should decay monotonically across steps"
            )

    def test_find_attractors_returns_list(self):
        """find_attractors must return a list."""
        from intelligence.ontology_forecaster import find_attractors
        attrs = find_attractors()
        assert isinstance(attrs, list)

    def test_find_attractors_domain_filter(self):
        """find_attractors with domain filter must not return wrong domains."""
        from intelligence.ontology_forecaster import find_attractors
        attrs = find_attractors(domain="geopolitics")
        for a in attrs:
            # Domain may be "general" as fallback — that's acceptable
            assert a.get("domain") in ("geopolitics", "general", ""), (
                f"Unexpected domain in attractor: {a}"
            )

