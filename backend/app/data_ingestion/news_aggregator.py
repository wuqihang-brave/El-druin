"""
News Aggregator – fetches articles from RSS feeds and optional NewsAPI.

Usage::

    from app.data_ingestion.news_aggregator import NewsAggregator

    agg = NewsAggregator()
    articles = agg.aggregate(limit=20, hours=24)
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone, timedelta
from functools import lru_cache
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import feedparser
import requests
from dateutil import parser as date_parser

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default RSS sources (used when RSS_FEED_URLS env var is not set)
# ---------------------------------------------------------------------------
_DEFAULT_SOURCES: List[Dict[str, Any]] = [
    {"name": "Reuters World", "url": "https://feeds.reuters.com/reuters/worldNews", "category": "world"},
    {"name": "Reuters Business", "url": "https://feeds.reuters.com/reuters/businessNews", "category": "economy"},
    {"name": "BBC World", "url": "http://feeds.bbci.co.uk/news/world/rss.xml", "category": "world"},
    {"name": "BBC Technology", "url": "http://feeds.bbci.co.uk/news/technology/rss.xml", "category": "technology"},
    {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml", "category": "world"},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "category": "technology"},
    {"name": "Financial Times", "url": "https://www.ft.com/rss/home/us", "category": "economy"},
]

# Simple keyword-to-category mapping for fallback categorisation
_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "politics": ["election", "parliament", "senate", "congress", "president", "minister", "government", "vote"],
    "economy": ["market", "stock", "gdp", "inflation", "interest rate", "bank", "trade", "economy", "financial"],
    "technology": ["ai", "artificial intelligence", "robot", "tech", "software", "cyber", "quantum", "startup"],
    "natural_disaster": ["hurricane", "earthquake", "flood", "wildfire", "tornado", "tsunami", "disaster"],
    "conflict": ["war", "attack", "missile", "bomb", "troops", "military", "ceasefire", "conflict"],
    "diplomacy": ["treaty", "agreement", "summit", "diplomacy", "sanctions", "negotiation", "bilateral"],
    "health": ["covid", "pandemic", "vaccine", "virus", "hospital", "disease", "outbreak", "health"],
}


def _infer_category(text: str) -> str:
    lower = text.lower()
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return cat
    return "general"


def _article_id(url: str, title: str) -> str:
    return hashlib.sha256(f"{url}:{title}".encode()).hexdigest()[:32]


def _parse_published(entry: Any) -> Optional[str]:
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
    """Fetches and normalises articles from RSS feeds."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "ELdruin-NewsBot/1.0"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_sources(self) -> List[Dict[str, Any]]:
        """Return the list of configured news sources."""
        custom = self._settings.rss_feed_urls
        if custom:
            return [{"name": urlparse(u).netloc, "url": u, "category": "general", "priority": 1} for u in custom]
        return [dict(s, priority=1) for s in _DEFAULT_SOURCES]

    def aggregate(
        self,
        sources: Optional[List[str]] = None,
        limit: int = 50,
        hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """Fetch articles from all configured RSS feeds.

        Args:
            sources: Optional list of source *names* to restrict to.
            limit: Maximum total articles to return.
            hours: Only include articles published within the last *hours* hours.

        Returns:
            List of normalised article dicts.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        all_articles: List[Dict[str, Any]] = []
        seen_ids: set = set()

        for source in self.get_sources():
            if sources and source["name"] not in sources:
                continue
            try:
                fetched = self._fetch_feed(source, cutoff)
                for art in fetched:
                    art_id = _article_id(art.get("link", ""), art.get("title", ""))
                    if art_id not in seen_ids:
                        seen_ids.add(art_id)
                        all_articles.append(art)
            except Exception as exc:
                logger.warning("Feed fetch failed [%s]: %s", source["name"], exc)

        # Sort by published date (newest first)
        all_articles.sort(key=lambda a: a.get("published", ""), reverse=True)
        return all_articles[:limit]

    def search(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Return articles matching *keyword* from the latest aggregate."""
        articles = self.aggregate(limit=200, hours=72)
        lower = keyword.lower()
        matches = [
            a for a in articles
            if lower in (a.get("title") or "").lower()
            or lower in (a.get("description") or "").lower()
        ]
        return matches[:limit]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_feed(
        self, source: Dict[str, Any], cutoff: datetime
    ) -> List[Dict[str, Any]]:
        url = source["url"]
        default_category = source.get("category", "general")

        feed = feedparser.parse(url)
        articles: List[Dict[str, Any]] = []

        for entry in feed.entries:
            title: str = getattr(entry, "title", "") or ""
            description: str = (
                getattr(entry, "summary", "")
                or getattr(entry, "description", "")
                or ""
            )
            link: str = getattr(entry, "link", "") or ""
            published_str = _parse_published(entry)

            # Filter by recency
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
            category = _infer_category(combined) if default_category == "general" else default_category

            articles.append({
                "title": title,
                "description": description[:500] if description else "",
                "source": source["name"],
                "category": category,
                "published": published_str,
                "link": link,
                "confidence": 0.85,
            })

        logger.debug("Fetched %d articles from %s", len(articles), source["name"])
        return articles
