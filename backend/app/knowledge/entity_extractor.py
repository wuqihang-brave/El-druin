"""
Entity and Relation Extractor for the Knowledge Graph.

修复说明 (v3)：
  1. 规则引擎「硬编码注入」bug：
     原版 _GPE_NAMES / _ORG_ABBREVS 包含全球知名实体列表，
     对每篇新闻都做全量扫描 —— 只要文本里出现 "US"、"China" 等词就会被注入。
     西班牙新闻里出现 "US warplanes" 就会给出美国中国分析。
     修复：_rule_based_entities 改为「仅提取文本中实际出现的实体」，
     列表本身仅作为 type 映射字典使用，不做全量注入。

  2. _rule_based_relations 硬写 entity[0]→entity[1]：
     原版无论哪个关键词被命中，都把提取列表里的第一、第二个实体配对。
     修复：找到动词匹配后，从文本中找最近的两个实体作为主语/宾语对。

  3. _rule_based_entities 提取上限过低（15）：
     新增 max_entities 参数。

  4. 保持 LLM 路径、OntologyConstrainedExtractor 完全不变。
"""

from __future__ import annotations

import concurrent.futures
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_LLM_TIMEOUT_SECONDS = 30  # hard cap per LLM call to avoid infinite Groq retries

# ---------------------------------------------------------------------------
# Circuit-breaker: if Groq returns 403 we open the circuit for the rest of the
# current ingest cycle so we don't waste time on guaranteed-to-fail calls.
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


def _is_403_error(exc: Exception) -> bool:
    """Return True if *exc* represents a 403 Forbidden HTTP error."""
    msg = str(exc)
    return "403" in msg or "Forbidden" in msg.lower()

# ---------------------------------------------------------------------------
# Rule-based entity patterns
# ---------------------------------------------------------------------------

# These dicts are TYPE MAPPINGS only.
# They are NOT injected wholesale — we only add an entity if its name
# actually appears in the text being analysed.
_ORG_ABBREVS: Dict[str, str] = {
    abbrev: "ORG" for abbrev in {
        "UN", "NATO", "WHO", "IMF", "WTO", "EU", "FBI", "CIA", "FEMA",
        "Fed", "ECB", "OPEC", "G7", "G20", "IAEA", "ICC", "WB",
        "OSCE", "ASEAN", "AU", "OAS", "SCO", "QUAD",
    }
}

# Known country / GPE names – used ONLY for type labelling when the name
# already appears in the text.  Never injected proactively.
_GPE_NAMES: Dict[str, str] = {
    name: "GPE" for name in {
        "USA", "United States", "US", "UK", "United Kingdom",
        "China", "Russia", "Germany", "France", "Japan", "India",
        "Brazil", "Australia", "Canada", "Iran", "Israel", "Ukraine",
        "Taiwan", "North Korea", "South Korea", "Saudi Arabia", "Turkey",
        "Mexico", "Italy", "Spain", "Poland", "Netherlands", "Sweden",
        "Norway", "Pakistan", "Afghanistan", "Syria", "Iraq", "Libya",
        "Venezuela", "Cuba", "Belarus", "Georgia", "Armenia", "Azerbaijan",
        "Ethiopia", "Sudan", "Yemen", "Lebanon", "Jordan", "Egypt",
    }
}

# Org suffix pattern (matches things like "European Commission")
_ORG_SUFFIX_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+"
    r"(?:Corp|Inc|Ltd|Group|Bank|Fund|Organization|Organisation|"
    r"Agency|Ministry|Council|Committee|Commission|Authority|"
    r"Department|Office|Bureau|Institute|Foundation|Alliance|"
    r"Federation|Union|Association|Coalition|Forces|Army|Navy|"
    r"Government|Parliament|Senate|Congress))\b"
)

# Person pattern: two or more capitalised words that are not a known GPE
_PERSON_RE = re.compile(r"\b([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b")

