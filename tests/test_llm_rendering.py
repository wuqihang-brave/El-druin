"""
tests/test_llm_rendering.py
============================
Unit tests for the LLM-based rendering / paraphrase layer added to
the evented pipeline.

Tests cover:
- render_conclusion_with_llm returns rendered fields when LLM is valid
- Falls back to raw when LLM changes numeric values (numeric guardrail)
- Falls back to raw when LLM injects disallowed jargon substrings
- Falls back to raw when LLM output exceeds 3 sentences
- run_evented_pipeline conclusion includes raw fields and rendering_meta
- _extract_numeric_values helper works correctly
- _count_sentences helper works correctly
"""

from __future__ import annotations

import json
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from intelligence.evented_pipeline import (
    render_conclusion_with_llm,
    run_evented_pipeline,
    _extract_numeric_values,
    _count_sentences,
)


# ---------------------------------------------------------------------------
# Fixtures / shared helpers
# ---------------------------------------------------------------------------

_NEWS_FRAGMENT = (
    "The United States imposed sweeping new tariffs on Chinese semiconductor "
    "exports, citing national security concerns. Analysts warn of supply-chain "
    "disruptions across global markets."
)

_RAW_EJ  = "The most probable projected outcome is: market fragmentation (assessed probability 65%)."
_RAW_EP  = "Primary projected outcome: market fragmentation. This trajectory is assessed at 65% probability."
_RAW_HP  = "Contingent outcome: structural realignment. This scenario is contingent on: reversal."

_ALPHA_PROB = 0.65
_BETA_PROB  = 0.35
_CONF       = 0.52


def _make_llm(response: str):
    """Stub LLM that always returns *response*."""

    class _StubLLM:
        def call(self, **kwargs):
            return response

    return _StubLLM()


def _render(llm_response: str, **overrides):
    """Helper: call render_conclusion_with_llm with defaults + overrides."""
    kwargs = dict(
        news_fragment=_NEWS_FRAGMENT,
        executive_judgement_raw=_RAW_EJ,
        evidence_summary_raw=_RAW_EP,
        hypothesis_summary_raw=_RAW_HP,
        alpha_prob=_ALPHA_PROB,
        beta_prob=_BETA_PROB,
        composite_confidence=_CONF,
        verification_gaps=["reversal of dominant trajectory"],
        allowed_entities=["United States", "China"],
        llm_service=_make_llm(llm_response),
    )
    kwargs.update(overrides)
    return render_conclusion_with_llm(**kwargs)


# ===========================================================================
# A. _extract_numeric_values helper
# ===========================================================================

class TestExtractNumericValues:
    def test_percentage_extraction(self):
        vals = _extract_numeric_values("The probability is 73% based on evidence.")
        assert round(0.73, 4) in vals

    def test_decimal_extraction(self):
        vals = _extract_numeric_values("Confidence: 0.52")
        assert round(0.52, 4) in vals

    def test_no_numbers(self):
        vals = _extract_numeric_values("No numeric values here.")
        assert vals == set()

    def test_multiple_numbers(self):
        vals = _extract_numeric_values("Alpha: 65%, beta: 35%, conf 0.52")
        assert round(0.65, 4) in vals
        assert round(0.35, 4) in vals
        assert round(0.52, 4) in vals


# ===========================================================================
# B. _count_sentences helper
# ===========================================================================

class TestCountSentences:
    def test_one_sentence(self):
        assert _count_sentences("This is a sentence.") == 1

    def test_two_sentences(self):
        assert _count_sentences("First sentence. Second sentence.") == 2

    def test_three_sentences(self):
        assert _count_sentences("One. Two. Three.") == 3

    def test_four_sentences(self):
        assert _count_sentences("One. Two. Three. Four.") == 4

    def test_empty(self):
        assert _count_sentences("") == 0


# ===========================================================================
# C. render_conclusion_with_llm – valid LLM response
# ===========================================================================

