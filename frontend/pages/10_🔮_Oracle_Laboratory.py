"""
🔮 Oracle Laboratory – Multi-Agent Simulation & Timeline Branching
===================================================================

Provides an interactive interface for running the Oracle Flow:
  • Seed event input
  • Three-round agent analysis (Action → Reaction → Synthesis)
  • Automatic divergence detection & scenario branching
  • Auditor agent flags (stereotype collapse, hallucinations, confidence mismatch)
  • Interactive timeline tree with graphviz visualisation
  • KuzuDB persistence of all decisions

Layout::

    ┌──────────────────┬──────────────────────────────────────────┐
    │  TIMELINE TREE   │   AGENT DECISIONS & AUDIT REPORT        │
    │  (left column)   │   (right column – expandable sections)  │
    └──────────────────┴──────────────────────────────────────────┘
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Optional

import streamlit as st

# ---------------------------------------------------------------------------
# Path setup – make frontend utils and backend intelligence importable
# ---------------------------------------------------------------------------
_FRONTEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_FRONTEND_DIR)
_BACKEND_DIR = os.path.join(_REPO_ROOT, "backend")

for _path in [_FRONTEND_DIR, _BACKEND_DIR]:
    if _path not in sys.path:
        sys.path.insert(0, _path)

# ---------------------------------------------------------------------------
# Streamlit page config (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Oracle Laboratory – EL-DRUIN",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Inline CSS – Light Blue Rational theme
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    :root {
      --accent: #0047AB;
      --bg: #F0F8FF;
      --card-bg: #FFFFFF;
      --border: #E0E0E0;
      --text: #333333;
      --text-sec: #606060;
    }
    .stApp, body { background-color: var(--bg) !important; color: var(--text) !important; }
    h1, h2, h3, h4, h5 { color: var(--accent) !important; }
    .stButton > button {
        background-color: var(--accent) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 4px !important;
        font-family: 'Inter', sans-serif;
    }
    .stButton > button:hover { background-color: #003580 !important; }
    .stTextArea textarea {
        border: 1px solid var(--border) !important;
        border-radius: 4px !important;
        font-family: 'Inter', sans-serif;
    }
    .oracle-header {
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 4px;
        padding: 16px 20px;
        margin-bottom: 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports – backend modules
# ---------------------------------------------------------------------------
_simulator: Optional[Any] = None


def _get_simulator() -> Optional[Any]:
    global _simulator
    if _simulator is not None:
        return _simulator
    try:
        from intelligence.langgraph_simulator import OracleSimulator

        db_path = os.path.join(_REPO_ROOT, "data", "oracle_lab.kuzu")
        _simulator = OracleSimulator(db_path=db_path)
        return _simulator
    except Exception as exc:
        logger.warning("Could not load OracleSimulator: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Frontend component imports
# ---------------------------------------------------------------------------
try:
    from components.timeline_tree import render_timeline_tree
    from components.agent_decisions_display import render_agent_decisions
    from components.auditor_report import render_auditor_report

    _COMPONENTS_OK = True
except ImportError as exc:
    logger.warning("Component import failed: %s", exc)
    _COMPONENTS_OK = False

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
if "oracle_state" not in st.session_state:
    st.session_state.oracle_state = None
if "oracle_running" not in st.session_state:
    st.session_state.oracle_running = False
if "oracle_seed_event" not in st.session_state:
    st.session_state.oracle_seed_event = ""

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="oracle-header">
      <h1 style="margin:0;font-size:1.6rem;">🔮 THE ORACLE LABORATORY</h1>
      <p style="margin:4px 0 0;color:#606060;font-size:0.9rem;">
        Multi-Agent Simulation &amp; Timeline Branching · Ontological Intelligence &amp; Systematic Order
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Seed event input panel
# ---------------------------------------------------------------------------
with st.container():
    st.markdown("##### 🌱 Seed Event")
    seed_input = st.text_area(
        label="Seed Event",
        label_visibility="collapsed",
        value=st.session_state.oracle_seed_event,
        placeholder=(
            "Paste a news article or describe a flashpoint event…\n"
            "Example: 'Federal Reserve raises rates by 75 bps amid stagflation fears; "
            "markets tumble 3% as yield curve inverts.'"
        ),
        height=100,
        key="oracle_seed_input",
    )

    col_btn, col_status = st.columns([2, 5])
    with col_btn:
        run_button = st.button(
            "🔮 Run Oracle Simulation",
            disabled=st.session_state.oracle_running,
            use_container_width=True,
        )

    with col_status:
        if st.session_state.oracle_running:
            st.info("⏳ Simulation in progress…")
        elif st.session_state.oracle_state is not None:
            sim_id = getattr(st.session_state.oracle_state, "simulation_id", "?")[:12]
            status = getattr(st.session_state.oracle_state, "status", "?")
            diverged = getattr(st.session_state.oracle_state, "divergence_detected", False)
            flags_count = len(getattr(st.session_state.oracle_state, "audit_flags", []) or [])
            st.success(
                f"✅ Simulation `{sim_id}` – {status.upper()} | "
                f"Divergence: {'⚠️ YES' if diverged else '✔ No'} | "
                f"Audit flags: {flags_count}"
            )

# ---------------------------------------------------------------------------
# Run simulation on button press
# ---------------------------------------------------------------------------
if run_button:
    if not seed_input.strip():
        st.warning("Please enter a seed event before running the simulation.")
    else:
        st.session_state.oracle_seed_event = seed_input.strip()
        st.session_state.oracle_running = True
        st.session_state.oracle_state = None
        st.rerun()

# Execute when running flag is set (separate rerun ensures UI shows spinner)
if st.session_state.oracle_running:
    with st.spinner("🔮 Running multi-agent simulation…"):
        simulator = _get_simulator()
        if simulator is None:
            st.error(
                "❌ Oracle Simulator could not be initialised. "
                "Check that the backend intelligence package is installed."
            )
            st.session_state.oracle_running = False
        else:
            try:
                result = simulator.run(st.session_state.oracle_seed_event)
                st.session_state.oracle_state = result
                st.session_state.oracle_running = False
                st.rerun()
            except Exception as exc:
                st.error(f"❌ Simulation error: {exc}")
                logger.error("Simulation error", exc_info=True)
                st.session_state.oracle_running = False

# ---------------------------------------------------------------------------
# Main display: Timeline (left) | Decisions + Audit (right)
# ---------------------------------------------------------------------------
state = st.session_state.oracle_state

if state is not None:
    st.markdown("---")
    left_col, right_col = st.columns([1, 2])

    # ── Left: Timeline tree ──────────────────────────────────────────────────
    with left_col:
        if _COMPONENTS_OK:
            render_timeline_tree(state)
        else:
            st.markdown("**Timeline**")
            diverged = getattr(state, "divergence_detected", False)
            st.markdown(
                "🌱 SEED → ⚡ ROUND 1 → "
                + ("⚠️ DIVERGENCE → 🔴 A / ⬜ B" if diverged else "⚡ ROUND 2 → 🔮 ROUND 3")
                + " → 🔎 AUDIT"
            )

        # KuzuDB indicator
        st.markdown("---")
        sim_id = getattr(state, "simulation_id", "")
        st.caption(f"🗄️ Simulation ID: `{sim_id[:12]}…`")
        st.caption("Stored in KuzuDB Oracle tables" if True else "")

        # Branch selector (for knowledge graph cross-reference)
        branches = getattr(state, "scenario_branches", {}) or {}
        if branches:
            st.markdown("##### 🗂️ Select Branch")
            branch_choice = st.radio(
                "Branch",
                options=["Main"] + [f"Scenario {k}" for k in branches.keys()],
                key="oracle_branch_choice",
                label_visibility="collapsed",
            )
            if branch_choice != "Main":
                key = branch_choice.replace("Scenario ", "")
                branch = branches.get(key)
                if branch:
                    st.session_state["oracle_selected_branch_id"] = getattr(
                        branch, "branch_id", None
                    )

    # ── Right: Agent decisions + audit report ────────────────────────────────
    with right_col:
        if _COMPONENTS_OK:
            render_agent_decisions(state)
            st.markdown("---")
            render_auditor_report(state)
        else:
            st.markdown("**Decisions and Audit unavailable** – component import failed.")

else:
    # Empty state – show example prompt
    st.markdown("---")
    st.markdown(
        """
        <div style="background:#FFFFFF;border:1px solid #E0E0E0;border-radius:4px;padding:20px;text-align:center;">
          <h3 style="color:#0047AB;">Run your first Oracle Simulation</h3>
          <p style="color:#606060;">
            Enter a seed event above and click <b>🔮 Run Oracle Simulation</b>.<br/>
            Five specialist agents will analyse the event across three rounds,<br/>
            with automatic divergence detection and scenario branching.
          </p>
          <p style="color:#606060;font-size:0.85rem;">
            <b>Example events:</b><br/>
            • "Federal Reserve raises rates by 75 bps; inflation at 9.1%."<br/>
            • "NATO activates Article 5 following border incident."<br/>
            • "ChatGPT-5 released with autonomous tool-use capabilities."
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