_RELATION_PATTERNS: List[Tuple[str, str]] = [
    (r"\b(sanctions?|sanctioned)\b",               "sanctions"),
    (r"\b(invades?|invaded|invasion)\b",            "invades"),
    (r"\b(signs?|signed)\b",                        "signs"),
    (r"\b(agrees?|agreed|agreement)\b",             "agrees_with"),
    (r"\b(raises?|raised|hikes?|hiked)\b",          "raises"),
    (r"\b(cuts?|cut)\b",                            "cuts"),
    (r"\b(attacks?|attacked)\b",                    "attacks"),
    (r"\b(opposes?|opposed)\b",                     "opposes"),
    (r"\b(supports?|supported)\b",                  "supports"),
    (r"\b(condemns?|condemned)\b",                  "condemns"),
    (r"\b(meets?|met|meeting)\b",                   "meets"),
    (r"\b(acquires?|acquired|acquisition)\b",       "acquires"),
    (r"\b(launches?|launched)\b",                   "launches"),
    (r"\b(closes?|closed|closure)\b",               "closes"),
    (r"\b(bans?|banned)\b",                         "bans"),
    (r"\b(withdraws?|withdrew|withdrawal)\b",       "withdraws"),
    (r"\b(expels?|expelled|expulsion)\b",           "expels"),
    (r"\b(imposes?|imposed)\b",                     "imposes"),
    (r"\b(refuses?|refused)\b",                     "refuses"),
    (r"\b(deploys?|deployed)\b",                    "deploys"),
    (r"\b(accuses?|accused)\b",                     "accuses"),
    (r"\b(negotiates?|negotiated|negotiation)\b",   "negotiates"),
    (r"\b(supplies?|supplied)\b",                   "supplies"),
    (r"\b(targets?|targeted)\b",                    "targets"),
]


def _rule_based_entities(text: str, max_entities: int = 20) -> List[Dict[str, Any]]:
    """Extract entities that actually appear in *text*.

    修复：不再全量注入 _GPE_NAMES / _ORG_ABBREVS，
    只有当名称在文本中出现时才添加。
    """
    entities: List[Dict[str, Any]] = []
    seen: set = set()

    def _add(name: str, etype: str, conf: float = 0.75) -> None:
        name = name.strip()
        if name and name not in seen and len(name) > 1:
            seen.add(name)
            entities.append({
                "name": name,
                "type": etype,
                "description": "",
                "confidence": conf,
            })

    # 1) Known ORG abbreviations — only if they appear in text
    for abbrev in _ORG_ABBREVS:
        if re.search(r"\b" + re.escape(abbrev) + r"\b", text):
            _add(abbrev, "ORG", 0.85)

    # 2) Known GPE names — only if they appear in text
    # Sort by length descending so "United States" is matched before "US"
    for gpe in sorted(_GPE_NAMES.keys(), key=len, reverse=True):
        if re.search(r"\b" + re.escape(gpe) + r"\b", text):
            _add(gpe, "GPE", 0.85)

    # 3) Org suffix pattern — captures context-specific organisations
    for m in _ORG_SUFFIX_RE.finditer(text):
        _add(m.group(1), "ORG", 0.75)

    # 4) Person pattern — two/three Title-Case words not matching a known GPE
    for m in _PERSON_RE.finditer(text):
        name = m.group(1)
        if name not in seen and not any(
            re.fullmatch(re.escape(gpe), name) for gpe in _GPE_NAMES
        ):
            _add(name, "PERSON", 0.65)

    return entities[:max_entities]


def _find_nearest_pair(
    text: str,
    entity_names: List[str],
    verb_match: re.Match,
) -> Optional[Tuple[str, str]]:
    """Find the two entity names closest to *verb_match* in *text*.

    修复：不再硬写 entity[0]→entity[1]，
    而是找距离动词位置最近的两个不同实体作为主语/宾语。

    Returns (subject, object) or None if fewer than 2 entities are close enough.
    """
    verb_pos = verb_match.start()

    # Find position of each entity in text; keep closest occurrence to verb
    positions: List[Tuple[int, str]] = []
    for name in entity_names:
        for m in re.finditer(re.escape(name), text):
            positions.append((abs(m.start() - verb_pos), name))

    if len(positions) < 2:
        return None

    # Sort by distance to verb
    positions.sort(key=lambda x: x[0])

    # Pick the two closest distinct entities
    seen_names: set = set()
    pair: List[str] = []
    for _, name in positions:
        if name not in seen_names:
            seen_names.add(name)
            pair.append(name)
        if len(pair) == 2:
            break

    if len(pair) < 2:
        return None

    # Heuristic: entity that appears before the verb is the subject
    pos_a = text.find(pair[0])
    pos_b = text.find(pair[1])
    if pos_a <= verb_pos and pos_b >= verb_pos:
        return (pair[0], pair[1])
    if pos_b <= verb_pos and pos_a >= verb_pos:
        return (pair[1], pair[0])
    # Both before or both after — use text order
    if pos_a < pos_b:
        return (pair[0], pair[1])
    return (pair[1], pair[0])


