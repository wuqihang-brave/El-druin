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


async def run_ingest_cycle(interval: int, initial_delay_seconds: int = 60) -> None:
    """Infinite loop: ingest news → generate assessments → sleep.

    Waits *initial_delay_seconds* before the first cycle so that the
    application has time to complete startup and pass Railway's health check.
    """
    global interval_minutes, next_run_at  # noqa: PLW0603

    interval_minutes = interval
    logger.info(
        "Ingest scheduler started — first cycle in %ds, then every %d min",
        initial_delay_seconds, interval_minutes,
    )

    # ── Initial delay: let uvicorn finish startup + Railway health check ──
    next_run_at = (
        datetime.now(timezone.utc) + timedelta(seconds=initial_delay_seconds)
    ).replace(microsecond=0)
    await asyncio.sleep(initial_delay_seconds)

    while True:
        try:
            await asyncio.to_thread(_run_once)
        except Exception as exc:
            logger.error("Ingest cycle failed: %s", exc, exc_info=True)

        next_run_at = (
            datetime.now(timezone.utc) + timedelta(minutes=interval_minutes)
        ).replace(microsecond=0)
        await asyncio.sleep(interval_minutes * 60)


async def run_once_async() -> dict:
    """Public async wrapper for _run_once, safe to use with create_task."""
    return await asyncio.to_thread(_run_once)


def _run_once() -> dict:
    """Execute one full ingest + assessment generation cycle."""
    global last_run_at, cycle_count  # noqa: PLW0603
    from app.data_ingestion.news_aggregator import NewsAggregator
    from app.services.assessment_generator import AssessmentGenerator
    from app.data_ingestion.event_extractor import reset_circuit as reset_event_circuit
    from app.knowledge.entity_extractor import reset_circuit as reset_entity_circuit

    # Reset LLM circuit-breakers at the start of each cycle so transient 403s
    # from a previous cycle do not permanently suppress LLM extraction.
    reset_event_circuit()
    reset_entity_circuit()

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

    # Generate assessments from news clusters, reusing the articles already
    # fetched above so AssessmentGenerator does not issue a second large
    # NewsAggregator request that would trigger another 200-article LLM burst.
    result = AssessmentGenerator().generate_from_news(
        hours=48,
        articles=articles,   # reuse already-fetched articles; skip second aggregation
        max_articles=30,     # limit EventExtractor to at most 30 articles
    )
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
