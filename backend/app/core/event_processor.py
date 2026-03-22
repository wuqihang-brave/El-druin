"""Event normalization, enrichment, and routing pipeline."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Entity:
    """A named entity extracted from text.

    Attributes:
        entity_id: Unique identifier.
        name: Entity surface form.
        entity_type: NER type (PERSON, ORG, GPE, etc.).
        start: Character start offset in source text.
        end: Character end offset in source text.
    """

    entity_id: str
    name: str
    entity_type: str
    start: int = 0
    end: int = 0


@dataclass
class NormalizedEvent:
    """Standardised event representation after normalization.

    Attributes:
        id: Unique event identifier.
        source: Originating source.
        title: Normalized title.
        description: Normalized description.
        event_type: Canonical event type.
        severity: Canonical severity level.
        location: Location dict or None.
        entities: Extracted entity list.
        tags: Normalized tag list.
        metadata: Extra metadata.
        raw: Original event dict preserved for audit.
    """

    id: str
    source: str
    title: str
    description: str
    event_type: str
    severity: str
    location: Optional[dict] = None
    entities: list[Entity] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class EnrichedEvent(NormalizedEvent):
    """Enriched event with embeddings and additional context.

    Attributes:
        embedding: Dense embedding vector.
        embedding_id: Vector store reference ID.
        sentiment_score: Sentiment polarity in [-1.0, 1.0].
        anomaly_score: Anomaly score in [0.0, 1.0].
    """

    embedding: list[float] = field(default_factory=list)
    embedding_id: Optional[str] = None
    sentiment_score: float = 0.0
    anomaly_score: float = 0.0


@dataclass
class ProcessedEvent:
    """Fully processed event ready for storage.

    Attributes:
        enriched: The enriched event data.
        queues: Downstream processing queues to route to.
    """

    enriched: EnrichedEvent
    queues: list[str] = field(default_factory=list)


@dataclass
class EventClassification:
    """Result of event classification.

    Attributes:
        event_type: Classified event type.
        severity: Classified severity.
        confidence: Classification confidence in [0.0, 1.0].
    """

    event_type: str
    severity: str
    confidence: float = 1.0


# ---------------------------------------------------------------------------
# Simple regex-based NER patterns
# ---------------------------------------------------------------------------

_NER_PATTERNS: list[tuple[str, str]] = [
    (r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", "PERSON"),
    (r"\b(?:Inc\.|Corp\.|Ltd\.|LLC|Company|Group|Association)\b", "ORG"),
    (
        r"\b(?:United States|United Kingdom|European Union|China|Russia|Germany|France|"
        r"India|Japan|Brazil|Canada|Australia|Israel|Iran|North Korea)\b",
        "GPE",
    ),
    (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "IP"),
    (
        r"\b(?:January|February|March|April|May|June|July|August|September|October|"
        r"November|December)\s+\d{1,2},?\s+\d{4}\b",
        "DATE",
    ),
]


# ---------------------------------------------------------------------------
# Processor
# ---------------------------------------------------------------------------


class EventProcessor:
    """Event normalization, enrichment, and routing.

    Transforms raw inbound event dicts into fully enriched, embedded, and
    routed :class:`ProcessedEvent` instances ready for persistence.

    Attributes:
        _severity_map: Mapping of severity synonyms to canonical values.
        _type_keywords: Mapping of keywords to canonical event types.
    """

    _severity_map: dict[str, str] = {
        "low": "low",
        "minor": "low",
        "info": "low",
        "medium": "medium",
        "moderate": "medium",
        "warning": "medium",
        "high": "high",
        "severe": "high",
        "major": "high",
        "critical": "critical",
        "emergency": "critical",
    }

    _type_keywords: dict[str, list[str]] = {
        "political": ["election", "government", "coup", "protest", "parliament"],
        "economic": ["market", "gdp", "inflation", "trade", "sanction", "tariff"],
        "military": ["attack", "strike", "troops", "missile", "conflict", "war"],
        "cyber": ["hack", "breach", "malware", "ransomware", "phishing", "exploit"],
        "natural_disaster": [
            "earthquake",
            "flood",
            "hurricane",
            "tsunami",
            "wildfire",
        ],
        "social": ["riot", "strike", "demonstration", "migration", "pandemic"],
    }

    # ------------------------------------------------------------------
    # Main pipeline
    # ------------------------------------------------------------------

    async def process(self, raw_event: dict) -> ProcessedEvent:
        """Run the full normalization → enrichment → routing pipeline.

        Args:
            raw_event: Inbound raw event dict.

        Returns:
            :class:`ProcessedEvent` ready for persistence.
        """
        normalized = await self.normalize(raw_event)
        enriched = await self.enrich(normalized)
        queues = await self.route(enriched)
        return ProcessedEvent(enriched=enriched, queues=queues)

    async def normalize(self, event: dict) -> NormalizedEvent:
        """Standardize raw event fields.

        Args:
            event: Raw event dict.

        Returns:
            :class:`NormalizedEvent` with canonical field names and values.
        """
        import uuid

        classification = await self.classify_event(event)

        return NormalizedEvent(
            id=event.get("id") or str(uuid.uuid4()),
            source=event.get("source", "unknown"),
            title=(event.get("title") or event.get("headline") or "").strip(),
            description=(
                event.get("description") or event.get("body") or ""
            ).strip(),
            event_type=event.get("event_type") or classification.event_type,
            severity=self._normalize_severity(
                event.get("severity") or classification.severity
            ),
            location=event.get("location"),
            tags=[t.lower().strip() for t in event.get("tags", []) if t],
            metadata=event.get("metadata", {}),
            raw=event,
        )

    async def enrich(self, event: NormalizedEvent) -> EnrichedEvent:
        """Add embeddings, entities, and sentiment to a normalized event.

        Args:
            event: Normalized event.

        Returns:
            :class:`EnrichedEvent` with additional context.
        """
        enriched = EnrichedEvent(**event.__dict__)

        text = f"{event.title} {event.description}"
        entities = await self.extract_entities(text)
        enriched.entities = entities

        try:
            from app.core.embeddings import embedding_engine

            enriched.embedding = await embedding_engine.encode_event(
                {
                    "title": event.title,
                    "description": event.description,
                    "tags": event.tags,
                }
            )
        except Exception as exc:
            logger.warning("Embedding failed: %s", exc)

        return enriched

    async def route(self, event: EnrichedEvent) -> list[str]:
        """Determine which processing queues an event should be sent to.

        Args:
            event: Enriched event.

        Returns:
            List of queue name strings.
        """
        queues: list[str] = ["events.store"]

        if event.severity in ("high", "critical"):
            queues.append("alerts.high_priority")

        if event.event_type in ("military", "cyber"):
            queues.append("predictions.immediate")

        if event.anomaly_score >= 0.75:
            queues.append("anomalies.review")

        return queues

    # ------------------------------------------------------------------
    # Entity extraction
    # ------------------------------------------------------------------

    async def extract_entities(self, text: str) -> list[Entity]:
        """Extract named entities from text using regex patterns.

        Falls back to spacy if installed.

        Args:
            text: Input text.

        Returns:
            List of :class:`Entity` instances.
        """
        # Try spacy first
        try:
            import spacy  # type: ignore

            nlp = spacy.load("en_core_web_sm")
            doc = nlp(text)
            return [
                Entity(
                    entity_id=str(hash(ent.text)),
                    name=ent.text,
                    entity_type=ent.label_,
                    start=ent.start_char,
                    end=ent.end_char,
                )
                for ent in doc.ents
            ]
        except Exception:
            pass

        # Fallback regex NER
        entities: list[Entity] = []
        seen: set[str] = set()
        for pattern, ent_type in _NER_PATTERNS:
            for match in re.finditer(pattern, text):
                name = match.group()
                if name not in seen:
                    seen.add(name)
                    entities.append(
                        Entity(
                            entity_id=str(hash(name)),
                            name=name,
                            entity_type=ent_type,
                            start=match.start(),
                            end=match.end(),
                        )
                    )
        return entities

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    async def classify_event(self, event: dict) -> EventClassification:
        """Classify an event's type and severity from its content.

        Args:
            event: Raw event dict.

        Returns:
            :class:`EventClassification` result.
        """
        text = (
            f"{event.get('title', '')} {event.get('description', '')}".lower()
        )
        detected_type = "general"
        for etype, keywords in self._type_keywords.items():
            if any(kw in text for kw in keywords):
                detected_type = etype
                break

        raw_severity = event.get("severity", "medium")
        severity = self._normalize_severity(raw_severity)
        return EventClassification(
            event_type=detected_type, severity=severity, confidence=0.85
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _normalize_severity(self, raw: str) -> str:
        """Map a raw severity string to a canonical value.

        Args:
            raw: Raw severity string.

        Returns:
            One of: ``low``, ``medium``, ``high``, ``critical``.
        """
        return self._severity_map.get((raw or "medium").lower(), "medium")


# Module-level singleton
event_processor = EventProcessor()
