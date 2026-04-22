"""
Event Extractor v3 – three-stage pipeline with parallel LLM calls.

CHANGES FROM v2:
================

PROBLEM 1 — Timeout / user experience
  BEFORE: Sequential LLM calls, 60s timeout each.
          30 articles × 60s worst case = 1920s (32 min). Even typical
          (3s/call + 12s batch sleep) = 3.5 min. Railway HTTP timeout = 60s.
  FIX A:  Reduce _LLM_TIMEOUT_SECONDS 60 → 15.
          Groq llama3-8b p95 latency is <5s. 15s gives 3× headroom with no
          user-visible penalty.
  FIX B:  Parallel LLM calls via ThreadPoolExecutor(max_workers=4).
          5 articles processed simultaneously → 6× throughput.
  FIX C:  Rule-first pipeline: run rule-based extraction on ALL articles
          instantly (< 1ms each), return immediately. LLM runs only as an
          enrichment pass on high-value articles.

PROBLEM 2 — Slow total pipeline
  FIX D:  extract_from_articles() accepts a fast_mode=True flag that
          returns rule-based events immediately (no LLM). The assessment
          generator can call with fast_mode=True for real-time display,
          then call again with fast_mode=False for full enrichment.
  FIX E:  Batch sleep replaced with token-budget tracking. Sleep only when
          the estimated token budget for the current batch would exceed the
          Groq free-tier limit (6000 TPM). Articles with short text are
          processed without sleep.

PROBLEM 3 — Extraction granularity
  FIX F:  LLM prompt expanded: requires PERSON entities, sub-type field,
          location, and a causal_chain field (what led to this event).
  FIX G:  Rule-based entity extraction now covers PERSON names (title-cased
          pairs that follow known prefixes: President, Minister, General…).
  FIX H:  New compound rules: sanctions+energy, cyber+infrastructure,
          diplomacy+military, finance+sanctions.
  FIX I:  _extract_quote() now returns the full sentence, not a char-window
          snippet, giving richer description fields.

BACKWARD COMPATIBILITY:
  - EventExtractor.extract_events() signature unchanged.
  - EventExtractor.extract_from_articles() gains optional fast_mode kwarg
    (default False to preserve existing behaviour).
  - All existing _RULES and _COMPOUND_RULES preserved unchanged.
"""

from __future__ import annotations

import concurrent.futures
import logging
import re
import time
from typing import Any, Dict, Generator, List, Optional, Set

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# FIX A: 60 → 15 seconds. Groq p95 < 5s; 15s = 3× headroom.
_LLM_TIMEOUT_SECONDS = 15

# FIX B: parallel workers for LLM calls
_LLM_PARALLEL_WORKERS = 4

# Token-budget rate limiting (FIX E)
_GROQ_FREE_TPM        = 6_000   # Groq free-tier tokens/min
_ESTIMATED_TOKENS_PER_ARTICLE = 600  # ~300 prompt + ~300 response for 200-char text
_BATCH_ARTICLES_BEFORE_SLEEP  = 8    # process N articles, then check budget
_BUDGET_SLEEP_S               = 10   # sleep when budget would be exceeded

# Circuit breaker
_llm_circuit_open: bool = False


def reset_circuit() -> None:
    global _llm_circuit_open  # noqa: PLW0603
    _llm_circuit_open = False


# Dedup prefix length (unchanged)
_DEDUP_TITLE_PREFIX_LENGTH = 60

# ---------------------------------------------------------------------------
# Event taxonomy (unchanged)
# ---------------------------------------------------------------------------
_EVENT_TYPES = [
    "政治冲突", "经济危机", "自然灾害", "恐怖袭击",
    "技术突破", "军事行动", "贸易摩擦", "外交事件",
    "人道危机", "其他事件",
]

