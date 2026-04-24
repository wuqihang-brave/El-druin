"""Tests that ontology_forecaster uses p-adic confidence (not lambda decay).

Verifies:
- p_adic_absolute_value is exported from p_adic_confidence
- Step 6 has no phase transition (|6|_7 = 1)
- Step 7 triggers a phase transition (|7|_7 = 1/7)
- Confidence is flat (equal to c0) for steps 1–6
- p-adic bifurcation is importable from intelligence.bifurcation
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from intelligence.p_adic_confidence import confidence, p_adic_absolute_value


class TestPAdicAliasExported:
    def test_p_adic_absolute_value_exported(self):
        """p_adic_absolute_value must be importable (alias for p_adic_abs)."""
        assert callable(p_adic_absolute_value)

    def test_alias_matches_abs_behaviour(self):
        assert p_adic_absolute_value(1, p=7) == 1.0
        assert abs(p_adic_absolute_value(7, p=7) - 1 / 7) < 1e-12


class TestPAdicWiring:
    def test_step_6_no_phase_transition(self):
        # 6 is not a multiple of 7 → |6|_7 = 1 → no phase transition
        assert p_adic_absolute_value(6, p=7) == 1.0

    def test_step_7_phase_transition(self):
        # 7 is a multiple of 7 → |7|_7 = 1/7
        assert abs(p_adic_absolute_value(7, p=7) - 1 / 7) < 1e-12

    def test_step_14_phase_transition(self):
        # 14 = 2×7 → |14|_7 = 1/7
        assert abs(p_adic_absolute_value(14, p=7) - 1 / 7) < 1e-12

    def test_confidence_flat_within_period(self):
        # Between steps 1–6, confidence should stay at c0 (no decay)
        for t in range(1, 7):
            assert confidence("P", t, c0=0.75, p=7) == 0.75, (
                f"Expected confidence 0.75 at step {t}, "
                f"got {confidence('P', t, c0=0.75, p=7)}"
            )

    def test_confidence_drops_at_step_7(self):
        c6 = confidence("P", 6, c0=0.75, p=7)
        c7 = confidence("P", 7, c0=0.75, p=7)
        assert c7 < c6, f"Expected c7 < c6, got c7={c7}, c6={c6}"


class TestBifurcationImport:
    def test_bifurcation_importable(self):
        from intelligence.bifurcation import bifurcation_detected
        assert callable(bifurcation_detected)

    def test_forecaster_step_conf_uses_padic(self):
        """The forecaster's _step_confidence should give c0 for step=6."""
        from intelligence.ontology_forecaster import _step_confidence
        c = _step_confidence(0.75, 6, p=7)
        assert c == 0.75, f"Expected 0.75 at step 6 (no phase transition), got {c}"

    def test_forecaster_step_conf_drops_at_7(self):
        """The forecaster's _step_confidence should drop at step=7."""
        from intelligence.ontology_forecaster import _step_confidence
        c6 = _step_confidence(0.75, 6, p=7)
        c7 = _step_confidence(0.75, 7, p=7)
        assert c7 < c6, f"Expected c7 < c6, got c7={c7}, c6={c6}"
