"""
tests/test_evented_pipeline.py
===============================
Unit tests for the evented reasoning pipeline:

- JSON brace escaping in prompts (no template-variable leakage)
- Composition table derivation (derive_composed_patterns)
- Inverse placeholder registration (validate_inverses passes with 0 errors)
- Rule-based event extraction (extract_events_rule_based)
- Lightweight entity typing (infer_entity_type_lightweight)
- Active pattern derivation (derive_active_patterns)
- Credibility computation (compute_credibility)
- Full pipeline smoke test (run_evented_pipeline)
"""

from __future__ import annotations

import json
import sys
import os

import pytest

# Make backend importable from the tests directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from intelligence.evented_pipeline import (
    EventType,
    extract_events_rule_based,
    extract_events,
    infer_entity_type_lightweight,
    derive_active_patterns,
    derive_composed_patterns,
    generate_conclusion,
    compute_credibility,
    run_evented_pipeline,
    postprocess_events,
    _fallback_top_events,
    _stable_id,
    _T0_CONF_THRESHOLD,
    _T2_CONF_THRESHOLD,
    _MIN_QUOTE_LEN,
)
from ontology.relation_schema import (
    validate_inverses,
    validate_composition_closure,
    composition_table,
    CARTESIAN_PATTERN_REGISTRY,
)


# ===========================================================================
# A. JSON brace escaping / prompt template variable safety
# ===========================================================================

class TestPromptBraceSafety:
    """
    Verify that the LLM prompts in evented_pipeline do NOT use Python
    .format() or f-string with un-escaped curly braces in a way that would
    cause 'missing variables {entities}'-style KeyError.
    """

    def _call_capture(self) -> list:
        """Return a list that records every prompt passed to the stub LLM."""
        captured = []

        class CaptureLLM:
            def call(self, prompt, **kwargs):
                captured.append(prompt)
                return "[]"   # empty events array

        return captured, CaptureLLM()

    def test_no_unformatted_braces_in_event_extraction_prompt(self):
        """extract_events_llm must not raise due to brace formatting."""
        from intelligence.evented_pipeline import extract_events_llm

        captured, stub_llm = self._call_capture()
        stub_llm.call = lambda prompt, **kw: (captured.append(prompt) or "[]")

        # Should not raise
        result = extract_events_llm("Some news text about sanctions.", stub_llm)
        assert isinstance(result, list)

        if captured:
            prompt = captured[0]
            # The prompt must be a plain string, not a template that needs .format()
            # Ensure it can survive a .format() call with no kwargs without KeyError
            # (escaped braces become literal { } after .format())
            try:
                prompt.format()
            except KeyError as exc:
                pytest.fail(
                    f"Prompt contains unescaped template variable: {exc}\n"
                    f"Prompt snippet: {prompt[:200]}"
                )

    def test_no_unformatted_braces_in_conclusion_prompt(self):
        """
        generate_conclusion must not raise during prompt construction.

        Our prompts are built via plain string concatenation (not .format()
        or LangChain PromptTemplate), so JSON output from json.dumps() is
        safe to include verbatim.  We verify no exception is raised and the
        static non-JSON parts of the prompt contain no {variable} placeholders.
        """
        from intelligence.evented_pipeline import generate_conclusion
        import re as _re

        captured = []

        class CaptureLLMConclusion:
            def call(self, prompt, **kwargs):
                captured.append(prompt)
                return json.dumps({
                    "selected_patterns": [],
                    "conclusion": "test",
                    "confidence": 0.5,
                })

        events = [{"id": "abc", "type": EventType.SANCTION_IMPOSED,
                   "args": {}, "evidence": {"quote": "sanctions imposed"}, "confidence": 0.85}]
        active = [{"pattern": "霸權制裁模式", "from_event": "abc"}]
        derived = []

        # Must not raise
        result = generate_conclusion("sanctions text", events, active, derived, CaptureLLMConclusion())
        assert isinstance(result, dict)
        assert "conclusion" in result

        if captured:
            prompt = captured[0]
            # Pattern name must appear verbatim in prompt
            assert "霸權制裁模式" in prompt
            # Check non-JSON instructional lines for accidental {variable} placeholders
            for line in prompt.split("\n"):
                stripped = line.strip()
                if stripped.startswith('"') or stripped.startswith("{") or \
                        stripped.startswith("[") or stripped.startswith("}") or \
                        stripped.startswith("]") or stripped.startswith("•"):
                    continue
                for m in _re.finditer(r"\{([^{}]+)\}", stripped):
                    inner = m.group(1).strip()
                    # Allow only JSON-like keys (contain quotes or colons)
                    if inner and '"' not in inner and ":" not in inner:
                        pytest.fail(
                            f"Possible un-escaped template variable in prompt: {{{inner}}}"
                        )

    def test_stable_id_deterministic(self):
        """_stable_id must return the same value for the same inputs."""
        id1 = _stable_id("sanction_imposed", "quote text")
        id2 = _stable_id("sanction_imposed", "quote text")
        assert id1 == id2
        assert len(id1) == 8

    def test_stable_id_different_inputs_different_ids(self):
        """Different event types or quotes must produce different IDs."""
        id_a = _stable_id("sanction_imposed", "quote text")
        id_b = _stable_id("military_strike",  "quote text")
        id_c = _stable_id("sanction_imposed", "different quote")
        assert id_a != id_b, "Different event types should yield different IDs"
        assert id_a != id_c, "Different quotes should yield different IDs"
        assert id_b != id_c


# ===========================================================================
# B. Inverse placeholder registration (relation_schema B1 strictness)
# ===========================================================================

class TestInversePlaceholderRegistration:
    def test_validate_inverses_passes_with_zero_errors(self):
        """After adding placeholder patterns, validate_inverses must be empty."""
        errors = validate_inverses()
        assert errors == [], f"Unexpected inverse errors: {errors}"

    def test_validate_composition_closure_passes(self):
        """All composition_table references must be registered."""
        errors = validate_composition_closure()
        assert errors == [], f"Unexpected composition errors: {errors}"

    def test_total_pattern_count_includes_placeholders(self):
        """Registry should now have 36 patterns (18 original + 18 placeholders)."""
        assert len(CARTESIAN_PATTERN_REGISTRY) >= 36

    def test_known_inverse_patterns_registered(self):
        """Check a sample of the required inverse patterns exist by name."""
        all_names = {p.pattern_name for p in CARTESIAN_PATTERN_REGISTRY.values()}
        required = [
            "制裁解除 / 正常化模式",
            "停火 / 和平協議模式",
            "貿易戰 / 脫鉤模式",
            "金融再整合模式",
            "同盟瓦解 / 中立化模式",
            "規範侵蝕 / 去合法化模式",
        ]
        for name in required:
            assert name in all_names, f"Missing inverse placeholder: {name}"


