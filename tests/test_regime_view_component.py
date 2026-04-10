"""
tests/test_regime_view_component.py
====================================

Unit tests for ``frontend/components/regime_view.py``.

Validates:
 - render_regime_view() does not raise with valid regime_data
 - render_regime_view() does not raise with minimal regime_data
 - regime_color_class() returns correct CSS class for each of the 6 regime states
 - threshold_color_class() color scale: 0.1 -> critical, 0.3 -> advisory, 0.6 -> safe
 - damping_color_class() color scale: 0.2 -> critical, 0.4 -> advisory, 0.6 -> safe
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Make frontend importable from repo root
# ---------------------------------------------------------------------------

_FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if _FRONTEND_DIR not in sys.path:
    sys.path.insert(0, _FRONTEND_DIR)

# ---------------------------------------------------------------------------
# Mock streamlit before importing the component
# ---------------------------------------------------------------------------

_st_mock = MagicMock()

def _columns_side_effect(arg):
    n = arg if isinstance(arg, int) else len(arg)
    mock_col = MagicMock()
    mock_col.__enter__ = MagicMock(return_value=mock_col)
    mock_col.__exit__ = MagicMock(return_value=False)
    return tuple(mock_col for _ in range(n))

_st_mock.columns.side_effect = _columns_side_effect
# Force-install our mock so it takes precedence even if another test module
# already registered a different streamlit stub via setdefault.
sys.modules["streamlit"] = _st_mock
# Remove any cached import of the component so it is re-imported against our
# mock rather than a stale module that points to a different stub.
sys.modules.pop("components.regime_view", None)

from components.regime_view import (  # noqa: E402
    damping_color_class,
    regime_color_class,
    render_regime_view,
    threshold_color_class,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FULL_REGIME: Dict[str, Any] = {
    "current_regime": "Nonlinear Escalation",
    "threshold_distance": 0.22,
    "transition_volatility": 0.71,
    "reversibility_index": 0.38,
    "dominant_axis": "military -> sanctions -> energy",
    "coupling_asymmetry": 0.55,
    "damping_capacity": 0.29,
    "forecast_implication": (
        "System is operating inside the nonlinear response band. "
        "A moderate shock is sufficient to trigger cascade propagation."
    ),
}

_MINIMAL_REGIME: Dict[str, Any] = {
    "current_regime": "Linear",
}

_EMPTY_REGIME: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _run(regime_data: Dict[str, Any]) -> None:
    """Call render_regime_view with a fresh columns mock."""
    _st_mock.columns.side_effect = _columns_side_effect
    render_regime_view(regime_data)


# ---------------------------------------------------------------------------
# Tests: regime_color_class
# ---------------------------------------------------------------------------

class TestRegimeColorClass:
    def test_linear_returns_regime_linear(self) -> None:
        assert regime_color_class("Linear") == "regime-linear"

    def test_stress_accumulation_returns_regime_stress(self) -> None:
        assert regime_color_class("Stress Accumulation") == "regime-stress"

    def test_nonlinear_escalation_returns_regime_nonlinear(self) -> None:
        assert regime_color_class("Nonlinear Escalation") == "regime-nonlinear"

    def test_cascade_risk_returns_regime_cascade(self) -> None:
        assert regime_color_class("Cascade Risk") == "regime-cascade"

    def test_attractor_lock_in_returns_regime_attractor(self) -> None:
        assert regime_color_class("Attractor Lock-in") == "regime-attractor"

    def test_dissipating_returns_regime_dissipating(self) -> None:
        assert regime_color_class("Dissipating") == "regime-dissipating"

    def test_unknown_regime_falls_back_to_linear(self) -> None:
        result = regime_color_class("Unknown State")
        assert result == "regime-linear"

    def test_empty_string_falls_back_to_linear(self) -> None:
        assert regime_color_class("") == "regime-linear"

    def test_all_valid_regimes_return_unique_classes(self) -> None:
        regimes = [
            "Linear",
            "Stress Accumulation",
            "Nonlinear Escalation",
            "Cascade Risk",
            "Attractor Lock-in",
            "Dissipating",
        ]
        classes = [regime_color_class(r) for r in regimes]
        assert len(set(classes)) == 6, "Each regime must map to a unique CSS class"


# ---------------------------------------------------------------------------
# Tests: threshold_color_class
# ---------------------------------------------------------------------------

class TestThresholdColorClass:
    def test_low_value_is_critical(self) -> None:
        assert threshold_color_class(0.1) == "threshold-critical"

    def test_mid_value_is_advisory(self) -> None:
        assert threshold_color_class(0.3) == "threshold-advisory"

    def test_high_value_is_safe(self) -> None:
        assert threshold_color_class(0.6) == "threshold-safe"

    def test_boundary_0_2_is_advisory(self) -> None:
        assert threshold_color_class(0.2) == "threshold-advisory"

    def test_boundary_0_4_is_safe(self) -> None:
        assert threshold_color_class(0.4) == "threshold-safe"

    def test_just_below_0_2_is_critical(self) -> None:
        assert threshold_color_class(0.19) == "threshold-critical"

    def test_zero_is_critical(self) -> None:
        assert threshold_color_class(0.0) == "threshold-critical"

    def test_one_is_safe(self) -> None:
        assert threshold_color_class(1.0) == "threshold-safe"


# ---------------------------------------------------------------------------
# Tests: damping_color_class
# ---------------------------------------------------------------------------

class TestDampingColorClass:
    def test_low_damping_is_critical(self) -> None:
        assert damping_color_class(0.2) == "threshold-critical"

    def test_mid_damping_is_advisory(self) -> None:
        assert damping_color_class(0.4) == "threshold-advisory"

    def test_high_damping_is_safe(self) -> None:
        assert damping_color_class(0.6) == "threshold-safe"

    def test_boundary_0_3_is_advisory(self) -> None:
        assert damping_color_class(0.3) == "threshold-advisory"

    def test_just_above_0_5_is_safe(self) -> None:
        assert damping_color_class(0.51) == "threshold-safe"

    def test_exactly_0_5_is_advisory(self) -> None:
        assert damping_color_class(0.5) == "threshold-advisory"


# ---------------------------------------------------------------------------
# Tests: render_regime_view
# ---------------------------------------------------------------------------

class TestRenderRegimeView:
    """Verify that render_regime_view does not raise under various inputs."""

    def test_full_data_does_not_raise(self) -> None:
        _run(_FULL_REGIME)

    def test_minimal_data_does_not_raise(self) -> None:
        _run(_MINIMAL_REGIME)

    def test_empty_data_does_not_raise(self) -> None:
        _run(_EMPTY_REGIME)

    def test_none_values_do_not_raise(self) -> None:
        _run(
            {
                "current_regime": None,
                "threshold_distance": None,
                "transition_volatility": None,
                "reversibility_index": None,
                "dominant_axis": None,
                "coupling_asymmetry": None,
                "damping_capacity": None,
                "forecast_implication": None,
            }
        )

    def test_missing_forecast_implication_does_not_raise(self) -> None:
        _run({"current_regime": "Cascade Risk", "threshold_distance": 0.15})

    def test_dominant_axis_with_arrow_chain_does_not_raise(self) -> None:
        _run(
            {
                "current_regime": "Stress Accumulation",
                "dominant_axis": "military -> sanctions -> energy -> finance",
                "threshold_distance": 0.25,
            }
        )

    def test_dominant_axis_single_node_does_not_raise(self) -> None:
        _run({"current_regime": "Linear", "dominant_axis": "geopolitical"})

    def test_all_six_regime_states_do_not_raise(self) -> None:
        for regime in [
            "Linear",
            "Stress Accumulation",
            "Nonlinear Escalation",
            "Cascade Risk",
            "Attractor Lock-in",
            "Dissipating",
        ]:
            _run({"current_regime": regime, "threshold_distance": 0.5})

    def test_markdown_called_for_banner(self) -> None:
        _st_mock.reset_mock()
        _st_mock.columns.side_effect = _columns_side_effect
        render_regime_view({"current_regime": "Cascade Risk"})
        # st.markdown should have been called at least once for the banner
        assert _st_mock.markdown.called

    def test_metric_values_rendered_in_output(self) -> None:
        """All six metric values should appear in the markdown calls when provided."""
        _st_mock.reset_mock()
        _st_mock.columns.side_effect = _columns_side_effect
        render_regime_view(_FULL_REGIME)
        all_rendered = " ".join(str(c) for c in _st_mock.markdown.call_args_list)

        # Numeric metrics should appear as formatted strings
        assert "0.22" in all_rendered, "threshold_distance value should appear"
        assert "0.71" in all_rendered, "transition_volatility value should appear"
        assert "0.38" in all_rendered, "reversibility_index value should appear"
        assert "0.55" in all_rendered, "coupling_asymmetry value should appear"
        assert "0.29" in all_rendered, "damping_capacity value should appear"

        # dominant_axis parts should appear
        assert "military" in all_rendered, "dominant_axis 'military' segment should appear"
        assert "sanctions" in all_rendered, "dominant_axis 'sanctions' segment should appear"
        assert "energy" in all_rendered, "dominant_axis 'energy' segment should appear"
        """regime-cascade CSS class must appear in the rendered HTML."""
        _st_mock.reset_mock()
        _st_mock.columns.side_effect = _columns_side_effect
        render_regime_view({"current_regime": "Cascade Risk"})
        rendered_calls = [
            str(call) for call in _st_mock.markdown.call_args_list
        ]
        banner_calls = [c for c in rendered_calls if "regime-cascade" in c]
        assert banner_calls, "regime-cascade CSS class should appear in markdown call"
