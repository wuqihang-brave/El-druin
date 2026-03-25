"""
Unit tests for the three-layer ontological entity extraction system.

Tests cover:
1. entity_labels         – taxonomy dictionaries are well-formed
2. models.entity         – OntologicalEntity construction, to_dict(), to_graph_node()
3. EntityExtractionEngine – _parse_response, _parse_multiple_labels,
                            _fuzzy_match_label, _calculate_confidence,
                            _create_ontological_entity, extract()
"""

from __future__ import annotations

import json
import sys
import os
from datetime import datetime

import pytest

_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(_BACKEND_DIR))

from intelligence.entity_labels import (
    LAYER1_PHYSICAL_TYPES,
    LAYER2_STRUCTURAL_ROLES,
    LAYER3_VIRTUE_VICE,
)
from models.entity import EntityLabel, OntologicalEntity
from intelligence.entity_extraction import EntityExtractionEngine


# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------

class _StubLLM:
    """LLM stub that returns a fixed JSON payload."""

    def __init__(self, payload: str = "[]") -> None:
        self._payload = payload

    def call(self, **_kwargs) -> str:
        return self._payload


def _make_engine(payload: str = "[]") -> EntityExtractionEngine:
    return EntityExtractionEngine(_StubLLM(payload))


def _sample_entity(**overrides) -> OntologicalEntity:
    defaults = dict(
        name="Iran",
        physical_type="COUNTRY",
        physical_type_description="Geopolitical state",
        structural_roles=["CATALYST", "AGGRESSOR"],
        role_descriptions={
            "CATALYST": "Triggers major change",
            "AGGRESSOR": "Initiates hostile action",
        },
        philosophical_nature=["DECEPTIVE", "RESILIENT"],
        virtue_descriptions={
            "DECEPTIVE": "Hides true intentions",
            "RESILIENT": "Bends but doesn't break; adapts and survives",
        },
        confidence_score=0.85,
        source_text="Iran launched a missile strike.",
        extracted_at=datetime(2024, 1, 1, 12, 0, 0),
        request_id="req_001",
    )
    defaults.update(overrides)
    return OntologicalEntity(**defaults)


# ---------------------------------------------------------------------------
# entity_labels: taxonomy consistency
# ---------------------------------------------------------------------------

class TestEntityLabels:
    def test_layer1_types_non_empty(self):
        assert len(LAYER1_PHYSICAL_TYPES) > 0

    def test_layer2_roles_non_empty(self):
        assert len(LAYER2_STRUCTURAL_ROLES) > 0

    def test_layer3_virtues_non_empty(self):
        assert len(LAYER3_VIRTUE_VICE) > 0

    def test_all_layer1_values_are_strings(self):
        for key, val in LAYER1_PHYSICAL_TYPES.items():
            assert isinstance(key, str) and isinstance(val, str)

    def test_all_layer2_values_are_strings(self):
        for key, val in LAYER2_STRUCTURAL_ROLES.items():
            assert isinstance(key, str) and isinstance(val, str)

    def test_all_layer3_values_are_strings(self):
        for key, val in LAYER3_VIRTUE_VICE.items():
            assert isinstance(key, str) and isinstance(val, str)

    def test_expected_layer1_keys_present(self):
        for key in ("PERSON", "COUNTRY", "ORGANIZATION", "CORPORATION", "MEDIA"):
            assert key in LAYER1_PHYSICAL_TYPES

    def test_expected_layer2_keys_present(self):
        for key in ("AGGRESSOR", "DEFENDER", "CATALYST", "PIVOT", "OBSERVER"):
            assert key in LAYER2_STRUCTURAL_ROLES

    def test_bamboo_virtues_present(self):
        for key in ("RESILIENT", "ADAPTIVE", "PRAGMATIC"):
            assert key in LAYER3_VIRTUE_VICE

    def test_plum_virtues_present(self):
        for key in ("PRINCIPLED", "RIGID", "DEFIANT"):
            assert key in LAYER3_VIRTUE_VICE

    def test_deception_labels_present(self):
        for key in ("DECEPTIVE", "OPAQUE", "MANIPULATIVE"):
            assert key in LAYER3_VIRTUE_VICE

    def test_emergent_labels_present(self):
        for key in ("RISING_POWER", "DECLINING_POWER", "TRANSFORMING"):
            assert key in LAYER3_VIRTUE_VICE


# ---------------------------------------------------------------------------
# OntologicalEntity model
# ---------------------------------------------------------------------------

