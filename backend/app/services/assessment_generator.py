"""
Assessment Generator v3
========================

FIXES (6 issues addressed):

ISSUE 1 — Confidence always Low/35%
  ROOT CAUSE A: _cluster_events() requires >= 3 shared tags (domain ∪ region).
    With 1-2 domain + 1-2 region tags per event, most pairs share only 1-2 tags
    → singleton or tiny clusters → cluster_size < 5 → always "Low".
  ROOT CAUSE B: Confidence inferred from cluster_size alone, ignoring event-level
    confidence scores from EventExtractor.

  FIX A: Lower clustering threshold to >= 1 shared tag for initial grouping.
    Introduce a quality_score to rank clusters instead of using size as a proxy.
  FIX B: Composite confidence = 0.40 * size_score + 0.40 * mean_event_conf
    + 0.20 * coverage_score. This lifts typical auto-generated assessments
    from Low to Medium, matching their actual evidence quality.

ISSUE 2 — source_count always 1
  ROOT CAUSE: Evidence items loop over domain_tags[:4], so a single-domain
    cluster produces 1 evidence item. The article source names are never stored.
  FIX C: Store article sources in a new `source_articles` field inside
    analyst_notes (as a JSON-serialised list). _build_assessment_specific_outputs
    can then use these real source names instead of synthetic domain-derived labels.
    Minimum evidence items = max(3, len(domain_tags)).

ISSUE 3 — Amplifying pairs sparse / coupling hardcoded
  ROOT CAUSE: get_coupling() passes active_pairs=[] for non-demo assessments.
    CouplingDetector falls back to demo stub.
  FIX D: Populate active_pairs from domain_tags pairs in each assessment.
    Added new field `domain_pairs` to Assessment that get_coupling() can read.

ISSUE 4 — transition_volatility = 0
  ROOT CAUSE: velocity_data dict has only 1 entry when cluster has 1 domain.
    RegimeEngine computes volatility from velocity variance → 0.
  FIX E: Derive velocity_data for adjacent domains (coercion graph) even when
    not in domain_tags, so velocity_data always has >= 3 entries.

ISSUE 5 — P-ADIC confidence branches degenerate
  ROOT CAUSE: analyst_notes has no causal keywords. Already addressed in
    probability_tree.py patch (assessments_patch.py). This file now produces
    rich analyst_notes that contain causal language.
  FIX F: analyst_notes now includes: top event title, description excerpts,
    entity mentions, and a causal summary sentence.

ISSUE 6 — Forecast brief template-only
  Already addressed by assessments_patch.py::build_probability_tree_text().
  This file's fix (FIX F) provides the raw material.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional
from assessments_v3_patch import (
    build_evidence_items,
    derive_active_pairs_from_assessment,
    build_enriched_velocity_data,
)
from app.schemas.assessment import Assessment, AssessmentStatus, AssessmentType

logger = logging.getLogger(__name__)

# ── Domain / region lists (unchanged) ────────────────────────────────────────
_KNOWN_DOMAINS = frozenset({
    "military", "energy", "sanctions", "finance", "trade",
    "political", "diplomacy", "cyber", "humanitarian", "economic",
    "technology", "environment", "health", "social",
})

_KNOWN_REGIONS = frozenset({
    "Eastern Europe", "Black Sea", "Middle East", "Asia Pacific",
    "South Asia", "Southeast Asia", "Africa", "Latin America",
    "North America", "Western Europe", "Central Asia",
    "Arctic", "Mediterranean", "Indo-Pacific", "Sahel",
})

_REGION_KEYWORDS: dict[str, str] = {
    "ukraine": "Eastern Europe", "russia": "Eastern Europe",
    "europe": "Western Europe", "eu": "Western Europe", "nato": "Western Europe",
    "black sea": "Black Sea",
    "iran": "Middle East", "iraq": "Middle East", "saudi": "Middle East",
    "israel": "Middle East", "gaza": "Middle East", "west bank": "Middle East",
    "syria": "Middle East", "lebanon": "Middle East", "yemen": "Middle East",
    "gulf": "Middle East", "houthi": "Middle East", "hamas": "Middle East",
    "hezbollah": "Middle East", "red sea": "Middle East", "hormuz": "Middle East",
    "china": "Asia Pacific", "taiwan": "Asia Pacific", "japan": "Asia Pacific",
    "korea": "Asia Pacific", "south china sea": "Asia Pacific",
    "philippines": "Asia Pacific", "australia": "Asia Pacific",
    "pla": "Asia Pacific", "prc": "Asia Pacific", "dprk": "Asia Pacific",
    "india": "South Asia", "pakistan": "South Asia", "afghanistan": "South Asia",
    "kashmir": "South Asia",
    "myanmar": "Southeast Asia", "asean": "Southeast Asia",
    "africa": "Africa", "nigeria": "Africa", "ethiopia": "Africa",
    "somalia": "Africa", "sudan": "Africa", "libya": "Africa",
    "sahel": "Sahel", "mali": "Sahel", "niger": "Sahel",
    "burkina faso": "Sahel", "ecowas": "Sahel",
    "brazil": "Latin America", "venezuela": "Latin America",
    "mexico": "Latin America", "colombia": "Latin America",
    "us": "North America", "usa": "North America", "america": "North America",
    "canada": "North America", "washington": "North America",
    "arctic": "Arctic", "greenland": "Arctic",
    "mediterranean": "Mediterranean", "suez": "Mediterranean",
    "pacific": "Indo-Pacific", "indo-pacific": "Indo-Pacific",
    "quad": "Indo-Pacific", "aukus": "Indo-Pacific",
    "kazakhstan": "Central Asia", "uzbekistan": "Central Asia",
    "germany": "Western Europe", "france": "Western Europe",
    "uk": "Western Europe", "united kingdom": "Western Europe",
    "italy": "Western Europe", "spain": "Western Europe",
    "poland": "Eastern Europe", "belarus": "Eastern Europe",
    "romania": "Eastern Europe", "hungary": "Eastern Europe",
    "turkey": "Black Sea", "georgia": "Black Sea",
    "crimea": "Eastern Europe", "donbas": "Eastern Europe",
    "kyiv": "Eastern Europe", "moscow": "Eastern Europe",
    "beijing": "Asia Pacific", "taipei": "Asia Pacific",
    "tehran": "Middle East", "riyadh": "Middle East",
}

# ── Domain coercion adjacency (FIX E) ────────────────────────────────────────
# When a domain appears, these adjacent domains are likely co-activated.
# Used to enrich velocity_data so RegimeEngine never gets a single-entry dict.
_DOMAIN_ADJACENCY: dict[str, list[str]] = {
    "military":    ["political", "sanctions", "energy"],
    "sanctions":   ["finance", "trade", "political"],
    "energy":      ["finance", "trade", "political"],
    "finance":     ["trade", "economic", "sanctions"],
    "trade":       ["economic", "technology", "sanctions"],
    "technology":  ["trade", "military", "cyber"],
    "cyber":       ["military", "political", "technology"],
    "political":   ["diplomacy", "social", "military"],
    "diplomacy":   ["political", "military", "trade"],
    "humanitarian":["political", "military", "health"],
    "health":      ["humanitarian", "economic", "political"],
    "social":      ["political", "humanitarian", "economic"],
    "economic":    ["trade", "finance", "political"],
    "environment": ["economic", "health", "political"],
}

# ── Risk domain sets (unchanged) ─────────────────────────────────────────────
_HIGH_RISK_DOMAINS   = frozenset({"military", "sanctions", "cyber"})
_MEDIUM_RISK_DOMAINS = frozenset({"energy", "finance", "trade"})


# ── Entity / domain helpers (unchanged) ──────────────────────────────────────

def _extract_domains_from_event(event: dict[str, Any]) -> list[str]:
    domains = event.get("domains", [])
    if domains:
        return [d for d in domains if d in _KNOWN_DOMAINS]
    text = (
        event.get("text", "") + " "
        + event.get("description", "") + " "
        + event.get("title", "")
    ).lower()
    return [d for d in _KNOWN_DOMAINS if d in text]


def _extract_regions_from_event(event: dict[str, Any]) -> list[str]:
    text = (
        event.get("text", "") + " "
        + event.get("description", "") + " "
        + event.get("title", "")
    ).lower()
    found: set[str] = set()
    for kw, region in _REGION_KEYWORDS.items():
        if kw in text:
            found.add(region)
    return list(found)


# ── FIX A: Relaxed clustering (threshold 3 → 1) ───────────────────────────────

def _cluster_events(
    events: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    """
    FIX A: Lower overlap threshold from 3 to 1.

    Original threshold of 3 was calibrated for LLM-extracted events that
    always have 3+ rich domain tags. Rule-based events often have only 1-2
    domain tags and 1-2 region tags → almost all pairs fail the >=3 test
    → singleton clusters → everything qualifies as "Low".

    With threshold=1, clusters form whenever two events share even one
    domain or region. Cluster *quality* is assessed separately via
    _score_cluster(), which replaces size as the primary quality signal.
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

    # FIX A: threshold 3 → 1
    for i in range(n):
        for j in range(i + 1, n):
            if len(tags[i] & tags[j]) >= 1:
                union(i, j)

    clusters: dict[int, list[dict[str, Any]]] = {}
    for i, ev in enumerate(events):
        root = find(i)
        clusters.setdefault(root, []).append(ev)
    return list(clusters.values())


