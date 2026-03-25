"""
Oracle Laboratory – Agent Decisions Display Component
=====================================================

Renders expandable sections showing all agent outputs for each round.

Public API::

    from components.agent_decisions_display import render_agent_decisions

    render_agent_decisions(state)
"""

from __future__ import annotations

import sys
import os
from typing import Any, List, Optional

import streamlit as st

_FRONTEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FRONTEND_DIR not in sys.path:
    sys.path.insert(0, _FRONTEND_DIR)

# ---------------------------------------------------------------------------
# Agent id → display name mapping
# ---------------------------------------------------------------------------
_AGENT_LABELS = {
    "analyst_1": "📊 Financial Analyst",
    "analyst_2": "🌍 Geopolitical Strategist",
    "analyst_3": "🚀 Technology Futurist",
    "analyst_4": "🏛️ Institutional Analyst",
    "analyst_5": "📣 Sentiment Monitor",
}

_ACTION_ICONS = {
    "escalate": "🔺",
    "stabilize": "🔵",
    "observe": "👁",
    "intervene": "⚙️",
}

_REACTION_ICONS = {
    "counteract": "↩️",
    "align": "✅",
    "neutral": "➡️",
}

_RISK_ICONS = {
    "low": "🟢",
    "medium": "🟡",
    "high": "🔴",
    "critical": "💀",
}


# ---------------------------------------------------------------------------
# Confidence colouring helper
# ---------------------------------------------------------------------------

def _confidence_html(confidence: float) -> str:
    if confidence >= 0.7:
        colour = "#27AE60"  # green
        icon = "✅"
    elif confidence >= 0.6:
        colour = "#E67E22"  # yellow/orange
        icon = "⚠️"
    else:
        colour = "#C0392B"  # red
        icon = "🔴"
    return f'<span style="color:{colour};font-weight:600;">{icon} {confidence:.2f}</span>'


def _agent_label(agent_id: str) -> str:
    return _AGENT_LABELS.get(agent_id, f"🤖 {agent_id}")


# ---------------------------------------------------------------------------
# Public render function
# ---------------------------------------------------------------------------

def render_agent_decisions(state: Any) -> None:
    """Render all round decisions from *state*.

    Parameters
    ----------
    state:
        A ``SimulationState`` instance or compatible object.
    """
    if state is None:
        st.info("No simulation data available.")
        return

    round1 = getattr(state, "round1_decisions", []) or []
    round2 = getattr(state, "round2_reactions", []) or []
    round3 = getattr(state, "round3_syntheses", []) or []
    branches = getattr(state, "scenario_branches", {}) or {}

    # ── Round 1 ──────────────────────────────────────────────────────────────
    if round1:
        with st.expander("⚡ Round 1 — ACTION", expanded=True):
            _render_round1(round1)

    # ── Round 2 ──────────────────────────────────────────────────────────────
    if round2:
        with st.expander("🔁 Round 2 — REACTION", expanded=True):
            _render_round2(round2)

    # ── Round 3 ──────────────────────────────────────────────────────────────
    if round3:
        with st.expander("🔮 Round 3 — SYNTHESIS", expanded=True):
            _render_round3(round3)

    # ── Scenario branches ────────────────────────────────────────────────────
    if branches:
        st.markdown("---")
        for key, branch in branches.items():
            scenario_type = getattr(branch, "scenario_type", key)
            icon = "🔴" if scenario_type == "high_risk" else "⬜"
            label = "High Risk" if scenario_type == "high_risk" else "Status Quo"
            with st.expander(f"{icon} Scenario {key} — {label}", expanded=False):
                _render_branch(branch)


# ---------------------------------------------------------------------------
# Private per-round renderers
# ---------------------------------------------------------------------------

