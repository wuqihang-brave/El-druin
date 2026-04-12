"""
Assessment Generator
====================

Bridges the existing news pipeline with the Assessment store.

Reads extracted events from ``NewsAggregator`` + ``EventExtractor``,
clusters them by region/domain similarity, and synthesises new
``Assessment`` records deterministically (no LLM required).

Algorithm
---------
1. Fetch recent articles via NewsAggregator().aggregate(limit=50, hours=N)
   (or accept a pre-fetched list to avoid a redundant HTTP round-trip).
2. Extract events via EventExtractor().extract_from_articles(articles).
3. Cluster events that share >=2 domain/region keywords.
4. For each cluster with >= min_events_per_cluster events:
   - Derive title from most common entity mentions + domain.
   - Set domain_tags = top-3 domains in the cluster.
   - Set region_tags = top-3 regions in the cluster.
   - Generate stable assessment_id = "ae-" + sha256(cluster_key)[:8].
   - Build analyst_notes summary string.
5. Upsert each generated assessment (idempotent on re-runs).
6. Return summary dict {"generated": N, "updated": M, "assessment_ids": [...]}.
"""

from __future__ import annotations

import hashlib
import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional

from app.schemas.assessment import Assessment, AssessmentStatus, AssessmentType

logger = logging.getLogger(__name__)

# Domains and regions recognised for clustering
_KNOWN_DOMAINS = frozenset(
    {
        "military",
        "energy",
        "sanctions",
        "finance",
        "trade",
        "political",
        "diplomacy",
        "cyber",
        "humanitarian",
        "economic",
        "technology",
        "environment",
        "health",
        "social",
    }
)

_KNOWN_REGIONS = frozenset(
    {
        "Eastern Europe",
        "Black Sea",
        "Middle East",
        "Asia Pacific",
        "South Asia",
        "Southeast Asia",
        "Africa",
        "Latin America",
        "North America",
        "Western Europe",
        "Central Asia",
        "Arctic",
        "Mediterranean",
        "Indo-Pacific",
        "Sahel",
    }
)

# Simple keyword→region mapping for lightweight region detection
_REGION_KEYWORDS: dict[str, str] = {
    "ukraine": "Eastern Europe",
    "russia": "Eastern Europe",
    "europe": "Western Europe",
    "eu": "Western Europe",
    "nato": "Western Europe",
    "black sea": "Black Sea",
    "iran": "Middle East",
    "iraq": "Middle East",
    "saudi": "Middle East",
    "israel": "Middle East",
    "china": "Asia Pacific",
    "taiwan": "Asia Pacific",
    "japan": "Asia Pacific",
    "korea": "Asia Pacific",
    "india": "South Asia",
    "pakistan": "South Asia",
    "myanmar": "Southeast Asia",
    "africa": "Africa",
    "sahel": "Sahel",
    "mali": "Sahel",
    "nigeria": "Africa",
    "brazil": "Latin America",
    "venezuela": "Latin America",
    "us": "North America",
    "usa": "North America",
    "america": "North America",
    "canada": "North America",
    "arctic": "Arctic",
    "mediterranean": "Mediterranean",
    "pacific": "Indo-Pacific",
}


def _extract_domains_from_event(event: dict[str, Any]) -> list[str]:
    """Return domain tags from an event dict, falling back to keyword scan."""
    domains = event.get("domains", [])
    if domains:
        return [d for d in domains if d in _KNOWN_DOMAINS]

    # Keyword scan on text
    text = (event.get("text", "") + " " + event.get("title", "")).lower()
    return [d for d in _KNOWN_DOMAINS if d in text]


def _extract_regions_from_event(event: dict[str, Any]) -> list[str]:
    """Return region tags from an event dict via keyword mapping."""
    text = (event.get("text", "") + " " + event.get("title", "")).lower()
    found: set[str] = set()
    for kw, region in _REGION_KEYWORDS.items():
        if kw in text:
            found.add(region)
    return list(found)


