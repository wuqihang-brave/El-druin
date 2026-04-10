"""
tests/test_forecast_brief_component.py
=======================================

Unit tests for ``frontend/components/forecast_brief.py``.

Validates:
 - render_forecast_brief() does not raise on valid brief_data
 - render_forecast_brief() does not raise on minimal brief_data (optional fields absent)
 - confidence_css_class() returns correct CSS class for High/Medium/Low
 - confidence_color() returns correct hex colors
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict
from unittest.mock import MagicMock, patch

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

# Provide a minimal stub so that importing forecast_brief doesn't need a
# real Streamlit session context.
_st_mock = MagicMock()
_st_mock.columns.return_value = (MagicMock(), MagicMock(), MagicMock())
sys.modules.setdefault("streamlit", _st_mock)

from components.forecast_brief import (  # noqa: E402
    confidence_css_class,
    confidence_color,
    render_forecast_brief,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FULL_BRIEF: Dict[str, Any] = {
    "forecast_posture": "Escalation Trajectory — High Structural Stress",
    "time_horizon": "30–90 days",
    "confidence": "High",
    "why_it_matters": (
        "The system is approaching a nonlinear threshold. Continued stress "
        "accumulation along the energy-security axis creates conditions for "
        "a rapid regime shift."
    ),
    "dominant_driver": "Energy corridor disruption amplified by proxy dynamics",
    "strengthening_conditions": [
        "Additional naval incidents in contested transit zones",
        "Sanctions escalation reducing market liquidity",
    ],
    "weakening_conditions": [
        "Back-channel diplomatic progress",
        "Energy price stabilisation reducing pressure",
    ],
    "invalidation_conditions": [
        "Formal ceasefire agreement with third-party verification",
        "Strategic partner disengagement from proxy actors",
    ],
}

_MINIMAL_BRIEF: Dict[str, Any] = {
    "forecast_posture": "Stable Observation",
}

_EMPTY_BRIEF: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Tests: confidence_css_class
# ---------------------------------------------------------------------------

class TestConfidenceCssClass:
    def test_high_returns_confidence_high(self) -> None:
        assert confidence_css_class("High") == "confidence-high"

    def test_medium_returns_confidence_medium(self) -> None:
        assert confidence_css_class("Medium") == "confidence-medium"

    def test_low_returns_confidence_low(self) -> None:
        assert confidence_css_class("Low") == "confidence-low"

    def test_unknown_value_falls_back_to_medium(self) -> None:
        result = confidence_css_class("Unknown")
        assert result == "confidence-medium"

    def test_empty_string_falls_back_to_medium(self) -> None:
        result = confidence_css_class("")
        assert result == "confidence-medium"


# ---------------------------------------------------------------------------
# Tests: confidence_color
# ---------------------------------------------------------------------------

class TestConfidenceColor:
    def test_high_is_green_toned(self) -> None:
        color = confidence_color("High")
        assert color == "#4caf7d"

    def test_medium_is_amber_toned(self) -> None:
        color = confidence_color("Medium")
        assert color == "#e8a742"

    def test_low_is_red_toned(self) -> None:
        color = confidence_color("Low")
        assert color == "#e05c5c"

    def test_all_values_are_hex_colors(self) -> None:
        for level in ("High", "Medium", "Low"):
            c = confidence_color(level)
            assert c.startswith("#"), f"Color for {level!r} should be a hex string, got {c!r}"
            assert len(c) == 7, f"Color for {level!r} should be 7 chars, got {c!r}"


# ---------------------------------------------------------------------------
# Tests: render_forecast_brief
# ---------------------------------------------------------------------------

class TestRenderForecastBrief:
    """Verify that render_forecast_brief does not raise under various inputs."""

    def _run(self, brief_data: Dict[str, Any]) -> None:
        """Helper: call render_forecast_brief inside a fresh st mock context."""
        mock_col = MagicMock()
        mock_col.__enter__ = MagicMock(return_value=mock_col)
        mock_col.__exit__ = MagicMock(return_value=False)

        def _columns_side_effect(arg):
            n = arg if isinstance(arg, int) else len(arg)
            return tuple(mock_col for _ in range(n))

        _st_mock.columns.side_effect = _columns_side_effect
        render_forecast_brief(brief_data)

    def test_full_brief_does_not_raise(self) -> None:
        self._run(_FULL_BRIEF)

    def test_minimal_brief_does_not_raise(self) -> None:
        self._run(_MINIMAL_BRIEF)

    def test_empty_brief_does_not_raise(self) -> None:
        self._run(_EMPTY_BRIEF)

    def test_missing_conditions_does_not_raise(self) -> None:
        brief = {
            "forecast_posture": "Elevated Watch",
            "confidence": "Medium",
            "time_horizon": "14 days",
        }
        self._run(brief)

    def test_none_confidence_does_not_raise(self) -> None:
        brief = {"forecast_posture": "Watch", "confidence": None}
        self._run(brief)

    def test_empty_condition_lists_does_not_raise(self) -> None:
        brief = {
            "forecast_posture": "Stable",
            "confidence": "Low",
            "strengthening_conditions": [],
            "weakening_conditions": [],
            "invalidation_conditions": [],
        }
        self._run(brief)

    def test_high_confidence_uses_correct_css_class(self) -> None:
        """Verify the correct CSS class is produced for High confidence."""
        assert confidence_css_class("High") == "confidence-high"
        assert "4caf7d" in confidence_color("High")

    def test_medium_confidence_uses_correct_css_class(self) -> None:
        assert confidence_css_class("Medium") == "confidence-medium"
        assert "e8a742" in confidence_color("Medium")

    def test_low_confidence_uses_correct_css_class(self) -> None:
        assert confidence_css_class("Low") == "confidence-low"
        assert "e05c5c" in confidence_color("Low")
