"""
Entity and Relation Extractor for the Knowledge Graph.

Extracts (entity, type) pairs and (subject, relation, object) triples from
news text using LangChain (LLM-powered) or rule-based fallback.

Also provides :class:`OntologyConstrainedExtractor`, which wraps the base
extractor and enforces Schema.org node types and PROV-O edge types defined in
``config.ontology``.  All LLM outputs are validated and remapped to the
canonical ontology; a structured validation report is included in the result.

Usage::

    from app.knowledge.entity_extractor import EntityRelationExtractor
    from app.knowledge.entity_extractor import OntologyConstrainedExtractor

    # Basic extractor (unconstrained)
    extractor = EntityRelationExtractor()
    result = extractor.extract("Federal Reserve raises rates amid inflation fears.")

    # Ontology-constrained extractor
    constrained = OntologyConstrainedExtractor()
    result = constrained.extract("Federal Reserve raises rates amid inflation fears.")
    # result now includes 'validation_report' with compliance metrics
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rule-based entity patterns
# ---------------------------------------------------------------------------
_ORG_ABBREVS = {
    "UN", "NATO", "WHO", "IMF", "WTO", "EU", "FBI", "CIA", "FEMA",
    "Fed", "ECB", "OPEC", "G7", "G20", "IAEA", "ICC", "WB",
}
_GPE_NAMES = {
    "USA", "United States", "US", "UK", "United Kingdom", "China", "Russia",
    "Germany", "France", "Japan", "India", "Brazil", "Australia", "Canada",
    "Iran", "Israel", "Ukraine", "Taiwan", "North Korea", "South Korea",
    "Saudi Arabia", "Turkey", "Mexico", "Italy", "Spain",
}

_RELATION_PATTERNS: List[Tuple[str, str]] = [
    (r"\b(sanctions?|sanctioned)\b", "sanctions"),
    (r"\b(invades?|invaded|invasion)\b", "invades"),
    (r"\b(signs?|signed)\b", "signs"),
    (r"\b(agrees?|agreed|agreement)\b", "agrees_with"),
    (r"\b(raises?|raised|hikes?|hiked)\b", "raises"),
    (r"\b(cuts?|cut)\b", "cuts"),
    (r"\b(attacks?|attacked)\b", "attacks"),
    (r"\b(opposes?|opposed)\b", "opposes"),
    (r"\b(supports?|supported)\b", "supports"),
    (r"\b(condemns?|condemned)\b", "condemns"),
    (r"\b(meets?|met|meeting)\b", "meets"),
    (r"\b(acquires?|acquired|acquisition)\b", "acquires"),
    (r"\b(launches?|launched)\b", "launches"),
]


def _rule_based_entities(text: str) -> List[Dict[str, Any]]:
    entities: List[Dict[str, Any]] = []
    seen: set = set()

    def _add(name: str, etype: str) -> None:
        if name and name not in seen:
            seen.add(name)
            entities.append({"name": name, "type": etype, "description": "", "confidence": 0.7})

    # Known abbreviations
    for abbrev in _ORG_ABBREVS:
        if re.search(r"\b" + re.escape(abbrev) + r"\b", text):
            _add(abbrev, "ORG")

    # Known GPE names
    for gpe in _GPE_NAMES:
        if re.search(r"\b" + re.escape(gpe) + r"\b", text):
            _add(gpe, "GPE")

    # Org patterns (Title Case + org suffix)
    for m in re.finditer(
        r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)* (?:Corp|Inc|Ltd|Group|Bank|Fund|Organization|Agency|Ministry|Council|Committee|Commission))\b",
        text,
    ):
        _add(m.group(1), "ORG")

    # Person patterns (two capitalised words not after other caps)
    for m in re.finditer(r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b", text):
        name = m.group(1)
        if name not in seen and not any(name.startswith(g) for g in _GPE_NAMES):
            _add(name, "PERSON")

    return entities[:15]


def _rule_based_relations(
    text: str, entities: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    relations: List[Dict[str, Any]] = []
    entity_names = [e["name"] for e in entities]
    if len(entity_names) < 2:
        return []

    for pat, rel_type in _RELATION_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            # Emit relation between first two entities that appear close together
            if len(entity_names) >= 2:
                relations.append({
                    "from": entity_names[0],
                    "relation": rel_type,
                    "to": entity_names[1],
                    "weight": 0.6,
                })
    return relations[:5]


def _llm_extract(text: str) -> Dict[str, Any]:
    """LLM-based entity and relation extraction via LangChain.

    Uses a few-shot causal-link prompt that instructs the model to focus on
    "A causes B" patterns in addition to standard entity/relation extraction.
    """
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
            )
        elif settings.llm_provider == "groq":
            from langchain_groq import ChatGroq
            llm = ChatGroq(
                model=settings.llm_model,
                temperature=settings.llm_temperature,
                api_key=settings.groq_api_key,
            )
        else:
            return {}

        # Import the shared few-shot causal prompt.
        try:
            from knowledge_layer.incremental_extractor import FEW_SHOT_CAUSAL_PROMPT
            system_prompt = FEW_SHOT_CAUSAL_PROMPT
        except ImportError:
            # Fallback to the basic prompt if the incremental extractor is not
            # on the Python path (e.g. during isolated unit tests).
            system_prompt = (
                "You are a knowledge-graph builder. Extract entities and relations "
                "from the given text and return ONLY valid JSON in this exact format:\n"
                '{"entities": [{{"name": "...", "type": "ORG|GPE|PERSON|EVENT|PRODUCT", '
                '"description": "brief description", "confidence": 0.9}], '
                '"relations": [{"from": "...", "relation": "...", "to": "...", "weight": 0.8}]}}\n'
                "confidence must be a float between 0.0 and 1.0. "
                "Limit to the 10 most important entities and 5 most important relations."
            )

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{text}"),
        ])
        parser = JsonOutputParser()
        chain = prompt | llm | parser
        result = chain.invoke({"text": text[:2000]})
        if isinstance(result, dict):
            return result
        return {}
    except Exception as exc:
        logger.warning("LLM entity extraction failed: %s", exc)
        return {}


class EntityRelationExtractor:
    """Extracts entities and relations for populating the knowledge graph."""

    def __init__(self) -> None:
        self._settings = get_settings()

    def extract(self, text: str) -> Dict[str, Any]:
        """Extract entities and relations from *text*.

        Returns::

            {
                "entities": [{"name": str, "type": str}, ...],
                "relations": [{"from": str, "relation": str, "to": str, "weight": float}, ...],
            }
        """
        if not text or not text.strip():
            return {"entities": [], "relations": []}

        if self._settings.llm_enabled:
            result = _llm_extract(text)
            if result.get("entities"):
                return result

        # Rule-based fallback
        entities = _rule_based_entities(text)
        relations = _rule_based_relations(text, entities)
        return {"entities": entities, "relations": relations}


def _llm_extract_constrained(text: str, system_prompt: str) -> Dict[str, Any]:
    """LLM-based extraction using a custom ontology-constraining system prompt.

    Identical to :func:`_llm_extract` but accepts an explicit *system_prompt*
    so that callers can inject the Schema.org + PROV-O ontology constraints.

    Args:
        text:          News text to extract entities/relations from.
        system_prompt: System message enforcing ontological constraints.

    Returns:
        Parsed JSON dict with ``entities`` and ``relations`` lists, or ``{}``
        on failure.
    """
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
            )
        elif settings.llm_provider == "groq":
            from langchain_groq import ChatGroq
            llm = ChatGroq(
                model=settings.llm_model,
                temperature=settings.llm_temperature,
                api_key=settings.groq_api_key,
            )
        else:
            return {}

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{text}"),
        ])
        parser = JsonOutputParser()
        chain = prompt | llm | parser
        result = chain.invoke({"text": text[:2000]})
        if isinstance(result, dict):
            return result
        return {}
    except Exception as exc:
        logger.warning("Constrained LLM extraction failed: %s", exc)
        return {}


class OntologyConstrainedExtractor:
    """Ontology-constrained entity and relation extractor.

    Wraps :class:`EntityRelationExtractor` and enforces that all extracted
    node types conform to the Schema.org vocabulary and all edge types conform
    to the PROV-O vocabulary defined in ``config.ontology``.

    **Extraction pipeline:**

    1. If LLM is enabled, use a system prompt that lists *only* the allowed
       node/edge types, forcing the model to stay within the ontology.
    2. Validate and remap every extracted entity type and relation type to
       the canonical Schema.org / PROV-O labels using :mod:`config.ontology`.
    3. Entities and edges that cannot be mapped are collected in
       ``invalid_entities`` / ``invalid_edges`` within the validation report.
    4. If the LLM returns nothing useful, fall back to the rule-based
       extractor and apply the same validation pass.

    Returns a dict with the standard ``entities`` / ``relations`` keys (now
    containing only ontologically valid items) plus a ``validation_report``
    key with detailed compliance metrics.

    Usage::

        extractor = OntologyConstrainedExtractor()
        result = extractor.extract("US sanctions Iran over nuclear programme.")
        # result["entities"]         – valid, remapped entities
        # result["relations"]        – valid, remapped relations
        # result["validation_report"]["compliance_pct"] – e.g. 87.5
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._base_extractor = EntityRelationExtractor()
        self._system_prompt: Optional[str] = None

    def _get_system_prompt(self) -> str:
        """Return the ontology-constraining system prompt (lazily cached)."""
        if self._system_prompt is None:
            try:
                from config.ontology import generate_ontology_system_prompt
                self._system_prompt = generate_ontology_system_prompt()
            except ImportError:
                # Fallback when config package is not on sys.path
                try:
                    import os
                    import sys
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

    def _load_build_validation_report(self):  # type: ignore[return]
        """Import and return the ``build_validation_report`` callable.

        Attempts a direct import from ``config.ontology``.  If that fails
        (e.g. the ``backend/`` directory is not on ``sys.path``), adds the
        backend root to ``sys.path`` and retries.

        Returns:
            The ``build_validation_report`` callable from ``config.ontology``.
        """
        try:
            from config.ontology import build_validation_report
            return build_validation_report
        except ImportError:
            import os
            import sys
            _backend = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "..")
            )
            if _backend not in sys.path:
                sys.path.insert(0, _backend)
            from config.ontology import build_validation_report
            return build_validation_report

    def extract(self, text: str) -> Dict[str, Any]:
        """Extract entities and relations with full ontological validation.

        Args:
            text: Raw news or document text (max 10 000 characters).

        Returns:
            Dict with keys:
            - ``entities``:          ontologically valid entities (type remapped)
            - ``relations``:         ontologically valid relations (type remapped)
            - ``validation_report``: detailed compliance report containing
              ``valid_entities``, ``invalid_entities``, ``valid_edges``,
              ``invalid_edges``, ``unmapped_nodes``, ``compliance_pct``, and
              ``validation_summary``
        """
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

        # Step 1 – LLM extraction with ontology-constrained system prompt
        raw_result: Dict[str, Any] = {}
        if self._settings.llm_enabled:
            raw_result = _llm_extract_constrained(text, self._get_system_prompt())

        # Step 2 – Fallback to rule-based if LLM returned nothing
        if not raw_result.get("entities"):
            fallback = self._base_extractor.extract(text)
            raw_result = fallback

        raw_entities: List[Dict] = raw_result.get("entities", [])
        raw_relations: List[Dict] = raw_result.get("relations", [])

        # Step 3 – Validate and remap to canonical ontology types
        build_report = self._load_build_validation_report()
        report = build_report(raw_entities, raw_relations)

        logger.info(
            "OntologyConstrainedExtractor: %s",
            report["validation_summary"],
        )

        return {
            "entities": report["valid_entities"],
            "relations": report["valid_edges"],
            "validation_report": report,
        }