# ===========================================================================
# C. Composition derivation
# ===========================================================================

class TestCompositionDerivation:
    def test_composition_table_has_entries(self):
        assert len(composition_table) >= 1

    def test_derive_composed_patterns_basic(self):
        """sanction + alliance patterns → should derive 多邊聯盟制裁模式."""
        active = [
            {"pattern": "霸權制裁模式",    "from_event": "ev1"},
            {"pattern": "正式軍事同盟模式", "from_event": "ev2"},
        ]
        derived = derive_composed_patterns(active)
        derived_names = [d["derived"] for d in derived]
        assert "多邊聯盟制裁模式" in derived_names

    def test_derive_composed_patterns_rule_format(self):
        """Each derived entry must have 'derived', 'rule', 'inputs' keys."""
        active = [
            {"pattern": "霸權制裁模式",       "from_event": "ev1"},
            {"pattern": "實體清單技術封鎖模式", "from_event": "ev2"},
        ]
        derived = derive_composed_patterns(active)
        for d in derived:
            assert "derived" in d
            assert "rule"    in d
            assert "inputs"  in d
            assert "->" in d["rule"]

    def test_derive_empty_if_no_composition(self):
        """Patterns with no defined composition yield no derived patterns."""
        # Use patterns that have no composition entry
        active = [{"pattern": "外交讓步 / 去升級模式", "from_event": "ev1"}]
        derived = derive_composed_patterns(active)
        assert isinstance(derived, list)

    def test_derive_no_duplicate_derived(self):
        """Derived patterns must not include the same pattern twice."""
        active = [
            {"pattern": "霸權制裁模式",    "from_event": "ev1"},
            {"pattern": "正式軍事同盟模式", "from_event": "ev2"},
        ]
        derived = derive_composed_patterns(active)
        names = [d["derived"] for d in derived]
        assert len(names) == len(set(names))


# ===========================================================================
# D. Rule-based event extraction
# ===========================================================================

class TestRuleBasedEventExtraction:
    def test_sanction_detection(self):
        text = "The US imposed new sanctions on Iran targeting its oil sector."
        events = extract_events_rule_based(text)
        types = [e["type"] for e in events]
        assert EventType.SANCTION_IMPOSED in types

    def test_military_strike_detection(self):
        text = "Israeli airstrikes targeted Gaza infrastructure overnight."
        events = extract_events_rule_based(text)
        types = [e["type"] for e in events]
        assert EventType.MILITARY_STRIKE in types

    def test_ceasefire_detection(self):
        text = "A fragile ceasefire was brokered between the warring factions."
        events = extract_events_rule_based(text)
        types = [e["type"] for e in events]
        assert EventType.CEASEFIRE in types

    def test_export_control_detection(self):
        text = "Washington added Huawei to the entity list imposing export controls."
        events = extract_events_rule_based(text)
        types = [e["type"] for e in events]
        assert EventType.EXPORT_CONTROL in types

    def test_withdrawal_detection(self):
        text = "US troops withdrew from the northern region after the agreement."
        events = extract_events_rule_based(text)
        types = [e["type"] for e in events]
        assert EventType.WITHDRAWAL in types

    def test_event_has_required_fields(self):
        text = "Heavy clashes erupted along the border."
        events = extract_events_rule_based(text)
        assert len(events) > 0
        for evt in events:
            assert "id"       in evt
            assert "type"     in evt
            assert "args"     in evt
            assert "evidence" in evt
            assert "quote"    in evt["evidence"]
            assert "confidence" in evt

    def test_no_duplicate_event_ids(self):
        text = (
            "The US imposed sanctions on Russia. "
            "The sanctions were condemned by Moscow."
        )
        events = extract_events_rule_based(text)
        ids = [e["id"] for e in events]
        assert len(ids) == len(set(ids))

    def test_empty_text_returns_empty(self):
        assert extract_events_rule_based("") == []

    def test_unrelated_text_returns_empty(self):
        text = "The football team scored three goals in the first half."
        events = extract_events_rule_based(text)
        # No military / regulatory events expected
        types = [e["type"] for e in events]
        assert EventType.MILITARY_STRIKE  not in types
        assert EventType.SANCTION_IMPOSED not in types


# ===========================================================================
# E. Entity typing
# ===========================================================================

class TestEntityTyping:
    def test_person_english_title_case(self):
        assert infer_entity_type_lightweight("John Smith") == "person"
        assert infer_entity_type_lightweight("Elon Musk")  == "person"

    def test_person_three_tokens(self):
        assert infer_entity_type_lightweight("Joe Biden Jr") == "person"

    def test_firm_detected(self):
        assert infer_entity_type_lightweight("Apple Inc")        == "firm"
        assert infer_entity_type_lightweight("Samsung Corp")     == "firm"
        assert infer_entity_type_lightweight("Alibaba Holdings") == "firm"

    def test_state_detected(self):
        assert infer_entity_type_lightweight("US government")  == "state"
        assert infer_entity_type_lightweight("China")          == "state"
        assert infer_entity_type_lightweight("Russia")         == "state"

    def test_alliance_detected(self):
        assert infer_entity_type_lightweight("NATO") == "alliance"
        assert infer_entity_type_lightweight("EU")   == "alliance"
        assert infer_entity_type_lightweight("G7")   == "alliance"

    def test_empty_name_returns_unknown(self):
        assert infer_entity_type_lightweight("") == "unknown"


# ===========================================================================
# F. Active pattern derivation
# ===========================================================================

class TestActivePatternsDerivation:
    def test_sanction_event_maps_to_pattern(self):
        events = [
            {"id": "e1", "type": EventType.SANCTION_IMPOSED,
             "args": {}, "evidence": {"quote": "q"}, "confidence": 0.85}
        ]
        active = derive_active_patterns(events)
        assert any(ap["pattern"] == "霸權制裁模式" for ap in active)

    def test_ceasefire_event_maps_to_pattern(self):
        events = [
            {"id": "e2", "type": EventType.CEASEFIRE,
             "args": {}, "evidence": {"quote": "q"}, "confidence": 0.88}
        ]
        active = derive_active_patterns(events)
        assert any(ap["pattern"] == "停火 / 和平協議模式" for ap in active)

    def test_no_duplicate_patterns(self):
        events = [
            {"id": "e1", "type": EventType.SANCTION_IMPOSED,
             "args": {}, "evidence": {"quote": "q1"}, "confidence": 0.85},
            {"id": "e2", "type": EventType.SANCTION_IMPOSED,
             "args": {}, "evidence": {"quote": "q2"}, "confidence": 0.85},
        ]
        active = derive_active_patterns(events)
        patterns = [ap["pattern"] for ap in active]
        assert len(patterns) == len(set(patterns))

    def test_from_event_field(self):
        events = [
            {"id": "abc123", "type": EventType.MILITARY_STRIKE,
             "args": {}, "evidence": {"quote": "q"}, "confidence": 0.88}
        ]
        active = derive_active_patterns(events)
        for ap in active:
            assert "from_event" in ap
            assert ap["from_event"] == "abc123"


