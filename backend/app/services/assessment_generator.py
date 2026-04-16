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
3. Cluster events that share >=3 domain/region keywords.
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

from app.schemas.assessment import Assessment, AssessmentStatus, AssessmentType, AssessmentUpdate

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
    # ── Eastern Europe ────────────────────────────────────────────
    "poland": "Eastern Europe",
    "belarus": "Eastern Europe",
    "moldova": "Eastern Europe",
    "romania": "Eastern Europe",
    "hungary": "Eastern Europe",
    "slovakia": "Eastern Europe",
    "czech": "Eastern Europe",
    "bulgaria": "Eastern Europe",
    "serbia": "Eastern Europe",
    "croatia": "Eastern Europe",
    "estonia": "Eastern Europe",
    "latvia": "Eastern Europe",
    "lithuania": "Eastern Europe",
    "kyiv": "Eastern Europe",
    "moscow": "Eastern Europe",
    "donbas": "Eastern Europe",
    "crimea": "Eastern Europe",
    "zaporizhzhia": "Eastern Europe",
    "kharkiv": "Eastern Europe",
    # ── Western Europe ────────────────────────────────────────────
    "germany": "Western Europe",
    "france": "Western Europe",
    "uk": "Western Europe",
    "united kingdom": "Western Europe",
    "britain": "Western Europe",
    "italy": "Western Europe",
    "spain": "Western Europe",
    "portugal": "Western Europe",
    "netherlands": "Western Europe",
    "belgium": "Western Europe",
    "austria": "Western Europe",
    "switzerland": "Western Europe",
    "sweden": "Western Europe",
    "norway": "Western Europe",
    "denmark": "Western Europe",
    "finland": "Western Europe",
    "ireland": "Western Europe",
    "greece": "Western Europe",
    "berlin": "Western Europe",
    "paris": "Western Europe",
    "london": "Western Europe",
    "brussels": "Western Europe",
    # ── Black Sea ─────────────────────────────────────────────────
    "turkey": "Black Sea",
    "georgia": "Black Sea",
    "azov": "Black Sea",
    "bosphorus": "Black Sea",
    "kerch": "Black Sea",
    "ankara": "Black Sea",
    "istanbul": "Black Sea",
    # ── Middle East ───────────────────────────────────────────────
    "syria": "Middle East",
    "lebanon": "Middle East",
    "jordan": "Middle East",
    "yemen": "Middle East",
    "oman": "Middle East",
    "uae": "Middle East",
    "qatar": "Middle East",
    "kuwait": "Middle East",
    "bahrain": "Middle East",
    "egypt": "Middle East",
    "gaza": "Middle East",
    "west bank": "Middle East",
    "tel aviv": "Middle East",
    "tehran": "Middle East",
    "riyadh": "Middle East",
    "gulf": "Middle East",
    "persian gulf": "Middle East",
    "red sea": "Middle East",
    "hormuz": "Middle East",
    "houthi": "Middle East",
    "hezbollah": "Middle East",
    "hamas": "Middle East",
    # ── Asia Pacific ──────────────────────────────────────────────
    "south china sea": "Asia Pacific",
    "east china sea": "Asia Pacific",
    "philippines": "Asia Pacific",
    "vietnam": "Asia Pacific",
    "indonesia": "Asia Pacific",
    "malaysia": "Asia Pacific",
    "thailand": "Asia Pacific",
    "singapore": "Asia Pacific",
    "australia": "Asia Pacific",
    "new zealand": "Asia Pacific",
    "beijing": "Asia Pacific",
    "shanghai": "Asia Pacific",
    "hong kong": "Asia Pacific",
    "seoul": "Asia Pacific",
    "tokyo": "Asia Pacific",
    "pyongyang": "Asia Pacific",
    "taipei": "Asia Pacific",
    "north korea": "Asia Pacific",
    "south korea": "Asia Pacific",
    "dprk": "Asia Pacific",
    "pla": "Asia Pacific",
    "prc": "Asia Pacific",
    # ── South Asia ────────────────────────────────────────────────
    "bangladesh": "South Asia",
    "sri lanka": "South Asia",
    "nepal": "South Asia",
    "afghanistan": "South Asia",
    "kashmir": "South Asia",
    "new delhi": "South Asia",
    "islamabad": "South Asia",
    "kabul": "South Asia",
    # ── Southeast Asia ────────────────────────────────────────────
    "cambodia": "Southeast Asia",
    "laos": "Southeast Asia",
    "brunei": "Southeast Asia",
    "timor": "Southeast Asia",
    "asean": "Southeast Asia",
    "mekong": "Southeast Asia",
    "naypyidaw": "Southeast Asia",
    "yangon": "Southeast Asia",
    # ── Africa ───────────────────────────────────────────────────
    "ethiopia": "Africa",
    "kenya": "Africa",
    "tanzania": "Africa",
    "somalia": "Africa",
    "sudan": "Africa",
    "south sudan": "Africa",
    "libya": "Africa",
    "morocco": "Africa",
    "algeria": "Africa",
    "tunisia": "Africa",
    "ghana": "Africa",
    "senegal": "Africa",
    "cameroon": "Africa",
    "congo": "Africa",
    "drc": "Africa",
    "mozambique": "Africa",
    "zimbabwe": "Africa",
    "south africa": "Africa",
    "angola": "Africa",
    "au": "Africa",
    "african union": "Africa",
    "addis ababa": "Africa",
    "nairobi": "Africa",
    # ── Sahel ─────────────────────────────────────────────────────
    "burkina faso": "Sahel",
    "niger": "Sahel",
    "chad": "Sahel",
    "mauritania": "Sahel",
    "g5 sahel": "Sahel",
    "ecowas": "Sahel",
    "wagadou": "Sahel",
    # ── Latin America ─────────────────────────────────────────────
    "mexico": "Latin America",
    "colombia": "Latin America",
    "argentina": "Latin America",
    "chile": "Latin America",
    "peru": "Latin America",
    "ecuador": "Latin America",
    "bolivia": "Latin America",
    "cuba": "Latin America",
    "haiti": "Latin America",
    "nicaragua": "Latin America",
    "honduras": "Latin America",
    "el salvador": "Latin America",
    "guatemala": "Latin America",
    "panama": "Latin America",
    "bogota": "Latin America",
    "caracas": "Latin America",
    "havana": "Latin America",
    "buenos aires": "Latin America",
    # ── North America ─────────────────────────────────────────────
    "washington": "North America",
    "new york": "North America",
    "pentagon": "North America",
    "white house": "North America",
    "congress": "North America",
    "ottawa": "North America",
    "mexico city": "North America",
    # ── Central Asia ──────────────────────────────────────────────
    "kazakhstan": "Central Asia",
    "uzbekistan": "Central Asia",
    "kyrgyzstan": "Central Asia",
    "tajikistan": "Central Asia",
    "turkmenistan": "Central Asia",
    "central asia": "Central Asia",
    "astana": "Central Asia",
    "tashkent": "Central Asia",
    # ── Arctic ───────────────────────────────────────────────────
    "greenland": "Arctic",
    "svalbard": "Arctic",
    "north pole": "Arctic",
    "arctic ocean": "Arctic",
    "barents": "Arctic",
    "alaska": "Arctic",
    # ── Mediterranean ─────────────────────────────────────────────
    "cyprus": "Mediterranean",
    "malta": "Mediterranean",
    "strait of gibraltar": "Mediterranean",
    "suez": "Mediterranean",
    # ── Indo-Pacific ──────────────────────────────────────────────
    "indo-pacific": "Indo-Pacific",
    "quad": "Indo-Pacific",
    "aukus": "Indo-Pacific",
    "strait of malacca": "Indo-Pacific",
    "indian ocean": "Indo-Pacific",
    "bay of bengal": "Indo-Pacific",
    "andaman": "Indo-Pacific",
}


