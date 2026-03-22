"""SQLAlchemy async ORM model for events."""

import uuid

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import declared_attr

from app.db.postgres import Base

_SEVERITY_ENUM = Enum(
    "low", "medium", "high", "critical", name="event_severity_enum"
)


class Event(Base):
    """Persisted intelligence event.

    Attributes:
        id: Primary key (UUID).
        source: Originating data source identifier.
        title: Short human-readable title.
        description: Full event description.
        event_type: Categorical event type (e.g. political, economic).
        severity: Severity level – low | medium | high | critical.
        location: GeoJSON-compatible location dict.
        entities: List of entity dicts referenced by this event.
        tags: Free-text tags for quick filtering.
        metadata: Arbitrary extra data.
        embedding_id: Reference ID in the vector store.
        created_at: Row creation timestamp (server-side default).
        updated_at: Last modification timestamp.
    """

    __tablename__ = "events"

    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        nullable=False,
    )
    source = Column(String(255), nullable=False, index=True)
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    event_type = Column(String(128), nullable=False)
    severity = Column(_SEVERITY_ENUM, nullable=False, default="medium")
    location = Column(JSON, nullable=True)
    entities = Column(JSON, nullable=False, default=list)
    tags = Column(ARRAY(String), nullable=False, default=list)
    event_metadata = Column("metadata", JSON, nullable=False, default=dict)
    embedding_id = Column(String(255), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_events_event_type", "event_type"),
        Index("ix_events_severity", "severity"),
        Index("ix_events_created_at", "created_at"),
        Index("ix_events_tags", "tags", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return f"<Event id={self.id} title={self.title!r}>"
