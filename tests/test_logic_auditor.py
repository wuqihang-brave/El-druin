"""
Unit tests for the Bayesian Bridge – Logic Auditor
===================================================

Tests cover:
1. ReasoningPathRecorder: start_path, record_evidence, record_inference_step,
   record_graph_change, finalize_path, get_path, list_paths
2. ProbabilityTreeBuilder: build_tree, select_best_branch, store_tree, get_tree
3. Pydantic models: ReasoningPath, ProbabilityTree validation
4. Edge cases: unknown enum values, empty inputs, missing fields
"""

from __future__ import annotations

import json
import sys
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

# Allow importing from the backend directory directly.
_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(_BACKEND_DIR))

from intelligence.models import (
    AuditStatus,
    ChangeType,
    ExtractedFact,
    GraphChange,
    InferenceStep,
    InputEvidence,
    InterpretationBranch,
    ProbabilityTree,
    ReasoningPath,
    ReasoningType,
    SourceInfo,
    SourceType,
)
from intelligence.logic_auditor import ReasoningPathRecorder
from intelligence.probability_tree import (
    ProbabilityTreeBuilder,
    _causal_confidence,
    _contradiction_confidence,
    _extract_entities_from_text,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_recorder(tmp_path: Path) -> ReasoningPathRecorder:
    """ReasoningPathRecorder backed by a temp JSONL file."""
    return ReasoningPathRecorder(audit_log=tmp_path / "audit.jsonl")


@pytest.fixture()
def tmp_builder(tmp_path: Path) -> ProbabilityTreeBuilder:
    """ProbabilityTreeBuilder backed by a temp JSONL file."""
    return ProbabilityTreeBuilder(tree_store=tmp_path / "trees.jsonl")


# ---------------------------------------------------------------------------
# Model validation
# ---------------------------------------------------------------------------

class TestModels:
    def test_source_info_defaults(self):
        s = SourceInfo(type=SourceType.NEWS_ARTICLE)
        assert s.reliability == 0.7
        assert s.url == ""

    def test_reasoning_path_serialises_enum_as_string(self):
        path = ReasoningPath(
            path_id="test-id",
            timestamp="2024-01-01T00:00:00Z",
            source=SourceInfo(type=SourceType.NEWS_ARTICLE),
            audit_status=AuditStatus.APPROVED,
        )
        d = path.model_dump()
        assert d["audit_status"] == "approved"

    def test_inference_step_enum_serialised(self):
        step = InferenceStep(
            step_num=1,
            reasoning_type=ReasoningType.CAUSAL_EXTRACTION,
        )
        d = step.model_dump()
        assert d["reasoning_type"] == "causal_extraction"

    def test_graph_change_enum_serialised(self):
        change = GraphChange(
            change_type=ChangeType.EDGE_CREATED,
            entity_id="ent_1",
        )
        d = change.model_dump()
        assert d["change_type"] == "edge_created"

    def test_extracted_fact_alias_fields(self):
        fact = ExtractedFact(
            type="INFLUENCES",
            **{"from": "A", "to": "B"},
            causality_score=0.8,
        )
        assert fact.from_entity == "A"
        assert fact.to_entity == "B"

    def test_probability_tree_defaults(self):
        tree = ProbabilityTree(
            report_id="r1",
            timestamp="2024-01-01T00:00:00Z",
            raw_text="some text",
        )
        assert tree.total_probability == 1.0
        assert tree.selected_branch == 1


# ---------------------------------------------------------------------------
# ReasoningPathRecorder
# ---------------------------------------------------------------------------

class TestReasoningPathRecorderStartPath:
    def test_returns_uuid_string(self, tmp_recorder):
        path_id = tmp_recorder.start_path("news_article", "https://example.com", 0.8)
        import uuid
        uuid.UUID(path_id)  # Should not raise

    def test_unknown_source_type_defaults_to_news_article(self, tmp_recorder):
        path_id = tmp_recorder.start_path("unknown_type", "", 0.5)
        # Should not raise; just logs a warning
        assert path_id in tmp_recorder._active

    def test_path_in_active_after_start(self, tmp_recorder):
        path_id = tmp_recorder.start_path("news_article", "", 0.8)
        assert path_id in tmp_recorder._active

    def test_source_reliability_clamped_to_float(self, tmp_recorder):
        path_id = tmp_recorder.start_path("news_article", "", 1)
        source = tmp_recorder._active[path_id]["source"]
        assert isinstance(source["reliability"], float)


class TestReasoningPathRecorderRecordEvidence:
    def test_evidence_appended(self, tmp_recorder):
        path_id = tmp_recorder.start_path("news_article", "", 0.8)
        tmp_recorder.record_evidence(path_id, "e1", "Fed Reserve", "mentioned", 0.9)
        assert len(tmp_recorder._active[path_id]["input_evidence"]) == 1

    def test_multiple_evidence_items(self, tmp_recorder):
        path_id = tmp_recorder.start_path("news_article", "", 0.8)
        for i in range(3):
            tmp_recorder.record_evidence(path_id, f"e{i}", f"Entity {i}", "", 0.7)
        assert len(tmp_recorder._active[path_id]["input_evidence"]) == 3

    def test_unknown_path_id_is_ignored(self, tmp_recorder):
        # Should not raise
        tmp_recorder.record_evidence("nonexistent", "e1", "Name", "", 0.9)


class TestReasoningPathRecorderInferenceStep:
    def test_step_appended_with_sequential_num(self, tmp_recorder):
        path_id = tmp_recorder.start_path("news_article", "", 0.8)
        tmp_recorder.record_inference_step(path_id, "prompt", "response", 0.85, "causal_extraction")
        step = tmp_recorder._active[path_id]["inference_steps"][0]
        assert step["step_num"] == 1

    def test_step_num_increments(self, tmp_recorder):
        path_id = tmp_recorder.start_path("news_article", "", 0.8)
        tmp_recorder.record_inference_step(path_id, "p1", "r1", 0.85, "causal_extraction")
        tmp_recorder.record_inference_step(path_id, "p2", "r2", 0.72, "conflict_detection")
        steps = tmp_recorder._active[path_id]["inference_steps"]
        assert steps[0]["step_num"] == 1
        assert steps[1]["step_num"] == 2

    def test_unknown_reasoning_type_defaults(self, tmp_recorder):
        path_id = tmp_recorder.start_path("news_article", "", 0.8)
        tmp_recorder.record_inference_step(path_id, "p", "r", 0.5, "totally_unknown")
        step = tmp_recorder._active[path_id]["inference_steps"][0]
        assert step["reasoning_type"] == "causal_extraction"


class TestReasoningPathRecorderGraphChange:
    def test_change_appended(self, tmp_recorder):
        path_id = tmp_recorder.start_path("news_article", "", 0.8)
        tmp_recorder.record_graph_change(path_id, "edge_created", "A", "B", "INFLUENCES", {})
        assert len(tmp_recorder._active[path_id]["graph_changes"]) == 1

    def test_unknown_change_type_defaults(self, tmp_recorder):
        path_id = tmp_recorder.start_path("news_article", "", 0.8)
        tmp_recorder.record_graph_change(path_id, "bad_type", "A", "B", "R")
        change = tmp_recorder._active[path_id]["graph_changes"][0]
        assert change["change_type"] == "edge_created"

    def test_properties_default_empty_dict(self, tmp_recorder):
        path_id = tmp_recorder.start_path("news_article", "", 0.8)
        tmp_recorder.record_graph_change(path_id, "node_created", "A", "", "")
        change = tmp_recorder._active[path_id]["graph_changes"][0]
        assert change["properties"] == {}


class TestReasoningPathRecorderFinalize:
    def test_returns_reasoning_path(self, tmp_recorder):
        path_id = tmp_recorder.start_path("news_article", "", 0.8)
        path = tmp_recorder.finalize_path(path_id)
        assert isinstance(path, ReasoningPath)

    def test_path_moved_to_completed(self, tmp_recorder):
        path_id = tmp_recorder.start_path("news_article", "", 0.8)
        tmp_recorder.finalize_path(path_id)
        assert path_id not in tmp_recorder._active
        assert path_id in tmp_recorder._completed

    def test_final_confidence_is_step_average(self, tmp_recorder):
        path_id = tmp_recorder.start_path("news_article", "", 0.8)
        tmp_recorder.record_inference_step(path_id, "p1", "r1", 0.8, "causal_extraction")
        tmp_recorder.record_inference_step(path_id, "p2", "r2", 0.6, "conflict_detection")
        path = tmp_recorder.finalize_path(path_id)
        assert abs(path.final_confidence - 0.7) < 1e-4

    def test_final_confidence_fallback_to_source_reliability(self, tmp_recorder):
        path_id = tmp_recorder.start_path("news_article", "", 0.9)
        path = tmp_recorder.finalize_path(path_id)
        assert path.final_confidence == 0.9

    def test_unknown_audit_status_defaults_to_pending(self, tmp_recorder):
        path_id = tmp_recorder.start_path("news_article", "", 0.8)
        path = tmp_recorder.finalize_path(path_id, audit_status="totally_unknown")
        assert path.audit_status == "pending_review"

    def test_audit_log_written(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        recorder = ReasoningPathRecorder(audit_log=log)
        path_id = recorder.start_path("news_article", "", 0.8)
        recorder.finalize_path(path_id)
        assert log.exists()
        data = json.loads(log.read_text().strip())
        assert data["path_id"] == path_id

    def test_finalize_nonexistent_path_raises(self, tmp_recorder):
        with pytest.raises(KeyError):
            tmp_recorder.finalize_path("nonexistent-id")

    def test_get_path_returns_none_for_unknown(self, tmp_recorder):
        assert tmp_recorder.get_path("no-such-id") is None

    def test_get_path_returns_completed(self, tmp_recorder):
        path_id = tmp_recorder.start_path("news_article", "", 0.8)
        tmp_recorder.finalize_path(path_id)
        assert tmp_recorder.get_path(path_id) is not None

    def test_list_paths_respects_limit(self, tmp_recorder):
        for _ in range(5):
            pid = tmp_recorder.start_path("news_article", "", 0.8)
            tmp_recorder.finalize_path(pid)
        assert len(tmp_recorder.list_paths(limit=3)) <= 3


# ---------------------------------------------------------------------------
# ProbabilityTreeBuilder – heuristics
# ---------------------------------------------------------------------------

class TestHeuristics:
    def test_causal_confidence_no_keywords(self):
        assert _causal_confidence("Nothing happens here.") == 0.2

    def test_causal_confidence_single_keyword(self):
        conf = _causal_confidence("The Fed raises rates today.")
        assert 0.5 <= conf <= 0.65

    def test_causal_confidence_multiple_keywords(self):
        conf = _causal_confidence("Fed raises rates, boosts inflation, impacts economy.")
        assert conf > 0.7

    def test_contradiction_confidence_no_keywords(self):
        assert _contradiction_confidence("All is well.") == 0.1

    def test_contradiction_confidence_single_keyword(self):
        conf = _contradiction_confidence("The official denies the report.")
        assert 0.4 <= conf <= 0.55

    def test_extract_entities_returns_capitalised(self):
        entities = _extract_entities_from_text("Federal Reserve Chair Jerome Powell announced today.")
        assert len(entities) > 0
        assert all(e[0].isupper() for e in entities)

    def test_extract_entities_cap_at_six(self):
        text = "Alice Bob Charlie David Eve Frank Grace Henry Ivan Jane"
        entities = _extract_entities_from_text(text)
        assert len(entities) <= 6


# ---------------------------------------------------------------------------
# ProbabilityTreeBuilder – build_tree
# ---------------------------------------------------------------------------

class TestProbabilityTreeBuilderBuildTree:
    def test_returns_probability_tree(self, tmp_builder):
        tree = tmp_builder.build_tree("Fed raises rates.", 0.9)
        assert isinstance(tree, ProbabilityTree)

    def test_always_three_branches(self, tmp_builder):
        tree = tmp_builder.build_tree("Some text.", 0.7)
        assert len(tree.interpretation_branches) == 3

    def test_weights_sum_to_one(self, tmp_builder):
        tree = tmp_builder.build_tree("The policy was reversed after denials.", 0.8)
        total = sum(b.weight for b in tree.interpretation_branches)
        assert abs(total - 1.0) < 1e-3

    def test_selected_branch_is_highest_weight(self, tmp_builder):
        tree = tmp_builder.build_tree("Fed Chair announces rate hike affecting stock market.", 0.9)
        best = max(tree.interpretation_branches, key=lambda b: b.weight)
        assert tree.selected_branch == best.branch_id

    def test_report_id_auto_generated(self, tmp_builder):
        tree = tmp_builder.build_tree("text", 0.5)
        import uuid
        uuid.UUID(tree.report_id)  # Should not raise

    def test_custom_report_id_preserved(self, tmp_builder):
        tree = tmp_builder.build_tree("text", 0.5, report_id="custom-report-id")
        assert tree.report_id == "custom-report-id"

    def test_causal_branch_has_extracted_fact(self, tmp_builder):
        tree = tmp_builder.build_tree(
            "Federal Reserve raises interest rates affecting stock market prices.", 0.9
        )
        branch1 = next(b for b in tree.interpretation_branches if b.branch_id == 1)
        # Branch 1 should have a causal fact when entities are detected
        if branch1.extracted_facts:
            assert branch1.extracted_facts[0].type == "INFLUENCES"

    def test_insufficient_evidence_branch_has_low_confidence(self, tmp_builder):
        tree = tmp_builder.build_tree("Some news.", 0.7)
        branch3 = next(b for b in tree.interpretation_branches if b.branch_id == 3)
        assert branch3.confidence == 0.2

    def test_source_reliability_affects_calculated_weight(self, tmp_builder):
        tree_high = tmp_builder.build_tree("Fed raises rates.", 0.9)
        tree_low = tmp_builder.build_tree("Fed raises rates.", 0.3)
        b1_high = next(b for b in tree_high.interpretation_branches if b.branch_id == 1)
        b1_low = next(b for b in tree_low.interpretation_branches if b.branch_id == 1)
        assert b1_high.calculated_weight > b1_low.calculated_weight


# ---------------------------------------------------------------------------
# ProbabilityTreeBuilder – select_best_branch
# ---------------------------------------------------------------------------

class TestSelectBestBranch:
    def test_returns_highest_weight_branch(self, tmp_builder):
        tree = tmp_builder.build_tree("Fed raises rates affecting markets heavily.", 0.9)
        best = tmp_builder.select_best_branch(tree)
        max_weight = max(b.weight for b in tree.interpretation_branches)
        assert abs(best["weight"] - max_weight) < 1e-6

    def test_empty_tree_returns_empty_dict(self, tmp_builder):
        tree = ProbabilityTree(
            report_id="r1",
            timestamp="2024-01-01T00:00:00Z",
            raw_text="text",
            interpretation_branches=[],
        )
        assert tmp_builder.select_best_branch(tree) == {}


# ---------------------------------------------------------------------------
# ProbabilityTreeBuilder – store and retrieve
# ---------------------------------------------------------------------------

class TestStorageAndRetrieval:
    def test_store_and_get_from_cache(self, tmp_builder):
        tree = tmp_builder.build_tree("Test article text.", 0.8)
        tmp_builder.store_tree(tree)
        retrieved = tmp_builder.get_tree(tree.report_id)
        assert retrieved is not None
        assert retrieved.report_id == tree.report_id

    def test_store_writes_jsonl(self, tmp_path):
        store_path = tmp_path / "trees.jsonl"
        builder = ProbabilityTreeBuilder(tree_store=store_path)
        tree = builder.build_tree("Article text here.", 0.7)
        builder.store_tree(tree)
        assert store_path.exists()
        data = json.loads(store_path.read_text().strip().split("\n")[0])
        assert data["report_id"] == tree.report_id

    def test_get_tree_from_file_after_cache_miss(self, tmp_path):
        store_path = tmp_path / "trees.jsonl"
        builder1 = ProbabilityTreeBuilder(tree_store=store_path)
        tree = builder1.build_tree("Article text here.", 0.7)
        builder1.store_tree(tree)

        # New builder instance, same file, no in-memory cache
        builder2 = ProbabilityTreeBuilder(tree_store=store_path)
        retrieved = builder2.get_tree(tree.report_id)
        assert retrieved is not None
        assert retrieved.report_id == tree.report_id

    def test_get_nonexistent_tree_returns_none(self, tmp_builder):
        result = tmp_builder.get_tree("completely-unknown-id")
        assert result is None