class TestOntologicalEntity:
    def test_to_dict_keys(self):
        entity = _sample_entity()
        d = entity.to_dict()
        assert "name" in d
        assert "layer1" in d and "value" in d["layer1"] and "description" in d["layer1"]
        assert "layer2" in d and "roles" in d["layer2"] and "descriptions" in d["layer2"]
        assert "layer3" in d and "virtues" in d["layer3"] and "descriptions" in d["layer3"]
        assert "confidence" in d
        assert "extracted_at" in d

    def test_to_dict_values(self):
        entity = _sample_entity()
        d = entity.to_dict()
        assert d["name"] == "Iran"
        assert d["layer1"]["value"] == "COUNTRY"
        assert "CATALYST" in d["layer2"]["roles"]
        assert "DECEPTIVE" in d["layer3"]["virtues"]
        assert d["confidence"] == 0.85

    def test_to_dict_extracted_at_is_iso_string(self):
        entity = _sample_entity()
        d = entity.to_dict()
        # Should be parseable as ISO datetime
        datetime.fromisoformat(d["extracted_at"])

    def test_to_graph_node_keys(self):
        entity = _sample_entity()
        node = entity.to_graph_node()
        assert "id" in node
        assert "name" in node
        assert "ontology_class" in node
        assert "structural_roles" in node
        assert "virtues" in node
        assert "confidence" in node
        assert "properties" in node

    def test_to_graph_node_id_format(self):
        entity = _sample_entity(name="United States")
        node = entity.to_graph_node()
        assert node["id"] == "united_states"

    def test_to_graph_node_roles_joined_with_pipe(self):
        entity = _sample_entity()
        node = entity.to_graph_node()
        assert " | ".join(entity.structural_roles) == node["structural_roles"]

    def test_to_graph_node_virtues_joined_with_pipe(self):
        entity = _sample_entity()
        node = entity.to_graph_node()
        assert " | ".join(entity.philosophical_nature) == node["virtues"]

    def test_narrative_context_defaults_to_none(self):
        entity = _sample_entity()
        assert entity.narrative_context is None

    def test_relationships_defaults_to_empty_list(self):
        entity = _sample_entity()
        assert entity.relationships == []


# ---------------------------------------------------------------------------
# EntityLabel dataclass
# ---------------------------------------------------------------------------

class TestEntityLabel:
    def test_fields_stored_correctly(self):
        lbl = EntityLabel(layer=1, value="COUNTRY", description="Geopolitical state", confidence=0.9)
        assert lbl.layer == 1
        assert lbl.value == "COUNTRY"
        assert lbl.description == "Geopolitical state"
        assert lbl.confidence == 0.9


# ---------------------------------------------------------------------------
# EntityExtractionEngine._parse_response
# ---------------------------------------------------------------------------

class TestParseResponse:
    def test_parses_valid_json_array(self):
        engine = _make_engine()
        data = [{"name": "Iran", "layer1": "COUNTRY", "layer2": "CATALYST", "layer3": "DECEPTIVE"}]
        result = engine._parse_response(json.dumps(data))
        assert result == data

    def test_returns_empty_list_for_empty_string(self):
        engine = _make_engine()
        assert engine._parse_response("") == []

    def test_returns_empty_list_for_invalid_json(self):
        engine = _make_engine()
        assert engine._parse_response("not valid json") == []

    def test_extracts_from_markdown_json_block(self):
        engine = _make_engine()
        data = [{"name": "EU", "layer1": "ORGANIZATION", "layer2": "REGULATOR", "layer3": "RIGID"}]
        response = f"```json\n{json.dumps(data)}\n```"
        result = engine._parse_response(response)
        assert result == data

    def test_extracts_from_plain_markdown_block(self):
        engine = _make_engine()
        data = [{"name": "EU", "layer1": "ORGANIZATION", "layer2": "REGULATOR", "layer3": "RIGID"}]
        response = f"```\n{json.dumps(data)}\n```"
        result = engine._parse_response(response)
        assert result == data

    def test_extracts_array_embedded_in_text(self):
        engine = _make_engine()
        data = [{"name": "X", "layer1": "PERSON", "layer2": "OBSERVER", "layer3": "PRAGMATIC"}]
        response = "Here is the output: " + json.dumps(data) + " end."
        result = engine._parse_response(response)
        assert result == data


# ---------------------------------------------------------------------------
# EntityExtractionEngine._parse_multiple_labels
# ---------------------------------------------------------------------------