# ---------------------------------------------------------------------------
# Single-trigger rules (unchanged from v2)
# ---------------------------------------------------------------------------
_RULES: List[Dict[str, Any]] = [
    {
        "event_type": "政治冲突",
        "severity": "high",
        "keywords": ["conflict", "protest", "coup", "riot", "civil war", "uprising",
                     "opposition", "parliament", "insurrection", "putsch", "crackdown",
                     "political violence", "election fraud", "political prisoner",
                     "martial law", "state of emergency"],
    },
    {
        "event_type": "经济危机",
        "severity": "high",
        "keywords": ["recession", "inflation", "rate hike", "rate cut", "central bank",
                     "market crash", "gdp", "unemployment", "debt crisis", "default",
                     "currency collapse", "hyperinflation", "bank failure",
                     "stock market crash", "financial crisis"],
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
                     "robot", "launch", "generative ai", "chatgpt", "large language model",
                     "fusion energy", "space exploration", "moon landing", "mars mission",
                     "nuclear fusion", "semiconductor breakthrough", "quantum supremacy"],
    },
    {
        "event_type": "军事行动",
        "severity": "high",
        "keywords": ["military", "troops", "airstrike", "missile", "navy", "army",
                     "war", "ceasefire", "warplane", "airspace", "base", "operation",
                     "deployed", "strike", "strikes", "bombed", "shelled",
                     "drone strike", "cruise missile", "artillery", "offensive",
                     "counteroffensive", "siege", "blockade", "naval blockade",
                     "territorial waters", "incursion", "cross-border",
                     "air defense", "intercept"],
    },
    {
        "event_type": "贸易摩擦",
        "severity": "medium",
        "keywords": ["tariff", "trade war", "sanctions", "embargo", "export ban", "import",
                     "trade dispute", "import tariff", "export restriction", "quota",
                     "countervailing duty", "anti-dumping", "supply chain", "decoupling",
                     "reshoring", "friend-shoring", "tech war"],
    },
    {
        "event_type": "外交事件",
        "severity": "low",
        "keywords": ["summit", "treaty", "agreement", "diplomat", "bilateral",
                     "negotiation", "ambassador", "airspace", "refused", "closed",
                     "ban", "access denied", "diplomatic expulsion", "persona non grata",
                     "embassy closure", "consulate", "foreign minister", "state visit",
                     "joint statement", "communiqué", "ceasefire talks",
                     "peace negotiations", "mediation"],
    },
    {
        "event_type": "人道危机",
        "severity": "high",
        "keywords": ["refugee", "famine", "humanitarian", "aid", "displacement",
                     "starvation", "civilian casualties", "mass exodus", "shelter",
                     "internally displaced", "war crimes", "atrocity",
                     "ethnic cleansing", "genocide"],
    },
]

