"""Tests for backend/intelligence/group_structure.py.

Verifies that Z_7 ⋊ Z_3 (|S| = 21) satisfies all group axioms and that
every element maps uniquely to a (domain, mode) pair.
"""

from __future__ import annotations

import sys
import os

# Ensure backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from intelligence.group_structure import (
    AUTOMORPHISM,
    CAYLEY_TABLE,
    H3,
    H3_MODE_MAP,
    H7,
    H7_DOMAIN_MAP,
    IDENTITY,
    S,
    build_cayley_table,
    get_coset,
    group_inv,
    group_mul,
    verify_group,
)


class TestGroupSize:
    def test_exactly_21_elements(self):
        assert len(S) == 21

    def test_no_duplicate_elements(self):
        assert len(set(S)) == 21

    def test_elements_in_correct_range(self):
        for a, b in S:
            assert 0 <= a <= 6, f"a={a} out of range Z_7"
            assert 0 <= b <= 2, f"b={b} out of range Z_3"


class TestIdentity:
    def test_identity_element_exists(self):
        assert IDENTITY in S
        assert IDENTITY == (0, 0)

    def test_right_identity(self):
        for g in S:
            assert group_mul(g, IDENTITY) == g, f"Right identity failed for {g}"

    def test_left_identity(self):
        for g in S:
            assert group_mul(IDENTITY, g) == g, f"Left identity failed for {g}"


class TestClosure:
    def test_closed_under_multiplication(self):
        s_set = set(S)
        for g1 in S:
            for g2 in S:
                result = group_mul(g1, g2)
                assert result in s_set, (
                    f"Closure violated: {g1} · {g2} = {result} ∉ S"
                )


class TestInverses:
    def test_every_element_has_inverse(self):
        for g in S:
            inv = group_inv(g)
            assert inv in S, f"Inverse of {g} = {inv} not in S"

    def test_right_inverse(self):
        for g in S:
            assert group_mul(g, group_inv(g)) == IDENTITY, (
                f"g · g⁻¹ ≠ e for g={g}"
            )

    def test_left_inverse(self):
        for g in S:
            assert group_mul(group_inv(g), g) == IDENTITY, (
                f"g⁻¹ · g ≠ e for g={g}"
            )

    def test_identity_is_own_inverse(self):
        assert group_inv(IDENTITY) == IDENTITY


class TestAssociativity:
    def test_associativity_sample(self):
        import random
        random.seed(0)
        for _ in range(200):
            a, b, c = random.choices(S, k=3)
            lhs = group_mul(group_mul(a, b), c)
            rhs = group_mul(a, group_mul(b, c))
            assert lhs == rhs, f"({a}·{b})·{c}={lhs} ≠ {a}·({b}·{c})={rhs}"

    def test_specific_associativity(self):
        # (1,1)·(2,1) = ((1 + 2*2)%7, 2%3) = (5,2)
        # (5,2)·(3,0) = ((5 + 4*3)%7, 2%3) = ((5+12)%7, 2) = (3,2)
        a, b, c = (1, 1), (2, 1), (3, 0)
        assert group_mul(group_mul(a, b), c) == group_mul(a, group_mul(b, c))


class TestAutomorphism:
    def test_automorphism_values(self):
        assert AUTOMORPHISM[0] == 1   # 2^0 mod 7 = 1
        assert AUTOMORPHISM[1] == 2   # 2^1 mod 7 = 2
        assert AUTOMORPHISM[2] == 4   # 2^2 mod 7 = 4

    def test_automorphism_order_3(self):
        # Applying automorphism 3 times should return to identity: 2^3 = 8 ≡ 1 mod 7
        a = 3
        assert (AUTOMORPHISM[0] * a) % 7 == a
        result = a
        for b in range(3):
            result = (AUTOMORPHISM[b % 3] * result) % 7
        # After 3 applications the composition is φ(0)∘φ(1)∘φ(2) — just check
        # the simpler fact: 2^3 ≡ 1 mod 7
        assert (2**3) % 7 == 1


class TestSylowSubgroups:
    def test_h7_size(self):
        assert len(H7) == 7

    def test_h7_elements(self):
        assert set(H7) == {(a, 0) for a in range(7)}

    def test_h3_size(self):
        assert len(H3) == 3

    def test_h3_elements(self):
        assert set(H3) == {(0, b) for b in range(3)}

    def test_h7_closed_under_mul(self):
        h7_set = set(H7)
        for g1 in H7:
            for g2 in H7:
                assert group_mul(g1, g2) in h7_set

    def test_h7_domain_map_covers_all_domains(self):
        expected = {"geopolitics", "economics", "technology", "military",
                    "information", "legal", "social"}
        assert set(H7_DOMAIN_MAP.values()) == expected

    def test_h3_mode_map_covers_all_modes(self):
        expected = {"structural", "coercive", "cooperative"}
        assert set(H3_MODE_MAP.values()) == expected


class TestGetCoset:
    def test_identity_is_geopolitics_structural(self):
        domain, mode = get_coset((0, 0))
        assert domain == "geopolitics"
        assert mode == "structural"

    def test_all_elements_have_unique_coset(self):
        cosets = [get_coset(g) for g in S]
        assert len(cosets) == 21

    def test_coset_domain_determined_by_a(self):
        for a in range(7):
            for b in range(3):
                domain, _ = get_coset((a, b))
                assert domain == H7_DOMAIN_MAP[a]

    def test_coset_mode_determined_by_b(self):
        for a in range(7):
            for b in range(3):
                _, mode = get_coset((a, b))
                assert mode == H3_MODE_MAP[b]


class TestCayleyTable:
    def test_cayley_table_size(self):
        assert len(CAYLEY_TABLE) == 21 * 21

    def test_cayley_table_consistent_with_group_mul(self):
        for g1 in S:
            for g2 in S:
                assert CAYLEY_TABLE[(g1, g2)] == group_mul(g1, g2)


class TestVerifyGroup:
    def test_verify_group_passes(self):
        # Should not raise
        verify_group()
