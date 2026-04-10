"""
Forecast Brief Card — EL'druin Intelligence Platform
=====================================================

Provides ``render_forecast_brief(brief_data)`` for rendering the Forecast
Brief card inside the Assessment Workspace.

brief_data keys:
    forecast_posture, time_horizon, confidence, why_it_matters,
    dominant_driver, strengthening_conditions, weakening_conditions,
    invalidation_conditions
"""

from __future__ import annotations

from typing import Dict, List, Any

import streamlit as st


# ---------------------------------------------------------------------------
# Confidence color mapping
# ---------------------------------------------------------------------------

_CONFIDENCE_CSS_CLASS: Dict[str, str] = {
    "High": "confidence-high",
    "Medium": "confidence-medium",
    "Low": "confidence-low",
}

_CONFIDENCE_COLOR: Dict[str, str] = {
    "High": "#4caf7d",
    "Medium": "#e8a742",
    "Low": "#e05c5c",
}


def confidence_css_class(confidence: str) -> str:
    """Return the CSS class name for a given confidence level string.

    Args:
        confidence: One of ``"High"``, ``"Medium"``, or ``"Low"``.

    Returns:
        CSS class string such as ``"confidence-high"``.
    """
    return _CONFIDENCE_CSS_CLASS.get(confidence, "confidence-medium")


def confidence_color(confidence: str) -> str:
    """Return the hex color for a given confidence level string.

    Args:
        confidence: One of ``"High"``, ``"Medium"``, or ``"Low"``.

    Returns:
        Hex color string.
    """
    return _CONFIDENCE_COLOR.get(confidence, "#e8a742")


# ---------------------------------------------------------------------------
# Component
# ---------------------------------------------------------------------------

def render_forecast_brief(brief_data: Dict[str, Any]) -> None:
    """Render the Forecast Brief card.

    Reads the following keys from *brief_data* (all optional — missing values
    degrade gracefully to placeholders):

    - ``forecast_posture`` – primary headline text
    - ``time_horizon`` – compact status indicator
    - ``confidence`` – ``"High"`` | ``"Medium"`` | ``"Low"``
    - ``why_it_matters`` – explanatory paragraph
    - ``dominant_driver`` – labeled field
    - ``strengthening_conditions`` – list of strings
    - ``weakening_conditions`` – list of strings
    - ``invalidation_conditions`` – list of strings

    Args:
        brief_data: Dict returned by ``GET /api/v1/assessments/{id}/brief``.
    """
    posture: str = brief_data.get("forecast_posture") or "—"
    horizon: str = brief_data.get("time_horizon") or "—"
    conf: str = brief_data.get("confidence") or "—"
    why: str = brief_data.get("why_it_matters") or ""
    driver: str = brief_data.get("dominant_driver") or "—"
    strengthen: List[str] = brief_data.get("strengthening_conditions") or []
    weaken: List[str] = brief_data.get("weakening_conditions") or []
    invalidate: List[str] = brief_data.get("invalidation_conditions") or []

    conf_color = confidence_color(conf)

    # --- Posture headline + compact status row ---
    st.markdown(
        f'<div class="brief-label">Forecast Posture</div>'
        f'<div class="brief-posture">{posture}</div>',
        unsafe_allow_html=True,
    )

    _c1, _c2, _spacer = st.columns([2, 2, 4])

    with _c1:
        st.markdown(
            f'<div class="aw-metric-card" style="padding:8px 12px">'
            f'<div class="brief-label">Time Horizon</div>'
            f'<div class="brief-value" style="font-size:0.88rem;font-weight:600">{horizon}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with _c2:
        st.markdown(
            f'<div class="aw-metric-card" style="padding:8px 12px">'
            f'<div class="brief-label">Confidence</div>'
            f'<div class="{confidence_css_class(conf)}">{conf}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # --- Why it matters ---
    if why:
        st.markdown(
            f'<div class="aw-callout" style="margin-top:12px">'
            f'<span class="brief-label">Why it matters</span><br>'
            f'<span class="brief-value">{why}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # --- Dominant driver ---
    st.markdown(
        f'<div class="brief-label" style="margin-top:12px">Dominant Driver</div>'
        f'<div class="aw-card-compact brief-value">{driver}</div>',
        unsafe_allow_html=True,
    )

    # --- Conditions ---
    if strengthen or weaken or invalidate:
        _left, _right = st.columns(2)

        with _left:
            if strengthen:
                _sc_html = "".join(
                    f'<div class="condition-item">'
                    f'<span style="color:#4caf7d;font-size:9px;margin-right:5px">&#9658;</span>{c}'
                    f'</div>'
                    for c in strengthen
                )
                st.markdown(
                    f'<div class="brief-label" style="margin-top:10px">Strengthening Conditions</div>'
                    f'<div class="aw-card-compact">{_sc_html}</div>',
                    unsafe_allow_html=True,
                )

            if invalidate:
                _ic_html = "".join(
                    f'<div class="condition-item">'
                    f'<span style="color:#7A8FA6;font-size:9px;margin-right:5px">&#9658;</span>{c}'
                    f'</div>'
                    for c in invalidate
                )
                st.markdown(
                    f'<div class="brief-label" style="margin-top:10px">Invalidation Conditions</div>'
                    f'<div class="aw-card-compact">{_ic_html}</div>',
                    unsafe_allow_html=True,
                )

        with _right:
            if weaken:
                _wc_html = "".join(
                    f'<div class="condition-item">'
                    f'<span style="color:#e8a742;font-size:9px;margin-right:5px">&#9658;</span>{c}'
                    f'</div>'
                    for c in weaken
                )
                st.markdown(
                    f'<div class="brief-label" style="margin-top:10px">Weakening Conditions</div>'
                    f'<div class="aw-card-compact">{_wc_html}</div>',
                    unsafe_allow_html=True,
                )
    else:
        st.markdown(
            '<div style="font-size:11px;color:#7A8FA6;margin-top:10px;font-style:italic">'
            'No conditions recorded for this assessment.'
            '</div>',
            unsafe_allow_html=True,
        )