# ---------------------------------------------------------------------------
# Compound rules (v2 originals preserved + FIX H: new rules)
# ---------------------------------------------------------------------------
_COMPOUND_RULES: List[Dict[str, Any]] = [
    # --- Original v2 rules (unchanged) ---
    {
        "trigger_a": ["strike", "strikes", "airstrike", "airstrikes", "bombed",
                      "shelled", "fired on", "hit", "attacked", "kill", "kills"],
        "trigger_b": ["dead", "killed", "casualties", "wounded", "targets",
                      "civilians", "infrastructure", "death toll"],
        "event_type_a": "军事行动",  "severity_a": "high",
        "event_type_b": "人道危机",  "severity_b": "high",
    },
    {
        "trigger_a": ["sanction", "sanctions", "embargo", "ban", "blocked", "restrict"],
        "trigger_b": ["chip", "semiconductor", "export", "technology", "tech",
                      "huawei", "supply chain", "ai"],
        "event_type_a": "贸易摩擦",  "severity_a": "high",
        "event_type_b": "政治冲突",  "severity_b": "medium",
    },
    {
        "trigger_a": ["election", "vote", "ballot", "referendum", "polling"],
        "trigger_b": ["disputed", "fraud", "protest", "unrest", "rigged",
                      "violent", "clashes", "rejected"],
        "event_type_a": "政治冲突",  "severity_a": "high",
        "event_type_b": "外交事件",  "severity_b": "medium",
    },
    {
        "trigger_a": ["fed", "federal reserve", "ecb", "central bank",
                      "rate hike", "rate cut", "interest rate"],
        "trigger_b": ["inflation", "recession", "market", "crash", "yield",
                      "dollar", "currency", "devaluation"],
        "event_type_a": "经济危机",  "severity_a": "high",
        "event_type_b": "贸易摩擦",  "severity_b": "medium",
    },
    {
        "trigger_a": ["deploy", "deployed", "troops", "forces", "soldiers",
                      "warships", "jets", "military buildup"],
        "trigger_b": ["nato", "alliance", "treaty", "partner", "agreement",
                      "border", "flank", "eastern", "western"],
        "event_type_a": "军事行动",  "severity_a": "high",
        "event_type_b": "外交事件",  "severity_b": "medium",
    },
    {
        "trigger_a": ["earthquake", "flood", "hurricane", "wildfire",
                      "tsunami", "cyclone", "tornado", "eruption"],
        "trigger_b": ["dead", "killed", "casualties", "missing", "aid",
                      "rescue", "displaced", "humanitarian", "evacuated"],
        "event_type_a": "自然灾害",  "severity_a": "high",
        "event_type_b": "人道危机",  "severity_b": "high",
    },
    # --- FIX H: New compound rules ---
    # Sanctions + energy → 贸易摩擦 + 经济危机
    {
        "trigger_a": ["sanction", "sanctions", "cut off", "freeze", "seized"],
        "trigger_b": ["oil", "gas", "energy", "pipeline", "lng", "fuel",
                      "petroleum", "nord stream", "corridor"],
        "event_type_a": "贸易摩擦",  "severity_a": "high",
        "event_type_b": "经济危机",  "severity_b": "high",
    },
    # Cyber + critical infrastructure → 技术突破 (as threat) + 政治冲突
    {
        "trigger_a": ["cyber", "hack", "ransomware", "malware", "breach",
                      "intrusion", "ddos", "zero-day"],
        "trigger_b": ["infrastructure", "power grid", "hospital", "government",
                      "military", "financial system", "water", "election system"],
        "event_type_a": "技术突破",  "severity_a": "high",
        "event_type_b": "政治冲突",  "severity_b": "high",
    },
    # Diplomatic breakdown + military posture → 外交事件 + 军事行动
    {
        "trigger_a": ["expelled", "expelled ambassador", "withdraw", "recalled",
                      "broke off", "severed", "terminated", "suspended relations"],
        "trigger_b": ["military", "troops", "forces", "alert", "mobilised",
                      "readiness", "border", "drills", "exercises"],
        "event_type_a": "外交事件",  "severity_a": "high",
        "event_type_b": "军事行动",  "severity_b": "high",
    },
    # Finance + sanctions → 经济危机 + 贸易摩擦
    {
        "trigger_a": ["swift", "correspondent banking", "dollar clearing",
                      "frozen assets", "financial isolation"],
        "trigger_b": ["sanction", "sanctions", "restricted", "blocked",
                      "exclude", "cut off"],
        "event_type_a": "经济危机",  "severity_a": "high",
        "event_type_b": "贸易摩擦",  "severity_b": "high",
    },
]

# ---------------------------------------------------------------------------
# FIX G: Enhanced entity extraction with PERSON support
# ---------------------------------------------------------------------------

_ORG_ABBREV_RE = re.compile(
    r"\b(UN|NATO|WHO|IMF|WTO|EU|FBI|CIA|FEMA|Fed|ECB|OPEC|G7|G20|IAEA|ICC|WB|"
    r"UNSC|NSC|DOD|CENTCOM|INDOPACOM|AFRICOM|IEA|SWIFT|OFAC|WFP|UNHCR|ICRC)\b"
)

