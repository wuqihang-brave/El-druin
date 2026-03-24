"""
Pydantic models for the Bayesian Bridge system.

Data structures:
    SourceInfo           – provenance of a piece of evidence
    InputEvidence        – a single evidence item with confidence score
    InferenceStep        – one LLM inference step in a reasoning chain
    GraphChange          – a single change applied to the knowledge graph
    ReasoningPath        – full audit trail from evidence → inference → graph update
    ExtractedFact        – a fact extracted from a news branch
    InterpretationBranch – one branch in the probability tree
    ProbabilityTree      – complete set of alternative interpretations for a report
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class SourceType(str, Enum):
    NEWS_ARTICLE = "news_article"
    USER_INPUT = "user_input"
    INFERENCE = "inference"


class ReasoningType(str, Enum):
    CAUSAL_EXTRACTION = "causal_extraction"
    ENTITY_LINKING = "entity_linking"
    DISAMBIGUATION = "disambiguation"
    CONFLICT_DETECTION = "conflict_detection"


class ChangeType(str, Enum):
    NODE_CREATED = "node_created"
    EDGE_CREATED = "edge_created"
    CONTRADICTS_EDGE_CREATED = "contradicts_edge_created"


class AuditStatus(str, Enum):
    APPROVED = "approved"
    FLAGGED = "flagged"
    PENDING_REVIEW = "pending_review"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class SourceInfo(BaseModel):
    """Provenance metadata for a piece of source evidence."""

    type: SourceType = Field(..., description="Type of the source")
    url: str = Field(default="", description="URL of the original source")
    reliability: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Reliability score of the source (0.0–1.0)",
    )


class InputEvidence(BaseModel):
    """A single evidence item linked to a named entity."""

    entity_id: str = Field(..., description="Identifier of the entity")
    entity_name: str = Field(..., description="Human-readable entity name")
    context: str = Field(default="", description="Context in which the entity was mentioned")
    confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Confidence in this evidence (0.0–1.0)",
    )


class InferenceStep(BaseModel):
    """One LLM inference step in a reasoning chain."""

    model_config = {"use_enum_values": True}

    step_num: int = Field(..., ge=1, description="Sequential step number (1-based)")
    llm_prompt: str = Field(default="", description="Prompt sent to the LLM")
    llm_response: str = Field(default="", description="Response received from the LLM")
    confidence_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence produced by this step (0.0–1.0)",
    )
    reasoning_type: ReasoningType = Field(
        default=ReasoningType.CAUSAL_EXTRACTION,
        description="Type of reasoning performed in this step",
    )


class GraphChange(BaseModel):
    """A single change that was applied to the knowledge graph."""

    model_config = {"use_enum_values": True}

    change_type: ChangeType = Field(..., description="Type of graph mutation")
    entity_id: str = Field(..., description="Primary entity involved in the change")
    target_entity_id: str = Field(
        default="",
        description="Target entity for edge changes",
    )
    relationship_type: str = Field(
        default="",
        description="Relationship label (e.g. INFLUENCES, CONTRADICTS)",
    )
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extra properties stored on the created node/edge",
    )


# ---------------------------------------------------------------------------
# Top-level models
# ---------------------------------------------------------------------------

class ReasoningPath(BaseModel):
    """Complete audit trail from evidence → LLM inference → graph update."""

    model_config = {"use_enum_values": True}

    path_id: str = Field(..., description="UUID of this reasoning path")
    timestamp: str = Field(..., description="ISO 8601 creation timestamp")
    source: SourceInfo = Field(..., description="Provenance of the evidence")
    input_evidence: List[InputEvidence] = Field(
        default_factory=list,
        description="Evidence items used as input",
    )
    inference_steps: List[InferenceStep] = Field(
        default_factory=list,
        description="Ordered list of LLM inference steps",
    )
    graph_changes: List[GraphChange] = Field(
        default_factory=list,
        description="Graph mutations resulting from this reasoning path",
    )
    final_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Weighted confidence across all inference steps",
    )
    audit_status: AuditStatus = Field(
        default=AuditStatus.PENDING_REVIEW,
        description="Current audit status",
    )


class ExtractedFact(BaseModel):
    """A single fact extracted within an interpretation branch."""

    type: str = Field(..., description="Relation type (e.g. INFLUENCES, CONTRADICTS)")
    from_entity: str = Field(..., alias="from", description="Source entity of the fact")
    to_entity: str = Field(..., alias="to", description="Target entity of the fact")
    causality_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Causality score (0.0–1.0) for INFLUENCES facts",
    )
    conflict_confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Conflict confidence (0.0–1.0) for CONTRADICTS facts",
    )

    model_config = {"populate_by_name": True}


class InterpretationBranch(BaseModel):
    """One alternative interpretation of a news report."""

    branch_id: int = Field(..., ge=1, description="Sequential branch number (1-based)")
    interpretation: str = Field(..., description="Human-readable description of this interpretation")
    evidence_nodes: List[str] = Field(
        default_factory=list,
        description="Entity IDs relevant to this branch",
    )
    extracted_facts: List[ExtractedFact] = Field(
        default_factory=list,
        description="Facts extracted in this interpretation",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Raw confidence score for this interpretation",
    )
    weight: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Normalised probability weight (sums to 1.0 across all branches)",
    )
    source_reliability: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Reliability of the originating source",
    )
    calculated_weight: float = Field(
        default=0.0,
        ge=0.0,
        description="Raw product: confidence × source_reliability (before normalisation)",
    )


class ProbabilityTree(BaseModel):
    """Complete probability tree for a single intelligence report."""

    report_id: str = Field(..., description="UUID of the intelligence report")
    timestamp: str = Field(..., description="ISO 8601 creation timestamp")
    raw_text: str = Field(..., description="Original news/report text")
    interpretation_branches: List[InterpretationBranch] = Field(
        default_factory=list,
        description="Alternative interpretation branches",
    )
    total_probability: float = Field(
        default=1.0,
        description="Sum of all normalised branch weights (should be ~1.0)",
    )
    selected_branch: int = Field(
        default=1,
        description="branch_id of the interpretation chosen for graph insertion",
    )
    reasoning_summary: str = Field(
        default="",
        description="Plain-English explanation of why the selected branch was chosen",
    )
