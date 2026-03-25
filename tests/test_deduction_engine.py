"""
Unit tests for the DeductionEngine (Deduction Soul)
====================================================

Tests cover:
1. CausalChain.to_text() rendering
2. DeductionResult.to_strict_json() output shape
3. _parse_causal_chain: normal, partial, and empty inputs
4. _validate_and_structure_deduction: full valid JSON
5. _fallback_deduction: returns confidence=0.0
6. deduce_from_ontological_paths: success path and JSON decode error fallback
7. ScenarioType enum values
"""

from __future__ import annotations

import json
import sys
import os

import pytest

_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(_BACKEND_DIR))

from intelligence.deduction_engine import (
    CausalChain,
    DeductionEngine,
    DeductionResult,
    DEDUCTION_SOUL_SYSTEM_PROMPT,
    Scenario,
    ScenarioType,
)


# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------

class _FakeLLM:
    """Fake LLM service that returns a pre-configured JSON string."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.last_call_kwargs: dict = {}

    def call(self, prompt: str, **kwargs) -> str:  # noqa: ANN003
        self.last_call_kwargs = {"prompt": prompt, **kwargs}
        return self._response


_VALID_DEDUCTION_JSON = {
    "driving_factor": "US-China trade tension is the core nexus",
    "scenario_alpha": {
        "name": "现状延续路径",
        "causal_chain": "Tariff increase -> Supply chain disruption -> GDP contraction",
        "entities": ["USA", "China"],
        "grounding_paths": ["USA --[IMPOSES_TARIFF]--> China"],
        "probability": 0.75,
    },
    "scenario_beta": {
        "name": "结构性断裂路径",
        "causal_chain": "Trade deal collapses -> Supply chain reversal -> Recession",
        "trigger_condition": "Diplomatic breakdown removes tariff waiver",
        "probability": 0.25,
    },
    "verification_gap": "Missing real-time tariff rate data",
    "confidence": 0.82,
}


# ---------------------------------------------------------------------------
# CausalChain tests
# ---------------------------------------------------------------------------

class TestCausalChain:
    def test_to_text_full(self) -> None:
        chain = CausalChain(
            source_fact="A",
            triggering_relation="B",
            resulting_change="C",
        )
        assert chain.to_text() == "A -> B -> C"

    def test_to_text_empty_parts(self) -> None:
        chain = CausalChain(source_fact="", triggering_relation="", resulting_change="")
        assert chain.to_text() == " ->  -> "

    def test_entities_default_empty(self) -> None:
        chain = CausalChain(source_fact="X", triggering_relation="Y", resulting_change="Z")
        assert chain.entities_involved == []

    def test_entities_provided(self) -> None:
        chain = CausalChain(
            source_fact="X",
            triggering_relation="Y",
            resulting_change="Z",
            entities_involved=["E1", "E2"],
        )
        assert chain.entities_involved == ["E1", "E2"]


# ---------------------------------------------------------------------------
# DeductionResult tests
# ---------------------------------------------------------------------------

class TestDeductionResult:
    def _make_result(self) -> DeductionResult:
        alpha_chain = CausalChain(
            source_fact="Fact A",
            triggering_relation="Rel B",
            resulting_change="Result C",
            entities_involved=["Entity1"],
        )
        beta_chain = CausalChain(
            source_fact="Premise X",
            triggering_relation="Collapse",
            resulting_change="State Z",
        )
        alpha = Scenario(
            name="现状延续路径",
            scenario_type=ScenarioType.CONTINUATION,
            causal_chain=alpha_chain,
            probability=0.8,
            grounding_paths=["A --[REL]--> B"],
        )
        beta = Scenario(
            name="结构性断裂路径",
            scenario_type=ScenarioType.STRUCTURAL_BREAK,
            causal_chain=beta_chain,
            probability=0.2,
            grounding_paths=["Trigger condition description"],
        )
        return DeductionResult(
            driving_factor="Core nexus",
            scenario_alpha=alpha,
            scenario_beta=beta,
            verification_gap="Missing data",
            deduction_confidence=0.85,
        )

    def test_to_strict_json_keys(self) -> None:
        result = self._make_result()
        j = result.to_strict_json()
        assert "driving_factor" in j
        assert "scenario_alpha" in j
        assert "scenario_beta" in j
        assert "verification_gap" in j
        assert "confidence" in j

    def test_to_strict_json_alpha_shape(self) -> None:
        j = self._make_result().to_strict_json()
        alpha = j["scenario_alpha"]
        assert "name" in alpha
        assert "causal_chain" in alpha
        assert "entities" in alpha
        assert "grounding_paths" in alpha
        assert "probability" in alpha
        assert alpha["causal_chain"] == "Fact A -> Rel B -> Result C"

    def test_to_strict_json_beta_trigger_condition(self) -> None:
        j = self._make_result().to_strict_json()
        beta = j["scenario_beta"]
        assert beta["trigger_condition"] == "Trigger condition description"

    def test_to_strict_json_beta_no_grounding_paths(self) -> None:
        result = self._make_result()
        result.scenario_beta.grounding_paths = []
        j = result.to_strict_json()
        assert j["scenario_beta"]["trigger_condition"] == "Unknown"

    def test_confidence_value(self) -> None:
        j = self._make_result().to_strict_json()
        assert j["confidence"] == 0.85


# ---------------------------------------------------------------------------
# DeductionEngine unit tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def engine_with_valid_llm() -> DeductionEngine:
    llm = _FakeLLM(json.dumps(_VALID_DEDUCTION_JSON))
    return DeductionEngine(llm_service=llm)


@pytest.fixture()
def engine_with_bad_llm() -> DeductionEngine:
    """LLM returns invalid JSON."""
    llm = _FakeLLM("this is not json {broken}")
    return DeductionEngine(llm_service=llm)


class TestDeductionEngineParseChain:
    def test_full_chain(self) -> None:
        engine = DeductionEngine(_FakeLLM("{}"))
        chain = engine._parse_causal_chain("A -> B -> C", ["E1"])
        assert chain.source_fact == "A"
        assert chain.triggering_relation == "B"
        assert chain.resulting_change == "C"
        assert chain.entities_involved == ["E1"]

    def test_partial_chain(self) -> None:
        engine = DeductionEngine(_FakeLLM("{}"))
        chain = engine._parse_causal_chain("A -> B", [])
        assert chain.source_fact == "A"
        assert chain.triggering_relation == "B"
        assert chain.resulting_change == ""

    def test_empty_chain(self) -> None:
        engine = DeductionEngine(_FakeLLM("{}"))
        chain = engine._parse_causal_chain("", [])
        assert chain.source_fact == ""
        assert chain.triggering_relation == ""
        assert chain.resulting_change == ""


class TestDeductionEngineValidate:
    def test_valid_json_builds_result(self, engine_with_valid_llm: DeductionEngine) -> None:
        result = engine_with_valid_llm._validate_and_structure_deduction(
            _VALID_DEDUCTION_JSON
        )
        assert result.driving_factor == "US-China trade tension is the core nexus"
        assert result.scenario_alpha.probability == 0.75
        assert result.scenario_beta.probability == 0.25
        assert result.deduction_confidence == 0.82
        assert result.verification_gap == "Missing real-time tariff rate data"

    def test_alpha_grounding_paths(self, engine_with_valid_llm: DeductionEngine) -> None:
        result = engine_with_valid_llm._validate_and_structure_deduction(
            _VALID_DEDUCTION_JSON
        )
        assert result.scenario_alpha.grounding_paths == [
            "USA --[IMPOSES_TARIFF]--> China"
        ]

    def test_beta_trigger_stored_in_grounding_paths(
        self, engine_with_valid_llm: DeductionEngine
    ) -> None:
        result = engine_with_valid_llm._validate_and_structure_deduction(
            _VALID_DEDUCTION_JSON
        )
        assert result.scenario_beta.grounding_paths == [
            "Diplomatic breakdown removes tariff waiver"
        ]

    def test_missing_keys_use_defaults(
        self, engine_with_valid_llm: DeductionEngine
    ) -> None:
        result = engine_with_valid_llm._validate_and_structure_deduction({})
        assert result.driving_factor == "Unknown"
        assert result.deduction_confidence == 0.75


class TestDeductionEngineFallback:
    def test_fallback_confidence_zero(self) -> None:
        engine = DeductionEngine(_FakeLLM("{}"))
        result = engine._fallback_deduction("some news", "some context")
        assert result.deduction_confidence == 0.0

    def test_fallback_verification_gap_message(self) -> None:
        engine = DeductionEngine(_FakeLLM("{}"))
        result = engine._fallback_deduction("some news", "some context")
        assert "LLM" in result.verification_gap or "格式错误" in result.verification_gap

    def test_fallback_alpha_scenario_type(self) -> None:
        engine = DeductionEngine(_FakeLLM("{}"))
        result = engine._fallback_deduction("news", "ctx")
        assert result.scenario_alpha.scenario_type == ScenarioType.CONTINUATION

    def test_fallback_beta_scenario_type(self) -> None:
        engine = DeductionEngine(_FakeLLM("{}"))
        result = engine._fallback_deduction("news", "ctx")
        assert result.scenario_beta.scenario_type == ScenarioType.STRUCTURAL_BREAK


class TestDeductionEngineDeduceFromPaths:
    def test_success_path_returns_result(
        self, engine_with_valid_llm: DeductionEngine
    ) -> None:
        result = engine_with_valid_llm.deduce_from_ontological_paths(
            news_summary="Trade war escalates",
            ontological_context="USA --[IMPOSES_TARIFF]--> China",
            seed_entities=["USA", "China"],
        )
        assert result.driving_factor == "US-China trade tension is the core nexus"
        assert result.deduction_confidence == 0.82

    def test_llm_called_with_low_temperature(
        self, engine_with_valid_llm: DeductionEngine
    ) -> None:
        engine_with_valid_llm.deduce_from_ontological_paths(
            news_summary="Test event",
            ontological_context="A -> B",
            seed_entities=["A"],
        )
        kwargs = engine_with_valid_llm.llm.last_call_kwargs
        assert kwargs.get("temperature", 1.0) <= 0.3

    def test_json_decode_error_returns_fallback(
        self, engine_with_bad_llm: DeductionEngine
    ) -> None:
        result = engine_with_bad_llm.deduce_from_ontological_paths(
            news_summary="Some event",
            ontological_context="No paths",
            seed_entities=["X"],
        )
        assert result.deduction_confidence == 0.0

    def test_news_summary_included_in_prompt(
        self, engine_with_valid_llm: DeductionEngine
    ) -> None:
        summary = "Trade war between USA and China escalates dramatically"
        engine_with_valid_llm.deduce_from_ontological_paths(
            news_summary=summary,
            ontological_context="ctx",
            seed_entities=["E"],
        )
        prompt = engine_with_valid_llm.llm.last_call_kwargs.get("prompt", "")
        assert summary in prompt


# ---------------------------------------------------------------------------
# ScenarioType tests
# ---------------------------------------------------------------------------

class TestScenarioType:
    def test_continuation_value(self) -> None:
        assert ScenarioType.CONTINUATION.value == "现状延续路径"

    def test_structural_break_value(self) -> None:
        assert ScenarioType.STRUCTURAL_BREAK.value == "结构性断裂路径"

    def test_bifurcation_value(self) -> None:
        assert ScenarioType.BIFURCATION.value == "分岔演化路径"


# ---------------------------------------------------------------------------
# System prompt tests
# ---------------------------------------------------------------------------

class TestDeductionSoulSystemPrompt:
    def test_prompt_forbids_fabrication(self) -> None:
        assert "严禁" in DEDUCTION_SOUL_SYSTEM_PROMPT

    def test_prompt_requires_json(self) -> None:
        assert "JSON" in DEDUCTION_SOUL_SYSTEM_PROMPT