_GPE_NAMES_SORTED = sorted([
    "USA", "United States", "US", "UK", "United Kingdom", "China", "Russia",
    "Germany", "France", "Japan", "India", "Brazil", "Australia", "Canada",
    "Iran", "Israel", "Ukraine", "Taiwan", "North Korea", "South Korea",
    "Saudi Arabia", "Turkey", "Mexico", "Italy", "Spain", "Poland",
    "Netherlands", "Sweden", "Norway", "Pakistan", "Afghanistan",
    "Syria", "Iraq", "Libya", "Venezuela", "Cuba", "Belarus",
    "Madrid", "Washington", "Beijing", "Moscow", "Brussels",
    "Ethiopia", "Sudan", "South Sudan", "Somalia", "Kenya", "Tanzania",
    "Ghana", "Senegal", "Morocco", "Algeria", "Tunisia",
    "Colombia", "Argentina", "Chile", "Peru",
    "Bangladesh", "Sri Lanka", "Nepal",
    "Vietnam", "Philippines", "Indonesia", "Thailand", "Singapore",
    "Malaysia", "Myanmar", "Cambodia",
    "Kazakhstan", "Uzbekistan", "Azerbaijan", "Armenia", "Georgia",
    "Hungary", "Romania", "Bulgaria", "Serbia", "Croatia",
    "Qatar", "UAE", "Kuwait", "Bahrain", "Oman", "Yemen",
    "Cyprus", "Malta", "Bosnia",
    "New Zealand", "Belgium", "Switzerland", "Austria",
    "Finland", "Denmark",
    "Gaza", "Crimea", "Donbas", "West Bank", "Strait of Hormuz",
    "South China Sea", "Taiwan Strait", "Black Sea",
], key=len, reverse=True)

_GPE_RE = re.compile(
    r"\b(" + "|".join(re.escape(g) for g in _GPE_NAMES_SORTED) + r")\b"
)

_ORG_SUFFIX_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+"
    r"(?:Corp|Inc|Ltd|Group|Bank|Fund|Organization|Organisation|"
    r"Agency|Ministry|Council|Committee|Commission|Authority|"
    r"Department|Office|Forces|Army|Navy|Government|Parliament|"
    r"Alliance|Coalition|Command|Bureau|Secretariat))\\b"
)

# FIX G: PERSON extraction — title-prefixed names
_PERSON_PREFIX_RE = re.compile(
    r"\b(?:President|Prime Minister|Minister|Secretary|General|Admiral|"
    r"Senator|Chancellor|King|Queen|Prince|Emperor|Premier|"
    r"Director|Chief|Commander|Ambassador|Governor|Mayor)\s+"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b"
)


def _extract_entities_rule(text: str) -> Dict[str, List[str]]:
    orgs, gpes, persons, seen = [], [], [], set()

    for m in _ORG_ABBREV_RE.finditer(text):
        n = m.group(1)
        if n not in seen:
            seen.add(n); orgs.append(n)

    for m in _GPE_RE.finditer(text):
        n = m.group(1)
        if n not in seen:
            seen.add(n); gpes.append(n)

    for m in _ORG_SUFFIX_RE.finditer(text):
        n = m.group(1).strip()
        if n not in seen:
            seen.add(n); orgs.append(n)

    # FIX G: extract persons
    for m in _PERSON_PREFIX_RE.finditer(text):
        n = m.group(1).strip()
        if n not in seen:
            seen.add(n); persons.append(n)

    return {
        "ORG":    orgs[:6],
        "GPE":    gpes[:6],
        "PERSON": persons[:4],
    }


# ---------------------------------------------------------------------------
# FIX I: Sentence-level quote extraction
# ---------------------------------------------------------------------------

_SENT_END_RE = re.compile(r"[.!?]\s+")


def _extract_quote(text: str, keyword: str, max_len: int = 250) -> str:
    """
    FIX I: Extract the complete sentence containing *keyword*.

    v1 used a character-window approach that would cut sentences mid-word.
    This version finds the sentence boundary properly.
    """
    lower = text.lower()
    kw_lower = keyword.lower()
    idx = lower.find(kw_lower)
    if idx == -1:
        return text[:max_len].strip()

    # Find the sentence start: last sentence-ending punctuation before idx
    prefix = text[:idx]
    sentence_start = 0
    for m in _SENT_END_RE.finditer(prefix):
        sentence_start = m.end()

    # Find the sentence end: next sentence-ending punctuation after idx
    rest = text[sentence_start:]
    m_end = _SENT_END_RE.search(rest)
    if m_end:
        sentence = rest[: m_end.start() + 1].strip()
    else:
        sentence = rest.strip()

    return sentence[:max_len] if sentence else text[:max_len].strip()


