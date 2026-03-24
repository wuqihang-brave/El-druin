"""
Unit tests for knowledge_layer.entity_resolver
===============================================

Tests cover:
1. _similarity helper
2. GlobalEntityResolver.find_similar_entities
3. GlobalEntityResolver.resolve_entity (new vs existing)
4. GlobalEntityResolver.merge_entities
5. GlobalEntityResolver.update_property_history
6. Match.to_dict
"""

from __future__ import annotations

import json
import sys
import os
import uuid

import pytest

# Allow importing from the backend directory directly.
_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(_BACKEND_DIR))

from knowledge_layer.entity_resolver import (
    SIMILARITY_THRESHOLD,
    GlobalEntityResolver,
    Match,
    _similarity,
    _now_iso,
)


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
        assert _similarity("xyz123", "abc456") < 0.5

    def test_empty_strings(self):
        assert _similarity("", "") == 1.0


# ---------------------------------------------------------------------------
# Match
# ---------------------------------------------------------------------------

class TestMatch:
    def test_to_dict_keys(self):
        m = Match("id1", "Alice", "Person", 0.92, True)
        d = m.to_dict()
        assert set(d.keys()) == {"entity_id", "entity_name", "entity_type", "similarity", "auto_merge"}

    def test_auto_merge_true_above_threshold(self):
        m = Match("id1", "Alice", "Person", SIMILARITY_THRESHOLD + 0.01, True)
        assert m.auto_merge is True

    def test_auto_merge_false_below_threshold(self):
        m = Match("id1", "Alice", "Person", SIMILARITY_THRESHOLD - 0.01, False)
        assert m.auto_merge is False


# ---------------------------------------------------------------------------
# GlobalEntityResolver (in-memory, no store)
# ---------------------------------------------------------------------------

class TestFindSimilarEntities:
    def test_empty_memory(self):
        resolver = GlobalEntityResolver()
        result = resolver.find_similar_entities("Federal Reserve", "Organization")
        assert result == []

    def test_high_similarity_sets_auto_merge(self):
        resolver = GlobalEntityResolver()
        resolver._memory["id1"] = {
            "id": "id1", "name": "Federal Reserve", "type": "Organization",
            "property_history": "[]",
        }
        matches = resolver.find_similar_entities("Federal Reserve", "Organization")
        assert len(matches) == 1
        assert matches[0].auto_merge is True
        assert matches[0].similarity == 1.0

    def test_different_type_excluded(self):
        resolver = GlobalEntityResolver()
        resolver._memory["id1"] = {
            "id": "id1", "name": "Federal Reserve", "type": "Person",
            "property_history": "[]",
        }
        matches = resolver.find_similar_entities("Federal Reserve", "Organization")
        assert matches == []

    def test_sorted_descending(self):
        resolver = GlobalEntityResolver()
        resolver._memory["id1"] = {"id": "id1", "name": "Fed Reserve",         "type": "Organization", "property_history": "[]"}
        resolver._memory["id2"] = {"id": "id2", "name": "Federal Reserve Bank", "type": "Organization", "property_history": "[]"}
        resolver._memory["id3"] = {"id": "id3", "name": "Federal Reserve",      "type": "Organization", "property_history": "[]"}

        matches = resolver.find_similar_entities("Federal Reserve", "Organization")
        scores = [m.similarity for m in matches]
        assert scores == sorted(scores, reverse=True)

    def test_max_10_returned(self):
        resolver = GlobalEntityResolver()
        for i in range(20):
            resolver._memory[f"id{i}"] = {
                "id": f"id{i}", "name": f"Entity {i}", "type": "Organization",
                "property_history": "[]",
            }
        result = resolver.find_similar_entities("Entity X", "Organization")
        assert len(result) <= 10

    def test_custom_threshold(self):
        resolver = GlobalEntityResolver(similarity_threshold=0.0)
        resolver._memory["id1"] = {
            "id": "id1", "name": "Federal Reserve", "type": "Organization",
            "property_history": "[]",
        }
        matches = resolver.find_similar_entities("Federal Reserve", "Organization", threshold=0.0)
        assert all(m.auto_merge for m in matches)

    def test_skips_empty_name(self):
        resolver = GlobalEntityResolver()
        resolver._memory["id1"] = {
            "id": "id1", "name": "", "type": "Organization", "property_history": "[]"
        }
        result = resolver.find_similar_entities("Federal Reserve", "Organization")
        assert result == []


