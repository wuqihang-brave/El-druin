"""Analysis API router."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.postgres import get_db
from app.models.analysis import Analysis
from app.models.schemas import AnalysisRequest, AnalysisResponse, TokenData

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["Analysis"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _analysis_to_schema(row: Analysis) -> AnalysisResponse:
    return AnalysisResponse(
        id=str(row.id),
        analysis_type=row.analysis_type,
        entity_ids=row.entity_ids or [],
        result=row.result or {},
        methodology=row.methodology or "",
        confidence=row.confidence or 0.0,
        execution_time_ms=row.execution_time_ms,
        created_at=row.created_at,
    )


async def _save_analysis(
    db: AsyncSession,
    analysis_type: str,
    entity_ids: list[str],
    result: dict,
    methodology: str,
    confidence: float,
    execution_time_ms: float,
    created_by: str,
) -> Analysis:
    row = Analysis(
        id=str(uuid.uuid4()),
        analysis_type=analysis_type,
        entity_ids=entity_ids,
        result=result,
        methodology=methodology,
        confidence=confidence,
        execution_time_ms=execution_time_ms,
        created_by=created_by,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# POST /analysis/causality
# ---------------------------------------------------------------------------


@router.post(
    "/causality",
    response_model=AnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Causal chain analysis",
)
async def causality_analysis(
    payload: AnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> AnalysisResponse:
    """Perform causal chain analysis for a set of entities/events.

    Args:
        payload: Analysis request with entity IDs.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        :class:`AnalysisResponse` with causal chain results.
    """
    start = time.monotonic()
    result: dict[str, Any] = {}
    confidence = 0.75

    try:
        from app.agents.causal_analyst import CausalAnalystAgent
        from app.config import settings as _settings
        from app.db.postgres import fetch_all

        rows = await fetch_all(
            "SELECT id, title, description, event_type, severity FROM events WHERE id = ANY(:ids)",
            {"ids": payload.entity_ids},
        )
        events_combined = {
            "entities": payload.entity_ids,
            "events": rows,
            "title": "Multi-entity causal analysis",
            "description": " ".join(r.get("description", "") for r in rows[:3]),
            "event_type": "causal_analysis",
            "severity": "medium",
            "tags": [],
        }
        agent = CausalAnalystAgent(_settings)
        agent_result = await agent.analyze(
            events_combined, {"prediction_type": "causality"}
        )
        result = {
            "causal_chain": agent_result.analysis,
            "root_causes": agent_result.metadata.get("root_causes", []),
            "cascading_effects": agent_result.metadata.get("cascading_effects", []),
            "evidence": agent_result.evidence,
        }
        confidence = agent_result.confidence
    except Exception as exc:
        logger.warning("Causal analysis LLM call failed: %s", exc)
        result = {"message": "Analysis pending — LLM unavailable", "entity_ids": payload.entity_ids}

    elapsed = (time.monotonic() - start) * 1000
    row = await _save_analysis(
        db,
        analysis_type="causality",
        entity_ids=payload.entity_ids,
        result=result,
        methodology="Multi-agent causal chain analysis",
        confidence=confidence,
        execution_time_ms=elapsed,
        created_by=current_user.user_id or "unknown",
    )
    return _analysis_to_schema(row)


# ---------------------------------------------------------------------------
# POST /analysis/impact
# ---------------------------------------------------------------------------


@router.post(
    "/impact",
    response_model=AnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Impact assessment (what-if scenario)",
)
async def impact_analysis(
    payload: AnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> AnalysisResponse:
    """Assess the potential impact of an event or scenario.

    Args:
        payload: Analysis request.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        :class:`AnalysisResponse` with impact assessment.
    """
    start = time.monotonic()
    result: dict[str, Any] = {}
    confidence = 0.70

    try:
        from app.agents.economic_agent import EconomicAgent
        from app.agents.geopolitical_agent import GeopoliticalAgent
        from app.config import settings as _settings
        import asyncio

        event_data = {
            "entity_ids": payload.entity_ids,
            "title": "Impact assessment",
            "description": str(payload.parameters),
            "event_type": "impact_analysis",
            "severity": payload.parameters.get("severity", "medium"),
            "entities": [],
            "tags": [],
        }
        eco = EconomicAgent(_settings)
        geo = GeopoliticalAgent(_settings)
        eco_result, geo_result = await asyncio.gather(
            eco.analyze(event_data, {"prediction_type": "impact"}),
            geo.analyze(event_data, {"prediction_type": "impact"}),
            return_exceptions=True,
        )
        result = {
            "economic_impact": eco_result.analysis if not isinstance(eco_result, Exception) else "unavailable",
            "geopolitical_impact": geo_result.analysis if not isinstance(geo_result, Exception) else "unavailable",
            "parameters": payload.parameters,
        }
        confs = [
            r.confidence
            for r in [eco_result, geo_result]
            if not isinstance(r, Exception)
        ]
        confidence = sum(confs) / len(confs) if confs else 0.7
    except Exception as exc:
        logger.warning("Impact analysis failed: %s", exc)
        result = {"message": "Impact analysis pending", "entity_ids": payload.entity_ids}

    elapsed = (time.monotonic() - start) * 1000
    row = await _save_analysis(
        db,
        analysis_type="impact",
        entity_ids=payload.entity_ids,
        result=result,
        methodology="Economic and geopolitical agent analysis",
        confidence=confidence,
        execution_time_ms=elapsed,
        created_by=current_user.user_id or "unknown",
    )
    return _analysis_to_schema(row)


# ---------------------------------------------------------------------------
# POST /analysis/networks
# ---------------------------------------------------------------------------


@router.post(
    "/networks",
    response_model=AnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Network analysis (connections, centrality, communities)",
)
async def network_analysis(
    payload: AnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> AnalysisResponse:
    """Analyze entity network connections and centrality.

    Args:
        payload: Analysis request with entity IDs.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        :class:`AnalysisResponse` with network analysis.
    """
    start = time.monotonic()
    result: dict[str, Any] = {}
    confidence = 0.80

    try:
        from app.db.neo4j_client import neo4j_client

        nodes_seen: set = set()
        edges: list[dict] = []

        for entity_id in payload.entity_ids[:5]:
            subgraph = await neo4j_client.get_subgraph(entity_id, depth=2)
            for node in subgraph.get("nodes", []):
                node_id = node.get("id", str(node))
                nodes_seen.add(node_id)
            for rel in subgraph.get("relationships", []):
                edges.append({"relationship": rel})

        # Simple degree centrality
        degree: dict[str, int] = {nid: 0 for nid in nodes_seen}
        for edge in edges:
            src = str(edge.get("relationship", {}).get("start_id", ""))
            tgt = str(edge.get("relationship", {}).get("end_id", ""))
            if src in degree:
                degree[src] += 1
            if tgt in degree:
                degree[tgt] += 1

        sorted_centrality = sorted(degree.items(), key=lambda x: x[1], reverse=True)
        result = {
            "node_count": len(nodes_seen),
            "edge_count": len(edges),
            "top_central_nodes": sorted_centrality[:10],
        }
    except Exception as exc:
        logger.warning("Network analysis failed: %s", exc)
        result = {"message": "Network analysis pending", "entity_ids": payload.entity_ids}

    elapsed = (time.monotonic() - start) * 1000
    row = await _save_analysis(
        db,
        analysis_type="networks",
        entity_ids=payload.entity_ids,
        result=result,
        methodology="Knowledge graph network analysis",
        confidence=confidence,
        execution_time_ms=elapsed,
        created_by=current_user.user_id or "unknown",
    )
    return _analysis_to_schema(row)


# ---------------------------------------------------------------------------
# POST /analysis/trends
# ---------------------------------------------------------------------------


@router.post(
    "/trends",
    response_model=AnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trend detection across a time window",
)
async def trend_analysis(
    payload: AnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> AnalysisResponse:
    """Detect trends in event frequency and severity over time.

    Args:
        payload: Analysis request with optional parameters (days, event_type).
        db: Database session.
        current_user: Authenticated user.

    Returns:
        :class:`AnalysisResponse` with trend data.
    """
    from datetime import timedelta, UTC
    from datetime import datetime as dt

    start = time.monotonic()
    days = int(payload.parameters.get("days", 30))
    event_type = payload.parameters.get("event_type")

    try:
        from app.db.postgres import fetch_all

        since = dt.now(UTC) - timedelta(days=days)
        params: dict[str, Any] = {"since": since}
        sql = (
            "SELECT DATE(created_at) AS day, event_type, severity, COUNT(*) AS count "
            "FROM events WHERE created_at >= :since"
        )
        if event_type:
            sql += " AND event_type = :event_type"
            params["event_type"] = event_type
        sql += " GROUP BY day, event_type, severity ORDER BY day"
        rows = await fetch_all(sql, params)

        # Build simple trend
        daily_counts: dict[str, int] = {}
        for row in rows:
            day = str(row.get("day", ""))
            daily_counts[day] = daily_counts.get(day, 0) + int(row.get("count", 0))

        trend_direction = "stable"
        counts = list(daily_counts.values())
        if len(counts) >= 2:
            first_half = sum(counts[: len(counts) // 2]) / max(1, len(counts) // 2)
            second_half = sum(counts[len(counts) // 2 :]) / max(1, len(counts) - len(counts) // 2)
            if second_half > first_half * 1.2:
                trend_direction = "increasing"
            elif second_half < first_half * 0.8:
                trend_direction = "decreasing"

        result: dict[str, Any] = {
            "daily_counts": daily_counts,
            "trend_direction": trend_direction,
            "period_days": days,
            "total_events": sum(counts),
        }
        confidence = 0.85
    except Exception as exc:
        logger.warning("Trend analysis failed: %s", exc)
        result = {"message": "Trend analysis pending", "entity_ids": payload.entity_ids}
        confidence = 0.5

    elapsed = (time.monotonic() - start) * 1000
    row = await _save_analysis(
        db,
        analysis_type="trends",
        entity_ids=payload.entity_ids,
        result=result,
        methodology="Time-series event frequency analysis",
        confidence=confidence,
        execution_time_ms=elapsed,
        created_by=current_user.user_id or "unknown",
    )
    return _analysis_to_schema(row)


# ---------------------------------------------------------------------------
# GET /analysis/accuracy-report
# ---------------------------------------------------------------------------


@router.get(
    "/accuracy-report",
    response_model=dict,
    summary="System-wide accuracy metrics",
)
async def accuracy_report(
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> dict:
    """Return system-wide prediction accuracy metrics.

    Args:
        db: Database session.
        current_user: Authenticated user.

    Returns:
        Accuracy metrics dict.
    """
    from app.db.postgres import fetch_all

    try:
        rows = await fetch_all(
            """
            SELECT prediction_type,
                   COUNT(*)             AS total,
                   AVG(confidence)      AS avg_confidence,
                   AVG(consensus_confidence) AS avg_consensus_confidence
            FROM predictions
            WHERE status = 'completed'
            GROUP BY prediction_type
            """
        )
        return {
            "prediction_types": [
                {
                    "type": r["prediction_type"],
                    "total": r["total"],
                    "avg_confidence": round(float(r["avg_confidence"] or 0), 4),
                    "avg_consensus": round(float(r["avg_consensus_confidence"] or 0), 4),
                }
                for r in rows
            ]
        }
    except Exception as exc:
        logger.warning("Accuracy report failed: %s", exc)
        return {"prediction_types": [], "error": str(exc)}
