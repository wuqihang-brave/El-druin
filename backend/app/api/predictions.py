"""Predictions API router."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.postgres import get_db
from app.models.prediction import Prediction
from app.models.schemas import (
    AgentResultSchema,
    PredictionCreate,
    PredictionResponse,
    TokenData,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/predictions", tags=["Predictions"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _prediction_to_schema(row: Prediction) -> PredictionResponse:
    """Convert ORM Prediction to PredictionResponse schema."""
    agents_raw = row.agents_results or []
    agents: list[AgentResultSchema] = []
    for a in agents_raw:
        if isinstance(a, dict):
            try:
                agents.append(AgentResultSchema(**a))
            except Exception:
                pass
    return PredictionResponse(
        id=str(row.id),
        event_id=str(row.event_id),
        prediction_type=row.prediction_type,
        confidence=row.confidence or 0.0,
        timeframe=row.timeframe,
        agents_results=agents,
        consensus_confidence=row.consensus_confidence or 0.0,
        status=row.status or "pending",
        metadata=row.prediction_metadata or {},
        created_at=row.created_at,
    )


# ---------------------------------------------------------------------------
# POST /predictions
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=PredictionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a prediction (runs multi-agent analysis)",
)
async def create_prediction(
    payload: PredictionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> PredictionResponse:
    """Trigger multi-agent prediction analysis for an event.

    Args:
        payload: Prediction creation payload.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        Created :class:`PredictionResponse`.

    Raises:
        HTTPException: 404 if the referenced event does not exist.
    """
    from app.models.event import Event

    event_result = await db.execute(
        select(Event).where(Event.id == payload.event_id)
    )
    event = event_result.scalar_one_or_none()
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {payload.event_id} not found",
        )

    # Create a pending record immediately
    prediction_id = str(uuid.uuid4())
    prediction = Prediction(
        id=prediction_id,
        event_id=payload.event_id,
        prediction_type=payload.prediction_type,
        timeframe=payload.timeframe,
        status="running",
        confidence=0.0,
        consensus_confidence=0.0,
        agents_results=[],
        prediction_metadata=payload.metadata,
    )
    db.add(prediction)
    await db.flush()

    # Run multi-agent analysis
    try:
        from app.core.predictor import prediction_orchestrator

        event_data = {
            "id": str(event.id),
            "title": event.title,
            "description": event.description,
            "event_type": event.event_type,
            "severity": event.severity,
            "location": event.location,
            "entities": event.entities,
            "tags": event.tags,
        }
        pred_result = await prediction_orchestrator.predict(
            event_data, payload.prediction_type
        )

        agents_dicts = [
            {
                "agent_type": r.agent_type,
                "analysis": r.analysis,
                "confidence": r.confidence,
                "evidence": r.evidence,
                "reasoning": r.reasoning,
                "token_usage": r.token_usage,
                "execution_time_ms": r.execution_time_ms,
                "metadata": r.metadata,
            }
            for r in pred_result.agent_results
        ]

        prediction.agents_results = agents_dicts
        prediction.confidence = pred_result.confidence
        prediction.consensus_confidence = pred_result.confidence
        prediction.status = "completed"
    except Exception as exc:
        logger.error("Prediction analysis failed: %s", exc)
        prediction.status = "failed"
        existing_meta = dict(prediction.prediction_metadata or {})
        existing_meta["error"] = str(exc)
        prediction.prediction_metadata = existing_meta

    await db.flush()
    await db.refresh(prediction)
    return _prediction_to_schema(prediction)


# ---------------------------------------------------------------------------
# GET /predictions/{prediction_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{prediction_id}",
    response_model=PredictionResponse,
    summary="Get prediction with full agent breakdown",
)
async def get_prediction(
    prediction_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> PredictionResponse:
    """Retrieve a prediction by ID.

    Args:
        prediction_id: Prediction UUID.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        :class:`PredictionResponse`.

    Raises:
        HTTPException: 404 if not found.
    """
    result = await db.execute(
        select(Prediction).where(Prediction.id == prediction_id)
    )
    pred = result.scalar_one_or_none()
    if pred is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found"
        )
    return _prediction_to_schema(pred)


# ---------------------------------------------------------------------------
# GET /predictions/{prediction_id}/timeline
# ---------------------------------------------------------------------------


@router.get(
    "/{prediction_id}/timeline",
    response_model=list[dict],
    summary="Confidence change timeline for a prediction",
)
async def get_prediction_timeline(
    prediction_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> list[dict]:
    """Return a timeline of confidence changes for a prediction.

    In the current implementation, returns per-agent confidence snapshots.

    Args:
        prediction_id: Prediction UUID.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        List of confidence snapshot dicts.

    Raises:
        HTTPException: 404 if not found.
    """
    result = await db.execute(
        select(Prediction).where(Prediction.id == prediction_id)
    )
    pred = result.scalar_one_or_none()
    if pred is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found"
        )

    timeline = []
    for i, agent in enumerate(pred.agents_results or []):
        timeline.append(
            {
                "step": i + 1,
                "agent_type": agent.get("agent_type"),
                "confidence": agent.get("confidence", 0.0),
                "timestamp": pred.created_at.isoformat() if pred.created_at else None,
            }
        )
    if pred.consensus_confidence:
        timeline.append(
            {
                "step": len(timeline) + 1,
                "agent_type": "consensus",
                "confidence": pred.consensus_confidence,
                "timestamp": pred.created_at.isoformat() if pred.created_at else None,
            }
        )
    return timeline


# ---------------------------------------------------------------------------
# GET /predictions/{prediction_id}/analysis
# ---------------------------------------------------------------------------


@router.get(
    "/{prediction_id}/analysis",
    response_model=dict,
    summary="Detailed per-agent analysis for a prediction",
)
async def get_prediction_analysis(
    prediction_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> dict:
    """Return detailed per-agent analysis for a prediction.

    Args:
        prediction_id: Prediction UUID.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        Dict with agent analyses keyed by agent type.

    Raises:
        HTTPException: 404 if not found.
    """
    result = await db.execute(
        select(Prediction).where(Prediction.id == prediction_id)
    )
    pred = result.scalar_one_or_none()
    if pred is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found"
        )

    agents_by_type: dict[str, Any] = {}
    for agent in pred.agents_results or []:
        agent_type = agent.get("agent_type", "unknown")
        agents_by_type[agent_type] = agent

    return {
        "prediction_id": prediction_id,
        "prediction_type": pred.prediction_type,
        "consensus_confidence": pred.consensus_confidence,
        "agents": agents_by_type,
    }


# ---------------------------------------------------------------------------
# POST /predictions/{prediction_id}/scenarios
# ---------------------------------------------------------------------------


@router.post(
    "/{prediction_id}/scenarios",
    response_model=list[dict],
    summary="Generate alternative scenarios for a prediction",
)
async def generate_scenarios(
    prediction_id: str,
    num_scenarios: int = Query(default=3, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> list[dict]:
    """Generate alternative future scenarios for a prediction.

    Args:
        prediction_id: Reference prediction UUID.
        num_scenarios: Number of scenarios to generate.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        List of scenario dicts.

    Raises:
        HTTPException: 404 if prediction not found.
    """
    result = await db.execute(
        select(Prediction).where(Prediction.id == prediction_id)
    )
    pred = result.scalar_one_or_none()
    if pred is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found"
        )

    from app.core.predictor import prediction_orchestrator
    import dataclasses

    scenarios = await prediction_orchestrator.generate_scenarios(
        prediction_id, num_scenarios=num_scenarios
    )
    return [dataclasses.asdict(s) for s in scenarios]


# ---------------------------------------------------------------------------
# GET /predictions/{prediction_id}/accuracy
# ---------------------------------------------------------------------------


@router.get(
    "/{prediction_id}/accuracy",
    response_model=dict,
    summary="Historical accuracy for this prediction type",
)
async def get_prediction_accuracy(
    prediction_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> dict:
    """Return historical accuracy metrics for a prediction type.

    Args:
        prediction_id: Reference prediction UUID.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        Accuracy metrics dict.

    Raises:
        HTTPException: 404 if not found.
    """
    result = await db.execute(
        select(Prediction).where(Prediction.id == prediction_id)
    )
    pred = result.scalar_one_or_none()
    if pred is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found"
        )

    from app.core.predictor import prediction_orchestrator
    import dataclasses

    metrics = await prediction_orchestrator.get_accuracy_metrics(
        pred.prediction_type
    )
    return dataclasses.asdict(metrics)