# ---------------------------------------------------------------------------
# resolve_entity
# ---------------------------------------------------------------------------

class TestResolveEntity:
    def test_creates_new_entity_when_no_match(self):
        resolver = GlobalEntityResolver()
        eid = resolver.resolve_entity("New Entity", "Organization")
        assert isinstance(eid, str) and len(eid) > 0
        assert eid in resolver._memory

    def test_returns_existing_entity_on_high_similarity(self):
        resolver = GlobalEntityResolver()
        # Pre-seed an entity
        fixed_id = "existing-id"
        resolver._memory[fixed_id] = {
            "id": fixed_id, "name": "Federal Reserve", "type": "Organization",
            "property_history": "[]",
        }
        returned_id = resolver.resolve_entity("Federal Reserve", "Organization")
        assert returned_id == fixed_id

    def test_creates_separate_entity_for_different_name(self):
        resolver = GlobalEntityResolver()
        id1 = resolver.resolve_entity("Federal Reserve", "Organization")
        id2 = resolver.resolve_entity("European Central Bank", "Organization")
        assert id1 != id2

    def test_raises_on_empty_name(self):
        resolver = GlobalEntityResolver()
        with pytest.raises(ValueError):
            resolver.resolve_entity("", "Organization")

    def test_exact_id_match_returns_same_id(self):
        resolver = GlobalEntityResolver()
        fixed_id = str(uuid.uuid4())
        resolver._memory[fixed_id] = {
            "id": fixed_id, "name": "Test Entity", "type": "Person",
            "property_history": "[]",
        }
        returned = resolver.resolve_entity(
            "Test Entity", "Person", properties={"id": fixed_id}
        )
        assert returned == fixed_id

    def test_property_history_recorded_for_new_entity(self):
        resolver = GlobalEntityResolver()
        eid = resolver.resolve_entity(
            "Test Corp", "Organization",
            properties={"order_index": 80},
            source_ref="article-abc",
        )
        entity = resolver._memory[eid]
        history = json.loads(entity["property_history"])
        assert any(h["property_name"] == "order_index" for h in history)

    def test_property_updated_on_second_resolve(self):
        resolver = GlobalEntityResolver()
        eid = resolver.resolve_entity("Federal Reserve", "Organization",
                                      properties={"order_index": 70})
        # Second call with new property value
        resolver.resolve_entity("Federal Reserve", "Organization",
                                 properties={"order_index": 85},
                                 source_ref="article-xyz")
        entity = resolver._memory[eid]
        history = json.loads(entity["property_history"])
        order_changes = [h for h in history if h["property_name"] == "order_index"]
        assert len(order_changes) >= 1


# ---------------------------------------------------------------------------
# merge_entities
# ---------------------------------------------------------------------------