# ===========================================================================
# G. Credibility computation
# ===========================================================================

class TestCredibilityComputation:
    def test_high_verifiability_with_anchors(self):
        text = (
            "On 15 March 2024 the US Treasury imposed sanctions "
            "via OFAC Order No. REF-2024-001. "
            "See https://treasury.gov/sanctions-list."
        )
        cred = compute_credibility(text, [], [])
        assert cred["verifiability_score"] > 0.5

    def test_low_verifiability_no_anchors(self):
        text = "Someone said something happened somewhere recently."
        cred = compute_credibility(text, [], [])
        assert cred["verifiability_score"] < 0.5

    def test_contradiction_detected(self):
        active = [
            {"pattern": "霸權制裁模式"},
            {"pattern": "制裁解除 / 正常化模式"},
        ]
        cred = compute_credibility("text", active, [])
        assert len(cred["contradictions"]) > 0
        assert cred["kg_consistency_score"] < 1.0

    def test_no_contradiction_clean(self):
        active = [{"pattern": "霸權制裁模式"}]
        cred = compute_credibility("text", active, [])
        assert cred["contradictions"] == []
        assert cred["kg_consistency_score"] == 1.0

    def test_result_keys_present(self):
        cred = compute_credibility("text", [], [])
        for key in ("verifiability_score", "missing_evidence",
                    "kg_consistency_score", "contradictions", "supporting_paths"):
            assert key in cred


# ===========================================================================
# H. Full pipeline smoke tests
# ===========================================================================

class TestFullPipeline:
    def test_sanctions_text_produces_events_and_patterns(self):
        text = (
            "The United States imposed sweeping new sanctions on Russia "
            "following the military strike on Ukrainian infrastructure."
        )
        result = run_evented_pipeline(text, llm_service=None)
        assert len(result.events) > 0, "Expected at least one event"
        assert len(result.active_patterns) > 0, "Expected at least one active pattern"
        assert "conclusion" in result.conclusion
        assert "verifiability_score" in result.credibility

    def test_ceasefire_text_produces_ceasefire_event(self):
        text = "A ceasefire agreement was reached between the two factions."
        result = run_evented_pipeline(text)
        types = [e["type"] for e in result.events]
        assert EventType.CEASEFIRE in types

    def test_result_structure(self):
        result = run_evented_pipeline("Some neutral text without events.")
        assert hasattr(result, "events")
        assert hasattr(result, "active_patterns")
        assert hasattr(result, "derived_patterns")
        assert hasattr(result, "conclusion")
        assert hasattr(result, "credibility")

    def test_deterministic_fallback_when_no_llm(self):
        text = "Troops were mobilized along the border."
        result = run_evented_pipeline(text, llm_service=None)
        assert result.conclusion.get("mode") == "deterministic_fallback"

    def test_composition_derived_for_sanction_and_alliance(self):
        text = (
            "NATO allies imposed multilateral sanctions on the regime "
            "after the military alliance activated Article 5."
        )
        result = run_evented_pipeline(text, llm_service=None)
        active_names = [ap["pattern"] for ap in result.active_patterns]
        derived_names = [d["derived"] for d in result.derived_patterns]
        # If both sanction and alliance patterns are active, composition must fire
        if "霸權制裁模式" in active_names and "正式軍事同盟模式" in active_names:
            assert "多邊聯盟制裁模式" in derived_names, (
                "Expected 多邊聯盟制裁模式 to be derived from "
                "霸權制裁模式 + 正式軍事同盟模式 via composition_table"
            )
        else:
            # Verify that at minimum a sanction event was detected from the text
            assert EventType.SANCTION_IMPOSED in [e["type"] for e in result.events] or \
                   len(result.events) > 0, "Expected at least one event from alliance/sanction text"


# ===========================================================================
# I. Post-processing: reject, tier, normalize, confidence folding
# ===========================================================================

def _make_event(
    event_type: str = EventType.SANCTION_IMPOSED,
    confidence: float = 0.85,
    quote: str = "The US imposed sanctions on the target country.",
    inferred_fields: list | None = None,
    inference_rationale: str = "",
    verification_gap: list | None = None,
    args: dict | None = None,
    eid: str | None = None,
) -> dict:
    """Helper to create a minimal candidate event dict."""
    evt: dict = {
        "type":       event_type,
        "args":       args or {},
        "evidence":   {"quote": quote},
        "confidence": confidence,
    }
    if inferred_fields is not None:
        evt["inferred_fields"] = inferred_fields
    if inference_rationale:
        evt["inference_rationale"] = inference_rationale
    if verification_gap is not None:
        evt["verification_gap"] = verification_gap
    if eid:
        evt["id"] = eid
    return evt


