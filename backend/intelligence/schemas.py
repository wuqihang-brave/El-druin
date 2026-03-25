"""
Oracle Laboratory – Pydantic Schemas
=====================================

Defines all data models for the multi-agent simulation engine:
  * AgentProfile      – persistent agent identity stored in KuzuDB
  * AgentDecision     – round 1 action output
  * AgentReaction     – round 2 reaction output
  * AgentSynthesis    – round 3 synthesis output
  * AuditFlag         – auditor-detected issue
  * SimulationBranch  – a branched sub-simulation scenario
  * SimulationState   – full LangGraph state container

All models are forward-compatible with pydantic v1 and v2 (model_config /
class Config where needed).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _new_uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Agent identity
# ---------------------------------------------------------------------------

class AgentProfile(BaseModel):
    """Persistent agent identity profile stored in KuzuDB."""

    agent_id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Human-readable agent name")
    expertise_domain: str = Field(..., description="Area of specialisation")
    decision_style: str = Field(..., description="Behavioural pattern")
    historical_accuracy: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Past-performance metric (0.0–1.0)",
    )
    bias_profile: str = Field(default="", description="Known cognitive biases")
    reasoning_framework: str = Field(
        default="", description="Cognitive / analytical approach"
    )
    created_at: str = Field(default_factory=_now_iso)


# ---------------------------------------------------------------------------
# Round outputs
# ---------------------------------------------------------------------------

class AgentDecision(BaseModel):
    """Round 1 – ACTION: what should happen?"""

    agent_id: str
    round: Literal[1] = 1
    action_type: Literal["escalate", "stabilize", "observe", "intervene"] = "observe"
    target_entity: str = Field(default="", description="Entity to act upon")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning: str = Field(default="")
    created_at: str = Field(default_factory=_now_iso)


class AgentReaction(BaseModel):
    """Round 2 – REACTION: how will others respond?"""

    agent_id: str
    round: Literal[2] = 2
    reaction_type: Literal["counteract", "align", "neutral"] = "neutral"
    affected_entities: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning: str = Field(default="")
    created_at: str = Field(default_factory=_now_iso)


class AgentSynthesis(BaseModel):
    """Round 3 – SYNTHESIS: what is the equilibrium?"""

    agent_id: str
    round: Literal[3] = 3
    outcome_prediction: str = Field(default="")
    risk_level: Literal["low", "medium", "high", "critical"] = "medium"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning: str = Field(default="")
    created_at: str = Field(default_factory=_now_iso)


# ---------------------------------------------------------------------------
# Audit flag
# ---------------------------------------------------------------------------

class AuditFlag(BaseModel):
    """A single issue flagged by the Auditor agent."""

    flag_id: str = Field(default_factory=_new_uuid)
    agent_id: str
    issue_type: Literal[
        "stereotype_collapse", "logical_hallucination", "confidence_mismatch"
    ]
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    description: str = Field(default="")
    flagged_text: str = Field(default="")
    created_at: str = Field(default_factory=_now_iso)


# ---------------------------------------------------------------------------
# Scenario branch
# ---------------------------------------------------------------------------

class SimulationBranch(BaseModel):
    """A branched sub-simulation (high-risk or status-quo scenario)."""

    branch_id: str = Field(default_factory=_new_uuid)
    parent_simulation_id: str = Field(default="")
    scenario_type: Literal["high_risk", "status_quo"] = "status_quo"
    agents_decisions: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_range: tuple = Field(default=(0.0, 1.0))
    created_at: str = Field(default_factory=_now_iso)

    model_config = {"arbitrary_types_allowed": True}


# ---------------------------------------------------------------------------
# Top-level simulation state  (LangGraph-compatible TypedDict-style)
# ---------------------------------------------------------------------------

class SimulationState(BaseModel):
    """Full simulation state – passed between LangGraph nodes."""

    simulation_id: str = Field(default_factory=_new_uuid)
    seed_event: str = Field(default="")
    round_number: int = Field(default=0, ge=0, le=3)

    # Decisions per round
    round1_decisions: List[AgentDecision] = Field(default_factory=list)
    round2_reactions: List[AgentReaction] = Field(default_factory=list)
    round3_syntheses: List[AgentSynthesis] = Field(default_factory=list)

    # Per-round confidence tracking  {agent_id: confidence}
    confidence_scores: Dict[str, float] = Field(default_factory=dict)

    # Divergence state
    divergence_detected: bool = False
    divergence_agent: str = Field(default="")
    divergence_round: int = Field(default=0)

    # Scenario branches (keyed "A" = high_risk, "B" = status_quo)
    scenario_branches: Dict[str, SimulationBranch] = Field(default_factory=dict)

    # Auditor output
    audit_flags: List[AuditFlag] = Field(default_factory=list)

    # Full history of all rounds (list of dicts for JSON serialisation)
    simulation_history: List[Dict[str, Any]] = Field(default_factory=list)

    # Overall status
    status: Literal["running", "completed", "error"] = "running"

    created_at: str = Field(default_factory=_now_iso)

    model_config = {"arbitrary_types_allowed": True}
