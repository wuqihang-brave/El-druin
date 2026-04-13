"""
Semantic Explainer – EL-DRUIN Intelligence Platform
====================================================

Generates LLM-powered ontological explanations for knowledge-graph entities.
Results are cached in memory to avoid redundant LLM calls for the same entity.

Usage::

    from intelligence.semantic_explainer import generate_ontological_explanation

    explanation = generate_ontological_explanation(
        entity={"name": "Federal Reserve", "type": "ORG", "description": "..."},
        connected_entities=[
            {"name": "Stock Market", "type": "ORG", "relationship": "INFLUENCES"},
        ],
    )
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-process LRU cache keyed on a content hash (entity + connections)
# ---------------------------------------------------------------------------
_CACHE: Dict[str, str] = {}
_MAX_CACHE_SIZE = 256  # max number of cached entries


def _cache_key(entity: Dict[str, Any], connected: List[Dict[str, Any]]) -> str:
    """Produce a stable cache key from entity data and its connections."""
    raw = (
        f"{entity.get('name', '')}|{entity.get('type', '')}|"
        f"{entity.get('ontology_class', '')}|"
        + ",".join(
            f"{c.get('name', '')}:{c.get('type', '')}:{c.get('relationship', '')}"
            for c in connected[:10]
        )
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


_SYSTEM_PROMPT = """You are a philosopher specializing in ontology and knowledge structures.
Given an entity and its relationships, explain its significance in 100-150 words.
Focus on:
1. What this entity represents (its essence/being)
2. How it influences or is influenced by other entities
3. Its role in the larger system of meaning
Be poetic but precise. Reference its ontological class."""


def _build_user_message(
    entity: Dict[str, Any],
    connected: List[Dict[str, Any]],
) -> str:
    """Build the user-turn message for the LLM."""
    name = entity.get("name", "Unknown")
    etype = entity.get("ontology_class") or entity.get("type", "Unknown")
    desc = entity.get("description", "No description available.")

    connection_lines = "\n".join(
        f"  - {c.get('name', '?')} ({c.get('type', '?')}) via {c.get('relationship', '?')}"
        for c in connected[:10]
    ) or "  (no connections)"

    return (
        f"Entity: {name}\n"
        f"Ontological Class: {etype}\n"
        f"Description: {desc}\n\n"
        f"Connected entities:\n{connection_lines}"
    )


def generate_ontological_explanation(
    entity: Dict[str, Any],
    connected_entities: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Generate a philosophical explanation for *entity*'s ontological role.

    Uses the configured LLM provider (OpenAI or Groq) when available; returns
    a concise static explanation when LLM is unavailable or fails.

    Results are cached per unique (entity, connections) combination.

    Args:
        entity: Entity dict with at least ``"name"`` and ``"type"`` keys.
        connected_entities: Optional list of connected entity dicts, each with
            ``"name"``, ``"type"``, and ``"relationship"`` keys.

    Returns:
        A philosophical explanation string (100-150 words when LLM is active).
    """
    if connected_entities is None:
        connected_entities = []

    cache_key = _cache_key(entity, connected_entities)
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    result = _generate(entity, connected_entities)

    # Evict oldest entry if cache is full
    if len(_CACHE) >= _MAX_CACHE_SIZE:
        oldest = next(iter(_CACHE))
        del _CACHE[oldest]
    _CACHE[cache_key] = result
    return result


def _generate(
    entity: Dict[str, Any],
    connected: List[Dict[str, Any]],
) -> str:
    """Internal: call LLM or return fallback explanation."""
    try:
        from app.core.config import get_settings
        settings = get_settings()
    except ImportError:
        return _fallback_explanation(entity)

    if not settings.llm_enabled:
        return _fallback_explanation(entity)

    user_msg = _build_user_message(entity, connected)

    try:
        if settings.llm_provider == "openai":
            return _call_openai(settings, user_msg)
        if settings.llm_provider == "groq":
            return _call_groq(settings, user_msg)
        if settings.llm_provider == "deepseek":
            return _call_deepseek(settings, user_msg)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ontological explanation LLM call failed: %s", exc)

    return _fallback_explanation(entity)


def _call_openai(settings: Any, user_msg: str) -> str:
    """Call OpenAI to generate the explanation."""
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=0.7,
        api_key=settings.openai_api_key,
        max_tokens=250,
    )
    response = llm.invoke([
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ])
    return str(response.content).strip()


def _call_groq(settings: Any, user_msg: str) -> str:
    """Call Groq to generate the explanation."""
    from langchain_groq import ChatGroq
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = ChatGroq(
        model=settings.llm_model,
        temperature=0.7,
        api_key=settings.groq_api_key,
        max_tokens=250,
    )
    response = llm.invoke([
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ])
    return str(response.content).strip()


def _call_deepseek(settings: Any, user_msg: str) -> str:
    """Call DeepSeek to generate the explanation."""
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=0.7,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        max_tokens=250,
    )
    response = llm.invoke([
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ])
    return str(response.content).strip()


def _fallback_explanation(entity: Dict[str, Any]) -> str:
    """Return a static philosophical explanation when LLM is unavailable."""
    name = entity.get("name", "This entity")
    etype = entity.get("ontology_class") or entity.get("type", "entity")
    return (
        f"{name} stands as a {etype.lower()} within the fabric of the knowledge graph — "
        "a node of meaning whose connections define its place in the larger order of things. "
        "To understand its essence is to trace the threads of relationship that bind it "
        "to other entities: each link a testament to influence, causality, or shared context. "
        "Its significance emerges not in isolation, but through the pattern of relationships "
        "that render it legible within the system of structured knowledge."
    )
