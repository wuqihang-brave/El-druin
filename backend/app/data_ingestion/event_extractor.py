"""
Event Extractor – derives structured events from raw article text.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Maximum length constants for text truncation
MAX_TITLE_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 300

# Keyword → event-type mapping used for lightweight extraction.
_KEYWORD_MAP: Dict[str, str] = {
    "war": "政治冲突",
    "conflict": "政治冲突",
    "attack": "恐怖袭击",
    "terror": "恐怖袭击",
    "bombing": "恐怖袭击",
    "crisis": "经济危机",
    "recession": "经济危机",
    "market crash": "经济危机",
    "earthquake": "自然灾害",
    "hurricane": "自然灾害",
    "flood": "自然灾害",
    "wildfire": "自然灾害",
    "disaster": "自然灾害",
    "breakthrough": "技术突破",
    "quantum": "技术突破",
    "ai ": "技术突破",
    "military": "军事行动",
    "troops": "军事行动",
    "invasion": "军事行动",
    "trade": "贸易摩擦",
    "tariff": "贸易摩擦",
    "sanctions": "贸易摩擦",
    "diplomat": "外交事件",
    "summit": "外交事件",
    "agreement": "外交事件",
    "treaty": "外交事件",
    "refugee": "人道危机",
    "humanitarian": "人道危机",
    "famine": "人道危机",
}

_SEVERITY_KEYWORDS: Dict[str, List[str]] = {
    "high": [
        "war", "attack", "bombing", "invasion", "earthquake", "hurricane",
        "terror", "catastrophe", "emergency", "crisis", "landfall",
    ],
    "medium": [
        "conflict", "sanctions", "military", "disaster", "flooding",
        "recession", "breakthrough", "strike", "protest",
    ],
    "low": [
        "trade", "diplomat", "agreement", "treaty", "summit", "accord",
        "negotiations", "talks", "forum",
    ],
}


class EventExtractor:
    """Lightweight keyword-based event extractor.

    Derives event type, severity, and basic entities from article text.
    A spaCy-powered implementation can be substituted by overriding
    ``extract_events`` with a real NLP pipeline.
    """

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def extract_events(self, text: str) -> List[Dict[str, Any]]:
        """Extract zero or more events from a single piece of text.

        Args:
            text: Combined title + description string.

        Returns:
            List of event dicts (may be empty).
        """
        lower = text.lower()
        event_type = self._classify_event_type(lower)
        if not event_type:
            return []

        severity = self._classify_severity(lower)
        confidence = self._estimate_confidence(lower, event_type, severity)
        entities = self._extract_entities(text)

        return [
            {
                "title": text[:MAX_TITLE_LENGTH].strip(),
                "event_type": event_type,
                "severity": severity,
                "confidence": confidence,
                "description": text[:MAX_DESCRIPTION_LENGTH].strip(),
                "entities": entities,
            }
        ]

    def extract_from_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract events from a list of article dicts.

        Deduplicates by event_type, keeping the highest-confidence entry.

        Args:
            articles: List of article dicts (must have ``title`` and
                ``description`` keys).

        Returns:
            Deduplicated list of event dicts.
        """
        all_events: List[Dict[str, Any]] = []
        for article in articles:
            combined = f"{article.get('title', '')} {article.get('description', '')}"
            events = self.extract_events(combined)
            for event in events:
                event["source"] = article.get("source", "Unknown")
                event["published"] = article.get("published", "")
            all_events.extend(events)

        # Deduplicate by event_type, keeping highest confidence
        best: Dict[str, Dict[str, Any]] = {}
        for event in all_events:
            key = event["event_type"]
            if key not in best or event["confidence"] > best[key]["confidence"]:
                best[key] = event

        return list(best.values())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _classify_event_type(self, lower_text: str) -> str:
        """Return the most relevant event type string, or empty string."""
        for keyword, event_type in _KEYWORD_MAP.items():
            if keyword in lower_text:
                return event_type
        return ""

    def _classify_severity(self, lower_text: str) -> str:
        """Infer severity from keyword presence."""
        for severity, keywords in _SEVERITY_KEYWORDS.items():
            for kw in keywords:
                if kw in lower_text:
                    return severity
        return "medium"

    def _estimate_confidence(self, lower_text: str, event_type: str, severity: str) -> float:
        """Heuristic confidence score in [0.5, 0.98]."""
        score = 0.65
        # More matching keywords → higher confidence
        matches = sum(1 for kw in _KEYWORD_MAP if kw in lower_text)
        score += min(matches * 0.05, 0.30)
        if severity == "high":
            score += 0.03
        return round(min(score, 0.98), 2)

    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Very lightweight entity extraction (no spaCy dependency).

        Returns a dict with keys ``PERSON``, ``ORG``, ``GPE``, ``EVENT``.
        """
        entities: Dict[str, List[str]] = {"PERSON": [], "ORG": [], "GPE": [], "EVENT": []}

        # Known organisations
        known_orgs = [
            "UN", "NATO", "EU", "OPEC", "WHO", "IMF", "World Bank",
            "Federal Reserve", "ECB", "FEMA", "Pentagon",
        ]
        for org in known_orgs:
            if org.lower() in text.lower():
                entities["ORG"].append(org)

        # Known geopolitical entities
        known_gpes = [
            "USA", "China", "Russia", "Ukraine", "Europe", "Middle East",
            "Gulf Coast", "Asia", "Africa",
        ]
        for gpe in known_gpes:
            if gpe.lower() in text.lower():
                entities["GPE"].append(gpe)

        return entities
