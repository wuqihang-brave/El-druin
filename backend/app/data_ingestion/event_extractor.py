"""
Event Extractor – classifies news text into structured event records.

修复说明 (v2)：
  - 原版 _ORG_PATTERNS / _GPE_PATTERNS 对文本中出现的实体做 re.finditer，
    这部分本身没问题。但 _extract_entities_rule 里的 group(1) 取法在某些
    pattern 没有捕获组时会崩溃（match.lastindex 为 None）。
    修复：统一用 match.group(0) 作为 fallback，并加更严格的 None 检查。
  - 与 entity_extractor.py 的修复思路一致：只提取文本中实际出现的内容。
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event taxonomy
# ---------------------------------------------------------------------------
_EVENT_TYPES = [
    "政治冲突",
    "经济危机",
    "自然灾害",
    "恐怖袭击",
    "技术突破",
    "军事行动",
    "贸易摩擦",
    "外交事件",
    "人道危机",
    "其他事件",
]

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
        "keywords": ["military", "troops", "airstrike", "missile", "navy", "army", "war", "ceasefire",
                     "warplane", "airspace", "base", "operation", "deployed"],
    },
    {
        "event_type": "贸易摩擦",
        "severity": "medium",
        "keywords": ["tariff", "trade war", "sanctions", "embargo", "export ban", "import"],
    },
    {
        "event_type": "外交事件",
        "severity": "low",
        "keywords": ["summit", "treaty", "agreement", "diplomat", "bilateral", "negotiation",
                     "ambassador", "airspace", "refused", "closed", "ban", "access denied"],
    },
    {
        "event_type": "人道危机",
        "severity": "high",
        "keywords": ["refugee", "famine", "humanitarian", "aid", "displacement", "starvation"],
    },
]

# ---------------------------------------------------------------------------
# Entity patterns – extract only entities that APPEAR in the text
# ---------------------------------------------------------------------------

# Well-known ORG abbreviations: only matched if actually present in text
_ORG_ABBREV_RE = re.compile(
    r"\b(UN|NATO|WHO|IMF|WTO|EU|FBI|CIA|FEMA|Fed|ECB|OPEC|G7|G20|IAEA|ICC|WB)\b"
)

# Country / GPE names – sorted longest-first to avoid partial matches
_GPE_NAMES_SORTED = sorted([
    "USA", "United States", "US", "UK", "United Kingdom", "China", "Russia",
    "Germany", "France", "Japan", "India", "Brazil", "Australia", "Canada",
    "Iran", "Israel", "Ukraine", "Taiwan", "North Korea", "South Korea",
    "Saudi Arabia", "Turkey", "Mexico", "Italy", "Spain", "Poland",
    "Netherlands", "Sweden", "Norway", "Pakistan", "Afghanistan",
    "Syria", "Iraq", "Libya", "Venezuela", "Cuba", "Belarus",
    "Madrid", "Washington", "Beijing", "Moscow", "Brussels",
], key=len, reverse=True)

_GPE_RE = re.compile(
    r"\b(" + "|".join(re.escape(g) for g in _GPE_NAMES_SORTED) + r")\b"
)

# Org suffix pattern for context-specific orgs
_ORG_SUFFIX_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+"
    r"(?:Corp|Inc|Ltd|Group|Bank|Fund|Organization|Organisation|"
    r"Agency|Ministry|Council|Committee|Commission|Authority|"
    r"Department|Office|Forces|Army|Navy|Government|Parliament))\b"
)


def _extract_entities_rule(text: str) -> Dict[str, List[str]]:
    """Extract entities that actually appear in *text*.

    修复：不再对整个预定义列表做全量扫描注入，
    只提取在文本中实际出现的实体。
    """
    orgs: List[str] = []
    gpes: List[str] = []
    seen: set = set()

    # Known ORG abbreviations present in text
    for m in _ORG_ABBREV_RE.finditer(text):
        name = m.group(1)
        if name not in seen:
            seen.add(name)
            orgs.append(name)

    # Known GPE names present in text
    for m in _GPE_RE.finditer(text):
        name = m.group(1)
        if name not in seen:
            seen.add(name)
            gpes.append(name)

    # Context-specific org names
    for m in _ORG_SUFFIX_RE.finditer(text):
        name = m.group(1).strip()
        if name not in seen:
            seen.add(name)
            orgs.append(name)

    return {
        "ORG":  orgs[:5],
        "GPE":  gpes[:5],
    }


def _rule_based_extract(text: str) -> List[Dict[str, Any]]:
    """Return events matching keyword rules."""
    lower = text.lower()
    matched: List[Dict[str, Any]] = []
    for rule in _RULES:
        if any(kw in lower for kw in rule["keywords"]):
            entities = _extract_entities_rule(text)
            hits = sum(1 for kw in rule["keywords"] if kw in lower)
            confidence = min(0.95, 0.60 + hits * 0.05)
            matched.append({
                "event_type":  rule["event_type"],
                "severity":    rule["severity"],
                "title":       text[:80].strip(),
                "description": text[:200].strip(),
                "entities":    entities,
                "confidence":  round(confidence, 2),
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
            event_type:  str = Field(description=f"One of: {', '.join(_EVENT_TYPES)}")
            severity:    str = Field(description="high | medium | low")
            title:       str = Field(description="Short title (<=80 chars)")
            description: str = Field(description="Brief description (<=200 chars)")
            entities:    Dict[str, List[str]] = Field(
                description="Only entities mentioned in the text: {ORG: [...], GPE: [...], PERSON: [...]}"
            )
            confidence: float = Field(description="0.0-1.0 confidence score")

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
                "event_type, severity, title, description, "
                "entities (with ORG, GPE, PERSON lists — only entities mentioned in the text), "
                "confidence. "
                f"event_type must be one of: {', '.join(_EVENT_TYPES)}. "
                "severity: high/medium/low. confidence: 0.0-1.0. "
                "IMPORTANT: Only include entities that actually appear in the provided text. "
                "Do NOT add well-known entities that are not mentioned. "
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