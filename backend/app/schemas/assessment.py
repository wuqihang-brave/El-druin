"""
Assessment schema
=================

Top-level assessment container models used by the assessments API.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel

from app.schemas.structural_forecast import RegimeState


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class AssessmentType(str, Enum):
    event_driven = "event_driven"
    region_sector_watch = "region_sector_watch"
    custom_scenario = "custom_scenario"
    structural_watch = "structural_watch"


class AssessmentStatus(str, Enum):
    active = "active"
    archived = "archived"
    draft = "draft"
    review_required = "review_required"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Assessment(BaseModel):
    assessment_id: str
    title: str
    assessment_type: AssessmentType
    status: AssessmentStatus
    region_tags: list[str]
    domain_tags: list[str]
    created_at: datetime
    updated_at: datetime
    last_regime: RegimeState | None = None
    last_confidence: str | None = None
    alert_count: int = 0
    analyst_notes: str | None = None


class AssessmentListResponse(BaseModel):
    assessments: list[Assessment]
    total: int


class AssessmentCreate(BaseModel):
    title: str
    assessment_type: AssessmentType = AssessmentType.structural_watch
    status: AssessmentStatus = AssessmentStatus.active
    region_tags: list[str] = []
    domain_tags: list[str] = []
    analyst_notes: str | None = None


class AssessmentUpdate(BaseModel):
    title: str | None = None
    status: AssessmentStatus | None = None
    region_tags: list[str] | None = None
    domain_tags: list[str] | None = None
    last_regime: str | None = None
    last_confidence: str | None = None
    alert_count: int | None = None
    analyst_notes: str | None = None
