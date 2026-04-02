"""
Tests for relation_schema.py v2 additions:
  - EntityType.UNKNOWN
  - _infer_entity_type() unknown default
  - inverse_table / composition_table
  - validate_inverses / validate_composition_closure / run_ontology_validation
  - get_inverse_pattern / compose_patterns
  - generate_diagnostic_report UNKNOWN short-circuit
  - build_pattern_context_for_prompt UNKNOWN short-circuit
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from ontology.relation_schema import (
    EntityType,
    _infer_entity_type,
    inverse_table,
    composition_table,
    validate_inverses,
    validate_composition_closure,
    run_ontology_validation,
    get_inverse_pattern,
    compose_patterns,
    generate_diagnostic_report,
    build_pattern_context_for_prompt,
    CARTESIAN_PATTERN_REGISTRY,
)


# ---------------------------------------------------------------------------
# EntityType.UNKNOWN
# ---------------------------------------------------------------------------

class TestEntityTypeUnknown:
    def test_unknown_member_exists(self):
        assert EntityType.UNKNOWN == "unknown"

    def test_unknown_value_is_string(self):
        assert EntityType.UNKNOWN.value == "unknown"


# ---------------------------------------------------------------------------
# _infer_entity_type()
# ---------------------------------------------------------------------------

class TestInferEntityType:
    def test_unknown_person_name(self):
        """Names not in keyword list → 'unknown' (no longer 'state')."""
        assert _infer_entity_type("Tiger Woods") == "unknown"
        assert _infer_entity_type("Ryder Cup") == "unknown"
        assert _infer_entity_type("John Doe") == "unknown"

    def test_state_keyword_matched(self):
        assert _infer_entity_type("United States") == "state"
        assert _infer_entity_type("China") == "state"

    def test_firm_keyword_matched(self):
        assert _infer_entity_type("Apple Corp") == "firm"

    def test_media_keyword_matched(self):
        assert _infer_entity_type("CNN News") == "media"


# ---------------------------------------------------------------------------
# inverse_table
# ---------------------------------------------------------------------------

class TestInverseTable:
    def test_inverse_table_is_populated(self):
        """inverse_table must be built from the registry at module load."""
        assert len(inverse_table) > 0

    def test_known_inverse_present(self):
        assert "霸權制裁模式" in inverse_table
        assert inverse_table["霸權制裁模式"] == "制裁解除 / 正常化模式"

    def test_get_inverse_pattern_function(self):
        inv = get_inverse_pattern("霸權制裁模式")
        assert inv == "制裁解除 / 正常化模式"

    def test_get_inverse_pattern_missing(self):
        assert get_inverse_pattern("nonexistent_pattern") is None


# ---------------------------------------------------------------------------
# composition_table
# ---------------------------------------------------------------------------

class TestCompositionTable:
    def test_composition_table_is_populated(self):
        assert len(composition_table) >= 1

    def test_known_composition(self):
        result = compose_patterns("霸權制裁模式", "正式軍事同盟模式")
        assert result == "多邊聯盟制裁模式"

    def test_compose_patterns_missing(self):
        assert compose_patterns("nonexistent_a", "nonexistent_b") is None


# ---------------------------------------------------------------------------
# Validation functions
# ---------------------------------------------------------------------------

class TestValidation:
    def test_validate_composition_closure_passes(self):
        """All patterns in composition_table keys must exist in registry."""
        errors = validate_composition_closure()
        # The result values reference existing pattern names; keys reference
        # known pattern names in CARTESIAN_PATTERN_REGISTRY.
        # Errors only occur if pattern names are misspelled.
        comp_errors = [e for e in errors if "composition" in e.lower() or "MISSING_PATTERN" in e]
        assert comp_errors == []

    def test_validate_inverses_returns_list(self):
        """validate_inverses must return a list (may have items for missing inverses)."""
        errors = validate_inverses()
        assert isinstance(errors, list)

    def test_run_ontology_validation_non_strict(self):
        """run_ontology_validation in non-strict mode must not raise."""
        result = run_ontology_validation(strict=False)
        assert isinstance(result, bool)

    def test_run_ontology_validation_strict_raises_on_error(self):
        """If there are errors, strict=True should raise ValueError."""
        errors = validate_inverses() + validate_composition_closure()
        if errors:
            with pytest.raises(ValueError):
                run_ontology_validation(strict=True)


# ---------------------------------------------------------------------------
# generate_diagnostic_report UNKNOWN short-circuit
# ---------------------------------------------------------------------------

class TestDiagnosticReportUnknown:
    def test_unknown_src_short_circuits(self):
        report = generate_diagnostic_report("unknown", "sanction", "state")
        assert report.matched_pattern is None
        assert "UNKNOWN_ENTITY_TYPE" in report.diagnostic_note

    def test_unknown_tgt_short_circuits(self):
        report = generate_diagnostic_report("state", "sanction", "unknown")
        assert report.matched_pattern is None
        assert "UNKNOWN_ENTITY_TYPE" in report.diagnostic_note

    def test_both_unknown_short_circuits(self):
        report = generate_diagnostic_report("unknown", "sanction", "unknown")
        assert report.matched_pattern is None
        assert report.mechanism_class == "unknown"

    def test_known_types_not_affected(self):
        report = generate_diagnostic_report("state", "sanction", "state")
        # Should find the 霸權制裁模式 pattern
        assert report.matched_pattern is not None
        assert report.matched_pattern.pattern_name == "霸權制裁模式"


# ---------------------------------------------------------------------------
# build_pattern_context_for_prompt UNKNOWN short-circuit
# ---------------------------------------------------------------------------

class TestBuildPatternContext:
    def _make_mock_label(self, source: str, relation: str, target: str):
        """Create a duck-typed MechanismLabel."""
        class _Label:
            def __init__(self, src, rel, tgt):
                self.source = src
                self.relation = rel
                self.target = tgt
                self.evidence = ""
        return _Label(source, relation, target)

    def test_unknown_entities_skipped(self):
        """Entities that can't be typed produce no output."""
        labels = [self._make_mock_label("Tiger Woods", "sanction", "Ryder Cup")]
        result = build_pattern_context_for_prompt(labels)
        # Both entities → unknown → skipped → empty output
        assert result == ""

    def test_known_entities_produce_output(self):
        labels = [self._make_mock_label("United States", "sanction", "China")]
        result = build_pattern_context_for_prompt(labels)
        # state × sanction × state should produce output with the pattern
        assert result != ""
        assert "霸權制裁模式" in result