def _rule_based_relations(
    text: str,
    entities: List[Dict[str, Any]],
    max_relations: int = 8,
) -> List[Dict[str, Any]]:
    """Extract relations from *text* using verb-pattern matching.

    修复：通过 _find_nearest_pair 找到动词附近的实体对，
    而不是硬写 entity[0]→entity[1]。
    """
    relations: List[Dict[str, Any]] = []
    entity_names = [e["name"] for e in entities]
    if len(entity_names) < 2:
        return []

    seen_pairs: set = set()

    for pat, rel_type in _RELATION_PATTERNS:
        for verb_match in re.finditer(pat, text, re.IGNORECASE):
            pair = _find_nearest_pair(text, entity_names, verb_match)
            if pair is None:
                continue
            subj, obj = pair
            key = (subj, rel_type, obj)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            relations.append({
                "from":     subj,
                "relation": rel_type,
                "to":       obj,
                "weight":   0.65,
            })
            if len(relations) >= max_relations:
                return relations

    return relations


def _llm_extract(text: str) -> Dict[str, Any]:
    """LLM-based entity and relation extraction via LangChain."""
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
            return {}

        try:
            from knowledge_layer.incremental_extractor import FEW_SHOT_CAUSAL_PROMPT
            system_prompt = FEW_SHOT_CAUSAL_PROMPT
        except ImportError:
            system_prompt = (
                "You are a knowledge-graph builder. Extract entities and relations "
                "from the given text and return ONLY valid JSON in this exact format:\n"
                '{{"entities": [{{"name": "...", "type": "ORG|GPE|PERSON|EVENT|PRODUCT", '
                '"description": "brief description", "confidence": 0.9}}], '
                '"relations": [{{"from": "...", "relation": "...", "to": "...", "weight": 0.8}]}}\n'
                "confidence must be a float between 0.0 and 1.0. "
                "Limit to the 10 most important entities and 5 most important relations."
            )

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{text}"),
        ])
        parser = JsonOutputParser()
        chain = prompt | llm | parser

        def _invoke() -> Dict[str, Any]:
            result = chain.invoke({"text": text[:2000]})
            return result if isinstance(result, dict) else {}

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_invoke)
            try:
                return future.result(timeout=_LLM_TIMEOUT_SECONDS)
            except concurrent.futures.TimeoutError:
                logger.warning("LLM extraction timed out after %ds", _LLM_TIMEOUT_SECONDS)
                return {}
    except Exception as exc:
        if _is_403_error(exc):
            _llm_circuit_open = True
            logger.warning(
                "Groq 403 received — disabling LLM for this ingest cycle"
            )
            return {}
        logger.debug("LLM extraction failed: %s", exc)
        return {}


class EntityRelationExtractor:
    """Extracts entities and relations for populating the knowledge graph."""

    def __init__(self) -> None:
        self._settings = get_settings()

    def extract(self, text: str) -> Dict[str, Any]:
        """Extract entities and relations from *text*.

        Returns::

            {
                "entities": [{"name": str, "type": str, "description": str, "confidence": float}, ...],
                "relations": [{"from": str, "relation": str, "to": str, "weight": float}, ...],
            }
        """
        if not text or not text.strip():
            return {"entities": [], "relations": []}

        if self._settings.llm_enabled and not _llm_circuit_open:
            result = _llm_extract(text)
            if result.get("entities"):
                return result

        # Rule-based fallback — entities grounded in the actual text
        entities = _rule_based_entities(text)
        relations = _rule_based_relations(text, entities)
        return {"entities": entities, "relations": relations}


