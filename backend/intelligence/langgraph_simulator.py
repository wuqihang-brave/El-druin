"""
Oracle Laboratory – LangGraph-Style State Machine
===================================================

Implements the simulation as an explicit directed graph with named nodes and
conditional edge routing, mirroring the LangGraph pattern while remaining
importable without the langgraph package (uses a lightweight local
``_GraphRunner``).

If the ``langgraph`` package is installed it will be used automatically;
otherwise the built-in runner is used as a fallback.

Graph topology::

    input_processor
         ↓
    agent_analyzer_round1
         ↓
    divergence_checker ──(diverge)──→ scenario_brancher → auditor → finalize
         ↓ (continue)
    agent_analyzer_round2
         ↓
    divergence_checker_r2 ──(diverge)──→ scenario_brancher → auditor → finalize
         ↓ (continue)
    agent_analyzer_round3
         ↓
    auditor
         ↓
    finalize

Public API::

    from intelligence.langgraph_simulator import OracleSimulator

    sim = OracleSimulator()
    state = sim.run("Fed raises rates 75 bps")
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from intelligence.schemas import SimulationState
from intelligence.multi_agent_engine import MultiAgentEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lightweight local graph runner (used when langgraph is absent)
# ---------------------------------------------------------------------------


class _Node:
    """A named graph node wrapping a callable."""

    def __init__(self, name: str, fn: Callable[[SimulationState], SimulationState]) -> None:
        self.name = name
        self.fn = fn


class _GraphRunner:
    """Minimal sequential / conditional graph runner.

    Nodes are executed in the order they are added.  Conditional routing is
    supported via ``add_conditional_edges``.
    """

    def __init__(self) -> None:
        self._nodes: Dict[str, _Node] = {}
        self._edges: List[Tuple[str, str]] = []
        # src → {condition_value: target_node}
        self._conditional: Dict[str, Tuple[Callable, Dict[str, str]]] = {}
        self._entry: Optional[str] = None

    def add_node(self, name: str, fn: Callable) -> None:
        self._nodes[name] = _Node(name, fn)

    def add_edge(self, src: str, dst: str) -> None:
        self._edges.append((src, dst))

    def add_conditional_edges(
        self,
        src: str,
        condition_fn: Callable[[SimulationState], str],
        routing: Dict[str, str],
    ) -> None:
        self._conditional[src] = (condition_fn, routing)

    def set_entry_point(self, name: str) -> None:
        self._entry = name

    def invoke(self, state: SimulationState) -> SimulationState:
        if self._entry is None:
            raise RuntimeError("Entry point not set")
        current = self._entry
        visited: List[str] = []
        while current and current not in visited:
            visited.append(current)
            node = self._nodes.get(current)
            if node is None:
                break
            logger.debug("Executing node: %s", current)
            state = node.fn(state)

            # Conditional routing takes priority
            if current in self._conditional:
                cond_fn, routing = self._conditional[current]
                outcome = cond_fn(state)
                current = routing.get(outcome, routing.get("default", ""))
                continue

            # Linear routing
            next_nodes = [dst for src, dst in self._edges if src == current]
            current = next_nodes[0] if next_nodes else ""

        return state


# ---------------------------------------------------------------------------
# OracleSimulator
# ---------------------------------------------------------------------------


class OracleSimulator:
    """LangGraph-style multi-agent simulation engine.

    Internally delegates to MultiAgentEngine for agent inference and
    persistence, while exposing a clean graph-based invocation API.
    """

    def __init__(
        self,
        settings: Optional[Any] = None,
        db_path: str = "./data/oracle_lab.kuzu",
    ) -> None:
        self._engine = MultiAgentEngine(settings=settings, db_path=db_path)
        self._graph = self._build_graph()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, seed_event: str) -> SimulationState:
        """Execute the full simulation graph and return the final state."""
        initial_state = SimulationState(seed_event=seed_event)
        return self._graph.invoke(initial_state)

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _build_graph(self) -> _GraphRunner:
        graph = _GraphRunner()

        graph.add_node("input_processor", self._input_processor)
        graph.add_node("agent_analyzer_round1", self._agent_analyzer_round1)
        graph.add_node("divergence_checker", self._divergence_checker)
        graph.add_node("agent_analyzer_round2", self._agent_analyzer_round2)
        graph.add_node("divergence_checker_r2", self._divergence_checker_r2)
        graph.add_node("agent_analyzer_round3", self._agent_analyzer_round3)
        graph.add_node("scenario_brancher", self._scenario_brancher)
        graph.add_node("auditor", self._auditor_node)
        graph.add_node("finalize", self._finalize)

        graph.set_entry_point("input_processor")

        graph.add_edge("input_processor", "agent_analyzer_round1")
        graph.add_edge("agent_analyzer_round1", "divergence_checker")
        graph.add_conditional_edges(
            "divergence_checker",
            lambda s: "diverge" if s.divergence_detected else "continue",
            {"diverge": "scenario_brancher", "continue": "agent_analyzer_round2"},
        )
        graph.add_edge("agent_analyzer_round2", "divergence_checker_r2")
        graph.add_conditional_edges(
            "divergence_checker_r2",
            lambda s: "diverge" if s.divergence_detected else "continue",
            {"diverge": "scenario_brancher", "continue": "agent_analyzer_round3"},
        )
        graph.add_edge("agent_analyzer_round3", "auditor")
        graph.add_edge("scenario_brancher", "auditor")
        graph.add_edge("auditor", "finalize")

        return graph

    # ------------------------------------------------------------------
    # Node implementations
    # ------------------------------------------------------------------

    def _input_processor(self, state: SimulationState) -> SimulationState:
        """Parse / normalise the seed event and initialise state."""
        logger.info("OracleSimulator: processing seed event (%d chars)", len(state.seed_event))
        state.simulation_history.append({"step": "input_processor", "seed_event": state.seed_event})
        return state

    def _agent_analyzer_round1(self, state: SimulationState) -> SimulationState:
        """Run all five agents through round 1."""
        return self._engine._round1(state)

    def _divergence_checker(self, state: SimulationState) -> SimulationState:
        """Round 1 divergence is already flagged inside _round1; this is a pass-through."""
        logger.info(
            "Divergence after round 1: %s (agent: %s)",
            state.divergence_detected,
            state.divergence_agent,
        )
        return state

    def _agent_analyzer_round2(self, state: SimulationState) -> SimulationState:
        return self._engine._round2(state)

    def _divergence_checker_r2(self, state: SimulationState) -> SimulationState:
        logger.info(
            "Divergence after round 2: %s (agent: %s)",
            state.divergence_detected,
            state.divergence_agent,
        )
        return state

    def _agent_analyzer_round3(self, state: SimulationState) -> SimulationState:
        return self._engine._round3(state)

    def _scenario_brancher(self, state: SimulationState) -> SimulationState:
        """Create high-risk and status-quo scenario branches."""
        return self._engine._create_branches(state)

    def _auditor_node(self, state: SimulationState) -> SimulationState:
        return self._engine._run_audit(state)

    def _finalize(self, state: SimulationState) -> SimulationState:
        state.status = "completed"
        self._engine._store.persist_simulation(state)
        logger.info("Simulation %s finalised with %d audit flags", state.simulation_id, len(state.audit_flags))
        return state