class TestRenderConclusionWithLLM:

    def _valid_response(self):
        """Build a valid JSON response that obeys all guardrails."""
        return json.dumps({
            "executive_judgement": (
                "Market fragmentation is the primary projected outcome, assessed at 65% probability "
                "amid sweeping new tariffs on semiconductor exports."
            ),
            "evidence_path_summary": (
                "The 65% probability trajectory reflects corroborating evidence of supply-chain "
                "disruptions signalled by the tariff action."
            ),
            "hypothesis_path_summary": (
                "The contingent scenario of structural realignment remains dependent on a "
                "reversal of dominant trajectory."
            ),
        })

    def test_rendered_fields_present_when_llm_valid(self):
        result = _render(self._valid_response())
        assert "executive_judgement" in result
        assert "evidence_path_summary" in result
        assert "hypothesis_path_summary" in result
        assert "rendering_meta" in result

    def test_rendering_meta_enabled_when_llm_called(self):
        result = _render(self._valid_response())
        assert result["rendering_meta"]["enabled"] is True

    def test_rendered_text_differs_from_raw_on_success(self):
        result = _render(self._valid_response())
        # When guardrails don't trigger, the rendered executive_judgement should
        # contain content from the LLM output (which includes "sweeping new tariffs")
        assert result["rendering_meta"]["guardrails_triggered"] is False
        assert "sweeping new tariffs" in result["executive_judgement"]

    def test_no_guardrails_triggered_on_valid_response(self):
        result = _render(self._valid_response())
        assert result["rendering_meta"]["guardrails_triggered"] is False

    def test_llm_none_returns_raw(self):
        result = render_conclusion_with_llm(
            news_fragment=_NEWS_FRAGMENT,
            executive_judgement_raw=_RAW_EJ,
            evidence_summary_raw=_RAW_EP,
            hypothesis_summary_raw=_RAW_HP,
            alpha_prob=_ALPHA_PROB,
            beta_prob=_BETA_PROB,
            composite_confidence=_CONF,
            verification_gaps=[],
            allowed_entities=[],
            llm_service=None,
        )
        assert result["executive_judgement"] == _RAW_EJ
        assert result["evidence_path_summary"] == _RAW_EP
        assert result["hypothesis_path_summary"] == _RAW_HP
        assert result["rendering_meta"]["enabled"] is False


# ===========================================================================
# D. Numeric guardrail
# ===========================================================================

class TestNumericGuardrail:
    """LLM that changes a probability value must trigger fallback to raw."""

    def _response_with_bad_number(self):
        return json.dumps({
            "executive_judgement": (
                "Market fragmentation is projected at 80% probability — "
                "an invented number not in the allowed set."
            ),
            "evidence_path_summary": _RAW_EP,
            "hypothesis_path_summary": _RAW_HP,
        })

    def test_changed_number_triggers_fallback(self):
        result = _render(self._response_with_bad_number())
        # executive_judgement should fall back to raw
        assert result["executive_judgement"] == _RAW_EJ
        assert result["rendering_meta"]["guardrails_triggered"] is True

    def test_allowed_numbers_do_not_trigger_fallback(self):
        """A response that mentions only allowed percentages must not fallback."""
        response = json.dumps({
            "executive_judgement": (
                "Market fragmentation is the primary projected outcome, assessed at 65% probability."
            ),
            "evidence_path_summary": "The trajectory reflects 52% overall confidence.",
            "hypothesis_path_summary": "The contingent scenario has a 35% probability.",
        })
        result = _render(response)
        assert result["rendering_meta"]["guardrails_triggered"] is False


# ===========================================================================
# E. Disallowed substring guardrail
# ===========================================================================

class TestDisallowedSubstringGuardrail:

    def test_pattern_keyword_triggers_fallback(self):
        response = json.dumps({
            "executive_judgement": "The active pattern coercive_leverage drives escalation.",
            "evidence_path_summary": _RAW_EP,
            "hypothesis_path_summary": _RAW_HP,
        })
        result = _render(response)
        assert result["executive_judgement"] == _RAW_EJ
        assert result["rendering_meta"]["guardrails_triggered"] is True

    def test_mechanism_keyword_triggers_fallback(self):
        response = json.dumps({
            "executive_judgement": "The mechanism class drives the outcome.",
            "evidence_path_summary": _RAW_EP,
            "hypothesis_path_summary": _RAW_HP,
        })
        result = _render(response)
        assert result["executive_judgement"] == _RAW_EJ
        assert result["rendering_meta"]["guardrails_triggered"] is True

    def test_composition_symbol_triggers_fallback(self):
        response = json.dumps({
            "executive_judgement": "The ⊕ operator combines signals.",
            "evidence_path_summary": _RAW_EP,
            "hypothesis_path_summary": _RAW_HP,
        })
        result = _render(response)
        assert result["executive_judgement"] == _RAW_EJ
        assert result["rendering_meta"]["guardrails_triggered"] is True


# ===========================================================================
# F. Sentence-length guardrail
# ===========================================================================

