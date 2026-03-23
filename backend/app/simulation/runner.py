"""
High-level simulation runner.

Usage::

    from app.simulation.runner import SimulationRunner

    result = SimulationRunner().run(
        news_event="CountryA begins live-fire exercises near the contested strait.",
        max_steps=8,
        initial_tension=0.4,
    )
    print(result)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from app.simulation.agents import AGENT_REGISTRY, query_kg_context
from app.simulation.graph import build_simulation_graph
from app.simulation.state import SimulationState

logger = logging.getLogger(__name__)


class SimulationRunner:
    """Orchestrates a single multi-agent simulation run."""

    def __init__(self) -> None:
        self._graph = build_simulation_graph()

    def run(
        self,
        news_event: str,
        max_steps: int = 8,
        initial_tension: float = 0.45,
        seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run the simulation and return a structured result dict.

        Args:
            news_event:       Triggering event summary (injected at step 0).
            max_steps:        Maximum number of simulation steps (5–10).
            initial_tension:  Starting tension level in [0.0, 1.0].
            seed:             Optional random seed for reproducible runs.

        Returns:
            A dict with keys: ``messages``, ``path``, ``tension_level``,
            ``resolution_probabilities``, ``steps_run``, ``elapsed_ms``,
            ``agents``, ``news_event``.
        """
        import random
        if seed is not None:
            random.seed(seed)

        max_steps = max(5, min(10, max_steps))
        initial_tension = max(0.0, min(1.0, initial_tension))

        # ── Build knowledge graph context ────────────────────────────────
        kg_context = query_kg_context(news_event)

        # ── Build initial state ──────────────────────────────────────────
        initial_state: SimulationState = {
            "news_event": news_event,
            "max_steps": max_steps,
            "step": 0,
            "current_agent": "LeaderA",
            "messages": [],
            "tension_level": initial_tension,
            "path": [],
            "kg_context": kg_context,
            "resolution_probabilities": {},
            "finished": False,
        }

        # ── Run the graph ────────────────────────────────────────────────
        t0 = time.monotonic()
        final_state = self._graph.invoke(initial_state)
        elapsed_ms = round((time.monotonic() - t0) * 1000)

        # ── Serialise messages for JSON transport ────────────────────────
        messages = [dict(m) for m in final_state.get("messages", [])]

        return {
            "news_event": news_event,
            "steps_run": final_state.get("step", 0),
            "initial_tension": initial_tension,
            "tension_level": round(final_state.get("tension_level", 0.0), 4),
            "path": final_state.get("path", []),
            "resolution_probabilities": final_state.get("resolution_probabilities", {}),
            "messages": messages,
            "kg_context": kg_context,
            "elapsed_ms": elapsed_ms,
            "agents": {
                name: {
                    "role": meta["role"],
                    "goal": meta["goal"],
                    "backstory": meta["backstory"],
                }
                for name, meta in AGENT_REGISTRY.items()
            },
        }