def _render_round1(decisions: List[Any]) -> None:
    cols = st.columns(len(decisions) if len(decisions) <= 5 else 5)
    for idx, d in enumerate(decisions):
        col = cols[idx % 5]
        with col:
            action = getattr(d, "action_type", "—")
            target = getattr(d, "target_entity", "—")
            conf = getattr(d, "confidence", 0.0)
            reasoning = getattr(d, "reasoning", "")
            icon = _ACTION_ICONS.get(action, "❓")
            st.markdown(
                f"""
                <div style="background:#FFFFFF;border:1px solid #E0E0E0;border-radius:4px;padding:10px;margin:4px 0;">
                  <div style="font-weight:700;color:#0047AB;font-size:0.85rem;">{_agent_label(d.agent_id)}</div>
                  <div style="font-size:0.8rem;color:#333333;">{icon} <b>{action.capitalize()}</b></div>
                  <div style="font-size:0.75rem;color:#606060;">Target: {target}</div>
                  <div style="font-size:0.75rem;">Conf: {_confidence_html(conf)}</div>
                  <div style="font-size:0.72rem;color:#606060;margin-top:4px;font-style:italic;">{reasoning[:120]}{'...' if len(reasoning) > 120 else ''}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_round2(reactions: List[Any]) -> None:
    for r in reactions:
        reaction_type = getattr(r, "reaction_type", "—")
        affected = getattr(r, "affected_entities", [])
        conf = getattr(r, "confidence", 0.0)
        reasoning = getattr(r, "reasoning", "")
        icon = _REACTION_ICONS.get(reaction_type, "➡️")
        st.markdown(
            f"""
            <div style="background:#FFFFFF;border:1px solid #E0E0E0;border-radius:4px;
                        padding:10px;margin:6px 0;">
              <span style="font-weight:700;color:#0047AB;">{_agent_label(r.agent_id)}</span>
              &nbsp;&nbsp;{icon} <b>{reaction_type.capitalize()}</b>
              &nbsp;| Entities: <code>{', '.join(affected) if affected else '—'}</code>
              &nbsp;| Confidence: {_confidence_html(conf)}<br/>
              <span style="font-size:0.8rem;color:#606060;font-style:italic;">{reasoning[:150]}{'...' if len(reasoning) > 150 else ''}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_round3(syntheses: List[Any]) -> None:
    for s in syntheses:
        risk = getattr(s, "risk_level", "medium")
        prediction = getattr(s, "outcome_prediction", "")
        conf = getattr(s, "confidence", 0.0)
        reasoning = getattr(s, "reasoning", "")
        risk_icon = _RISK_ICONS.get(risk, "🟡")
        st.markdown(
            f"""
            <div style="background:#FFFFFF;border:1px solid #E0E0E0;border-radius:4px;
                        padding:10px;margin:6px 0;">
              <span style="font-weight:700;color:#0047AB;">{_agent_label(s.agent_id)}</span>
              &nbsp;&nbsp;{risk_icon} Risk: <b>{risk.upper()}</b>
              &nbsp;| Confidence: {_confidence_html(conf)}<br/>
              <div style="font-size:0.82rem;color:#333333;margin-top:4px;">{prediction[:200]}{'...' if len(prediction) > 200 else ''}</div>
              <div style="font-size:0.78rem;color:#606060;font-style:italic;margin-top:2px;">{reasoning[:120]}{'...' if len(reasoning) > 120 else ''}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_branch(branch: Any) -> None:
    decisions = getattr(branch, "agents_decisions", []) or []
    conf_range = getattr(branch, "confidence_range", (0.0, 1.0))
    st.caption(f"Confidence range: {conf_range[0]:.2f} – {conf_range[1]:.2f}")
    for item in decisions:
        agent_id = item.get("agent_id", "?") if isinstance(item, dict) else getattr(item, "agent_id", "?")
        action_data = item.get("action", {}) if isinstance(item, dict) else {}
        synthesis_data = item.get("synthesis", {}) if isinstance(item, dict) else {}
        action_type = action_data.get("action_type", "—") if action_data else "—"
        outcome = synthesis_data.get("outcome_prediction", "—") if synthesis_data else "—"
        st.markdown(
            f"**{_agent_label(agent_id)}** → `{action_type}` | _{outcome[:100]}_"
        )
