"""
Provenance API routes.

Endpoints:
  GET /provenance/relationship/{relationship_id}  – source refs for a relationship
  GET /provenance/entity/{entity_id}              – all edges + proofs for an entity
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from app.knowledge.knowledge_graph import get_knowledge_graph

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/provenance", tags=["provenance"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_source_refs(raw: Any) -> List[Dict[str, Any]]:
    """Normalise source_refs: accept a JSON string, list, or None."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, ValueError):
            return []
    return []


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/relationship/{relationship_id}")
async def get_relationship_provenance(relationship_id: str) -> Dict[str, Any]:
    """Return all source references supporting a specific relationship.

    Parameters
    ----------
    relationship_id:
        Unique identifier of the relationship edge (stored as the ``id``
        property on relation records).

    Returns
    -------
    dict
        ``relationship_id``, ``relationship_type``, ``from_entity``,
        ``to_entity``, ``causality_score``, ``confidence``,
        ``source_refs`` list.
    """
    kg = get_knowledge_graph()
    relations: List[Dict[str, Any]] = kg.get_relations(limit=5000)

    target: Optional[Dict[str, Any]] = None
    for rel in relations:
        rel_id = rel.get("id") or rel.get("relationship_id") or ""
        # Also support matching by composite key "from|type|to"
        composite = (
            f"{rel.get('from', '')}"
            f"|{rel.get('relation', rel.get('relationship_type', ''))}"
            f"|{rel.get('to', '')}"
        )
        if rel_id == relationship_id or composite == relationship_id:
            target = rel
            break

    if target is None:
        raise HTTPException(
            status_code=404,
            detail=f"Relationship not found: {relationship_id!r}",
        )

    return {
        "relationship_id": relationship_id,
        "relationship_type": target.get("relation", target.get("relationship_type", "")),
        "from_entity": target.get("from", target.get("from_entity", "")),
        "to_entity": target.get("to", target.get("to_entity", "")),
        "causality_score": target.get("weight", target.get("causality_score", 0.5)),
        "confidence": target.get("confidence", target.get("weight", 0.5)),
        "source_refs": _safe_source_refs(target.get("source_refs")),
        "timestamp": target.get("timestamp", ""),
    }


@router.get("/entity/{entity_id}")
async def get_entity_provenance(entity_id: str) -> Dict[str, Any]:
    """Return all relationships connected to an entity plus their source refs.

    Parameters
    ----------
    entity_id:
        Unique identifier or name of the entity node.

    Returns
    -------
    dict
        ``entity_id``, ``entity_name``, ``outgoing`` edges list,
        ``incoming`` edges list, ``property_history`` list.
    """
    kg = get_knowledge_graph()
    entities: List[Dict[str, Any]] = kg.get_entities(limit=5000)
    relations: List[Dict[str, Any]] = kg.get_relations(limit=5000)

    # Find entity by id or by name.
    entity: Optional[Dict[str, Any]] = None
    for ent in entities:
        if ent.get("id") == entity_id or ent.get("name") == entity_id:
            entity = ent
            break

    if entity is None:
        raise HTTPException(
            status_code=404,
            detail=f"Entity not found: {entity_id!r}",
        )

    entity_name: str = entity.get("name", entity_id)

    outgoing: List[Dict[str, Any]] = []
    incoming: List[Dict[str, Any]] = []

    for rel in relations:
        from_ent = rel.get("from", rel.get("from_entity", ""))
        to_ent = rel.get("to", rel.get("to_entity", ""))

        proof = {
            "relationship_id": rel.get("id", f"{from_ent}|{rel.get('relation', '')}|{to_ent}"),
            "relationship_type": rel.get("relation", rel.get("relationship_type", "")),
            "from_entity": from_ent,
            "to_entity": to_ent,
            "causality_score": rel.get("weight", rel.get("causality_score", 0.5)),
            "confidence": rel.get("confidence", rel.get("weight", 0.5)),
            "source_refs": _safe_source_refs(rel.get("source_refs")),
            "timestamp": rel.get("timestamp", ""),
        }

        if from_ent == entity_name or from_ent == entity_id:
            outgoing.append(proof)
        if to_ent == entity_name or to_ent == entity_id:
            incoming.append(proof)

    # Property history (stored as JSON string on entity or empty).
    raw_history = entity.get("property_history", "[]")
    try:
        property_history = json.loads(raw_history) if isinstance(raw_history, str) else raw_history
    except (json.JSONDecodeError, TypeError):
        property_history = []

    return {
        "entity_id": entity.get("id", entity_id),
        "entity_name": entity_name,
        "entity_type": entity.get("type", ""),
        "outgoing": outgoing,
        "incoming": incoming,
        "total_relationships": len(outgoing) + len(incoming),
        "property_history": property_history,
    }
