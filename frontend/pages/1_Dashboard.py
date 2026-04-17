"""
Dashboard – EL-DRUIN Structural Forecast Command Surface
=========================================================

Primary question: "Is any watched system leaving its linear response regime?"

Layout:
  Top  – Global Structural Alert Bar (full width, one line)
  A    – 4 Structural Status Cards
  B    – Priority Assessments Table (sorted by threshold_distance ascending)
  C    – Top Triggers | Top Attractors split panel
  D    – Structural Change Feed (last 10 structural events)
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import streamlit as st

_FRONTEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FRONTEND_DIR not in sys.path:
    sys.path.insert(0, _FRONTEND_DIR)

st.set_page_config(
    page_title="Dashboard – EL-DRUIN",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    from components.sidebar import render_sidebar_navigation
    st.session_state["current_page"] = "Dashboard"
    render_sidebar_navigation(is_subpage=True)
except Exception:
    pass

from utils.api_client import (  # noqa: E402
    get_assessments,
    get_regime,
    get_triggers,
    get_attractors,
    get_delta,
    get_probability_tree,
)

# ---------------------------------------------------------------------------
# CSS – mirror design tokens from app.py
# ---------------------------------------------------------------------------

st.markdown("""
<style>
:root {
  --blue: #3B6EA8;
  --blue-dark: #2A5280;
  --blue-accent: #4A8FD4;
  --gold: #C8A84B;
  --gold-dark: #A8882A;
  --red: #C0392B;
  --red-dark: #A93226;
  --bg: #0F1923;
  --surface: #162030;
  --surface-raised: #1E2D3D;
  --border: #2D3F52;
  --text: #D4DDE6;
  --text-strong: #EDF2F7;
  --muted: #7A8FA6;
  --tag-bg: #1A2D42;
}
.stApp { background-color: var(--bg); color: var(--text); }
h1, h2, h3, h4 {
  color: var(--text-strong) !important;
  font-weight: 600;
  letter-spacing: -0.01em;
}
[data-testid="stSidebar"] {
  background-color: #0A1520 !important;
  border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] * { color: var(--muted); }

