"""
Structural Regime View — EL'druin Intelligence Platform
========================================================

Provides ``render_regime_view(regime_data)`` for rendering the Structural
Regime View card inside the Assessment Workspace.

regime_data keys:
    current_regime, threshold_distance, transition_volatility,
    reversibility_index, dominant_axis, coupling_asymmetry,
    damping_capacity, forecast_implication
"""

from __future__ import annotations

from typing import Any, Dict

import streamlit as st


# ---------------------------------------------------------------------------
# Regime color mapping
# ---------------------------------------------------------------------------

_REGIME_CSS_CLASS: Dict[str, str] = {
    "Linear": "regime-linear",
    "Stress Accumulation": "regime-stress",
    "Nonlinear Escalation": "regime-nonlinear",
    "Cascade Risk": "regime-cascade",
    "Attractor Lock-in": "regime-attractor",
    "Dissipating": "regime-dissipating",
}


def regime_color_class(regime: str) -> str:
    """Return the CSS class for a given regime state string.

    Args:
        regime: One of the six valid regime states.

    Returns:
        CSS class string such as ``"regime-linear"``.
    """
    return _REGIME_CSS_CLASS.get(regime, "regime-linear")


# ---------------------------------------------------------------------------
# Threshold color mapping
# ---------------------------------------------------------------------------


def threshold_color_class(value: float) -> str:
    """Return the CSS class for a threshold distance value.

    Lower threshold distance = more dangerous.

    Args:
        value: Float in [0, 1]. Lower means closer to threshold.

    Returns:
        One of ``"threshold-safe"``, ``"threshold-advisory"``,
        ``"threshold-critical"``.
    """
    if value >= 0.4:
        return "threshold-safe"
    if value >= 0.2:
        return "threshold-advisory"
    return "threshold-critical"


def damping_color_class(value: float) -> str:
    """Return the CSS class for a damping capacity value.

    Higher damping capacity = safer.

    Args:
        value: Float in [0, 1]. Higher means more damping.

    Returns:
        One of ``"threshold-safe"``, ``"threshold-advisory"``,
        ``"threshold-critical"``.
    """
    if value > 0.5:
        return "threshold-safe"
    if value >= 0.3:
        return "threshold-advisory"
    return "threshold-critical"


# ---------------------------------------------------------------------------
# Progress bar HTML helper
# ---------------------------------------------------------------------------


def _value_bar_html(value: float, color_class: str = "") -> str:
    """Return an HTML progress bar with a numeric label."""
    pct = int(round(value * 100))
    bar_color = {
        "threshold-safe": "#68d391",
        "threshold-advisory": "#f6ad55",
        "threshold-critical": "#fc8181",
    }.get(color_class, "#718096")

    return (
        f'<div style="margin:4px 0 2px 0">'
        f'<div style="background:#2d3748;border-radius:2px;height:4px;overflow:hidden">'
        f'<div style="width:{pct}%;background:{bar_color};height:100%"></div>'
        f'</div>'
        f'</div>'
        f'<div class="metric-value {color_class}">{value:.2f}</div>'
    )


# ---------------------------------------------------------------------------
# Component
# ---------------------------------------------------------------------------


def render_regime_view(regime_data: Dict[str, Any]) -> None:
    """Render the Structural Regime View card.

    Reads the following keys from *regime_data* (all optional — missing values
    degrade gracefully to placeholders):

    - ``current_regime`` – one of the six regime state labels
    - ``threshold_distance`` – float [0, 1]; lower = more dangerous
    - ``transition_volatility`` – float [0, 1]
    - ``reversibility_index`` – float [0, 1]
    - ``dominant_axis`` – string chain, e.g. "military -> sanctions -> energy"
    - ``coupling_asymmetry`` – float [0, 1]
    - ``damping_capacity`` – float [0, 1]; higher = safer
    - ``forecast_implication`` – explanatory paragraph

    Args:
        regime_data: Dict returned by ``GET /api/v1/assessments/{id}/regime``.
    """
    current_regime: str = regime_data.get("current_regime") or "—"
    threshold_distance: float = float(regime_data.get("threshold_distance") or 0.0)
    transition_volatility: float = float(regime_data.get("transition_volatility") or 0.0)
    reversibility_index: float = float(regime_data.get("reversibility_index") or 0.0)
    dom_axis: str = regime_data.get("dominant_axis") or "—"
    coupling_asymmetry: float = float(regime_data.get("coupling_asymmetry") or 0.0)
    damping_capacity: float = float(regime_data.get("damping_capacity") or 0.0)
    forecast_impl: str = regime_data.get("forecast_implication") or ""

    # -----------------------------------------------------------------------
    # Section A — Regime Banner
    # -----------------------------------------------------------------------

    banner_class = regime_color_class(current_regime)

    st.markdown(
        f'<div class="regime-banner {banner_class}">{current_regime}</div>',
        unsafe_allow_html=True,
    )

    if forecast_impl:
        st.markdown(
            f'<div class="aw-callout aw-callout-warn" style="margin-bottom:16px">'
            f'{forecast_impl}'
            f'</div>',
            unsafe_allow_html=True,
        )

    # -----------------------------------------------------------------------
    # Section B — Structural Metrics Grid (3 columns × 2 rows)
    # -----------------------------------------------------------------------

    st.markdown(
        '<div class="metric-label" style="margin:12px 0 8px 0;font-size:0.72rem;'
        'text-transform:uppercase;letter-spacing:0.07em;color:#718096">Structural Metrics</div>',
        unsafe_allow_html=True,
    )

    _col1, _col2, _col3 = st.columns(3)

    # Row 1
    with _col1:
        _td_class = threshold_color_class(threshold_distance)
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-label">Threshold Distance</div>'
            f'{_value_bar_html(threshold_distance, _td_class)}'
            f'</div>',
            unsafe_allow_html=True,
        )

    with _col2:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-label">Transition Volatility</div>'
            f'{_value_bar_html(transition_volatility)}'
            f'</div>',
            unsafe_allow_html=True,
        )

    with _col3:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-label">Reversibility Index</div>'
            f'{_value_bar_html(reversibility_index)}'
            f'</div>',
            unsafe_allow_html=True,
        )

    _col4, _col5, _col6 = st.columns(3)

    # Row 2
    with _col4:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-label">Coupling Asymmetry</div>'
            f'{_value_bar_html(coupling_asymmetry)}'
            f'</div>',
            unsafe_allow_html=True,
        )

    with _col5:
        _damp_class = damping_color_class(damping_capacity)
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-label">Damping Capacity</div>'
            f'{_value_bar_html(damping_capacity, _damp_class)}'
            f'</div>',
            unsafe_allow_html=True,
        )

    with _col6:
        # dominant_axis: displayed as a chain/path
        _axis_parts = [
            p.strip()
            for p in dom_axis.replace("->", " -> ").split(" -> ")
            if p.strip()
        ]
        _axis_html = (
            ' <span class="axis-arrow">&rarr;</span> '.join(
                f'<span class="axis-badge">{p}</span>'
                for p in _axis_parts
            )
            if _axis_parts
            else dom_axis
        )
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-label">Dominant Coupling Axis</div>'
            f'<div style="margin-top:6px;line-height:1.8">{_axis_html}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