def _llm_extract_constrained(text: str, system_prompt: str) -> Dict[str, Any]:
    """LLM-based extraction using a custom ontology-constraining system prompt."""
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
            return {}

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{text}"),
        ])
        parser = JsonOutputParser()
        chain = prompt | llm | parser

        def _invoke() -> Dict[str, Any]:
            result = chain.invoke({"text": text[:2000]})
            return result if isinstance(result, dict) else {}

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_invoke)
            try:
                return future.result(timeout=_LLM_TIMEOUT_SECONDS)
            except concurrent.futures.TimeoutError:
                logger.warning(
                    "Constrained LLM extraction timed out after %ds", _LLM_TIMEOUT_SECONDS
                )
                return {}
    except Exception as exc:
        if _is_403_error(exc):
            _llm_circuit_open = True
            logger.warning(
                "Groq 403 received — disabling LLM for this ingest cycle"
            )
            return {}
        logger.warning("Constrained LLM extraction failed: %s", exc)
        return {}


class OntologyConstrainedExtractor:
    """Ontology-constrained entity and relation extractor.

    Wraps EntityRelationExtractor and enforces Schema.org node types and
    PROV-O edge types.  All outputs are validated and remapped to the canonical
    ontology; a structured validation report is included in the result.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._base_extractor = EntityRelationExtractor()
        self._system_prompt: Optional[str] = None

    def _get_system_prompt(self) -> str:
        if self._system_prompt is None:
            try:
                from config.ontology import generate_ontology_system_prompt
                self._system_prompt = generate_ontology_system_prompt()
            except ImportError:
                try:
                    import os, sys
                    _backend = os.path.abspath(
                        os.path.join(os.path.dirname(__file__), "..", "..", "..")
                    )
                    if _backend not in sys.path:
                        sys.path.insert(0, _backend)
                    from config.ontology import generate_ontology_system_prompt
                    self._system_prompt = generate_ontology_system_prompt()
                except Exception:
                    self._system_prompt = (
                        "You are a knowledge-graph builder. Extract entities and "
                        "relations from the given text and return ONLY valid JSON:\n"
                        '{"entities": [{"name": "...", "type": "Organization|Person'
                        '|Place|Event|SoftwareApplication|CreativeWork|Dataset'
                        '|Technique|Indicator|ThreatIndicator|EconomicIndicator'
                        '|GeopoliticalIndicator|NewsArticle", "description": "...", '
                        '"confidence": 0.9}], "relations": [{"from": "...", '
                        '"relation": "works_for|leads|member_of|allied_with'
                        '|antagonistic_to|competes_with|located_in|operates_in'
                        '|originates_from|mentions|reports_on|cites|involved_in'
                        '|caused_by|impacts|implements|vulnerable_to|infected_by'
                        '|targets|depends_on|provides|uses|signals|attributed_to'
                        '|verified_by|contradicts", "to": "...", "weight": 0.8}]}'
                    )
        return self._system_prompt  # type: ignore[return-value]

    def _load_build_validation_report(self):
        try:
            from config.ontology import build_validation_report
            return build_validation_report
        except ImportError:
            import os, sys
            _backend = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "..")
            )
            if _backend not in sys.path:
                sys.path.insert(0, _backend)
            from config.ontology import build_validation_report
            return build_validation_report

    def extract(self, text: str) -> Dict[str, Any]:
        """Extract entities and relations with full ontological validation."""
        if not text or not text.strip():
            return {
                "entities": [],
                "relations": [],
                "validation_report": {
                    "valid_entities": [],
                    "invalid_entities": [],
                    "valid_edges": [],
                    "invalid_edges": [],
                    "unmapped_nodes": [],
                    "compliance_pct": 100.0,
                    "validation_summary": "No text provided.",
                },
            }

        raw_result: Dict[str, Any] = {}
        if self._settings.llm_enabled and not _llm_circuit_open:
            raw_result = _llm_extract_constrained(text, self._get_system_prompt())

        if not raw_result.get("entities"):
            raw_result = self._base_extractor.extract(text)

        raw_entities: List[Dict] = raw_result.get("entities", [])
        raw_relations: List[Dict] = raw_result.get("relations", [])

        build_report = self._load_build_validation_report()
        report = build_report(raw_entities, raw_relations)

        logger.info("OntologyConstrainedExtractor: %s", report["validation_summary"])

        return {
            "entities": report["valid_entities"],
            "relations": report["valid_edges"],
            "validation_report": report,
        }