/* Alert bar */
.alert-bar {
    padding: 10px 18px;
    border-radius: 3px;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.4px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 18px;
    border: 1px solid;
}
.alert-bar-linear    { background: #0A1520; color: #4A8FD4; border-color: #2D4A66; }
.alert-bar-stress    { background: #1A1500; color: #C8A84B; border-color: #4A3820; }
.alert-bar-nonlinear { background: #200A0A; color: #E05050; border-color: #5A1818; }
.alert-bar-cascade   { background: #200808; color: #FF4444; border-color: #6A0808; }

/* Status cards */
.stat-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 14px 16px;
    height: 110px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}
.stat-card-label {
    font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 1.2px; color: var(--muted);
}
.stat-card-value {
    font-size: 32px; font-weight: 800; color: var(--text-strong);
    line-height: 1;
}
.stat-card-sub {
    font-size: 11px; color: var(--muted);
}

/* Regime badge */
.regime-badge {
    display: inline-block;
    padding: 3px 9px; border-radius: 2px;
    font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px;
}
.regime-linear       { background: #0A1520; color: #4A8FD4; border: 1px solid #2D4A66; }
.regime-stress       { background: #1A1500; color: #C8A84B; border: 1px solid #4A3820; }
.regime-nonlinear    { background: #1A0808; color: #E05050; border: 1px solid #4A1818; }
.regime-cascade      { background: #1A0808; color: #FF4444; border: 1px solid #5A1010; }
.regime-convergence  { background: #0F1A2A; color: #9B72CF; border: 1px solid #3A2050; }
.regime-dissipating  { background: #0F1A0F; color: #4CAF72; border: 1px solid #1E4228; }

/* Threshold bar */
.thresh-wrap { background: #1A2D3D; border-radius: 2px; height: 5px; overflow: hidden; margin: 3px 0; width: 100%; }
.thresh-bar  { height: 5px; border-radius: 2px; }

/* Priority table row */
.prio-row {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 10px 12px;
    margin-bottom: 5px;
}
.prio-title { font-size: 13px; font-weight: 600; color: var(--text-strong); }
.prio-meta  { font-size: 11px; color: var(--muted); margin-top: 2px; }

/* Trigger / Attractor items */
.ta-item {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 10px 12px;
    margin-bottom: 6px;
}
.ta-name  { font-size: 13px; font-weight: 600; color: var(--text-strong); }
.ta-meta  { font-size: 11px; color: var(--muted); margin-top: 3px; }
.ta-score { font-size: 13px; font-weight: 700; color: #C8A84B; }

/* Change feed */
.feed-item {
    background: var(--surface);
    border-left: 3px solid var(--border);
    border-radius: 0 3px 3px 0;
    padding: 7px 10px;
    margin-bottom: 4px;
    font-size: 12px;
    color: var(--text);
    display: flex;
    align-items: flex-start;
    gap: 8px;
}
.feed-icon { font-size: 14px; min-width: 18px; }
.feed-time { color: var(--muted); min-width: 120px; font-size: 11px; }
.feed-title { font-weight: 600; color: var(--text-strong); min-width: 120px; font-size: 11px; }
.feed-desc  { color: var(--text); font-size: 12px; }
.feed-regime  { border-left-color: #E05050; }
.feed-narrow  { border-left-color: #C8A84B; }
.feed-trigger { border-left-color: #4A8FD4; }
.feed-attractor { border-left-color: #9B72CF; }

/* Section headers */
.section-hdr {
    font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 1.4px; color: var(--muted);
    padding: 8px 0 6px 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 12px;
}

/* Offline badge */
.offline-badge {
    display: inline-block;
    background: #1A1500; color: #C8A84B;
    border: 1px solid #4A3820;
    border-radius: 2px; padding: 2px 8px;
    font-size: 10px; font-weight: 700; letter-spacing: 0.8px;
}

/* Streamlit overrides */
.stButton button {
    background: var(--surface-raised) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    border-radius: 2px !important;
    font-size: 11px !important;
}
[data-testid="stMetric"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 10px 14px;
}
hr { border-color: var(--border) !important; opacity: 0.5; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REGIME_ORDER: List[str] = [
    "Linear",
    "Stress Accumulation",
    "Nonlinear Escalation",
    "Cascade Risk",
    "Attractor Lock-in",
]

_REGIME_CSS_CLASS: Dict[str, str] = {
    "Linear": "regime-linear",
    "Stress Accumulation": "regime-stress",
    "Nonlinear Escalation": "regime-nonlinear",
    "Cascade Risk": "regime-cascade",
    "Attractor Lock-in": "regime-convergence",
}

_ALERT_LEVEL_CSS: Dict[str, str] = {
    "Linear": "alert-bar-linear",
    "Stress Accumulation": "alert-bar-stress",
    "Nonlinear Escalation": "alert-bar-nonlinear",
    "Cascade Risk": "alert-bar-cascade",
    "Attractor Lock-in": "alert-bar-cascade",
}

_THRESH_BAR_COLOR: Dict[str, str] = {
    "Linear": "#4A8FD4",
    "Stress Accumulation": "#C8A84B",
    "Nonlinear Escalation": "#E05050",
    "Cascade Risk": "#FF4444",
    "Attractor Lock-in": "#9B72CF",
}

# Scaling factor: raw amplification_factor [0–1] → display multiplier (×N)
_AMP_DISPLAY_MULTIPLIER: float = 5.0
# Maximum chars for short assessment title display
_TITLE_SHORT_LEN: int = 28
# Cache TTL in seconds (5 minutes)
_CACHE_TTL_SECONDS: int = 300

# ---------------------------------------------------------------------------
# Data loading (cached 5 min)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=_CACHE_TTL_SECONDS)
def _load_assessment_data(assessment_id: str) -> Dict[str, Any]:
    """Load all structural data for one assessment, cached 5 min."""
    return {
        "regime": get_regime(assessment_id),
        "triggers": get_triggers(assessment_id),
        "attractors": get_attractors(assessment_id),
        "delta": get_delta(assessment_id),
        "probability_tree": get_probability_tree(assessment_id),
    }


def _is_stub_data(regime: Dict[str, Any]) -> bool:
    """Return True if this looks like offline stub data (assessment_id == ae-204)."""
    return regime.get("assessment_id") == "ae-204"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _regime_severity(regime_label: str) -> int:
    """Return a comparable severity integer (higher = more severe)."""
    try:
        return _REGIME_ORDER.index(regime_label)
    except ValueError:
        return 0


def _regime_badge(regime_label: str) -> str:
    css = _REGIME_CSS_CLASS.get(regime_label, "regime-linear")
    return f'<span class="regime-badge {css}">{regime_label}</span>'


def _amp_arrow(amp: float) -> str:
    if amp >= 0.7:
        return "↑"
    if amp >= 0.4:
        return "→"
    return "↓"


def _pull_arrow(trend: str) -> str:
    arrows = {"up": "↑", "stable": "→", "down": "↓"}
    return arrows.get(trend, "→")


def _jump_label(jump: str) -> str:
    colors = {
        "Critical": "#E05050",
        "High": "#C8A84B",
        "Moderate": "#7A8FA6",
        "Low": "#4A8FD4",
    }
    c = colors.get(jump, "#7A8FA6")
    return f'<span style="color:{c};font-weight:700;">{jump}</span>'


def _fmt_updated(updated_at: str) -> str:
    """Format ISO timestamp to readable string."""
    try:
        dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y %H:%M UTC")
    except Exception:
        return updated_at or "—"


def _thresh_bar_html(threshold_distance: float, regime: str) -> str:
    # Bar fill shows "how much headroom remains" (higher fill = farther from threshold)
    fill = max(0.0, min(1.0, 1.0 - threshold_distance))
    fill_pct = int(fill * 100)
    # Label shows threshold_distance directly: lower % = closer to tipping point
    label_pct = int(round(max(0.0, min(1.0, threshold_distance)) * 100))
    color = _THRESH_BAR_COLOR.get(regime, "#4A8FD4")
    return (
        f'<div class="thresh-wrap">'
        f'<div class="thresh-bar" style="width:{fill_pct}%;background:{color};"></div>'
        f'</div>'
        f'<span style="font-size:11px;color:#D4DDE6;" title="distance to threshold — lower = more dangerous">{label_pct}%↓</span>'
    )


# ---------------------------------------------------------------------------
# Load all data
# ---------------------------------------------------------------------------

assessments_raw = get_assessments()
if not isinstance(assessments_raw, list):
    assessments_raw = []

# Enrich each assessment with structural data
enriched: List[Dict[str, Any]] = []
all_offline = True
for asm in assessments_raw:
    aid = asm.get("assessment_id", "")
    data = _load_assessment_data(aid) if aid else {
        "regime": {}, "triggers": {}, "attractors": {}, "delta": {}, "probability_tree": {}
    }
    regime = data["regime"]
    triggers_data = data["triggers"]
    attractors_data = data["attractors"]
    delta = data["delta"]
    probability_tree = data.get("probability_tree", {})

    if not _is_stub_data(regime):
        all_offline = False

    enriched.append({
        "assessment": asm,
        "regime": regime,
        "triggers": triggers_data.get("triggers", []),
        "attractors": attractors_data.get("attractors", []),
        "delta": delta,
        "probability_tree": probability_tree,
        "updated_at": regime.get("updated_at") or asm.get("updated_at", ""),
    })

# ---------------------------------------------------------------------------
# Patch threshold_distance and regime_changed from assessment metadata when the
# regime engine returns conservative defaults for assessments that lack rich
# context (e.g. empty mechanisms/bifurcation data).
#
# _REGIME_TD_DEFAULTS maps each regime label to a representative
# threshold_distance used when the engine cannot compute a reliable value:
#   - "Cascade Risk" / "Attractor Lock-in": deeply non-linear, very close to
#     the tipping threshold (< 0.1).
#   - "Nonlinear Escalation": in the non-linear band but not yet at cascade
#     risk (~0.18).
#   - "Stress Accumulation": mid-range, approaching non-linear territory (~0.35).
#   - "Linear" / "Dissipating": comfortably away from threshold (> 0.5).
# ---------------------------------------------------------------------------
_REGIME_TD_DEFAULTS: Dict[str, float] = {
    "Nonlinear Escalation": 0.18,
    "Cascade Risk": 0.08,
    "Attractor Lock-in": 0.05,
    "Stress Accumulation": 0.35,
    "Linear": 0.65,
    "Dissipating": 0.50,
}

# Regimes where the engine's threshold_distance should be overridden when it
# returns a value >= _ENGINE_TD_OVERRIDE_THRESHOLD (i.e., appears safe) but
# the stored assessment regime says otherwise.
_HIGH_RISK_REGIMES = ("Nonlinear Escalation", "Cascade Risk", "Attractor Lock-in")

# Threshold_distance above which the engine's value is considered too conservative
# to trust when the stored regime indicates high risk.
_ENGINE_TD_OVERRIDE_THRESHOLD = 0.90  # only override clearly erroneous values (> 90%)

# Regimes that definitively indicate a structural regime change has occurred.
_REGIME_SHIFTED_REGIMES = ("Nonlinear Escalation", "Cascade Risk")

for _e in enriched:
    _regime = _e["regime"]
    _asm = _e["assessment"]
    _engine_td = _regime.get("threshold_distance", 1.0)
    _stored_regime = _asm.get("last_regime", "")
    # If engine returns >= threshold but metadata says high-risk, use metadata-derived
    # threshold_distance so NEAR THRESHOLD counts are correct.
    if _engine_td >= _ENGINE_TD_OVERRIDE_THRESHOLD and _stored_regime in _HIGH_RISK_REGIMES:
        _fallback_td = _REGIME_TD_DEFAULTS.get(_stored_regime, _engine_td)
        if _fallback_td < _engine_td:
            _regime["threshold_distance"] = _fallback_td
    # Patch regime_changed in delta: flag based on high-risk stored regime when
    # the delta engine (which has no persistent history across restarts) hasn't.
    _delta = _e["delta"]
    if not _delta.get("regime_changed") and _stored_regime in _REGIME_SHIFTED_REGIMES:
        _delta["regime_changed"] = True
        if not _delta.get("summary"):
            _delta["summary"] = f"Regime elevated to {_stored_regime} based on structural assessment."
        if not _delta.get("threshold_direction"):
            _delta["threshold_direction"] = "narrowing"

# Sort by threshold_distance ascending (most dangerous first)
enriched.sort(key=lambda e: e["regime"].get("threshold_distance", 1.0))

# ---------------------------------------------------------------------------
# Compute global aggregates
# ---------------------------------------------------------------------------

worst_regime = "Linear"
near_threshold_items: List[Dict[str, Any]] = []
regime_shifted_items: List[Dict[str, Any]] = []
high_amp_triggers: List[Dict[str, Any]] = []

for e in enriched:
    regime = e["regime"]
    asm = e["assessment"]
    delta = e["delta"]
    regime_label = regime.get("current_regime", "Linear")

    if _regime_severity(regime_label) > _regime_severity(worst_regime):
        worst_regime = regime_label

    if regime.get("threshold_distance", 1.0) < 0.25:
        near_threshold_items.append(e)

    if delta.get("regime_changed"):
        regime_shifted_items.append(e)

    for t in e["triggers"]:
        if t.get("amplification_factor", 0) > 0.7:
            high_amp_triggers.append({
                "trigger": t,
                "assessment": asm,
                "regime": regime,
            })

top_amp_factor = max(
    (h["trigger"].get("amplification_factor", 0) for h in high_amp_triggers),
    default=0.0,
)
now_str = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")

# ---------------------------------------------------------------------------
# TOP: Global Structural Alert Bar
# ---------------------------------------------------------------------------

alert_css = _ALERT_LEVEL_CSS.get(worst_regime, "alert-bar-linear")
near_count = len(near_threshold_items)
shifted_count = len(regime_shifted_items)

near_text = f"{near_count} Near Threshold"
shifted_text = f"{shifted_count} Regime Shift (24h)"
offline_html = (
    '<span class="offline-badge">OFFLINE — showing cached data</span>&nbsp;&nbsp;'
    if all_offline and assessments_raw
    else ""
)

_alert_html = (
    f'<div class="alert-bar {alert_css}">'
    f'<span>{offline_html}'
    f'<strong>STRUCTURAL ALERT LEVEL: {worst_regime.upper()}</strong></span>'
    f'<span style="font-size:12px;font-weight:400;">'
    f'{near_text}&nbsp;&nbsp;|&nbsp;&nbsp;{shifted_text}&nbsp;&nbsp;|&nbsp;&nbsp;Updated: {now_str}'
    f'</span></div>'
)
st.markdown(_alert_html, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Section A: 4 Structural Status Cards
# ---------------------------------------------------------------------------

st.markdown('<div class="section-hdr">Structural Status</div>', unsafe_allow_html=True)

active_count = sum(
    1 for e in enriched if e["assessment"].get("status") == "active"
)
near_names = ", ".join(
    e["assessment"].get("title", "—")[:_TITLE_SHORT_LEN] for e in near_threshold_items[:3]
) or "—"
shifted_labels = ", ".join(
    e["regime"].get("current_regime", "")[:20] for e in regime_shifted_items[:3]
) or "—"
top_amp_display = f"×{top_amp_factor * _AMP_DISPLAY_MULTIPLIER:.1f}" if top_amp_factor > 0 else "—"

card_col1, card_col2, card_col3, card_col4 = st.columns([1, 1, 1, 1])

with card_col1:
    st.markdown(
        f"""
        <div class="stat-card">
            <div class="stat-card-label">Active Assessments</div>
            <div class="stat-card-value">{active_count}</div>
            <div class="stat-card-sub">tracked systems</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with card_col2:
    st.markdown(
        f"""
        <div class="stat-card">
            <div class="stat-card-label">Near Threshold ▲</div>
            <div class="stat-card-value" style="color:#C8A84B;">{near_count}</div>
            <div class="stat-card-sub" title="{near_names}">threshold &lt;25%&nbsp;&nbsp;{near_names[:32]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with card_col3:
    st.markdown(
        f"""
        <div class="stat-card">
            <div class="stat-card-label">Regime Shifted ⚠ (24h)</div>
            <div class="stat-card-value" style="color:#E05050;">{shifted_count}</div>
            <div class="stat-card-sub" title="{shifted_labels}">{shifted_labels[:36]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with card_col4:
    st.markdown(
        f"""
        <div class="stat-card">
            <div class="stat-card-label">Amplification Alerts ↗</div>
            <div class="stat-card-value" style="color:#C8A84B;">{len(high_amp_triggers)}</div>
            <div class="stat-card-sub">trigger {top_amp_display}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Section B: Priority Assessments Table
# ---------------------------------------------------------------------------

st.markdown('<div class="section-hdr">Priority Assessments — sorted by threshold proximity</div>', unsafe_allow_html=True)

if not enriched:
    st.info("No assessments loaded. Check backend connectivity.")
else:
    # Table header
    hdr_cols = st.columns([3, 2, 2, 3, 2, 2, 1])
    labels = ["Assessment", "Regime", "Threshold", "Top Trigger (amp)", "Top Attractor", "Delta", ""]
    for col, lbl in zip(hdr_cols, labels):
        with col:
            st.markdown(
                f'<div style="font-size:10px;font-weight:700;text-transform:uppercase;'
                f'letter-spacing:1px;color:#7A8FA6;padding-bottom:4px;'
                f'border-bottom:1px solid #2D3F52;">{lbl}</div>',
                unsafe_allow_html=True,
            )

    for e in enriched:
        asm = e["assessment"]
        regime = e["regime"]
        delta = e["delta"]
        triggers = e["triggers"]
        attractors = e["attractors"]
        probability_tree = e.get("probability_tree", {})
        aid = asm.get("assessment_id", "")
        title = asm.get("title", "—")
        regime_label = regime.get("current_regime", "Linear")
        thresh_dist = regime.get("threshold_distance", 1.0)
        is_phase_transition = bool(probability_tree.get("is_phase_transition", False))

        # Top trigger
        top_trig = triggers[0] if triggers else None
        if top_trig:
            t_amp = top_trig.get("amplification_factor", 0)
            t_arrow = _amp_arrow(t_amp)
            t_name = top_trig.get("name", "—")[:26]
            trig_cell = f"{t_name} ×{t_amp * _AMP_DISPLAY_MULTIPLIER:.1f} {t_arrow}"
        else:
            trig_cell = "—"

        # Top attractor
        top_attr = attractors[0] if attractors else None
        if top_attr:
            a_pull = top_attr.get("pull_strength", 0)
            a_trend = top_attr.get("trend", "stable")
            a_name = top_attr.get("name", "—")[:22]
            attr_cell = f"{a_name} {a_pull:.2f} {_pull_arrow(a_trend)}"
        else:
            attr_cell = "—"

        # Delta summary
        if delta.get("regime_changed"):
            delta_html = '<span style="color:#E05050;font-weight:700;">Regime ⚠</span>'
        elif delta.get("threshold_direction") == "narrowing":
            delta_html = '<span style="color:#C8A84B;font-weight:700;">Narrowing ▼</span>'
        else:
            delta_html = '<span style="color:#4CAF72;font-weight:600;">Stable →</span>'

        row_cols = st.columns([3, 2, 2, 3, 2, 2, 1])

        with row_cols[0]:
            st.markdown(
                f'<div style="padding:6px 0;font-size:12px;color:#D4DDE6;font-weight:600;">{title[:40]}</div>',
                unsafe_allow_html=True,
            )

        with row_cols[1]:
            st.markdown(
                f'<div style="padding:6px 0;">{_regime_badge(regime_label)}</div>',
                unsafe_allow_html=True,
            )

        with row_cols[2]:
            thresh_html = _thresh_bar_html(thresh_dist, regime_label)
            phase_icon = ' <span title="P-adic phase transition detected" style="color:#FFD700;">⚡</span>' if is_phase_transition else ""
            st.markdown(
                f'<div style="padding:6px 0;">{thresh_html}{phase_icon}</div>',
                unsafe_allow_html=True,
            )

        with row_cols[3]:
            st.markdown(
                f'<div style="padding:6px 0;font-size:11px;color:#D4DDE6;">{trig_cell}</div>',
                unsafe_allow_html=True,
            )

        with row_cols[4]:
            st.markdown(
                f'<div style="padding:6px 0;font-size:11px;color:#D4DDE6;">{attr_cell}</div>',
                unsafe_allow_html=True,
            )

        with row_cols[5]:
            st.markdown(
                f'<div style="padding:6px 0;">{delta_html}</div>',
                unsafe_allow_html=True,
            )

        with row_cols[6]:
            if aid and st.button("→", key=f"open_{aid}", help=f"Open {title}"):
                st.session_state["current_page"] = "Assessments"
                st.session_state["selected_assessment_id"] = aid
                st.switch_page("pages/2_Assessments.py")

    st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Section C: Top Triggers | Top Attractors
# ---------------------------------------------------------------------------

st.markdown('<div class="section-hdr">Cross-System Signal Surface</div>', unsafe_allow_html=True)

# Build global trigger list (deduplicated by name, sorted by amp_factor desc)
all_triggers: List[Dict[str, Any]] = []
seen_trigger_names: set = set()
for e in enriched:
    asm = e["assessment"]
    for t in e["triggers"]:
        name = t.get("name", "")
        if name and name not in seen_trigger_names:
            seen_trigger_names.add(name)
            all_triggers.append({
                "trigger": t,
                "assessment_title": asm.get("title", "—"),
            })
all_triggers.sort(key=lambda x: x["trigger"].get("amplification_factor", 0), reverse=True)
top_triggers = all_triggers[:5]

# Build global attractor list (sorted by pull_strength desc)
all_attractors: List[Dict[str, Any]] = []
seen_attr_names: set = set()
for e in enriched:
    asm = e["assessment"]
    for a in e["attractors"]:
        name = a.get("name", "")
        if name and name not in seen_attr_names:
            seen_attr_names.add(name)
            all_attractors.append({
                "attractor": a,
                "assessment_title": asm.get("title", "—"),
            })
all_attractors.sort(key=lambda x: x["attractor"].get("pull_strength", 0), reverse=True)
top_attractors = all_attractors[:5]

col_trig, col_attr = st.columns([1, 1])

with col_trig:
    st.markdown(
        '<div style="font-size:11px;font-weight:700;text-transform:uppercase;'
        'letter-spacing:1px;color:#7A8FA6;margin-bottom:10px;">'
        'TOP TRIGGERS by amplification factor</div>',
        unsafe_allow_html=True,
    )
    if not top_triggers:
        st.markdown('<div style="color:#7A8FA6;font-size:12px;">No trigger data available.</div>', unsafe_allow_html=True)
    else:
        for i, item in enumerate(top_triggers, 1):
            t = item["trigger"]
            a_title = item["assessment_title"]
            amp = t.get("amplification_factor", 0)
            arrow = _amp_arrow(amp)
            name = t.get("name", "—")
            domains = " · ".join(t.get("impacted_domains", []))
            jump = t.get("jump_potential", "—")
            lag = t.get("expected_lag_hours", "—")
            amp_display = amp * _AMP_DISPLAY_MULTIPLIER
            jump_html = _jump_label(jump)
            st.markdown(
                f"""
                <div class="ta-item">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <span class="ta-name">{i}. {name}</span>
                        <span class="ta-score">×{amp_display:.1f} {arrow}</span>
                    </div>
                    <div class="ta-meta">{domains}</div>
                    <div class="ta-meta">Jump: {jump_html}&nbsp;&nbsp;lag: {lag}h</div>
                    <div class="ta-meta" style="color:#4A8FD4;">{a_title[:40]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

with col_attr:
    st.markdown(
        '<div style="font-size:11px;font-weight:700;text-transform:uppercase;'
        'letter-spacing:1px;color:#7A8FA6;margin-bottom:10px;">'
        'TOP ATTRACTORS by pull strength</div>',
        unsafe_allow_html=True,
    )
    if not top_attractors:
        st.markdown('<div style="color:#7A8FA6;font-size:12px;">No attractor data available.</div>', unsafe_allow_html=True)
    else:
        for i, item in enumerate(top_attractors, 1):
            a = item["attractor"]
            a_title = item["assessment_title"]
            pull = a.get("pull_strength", 0)
            trend = a.get("trend", "stable")
            arrow = _pull_arrow(trend)
            name = a.get("name", "—")
            horizon = a.get("horizon", "—")
            cf_count = len(a.get("counterforces", []))
            st.markdown(
                f"""
                <div class="ta-item">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <span class="ta-name">{i}. {name}</span>
                        <span class="ta-score">pull: {pull:.2f} {arrow}</span>
                    </div>
                    <div class="ta-meta">horizon: {horizon}&nbsp;&nbsp;{cf_count} counterforce(s)</div>
                    <div class="ta-meta" style="color:#4A8FD4;">{a_title[:40]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Section D: Structural Change Feed
# ---------------------------------------------------------------------------

st.markdown('<div class="section-hdr">Structural Change Feed — last 10 structural events</div>', unsafe_allow_html=True)

feed_entries: List[Dict[str, Any]] = []

for e in enriched:
    asm = e["assessment"]
    delta = e["delta"]
    updated_at = e.get("updated_at", "")
    short_title = asm.get("title", "—")[:_TITLE_SHORT_LEN]

    if delta.get("regime_changed"):
        summary = delta.get("summary", "Regime changed")
        # Split on first period, then apply char limit to avoid mid-word cuts
        parts = summary.split(".") if summary else []
        first_sentence = (parts[0][:80] if parts else "Regime shifted") if summary else "Regime shifted"
        feed_entries.append({
            "icon": "⚠",
            "css_extra": "feed-regime",
            "time": updated_at,
            "title": short_title,
            "desc": first_sentence,
            "sort_key": updated_at,
        })

    if delta.get("threshold_direction") == "narrowing":
        feed_entries.append({
            "icon": "▼",
            "css_extra": "feed-narrow",
            "time": updated_at,
            "title": short_title,
            "desc": "Threshold narrowing",
            "sort_key": updated_at,
        })

    for chg in delta.get("trigger_ranking_changes", []):
        if chg.get("current") == 1 and chg.get("direction") == "increased":
            field = chg.get("field", "Trigger")
            feed_entries.append({
                "icon": "↑",
                "css_extra": "feed-trigger",
                "time": updated_at,
                "title": short_title,
                "desc": field + " rose to #1",
                "sort_key": updated_at,
            })

    for chg in delta.get("attractor_pull_changes", []):
        if chg.get("direction") == "increased":
            field = chg.get("field", "Attractor")
            feed_entries.append({
                "icon": "→",
                "css_extra": "feed-attractor",
                "time": updated_at,
                "title": short_title,
                "desc": field + " pull increasing",
                "sort_key": updated_at,
            })

# Sort by updated_at descending, take top 10
feed_entries.sort(key=lambda x: x.get("sort_key", ""), reverse=True)
feed_entries = feed_entries[:10]

if not feed_entries:
    st.markdown(
        '<div style="color:#7A8FA6;font-size:12px;padding:10px 0;">'
        'No structural changes detected in current data.</div>',
        unsafe_allow_html=True,
    )
else:
    for entry in feed_entries:
        time_fmt = _fmt_updated(entry["time"])
        icon = entry["icon"]
        css_extra = entry["css_extra"]
        title = entry["title"]
        desc = entry["desc"]
        st.markdown(
            f"""
            <div class="feed-item {css_extra}">
                <span class="feed-icon">{icon}</span>
                <span class="feed-time">{time_fmt}</span>
                <span class="feed-title">{title}</span>
                <span class="feed-desc">{desc}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