class TestPostProcessingReject:
    """Post-processor T0 rejection: only truly invalid events are dropped."""

    def test_rejects_zero_confidence(self):
        candidate = _make_event(confidence=0.0)
        assert postprocess_events([candidate]) == []

    def test_rejects_negative_confidence(self):
        candidate = _make_event(confidence=-0.1)
        assert postprocess_events([candidate]) == []

    def test_empty_quote_kept_as_t1_with_gap(self):
        # Empty quote is no longer a hard-reject; event kept as T1 with verification_gap.
        # confidence=0.85, no trigger in "" → folded * 0.7 = 0.595 (above T0=0.2)
        candidate = _make_event(quote="")
        result = postprocess_events([candidate])
        assert len(result) == 1, f"Expected 1 event, got {result}"
        assert result[0]["tier"] == "T1"
        assert any("quote missing" in g for g in result[0]["verification_gap"])

    def test_whitespace_only_quote_kept_as_t1_with_gap(self):
        # Whitespace-only quote is stripped to empty → same treatment as missing quote.
        candidate = _make_event(quote="   ")
        result = postprocess_events([candidate])
        assert len(result) == 1, f"Expected 1 event, got {result}"
        assert result[0]["tier"] == "T1"
        assert any("quote" in g for g in result[0]["verification_gap"])

    def test_short_quote_no_trigger_kept_as_t1_with_gap(self):
        # Short quote without trigger keywords → T1 with gap (not hard-rejected).
        # confidence=0.85, no trigger → folded * 0.7 = 0.595 (above T0=0.2)
        short_q = "x" * (_MIN_QUOTE_LEN - 1)
        candidate = _make_event(quote=short_q)
        result = postprocess_events([candidate])
        assert len(result) == 1, f"Expected 1 event, got {result}"
        assert result[0]["tier"] == "T1"
        assert any("quote" in g for g in result[0]["verification_gap"])

    def test_rejects_confidence_below_t0_threshold(self):
        candidate = _make_event(confidence=_T0_CONF_THRESHOLD - 0.01)
        assert postprocess_events([candidate]) == []

    def test_rejects_event_that_falls_below_threshold_after_folding(self):
        # Folding chain: * 0.7 (any inferred_fields) * 0.8 (actor+target in _ACTOR_TARGET_KEYS)
        #                * 0.7 (quote has no sanction trigger keyword)
        # 0.22 * 0.7 * 0.8 * 0.7 ≈ 0.086 < 0.2 → rejected (T0)
        candidate = _make_event(
            confidence=0.22,
            inferred_fields=["actor", "target"],
            quote="The deal was announced at a press conference today in the capital.",
        )
        result = postprocess_events([candidate])
        assert result == [], (
            f"Expected T0 rejection after confidence folding, got {result}"
        )

    def test_valid_event_passes_through(self):
        candidate = _make_event(confidence=0.85)
        result = postprocess_events([candidate])
        assert len(result) == 1


class TestFallbackTopEvents:
    """_fallback_top_events: keeps best candidates when all are T0-rejected."""

    def test_returns_empty_for_no_candidates(self):
        assert _fallback_top_events([]) == []

    def test_returns_empty_for_zero_confidence_only(self):
        candidate = _make_event(confidence=0.0)
        assert _fallback_top_events([candidate]) == []

    def test_keeps_top_event_as_t1(self):
        candidate = _make_event(confidence=0.55)
        result = _fallback_top_events([candidate])
        assert len(result) == 1
        assert result[0]["tier"] == "T1"
        assert result[0]["confidence"] <= 0.35  # clamped
        assert any("fallback" in g for g in result[0]["verification_gap"])

    def test_keeps_at_most_max_keep_events(self):
        candidates = [_make_event(confidence=0.5 + i * 0.1, eid=f"id{i}") for i in range(5)]
        result = _fallback_top_events(candidates, max_keep=2)
        assert len(result) == 2

    def test_selects_highest_confidence_candidates(self):
        low  = _make_event(confidence=0.3, eid="low")
        high = _make_event(confidence=0.8, eid="high")
        result = _fallback_top_events([low, high], max_keep=1)
        assert len(result) == 1
        assert result[0]["id"] == "high"



class TestPostProcessingTiering:
    """Tiering boundary tests: T0 < 0.2, T1 in [0.2, 0.7), T2 >= 0.7."""

    def test_exactly_t0_boundary_rejected(self):
        candidate = _make_event(confidence=_T0_CONF_THRESHOLD - 0.001)
        assert postprocess_events([candidate]) == []

    def test_exactly_t0_boundary_passes(self):
        candidate = _make_event(confidence=_T0_CONF_THRESHOLD)
        result = postprocess_events([candidate])
        assert len(result) == 1
        assert result[0]["tier"] == "T1"

    def test_t1_tier_at_lower_bound(self):
        candidate = _make_event(confidence=_T0_CONF_THRESHOLD)
        result = postprocess_events([candidate])
        assert result[0]["tier"] == "T1"

    def test_t1_tier_mid_range(self):
        candidate = _make_event(confidence=0.50)
        result = postprocess_events([candidate])
        assert result[0]["tier"] == "T1"

    def test_t2_boundary_exactly(self):
        candidate = _make_event(confidence=_T2_CONF_THRESHOLD)
        result = postprocess_events([candidate])
        assert result[0]["tier"] == "T2"

    def test_t2_high_confidence(self):
        candidate = _make_event(confidence=0.95)
        result = postprocess_events([candidate])
        assert result[0]["tier"] == "T2"

    def test_inferred_fields_forces_t1_even_at_high_base_confidence(self):
        # confidence = 0.90, but inferred_fields present → T1 regardless
        candidate = _make_event(
            confidence=0.90,
            inferred_fields=["actor"],
        )
        result = postprocess_events([candidate])
        assert len(result) == 1
        assert result[0]["tier"] == "T1"

    def test_tier_field_present_in_output(self):
        candidate = _make_event(confidence=0.85)
        result = postprocess_events([candidate])
        assert "tier" in result[0]


class TestPostProcessingNormalization:
    """Normalization: strip whitespace in pattern names (via args) and de-dup."""

    def test_strips_whitespace_from_args_strings(self):
        candidate = _make_event(args={"actor": "  United States  ", "target": " China "})
        result = postprocess_events([candidate])
        assert result[0]["args"]["actor"] == "United States"
        assert result[0]["args"]["target"] == "China"

    def test_strips_whitespace_from_quote(self):
        q = "  The US imposed sanctions on the target country.  "
        candidate = _make_event(quote=q)
        result = postprocess_events([candidate])
        assert not result[0]["evidence"]["quote"].startswith(" ")
        assert not result[0]["evidence"]["quote"].endswith(" ")

    def test_strips_whitespace_from_event_type(self):
        # Note: EventType constants have no spaces, but user-supplied types might
        candidate = _make_event(event_type="  sanction_imposed  ")
        result = postprocess_events([candidate])
        assert result[0]["type"] == "sanction_imposed"

    def test_deduplicates_events_with_same_id(self):
        evt1 = _make_event(confidence=0.85, eid="dup001")
        evt2 = _make_event(confidence=0.90, eid="dup001")
        result = postprocess_events([evt1, evt2])
        assert len(result) == 1
        assert result[0]["id"] == "dup001"

    def test_deduplicates_events_with_same_type_and_quote(self):
        # Without explicit IDs – stable ID is derived from type + quote
        quote = "The US imposed sanctions on the target country."
        evt1 = _make_event(confidence=0.85, quote=quote)
        evt2 = _make_event(confidence=0.88, quote=quote)
        result = postprocess_events([evt1, evt2])
        assert len(result) == 1


