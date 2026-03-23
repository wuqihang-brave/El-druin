"""
Knowledge-graph data models for EL'druin.

Defines the core domain objects used throughout the ``kg`` package:

* :class:`EntityType`  – allowed node types (prevents LLM hallucination)
* :class:`RelationType` – allowed edge types
* :class:`Entity`       – a typed named entity (node)
* :class:`Relation`     – a typed directed edge between two entities
* :class:`Triple`       – a (subject, predicate, object) fact with confidence
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Controlled vocabularies
# ---------------------------------------------------------------------------

class EntityType(str, Enum):
    """Allowed entity types.  Restricting to this set prevents LLM hallucination."""

    PERSON = "Person"
    ORGANIZATION = "Organization"
    LOCATION = "Location"
    EVENT = "Event"
    DATE = "Date"


class RelationType(str, Enum):
    """Allowed relation types between entities."""

    WORKS_FOR = "WORKS_FOR"
    LOCATED_IN = "LOCATED_IN"
    PARTICIPATES_IN = "PARTICIPATES_IN"
    OWNS = "OWNS"
    MANAGES = "MANAGES"
    BORN_IN = "BORN_IN"
    PREDECESSOR = "PREDECESSOR"
    SUCCESSOR = "SUCCESSOR"
    ALLIED_WITH = "ALLIED_WITH"
    OPPOSED_TO = "OPPOSED_TO"
    PART_OF = "PART_OF"
    CAUSED_BY = "CAUSED_BY"
    RELATED_TO = "RELATED_TO"


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------

class Entity(BaseModel):
    """A named entity extracted from news text.

    Attributes:
        name:        Canonical surface form (e.g. ``"Tim Cook"``).
        entity_type: One of :class:`EntityType`.
        description: Optional short description produced by the LLM.
    """

    name: str = Field(..., description="Canonical entity name")
    entity_type: EntityType = Field(..., description="Entity type")
    description: Optional[str] = Field(None, description="Short description")

    class Config:
        use_enum_values = True


class Relation(BaseModel):
    """A directed relation between two entities.

    Attributes:
        source:        Surface form of the source entity.
        target:        Surface form of the target entity.
        relation_type: One of :class:`RelationType`.
        description:   Optional natural-language gloss.
    """

    source: str = Field(..., description="Source entity name")
    target: str = Field(..., description="Target entity name")
    relation_type: RelationType = Field(..., description="Relation type")
    description: Optional[str] = Field(None, description="Natural-language gloss")

    class Config:
        use_enum_values = True


class Triple(BaseModel):
    """A (subject, predicate, object) fact extracted from text.

    Attributes:
        subject:       The subject entity.
        predicate:     The relation connecting them.
        obj:           The object entity.
        confidence:    Extraction confidence in ``[0.0, 1.0]``.
        source_text:   The sentence / passage the triple was extracted from.
    """

    subject: Entity = Field(..., description="Subject entity")
    predicate: Relation = Field(..., description="Connecting relation")
    obj: Entity = Field(..., description="Object entity")
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Extraction confidence",
    )
    source_text: Optional[str] = Field(None, description="Source sentence")

    # Convenience accessors used by GraphBuilder
    @property
    def subject_name(self) -> str:  # noqa: D401
        """Subject entity name."""
        return self.subject.name

    @property
    def object_name(self) -> str:  # noqa: D401
        """Object entity name."""
        return self.obj.name

    @property
    def relation_label(self) -> str:  # noqa: D401
        """Relation type string."""
        return self.predicate.relation_type
