"""
Shared state definition for the multi-agent simulation.

The ``SimulationState`` TypedDict is the single mutable object that flows
through every node in the LangGraph StateGraph.
"""

from __future__ import annotations

from typing import Any, Dict, List

try:
    from typing import TypedDict
except ImportError:  # Python < 3.8 fallback (should not happen)
    from typing_extensions import TypedDict  # type: ignore[assignment]


class AgentMessage(TypedDict):
    """A single message produced by an agent during one simulation step."""

    agent: str        # Agent identifier, e.g. "LeaderA"
    role: str         # Human-readable role label, e.g. "Aggressive Leader"
    content: str      # The text of the message / action
    step: int         # Simulation step at which the message was produced
    tension_delta: float  # How much this message shifted the tension level


class SimulationState(TypedDict):
    """Mutable state threaded through every node in the StateGraph."""

    # ── Input ───────────────────────────────────────────────────────────────
    news_event: str          # The triggering news summary injected at step 0
    max_steps: int           # Maximum number of simulation steps to run

    # ── Runtime ─────────────────────────────────────────────────────────────
    step: int                # Current step counter (0-indexed)
    current_agent: str       # Which agent acts next
    messages: List[AgentMessage]  # Full conversation / action history

    # ── World state ─────────────────────────────────────────────────────────
    tension_level: float     # 0.0 = fully peaceful, 1.0 = open conflict
    path: List[str]          # Branch labels taken, e.g. ["escalation", "negotiation"]

    # ── Knowledge context ───────────────────────────────────────────────────
    kg_context: str          # Snippet from knowledge graph relevant to the event

    # ── Output ──────────────────────────────────────────────────────────────
    resolution_probabilities: Dict[str, float]  # e.g. {"war": 0.3, "negotiation": 0.5, …}
    finished: bool           # Set to True to terminate the graph
