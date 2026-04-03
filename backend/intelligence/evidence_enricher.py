"""
intelligence/evidence_enricher.py
===================================
Deep Ontology Analysis – Evidence Enrichment Pipeline.

When ``deep_mode`` is enabled and the credibility report shows missing
evidence anchors, this module tries to fill those anchors by:

Priority order (stops when anchors are sufficiently filled or limits reached):
  1. Local metadata  – fields already present in the request (published_at,
                       source, url).
  2. Source URL fetch – if ``source_url`` is provided, fetch the page and
                        extract publish date, publisher, byline, canonical URL.
  3. Web search       – query title + key entities; pick up to ``max_sources``
                        reputable sources; extract snippets for missing anchors.

Results are cached (keyed by a stable hash of inputs) with a configurable TTL.

Public API
----------
    enricher = EvidenceEnricher()
    result   = enricher.enrich(
        text           = "...",
        missing_before = ["specific_date", ...],
        deep_config    = DeepConfig(level=3, timeout_seconds=20, max_sources=3),
        source_url     = "https://...",  # optional
        local_meta     = {"published_at": "...", "source": "...", "url": "..."},
    )
    # result: EnrichmentResult
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration helpers (from env)
# ---------------------------------------------------------------------------

_CACHE_TTL_SECONDS: int = int(os.getenv("ENRICHMENT_CACHE_TTL", str(24 * 3600)))
_DEFAULT_TIMEOUT:   int = int(os.getenv("ENRICHMENT_TIMEOUT", "20"))
_DEFAULT_MAX_SOURCES: int = 3

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class DeepConfig:
    """Configuration for the deep enrichment step."""
    level:           int = 0   # 0=off, 1=local only, 2=+source_url, 3=+web search
    timeout_seconds: int = _DEFAULT_TIMEOUT
    max_sources:     int = _DEFAULT_MAX_SOURCES

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DeepConfig":
        if not d:
            return cls()
        return cls(
            level=int(d.get("level", 0)),
            timeout_seconds=int(d.get("timeout_seconds", _DEFAULT_TIMEOUT)),
            max_sources=int(d.get("max_sources", _DEFAULT_MAX_SOURCES)),
        )


@dataclass
class ProvenanceEntry:
    """A single enrichment provenance record."""
    anchor_type: str          # e.g. "specific_date"
    source_url:  str = ""
    title:       str = ""
    snippet:     str = ""
    fetched_at:  str = ""
    confidence:  float = 0.0


@dataclass
class EnrichmentResult:
    """Full result from the enrichment phase."""
    enabled:                bool = False
    level:                  int  = 0
    timeout_seconds:        int  = _DEFAULT_TIMEOUT

    missing_before:         List[str] = field(default_factory=list)
    missing_after:          List[str] = field(default_factory=list)

    provenance:             List[ProvenanceEntry] = field(default_factory=list)
    enriched_context_summary: str = ""

    cache_hit:              bool = False
    limits: Dict[str, Any]      = field(default_factory=lambda: {
        "searched": False,
        "fetched_urls": 0,
        "total_sources_used": 0,
        "truncated": False,
    })

    # Non-serialised: extra context text to append to the LLM prompt
    extra_context:          str = ""
    error:                  Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled":                  self.enabled,
            "level":                    self.level,
            "timeout_seconds":          self.timeout_seconds,
            "missing_before":           list(self.missing_before),
            "missing_after":            list(self.missing_after),
            "provenance":               [
                {
                    "anchor_type": p.anchor_type,
                    "source_url":  p.source_url,
                    "title":       p.title,
                    "snippet":     p.snippet,
                    "fetched_at":  p.fetched_at,
                    "confidence":  p.confidence,
                }
                for p in self.provenance
            ],
            "enriched_context_summary": self.enriched_context_summary,
            "cache_hit":                self.cache_hit,
            "limits":                   dict(self.limits),
            **({"error": self.error} if self.error else {}),
        }


# ---------------------------------------------------------------------------
# In-process cache
# ---------------------------------------------------------------------------

class _EnrichmentCache:
    """Thread-safe in-process LRU-ish cache with TTL."""

    def __init__(self, ttl: int = _CACHE_TTL_SECONDS) -> None:
        self._ttl   = ttl
        self._store: Dict[str, Tuple[float, EnrichmentResult]] = {}
        self._lock  = threading.Lock()

    @staticmethod
    def make_key(text: str, source_url: Optional[str], level: int) -> str:
        raw = json.dumps(
            {"t": text[:512], "u": source_url or "", "l": level},
            ensure_ascii=True, sort_keys=True,
        ).encode()
        return hashlib.sha256(raw).hexdigest()[:32]

    def get(self, key: str) -> Optional[EnrichmentResult]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            ts, result = entry
            if time.monotonic() - ts > self._ttl:
                del self._store[key]
                return None
            return result

    def set(self, key: str, result: EnrichmentResult) -> None:
        with self._lock:
            self._store[key] = (time.monotonic(), result)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


_CACHE = _EnrichmentCache()

# ---------------------------------------------------------------------------
# Regex helpers (reuse evented_pipeline patterns where possible)
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(
    r"\b(\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
    r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{4}|"
    r"\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})\b",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_INSTITUTION_RE = re.compile(
    r"\b(UN|NATO|EU|IMF|WTO|IAEA|World\s+Bank|Federal\s+Reserve|"
    r"US\s+Treasury|US\s+State\s+Department|European\s+Commission|"
    r"OFAC|BIS|Congress|Senate|Parliament|Ministry|Pentagon|Kremlin|"
    r"White\s+House|Reuters|Associated\s+Press|AP\s+News|BBC|"
    r"Bloomberg|Financial\s+Times|The\s+Guardian)\b",
    re.IGNORECASE,
)


def _extract_date(text: str) -> Optional[str]:
    m = _DATE_RE.search(text)
    return m.group(0) if m else None


def _extract_url(text: str) -> Optional[str]:
    m = _URL_RE.search(text)
    return m.group(0) if m else None


def _extract_institution(text: str) -> Optional[str]:
    m = _INSTITUTION_RE.search(text)
    return m.group(0) if m else None


# ---------------------------------------------------------------------------
# Step 1: Local metadata
# ---------------------------------------------------------------------------

def _enrich_from_local_meta(
    missing: List[str],
    local_meta: Dict[str, Any],
    provenance: List[ProvenanceEntry],
) -> List[str]:
    """Fill anchors from already-known article metadata. Returns remaining missing."""
    remaining = list(missing)
    now_str = datetime.now(timezone.utc).isoformat()

    published_at = local_meta.get("published_at") or local_meta.get("published") or ""
    source       = local_meta.get("source") or ""
    url          = local_meta.get("url") or ""

    if "specific_date" in remaining and published_at:
        provenance.append(ProvenanceEntry(
            anchor_type="specific_date",
            source_url=url,
            title=source,
            snippet=str(published_at),
            fetched_at=now_str,
            confidence=0.95,
        ))
        remaining.remove("specific_date")

    if "named_institution_or_official_source" in remaining and source:
        provenance.append(ProvenanceEntry(
            anchor_type="named_institution_or_official_source",
            source_url=url,
            title=source,
            snippet=f"Source: {source}",
            fetched_at=now_str,
            confidence=0.80,
        ))
        remaining.remove("named_institution_or_official_source")

    if "official_document_or_url_reference" in remaining and url:
        provenance.append(ProvenanceEntry(
            anchor_type="official_document_or_url_reference",
            source_url=url,
            title=source,
            snippet=url,
            fetched_at=now_str,
            confidence=0.85,
        ))
        remaining.remove("official_document_or_url_reference")

    return remaining


# ---------------------------------------------------------------------------
# Step 2: Fetch source URL
# ---------------------------------------------------------------------------

def _fetch_url_text(url: str, timeout: float = 8.0) -> Optional[str]:
    """Fetch a URL and return the plain-text body (best-effort). Returns None on error."""
    try:
        import urllib.request
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; El-druin/1.0; +https://github.com/wuqihang-brave/El-druin)"
                )
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "text" not in content_type.lower():
                return None
            raw = resp.read(65536)  # max 64 KB
            charset = "utf-8"
            if "charset=" in content_type:
                charset = content_type.split("charset=")[-1].split(";")[0].strip()
            try:
                text = raw.decode(charset, errors="replace")
            except LookupError:
                text = raw.decode("utf-8", errors="replace")
            # Strip HTML tags
            text = re.sub(r"<[^>]{0,200}>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:8000]
    except Exception as exc:
        logger.debug("Failed to fetch URL %s: %s", url, exc)
        return None


def _enrich_from_source_url(
    missing: List[str],
    source_url: str,
    provenance: List[ProvenanceEntry],
    timeout: float = 8.0,
) -> Tuple[List[str], int]:
    """Fetch source_url and extract anchors. Returns (remaining_missing, fetched_count)."""
    if not source_url:
        return missing, 0

    page_text = _fetch_url_text(source_url, timeout=timeout)
    if not page_text:
        return missing, 0

    remaining   = list(missing)
    now_str     = datetime.now(timezone.utc).isoformat()
    fetched_cnt = 1

    date_val = _extract_date(page_text)
    if "specific_date" in remaining and date_val:
        provenance.append(ProvenanceEntry(
            anchor_type="specific_date",
            source_url=source_url,
            title="Fetched article page",
            snippet=date_val,
            fetched_at=now_str,
            confidence=0.82,
        ))
        remaining.remove("specific_date")

    institution_val = _extract_institution(page_text)
    if "named_institution_or_official_source" in remaining and institution_val:
        provenance.append(ProvenanceEntry(
            anchor_type="named_institution_or_official_source",
            source_url=source_url,
            title="Fetched article page",
            snippet=institution_val,
            fetched_at=now_str,
            confidence=0.75,
        ))
        remaining.remove("named_institution_or_official_source")

    if "official_document_or_url_reference" in remaining:
        extra_url = _extract_url(page_text)
        if extra_url and extra_url != source_url:
            provenance.append(ProvenanceEntry(
                anchor_type="official_document_or_url_reference",
                source_url=extra_url,
                title="Linked from fetched page",
                snippet=extra_url,
                fetched_at=now_str,
                confidence=0.65,
            ))
            remaining.remove("official_document_or_url_reference")
        else:
            # The source_url itself counts as a URL reference
            provenance.append(ProvenanceEntry(
                anchor_type="official_document_or_url_reference",
                source_url=source_url,
                title="Source article URL",
                snippet=source_url,
                fetched_at=now_str,
                confidence=0.70,
            ))
            remaining.remove("official_document_or_url_reference")

    return remaining, fetched_cnt


# ---------------------------------------------------------------------------
# Step 3: Web search (DuckDuckGo Instant Answer – no API key needed)
# ---------------------------------------------------------------------------

_DDG_URL = "https://api.duckduckgo.com/"


def _web_search_snippets(
    query: str,
    max_results: int = 3,
    timeout: float = 6.0,
) -> List[Dict[str, str]]:
    """
    Query DuckDuckGo Instant Answer API and return snippets.
    Returns list of {"title": ..., "snippet": ..., "url": ...}.
    Falls back to empty list on any error.
    """
    try:
        import urllib.parse
        import urllib.request

        params = urllib.parse.urlencode({
            "q": query,
            "format": "json",
            "no_redirect": "1",
            "no_html": "1",
            "skip_disambig": "1",
        })
        url = f"{_DDG_URL}?{params}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "El-druin/1.0 (Deep Ontology Enricher)"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))

        results: List[Dict[str, str]] = []

        # AbstractText + AbstractURL
        abstract = (data.get("AbstractText") or "").strip()
        abstract_url = (data.get("AbstractURL") or "").strip()
        if abstract:
            results.append({
                "title":   data.get("Heading", query),
                "snippet": abstract[:400],
                "url":     abstract_url,
            })

        # RelatedTopics
        for topic in (data.get("RelatedTopics") or [])[:max_results]:
            if not isinstance(topic, dict):
                continue
            text = (topic.get("Text") or "").strip()
            first_url = (topic.get("FirstURL") or "").strip()
            if text:
                results.append({
                    "title":   topic.get("Name") or query,
                    "snippet": text[:400],
                    "url":     first_url,
                })
            if len(results) >= max_results:
                break

        return results[:max_results]

    except Exception as exc:
        logger.debug("Web search failed: %s", exc)
        return []


def _enrich_from_web_search(
    missing: List[str],
    text: str,
    provenance: List[ProvenanceEntry],
    max_sources: int = 3,
    timeout: float = 6.0,
) -> Tuple[List[str], bool, int]:
    """
    Run a web search for missing anchors.
    Returns (remaining_missing, searched, total_sources_used).
    """
    if not missing:
        return missing, False, 0

    # Build a compact search query from first ~80 chars of text
    query = re.sub(r"\s+", " ", text[:120]).strip()
    if len(query) > 120:
        query = query[:120]

    snippets = _web_search_snippets(query, max_results=max_sources, timeout=timeout)
    if not snippets:
        return missing, True, 0

    remaining = list(missing)
    now_str   = datetime.now(timezone.utc).isoformat()
    total_used = len(snippets)

    for snippet_item in snippets:
        snippet_text = snippet_item.get("snippet", "")
        snippet_url  = snippet_item.get("url", "")
        snippet_title = snippet_item.get("title", "")

        date_val = _extract_date(snippet_text)
        if "specific_date" in remaining and date_val:
            provenance.append(ProvenanceEntry(
                anchor_type="specific_date",
                source_url=snippet_url,
                title=snippet_title,
                snippet=date_val,
                fetched_at=now_str,
                confidence=0.60,
            ))
            remaining.remove("specific_date")

        inst_val = _extract_institution(snippet_text)
        if "named_institution_or_official_source" in remaining and inst_val:
            provenance.append(ProvenanceEntry(
                anchor_type="named_institution_or_official_source",
                source_url=snippet_url,
                title=snippet_title,
                snippet=inst_val,
                fetched_at=now_str,
                confidence=0.55,
            ))
            remaining.remove("named_institution_or_official_source")

        if "official_document_or_url_reference" in remaining and snippet_url:
            provenance.append(ProvenanceEntry(
                anchor_type="official_document_or_url_reference",
                source_url=snippet_url,
                title=snippet_title,
                snippet=snippet_url,
                fetched_at=now_str,
                confidence=0.50,
            ))
            remaining.remove("official_document_or_url_reference")

        if not remaining:
            break

    return remaining, True, total_used


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def _build_enriched_context(provenance: List[ProvenanceEntry]) -> str:
    """Return a plain-text Evidence Anchors block to append to the LLM prompt."""
    if not provenance:
        return ""
    lines = ["[Evidence Anchors – provided by Deep Ontology Enrichment]"]
    for p in provenance:
        lines.append(
            f"  • [{p.anchor_type}] {p.snippet}"
            + (f" (source: {p.source_url})" if p.source_url else "")
            + f" [confidence={p.confidence:.0%}]"
        )
    return "\n".join(lines)


def _build_summary(provenance: List[ProvenanceEntry], missing_before: List[str]) -> str:
    if not provenance:
        return f"No enrichment was possible; missing anchors: {', '.join(missing_before)}."
    filled = {p.anchor_type for p in provenance}
    return (
        f"Enrichment filled {len(filled)} anchor(s): "
        + ", ".join(sorted(filled))
        + "."
    )


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

class EvidenceEnricher:
    """
    Stateless (except cache) enrichment engine.
    Thread-safe; cache is module-level.
    """

    def __init__(self, cache: Optional[_EnrichmentCache] = None) -> None:
        self._cache = cache or _CACHE

    def enrich(
        self,
        text: str,
        missing_before: List[str],
        deep_config: Optional[DeepConfig] = None,
        source_url: Optional[str] = None,
        local_meta: Optional[Dict[str, Any]] = None,
    ) -> EnrichmentResult:
        """
        Run the enrichment pipeline.

        Args:
            text:           Original news_fragment text.
            missing_before: List of missing anchor types from credibility report.
            deep_config:    Configuration for this enrichment run.
            source_url:     Optional article URL to fetch.
            local_meta:     Dict with optional keys: published_at, source, url.

        Returns:
            EnrichmentResult (always; falls back gracefully on errors).
        """
        cfg = deep_config or DeepConfig()
        local_meta = local_meta or {}

        if not missing_before or cfg.level == 0:
            return EnrichmentResult(
                enabled=True,
                level=cfg.level,
                timeout_seconds=cfg.timeout_seconds,
                missing_before=list(missing_before),
                missing_after=list(missing_before),
            )

        # Cache lookup
        cache_key = _EnrichmentCache.make_key(text, source_url, cfg.level)
        cached = self._cache.get(cache_key)
        if cached is not None:
            cached.cache_hit = True
            return cached

        deadline = time.monotonic() + cfg.timeout_seconds
        provenance: List[ProvenanceEntry] = []
        remaining = list(missing_before)
        fetched_urls = 0
        searched = False
        truncated = False

        try:
            # Step 1: local metadata (level >= 1)
            if remaining and cfg.level >= 1:
                remaining = _enrich_from_local_meta(remaining, local_meta, provenance)
                logger.debug("After local meta: remaining=%s", remaining)

            # Step 2: source URL fetch (level >= 2)
            if remaining and cfg.level >= 2 and source_url:
                if time.monotonic() < deadline:
                    url_timeout = min(8.0, deadline - time.monotonic())
                    remaining, cnt = _enrich_from_source_url(
                        remaining, source_url, provenance, timeout=url_timeout
                    )
                    fetched_urls += cnt
                    logger.debug("After source_url fetch: remaining=%s", remaining)
                else:
                    truncated = True

            # Step 3: web search (level >= 3)
            if remaining and cfg.level >= 3:
                if time.monotonic() < deadline:
                    search_timeout = min(6.0, deadline - time.monotonic())
                    remaining, searched, total_sources = _enrich_from_web_search(
                        remaining, text, provenance,
                        max_sources=cfg.max_sources,
                        timeout=search_timeout,
                    )
                    fetched_urls += total_sources
                    logger.debug("After web search: remaining=%s", remaining)
                else:
                    truncated = True

        except Exception as exc:
            logger.warning("Enrichment pipeline error: %s", exc, exc_info=True)
            result = EnrichmentResult(
                enabled=True,
                level=cfg.level,
                timeout_seconds=cfg.timeout_seconds,
                missing_before=list(missing_before),
                missing_after=list(missing_before),
                error=str(exc),
            )
            return result

        extra_context = _build_enriched_context(provenance)
        summary = _build_summary(provenance, missing_before)

        result = EnrichmentResult(
            enabled=True,
            level=cfg.level,
            timeout_seconds=cfg.timeout_seconds,
            missing_before=list(missing_before),
            missing_after=remaining,
            provenance=provenance,
            enriched_context_summary=summary,
            cache_hit=False,
            limits={
                "searched":           searched,
                "fetched_urls":       fetched_urls,
                "total_sources_used": fetched_urls,
                "truncated":          truncated,
            },
            extra_context=extra_context,
        )

        self._cache.set(cache_key, result)
        return result


# Module-level singleton
_enricher = EvidenceEnricher()


def enrich_missing_anchors(
    text: str,
    missing_before: List[str],
    deep_config: Optional[DeepConfig] = None,
    source_url: Optional[str] = None,
    local_meta: Optional[Dict[str, Any]] = None,
) -> EnrichmentResult:
    """Convenience function using the module-level singleton enricher."""
    return _enricher.enrich(
        text=text,
        missing_before=missing_before,
        deep_config=deep_config,
        source_url=source_url,
        local_meta=local_meta,
    )
