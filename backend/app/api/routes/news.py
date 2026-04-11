"""
News API routes.

Endpoints:
  GET  /news/sources              – list configured RSS sources
  POST /news/ingest               – trigger a news-ingestion cycle
  GET  /news/latest               – fetch most recent articles
  GET  /news/search               – full-text keyword search
  GET  /news/events/extracted     – return extracted events
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.data_ingestion.event_extractor import EventExtractor
from app.data_ingestion.news_aggregator import NewsAggregator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/news", tags=["news"])


@lru_cache(maxsize=1)
def _aggregator() -> NewsAggregator:
    return NewsAggregator()


@lru_cache(maxsize=1)
def _extractor() -> EventExtractor:
    return EventExtractor()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/sources")
def get_news_sources() -> Dict[str, Any]:
    """Return the list of configured news sources."""
    sources = _aggregator().get_sources()
    return {"sources": sources, "total": len(sources)}


@router.post("/ingest")
def ingest_news(
    include_newsapi: bool = Query(False, description="Also fetch from NewsAPI (requires NEWSAPI_KEY)"),
) -> Dict[str, Any]:
    """Trigger a full news-ingestion cycle.

    Fetches articles from all RSS sources, then extracts events and populates
    the knowledge graph.
    """
    try:
        articles = _aggregator().aggregate(limit=100, hours=24)

        # Optionally ingest into knowledge graph
        try:
            from app.knowledge.knowledge_graph import get_knowledge_graph
            kg = get_knowledge_graph()
            kg_stats = kg.ingest_articles(articles)
        except Exception as exc:
            logger.warning("Knowledge graph ingestion failed: %s", exc)
            kg_stats = {}

        return {
            "status": "ok",
            "articles_ingested": len(articles),
            "knowledge_graph": kg_stats,
        }
    except Exception as exc:
        logger.error("Ingestion failed: %s", exc, exc_info=True)
        return {"status": "error", "message": str(exc)}


@router.get("/latest")
def get_latest_news(
    category: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=200),
    hours: int = Query(24, ge=1, le=720),
) -> Dict[str, Any]:
    """Return the most recent articles."""
    try:
        articles = _aggregator().aggregate(limit=limit, hours=hours)
        if category:
            articles = [a for a in articles if a.get("category") == category]
        return {"articles": articles, "total": len(articles)}
    except Exception as exc:
        logger.error("Failed to fetch latest news (limit=%s, hours=%s): %s", limit, hours, exc, exc_info=True)
        raise HTTPException(status_code=503, detail=f"News aggregation unavailable: {exc}") from exc


@router.get("/search")
def search_news(
    keyword: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    """Full-text keyword search across ingested articles."""
    articles = _aggregator().search(keyword=keyword, limit=limit)
    return {"articles": articles, "total": len(articles), "keyword": keyword}


@router.get("/events/extracted")
def get_extracted_events(
    event_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> Dict[str, Any]:
    """Return events extracted from recently ingested articles."""
    articles = _aggregator().aggregate(limit=100, hours=48)
    events = _extractor().extract_from_articles(articles)

    if event_type:
        events = [e for e in events if e.get("event_type") == event_type]
    if severity:
        events = [e for e in events if e.get("severity") == severity]

    return {"events": events[:limit], "total": len(events)}


# ---------------------------------------------------------------------------
# Scheduler status / trigger endpoints
# ---------------------------------------------------------------------------

@router.get("/scheduler/status")
def get_scheduler_status() -> Dict[str, Any]:
    """Return the current ingest scheduler status."""
    import app.services.ingest_scheduler as _sched

    return {
        "last_run_at": _sched.last_run_at.isoformat() if _sched.last_run_at else None,
        "next_run_at": _sched.next_run_at.isoformat() if _sched.next_run_at else None,
        "interval_minutes": _sched.interval_minutes,
        "cycle_count": _sched.cycle_count,
    }


@router.post("/scheduler/trigger")
async def trigger_ingest_cycle() -> Dict[str, Any]:
    """Immediately trigger one ingest cycle (fire-and-forget)."""
    import asyncio as _asyncio
    import app.services.ingest_scheduler as _sched

    _asyncio.create_task(_asyncio.to_thread(_sched._run_once))
    return {"status": "dispatched", "message": "Ingest cycle triggered in background"}
