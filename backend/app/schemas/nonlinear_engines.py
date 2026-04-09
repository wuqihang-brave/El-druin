"""
Nonlinear Engine Internal Output Types
=======================================

Internal-only types for the six core engine outputs. These are NOT exposed
directly to the UI; they are used by engine adapters that translate raw engine
results into the product-facing structural forecast schema (PR-4 through PR-8).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Regime Engine output
# ---------------------------------------------------------------------------

class RegimeEngineOutput(BaseModel):
    """Raw output from the Regime Classification Engine."""

    regime_label: str
    regime_score: float = Field(ge=0.0, le=1.0)
    threshold_distance: float = Field(ge=0.0, le=1.0)
    transition_volatility: float = Field(ge=0.0, le=1.0)
    reversibility_index: float = Field(ge=0.0, le=1.0)
    dominant_axis: str
    computed_at: datetime
    metadata: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Coupling Engine output
# ---------------------------------------------------------------------------

class CouplingEngineOutput(BaseModel):
    """Raw output from the Domain Coupling Engine."""

    coupling_score: float = Field(ge=0.0, le=1.0)
    coupling_asymmetry: float = Field(ge=0.0, le=1.0)
    domain_pair_scores: dict[str, float] = {}
    computed_at: datetime
    metadata: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Attractor Engine output
# ---------------------------------------------------------------------------

class AttractorEngineOutput(BaseModel):
    """Raw output from the Attractor Identification Engine."""

    attractor_name: str
    pull_strength: float = Field(ge=0.0, le=1.0)
    horizon_days_min: int
    horizon_days_max: int
    supporting_evidence_count: int
    counterforces: list[str] = []
    invalidation_conditions: list[str] = []
    trend_direction: str  # "up" | "down" | "stable"
    computed_at: datetime
    metadata: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Trigger Amplification Engine output
# ---------------------------------------------------------------------------

class TriggerEngineOutput(BaseModel):
    """Raw output from the Trigger Amplification Engine."""

    trigger_name: str
    amplification_factor: float = Field(ge=0.0, le=1.0)
    jump_potential_level: str  # "Low" | "Medium" | "High" | "Critical"
    impacted_domains: list[str] = []
    expected_lag_hours: int
    confidence: float = Field(ge=0.0, le=1.0)
    watch_signals: list[str] = []
    damping_opportunities: list[str] = []
    computed_at: datetime
    metadata: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Propagation Engine output
# ---------------------------------------------------------------------------

class PropagationEngineOutput(BaseModel):
    """Raw output from the Cross-Domain Propagation Engine."""

    sequence: list[dict[str, Any]] = []
    bottlenecks: list[str] = []
    second_order_effects: list[str] = []
    propagation_risk: float = Field(ge=0.0, le=1.0)
    computed_at: datetime
    metadata: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Delta Engine output
# ---------------------------------------------------------------------------

class DeltaEngineOutput(BaseModel):
    """Raw output from the Update Delta Engine."""

    regime_changed: bool
    threshold_direction: str  # "narrowing" | "widening" | "stable"
    trigger_ranking_changes: list[dict[str, Any]] = []
    attractor_pull_changes: list[dict[str, Any]] = []
    damping_capacity_delta: float
    confidence_delta: float
    new_evidence_count: int
    summary: str
    computed_at: datetime
    metadata: dict[str, Any] = {}
