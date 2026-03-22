"""
News Aggregator – fetches articles from RSS feeds and optional NewsAPI.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Maximum length constants for text truncation
MAX_DESCRIPTION_LENGTH = 300

_DEFAULT_SOURCES = [
    {
        "name": "BBC News",
        "url": "http://feeds.bbc.co.uk/news/rss.xml",
        "category": "general",
        "priority": 1,
    },
    {
        "name": "Reuters Top News",
        "url": "https://feeds.reuters.com/reuters/topNews",
        "category": "general",
        "priority": 1,
    },
    {
        "name": "Al Jazeera",
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "category": "politics",
        "priority": 2,
    },
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "category": "technology",
        "priority": 2,
    },
]

# Sample articles used as a fallback when RSS feeds are unreachable.
_SAMPLE_ARTICLES: List[Dict[str, Any]] = [
    {
        "title": "Global Markets React to Central Bank Decisions",
        "description": (
            "Stock markets worldwide reacted sharply after several central banks "
            "announced unexpected interest rate adjustments, triggering volatility "
            "across emerging and developed economies."
        ),
        "source": "Reuters",
        "category": "economy",
        "published": "2024-01-15T09:30:00Z",
        "link": "https://reuters.com/sample/markets-react",
        "confidence": 0.92,
    },
    {
        "title": "UN Security Council Meets on Regional Conflict",
        "description": (
            "The United Nations Security Council convened an emergency session to "
            "address escalating tensions in the disputed border region, with member "
            "states calling for an immediate ceasefire."
        ),
        "source": "BBC News",
        "category": "politics",
        "published": "2024-01-15T11:00:00Z",
        "link": "https://bbc.com/sample/un-security",
        "confidence": 0.88,
    },
    {
        "title": "Major Tech Firm Announces Breakthrough in Quantum Computing",
        "description": (
            "A leading technology corporation revealed a landmark achievement in "
            "quantum processing, claiming error rates low enough for practical "
            "commercial applications within two years."
        ),
        "source": "TechCrunch",
        "category": "technology",
        "published": "2024-01-15T13:45:00Z",
        "link": "https://techcrunch.com/sample/quantum",
        "confidence": 0.95,
    },
    {
        "title": "Category-4 Hurricane Approaches Gulf Coast",
        "description": (
            "Emergency management officials ordered mandatory evacuations for coastal "
            "communities as a powerful hurricane strengthened over warm gulf waters, "
            "expected to make landfall within 48 hours."
        ),
        "source": "CNN",
        "category": "natural_disaster",
        "published": "2024-01-15T14:20:00Z",
        "link": "https://cnn.com/sample/hurricane",
        "confidence": 0.97,
    },
    {
        "title": "Diplomatic Talks Yield Preliminary Trade Agreement",
        "description": (
            "After months of negotiations, senior diplomats from both nations "
            "initialled a preliminary trade framework that could eliminate tariffs "
            "on over 3,000 goods by next fiscal year."
        ),
        "source": "Financial Times",
        "category": "diplomacy",
        "published": "2024-01-15T16:00:00Z",
        "link": "https://ft.com/sample/trade",
        "confidence": 0.85,
    },
]


class NewsAggregator:
    """Fetches articles from RSS feeds.

    Falls back to built-in sample articles when network access is unavailable.
    """

    def __init__(self, sources: Optional[List[Dict[str, Any]]] = None) -> None:
        self.sources = sources or _DEFAULT_SOURCES

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def aggregate(
        self,
        sources: Optional[List[str]] = None,
        limit: int = 50,
        hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """Fetch articles from all configured RSS sources.

        Args:
            sources: Optional whitelist of source names.  ``None`` means all.
            limit: Maximum total articles to return.
            hours: Only return articles published within the last *hours* hours.

        Returns:
            List of article dicts.
        """
        articles: List[Dict[str, Any]] = []

        for source in self.sources:
            if sources and source["name"] not in sources:
                continue
            fetched = self._fetch_rss(source)
            articles.extend(fetched)

        # Apply time filter when possible
        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
        filtered: List[Dict[str, Any]] = []
        for art in articles:
            pub = art.get("published", "")
            try:
                import email.utils

                parsed_dt = email.utils.parsedate_to_datetime(pub)
                if parsed_dt >= cutoff:
                    filtered.append(art)
            except Exception:
                # If we can't parse the date, include the article anyway
                filtered.append(art)

        result = filtered if filtered else articles

        if not result:
            logger.warning("No live articles fetched – using sample dataset")
            result = list(_SAMPLE_ARTICLES)

        return result[:limit]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_rss(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse a single RSS feed and return a list of article dicts."""
        articles: List[Dict[str, Any]] = []
        try:
            import feedparser  # type: ignore

            feed = feedparser.parse(source["url"])
            for entry in feed.entries[:30]:
                article: Dict[str, Any] = {
                    "title": entry.get("title", ""),
                    "description": (entry.get("summary") or entry.get("description") or "")[:MAX_DESCRIPTION_LENGTH],
                    "source": source["name"],
                    "category": source.get("category", "general"),
                    "published": entry.get("published", ""),
                    "link": entry.get("link", ""),
                    "priority": source.get("priority", 1),
                }
                articles.append(article)
            logger.info("Fetched %d articles from %s", len(articles), source["name"])
        except Exception as exc:
            logger.error("Failed to fetch RSS from %s: %s", source["name"], exc)
        return articles
