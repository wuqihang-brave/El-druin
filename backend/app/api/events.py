"""Events API router."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.postgres import get_db
from app.models.event import Event
from app.models.schemas import (
    EventCreate,
    EventResponse,
    EventUpdate,
    PaginatedResponse,
    TokenData,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/events", tags=["Events"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event_to_schema(row: Event) -> EventResponse:
    """Convert ORM Event to EventResponse schema."""
    return EventResponse(
        id=str(row.id),
        source=row.source,
        title=row.title,
        description=row.description,
        event_type=row.event_type,
        severity=row.severity,
        location=row.location,
        entities=row.entities or [],
        tags=row.tags or [],
        metadata=row.event_metadata or {},
        embedding_id=row.embedding_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


# ---------------------------------------------------------------------------
# POST /events
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new event",
)
async def create_event(
    payload: EventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> EventResponse:
    """Create a new intelligence event.

    Generates a text embedding, stores the event in PostgreSQL, and
    creates a corresponding node in the knowledge graph.

    Args:
        payload: Event creation payload.
        db: Database session.
        current_user: Authenticated user token data.

    Returns:
        Created :class:`EventResponse`.
    """
    event_id = str(uuid.uuid4())
    embedding_id: Optional[str] = None

    # Generate embedding and upsert to vector store
    try:
        from app.core.embeddings import embedding_engine
        from app.db.pinecone_client import pinecone_client

        vector = await embedding_engine.encode_event(payload.model_dump())
        await pinecone_client.upsert_vectors(
            [{"id": event_id, "values": vector, "metadata": {"title": payload.title, "event_type": payload.event_type}}]
        )
        embedding_id = event_id
    except Exception as exc:
        logger.warning("Embedding/upsert failed: %s", exc)

    event = Event(
        id=event_id,
        source=payload.source,
        title=payload.title,
        description=payload.description,
        event_type=payload.event_type,
        severity=payload.severity,
        location=payload.location,
        entities=payload.entities,
        tags=payload.tags,
        event_metadata=payload.metadata,
        embedding_id=embedding_id,
    )
    db.add(event)
    await db.flush()
    await db.refresh(event)

    # Knowledge graph node
    try:
        from app.db.neo4j_client import neo4j_client

        await neo4j_client.create_node(
            "Event",
            {"id": event_id, "title": payload.title, "event_type": payload.event_type},
        )
    except Exception as exc:
        logger.warning("KG node creation failed: %s", exc)

    # Trigger workflows
    try:
        from app.collaboration.workflow_automation import workflow_engine

        triggered = await workflow_engine.evaluate_triggers(payload.model_dump())
        for wf_id in triggered:
            await workflow_engine.execute_workflow(wf_id, {"event": payload.model_dump()})
    except Exception as exc:
        logger.warning("Workflow trigger failed: %s", exc)

    return _event_to_schema(event)


# ---------------------------------------------------------------------------
# GET /events
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=PaginatedResponse[EventResponse],
    summary="List events with filtering and pagination",
)
async def list_events(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    event_type: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> PaginatedResponse[EventResponse]:
    """List events with optional filtering, sorting, and pagination.

    Args:
        page: 1-indexed page number.
        size: Page size.
        event_type: Optional event type filter.
        severity: Optional severity filter.
        source: Optional source filter.
        date_from: Optional inclusive start date filter.
        date_to: Optional inclusive end date filter.
        sort_by: Column to sort by.
        sort_order: "asc" or "desc".
        db: Database session.
        current_user: Authenticated user.

    Returns:
        :class:`PaginatedResponse` of events.
    """
    filters = []
    if event_type:
        filters.append(Event.event_type == event_type)
    if severity:
        filters.append(Event.severity == severity)
    if source:
        filters.append(Event.source == source)
    if date_from:
        filters.append(Event.created_at >= date_from)
    if date_to:
        filters.append(Event.created_at <= date_to)

    # Count
    count_stmt = select(func.count(Event.id))
    if filters:
        count_stmt = count_stmt.where(and_(*filters))
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Fetch page
    sort_col = getattr(Event, sort_by, Event.created_at)
    order_col = desc(sort_col) if sort_order == "desc" else sort_col

    stmt = select(Event).order_by(order_col).offset((page - 1) * size).limit(size)
    if filters:
        stmt = stmt.where(and_(*filters))
    result = await db.execute(stmt)
    events = result.scalars().all()

    return PaginatedResponse.create(
        items=[_event_to_schema(e) for e in events],
        total=total,
        page=page,
        size=size,
    )


# ---------------------------------------------------------------------------
# GET /events/search
# ---------------------------------------------------------------------------


@router.get(
    "/search",
    response_model=list[EventResponse],
    summary="Semantic search using embeddings",
)
async def search_events(
    query: str = Query(..., min_length=1),
    top_k: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> list[EventResponse]:
    """Search events using semantic similarity.

    Args:
        query: Search query string.
        top_k: Maximum number of results.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        List of semantically similar events.
    """
    try:
        from app.core.embeddings import embedding_engine
        from app.db.pinecone_client import pinecone_client

        vector = await embedding_engine.encode(query)
        matches = await pinecone_client.query_similar(vector, top_k=top_k)
        event_ids = [m["id"] for m in matches]
    except Exception as exc:
        logger.warning("Semantic search failed: %s; falling back to text search", exc)
        # Fallback: basic ILIKE text search
        stmt = (
            select(Event)
            .where(or_(Event.title.ilike(f"%{query}%"), Event.description.ilike(f"%{query}%")))
            .limit(top_k)
        )
        result = await db.execute(stmt)
        return [_event_to_schema(e) for e in result.scalars().all()]

    if not event_ids:
        return []

    stmt = select(Event).where(Event.id.in_(event_ids))
    result = await db.execute(stmt)
    events_map = {str(e.id): e for e in result.scalars().all()}
    # Preserve similarity order
    return [_event_to_schema(events_map[eid]) for eid in event_ids if eid in events_map]


# ---------------------------------------------------------------------------
# GET /events/{event_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{event_id}",
    response_model=EventResponse,
    summary="Get event by ID",
)
async def get_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> EventResponse:
    """Retrieve a single event by its ID.

    Args:
        event_id: Event UUID.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        :class:`EventResponse`.

    Raises:
        HTTPException: 404 if not found.
    """
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return _event_to_schema(event)


# ---------------------------------------------------------------------------
# GET /events/{event_id}/related
# ---------------------------------------------------------------------------


@router.get(
    "/{event_id}/related",
    response_model=list[dict],
    summary="Get related events from the Knowledge Graph",
)
async def get_related_events(
    event_id: str,
    depth: int = Query(default=1, ge=1, le=3),
    current_user: TokenData = Depends(get_current_user),
) -> list[dict]:
    """Return events related via knowledge graph relationships.

    Args:
        event_id: Root event ID.
        depth: Traversal depth.
        current_user: Authenticated user.

    Returns:
        List of related event node dicts.
    """
    try:
        from app.db.neo4j_client import neo4j_client

        subgraph = await neo4j_client.get_subgraph(event_id, depth=depth)
        return subgraph.get("nodes", [])
    except Exception as exc:
        logger.warning("Related events KG query failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# GET /events/{event_id}/timeline
# ---------------------------------------------------------------------------


@router.get(
    "/{event_id}/timeline",
    response_model=list[EventResponse],
    summary="Get timeline of events around this event",
)
async def get_event_timeline(
    event_id: str,
    window_hours: int = Query(default=24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> list[EventResponse]:
    """Return events within a time window of the specified event.

    Args:
        event_id: Reference event ID.
        window_hours: Time window in hours (before and after).
        db: Database session.
        current_user: Authenticated user.

    Returns:
        List of temporally proximate events.

    Raises:
        HTTPException: 404 if the reference event is not found.
    """
    from datetime import timedelta

    result = await db.execute(select(Event).where(Event.id == event_id))
    reference = result.scalar_one_or_none()
    if reference is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    window = timedelta(hours=window_hours)
    stmt = (
        select(Event)
        .where(
            and_(
                Event.id != event_id,
                Event.created_at >= reference.created_at - window,
                Event.created_at <= reference.created_at + window,
            )
        )
        .order_by(Event.created_at)
        .limit(50)
    )
    timeline_result = await db.execute(stmt)
    return [_event_to_schema(e) for e in timeline_result.scalars().all()]


# ---------------------------------------------------------------------------
# PUT /events/{event_id}
# ---------------------------------------------------------------------------


@router.put(
    "/{event_id}",
    response_model=EventResponse,
    summary="Update an event",
)
async def update_event(
    event_id: str,
    payload: EventUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> EventResponse:
    """Update fields on an existing event.

    Args:
        event_id: Event UUID.
        payload: Fields to update (unset fields are left unchanged).
        db: Database session.
        current_user: Authenticated user.

    Returns:
        Updated :class:`EventResponse`.

    Raises:
        HTTPException: 404 if not found.
    """
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(event, field, value)

    await db.flush()
    await db.refresh(event)
    return _event_to_schema(event)


# ---------------------------------------------------------------------------
# DELETE /events/{event_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an event",
)
async def delete_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
) -> None:
    """Permanently delete an event.

    Args:
        event_id: Event UUID.
        db: Database session.
        current_user: Authenticated user.

    Raises:
        HTTPException: 404 if not found.
    """
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    await db.delete(event)

    # Clean up vector store
    try:
        from app.db.pinecone_client import pinecone_client

        await pinecone_client.delete_vectors([event_id])
    except Exception as exc:
        logger.warning("Vector delete failed: %s", exc)
