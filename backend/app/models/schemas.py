"""Pydantic v2 schemas for the EL'druin Intelligence Platform."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _new_uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# User / Auth
# ---------------------------------------------------------------------------


class UserCreate(BaseModel):
    """Schema for creating a new user."""

    username: str
    email: str
    password: str
    full_name: Optional[str] = None
    roles: list[str] = Field(default_factory=lambda: ["viewer"])
    clearance_level: str = "internal"
    tenant_id: str = "default"


class UserResponse(BaseModel):
    """Public user representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str
    full_name: Optional[str] = None
    roles: list[str]
    clearance_level: str
    tenant_id: str
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Decoded JWT token payload."""

    user_id: Optional[str] = None
    username: Optional[str] = None
    roles: list[str] = Field(default_factory=list)
    tenant_id: str = "default"


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class EventCreate(BaseModel):
    """Schema for creating a new event."""

    source: str
    title: str
    description: Optional[str] = None
    event_type: str
    severity: str = "medium"
    location: Optional[dict[str, Any]] = None
    entities: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EventUpdate(BaseModel):
    """Schema for updating an existing event."""

    source: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    event_type: Optional[str] = None
    severity: Optional[str] = None
    location: Optional[dict[str, Any]] = None
    entities: Optional[list[dict[str, Any]]] = None
    tags: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None


class EventResponse(BaseModel):
    """Full event representation returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    source: str
    title: str
    description: Optional[str] = None
    event_type: str
    severity: str
    location: Optional[dict[str, Any]] = None
    entities: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Predictions
# ---------------------------------------------------------------------------


class AgentResultSchema(BaseModel):
    """Result from a single agent."""

    agent_type: str
    analysis: str
    confidence: float
    evidence: list[str]
    reasoning: str
    token_usage: dict[str, int]
    execution_time_ms: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConsensusResultSchema(BaseModel):
    """Aggregated consensus from multiple agents."""

    final_prediction: str
    consensus_confidence: float
    agreement_score: float
    dissenting_agents: list[str]
    key_insights: list[str]
    uncertainty_factors: list[str]
    agent_breakdown: dict[str, float]


class PredictionCreate(BaseModel):
    """Schema for requesting a new prediction."""

    event_id: str
    prediction_type: str
    timeframe: Optional[str] = "7d"
    metadata: dict[str, Any] = Field(default_factory=dict)


class PredictionResponse(BaseModel):
    """Full prediction representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str
    prediction_type: str
    confidence: float
    timeframe: Optional[str]
    agents_results: list[AgentResultSchema] = Field(default_factory=list)
    consensus_confidence: float
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


class AnalysisRequest(BaseModel):
    """Schema for requesting an analysis."""

    analysis_type: str  # causality | impact | networks | trends
    entity_ids: list[str]
    parameters: dict[str, Any] = Field(default_factory=dict)


class AnalysisResponse(BaseModel):
    """Schema for analysis results."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    analysis_type: str
    entity_ids: list[str]
    result: dict[str, Any]
    methodology: str
    confidence: float
    execution_time_ms: Optional[float] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------


class AlertRuleCreate(BaseModel):
    """Schema for creating an alert rule."""

    condition_type: str
    threshold: float
    notification_channels: list[str] = Field(default_factory=lambda: ["websocket"])
    is_active: bool = True


class AlertRuleResponse(BaseModel):
    """Persisted alert rule."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    watchlist_id: str
    condition_type: str
    threshold: float
    notification_channels: list[str]
    is_active: bool


class WatchlistCreate(BaseModel):
    """Schema for adding an item to the watchlist."""

    entity_id: str
    entity_type: str
    criteria: dict[str, Any] = Field(default_factory=dict)
    alert_rules: list[AlertRuleCreate] = Field(default_factory=list)


class WatchlistResponse(BaseModel):
    """Persisted watchlist item."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    entity_id: str
    entity_type: str
    criteria: dict[str, Any]
    alert_rules: list[AlertRuleResponse] = Field(default_factory=list)
    created_at: datetime


# ---------------------------------------------------------------------------
# Knowledge Graph
# ---------------------------------------------------------------------------


class EntityResponse(BaseModel):
    """KG entity representation."""

    id: str
    entity_class: str
    properties: dict[str, Any]
    relationships: list[dict[str, Any]] = Field(default_factory=list)


class RelationshipResponse(BaseModel):
    """KG relationship representation."""

    id: str
    source_id: str
    target_id: str
    relationship_type: str
    properties: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Ontology
# ---------------------------------------------------------------------------


class OntologyCreate(BaseModel):
    """Schema for creating an ontology."""

    name: str
    entity_classes: dict[str, Any]
    relationship_types: dict[str, Any]
    validation_rules: dict[str, Any] = Field(default_factory=dict)
    perspectives: dict[str, Any] = Field(default_factory=dict)


class OntologyResponse(BaseModel):
    """Persisted ontology."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    version: int
    entity_classes: dict[str, Any]
    relationship_types: dict[str, Any]
    validation_rules: dict[str, Any]
    perspectives: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    items: list[T]
    total: int
    page: int
    size: int
    pages: int

    @classmethod
    def create(
        cls, items: list[T], total: int, page: int, size: int
    ) -> "PaginatedResponse[T]":
        """Create a paginated response.

        Args:
            items: Page of items.
            total: Total number of items across all pages.
            page: Current page number (1-indexed).
            size: Items per page.

        Returns:
            PaginatedResponse instance.
        """
        pages = max(1, (total + size - 1) // size)
        return cls(items=items, total=total, page=page, size=size, pages=pages)