class TestParseMultipleLabels:
    def test_single_valid_label(self):
        engine = _make_engine()
        valid = list(LAYER2_STRUCTURAL_ROLES.keys())
        result = engine._parse_multiple_labels("CATALYST", valid)
        assert result == ["CATALYST"]

    def test_underscore_separated_labels(self):
        engine = _make_engine()
        valid = list(LAYER2_STRUCTURAL_ROLES.keys())
        result = engine._parse_multiple_labels("CATALYST_AGGRESSOR", valid)
        assert "CATALYST" in result
        assert "AGGRESSOR" in result

    def test_comma_separated_labels(self):
        engine = _make_engine()
        valid = list(LAYER2_STRUCTURAL_ROLES.keys())
        result = engine._parse_multiple_labels("CATALYST,AGGRESSOR", valid)
        assert "CATALYST" in result
        assert "AGGRESSOR" in result

    def test_invalid_labels_filtered_out(self):
        engine = _make_engine()
        valid = list(LAYER2_STRUCTURAL_ROLES.keys())
        result = engine._parse_multiple_labels("CATALYST_INVALID_AGGRESSOR", valid)
        assert "INVALID" not in result

    def test_max_three_labels(self):
        engine = _make_engine()
        valid = list(LAYER3_VIRTUE_VICE.keys())
        label_str = "_".join(valid[:6])
        result = engine._parse_multiple_labels(label_str, valid)
        assert len(result) <= 3

    def test_empty_string_returns_empty(self):
        engine = _make_engine()
        assert engine._parse_multiple_labels("", list(LAYER2_STRUCTURAL_ROLES.keys())) == []


# ---------------------------------------------------------------------------
# EntityExtractionEngine._fuzzy_match_label
# ---------------------------------------------------------------------------

class TestFuzzyMatchLabel:
    def test_exact_match(self):
        engine = _make_engine()
        result = engine._fuzzy_match_label("COUNTRY", list(LAYER1_PHYSICAL_TYPES.keys()))
        assert result == "COUNTRY"

    def test_substring_match(self):
        engine = _make_engine()
        result = engine._fuzzy_match_label("CORP", list(LAYER1_PHYSICAL_TYPES.keys()))
        assert result == "CORPORATION"

    def test_no_match_returns_none(self):
        engine = _make_engine()
        result = engine._fuzzy_match_label("ZZZZZ", list(LAYER1_PHYSICAL_TYPES.keys()))
        assert result is None


# ---------------------------------------------------------------------------
# EntityExtractionEngine._calculate_confidence
# ---------------------------------------------------------------------------

class TestCalculateConfidence:
    def test_full_confidence_no_defaults(self):
        engine = _make_engine()
        score = engine._calculate_confidence("COUNTRY", ["CATALYST"], ["DECEPTIVE"])
        assert score == 0.85

    def test_observer_role_reduces_confidence(self):
        engine = _make_engine()
        score = engine._calculate_confidence("COUNTRY", ["OBSERVER"], ["DECEPTIVE"])
        assert score == 0.80

    def test_pragmatic_virtue_reduces_confidence(self):
        engine = _make_engine()
        score = engine._calculate_confidence("COUNTRY", ["CATALYST"], ["PRAGMATIC"])
        assert score == 0.80

    def test_both_defaults_reduces_confidence(self):
        engine = _make_engine()
        score = engine._calculate_confidence("COUNTRY", ["OBSERVER"], ["PRAGMATIC"])
        assert score == 0.75

    def test_confidence_clamped_above_0_5(self):
        engine = _make_engine()
        # Even with both defaults, result should be >= 0.5
        score = engine._calculate_confidence("COUNTRY", ["OBSERVER"], ["PRAGMATIC"])
        assert score >= 0.5

    def test_confidence_at_most_1_0(self):
        engine = _make_engine()
        score = engine._calculate_confidence("PERSON", ["AGGRESSOR"], ["RESILIENT"])
        assert score <= 1.0


# ---------------------------------------------------------------------------
# EntityExtractionEngine._create_ontological_entity
# ---------------------------------------------------------------------------

