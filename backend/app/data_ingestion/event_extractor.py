"""
Event Extractor – classifies news text into structured event records.

Two extraction strategies are supported:
  1. **LLM-based** (OpenAI / Groq via LangChain) – uses structured output for
     accurate event classification.  Requires OPENAI_API_KEY or GROQ_API_KEY.
  2. **Rule-based fallback** – keyword matching, always available.

Usage::

    from app.data_ingestion.event_extractor import EventExtractor

    extractor = EventExtractor()
    events = extractor.extract_from_articles(articles)
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event taxonomy
# ---------------------------------------------------------------------------
_EVENT_TYPES = [
    "政治冲突",   # Political conflict
    "经济危机",   # Economic crisis
    "自然灾害",   # Natural disaster
    "恐怖袭击",   # Terrorist attack
    "技术突破",   # Technology breakthrough
    "军事行动",   # Military operation
    "贸易摩擦",   # Trade friction
    "外交事件",   # Diplomatic event
    "人道危机",   # Humanitarian crisis
    "其他事件",   # Other
]

# Keyword rules for rule-based fallback
_RULES: List[Dict[str, Any]] = [
    {
        "event_type": "政治冲突",
        "severity": "high",
        "keywords": ["conflict", "protest", "coup", "riot", "civil war", "uprising", "opposition", "parliament"],
    },
    {
        "event_type": "经济危机",
        "severity": "high",
        "keywords": ["recession", "inflation", "rate hike", "rate cut", "central bank", "market crash", "gdp", "unemployment"],
    },
    {
        "event_type": "自然灾害",
        "severity": "high",
        "keywords": ["earthquake", "hurricane", "flood", "wildfire", "tornado", "tsunami", "disaster", "evacuation"],
    },
    {
        "event_type": "恐怖袭击",
        "severity": "high",
        "keywords": ["terrorist", "attack", "explosion", "bombing", "gunman", "hostage"],
    },
    {
        "event_type": "技术突破",
        "severity": "medium",
        "keywords": ["breakthrough", "discovery", "innovation", "ai", "quantum", "robot", "launch"],
    },
    {
        "event_type": "军事行动",
        "severity": "high",
        "keywords": ["military", "troops", "airstrike", "missile", "navy", "army", "war", "ceasefire"],
    },
    {
        "event_type": "贸易摩擦",
        "severity": "medium",
        "keywords": ["tariff", "trade war", "sanctions", "embargo", "export ban", "import"],
    },
    {
        "event_type": "外交事件",
        "severity": "low",
        "keywords": ["summit", "treaty", "agreement", "diplomat", "bilateral", "negotiation", "ambassador"],
    },
    {
        "event_type": "人道危机",
        "severity": "high",
        "keywords": ["refugee", "famine", "humanitarian", "aid", "displacement", "starvation"],
    },
]

_ORG_PATTERNS = [
    r"\b(UN|NATO|WHO|IMF|WTO|EU|FBI|CIA|FEMA|Fed|ECB|OPEC)\b",
    r"\b([A-Z][a-z]+ (?:Corp|Inc|Ltd|Group|Bank|Fund|Organization|Agency|Ministry|Council))\b",
]
_GPE_PATTERNS = [
    r"\b(USA|United States|US|UK|United Kingdom|China|Russia|Germany|France|Japan|India|Brazil|Australia)\b",
    r"\b([A-Z][a-z]+ (?:Coast|Region|Province|State|City))\b",
]


def _extract_entities_rule(text: str) -> Dict[str, List[str]]:
    """Simple regex-based entity extraction."""
    orgs: List[str] = []
    gpes: List[str] = []
    for pat in _ORG_PATTERNS:
        for match in re.finditer(pat, text):
            orgs.append(match.group(1) if match.lastindex and match.lastindex >= 1 else match.group(0))
    for pat in _GPE_PATTERNS:
        for match in re.finditer(pat, text):
            gpes.append(match.group(1) if match.lastindex and match.lastindex >= 1 else match.group(0))
    return {
        "ORG": list(dict.fromkeys(orgs))[:5],
        "GPE": list(dict.fromkeys(gpes))[:5],
    }


def _rule_based_extract(text: str) -> List[Dict[str, Any]]:
    """Return events matching keyword rules."""
    lower = text.lower()
    matched: List[Dict[str, Any]] = []
    for rule in _RULES:
        if any(kw in lower for kw in rule["keywords"]):
            entities = _extract_entities_rule(text)
            # Estimate confidence by keyword density
            hits = sum(1 for kw in rule["keywords"] if kw in lower)
            confidence = min(0.95, 0.60 + hits * 0.05)
            matched.append({
                "event_type": rule["event_type"],
                "severity": rule["severity"],
                "title": text[:80].strip(),
                "description": text[:200].strip(),
                "entities": entities,
                "confidence": round(confidence, 2),
            })
    return matched


def _llm_extract(text: str) -> List[Dict[str, Any]]:
    """LLM-based extraction using LangChain structured output."""
    settings = get_settings()
    try:
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser
        from pydantic import BaseModel, Field

        class EventRecord(BaseModel):
            event_type: str = Field(description=f"One of: {', '.join(_EVENT_TYPES)}")
            severity: str = Field(description="high | medium | low")
            title: str = Field(description="Short title (≤80 chars)")
            description: str = Field(description="Brief description (≤200 chars)")
            entities: Dict[str, List[str]] = Field(
                description="Extracted entities: {ORG: [...], GPE: [...], PERSON: [...]}"
            )
            confidence: float = Field(description="0.0–1.0 confidence score")

        if settings.llm_provider == "openai":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=settings.llm_model,
                temperature=settings.llm_temperature,
                api_key=settings.openai_api_key,
            )
        elif settings.llm_provider == "groq":
            from langchain_groq import ChatGroq
            llm = ChatGroq(
                model=settings.llm_model,
                temperature=settings.llm_temperature,
                api_key=settings.groq_api_key,
            )
        else:
            return []

        prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "You are an intelligence analyst. Extract structured events from news text. "
                "Return a JSON array of event objects. Each object must have: "
                "event_type, severity, title, description, entities (with ORG, GPE, PERSON lists), confidence. "
                f"event_type must be one of: {', '.join(_EVENT_TYPES)}. "
                "severity: high/medium/low. confidence: 0.0-1.0. "
                "Return [] if no significant events found."
            )),
            ("human", "News text:\n\n{text}"),
        ])

        parser = JsonOutputParser()
        chain = prompt | llm | parser
        result = chain.invoke({"text": text[:2000]})
        if isinstance(result, list):
            return result
        return []
    except Exception as exc:
        logger.warning("LLM extraction failed, falling back to rules: %s", exc)
        return []


class EventExtractor:
    """Extracts structured events from news text."""

    def __init__(self) -> None:
        self._settings = get_settings()

    def extract_events(self, text: str) -> List[Dict[str, Any]]:
        """Extract events from a single text string.

        Tries LLM extraction first if configured; falls back to rule-based.
        """
        if not text or not text.strip():
            return []

        if self._settings.llm_enabled:
            events = _llm_extract(text)
            if events:
                return events

        events = _rule_based_extract(text)
        return events if events else []

    def extract_from_articles(
        self, articles: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract and deduplicate events across a list of articles.

        Args:
            articles: List of article dicts (must have 'title' and 'description').

        Returns:
            Deduplicated list of event dicts.
        """
        all_events: List[Dict[str, Any]] = []
        for article in articles:
            combined = (
                f"{article.get('title', '')} {article.get('description', '')}"
            ).strip()
            try:
                all_events.extend(self.extract_events(combined))
            except Exception as exc:
                logger.warning("Event extraction failed for article: %s", exc)

        # Deduplicate by event_type, keeping highest-confidence occurrence
        best: Dict[str, Dict[str, Any]] = {}
        for ev in all_events:
            key = ev.get("event_type", "other")
            if key not in best or ev.get("confidence", 0) > best[key].get("confidence", 0):
                best[key] = ev
        return list(best.values())