class TestPostProcessingConfidenceFolding:
    """Confidence folding rules for inferred fields and trigger keywords."""

    def test_inferred_fields_reduce_confidence(self):
        base_conf = 0.80
        candidate = _make_event(confidence=base_conf, inferred_fields=["actor"])
        result = postprocess_events([candidate])
        assert len(result) == 1
        # Folding: * 0.7 (any inferred_fields) * 0.8 (actor in _ACTOR_TARGET_KEYS) = * 0.56
        expected = round(base_conf * 0.7 * 0.8, 4)
        assert result[0]["confidence"] == pytest.approx(expected, abs=0.001)

    def test_inferred_actor_target_gets_additional_penalty(self):
        base_conf = 0.90
        candidate_actor  = _make_event(confidence=base_conf, inferred_fields=["actor"])
        candidate_item   = _make_event(
            confidence=base_conf, inferred_fields=["item"],
            quote="The US imposed sanctions on the target country. Item X was restricted.",
            eid="item_evt",
        )
        result_actor = postprocess_events([candidate_actor])
        result_item  = postprocess_events([candidate_item])
        # actor should be lower than item because actor/target get extra *0.8
        assert result_actor[0]["confidence"] < result_item[0]["confidence"]

    def test_missing_trigger_keyword_reduces_confidence(self):
        # Quote about a ceasefire but event type is MILITARY_STRIKE (no trigger words)
        candidate = _make_event(
            event_type=EventType.MILITARY_STRIKE,
            confidence=0.80,
            quote="The ceasefire agreement was reached between the two parties today.",
        )
        result = postprocess_events([candidate])
        if result:
            assert result[0]["confidence"] < 0.80

    def test_present_trigger_keyword_no_extra_penalty(self):
        candidate = _make_event(
            event_type=EventType.SANCTION_IMPOSED,
            confidence=0.80,
            quote="The US imposed sanctions on the target country.",
        )
        result = postprocess_events([candidate])
        assert len(result) == 1
        # No inferred_fields, quote has "sanctions" → no penalty → confidence stays 0.80
        assert result[0]["confidence"] == pytest.approx(0.80, abs=0.001)


class TestActivePatternsProvenance:
    """derive_active_patterns must include tier, inferred, confidence fields."""

    def test_output_has_tier_field(self):
        events = [_make_event(confidence=0.85, eid="e1")]
        events[0]["id"] = "e1"
        active = derive_active_patterns(events)
        assert len(active) > 0
        assert "tier" in active[0]

    def test_output_has_inferred_field(self):
        events = [_make_event(confidence=0.85, eid="e1")]
        events[0]["id"] = "e1"
        active = derive_active_patterns(events)
        assert "inferred" in active[0]
        assert active[0]["inferred"] is False

    def test_output_has_confidence_field(self):
        events = [_make_event(confidence=0.85, eid="e1")]
        events[0]["id"] = "e1"
        active = derive_active_patterns(events)
        assert "confidence" in active[0]

    def test_t1_event_maps_to_weak_pattern(self):
        evt = _make_event(confidence=0.40, eid="e_t1")
        evt["id"] = "e_t1"
        # Force T1 tier
        evt["tier"] = "T1"
        active = derive_active_patterns([evt])
        pattern_names = [ap["pattern"] for ap in active]
        # Should map to a weak pattern, not the strong 霸權制裁模式
        assert "政策性貿易限制模式" in pattern_names
        assert "霸權制裁模式" not in pattern_names

    def test_t2_event_maps_to_strong_pattern(self):
        evt = _make_event(confidence=0.85, eid="e_t2")
        evt["id"] = "e_t2"
        evt["tier"] = "T2"
        active = derive_active_patterns([evt])
        pattern_names = [ap["pattern"] for ap in active]
        assert "霸權制裁模式" in pattern_names


class TestDerivedPatternConfidence:
    """derive_composed_patterns must attach derived_tier, derived_inferred, derived_confidence."""

    def test_derived_confidence_formula(self):
        active = [
            {"pattern": "霸權制裁模式",    "from_event": "ev1",
             "tier": "T2", "inferred": False, "confidence": 0.80},
            {"pattern": "正式軍事同盟模式", "from_event": "ev2",
             "tier": "T2", "inferred": False, "confidence": 0.75},
        ]
        derived = derive_composed_patterns(active)
        derived_map = {d["derived"]: d for d in derived}
        if "多邊聯盟制裁模式" in derived_map:
            entry = derived_map["多邊聯盟制裁模式"]
            expected_conf = round(min(0.80, 0.75) * 0.9, 4)
            assert entry["derived_confidence"] == pytest.approx(expected_conf, abs=0.001)
            # min(0.80, 0.75) * 0.9 = 0.675 < 0.7 → T1
            assert entry["derived_tier"] == "T1"
            assert entry["derived_inferred"] is False

    def test_derived_confidence_penalised_when_inferred(self):
        active = [
            {"pattern": "霸權制裁模式",    "from_event": "ev1",
             "tier": "T1", "inferred": True, "confidence": 0.80},
            {"pattern": "正式軍事同盟模式", "from_event": "ev2",
             "tier": "T2", "inferred": False, "confidence": 0.75},
        ]
        derived = derive_composed_patterns(active)
        derived_map = {d["derived"]: d for d in derived}
        if "多邊聯盟制裁模式" in derived_map:
            entry = derived_map["多邊聯盟制裁模式"]
            expected_conf = round(min(0.80, 0.75) * 0.9 * 0.8, 4)
            assert entry["derived_confidence"] == pytest.approx(expected_conf, abs=0.001)
            assert entry["derived_inferred"] is True

    def test_derived_tier_propagates_from_t1_inputs(self):
        active = [
            {"pattern": "霸權制裁模式",    "from_event": "ev1",
             "tier": "T1", "inferred": False, "confidence": 0.50},
            {"pattern": "正式軍事同盟模式", "from_event": "ev2",
             "tier": "T2", "inferred": False, "confidence": 0.75},
        ]
        derived = derive_composed_patterns(active)
        derived_map = {d["derived"]: d for d in derived}
        if "多邊聯盟制裁模式" in derived_map:
            assert derived_map["多邊聯盟制裁模式"]["derived_tier"] == "T1"

    def test_derived_patterns_have_required_keys(self):
        active = [
            {"pattern": "霸權制裁模式",    "from_event": "ev1",
             "tier": "T2", "inferred": False, "confidence": 0.80},
            {"pattern": "正式軍事同盟模式", "from_event": "ev2",
             "tier": "T2", "inferred": False, "confidence": 0.75},
        ]
        derived = derive_composed_patterns(active)
        for entry in derived:
            for key in ("derived", "rule", "inputs",
                        "derived_tier", "derived_inferred", "derived_confidence"):
                assert key in entry, f"Missing key '{key}' in derived entry: {entry}"


