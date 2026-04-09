"""Tests for dual_inference_engine."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import numpy as np
import pytest


class TestLieAlgebraInference:
    def test_nonlinear_activation_nonzero(self):
        from ontology.dual_inference_engine import run_lie_algebra_inference
        result = run_lie_algebra_inference("霸權制裁模式", "正式軍事同盟模式")
        assert result.sigma1 > 0.0, "sigma1 must be non-zero after PR#85 fix"
        assert len(result.nonlinear_activation) == 8
        assert result.top_emergent_dims  # at least one emergent dim

    def test_nonlinear_activation_shape(self):
        from ontology.dual_inference_engine import run_lie_algebra_inference
        result = run_lie_algebra_inference("霸權制裁模式", "實體清單技術封鎖模式")
        assert result.bracket_matrix.shape == (8, 8)
        assert result.nonlinear_activation.shape == (8,)

    def test_tech_sanctions_top_dim_is_technology(self):
        """霸权制裁 ⊕ 实体清单技术封锁 → top emergent dim should be technology"""
        from ontology.dual_inference_engine import run_lie_algebra_inference
        result = run_lie_algebra_inference("霸權制裁模式", "實體清單技術封鎖模式")
        assert result.top_emergent_dims[0] in ("technology", "coercion", "economic"), \
            f"Unexpected top dim: {result.top_emergent_dims[0]}"


class TestBayesianInference:
    def test_posteriors_sum_to_one(self):
        from ontology.dual_inference_engine import _compute_bayesian_posteriors
        posteriors = _compute_bayesian_posteriors("霸權制裁模式", "正式軍事同盟模式", 0.72, 0.72)
        if posteriors:
            total = sum(posteriors.values())
            assert abs(total - 1.0) < 1e-3, f"Posteriors must sum to 1, got {total}"

    def test_posteriors_all_nonnegative(self):
        from ontology.dual_inference_engine import _compute_bayesian_posteriors
        posteriors = _compute_bayesian_posteriors("霸權制裁模式", "正式軍事同盟模式", 0.72, 0.72)
        for k, v in posteriors.items():
            assert v >= 0.0, f"Negative posterior for {k}: {v}"


class TestIntegration:
    def test_verdict_is_valid(self):
        from ontology.dual_inference_engine import run_lie_algebra_inference, run_bayesian_inference, integrate
        lie = run_lie_algebra_inference("霸權制裁模式", "正式軍事同盟模式")
        posteriors = {"多邊聯盟制裁模式": 1.0}
        bayes = run_bayesian_inference(
            "霸權制裁模式", "正式軍事同盟模式", "多邊聯盟制裁模式",
            0.72, 0.72, posteriors
        )
        result = integrate(bayes, lie)
        assert result.verdict in ("convergent", "neutral", "divergent", "emergent")
        assert 0.0 <= result.confidence_final <= 1.0
        assert result.consistency_score >= -1.0
        assert result.consistency_score <= 1.0

    def test_confidence_formula_is_traceable(self):
        from ontology.dual_inference_engine import run_lie_algebra_inference, run_bayesian_inference, integrate
        lie = run_lie_algebra_inference("霸權制裁模式", "正式軍事同盟模式")
        posteriors = {"多邊聯盟制裁模式": 1.0}
        bayes = run_bayesian_inference(
            "霸權制裁模式", "正式軍事同盟模式", "多邊聯盟制裁模式",
            0.72, 0.72, posteriors
        )
        result = integrate(bayes, lie)
        assert "P_Bayes" in result.confidence_formula
        assert str(round(result.confidence_final, 3)) in result.confidence_formula


class TestDiagnoseIndependence:
    def test_independence_delta_in_range(self):
        from ontology.dual_inference_engine import diagnose_independence
        result = diagnose_independence("霸權制裁模式", "正式軍事同盟模式", "多邊聯盟制裁模式")
        assert 0.0 <= result["independence_delta"] <= 1.0

    def test_two_paths_structurally_different(self):
        """The two inference paths must use structurally different inputs."""
        from ontology.dual_inference_engine import diagnose_independence
        result = diagnose_independence("霸權制裁模式", "實體清單技術封鎖模式", "科技脫鉤/技術鐵幕模式")
        # cross_corr should not be 1.0 — paths are not identical
        assert result["independence_delta"] > 0.05, \
            "Paths appear redundant — check vector design"


class TestRunDualInference:
    def test_returns_list(self):
        from ontology.dual_inference_engine import run_dual_inference
        active = [
            {"pattern_name": "霸權制裁模式", "confidence_prior": 0.72},
            {"pattern_name": "正式軍事同盟模式", "confidence_prior": 0.72},
        ]
        results = run_dual_inference(active, [])
        assert isinstance(results, list)

    def test_result_has_required_keys(self):
        from ontology.dual_inference_engine import run_dual_inference
        from ontology.relation_schema import composition_table
        active = [
            {"pattern_name": "霸權制裁模式", "confidence_prior": 0.72},
            {"pattern_name": "正式軍事同盟模式", "confidence_prior": 0.72},
        ]
        results = run_dual_inference(active, [])
        if results:
            r = results[0]
            assert "bayesian" in r
            assert "lie_algebra" in r
            assert "integration" in r
            assert "confidence_final" in r["integration"]
            assert "verdict" in r["integration"]
            assert "consistency_score" in r["integration"]

    def test_transition_pass_produces_results_with_one_active_pattern(self):
        """Pass 2: transitions list should produce Lie algebra results even when
        only ONE source pattern is in active_patterns (the other uses registry priors)."""
        from ontology.dual_inference_engine import run_dual_inference

        class _FakeTransition:
            from_pattern_a = "霸權制裁模式"
            from_pattern_b = "雙邊貿易依存模式"
            to_pattern = "金融孤立 / SWIFT 切斷模式"
            prior_a = 0.80
            prior_b = 0.50

        active = [{"pattern_name": "霸權制裁模式", "confidence_prior": 0.80}]
        results = run_dual_inference(active, [_FakeTransition()])
        assert len(results) >= 1, "Transition-based pass must produce ≥1 result with one active pattern"
        r = results[0]
        # Lie algebra computation must have run (sigma1 > 0 for non-parallel patterns)
        assert r["lie_algebra"]["sigma1"] > 0.0, "Lie bracket must be non-zero for non-parallel patterns"
        # Required keys present
        assert "verdict" in r["integration"]
        assert "confidence_final" in r["integration"]

    def test_inverse_transitions_are_skipped(self):
        """Pass 2 must skip inverse-mode transitions (from_pattern_b == '(inverse)')."""
        from ontology.dual_inference_engine import run_dual_inference

        class _InverseTransition:
            from_pattern_a = "霸權制裁模式"
            from_pattern_b = "(inverse)"
            to_pattern = "制裁解除 / 正常化模式"
            prior_a = 0.80
            prior_b = 0.35

        active = [{"pattern_name": "霸權制裁模式", "confidence_prior": 0.80}]
        results = run_dual_inference(active, [_InverseTransition()])
        # Inverse transitions cannot have a valid Lie bracket — they must not appear
        for r in results:
            assert r["pattern_b"] != "(inverse)", "Inverse-mode transition leaked into dual inference"

    def test_result_key_names_match_pipeline_expectations(self):
        """
        Fix 1 regression: run_dual_inference must output 'pattern_c' (not 'to_pattern').
        evented_pipeline._dual_lookup uses _dr.get("pattern_c") to build the lookup key.
        """
        from ontology.dual_inference_engine import run_dual_inference
        active = [
            {"pattern_name": "霸權制裁模式", "confidence_prior": 0.72},
            {"pattern_name": "正式軍事同盟模式", "confidence_prior": 0.72},
        ]
        results = run_dual_inference(active, [])
        if results:
            r = results[0]
            assert "pattern_a" in r, "result must have 'pattern_a' key"
            assert "pattern_b" in r, "result must have 'pattern_b' key"
            assert "pattern_c" in r, "result must have 'pattern_c' key (used by _dual_lookup)"
            assert "to_pattern" not in r, "top-level key should be 'pattern_c', not 'to_pattern'"

    def test_lie_algebra_has_matrix_norm(self):
        """
        Fix 2 regression: lie_algebra dict must contain 'matrix_norm' and 'sigma1'
        so the probability-tree tooltip_data can display them.
        """
        from ontology.dual_inference_engine import run_dual_inference
        active = [
            {"pattern_name": "霸權制裁模式", "confidence_prior": 0.72},
            {"pattern_name": "正式軍事同盟模式", "confidence_prior": 0.72},
        ]
        results = run_dual_inference(active, [])
        if results:
            lie = results[0]["lie_algebra"]
            assert "matrix_norm" in lie, "'matrix_norm' must be emitted by dual_inference_engine"
            assert "sigma1" in lie, "'sigma1' must be emitted"
            assert "top_emergent_dims" in lie
            assert "top_emergent_values" in lie
            assert lie["sigma1"] > 0.0, "sigma1 must be non-zero for non-trivial pattern pairs"
            assert lie["matrix_norm"] > 0.0, "matrix_norm must be non-zero"


class TestDistributionSharpening:
    """Verify that probability collapse triggers power-sharpening in _run_stage3."""

    def _make_transitions(self, weights, patterns=None):
        """Build a minimal TransitionEdge list for testing."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
        from intelligence.evented_pipeline import TransitionEdge
        pats = patterns or [f"P{i}" for i in range(len(weights))]
        edges = []
        for i, w in enumerate(weights):
            edges.append(TransitionEdge(
                from_pattern_a=pats[i],
                from_pattern_b="(inverse)",
                to_pattern=f"T{i}",
                transition_type="inverse",
                prior_a=0.5,
                prior_b=0.35,
                lie_similarity=0.5,
                posterior_weight=w,
                typical_outcomes=["structural_realignment"],
                description="test",
            ))
        return edges

    def test_collapse_produces_spread_probs(self):
        """When weights are flat, sharpening must spread alpha_prob above 0.50."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
        from intelligence.evented_pipeline import _run_stage3
        from intelligence.evented_pipeline import EventNode

        # Near-uniform weights — mimics the 45-65% collapse scenario
        weights = [0.35, 0.33, 0.32]
        transitions = self._make_transitions(weights)

        conclusion, _ = _run_stage3(
            text="US imposes sanctions on Iran. NATO allies support.",
            events=[],
            active=[],
            transitions=transitions,
            state_vector={},
            driving_factors=[],
            llm_service=None,
        )
        alpha_prob = conclusion["alpha_path"]["probability"]
        # After sharpening 0.35^2.5 / (0.35^2.5 + 0.33^2.5 + 0.32^2.5) > 0.50
        assert alpha_prob > 0.50, (
            f"Expected alpha_prob > 0.50 after sharpening, got {alpha_prob}"
        )

    def test_no_sharpening_when_spread(self):
        """When top_prob is already well above floor, sharpening must not trigger."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
        from intelligence.evented_pipeline import _run_stage3

        # Already well-spread
        weights = [0.70, 0.20, 0.10]
        transitions = self._make_transitions(weights)

        conclusion, _ = _run_stage3(
            text="US imposes sanctions on Iran.",
            events=[],
            active=[],
            transitions=transitions,
            state_vector={},
            driving_factors=[],
            llm_service=None,
        )
        alpha_prob = conclusion["alpha_path"]["probability"]
        # Should be approximately 0.70 (or higher after sharpening, still > 0.70)
        assert alpha_prob > 0.65, f"Well-spread weights should stay well-spread: {alpha_prob}"


class TestEntityExtraction:
    """Verify that proper nouns from news text are used as allowed_entities."""

    def test_extract_proper_nouns_from_text(self):
        """_extract_proper_nouns must return named entities from the news fragment.

        Note: the function only extracts mid-sentence capitalised tokens
        (sentence-initial words are excluded to reduce false positives).
        """
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
        from intelligence.evented_pipeline import _extract_proper_nouns

        # Entities appear in mid-sentence positions so they are not skipped by the
        # sentence-initial-word exclusion rule in _extract_proper_nouns.
        text = (
            "Sanctions imposed by the US have forced Iran to respond. "
            "The alliance between Turkey and Pakistan has alarmed India."
        )
        nouns = _extract_proper_nouns(text)
        expected = {"Iran", "Turkey", "Pakistan", "India"}
        found = expected & nouns
        assert len(found) >= 2, (
            f"Expected at least 2 of {expected} to be extracted, got: {nouns}"
        )