def _extract_domains_from_event(event: dict[str, Any]) -> list[str]:
    """Return domain tags from an event dict, falling back to keyword scan."""
    domains = event.get("domains", [])
    if domains:
        return [d for d in domains if d in _KNOWN_DOMAINS]

    # Keyword scan on text and description (rule extractor uses "description" field)
    text = (
        event.get("text", "")
        + " " + event.get("description", "")
        + " " + event.get("title", "")
    ).lower()
    return [d for d in _KNOWN_DOMAINS if d in text]


def _extract_regions_from_event(event: dict[str, Any]) -> list[str]:
    """Return region tags from an event dict via keyword mapping."""
    # Also check 'description' field (rule extractor uses it instead of 'text')
    text = (
        event.get("text", "")
        + " " + event.get("description", "")
        + " " + event.get("title", "")
    ).lower()
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

    Two events belong to the same cluster if they share >= 3 domain or
    region keywords. Using a higher threshold (3 vs the previous 2) reduces
    over-splitting and duplicate assessment generation.  Uses a greedy
    union-find approach.
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
            if len(tags[i] & tags[j]) >= 3:
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
        entities = ev.get("entities", [])
        # entities may be dict {"ORG": [...], "GPE": [...]} or list of str/dict
        if isinstance(entities, dict):
            # Flatten dict structure: collect all string values from each list
            candidates: list[Any] = []
            for v in entities.values():
                if isinstance(v, list):
                    candidates.extend(v)
        elif isinstance(entities, list):
            candidates = entities
        else:
            candidates = []

        for ent in candidates:
            if isinstance(ent, dict):
                name = ent.get("name", "").strip()
            elif isinstance(ent, str):
                name = ent.strip()
            else:
                continue
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


