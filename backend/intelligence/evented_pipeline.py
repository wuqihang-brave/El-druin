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
    # Business / Tech / Product Strategy
    MARKET_ENTRY              = "market_entry"
    PRODUCT_FEATURE_LAUNCH    = "product_feature_launch"
    COMPETITIVE_POSITIONING   = "competitive_positioning"
    PLATFORM_STRATEGY         = "platform_strategy"
    # Space / Technology
    SPACE_MISSION             = "space_mission"


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
    # Business / Tech / Product Strategy
    {
        "type": EventType.MARKET_ENTRY,
        "patterns": [
            r"\bexpand(?:ing|s|ed)?\s+into\b",
            r"\bentering?\s+(?:the\s+)?(?:new\s+)?market\b",
            r"\blaunch(?:es|ed|ing)?\s+in\b",
            r"\broll(?:s|ed|ing)?\s+out\b",
            r"\bintroduc(?:e|es|ed|ing)\s+(?:new\s+)?(?:service|product|offering|feature)\b",
            r"\bexpand(?:s|ed|ing)?\s+(?:its\s+)?(?:service|platform|product|offering)\b",
            r"\benters?\s+(?:the\s+)?(?:space|sector|market|arena|industry)\b",
            r"\bmov(?:e|es|ed|ing)\s+into\s+(?:the\s+)?(?:new\s+)?market\b",
        ],
        "confidence": 0.80,
    },
    {
        "type": EventType.PRODUCT_FEATURE_LAUNCH,
        "patterns": [
            r"\blaunch(?:es|ed|ing)?\s+(?:new\s+)?(?:product|feature|service|tool|app|platform)\b",
            r"\bannounce(?:s|d|ing)?\s+(?:new\s+)?(?:product|feature|service|offering)\b",
            r"\breleas(?:e|es|ed|ing)?\s+(?:new\s+)?(?:product|feature|version|update)\b",
            r"\bintroduc(?:e|es|ed|ing)\s+(?:new\s+)?(?:product|feature|service|tool)\b",
            r"\bdebut(?:s|ed|ing)?\b",
            r"\bunveil(?:s|ed|ing)?\b",
            r"\broll(?:s|ed|ing)\s+out\s+(?:new\s+)?(?:feature|service|product)\b",
            r"\bpilot(?:s|ed|ing)?\s+(?:new\s+)?(?:program|feature|service)\b",
        ],
        "confidence": 0.78,
    },
    {
        "type": EventType.COMPETITIVE_POSITIONING,
        "patterns": [
            r"\btake(?:s|n)?\s+aim\s+at\b",
            r"\bchalleng(?:e|es|ed|ing)\s+(?:the\s+)?(?:dominan|incumbent|rival|leader)\b",
            r"\brival(?:s|ed|ing|ling)?\b",
            r"\bcompet(?:e|es|ed|ing|ition|itor)\b",
            r"\bdisrupt(?:s|ed|ing|or|ive)?\b",
            r"\bchalleng(?:e|es|er)\s+to\b",
            r"\bvs\.\s+\w+|versus\s+\w+",
            r"\bgain(?:s|ed|ing)?\s+(?:market\s+)?share\b",
            r"\bovert(?:ake|akes|aking|ook)\b",
            r"\balternative\s+to\b",
        ],
        "confidence": 0.72,
    },
    {
        "type": EventType.PLATFORM_STRATEGY,
        "patterns": [
            r"\bplatform\s+(?:strateg|expan|ecosys|monetiz|business)\b",
            r"\becosystem\b",
            r"\bmonetiz(?:e|es|ed|ing|ation)\b",
            r"\bsubscription\s+(?:model|business|tier|plan|revenue)\b",
            r"\bcreator\s+(?:economy|platform|tool|monetiz)\b",
            r"\bmarketplace\b",
            r"\bconsolidat(?:e|es|ed|ing|ion)\b",
            r"\bvertical\s+integrat(?:e|ion)\b",
            r"\bbundl(?:e|es|ed|ing)\b",
        ],
        "confidence": 0.72,
    },
    # Space / Technology breakthrough
    {
        "type": EventType.SPACE_MISSION,
        "patterns": [
            r"\borbit(?:s|ed|ing|al)?\b",
            r"\bastronauts?\b",
            r"\b(?:NASA|ESA|JAXA|SpaceX|Roscosmos|ISRO)\b",
            r"\blaunch(?:es|ed|ing)?\s+(?:a\s+)?(?:rocket|spacecraft|satellite|probe|mission)\b",
            r"\blunar\b",
            r"\bmoon\s+(?:mission|landing|orbit|probe)\b",
            r"\brocket\s+(?:launch|test|engine)\b",
            r"\bspacecraft\b",
            r"\bsatellite\s+(?:launch|deploy|orbit)\b",
            r"\bspace\s+(?:station|mission|launch|exploration|agency)\b",
            r"\bliftoff\b",
            r"\bsplashdown\b",
            r"\binterplanetary\b",
        ],
        "confidence": 0.82,
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


# ---------------------------------------------------------------------------
# Event post-processing constants and helpers
# ---------------------------------------------------------------------------

_MIN_QUOTE_LEN    = 10     # minimum meaningful evidence quote length (chars)
_T0_CONF_THRESHOLD = 0.2   # below this (after folding) → reject (T0)
_T2_CONF_THRESHOLD = 0.7   # at or above this (+ no inferred_fields) → T2
_ACTOR_TARGET_KEYS = frozenset(["actor", "target"])

# Trigger keywords per event type – used to validate evidence quotes.
# If the quote contains none of these keywords the confidence is penalised.
_EVENT_TRIGGER_KEYWORDS: Dict[str, List[str]] = {
    EventType.SANCTION_IMPOSED:  ["sanction", "blacklist", "embargo", "restrict", "penalt"],
    EventType.SANCTION_LIFTED:   ["lift", "ease", "remov", "relief", "normaliz", "sanction"],
    EventType.EXPORT_CONTROL:    ["export", "control", "restrict", "ban", "chip", "entity list"],
    EventType.ASSET_FREEZE:      ["asset", "frozen", "freeze", "seize"],
    EventType.LEGAL_REGULATORY:  ["legal", "regulat", "fine", "prosecution", "compliance", "indictment"],
    EventType.COERCIVE_WARNING:  ["threat", "warn", "ultimatum", "coercive", "deadline", "line"],
    EventType.MILITARY_STRIKE:   ["strike", "bombing", "missile", "attack", "shell", "drone", "air"],
    EventType.CLASHES:           ["clash", "fight", "battle", "gunfire", "offensive", "skirmish"],
    EventType.CEASEFIRE:         ["ceasefire", "truce", "peace", "armistice", "cease"],
    EventType.MOBILIZATION:      ["mobiliz", "troop", "buildup", "deployment", "conscription"],
    EventType.WITHDRAWAL:        ["withdraw", "retreat", "pull"],
    # Business / Tech
    EventType.MARKET_ENTRY:           ["expand", "enter", "launch", "roll out", "introduc", "mov"],
    EventType.PRODUCT_FEATURE_LAUNCH: ["launch", "announc", "releas", "introduc", "debut", "unveil", "pilot", "roll"],
    EventType.COMPETITIVE_POSITIONING:["compet", "rival", "challenge", "disrupt", "share", "overtake", "alternative", "vs"],
    EventType.PLATFORM_STRATEGY:      ["platform", "ecosystem", "monetiz", "subscription", "creator", "marketplace", "bundl", "consolidat"],
    EventType.SPACE_MISSION:          ["orbit", "astronaut", "NASA", "ESA", "SpaceX", "lunar", "moon", "rocket", "spacecraft", "satellite", "space", "liftoff"],
}

# T1 weak / generic pattern overrides – used when an event is tiered T1 to
# avoid activating strong (kinetic) patterns on low-confidence evidence.
_T1_WEAK_PATTERNS: Dict[str, str] = {
    EventType.SANCTION_IMPOSED:  "政策性貿易限制模式",
    EventType.SANCTION_LIFTED:   "政策性貿易限制模式",
    EventType.EXPORT_CONTROL:    "政策性貿易限制模式",
    EventType.ASSET_FREEZE:      "潛在強制信號模式",
    EventType.LEGAL_REGULATORY:  "潛在強制信號模式",
    EventType.COERCIVE_WARNING:  "潛在強制信號模式",
    EventType.MILITARY_STRIKE:   "潛在強制信號模式",
    EventType.CLASHES:           "潛在強制信號模式",
    EventType.CEASEFIRE:         "政策性貿易限制模式",
    EventType.MOBILIZATION:      "潛在強制信號模式",
    EventType.WITHDRAWAL:        "政策性貿易限制模式",
    # Business / Tech weak patterns
    EventType.MARKET_ENTRY:            "產品能力擴張模式",
    EventType.PRODUCT_FEATURE_LAUNCH:  "產品能力擴張模式",
    EventType.COMPETITIVE_POSITIONING: "平台競爭 / 生態位擴張模式",
    EventType.PLATFORM_STRATEGY:       "創作者經濟整合模式",
    EventType.SPACE_MISSION:           "技術突破 / 太空探索模式",
}


def _quote_has_trigger(quote: str, event_type: str) -> bool:
    """Return True if the evidence quote contains a trigger keyword for *event_type*.

    If the event type is unknown (no keywords defined) we return True to avoid
    penalising events whose type is outside our fixed vocabulary.
    """
    keywords = _EVENT_TRIGGER_KEYWORDS.get(event_type, [])
    if not keywords:
        return True
    q_lower = quote.lower()
    return any(kw in q_lower for kw in keywords)


def postprocess_events(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Post-process candidate events: filter (T0), normalise, tier, fold confidence.

    Filtering (T0 – rejected, dropped)
    ------------------------------------
    An event is rejected (T0) if ANY of the following hold:
      - ``confidence <= 0``
      - ``evidence.quote`` is missing or empty
      - ``confidence < _T0_CONF_THRESHOLD`` (before *or* after folding)

    Exception to quote-length rule: if the event type has strong trigger
    keywords present in the source text, a short quote is tolerated but
    the event is downgraded to tier T1 and a verification_gap entry is added.

    Normalisation
    -------------
    - Strip whitespace from ``type`` and all string values in ``args``.
    - De-duplicate: the first occurrence with a given stable ID is kept.

    Confidence folding
    ------------------
    Applied in order *after* the initial T0 check:
      1. ``inferred_fields`` non-empty → multiply by 0.7
      2. ``actor`` or ``target`` among inferred_fields → additional × 0.8
      3. Evidence quote lacks trigger keywords for the event type → × 0.7

    After folding, events whose confidence drops below ``_T0_CONF_THRESHOLD``
    are also rejected.

    Tiering
    -------
    - T2 (grounded): ``confidence >= _T2_CONF_THRESHOLD`` **and** ``inferred_fields`` empty.
    - T1 (hypothesis): everything else that survives the T0 filter.

    New fields added to each surviving event
    ----------------------------------------
    ``tier``                "T1" | "T2"
    ``inferred_fields``     list[str]  (may be empty)
    ``inference_rationale`` str        (<= 200 chars)
    ``verification_gap``    list[str]
    """
    result: List[Dict[str, Any]] = []
    seen_ids: set = set()

    for _evt in candidates:
        evt = dict(_evt)  # shallow copy to avoid mutating caller's data

        # --- Normalisation: strip whitespace ---
        evt["type"] = (evt.get("type") or "").strip()
        evidence = evt.get("evidence")
        if isinstance(evidence, dict):
            q = (evidence.get("quote") or "").strip()
            evt["evidence"] = dict(evidence)
            evt["evidence"]["quote"] = q
        else:
            evt["evidence"] = {"quote": ""}
            q = ""
        args = evt.get("args", {})
        if isinstance(args, dict):
            evt["args"] = {
                k: (v.strip() if isinstance(v, str) else v)
                for k, v in args.items()
            }

        confidence = float(evt.get("confidence", 0.0))

        # --- Initial T0 check: reject zero/negative confidence or empty quote ---
        if confidence <= 0 or not q:
            continue
        if confidence < _T0_CONF_THRESHOLD:
            continue

        # --- Inference metadata ---
        inferred_fields: List[str] = list(evt.get("inferred_fields") or [])
        inference_rationale: str = str(evt.get("inference_rationale") or "")[:200]
        verification_gap: List[str] = list(evt.get("verification_gap") or [])

        # --- Short-quote handling: keep as T1 with verification_gap ---
        force_t1_short_quote = False
        if len(q) < _MIN_QUOTE_LEN:
            # Keep only when strong trigger is present in the quote
            if _quote_has_trigger(q, evt["type"]):
                force_t1_short_quote = True
                verification_gap = list(verification_gap)
                if "need more context: quote too short for full verification" not in verification_gap:
                    verification_gap.append(
                        "need more context: quote too short for full verification"
                    )
            else:
                continue  # reject: short quote with no trigger

        # --- Confidence folding ---
        if inferred_fields:
            confidence *= 0.7
            if any(k in _ACTOR_TARGET_KEYS for k in inferred_fields):
                confidence *= 0.8
        if not _quote_has_trigger(q, evt["type"]):
            confidence *= 0.7

        confidence = round(min(1.0, max(0.0, confidence)), 4)

        # --- Post-folding T0 check ---
        if confidence < _T0_CONF_THRESHOLD:
            continue

        # --- Tiering ---
        if force_t1_short_quote:
            tier = "T1"
        else:
            tier = "T2" if (confidence >= _T2_CONF_THRESHOLD and not inferred_fields) else "T1"

        evt["confidence"] = confidence
        evt["tier"] = tier
        evt["inferred_fields"] = inferred_fields
        evt["inference_rationale"] = inference_rationale
        evt["verification_gap"] = verification_gap

        # --- De-duplication ---
        eid = evt.get("id") or _stable_id(evt["type"], q)
        if eid in seen_ids:
            continue
        seen_ids.add(eid)
        evt["id"] = eid

        result.append(evt)

    return result


def _extract_quote(text: str, match: re.Match, window: int = 80) -> str:
    """Return a short quote centred on the match.

    Guarantees a non-empty result by using the matched text itself as the
    fallback when context expansion produces an empty string.
    """
    start = max(0, match.start() - window // 2)
    end   = min(len(text), match.end() + window // 2)
    snippet = text[start:end].strip()
    # Collapse whitespace
    snippet = re.sub(r"\s+", " ", snippet)
    # Fallback: always return at least the matched text
    if not snippet:
        snippet = match.group(0)
    return snippet


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
        "military_strike, clashes, ceasefire, mobilization, withdrawal, "
        "market_entry, product_feature_launch, competitive_positioning, "
        "platform_strategy, space_mission"
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
    falls back to LLM.  Compound multi-event rules are always applied to
    supplement extracted candidates.  Candidate events are always
    post-processed (tiered, filtered, normalised) before being returned.
    """
    candidates = extract_events_rule_based(text)
    if not candidates and llm_service is not None:
        logger.info("Rule-based extraction yielded 0 events; trying LLM fallback")
        candidates = extract_events_llm(text, llm_service)
    # Supplement with compound rules (always deterministic, no LLM needed)
    compound = _apply_compound_rules(text, candidates)
    # Merge compound events that aren't already covered
    existing_types = {e["type"] for e in candidates}
    for evt in compound:
        if evt["type"] not in existing_types:
            candidates.append(evt)
            existing_types.add(evt["type"])
    return postprocess_events(candidates)


# ---------------------------------------------------------------------------
# Compound multi-event rules
# ---------------------------------------------------------------------------

# Co-occurrence trigger sets: when multiple trigger sets are all present in
# text, generate synthetic supplemental events to ensure distinct event types.
_COMPOUND_RULES: List[Dict[str, Any]] = [
    # Market entry + competitive positioning → generate both if only one detected
    {
        "requires_any": [EventType.MARKET_ENTRY, EventType.PRODUCT_FEATURE_LAUNCH],
        "if_text_matches": [
            r"\bcompet\w*\b",
            r"\brival\w*\b",
            r"\balternative\s+to\b",
            r"\btake\s+aim\b",
        ],
        "emit": EventType.COMPETITIVE_POSITIONING,
        "confidence": 0.65,
    },
    # Platform strategy + product launch → emit platform_strategy
    {
        "requires_any": [EventType.PRODUCT_FEATURE_LAUNCH, EventType.MARKET_ENTRY],
        "if_text_matches": [
            r"\bmonetiz\w*\b",
            r"\bsubscription\b",
            r"\bcreator\s+economy\b",
            r"\bplatform\b",
            r"\becosystem\b",
        ],
        "emit": EventType.PLATFORM_STRATEGY,
        "confidence": 0.65,
    },
    # Sanction + export_control → compound tech decoupling signal
    {
        "requires_any": [EventType.SANCTION_IMPOSED, EventType.EXPORT_CONTROL],
        "if_text_matches": [
            r"\btrade\s+war\b",
            r"\bdecoupl\w*\b",
            r"\bchip\b",
            r"\bsemiconductor\b",
        ],
        "emit": EventType.EXPORT_CONTROL,
        "confidence": 0.75,
    },
]

_COMPOUND_RULE_COMPILED: List[Dict[str, Any]] = [
    {
        **rule,
        "if_text_compiled": [re.compile(p, re.IGNORECASE) for p in rule["if_text_matches"]],
    }
    for rule in _COMPOUND_RULES
]


def _apply_compound_rules(
    text: str,
    existing_candidates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Apply compound multi-event rules to supplement rule-based extraction.

    Returns additional candidate events (may be empty).  Each emitted event
    has the required evented fields: id, type, args, evidence.quote, confidence.
    """
    existing_types = {e["type"] for e in existing_candidates}
    added: List[Dict[str, Any]] = []

    for rule in _COMPOUND_RULE_COMPILED:
        # Skip if emit type already present
        if rule["emit"] in existing_types:
            continue
        # Check that at least one required event type is present
        if not any(t in existing_types for t in rule["requires_any"]):
            continue
        # Check that at least one text pattern matches
        for compiled_re in rule["if_text_compiled"]:
            m = compiled_re.search(text)
            if m:
                quote = _extract_quote(text, m)
                eid = _stable_id(rule["emit"], quote)
                added.append({
                    "id":         eid,
                    "type":       rule["emit"],
                    "args":       {},
                    "evidence":   {"quote": quote},
                    "confidence": rule["confidence"],
                })
                break  # only emit once per rule

    return added


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
    # Business / Tech / Product Strategy
    (EventType.MARKET_ENTRY,            "產品能力擴張模式"),
    (EventType.PRODUCT_FEATURE_LAUNCH,  "產品能力擴張模式"),
    (EventType.COMPETITIVE_POSITIONING, "平台競爭 / 生態位擴張模式"),
    (EventType.PLATFORM_STRATEGY,       "創作者經濟整合模式"),
    (EventType.SPACE_MISSION,           "技術突破 / 太空探索模式"),
]

_EVENT_TYPE_TO_PATTERN: Dict[str, str] = {
    event_type: pattern for event_type, pattern in _EVENT_TO_PATTERN
}


def derive_active_patterns(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deterministically map extracted events to relation_schema pattern names.

    Events tiered T1 are mapped to generic/weak placeholder patterns to avoid
    activating strong kinetic patterns on low-confidence or inferred evidence.

    If an event has no ``tier`` field (e.g. raw rule-based output passed
    directly in tests), the tier is inferred from ``confidence``.

    Returns a list of dicts with keys:
        pattern, from_event, tier, inferred, confidence
    """
    active: List[Dict[str, Any]] = []
    seen: set = set()
    for evt in events:
        confidence = float(evt.get("confidence", 0.5))
        evt_tier = evt.get("tier")
        # Backward-compat: infer tier when not set
        if evt_tier is None:
            evt_tier = "T2" if confidence >= _T2_CONF_THRESHOLD else "T1"
        inferred = bool(evt.get("inferred_fields"))

        if evt_tier == "T1":
            pattern = (
                _T1_WEAK_PATTERNS.get(evt["type"])
                or _EVENT_TYPE_TO_PATTERN.get(evt["type"])
            )
        else:
            pattern = _EVENT_TYPE_TO_PATTERN.get(evt["type"])

        if pattern:
            pattern = pattern.strip()
            if pattern not in seen:
                seen.add(pattern)
                active.append({
                    "pattern":    pattern,
                    "from_event": evt["id"],
                    "tier":       evt_tier,
                    "inferred":   inferred,
                    "confidence": round(confidence, 4),
                })
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

    Returns list of dicts with keys:
        derived, rule, inputs,
        derived_tier, derived_inferred, derived_confidence
    """
    try:
        from ontology.relation_schema import composition_table
    except ImportError:
        logger.warning("relation_schema not importable; skipping composition")
        return []

    # Build per-pattern metadata lookup
    pattern_meta: Dict[str, Dict[str, Any]] = {}
    for ap in active_patterns:
        name = ap["pattern"].strip()
        pattern_meta[name] = {
            "tier":       ap.get("tier", "T2"),
            "inferred":   bool(ap.get("inferred", False)),
            "confidence": float(ap.get("confidence", 0.5)),
        }

    active_names = list(pattern_meta.keys())
    derived: List[Dict[str, Any]] = []
    seen: set = set(active_names)

    for a in active_names:
        for b in active_names:
            comp_result = composition_table.get((a, b))
            if comp_result and comp_result not in seen:
                seen.add(comp_result)
                meta_a = pattern_meta.get(a, {})
                meta_b = pattern_meta.get(b, {})
                conf_a = float(meta_a.get("confidence", 0.5))
                conf_b = float(meta_b.get("confidence", 0.5))
                derived_inferred = (
                    meta_a.get("inferred", False) or meta_b.get("inferred", False)
                )
                # Confidence composition: min(A, B) * 0.9; penalty if any input inferred
                derived_conf = min(conf_a, conf_b) * 0.9
                if derived_inferred:
                    derived_conf *= 0.8
                derived_conf = round(derived_conf, 4)
                # Derived tier: T1 if either input is T1 or confidence < threshold
                input_t1 = (
                    meta_a.get("tier") == "T1" or meta_b.get("tier") == "T1"
                )
                derived_tier = (
                    "T1"
                    if (input_t1 or derived_conf < _T2_CONF_THRESHOLD or derived_inferred)
                    else "T2"
                )
                derived.append({
                    "derived":            comp_result,
                    "rule":               f"compose({a},{b})->{comp_result}",
                    "inputs":             [a, b],
                    "derived_tier":       derived_tier,
                    "derived_inferred":   derived_inferred,
                    "derived_confidence": derived_conf,
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
    Stage 3a: Conclusion generation with forced dual-path output.

    Dual-path structure
    -------------------
    ``evidence_path``   – based only on T2 patterns/events (grounded).
    ``hypothesis_path`` – may draw on T1 evidence; must list verification gaps.

    The LLM receives the event list and candidate patterns (active + derived)
    and must cite event evidence.  If LLM is disabled, returns a deterministic
    fallback summary.
    """
    all_candidates = (
        [ap["pattern"] for ap in active_patterns]
        + [dp["derived"] for dp in derived_patterns]
    )

    if not llm_service or not all_candidates:
        return _deterministic_conclusion(events, active_patterns, derived_patterns)

    # Separate T2 (grounded) from T1 (hypothesis) patterns for the dual-path prompt
    t2_patterns = [ap for ap in active_patterns if ap.get("tier", "T2") == "T2"]
    t1_patterns = [ap for ap in active_patterns if ap.get("tier", "T2") == "T1"]
    t2_derived  = [dp for dp in derived_patterns if dp.get("derived_tier", "T2") == "T2"]
    t1_derived  = [dp for dp in derived_patterns if dp.get("derived_tier", "T2") == "T1"]

    # Aggregate verification gaps from all events
    all_gaps: List[str] = []
    for evt in events:
        all_gaps.extend(evt.get("verification_gap", []))

    events_block   = json.dumps(events, ensure_ascii=False, indent=2)
    t2_block       = json.dumps({"t2_active": t2_patterns, "t2_derived": t2_derived},
                                ensure_ascii=False, indent=2)
    t1_block       = json.dumps({"t1_active": t1_patterns, "t1_derived": t1_derived},
                                ensure_ascii=False, indent=2)
    candidates_list = "\n".join(f"  - {c}" for c in all_candidates)

    prompt = (
        "You are a geopolitical intelligence analyst using an ontology-grounded "
        "reasoning system.\n\n"
        "NEWS TEXT:\n"
        f"{text}\n\n"
        "EXTRACTED EVENTS (with evidence quotes and tiers):\n"
        f"{events_block}\n\n"
        "T2 GROUNDED PATTERNS (high-confidence, no inferred args):\n"
        f"{t2_block}\n\n"
        "T1 HYPOTHESIS PATTERNS (lower-confidence or inferred args):\n"
        f"{t1_block}\n\n"
        "CANDIDATE PATTERN NAMES (for reference):\n"
        f"{candidates_list}\n\n"
        "TASK:\n"
        "Produce a dual-path analysis:\n"
        "1. evidence_path: Use ONLY T2 grounded patterns/events. "
        "Select 1-3 patterns, cite specific event IDs.\n"
        "2. hypothesis_path: May use T1 patterns and events. "
        "Must list at least one verification_gap explaining what additional "
        "evidence would upgrade this to grounded.\n"
        "3. Write a 2-3 sentence conclusion synthesising both paths.\n"
        "4. Do NOT invent patterns outside the candidate list.\n\n"
        "Output strict JSON with keys:\n"
        '  "evidence_path": {"patterns": [{"pattern": str, "supporting_event_id": str}], '
        '"summary": str}\n'
        '  "hypothesis_path": {"patterns": [{"pattern": str, "supporting_event_id": str}], '
        '"summary": str, "verification_gaps": [str]}\n'
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
            max_tokens=1000,
        )
        text_resp = raw if isinstance(raw, str) else json.dumps(raw)
        start = text_resp.find("{")
        end   = text_resp.rfind("}")
        if start == -1 or end < start:
            raise ValueError("No JSON object found in LLM response")
        parsed = json.loads(text_resp[start : end + 1])
        evidence_path   = parsed.get("evidence_path", {})
        hypothesis_path = parsed.get("hypothesis_path", {})
        conclusion_text = parsed.get("conclusion", "")
        # Back-compat: selected_patterns = evidence_path patterns + hypothesis_path patterns
        selected = (
            evidence_path.get("patterns", []) + hypothesis_path.get("patterns", [])
        )
        return {
            "selected_patterns": selected,
            "conclusion":        conclusion_text,
            "confidence":        float(parsed.get("confidence", 0.5)),
            "mode":              "llm_constrained",
            "evidence_path":     evidence_path,
            "hypothesis_path":   hypothesis_path,
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
    t2_active = [ap for ap in active_patterns if ap.get("tier", "T2") == "T2"]
    t1_active = [ap for ap in active_patterns if ap.get("tier", "T2") == "T1"]

    # Build evidence_path from T2 patterns
    evidence_selected = [
        {"pattern": ap["pattern"], "supporting_event_id": ap["from_event"]}
        for ap in t2_active[:3]
    ]
    evidence_summary = (
        "Grounded evidence supports: " + ", ".join(ap["pattern"] for ap in t2_active[:2])
        if t2_active else "No grounded (T2) patterns available."
    )

    # Build hypothesis_path from T1 patterns
    all_gaps: List[str] = []
    for evt in events:
        all_gaps.extend(evt.get("verification_gap", []))
    if not all_gaps:
        all_gaps = ["Additional source confirmation required"]
    hypothesis_selected = [
        {"pattern": ap["pattern"], "supporting_event_id": ap["from_event"]}
        for ap in t1_active[:2]
    ]
    hypothesis_summary = (
        "Hypothesis-level signals: " + ", ".join(ap["pattern"] for ap in t1_active[:2])
        if t1_active else "No hypothesis (T1) patterns active."
    )

    # Overall conclusion text
    all_names = [ap["pattern"] for ap in active_patterns[:2]]
    derived_names = [dp["derived"] for dp in derived_patterns[:1]]
    if all_names:
        conclusion = f"The text exhibits the following dynamics: {', '.join(all_names)}."
        if derived_names:
            conclusion += f" Compositional analysis further suggests: {', '.join(derived_names)}."
    else:
        conclusion = (
            "No strong pattern signals detected. "
            "LLM analysis is disabled; deterministic fallback applied."
        )

    selected = [
        {"pattern": ap["pattern"], "supporting_event_id": ap["from_event"]}
        for ap in active_patterns[:3]
    ]
    return {
        "selected_patterns": selected,
        "conclusion":        conclusion,
        "confidence":        0.40,
        "mode":              "deterministic_fallback",
        "evidence_path": {
            "patterns": evidence_selected,
            "summary":  evidence_summary,
        },
        "hypothesis_path": {
            "patterns":          hypothesis_selected,
            "summary":           hypothesis_summary,
            "verification_gaps": list(dict.fromkeys(all_gaps))[:5],
        },
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
    events: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Compute a credibility report for the pipeline run.

    Fields returned
    ---------------
    verifiability_score   float 0-1  additive scoring on verifiable anchor presence
    missing_evidence      list[str]  types of anchor that are absent
    kg_consistency_score  float 0-1  based on absence of contradicting patterns
    contradictions        list[str]  co-activated contradicting pattern pairs
    supporting_paths      list       populated by KG infra when available
    hypothesis_ratio      float 0-1  fraction of patterns that are T1 (hypothesis)
    overall_score         float 0-1  composite: (0.6*verifiability + 0.4*kg_consistency)
                                     * (1 - 0.5*hypothesis_ratio)

    Verifiability is additive: each anchor type contributes independently,
    so short but evidence-containing texts don't always yield 0.
    Anchor weights (sum to 1.0 at max):
      - specific_date:            0.30
      - named_institution:        0.30
      - official_document_or_url: 0.25
      - named_person_or_source:   0.15
    """
    # --- Verifiability (additive scoring) ---
    has_date        = bool(_DATE_RE.search(text))
    has_url         = bool(_URL_RE.search(text))
    has_filing      = bool(_FILING_RE.search(text))
    has_institution = bool(_INSTITUTION_RE.search(text))
    # Named person / source heuristic (simple: quoted speech or "said"/"according to" attribution)
    has_named_source = bool(re.search(
        r'(?:"\s*,?\s*(?:said|according\s+to|stated|told|confirmed|announced)'
        r'|\baccording\s+to\b)',
        text, re.IGNORECASE,
    ))

    verifiability_score = (
        (0.30 if has_date else 0.0)
        + (0.30 if has_institution else 0.0)
        + (0.25 if (has_filing or has_url) else 0.0)
        + (0.15 if has_named_source else 0.0)
    )
    verifiability_score = min(1.0, verifiability_score)

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

    # --- Hypothesis ratio ---
    all_tiers: List[str] = (
        [ap.get("tier", "T2") for ap in active_patterns]
        + [dp.get("derived_tier", "T2") for dp in derived_patterns]
    )
    if all_tiers:
        t1_count = sum(1 for t in all_tiers if t == "T1")
        hypothesis_ratio = t1_count / len(all_tiers)
    else:
        hypothesis_ratio = 0.0

    overall_score = (
        (0.6 * verifiability_score + 0.4 * kg_consistency_score)
        * (1.0 - 0.5 * hypothesis_ratio)
    )

    return {
        "verifiability_score":   round(verifiability_score, 3),
        "missing_evidence":      missing_evidence,
        "kg_consistency_score":  round(kg_consistency_score, 3),
        "contradictions":        contradictions,
        "supporting_paths":      [],   # populated by KG infra when available
        "hypothesis_ratio":      round(hypothesis_ratio, 3),
        "overall_score":         round(overall_score, 3),
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