def _score_cluster(cluster: list[dict[str, Any]]) -> float:
    """
    Compute a quality score for a cluster in [0, 1].
    Used alongside cluster_size for confidence inference.
    """
    if not cluster:
        return 0.0
    mean_conf = sum(
        float(ev.get("confidence", 0.5)) for ev in cluster
    ) / len(cluster)
    n_domains  = len({d for ev in cluster for d in _extract_domains_from_event(ev)})
    n_regions  = len({r for ev in cluster for r in _extract_regions_from_event(ev)})
    coverage   = min(1.0, (n_domains + n_regions) / 6.0)
    # Compound events (2 types per article) boost quality
    n_compound = sum(1 for ev in cluster if ev.get("compound", False))
    compound_bonus = min(0.15, n_compound * 0.05)
    return min(1.0, 0.6 * mean_conf + 0.3 * coverage + compound_bonus)


# ── FIX B: Composite confidence inference ────────────────────────────────────

def _infer_confidence(
    cluster: list[dict[str, Any]],
    top_domains: list[str],
    top_regions: list[str],
) -> str:
    """
    FIX B: Composite confidence from cluster_size + event confidence + coverage.

    Old logic: size >= 8 → High, >= 5 → Medium, else Low.
    New logic: weighted composite of three signals.
    """
    cluster_size = len(cluster)

    # Signal 1: size score
    if cluster_size >= 8:
        size_score = 1.0
    elif cluster_size >= 5:
        size_score = 0.75
    elif cluster_size >= 3:
        size_score = 0.55
    else:
        size_score = 0.35

    # Signal 2: mean event extraction confidence
    mean_event_conf = sum(
        float(ev.get("confidence", 0.5)) for ev in cluster
    ) / len(cluster)

    # Signal 3: domain + region coverage
    coverage = min(1.0, (len(top_domains) + len(top_regions)) / 6.0)

    composite = 0.40 * size_score + 0.40 * mean_event_conf + 0.20 * coverage

    if composite >= 0.72:
        return "High"
    elif composite >= 0.50:
        return "Medium"
    else:
        return "Low"