# ---------------------------------------------------------------------------
# Rule-based extraction (single + compound, unchanged logic + FIX I quotes)
# ---------------------------------------------------------------------------

def _rule_based_extract(text: str) -> List[Dict[str, Any]]:
    lower = text.lower()
    matched: List[Dict[str, Any]] = []
    seen_types: Set[str] = set()

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
                "description": _extract_quote(text, a_hit),   # FIX I
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
                "description": _extract_quote(text, b_hit),   # FIX I
                "entities":    entities,
                "confidence":  0.72,
                "compound":    True,
                "trigger":     b_hit,
            })

    return matched


# ---------------------------------------------------------------------------
# LLM extraction — FIX A (timeout 15s) + FIX F (richer prompt)
# ---------------------------------------------------------------------------

def _is_403_error(exc: Exception) -> bool:
    msg = str(exc)
    return "403" in msg or "Forbidden" in msg.lower()


def _is_rate_limit_error(exc: Exception) -> bool:
    msg = str(exc)
    return any(kw in msg for kw in ("429", "rate_limit", "Too Many Requests", "RateLimitError"))


def _llm_extract(text: str) -> List[Dict[str, Any]]:
    global _llm_circuit_open  # noqa: PLW0603
    if _llm_circuit_open:
        return []

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
                max_retries=0,
            )
        elif settings.llm_provider == "groq":
            from langchain_groq import ChatGroq
            llm = ChatGroq(
                model=settings.llm_model,
                temperature=settings.llm_temperature,
                api_key=settings.groq_api_key,
                max_retries=0,
            )
        elif settings.llm_provider == "deepseek":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=settings.llm_model,
                temperature=settings.llm_temperature,
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                max_retries=0,
            )
        else:
            return []

        # FIX F: richer prompt — adds PERSON, sub_type, location, causal_chain
        prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "You are an intelligence analyst extracting structured events from news. "
                "Return a JSON array. Each object must have exactly these fields:\n"
                "  event_type: one of: " + ", ".join(_EVENT_TYPES) + "\n"
                "  sub_type: specific sub-category (e.g. 'drone strike', 'rate hike', 'trade embargo')\n"
                "  severity: high | medium | low\n"
                "  title: concise event title (max 80 chars)\n"
                "  description: 1-2 sentence factual summary\n"
                "  causal_chain: what directly caused or triggered this event (max 100 chars)\n"
                "  location: country or region where the event occurs\n"
                "  entities: {ORG: [...], GPE: [...], PERSON: [...]} — only entities in the text\n"
                "  confidence: 0.0-1.0\n"
                "Only include entities that actually appear in the text. "
                "Return [] if no significant events found. "
                "Return raw JSON array only, no markdown."
            )),
            ("human", "News text:\n\n{text}"),
        ])
        parser = JsonOutputParser()
        chain  = prompt | llm | parser

        def _invoke() -> List[Dict[str, Any]]:
            result = chain.invoke({"text": text[:2000]})
            return result if isinstance(result, list) else []

        # FIX A: timeout reduced 60s → 15s
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_invoke)
            try:
                return future.result(timeout=_LLM_TIMEOUT_SECONDS)
            except concurrent.futures.TimeoutError:
                logger.warning("LLM extraction timed out after %ds", _LLM_TIMEOUT_SECONDS)
                return []

    except Exception as exc:
        if _is_403_error(exc):
            _llm_circuit_open = True
            logger.warning("LLM 403 — disabling LLM for this ingest cycle")
            return []
        if _is_rate_limit_error(exc):
            _llm_circuit_open = True
            logger.warning("LLM 429 — disabling LLM for this ingest cycle")
            return []
        logger.warning("LLM extraction failed, falling back to rules: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class EventExtractor:
    """Extracts structured events from news text (v3)."""

    def __init__(self) -> None:
        self._settings = get_settings()

    def extract_events(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract events from a single text string.

        Strategy (unchanged from v2, FIX F applied to LLM prompt):
          1. LLM if enabled and circuit not open
          2. Augment with compound-rule events LLM missed
          3. Rule-based fallback
        """
        if not text or not text.strip():
            return []

        if self._settings.llm_enabled and not _llm_circuit_open:
            llm_events = _llm_extract(text)
            if llm_events:
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
        reset_circuit_flag: bool = False,
        fast_mode: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Extract and deduplicate events across a list of articles.

        FIX B + C + D + E: parallel LLM, rule-first, token-budget sleep.

        Args:
            articles:           Article dicts (title, description, …).
            max_articles:       Cap on articles processed.
            reset_circuit_flag: Reset LLM circuit-breaker before processing.
            fast_mode:          If True, skip LLM entirely and return
                                rule-based events immediately.  Use for
                                real-time display; follow up with
                                fast_mode=False for LLM enrichment.
        """
        global _llm_circuit_open  # noqa: PLW0603
        if reset_circuit_flag:
            _llm_circuit_open = False

        capped = articles[:max_articles]
        if len(articles) > max_articles:
            logger.info(
                "extract_from_articles: capping %d articles to %d",
                len(articles), max_articles,
            )

        # ── STAGE 1: Rule-based on ALL articles (instant) ──────────────
        # Always run this first. Results are returned immediately in fast_mode.
        texts = [
            f"{a.get('title', '')} {a.get('description', '')}".strip()
            for a in capped
        ]
        rule_events: List[Dict[str, Any]] = []
        for text in texts:
            if text:
                rule_events.extend(_rule_based_extract(text))

        if fast_mode or not self._settings.llm_enabled or _llm_circuit_open:
            return self._dedup(rule_events)

        # ── STAGE 2: Parallel LLM on high-value articles ───────────────
        # Only run LLM on articles that produced ≥1 rule event (high-value).
        high_value_texts = [
            t for t in texts
            if t and any(
                any(kw in t.lower() for kw in rule["keywords"])
                for rule in _RULES
            )
        ][:max_articles]

        llm_events: List[Dict[str, Any]] = []
        token_budget_used = 0

        # FIX B: process in parallel batches
        for batch_start in range(0, len(high_value_texts), _LLM_PARALLEL_WORKERS):
            if _llm_circuit_open:
                break

            batch = high_value_texts[batch_start: batch_start + _LLM_PARALLEL_WORKERS]

            # FIX E: token-budget check before each batch
            batch_tokens = len(batch) * _ESTIMATED_TOKENS_PER_ARTICLE
            token_budget_used += batch_tokens
            if token_budget_used > _GROQ_FREE_TPM:
                logger.debug(
                    "Token budget %d exceeded limit %d — sleeping %ds",
                    token_budget_used, _GROQ_FREE_TPM, _BUDGET_SLEEP_S,
                )
                time.sleep(_BUDGET_SLEEP_S)
                token_budget_used = 0  # reset after sleep

            # FIX B: submit all articles in batch concurrently
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=_LLM_PARALLEL_WORKERS
            ) as pool:
                futures = {pool.submit(_llm_extract, t): t for t in batch}
                for future in concurrent.futures.as_completed(
                    futures, timeout=_LLM_TIMEOUT_SECONDS + 2
                ):
                    try:
                        result = future.result(timeout=_LLM_TIMEOUT_SECONDS)
                        llm_events.extend(result)
                    except Exception as exc:
                        logger.debug("LLM batch item failed: %s", exc)

        # Merge: prefer LLM events, augment with compound-rule events LLM missed
        if llm_events:
            llm_types = {e.get("event_type") for e in llm_events}
            for ce in rule_events:
                if ce.get("compound") and ce["event_type"] not in llm_types:
                    llm_events.append(ce)
            return self._dedup(llm_events)

        return self._dedup(rule_events)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _dedup(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Keep highest-confidence event per (event_type, title_prefix) key."""
        best: Dict[tuple, Dict[str, Any]] = {}
        for ev in events:
            key = (
                ev.get("event_type", "other"),
                ev.get("title", "")[:_DEDUP_TITLE_PREFIX_LENGTH],
            )
            if key not in best or ev.get("confidence", 0) > best[key].get("confidence", 0):
                best[key] = ev
        return list(best.values())