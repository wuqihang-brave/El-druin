"""
p-adic Confidence
==================

Replaces the geometric step-decay λᵗ with a p-adic valuation |t|_p.

Formula::

    c(P, t) = c₀^(P) · |t|_p = c₀^(P) · p^{−v_p(t)}

where:
  - v_p(t) is the p-adic valuation of t (largest k such that p^k divides t)
  - |t|_p = p^{−v_p(t)} is the p-adic absolute value

Phase transitions occur at t = p, 2p, 3p, … (multiples of p), where the
confidence |t|_p drops by a factor of p relative to nearby non-multiple steps.
This grounds temporal confidence in the ultrametric topology of the pattern
space rather than an ad hoc decay constant.

Default prime p = 7 matches the number of Sylow-7 domains (geopolitics,
economics, technology, military, information, legal, social), encoding the
system's domain-level phase-transition period.
"""

from __future__ import annotations


def p_adic_valuation(t: int, p: int = 7) -> int:
    """Compute the p-adic valuation v_p(t).

    v_p(t) is the largest non-negative integer k such that p^k divides t.
    By convention, v_p(0) = +∞ (returned as a very large sentinel integer).

    Args:
        t: Integer to evaluate (must be non-negative for meaningful results).
        p: Prime base (default 7).

    Returns:
        Non-negative integer valuation, or 10**18 if t == 0.

    Examples:
        >>> p_adic_valuation(7)
        1
        >>> p_adic_valuation(49)
        2
        >>> p_adic_valuation(1)
        0
        >>> p_adic_valuation(0)
        1000000000000000000
    """
    if t == 0:
        return 10**18  # sentinel for +∞
    t = abs(t)
    v = 0
    while t % p == 0:
        t //= p
        v += 1
    return v


def p_adic_abs(t: int, p: int = 7) -> float:
    """Compute the p-adic absolute value |t|_p = p^{−v_p(t)}.

    For t = 0 the p-adic absolute value is 0 (by convention).

    Args:
        t: Integer (step index or weight numerator).
        p: Prime base (default 7).

    Returns:
        Float in (0, 1] for t ≠ 0, or 0.0 for t = 0.

    Examples:
        >>> p_adic_abs(7)       # v_7(7) = 1 → 7^{-1}
        0.142857...
        >>> p_adic_abs(49)      # v_7(49) = 2 → 7^{-2}
        0.020408...
        >>> p_adic_abs(1)       # v_7(1) = 0 → 7^0 = 1
        1.0
    """
    if t == 0:
        return 0.0
    v = p_adic_valuation(t, p)
    return float(p) ** (-v)


def confidence(P: object, t: int, c0: float = 1.0, p: int = 7) -> float:
    """Compute the p-adic confidence for pattern P at step t.

    Formula::

        c(P, t) = c₀^(P) · |t|_p

    Phase transitions (confidence jumps) occur at t = p, 2p, 3p, … — steps
    where v_p(t) ≥ 1, giving |t|_p ≤ 1/p < 1.

    Args:
        P:   Pattern identifier (unused in computation; reserved for future
             per-pattern base confidence c₀^(P)).
        t:   Current reasoning step (positive integer).
        c0:  Base confidence for pattern P (default 1.0).
        p:   Prime base (default 7).

    Returns:
        Confidence value in (0, c0].

    Examples:
        >>> confidence("P", 1)   # |1|_7 = 1.0
        1.0
        >>> confidence("P", 7)   # |7|_7 = 1/7
        0.142857...
        >>> confidence("P", 14)  # |14|_7 = 1/7
        0.142857...
        >>> confidence("P", 49)  # |49|_7 = 1/49
        0.020408...
    """
    return c0 * p_adic_abs(t, p)


if __name__ == "__main__":
    print("p-adic confidence schedule (p=7, c0=1.0):")
    for step in range(1, 30):
        c = confidence("P_example", step)
        marker = " ← PHASE TRANSITION" if step % 7 == 0 else ""
        print(f"  t={step:2d}: |t|_7 = {c:.6f}{marker}")
