"""
Bifurcation Detection (p-adic definition)
==========================================

Old definition:
    bifurcation ⟺ |π(p₁) − π(p₂)| < threshold

New definition::

    bifurcation at step t  ⟺  v_p(π_t(p_top1) − π_t(p_top2)) ≥ k₀

The two highest-weight patterns are considered "p-adically close" when the
p-adic valuation of their weight difference is at least k₀.  A large
valuation means the difference is divisible by a high power of p, making
the two weights indistinguishable at the resolution of p^k₀ — a more
structurally precise notion of near-tie than a simple real-valued threshold.

Uses ``fractions.Fraction`` for exact rational arithmetic when the weights
are expressible as rationals, avoiding floating-point rounding artefacts.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Dict, Hashable

from intelligence.p_adic_confidence import p_adic_valuation


def bifurcation_detected(
    pi_t: Dict[Hashable, float],
    k0: int = 1,
    p: int = 7,
) -> bool:
    """Detect bifurcation using the p-adic valuation of the top-weight gap.

    bifurcation at step t  ⟺  v_p(π_t(p_top1) − π_t(p_top2)) ≥ k₀

    Args:
        pi_t: Mapping from pattern identifier to posterior weight.  Weights
              are treated as rational numbers (converted via
              ``Fraction.limit_denominator`` for precision).
        k0:   Minimum p-adic valuation threshold (default 1).
        p:    Prime base matching the domain count (default 7).

    Returns:
        ``True`` if the bifurcation condition is satisfied.

    Notes:
        - If fewer than two patterns are present, returns ``False``.
        - An exact tie (difference = 0) is treated as v_p = +∞ ≥ k₀, so
          ``True`` is always returned.
        - The valuation is computed on the *numerator* of the Fraction
          representation of the difference (after cancellation), which
          correctly captures divisibility by p for rational differences.
    """
    if len(pi_t) < 2:
        return False

    sorted_patterns = sorted(pi_t, key=lambda x: pi_t[x], reverse=True)
    w1 = pi_t[sorted_patterns[0]]
    w2 = pi_t[sorted_patterns[1]]

    # Convert to exact rationals to avoid floating-point rounding errors
    frac1 = Fraction(w1).limit_denominator(10**9)
    frac2 = Fraction(w2).limit_denominator(10**9)
    diff = frac1 - frac2

    if diff == 0:
        # Exact tie → valuation is +∞ ≥ k₀ for any finite k₀
        return True

    # Valuation of the numerator of the reduced fraction
    numerator = abs(diff.numerator)
    v = p_adic_valuation(numerator, p)
    return v >= k0
