"""
Oracle Laboratory – Timeline Tree Component
=============================================

Renders a horizontal timeline tree using Graphviz (via the ``graphviz``
Python package) or falls back to a plain text / emoji representation when
Graphviz is not available.

Public API::

    from components.timeline_tree import render_timeline_tree

    render_timeline_tree(state)
"""

from __future__ import annotations

import sys
import os
from typing import Any, Dict, Optional

import streamlit as st

_FRONTEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FRONTEND_DIR not in sys.path:
    sys.path.insert(0, _FRONTEND_DIR)

try:
    import graphviz  # type: ignore[import]
    _GRAPHVIZ = True
except ImportError:
    _GRAPHVIZ = False


# ---------------------------------------------------------------------------
# Colour constants matching the Light Blue Rational theme
# ---------------------------------------------------------------------------
_COLOR_MAIN = "#0047AB"       # Cobalt Blue – main timeline
_COLOR_HIGH_RISK = "#C0392B"  # Red – high-risk scenario A
_COLOR_STATUS_QUO = "#7F8C8D"  # Grey – status-quo scenario B
_COLOR_BG = "#FFFFFF"
_COLOR_DIVERGE = "#E67E22"    # Orange – divergence node
_COLOR_FONT = "#333333"


def render_timeline_tree(state: Any) -> None:
    """Render an interactive timeline tree for *state*.

    Parameters
    ----------
    state:
        A ``SimulationState`` (or compatible dict-like object).
    """
    st.markdown("#### 🕐 Simulation Timeline")

    if state is None:
        st.info("Run a simulation to see the timeline.")
        return

    sim_id = getattr(state, "simulation_id", "?")[:8]
    diverged = getattr(state, "divergence_detected", False)
    diverge_agent = getattr(state, "divergence_agent", "")
    round_num = getattr(state, "round_number", 0)
    branches = getattr(state, "scenario_branches", {})

    if _GRAPHVIZ:
        _render_graphviz(sim_id, diverged, diverge_agent, round_num, branches, state)
    else:
        _render_text(sim_id, diverged, diverge_agent, round_num, branches)


# ---------------------------------------------------------------------------
# Graphviz renderer
# ---------------------------------------------------------------------------

def _render_graphviz(
    sim_id: str,
    diverged: bool,
    diverge_agent: str,
    round_num: int,
    branches: Dict[str, Any],
    state: Any,
) -> None:
    dot = graphviz.Digraph(
        name="timeline",
        graph_attr={
            "rankdir": "LR",
            "bgcolor": _COLOR_BG,
            "fontname": "Inter",
            "splines": "ortho",
            "nodesep": "0.5",
            "ranksep": "0.8",
        },
        node_attr={
            "style": "filled,rounded",
            "fontname": "Inter",
            "fontsize": "10",
            "fontcolor": "#FFFFFF",
            "penwidth": "1.5",
        },
        edge_attr={
            "color": "#A0A0A0",
            "fontsize": "9",
            "fontname": "Inter",
        },
    )

    # Seed node
    dot.node("seed", f"🌱 SEED\n{sim_id}", fillcolor=_COLOR_MAIN, color=_COLOR_MAIN)

    # Round 1
    dot.node("r1", "⚡ ROUND 1\nACTION", fillcolor=_COLOR_MAIN, color=_COLOR_MAIN)
    dot.edge("seed", "r1")

    # Divergence check
    div_color = _COLOR_DIVERGE if diverged else _COLOR_MAIN
    div_label = f"⚠ DIVERGENCE\n{diverge_agent}" if diverged else "✔ STABLE"
    dot.node("div", div_label, fillcolor=div_color, color=div_color, shape="diamond")
    dot.edge("r1", "div")

    if diverged:
        # Branch A – high risk
        dot.node(
            "branch_a",
            "🔴 SCENARIO A\nHigh Risk",
            fillcolor=_COLOR_HIGH_RISK,
            color=_COLOR_HIGH_RISK,
        )
        # Branch B – status quo
        dot.node(
            "branch_b",
            "⬜ SCENARIO B\nStatus Quo",
            fillcolor=_COLOR_STATUS_QUO,
            color=_COLOR_STATUS_QUO,
        )
        dot.edge("div", "branch_a", label="Worst-case", color=_COLOR_HIGH_RISK)
        dot.edge("div", "branch_b", label="Continuity", color=_COLOR_STATUS_QUO)

        # Sub-nodes for each branch
        for key, color in [("branch_a", _COLOR_HIGH_RISK), ("branch_b", _COLOR_STATUS_QUO)]:
            suffix = "A" if key == "branch_a" else "B"
            dot.node(f"r2_{suffix}", f"⚡ R2\nREACTION", fillcolor=color, color=color)
            dot.node(f"r3_{suffix}", f"🔮 R3\nSYNTHESIS", fillcolor=color, color=color)
            dot.edge(key, f"r2_{suffix}")
            dot.edge(f"r2_{suffix}", f"r3_{suffix}")
    else:
        # Main path continues
        dot.node("r2", "⚡ ROUND 2\nREACTION", fillcolor=_COLOR_MAIN, color=_COLOR_MAIN)
        dot.node("r3", "🔮 ROUND 3\nSYNTHESIS", fillcolor=_COLOR_MAIN, color=_COLOR_MAIN)
        dot.edge("div", "r2")
        dot.edge("r2", "r3")

    # Final audit node
    audit_flags = getattr(state, "audit_flags", [])
    audit_color = "#C0392B" if audit_flags else "#27AE60"
    dot.node(
        "audit",
        f"🔎 AUDIT\n{len(audit_flags)} flag(s)",
        fillcolor=audit_color,
        color=audit_color,
    )
    if diverged:
        dot.edge("branch_a", "audit")
        dot.edge("branch_b", "audit")
    else:
        dot.edge("r3", "audit")

    st.graphviz_chart(dot)


# ---------------------------------------------------------------------------
# Plain-text fallback renderer
# ---------------------------------------------------------------------------

def _render_text(
    sim_id: str,
    diverged: bool,
    diverge_agent: str,
    round_num: int,
    branches: Dict[str, Any],
) -> None:
    steps = [f"🌱 **SEED** `{sim_id}`", "⚡ **ROUND 1** – Action"]

    if diverged:
        steps.append(f"⚠️ **DIVERGENCE** detected by `{diverge_agent}`")
        steps.append("🔴 **SCENARIO A** – High Risk Timeline")
        steps.append("⬜ **SCENARIO B** – Status Quo Timeline")
    else:
        steps.append("✔️ No divergence")
        steps.append("⚡ **ROUND 2** – Reaction")
        steps.append("🔮 **ROUND 3** – Synthesis")

    steps.append("🔎 **AUDIT**")

    st.markdown(" → ".join(steps))
