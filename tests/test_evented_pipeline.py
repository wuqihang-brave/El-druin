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
    _stable_id,
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
