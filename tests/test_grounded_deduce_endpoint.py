"""
Integration tests for POST /analysis/grounded/deduce
======================================================

Validates that the endpoint:
1. Returns HTTP 200 with valid JSON on a normal request.
2. Returns all required top-level keys (status, ontological_grounding,
   deduction_result, timestamp).
3. Returns all required deduction_result sub-keys.
4. Handles kuzu_conn=None gracefully (no 500 error).
5. Returns HTTP 422 for invalid request bodies.
6. CoT fallback path returns status="success" and mode="cot_fallback".
"""

from __future__ import annotations

import json
import os
import sys
from types import ModuleType
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Make the backend package importable from the tests directory
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------

_VALID_DEDUCTION_JSON = json.dumps({
    "driving_factor": "Tariff policy is the core nexus",
    "scenario_alpha": {
        "name": "现状延续路径",
        "causal_chain": "Tariff -> Supply disruption -> GDP fall",
        "entities": ["USA", "China"],
        "grounding_paths": ["USA --[TARIFF]--> China"],
        "probability": 0.75,
    },
    "scenario_beta": {
        "name": "结构性断裂路径",
        "causal_chain": "Deal collapse -> Reversal -> Recession",
        "trigger_condition": "Diplomatic failure",
        "probability": 0.25,
    },
    "verification_gap": "Missing real-time data",
    "confidence": 0.82,
})


class _FakeLLM:
    """Stub LLM that always returns the valid deduction JSON."""

    def call(self, **kwargs: Any) -> str:
        return _VALID_DEDUCTION_JSON


def _fake_get_ontological_context(conn: Any, entity: str) -> str:
    """Stub that always returns an empty context string (0-path indicator)."""
    return f"Entity: {entity} | 1-hop: 0 1-hop + 0 2-hop"


def _make_fake_kuzu_context_module() -> ModuleType:
    """Build a fake ontology.kuzu_context_extractor module."""
    mod = ModuleType("ontology.kuzu_context_extractor")
    mod.get_ontological_context = _fake_get_ontological_context  # type: ignore[attr-defined]
    return mod


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """Return a TestClient wired to the real FastAPI app with mocked helpers."""
    from fastapi import FastAPI
    from app.api.routes import analysis as analysis_module

    app = FastAPI()
    app.include_router(analysis_module.router, prefix="/api/v1")

    fake_kuzu_ctx = _make_fake_kuzu_context_module()
    sys.modules.setdefault("ontology", ModuleType("ontology"))
    sys.modules["ontology.kuzu_context_extractor"] = fake_kuzu_ctx

    with (
        patch.object(analysis_module, "_get_llm_service", return_value=_FakeLLM()),
        patch.object(analysis_module, "_get_kuzu_connection", return_value=None),
        patch.object(analysis_module, "_ensure_intelligence_importable", return_value=None),
    ):
        with TestClient(app) as c:
            yield c


_REQUEST_BODY = {
    "news_fragment": "Trade war between USA and China escalates.",
    "seed_entities": ["USA", "China"],
    "claim": "What will be the impact?",
}

# ---------------------------------------------------------------------------
# Tests: HTTP status
# ---------------------------------------------------------------------------

class TestDeduceEndpointStatus:
    def test_returns_200_on_valid_request(self, client: TestClient) -> None:
        resp = client.post("/api/v1/analysis/grounded/deduce", json=_REQUEST_BODY)
        assert resp.status_code == 200

    def test_returns_422_on_missing_fields(self, client: TestClient) -> None:
        resp = client.post("/api/v1/analysis/grounded/deduce", json={})
        assert resp.status_code == 422

    def test_returns_422_on_empty_body(self, client: TestClient) -> None:
        resp = client.post("/api/v1/analysis/grounded/deduce", content=b"")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: Response shape (CoT fallback path – graph paths = 0)
# ---------------------------------------------------------------------------

class TestDeduceEndpointResponseShape:
    @pytest.fixture(autouse=True)
    def _response(self, client: TestClient) -> None:
        resp = client.post("/api/v1/analysis/grounded/deduce", json=_REQUEST_BODY)
        assert resp.status_code == 200
        self.data = resp.json()

    def test_top_level_status_key(self) -> None:
        assert "status" in self.data

    def test_top_level_status_value(self) -> None:
        assert self.data["status"] == "success"

    def test_top_level_mode_is_cot_fallback(self) -> None:
        # When graph paths are 0 the endpoint signals CoT mode
        assert self.data.get("mode") == "cot_fallback"

    def test_top_level_ontological_grounding_key(self) -> None:
        assert "ontological_grounding" in self.data

    def test_top_level_deduction_result_key(self) -> None:
        assert "deduction_result" in self.data

    def test_top_level_timestamp_key(self) -> None:
        assert "timestamp" in self.data

    def test_ontological_grounding_seed_entities(self) -> None:
        grounding = self.data["ontological_grounding"]
        assert "seed_entities" in grounding

    def test_ontological_grounding_total_paths(self) -> None:
        grounding = self.data["ontological_grounding"]
        assert "total_paths_extracted" in grounding

    def test_deduction_result_driving_factor(self) -> None:
        dr = self.data["deduction_result"]
        assert "driving_factor" in dr

    def test_deduction_result_scenario_alpha(self) -> None:
        dr = self.data["deduction_result"]
        assert "scenario_alpha" in dr

    def test_deduction_result_scenario_alpha_causal_chain(self) -> None:
        dr = self.data["deduction_result"]
        assert "causal_chain" in dr["scenario_alpha"]

    def test_deduction_result_scenario_beta(self) -> None:
        dr = self.data["deduction_result"]
        assert "scenario_beta" in dr

    def test_deduction_result_scenario_beta_trigger_condition(self) -> None:
        dr = self.data["deduction_result"]
        assert "trigger_condition" in dr["scenario_beta"]

    def test_deduction_result_verification_gap(self) -> None:
        dr = self.data["deduction_result"]
        assert "verification_gap" in dr

    def test_deduction_result_confidence(self) -> None:
        dr = self.data["deduction_result"]
        assert "confidence" in dr

    def test_deduction_result_graph_evidence(self) -> None:
        dr = self.data["deduction_result"]
        assert "graph_evidence" in dr

    def test_deduction_result_is_valid_json(self) -> None:
        # Round-trip: ensure the whole response is JSON-serialisable
        assert json.loads(json.dumps(self.data))


