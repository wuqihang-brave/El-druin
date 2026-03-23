"""
Multi-agent simulation API routes.

Endpoints:
  POST /simulation/run      – run the crisis simulation
  GET  /simulation/agents   – list available agents and their metadata
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.simulation.agents import AGENT_REGISTRY

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/simulation", tags=["simulation"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SimulationRequest(BaseModel):
    news_event: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="The triggering news event summary to inject into the simulation.",
        examples=[
            "CountryA has begun live-fire military exercises near the contested strait, "
            "deploying three carrier groups and issuing a no-fly zone declaration."
        ],
    )
    max_steps: int = Field(
        default=8,
        ge=5,
        le=10,
        description="Number of simulation steps to run (5–10).",
    )
    initial_tension: float = Field(
        default=0.45,
        ge=0.0,
        le=1.0,
        description="Starting tension level in [0.0, 1.0].",
    )
    seed: Optional[int] = Field(
        default=None,
        description="Optional random seed for reproducible runs.",
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/run")
def run_simulation(request: SimulationRequest) -> Dict[str, Any]:
    """Run the multi-agent Taiwan-Strait crisis simulation.

    Executes a LangGraph StateGraph with four agents (LeaderA, LeaderB,
    Ally, Analyst) for the requested number of steps.  Returns the full
    message history, the branch path taken, tension level, and final
    resolution probability estimates.

    Example::

        POST /simulation/run
        {
            "news_event": "CountryA has begun live-fire exercises...",
            "max_steps": 8,
            "initial_tension": 0.4
        }
    """
    try:
        from app.simulation.runner import SimulationRunner

        result = SimulationRunner().run(
            news_event=request.news_event,
            max_steps=request.max_steps,
            initial_tension=request.initial_tension,
            seed=request.seed,
        )
        return {"status": "ok", **result}
    except Exception as exc:
        logger.error("Simulation run error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/agents")
def list_agents() -> Dict[str, Any]:
    """Return metadata for all available simulation agents."""
    return {
        "agents": {
            name: {
                "role": meta["role"],
                "goal": meta["goal"],
                "backstory": meta["backstory"],
                "tension_bias": meta["tension_bias"],
            }
            for name, meta in AGENT_REGISTRY.items()
        }
    }
