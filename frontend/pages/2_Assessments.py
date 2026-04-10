"""
Assessment Workspace – EL-DRUIN Intelligence Platform
======================================================

Primary product surface for EL'druin's nonlinear intelligence operating system.
Provides the Assessment list sidebar and three-column workspace layout with
seven intelligence tabs: Brief, Regime, Triggers, Propagation, Attractors,
Evidence, Trace.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Any, Dict, List

import streamlit as st

_FRONTEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FRONTEND_DIR not in sys.path:
    sys.path.insert(0, _FRONTEND_DIR)

st.set_page_config(
    page_title="Assessments – EL-DRUIN",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

from utils.api_client import (  # noqa: E402
    get_assessments,
    get_assessment,
    get_brief,
    get_regime,
    get_triggers,
    get_attractors,
    get_propagation,
    get_delta,
    get_evidence,
    get_coupling,
)
from components.forecast_brief import render_forecast_brief  # noqa: E402
from components.regime_view import render_regime_view  # noqa: E402

try:
    from components.sidebar import render_sidebar_navigation  # noqa: E402
    st.session_state["current_page"] = "Assessments"
    render_sidebar_navigation(is_subpage=True)
except Exception:
    pass

# ---------------------------------------------------------------------------
# Design constants
# ---------------------------------------------------------------------------

_REGIME_COLORS: Dict[str, str] = {
    "Linear": "#6b7280",
    "Stress Accumulation": "#92400e",
    "Nonlinear Escalation": "#9a3412",
    "Cascade Risk": "#7f1d1d",
    "Attractor Lock-in": "#4c0519",
    "Dissipating": "#14532d",
}

_JUMP_COLORS: Dict[str, str] = {
    "Low": "#6b7280",
    "Medium": "#92400e",
    "High": "#9a3412",
    "Critical": "#7f1d1d",
}

_QUALITY_COLORS: Dict[str, str] = {
    "Low": "#6b7280",
    "Medium": "#92400e",
    "High": "#1d4ed8",
    "Primary": "#14532d",
}

_STATUS_LABELS: Dict[str, str] = {
    "active": "Active",
    "review_required": "Review Required",
    "draft": "Draft",
    "archived": "Archived",
}

_TYPE_LABELS: Dict[str, str] = {
    "event_driven": "Event-driven",
    "structural_watch": "Structural Watch",
    "region_sector_watch": "Region/Sector Watch",
    "custom_scenario": "Custom Scenario",
}

# Amplification factor display: amplification_factor ∈ [0,1] is mapped to a
# ×multiplier for analyst readability. Scale 5.0 maps factor=0.64 → ×3.2.
_AMP_DISPLAY_SCALE: float = 5.0

# Maximum number of characters shown for a propagation event in the inline
# Propagation Sequence panel (keeps each row to a single readable line).
_MAX_EVENT_PREVIEW_LENGTH: int = 60

# ---------------------------------------------------------------------------
# Inline CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
.aw-page-label {
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: #7A8FA6;
    margin-bottom: 2px;
}
.aw-section-title {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #7A8FA6;
    margin: 12px 0 6px 0;
}
.aw-card {
    background: #162030;
    border: 1px solid #2D3F52;
    border-radius: 3px;
    padding: 14px 16px;
    margin-bottom: 10px;
}
.aw-card-compact {
    background: #162030;
    border: 1px solid #2D3F52;
    border-radius: 3px;
    padding: 10px 12px;
    margin-bottom: 8px;
}
.aw-list-item {
    background: #162030;
    border: 1px solid #2D3F52;
    border-radius: 3px;
    padding: 12px 14px;
    margin-bottom: 8px;
}
.aw-list-item-title {
    font-size: 13px;
    font-weight: 600;
    color: #D4DDE6;
    margin-bottom: 4px;
    line-height: 1.4;
}
.aw-badge {
    display: inline-block;
    font-size: 10px;
    font-weight: 600;
    padding: 2px 7px;
    border-radius: 2px;
    margin-right: 4px;
    text-transform: uppercase;
    letter-spacing: 0.4px;
}
.aw-badge-type {
    background: #1e2d3d;
    color: #7A8FA6;
    border: 1px solid #2D3F52;
}
.aw-badge-status-active {
    background: #14532d22;
    color: #4ade80;
    border: 1px solid #14532d;
}
.aw-badge-status-review {
    background: #92400e22;
    color: #fbbf24;
    border: 1px solid #92400e;
}
.aw-badge-status-draft {
    background: #1e2d3d;
    color: #7A8FA6;
    border: 1px solid #2D3F52;
}
.aw-badge-status-archived {
    background: #1e2d3d;
    color: #4b5563;
    border: 1px solid #2D3F52;
}
.aw-regime-badge {
    display: inline-block;
    font-size: 12px;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 3px;
    letter-spacing: 0.3px;
}
.aw-callout {
    background: #1e2d3d;
    border-left: 3px solid #4A6FA5;
    border-radius: 0 3px 3px 0;
    padding: 10px 14px;
    margin: 8px 0;
    font-size: 13px;
    color: #D4DDE6;
    line-height: 1.5;
}
.aw-callout-warn {
    border-left-color: #92400e;
}
.aw-metric-card {
    background: #162030;
    border: 1px solid #2D3F52;
    border-radius: 3px;
    padding: 10px 12px;
    text-align: center;
}
.aw-metric-label {
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: #7A8FA6;
    margin-bottom: 4px;
}
.aw-metric-value {
    font-size: 20px;
    font-weight: 700;
    color: #D4DDE6;
    line-height: 1.2;
}
.aw-condition-item {
    font-size: 12px;
    color: #D4DDE6;
    padding: 3px 0;
    line-height: 1.4;
}
.aw-domain-badge {
    display: inline-block;
    font-size: 10px;
    padding: 1px 6px;
    border-radius: 2px;
    margin: 1px 2px;
    background: #1e2d3d;
    color: #7A8FA6;
    border: 1px solid #2D3F52;
}
.aw-divider {
    height: 1px;
    background: #2D3F52;
    margin: 10px 0;
}
.aw-topbar-title {
    font-size: 15px;
    font-weight: 700;
    color: #D4DDE6;
    line-height: 1.3;
}
.aw-step {
    display: flex;
    align-items: flex-start;
    margin-bottom: 8px;
}
.aw-step-domain {
    font-size: 10px;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 2px;
    background: #1e2d3d;
    color: #C8A84B;
    border: 1px solid #2D3F52;
    margin-right: 8px;
    white-space: nowrap;
}
.aw-step-event {
    font-size: 12px;
    color: #D4DDE6;
    line-height: 1.4;
}
.aw-alert-count {
    display: inline-block;
    background: #7f1d1d;
    color: #fca5a5;
    font-size: 11px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 10px;
    border: 1px solid #991b1b;
}
/* Forecast Brief card styles */
.brief-posture { font-size: 1.4rem; font-weight: 600; color: #e8e8e8; margin: 4px 0 10px 0; }
.brief-label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.08em; color: #888; }
.brief-value { font-size: 0.95rem; color: #c8c8c8; }
.confidence-high { color: #4caf7d; font-weight: 600; }
.confidence-medium { color: #e8a742; font-weight: 600; }
.confidence-low { color: #e05c5c; font-weight: 600; }
.condition-item { padding: 2px 0; color: #b0b0b0; font-size: 0.88rem; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _fmt_ts(ts_str: str) -> str:
    """Format an ISO timestamp string to a short display string."""
    if not ts_str:
        return "—"
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y %H:%M UTC")
    except Exception:
        return ts_str[:16]


def _status_badge_html(status: str) -> str:
    label = _STATUS_LABELS.get(status, status.replace("_", " ").title())
    cls = {
        "active": "aw-badge-status-active",
        "review_required": "aw-badge-status-review",
        "draft": "aw-badge-status-draft",
        "archived": "aw-badge-status-archived",
    }.get(status, "aw-badge-status-draft")
    return f'<span class="aw-badge {cls}">{label}</span>'


def _type_badge_html(assessment_type: str) -> str:
    label = _TYPE_LABELS.get(assessment_type, assessment_type.replace("_", " ").title())
    return f'<span class="aw-badge aw-badge-type">{label}</span>'


def _domain_badges_html(tags: List[str]) -> str:
    return " ".join(f'<span class="aw-domain-badge">{t}</span>' for t in tags)


def _jump_color(jump: str) -> str:
    return _JUMP_COLORS.get(jump, "#6b7280")


def _quality_color(quality: str) -> str:
    return _QUALITY_COLORS.get(quality, "#6b7280")


# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

if "selected_assessment_id" not in st.session_state:
    st.session_state.selected_assessment_id = None
if "selected_tab" not in st.session_state:
    st.session_state.selected_tab = "Brief"
if "selected_trigger" not in st.session_state:
    st.session_state.selected_trigger = None
if "selected_attractor" not in st.session_state:
    st.session_state.selected_attractor = None

# Allow assessment_id to be pre-selected via query parameter
_qp = st.query_params.get("assessment_id")
if _qp and not st.session_state.selected_assessment_id:
    st.session_state.selected_assessment_id = _qp


# ---------------------------------------------------------------------------
# Page label
# ---------------------------------------------------------------------------

st.markdown(
    '<div class="aw-page-label">INTELLIGENCE ASSESSMENTS — WORKSPACE</div>',
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Fetch assessment list
# ---------------------------------------------------------------------------

_assessments: List[Dict[str, Any]] = get_assessments()

# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------

if not _assessments:
    st.markdown("""
    <div style="max-width:480px;margin:80px auto;text-align:center;">
        <div style="font-size:13px;color:#7A8FA6;margin-bottom:16px;line-height:1.6">
            No active assessments. Connect your backend or compose a new assessment.
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Compose Assessment", key="empty_state_compose"):
        st.info("Compose Assessment: coming in next release")
    st.stop()


