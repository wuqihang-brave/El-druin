"""
Streams – Structural Triage Queue
===================================

Primary purpose: answer for each incoming item, "Does this event move the
structural state?"

Layout:
  Tab 1 – Triage Queue: left column (queue), right column (structural impact)
  Tab 2 – Manual Extraction: knowledge-graph extraction (preserved from prior version)
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

import streamlit as st

_FRONTEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FRONTEND_DIR not in sys.path:
    sys.path.insert(0, _FRONTEND_DIR)

st.set_page_config(
    page_title="Streams – EL-DRUIN",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    from components.sidebar import render_sidebar_navigation
    st.session_state["current_page"] = "Streams"
    render_sidebar_navigation(is_subpage=True)
except Exception:
    pass

from utils.api_client import (
    APIClient,
    get_assessments,
    get_regime,
    get_attractors,
)

# ---------------------------------------------------------------------------
# Design constants
# ---------------------------------------------------------------------------

_SENSITIVITY_COLORS: Dict[str, str] = {
    "High": "#9a3412",
    "Moderate": "#92400e",
    "Low": "#6b7280",
    "Unscored": "#4b5563",
}

# Domain keywords for lightweight heuristic scoring
_DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "military": ["military", "naval", "troops", "forces", "weapons", "strike", "attack", "defense", "army"],
    "sanctions": ["sanctions", "embargo", "restrictions", "ofac", "treasury", "penalty", "designat"],
    "energy": ["energy", "oil", "gas", "pipeline", "tanker", "crude", "lng", "fuel", "power"],
    "finance": ["finance", "bank", "credit", "debt", "bond", "spread", "currency", "dollar", "market"],
    "trade": ["trade", "export", "import", "tariff", "supply chain", "shipping", "cargo", "port"],
    "political": ["political", "government", "election", "diplomat", "minister", "president", "treaty"],
}

_DOMAIN_AMP_BOOST: Dict[str, float] = {
    "military": 0.35,
    "sanctions": 0.25,
    "energy": 0.20,
    "finance": 0.15,
    "trade": 0.10,
    "political": 0.05,
}

_AMP_DISPLAY_SCALE: float = 5.0

# ---------------------------------------------------------------------------
# Inline CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
.str-page-label {
    font-size: 9px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 1.2px; color: #7A8FA6; margin-bottom: 2px;
}
.str-section-title {
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.8px; color: #7A8FA6; margin: 12px 0 6px 0;
}
.str-card {
    background: #162030; border: 1px solid #2D3F52; border-radius: 3px;
    padding: 12px 14px; margin-bottom: 8px;
}
.str-card-compact {
    background: #162030; border: 1px solid #2D3F52; border-radius: 3px;
    padding: 8px 12px; margin-bottom: 6px;
}
.str-badge {
    display: inline-block; font-size: 10px; font-weight: 600;
    padding: 2px 7px; border-radius: 2px; margin-right: 4px;
    text-transform: uppercase; letter-spacing: 0.4px;
}
.str-badge-unscored { background: #1e2d3d; color: #4b5563; border: 1px solid #2D3F52; }
.str-domain-badge {
    display: inline-block; font-size: 10px; padding: 1px 6px;
    border-radius: 2px; margin: 1px 2px; background: #1e2d3d;
    color: #7A8FA6; border: 1px solid #2D3F52;
}
.str-callout {
    background: #1e2d3d; border-left: 3px solid #4A6FA5;
    border-radius: 0 3px 3px 0; padding: 10px 14px; margin: 8px 0;
    font-size: 13px; color: #D4DDE6; line-height: 1.5;
}
.str-divider { height: 1px; background: #2D3F52; margin: 10px 0; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "active_assessment_id" not in st.session_state:
    st.session_state.active_assessment_id = None
if "selected_triage_item" not in st.session_state:
    st.session_state.selected_triage_item = None
if "pending_evidence" not in st.session_state:
    st.session_state.pending_evidence = {}
if "triage_queue" not in st.session_state:
    st.session_state.triage_queue = []
if "reviewed_items" not in st.session_state:
    st.session_state.reviewed_items = set()
if "kg_extract_result" not in st.session_state:
    st.session_state.kg_extract_result = {}

# Seed triage queue with representative items if empty
if not st.session_state.triage_queue:
    st.session_state.triage_queue = [
        {
            "id": "ti-001",
            "title": "Additional naval vessels reported in contested strait — AIS blackout zone expanding",
            "snippet": "Multiple AIS signals went dark in the northern corridor sector as naval exercises were announced.",
            "domains": ["military", "energy"],
            "timestamp": "2026-04-10T06:14:00Z",
            "source": "Lloyd's List Intelligence",
        },
        {
            "id": "ti-002",
            "title": "Treasury signals expansion of secondary sanctions to transit payment facilitators",
            "snippet": "Officials briefed key banks on forthcoming designations targeting energy corridor financing.",
            "domains": ["sanctions", "finance"],
            "timestamp": "2026-04-10T04:30:00Z",
            "source": "Reuters",
        },
        {
            "id": "ti-003",
            "title": "EU emergency energy ministers meeting convened for Thursday",
            "snippet": "The agenda focuses on alternative routing options and emergency reserve activation.",
            "domains": ["political", "energy"],
            "timestamp": "2026-04-09T22:00:00Z",
            "source": "EU Commission",
        },
        {
            "id": "ti-004",
            "title": "Lloyd's market withdraws war-risk coverage for corridor tankers",
            "snippet": "Underwriters cite escalating geopolitical risk following recent incidents.",
            "domains": ["insurance", "energy"],
            "timestamp": "2026-04-09T18:45:00Z",
            "source": "Lloyd's of London",
        },
        {
            "id": "ti-005",
            "title": "Regional sovereign spreads widen 35bps on risk repricing",
            "snippet": "Credit default swap spreads for corridor-adjacent sovereigns hit 18-month highs.",
            "domains": ["finance"],
            "timestamp": "2026-04-09T15:00:00Z",
            "source": "Bloomberg Terminal",
        },
    ]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _fmt_ts(ts_str: str) -> str:
    if not ts_str:
        return "\u2014"
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.strftime("%d %b %H:%M UTC")
    except Exception:
        return ts_str[:16]


def _heuristic_amplification(item: Dict[str, Any]) -> Optional[float]:
    text = (item.get("title", "") + " " + item.get("snippet", "")).lower()
    score = 0.0
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            score += _DOMAIN_AMP_BOOST.get(domain, 0.0)
    return min(1.0, score) if score > 0 else None


def _regime_sensitivity(item: Dict[str, Any], assessment_id: Optional[str]) -> str:
    if not assessment_id:
        return "Unscored"
    regime_key = f"regime_{assessment_id}"
    if regime_key not in st.session_state:
        try:
            st.session_state[regime_key] = get_regime(assessment_id)
        except Exception:
            st.session_state[regime_key] = {}
    regime_data = st.session_state.get(regime_key, {})
    current_regime = regime_data.get("current_regime", "")
    item_domains = set(item.get("domains", []))
    high_regimes = {"Nonlinear Escalation", "Cascade Risk", "Attractor Lock-in"}
    if current_regime in high_regimes and item_domains & {"military", "sanctions", "energy"}:
        return "High"
    if item_domains & {"finance", "trade", "political"}:
        return "Moderate"
    return "Low"


def _attractor_affinity(item: Dict[str, Any], assessment_id: Optional[str]) -> str:
    if not assessment_id:
        return "\u2014"
    attract_key = f"attractors_{assessment_id}"
    if attract_key not in st.session_state:
        try:
            st.session_state[attract_key] = get_attractors(assessment_id)
        except Exception:
            st.session_state[attract_key] = {}
    attract_data = st.session_state.get(attract_key, {})
    attractors = attract_data.get("attractors", [])
    if not attractors:
        return "\u2014"
    top = max(attractors, key=lambda a: float(a.get("pull_strength", 0)), default=None)
    return top.get("name", "\u2014") if top else "\u2014"


def _attach_to_assessment(item_id: str, assessment_id: str) -> None:
    if assessment_id not in st.session_state.pending_evidence:
        st.session_state.pending_evidence[assessment_id] = []
    existing_ids = {e.get("id") for e in st.session_state.pending_evidence[assessment_id]}
    if item_id not in existing_ids:
        item = next((i for i in st.session_state.triage_queue if i.get("id") == item_id), {})
        st.session_state.pending_evidence[assessment_id].append(item)


# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.markdown(
    '<div class="str-page-label">STREAMS \u2014 STRUCTURAL TRIAGE QUEUE</div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Top bar: Active Assessment selector
# ---------------------------------------------------------------------------

_assessments = get_assessments()
_assessment_options: Dict[str, str] = {
    a.get("assessment_id", ""): a.get("title", "\u2014")
    for a in _assessments
    if a.get("assessment_id")
}

_top_bar_l, _top_bar_r = st.columns([3, 1])
with _top_bar_l:
    if _assessment_options:
        _active_id = st.selectbox(
            "Active Assessment",
            options=["\u2014"] + list(_assessment_options.keys()),
            format_func=lambda x: "\u2014 No active assessment \u2014" if x == "\u2014" else _assessment_options.get(x, x),
            key="active_assessment_selector_streams",
        )
        st.session_state.active_assessment_id = _active_id if _active_id != "\u2014" else None
    else:
        st.caption("No assessments available \u2014 connect backend to load")

with _top_bar_r:
    _pending_count = sum(len(v) for v in st.session_state.pending_evidence.values())
    if _pending_count:
        st.markdown(
            f'<span style="font-size:11px;color:#7A8FA6">Pending: '
            f'<span style="color:#D4DDE6;font-weight:600">{_pending_count}</span> items</span>',
            unsafe_allow_html=True,
        )

st.markdown('<div class="str-divider"></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

_tab_triage, _tab_extraction = st.tabs(["Triage Queue", "Manual Extraction"])


# ===========================================================================
# Tab 1 \u2014 Triage Queue
# ===========================================================================

with _tab_triage:
    _active_assessment_id = st.session_state.active_assessment_id
    _queue = [
        item for item in st.session_state.triage_queue
        if item.get("id") not in st.session_state.reviewed_items
    ]

    _col_queue, _col_impact = st.columns([1, 1])

    # -----------------------------------------------------------------------
    # Left: Triage queue
    # -----------------------------------------------------------------------
    with _col_queue:
        st.markdown('<div class="str-section-title">Incoming Events</div>', unsafe_allow_html=True)

        if not _queue:
            st.markdown(
                '<div class="str-callout">All items reviewed. Queue is empty.</div>',
                unsafe_allow_html=True,
            )

        for _item in _queue[:20]:
            _iid = _item.get("id", "")
            _ititle = _item.get("title", "\u2014")
            _isource = _item.get("source", "\u2014")
            _its = _fmt_ts(_item.get("timestamp", ""))
            _idomains = _item.get("domains", [])

            _amp_raw = _heuristic_amplification(_item)
            _amp_display = f"\xd7{_amp_raw * _AMP_DISPLAY_SCALE:.1f}" if _amp_raw is not None else "Unscored"
            _amp_color = "#C8A84B" if _amp_raw is not None else "#4b5563"
            _sensitivity = _regime_sensitivity(_item, _active_assessment_id)
            _sens_color = _SENSITIVITY_COLORS.get(_sensitivity, "#4b5563")
            _affinity = _attractor_affinity(_item, _active_assessment_id)

            _domain_html = " ".join(
                f'<span class="str-domain-badge">{d}</span>' for d in _idomains
            )
            _is_selected = st.session_state.selected_triage_item == _iid
            _card_border = "border-color:#4A9FD4;" if _is_selected else ""

            st.markdown(
                f'<div class="str-card" style="{_card_border}">' +
                f'<div style="font-size:12px;font-weight:600;color:#D4DDE6;margin-bottom:4px;line-height:1.4">{_ititle}</div>' +
                f'<div style="margin-bottom:4px">{_domain_html}</div>' +
                f'<div style="display:flex;gap:12px;flex-wrap:wrap;align-items:center">' +
                f'<span style="font-size:11px;color:#7A8FA6">Amplification: ' +
                f'<span style="color:{_amp_color};font-weight:700">{_amp_display}</span></span>' +
                f'<span style="font-size:11px;color:#7A8FA6">Sensitivity: ' +
                f'<span style="color:{_sens_color};font-weight:600">{_sensitivity}</span></span>' +
                f'</div>' +
                f'<div style="font-size:9px;color:#7A8FA6;margin-top:4px">{_isource} \u00b7 {_its}</div>' +
                f'</div>',
                unsafe_allow_html=True,
            )

            _btn_col_a, _btn_col_b = st.columns(2)
            with _btn_col_a:
                if st.button("View impact", key=f"view_{_iid}", use_container_width=True):
                    st.session_state.selected_triage_item = _iid
                    st.rerun()
            with _btn_col_b:
                if st.button("Mark reviewed", key=f"review_{_iid}", use_container_width=True):
                    st.session_state.reviewed_items.add(_iid)
                    if st.session_state.selected_triage_item == _iid:
                        st.session_state.selected_triage_item = None
                    st.rerun()

            if _assessment_options:
                _attach_sel = st.selectbox(
                    "Attach to assessment",
                    options=["\u2014"] + list(_assessment_options.keys()),
                    format_func=lambda x: "\u2014 Select assessment \u2014" if x == "\u2014" else _assessment_options.get(x, x),
                    key=f"attach_{_iid}",
                    label_visibility="collapsed",
                )
                if _attach_sel and _attach_sel != "\u2014":
                    if st.button("Confirm attach", key=f"confirm_{_iid}"):
                        _attach_to_assessment(_iid, _attach_sel)
                        st.success("Attached to assessment")

    # -----------------------------------------------------------------------
    # Right: Structural impact preview
    # -----------------------------------------------------------------------
    with _col_impact:
        st.markdown('<div class="str-section-title">Structural Impact Preview</div>', unsafe_allow_html=True)

        _sel_id = st.session_state.selected_triage_item
        _sel_item = next(
            (i for i in st.session_state.triage_queue if i.get("id") == _sel_id),
            None,
        ) if _sel_id else None

        if _sel_item is None:
            st.markdown(
                '<div class="str-callout">Select an item from the queue to see its structural impact preview.</div>',
                unsafe_allow_html=True,
            )
        else:
            _sel_title = _sel_item.get("title", "\u2014")
            _sel_snippet = _sel_item.get("snippet", "")
            _sel_domains = _sel_item.get("domains", [])
            _sel_source = _sel_item.get("source", "\u2014")

            st.markdown(
                f'<div class="str-card">' +
                f'<div style="font-size:13px;font-weight:600;color:#D4DDE6;margin-bottom:6px">{_sel_title}</div>' +
                f'<div style="font-size:11px;color:#7A8FA6;line-height:1.5">{_sel_snippet}</div>' +
                f'<div style="font-size:9px;color:#7A8FA6;margin-top:6px">{_sel_source}</div>' +
                f'</div>',
                unsafe_allow_html=True,
            )

            _amp_raw_sel = _heuristic_amplification(_sel_item)
            _amp_disp_sel = f"\xd7{_amp_raw_sel * _AMP_DISPLAY_SCALE:.1f}" if _amp_raw_sel is not None else "Unscored"
            _amp_color_sel = "#C8A84B" if _amp_raw_sel is not None else "#4b5563"
            _sens_sel = _regime_sensitivity(_sel_item, _active_assessment_id)
            _sens_color_sel = _SENSITIVITY_COLORS.get(_sens_sel, "#4b5563")
            _affinity_sel = _attractor_affinity(_sel_item, _active_assessment_id)

            st.markdown(
                f'<div class="str-section-title">Structural Scores</div>' +
                f'<div class="str-card-compact">' +
                f'<div style="display:flex;gap:16px;flex-wrap:wrap">' +
                f'<div><div style="font-size:9px;color:#7A8FA6;text-transform:uppercase;margin-bottom:2px">Estimated Amplification</div>' +
                f'<div style="font-size:18px;font-weight:700;color:{_amp_color_sel}">{_amp_disp_sel}</div></div>' +
                f'<div><div style="font-size:9px;color:#7A8FA6;text-transform:uppercase;margin-bottom:2px">Regime Sensitivity</div>' +
                f'<div style="font-size:18px;font-weight:700;color:{_sens_color_sel}">{_sens_sel}</div></div>' +
                f'</div></div>',
                unsafe_allow_html=True,
            )

            if _affinity_sel and _affinity_sel != "\u2014":
                st.markdown(
                    f'<div class="str-section-title">Attractor Affinity</div>' +
                    f'<div class="str-card-compact">' +
                    f'<div style="font-size:12px;color:#D4DDE6">{_affinity_sel}</div></div>',
                    unsafe_allow_html=True,
                )
            elif not _active_assessment_id:
                st.markdown(
                    '<div class="str-card-compact">' +
                    '<div style="font-size:11px;color:#7A8FA6;font-style:italic">' +
                    'Select an active assessment to compute attractor affinity</div></div>',
                    unsafe_allow_html=True,
                )

            if _sel_domains:
                _dom_html = " ".join(
                    f'<span class="str-domain-badge">{d}</span>' for d in _sel_domains
                )
                st.markdown(
                    f'<div class="str-section-title">Impacted Domains</div>' +
                    f'<div style="margin-bottom:8px">{_dom_html}</div>',
                    unsafe_allow_html=True,
                )

            if _amp_raw_sel is None or _sens_sel == "Unscored":
                st.markdown(
                    '<div class="str-card-compact">' +
                    '<div class="str-badge str-badge-unscored">Unscored</div>' +
                    '<span style="font-size:10px;color:#7A8FA6"> \u2014 structural impact unknown</span>' +
                    '</div>',
                    unsafe_allow_html=True,
                )


# ===========================================================================
# Tab 2 \u2014 Manual Extraction (preserved)
# ===========================================================================

with _tab_extraction:
    st.subheader("Manual Knowledge Extraction")
    st.caption("Extract entities and relations from text. Requires a running backend.")

    _backend_url_raw = os.environ.get("BACKEND_URL")
    if not _backend_url_raw:
        st.info(
            "Knowledge extraction requires a running backend.\n\n"
            "To run locally: `cd backend && uvicorn app.main:app --port 8000`\n\n"
            "Then set `BACKEND_URL` environment variable."
        )
    else:
        import pandas as pd

        _backend_url = _backend_url_raw.rstrip("/")
        _api = APIClient(base_url=_backend_url)

        input_text = st.text_area(
            "News article text",
            placeholder="Paste a news article (10 \u2013 10000 characters)\u2026",
            height=180,
            max_chars=10000,
            key="extract_input_text",
        )

        col_btn, col_clear = st.columns([1, 5])
        with col_btn:
            do_extract = st.button("Extract Knowledge", type="primary", key="btn_extract")
        with col_clear:
            if st.button("Clear results", key="btn_clear_extract"):
                st.session_state.kg_extract_result = {}
                st.rerun()

        if do_extract:
            text_stripped = (input_text or "").strip()
            if len(text_stripped) < 10:
                st.warning("Text is too short. Minimum 10 characters required.")
            else:
                with st.spinner("Extracting entities and relations\u2026"):
                    result = _api.extract_knowledge(text_stripped)
                if result.get("status") == "error" or (
                    "error" in result and "entities" not in result
                ):
                    st.error(f"Extraction failed: {result.get('error', 'Unknown error')}")
                else:
                    st.session_state.kg_extract_result = result
                    st.success("Extraction complete.")

        cached = st.session_state.kg_extract_result
        if cached:
            entities: List[Dict[str, Any]] = cached.get("entities", [])
            relations: List[Dict[str, Any]] = cached.get("relations", [])

            m1, m2 = st.columns(2)
            m1.metric("Entities", len(entities))
            m2.metric("Relations", len(relations))

            st.divider()

            if entities:
                st.markdown("#### Extracted Entities")
                df_entities = pd.DataFrame([
                    {
                        "Name": e.get("name", ""),
                        "Type": e.get("type", ""),
                        "Description": e.get("description", ""),
                    }
                    for e in entities
                ])
                st.dataframe(df_entities, use_container_width=True, height=250)

            if relations:
                st.markdown("#### Extracted Relations")
                df_relations = pd.DataFrame([
                    {
                        "Subject": r.get("subject", ""),
                        "Predicate": r.get("predicate", ""),
                        "Object": r.get("object", ""),
                    }
                    for r in relations
                ])
                st.dataframe(df_relations, use_container_width=True, height=250)
        elif not do_extract:
            st.info("Enter text above and click 'Extract Knowledge' to begin.")