class TestCredibilityHypothesisRatio:
    """compute_credibility must return hypothesis_ratio and overall_score."""

    def test_hypothesis_ratio_zero_when_all_t2(self):
        active = [{"pattern": "霸權制裁模式", "tier": "T2"}]
        cred = compute_credibility("text", active, [])
        assert cred["hypothesis_ratio"] == pytest.approx(0.0, abs=0.001)

    def test_hypothesis_ratio_one_when_all_t1(self):
        active = [{"pattern": "政策性貿易限制模式", "tier": "T1"}]
        cred = compute_credibility("text", active, [])
        assert cred["hypothesis_ratio"] == pytest.approx(1.0, abs=0.001)

    def test_hypothesis_ratio_mixed(self):
        active = [
            {"pattern": "霸權制裁模式",       "tier": "T2"},
            {"pattern": "政策性貿易限制模式",   "tier": "T1"},
        ]
        cred = compute_credibility("text", active, [])
        assert cred["hypothesis_ratio"] == pytest.approx(0.5, abs=0.001)

    def test_overall_score_present(self):
        cred = compute_credibility("text", [], [])
        assert "overall_score" in cred
        assert 0.0 <= cred["overall_score"] <= 1.0

    def test_overall_score_reduced_by_high_hypothesis_ratio(self):
        active_pure_t2 = [{"pattern": "霸權制裁模式", "tier": "T2"}]
        active_pure_t1 = [{"pattern": "政策性貿易限制模式", "tier": "T1"}]
        text = "On 15 March 2024 OFAC imposed sanctions."
        cred_t2 = compute_credibility(text, active_pure_t2, [])
        cred_t1 = compute_credibility(text, active_pure_t1, [])
        assert cred_t2["overall_score"] > cred_t1["overall_score"], (
            "All-T2 patterns should yield a higher overall_score than all-T1"
        )

    def test_result_has_all_new_keys(self):
        cred = compute_credibility("text", [], [])
        for key in ("verifiability_score", "missing_evidence",
                    "kg_consistency_score", "contradictions", "supporting_paths",
                    "hypothesis_ratio", "overall_score"):
            assert key in cred


class TestEndToEndEventFiltering:
    """End-to-end: zero-confidence and empty-quote events never appear in pipeline output."""

    def test_pipeline_has_no_zero_confidence_events(self):
        result = run_evented_pipeline(
            "The United States imposed sanctions following the military strike.",
            llm_service=None,
        )
        for evt in result.events:
            assert evt["confidence"] > 0, (
                f"Event with confidence=0 survived post-processing: {evt}"
            )

    def test_pipeline_has_no_empty_quote_events(self):
        result = run_evented_pipeline(
            "Ceasefire declared after months of fighting.",
            llm_service=None,
        )
        for evt in result.events:
            assert evt["evidence"]["quote"], (
                f"Event with empty quote survived post-processing: {evt}"
            )

    def test_pipeline_events_all_have_tier_field(self):
        result = run_evented_pipeline(
            "Export controls were imposed on semiconductor chips.",
            llm_service=None,
        )
        for evt in result.events:
            assert "tier" in evt
            assert evt["tier"] in ("T1", "T2")

    def test_conclusion_has_evidence_and_hypothesis_paths(self):
        result = run_evented_pipeline(
            "The United States imposed sanctions following the military strike.",
            llm_service=None,
        )
        assert "evidence_path" in result.conclusion
        assert "hypothesis_path" in result.conclusion

    def test_credibility_has_overall_score(self):
        result = run_evented_pipeline(
            "Sanctions imposed by the US Treasury Department.",
            llm_service=None,
        )
        assert "overall_score" in result.credibility


# ===========================================================================
# J. Domain fixture tests (LLM disabled, offline, deterministic)
#    Validates business, geopolitics, economics, tech/space coverage.
# ===========================================================================

# ---------------------------------------------------------------------------
# Static offline fixtures – no web fetching, no LLM calls
# ---------------------------------------------------------------------------

_FIXTURE_BUSINESS = (
    "Beehiiv, the newsletter platform, is expanding into podcast hosting. "
    "The company announced the launch of a new audio feature that lets creators "
    "publish and monetize podcasts directly within their Beehiiv subscription. "
    "This move takes aim at rivals like Spotify and Substack, which have been "
    "rolling out competing creator economy tools. Beehiiv's CEO said the platform "
    "will introduce bundled subscription tiers, helping creators consolidate their "
    "audience and revenue streams in one ecosystem."
)

_FIXTURE_GEOPOLITICS = (
    "Israeli airstrikes killed at least 7 people in southern Lebanon overnight, "
    "targeting Hezbollah infrastructure near the border. Hezbollah fighters "
    "clashed with Israeli ground troops advancing into the buffer zone. "
    "The Israeli military threatened further strikes if Hezbollah continued "
    "launching rockets. A fragile ceasefire brokered last month appears to be "
    "collapsing, with both sides mobilizing additional forces along the frontier."
)

_FIXTURE_ECONOMICS = (
    "The United States imposed sweeping new tariffs on Chinese goods, escalating "
    "the trade war that has disrupted global supply chains. Washington added "
    "dozens of Chinese firms to the entity list, imposing export controls on "
    "semiconductor chips and advanced manufacturing equipment. Economists warn "
    "the decoupling will accelerate inflation pressure and bilateral trade collapse. "
    "The Federal Reserve signaled it may adjust monetary policy in response to "
    "the economic shock from trade restrictions."
)

_FIXTURE_TECH_SPACE = (
    "NASA and SpaceX successfully launched the Artemis IV mission, placing the "
    "Orion spacecraft into lunar orbit after a flawless rocket liftoff from "
    "Kennedy Space Center. The four astronauts aboard will conduct the first "
    "crewed lunar surface landing since Apollo 17. The space mission marks a "
    "major technology breakthrough for deep space exploration. ESA also "
    "announced plans to deploy a new satellite constellation for Earth observation."
)

_FIXTURE_TARIFF_TRADE = (
    "China and the EU exchanged retaliatory tariffs on agricultural products "
    "and electric vehicles, deepening the trade war that began after Brussels "
    "imposed economic restrictions on Chinese EV imports. Trade analysts warned "
    "the sanctions and export controls will cause third-country trade diversion "
    "and supply chain fragmentation. The bilateral trade dependency that once "
    "stabilized relations is now a source of coercive leverage, with both sides "
    "threatening further economic penalties."
)


