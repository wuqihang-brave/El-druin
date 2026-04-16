"""
Group Structure: Z_7 ⋊ Z_3 (Non-abelian Semidirect Product, |S| = 21)
========================================================================

Implements a proper group of order 21 = 7 × 3 as the pattern space S.
This replaces the previous partial-semigroup structure.

Group law:
    (a1, b1) · (a2, b2) = ((a1 + 2^b1 · a2) mod 7, (b1 + b2) mod 3)

where the automorphism φ(b): a ↦ 2^b · a mod 7 has order 3
(since 2^3 ≡ 1 mod 7).

Identity: (0, 0)
Inverse: (a, b)^{-1} = (−2^{−b} · a mod 7, −b mod 3)

Sylow-7 subgroup H₇ = {(a, 0) | a ∈ Z₇} (unique, normal)
    maps to 7 domains: geopolitics, economics, technology, military,
                       information, legal, social

Sylow-3 subgroup H₃ = {(0, b) | b ∈ Z₃}
    maps to 3 interaction modes: structural, coercive, cooperative
"""

from __future__ import annotations

from itertools import product as iproduct
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Automorphism table: φ(b)(a) = 2^b · a mod 7
# 2^0 = 1, 2^1 = 2, 2^2 = 4  (all mod 7)
# ---------------------------------------------------------------------------

AUTOMORPHISM: Dict[int, int] = {0: 1, 1: 2, 2: 4}

# ---------------------------------------------------------------------------
# Core group operations
# ---------------------------------------------------------------------------

Element = Tuple[int, int]  # (a, b) with a ∈ Z_7, b ∈ Z_3


def group_mul(g1: Element, g2: Element) -> Element:
    """Group multiplication in Z_7 ⋊ Z_3.

    (a1, b1) · (a2, b2) = ((a1 + 2^b1 · a2) mod 7, (b1 + b2) mod 3)
    """
    a1, b1 = g1
    a2, b2 = g2
    return ((a1 + AUTOMORPHISM[b1] * a2) % 7, (b1 + b2) % 3)


def group_inv(g: Element) -> Element:
    """Inverse of element g in Z_7 ⋊ Z_3.

    (a, b)^{-1} = (−2^{−b} · a mod 7, −b mod 3)
    """
    a, b = g
    b_inv = (-b) % 3
    a_inv = (-AUTOMORPHISM[b_inv] * a) % 7
    return (a_inv, b_inv)


# Identity element
IDENTITY: Element = (0, 0)

# ---------------------------------------------------------------------------
# All 21 elements
# ---------------------------------------------------------------------------

S: List[Element] = [(a, b) for b in range(3) for a in range(7)]

# ---------------------------------------------------------------------------
# Sylow subgroups
# ---------------------------------------------------------------------------

# Sylow-7 subgroup H₇ = {(a, 0) | a ∈ Z₇} — unique and normal in S
H7: List[Element] = [(a, 0) for a in range(7)]

H7_DOMAIN_MAP: Dict[int, str] = {
    0: "geopolitics",
    1: "economics",
    2: "technology",
    3: "military",
    4: "information",
    5: "legal",
    6: "social",
}

# Sylow-3 subgroup H₃ = {(0, b) | b ∈ Z₃}
H3: List[Element] = [(0, b) for b in range(3)]

H3_MODE_MAP: Dict[int, str] = {
    0: "structural",
    1: "coercive",
    2: "cooperative",
}

# ---------------------------------------------------------------------------
# Coset lookup
# ---------------------------------------------------------------------------


def get_coset(elem: Element) -> Tuple[str, str]:
    """Return the (domain, mode) pair for a pattern element.

    Each element (a, b) uniquely falls in a (H₇-coset, H₃-coset) pair
    determined by its coordinates:
      - a ∈ Z₇  → H₇ domain index
      - b ∈ Z₃  → H₃ mode index

    Args:
        elem: A group element (a, b) with a ∈ Z₇, b ∈ Z₃.

    Returns:
        Tuple of (domain_str, mode_str).
    """
    a, b = elem
    return H7_DOMAIN_MAP[a], H3_MODE_MAP[b]


# ---------------------------------------------------------------------------
# Cayley table
# ---------------------------------------------------------------------------


def build_cayley_table() -> Dict[Tuple[Element, Element], Element]:
    """Build the complete 21×21 Cayley multiplication table.

    Returns:
        Dict mapping (g1, g2) → g1 · g2 for all g1, g2 ∈ S.
    """
    table: Dict[Tuple[Element, Element], Element] = {}
    for g1 in S:
        for g2 in S:
            table[(g1, g2)] = group_mul(g1, g2)
    return table


CAYLEY_TABLE: Dict[Tuple[Element, Element], Element] = build_cayley_table()

# ---------------------------------------------------------------------------
# Verification functions
# ---------------------------------------------------------------------------


def verify_closure() -> None:
    """Verify that S is closed under group multiplication."""
    s_set = set(S)
    for g1, g2 in iproduct(S, S):
        result = group_mul(g1, g2)
        assert result in s_set, f"Closure violated: {g1} · {g2} = {result} ∉ S"


def verify_identity() -> None:
    """Verify that (0, 0) is the two-sided identity."""
    for g in S:
        assert group_mul(g, IDENTITY) == g, f"Right identity failed for {g}"
        assert group_mul(IDENTITY, g) == g, f"Left identity failed for {g}"


def verify_inverses() -> None:
    """Verify that every element has a valid two-sided inverse."""
    for g in S:
        inv = group_inv(g)
        assert group_mul(g, inv) == IDENTITY, f"Right inverse failed for {g}"
        assert group_mul(inv, g) == IDENTITY, f"Left inverse failed for {g}"


def verify_associativity(num_samples: int = 300) -> None:
    """Spot-check associativity: (a·b)·c == a·(b·c).

    Args:
        num_samples: Number of random triples to test.
    """
    import random

    random.seed(42)
    for _ in range(num_samples):
        a, b, c = random.choices(S, k=3)
        lhs = group_mul(group_mul(a, b), c)
        rhs = group_mul(a, group_mul(b, c))
        assert lhs == rhs, f"Associativity violated: ({a}·{b})·{c}={lhs} ≠ {a}·({b}·{c})={rhs}"


def verify_group() -> None:
    """Verify all four group axioms for Z_7 ⋊ Z_3 (|S| = 21).

    Raises:
        AssertionError: If any axiom is violated.
    """
    assert len(S) == 21, f"Expected |S|=21, got {len(S)}"
    assert len(set(S)) == 21, "Duplicate elements found in S"
    verify_closure()
    verify_identity()
    verify_inverses()
    verify_associativity()


if __name__ == "__main__":
    verify_group()
    print("✓ Group axioms verified: |S|=21, Z_7 ⋊ Z_3")
    print(f"  H₇ (Sylow-7, normal): {H7}")
    print(f"  H₃ (Sylow-3): {H3}")
    print("  Domain map:", H7_DOMAIN_MAP)
    print("  Mode map:  ", H3_MODE_MAP)
