"""
LangGraph StateGraph for the multi-agent crisis simulation.

Tries to import LangGraph and builds a real StateGraph when available.
Falls back to a pure-Python state-machine that mirrors the same interface
when LangGraph is not installed, so the simulation always works.

Graph topology
--------------

    [START]
       │
       ▼
  step_counter ──── finished? ───► [END]
       │                no
       ▼
  router_node  ──► leader_a_node
                ├─► leader_b_node
                ├─► ally_node
                └─► analyst_node
       │
       └──────────────────────────► step_counter  (loop)

The ``router_node`` selects the agent whose turn it is according to
``state["current_agent"]``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.simulation.agents import (
    AGENT_REGISTRY,
    ally_node,
    analyst_node,
    leader_a_node,
    leader_b_node,
    step_counter_node,
)
from app.simulation.state import SimulationState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Node map
# ---------------------------------------------------------------------------

_NODE_MAP = {
    "LeaderA": leader_a_node,
    "LeaderB": leader_b_node,
    "Ally": ally_node,
    "Analyst": analyst_node,
}

# ---------------------------------------------------------------------------
# LangGraph implementation
# ---------------------------------------------------------------------------

def _build_langgraph_graph():  # type: ignore[return]
    """Build and compile a real LangGraph StateGraph."""
    from langgraph.graph import END, START, StateGraph  # type: ignore[import]

    def router(state: SimulationState) -> str:
        """Route to the appropriate agent node."""
        return state["current_agent"]

    def dispatch_node(state: SimulationState) -> Dict[str, Any]:
        """Thin wrapper – select and call the right agent function."""
        agent_name = state["current_agent"]
        fn = _NODE_MAP.get(agent_name)
        if fn is None:
            logger.warning("Unknown agent '%s', defaulting to LeaderA", agent_name)
            fn = leader_a_node
        return fn(state)

    def should_continue(state: SimulationState) -> str:
        if state.get("finished", False):
            return "end"
        return "continue"

    graph = StateGraph(SimulationState)

    # Nodes
    graph.add_node("step_counter", step_counter_node)
    graph.add_node("dispatch", dispatch_node)

    # Edges
    graph.add_edge(START, "step_counter")
    graph.add_conditional_edges(
        "step_counter",
        should_continue,
        {"continue": "dispatch", "end": END},
    )
    graph.add_edge("dispatch", "step_counter")

    return graph.compile()


# ---------------------------------------------------------------------------
# Pure-Python fallback state machine
# ---------------------------------------------------------------------------

class _FallbackGraph:
    """Minimal state-machine that replicates the LangGraph graph semantics."""

    def invoke(self, initial_state: SimulationState) -> SimulationState:
        state: SimulationState = dict(initial_state)  # type: ignore[assignment]
        while not state.get("finished", False):
            # step_counter
            update = step_counter_node(state)
            state.update(update)
            if state["finished"]:
                break
            # dispatch
            agent_name = state["current_agent"]
            fn = _NODE_MAP.get(agent_name, leader_a_node)
            update = fn(state)
            state.update(update)
        return state


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------

def build_simulation_graph():
    """Return a compiled graph (LangGraph or fallback) ready to call ``.invoke()``."""
    try:
        graph = _build_langgraph_graph()
        logger.info("LangGraph StateGraph compiled successfully.")
        return graph
    except ImportError:
        logger.info("LangGraph not available – using built-in fallback state machine.")
        return _FallbackGraph()
    except Exception as exc:
        logger.warning("LangGraph graph build failed (%s) – using fallback.", exc)
        return _FallbackGraph()