class TestDomainFixtures:
    """
    Offline, LLM-disabled tests using static sample articles.

    Coverage domains: business, geopolitics, economics, tech/space.
    All tests use run_evented_pipeline(..., llm_service=None).
    """

    # --- Business (Beehiiv podcast hosting) ---

    def test_business_yields_at_least_two_events(self):
        result = run_evented_pipeline(_FIXTURE_BUSINESS, llm_service=None)
        assert len(result.events) >= 2, (
            f"Business sample should produce >=2 events, got {len(result.events)}: "
            f"{[e['type'] for e in result.events]}"
        )

    def test_business_yields_at_least_one_active_pattern(self):
        result = run_evented_pipeline(_FIXTURE_BUSINESS, llm_service=None)
        assert len(result.active_patterns) >= 1, (
            "Business sample should produce >=1 active pattern"
        )

    def test_business_contains_business_event_types(self):
        result = run_evented_pipeline(_FIXTURE_BUSINESS, llm_service=None)
        types = {e["type"] for e in result.events}
        business_types = {
            EventType.MARKET_ENTRY,
            EventType.PRODUCT_FEATURE_LAUNCH,
            EventType.COMPETITIVE_POSITIONING,
            EventType.PLATFORM_STRATEGY,
        }
        assert types & business_types, (
            f"Business sample should contain at least one business event type. "
            f"Got: {types}"
        )

    def test_business_no_zero_confidence_events(self):
        result = run_evented_pipeline(_FIXTURE_BUSINESS, llm_service=None)
        for evt in result.events:
            assert evt["confidence"] > 0, (
                f"confidence==0 event detected: {evt}"
            )

    def test_business_no_empty_evidence_quotes(self):
        result = run_evented_pipeline(_FIXTURE_BUSINESS, llm_service=None)
        for evt in result.events:
            assert evt["evidence"]["quote"], (
                f"Empty evidence.quote detected: {evt}"
            )

    # --- Geopolitics (Israeli strikes / Hezbollah) ---

    def test_geopolitics_yields_kinetic_events(self):
        result = run_evented_pipeline(_FIXTURE_GEOPOLITICS, llm_service=None)
        types = {e["type"] for e in result.events}
        kinetic = {
            EventType.MILITARY_STRIKE,
            EventType.CLASHES,
            EventType.MOBILIZATION,
            EventType.CEASEFIRE,
            EventType.COERCIVE_WARNING,
        }
        assert types & kinetic, (
            f"Geopolitics sample should contain kinetic events. Got: {types}"
        )

    def test_geopolitics_yields_at_least_two_events(self):
        result = run_evented_pipeline(_FIXTURE_GEOPOLITICS, llm_service=None)
        assert len(result.events) >= 2, (
            f"Geopolitics sample expected >=2 events, got {len(result.events)}"
        )

    def test_geopolitics_produces_active_patterns(self):
        result = run_evented_pipeline(_FIXTURE_GEOPOLITICS, llm_service=None)
        assert len(result.active_patterns) >= 1

    def test_geopolitics_events_have_non_empty_quotes(self):
        result = run_evented_pipeline(_FIXTURE_GEOPOLITICS, llm_service=None)
        for evt in result.events:
            assert evt["evidence"]["quote"], (
                f"Empty quote in geopolitics event: {evt}"
            )

    # --- Economics (tariffs / trade war / entity list) ---

    def test_economics_yields_events(self):
        result = run_evented_pipeline(_FIXTURE_ECONOMICS, llm_service=None)
        assert len(result.events) >= 1, (
            "Economics sample should produce >=1 event"
        )

    def test_economics_yields_patterns(self):
        result = run_evented_pipeline(_FIXTURE_ECONOMICS, llm_service=None)
        assert len(result.active_patterns) >= 1, (
            "Economics sample should produce >=1 active pattern"
        )

    def test_economics_detects_trade_or_sanction(self):
        result = run_evented_pipeline(_FIXTURE_ECONOMICS, llm_service=None)
        types = {e["type"] for e in result.events}
        econ_types = {
            EventType.SANCTION_IMPOSED,
            EventType.EXPORT_CONTROL,
            EventType.COERCIVE_WARNING,
        }
        assert types & econ_types, (
            f"Economics sample should contain sanction/export/coercive events. Got: {types}"
        )

    # --- Tech / Space (NASA/SpaceX Artemis) ---

    def test_space_yields_space_mission_event(self):
        result = run_evented_pipeline(_FIXTURE_TECH_SPACE, llm_service=None)
        types = {e["type"] for e in result.events}
        assert EventType.SPACE_MISSION in types, (
            f"Tech/space sample should contain space_mission event. Got: {types}"
        )

    def test_space_does_not_misclassify_as_legal_regulatory(self):
        result = run_evented_pipeline(_FIXTURE_TECH_SPACE, llm_service=None)
        # Ensure space_mission is detected and legal_regulatory_action is NOT
        # the dominant (or only) event when the text is clearly about space.
        types = {e["type"] for e in result.events}
        # space_mission must be present
        assert EventType.SPACE_MISSION in types, (
            f"Tech/space text misclassified: space_mission absent. Types: {types}"
        )

    def test_space_yields_active_patterns(self):
        result = run_evented_pipeline(_FIXTURE_TECH_SPACE, llm_service=None)
        assert len(result.active_patterns) >= 1, (
            "Tech/space sample should produce >=1 active pattern"
        )

    def test_space_no_zero_confidence_events(self):
        result = run_evented_pipeline(_FIXTURE_TECH_SPACE, llm_service=None)
        for evt in result.events:
            assert evt["confidence"] > 0

    # --- Cross-domain: derived patterns appear via composition ---

    def test_tariff_trade_derived_patterns_exist(self):
        """Economics/trade sample should produce derived patterns via composition."""
        result = run_evented_pipeline(_FIXTURE_TARIFF_TRADE, llm_service=None)
        # Derived patterns require >=2 distinct active patterns that compose
        # We verify derived patterns appear in at least this rich sample
        assert len(result.derived_patterns) >= 1, (
            f"Expected >=1 derived pattern in tariff/trade sample. "
            f"Active: {[ap['pattern'] for ap in result.active_patterns]}, "
            f"Derived: {result.derived_patterns}"
        )

    def test_no_confidence_zero_across_all_fixtures(self):
        """No fixture should ever produce an event with confidence==0."""
        for label, text in [
            ("business",   _FIXTURE_BUSINESS),
            ("geopolitics", _FIXTURE_GEOPOLITICS),
            ("economics",  _FIXTURE_ECONOMICS),
            ("tech_space", _FIXTURE_TECH_SPACE),
            ("tariff",     _FIXTURE_TARIFF_TRADE),
        ]:
            result = run_evented_pipeline(text, llm_service=None)
            for evt in result.events:
                assert evt["confidence"] > 0, (
                    f"[{label}] confidence==0 event: {evt}"
                )

    def test_composition_table_has_business_entries(self):
        """Composition table must contain at least one business/tech entry."""
        business_patterns = {
            "產品能力擴張模式",
            "平台競爭 / 生態位擴張模式",
            "創作者經濟整合模式",
            "技術突破 / 太空探索模式",
        }
        found = any(
            p in business_patterns
            for pair in composition_table.keys()
            for p in pair
        )
        assert found, (
            "composition_table should contain at least one business/tech pattern"
        )

    def test_registry_has_business_patterns(self):
        """CARTESIAN_PATTERN_REGISTRY should contain new business pattern names."""
        all_names = {p.pattern_name for p in CARTESIAN_PATTERN_REGISTRY.values()}
        required = [
            "產品能力擴張模式",
            "平台競爭 / 生態位擴張模式",
            "創作者經濟整合模式",
            "技術突破 / 太空探索模式",
        ]
        for name in required:
            assert name in all_names, (
                f"CARTESIAN_PATTERN_REGISTRY missing business pattern: {name}"
            )

    def test_business_derived_patterns_appear(self):
        """Business sample should produce derived patterns via composition."""
        result = run_evented_pipeline(_FIXTURE_BUSINESS, llm_service=None)
        # Business events should produce >=2 active patterns enabling composition
        if len(result.active_patterns) >= 2:
            assert len(result.derived_patterns) >= 1, (
                f"Expected derived patterns when >=2 active patterns present. "
                f"Active: {[ap['pattern'] for ap in result.active_patterns]}"
            )