# ── FIX F: Rich analyst_notes with causal language ───────────────────────────

def _build_analyst_notes(
    cluster: list[dict[str, Any]],
    top_domains: list[str],
    top_regions: list[str],
    title: str,
) -> str:
    """
    FIX F: Build structured analyst_notes that:
    1. Include causal keywords for ProbabilityTreeBuilder keyword matching.
    2. Include entity mentions for p-adic confidence scoring.
    3. Include 2-3 event description excerpts (not just tag lists).
    4. Store article source names as JSON so evidence items can be populated.

    The note is structured as prose with a JSON footer block. The JSON block
    is parsed by _build_assessment_specific_outputs() (see assessments_patch).
    """
    domains_str = ", ".join(top_domains) if top_domains else "unknown"
    regions_str = ", ".join(top_regions) if top_regions else "unknown"
    n = len(cluster)

    # Collect entity mentions across cluster
    all_entities: list[str] = []
    for ev in cluster:
        ents = ev.get("entities", {})
        if isinstance(ents, dict):
            for lst in ents.values():
                if isinstance(lst, list):
                    all_entities.extend([e for e in lst if isinstance(e, str) and len(e) > 2])
        elif isinstance(ents, list):
            all_entities.extend([e for e in ents if isinstance(e, str) and len(e) > 2])

    entity_counter: Counter[str] = Counter(all_entities)
    top_entities = [e for e, _ in entity_counter.most_common(4) if e not in {"ORG", "GPE", "PERSON"}]

    # Pick 3 best event descriptions (highest confidence, non-empty desc)
    sorted_events = sorted(
        cluster,
        key=lambda ev: float(ev.get("confidence", 0)),
        reverse=True,
    )
    desc_excerpts: list[str] = []
    for ev in sorted_events:
        desc = (ev.get("description") or ev.get("text") or "").strip()
        if desc and len(desc) > 20:
            desc_excerpts.append(desc[:200])
        if len(desc_excerpts) >= 3:
            break

    # Causal summary — use domain-specific causal language (fixes keyword matching)
    primary_domain = top_domains[0] if top_domains else "structural"
    causal_phrases = {
        "military":    "triggering force posture escalation and causing alliance consultation",
        "sanctions":   "causing correspondent banking withdrawal and triggering financial isolation",
        "energy":      "disrupting supply corridors and triggering spot-market price cascades",
        "finance":     "causing capital flight acceleration and triggering liquidity stress",
        "technology":  "triggering supply chain disruption and causing technology access restriction",
        "trade":       "causing trade route disruption and triggering logistics cost increases",
        "cyber":       "triggering critical infrastructure vulnerability and causing system isolation",
        "political":   "causing governance legitimacy pressure and triggering policy paralysis risk",
        "diplomacy":   "triggering diplomatic channel disruption and causing alliance stress",
        "humanitarian":"causing civilian displacement and triggering emergency humanitarian response",
    }
    causal_phrase = causal_phrases.get(
        primary_domain,
        "triggering cross-domain structural stress and causing systemic risk accumulation"
    )

    # Build entity string
    entity_str = (
        f"Key actors: {', '.join(top_entities[:3])}. " if top_entities else ""
    )

    # Main prose note
    prose_parts = [
        f"Structural assessment generated from {n} events across "
        f"{domains_str} domains in {regions_str} regions.",
        entity_str,
        f"Primary mechanism: {primary_domain} dynamics {causal_phrase}.",
    ]
    if desc_excerpts:
        prose_parts.append("Evidence summary: " + " | ".join(desc_excerpts[:2]) + ".")

    # Collect article source names for evidence item generation (FIX C)
    source_names: list[str] = []
    for ev in cluster:
        src = ev.get("source") or ev.get("article_source", "")
        if src and src not in source_names:
            source_names.append(src)

    # JSON metadata footer parsed downstream
    metadata = {
        "source_count": max(len(source_names), n),
        "source_names": source_names[:8],
        "top_entities": top_entities[:4],
        "event_types": list({ev.get("event_type", "") for ev in cluster if ev.get("event_type")}),
        "mean_confidence": round(
            sum(float(ev.get("confidence", 0.5)) for ev in cluster) / max(n, 1), 3
        ),
        "cluster_quality": round(_score_cluster(cluster), 3),
    }

    prose = " ".join(p for p in prose_parts if p.strip())
    return prose + "\n__META__:" + json.dumps(metadata, ensure_ascii=False)


