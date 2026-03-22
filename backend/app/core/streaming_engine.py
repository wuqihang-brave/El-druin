"""Kafka-based real-time streaming engine with deduplication and enrichment."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

try:
    from aiokafka import AIOKafkaConsumer, AIOKafkaProducer  # type: ignore
    _KAFKA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _KAFKA_AVAILABLE = False
    logger.warning("aiokafka not installed; Kafka features disabled")

from app.config import settings


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class IngestResult:
    """Summary of a batch ingest operation.

    Attributes:
        total: Total events submitted.
        accepted: Events that passed deduplication.
        rejected: Events rejected as duplicates.
        enriched: Events that were successfully enriched.
        errors: Number of processing errors encountered.
    """

    total: int = 0
    accepted: int = 0
    rejected: int = 0
    enriched: int = 0
    errors: int = 0


@dataclass
class AnomalyScore:
    """Anomaly scoring result for a single event.

    Attributes:
        score: Anomaly score in [0.0, 1.0].
        is_anomaly: Whether the score exceeds the threshold.
        reason: Human-readable reason for the score.
    """

    score: float = 0.0
    is_anomaly: bool = False
    reason: str = ""


# ---------------------------------------------------------------------------
# Deduplicator
# ---------------------------------------------------------------------------


class TimeWindowDeduplicator:
    """Redis-backed deduplication within a configurable time window.

    Args:
        redis_prefix: Key prefix used for deduplication flags.
    """

    def __init__(self, redis_prefix: str = "dedup") -> None:
        self._prefix = redis_prefix

    async def check_and_mark(
        self,
        event_id: str,
        window_seconds: int = 60,
    ) -> bool:
        """Check if an event ID is new; mark it as seen if so.

        Args:
            event_id: Unique event identifier.
            window_seconds: Deduplication window in seconds.

        Returns:
            True if the event is new (not yet seen), False if duplicate.
        """
        try:
            from app.db.redis_client import redis_client

            key = f"{self._prefix}:{event_id}"
            if await redis_client.exists(key):
                return False
            await redis_client.set(key, "1", ttl=window_seconds)
            return True
        except Exception as exc:
            # Fail-open: if Redis is unavailable, accept the event
            logger.warning("Deduplication check failed: %s", exc)
            return True


# ---------------------------------------------------------------------------
# Streaming engine
# ---------------------------------------------------------------------------


class RealTimeStreamingEngine:
    """Kafka-based real-time event ingestion with enrichment.

    Events are consumed from a Kafka topic, deduplicated, enriched with
    geo-coding, entity linking, and sentiment analysis, and then
    published to a downstream enriched-events topic.

    Args:
        max_concurrent: Maximum number of events processed concurrently
            (controls back-pressure via a semaphore).

    Attributes:
        _consumer: AIOKafka consumer instance.
        _producer: AIOKafka producer instance.
        _consumer_task: Background asyncio task running the consumer loop.
        _deduplicator: Time-window deduplicator.
        _semaphore: Concurrency limiter.
    """

    ANOMALY_THRESHOLD = 0.75

    def __init__(self, max_concurrent: int = 50) -> None:
        self._consumer: Optional[Any] = None
        self._producer: Optional[Any] = None
        self._consumer_task: Optional[asyncio.Task] = None
        self._deduplicator = TimeWindowDeduplicator()
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start_consumer(self) -> None:
        """Start the Kafka consumer loop as a background task."""
        if not _KAFKA_AVAILABLE:
            logger.warning("Kafka not available; consumer not started")
            return
        self._producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode(),
        )
        await self._producer.start()

        self._consumer = AIOKafkaConsumer(
            settings.KAFKA_TOPIC_EVENTS,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=settings.KAFKA_CONSUMER_GROUP,
            auto_offset_reset="earliest",
            value_deserializer=lambda v: json.loads(v.decode()),
        )
        await self._consumer.start()
        self._running = True
        self._consumer_task = asyncio.create_task(self._consume_loop())
        logger.info("Kafka consumer started")

    async def stop_consumer(self) -> None:
        """Stop the Kafka consumer loop and release resources."""
        self._running = False
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
        if self._consumer:
            await self._consumer.stop()
        if self._producer:
            await self._producer.stop()
        logger.info("Kafka consumer stopped")

    # ------------------------------------------------------------------
    # Consumer loop
    # ------------------------------------------------------------------

    async def _consume_loop(self) -> None:
        """Internal loop that reads messages from Kafka and processes them."""
        while self._running and self._consumer:
            try:
                async for message in self._consumer:
                    if not self._running:
                        break
                    event = message.value
                    asyncio.create_task(self._handle_event(event))
            except Exception as exc:
                logger.error("Consumer loop error: %s", exc)
                await asyncio.sleep(1)

    async def _handle_event(self, event: dict) -> None:
        """Process a single event from the consumer loop."""
        async with self._semaphore:
            event_id = event.get("id", "")
            is_new = await self._deduplicator.check_and_mark(event_id)
            if not is_new:
                return
            enriched = await self._enrich_event(event)
            await self._publish_to_kafka(
                settings.KAFKA_TOPIC_PREDICTIONS, enriched
            )

    # ------------------------------------------------------------------
    # Public ingestion API
    # ------------------------------------------------------------------

    async def ingest_event_stream(
        self,
        source: str,
        event_batch: list[dict],
    ) -> IngestResult:
        """Ingest a batch of raw events from an external source.

        Args:
            source: Identifying name of the data source.
            event_batch: List of raw event dicts.

        Returns:
            :class:`IngestResult` summarising the operation.
        """
        result = IngestResult(total=len(event_batch))
        tasks = []
        for event in event_batch:
            event.setdefault("source", source)
            tasks.append(self._process_single(event, result))
        await asyncio.gather(*tasks, return_exceptions=True)
        return result

    async def _process_single(
        self, event: dict, result: IngestResult
    ) -> None:
        """Deduplicate, enrich, and publish a single event."""
        try:
            event_id = event.get("id", "")
            is_new = await self._deduplicator.check_and_mark(event_id)
            if not is_new:
                result.rejected += 1
                return
            result.accepted += 1
            enriched = await self._enrich_event(event)
            result.enriched += 1
            await self._publish_to_kafka(settings.KAFKA_TOPIC_EVENTS, enriched)
        except Exception as exc:
            logger.error("Error processing event: %s", exc)
            result.errors += 1

    # ------------------------------------------------------------------
    # Enrichment
    # ------------------------------------------------------------------

    async def _enrich_event(self, event: dict) -> dict:
        """Enrich an event with geo-coding, entity linking, and sentiment.

        Args:
            event: Raw event dict.

        Returns:
            Enriched event dict.
        """
        enriched = dict(event)

        # Geo-coding
        if location := event.get("location"):
            if isinstance(location, str):
                try:
                    from app.multimodal.geospatial_engine import geospatial_engine

                    coords = await geospatial_engine.geocode(location)
                    enriched["location"] = {
                        "address": location,
                        "lat": coords.lat,
                        "lon": coords.lon,
                    }
                except Exception:
                    enriched["location"] = {"address": location}

        # Entity extraction
        text = f"{event.get('title', '')} {event.get('description', '')}"
        if text.strip():
            try:
                from app.core.event_processor import event_processor

                entities = await event_processor.extract_entities(text)
                enriched.setdefault("entities", [])
                enriched["entities"].extend(
                    [asdict(e) if hasattr(e, "__dataclass_fields__") else vars(e) for e in entities]
                )
            except Exception:
                pass

        # Anomaly detection
        recent: list[dict] = []
        try:
            from app.db.redis_client import redis_client

            raw = await redis_client.lrange("recent_events", 0, 50)
            recent = [r for r in raw if isinstance(r, dict)]
        except Exception:
            pass

        anomaly = await self._detect_anomalies(event, recent)
        if anomaly.is_anomaly:
            enriched["anomaly"] = {
                "score": anomaly.score,
                "reason": anomaly.reason,
            }

        # Store in recent-events rolling window
        try:
            from app.db.redis_client import redis_client

            await redis_client.lpush("recent_events", event)
            await redis_client.expire("recent_events", 3600)
        except Exception:
            pass

        return enriched

    async def _detect_anomalies(
        self, event: dict, recent_events: list[dict]
    ) -> AnomalyScore:
        """Detect anomalies relative to recent events.

        A simple heuristic: if severity is "critical" and there are few
        recent events of the same type, score is elevated.

        Args:
            event: Candidate event.
            recent_events: Recent events for context.

        Returns:
            :class:`AnomalyScore`.
        """
        severity = event.get("severity", "medium")
        event_type = event.get("event_type", "")

        same_type_count = sum(
            1 for e in recent_events if e.get("event_type") == event_type
        )

        score = 0.0
        reason = "normal"

        if severity == "critical":
            score += 0.5
            reason = "critical severity"

        if same_type_count == 0:
            score += 0.3
            reason += "; novel event type"

        if score >= self.ANOMALY_THRESHOLD:
            return AnomalyScore(score=score, is_anomaly=True, reason=reason)
        return AnomalyScore(score=score, is_anomaly=False, reason=reason)

    # ------------------------------------------------------------------
    # Kafka publishing
    # ------------------------------------------------------------------

    async def _publish_to_kafka(self, topic: str, event: dict) -> None:
        """Publish a single event dict to a Kafka topic.

        Args:
            topic: Target Kafka topic name.
            event: Event dict to publish.
        """
        if not self._producer:
            return
        try:
            await self._producer.send_and_wait(topic, event)
        except Exception as exc:
            logger.error("Kafka publish error (topic=%s): %s", topic, exc)


# Module-level singleton
streaming_engine = RealTimeStreamingEngine()