def _cluster_events(
    events: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    """
    Cluster events by (domain_tags, region_tags) similarity.

    Two events belong to the same cluster if they share >= 2 domain or
    region keywords. Uses a greedy union-find approach.
    """
    n = len(events)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        parent[find(x)] = find(y)

    tags: list[set[str]] = []
    for ev in events:
        domains = set(_extract_domains_from_event(ev))
        regions = set(_extract_regions_from_event(ev))
        tags.append(domains | regions)

    for i in range(n):
        for j in range(i + 1, n):
            if len(tags[i] & tags[j]) >= 2:
                union(i, j)

    clusters: dict[int, list[dict[str, Any]]] = {}
    for i, ev in enumerate(events):
        root = find(i)
        clusters.setdefault(root, []).append(ev)
    return list(clusters.values())


ENTITY_STOPWORDS = frozenset(
    {"ORG", "GPE", "PERSON", "MISC", "LOC", "FAC", "UN", "EU", "US", "UK"}
)


def _derive_title(cluster: list[dict[str, Any]], top_domains: list[str]) -> str:
    """Derive a human-readable title from entity mentions and domains."""
    entity_counter: Counter[str] = Counter()
    for ev in cluster:
        for ent in ev.get("entities", []):
            if isinstance(ent, dict):
                name = ent.get("name", "").strip()
            elif isinstance(ent, str):
                name = ent.strip()
            else:
                continue
            # Filter out generic NER type labels and very short tokens
            if name and name not in ENTITY_STOPWORDS and len(name) > 2:
                entity_counter[name] += 1

    top_entities = [e for e, _ in entity_counter.most_common(2)]
    domain_label = " / ".join(top_domains[:2]).title() if top_domains else "Multi-Domain"

    if top_entities:
        return f"{top_entities[0]} \u2013 {domain_label} Watch"
    if top_domains:
        return f"{domain_label} Structural Watch"
    return "Auto-Generated Structural Assessment"


def _stable_id(cluster_key: str) -> str:
    """Generate a stable ae-XXXXXXXX ID from a cluster key string."""
    digest = hashlib.sha256(cluster_key.encode()).hexdigest()
    return "ae-" + digest[:8]


class AssessmentGenerator:
    """Generates Assessment records from the news event pipeline."""

    def generate_from_news(
        self,
        hours: int = 48,
        min_events_per_cluster: int = 3,
        max_assessments: int = 10,
        articles: Optional[list[dict[str, Any]]] = None,
        max_articles: int = 30,
    ) -> dict[str, Any]:
        """
        Generate or update assessments from recent news events.

        Args:
            hours: Look-back window in hours for news articles.
            min_events_per_cluster: Minimum events needed to form a cluster.
            max_assessments: Cap on newly generated assessments per run.
            articles: Optional pre-fetched article list.  When provided the
                NewsAggregator fetch is skipped (avoids a redundant round-trip
                and a second large article batch hitting the LLM).
            max_articles: Maximum articles passed to EventExtractor for LLM
                extraction.  Caps Groq token consumption per cycle.

        Returns:
            Summary dict with keys ``generated``, ``updated``, ``assessment_ids``.
        """
        from app.core.assessment_store import assessment_store  # noqa: PLC0415

        # --- Step 1: Fetch articles (skip if caller provides them) ---
        if articles is None:
            articles = []
            try:
                from app.data_ingestion.news_aggregator import NewsAggregator  # noqa: PLC0415

                articles = NewsAggregator().aggregate(limit=50, hours=hours)
                logger.info("AssessmentGenerator: fetched %d articles", len(articles))
            except Exception as exc:
                logger.warning("AssessmentGenerator: news aggregation failed: %s", exc)
        else:
            logger.info(
                "AssessmentGenerator: using %d pre-fetched articles", len(articles)
            )

        # --- Step 2: Extract events ---
        events: list[dict[str, Any]] = []
        try:
            from app.data_ingestion.event_extractor import EventExtractor  # noqa: PLC0415

            events = EventExtractor().extract_from_articles(articles, max_articles=max_articles)
            logger.info("AssessmentGenerator: extracted %d events", len(events))
        except Exception as exc:
            logger.warning("AssessmentGenerator: event extraction failed: %s", exc)

        if not events:
            return {"generated": 0, "updated": 0, "assessment_ids": []}

        # --- Step 3: Cluster events ---
        clusters = _cluster_events(events)
        qualified = [c for c in clusters if len(c) >= min_events_per_cluster]
        logger.info(
            "AssessmentGenerator: %d clusters, %d qualify (min_events=%d)",
            len(clusters),
            len(qualified),
            min_events_per_cluster,
        )

        # --- Step 4+5: Generate and upsert assessments ---
        generated = 0
        updated = 0
        assessment_ids: list[str] = []

        for cluster in qualified[:max_assessments]:
            domain_counter: Counter[str] = Counter()
            region_counter: Counter[str] = Counter()

            for ev in cluster:
                for d in _extract_domains_from_event(ev):
                    domain_counter[d] += 1
                for r in _extract_regions_from_event(ev):
                    region_counter[r] += 1

            top_domains = [d for d, _ in domain_counter.most_common(3)]
            top_regions = [r for r, _ in region_counter.most_common(3)]
            cluster_key = "|".join(sorted(top_domains)) + ";" + "|".join(sorted(top_regions))
            assessment_id = _stable_id(cluster_key)
            title = _derive_title(cluster, top_domains)

            domains_str = ", ".join(top_domains) if top_domains else "unknown"
            regions_str = ", ".join(top_regions) if top_regions else "unknown"
            analyst_notes = (
                f"Auto-generated from {len(cluster)} events in "
                f"domains: {domains_str} / regions: {regions_str}"
            )

            now = datetime.now(tz=timezone.utc)
            existing = assessment_store.get_assessment(assessment_id)

            assessment = Assessment(
                assessment_id=assessment_id,
                title=title,
                assessment_type=AssessmentType.event_driven,
                status=AssessmentStatus.active,
                region_tags=top_regions,
                domain_tags=top_domains,
                created_at=existing.created_at if existing else now,
                updated_at=now,
                last_regime=None,
                last_confidence=None,
                alert_count=len(cluster),
                analyst_notes=analyst_notes,
            )

            assessment_store.upsert_assessment(assessment)
            assessment_ids.append(assessment_id)

            if existing is None:
                generated += 1
            else:
                updated += 1

        logger.info(
            "AssessmentGenerator: generated=%d updated=%d", generated, updated
        )
        return {
            "generated": generated,
            "updated": updated,
            "assessment_ids": assessment_ids,
        }