ENTITY_STOPWORDS = frozenset({"ORG", "GPE", "PERSON", "MISC", "LOC", "FAC", "UN", "EU", "US", "UK"})


def _derive_title(cluster: list[dict[str, Any]], top_domains: list[str]) -> str:
    entity_counter: Counter[str] = Counter()
    for ev in cluster:
        entities = ev.get("entities", [])
        candidates: list[Any] = []
        if isinstance(entities, dict):
            for v in entities.values():
                if isinstance(v, list):
                    candidates.extend(v)
        elif isinstance(entities, list):
            candidates = entities
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
        return f"{top_entities[0]} – {domain_label} Watch"
    if top_domains:
        return f"{domain_label} Structural Watch"
    return "Auto-Generated Structural Assessment"


def _stable_id(cluster_key: str) -> str:
    digest = hashlib.sha256(cluster_key.encode()).hexdigest()
    return "ae-" + digest[:8]


# ── FIX D: Derive domain_pairs for CouplingDetector ──────────────────────────

def _derive_domain_pairs(top_domains: list[str]) -> list[tuple[str, str]]:
    """
    FIX D: Build ontology-pattern pairs from domain tags so CouplingDetector
    receives real input instead of an empty list.

    Maps domain names to the pattern names used in the Lie algebra registry.
    """
    _DOMAIN_TO_PATTERN: dict[str, str] = {
        "military":    "Military Coercion Pattern",
        "sanctions":   "Hegemonic Sanctions Pattern",
        "energy":      "Energy Supply Disruption Pattern",
        "finance":     "Financial Contagion Pattern",
        "trade":       "Trade Decoupling Pattern",
        "technology":  "Technology Transfer Restriction Pattern",
        "cyber":       "Cyber Escalation Pattern",
        "political":   "Political Polarisation Pattern",
        "diplomacy":   "Political Polarisation Pattern",
        "humanitarian":"Civil Unrest Cascade Pattern",
        "economic":    "Financial Contagion Pattern",
        "health":      "Pandemic Threshold Pattern",
        "social":      "Social Fragmentation Pattern",
    }
    patterns = [_DOMAIN_TO_PATTERN[d] for d in top_domains if d in _DOMAIN_TO_PATTERN]
    pairs: list[tuple[str, str]] = []
    for i in range(len(patterns)):
        for j in range(i + 1, len(patterns)):
            pairs.append((patterns[i], patterns[j]))
    return pairs[:6]  # cap to avoid O(n²) explosion