class TestMergeEntities:
    def test_merge_returns_primary_id(self):
        resolver = GlobalEntityResolver()
        primary_id = "p1"
        secondary_id = "s1"
        resolver._memory[primary_id] = {
            "id": primary_id, "name": "Federal Reserve", "type": "Organization",
            "property_history": "[]",
        }
        resolver._memory[secondary_id] = {
            "id": secondary_id, "name": "Fed Reserve", "type": "Organization",
            "property_history": "[]",
        }
        result = resolver.merge_entities(primary_id, secondary_id, "same entity")
        assert result == primary_id

    def test_secondary_removed_after_merge(self):
        resolver = GlobalEntityResolver()
        resolver._memory["p1"] = {"id": "p1", "name": "A", "type": "Organization", "property_history": "[]"}
        resolver._memory["s1"] = {"id": "s1", "name": "B", "type": "Organization", "property_history": "[]"}
        resolver.merge_entities("p1", "s1")
        assert "s1" not in resolver._memory

    def test_merge_event_in_primary_history(self):
        resolver = GlobalEntityResolver()
        resolver._memory["p1"] = {"id": "p1", "name": "A", "type": "Organization", "property_history": "[]"}
        resolver._memory["s1"] = {"id": "s1", "name": "B", "type": "Organization", "property_history": "[]"}
        resolver.merge_entities("p1", "s1", reasoning="test merge")
        history = json.loads(resolver._memory["p1"]["property_history"])
        merge_events = [h for h in history if h["property_name"] == "_merge"]
        assert len(merge_events) == 1
        assert merge_events[0]["reasoning"] == "test merge"

    def test_secondary_name_added_to_aliases(self):
        resolver = GlobalEntityResolver()
        resolver._memory["p1"] = {"id": "p1", "name": "A", "type": "Organization", "property_history": "[]"}
        resolver._memory["s1"] = {"id": "s1", "name": "B", "type": "Organization", "property_history": "[]"}
        resolver.merge_entities("p1", "s1")
        aliases = resolver._memory["p1"].get("aliases", [])
        assert "B" in aliases

    def test_raises_for_missing_primary(self):
        resolver = GlobalEntityResolver()
        resolver._memory["s1"] = {"id": "s1", "name": "B", "type": "Organization", "property_history": "[]"}
        with pytest.raises(KeyError):
            resolver.merge_entities("nonexistent", "s1")

    def test_raises_for_missing_secondary(self):
        resolver = GlobalEntityResolver()
        resolver._memory["p1"] = {"id": "p1", "name": "A", "type": "Organization", "property_history": "[]"}
        with pytest.raises(KeyError):
            resolver.merge_entities("p1", "nonexistent")

    def test_secondary_history_prepended_to_primary(self):
        resolver = GlobalEntityResolver()
        sec_history = [{"timestamp": "2024-01-01T00:00:00Z", "property_name": "old_prop",
                        "old_value": None, "new_value": "x", "source_ref": "", "confidence": 1.0}]
        resolver._memory["p1"] = {"id": "p1", "name": "A", "type": "Organization", "property_history": "[]"}
        resolver._memory["s1"] = {
            "id": "s1", "name": "B", "type": "Organization",
            "property_history": json.dumps(sec_history),
        }
        resolver.merge_entities("p1", "s1")
        history = json.loads(resolver._memory["p1"]["property_history"])
        assert history[0]["property_name"] == "old_prop"


# ---------------------------------------------------------------------------
# update_property_history
# ---------------------------------------------------------------------------

class TestUpdatePropertyHistory:
    def test_appends_entry(self):
        resolver = GlobalEntityResolver()
        eid = "e1"
        resolver._memory[eid] = {"id": eid, "name": "X", "type": "Organization", "property_history": "[]"}
        resolver.update_property_history(eid, "risk_level", "medium", "high", "article-1", 0.9)
        history = json.loads(resolver._memory[eid]["property_history"])
        assert len(history) == 1
        entry = history[0]
        assert entry["property_name"] == "risk_level"
        assert entry["old_value"] == "medium"
        assert entry["new_value"] == "high"
        assert entry["source_ref"] == "article-1"
        assert entry["confidence"] == 0.9

    def test_multiple_entries_accumulated(self):
        resolver = GlobalEntityResolver()
        eid = "e1"
        resolver._memory[eid] = {"id": eid, "name": "X", "type": "Organization", "property_history": "[]"}
        resolver.update_property_history(eid, "p1", None, 1, "src-a", 0.8)
        resolver.update_property_history(eid, "p2", None, 2, "src-b", 0.9)
        history = json.loads(resolver._memory[eid]["property_history"])
        assert len(history) == 2

    def test_noop_for_unknown_entity(self):
        resolver = GlobalEntityResolver()
        # Should not raise
        resolver.update_property_history("nonexistent", "p", None, 1, "", 1.0)
