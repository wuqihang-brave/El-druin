"""
Structural Forecast Schema
==========================

Normalized contract between backend engine outputs and the frontend UX.
This is the foundational data layer for EL'druin's nonlinear intelligence
operating system.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Core regime state taxonomy
# ---------------------------------------------------------------------------

RegimeState = Literal[
    "Linear",
    "Stress Accumulation",
    "Nonlinear Escalation",
    "Cascade Risk",
    "Attractor Lock-in",
    "Dissipating",
]


# ---------------------------------------------------------------------------
# Regime
# ---------------------------------------------------------------------------

class RegimeOutput(BaseModel):
    assessment_id: str
    current_regime: RegimeState
    threshold_distance: float = Field(ge=0.0, le=1.0)
    transition_volatility: float = Field(ge=0.0, le=1.0)
    reversibility_index: float = Field(ge=0.0, le=1.0)
    dominant_axis: str  # e.g. "military -> sanctions -> energy"
    coupling_asymmetry: float = Field(ge=0.0, le=1.0)
    damping_capacity: float = Field(ge=0.0, le=1.0)
    forecast_implication: str
    updated_at: datetime


# ---------------------------------------------------------------------------
# Triggers
# ---------------------------------------------------------------------------

class TriggerOutput(BaseModel):
    name: str
    amplification_factor: float = Field(ge=0.0, le=1.0)
    jump_potential: Literal["Low", "Medium", "High", "Critical"]
    impacted_domains: list[str]
    expected_lag_hours: int
    confidence: float = Field(ge=0.0, le=1.0)
    watch_signals: list[str]
    damping_opportunities: list[str]


class TriggersOutput(BaseModel):
    assessment_id: str
    triggers: list[TriggerOutput]
    updated_at: datetime


# ---------------------------------------------------------------------------
# Attractors
# ---------------------------------------------------------------------------

class AttractorOutput(BaseModel):
    name: str
    pull_strength: float = Field(ge=0.0, le=1.0)
    horizon: str  # e.g. "3-10d"
    supporting_evidence_count: int
    counterforces: list[str]
    invalidation_conditions: list[str]
    trend: Literal["up", "down", "stable"]


class AttractorsOutput(BaseModel):
    assessment_id: str
    attractors: list[AttractorOutput]
    updated_at: datetime


# ---------------------------------------------------------------------------
# Propagation
# ---------------------------------------------------------------------------

class PropagationStep(BaseModel):
    step: int
    domain: str
    event: str
    time_bucket: Literal["T+0", "T+24h", "T+72h", "T+7d", "T+2-6w"]


class PropagationOutput(BaseModel):
    assessment_id: str
    sequence: list[PropagationStep]
    bottlenecks: list[str]
    second_order_effects: list[str]
    updated_at: datetime


# ---------------------------------------------------------------------------
# Delta
# ---------------------------------------------------------------------------

class DeltaField(BaseModel):
    field: str
    previous: Any
    current: Any
    direction: Literal["increased", "decreased", "unchanged", "new"]


class DeltaOutput(BaseModel):
    assessment_id: str
    regime_changed: bool
    threshold_direction: Literal["narrowing", "widening", "stable"]
    trigger_ranking_changes: list[DeltaField]
    attractor_pull_changes: list[DeltaField]
    damping_capacity_delta: float
    confidence_delta: float
    new_evidence_count: int
    summary: str
    updated_at: datetime


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

class EvidenceItem(BaseModel):
    evidence_id: str
    source: str
    timestamp: datetime
    source_quality: Literal["Low", "Medium", "High", "Primary"]
    impacted_area: str
    structural_novelty: float = Field(ge=0.0, le=1.0)
    confidence_contribution: float = Field(ge=0.0, le=1.0)
    provenance_link: str | None = None


class EvidenceOutput(BaseModel):
    assessment_id: str
    evidence: list[EvidenceItem]
    updated_at: datetime


# ---------------------------------------------------------------------------
# Brief
# ---------------------------------------------------------------------------

class BriefOutput(BaseModel):
    assessment_id: str
    forecast_posture: str  # e.g. "Upward-skewed energy risk"
    time_horizon: str  # e.g. "3-7 days"
    confidence: Literal["Low", "Medium", "High", "Very High"]
    why_it_matters: str
    dominant_driver: str
    strengthening_conditions: list[str]
    weakening_conditions: list[str]
    invalidation_conditions: list[str]
    updated_at: datetime


# ---------------------------------------------------------------------------
# Full normalized metrics schema
# ---------------------------------------------------------------------------

class StructuralForecastMetrics(BaseModel):
    """Full normalized schema combining all engine outputs for one assessment."""

    assessment_id: str
    regime_state: RegimeState
    dominant_axis: str
    coupling_score: float
    coupling_asymmetry: float
    propagation_risk: float
    threshold_distance: float
    transition_volatility: float
    reversibility_index: float
    damping_capacity: float
    attractor_candidates: list[str]
    trigger_sensitivity: float
    trigger_amplification: float
    expected_cross_domain_sequence: list[str]
    nonlinear_confidence: float
    structural_novelty: float
    update_delta: dict[str, Any]
    updated_at: datetime
