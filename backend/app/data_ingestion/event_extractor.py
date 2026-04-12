"""
Event Extractor – classifies news text into structured event records.

修复说明 (v2)：
  Bug：标题含 strike/kill/targets 等时只抽出 1 个事件
       → active_patterns=1 → derived_patterns=0 → 前端显示空。

  根因：原版规则是单一触发模式（单个关键词组 → 单个事件类型），
  同一篇报道的所有军事关键词都落入 "军事行动" 这一个桶，
  即使报道同时描述了打击行动和伤亡，也只产出 1 条事件记录。

  修复：新增 _COMPOUND_RULES（复合多事件规则），
  当 trigger_a 和 trigger_b 同时命中时，强制生成两条不同类型的事件，
  每条都带原文 quote，确保 active_patterns≥2，为 compose 提供素材。

  复合规则（AND 语义）：
    1. 打击词 + 伤亡词  → 军事行动 + 人道危机
    2. 制裁词 + 科技词  → 贸易摩擦 + 政治冲突
    3. 选举词 + 争议词  → 政治冲突 + 外交事件
    4. 央行词 + 通胀词  → 经济危机 + 贸易摩擦
    5. 部署词 + 同盟词  → 军事行动 + 外交事件
    6. 灾害词 + 伤亡词  → 自然灾害 + 人道危机

  原有单条规则完全不变，向后兼容。
"""

from __future__ import annotations

import concurrent.futures
import logging
import re
import time
from typing import Any, Dict, List, Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_LLM_TIMEOUT_SECONDS = 30   # hard cap per LLM call – mirrors entity_extractor.py

# ---------------------------------------------------------------------------
# Circuit-breaker: if Groq returns 403 we open the circuit for the rest of the
# current ingest cycle so we don't waste time on 30 guaranteed-to-fail calls.
# The flag is reset by reset_circuit() at the start of each new cycle.
# ---------------------------------------------------------------------------
_llm_circuit_open: bool = False


def reset_circuit() -> None:
    """Reset the LLM circuit-breaker flag.

    Should be called at the start of each new ingest cycle so the LLM is
    retried in case the API key was rotated or the 403 was transient.
    """
    global _llm_circuit_open  # noqa: PLW0603
    _llm_circuit_open = False


_LLM_BATCH_SIZE      = 5    # pause after every N LLM calls to respect Groq RPM/TPM limits
_LLM_BATCH_SLEEP     = 1.0  # seconds to sleep between batches
# Prefix length used when building (event_type, title_prefix) dedup keys.
# Short enough to collapse near-duplicates within the same article while
# keeping events from different articles distinct.
_DEDUP_TITLE_PREFIX_LENGTH = 60

# ---------------------------------------------------------------------------
# Event taxonomy
# ---------------------------------------------------------------------------
_EVENT_TYPES = [
    "政治冲突", "经济危机", "自然灾害", "恐怖袭击",
    "技术突破", "军事行动", "贸易摩擦", "外交事件",
    "人道危机", "其他事件",
]

# ---------------------------------------------------------------------------
# Single-trigger rules（原有，不变）
# ---------------------------------------------------------------------------
_RULES: List[Dict[str, Any]] = [
    {
        "event_type": "政治冲突",
        "severity": "high",
        "keywords": ["conflict", "protest", "coup", "riot", "civil war", "uprising",
                     "opposition", "parliament"],
    },
    {
        "event_type": "经济危机",
        "severity": "high",
        "keywords": ["recession", "inflation", "rate hike", "rate cut", "central bank",
                     "market crash", "gdp", "unemployment"],
    },
    {
        "event_type": "自然灾害",
        "severity": "high",
        "keywords": ["earthquake", "hurricane", "flood", "wildfire", "tornado",
                     "tsunami", "disaster", "evacuation"],
    },
    {
        "event_type": "恐怖袭击",
        "severity": "high",
        "keywords": ["terrorist", "attack", "explosion", "bombing", "gunman", "hostage"],
    },
    {
        "event_type": "技术突破",
        "severity": "medium",
        "keywords": ["breakthrough", "discovery", "innovation", "ai", "quantum",
                     "robot", "launch"],
    },
    {
        "event_type": "军事行动",
        "severity": "high",
        "keywords": ["military", "troops", "airstrike", "missile", "navy", "army",
                     "war", "ceasefire", "warplane", "airspace", "base", "operation",
                     "deployed", "strike", "strikes", "bombed", "shelled"],
    },
    {
        "event_type": "贸易摩擦",
        "severity": "medium",
        "keywords": ["tariff", "trade war", "sanctions", "embargo", "export ban", "import"],
    },
    {
        "event_type": "外交事件",
        "severity": "low",
        "keywords": ["summit", "treaty", "agreement", "diplomat", "bilateral",
                     "negotiation", "ambassador", "airspace", "refused", "closed",
                     "ban", "access denied"],
    },
    {
        "event_type": "人道危机",
        "severity": "high",
        "keywords": ["refugee", "famine", "humanitarian", "aid", "displacement",
                     "starvation"],
    },
]

