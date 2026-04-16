"""
Assessment Workspace – EL-DRUIN Intelligence Platform
======================================================

Structural forecast operating surface.

Layout:
  - Top command bar (full width): assessment name, regime, threshold, trigger,
    attractor, propagation mode, delta status, confidence, updated_at
  - Left rail: assessment navigator list
  - Center column: Regime -> Triggers -> Attractors -> Propagation (full
    sections, no tabs), then Delta / Brief / Evidence / Trace below
  - Right rail: lightweight supporting context only
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List

import streamlit as st

_FRONTEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FRONTEND_DIR not in sys.path:
    sys.path.insert(0, _FRONTEND_DIR)

st.set_page_config(
    page_title="Assessments - EL-DRUIN",
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
    api_client as _api_client,
)
from components.forecast_brief import render_forecast_brief  # noqa: E402
from components.regime_view import render_regime_view  # noqa: E402

logger = logging.getLogger(__name__)

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
    "review_required": "Review",
    "draft": "Draft",
    "archived": "Archived",
}

_AMP_DISPLAY_SCALE: float = 5.0
_MAX_EVENT_PREVIEW_LENGTH: int = 60
_EM: str = "\u2014"  # em-dash literal; defined here to avoid backslash inside f-string {}

# ---------------------------------------------------------------------------
# Inline CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
.aw-page-label {
    font-size: 9px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 1.2px; color: #7A8FA6; margin-bottom: 2px;
}
.aw-section-title {
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.8px; color: #7A8FA6; margin: 14px 0 6px 0;
}
.aw-card {
    background: #162030; border: 1px solid #2D3F52; border-radius: 3px;
    padding: 14px 16px; margin-bottom: 10px;
}
.aw-card-compact {
    background: #162030; border: 1px solid #2D3F52; border-radius: 3px;
    padding: 10px 12px; margin-bottom: 8px;
}
.aw-list-item {
    background: #162030; border: 1px solid #2D3F52; border-radius: 3px;
    padding: 10px 12px; margin-bottom: 6px;
}
.aw-list-item-active { border-color: #4A8FD4; border-left: 3px solid #4A8FD4; }
.aw-list-item-title {
    font-size: 12px; font-weight: 600; color: #D4DDE6;
    margin-bottom: 4px; line-height: 1.4;
}
.aw-badge {
    display: inline-block; font-size: 10px; font-weight: 600;
    padding: 2px 7px; border-radius: 2px; margin-right: 4px;
    text-transform: uppercase; letter-spacing: 0.4px;
}
.aw-badge-type { background: #1e2d3d; color: #7A8FA6; border: 1px solid #2D3F52; }
.aw-badge-status-active { background: #14532d22; color: #4ade80; border: 1px solid #14532d; }
.aw-badge-status-review { background: #92400e22; color: #fbbf24; border: 1px solid #92400e; }
.aw-badge-status-draft { background: #1e2d3d; color: #7A8FA6; border: 1px solid #2D3F52; }
.aw-badge-status-archived { background: #1e2d3d; color: #4b5563; border: 1px solid #2D3F52; }
.aw-regime-badge {
    display: inline-block; font-size: 11px; font-weight: 700;
    padding: 3px 8px; border-radius: 3px; letter-spacing: 0.3px;
}
.aw-callout {
    background: #1e2d3d; border-left: 3px solid #4A6FA5;
    border-radius: 0 3px 3px 0; padding: 10px 14px; margin: 8px 0;
    font-size: 13px; color: #D4DDE6; line-height: 1.5;
}
.aw-callout-warn { border-left-color: #92400e; }
.aw-metric-card {
    background: #162030; border: 1px solid #2D3F52; border-radius: 3px;
    padding: 10px 12px; text-align: center; margin-bottom: 8px;
}
.aw-metric-label {
    font-size: 9px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.6px; color: #7A8FA6; margin-bottom: 4px;
}
.aw-metric-value { font-size: 20px; font-weight: 700; color: #D4DDE6; line-height: 1.2; }
.aw-condition-item { font-size: 12px; color: #D4DDE6; padding: 3px 0; line-height: 1.4; }
.aw-domain-badge {
    display: inline-block; font-size: 10px; padding: 1px 6px;
    border-radius: 2px; margin: 1px 2px;
    background: #1e2d3d; color: #7A8FA6; border: 1px solid #2D3F52;
}
.aw-divider { height: 1px; background: #2D3F52; margin: 10px 0; }
.aw-topbar-title { font-size: 14px; font-weight: 700; color: #D4DDE6; line-height: 1.3; }
.aw-step-domain {
    font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 2px;
    background: #1e2d3d; color: #C8A84B; border: 1px solid #2D3F52;
    margin-right: 8px; white-space: nowrap;
}
.aw-cmd-field { display: flex; flex-direction: column; gap: 2px; }
.aw-cmd-label {
    font-size: 8px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.6px; color: #5A7A9A;
}
.aw-cmd-value {
    font-size: 12px; font-weight: 600; color: #C8D8E8;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
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
        return "\u2014"
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


def _regime_badge_html(regime: str, small: bool = False) -> str:
    color = _REGIME_COLORS.get(regime, "#6b7280")
    size = "10px" if small else "11px"
    return (
        f'<span class="aw-regime-badge" style="background:{color}22;color:{color};'
        f'border:1px solid {color}55;font-size:{size}">{regime or "—"}</span>'
    )


def _domain_badges_html(tags: List[str]) -> str:
    return " ".join(f'<span class="aw-domain-badge">{t}</span>' for t in tags)


def _jump_color(jump: str) -> str:
    return _JUMP_COLORS.get(jump, "#6b7280")


def _quality_color(quality: str) -> str:
    return _QUALITY_COLORS.get(quality, "#6b7280")


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "selected_assessment_id" not in st.session_state:
    st.session_state.selected_assessment_id = None

_qp = st.query_params.get("assessment_id")
if _qp and not st.session_state.selected_assessment_id:
    st.session_state.selected_assessment_id = _qp


# ---------------------------------------------------------------------------
# Fetch assessment list
# ---------------------------------------------------------------------------

_assessments: List[Dict[str, Any]] = get_assessments()

if not st.session_state.selected_assessment_id and _assessments:
    st.session_state.selected_assessment_id = _assessments[0].get("assessment_id")

if not _assessments:
    st.markdown("""
    <div style="max-width:480px;margin:80px auto;text-align:center;">
        <div style="font-size:13px;color:#7A8FA6;margin-bottom:16px;line-height:1.6">
            No active assessments. Connect your backend to load assessments.
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ===========================================================================
# THREE-COLUMN LAYOUT
# ===========================================================================