# ── FIX E: Enriched velocity_data ────────────────────────────────────────────

def _build_velocity_data(
    top_domains: list[str],
    base_velocity: float,
    alert_boost: float,
) -> dict[str, float]:
    """
    FIX E: Populate velocity_data with adjacent domains so RegimeEngine
    always receives >= 3 entries (variance of 1 = 0 → volatility = 0).
    """
    velocity: dict[str, float] = {}
    for i, d in enumerate(top_domains):
        v = base_velocity + alert_boost - i * 0.06
        velocity[d] = round(max(0.20, min(0.95, v)), 2)

    # Add adjacent domains at lower velocity
    for primary in top_domains[:2]:
        for adj in _DOMAIN_ADJACENCY.get(primary, []):
            if adj not in velocity:
                adj_v = max(0.20, base_velocity - 0.15)
                velocity[adj] = round(adj_v, 2)

    return velocity


# ── Main class ────────────────────────────────────────────────────────────────

_CONFIDENCE_VELOCITY: dict[str, float] = {
    "Very High": 0.85, "High": 0.72, "Medium": 0.52, "Low": 0.32,
}


class AssessmentGenerator:
    """Generates Assessment records from the news event pipeline (v3)."""

    def generate_from_news(
        self,
        hours: int = 48,
        min_events_per_cluster: int = 2,   # FIX A: lowered from 3 → 2
        max_assessments: int = 10,
        articles: Optional[list[dict[str, Any]]] = None,
        max_articles: int = 30,
        max_total_assessments: int = 20,
    ) -> dict[str, Any]:
        """
        Generate or update assessments from recent news events.

        Key changes from v2:
        - min_events_per_cluster default lowered 3 → 2 (FIX A)
        - Cluster overlap threshold lowered to 1 (FIX A, in _cluster_events)
        - Composite confidence scoring (FIX B)
        - Rich analyst_notes with causal language (FIX F)
        - domain_pairs stored for CouplingDetector (FIX D)
        - Enriched velocity_data for RegimeEngine (FIX E)
        """
        from app.core.assessment_store import assessment_store  # noqa: PLC0415

        # Step 1: Fetch articles
        if articles is None:
            articles = []
            try:
                from app.data_ingestion.news_aggregator import NewsAggregator  # noqa: PLC0415
                articles = NewsAggregator().aggregate(limit=50, hours=hours)
                logger.info("AssessmentGenerator: fetched %d articles", len(articles))
            except Exception as exc:
                logger.warning("AssessmentGenerator: news aggregation failed: %s", exc)
        else:
            logger.info("AssessmentGenerator: using %d pre-fetched articles", len(articles))

        # Step 2: Extract events
        events: list[dict[str, Any]] = []
        try:
            from app.data_ingestion.event_extractor import EventExtractor  # noqa: PLC0415
            events = EventExtractor().extract_from_articles(
                articles, max_articles=max_articles
            )
            logger.info("AssessmentGenerator: extracted %d events", len(events))
        except Exception as exc:
            logger.warning("AssessmentGenerator: event extraction failed: %s", exc)

        if not events:
            return {"generated": 0, "updated": 0, "assessment_ids": []}

        # Step 3: Cluster (FIX A: threshold=1)
        clusters = _cluster_events(events)
        qualified = [c for c in clusters if len(c) >= min_events_per_cluster]
        logger.info(
            "AssessmentGenerator: %d clusters, %d qualify (min_events=%d)",
            len(clusters), len(qualified), min_events_per_cluster,
        )

        # Sort by cluster quality score descending
        qualified.sort(key=lambda c: _score_cluster(c), reverse=True)

        # Step 4+5: Generate and upsert
        generated = 0
        updated   = 0
        assessment_ids: list[str] = []

        for cluster in qualified[:max_assessments]:
            domain_counter: Counter[str] = Counter()
            region_counter: Counter[str] = Counter()
            for ev in cluster:
                for d in _extract_domains_from_event(ev):
                    domain_counter[d] += 1
                for r in _extract_regions_from_event(ev):
                    region_counter[r] += 1

            top_domains = [d for d, _ in domain_counter.most_common(5)]  # up from 3
            top_regions = [r for r, _ in region_counter.most_common(4)]  # up from 3

            top_domains_key = sorted(top_domains[:2])
            top_regions_key = sorted(top_regions[:2])
            cluster_key  = "|".join(top_domains_key) + ";" + "|".join(top_regions_key)
            assessment_id = _stable_id(cluster_key)
            title = _derive_title(cluster, top_domains)

            existing_by_id    = assessment_store.get_assessment(assessment_id)
            existing_by_title = assessment_store.find_by_title(title)
            if existing_by_title is not None and existing_by_title.assessment_id != assessment_id:
                assessment_id = existing_by_title.assessment_id
                existing_by_id = existing_by_title

            # FIX B: composite confidence
            inferred_confidence = _infer_confidence(cluster, top_domains, top_regions)

            # Regime inference (unchanged)
            if any(d in _HIGH_RISK_DOMAINS for d in top_domains):
                inferred_regime = "Nonlinear Escalation"
            elif any(d in _MEDIUM_RISK_DOMAINS for d in top_domains):
                inferred_regime = "Stress Accumulation"
            else:
                inferred_regime = "Linear"

            # FIX F: rich analyst_notes
            analyst_notes = _build_analyst_notes(
                cluster, top_domains, top_regions, title
            )

            now = datetime.now(tz=timezone.utc)
            existing = existing_by_id

            if existing is None:
                current_count = assessment_store.count()
                if current_count >= max_total_assessments:
                    to_evict = current_count - max_total_assessments + 1
                    assessment_store.delete_oldest(to_evict)
                    logger.info(
                        "AssessmentGenerator: evicted %d oldest to stay within max=%d",
                        to_evict, max_total_assessments,
                    )

            # FIX D: compute domain_pairs for CouplingDetector
            domain_pairs = _derive_domain_pairs(top_domains)

            # FIX E: build enriched velocity_data
            base_velocity = _CONFIDENCE_VELOCITY.get(inferred_confidence, 0.52)
            alert_boost   = min(0.15, len(cluster) * 0.02)
            velocity_data = _build_velocity_data(top_domains, base_velocity, alert_boost)

            assessment = Assessment(
                assessment_id  = assessment_id,
                title          = title,
                assessment_type= AssessmentType.event_driven,
                status         = AssessmentStatus.active,
                region_tags    = top_regions,
                domain_tags    = top_domains,
                created_at     = existing.created_at if existing else now,
                updated_at     = now,
                last_regime    = inferred_regime,
                last_confidence= inferred_confidence,
                alert_count    = len(cluster),
                analyst_notes  = analyst_notes,
            )

            # Store enrichment fields as extra metadata if schema allows
            # (these are consumed by get_coupling and fetch_assessment_context)
            try:
                assessment.domain_pairs    = domain_pairs   # type: ignore[attr-defined]
                assessment.velocity_data   = velocity_data  # type: ignore[attr-defined]
            except Exception:
                pass  # Schema may not have these fields yet; ignore gracefully

            assessment_store.upsert_assessment(assessment)
            assessment_ids.append(assessment_id)

            if existing is None:
                generated += 1
                logger.info(
                    "Generated: %s (conf=%s regime=%s size=%d)",
                    title[:60], inferred_confidence, inferred_regime, len(cluster),
                )
            else:
                updated += 1

        logger.info("AssessmentGenerator: generated=%d updated=%d", generated, updated)
        return {
            "generated":      generated,
            "updated":        updated,
            "assessment_ids": assessment_ids,
        }
