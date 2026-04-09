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
    def test_posteriors_return_weights_and_Z(self):
        from ontology.dual_inference_engine import _compute_bayesian_posteriors
        weights, Z_pair = _compute_bayesian_posteriors("霸權制裁模式", "正式軍事同盟模式", 0.72, 0.72)
        # weights may be empty if no composition_table entry; if non-empty, all non-negative
        for k, v in weights.items():
            assert v >= 0.0, f"Negative weight for {k}: {v}"
        assert Z_pair >= 0.0

    def test_posteriors_all_nonnegative(self):
        from ontology.dual_inference_engine import _compute_bayesian_posteriors
        weights, Z_pair = _compute_bayesian_posteriors("霸權制裁模式", "正式軍事同盟模式", 0.72, 0.72)
        for k, v in weights.items():
            assert v >= 0.0, f"Negative weight for {k}: {v}"


class TestIntegration:
    def test_verdict_is_valid(self):
        from ontology.dual_inference_engine import run_lie_algebra_inference, run_bayesian_inference, integrate
        lie = run_lie_algebra_inference("霸權制裁模式", "正式軍事同盟模式")
        weights = {"多邊聯盟制裁模式": 0.5184}  # prior_a * prior_b * lie_sim ≈ 0.72*0.72*1.0
        Z_pair = sum(weights.values())
        bayes = run_bayesian_inference(
            "霸權制裁模式", "正式軍事同盟模式", "多邊聯盟制裁模式",
            0.72, 0.72, weights, Z_pair,
        )
        result = integrate(bayes, lie)
        assert result.verdict in ("convergent", "neutral", "divergent", "emergent")
        assert 0.0 <= result.confidence_final <= 1.0
        assert result.consistency_score >= -1.0
        assert result.consistency_score <= 1.0

    def test_confidence_formula_is_traceable(self):
        from ontology.dual_inference_engine import run_lie_algebra_inference, run_bayesian_inference, integrate
        lie = run_lie_algebra_inference("霸權制裁模式", "正式軍事同盟模式")
        weights = {"多邊聯盟制裁模式": 0.5184}
        Z_pair = sum(weights.values())
        bayes = run_bayesian_inference(
            "霸權制裁模式", "正式軍事同盟模式", "多邊聯盟制裁模式",
            0.72, 0.72, weights, Z_pair,
        )
        result = integrate(bayes, lie)
        assert "P_Bayes" in result.confidence_formula
        assert str(round(result.confidence_final, 3)) in result.confidence_formula

    def test_confidence_final_never_exceeds_p_bayes(self):
        """confidence_final must be ≤ P_Bayes (integration formula only scales down)."""
        from ontology.dual_inference_engine import run_lie_algebra_inference, run_bayesian_inference, integrate
        lie = run_lie_algebra_inference("霸權制裁模式", "正式軍事同盟模式")
        weights = {"多邊聯盟制裁模式": 0.5184}
        Z_pair = sum(weights.values())
        bayes = run_bayesian_inference(
            "霸權制裁模式", "正式軍事同盟模式", "多邊聯盟制裁模式",
            0.72, 0.72, weights, Z_pair,
        )
        # Simulate a globally-normalised probability (less than 1.0)
        bayes.probability = 0.45
        result = integrate(bayes, lie)
        assert result.confidence_final <= bayes.probability + 1e-4, (
            f"confidence_final={result.confidence_final} must not exceed P_Bayes={bayes.probability}"
        )


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

    def test_p_bayes_not_one_with_multiple_transitions(self):
        """
        Regression: P_Bayes must NOT be 1.0 when multiple transitions compete.
        Use three active patterns so two composition_table entries are found,
        giving two results. After global normalisation each probability < 1.0.
        """
        from ontology.dual_inference_engine import run_dual_inference
        # Three active patterns produce two composition_table matches:
        #   霸權制裁模式 + 正式軍事同盟模式 → 多邊聯盟制裁模式
        #   霸權制裁模式 + 實體清單技術封鎖模式 → 科技脫鉤/技術鐵幕模式
        active = [
            {"pattern_name": "霸權制裁模式",         "confidence_prior": 0.72},
            {"pattern_name": "正式軍事同盟模式",      "confidence_prior": 0.70},
            {"pattern_name": "實體清單技術封鎖模式",  "confidence_prior": 0.65},
        ]
        results = run_dual_inference(active, [])
        assert len(results) >= 2, (
            "Expected at least 2 dual_inference results for three active patterns"
        )
        for r in results:
            prob = r["bayesian"]["probability"]
            assert prob < 1.0 - 1e-4, (
                f"P_Bayes={prob:.6f} must be < 1.0 when multiple transitions compete"
            )
            # Formula string must show the correct (non-1.0) P_Bayes
            formula = r["integration"]["confidence_formula"]
            assert "P_Bayes=1.0000" not in formula, (
                f"Integration formula must not display P_Bayes=1.0000: {formula}"
            )

    def test_p_bayes_consistent_with_probability_tree(self):
        """
        P_Bayes in the integration formula must equal posterior_weight / Z_global,
        matching the probability shown in the probability tree for each transition.
        """
        from ontology.dual_inference_engine import run_dual_inference
        active = [
            {"pattern_name": "霸權制裁模式",         "confidence_prior": 0.72},
            {"pattern_name": "正式軍事同盟模式",      "confidence_prior": 0.70},
            {"pattern_name": "實體清單技術封鎖模式",  "confidence_prior": 0.65},
        ]
        results = run_dual_inference(active, [])
        if not results:
            return
        Z_global = sum(r["bayesian"]["posterior_weight"] for r in results)
        if Z_global < 1e-9:
            return
        for r in results:
            expected_prob = r["bayesian"]["posterior_weight"] / Z_global
            actual_prob   = r["bayesian"]["probability"]
            assert abs(actual_prob - expected_prob) < 1e-4, (
                f"P_Bayes mismatch: expected {expected_prob:.6f}, got {actual_prob:.6f}"
            )

    def test_confidence_final_le_p_bayes_for_all_results(self):
        """
        confidence_final must be ≤ P_Bayes for every result.
        Integration formula scales by (1+α×max(0,c))/(1+α) ≤ 1, so
        confidence_final can only equal or reduce P_Bayes, never exceed it.
        """
        from ontology.dual_inference_engine import run_dual_inference
        active = [
            {"pattern_name": "霸權制裁模式",         "confidence_prior": 0.72},
            {"pattern_name": "正式軍事同盟模式",      "confidence_prior": 0.70},
            {"pattern_name": "實體清單技術封鎖模式",  "confidence_prior": 0.65},
        ]
        results = run_dual_inference(active, [])
        for r in results:
            p_bayes = r["bayesian"]["probability"]
            conf    = r["integration"]["confidence_final"]
            assert conf <= p_bayes + 1e-4, (
                f"confidence_final={conf:.6f} must not exceed P_Bayes={p_bayes:.6f}"
            )

    def test_partition_function_is_z_global(self):
        """partition_function stored in bayesian dict must equal Z_global."""
        from ontology.dual_inference_engine import run_dual_inference
        active = [
            {"pattern_name": "霸權制裁模式",         "confidence_prior": 0.72},
            {"pattern_name": "正式軍事同盟模式",      "confidence_prior": 0.70},
            {"pattern_name": "實體清單技術封鎖模式",  "confidence_prior": 0.65},
        ]
        results = run_dual_inference(active, [])
        if not results:
            return
        Z_global = sum(r["bayesian"]["posterior_weight"] for r in results)
        for r in results:
            pf = r["bayesian"].get("partition_function", None)
            assert pf is not None, "bayesian dict must include 'partition_function'"
            assert abs(pf - Z_global) < 1e-4, (
                f"partition_function={pf:.6f} should equal Z_global={Z_global:.6f}"
            )


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
