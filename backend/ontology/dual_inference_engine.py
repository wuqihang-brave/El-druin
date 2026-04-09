"""
ontology/dual_inference_engine.py
===================================
Dual Inference Engine: Bayesian Path ∥ Lie Algebra Path

Design Philosophy
-----------------
Two mathematically distinct inference problems exist in ontological reasoning:

  Problem A (Bayesian Path):
    Given the current activated pattern set {A, B, ...},
    which target pattern C is most likely to be activated next
    under historical priors and structural rules?
    → Output: P_Bayes(C) ∈ [0,1] discrete probability distribution over S

  Problem B (Lie Algebra Path):
    Given two simultaneously activated patterns A and B,
    in which semantic dimensions does their interaction produce
    non-linear emergence effects?
    → Output: nonlinear_activation[d] ∈ ℝ⁸ emergence intensity vector

These are two independent inference problems answering different things.

Incorrect integration:
  ✗ Multiply bracket norm ‖[X_A,X_B]‖_F by Bayesian probability (loses info)
  ✗ Project row-norm vector to nearest neighbor as "prediction" (category error)

Correct integration (ensemble layer):
  - Each path produces independent output
  - Integration layer detects consistency (convergence) or conflict (divergence)
  - Convergent → high confidence, converging prediction
  - Divergent → bifurcation point detected, confidence reduced, expose diverging dims
  - Lie algebra signal only → emergent effect not captured by ontology library

Mathematical Foundation
-----------------------
Lie algebra path row-norm vector:
  C = [X_A, X_B] = X_A @ X_B - X_B @ X_A    (8×8 antisymmetric matrix)
  nonlinear_activation[i] = ‖C[i, :]‖₂       (L2 norm of row i)

Physical meaning: C[i,j] measures non-linear interference intensity of dim i on dim j.
Row norm ‖C[i,:]‖₂ is total activation intensity of dimension i in the non-linear field.
This is a structural signal from Lie algebra embedding, independent of priors.

Consistency measure:
  consistency(A,B,C) = cos(nonlinear_activation, v_C)
  Range [-1, 1]:
    +1 → two paths fully aligned
    0  → paths orthogonal (complementary, not contradictory)
    -1 → paths opposed (bifurcation signal)

Integrated confidence (replaces hallucinated values):
  confidence_final = P_Bayes(C*) × (1 + α × max(0, consistency)) / (1 + α)
  where α = 0.3 (integration coefficient)
  When consistency = +1: confidence increases by at most α/(1+α) ≈ 23%
  When consistency = -1: confidence decreases, bifurcation flag triggered
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from ontology.lie_algebra_space import _vec, hat, _commutator, SEMANTIC_DIMS

logger = logging.getLogger(__name__)

_ALPHA = 0.30
_EMERGENCE_THRESHOLD = 2.5
_DIVERGENCE_THRESHOLD = 0.20


@dataclass
class BayesianInference:
    """Bayesian path output: transition probability distribution."""
    target_pattern:       str
    probability:          float
    posterior_weight:     float
    partition_function:   float
    prior_a:              float
    prior_b:              float
    lie_sim:              float   # cos(v_A + v_B, v_C) — additive similarity, NOT bracket
    evidence_basis:       str


@dataclass
class LieAlgebraInference:
    """
    Lie algebra path output: non-linear emergence intensity vector.

    This is NOT a probability. It is a diagnostic of which semantic
    dimensions are non-linearly activated by the A⊕B interaction.
    high activation[d] = dimension d has strong non-linear effect in A⊕B
    """
    nonlinear_activation: np.ndarray   # shape (8,)
    top_emergent_dims:    List[str]
    top_emergent_values:  List[float]
    bracket_matrix:       np.ndarray   # [X_A, X_B], shape (8,8)
    sigma1:               float
    pattern_a:            str
    pattern_b:            str
    superlinear_dims:     List[str] = field(default_factory=list)


@dataclass
class IntegrationResult:
    """
    Integration layer output: consistency analysis and final inference.
    This is the final inference conclusion exposed to the frontend.
    """
    bayesian:             BayesianInference
    lie_algebra:          LieAlgebraInference
    consistency_score:    float
    verdict:              str   # "convergent" | "divergent" | "emergent" | "neutral"
    confidence_final:     float
    confidence_formula:   str
    divergence_dims:      List[str]
    emergence_signal:     Optional[str]
    summary:              str


def _compute_bayesian_posteriors(
    pattern_a: str,
    pattern_b: str,
    prior_a: float,
    prior_b: float,
) -> tuple:
    """
    Compute unnormalized weights w(C) = π(A) × π(B) × cos(v_A + v_B, v_C)
    for all patterns C such that compose(A, B) = C is in composition_table.

    Returns (weights_dict, Z_pair) where:
      weights_dict: {C: w(C)} — unnormalized weights (not yet divided by Z)
      Z_pair: Σ_C w(C) for this (A, B) pair

    Callers that need a proper per-pair distribution should divide by Z_pair.
    Global normalization across all (A, B) pairs is done in run_dual_inference.
    If cos is negative (opposing direction), clip to 0 to ensure valid prob.
    """
    try:
        from ontology.relation_schema import composition_table
    except ImportError:
        return {}, 0.0

    v_a = _vec(pattern_a)
    v_b = _vec(pattern_b)
    v_sum = v_a + v_b
    n_sum = np.linalg.norm(v_sum)

    weights: Dict[str, float] = {}
    for (pa, pb), pc in composition_table.items():
        if pa != pattern_a or pb != pattern_b:
            continue
        v_c = _vec(pc)
        n_c = np.linalg.norm(v_c)
        if n_sum > 1e-9 and n_c > 1e-9:
            cos_sim = float(np.dot(v_sum / n_sum, v_c / n_c))
        else:
            cos_sim = 0.0
        w = prior_a * prior_b * max(0.0, cos_sim)
        weights[pc] = weights.get(pc, 0.0) + w

    Z_pair = sum(weights.values())
    return weights, Z_pair


def run_lie_algebra_inference(
    pattern_a: str,
    pattern_b: str,
) -> LieAlgebraInference:
    """
    Lie algebra path: compute the non-linear emergence intensity vector
    for the interaction of pattern_a and pattern_b.

    Returns nonlinear_activation[i] = ‖[X_A, X_B][i,:]‖₂ for each semantic dim i.
    """
    v_a = _vec(pattern_a)
    v_b = _vec(pattern_b)

    X_A = hat(v_a)  # shape (8, 8)
    X_B = hat(v_b)  # shape (8, 8)
    C = _commutator(X_A, X_B)  # [X_A, X_B], shape (8, 8)

    # Row norms → nonlinear activation per semantic dimension
    nonlinear_activation = np.array(
        [np.linalg.norm(C[i, :]) for i in range(len(SEMANTIC_DIMS))],
        dtype=float,
    )

    # First singular value of commutator matrix
    svd_vals = np.linalg.svd(C, compute_uv=False)
    sigma1 = float(svd_vals[0]) if len(svd_vals) > 0 else 0.0

    # Top emergent dimensions (sorted by activation magnitude)
    sorted_idx = np.argsort(nonlinear_activation)[::-1]
    top_emergent_dims = [
        SEMANTIC_DIMS[i] for i in sorted_idx if nonlinear_activation[i] > 0
    ][:3]
    top_emergent_values = [
        round(float(nonlinear_activation[i]), 4)
        for i in sorted_idx if nonlinear_activation[i] > 0
    ][:3]

    # Superlinear dimensions (activation above emergence threshold)
    superlinear_dims = [
        SEMANTIC_DIMS[i]
        for i in range(len(SEMANTIC_DIMS))
        if nonlinear_activation[i] > _EMERGENCE_THRESHOLD
    ]

    return LieAlgebraInference(
        nonlinear_activation=nonlinear_activation,
        top_emergent_dims=top_emergent_dims,
        top_emergent_values=top_emergent_values,
        bracket_matrix=C,
        sigma1=sigma1,
        pattern_a=pattern_a,
        pattern_b=pattern_b,
        superlinear_dims=superlinear_dims,
    )


def run_bayesian_inference(
    pattern_a: str,
    pattern_b: str,
    pattern_c: str,
    prior_a: float,
    prior_b: float,
    weights: Dict[str, float],
    Z_pair: float,
    Z_global: float = 0.0,
) -> BayesianInference:
    """
    Bayesian path: given unnormalized weights from _compute_bayesian_posteriors,
    compute the posterior probability for target pattern_c and its additive similarity.

    probability is initially set to w(C)/Z_pair (per-pair normalization) and is
    later updated to w(C)/Z_global by run_dual_inference for cross-pair consistency.

    partition_function stores Z_pair (true unnormalized weight sum for this pair).
    """
    v_a = _vec(pattern_a)
    v_b = _vec(pattern_b)
    v_c = _vec(pattern_c)
    v_sum = v_a + v_b

    n_sum = np.linalg.norm(v_sum)
    n_c = np.linalg.norm(v_c)

    if n_sum > 1e-9 and n_c > 1e-9:
        lie_sim = float(np.dot(v_sum / n_sum, v_c / n_c))
    else:
        lie_sim = 0.0

    posterior_weight = prior_a * prior_b * max(0.0, lie_sim)

    # Per-pair probability (w(C) / Z_pair): used as the initial estimate.
    # Will be overwritten by run_dual_inference with the global-normalised value.
    if Z_pair > 1e-9:
        probability = weights.get(pattern_c, 0.0) / Z_pair
    elif weights:
        # Fallback: uniform distribution over candidates in this pair
        probability = 1.0 / len(weights)
    else:
        probability = 0.0

    return BayesianInference(
        target_pattern=pattern_c,
        probability=round(probability, 6),
        posterior_weight=round(posterior_weight, 6),
        partition_function=round(Z_pair, 6),
        prior_a=prior_a,
        prior_b=prior_b,
        lie_sim=round(lie_sim, 4),
        evidence_basis=f"composition_table[({pattern_a}, {pattern_b})] = {pattern_c}",
    )


def integrate(
    bayes: BayesianInference,
    lie: LieAlgebraInference,
) -> IntegrationResult:
    """
    Integration layer: compute consistency between the two paths and
    produce a final confidence with a traceable formula.

    consistency = cos(nonlinear_activation, v_C)
    confidence_final = P_Bayes(C) × (1 + α × max(0, consistency)) / (1 + α)
    """
    v_c = _vec(bayes.target_pattern)
    na = lie.nonlinear_activation

    n_c = np.linalg.norm(v_c)
    n_na = np.linalg.norm(na)

    if n_c > 1e-9 and n_na > 1e-9:
        consistency_score = float(np.dot(na / n_na, v_c / n_c))
    else:
        consistency_score = 0.0

    # Integrated confidence formula
    raw_confidence = (
        bayes.probability
        * (1.0 + _ALPHA * max(0.0, consistency_score))
        / (1.0 + _ALPHA)
    )
    confidence_final = round(min(1.0, max(0.0, raw_confidence)), 4)

    # Verdict
    if consistency_score >= 0.5:
        verdict = "convergent"
    elif consistency_score <= -_DIVERGENCE_THRESHOLD:
        verdict = "divergent"
    elif n_na > _EMERGENCE_THRESHOLD:
        verdict = "emergent"
    else:
        verdict = "neutral"

    # Dimensions where the two paths conflict (negative dot product contribution)
    divergence_dims: List[str] = []
    if n_c > 1e-9 and n_na > 1e-9:
        for i in range(len(SEMANTIC_DIMS)):
            if (na[i] / n_na) * (v_c[i] / n_c) < -0.05:
                divergence_dims.append(SEMANTIC_DIMS[i])

    # Emergence signal from Lie algebra path
    emergence_signal: Optional[str] = None
    if lie.superlinear_dims:
        emergence_signal = f"Superlinear emergence in {', '.join(lie.superlinear_dims)}"

    confidence_formula = (
        f"P_Bayes={bayes.probability:.4f} × "
        f"(1 + {_ALPHA} × max(0, {consistency_score:.4f})) "
        f"/ (1 + {_ALPHA}) = {confidence_final:.3f}"
    )

    summary = (
        f"[{lie.pattern_a}]⊕[{lie.pattern_b}] → [{bayes.target_pattern}] "
        f"verdict={verdict} consistency={consistency_score:.3f} "
        f"confidence={confidence_final:.3f}"
    )

    return IntegrationResult(
        bayesian=bayes,
        lie_algebra=lie,
        consistency_score=round(consistency_score, 4),
        verdict=verdict,
        confidence_final=confidence_final,
        confidence_formula=confidence_formula,
        divergence_dims=divergence_dims,
        emergence_signal=emergence_signal,
        summary=summary,
    )


def run_dual_inference(
    active_patterns: List[Dict[str, Any]],
    transitions: List[Any],
) -> List[Dict[str, Any]]:
    """
    Run dual inference for all transition pairs that appear in the pipeline.

    Two-pass design:
      Pass 1 — composition_table pairs where BOTH patterns are active (full prior info).
      Pass 2 — TransitionEdge list (raw internal CJK keys) for single-active-pattern
               coverage.  Inverse transitions (from_pattern_b == "(inverse)") are
               skipped because they don't have a meaningful two-pattern Lie bracket.

    All pattern keys used here are raw internal CJK keys (never display labels).
    Translation to English happens only at the serialisation boundary in
    evented_pipeline.py.

    Args:
        active_patterns: list of dicts with "pattern_name" (raw CJK key) and
                         "confidence_prior" keys.
        transitions:     list of TransitionEdge objects from _run_stage2b, carrying
                         raw CJK keys in from_pattern_a / from_pattern_b / to_pattern.

    Returns:
        list of dicts with "pattern_a", "pattern_b", "pattern_c", "bayesian",
        "lie_algebra", "integration" keys, sorted by confidence_final descending.
    """
    try:
        from ontology.relation_schema import composition_table
    except ImportError:
        return []

    # Build prior lookup using raw internal CJK pattern keys
    pattern_priors: Dict[str, float] = {
        p["pattern_name"]: float(p.get("confidence_prior", 0.5))
        for p in active_patterns
        if "pattern_name" in p
    }

    results: List[Dict[str, Any]] = []
    processed: set = set()

    # ── Collect raw Bayesian + Lie results (no final integration yet) ─────────
    # We need all posterior_weights first to compute Z_global for proper normalization.
    raw_items: List[tuple] = []  # (pa, pb, pc, bayes, lie)

    def _collect(pa: str, pb: str, pc: str, prior_a: float, prior_b: float) -> None:
        """Compute raw Bayesian and Lie results; defer integration until Z_global is known."""
        try:
            weights, Z_pair = _compute_bayesian_posteriors(pa, pb, prior_a, prior_b)
            bayes = run_bayesian_inference(pa, pb, pc, prior_a, prior_b, weights, Z_pair)
            lie = run_lie_algebra_inference(pa, pb)
            raw_items.append((pa, pb, pc, bayes, lie))
        except Exception as exc:
            logger.warning(
                "run_dual_inference: error computing raw result for (%s, %s) → %s: %s",
                pa, pb, pc, exc,
            )

    # ── Pass 1: composition_table pairs where BOTH patterns are active ────────
    for (pa, pb), pc in composition_table.items():
        if pa not in pattern_priors or pb not in pattern_priors:
            continue
        key = (pa, pb, pc)
        if key in processed:
            continue
        processed.add(key)
        _collect(pa, pb, pc, pattern_priors[pa], pattern_priors[pb])

    # ── Pass 2: TransitionEdge list — cover single-active-pattern transitions ─
    # _run_stage2b emits edges where only ONE of (pa, pb) is active but a
    # composition_table entry exists.  Pass 1 skips those.  We handle them here
    # so that every edge in the probability tree gets a dual_inference entry,
    # making _dual_lookup in evented_pipeline resolve to a non-None match.
    # NOTE: All from_pattern_a / from_pattern_b / to_pattern values on a
    # TransitionEdge are raw internal CJK keys — no display_pattern() is called.
    for t in transitions:
        pa = getattr(t, "from_pattern_a", "")
        pb = getattr(t, "from_pattern_b", "")
        pc = getattr(t, "to_pattern", "")

        # Inverse transitions use a synthetic "(inverse)" marker for pb;
        # there is no meaningful two-pattern Lie bracket to compute.
        # Also skip entries where any key is missing/empty.
        if pb == "(inverse)" or not pa or not pc:
            continue

        key = (pa, pb, pc)
        if key in processed:
            continue
        processed.add(key)

        # Use whatever priors are available; default to 0.5 for non-active patterns
        prior_a = pattern_priors.get(pa, 0.5)
        prior_b = pattern_priors.get(pb, 0.5)
        _collect(pa, pb, pc, prior_a, prior_b)

    # ── Global normalisation: P_Bayes(C) = posterior_weight(C) / Z_global ────
    # Z_global = Σ posterior_weights across ALL collected (A, B, C) triples.
    # This ensures the displayed P_Bayes matches the probability tree (which
    # also normalises each transition weight against the global sum), and
    # prevents P_Bayes from incorrectly showing as 1.0 when the composition
    # table has only one C per (A, B) pair (which is the typical case).
    Z_global = sum(b.posterior_weight for _, _, _, b, _ in raw_items)
    if Z_global < 1e-9:
        Z_global = 1.0

    # ── Pass 3: update probability with global normalisation and integrate ────
    for pa, pb, pc, bayes, lie in raw_items:
        try:
            # Overwrite probability with globally normalised value
            bayes.probability = round(bayes.posterior_weight / Z_global, 6)
            # Store true global partition function so callers can verify normalisation
            bayes.partition_function = round(Z_global, 6)

            integration = integrate(bayes, lie)

            results.append({
                "pattern_a": pa,
                "pattern_b": pb,
                "pattern_c": pc,
                "bayesian": {
                    "target_pattern":    bayes.target_pattern,
                    "probability":       bayes.probability,
                    "posterior_weight":  bayes.posterior_weight,
                    "partition_function": bayes.partition_function,
                    "lie_sim":           bayes.lie_sim,
                    "evidence_basis":    bayes.evidence_basis,
                },
                "lie_algebra": {
                    "sigma1":             lie.sigma1,
                    "matrix_norm":        round(float(np.linalg.norm(lie.bracket_matrix, "fro")), 4),
                    "bracket_matrix":     lie.bracket_matrix.tolist(),
                    "top_emergent_dims":  lie.top_emergent_dims,
                    "top_emergent_values": lie.top_emergent_values,
                    "superlinear_dims":   lie.superlinear_dims,
                    "cosine_similarity":  round(bayes.lie_sim, 4),
                },
                "integration": {
                    "consistency_score":  integration.consistency_score,
                    "verdict":            integration.verdict,
                    "confidence_final":   integration.confidence_final,
                    "confidence_formula": integration.confidence_formula,
                    "divergence_dims":    integration.divergence_dims,
                    "emergence_signal":   integration.emergence_signal,
                    "summary":            integration.summary,
                },
            })
        except Exception as exc:
            logger.warning(
                "run_dual_inference: error integrating (%s, %s) → %s: %s", pa, pb, pc, exc
            )

    results.sort(key=lambda r: r["integration"]["confidence_final"], reverse=True)
    return results


def diagnose_independence(
    pattern_a: str,
    pattern_b: str,
    pattern_c: str,
) -> Dict[str, Any]:
    """
    Verify that the Bayesian and Lie algebra paths use structurally different inputs.

    The Bayesian path input is v_A + v_B (additive vector sum in ℝ⁸).
    The Lie algebra path input is nonlinear_activation from [X_A, X_B].
    independence_delta = 1 - |cos(v_sum, nonlinear_activation)|

    Near 0 = redundant paths; near 1 = maximally independent paths.
    """
    v_a = _vec(pattern_a)
    v_b = _vec(pattern_b)
    v_sum = v_a + v_b

    lie_inf = run_lie_algebra_inference(pattern_a, pattern_b)

    n_sum = np.linalg.norm(v_sum)
    v_sum_normed = v_sum / n_sum if n_sum > 1e-9 else v_sum

    na = lie_inf.nonlinear_activation
    n_na = np.linalg.norm(na)
    na_normed = na / n_na if n_na > 1e-9 else na

    # Cross-correlation between the two path inputs
    cross_corr = float(np.dot(v_sum_normed, na_normed))
    # independence_delta: how structurally different are the two paths' inputs
    # cross_corr near 0 = independent inputs; near 1 = redundant paths
    independence_delta = round(1.0 - abs(cross_corr), 4)

    return {
        "pattern_a":                pattern_a,
        "pattern_b":                pattern_b,
        "pattern_c":                pattern_c,
        "v_sum_norm":               round(float(n_sum), 4),
        "nonlinear_activation_norm": round(float(n_na), 4),
        "cross_correlation":        round(cross_corr, 4),
        "independence_delta":       independence_delta,
        "interpretation": (
            "paths are structurally independent"
            if independence_delta > 0.5
            else "paths partially share input structure"
        ),
    }
