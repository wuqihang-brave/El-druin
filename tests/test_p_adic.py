"""Tests for backend/intelligence/p_adic_confidence.py.

Verifies p-adic valuation, p-adic absolute value, and the confidence
function with phase transitions at multiples of p.
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from intelligence.p_adic_confidence import confidence, p_adic_abs, p_adic_valuation


class TestPAdicValuation:
    def test_v7_of_7_is_1(self):
        assert p_adic_valuation(7) == 1

    def test_v7_of_49_is_2(self):
        assert p_adic_valuation(49) == 2

    def test_v7_of_343_is_3(self):
        assert p_adic_valuation(343) == 3

    def test_v7_of_1_is_0(self):
        assert p_adic_valuation(1) == 0

    def test_v7_of_6_is_0(self):
        assert p_adic_valuation(6) == 0

    def test_v7_of_14_is_1(self):
        # 14 = 2 × 7, so v_7(14) = 1
        assert p_adic_valuation(14) == 1

    def test_v7_of_21_is_1(self):
        # 21 = 3 × 7
        assert p_adic_valuation(21) == 1

    def test_v7_of_0_is_sentinel(self):
        # Convention: v_p(0) = +∞ (returned as sentinel 10**18)
        assert p_adic_valuation(0) == 10**18

    def test_v7_of_negative_mirrors_positive(self):
        # v_p is defined on absolute value
        assert p_adic_valuation(-7) == 1
        assert p_adic_valuation(-49) == 2

    def test_v5_of_25_is_2(self):
        assert p_adic_valuation(25, p=5) == 2

    def test_v5_of_7_is_0(self):
        assert p_adic_valuation(7, p=5) == 0


class TestPAdicAbs:
    def test_abs_7_is_1_over_7(self):
        result = p_adic_abs(7)
        assert abs(result - 1 / 7) < 1e-12

    def test_abs_14_is_1_over_7(self):
        # 14 = 2 × 7 → v_7(14) = 1 → |14|_7 = 1/7
        result = p_adic_abs(14)
        assert abs(result - 1 / 7) < 1e-12

    def test_abs_49_is_1_over_49(self):
        result = p_adic_abs(49)
        assert abs(result - 1 / 49) < 1e-12

    def test_abs_1_is_1(self):
        assert p_adic_abs(1) == 1.0

    def test_abs_6_is_1(self):
        # 6 not divisible by 7 → v_7(6) = 0 → |6|_7 = 1
        assert p_adic_abs(6) == 1.0

    def test_abs_0_is_0(self):
        assert p_adic_abs(0) == 0.0

    def test_abs_343_is_1_over_343(self):
        result = p_adic_abs(343)
        assert abs(result - 1 / 343) < 1e-12

    def test_abs_always_in_0_1(self):
        for t in range(1, 50):
            assert 0.0 < p_adic_abs(t) <= 1.0


class TestConfidence:
    def test_confidence_at_step_1_is_c0(self):
        # |1|_7 = 1, so c(P, 1) = c0
        assert confidence("P", 1) == 1.0
        assert confidence("P", 1, c0=0.8) == 0.8

    def test_confidence_at_step_7_is_c0_over_7(self):
        result = confidence("P", 7, c0=1.0)
        assert abs(result - 1 / 7) < 1e-12

    def test_confidence_at_step_14_is_c0_over_7(self):
        result = confidence("P", 14, c0=1.0)
        assert abs(result - 1 / 7) < 1e-12

    def test_confidence_at_step_21_is_c0_over_7(self):
        result = confidence("P", 21, c0=1.0)
        assert abs(result - 1 / 7) < 1e-12

    def test_confidence_at_step_49_is_c0_over_49(self):
        result = confidence("P", 49, c0=1.0)
        assert abs(result - 1 / 49) < 1e-12


class TestPhaseTransitions:
    """Phase transitions occur at multiples of p: confidence drops by factor p."""

    def test_phase_transition_at_7_smaller_than_6(self):
        c6 = confidence("P", 6)
        c7 = confidence("P", 7)
        assert c7 < c6

    def test_phase_transition_at_7_smaller_than_8(self):
        c7 = confidence("P", 7)
        c8 = confidence("P", 8)
        assert c7 < c8

    def test_phase_transition_at_14_smaller_than_13(self):
        c13 = confidence("P", 13)
        c14 = confidence("P", 14)
        assert c14 < c13

    def test_phase_transition_at_14_smaller_than_15(self):
        c14 = confidence("P", 14)
        c15 = confidence("P", 15)
        assert c14 < c15

    def test_phase_transition_at_21_smaller_than_20(self):
        c20 = confidence("P", 20)
        c21 = confidence("P", 21)
        assert c21 < c20

    def test_non_multiples_have_same_abs_value(self):
        # All non-multiples of 7 have |t|_7 = 1
        for t in [1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 13]:
            assert confidence("P", t) == 1.0

    def test_multiples_of_49_have_extra_drop(self):
        c7 = confidence("P", 7)
        c49 = confidence("P", 49)
        # v_7(49) = 2, v_7(7) = 1 → c49 is 7× smaller than c7
        assert abs(c7 / c49 - 7.0) < 1e-10
