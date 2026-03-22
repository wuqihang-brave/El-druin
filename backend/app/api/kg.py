"""Knowledge Graph API router."""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.auth import get_current_user
from app.models.schemas import EntityResponse, RelationshipResponse, TokenData

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/kg", tags=["Knowledge Graph"])


# ---------------------------------------------------------------------------
# GET /kg/entities
# ---------------------------------------------------------------------------


@router.get(
    "/entities",
    response_model=list[EntityResponse],
    summary="List entities with filtering and pagination",
)
async def list_entities(
    entity_class: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
    current_user: TokenData = Depends(get_current_user),
) -> list[EntityResponse]:
    """List entities in the knowledge graph.

    Args:
        entity_class: Optional entity class filter (Person, Org, etc.).
        limit: Maximum number of results.
        skip: Number of results to skip.
        current_user: Authenticated user.

    Returns:
        List of :class:`EntityResponse`.
    """
    try:
        from app.db.neo4j_client import neo4j_client

        if entity_class:
            cypher = (
                f"MATCH (n:{entity_class}) RETURN n SKIP {skip} LIMIT {limit}"
            )
        else:
            cypher = f"MATCH (n) RETURN n SKIP {skip} LIMIT {limit}"

        records = await neo4j_client.run_cypher(cypher)
        entities: list[EntityResponse] = []
        for rec in records:
            node = rec.get("n") or {}
            if not isinstance(node, dict):
                node = dict(node) if hasattr(node, "__iter__") else {}
            labels = node.get("__labels__")
            if entity_class:
                resolved_class = entity_class
            elif isinstance(labels, list) and labels:
                resolved_class = labels[0]
            else:
                resolved_class = "Unknown"
            entities.append(
                EntityResponse(
                    id=str(node.get("id", "")),
                    entity_class=resolved_class,
                    properties={k: v for k, v in node.items() if not k.startswith("__")},
                )
            )
        return entities
    except Exception as exc:
        logger.warning("KG list_entities failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# GET /kg/entities/{id}
# ---------------------------------------------------------------------------


@router.get(
    "/entities/{entity_id}",
    response_model=EntityResponse,
    summary="Get entity with all relationships",
)
async def get_entity(
    entity_id: str,
    current_user: TokenData = Depends(get_current_user),
) -> EntityResponse:
    """Retrieve a single entity with its relationships.

    Args:
        entity_id: Entity ID property value.
        current_user: Authenticated user.

    Returns:
        :class:`EntityResponse` with relationships.

    Raises:
        HTTPException: 404 if not found.
    """
    from app.db.neo4j_client import neo4j_client

    node = await neo4j_client.get_node(entity_id)
    if node is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found"
        )

    neighbors = await neo4j_client.get_neighbors(entity_id)
    relationships: list[dict] = []
    for rec in neighbors:
        relationships.append(
            {
                "neighbor": rec.get("m"),
                "relationship_type": rec.get("rel_type"),
            }
        )

    node_dict = dict(node) if not isinstance(node, dict) else node
    return EntityResponse(
        id=entity_id,
        entity_class=node_dict.get("entity_class", "Unknown"),
        properties={k: v for k, v in node_dict.items() if not k.startswith("__")},
        relationships=relationships,
    )


# ---------------------------------------------------------------------------
# GET /kg/relations
# ---------------------------------------------------------------------------


@router.get(
    "/relations",
    response_model=list[RelationshipResponse],
    summary="List relationships with filtering",
)
async def list_relationships(
    relationship_type: Optional[str] = Query(default=None),
    source_id: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: TokenData = Depends(get_current_user),
) -> list[RelationshipResponse]:
    """List relationships in the knowledge graph.

    Args:
        relationship_type: Optional relationship type filter.
        source_id: Optional source node ID filter.
        limit: Maximum number of results.
        current_user: Authenticated user.

    Returns:
        List of :class:`RelationshipResponse`.
    """
    try:
        from app.db.neo4j_client import neo4j_client

        if source_id and relationship_type:
            cypher = (
                f"MATCH (a {{id: $source_id}})-[r:{relationship_type}]->(b) "
                f"RETURN a.id AS src, b.id AS tgt, type(r) AS rel_type, id(r) AS rel_id "
                f"LIMIT {limit}"
            )
            params: dict = {"source_id": source_id}
        elif source_id:
            cypher = (
                f"MATCH (a {{id: $source_id}})-[r]->(b) "
                f"RETURN a.id AS src, b.id AS tgt, type(r) AS rel_type, id(r) AS rel_id "
                f"LIMIT {limit}"
            )
            params = {"source_id": source_id}
        elif relationship_type:
            cypher = (
                f"MATCH (a)-[r:{relationship_type}]->(b) "
                f"RETURN a.id AS src, b.id AS tgt, type(r) AS rel_type, id(r) AS rel_id "
                f"LIMIT {limit}"
            )
            params = {}
        else:
            cypher = (
                f"MATCH (a)-[r]->(b) "
                f"RETURN a.id AS src, b.id AS tgt, type(r) AS rel_type, id(r) AS rel_id "
                f"LIMIT {limit}"
            )
            params = {}

        records = await neo4j_client.run_cypher(cypher, params)
        return [
            RelationshipResponse(
                id=str(rec.get("rel_id", "")),
                source_id=str(rec.get("src", "")),
                target_id=str(rec.get("tgt", "")),
                relationship_type=str(rec.get("rel_type", "")),
            )
            for rec in records
        ]
    except Exception as exc:
        logger.warning("KG list_relationships failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# GET /kg/subgraph
# ---------------------------------------------------------------------------


@router.get(
    "/subgraph",
    response_model=dict,
    summary="Get subgraph around an entity",
)
async def get_subgraph(
    entity_id: str = Query(...),
    depth: int = Query(default=2, ge=1, le=4),
    current_user: TokenData = Depends(get_current_user),
) -> dict:
    """Return the subgraph rooted at an entity up to a given depth.

    Args:
        entity_id: Root entity ID.
        depth: Traversal depth.
        current_user: Authenticated user.

    Returns:
        Dict with ``nodes`` and ``relationships`` lists.
    """
    try:
        from app.db.neo4j_client import neo4j_client

        return await neo4j_client.get_subgraph(entity_id, depth=depth)
    except Exception as exc:
        logger.warning("KG subgraph failed: %s", exc)
        return {"nodes": [], "relationships": []}
