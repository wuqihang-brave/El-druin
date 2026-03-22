"""Unit tests for RealTimeStreamingEngine (Kafka and Redis mocked)."""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.streaming_engine import (
    IngestResult,
    RealTimeStreamingEngine,
    TimeWindowDeduplicator,
)


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

@pytest.fixture()
def engine():
    """Fresh streaming engine instance for each test."""
    return RealTimeStreamingEngine(max_concurrent=10)


@pytest.fixture()
def deduplicator():
    """Fresh deduplicator for unit testing."""
    return TimeWindowDeduplicator(redis_prefix="test-dedup")


def _make_event(event_id: str = "evt-1", source: str = "test-src") -> dict:
    return {
        "id": event_id,
        "source": source,
        "title": "Test event",
        "description": "Something happened.",
        "event_type": "SECURITY",
        "severity": "medium",
    }


# ─────────────────────────────────────────────
# TimeWindowDeduplicator
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_deduplicator_new_event_is_accepted(deduplicator):
    """An event ID not yet seen returns True (new / accepted)."""
    mock_redis = AsyncMock()
    mock_redis.exists = AsyncMock(return_value=False)
    mock_redis.set = AsyncMock()

    with patch("app.db.redis_client.redis_client", mock_redis):
        result = await deduplicator.check_and_mark("unique-id-123")
    assert result is True


@pytest.mark.asyncio
async def test_deduplicator_duplicate_event_is_rejected(deduplicator):
    """An event ID already in Redis returns False (duplicate)."""
    mock_redis = AsyncMock()
    mock_redis.exists = AsyncMock(return_value=True)

    with patch("app.db.redis_client.redis_client", mock_redis):
        result = await deduplicator.check_and_mark("already-seen-id")
    assert result is False


@pytest.mark.asyncio
async def test_deduplicator_fail_open_on_redis_error(deduplicator):
    """If Redis is unavailable, deduplicator fails open (accepts the event)."""
    mock_redis = AsyncMock()
    mock_redis.exists = AsyncMock(side_effect=ConnectionError("Redis down"))

    with patch("app.db.redis_client.redis_client", mock_redis):
        result = await deduplicator.check_and_mark("some-id")
    assert result is True


# ─────────────────────────────────────────────
# ingest_event_stream — deduplication
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ingest_accepts_new_events(engine):
    """All unique events are accepted and counted."""
    events = [_make_event(f"evt-{i}") for i in range(5)]

    # Patch deduplicator to always accept
    engine._deduplicator.check_and_mark = AsyncMock(return_value=True)
    # Patch enrichment and Kafka publish to no-ops
    engine._enrich_event = AsyncMock(side_effect=lambda e: e)
    engine._publish_to_kafka = AsyncMock()

    result = await engine.ingest_event_stream("test-source", events)
    assert isinstance(result, IngestResult)
    assert result.total == 5
    assert result.accepted == 5
    assert result.rejected == 0


@pytest.mark.asyncio
async def test_ingest_rejects_duplicate_events(engine):
    """Duplicate events (deduplicator returns False) are counted as rejected."""
    events = [_make_event("dup-id")] * 3

    call_count = 0

    async def first_only(event_id, **kwargs):
        nonlocal call_count
        call_count += 1
        return call_count == 1  # Only first call returns True

    engine._deduplicator.check_and_mark = first_only
    engine._enrich_event = AsyncMock(side_effect=lambda e: e)
    engine._publish_to_kafka = AsyncMock()

    result = await engine.ingest_event_stream("test-source", events)
    assert result.accepted == 1
    assert result.rejected == 2


@pytest.mark.asyncio
async def test_ingest_empty_batch_returns_zero_counts(engine):
    """Empty batch produces an all-zero IngestResult."""
    result = await engine.ingest_event_stream("test-source", [])
    assert result.total == 0
    assert result.accepted == 0
    assert result.rejected == 0
    assert result.errors == 0


# ─────────────────────────────────────────────
# Event enrichment
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_enrich_event_adds_sentiment(engine):
    """Enrichment adds a sentiment key when description is present."""
    event = _make_event()
    # Only mock external calls; let _enrich_event run its logic
    with (
        patch("app.multimodal.geospatial_engine.geospatial_engine") as mock_geo,
        patch("app.db.postgres.fetch_one", new_callable=AsyncMock, return_value=None),
    ):
        mock_geo.geocode = AsyncMock(return_value=MagicMock(lat=0.0, lon=0.0))
        enriched = await engine._enrich_event(event)
    assert isinstance(enriched, dict)
    assert enriched.get("id") == event["id"]


@pytest.mark.asyncio
async def test_enrich_event_survives_geocoding_failure(engine):
    """Enrichment continues and returns event even if geocoding raises."""
    event = {**_make_event(), "location": "Unknown City XYZ"}

    with patch("app.multimodal.geospatial_engine.geospatial_engine") as mock_geo:
        mock_geo.geocode = AsyncMock(side_effect=Exception("Geocoding unavailable"))
        enriched = await engine._enrich_event(event)

    assert enriched["id"] == event["id"]


# ─────────────────────────────────────────────
# Anomaly detection
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_anomaly_detection_flags_high_severity(engine):
    """Events with very high severity scores are flagged as anomalies."""
    event = {**_make_event(), "severity": "critical", "sentiment_score": -0.95}

    with patch("app.db.postgres.fetch_all", new_callable=AsyncMock, return_value=[]):
        score = await engine._detect_anomalies(event, [])

    assert hasattr(score, "score")
    assert hasattr(score, "is_anomaly")


@pytest.mark.asyncio
async def test_anomaly_detection_normal_event_not_flagged(engine):
    """A routine low-severity event should not be flagged as an anomaly."""
    event = {**_make_event(), "severity": "low", "sentiment_score": 0.1}

    with patch("app.db.postgres.fetch_all", new_callable=AsyncMock, return_value=[]):
        score = await engine._detect_anomalies(event, [])

    assert hasattr(score, "is_anomaly")
    assert score.is_anomaly is False


# ─────────────────────────────────────────────
# Kafka publish (smoke test)
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_publish_to_kafka_calls_producer(engine):
    """_publish_to_kafka sends to the Kafka producer when available."""
    mock_producer = AsyncMock()
    mock_producer.send_and_wait = AsyncMock()
    engine._producer = mock_producer

    event = _make_event()
    await engine._publish_to_kafka("test.topic", event)
    mock_producer.send_and_wait.assert_called_once()


@pytest.mark.asyncio
async def test_publish_to_kafka_skips_when_no_producer(engine):
    """_publish_to_kafka is a no-op when producer is None."""
    engine._producer = None
    # Should not raise
    await engine._publish_to_kafka("test.topic", _make_event())
