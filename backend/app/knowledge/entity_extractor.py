"""
Entity and Relation Extractor for the Knowledge Graph.

Extracts (entity, type) pairs and (subject, relation, object) triples from
news text using LangChain (LLM-powered) or rule-based fallback.

Usage::

    from app.knowledge.entity_extractor import EntityRelationExtractor

    extractor = EntityRelationExtractor()
    result = extractor.extract("Federal Reserve raises rates amid inflation fears.")
    # {
    #   "entities": [{"name": "Federal Reserve", "type": "ORG"}, ...],
    #   "relations": [{"from": "Federal Reserve", "relation": "raises", "to": "rates"}, ...]
    # }
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any, Dict, List, Tuple

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
                '{"entities": [{"name": "...", "type": "ORG|GPE|PERSON|EVENT|PRODUCT", '
                '"description": "brief description", "confidence": 0.9}], '
                '"relations": [{"from": "...", "relation": "...", "to": "...", "weight": 0.8}]}\n'
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