# ---------------------------------------------------------------------------
# Tests: kuzu_conn=None does not cause a 500
# ---------------------------------------------------------------------------

class TestDeduceEndpointWithoutKuzu:
    def test_no_500_when_kuzu_unavailable(self, client: TestClient) -> None:
        """The endpoint must succeed even without a KuzuDB connection."""
        resp = client.post("/api/v1/analysis/grounded/deduce", json=_REQUEST_BODY)
        assert resp.status_code != 500

    def test_returns_200_without_kuzu(self, client: TestClient) -> None:
        resp = client.post("/api/v1/analysis/grounded/deduce", json=_REQUEST_BODY)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests: LLM failure returns fallback result (not 500)
# ---------------------------------------------------------------------------

class TestDeduceEndpointLLMFailure:
    def test_llm_exception_returns_fallback_not_500(self) -> None:
        """If the LLM raises, the endpoint should still return 200 via CoT fallback."""
        from fastapi import FastAPI
        from app.api.routes import analysis as analysis_module

        class _BrokenLLM:
            def call(self, **kwargs: Any) -> str:
                raise RuntimeError("LLM service unavailable")

        app = FastAPI()
        app.include_router(analysis_module.router, prefix="/api/v1")

        fake_kuzu_ctx = _make_fake_kuzu_context_module()
        sys.modules.setdefault("ontology", ModuleType("ontology"))
        sys.modules["ontology.kuzu_context_extractor"] = fake_kuzu_ctx

        with (
            patch.object(analysis_module, "_get_llm_service", return_value=_BrokenLLM()),
            patch.object(analysis_module, "_get_kuzu_connection", return_value=None),
            patch.object(analysis_module, "_ensure_intelligence_importable", return_value=None),
        ):
            with TestClient(app) as c:
                resp = c.post("/api/v1/analysis/grounded/deduce", json=_REQUEST_BODY)
        assert resp.status_code == 200
        data = resp.json()
        assert "deduction_result" in data
        dr = data["deduction_result"]
        # When LLM fails, _cot_deduction_from_text returns the hard-coded fallback
        assert "driving_factor" in dr
        assert "scenario_alpha" in dr
        assert "scenario_beta" in dr
        assert "verification_gap" in dr
        assert "confidence" in dr
        assert float(dr["confidence"]) <= 0.55


# ---------------------------------------------------------------------------
# Tests: CoT fallback – empty seed_entities still yields complete schema
# ---------------------------------------------------------------------------

class TestDeduceEndpointEmptySeedEntities:
    """Endpoint must return a full deduction_result even when seed_entities=[]."""

    def test_empty_seed_entities_returns_success(self) -> None:
        from fastapi import FastAPI
        from app.api.routes import analysis as analysis_module

        app = FastAPI()
        app.include_router(analysis_module.router, prefix="/api/v1")

        body = {
            "news_fragment": "Israel launched airstrikes on Gaza.",
            "seed_entities": [],
            "claim": "What will happen next?",
        }

        fake_kuzu_ctx = _make_fake_kuzu_context_module()
        sys.modules.setdefault("ontology", ModuleType("ontology"))
        sys.modules["ontology.kuzu_context_extractor"] = fake_kuzu_ctx

        with (
            patch.object(analysis_module, "_get_llm_service", return_value=_FakeLLM()),
            patch.object(analysis_module, "_get_kuzu_connection", return_value=None),
            patch.object(analysis_module, "_ensure_intelligence_importable", return_value=None),
        ):
            with TestClient(app) as c:
                resp = c.post("/api/v1/analysis/grounded/deduce", json=body)

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        dr = data["deduction_result"]
        for field in ("driving_factor", "scenario_alpha", "scenario_beta",
                      "verification_gap", "confidence", "graph_evidence"):
            assert field in dr, f"Missing field in deduction_result: {field}"
        assert "causal_chain" in dr["scenario_alpha"]
        assert "trigger_condition" in dr["scenario_beta"]
