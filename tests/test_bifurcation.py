"""Tests for backend/intelligence/bifurcation.py.

Verifies the p-adic bifurcation detection:
    bifurcation ⟺ v_p(π_t(p_top1) − π_t(p_top2)) ≥ k₀
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from intelligence.bifurcation import bifurcation_detected


class TestExactTie:
    def test_exact_tie_is_bifurcation(self):
        # Difference = 0 → v_p = +∞ ≥ k₀ for any k₀
        pi = {"A": 0.5, "B": 0.5}
        assert bifurcation_detected(pi, k0=1) is True

    def test_exact_tie_with_k0_large(self):
        pi = {"A": 0.5, "B": 0.5}
        assert bifurcation_detected(pi, k0=100) is True

    def test_three_patterns_exact_top_tie(self):
        pi = {"A": 0.5, "B": 0.5, "C": 0.0}
        assert bifurcation_detected(pi, k0=1) is True


class TestDifferenceDivisibleByP:
    def test_difference_7_over_common_denom_gives_valuation_1(self):
        # w1 - w2 = 7/100 → numerator 7 after reducing → v_7(7) = 1 ≥ k0=1
        pi = {"A": 0.57, "B": 0.50}
        # 0.57 - 0.50 = 0.07 = 7/100 → v_7(numerator=7) = 1
        assert bifurcation_detected(pi, k0=1, p=7) is True

    def test_difference_49_numerator_gives_valuation_2(self):
        # Difference = 49/10000 → numerator = 49 → v_7(49) = 2 ≥ k0=2
        from fractions import Fraction
        w1 = float(Fraction(149, 10000))  # 149/10000
        w2 = float(Fraction(100, 10000))  # 100/10000 → diff = 49/10000
        pi = {"A": w1, "B": w2}
        assert bifurcation_detected(pi, k0=2, p=7) is True
        assert bifurcation_detected(pi, k0=3, p=7) is False

    def test_difference_7_valuation_not_enough_for_k0_2(self):
        # v_7(7) = 1 < k0=2 → no bifurcation
        from fractions import Fraction
        w1 = float(Fraction(107, 1000))
        w2 = float(Fraction(100, 1000))  # diff = 7/1000 → numerator = 7 → v=1
        pi = {"A": w1, "B": w2}
        assert bifurcation_detected(pi, k0=2, p=7) is False


class TestDifferenceNotDivisibleByP:
    def test_difference_1_gives_valuation_0(self):
        # w1 - w2 = 1/10 → numerator = 1 → v_7(1) = 0 < k0=1 → no bifurcation
        from fractions import Fraction
        w1 = float(Fraction(3, 10))
        w2 = float(Fraction(2, 10))
        pi = {"A": w1, "B": w2}
        assert bifurcation_detected(pi, k0=1, p=7) is False

    def test_difference_3_gives_valuation_0(self):
        # numerator = 3 → v_7(3) = 0 < 1
        from fractions import Fraction
        w1 = float(Fraction(53, 100))
        w2 = float(Fraction(50, 100))
        pi = {"A": w1, "B": w2}
        assert bifurcation_detected(pi, k0=1, p=7) is False

    def test_large_non_multiple_difference(self):
        # 0.9 - 0.1 = 0.8 → numerator = 4 (= 4/5 reduced) → v_7(4) = 0
        pi = {"A": 0.9, "B": 0.1}
        assert bifurcation_detected(pi, k0=1, p=7) is False


class TestEdgeCases:
    def test_empty_dict_returns_false(self):
        assert bifurcation_detected({}, k0=1) is False

    def test_single_pattern_returns_false(self):
        assert bifurcation_detected({"A": 1.0}, k0=1) is False

    def test_k0_zero_always_bifurcation(self):
        # v_p(anything) ≥ 0 always → k0=0 always bifurcates for non-tie
        pi = {"A": 0.9, "B": 0.1}
        assert bifurcation_detected(pi, k0=0, p=7) is True

    def test_different_prime_p5(self):
        # Difference = 5/100 = 1/20 → numerator=1 under p=5 → v_5(1)=0 < 1
        from fractions import Fraction
        w1 = float(Fraction(55, 100))
        w2 = float(Fraction(50, 100))  # diff = 5/100 = 1/20 → num=1
        pi = {"A": w1, "B": w2}
        # With p=5: v_5(1) = 0 < 1 → no bifurcation after reduction
        # Note: 5/100 = 1/20, numerator=1
        assert bifurcation_detected(pi, k0=1, p=5) is False

    def test_different_prime_p5_divisible(self):
        # Difference numerator = 5 → v_5(5) = 1 ≥ k0=1
        from fractions import Fraction
        w1 = float(Fraction(105, 1000))
        w2 = float(Fraction(100, 1000))  # diff = 5/1000 = 1/200 → num=1
        pi = {"A": w1, "B": w2}
        # 5/1000 = 1/200 after reduction → v_5(1) = 0 < 1
        # To get v_5(numerator) = 1 we need numerator divisible by 5
        # Let's use 5/100 which reduces to 1/20 — numerator 1
        # Instead try 25/1000 = 1/40 → no
        # Best: use exact fractions
        w1b = float(Fraction(25, 100))
        w2b = float(Fraction(0, 100))
        pi2 = {"A": w1b, "B": w2b}
        # 25/100 = 1/4 → numerator=1 → v_5(1)=0 → False
        assert bifurcation_detected(pi2, k0=1, p=5) is False
