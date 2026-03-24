"""
Unit tests for knowledge_layer.incremental_extractor
=====================================================

Tests cover:
1. Entity similarity matching (find_similar_entities)
2. Conflict detection between relations (detect_conflict)
3. CONTRADICTS edge creation (create_contradicts_edge)
4. Full incremental_update orchestration
5. FEW_SHOT_CAUSAL_PROMPT content validation
"""

from __future__ import annotations

import sys
import os

# Allow importing from the backend directory directly.
_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(_BACKEND_DIR))

from unittest.mock import MagicMock, patch, call
from typing import Any, Dict, List

import pytest

from knowledge_layer.incremental_extractor import (
    ENTITY_SIMILARITY_THRESHOLD,
    FEW_SHOT_CAUSAL_PROMPT,
    _CONTRADICTING_SET,
    _similarity,
    create_contradicts_edge,
    detect_conflict,
    find_similar_entities,
    incremental_update,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store(entities: List[Dict] = None, relations: List[Dict] = None) -> MagicMock:
    """Return a mock store pre-loaded with *entities* and *relations*."""
    store = MagicMock()
    store.get_entities.return_value = entities or []
    store.get_relations.return_value = relations or []
    store.add_entity.return_value = None
    store.add_relation.return_value = None
    store.add_contradicts.return_value = None
    return store


# ---------------------------------------------------------------------------
# _similarity
# ---------------------------------------------------------------------------

class TestSimilarity:
    def test_identical_strings(self):
        assert _similarity("Federal Reserve", "Federal Reserve") == 1.0

    def test_case_insensitive(self):
        assert _similarity("federal reserve", "Federal Reserve") == 1.0

    def test_partial_overlap(self):
        sim = _similarity("Federal Reserve", "Federal Bank")
        assert 0.0 < sim < 1.0

    def test_no_overlap(self):
        sim = _similarity("xyz123", "abc456")
        assert sim < 0.5

    def test_empty_strings(self):
        assert _similarity("", "") == 1.0


# ---------------------------------------------------------------------------
# find_similar_entities
# ---------------------------------------------------------------------------

class TestFindSimilarEntities:
    def test_returns_empty_when_store_empty(self):
        store = _make_store(entities=[])
        result = find_similar_entities("Federal Reserve", "ORG", store)
        assert result == []

    def test_exact_match_is_conflict(self):
        store = _make_store(entities=[
            {"name": "Federal Reserve", "type": "ORG", "description": "US central bank"},
        ])
        result = find_similar_entities("Federal Reserve", "ORG", store)
        assert len(result) == 1
        assert result[0]["is_conflict"] is True
        assert result[0]["similarity"] == 1.0

    def test_unrelated_name_not_conflict(self):
        store = _make_store(entities=[
            {"name": "Taylor Swift", "type": "PERSON", "description": "Pop star"},
        ])
        result = find_similar_entities("Federal Reserve", "ORG", store)
        # Should have low similarity, not flagged as conflict
        for c in result:
            assert c["is_conflict"] is False

    def test_sorted_by_similarity_descending(self):
        store = _make_store(entities=[
            {"name": "Fed Reserve", "type": "ORG", "description": ""},
            {"name": "Federal Reserve Bank", "type": "ORG", "description": ""},
            {"name": "Federal Reserve", "type": "ORG", "description": ""},
        ])
        result = find_similar_entities("Federal Reserve", "ORG", store)
        scores = [c["similarity"] for c in result]
        assert scores == sorted(scores, reverse=True)

    def test_max_10_candidates_returned(self):
        store = _make_store(entities=[
            {"name": f"Entity {i}", "type": "ORG", "description": ""} for i in range(50)
        ])
        result = find_similar_entities("Entity X", "ORG", store)
        assert len(result) <= 10

    def test_store_error_returns_empty(self):
        store = MagicMock()
        store.get_entities.side_effect = RuntimeError("DB unavailable")
        result = find_similar_entities("Federal Reserve", "ORG", store)
        assert result == []

    def test_custom_threshold(self):
        store = _make_store(entities=[
            {"name": "Fed Reserve", "type": "ORG", "description": ""},
        ])
        # With a very low threshold (0.0) everything is a conflict
        result = find_similar_entities("Fed Reserve", "ORG", store, threshold=0.0)
        assert all(c["is_conflict"] for c in result)

    def test_skips_entities_with_empty_name(self):
        store = _make_store(entities=[
            {"name": "", "type": "ORG", "description": ""},
            {"name": "Federal Reserve", "type": "ORG", "description": ""},
        ])
        result = find_similar_entities("Federal Reserve", "ORG", store)
        names = [c["name"] for c in result]
        assert "" not in names


# ---------------------------------------------------------------------------
# detect_conflict
# ---------------------------------------------------------------------------

class TestDetectConflict:
    def test_raises_vs_cuts_is_conflict(self):
        old = {"subject": "Fed", "predicate": "raises", "object": "rates"}
        new = {"subject": "Fed", "predicate": "cuts",   "object": "rates"}
        assert detect_conflict(old, new) is True

    def test_cuts_vs_raises_symmetric(self):
        old = {"subject": "Fed", "predicate": "cuts",   "object": "rates"}
        new = {"subject": "Fed", "predicate": "raises", "object": "rates"}
        assert detect_conflict(old, new) is True

    def test_same_predicate_no_conflict(self):
        old = {"subject": "Fed", "predicate": "raises", "object": "rates"}
        new = {"subject": "Fed", "predicate": "raises", "object": "rates"}
        assert detect_conflict(old, new) is False

    def test_different_endpoints_no_conflict(self):
        old = {"subject": "Fed", "predicate": "raises", "object": "rates"}
        new = {"subject": "ECB", "predicate": "cuts",   "object": "rates"}
        assert detect_conflict(old, new) is False

    def test_supports_vs_opposes(self):
        old = {"subject": "USA", "predicate": "supports", "object": "Ukraine"}
        new = {"subject": "USA", "predicate": "opposes",  "object": "Ukraine"}
        assert detect_conflict(old, new) is True

    def test_alt_field_names_from_to(self):
        """Should also work with 'from'/'to' field names."""
        old = {"from": "Fed", "relation": "raises", "to": "rates"}
        new = {"from": "Fed", "relation": "cuts",   "to": "rates"}
        assert detect_conflict(old, new) is True

    def test_case_insensitive_predicates(self):
        old = {"subject": "Fed", "predicate": "Raises", "object": "rates"}
        new = {"subject": "Fed", "predicate": "Cuts",   "object": "rates"}
        assert detect_conflict(old, new) is True

    def test_unknown_predicate_pair_no_conflict(self):
        old = {"subject": "A", "predicate": "observes", "object": "B"}
        new = {"subject": "A", "predicate": "monitors", "object": "B"}
        assert detect_conflict(old, new) is False

    def test_reversed_endpoints_still_detected(self):
        """subject/object swapped should still count as same pair."""
        old = {"subject": "rates", "predicate": "raised_by", "object": "Fed"}
        new = {"subject": "Fed",   "predicate": "cuts",       "object": "rates"}
        # Same entity pair (rates ↔ Fed), but "raised_by" not in opposing set
        assert detect_conflict(old, new) is False

    def test_all_known_contradicting_pairs_covered(self):
        """Every pair in _CONTRADICTING_SET should be detected."""
        for pred_a, pred_b in _CONTRADICTING_SET:
            old = {"subject": "X", "predicate": pred_a, "object": "Y"}
            new = {"subject": "X", "predicate": pred_b, "object": "Y"}
            assert detect_conflict(old, new) is True, (
                f"Expected conflict for ({pred_a!r}, {pred_b!r})"
            )


# ---------------------------------------------------------------------------
# create_contradicts_edge
# ---------------------------------------------------------------------------

class TestCreateContradictsEdge:
    def test_calls_store_add_contradicts(self):
        store = _make_store()
        result = create_contradicts_edge(
            store, "Fed", "ECB",
            reason="Test contradiction",
            confidence=0.9,
            source_reliability=0.8,
        )
        assert result is True
        store.add_contradicts.assert_called_once_with(
            from_name="Fed",
            to_name="ECB",
            reason="Test contradiction",
            confidence=0.9,
            source_reliability=0.8,
        )

    def test_returns_false_on_exception(self):
        store = MagicMock()
        store.add_contradicts.side_effect = RuntimeError("DB error")
        result = create_contradicts_edge(store, "A", "B", reason="test")
        assert result is False

    def test_default_confidence_and_reliability(self):
        store = _make_store()
        create_contradicts_edge(store, "A", "B", reason="reason")
        _, kwargs = store.add_contradicts.call_args
        assert kwargs["confidence"] == 0.8
        assert kwargs["source_reliability"] == 0.7


# ---------------------------------------------------------------------------
# incremental_update – entity phase
# ---------------------------------------------------------------------------

class TestIncrementalUpdateEntities:
    def test_new_entity_inserted(self):
        store = _make_store(entities=[], relations=[])
        summary = incremental_update(
            entities=[{"name": "Federal Reserve", "type": "ORG"}],
            relations=[],
            store=store,
        )
        assert summary["entities_added"] == 1
        assert summary["entities_merged"] == 0
        store.add_entity.assert_called_once()

    def test_existing_entity_merged_not_reinserted(self):
        store = _make_store(
            entities=[{"name": "Federal Reserve", "type": "ORG", "description": ""}],
            relations=[],
        )
        summary = incremental_update(
            entities=[{"name": "Federal Reserve", "type": "ORG"}],
            relations=[],
            store=store,
        )
        assert summary["entities_merged"] == 1
        assert summary["entities_added"] == 0
        store.add_entity.assert_not_called()

    def test_empty_name_skipped(self):
        store = _make_store(entities=[], relations=[])
        summary = incremental_update(
            entities=[{"name": "", "type": "ORG"}],
            relations=[],
            store=store,
        )
        assert summary["entities_added"] == 0
        store.add_entity.assert_not_called()

    def test_multiple_entities_partial_merge(self):
        store = _make_store(
            entities=[{"name": "Federal Reserve", "type": "ORG", "description": ""}],
            relations=[],
        )
        summary = incremental_update(
            entities=[
                {"name": "Federal Reserve", "type": "ORG"},
                {"name": "European Central Bank", "type": "ORG"},
            ],
            relations=[],
            store=store,
        )
        assert summary["entities_merged"] == 1
        assert summary["entities_added"] == 1


# ---------------------------------------------------------------------------
# incremental_update – relation / conflict phase
# ---------------------------------------------------------------------------

class TestIncrementalUpdateRelations:
    def test_new_relation_inserted_when_no_conflict(self):
        store = _make_store(entities=[], relations=[])
        summary = incremental_update(
            entities=[],
            relations=[{"from": "Fed", "relation": "raises", "to": "rates"}],
            store=store,
        )
        assert summary["relations_added"] == 1
        assert summary["conflicts_found"] == 0
        store.add_relation.assert_called_once()

    def test_conflicting_relation_creates_contradicts_edge(self):
        existing = [{"from": "Fed", "relation": "raises", "to": "rates"}]
        store = _make_store(entities=[], relations=existing)
        summary = incremental_update(
            entities=[],
            relations=[{"from": "Fed", "relation": "cuts", "to": "rates"}],
            source_reliability=0.8,
            store=store,
        )
        assert summary["conflicts_found"] == 1
        assert summary["contradicts_created"] == 1
        assert summary["relations_added"] == 0
        store.add_contradicts.assert_called_once()
        store.add_relation.assert_not_called()

    def test_contradiction_details_in_output(self):
        existing = [{"from": "USA", "relation": "supports", "to": "Ukraine"}]
        store = _make_store(entities=[], relations=existing)
        summary = incremental_update(
            entities=[],
            relations=[{"from": "USA", "relation": "opposes", "to": "Ukraine"}],
            source_url="https://example.com",
            store=store,
        )
        assert len(summary["contradictions"]) == 1
        c = summary["contradictions"][0]
        assert c["source_url"] == "https://example.com"
        assert "reason" in c
        assert "new_relation" in c
        assert "old_relation" in c

    def test_skips_incomplete_relations(self):
        store = _make_store(entities=[], relations=[])
        summary = incremental_update(
            entities=[],
            relations=[
                {"from": "", "relation": "raises", "to": "rates"},
                {"from": "Fed",  "relation": "raises", "to": ""},
            ],
            store=store,
        )
        assert summary["relations_added"] == 0

    def test_relation_uses_canonical_entity_name(self):
        """After entity merge, relations should reference the canonical name."""
        store = _make_store(
            entities=[{"name": "Federal Reserve", "type": "ORG", "description": ""}],
            relations=[],
        )
        summary = incremental_update(
            entities=[{"name": "Federal Reserve", "type": "ORG"}],
            relations=[{"from": "Federal Reserve", "relation": "raises", "to": "rates"}],
            store=store,
        )
        assert summary["entities_merged"] == 1
        assert summary["relations_added"] == 1

    def test_store_get_relations_error_handled(self):
        store = MagicMock()
        store.get_entities.return_value = []
        store.get_relations.side_effect = RuntimeError("DB error")
        store.add_entity.return_value = None
        store.add_relation.return_value = None
        # Should not raise; relations are still attempted with empty existing set
        summary = incremental_update(
            entities=[],
            relations=[{"from": "A", "relation": "r", "to": "B"}],
            store=store,
        )
        assert summary["relations_added"] == 1

    def test_non_incremental_path_simple_insert(self):
        store = _make_store(entities=[], relations=[])
        # Provide a store that exposes add_entity / add_relation (basic interface)
        summary = incremental_update(
            entities=[{"name": "Fed", "type": "ORG"}],
            relations=[{"from": "Fed", "relation": "raises", "to": "rates"}],
            store=store,
        )
        # incremental_update is always incremental; non-incremental is handled
        # at the API layer.  Here we just verify it runs without error.
        assert isinstance(summary["entities_added"], int)


# ---------------------------------------------------------------------------
# FEW_SHOT_CAUSAL_PROMPT validation
# ---------------------------------------------------------------------------

class TestFewShotCausalPrompt:
    def test_prompt_is_non_empty_string(self):
        assert isinstance(FEW_SHOT_CAUSAL_PROMPT, str)
        assert len(FEW_SHOT_CAUSAL_PROMPT) > 100

    def test_contains_three_examples(self):
        assert FEW_SHOT_CAUSAL_PROMPT.count("### Example") == 3

    def test_contains_example1_policy_change(self):
        assert "Federal Reserve" in FEW_SHOT_CAUSAL_PROMPT
        assert "interest rates" in FEW_SHOT_CAUSAL_PROMPT

    def test_contains_example2_event_response(self):
        assert "earthquake" in FEW_SHOT_CAUSAL_PROMPT
        assert "NATO" in FEW_SHOT_CAUSAL_PROMPT

    def test_contains_example3_person_consequence(self):
        assert "Elon Musk" in FEW_SHOT_CAUSAL_PROMPT
        assert "Twitter" in FEW_SHOT_CAUSAL_PROMPT

    def test_prompt_instructs_causal_extraction(self):
        lower = FEW_SHOT_CAUSAL_PROMPT.lower()
        assert "causal" in lower or "causes" in lower

    def test_prompt_specifies_json_output(self):
        assert "entities" in FEW_SHOT_CAUSAL_PROMPT
        assert "relations" in FEW_SHOT_CAUSAL_PROMPT