class TestCreateOntologicalEntity:
    def test_valid_raw_creates_entity(self):
        engine = _make_engine()
        raw = {"name": "Iran", "layer1": "COUNTRY", "layer2": "CATALYST", "layer3": "DECEPTIVE"}
        entity = engine._create_ontological_entity(raw, "req_1", "Some text about Iran.")
        assert entity is not None
        assert entity.name == "Iran"
        assert entity.physical_type == "COUNTRY"
        assert "CATALYST" in entity.structural_roles
        assert "DECEPTIVE" in entity.philosophical_nature

    def test_missing_name_returns_none(self):
        engine = _make_engine()
        raw = {"name": "", "layer1": "COUNTRY", "layer2": "CATALYST", "layer3": "DECEPTIVE"}
        assert engine._create_ontological_entity(raw, "req", "text") is None

    def test_missing_layer1_returns_none(self):
        engine = _make_engine()
        raw = {"name": "Iran", "layer1": "", "layer2": "CATALYST", "layer3": "DECEPTIVE"}
        assert engine._create_ontological_entity(raw, "req", "text") is None

    def test_invalid_layer1_returns_none_when_no_fuzzy(self):
        engine = _make_engine()
        raw = {"name": "Iran", "layer1": "ZZZZZ", "layer2": "CATALYST", "layer3": "DECEPTIVE"}
        assert engine._create_ontological_entity(raw, "req", "text") is None

    def test_invalid_layer2_defaults_to_observer(self):
        engine = _make_engine()
        raw = {"name": "Iran", "layer1": "COUNTRY", "layer2": "ZZZZZ", "layer3": "DECEPTIVE"}
        entity = engine._create_ontological_entity(raw, "req", "text")
        assert entity is not None
        assert entity.structural_roles == ["OBSERVER"]

    def test_invalid_layer3_defaults_to_pragmatic(self):
        engine = _make_engine()
        raw = {"name": "Iran", "layer1": "COUNTRY", "layer2": "CATALYST", "layer3": "ZZZZZ"}
        entity = engine._create_ontological_entity(raw, "req", "text")
        assert entity is not None
        assert entity.philosophical_nature == ["PRAGMATIC"]

    def test_source_text_truncated_to_200_chars(self):
        engine = _make_engine()
        long_text = "x" * 500
        raw = {"name": "X", "layer1": "PERSON", "layer2": "OBSERVER", "layer3": "PRAGMATIC"}
        entity = engine._create_ontological_entity(raw, "req", long_text)
        assert entity is not None
        assert len(entity.source_text) <= 200

    def test_role_descriptions_populated(self):
        engine = _make_engine()
        raw = {"name": "EU", "layer1": "ORGANIZATION", "layer2": "REGULATOR", "layer3": "RIGID"}
        entity = engine._create_ontological_entity(raw, "req", "text")
        assert entity is not None
        assert "REGULATOR" in entity.role_descriptions

    def test_virtue_descriptions_populated(self):
        engine = _make_engine()
        raw = {"name": "EU", "layer1": "ORGANIZATION", "layer2": "REGULATOR", "layer3": "RIGID"}
        entity = engine._create_ontological_entity(raw, "req", "text")
        assert entity is not None
        assert "RIGID" in entity.virtue_descriptions


# ---------------------------------------------------------------------------
# EntityExtractionEngine.extract – integration
# ---------------------------------------------------------------------------

class TestExtract:
    def test_returns_list(self):
        engine = _make_engine("[]")
        result = engine.extract("Some news text.", "req_1")
        assert isinstance(result, list)

    def test_empty_llm_response_returns_empty_list(self):
        engine = _make_engine("[]")
        assert engine.extract("text", "req") == []

    def test_valid_llm_response_returns_entities(self):
        payload = json.dumps([
            {"name": "Iran", "layer1": "COUNTRY", "layer2": "CATALYST_AGGRESSOR", "layer3": "DECEPTIVE_RESILIENT"},
            {"name": "EU", "layer1": "ORGANIZATION", "layer2": "REGULATOR", "layer3": "RIGID_PRINCIPLED"},
        ])
        engine = _make_engine(payload)
        result = engine.extract("Iran launched a strike. The EU responded.", "req_2")
        assert len(result) == 2
        names = {e.name for e in result}
        assert "Iran" in names
        assert "EU" in names

    def test_entity_has_all_required_fields(self):
        payload = json.dumps([
            {"name": "Iran", "layer1": "COUNTRY", "layer2": "CATALYST", "layer3": "DECEPTIVE"},
        ])
        engine = _make_engine(payload)
        result = engine.extract("Iran news.", "req_3")
        assert len(result) == 1
        e = result[0]
        assert e.name == "Iran"
        assert e.physical_type == "COUNTRY"
        assert isinstance(e.structural_roles, list) and len(e.structural_roles) > 0
        assert isinstance(e.philosophical_nature, list) and len(e.philosophical_nature) > 0
        assert 0.0 <= e.confidence_score <= 1.0
        assert e.request_id == "req_3"

    def test_malformed_llm_response_returns_empty(self):
        engine = _make_engine("this is not json at all")
        result = engine.extract("text", "req")
        assert result == []

    def test_multiple_roles_parsed(self):
        payload = json.dumps([
            {"name": "Iran", "layer1": "COUNTRY", "layer2": "CATALYST_AGGRESSOR", "layer3": "DECEPTIVE"},
        ])
        engine = _make_engine(payload)
        result = engine.extract("Iran news.", "req")
        assert len(result) == 1
        assert "CATALYST" in result[0].structural_roles
        assert "AGGRESSOR" in result[0].structural_roles

    def test_multiple_virtues_parsed(self):
        payload = json.dumps([
            {"name": "Iran", "layer1": "COUNTRY", "layer2": "CATALYST", "layer3": "DECEPTIVE_RESILIENT_CALCULATED"},
        ])
        engine = _make_engine(payload)
        result = engine.extract("Iran news.", "req")
        assert len(result) == 1
        assert "DECEPTIVE" in result[0].philosophical_nature
        assert "RESILIENT" in result[0].philosophical_nature
        assert "CALCULATED" in result[0].philosophical_nature
