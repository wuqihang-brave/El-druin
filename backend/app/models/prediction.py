"""SQLAlchemy async ORM model for predictions."""

import uuid

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.db.postgres import Base


class Prediction(Base):
    """Multi-agent prediction record.

    Attributes:
        id: Primary key (UUID).
        event_id: Foreign key referencing the triggering event.
        prediction_type: Category of prediction (e.g. escalation, economic_impact).
        confidence: Aggregate confidence score 0.0-1.0.
        timeframe: Human-readable timeframe string (e.g. "7d", "30d").
        agents_results: JSON list of per-agent result dicts.
        consensus_confidence: Weighted consensus confidence score.
        status: Lifecycle status (pending | running | completed | failed).
        metadata: Arbitrary extra data.
        created_at: Row creation timestamp.
        updated_at: Last modification timestamp.
    """

    __tablename__ = "predictions"

    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        nullable=False,
    )
    event_id = Column(
        UUID(as_uuid=False),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prediction_type = Column(String(128), nullable=False)
    confidence = Column(Float, nullable=False, default=0.0)
    timeframe = Column(String(64), nullable=True)
    agents_results = Column(JSON, nullable=False, default=list)
    consensus_confidence = Column(Float, nullable=False, default=0.0)
    status = Column(String(32), nullable=False, default="pending")
    prediction_metadata = Column("metadata", JSON, nullable=False, default=dict)
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
        return f"<Prediction id={self.id} type={self.prediction_type!r} confidence={self.confidence}>"
