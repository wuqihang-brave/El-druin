"""
News aggregation and management API routes.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/news", tags=["news"])


@router.get("/sources")
async def get_news_sources():
    """Return the list of configured news sources."""
    return {
        "sources": [
            {
                "name": "BBC News",
                "category": "general",
                "priority": 1,
                "url": "http://feeds.bbc.co.uk/news/rss.xml",
            },
            {
                "name": "Reuters",
                "category": "business",
                "priority": 1,
                "url": "https://feeds.reuters.com/reuters/topNews",
            },
            {
                "name": "Al Jazeera",
                "category": "politics",
                "priority": 2,
                "url": "https://www.aljazeera.com/xml/rss/all.xml",
            },
            {
                "name": "TechCrunch",
                "category": "technology",
                "priority": 2,
                "url": "https://techcrunch.com/feed/",
            },
        ]
    }


@router.post("/ingest")
async def ingest_news(include_newsapi: bool = False):
    """Trigger a news ingestion cycle."""
    try:
        from app.data_ingestion.news_aggregator import NewsAggregator

        aggregator = NewsAggregator()
        articles = aggregator.aggregate(limit=50, hours=24)
        return {
            "message": "News ingestion completed",
            "status": "success",
            "articles_collected": len(articles),
            "include_newsapi": include_newsapi,
        }
    except Exception as exc:
        logger.error("News ingestion failed: %s", exc)
        return {
            "message": "News ingestion failed",
            "status": "error",
            "error": str(exc),
            "include_newsapi": include_newsapi,
        }


@router.get("/latest")
async def get_latest_news(
    limit: int = Query(20, ge=1, le=100),
    hours: int = Query(24, ge=1),
    category: Optional[str] = None,
):
    """Return the most recent ingested articles."""
    try:
        from app.data_ingestion.news_aggregator import NewsAggregator

        aggregator = NewsAggregator()
        articles = aggregator.aggregate(limit=limit, hours=hours)
        if category:
            articles = [a for a in articles if a.get("category") == category]
        return {"articles": articles, "total": len(articles), "limit": limit, "hours": hours}
    except Exception as exc:
        logger.error("Failed to fetch latest news: %s", exc)
        return {"articles": [], "total": 0, "limit": limit, "hours": hours, "category": category}


@router.get("/search")
async def search_news(
    keyword: str,
    limit: int = Query(20, ge=1, le=100),
):
    """Full-text keyword search across ingested articles."""
    try:
        from app.data_ingestion.news_aggregator import NewsAggregator

        aggregator = NewsAggregator()
        all_articles = aggregator.aggregate(limit=200, hours=168)
        kw_lower = keyword.lower()
        matched = [
            a
            for a in all_articles
            if kw_lower in (a.get("title") or "").lower()
            or kw_lower in (a.get("description") or "").lower()
        ]
        return {"articles": matched[:limit], "keyword": keyword, "total": len(matched), "limit": limit}
    except Exception as exc:
        logger.error("News search failed: %s", exc)
        return {"articles": [], "keyword": keyword, "total": 0, "limit": limit}


@router.get("/events/extracted")
async def get_extracted_events(
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
):
    """Return events extracted from ingested articles."""
    try:
        from app.data_ingestion.news_aggregator import NewsAggregator
        from app.data_ingestion.event_extractor import EventExtractor

        aggregator = NewsAggregator()
        articles = aggregator.aggregate(limit=50, hours=24)

        extractor = EventExtractor()
        events = extractor.extract_from_articles(articles)

        if event_type:
            events = [e for e in events if e.get("event_type") == event_type]
        if severity:
            events = [e for e in events if e.get("severity") == severity]

        return {"events": events[:limit], "total": len(events), "event_type": event_type, "severity": severity}
    except Exception as exc:
        logger.error("Failed to fetch extracted events: %s", exc)
        return {"events": [], "total": 0, "event_type": event_type, "severity": severity}