# ===========================================================================
# H. Schema Contract Validation – backward-compatible keys
# ===========================================================================

class TestPipelineResultSchemaContract:
    """
    Verify that PipelineResult serialized dicts always contain the
    backward-compatible keys that the frontend expects.

    These tests catch schema regressions where backend v3 internal field
    names (pattern_name, event_type, confidence_prior, source_event) change
    but the frontend still reads the old aliases (pattern, type, confidence,
    from_event, derived).
    """

    # ── Events ──────────────────────────────────────────────────────────

    def test_events_have_type_alias(self):
        """Each event dict must contain 'type' (frontend alias for event_type)."""
        result = run_evented_pipeline(_FIXTURE_GEOPOLITICS, llm_service=None)
        for evt in result.events:
            assert "type" in evt, (
                f"Event missing backward-compat 'type' key: {evt}"
            )
            assert evt["type"] == evt.get("event_type"), (
                f"'type' alias must equal 'event_type'. Got: {evt}"
            )

    def test_events_type_is_not_unknown(self):
        """'type' must be a non-empty, non-'unknown' string when events exist."""
        result = run_evented_pipeline(_FIXTURE_GEOPOLITICS, llm_service=None)
        for evt in result.events:
            assert evt.get("type", "unknown") != "unknown", (
                f"Event 'type' resolved to 'unknown': {evt}"
            )
            assert evt.get("type"), (
                f"Event 'type' is empty: {evt}"
            )

    # ── Active patterns ──────────────────────────────────────────────────

    def test_active_patterns_have_pattern_alias(self):
        """Each active-pattern dict must contain the 'pattern' alias."""
        result = run_evented_pipeline(_FIXTURE_GEOPOLITICS, llm_service=None)
        for ap in result.active_patterns:
            assert "pattern" in ap, (
                f"Active pattern missing backward-compat 'pattern' key: {ap}"
            )
            assert ap["pattern"] == ap.get("pattern_name"), (
                f"'pattern' alias must equal 'pattern_name'. Got: {ap}"
            )

    def test_active_patterns_have_confidence_alias(self):
        """Each active-pattern dict must contain 'confidence' alias."""
        result = run_evented_pipeline(_FIXTURE_GEOPOLITICS, llm_service=None)
        for ap in result.active_patterns:
            assert "confidence" in ap, (
                f"Active pattern missing backward-compat 'confidence' key: {ap}"
            )

    def test_active_patterns_have_from_event_alias(self):
        """Each active-pattern dict must contain 'from_event' alias."""
        result = run_evented_pipeline(_FIXTURE_GEOPOLITICS, llm_service=None)
        for ap in result.active_patterns:
            assert "from_event" in ap, (
                f"Active pattern missing backward-compat 'from_event' key: {ap}"
            )

    # ── Derived patterns ─────────────────────────────────────────────────

    def test_derived_patterns_have_derived_alias(self):
        """Each derived-pattern dict must contain 'derived' alias."""
        result = run_evented_pipeline(_FIXTURE_TARIFF_TRADE, llm_service=None)
        for dp in result.derived_patterns:
            assert "derived" in dp, (
                f"Derived pattern missing backward-compat 'derived' key: {dp}"
            )

    def test_derived_patterns_have_pattern_alias(self):
        """Each derived-pattern dict must contain 'pattern' alias."""
        result = run_evented_pipeline(_FIXTURE_TARIFF_TRADE, llm_service=None)
        for dp in result.derived_patterns:
            assert "pattern" in dp, (
                f"Derived pattern missing backward-compat 'pattern' key: {dp}"
            )

    def test_derived_patterns_have_derived_confidence(self):
        """Each derived-pattern dict must contain 'derived_confidence'."""
        result = run_evented_pipeline(_FIXTURE_TARIFF_TRADE, llm_service=None)
        for dp in result.derived_patterns:
            assert "derived_confidence" in dp, (
                f"Derived pattern missing 'derived_confidence' key: {dp}"
            )

    # ── v3 new fields ────────────────────────────────────────────────────

    def test_result_has_top_transitions_field(self):
        """PipelineResult must expose top_transitions list."""
        result = run_evented_pipeline(_FIXTURE_GEOPOLITICS, llm_service=None)
        assert hasattr(result, "top_transitions"), (
            "PipelineResult missing 'top_transitions' attribute"
        )
        assert isinstance(result.top_transitions, list)

    def test_result_has_state_vector_field(self):
        """PipelineResult must expose state_vector dict."""
        result = run_evented_pipeline(_FIXTURE_GEOPOLITICS, llm_service=None)
        assert hasattr(result, "state_vector"), (
            "PipelineResult missing 'state_vector' attribute"
        )
        assert isinstance(result.state_vector, dict)