# ---------------------------------------------------------------------------
# Compound multi-event rules（v2 新增）
#
# 格式：
#   trigger_a  : 关键词组 A（any → 命中）
#   trigger_b  : 关键词组 B（any → 命中）—— A AND B 同时满足才触发
#   event_type_a : 第一条事件类型
#   event_type_b : 第二条事件类型（不同于 A）
#   severity_a/b : 严重程度
# ---------------------------------------------------------------------------
_COMPOUND_RULES: List[Dict[str, Any]] = [
    # 1. 军事打击 + 伤亡 → 军事行动 + 人道危机
    {
        "trigger_a": ["strike", "strikes", "airstrike", "airstrikes", "bombed",
                      "shelled", "fired on", "hit", "attacked", "kill", "kills"],
        "trigger_b": ["dead", "killed", "casualties", "wounded", "targets",
                      "civilians", "infrastructure", "death toll"],
        "event_type_a": "军事行动",
        "severity_a":   "high",
        "event_type_b": "人道危机",
        "severity_b":   "high",
    },
    # 2. 制裁 / 封锁 + 科技 → 贸易摩擦 + 政治冲突
    {
        "trigger_a": ["sanction", "sanctions", "embargo", "ban", "blocked", "restrict"],
        "trigger_b": ["chip", "semiconductor", "export", "technology", "tech",
                      "huawei", "supply chain", "ai"],
        "event_type_a": "贸易摩擦",
        "severity_a":   "high",
        "event_type_b": "政治冲突",
        "severity_b":   "medium",
    },
    # 3. 选举 / 投票 + 争议 / 暴力 → 政治冲突 + 外交事件
    {
        "trigger_a": ["election", "vote", "ballot", "referendum", "polling"],
        "trigger_b": ["disputed", "fraud", "protest", "unrest", "rigged",
                      "violent", "clashes", "rejected"],
        "event_type_a": "政治冲突",
        "severity_a":   "high",
        "event_type_b": "外交事件",
        "severity_b":   "medium",
    },
    # 4. 央行 / 利率 + 市场 / 通胀 → 经济危机 + 贸易摩擦
    {
        "trigger_a": ["fed", "federal reserve", "ecb", "central bank",
                      "rate hike", "rate cut", "interest rate"],
        "trigger_b": ["inflation", "recession", "market", "crash", "yield",
                      "dollar", "currency", "devaluation"],
        "event_type_a": "经济危机",
        "severity_a":   "high",
        "event_type_b": "贸易摩擦",
        "severity_b":   "medium",
    },
    # 5. 军事部署 + 同盟 / 外交 → 军事行动 + 外交事件
    {
        "trigger_a": ["deploy", "deployed", "troops", "forces", "soldiers",
                      "warships", "jets", "military buildup"],
        "trigger_b": ["nato", "alliance", "treaty", "partner", "agreement",
                      "border", "flank", "eastern", "western"],
        "event_type_a": "军事行动",
        "severity_a":   "high",
        "event_type_b": "外交事件",
        "severity_b":   "medium",
    },
    # 6. 自然灾害 + 伤亡 / 响应 → 自然灾害 + 人道危机
    {
        "trigger_a": ["earthquake", "flood", "hurricane", "wildfire",
                      "tsunami", "cyclone", "tornado", "eruption"],
        "trigger_b": ["dead", "killed", "casualties", "missing", "aid",
                      "rescue", "displaced", "humanitarian", "evacuated"],
        "event_type_a": "自然灾害",
        "severity_a":   "high",
        "event_type_b": "人道危机",
        "severity_b":   "high",
    },
]


# ---------------------------------------------------------------------------
# Quote / evidence extraction helper
# ---------------------------------------------------------------------------