# ---------------------------------------------------------------------------
# Assessment list view (no assessment selected)
# ---------------------------------------------------------------------------

if not st.session_state.selected_assessment_id:
    st.markdown("## Assessments")
    st.markdown('<div class="aw-divider"></div>', unsafe_allow_html=True)

    for _a in _assessments:
        _aid = _a.get("assessment_id", "")
        _title = _a.get("title", "—")
        _atype = _a.get("assessment_type", "")
        _status = _a.get("status", "")
        _updated = _fmt_ts(_a.get("updated_at", ""))
        _regime = _a.get("last_regime") or ""
        _regime_color = _REGIME_COLORS.get(_regime, "#6b7280")
        _alerts = _a.get("alert_count", 0)

        _regime_html = (
            f'<span style="font-size:10px;font-weight:600;'
            f'color:{_regime_color};margin-left:4px">{_regime}</span>'
            if _regime else ""
        )
        _alert_html = (
            f'<span class="aw-alert-count" style="float:right">{_alerts} alerts</span>'
            if _alerts else ""
        )

        st.markdown(
            f'<div class="aw-list-item">'
            f'<div class="aw-list-item-title">{_alert_html}{_title}</div>'
            f'<div style="margin:4px 0">'
            f'{_type_badge_html(_atype)} {_status_badge_html(_status)} {_regime_html}'
            f'</div>'
            f'<div style="font-size:10px;color:#7A8FA6;margin-top:4px">Updated {_updated}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button("Open workspace", key=f"open_{_aid}"):
            st.session_state.selected_assessment_id = _aid
            st.rerun()

    st.stop()


# ---------------------------------------------------------------------------
# Workspace view — load selected assessment data
# ---------------------------------------------------------------------------

_assessment_id: str = st.session_state.selected_assessment_id
_assessment: Dict[str, Any] = get_assessment(_assessment_id)

_title = _assessment.get("title", "—")
_atype = _assessment.get("assessment_type", "")
_status = _assessment.get("status", "")
_updated = _fmt_ts(_assessment.get("updated_at", ""))
_alerts = _assessment.get("alert_count", 0)
_region_tags: List[str] = _assessment.get("region_tags", [])
_domain_tags: List[str] = _assessment.get("domain_tags", [])
_analyst_notes = _assessment.get("analyst_notes") or ""

# ---------------------------------------------------------------------------
# Top bar
# ---------------------------------------------------------------------------

_tb1, _tb2, _tb3, _tb4, _tb5 = st.columns([5, 2, 2, 1, 2])

with _tb1:
    st.markdown(
        f'<div class="aw-topbar-title">{_title}</div>'
        f'<div style="margin-top:4px">'
        f'{_domain_badges_html(_region_tags + _domain_tags)}'
        f'</div>',
        unsafe_allow_html=True,
    )

with _tb2:
    st.markdown(
        f'<div class="aw-metric-label">Status</div>'
        f'{_status_badge_html(_status)}',
        unsafe_allow_html=True,
    )

with _tb3:
    st.markdown(
        f'<div class="aw-metric-label">Last Updated</div>'
        f'<div style="font-size:12px;color:#D4DDE6">{_updated}</div>',
        unsafe_allow_html=True,
    )

with _tb4:
    if _alerts:
        st.markdown(
            f'<span class="aw-alert-count">{_alerts}</span>',
            unsafe_allow_html=True,
        )

with _tb5:
    _c5a, _c5b = st.columns(2)
    with _c5a:
        if st.button("Update Assessment", key="topbar_update", type="primary"):
            st.info("Update Assessment: triggers a new assessment run")
    with _c5b:
        if st.button("Back", key="topbar_back"):
            st.session_state.selected_assessment_id = None
            st.rerun()

st.markdown('<div class="aw-divider"></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Three-column workspace
# ---------------------------------------------------------------------------

_left_col, _center_col, _right_col = st.columns([1, 2, 1])


# ===========================================================================
# LEFT COLUMN — Context panel
# ===========================================================================

with _left_col:
    st.markdown(
        f'<div class="aw-section-title">Assessment</div>'
        f'<div class="aw-card">'
        f'<div style="font-size:13px;font-weight:600;color:#D4DDE6;margin-bottom:6px">{_title}</div>'
        f'<div style="margin-bottom:6px">{_type_badge_html(_atype)} {_status_badge_html(_status)}</div>'
        f'<div style="font-size:10px;color:#7A8FA6">Updated {_updated}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if _region_tags or _domain_tags:
        st.markdown(
            f'<div class="aw-section-title">Region / Domain</div>'
            f'<div style="margin-bottom:10px">'
            f'{_domain_badges_html(_region_tags + _domain_tags)}'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="aw-section-title">Tracked Entities</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="aw-card-compact">'
        '<div style="font-size:11px;color:#7A8FA6;font-style:italic">'
        'Entity tracking panel — coming in next release'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="aw-section-title">Watch Indicators</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="aw-card-compact">'
        '<div style="font-size:11px;color:#7A8FA6;font-style:italic">'
        'Watch indicators — coming in next release'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="aw-section-title">Update History</div>', unsafe_allow_html=True)
    _history_items = [
        ("2026-04-09T18:00:00Z", "Regime updated to Nonlinear Escalation"),
        ("2026-04-08T12:30:00Z", "Four new evidence items incorporated"),
        ("2026-04-07T09:15:00Z", "Trigger ranking revised"),
    ]
    for _ts_raw, _desc in _history_items:
        st.markdown(
            f'<div class="aw-card-compact">'
            f'<div style="font-size:9px;color:#7A8FA6;margin-bottom:3px">{_fmt_ts(_ts_raw)}</div>'
            f'<div style="font-size:12px;color:#D4DDE6">{_desc}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if _analyst_notes:
        st.markdown('<div class="aw-section-title">Analyst Notes</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="aw-callout">{_analyst_notes}</div>',
            unsafe_allow_html=True,
        )


# ===========================================================================
# Pre-fetch all structural data (used in both inline panels and tabs)
# ===========================================================================

_regime_data = get_regime(_assessment_id)
_delta_data = get_delta(_assessment_id)
_triggers_data = get_triggers(_assessment_id)
_attract_data = get_attractors(_assessment_id)
_prop_data = get_propagation(_assessment_id)
_coupling_data = get_coupling(_assessment_id)


# ===========================================================================
# CENTER COLUMN — Inline structural panels + tabbed detail
# ===========================================================================

with _center_col:

    # -----------------------------------------------------------------------
    # Panel 1 — STRUCTURAL REGIME
    # -----------------------------------------------------------------------
    _regime_name = _regime_data.get("current_regime", "—") if isinstance(_regime_data, dict) else "—"
    _regime_thresh = float(_regime_data.get("threshold_distance", 0)) if isinstance(_regime_data, dict) else 0.0
    _regime_vol = float(_regime_data.get("transition_volatility", 0)) if isinstance(_regime_data, dict) else 0.0
    _regime_rev = float(_regime_data.get("reversibility_index", 0)) if isinstance(_regime_data, dict) else 0.0
    _regime_color = _REGIME_COLORS.get(_regime_name, "#6b7280")
    _thresh_pct = int(round(_regime_thresh * 100))
    _thresh_bar_fill = int(round((1 - _regime_thresh) * 100))
    _vol_label = "High" if _regime_vol >= 0.6 else ("Medium" if _regime_vol >= 0.35 else "Low")
    _rev_label = "Low" if _regime_rev <= 0.35 else ("Medium" if _regime_rev <= 0.65 else "High")
    _vol_color = {"High": "#9a3412", "Medium": "#92400e", "Low": "#14532d"}.get(_vol_label, "#6b7280")
    _rev_color = {"Low": "#9a3412", "Medium": "#92400e", "High": "#14532d"}.get(_rev_label, "#6b7280")

    st.markdown(
        f'<div class="aw-section-title">STRUCTURAL REGIME</div>'
        f'<div class="aw-card" style="border-left:3px solid {_regime_color}">'
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">'
        f'<span class="aw-regime-badge" style="background:{_regime_color}22;color:{_regime_color};'
        f'border:1px solid {_regime_color}55">{_regime_name}</span>'
        f'<span style="font-size:10px;color:#7A8FA6">Threshold proximity</span>'
        f'<div style="flex:1;background:#2D3F52;border-radius:2px;height:6px;overflow:hidden">'
        f'<div style="width:{_thresh_bar_fill}%;background:{_regime_color};height:100%"></div>'
        f'</div>'
        f'<span style="font-size:11px;font-weight:700;color:{_regime_color}">{_thresh_pct}%</span>'
        f'</div>'
        f'<div style="display:flex;gap:16px">'
        f'<span style="font-size:10px;color:#7A8FA6">Volatility: <span style="color:{_vol_color};font-weight:600">{_vol_label}</span></span>'
        f'<span style="font-size:10px;color:#7A8FA6">Reversibility: <span style="color:{_rev_color};font-weight:600">{_rev_label}</span></span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # -----------------------------------------------------------------------
    # Panel 2 — DELTA SINCE PRIOR UPDATE
    # -----------------------------------------------------------------------
    _delta_summary = _delta_data.get("summary", "") if isinstance(_delta_data, dict) else ""
    _is_first_run = "First assessment run" in _delta_summary or "No prior state" in _delta_summary

    if _is_first_run:
        st.markdown(
            '<div class="aw-section-title">DELTA SINCE PRIOR UPDATE</div>'
            '<div class="aw-card-compact">'
            '<div class="aw-callout" style="margin:0;font-size:12px;color:#7A8FA6">'
            'No baseline — first assessment'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        _reg_changed = _delta_data.get("regime_changed", False) if isinstance(_delta_data, dict) else False
        _thresh_dir = _delta_data.get("threshold_direction", "stable") if isinstance(_delta_data, dict) else "stable"
        _trigger_changes = _delta_data.get("trigger_ranking_changes", []) if isinstance(_delta_data, dict) else []
        _attract_changes = _delta_data.get("attractor_pull_changes", []) if isinstance(_delta_data, dict) else []
        _new_ev_count = _delta_data.get("new_evidence_count", 0) if isinstance(_delta_data, dict) else 0

        _reg_delta_color = "#9a3412" if _reg_changed else "#14532d"
        _reg_delta_label = "Regime shifted" if _reg_changed else "Regime stable"

        _thresh_delta_color = {
            "narrowing": "#9a3412", "widening": "#14532d", "stable": "#6b7280"
        }.get(_thresh_dir, "#6b7280")
        _thresh_delta_arrow = {"narrowing": "▼", "widening": "▲", "stable": "→"}.get(_thresh_dir, "→")
        _thresh_pct_delta = abs(
            float(_delta_data.get("damping_capacity_delta", 0)) if isinstance(_delta_data, dict) else 0
        )
        _thresh_dir_label = (
            f'{_thresh_delta_arrow} {int(_thresh_pct_delta * 100)}% {_thresh_dir}'
            if _thresh_pct_delta > 0
            else f'{_thresh_delta_arrow} {_thresh_dir}'
        )

        # Top trigger rank shift
        _trigger_shift_html = ""
        if _trigger_changes:
            _tc = _trigger_changes[0]
            if isinstance(_tc, dict):
                _prev = _tc.get("previous", "")
                _curr = _tc.get("current", "")
                _tname = _tc.get("field", "Top trigger")
                if _prev != _curr and _prev != "" and _curr != "":
                    _trigger_shift_html = (
                        f'<span style="font-size:11px;color:#7A8FA6">'
                        f'{_tname}: <span style="color:#D4DDE6;font-weight:600">#{_prev} → #{_curr}</span>'
                        f'</span>'
                    )

        # Top attractor pull delta
        _attractor_shift_html = ""
        if _attract_changes:
            _ac = _attract_changes[0]
            if isinstance(_ac, dict):
                _a_prev = float(_ac.get("previous", 0))
                _a_curr = float(_ac.get("current", 0))
                _a_delta = _a_curr - _a_prev
                _a_name = _ac.get("field", "Top attractor")
                _a_color = "#9a3412" if _a_delta > 0 else "#14532d" if _a_delta < 0 else "#6b7280"
                _a_delta_str = f"{_a_delta:+.2f}"  # :+ already includes sign
                _attractor_shift_html = (
                    f'<span style="font-size:11px;color:#7A8FA6">'
                    f'Pull strength: <span style="color:{_a_color};font-weight:600">{_a_delta_str}</span>'
                    f'</span>'
                )

        _new_ev_html = (
            f'<span class="aw-badge" style="background:#1e2d3d;color:#7A8FA6;border:1px solid #2D3F52">'
            f'New evidence: {_new_ev_count}'
            f'</span>'
        ) if _new_ev_count else ""

        st.markdown(
            f'<div class="aw-section-title">DELTA SINCE PRIOR UPDATE</div>'
            f'<div class="aw-card-compact">'
            f'<div style="display:flex;gap:12px;flex-wrap:wrap;align-items:center">'
            f'<span class="aw-badge" style="background:{_reg_delta_color}22;color:{_reg_delta_color};'
            f'border:1px solid {_reg_delta_color}44">{_reg_delta_label}</span>'
            f'<span style="font-size:11px;color:#7A8FA6">Threshold: '
            f'<span style="color:{_thresh_delta_color};font-weight:600">{_thresh_dir_label}</span>'
            f'</span>'
            f'{_trigger_shift_html}'
            f'{_attractor_shift_html}'
            f'{_new_ev_html}'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # -----------------------------------------------------------------------
    # Panel 3 — TRIGGER AMPLIFICATION BOARD (top 3–5)
    # -----------------------------------------------------------------------
    _triggers_list = _triggers_data.get("triggers", []) if isinstance(_triggers_data, dict) else []
    _sorted_triggers_inline = sorted(
        _triggers_list,
        key=lambda x: float(x.get("amplification_factor", 0)),
        reverse=True,
    )[:5]

    if not _sorted_triggers_inline:
        _trig_board_html = (
            '<div class="aw-callout aw-callout-warn" style="font-size:12px">'
            'Insufficient structural data — no triggers computed for this assessment.'
            '</div>'
        )
    else:
        _trig_rows = ""
        for _ti, _t in enumerate(_sorted_triggers_inline, 1):
            _amp = float(_t.get("amplification_factor", 0))
            _domains = _t.get("impacted_domains", [])
            _amp_x = f"×{_amp * _AMP_DISPLAY_SCALE:.1f}"
            _trend_arrow = "↑" if _amp >= 0.7 else ("→" if _amp >= 0.4 else "↓")
            _trend_color = "#9a3412" if _amp >= 0.7 else ("#92400e" if _amp >= 0.4 else "#6b7280")
            # Coupling label from top-2 impacted domains
            if len(_domains) >= 2:
                _coupling_label = f"{_domains[0].title()} ↔ {_domains[1].title()}"
            elif len(_domains) == 1:
                _coupling_label = f"{_domains[0].title()} coupling"
            else:
                _coupling_label = ""
            _coupling_html = (
                f'<span style="font-size:9px;color:#4A6FA5;margin-left:4px">{_coupling_label}</span>'
                if _coupling_label else ""
            )
            _trig_rows += (
                f'<div style="display:flex;align-items:center;gap:8px;padding:5px 0;'
                f'border-bottom:1px solid #2D3F52">'
                f'<span style="font-size:10px;color:#7A8FA6;min-width:14px">{_ti}.</span>'
                f'<span style="font-size:12px;color:#D4DDE6;flex:1">'
                f'{_t.get("name", "—")}'
                f'{_coupling_html}'
                f'</span>'
                f'<span style="font-size:13px;font-weight:700;color:#C8A84B;min-width:42px;text-align:right">{_amp_x}</span>'
                f'<span style="font-size:12px;color:{_trend_color}">{_trend_arrow}</span>'
                f'</div>'
            )
        _trig_board_html = _trig_rows

    st.markdown(
        f'<div class="aw-section-title">TRIGGER AMPLIFICATION</div>'
        f'<div class="aw-card-compact">'
        f'{_trig_board_html}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # -----------------------------------------------------------------------
    # Panel 4 — ATTRACTOR MAP (top 2, relative pull bars)
    # -----------------------------------------------------------------------
    _attract_list = _attract_data.get("attractors", []) if isinstance(_attract_data, dict) else []
    _ranked_attract_inline = sorted(
        _attract_list,
        key=lambda x: float(x.get("pull_strength", 0)),
        reverse=True,
    )[:2]

    _max_pull = max((float(a.get("pull_strength", 0)) for a in _ranked_attract_inline), default=1.0)
    _max_pull = _max_pull if _max_pull > 0 else 1.0

    _attr_rows = ""
    for _ai, _attr in enumerate(_ranked_attract_inline, 1):
        _pull = float(_attr.get("pull_strength", 0))
        _trend = _attr.get("trend", "stable")
        _trend_arrow = {"up": "↑", "down": "↓", "stable": "→"}.get(_trend, "→")
        _trend_color = {"up": "#9a3412", "down": "#14532d", "stable": "#6b7280"}.get(_trend, "#6b7280")
        _bar_fill_pct = int(round((_pull / _max_pull) * 100))
        _attr_rows += (
            f'<div style="margin-bottom:8px">'
            f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:3px">'
            f'<span style="font-size:10px;color:#7A8FA6;min-width:14px">{_ai}.</span>'
            f'<span style="font-size:12px;color:#D4DDE6;flex:1">{_attr.get("name", "—")}</span>'
            f'<span style="font-size:12px;color:{_trend_color}">{_trend_arrow}</span>'
            f'</div>'
            f'<div style="background:#2D3F52;border-radius:2px;height:5px;overflow:hidden;margin-left:20px;max-width:160px">'
            f'<div style="width:{_bar_fill_pct}%;background:#4A9FD4;height:100%"></div>'
            f'</div>'
            f'<div style="font-size:9px;color:#7A8FA6;margin-left:20px;margin-top:2px">Pull Strength</div>'
            f'</div>'
        )

    _attr_rows_empty = '<div style="font-size:11px;color:#7A8FA6;font-style:italic">No attractor data available</div>'
    st.markdown(
        f'<div class="aw-section-title">ATTRACTOR PULL</div>'
        f'<div class="aw-card-compact">'
        f'{_attr_rows if _attr_rows else _attr_rows_empty}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # -----------------------------------------------------------------------
    # Panel 5 — PROPAGATION SEQUENCE (compact 3-step preview)
    # -----------------------------------------------------------------------
    _sequence = _prop_data.get("sequence", []) if isinstance(_prop_data, dict) else []
    _sorted_seq = sorted(_sequence, key=lambda x: x.get("step", 0))[:3]

    _prop_preview_html = ""
    for _si, _step in enumerate(_sorted_seq):
        _domain = _step.get("domain", "—")
        _tbucket = _step.get("time_bucket", "T+?")
        _arrow = ' <span style="font-size:11px;color:#4A6FA5">→</span> ' if _si < len(_sorted_seq) - 1 else ""
        _prop_preview_html += (
            f'<span style="display:inline-block;margin-right:2px">'
            f'<span style="font-size:8px;color:#4A6FA5;display:block;text-align:center">{_tbucket}</span>'
            f'<span class="aw-step-domain">{_domain}</span>'
            f'</span>'
            f'{_arrow}'
        )

    _prop_html_empty = '<div style="font-size:11px;color:#7A8FA6;font-style:italic">No propagation data</div>'
    st.markdown(
        f'<div class="aw-section-title">PROPAGATION SEQUENCE</div>'
        f'<div class="aw-card-compact">'
        f'<div style="display:flex;align-items:flex-end;gap:2px;flex-wrap:wrap">'
        f'{_prop_preview_html if _prop_preview_html else _prop_html_empty}'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="aw-divider"></div>', unsafe_allow_html=True)

    # -----------------------------------------------------------------------
    # Tabbed detail view
    # -----------------------------------------------------------------------
    _tabs = st.tabs(["Brief", "Regime", "Triggers", "Attractors", "Propagation", "Coupling", "Evidence", "Trace"])

    # -----------------------------------------------------------------------
    # Tab: Brief
    # -----------------------------------------------------------------------
    with _tabs[0]:
        _brief = get_brief(_assessment_id)
        if isinstance(_brief, dict) and "error" in _brief:
            st.error(f"Could not load brief: {_brief['error']}")
        elif _brief:
            render_forecast_brief(_brief)
        else:
            st.markdown(
                '<div style="font-size:12px;color:#7A8FA6;font-style:italic;margin-top:20px">'
                "Brief data unavailable for this assessment."
                "</div>",
                unsafe_allow_html=True,
            )

    # -----------------------------------------------------------------------
    # Tab: Regime
    # -----------------------------------------------------------------------
    with _tabs[1]:
        if isinstance(_regime_data, dict) and "error" in _regime_data:
            st.error(f"Could not load regime data: {_regime_data['error']}")
        elif _regime_data:
            render_regime_view(_regime_data)
        else:
            st.markdown(
                '<div style="font-size:12px;color:#7A8FA6;font-style:italic;margin-top:20px">'
                "Regime data unavailable for this assessment."
                "</div>",
                unsafe_allow_html=True,
            )

    # -----------------------------------------------------------------------
    # Tab: Triggers
    # -----------------------------------------------------------------------
    with _tabs[2]:
        _triggers_list_tab = _triggers_data.get("triggers", []) if isinstance(_triggers_data, dict) else []

        st.markdown(
            '<div class="aw-section-title">Trigger Amplification Board</div>'
            '<div style="font-size:10px;color:#7A8FA6;margin-bottom:8px">'
            'Sorted by amplification factor (highest first)'
            '</div>',
            unsafe_allow_html=True,
        )

        if not _triggers_list_tab:
            st.markdown(
                '<div class="aw-callout aw-callout-warn">'
                'Insufficient structural data — no triggers computed for this assessment.'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            _sorted_triggers = sorted(
                _triggers_list_tab,
                key=lambda x: float(x.get("amplification_factor", 0)),
                reverse=True,
            )

            for _t in _sorted_triggers:
                _tname = _t.get("name", "—")
                _amp = float(_t.get("amplification_factor", 0))
                _amp_x = f"×{_amp * _AMP_DISPLAY_SCALE:.1f}"
                _jump = _t.get("jump_potential", "Low")
                _domains = _t.get("impacted_domains", [])
                _lag = _t.get("expected_lag_hours", 0)
                _tconf = float(_t.get("confidence", 0))
                _signals = _t.get("watch_signals", [])
                _tdamping = _t.get("damping_opportunities", [])
                _trend_arrow = "↑" if _amp >= 0.7 else ("→" if _amp >= 0.4 else "↓")

                _jcolor = _jump_color(_jump)
                _domains_html = " ".join(
                    f'<span class="aw-domain-badge">{d}</span>' for d in _domains
                )
                _jump_html = (
                    f'<span class="aw-badge" style="background:{_jcolor}22;'
                    f'color:{_jcolor};border:1px solid {_jcolor}44">{_jump}</span>'
                )
                # Coupling score from top-2 domains
                if len(_domains) >= 2:
                    _coup_label = f"{_domains[0].title()} ↔ {_domains[1].title()}"
                elif len(_domains) == 1:
                    _coup_label = f"{_domains[0].title()} coupling"
                else:
                    _coup_label = ""

                with st.expander(
                    f"{_tname}  {_amp_x}  {_trend_arrow}",
                    expanded=False,
                ):
                    _t1, _t2, _t3 = st.columns([2, 1, 1])
                    with _t1:
                        st.markdown(
                            f'<div class="aw-metric-label">Impacted Domains</div>'
                            f'<div style="margin-top:4px">{_domains_html}</div>'
                            + (
                                f'<div style="font-size:10px;color:#4A6FA5;margin-top:4px">{_coup_label}</div>'
                                if _coup_label else ""
                            ),
                            unsafe_allow_html=True,
                        )
                    with _t2:
                        st.markdown(
                            f'<div class="aw-metric-label">Amplification</div>'
                            f'<div style="font-size:20px;font-weight:700;color:#C8A84B">{_amp_x}</div>'
                            f'<div class="aw-metric-label" style="margin-top:6px">Jump Potential</div>'
                            f'{_jump_html}',
                            unsafe_allow_html=True,
                        )
                    with _t3:
                        st.markdown(
                            f'<div class="aw-metric-label">Expected Lag</div>'
                            f'<div style="font-size:16px;font-weight:700;color:#D4DDE6">{_lag}h</div>'
                            f'<div class="aw-metric-label" style="margin-top:6px">Confidence</div>'
                            f'<div style="font-size:16px;font-weight:700;color:#D4DDE6">{_tconf:.0%}</div>',
                            unsafe_allow_html=True,
                        )

                    st.markdown('<div class="aw-divider"></div>', unsafe_allow_html=True)

                    _s1, _s2 = st.columns(2)
                    with _s1:
                        st.markdown('<div class="aw-metric-label">Watch Signals</div>', unsafe_allow_html=True)
                        if _signals:
                            _sig_html = "".join(
                                f'<div class="aw-condition-item">'
                                f'<span style="color:#7A8FA6;margin-right:5px">–</span>{s}'
                                f'</div>'
                                for s in _signals
                            )
                            st.markdown(_sig_html, unsafe_allow_html=True)
                    with _s2:
                        st.markdown('<div class="aw-metric-label">Damping Opportunities</div>', unsafe_allow_html=True)
                        if _tdamping:
                            _damp_html = "".join(
                                f'<div class="aw-condition-item">'
                                f'<span style="color:#4ade80;margin-right:5px">–</span>{d}'
                                f'</div>'
                                for d in _tdamping
                            )
                            st.markdown(_damp_html, unsafe_allow_html=True)

    # -----------------------------------------------------------------------
    # Tab: Attractors  (index 3)
    # -----------------------------------------------------------------------
    with _tabs[3]:
        _attract_list_tab = _attract_data.get("attractors", []) if isinstance(_attract_data, dict) else []

        st.markdown('<div class="aw-section-title">Attractor Landscape</div>', unsafe_allow_html=True)

        _ranked_attract = sorted(
            _attract_list_tab,
            key=lambda x: float(x.get("pull_strength", 0)),
            reverse=True,
        )

        _max_pull_tab = max((float(a.get("pull_strength", 0)) for a in _ranked_attract), default=1.0)
        _max_pull_tab = _max_pull_tab if _max_pull_tab > 0 else 1.0

        for _i, _attr in enumerate(_ranked_attract, 1):
            _aname = _attr.get("name", "—")
            _pull = float(_attr.get("pull_strength", 0))
            _ahorizon = _attr.get("horizon", "—")
            _trend = _attr.get("trend", "stable")
            _ev_count = _attr.get("supporting_evidence_count", 0)
            _counterforces = _attr.get("counterforces", [])
            _inv_cond = _attr.get("invalidation_conditions", [])
            _trend_arrow = {"up": "↑", "down": "↓", "stable": "→"}.get(_trend, "→")
            _trend_color = {"up": "#9a3412", "down": "#14532d", "stable": "#6b7280"}.get(_trend, "#6b7280")
            _bar_fill = int(round((_pull / _max_pull_tab) * 100))

            with st.expander(f"{_i}. {_aname}  {_trend_arrow}", expanded=False):
                _a1, _a2 = st.columns([3, 1])
                with _a1:
                    st.markdown(
                        f'<div class="aw-metric-label">Pull Strength</div>'
                        f'<div style="background:#2D3F52;border-radius:2px;height:8px;overflow:hidden;max-width:200px;margin-top:4px">'
                        f'<div style="width:{_bar_fill}%;background:#4A9FD4;height:100%"></div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with _a2:
                    st.markdown(
                        f'<div class="aw-metric-label">Horizon</div>'
                        f'<div style="font-size:14px;font-weight:700;color:#D4DDE6">{_ahorizon}</div>'
                        f'<div class="aw-metric-label" style="margin-top:6px">Trend</div>'
                        f'<div style="font-size:12px;font-weight:600;color:{_trend_color}">'
                        f'{"Rising" if _trend == "up" else "Falling" if _trend == "down" else "Stable"}'
                        f'</div>'
                        f'<div class="aw-metric-label" style="margin-top:6px">Evidence Items</div>'
                        f'<div style="font-size:14px;font-weight:700;color:#D4DDE6">{_ev_count}</div>',
                        unsafe_allow_html=True,
                    )

                st.markdown('<div class="aw-divider"></div>', unsafe_allow_html=True)

                _ac1, _ac2 = st.columns(2)
                with _ac1:
                    st.markdown('<div class="aw-metric-label">Counterforces</div>', unsafe_allow_html=True)
                    if _counterforces:
                        _cf_html = "".join(
                            f'<div class="aw-condition-item">'
                            f'<span style="color:#4ade80;margin-right:5px">–</span>{c}'
                            f'</div>'
                            for c in _counterforces
                        )
                        st.markdown(_cf_html, unsafe_allow_html=True)
                with _ac2:
                    st.markdown('<div class="aw-metric-label">Invalidation Conditions</div>', unsafe_allow_html=True)
                    if _inv_cond:
                        _ivc_html = "".join(
                            f'<div class="aw-condition-item">'
                            f'<span style="color:#6b7280;margin-right:5px">–</span>{c}'
                            f'</div>'
                            for c in _inv_cond
                        )
                        st.markdown(_ivc_html, unsafe_allow_html=True)

    # -----------------------------------------------------------------------
    # Tab: Propagation  (index 4) — 5-bucket horizontal timeline
    # -----------------------------------------------------------------------
    with _tabs[4]:
        _sequence_tab = _prop_data.get("sequence", []) if isinstance(_prop_data, dict) else []
        _bottlenecks = _prop_data.get("bottlenecks", []) if isinstance(_prop_data, dict) else []
        _second_order = _prop_data.get("second_order_effects", []) if isinstance(_prop_data, dict) else []

        st.markdown('<div class="aw-section-title">Propagation Timeline</div>', unsafe_allow_html=True)

        _bucket_order = ["T+0", "T+24h", "T+72h", "T+7d", "T+2-6w"]
        _bucket_map: Dict[str, list] = {}
        for _step in sorted(_sequence_tab, key=lambda x: x.get("step", 0)):
            _tb = _step.get("time_bucket", "T+?")
            _bucket_map.setdefault(_tb, []).append(_step)

        # Build 5-cell horizontal timeline HTML
        _timeline_html = '<div style="display:flex;gap:0;overflow-x:auto;margin-bottom:12px">'
        for _bi, _bk in enumerate(_bucket_order):
            _bk_steps = _bucket_map.get(_bk, [])
            _domain_cell = ""
            if _bk_steps:
                _domain_cell = " ".join(
                    f'<span class="aw-step-domain">{s.get("domain", "—")}</span>'
                    for s in _bk_steps
                )
                _event_cell = _bk_steps[0].get("event", "")[:_MAX_EVENT_PREVIEW_LENGTH]
            else:
                _domain_cell = '<span style="font-size:10px;color:#3a4a5a;font-style:italic">—</span>'
                _event_cell = ""

            _arrow = '<span style="font-size:14px;color:#4A6FA5;padding:0 4px;align-self:center">→</span>' if _bi < len(_bucket_order) - 1 else ""
            _cell_opacity = "1" if _bk_steps else "0.4"
            _timeline_html += (
                f'<div style="flex:1;min-width:80px;opacity:{_cell_opacity}">'
                f'<div style="font-size:9px;font-weight:700;color:#4A6FA5;text-transform:uppercase;'
                f'letter-spacing:0.5px;text-align:center;margin-bottom:4px">{_bk}</div>'
                f'<div class="aw-card-compact" style="min-height:40px;text-align:center">'
                f'{_domain_cell}'
                f'</div>'
                f'</div>'
                f'{_arrow}'
            )
        _timeline_html += "</div>"
        st.markdown(_timeline_html, unsafe_allow_html=True)

        # Cross-domain transition labels
        _sorted_seq_tab = sorted(_sequence_tab, key=lambda x: x.get("step", 0))
        if len(_sorted_seq_tab) > 1:
            _trans_html = ""
            for _si in range(len(_sorted_seq_tab) - 1):
                _d_from = _sorted_seq_tab[_si].get("domain", "—").title()
                _d_to = _sorted_seq_tab[_si + 1].get("domain", "—").title()
                _t_at = _sorted_seq_tab[_si + 1].get("time_bucket", "")
                if _d_from != _d_to:
                    _trans_html += (
                        f'<span style="font-size:10px;color:#7A8FA6;margin-right:12px">'
                        f'<span style="color:#D4DDE6">{_d_from} → {_d_to}</span> at {_t_at}'
                        f'</span>'
                    )
            if _trans_html:
                st.markdown(
                    f'<div style="margin-bottom:10px">{_trans_html}</div>',
                    unsafe_allow_html=True,
                )

        if _bottlenecks:
            st.markdown('<div class="aw-section-title">Bottlenecks</div>', unsafe_allow_html=True)
            _bn_html = "".join(
                f'<div class="aw-condition-item">'
                f'<span style="color:#fbbf24;margin-right:5px">!</span>{b}'
                f'</div>'
                for b in _bottlenecks
            )
            st.markdown(
                f'<div class="aw-card-compact" style="border-left:3px solid #92400e">{_bn_html}</div>',
                unsafe_allow_html=True,
            )

        if _second_order:
            st.markdown('<div class="aw-section-title">Second-order Effects</div>', unsafe_allow_html=True)
            _so_html = "".join(
                f'<div class="aw-condition-item">'
                f'<span style="color:#7A8FA6;margin-right:5px">–</span>{e}'
                f'</div>'
                for e in _second_order
            )
            st.markdown(f'<div class="aw-card-compact">{_so_html}</div>', unsafe_allow_html=True)

    # -----------------------------------------------------------------------
    # Tab: Coupling  (index 5)
    # -----------------------------------------------------------------------
    with _tabs[5]:
        _coupling_pairs = _coupling_data.get("pairs", []) if isinstance(_coupling_data, dict) else []

        st.markdown('<div class="aw-section-title">Structural Coupling Detector</div>', unsafe_allow_html=True)
        st.markdown(
            '<div style="font-size:10px;color:#7A8FA6;margin-bottom:10px">'
            'Domain pairs ranked by nonlinear coupling pressure'
            '</div>',
            unsafe_allow_html=True,
        )

        if not _coupling_pairs:
            st.markdown(
                '<div class="aw-callout aw-callout-warn">'
                'Coupling data unavailable — run assessment to compute structural coupling.'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            _max_coupling = max((float(p.get("coupling_strength", 0)) for p in _coupling_pairs), default=1.0)
            _max_coupling = _max_coupling if _max_coupling > 0 else 1.0

            for _cp in _coupling_pairs:
                _da = _cp.get("domain_a", "—").title()
                _db = _cp.get("domain_b", "—").title()
                _cs = float(_cp.get("coupling_strength", 0))
                _is_amp = _cp.get("is_amplifying", False)
                _amp_label = _cp.get("amplification_label", "")
                _bar_w = int(round((_cs / _max_coupling) * 100))
                _badge_html = (
                    f'<span class="aw-badge" style="background:#92400e22;color:#f97316;'
                    f'border:1px solid #92400e44;margin-left:6px">Amplifying</span>'
                    if _is_amp else ""
                )
                st.markdown(
                    f'<div class="aw-card-compact" style="margin-bottom:8px">'
                    f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
                    f'<span style="font-size:13px;font-weight:600;color:#D4DDE6">{_da} ↔ {_db}</span>'
                    f'{_badge_html}'
                    f'</div>'
                    f'<div style="background:#2D3F52;border-radius:2px;height:5px;overflow:hidden;max-width:200px">'
                    f'<div style="width:{_bar_w}%;background:#4A9FD4;height:100%"></div>'
                    f'</div>'
                    f'<div style="font-size:10px;color:#7A8FA6;margin-top:3px">{_amp_label}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # -----------------------------------------------------------------------
    # Tab: Evidence  (index 6)
    # -----------------------------------------------------------------------
    with _tabs[6]:
        _ev_data = get_evidence(_assessment_id)
        _ev_list = _ev_data.get("evidence", [])

        st.markdown('<div class="aw-section-title">Evidence Registry</div>', unsafe_allow_html=True)

        _all_areas = sorted({e.get("impacted_area", "") for e in _ev_list if e.get("impacted_area")})
        _area_filter = st.selectbox(
            "Filter by impacted area",
            options=["All"] + _all_areas,
            key="ev_area_filter",
        )

        _filtered_ev = (
            _ev_list
            if _area_filter == "All"
            else [e for e in _ev_list if e.get("impacted_area") == _area_filter]
        )

        for _ev in _filtered_ev:
            _ev_src = _ev.get("source", "—")
            _ev_ts = _fmt_ts(_ev.get("timestamp", ""))
            _ev_qual = _ev.get("source_quality", "—")
            _ev_area = _ev.get("impacted_area", "—")
            _ev_novelty = float(_ev.get("structural_novelty", 0))
            _ev_contrib = float(_ev.get("confidence_contribution", 0))
            _ev_link = _ev.get("provenance_link")

            _qcolor = _quality_color(_ev_qual)
            _qhtml = (
                f'<span class="aw-badge" style="background:{_qcolor}22;'
                f'color:{_qcolor};border:1px solid {_qcolor}44">{_ev_qual}</span>'
            )
            _link_html = (
                f' &nbsp;<a href="{_ev_link}" style="font-size:10px;color:#4A6FA5">Provenance</a>'
                if _ev_link else ""
            )

            st.markdown(
                f'<div class="aw-card-compact">'
                f'<div style="display:flex;justify-content:space-between;align-items:flex-start">'
                f'<div style="font-size:12px;font-weight:600;color:#D4DDE6;flex:1">{_ev_src}</div>'
                f'<div>{_qhtml}</div>'
                f'</div>'
                f'<div style="font-size:10px;color:#7A8FA6;margin-top:3px">'
                f'{_ev_ts} &nbsp;|&nbsp; {_ev_area}{_link_html}'
                f'</div>'
                f'<div style="margin-top:5px;display:flex;gap:16px">'
                f'<span style="font-size:10px;color:#7A8FA6">Novelty: '
                f'<span style="color:#D4DDE6;font-weight:600">{_ev_novelty:.0%}</span></span>'
                f'<span style="font-size:10px;color:#7A8FA6">Confidence contribution: '
                f'<span style="color:#D4DDE6;font-weight:600">{_ev_contrib:.0%}</span></span>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # -----------------------------------------------------------------------
    # Tab: Trace  (index 7)
    # -----------------------------------------------------------------------
    with _tabs[7]:
        st.markdown(
            '<div class="aw-card" style="text-align:center">'
            '<div style="font-size:13px;color:#7A8FA6;line-height:1.6">'
            'Model Trace is available for Power Users. Contains Bayesian path ranking, '
            'ontology activation chains, and confidence decomposition.'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        with st.expander("Trace Structure (JSON stub)", expanded=False):
            st.json({
                "trace_version": "1.0",
                "assessment_id": _assessment_id,
                "path_ranking": [
                    {"path_id": "p-001", "rank": 1, "score": 0.87},
                    {"path_id": "p-002", "rank": 2, "score": 0.71},
                ],
                "ontology_activation": {
                    "military_pressure": 0.92,
                    "energy_disruption": 0.85,
                    "financial_contagion": 0.63,
                },
                "confidence_decomposition": {
                    "base_confidence": 0.55,
                    "evidence_uplift": 0.19,
                    "structural_penalty": -0.07,
                    "final_confidence": 0.67,
                },
            })


# ===========================================================================
# RIGHT COLUMN — Causal Path + Evidence inspector
# ===========================================================================

with _right_col:

    # Causal Path (structured nodes display)
    st.markdown('<div class="aw-section-title">Causal Path</div>', unsafe_allow_html=True)

    _dominant_axis = _regime_data.get("dominant_axis", "") if isinstance(_regime_data, dict) else ""
    if _dominant_axis and _dominant_axis != "—":
        _axis_nodes = [p.strip() for p in _dominant_axis.replace("->", " -> ").split(" -> ") if p.strip()]
        _causal_html = ""
        for _ni, _node in enumerate(_axis_nodes):
            _arrow_html = '<span style="font-size:12px;color:#4A6FA5">→</span>' if _ni < len(_axis_nodes) - 1 else ""
            _causal_html += (
                f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">'
                f'<div style="background:#1e2d3d;border:1px solid #2D3F52;border-radius:3px;'
                f'padding:4px 10px;font-size:11px;font-weight:600;color:#C8A84B">{_node}</div>'
                f'{_arrow_html}'
                f'</div>'
            )
        st.markdown(
            f'<div class="aw-card-compact">{_causal_html}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="aw-card-compact">'
            '<div style="font-size:11px;color:#7A8FA6;font-style:italic">'
            'Causal path data unavailable'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    # Model trace summary
    st.markdown('<div class="aw-section-title">Model State</div>', unsafe_allow_html=True)
    _coupling = float(_regime_data.get("coupling_asymmetry", 0)) if isinstance(_regime_data, dict) else 0.0
    _damping = float(_regime_data.get("damping_capacity", 0)) if isinstance(_regime_data, dict) else 0.0
    st.markdown(
        f'<div class="aw-card-compact">'
        f'<div style="display:flex;justify-content:space-between;margin-bottom:4px">'
        f'<span style="font-size:10px;color:#7A8FA6">Coupling asymmetry</span>'
        f'<span style="font-size:11px;font-weight:600;color:#D4DDE6">{_coupling:.2f}</span>'
        f'</div>'
        f'<div style="display:flex;justify-content:space-between">'
        f'<span style="font-size:10px;color:#7A8FA6">Damping capacity</span>'
        f'<span style="font-size:11px;font-weight:600;color:#D4DDE6">{_damping:.2f}</span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Evidence preview — 2 most recent items
    _ev_data_r = get_evidence(_assessment_id)
    _ev_items_r = _ev_data_r.get("evidence", []) if isinstance(_ev_data_r, dict) else []

    _sorted_ev = sorted(
        _ev_items_r,
        key=lambda x: x.get("timestamp", ""),
        reverse=True,
    )[:2]

    st.markdown(
        f'<div class="aw-section-title">Latest Evidence</div>'
        f'<div style="font-size:10px;color:#7A8FA6;margin-bottom:6px">'
        f'{len(_ev_items_r)} items total</div>',
        unsafe_allow_html=True,
    )

    for _ev_r in _sorted_ev:
        _ev_src_r = _ev_r.get("source", "—")
        _ev_ts_r = _fmt_ts(_ev_r.get("timestamp", ""))
        _ev_qual_r = _ev_r.get("source_quality", "—")
        _ev_area_r = _ev_r.get("impacted_area", "—")
        _qcolor_r = _quality_color(_ev_qual_r)

        st.markdown(
            f'<div class="aw-card-compact">'
            f'<div style="font-size:11px;font-weight:600;color:#D4DDE6;margin-bottom:3px">{_ev_src_r}</div>'
            f'<div style="font-size:9px;color:#7A8FA6">{_ev_ts_r}</div>'
            f'<div style="margin-top:4px">'
            f'<span class="aw-badge" style="background:{_qcolor_r}22;color:{_qcolor_r};'
            f'border:1px solid {_qcolor_r}44">{_ev_qual_r}</span>'
            f'<span class="aw-domain-badge">{_ev_area_r}</span>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
