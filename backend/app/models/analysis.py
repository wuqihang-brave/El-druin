"""SQLAlchemy async ORM model for analysis results."""

import uuid

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres import Base


class Analysis(Base):
    """Stored analysis result.

    Attributes:
        id: Primary key (UUID).
        analysis_type: Type of analysis (causality | impact | networks | trends).
        entity_ids: JSON list of entity IDs that were analysed.
        result: Full analysis result payload.
        methodology: Description of the analytical methodology used.
        confidence: Overall confidence score 0.0-1.0.
        execution_time_ms: Wall-clock time taken for the analysis.
        created_by: User ID that initiated the analysis.
        created_at: Row creation timestamp.
    """

    __tablename__ = "analysis_results"

    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        nullable=False,
    )
    analysis_type = Column(String(128), nullable=False, index=True)
    entity_ids = Column(JSON, nullable=False, default=list)
    result = Column(JSON, nullable=False, default=dict)
    methodology = Column(Text, nullable=True)
    confidence = Column(Float, nullable=False, default=0.0)
    execution_time_ms = Column(Float, nullable=True)
    created_by = Column(String(255), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Analysis id={self.id} type={self.analysis_type!r}>"