def _extract_quote(text: str, keyword: str, window: int = 150) -> str:
    """Extract the sentence containing *keyword* (up to *window* chars)."""
    lower = text.lower()
    idx   = lower.find(keyword.lower())
    if idx == -1:
        return text[:min(len(text), window)].strip()

    # Expand to sentence boundaries
    start = max(0, idx - window // 2)
    end   = min(len(text), idx + window // 2)
    snippet = text[start:end].strip()

    # Snap to nearest sentence end before the keyword
    for sep in (". ", "! ", "? ", "\n"):
        left_parts = text[:idx].rsplit(sep, 1)
        if len(left_parts) == 2:
            sentence_start = len(left_parts[0]) + len(sep)
            right = text[sentence_start:].split(sep, 1)[0]
            if right.strip():
                return right.strip()[:window]

    return snippet[:window]


# ---------------------------------------------------------------------------
# Entity extraction (text-anchored, unchanged from v1)
# ---------------------------------------------------------------------------

_ORG_ABBREV_RE = re.compile(
    r"\b(UN|NATO|WHO|IMF|WTO|EU|FBI|CIA|FEMA|Fed|ECB|OPEC|G7|G20|IAEA|ICC|WB)\b"
)
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
_ORG_SUFFIX_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+"
    r"(?:Corp|Inc|Ltd|Group|Bank|Fund|Organization|Organisation|"
    r"Agency|Ministry|Council|Committee|Commission|Authority|"
    r"Department|Office|Forces|Army|Navy|Government|Parliament))\b"
)


def _extract_entities_rule(text: str) -> Dict[str, List[str]]:
    orgs, gpes, seen = [], [], set()
    for m in _ORG_ABBREV_RE.finditer(text):
        n = m.group(1)
        if n not in seen: seen.add(n); orgs.append(n)
    for m in _GPE_RE.finditer(text):
        n = m.group(1)
        if n not in seen: seen.add(n); gpes.append(n)
    for m in _ORG_SUFFIX_RE.finditer(text):
        n = m.group(1).strip()
        if n not in seen: seen.add(n); orgs.append(n)
    return {"ORG": orgs[:5], "GPE": gpes[:5]}


# ---------------------------------------------------------------------------
# Rule-based extraction (single + compound)
# ---------------------------------------------------------------------------

def _rule_based_extract(text: str) -> List[Dict[str, Any]]:
    """
    Apply single-trigger rules then compound multi-event rules.

    The compound rules guarantee ≥2 distinct event types when co-occurring
    military/crisis keywords are detected, so active_patterns≥2.
    """
    lower = text.lower()
    matched: List[Dict[str, Any]] = []
    seen_types: set = set()

    # ── Single-trigger rules ─────────────────────────────────────────────
    for rule in _RULES:
        if any(kw in lower for kw in rule["keywords"]):
            entities   = _extract_entities_rule(text)
            hits       = sum(1 for kw in rule["keywords"] if kw in lower)
            confidence = min(0.95, 0.60 + hits * 0.05)
            t = rule["event_type"]
            if t not in seen_types:
                seen_types.add(t)
                matched.append({
                    "event_type":  t,
                    "severity":    rule["severity"],
                    "title":       text[:80].strip(),
                    "description": text[:200].strip(),
                    "entities":    entities,
                    "confidence":  round(confidence, 2),
                })

    # ── Compound multi-event rules (v2) ──────────────────────────────────
    for crule in _COMPOUND_RULES:
        a_hit = next((kw for kw in crule["trigger_a"] if kw in lower), None)
        b_hit = next((kw for kw in crule["trigger_b"] if kw in lower), None)
        if a_hit is None or b_hit is None:
            continue

        entities = _extract_entities_rule(text)

        type_a = crule["event_type_a"]
        if type_a not in seen_types:
            seen_types.add(type_a)
            matched.append({
                "event_type":  type_a,
                "severity":    crule["severity_a"],
                "title":       text[:80].strip(),
                "description": _extract_quote(text, a_hit),
                "entities":    entities,
                "confidence":  0.78,
                "compound":    True,
                "trigger":     a_hit,
            })

        type_b = crule["event_type_b"]
        if type_b not in seen_types:
            seen_types.add(type_b)
            matched.append({
                "event_type":  type_b,
                "severity":    crule["severity_b"],
                "title":       text[:80].strip(),
                "description": _extract_quote(text, b_hit),
                "entities":    entities,
                "confidence":  0.72,
                "compound":    True,
                "trigger":     b_hit,
            })

    return matched


# ---------------------------------------------------------------------------
# LLM-based extraction (unchanged from v1)
# ---------------------------------------------------------------------------

def _is_403_error(exc: Exception) -> bool:
    """Return True if *exc* represents a 403 Forbidden HTTP error."""
    msg = str(exc)
    return "403" in msg or "Forbidden" in msg.lower()


def _llm_extract(text: str) -> List[Dict[str, Any]]:
    global _llm_circuit_open  # noqa: PLW0603
    settings = get_settings()
    try:
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser

        if settings.llm_provider == "openai":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=settings.llm_model,
                temperature=settings.llm_temperature,
                api_key=settings.openai_api_key,
                max_retries=0,   # disable built-in retries; ThreadPoolExecutor timeout is the hard cap
            )
        elif settings.llm_provider == "groq":
            from langchain_groq import ChatGroq
            llm = ChatGroq(
                model=settings.llm_model,
                temperature=settings.llm_temperature,
                api_key=settings.groq_api_key,
                max_retries=0,   # disable built-in retries; ThreadPoolExecutor timeout is the hard cap
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
                "Return [] if no significant events found."
            )),
            ("human", "News text:\n\n{text}"),
        ])
        parser = JsonOutputParser()
        chain  = prompt | llm | parser

        def _invoke() -> List[Dict[str, Any]]:
            result = chain.invoke({"text": text[:2000]})
            return result if isinstance(result, list) else []

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_invoke)
            try:
                return future.result(timeout=_LLM_TIMEOUT_SECONDS)
            except concurrent.futures.TimeoutError:
                logger.warning(
                    "Event LLM extraction timed out after %ds", _LLM_TIMEOUT_SECONDS
                )
                return []
    except Exception as exc:
        if _is_403_error(exc):
            _llm_circuit_open = True
            logger.warning(
                "Groq 403 received — disabling LLM for this ingest cycle"
            )
            return []
        logger.warning("LLM extraction failed, falling back to rules: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class EventExtractor:
    """Extracts structured events from news text."""

    def __init__(self) -> None:
        self._settings = get_settings()

    def extract_events(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract events from a single text string.

        v2 strategy:
          1. LLM (if enabled and circuit not open) — full semantic extraction
          2. Augment with compound-rule events not yet covered by LLM
          3. Rule-based fallback when LLM unavailable or circuit is open

        This guarantees active_patterns≥2 for military/crisis headlines.
        """
        if not text or not text.strip():
            return []

        if self._settings.llm_enabled and not _llm_circuit_open:
            llm_events = _llm_extract(text)
            if llm_events:
                # Augment with compound-rule events that LLM may have missed
                llm_types = {e.get("event_type") for e in llm_events}
                for ce in _rule_based_extract(text):
                    if ce.get("compound") and ce["event_type"] not in llm_types:
                        llm_events.append(ce)
                return llm_events

        events = _rule_based_extract(text)
        return events if events else []

    def extract_from_articles(
        self,
        articles: List[Dict[str, Any]],
        max_articles: int = 30,
        reset_circuit: bool = False,
    ) -> List[Dict[str, Any]]:
        """Extract and deduplicate events across a list of articles.

        Args:
            articles:      List of article dicts (title, description, …).
            max_articles:  Maximum number of articles to run LLM extraction on.
                           Articles beyond this cap are skipped to avoid burning
                           the Groq free-tier token budget (6 000 TPM).
            reset_circuit: If True, reset the LLM circuit-breaker before
                           processing so a new ingest cycle can retry the LLM.
        """
        global _llm_circuit_open  # noqa: PLW0603
        if reset_circuit:
            _llm_circuit_open = False
        all_events: List[Dict[str, Any]] = []
        llm_call_count = 0
        capped = articles[:max_articles]

        if len(articles) > max_articles:
            logger.info(
                "extract_from_articles: capping %d articles to %d (max_articles)",
                len(articles),
                max_articles,
            )

        for article in capped:
            combined = (
                f"{article.get('title', '')} {article.get('description', '')}"
            ).strip()
            try:
                all_events.extend(self.extract_events(combined))
            except Exception as exc:
                logger.warning("Event extraction failed for article: %s", exc)

            if self._settings.llm_enabled:
                llm_call_count += 1
                # Batch-level rate-limit: pause between batches to stay within
                # Groq free-tier TPM (6 000 tokens/min) and RPM limits.
                if llm_call_count % _LLM_BATCH_SIZE == 0:
                    time.sleep(_LLM_BATCH_SLEEP)

        # Deduplicate per-article by event_type (keep best confidence per article+type).
        # Do NOT deduplicate globally by event_type — that would collapse 30 articles
        # of military news into a single event, starving the cluster generator.
        best: Dict[tuple, Dict[str, Any]] = {}
        for ev in all_events:
            key = (ev.get("event_type", "other"), ev.get("title", "")[:_DEDUP_TITLE_PREFIX_LENGTH])
            if key not in best or ev.get("confidence", 0) > best[key].get("confidence", 0):
                best[key] = ev
        return list(best.values())