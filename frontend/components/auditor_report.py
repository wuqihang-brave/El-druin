"""
Oracle Laboratory – Auditor Report Component
=============================================

Renders flagged issues from the Auditor agent with severity-coded icons
and expandable detail panels.

Public API::

    from components.auditor_report import render_auditor_report

    render_auditor_report(state)
"""

from __future__ import annotations

import sys
import os
from typing import Any, List

import streamlit as st

_FRONTEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FRONTEND_DIR not in sys.path:
    sys.path.insert(0, _FRONTEND_DIR)

_AGENT_LABELS = {
    "analyst_1": "Financial Analyst",
    "analyst_2": "Geopolitical Strategist",
    "analyst_3": "Technology Futurist",
    "analyst_4": "Institutional Analyst",
    "analyst_5": "Sentiment Monitor",
    "all": "All Agents",
}

_SEVERITY_STYLES = {
    "critical": ("💀", "#C0392B", "#FDECEA"),
    "high": ("🔴", "#C0392B", "#FDECEA"),
    "medium": ("🟡", "#E67E22", "#FEF9E7"),
    "low": ("🔵", "#2980B9", "#EAF2FB"),
}

_ISSUE_LABELS = {
    "stereotype_collapse": "Stereotype Collapse",
    "logical_hallucination": "Logical Hallucination",
    "confidence_mismatch": "Confidence Mismatch",
}


def render_auditor_report(state: Any) -> None:
    """Render audit flags from *state*.

    Parameters
    ----------
    state:
        A ``SimulationState`` instance or compatible object.
    """
    st.markdown("#### 🔎 Auditor Report")

    flags: List[Any] = getattr(state, "audit_flags", []) or [] if state else []

    if not flags:
        st.success("✅ No issues detected by the Auditor Agent.")
        return

    # Summary counts
    severity_counts: dict = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in flags:
        sev = getattr(f, "severity", "low")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    # Summary row
    cols = st.columns(4)
    for idx, (sev, label) in enumerate([
        ("critical", "Critical"), ("high", "High"), ("medium", "Medium"), ("low", "Low")
    ]):
        icon, color, _ = _SEVERITY_STYLES[sev]
        cols[idx].metric(f"{icon} {label}", severity_counts[sev])

    st.markdown("---")

    # Group flags by issue type
    groups: dict = {}
    for f in flags:
        issue = getattr(f, "issue_type", "unknown")
        groups.setdefault(issue, []).append(f)

    for issue_type, issue_flags in groups.items():
        label = _ISSUE_LABELS.get(issue_type, issue_type.replace("_", " ").title())
        with st.expander(f"⚠️ {label} ({len(issue_flags)} flag{'s' if len(issue_flags) > 1 else ''})", expanded=True):
            for flag in issue_flags:
                _render_flag(flag)


def _render_flag(flag: Any) -> None:
    severity = getattr(flag, "severity", "low")
    agent_id = getattr(flag, "agent_id", "unknown")
    description = getattr(flag, "description", "")
    flagged_text = getattr(flag, "flagged_text", "")
    flag_id = getattr(flag, "flag_id", "?")[:8]

    icon, color, bg = _SEVERITY_STYLES.get(severity, ("🔵", "#2980B9", "#EAF2FB"))
    agent_label = _AGENT_LABELS.get(agent_id, agent_id)

    st.markdown(
        f"""
        <div style="background:{bg};border-left:4px solid {color};border-radius:0 4px 4px 0;
                    padding:10px 14px;margin:6px 0;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-weight:700;color:{color};">{icon} {severity.upper()}</span>
            <span style="font-size:0.75rem;color:#606060;">{agent_label} | ID: {flag_id}</span>
          </div>
          <p style="color:#333333;font-size:0.85rem;margin:6px 0 4px;">{description}</p>
          {f'<blockquote style="border-left:2px solid {color};margin:4px 0 0 8px;padding-left:8px;font-style:italic;color:#606060;font-size:0.78rem;">{flagged_text[:200]}</blockquote>' if flagged_text else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )
