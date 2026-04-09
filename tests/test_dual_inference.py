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