class TestSentenceLengthGuardrail:

    def test_more_than_3_sentences_triggers_fallback(self):
        long_text = "Sentence one. Sentence two. Sentence three. Sentence four."
        response = json.dumps({
            "executive_judgement": long_text,
            "evidence_path_summary": _RAW_EP,
            "hypothesis_path_summary": _RAW_HP,
        })
        result = _render(response)
        assert result["executive_judgement"] == _RAW_EJ
        assert result["rendering_meta"]["guardrails_triggered"] is True

    def test_exactly_3_sentences_passes(self):
        text_3 = "Outcome one is primary. Outcome two is contingent. Confidence is calibrated."
        response = json.dumps({
            "executive_judgement": text_3,
            "evidence_path_summary": _RAW_EP,
            "hypothesis_path_summary": _RAW_HP,
        })
        result = _render(response)
        # 3 sentences must not trigger the sentence-length guardrail
        # (other guardrails might still trigger, but not the length one)
        # We verify by constructing a response with no other violations
        text_3_safe = "The primary outcome is market fragmentation at 65% probability. The contingent scenario depends on a reversal. Confidence remains at 52%."
        response_safe = json.dumps({
            "executive_judgement": text_3_safe,
            "evidence_path_summary": "The evidence path supports a 65% trajectory.",
            "hypothesis_path_summary": "The 35% contingent scenario requires a reversal.",
        })
        result_safe = _render(response_safe)
        assert result_safe["executive_judgement"] == text_3_safe, (
            f"3 sentences should not trigger fallback, got: {result_safe['executive_judgement']!r}"
        )


# ===========================================================================
# G. Integration: run_evented_pipeline includes raw fields and rendering_meta
# ===========================================================================

class TestPipelineRenderedFields:

    _TEXT = (
        "The United States imposed sweeping new sanctions on Russian energy exports, "
        "raising fears of a global energy supply shock."
    )

    def test_conclusion_has_raw_fields(self):
        """run_evented_pipeline conclusion must include *_raw fields."""
        result = run_evented_pipeline(self._TEXT, llm_service=None)
        concl = result.conclusion
        assert "executive_judgement_raw" in concl, (
            f"conclusion missing 'executive_judgement_raw'. Keys: {list(concl.keys())}"
        )
        assert concl["executive_judgement_raw"], "executive_judgement_raw must be non-empty"

    def test_evidence_path_has_summary_raw(self):
        result = run_evented_pipeline(self._TEXT, llm_service=None)
        ep = result.conclusion.get("evidence_path", {})
        assert "summary_raw" in ep, (
            f"evidence_path missing 'summary_raw'. Keys: {list(ep.keys())}"
        )
        assert ep["summary_raw"], "evidence_path.summary_raw must be non-empty"

    def test_hypothesis_path_has_summary_raw(self):
        result = run_evented_pipeline(self._TEXT, llm_service=None)
        hp = result.conclusion.get("hypothesis_path", {})
        assert "summary_raw" in hp, (
            f"hypothesis_path missing 'summary_raw'. Keys: {list(hp.keys())}"
        )
        assert hp["summary_raw"], "hypothesis_path.summary_raw must be non-empty"

    def test_conclusion_has_rendering_meta(self):
        result = run_evented_pipeline(self._TEXT, llm_service=None)
        concl = result.conclusion
        assert "rendering_meta" in concl, (
            f"conclusion missing 'rendering_meta'. Keys: {list(concl.keys())}"
        )
        meta = concl["rendering_meta"]
        assert isinstance(meta, dict)
        assert "enabled" in meta
        assert "guardrails_triggered" in meta

    def test_rendering_meta_disabled_without_llm(self):
        result = run_evented_pipeline(self._TEXT, llm_service=None)
        meta = result.conclusion.get("rendering_meta", {})
        assert meta.get("enabled") is False

    def test_rendered_fields_exist_with_stub_llm(self):
        """When LLM returns valid JSON, rendered fields are present."""
        valid_json = json.dumps({
            "executive_judgement": "Energy supply disruption is the primary projected outcome.",
            "evidence_path_summary": "The trajectory is supported by the sanctions signal.",
            "hypothesis_path_summary": "A contingent recovery scenario remains plausible.",
        })

        class _ValidLLM:
            def call(self, **kwargs):
                return valid_json

        result = run_evented_pipeline(self._TEXT, llm_service=_ValidLLM())
        concl = result.conclusion
        assert concl.get("executive_judgement"), "rendered executive_judgement must be non-empty"
        assert concl.get("rendering_meta", {}).get("enabled") is True

    def test_numeric_guardrail_fallback_in_pipeline(self):
        """When LLM changes a numeric value, rendered field falls back to raw."""
        # Build a response that introduces a fabricated 99% probability
        bad_json = json.dumps({
            "executive_judgement": "Outcome is projected at 99% probability — invented.",
            "evidence_path_summary": "Evidence supports a 99% trajectory.",
            "hypothesis_path_summary": "Contingent at 1%.",
        })

        class _BadLLM:
            def call(self, **kwargs):
                return bad_json

        result = run_evented_pipeline(self._TEXT, llm_service=_BadLLM())
        concl = result.conclusion
        ej_raw = concl.get("executive_judgement_raw", "")
        ej     = concl.get("executive_judgement", "")
        # The rendered field must equal raw (fallback) because numeric guardrail fired
        assert ej == ej_raw, (
            f"Numeric guardrail failed: rendered field '{ej}' should equal raw '{ej_raw}'"
        )
        assert concl.get("rendering_meta", {}).get("guardrails_triggered") is True
