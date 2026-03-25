"""
Unit tests for the Sacred Sword Analyzer
=========================================

Tests cover:
1. Fact extraction: known vs unknown entities, max-5 cap
2. Conflict detection: CONSISTENT / CONFLICT fallback
3. Branch generation: Alpha/Beta names, fixed probabilities
4. Confidence calculation: formula, conflict penalty
5. Data-gap and counter-argument: fallback text when LLM unavailable
6. Full analyze() integration
"""

from __future__ import annotations

import sys
import os

import pytest

_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
sys.path.insert(0, os.path.abspath(_BACKEND_DIR))

from intelligence.sacred_sword_analyzer import (
    Branch,
    ConflictStatus,
    Fact,
    SacredSwordAnalyzer,
    SacredSwordAnalysis,
    _ALPHA_PROBABILITY,
    _BETA_PROBABILITY,
    _CONFIDENCE_THRESHOLD,
    _CONFLICT_PENALTY,
    _KNOWN_ENTITY_CONFIDENCE,
    _MAX_FACTS,
    _UNKNOWN_ENTITY_CONFIDENCE,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def analyzer() -> SacredSwordAnalyzer:
    """Analyzer with no LLM (settings=None → deterministic fallbacks)."""
    return SacredSwordAnalyzer(settings=None)


@pytest.fixture()
def graph_with_fed() -> dict:
    return {"entities": [{"name": "Federal Reserve"}, {"name": "Stock Market"}]}


@pytest.fixture()
def news_with_fed() -> list:
    return [
        "Federal Reserve announced a 0.5% interest rate hike.",
        "Stock Market declined 3% following the rate announcement.",
        "Unknown Entity XYZ made an unverified statement.",  # unknown entity → rejected
    ]


# ---------------------------------------------------------------------------
# Fact extraction
# ---------------------------------------------------------------------------

class TestExtractCoreFacts:
    def test_known_entity_gets_high_confidence(self, analyzer, graph_with_fed, news_with_fed):
        facts = analyzer._extract_core_facts(news_with_fed, graph_with_fed)
        assert all(f.confidence == _KNOWN_ENTITY_CONFIDENCE for f in facts)

    def test_unknown_entity_fragment_is_rejected(self, analyzer, graph_with_fed, news_with_fed):
        facts = analyzer._extract_core_facts(news_with_fed, graph_with_fed)
        statements = [f.statement for f in facts]
        assert all("Unknown Entity XYZ" not in s for s in statements)

    def test_max_five_facts_returned(self, analyzer):
        graph = {"entities": [{"name": "Alpha"}]}
        news = [f"Alpha news fragment {i}." for i in range(10)]
        facts = analyzer._extract_core_facts(news, graph)
        assert len(facts) <= _MAX_FACTS

    def test_empty_news_returns_no_facts(self, analyzer, graph_with_fed):
        facts = analyzer._extract_core_facts([], graph_with_fed)
        assert facts == []

    def test_source_label_truncated(self, analyzer, graph_with_fed):
        long_fragment = "Federal Reserve " + "x" * 100
        facts = analyzer._extract_core_facts([long_fragment], graph_with_fed)
        assert len(facts) == 1
        assert facts[0].source.endswith("…")

    def test_graph_nodes_key_also_recognised(self, analyzer):
        graph = {"nodes": [{"name": "Tesla"}]}
        news = ["Tesla stock surged 10% today."]
        facts = analyzer._extract_core_facts(news, graph)
        assert len(facts) == 1
        assert facts[0].confidence == _KNOWN_ENTITY_CONFIDENCE

    def test_graph_entity_as_plain_string(self, analyzer):
        graph = {"entities": ["Apple"]}
        news = ["Apple released a new product line."]
        facts = analyzer._extract_core_facts(news, graph)
        assert len(facts) == 1

    def test_all_unknown_entities_yields_no_facts(self, analyzer):
        graph = {"entities": []}
        news = ["Random unknown entity said something vague."]
        facts = analyzer._extract_core_facts(news, graph)
        assert facts == []


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

class TestDetectConflict:
    def test_returns_consistent_when_no_llm(self, analyzer):
        facts = [Fact("A is true.", "src", 0.95)]
        result = analyzer._detect_conflict(facts)
        assert result == ConflictStatus.CONSISTENT

    def test_returns_consistent_for_empty_facts(self, analyzer):
        assert analyzer._detect_conflict([]) == ConflictStatus.CONSISTENT

    def test_conflict_status_values(self):
        assert ConflictStatus.CONSISTENT.value == "CONSISTENT"
        assert ConflictStatus.CONFLICT.value == "CONFLICT"


# ---------------------------------------------------------------------------
# Branch generation
# ---------------------------------------------------------------------------

class TestBranchGeneration:
    def test_alpha_branch_name_and_probability(self, analyzer):
        facts = [Fact("Inflation rose.", "src", 0.95)]
        alpha = analyzer._generate_alpha_branch(facts, "inflation impact")
        assert alpha.name == "Alpha"
        assert alpha.probability == _ALPHA_PROBABILITY

    def test_beta_branch_name_and_probability(self, analyzer):
        facts = [Fact("Inflation rose.", "src", 0.95)]
        alpha = analyzer._generate_alpha_branch(facts, "inflation impact")
        beta = analyzer._generate_beta_branch(facts, "inflation impact", alpha)
        assert beta.name == "Beta"
        assert beta.probability == _BETA_PROBABILITY

    def test_alpha_key_assumption(self, analyzer):
        facts = [Fact("Rates rose.", "src", 0.95)]
        alpha = analyzer._generate_alpha_branch(facts, "rate impact")
        assert alpha.key_assumption == "Current trends continue"

    def test_beta_key_assumption(self, analyzer):
        facts = [Fact("Rates rose.", "src", 0.95)]
        alpha = analyzer._generate_alpha_branch(facts, "rate impact")
        beta = analyzer._generate_beta_branch(facts, "rate impact", alpha)
        assert beta.key_assumption == "Key assumption fails"

    def test_alpha_description_is_non_empty(self, analyzer):
        facts = [Fact("GDP grew.", "src", 0.95)]
        alpha = analyzer._generate_alpha_branch(facts, "economic growth")
        assert alpha.description

    def test_beta_description_is_non_empty(self, analyzer):
        facts = [Fact("GDP grew.", "src", 0.95)]
        alpha = analyzer._generate_alpha_branch(facts, "economic growth")
        beta = analyzer._generate_beta_branch(facts, "economic growth", alpha)
        assert beta.description


# ---------------------------------------------------------------------------
# Confidence calculation
# ---------------------------------------------------------------------------

class TestCalculateConfidence:
    def test_consistent_no_penalty(self, analyzer):
        facts = [Fact("A.", "s", 0.95), Fact("B.", "s", 0.95)]
        score = analyzer._calculate_confidence(facts, ConflictStatus.CONSISTENT)
        assert abs(score - 0.95) < 1e-4

    def test_conflict_applies_penalty(self, analyzer):
        facts = [Fact("A.", "s", 0.95), Fact("B.", "s", 0.95)]
        score = analyzer._calculate_confidence(facts, ConflictStatus.CONFLICT)
        assert abs(score - (0.95 - _CONFLICT_PENALTY)) < 1e-4

    def test_empty_facts_returns_zero(self, analyzer):
        assert analyzer._calculate_confidence([], ConflictStatus.CONSISTENT) == 0.0

    def test_score_clamped_to_zero_on_heavy_penalty(self, analyzer):
        facts = [Fact("A.", "s", 0.1)]  # very low confidence
        score = analyzer._calculate_confidence(facts, ConflictStatus.CONFLICT)
        assert score >= 0.0

    def test_score_not_above_one(self, analyzer):
        facts = [Fact("A.", "s", 1.0)]
        score = analyzer._calculate_confidence(facts, ConflictStatus.CONSISTENT)
        assert score <= 1.0


# ---------------------------------------------------------------------------
# Data gap & counter-argument fallbacks
# ---------------------------------------------------------------------------

class TestSelfAudit:
    def test_data_gap_non_empty_without_llm(self, analyzer):
        facts = [Fact("Rates rose.", "s", 0.95)]
        gap = analyzer._identify_one_critical_gap(facts, "rate impact")
        assert isinstance(gap, str) and gap

    def test_counter_arg_non_empty_without_llm(self, analyzer):
        facts = [Fact("Rates rose.", "s", 0.95)]
        arg = analyzer._find_strongest_counter_arg(facts, "rate impact")
        assert isinstance(arg, str) and arg


# ---------------------------------------------------------------------------
# Full integration
# ---------------------------------------------------------------------------

class TestAnalyzeIntegration:
    def test_returns_sacred_sword_analysis_type(self, analyzer, graph_with_fed, news_with_fed):
        result = analyzer.analyze(news_with_fed, graph_with_fed, "rate hike impact on housing")
        assert isinstance(result, SacredSwordAnalysis)

    def test_facts_capped_at_five(self, analyzer):
        graph = {"entities": [{"name": "Fed"}]}
        news = [f"Fed action {i}." for i in range(10)]
        result = analyzer.analyze(news, graph, "Fed policy")
        assert len(result.facts) <= _MAX_FACTS

    def test_alpha_beta_probabilities_sum_to_one(self, analyzer, graph_with_fed, news_with_fed):
        result = analyzer.analyze(news_with_fed, graph_with_fed, "rate hike impact")
        total = result.alpha.probability + result.beta.probability
        assert abs(total - 1.0) < 1e-6

    def test_conflict_is_consistent_without_llm(self, analyzer, graph_with_fed, news_with_fed):
        result = analyzer.analyze(news_with_fed, graph_with_fed, "rate hike impact")
        assert result.conflict == ConflictStatus.CONSISTENT

    def test_confidence_score_in_range(self, analyzer, graph_with_fed, news_with_fed):
        result = analyzer.analyze(news_with_fed, graph_with_fed, "rate hike impact")
        assert 0.0 <= result.confidence_score <= 1.0

    def test_empty_news_still_returns_analysis(self, analyzer, graph_with_fed):
        result = analyzer.analyze([], graph_with_fed, "empty news claim")
        assert isinstance(result, SacredSwordAnalysis)
        assert result.facts == []
        assert result.confidence_score == 0.0

    def test_empty_graph_context_still_works(self, analyzer):
        news = ["Some news fragment without known entities."]
        result = analyzer.analyze(news, {}, "test claim")
        assert isinstance(result, SacredSwordAnalysis)
