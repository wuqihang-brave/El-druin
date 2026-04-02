"""
intelligence/evented_pipeline.py
=================================
Three-stage evented reasoning pipeline for EL'druin.

Stage 1 – Event Extraction
    Rule-based extraction of Regulatory/Coercive and Kinetic events from text.
    If rule-based yields nothing, optionally falls back to an LLM that must
    output strict JSON.  LangChain-style prompt templates are NOT used; instead
    double-brace escaping is applied manually so no "missing variables" errors
    can arise.

Stage 2 – Pattern Derivation (deterministic)
    a) Active patterns  – event-type → relation_schema pattern lookup
    b) Derived patterns – semigroup composition via composition_table

Stage 3 – Conclusion + Credibility
    LLM is constrained to select/sort/explain among *candidate* patterns and
    cite event evidence.  Falls back to a deterministic summary when LLM is
    disabled.

Public entry-point
------------------
    run_evented_pipeline(text, llm_service=None) -> EventedPipelineResult
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event type constants
# ---------------------------------------------------------------------------

class EventType:
    # Regulatory / Coercive
    SANCTION_IMPOSED     = "sanction_imposed"
    SANCTION_LIFTED      = "sanction_lifted"
    EXPORT_CONTROL       = "export_control"
    ASSET_FREEZE         = "asset_freeze"
    LEGAL_REGULATORY     = "legal_regulatory_action"
    COERCIVE_WARNING     = "coercive_warning"
    # Kinetic
    MILITARY_STRIKE      = "military_strike"
    CLASHES              = "clashes"
    CEASEFIRE            = "ceasefire"
    MOBILIZATION         = "mobilization"
    WITHDRAWAL           = "withdrawal"


# ---------------------------------------------------------------------------
# Rule-based event extraction
# ---------------------------------------------------------------------------

_RULES: List[Dict[str, Any]] = [
    {
        "type": EventType.SANCTION_IMPOSED,
        "patterns": [
            r"\bsanction(?:ed|s|ing)\b",
            r"\bimpose[sd]?\s+(?:new\s+)?sanction",
            r"\bblackli(?:st|sted)\b",
            r"\bembargo\b",
            r"\beconomic\s+(?:penalty|penalties|restriction)",
        ],
        "confidence": 0.85,
    },
    {
        "type": EventType.SANCTION_LIFTED,
        "patterns": [
            r"\bsanction[s]?\s+(?:lifted|removed|eased|waived|suspended)",
            r"\blift(?:ed|ing)?\s+sanction",
            r"\bsanction\s+relief\b",
            r"\bnormaliz(?:e|ation)\b",
        ],
        "confidence": 0.85,
    },
    {
        "type": EventType.EXPORT_CONTROL,
        "patterns": [
            r"\bexport\s+control[s]?\b",
            r"\bexport\s+restriction[s]?\b",
            r"\bentity\s+list\b",
            r"\btech(?:nology)?\s+ban\b",
            r"\bchip\s+(?:ban|export|restriction)",
            r"\btechnology\s+(?:ban|restriction|denial)\b",
        ],
        "confidence": 0.85,
    },
    {
        "type": EventType.ASSET_FREEZE,
        "patterns": [
            r"\basset[s]?\s+fro(?:zen|ze)\b",
            r"\bfreez(?:e|ing)\s+(?:of\s+)?asset",
            r"\bseiz(?:e|ure|ing)\s+(?:of\s+)?asset",
        ],
        "confidence": 0.80,
    },
    {
        "type": EventType.LEGAL_REGULATORY,
        "patterns": [
            r"\blegal\s+action\b",
            r"\bregulatory\s+(?:action|measure|enforcement)\b",
            r"\bindictment\b",
            r"\bprosecution\b",
            r"\bfine[sd]?\s+\$?[\d,]+",
            r"\bcompliance\s+(?:order|requirement)\b",
        ],
        "confidence": 0.75,
    },
    {
        "type": EventType.COERCIVE_WARNING,
        "patterns": [
            r"\bthreaten(?:ed|s|ing)?\b",
            r"\bwarning[s]?\b",
            r"\bultimatum\b",
            r"\bcoercive\b",
            r"\bcross\s+(?:the\s+)?(?:red\s+)?line\b",
            r"\bdeadline\b.{0,30}\b(?:or|else|otherwise)\b",
        ],
        "confidence": 0.70,
    },
    {
        "type": EventType.MILITARY_STRIKE,
        "patterns": [
            r"\bair\s*strike[s]?\b",
            r"\bbombing\b",
            r"\bmissile[s]?\s+(?:attack|strike|launch)\b",
            r"\bdrone[s]?\s+(?:attack|strike)\b",
            r"\blaunch(?:ed|ing)?\s+(?:an?\s+)?attack",
            r"\bshell(?:ing|ed)\b",
            r"\bkilled\s+in\s+(?:an?\s+)?(?:air|military|drone)\b",
        ],
        "confidence": 0.88,
    },
    {
        "type": EventType.CLASHES,
        "patterns": [
            r"\bclash(?:es|ed)?\b",
            r"\bfighting\b",
            r"\bgunfire\b",
            r"\bskirmish(?:es)?\b",
            r"\bbattle[s]?\b",
            r"\boffensive\b",
            r"\bground\s+(?:assault|incursion|operation)\b",
        ],
        "confidence": 0.80,
    },
    {
        "type": EventType.CEASEFIRE,
        "patterns": [
            r"\bceasefire\b",
            r"\btruce\b",
            r"\barmistice\b",
            r"\bpeace\s+(?:deal|agreement|talks|process)\b",
            r"\bcease\s+fire\b",
            r"\bstop\s+(?:the\s+)?fighting\b",
        ],
        "confidence": 0.88,
    },
    {
        "type": EventType.MOBILIZATION,
        "patterns": [
            r"\bmobiliz(?:e|ation|ing)\b",
            r"\btroop[s]?\s+(?:deployment|deployed|massed)\b",
            r"\bmilitary\s+buildup\b",
            r"\bconscription\b",
            r"\bpartial\s+mobilization\b",
            r"\bsent\s+troops\b",
        ],
        "confidence": 0.80,
    },
    {
        "type": EventType.WITHDRAWAL,
        "patterns": [
            r"\bwithdraw(?:al|n|ing|s|drew)?\b",
            r"\bwithdrew\b",
            r"\bpull(?:ed|ing)?\s+(?:back|out|troops)\b",
            r"\bretreat(?:ed|ing)?\b",
            r"\btroops?\s+(?:out|leave|left|depart)",
        ],
        "confidence": 0.78,
    },
]

# Pre-compile regexes for performance
_COMPILED_RULES: List[Dict[str, Any]] = [
    {
        "type": rule["type"],
        "compiled": [re.compile(p, re.IGNORECASE) for p in rule["patterns"]],
        "confidence": rule["confidence"],
    }
    for rule in _RULES
]


def _extract_quote(text: str, match: re.Match, window: int = 80) -> str:
    """Return a short quote centred on the match."""
    start = max(0, match.start() - window // 2)
    end   = min(len(text), match.end() + window // 2)
    snippet = text[start:end].strip()
    # Collapse whitespace
    return re.sub(r"\s+", " ", snippet)


def _stable_id(event_type: str, quote: str) -> str:
    """Generate a stable short ID for an event within a request."""
    raw = f"{event_type}:{quote[:40]}"
    return hashlib.sha1(raw.encode()).hexdigest()[:8]


def extract_events_rule_based(text: str) -> List[Dict[str, Any]]:
    """
    Rule-based event extraction.

    Returns a list of event dicts with keys:
        id, type, args, evidence ({"quote": ...}), confidence
    """
    events: List[Dict[str, Any]] = []
    seen_ids: set = set()

    for rule in _COMPILED_RULES:
        for regex in rule["compiled"]:
            for m in regex.finditer(text):
                quote = _extract_quote(text, m)
                eid   = _stable_id(rule["type"], quote)
                if eid in seen_ids:
                    continue
                seen_ids.add(eid)
                events.append({
                    "id":       eid,
                    "type":     rule["type"],
                    "args":     {},
                    "evidence": {"quote": quote},
                    "confidence": rule["confidence"],
                })

    return events


def extract_events_llm(text: str, llm_service: Any) -> List[Dict[str, Any]]:
    """
    LLM fallback event extraction.  Prompt braces are escaped to avoid
    'missing variables {entities}'-style errors with template engines.
    Returns a list of event dicts (may be empty if parsing fails).
    """
    # Double-brace all literal braces so no template engine can misinterpret them
    focus_types = (
        "sanction_imposed, sanction_lifted, export_control, asset_freeze, "
        "legal_regulatory_action, coercive_warning, "
        "military_strike, clashes, ceasefire, mobilization, withdrawal"
    )
    prompt = (
        "You are an event-extraction engine.  Read the news text below and "
        "extract structured events.\n\n"
        f"NEWS TEXT:\n{text}\n\n"
        "Focus ONLY on these event types: " + focus_types + ".\n\n"
        "Output a JSON array.  Each element must have EXACTLY these keys:\n"
        '  "type"       : one of the event types listed above\n'
        '  "args"       : object with any relevant named arguments (actor, target, item, etc.)\n'
        '  "evidence"   : object with key "quote" containing a verbatim short quote from the text\n'
        '  "confidence" : float 0-1\n\n'
        "If no relevant events are found output an empty array: []\n"
        "Output ONLY the JSON array, no explanation."
    )
    try:
        raw = llm_service.call(
            prompt=prompt,
            system=(
                "You are a precise structured event extractor. "
                "Return ONLY a valid JSON array."
            ),
            temperature=0.0,
            max_tokens=1200,
        )
        text_resp = raw if isinstance(raw, str) else json.dumps(raw)
        start = text_resp.find("[")
        end   = text_resp.rfind("]")
        if start == -1 or end < start:
            return []
        parsed = json.loads(text_resp[start : end + 1])
        result = []
        for item in parsed:
            if not isinstance(item, dict) or "type" not in item:
                continue
            quote = item.get("evidence", {}).get("quote", text[:80])
            eid   = _stable_id(item["type"], quote)
            result.append({
                "id":       eid,
                "type":     item["type"],
                "args":     item.get("args", {}),
                "evidence": {"quote": quote},
                "confidence": float(item.get("confidence", 0.5)),
            })
        return result
    except Exception as exc:
        logger.warning("LLM event extraction failed: %s", exc)
        return []


def extract_events(
    text: str,
    llm_service: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    Primary event extraction entry-point.
    Tries rule-based first; if nothing found and llm_service is available,
    falls back to LLM.
    """
    events = extract_events_rule_based(text)
    if not events and llm_service is not None:
        logger.info("Rule-based extraction yielded 0 events; trying LLM fallback")
        events = extract_events_llm(text, llm_service)
    return events


