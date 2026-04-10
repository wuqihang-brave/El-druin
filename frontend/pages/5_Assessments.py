"""
Assessment Workspace – EL-DRUIN Intelligence Platform
======================================================

Assessment Workspace shell: assessment selector + tab-based intelligence view.
Default tab: Brief (rendered with forecast_brief component).
Tabs: Brief | Regime | Triggers | Propagation | Evidence | Trace

Route: /Assessments  (Streamlit page label "Assessments")
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
)

from components.forecast_brief import render_forecast_brief  # noqa: E402

try:
    from components.sidebar import render_sidebar_navigation  # noqa: E402
    st.session_state["current_page"] = "Assessments"
    render_sidebar_navigation(is_subpage=True)
except Exception:
    pass

# ---------------------------------------------------------------------------
# Design constants
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Inline CSS (workspace-specific)
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
.aw-card-compact {
    background: #162030;
    border: 1px solid #2D3F52;
    border-radius: 3px;
    padding: 10px 12px;
    margin-bottom: 8px;
}
.aw-metric-card {
    background: #162030;
    border: 1px solid #2D3F52;
    border-radius: 3px;
    padding: 10px 12px;
    text-align: center;
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
.aw-badge-type { background: #1e2d3d; color: #7A8FA6; border: 1px solid #2D3F52; }
.aw-badge-status-active { background: #14532d22; color: #4ade80; border: 1px solid #14532d; }
.aw-badge-status-review { background: #92400e22; color: #fbbf24; border: 1px solid #92400e; }
.aw-badge-status-draft  { background: #1e2d3d; color: #7A8FA6; border: 1px solid #2D3F52; }
.aw-badge-status-archived { background: #1e2d3d; color: #4b5563; border: 1px solid #2D3F52; }
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
.aw-divider { height: 1px; background: #2D3F52; margin: 10px 0; }
.aw-topbar-title { font-size: 15px; font-weight: 700; color: #D4DDE6; line-height: 1.3; }
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


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "aw5_selected_id" not in st.session_state:
    st.session_state.aw5_selected_id = None

_qp = st.query_params.get("assessment_id")
if _qp and not st.session_state.aw5_selected_id:
    st.session_state.aw5_selected_id = _qp

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

_assessments: List[Dict[str, Any]] = []
try:
    _raw = get_assessments()
    if isinstance(_raw, list):
        _assessments = _raw
    elif isinstance(_raw, dict) and "error" in _raw:
        st.error(f"Could not load assessments: {_raw['error']}")
except Exception as _exc:
    st.error(f"Unexpected error loading assessments: {_exc}")

# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------

if not _assessments:
    if not st.session_state.get("_aw5_error_shown"):
        st.markdown(
            '<div style="max-width:480px;margin:60px auto;text-align:center;">'
            '<div style="font-size:13px;color:#7A8FA6;line-height:1.6">'
            "No active assessments found. Connect your backend or compose a new assessment."
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    st.stop()

# ---------------------------------------------------------------------------
# Assessment selector (sidebar dropdown + list)
# ---------------------------------------------------------------------------

_assessment_options: Dict[str, str] = {
    a.get("assessment_id", ""): a.get("title", "—")
    for a in _assessments
    if a.get("assessment_id")
}
_ids = list(_assessment_options.keys())
_labels = [_assessment_options[i] for i in _ids]

with st.sidebar:
    st.markdown(
        '<div style="font-size:10px;font-weight:700;text-transform:uppercase;'
        'letter-spacing:0.8px;color:#7A8FA6;margin-bottom:6px">Select Assessment</div>',
        unsafe_allow_html=True,
    )
    _sel_label = st.selectbox(
        "Assessment",
        options=_labels,
        index=0,
        label_visibility="collapsed",
        key="aw5_selector",
    )
    _sel_idx = _labels.index(_sel_label) if _sel_label in _labels else 0
    st.session_state.aw5_selected_id = _ids[_sel_idx] if _ids else None

if not st.session_state.aw5_selected_id:
    st.info("Select an assessment from the sidebar to open the workspace.")
    st.stop()

# ---------------------------------------------------------------------------
# Load selected assessment metadata
# ---------------------------------------------------------------------------

_assessment_id: str = st.session_state.aw5_selected_id
_assessment: Dict[str, Any] = {}

try:
    _assessment = get_assessment(_assessment_id)
    if isinstance(_assessment, dict) and "error" in _assessment:
        st.error(f"Could not load assessment details: {_assessment['error']}")
        st.stop()
except Exception as _exc:
    st.error(f"Unexpected error loading assessment: {_exc}")
    st.stop()

_title = _assessment.get("title", "—")
_atype = _assessment.get("assessment_type", "")
_status = _assessment.get("status", "")
_updated = _fmt_ts(_assessment.get("updated_at", ""))
_alerts = _assessment.get("alert_count", 0)
_region_tags: List[str] = _assessment.get("region_tags", [])
_domain_tags: List[str] = _assessment.get("domain_tags", [])

# ---------------------------------------------------------------------------
# Top bar: title + metadata
# ---------------------------------------------------------------------------

_tb1, _tb2, _tb3, _tb4 = st.columns([5, 2, 2, 1])

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
        f'<div class="brief-label">Status</div>'
        f'{_status_badge_html(_status)}',
        unsafe_allow_html=True,
    )

with _tb3:
    st.markdown(
        f'<div class="brief-label">Last Updated</div>'
        f'<div style="font-size:12px;color:#D4DDE6">{_updated}</div>',
        unsafe_allow_html=True,
    )

with _tb4:
    if _alerts:
        st.markdown(
            f'<span style="display:inline-block;background:#7f1d1d;color:#fca5a5;'
            f'font-size:11px;font-weight:700;padding:2px 8px;border-radius:10px;'
            f'border:1px solid #991b1b">{_alerts}</span>',
            unsafe_allow_html=True,
        )

st.markdown('<div class="aw-divider"></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Intelligence tabs  (Brief is default — index 0)
# ---------------------------------------------------------------------------

_tabs = st.tabs(["Brief", "Regime", "Triggers", "Propagation", "Evidence", "Trace"])

# -----------------------------------------------------------------------
# Tab 0: Brief
# -----------------------------------------------------------------------
with _tabs[0]:
    _brief: Dict[str, Any] = {}
    try:
        _brief = get_brief(_assessment_id)
        if isinstance(_brief, dict) and "error" in _brief:
            st.error(f"Could not load brief: {_brief['error']}")
            _brief = {}
    except Exception as _exc:
        st.error(f"Unexpected error loading brief: {_exc}")
        _brief = {}

    if _brief:
        render_forecast_brief(_brief)
    else:
        st.markdown(
            '<div style="font-size:12px;color:#7A8FA6;font-style:italic;margin-top:20px">'
            "Brief data unavailable for this assessment."
            "</div>",
            unsafe_allow_html=True,
        )

# -----------------------------------------------------------------------
# Tab 1: Regime
# -----------------------------------------------------------------------
with _tabs[1]:
    st.markdown(
        '<div style="font-size:12px;color:#7A8FA6;font-style:italic;margin-top:20px">'
        "Structural Regime View — coming in PR-10."
        "</div>",
        unsafe_allow_html=True,
    )

# -----------------------------------------------------------------------
# Tab 2: Triggers
# -----------------------------------------------------------------------
with _tabs[2]:
    st.markdown(
        '<div style="font-size:12px;color:#7A8FA6;font-style:italic;margin-top:20px">'
        "Trigger Amplification Board — coming in PR-11."
        "</div>",
        unsafe_allow_html=True,
    )

# -----------------------------------------------------------------------
# Tab 3: Propagation
# -----------------------------------------------------------------------
with _tabs[3]:
    st.markdown(
        '<div style="font-size:12px;color:#7A8FA6;font-style:italic;margin-top:20px">'
        "Propagation Sequence View — coming in PR-13."
        "</div>",
        unsafe_allow_html=True,
    )

# -----------------------------------------------------------------------
# Tab 4: Evidence
# -----------------------------------------------------------------------
with _tabs[4]:
    st.markdown(
        '<div style="font-size:12px;color:#7A8FA6;font-style:italic;margin-top:20px">'
        "Evidence Panel — coming in a future release."
        "</div>",
        unsafe_allow_html=True,
    )

# -----------------------------------------------------------------------
# Tab 5: Trace
# -----------------------------------------------------------------------
with _tabs[5]:
    st.markdown(
        '<div style="font-size:12px;color:#7A8FA6;font-style:italic;margin-top:20px">'
        "Reasoning Trace — coming in a future release."
        "</div>",
        unsafe_allow_html=True,
    )
