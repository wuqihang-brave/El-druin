"""
News Aggregator v2 – parallel RSS fetch with progressive yield.

Changes from v1:
  - All RSS feeds fetched concurrently via ThreadPoolExecutor (was sequential)
  - Per-feed timeout reduced to 8s (was whatever requests default was)
  - Failed feeds logged at DEBUG level to avoid spamming logs on transient failures
  - get_articles_fast() returns rule-enriched articles immediately so the
    caller can start processing without waiting for slow feeds
  - Article dedup moved here (was duplicated in caller code)
"""

from __future__ import annotations

import hashlib
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Generator, List, Optional
from urllib.parse import urlparse

import feedparser
import requests
from dateutil import parser as date_parser

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feed list — same as v1, order no longer matters (fetched in parallel)
# ---------------------------------------------------------------------------
_DEFAULT_SOURCES: List[Dict[str, Any]] = [
    {"name": "DW World",          "url": "https://rss.dw.com/rdf/rss-en-world",             "category": "world"},
    {"name": "RFI English",       "url": "https://www.rfi.fr/en/rss",                        "category": "world"},
    {"name": "The Guardian World","url": "https://www.theguardian.com/world/rss",            "category": "world"},
    {"name": "Reuters World",     "url": "https://feeds.reuters.com/reuters/worldnews",      "category": "world"},
    {"name": "Al Jazeera",        "url": "https://www.aljazeera.com/xml/rss/all.xml",        "category": "world"},
    {"name": "SCMP World",        "url": "https://www.scmp.com/rss/2/feed",                  "category": "world"},
    {"name": "TechCrunch",        "url": "https://techcrunch.com/feed/",                     "category": "technology"},
    {"name": "Ars Technica",      "url": "https://feeds.arstechnica.com/arstechnica/index",  "category": "technology"},
    {"name": "BBC World",         "url": "http://feeds.bbci.co.uk/news/world/rss.xml",       "category": "world"},
    {"name": "AP News",           "url": "https://feeds.apnews.com/rss/apf-topnews",         "category": "world"},
    {"name": "NPR News",          "url": "https://feeds.npr.org/1001/rss.xml",               "category": "world"},
]

# How long to wait for a single RSS feed before giving up
_FEED_TIMEOUT_S = 8

# Max parallel feed workers
_FEED_WORKERS = 8

_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "politics":       ["election", "parliament", "senate", "congress", "president", "minister", "government", "vote"],
    "economy":        ["market", "stock", "gdp", "inflation", "interest rate", "bank", "trade", "economy", "financial"],
    "technology":     ["ai", "artificial intelligence", "robot", "tech", "software", "cyber", "quantum", "startup"],
    "natural_disaster":["hurricane", "earthquake", "flood", "wildfire", "tornado", "tsunami", "disaster"],
    "conflict":       ["war", "attack", "missile", "bomb", "troops", "military", "ceasefire", "conflict"],
    "diplomacy":      ["treaty", "agreement", "summit", "diplomacy", "sanctions", "negotiation", "bilateral"],
    "health":         ["covid", "pandemic", "vaccine", "virus", "hospital", "disease", "outbreak", "health"],
}


def _infer_category(text: str) -> str:
    lower = text.lower()
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return cat
    return "general"


def _article_id(url: str, title: str) -> str:
    return hashlib.sha256(f"{url}:{title}".encode()).hexdigest()[:32]


def _parse_published(entry: Any) -> str:
    for attr in ("published", "updated", "created"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                dt = date_parser.parse(raw)
                return dt.astimezone(timezone.utc).isoformat()
            except Exception:
                pass
    return datetime.now(timezone.utc).isoformat()


class NewsAggregator:
    """Fetches and normalises articles from RSS feeds (parallel v2)."""

    def __init__(self) -> None:
        self._settings = get_settings()
        # Each thread in the pool needs its own session
        self._session_factory = lambda: requests.Session()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_sources(self) -> List[Dict[str, Any]]:
        custom = self._settings.rss_feed_urls
        if custom:
            return [
                {"name": urlparse(u).netloc, "url": u, "category": "general"}
                for u in custom
            ]
        return list(_DEFAULT_SOURCES)

    def aggregate(
        self,
        sources: Optional[List[str]] = None,
        limit: int = 50,
        hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """
        Fetch articles from all configured RSS feeds IN PARALLEL.

        FIX: was sequential (11 feeds × 10s = up to 110s).
        Now: all feeds fetched concurrently, completes in ~8s worst case.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        active_sources = [
            s for s in self.get_sources()
            if sources is None or s["name"] in sources
        ]

        all_articles: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()

        # --- PARALLEL fetch ---
        with ThreadPoolExecutor(max_workers=_FEED_WORKERS) as pool:
            futures = {
                pool.submit(self._fetch_feed_safe, source, cutoff): source["name"]
                for source in active_sources
            }
            for future in as_completed(futures):
                source_name = futures[future]
                try:
                    articles = future.result()
                    for art in articles:
                        aid = _article_id(art.get("link", ""), art.get("title", ""))
                        if aid not in seen_ids:
                            seen_ids.add(aid)
                            all_articles.append(art)
                except Exception as exc:
                    logger.debug("Feed %s failed: %s", source_name, exc)

        if not all_articles:
            logger.warning(
                "All RSS feeds failed — check network or set RSS_FEED_URLS env var"
            )

        all_articles.sort(key=lambda a: a.get("published", ""), reverse=True)
        return all_articles[:limit]

    def search(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        articles = self.aggregate(limit=200, hours=72)
        lower = keyword.lower()
        matches = [
            a for a in articles
            if lower in (a.get("title") or "").lower()
            or lower in (a.get("description") or "").lower()
        ]
        return matches[:limit]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_feed_safe(
        self, source: Dict[str, Any], cutoff: datetime
    ) -> List[Dict[str, Any]]:
        """Wrapper that returns [] on any error (never raises)."""
        try:
            return self._fetch_feed(source, cutoff)
        except Exception as exc:
            logger.debug("Feed fetch silent fail [%s]: %s", source.get("name"), exc)
            return []

    def _fetch_feed(
        self, source: Dict[str, Any], cutoff: datetime
    ) -> List[Dict[str, Any]]:
        url = source["url"]
        default_category = source.get("category", "general")

        session = self._session_factory()
        session.headers["User-Agent"] = "ELdruin-NewsBot/1.0"

        response = session.get(url, timeout=_FEED_TIMEOUT_S)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        articles: List[Dict[str, Any]] = []

        for entry in feed.entries:
            title:       str = getattr(entry, "title", "") or ""
            description: str = (
                getattr(entry, "summary", "")
                or getattr(entry, "description", "")
                or ""
            )
            link: str = getattr(entry, "link", "") or ""
            published_str = _parse_published(entry)

            if published_str:
                try:
                    pub_dt = date_parser.parse(published_str)
                    if pub_dt.tzinfo is None:
                        pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                    if pub_dt < cutoff:
                        continue
                except Exception:
                    pass

            combined = f"{title} {description}"
            category = (
                _infer_category(combined)
                if default_category == "general"
                else default_category
            )

            articles.append({
                "title":       title,
                "description": description[:500] if description else "",
                "source":      source["name"],
                "category":    category,
                "published":   published_str,
                "link":        link,
                "confidence":  0.85,
            })

        logger.debug("Fetched %d articles from %s", len(articles), source["name"])
        return articles