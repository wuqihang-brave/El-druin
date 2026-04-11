"""
Ingest Scheduler – background asyncio task for periodic news ingestion
and Assessment auto-generation.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_INTERVAL_MINUTES = 30  # overridden by NEWS_INGEST_INTERVAL_MINUTES env var

# ---------------------------------------------------------------------------
# Module-level state – readable by the status endpoint
# ---------------------------------------------------------------------------
last_run_at: Optional[datetime] = None
next_run_at: Optional[datetime] = None
cycle_count: int = 0
interval_minutes: int = _DEFAULT_INTERVAL_MINUTES


async def run_ingest_cycle(interval: int) -> None:
    """Infinite loop: ingest news → generate assessments → sleep."""
    global interval_minutes, next_run_at  # noqa: PLW0603

    interval_minutes = interval
    logger.info(
        "Ingest scheduler started — cycle every %d min", interval_minutes
    )
    while True:
        try:
            _run_once()
        except Exception as exc:
            logger.error("Ingest cycle failed: %s", exc, exc_info=True)

        next_run_at = (
            datetime.now(timezone.utc) + timedelta(minutes=interval_minutes)
        ).replace(microsecond=0)
        await asyncio.sleep(interval_minutes * 60)


def _run_once() -> dict:
    """Execute one full ingest + assessment generation cycle."""
    global last_run_at, cycle_count  # noqa: PLW0603
    from app.data_ingestion.news_aggregator import NewsAggregator
    from app.services.assessment_generator import AssessmentGenerator

    t0 = datetime.now(timezone.utc)
    agg = NewsAggregator()
    articles = agg.aggregate(limit=50, hours=48)
    logger.info("Ingest cycle: fetched %d articles", len(articles))

    # Optionally ingest into KuzuDB knowledge graph
    try:
        from app.knowledge.knowledge_graph import get_knowledge_graph
        kg = get_knowledge_graph()
        kg.ingest_articles(articles, max_new=20, llm_batch_size=5)
        logger.info("Ingest cycle: KuzuDB updated")
    except Exception as exc:
        logger.warning("KuzuDB ingest skipped: %s", exc)

    # Generate assessments from news clusters
    result = AssessmentGenerator().generate_from_news(hours=48)
    elapsed = (datetime.now(timezone.utc) - t0).total_seconds()
    logger.info(
        "Ingest cycle complete in %.1fs — generated=%d updated=%d",
        elapsed,
        result.get("generated", 0),
        result.get("updated", 0),
    )

    last_run_at = datetime.now(timezone.utc).replace(microsecond=0)
    cycle_count += 1
    return result
