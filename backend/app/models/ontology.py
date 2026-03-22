"""SQLAlchemy async ORM model for ontologies."""

import uuid

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres import Base


class Ontology(Base):
    """Enterprise ontology definition.

    Attributes:
        id: Primary key (UUID).
        name: Human-readable ontology name.
        version: Monotonically increasing version counter.
        entity_classes: Dict mapping class name → property definitions.
        relationship_types: Dict mapping relationship type → metadata.
        validation_rules: Dict of field-level validation rules.
        perspectives: Dict mapping perspective name → filter config.
        is_active: Whether this is the currently active ontology.
        created_at: Row creation timestamp.
        updated_at: Last modification timestamp.
    """

    __tablename__ = "ontologies"

    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        nullable=False,
    )
    name = Column(String(255), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    entity_classes = Column(JSON, nullable=False, default=dict)
    relationship_types = Column(JSON, nullable=False, default=dict)
    validation_rules = Column(JSON, nullable=False, default=dict)
    perspectives = Column(JSON, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Ontology id={self.id} name={self.name!r} v{self.version}>"
