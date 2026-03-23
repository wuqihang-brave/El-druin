"""
Knowledge Graph API routes.

Endpoints:
  POST /knowledge/ingest          – ingest articles into the knowledge graph
  GET  /knowledge/entities        – list entity nodes
  GET  /knowledge/relations       – list relation edges
  GET  /knowledge/neighbours      – get neighbours of a named entity
  POST /knowledge/query           – run a Cypher query (Kuzu backend only)
  GET  /knowledge/query           – run a Cypher query via query parameter (cached)
  GET  /knowledge/stats           – graph statistics
  POST /knowledge/extract         – extract entities/relations from text and persist
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.knowledge.knowledge_graph import get_knowledge_graph

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/knowledge", tags=["knowledge"])

_DEFAULT_ENTITY_TYPE = "MISC"
_DEFAULT_RELATION_WEIGHT = 0.5


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ExtractRequest(BaseModel):
    text: str = Field(..., min_length=10, max_length=10000, description="Raw text to extract entities and relations from")


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=5, description="Cypher query string")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/ingest")
def ingest_into_graph(
    limit: int = Query(100, ge=1, le=500, description="Max articles to fetch and ingest"),
    hours: int = Query(24, ge=1, le=720, description="Look-back window in hours"),
) -> Dict[str, Any]:
    """Fetch recent news and ingest it into the knowledge graph."""
    try:
        from app.data_ingestion.news_aggregator import NewsAggregator
        articles = NewsAggregator().aggregate(limit=limit, hours=hours)
        stats = get_knowledge_graph().ingest_articles(articles)
        return {"status": "ok", "ingested": stats}
    except Exception as exc:
        logger.error("Knowledge ingestion error: %s", exc, exc_info=True)
        return {"status": "error", "message": str(exc)}


@router.get("/entities")
def list_entities(
    limit: int = Query(100, ge=1, le=1000),
) -> Dict[str, Any]:
    """Return entity nodes stored in the knowledge graph."""
    entities = get_knowledge_graph().get_entities(limit=limit)
    return {"entities": entities, "total": len(entities)}


@router.get("/relations")
def list_relations(
    limit: int = Query(200, ge=1, le=2000),
) -> Dict[str, Any]:
    """Return relation edges stored in the knowledge graph."""
    relations = get_knowledge_graph().get_relations(limit=limit)
    return {"relations": relations, "total": len(relations)}


@router.get("/neighbours")
def get_neighbours(
    entity: str = Query(..., min_length=1, description="Entity name to look up"),
    depth: int = Query(1, ge=1, le=3),
) -> Dict[str, Any]:
    """Return the neighbour entities of a named entity."""
    neighbours = get_knowledge_graph().get_neighbours(entity, depth=depth)
    return {"entity": entity, "neighbours": neighbours, "total": len(neighbours)}


@lru_cache(maxsize=128)
def _cached_cypher_query(query: str) -> Tuple[Any, ...]:
    """Execute and cache a Cypher query. Returns results as a tuple for hashability."""
    results = get_knowledge_graph().cypher_query(query)
    return tuple(results)


@router.post("/query")
def run_cypher_query(
    request: QueryRequest,
) -> Dict[str, Any]:
    """Execute a Cypher query against the knowledge graph (Kuzu backend only).

    Example::

        POST /knowledge/query
        {"query": "MATCH (e:Entity) RETURN e.name, e.type LIMIT 10"}
    """
    try:
        results = list(_cached_cypher_query(request.query))
        return {"results": results, "total": len(results)}
    except Exception as exc:
        logger.error("Cypher query error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/query")
def query_knowledge(
    query: str = Query(..., min_length=5, description="Cypher query string"),
) -> Dict[str, Any]:
    """Execute a Cypher query via query parameter (cached).

    Example::

        GET /knowledge/query?query=MATCH (e:Entity) RETURN e.name, e.type LIMIT 10
    """
    try:
        results = list(_cached_cypher_query(query))
        return {"results": results, "total": len(results)}
    except Exception as exc:
        logger.error("Cypher query error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/stats")
def graph_stats() -> Dict[str, Any]:
    """Return knowledge graph statistics (node and edge counts)."""
    return get_knowledge_graph().stats()


@router.post("/extract")
def extract_from_text(
    request: ExtractRequest,
) -> Dict[str, Any]:
    """Extract entities and relations from arbitrary text and persist to the knowledge graph.

    Request body::

        {"text": "Federal Reserve raises rates amid inflation fears."}

    Returns extracted triples along with summary counts.
    """
    from app.knowledge.entity_extractor import EntityRelationExtractor

    try:
        result = EntityRelationExtractor().extract(request.text)
        # Normalize entity fields: always include name, type, description, confidence
        def _safe_confidence(val: Any, default: float = 0.7) -> float:
            try:
                return float(val)
            except (TypeError, ValueError):
                return default

        entities = [
            {
                "name": e.get("name", ""),
                "type": e.get("type", ""),
                "description": e.get("description", ""),
                "confidence": _safe_confidence(e.get("confidence"), 0.7),
            }
            for e in result.get("entities", [])
        ]
        # Normalize relation fields: subject / predicate / object
        relations = [
            {
                "subject": r.get("from", ""),
                "predicate": r.get("relation", ""),
                "object": r.get("to", ""),
            }
            for r in result.get("relations", [])
        ]

        # Persist entities and relations to the knowledge graph
        kg = get_knowledge_graph()
        for entity in entities:
            name = entity["name"].strip()
            if name:
                kg.add_entity(name, entity["type"] or _DEFAULT_ENTITY_TYPE)
        for rel in relations:
            from_name = rel["subject"].strip()
            to_name = rel["object"].strip()
            if from_name and to_name:
                kg.add_relation(
                    from_name=from_name,
                    from_type=_DEFAULT_ENTITY_TYPE,
                    to_name=to_name,
                    to_type=_DEFAULT_ENTITY_TYPE,
                    relation_type=rel["predicate"] or "related_to",
                    weight=_DEFAULT_RELATION_WEIGHT,
                )

        return {
            "status": "ok",
            "entities": entities,
            "relations": relations,
            "nodes_count": len(entities),
            "edges_count": len(relations),
        }
    except Exception as exc:
        logger.error("Knowledge extraction error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