_HIGH_RISK_DOMAINS = frozenset({"military", "sanctions", "cyber"})
_MEDIUM_RISK_DOMAINS = frozenset({"energy", "finance", "trade"})


class AssessmentGenerator:
    """Generates Assessment records from the news event pipeline."""

    def generate_from_news(
        self,
        hours: int = 48,
        min_events_per_cluster: int = 3,
        max_assessments: int = 10,
        max_total_assessments: int = 20,
        articles: Optional[list[dict[str, Any]]] = None,
        max_articles: int = 30,
    ) -> dict[str, Any]:
        """
        Generate or update assessments from recent news events.

        Args:
            hours: Look-back window in hours for news articles.
            min_events_per_cluster: Minimum events needed to form a cluster.
            max_assessments: Cap on newly generated assessments per run.
            max_total_assessments: Global cap on total assessments in the store.
                When the store already contains this many assessments the oldest
                ones are pruned before new ones are inserted, preventing
                unbounded growth from repeated "Generate Assessments" clicks.
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

            # Use top-2 domains and top-2 regions for stable cluster_key,
            # reducing random ordering variation that causes duplicate IDs.
            top_domains = [d for d, _ in domain_counter.most_common(3)]
            top_regions = [r for r, _ in region_counter.most_common(3)]
            top_domains_key = sorted(top_domains[:2])
            top_regions_key = sorted(top_regions[:2])
            cluster_key = "|".join(top_domains_key) + ";" + "|".join(top_regions_key)
            assessment_id = _stable_id(cluster_key)
            title = _derive_title(cluster, top_domains)

            # Fetch existing record once; reuse for both dedup and upsert.
            existing = assessment_store.get_assessment(assessment_id)
            now = datetime.now(tz=timezone.utc)

            # Title dedup: if the same title exists under a different ID,
            # update that record's alert_count and updated_at instead of
            # creating a near-duplicate entry.
            if existing is None:
                title_duplicate = assessment_store.find_by_title(title)
                if title_duplicate is not None:
                    logger.info(
                        "AssessmentGenerator: skipping duplicate title %r "
                        "(existing id=%s)",
                        title,
                        title_duplicate.assessment_id,
                    )
                    # Refresh the existing record's alert_count and updated_at.
                    assessment_store.update_assessment(
                        title_duplicate.assessment_id,
                        AssessmentUpdate(
                            alert_count=len(cluster),
                        ),
                    )
                    assessment_ids.append(title_duplicate.assessment_id)
                    updated += 1
                    continue

            # Enforce global total cap: prune oldest assessments when needed
            # so repeated runs don't accumulate unbounded entries.
            if existing is None:
                current_total = assessment_store.count()
                if current_total >= max_total_assessments:
                    to_delete = current_total - max_total_assessments + 1
                    assessment_store.delete_oldest(to_delete)
                    logger.info(
                        "AssessmentGenerator: pruned %d oldest assessment(s) "
                        "to enforce max_total=%d",
                        to_delete,
                        max_total_assessments,
                    )

            domains_str = ", ".join(top_domains) if top_domains else "unknown"
            regions_str = ", ".join(top_regions) if top_regions else "unknown"
            # Include top event descriptions so trigger_engine has
            # differentiated input per assessment.
            top_events_preview = "; ".join(
                ev.get("description", ev.get("title", ""))[:80]
                for ev in cluster[:3]
                if ev.get("description") or ev.get("title")
            )
            analyst_notes = (
                f"Auto-generated from {len(cluster)} events in "
                f"domains: {domains_str} / regions: {regions_str}"
            )
            if top_events_preview:
                analyst_notes += f". Key events: {top_events_preview}"

            # Infer last_confidence from cluster size so engines produce
            # differentiated probability outputs instead of the fallback 0.52.
            cluster_size = len(cluster)
            if cluster_size >= 8:
                inferred_confidence = "High"
            elif cluster_size >= 5:
                inferred_confidence = "Medium"
            else:
                inferred_confidence = "Low"

            # Infer last_regime from the top domains in the cluster.
            if any(d in _HIGH_RISK_DOMAINS for d in top_domains):
                inferred_regime = "Nonlinear Escalation"
            elif any(d in _MEDIUM_RISK_DOMAINS for d in top_domains):
                inferred_regime = "Stress Accumulation"
            else:
                inferred_regime = "Linear"

            assessment = Assessment(
                assessment_id=assessment_id,
                title=title,
                assessment_type=AssessmentType.event_driven,
                status=AssessmentStatus.active,
                region_tags=top_regions,
                domain_tags=top_domains,
                created_at=existing.created_at if existing else now,
                updated_at=now,
                last_regime=inferred_regime,
                last_confidence=inferred_confidence,
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