# ---------------------------------------------------------------------------
# Lightweight entity typing (no DB write)
# ---------------------------------------------------------------------------

_ALLIANCE_KEYWORDS = frozenset([
    "eu", "nato", "asean", "g7", "g20", "au", "un", "arab league",
    "oas", "sco", "brics", "quad", "aukus", "five eyes",
])
_STATE_KEYWORDS = frozenset([
    "usa", "us", "uk", "china", "russia", "iran", "israel", "ukraine",
    "france", "germany", "japan", "india", "pakistan", "turkey", "brazil",
    "north korea", "south korea", "saudi arabia", "qatar", "egypt", "taiwan",
    "government", "ministry", "state", "country", "nation", "republic",
    "administration", "cabinet", "parliament", "congress", "senate",
    "president", "premier", "chancellor",
])
# Use word-boundary patterns to avoid substring false positives
# (e.g. "un" matching "samsung", "us" matching "musk")
_ALLIANCE_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(_ALLIANCE_KEYWORDS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_STATE_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(_STATE_KEYWORDS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_CORP_SUFFIXES = re.compile(
    r"\b(inc|ltd|corp|llc|gmbh|s\.a\.|plc|holdings?|group|co\.\s*ltd|co\.,?\s*inc)\b",
    re.IGNORECASE,
)
_TITLE_HINTS_EN = re.compile(
    r"\b(ceo|cfo|cto|chairman|president|minister|secretary|director|"
    r"general|admiral|senator|governor|ambassador|chancellor|premier|"
    r"prime\s+minister|foreign\s+minister|defence\s+minister)\b",
    re.IGNORECASE,
)
_TITLE_HINTS_ZH = re.compile(
    r"(总统|部长|主席|总理|总裁|创始人|首席执行官|外长|防长|CEO|总书记|省长|市长)",
)
_HAN_BLOCK = re.compile(r"[\u4e00-\u9fff]{2,4}")


def infer_entity_type_lightweight(name: str) -> str:
    """
    Infer a high-level entity type without any DB lookup.

    Returns one of: "person", "state", "alliance", "firm", "unknown".

    Word-boundary matching is used throughout to avoid false positives
    (e.g. "un" in "samsung", "us" in "musk").
    """
    if not name:
        return "unknown"

    # Alliance check (word-boundary regex)
    if _ALLIANCE_RE.search(name):
        return "alliance"

    # State / government check (word-boundary regex)
    if _STATE_RE.search(name):
        return "state"

    # Company suffix → firm
    if _CORP_SUFFIXES.search(name):
        return "firm"

    # Chinese person heuristic: 2-4 Han chars + nearby title hint
    if _HAN_BLOCK.fullmatch(name.strip()):
        # We only have the name, not surrounding context; mark as person
        return "person"

    # English person heuristic: Title Case 2-4 tokens, no corp suffix
    tokens = name.split()
    if 2 <= len(tokens) <= 4:
        all_title_case = all(
            len(t) >= 2 and t[0].isupper() and t[1:].islower()
            for t in tokens if t.isalpha()
        )
        if all_title_case and not _CORP_SUFFIXES.search(name):
            return "person"

    return "unknown"


# ---------------------------------------------------------------------------
# Event → Pattern mapping (deterministic)
# ---------------------------------------------------------------------------

# Maps (event_type, optional_entity_types) → pattern_name
# Priority: more-specific rules first (checked in order)
_EVENT_TO_PATTERN: List[Tuple[str, str]] = [
    # Regulatory / Coercive
    (EventType.SANCTION_IMPOSED,  "霸權制裁模式"),
    (EventType.SANCTION_LIFTED,   "制裁解除 / 正常化模式"),
    (EventType.EXPORT_CONTROL,    "實體清單技術封鎖模式"),
    (EventType.ASSET_FREEZE,      "金融孤立 / SWIFT 切斷模式"),
    (EventType.LEGAL_REGULATORY,  "跨國監管 / 合規約束模式"),
    (EventType.COERCIVE_WARNING,  "大國脅迫 / 威懾模式"),
    # Kinetic
    (EventType.MILITARY_STRIKE,   "國家間武力衝突模式"),
    (EventType.CLASHES,           "非國家武裝代理衝突模式"),
    (EventType.CEASEFIRE,         "停火 / 和平協議模式"),
    (EventType.MOBILIZATION,      "正式軍事同盟模式"),
    (EventType.WITHDRAWAL,        "外交讓步 / 去升級模式"),
]

_EVENT_TYPE_TO_PATTERN: Dict[str, str] = {
    event_type: pattern for event_type, pattern in _EVENT_TO_PATTERN
}


def derive_active_patterns(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deterministically map extracted events to relation_schema pattern names.

    Returns list of {"pattern": str, "from_event": str}.
    """
    active: List[Dict[str, Any]] = []
    seen: set = set()
    for evt in events:
        pattern = _EVENT_TYPE_TO_PATTERN.get(evt["type"])
        if pattern and pattern not in seen:
            seen.add(pattern)
            active.append({"pattern": pattern, "from_event": evt["id"]})
    return active


# ---------------------------------------------------------------------------
# Semigroup / Composition-based derived patterns
# ---------------------------------------------------------------------------

def derive_composed_patterns(
    active_patterns: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Apply composition_table to derive higher-order patterns.

    S_next = S ∪ {compose(a, b)} for all a, b in S.
    Returns list of {"derived": str, "rule": str, "inputs": [str, str]}.
    """
    try:
        from ontology.relation_schema import composition_table
    except ImportError:
        logger.warning("relation_schema not importable; skipping composition")
        return []

    active_names = [ap["pattern"] for ap in active_patterns]
    derived: List[Dict[str, Any]] = []
    seen: set = set(active_names)

    for a in active_names:
        for b in active_names:
            result = composition_table.get((a, b))
            if result and result not in seen:
                seen.add(result)
                derived.append({
                    "derived": result,
                    "rule":    f"compose({a},{b})->{result}",
                    "inputs":  [a, b],
                })

    return derived


# ---------------------------------------------------------------------------
# Conclusion generation (LLM constrained or deterministic fallback)
# ---------------------------------------------------------------------------

def generate_conclusion(
    text: str,
    events: List[Dict[str, Any]],
    active_patterns: List[Dict[str, Any]],
    derived_patterns: List[Dict[str, Any]],
    llm_service: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Stage 3a: Conclusion generation.

    LLM receives the event list and candidate patterns (active + derived)
    and must cite event evidence.  If LLM is disabled, returns a deterministic
    fallback summary.
    """
    all_candidates = (
        [ap["pattern"] for ap in active_patterns]
        + [dp["derived"] for dp in derived_patterns]
    )

    if not llm_service or not all_candidates:
        return _deterministic_conclusion(events, active_patterns, derived_patterns)

    # Build prompt (no template engine – manually construct the string)
    events_block = json.dumps(events, ensure_ascii=False, indent=2)
    patterns_block = json.dumps(
        {
            "active_patterns":  active_patterns,
            "derived_patterns": derived_patterns,
        },
        ensure_ascii=False,
        indent=2,
    )
    candidates_list = "\n".join(f"  - {c}" for c in all_candidates)

    prompt = (
        "You are a geopolitical intelligence analyst using an ontology-grounded "
        "reasoning system.\n\n"
        "NEWS TEXT:\n"
        f"{text}\n\n"
        "EXTRACTED EVENTS (with evidence quotes):\n"
        f"{events_block}\n\n"
        "CANDIDATE PATTERNS (active + derived):\n"
        f"{patterns_block}\n\n"
        "CANDIDATE PATTERN NAMES:\n"
        f"{candidates_list}\n\n"
        "TASK:\n"
        "1. Select the most plausible 1-3 patterns from the candidates above.\n"
        "2. For each selected pattern, cite the specific event ID that supports it.\n"
        "3. Write a 2-3 sentence conclusion explaining the geopolitical dynamic.\n"
        "4. Do NOT invent patterns outside the candidate list.\n\n"
        "Output strict JSON with keys:\n"
        '  "selected_patterns": [{"pattern": str, "supporting_event_id": str}]\n'
        '  "conclusion": str\n'
        '  "confidence": float 0-1\n\n'
        "Output ONLY the JSON object."
    )

    try:
        raw = llm_service.call(
            prompt=prompt,
            system=(
                "You are a rigorous geopolitical analyst. "
                "Select only from provided pattern candidates. "
                "Cite event evidence. Output only JSON."
            ),
            temperature=0.15,
            max_tokens=800,
        )
        text_resp = raw if isinstance(raw, str) else json.dumps(raw)
        start = text_resp.find("{")
        end   = text_resp.rfind("}")
        if start == -1 or end < start:
            raise ValueError("No JSON object found in LLM response")
        parsed = json.loads(text_resp[start : end + 1])
        return {
            "selected_patterns": parsed.get("selected_patterns", []),
            "conclusion":        parsed.get("conclusion", ""),
            "confidence":        float(parsed.get("confidence", 0.5)),
            "mode":              "llm_constrained",
        }
    except Exception as exc:
        logger.warning("LLM conclusion generation failed: %s", exc)
        return _deterministic_conclusion(events, active_patterns, derived_patterns)


def _deterministic_conclusion(
    events: List[Dict[str, Any]],
    active_patterns: List[Dict[str, Any]],
    derived_patterns: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Deterministic fallback when LLM is disabled or fails."""
    selected = [{"pattern": ap["pattern"], "supporting_event_id": ap["from_event"]}
                for ap in active_patterns[:3]]
    pattern_names = [ap["pattern"] for ap in active_patterns[:2]]
    derived_names = [dp["derived"] for dp in derived_patterns[:1]]

    if pattern_names:
        conclusion = (
            f"The text exhibits the following dynamics: {', '.join(pattern_names)}."
        )
        if derived_names:
            conclusion += (
                f" Compositional analysis further suggests: {', '.join(derived_names)}."
            )
    else:
        conclusion = (
            "No strong pattern signals detected. "
            "LLM analysis is disabled; deterministic fallback applied."
        )

    return {
        "selected_patterns": selected,
        "conclusion":        conclusion,
        "confidence":        0.40,
        "mode":              "deterministic_fallback",
    }


# ---------------------------------------------------------------------------
# Credibility assessment
# ---------------------------------------------------------------------------

# Scoring constants
_VERIFIABILITY_ANCHOR_COUNT = 3.0     # number of anchors for max verifiability score
_CONTRADICTION_PENALTY      = 0.3     # score deduction per contradicting pattern pair

_DATE_RE     = re.compile(
    r"\b(\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
    r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{4}|"
    r"\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})\b",
    re.IGNORECASE,
)
_URL_RE      = re.compile(r"https?://\S+", re.IGNORECASE)
_FILING_RE   = re.compile(
    r"\b(?:resolution|directive|case\s+no\.?|docket|ref\.?\s*(?:no\.?)?\s*[\w\-]+|"
    r"un\s+security\s+council\s+resolution\s+\d+|unsc\s+\d+)\b",
    re.IGNORECASE,
)
_INSTITUTION_RE = re.compile(
    r"\b(UN|NATO|EU|IMF|WTO|IAEA|World\s+Bank|Federal\s+Reserve|"
    r"US\s+Treasury|US\s+State\s+Department|European\s+Commission|"
    r"OFAC|BIS|Congress|Senate|Parliament|Ministry|Pentagon|Kremlin|"
    r"White\s+House)\b",
    re.IGNORECASE,
)

# Mutually inverse pattern pairs → activate both → contradiction signal
_CONTRADICTING_PAIRS: List[Tuple[str, str]] = [
    ("霸權制裁模式",              "制裁解除 / 正常化模式"),
    ("實體清單技術封鎖模式",      "技術許可 / 解禁模式"),
    ("國家間武力衝突模式",        "停火 / 和平協議模式"),
    ("非國家武裝代理衝突模式",    "代理武裝解除模式"),
    ("多邊聯盟制裁模式",          "多邊制裁解除模式"),
]


def compute_credibility(
    text: str,
    active_patterns: List[Dict[str, Any]],
    derived_patterns: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Compute a minimal credibility report.

    verifiability_score: 0-1, rule-based on verifiable anchor presence.
    kg_consistency_score: 0-1, based on absence of contradicting patterns.
    """
    # --- Verifiability ---
    has_date        = bool(_DATE_RE.search(text))
    has_url         = bool(_URL_RE.search(text))
    has_filing      = bool(_FILING_RE.search(text))
    has_institution = bool(_INSTITUTION_RE.search(text))

    anchors_present = sum([has_date, has_url, has_filing, has_institution])
    verifiability_score = min(1.0, anchors_present / _VERIFIABILITY_ANCHOR_COUNT)

    missing_evidence: List[str] = []
    if not has_date:
        missing_evidence.append("specific_date")
    if not has_institution:
        missing_evidence.append("named_institution_or_official_source")
    if not has_filing and not has_url:
        missing_evidence.append("official_document_or_url_reference")

    # --- KG Consistency ---
    active_names = {ap["pattern"] for ap in active_patterns}
    active_names |= {dp["derived"] for dp in derived_patterns}

    contradictions: List[str] = []
    for a, b in _CONTRADICTING_PAIRS:
        if a in active_names and b in active_names:
            contradictions.append(f"Contradicting co-activation: {a} + {b}")

    kg_consistency_score = max(0.0, 1.0 - _CONTRADICTION_PENALTY * len(contradictions))

    return {
        "verifiability_score":   round(verifiability_score, 3),
        "missing_evidence":      missing_evidence,
        "kg_consistency_score":  round(kg_consistency_score, 3),
        "contradictions":        contradictions,
        "supporting_paths":      [],   # populated by KG infra when available
    }


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

@dataclass
class EventedPipelineResult:
    events:           List[Dict[str, Any]] = field(default_factory=list)
    active_patterns:  List[Dict[str, Any]] = field(default_factory=list)
    derived_patterns: List[Dict[str, Any]] = field(default_factory=list)
    conclusion:       Dict[str, Any]       = field(default_factory=dict)
    credibility:      Dict[str, Any]       = field(default_factory=dict)


def run_evented_pipeline(
    text: str,
    llm_service: Optional[Any] = None,
) -> EventedPipelineResult:
    """
    Run the full three-stage evented reasoning pipeline.

    Args:
        text:        News text (title + summary or full article).
        llm_service: Optional LLM adapter with a `.call(prompt, ...)` method.

    Returns:
        EventedPipelineResult with events, active_patterns, derived_patterns,
        conclusion, and credibility.
    """
    logger.info("EventedPipeline: starting on %d chars", len(text))

    # Stage 1 – event extraction
    events = extract_events(text, llm_service=llm_service)
    logger.info("EventedPipeline: %d events extracted", len(events))

    # Stage 2a – active patterns
    active_patterns = derive_active_patterns(events)
    logger.info("EventedPipeline: %d active patterns", len(active_patterns))

    # Stage 2b – composed/derived patterns
    derived_patterns = derive_composed_patterns(active_patterns)
    logger.info("EventedPipeline: %d derived patterns", len(derived_patterns))

    # Stage 3a – conclusion
    conclusion = generate_conclusion(
        text, events, active_patterns, derived_patterns, llm_service
    )

    # Stage 3b – credibility
    credibility = compute_credibility(text, active_patterns, derived_patterns)

    return EventedPipelineResult(
        events=events,
        active_patterns=active_patterns,
        derived_patterns=derived_patterns,
        conclusion=conclusion,
        credibility=credibility,
    )
