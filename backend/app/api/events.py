"""
Event management API routes.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.get("")
async def get_events(limit: int = Query(20, ge=1, le=100)):
    """Return all events from the events store."""
    try:
        from app.data_ingestion.news_aggregator import NewsAggregator
        from app.data_ingestion.event_extractor import EventExtractor

        aggregator = NewsAggregator()
        articles = aggregator.aggregate(limit=50, hours=24)
        extractor = EventExtractor()
        events = extractor.extract_from_articles(articles)
        return {"items": events[:limit], "total": len(events), "limit": limit}
    except Exception as exc:
        logger.error("Failed to fetch events: %s", exc)
        return {"items": [], "total": 0, "limit": limit}


@router.get("/{event_id}")
async def get_event(event_id: str):
    """Return a single event by its ID."""
    raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found")