_left_col, _center_col, _right_col = st.columns([1, 3, 1])


# ===========================================================================
# LEFT COLUMN - Assessment Navigator
# ===========================================================================

with _left_col:
    st.markdown('<div class="aw-section-title">ASSESSMENTS</div>', unsafe_allow_html=True)

    for _a in _assessments:
        _aid = _a.get("assessment_id", "")
        _title_a = _a.get("title", "\u2014")
        _status_a = _a.get("status", "")
        _updated_a = _fmt_ts(_a.get("updated_at", ""))
        _regime_a = _a.get("last_regime") or ""
        _is_active = _aid == st.session_state.selected_assessment_id

        _delta_badge = ""
        if _a.get("regime_changed"):
            _delta_badge = (
                '<span class="aw-badge" style="background:#9a341222;color:#f87171;'
                'border:1px solid #9a341244">Regime</span>'
            )
        elif _a.get("threshold_direction") == "narrowing":
            _delta_badge = (
                '<span class="aw-badge" style="background:#92400e22;color:#fbbf24;'
                'border:1px solid #92400e44">Narrow</span>'
            )

        _active_cls = "aw-list-item-active" if _is_active else ""
        _regime_html_a = _regime_badge_html(_regime_a, small=True) if _regime_a else ""
        _delta_row = f'<div style="margin-top:3px">{_delta_badge}</div>' if _delta_badge else ""

        st.markdown(
            f'<div class="aw-list-item {_active_cls}">'
            f'<div class="aw-list-item-title">{_title_a}</div>'
            f'<div style="margin:3px 0;display:flex;flex-wrap:wrap;gap:2px;align-items:center">'
            f'{_status_badge_html(_status_a)} {_regime_html_a}'
            f'</div>'
            f'{_delta_row}'
            f'<div style="font-size:9px;color:#7A8FA6;margin-top:3px">{_updated_a}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button("Select", key=f"sel_{_aid}", use_container_width=True):
            st.session_state.selected_assessment_id = _aid
            st.rerun()


# ===========================================================================
# Load selected assessment data
# ===========================================================================

_assessment_id: str = st.session_state.selected_assessment_id or ""
_assessment: Dict[str, Any] = get_assessment(_assessment_id) if _assessment_id else {}

_title = _assessment.get("title", "\u2014")
_status = _assessment.get("status", "")
_updated = _fmt_ts(_assessment.get("updated_at", ""))
_region_tags: List[str] = _assessment.get("region_tags", [])
_domain_tags: List[str] = _assessment.get("domain_tags", [])

_regime_data = get_regime(_assessment_id) if _assessment_id else {}
_delta_data = get_delta(_assessment_id) if _assessment_id else {}
_triggers_data = get_triggers(_assessment_id) if _assessment_id else {}
_attract_data = get_attractors(_assessment_id) if _assessment_id else {}
_prop_data = get_propagation(_assessment_id) if _assessment_id else {}
_brief_data = get_brief(_assessment_id) if _assessment_id else {}
_ev_data = get_evidence(_assessment_id) if _assessment_id else {}
_coupling_data = get_coupling(_assessment_id) if _assessment_id else {}

# p-adic probability tree (backward compatible: {} if unavailable)
_padic_data: Dict[str, Any] = {}
if _assessment_id:
    try:
        _result = _api_client.get_probability_tree_for_assessment(_assessment_id)
        if isinstance(_result, dict) and "error" not in _result:
            _padic_data = _result
    except Exception as _exc:
        logger.debug("p-adic data unavailable for assessment %s: %s", _assessment_id, _exc)
        _padic_data = {}

_regime_name = _regime_data.get("current_regime", "\u2014") if isinstance(_regime_data, dict) else "\u2014"
_regime_thresh = float(_regime_data.get("threshold_distance", 0)) if isinstance(_regime_data, dict) else 0.0
_regime_color = _REGIME_COLORS.get(_regime_name, "#6b7280")

_triggers_list = _triggers_data.get("triggers", []) if isinstance(_triggers_data, dict) else []
_sorted_triggers = sorted(
    _triggers_list, key=lambda x: float(x.get("amplification_factor", 0)), reverse=True
)
_dominant_trigger = _sorted_triggers[0].get("name", "\u2014") if _sorted_triggers else "\u2014"

_attract_list = _attract_data.get("attractors", []) if isinstance(_attract_data, dict) else []
_sorted_attractors = sorted(
    _attract_list, key=lambda x: float(x.get("pull_strength", 0)), reverse=True
)
_dominant_attractor = _sorted_attractors[0].get("name", "\u2014") if _sorted_attractors else "\u2014"

_sequence = _prop_data.get("sequence", []) if isinstance(_prop_data, dict) else []
_sorted_seq = sorted(_sequence, key=lambda x: x.get("step", 0))
_prop_mode = _sorted_seq[0].get("domain", "\u2014") if _sorted_seq else "\u2014"

_delta_summary = _delta_data.get("summary", "") if isinstance(_delta_data, dict) else ""
_is_first_run = "First" in _delta_summary or "No prior" in _delta_summary
_reg_changed = _delta_data.get("regime_changed", False) if isinstance(_delta_data, dict) else False
_delta_status = "Regime shifted" if _reg_changed else ("First run" if _is_first_run else "Stable")
_delta_color = "#9a3412" if _reg_changed else ("#6b7280" if _is_first_run else "#14532d")

_confidence = _brief_data.get("confidence", "\u2014") if isinstance(_brief_data, dict) else "\u2014"


# ===========================================================================
# CENTER COLUMN
# ===========================================================================

with _center_col:

    # -----------------------------------------------------------------------
    # TOP COMMAND BAR
    # -----------------------------------------------------------------------
    _thresh_pct = int(round(_regime_thresh * 100))
    _thresh_bar = int(round((1 - _regime_thresh) * 100))
    _cb = st.columns([3, 2, 2, 3, 3, 2, 2, 1, 2])

    with _cb[0]:
        st.markdown(
            f'<div class="aw-cmd-field">'
            f'<div class="aw-cmd-label">Assessment</div>'
            f'<div class="aw-topbar-title" style="font-size:13px">{_title}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with _cb[1]:
        st.markdown(
            f'<div class="aw-cmd-field">'
            f'<div class="aw-cmd-label">Regime</div>'
            f'{_regime_badge_html(_regime_name)}'
            f'</div>',
            unsafe_allow_html=True,
        )
    with _cb[2]:
        st.markdown(
            f'<div class="aw-cmd-field">'
            f'<div class="aw-cmd-label">Threshold</div>'
            f'<div class="aw-cmd-value">{_thresh_pct}%'
            f'<div style="background:#2D3F52;border-radius:2px;height:4px;overflow:hidden;'
            f'margin-top:3px;max-width:80px">'
            f'<div style="width:{_thresh_bar}%;background:{_regime_color};height:100%"></div>'
            f'</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with _cb[3]:
        _trig_short = (_dominant_trigger[:26] + "\u2026") if len(_dominant_trigger) > 26 else _dominant_trigger
        st.markdown(
            f'<div class="aw-cmd-field">'
            f'<div class="aw-cmd-label">Dominant Trigger</div>'
            f'<div class="aw-cmd-value">{_trig_short}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with _cb[4]:
        _attr_short = (_dominant_attractor[:26] + "\u2026") if len(_dominant_attractor) > 26 else _dominant_attractor
        st.markdown(
            f'<div class="aw-cmd-field">'
            f'<div class="aw-cmd-label">Dominant Attractor</div>'
            f'<div class="aw-cmd-value">{_attr_short}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with _cb[5]:
        st.markdown(
            f'<div class="aw-cmd-field">'
            f'<div class="aw-cmd-label">Propagation Mode</div>'
            f'<div class="aw-cmd-value">{_prop_mode}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with _cb[6]:
        st.markdown(
            f'<div class="aw-cmd-field">'
            f'<div class="aw-cmd-label">Delta</div>'
            f'<span class="aw-badge" style="background:{_delta_color}22;color:{_delta_color};'
            f'border:1px solid {_delta_color}44">{_delta_status}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with _cb[7]:
        _conf_color = {"High": "#4caf7d", "Medium": "#e8a742", "Low": "#e05c5c"}.get(
            str(_confidence), "#7A8FA6"
        )
        st.markdown(
            f'<div class="aw-cmd-field">'
            f'<div class="aw-cmd-label">Conf.</div>'
            f'<div class="aw-cmd-value" style="color:{_conf_color}">{_confidence}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with _cb[8]:
        st.markdown(
            f'<div class="aw-cmd-field">'
            f'<div class="aw-cmd-label">Updated At</div>'
            f'<div class="aw-cmd-value">{_updated}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="aw-divider"></div>', unsafe_allow_html=True)

    # -----------------------------------------------------------------------
    # SECTION 1 - REGIME
    # -----------------------------------------------------------------------
    st.markdown('<div class="aw-section-title">REGIME</div>', unsafe_allow_html=True)

    if isinstance(_regime_data, dict) and "error" in _regime_data:
        st.markdown(
            f'<div class="aw-callout aw-callout-warn">'
            f'Could not load regime data: {_regime_data["error"]}</div>',
            unsafe_allow_html=True,
        )
    elif _regime_data:
        render_regime_view(_regime_data)
    else:
        st.markdown(
            '<div class="aw-callout">No regime data for this assessment.</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="aw-divider"></div>', unsafe_allow_html=True)

    # -----------------------------------------------------------------------
    # P-ADIC CONFIDENCE (collapsed)
    # -----------------------------------------------------------------------
    with st.expander("P-ADIC CONFIDENCE", expanded=False):
        if not _padic_data:
            st.markdown(
                '<div style="font-size:12px;color:#7A8FA6;font-style:italic">'
                'P-adic confidence data unavailable for this assessment.</div>',
                unsafe_allow_html=True,
            )
        else:
            _step_t = _padic_data.get("step_t", 1)
            _prime_p = _padic_data.get("prime_p", 7)
            _is_phase = _padic_data.get("is_phase_transition", False)
            _branches = _padic_data.get("interpretation_branches", [])

            # Header metrics
            _ph_color = "#C8A84B" if _is_phase else "#7A8FA6"
            _ph_label = "⚡ Phase Transition" if _is_phase else "Stable"
            # Compute |t|_p = p^{-v_p(t)}
            _tv = _step_t
            _vp = 0
            while _tv and _tv % _prime_p == 0:
                _tv //= _prime_p
                _vp += 1
            _t_abs_p_val = float(_prime_p) ** (-_vp) if _vp > 0 else 1.0

            _pm1, _pm2, _pm3, _pm4 = st.columns(4)
            with _pm1:
                st.markdown(
                    f'<div class="aw-metric-card">'
                    f'<div class="aw-metric-label">Step t</div>'
                    f'<div class="aw-metric-value">{_step_t}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with _pm2:
                st.markdown(
                    f'<div class="aw-metric-card">'
                    f'<div class="aw-metric-label">Prime p</div>'
                    f'<div class="aw-metric-value">{_prime_p}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with _pm3:
                st.markdown(
                    f'<div class="aw-metric-card">'
                    f'<div class="aw-metric-label">|t|_p</div>'
                    f'<div class="aw-metric-value">{_t_abs_p_val:.4f}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with _pm4:
                st.markdown(
                    f'<div class="aw-metric-card">'
                    f'<div class="aw-metric-label">Phase State</div>'
                    f'<div style="font-size:14px;font-weight:700;color:{_ph_color}">{_ph_label}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            if _branches:
                st.markdown(
                    '<div class="aw-metric-label" style="margin-top:10px">Interpretation Branches</div>',
                    unsafe_allow_html=True,
                )
                for _br in _branches:
                    _br_id = _br.get("branch_id", "?")
                    _br_interp = _br.get("interpretation", "—")
                    _br_weight = float(_br.get("p_adic_weight", 0))
                    _br_conf = float(_br.get("confidence", 0))
                    _br_domain = _br.get("domain", "")
                    _br_mode = _br.get("mode", "")
                    _br_calc = float(_br.get("calculated_weight", 0))
                    _br_norm = float(_br.get("weight", 0))
                    _w_bar = min(int(round(_br_norm * 100)), 100)
                    st.markdown(
                        f'<div class="aw-card-compact" style="margin-bottom:6px">'
                        f'<div style="display:flex;justify-content:space-between;align-items:flex-start">'
                        f'<div style="font-size:11px;color:#D4DDE6;font-weight:600;flex:1">'
                        f'Branch {_br_id}: {_br_interp}</div>'
                        f'<div style="font-size:10px;color:#7A8FA6;margin-left:8px">'
                        f'|t|_p weight: <span style="color:#C8A84B;font-weight:700">{_br_weight:.4f}</span>'
                        f'</div></div>'
                        f'<div style="margin-top:6px;display:flex;gap:12px">'
                        f'<span style="font-size:10px;color:#7A8FA6">Confidence: '
                        f'<span style="color:#D4DDE6;font-weight:600">{_br_conf:.0%}</span></span>'
                        f'<span style="font-size:10px;color:#7A8FA6">Normalised weight: '
                        f'<span style="color:#D4DDE6;font-weight:600">{_br_norm:.3f}</span></span>'
                        + (f'<span class="aw-domain-badge">{_br_domain}</span>' if _br_domain else "")
                        + (f'<span class="aw-domain-badge">{_br_mode}</span>' if _br_mode else "")
                        + f'</div>'
                        f'<div style="background:#2D3F52;border-radius:2px;height:4px;'
                        f'overflow:hidden;margin-top:6px;max-width:200px">'
                        f'<div style="width:{_w_bar}%;background:#4A8FD4;height:100%"></div>'
                        f'</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

    st.markdown('<div class="aw-divider"></div>', unsafe_allow_html=True)

    # -----------------------------------------------------------------------
    # SECTION 2 - TRIGGERS
    # -----------------------------------------------------------------------
    st.markdown(
        '<div class="aw-section-title">TRIGGERS</div>'
        '<div style="font-size:10px;color:#7A8FA6;margin-bottom:6px">'
        'Sorted by amplification factor \u2014 highest nonlinear consequence first'
        '</div>',
        unsafe_allow_html=True,
    )

    if not _sorted_triggers:
        st.markdown(
            '<div class="aw-callout aw-callout-warn">No trigger data for this assessment.</div>',
            unsafe_allow_html=True,
        )
    else:
        for _t in _sorted_triggers:
            _tname = _t.get("name", "\u2014")
            _amp = float(_t.get("amplification_factor", 0))
            _amp_x = f"\u00d7{_amp * _AMP_DISPLAY_SCALE:.1f}"
            _jump = _t.get("jump_potential", "Low")
            _domains = _t.get("impacted_domains", [])
            _lag = _t.get("expected_lag_hours", 0)
            _tconf = float(_t.get("confidence", 0))
            _signals = _t.get("watch_signals", [])
            _tdamping = _t.get("damping_opportunities", [])
            _trend_arrow = "\u2191" if _amp >= 0.7 else ("\u2192" if _amp >= 0.4 else "\u2193")

            _jcolor = _jump_color(_jump)
            _domains_html = " ".join(
                f'<span class="aw-domain-badge">{d}</span>' for d in _domains
            )
            _jump_html = (
                f'<span class="aw-badge" style="background:{_jcolor}22;'
                f'color:{_jcolor};border:1px solid {_jcolor}44">{_jump}</span>'
            )

            with st.expander(f"{_tname}  {_amp_x}  {_trend_arrow}", expanded=False):
                _t1, _t2, _t3 = st.columns([2, 1, 1])
                with _t1:
                    st.markdown(
                        f'<div class="aw-metric-label">Impacted Domains</div>'
                        f'<div style="margin-top:4px">{_domains_html}</div>',
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
                        st.markdown(
                            "".join(
                                f'<div class="aw-condition-item">'
                                f'<span style="color:#7A8FA6;margin-right:5px">\u2013</span>{s}'
                                f'</div>'
                                for s in _signals
                            ),
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            '<div class="aw-condition-item" style="color:#7A8FA6;font-style:italic">None</div>',
                            unsafe_allow_html=True,
                        )
                with _s2:
                    st.markdown('<div class="aw-metric-label">Damping Opportunities</div>', unsafe_allow_html=True)
                    if _tdamping:
                        st.markdown(
                            "".join(
                                f'<div class="aw-condition-item">'
                                f'<span style="color:#4ade80;margin-right:5px">\u2013</span>{d}'
                                f'</div>'
                                for d in _tdamping
                            ),
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            '<div class="aw-condition-item" style="color:#7A8FA6;font-style:italic">None</div>',
                            unsafe_allow_html=True,
                        )

    st.markdown('<div class="aw-divider"></div>', unsafe_allow_html=True)

    # -----------------------------------------------------------------------
    # SECTION 3 - ATTRACTORS
    # -----------------------------------------------------------------------
    st.markdown(
        '<div class="aw-section-title">ATTRACTORS</div>'
        '<div style="font-size:10px;color:#7A8FA6;margin-bottom:6px">'
        'Sorted by pull strength \u2014 strongest basin first'
        '</div>',
        unsafe_allow_html=True,
    )

    if not _sorted_attractors:
        st.markdown(
            '<div class="aw-callout">No attractor data for this assessment.</div>',
            unsafe_allow_html=True,
        )
    else:
        _max_pull = max((float(a.get("pull_strength", 0)) for a in _sorted_attractors), default=1.0)
        _max_pull = _max_pull if _max_pull > 0 else 1.0

        for _i, _attr in enumerate(_sorted_attractors, 1):
            _aname = _attr.get("name", "\u2014")
            _pull = float(_attr.get("pull_strength", 0))
            _ahorizon = _attr.get("horizon", "\u2014")
            _trend = _attr.get("trend", "stable")
            _ev_count = _attr.get("supporting_evidence_count", 0)
            _counterforces = _attr.get("counterforces", [])
            _inv_cond = _attr.get("invalidation_conditions", [])
            _trend_arrow = {"up": "\u2191", "down": "\u2193", "stable": "\u2192"}.get(_trend, "\u2192")
            _trend_color = {"up": "#9a3412", "down": "#14532d", "stable": "#6b7280"}.get(_trend, "#6b7280")
            _bar_fill = int(round((_pull / _max_pull) * 100))

            with st.expander(f"{_i}. {_aname}  {_trend_arrow}", expanded=False):
                _a1, _a2 = st.columns([3, 1])
                with _a1:
                    st.markdown(
                        f'<div class="aw-metric-label">Pull Strength</div>'
                        f'<div style="background:#2D3F52;border-radius:2px;height:8px;overflow:hidden;'
                        f'max-width:200px;margin-top:4px">'
                        f'<div style="width:{_bar_fill}%;background:#4A9FD4;height:100%"></div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with _a2:
                    _trend_label = "Rising" if _trend == "up" else ("Falling" if _trend == "down" else "Stable")
                    st.markdown(
                        f'<div class="aw-metric-label">Horizon</div>'
                        f'<div style="font-size:14px;font-weight:700;color:#D4DDE6">{_ahorizon}</div>'
                        f'<div class="aw-metric-label" style="margin-top:6px">Trend</div>'
                        f'<div style="font-size:12px;font-weight:600;color:{_trend_color}">{_trend_label}</div>'
                        f'<div class="aw-metric-label" style="margin-top:6px">Evidence Items</div>'
                        f'<div style="font-size:14px;font-weight:700;color:#D4DDE6">{_ev_count}</div>',
                        unsafe_allow_html=True,
                    )

                st.markdown('<div class="aw-divider"></div>', unsafe_allow_html=True)
                _ac1, _ac2 = st.columns(2)
                with _ac1:
                    st.markdown('<div class="aw-metric-label">Counterforces</div>', unsafe_allow_html=True)
                    if _counterforces:
                        st.markdown(
                            "".join(
                                f'<div class="aw-condition-item">'
                                f'<span style="color:#4ade80;margin-right:5px">\u2013</span>{c}'
                                f'</div>'
                                for c in _counterforces
                            ),
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            '<div class="aw-condition-item" style="color:#7A8FA6;font-style:italic">None</div>',
                            unsafe_allow_html=True,
                        )
                with _ac2:
                    st.markdown('<div class="aw-metric-label">Invalidation Conditions</div>', unsafe_allow_html=True)
                    if _inv_cond:
                        st.markdown(
                            "".join(
                                f'<div class="aw-condition-item">'
                                f'<span style="color:#6b7280;margin-right:5px">\u2013</span>{c}'
                                f'</div>'
                                for c in _inv_cond
                            ),
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            '<div class="aw-condition-item" style="color:#7A8FA6;font-style:italic">None</div>',
                            unsafe_allow_html=True,
                        )

    st.markdown('<div class="aw-divider"></div>', unsafe_allow_html=True)

    # -----------------------------------------------------------------------
    # SECTION 4 - PROPAGATION (5-bucket horizontal timeline)
    # -----------------------------------------------------------------------
    st.markdown(
        '<div class="aw-section-title">PROPAGATION</div>'
        '<div style="font-size:10px;color:#7A8FA6;margin-bottom:6px">'
        'Cross-domain propagation timeline'
        '</div>',
        unsafe_allow_html=True,
    )

    if not _sorted_seq:
        st.markdown(
            '<div class="aw-callout">No propagation data for this assessment.</div>',
            unsafe_allow_html=True,
        )
    else:
        _bottlenecks = _prop_data.get("bottlenecks", []) if isinstance(_prop_data, dict) else []
        _second_order = _prop_data.get("second_order_effects", []) if isinstance(_prop_data, dict) else []

        _bucket_order = ["T+0", "T+24h", "T+72h", "T+7d", "T+2-6w"]
        _bucket_map: Dict[str, list] = {}
        for _step in _sorted_seq:
            _tb = _step.get("time_bucket", "T+?")
            _bucket_map.setdefault(_tb, []).append(_step)

        _timeline_html = '<div style="display:flex;gap:0;overflow-x:auto;margin-bottom:12px">'
        for _bi, _bk in enumerate(_bucket_order):
            _bk_steps = _bucket_map.get(_bk, [])
            if _bk_steps:
                _domain_cell = " ".join(
                    f'<span class="aw-step-domain">{s.get("domain", "—")}</span>'
                    for s in _bk_steps
                )
                _ev_preview = _bk_steps[0].get("event", "")[:_MAX_EVENT_PREVIEW_LENGTH]
                _event_html = (
                    f'<div style="font-size:10px;color:#9AABB8;margin-top:4px;line-height:1.3">{_ev_preview}</div>'
                    if _ev_preview else ""
                )
            else:
                _domain_cell = '<span style="font-size:10px;color:#3a4a5a;font-style:italic">\u2014</span>'
                _event_html = ""

            _arrow = (
                '<span style="font-size:14px;color:#4A6FA5;padding:0 4px;align-self:center">\u2192</span>'
                if _bi < len(_bucket_order) - 1 else ""
            )
            _cell_opacity = "1" if _bk_steps else "0.4"
            _timeline_html += (
                f'<div style="flex:1;min-width:80px;opacity:{_cell_opacity}">'
                f'<div style="font-size:9px;font-weight:700;color:#4A6FA5;text-transform:uppercase;'
                f'letter-spacing:0.5px;text-align:center;margin-bottom:4px">{_bk}</div>'
                f'<div class="aw-card-compact" style="min-height:48px;text-align:center">'
                f'{_domain_cell}{_event_html}'
                f'</div>'
                f'</div>{_arrow}'
            )
        _timeline_html += "</div>"
        st.markdown(_timeline_html, unsafe_allow_html=True)

        if len(_sorted_seq) > 1:
            _trans_html = ""
            for _si in range(len(_sorted_seq) - 1):
                _d_from = _sorted_seq[_si].get("domain", "\u2014").title()
                _d_to = _sorted_seq[_si + 1].get("domain", "\u2014").title()
                _t_at = _sorted_seq[_si + 1].get("time_bucket", "")
                if _d_from != _d_to:
                    _trans_html += (
                        f'<span style="font-size:10px;color:#7A8FA6;margin-right:12px">'
                        f'<span style="color:#D4DDE6">{_d_from} \u2192 {_d_to}</span> at {_t_at}'
                        f'</span>'
                    )
            if _trans_html:
                st.markdown(f'<div style="margin-bottom:10px">{_trans_html}</div>', unsafe_allow_html=True)

        if _bottlenecks:
            st.markdown('<div class="aw-metric-label" style="margin-top:10px">Bottlenecks</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="aw-card-compact" style="border-left:3px solid #92400e">'
                + "".join(
                    f'<div class="aw-condition-item">'
                    f'<span style="color:#fbbf24;margin-right:5px">!</span>{b}'
                    f'</div>'
                    for b in _bottlenecks
                )
                + '</div>',
                unsafe_allow_html=True,
            )

        if _second_order:
            st.markdown('<div class="aw-metric-label" style="margin-top:10px">Second-order Effects</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="aw-card-compact">'
                + "".join(
                    f'<div class="aw-condition-item">'
                    f'<span style="color:#7A8FA6;margin-right:5px">\u2013</span>{e}'
                    f'</div>'
                    for e in _second_order
                )
                + '</div>',
                unsafe_allow_html=True,
            )

    st.markdown('<div class="aw-divider"></div>', unsafe_allow_html=True)

    # =======================================================================
    # SECTION 5 - STRUCTURAL COUPLING
    # =======================================================================
    st.markdown(
        '<div class="aw-section-title">STRUCTURAL COUPLING</div>'
        '<div style="font-size:10px;color:#7A8FA6;margin-bottom:6px">'
        'Domain-pair coupling strength \u2014 amplifying pairs highlighted'
        '</div>',
        unsafe_allow_html=True,
    )

    _coupling_pairs = _coupling_data.get("pairs", []) if isinstance(_coupling_data, dict) else []
    _sorted_pairs = sorted(_coupling_pairs, key=lambda x: float(x.get("coupling_strength", 0)), reverse=True)

    if not _sorted_pairs:
        st.markdown(
            '<div class="aw-callout">No coupling data for this assessment.</div>',
            unsafe_allow_html=True,
        )
    else:
        for _pair in _sorted_pairs:
            _da = _pair.get("domain_a", "\u2014")
            _db = _pair.get("domain_b", "\u2014")
            _cs = float(_pair.get("coupling_strength", 0))
            _is_amp = _pair.get("is_amplifying", False)
            _amp_label = _pair.get("amplification_label", "")

            _pair_color = "#9a3412" if _is_amp else "#4A6FA5"
            _pair_border = "#9a341244" if _is_amp else "#4A6FA544"
            _pair_bg = "#9a341211" if _is_amp else "#4A6FA511"

            _bar_pct = min(int(round((_cs / 3.0) * 100)), 100)
            _bar_color = "#f87171" if _is_amp else "#60a5fa"

            st.markdown(
                f'<div class="aw-card-compact" style="border-left:3px solid {_pair_color};margin-bottom:6px">'
                f'<div style="display:flex;align-items:center;justify-content:space-between">'
                f'<div style="display:flex;align-items:center;gap:8px">'
                f'<span class="aw-step-domain">{_da}</span>'
                f'<span style="color:#4A6FA5;font-size:12px">&#8596;</span>'
                f'<span class="aw-step-domain">{_db}</span>'
                f'</div>'
                f'<div style="display:flex;align-items:center;gap:8px">'
                f'<div style="width:80px;background:#2D3F52;border-radius:2px;height:4px;overflow:hidden">'
                f'<div style="width:{_bar_pct}%;background:{_bar_color};height:100%"></div>'
                f'</div>'
                f'<span style="font-size:12px;font-weight:700;color:#D4DDE6;min-width:32px;text-align:right">{_cs:.2f}</span>'
                f'<span class="aw-badge" style="background:{_pair_bg};color:{_pair_color};border:1px solid {_pair_border}">'
                f'{_amp_label or ("Amplifying" if _is_amp else "Moderate")}</span>'
                f'</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown('<div class="aw-divider"></div>', unsafe_allow_html=True)

    # =======================================================================
    # CHANGE AND EXPLANATION LAYER
    # =======================================================================

    # -----------------------------------------------------------------------
    # DELTA SINCE PRIOR UPDATE - full structural change card
    # -----------------------------------------------------------------------
    st.markdown('<div class="aw-section-title">DELTA SINCE PRIOR UPDATE</div>', unsafe_allow_html=True)

    if _is_first_run or not isinstance(_delta_data, dict) or not _delta_data:
        st.markdown(
            '<div class="aw-card">'
            '<div style="font-size:13px;color:#7A8FA6;font-style:italic">'
            'No baseline \u2014 first assessment run or no prior state available.'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        _thresh_dir = _delta_data.get("threshold_direction", "stable")
        _trigger_changes = _delta_data.get("trigger_ranking_changes", [])
        _attract_changes = _delta_data.get("attractor_pull_changes", [])
        _new_ev_count = _delta_data.get("new_evidence_count", 0)

        _reg_delta_color = "#9a3412" if _reg_changed else "#14532d"
        _reg_delta_label = "Regime shifted" if _reg_changed else "Regime stable"

        _thresh_delta_color = {
            "narrowing": "#9a3412", "widening": "#14532d", "stable": "#6b7280"
        }.get(_thresh_dir, "#6b7280")
        _thresh_delta_arrow = {
            "narrowing": "\u25bc", "widening": "\u25b2", "stable": "\u2192"
        }.get(_thresh_dir, "\u2192")
        _thresh_pct_delta = abs(float(_delta_data.get("damping_capacity_delta", 0)))
        _thresh_dir_label = (
            f'{_thresh_delta_arrow} {int(_thresh_pct_delta * 100)}% {_thresh_dir}'
            if _thresh_pct_delta > 0 else f'{_thresh_delta_arrow} {_thresh_dir}'
        )

        _trigger_rows_html = ""
        for _tc in (_trigger_changes if isinstance(_trigger_changes, list) else []):
            if isinstance(_tc, dict):
                _prev_r = _tc.get("previous", "")
                _curr_r = _tc.get("current", "")
                _tname_d = _tc.get("field", "Trigger")
                if _prev_r != _curr_r and _prev_r != "" and _curr_r != "":
                    _trigger_rows_html += (
                        f'<div style="font-size:11px;color:#7A8FA6;padding:2px 0">'
                        f'{_tname_d}: '
                        f'<span style="color:#D4DDE6;font-weight:600">#{_prev_r} \u2192 #{_curr_r}</span>'
                        f'</div>'
                    )

        _attractor_rows_html = ""
        for _ac in (_attract_changes if isinstance(_attract_changes, list) else []):
            if isinstance(_ac, dict):
                _a_prev = float(_ac.get("previous", 0))
                _a_curr = float(_ac.get("current", 0))
                _a_delta = _a_curr - _a_prev
                _a_name = _ac.get("field", "Attractor")
                _a_color = "#9a3412" if _a_delta > 0 else "#14532d" if _a_delta < 0 else "#6b7280"
                _attractor_rows_html += (
                    f'<div style="font-size:11px;color:#7A8FA6;padding:2px 0">'
                    f'{_a_name} pull: '
                    f'<span style="color:{_a_color};font-weight:600">{_a_delta:+.2f}</span>'
                    f'</div>'
                )

        _dd1, _dd2, _dd3, _dd4 = st.columns(4)
        with _dd1:
            st.markdown(
                f'<div class="aw-metric-card">'
                f'<div class="aw-metric-label">Regime</div>'
                f'<span class="aw-badge" style="background:{_reg_delta_color}22;color:{_reg_delta_color};'
                f'border:1px solid {_reg_delta_color}44">{_reg_delta_label}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with _dd2:
            st.markdown(
                f'<div class="aw-metric-card">'
                f'<div class="aw-metric-label">Threshold</div>'
                f'<div style="font-size:13px;font-weight:600;color:{_thresh_delta_color}">'
                f'{_thresh_dir_label}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with _dd3:
            _tr_content = (
                f'<div>{_trigger_rows_html}</div>'
                if _trigger_rows_html
                else '<div style="font-size:11px;color:#7A8FA6;font-style:italic">None</div>'
            )
            st.markdown(
                f'<div class="aw-metric-card">'
                f'<div class="aw-metric-label">Trigger Shifts</div>'
                f'{_tr_content}'
                f'</div>',
                unsafe_allow_html=True,
            )
        with _dd4:
            st.markdown(
                f'<div class="aw-metric-card">'
                f'<div class="aw-metric-label">New Evidence</div>'
                f'<div style="font-size:20px;font-weight:700;color:#D4DDE6">{_new_ev_count}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        if _attractor_rows_html:
            st.markdown(
                f'<div class="aw-card-compact" style="margin-top:4px">'
                f'<div class="aw-metric-label">Attractor Pull Changes</div>'
                f'{_attractor_rows_html}'
                f'</div>',
                unsafe_allow_html=True,
            )

    # -----------------------------------------------------------------------
    # BRIEF (collapsed)
    # -----------------------------------------------------------------------
    with st.expander("Forecast Brief", expanded=False):
        if isinstance(_brief_data, dict) and "error" in _brief_data:
            st.markdown(
                f'<div style="font-size:12px;color:#e05c5c">'
                f'Could not load brief: {_brief_data["error"]}</div>',
                unsafe_allow_html=True,
            )
        elif _brief_data:
            render_forecast_brief(_brief_data)
        else:
            st.markdown(
                '<div style="font-size:12px;color:#7A8FA6;font-style:italic">'
                'Brief data unavailable for this assessment.'
                '</div>',
                unsafe_allow_html=True,
            )

    # -----------------------------------------------------------------------
    # EVIDENCE (collapsed)
    # -----------------------------------------------------------------------
    with st.expander("Evidence", expanded=False):
        _ev_list = _ev_data.get("evidence", []) if isinstance(_ev_data, dict) else []
        _all_areas = sorted({e.get("impacted_area", "") for e in _ev_list if e.get("impacted_area")})
        _area_filter = st.selectbox(
            "Filter by impacted area",
            options=["All"] + _all_areas,
            key="ev_area_filter",
            label_visibility="collapsed",
        )
        _filtered_ev = (
            _ev_list if _area_filter == "All"
            else [e for e in _ev_list if e.get("impacted_area") == _area_filter]
        )

        if not _filtered_ev:
            st.markdown(
                '<div style="font-size:12px;color:#7A8FA6;font-style:italic">No evidence items.</div>',
                unsafe_allow_html=True,
            )
        else:
            for _ev in _filtered_ev:
                _ev_src = _ev.get("source", "\u2014")
                _ev_ts = _fmt_ts(_ev.get("timestamp", ""))
                _ev_qual = _ev.get("source_quality", "\u2014")
                _ev_area = _ev.get("impacted_area", "\u2014")
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
    # TRACE (collapsed)
    # -----------------------------------------------------------------------
    with st.expander("Trace", expanded=False):
        _path_id = _brief_data.get("reasoning_path_id") if isinstance(_brief_data, dict) else None

        if _path_id:
            from utils.api_client import api_client as _api_client_inst
            _trace_data = _api_client_inst.get_reasoning_path(_path_id)
            if "error" in _trace_data:
                st.markdown(
                    f'<div style="font-size:11px;color:#7A8FA6;font-style:italic">'
                    f'Reasoning path not available: {_trace_data["error"]}</div>',
                    unsafe_allow_html=True,
                )
                st.json({
                    "trace_version": "1.0",
                    "assessment_id": _assessment_id,
                    "note": "Live trace unavailable \u2014 showing structural stub",
                    "path_id_attempted": _path_id,
                })
            else:
                st.json(_trace_data)
        else:
            _conf_float = {"High": 0.81, "Medium": 0.62, "Low": 0.41}.get(str(_confidence), 0.55)
            _damping_penalty = round(
                -(1.0 - float(_regime_data.get("damping_capacity", 0.5) if isinstance(_regime_data, dict) else 0.5)) * 0.15,
                3,
            ) if _regime_data else -0.07
            st.json({
                "trace_version": "1.1",
                "assessment_id": _assessment_id,
                "confidence_decomposition": {
                    "final_confidence": _conf_float,
                    "damping_penalty": _damping_penalty,
                    "regime": _regime_name,
                    "threshold_distance": _regime_thresh,
                },
                "note": "No reasoning_path_id in brief \u2014 structural decomposition only",
            })


# ===========================================================================
# RIGHT COLUMN - Lightweight supporting context only
# ===========================================================================

with _right_col:

    _conf_color_r = {"High": "#4caf7d", "Medium": "#e8a742", "Low": "#e05c5c"}.get(
        str(_confidence), "#7A8FA6"
    )
    st.markdown(
        f'<div class="aw-metric-card">'
        f'<div class="aw-metric-label">Confidence</div>'
        f'<div class="aw-metric-value" style="color:{_conf_color_r}">{_confidence}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    _damping = float(_regime_data.get("damping_capacity", 0)) if isinstance(_regime_data, dict) else 0.0
    _rev_index = float(_regime_data.get("reversibility_index", 0)) if isinstance(_regime_data, dict) else 0.0
    st.markdown(
        f'<div class="aw-metric-card">'
        f'<div class="aw-metric-label">Damping Capacity</div>'
        f'<div style="font-size:16px;font-weight:700;color:#D4DDE6">{_damping:.2f}</div>'
        f'<div class="aw-metric-label" style="margin-top:6px">Reversibility</div>'
        f'<div style="font-size:16px;font-weight:700;color:#D4DDE6">{_rev_index:.2f}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    _cp_pairs = _coupling_data.get("pairs", []) if isinstance(_coupling_data, dict) else []
    _amp_count = sum(1 for p in _cp_pairs if p.get("is_amplifying", False))
    _max_cs_pair = max(_cp_pairs, key=lambda x: float(x.get("coupling_strength", 0)), default=None)
    _max_cs_label = (
        f'{_max_cs_pair.get("domain_a", _EM)} \u2194 {_max_cs_pair.get("domain_b", _EM)}'
        if _max_cs_pair else _EM
    )
    _max_cs_val = float(_max_cs_pair.get("coupling_strength", 0)) if _max_cs_pair else 0.0
    st.markdown(
        f'<div class="aw-metric-card">'
        f'<div class="aw-metric-label">Amplifying Pairs</div>'
        f'<div class="aw-metric-value" style="color:#f87171">{_amp_count}</div>'
        f'<div class="aw-metric-label" style="margin-top:6px">Strongest Coupling</div>'
        f'<div style="font-size:10px;font-weight:600;color:#D4DDE6;margin-top:2px">{_max_cs_label}</div>'
        f'<div style="font-size:13px;font-weight:700;color:#C8A84B">{_max_cs_val:.2f}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    _ev_items_r = _ev_data.get("evidence", []) if isinstance(_ev_data, dict) else []
    st.markdown(
        f'<div class="aw-metric-card">'
        f'<div class="aw-metric-label">Source Count</div>'
        f'<div class="aw-metric-value">{len(_ev_items_r)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="aw-section-title">Watch Next</div>', unsafe_allow_html=True)
    _watch_signals = _sorted_triggers[0].get("watch_signals", []) if _sorted_triggers else []
    if _watch_signals:
        st.markdown(
            '<div class="aw-card-compact">'
            + "".join(
                f'<div class="aw-condition-item">'
                f'<span style="color:#C8A84B;margin-right:5px">\u25c6</span>{s}'
                f'</div>'
                for s in _watch_signals
            )
            + '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="aw-card-compact">'
            '<div style="font-size:11px;color:#7A8FA6;font-style:italic">No watch signals</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="aw-section-title">Recent Evidence</div>', unsafe_allow_html=True)
    _sorted_ev_r = sorted(
        _ev_items_r, key=lambda x: x.get("timestamp", ""), reverse=True
    )[:2]

    if _sorted_ev_r:
        for _ev_r in _sorted_ev_r:
            _ev_src_r = _ev_r.get("source", "\u2014")
            _ev_ts_r = _fmt_ts(_ev_r.get("timestamp", ""))
            _ev_qual_r = _ev_r.get("source_quality", "\u2014")
            _ev_area_r = _ev_r.get("impacted_area", "\u2014")
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
    else:
        st.markdown(
            '<div class="aw-card-compact">'
            '<div style="font-size:11px;color:#7A8FA6;font-style:italic">No evidence items</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    if _region_tags or _domain_tags:
        st.markdown('<div class="aw-section-title">Linked Entities</div>', unsafe_allow_html=True)
        _all_tags = _region_tags + _domain_tags
        st.markdown(
            '<div class="aw-card-compact" style="line-height:1.8">'
            + " ".join(
                f'<span class="aw-domain-badge" style="margin-bottom:3px">{t}</span>'
                for t in _all_tags
            )
            + '</div>',
            unsafe_allow_html=True,
        )
