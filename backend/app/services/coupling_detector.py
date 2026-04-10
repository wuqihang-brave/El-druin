"""
Coupling Detector
=================
Surfaces domain pairs with highest nonlinear coupling pressure.

coupling(d_i, d_j) = |C[d_i, d_j]| where C = [X_A, X_B] is the commutator
from the dual inference engine for the most recently activated pattern pair.

A pair is "amplifying" if coupling(d_i, d_j) > COUPLING_THRESHOLD (1.5).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.schemas.structural_forecast import CouplingOutput, CouplingPair

logger = logging.getLogger(__name__)

COUPLING_THRESHOLD: float = 1.5
_TOP_N = 3


def _amplification_label(coupling_strength: float) -> str:
    if coupling_strength > COUPLING_THRESHOLD:
        return "High amplification"
    if coupling_strength > 0.8:
        return "Moderate coupling"
    return "Low coupling"


class CouplingDetector:
    """
    Surfaces domain pairs with highest nonlinear coupling pressure derived
    from the Lie algebra commutator [X_A, X_B] for active pattern pairs.

    Each element C[d_i, d_j] of the commutator measures non-linear
    interference intensity between semantic dimension d_i and d_j.
    The absolute value |C[d_i, d_j]| is the coupling strength for the pair.
    """

    def compute_coupling(
        self,
        assessment_id: str,
        active_pattern_pairs: list[tuple[str, str]],
    ) -> CouplingOutput:
        """
        Compute coupling for all active pattern pairs and return top-N domain
        pairs ranked by coupling strength.

        Args:
            assessment_id: The assessment identifier.
            active_pattern_pairs: List of (pattern_a, pattern_b) tuples from
                the assessment context.

        Returns:
            CouplingOutput with top-3 domain pairs ranked by coupling strength.
        """
        if not active_pattern_pairs:
            return CouplingOutput(
                assessment_id=assessment_id,
                pairs=[],
                updated_at=datetime.now(tz=timezone.utc),
            )

        try:
            from ontology.dual_inference_engine import run_lie_algebra_inference  # type: ignore
            from ontology.lie_algebra_space import SEMANTIC_DIMS  # type: ignore
        except ImportError as exc:
            logger.warning("Lie algebra engine unavailable for coupling detection: %s", exc)
            return CouplingOutput(
                assessment_id=assessment_id,
                pairs=[],
                updated_at=datetime.now(tz=timezone.utc),
            )

        # Aggregate |C[d_i, d_j]| over all active pattern pairs (take max per pair)
        pair_strengths: dict[tuple[str, str], float] = {}

        for pattern_a, pattern_b in active_pattern_pairs:
            try:
                result = run_lie_algebra_inference(pattern_a, pattern_b)
                bracket = result.bracket_matrix  # shape (8, 8)
                dims = SEMANTIC_DIMS

                for i, d_i in enumerate(dims):
                    for j, d_j in enumerate(dims):
                        if i >= j:
                            continue  # upper triangle only — avoid duplicates
                        strength = float(abs(bracket[i, j]))
                        key = (d_i, d_j)
                        if key not in pair_strengths or strength > pair_strengths[key]:
                            pair_strengths[key] = strength

            except Exception as exc:
                logger.debug(
                    "Coupling computation failed for (%s, %s): %s",
                    pattern_a, pattern_b, exc,
                )

        # Rank by coupling_strength descending, take top-N
        ranked = sorted(pair_strengths.items(), key=lambda x: x[1], reverse=True)[:_TOP_N]

        coupling_pairs = [
            CouplingPair(
                domain_a=domain_a,
                domain_b=domain_b,
                coupling_strength=round(strength, 4),
                is_amplifying=strength > COUPLING_THRESHOLD,
                amplification_label=_amplification_label(strength),
            )
            for (domain_a, domain_b), strength in ranked
        ]

        return CouplingOutput(
            assessment_id=assessment_id,
            pairs=coupling_pairs,
            updated_at=datetime.now(tz=timezone.utc),
        )
