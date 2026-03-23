"""
Knowledge Graph API routes.

Endpoints:
  POST /knowledge/ingest          – ingest articles into the knowledge graph
  GET  /knowledge/entities        – list entity nodes
  GET  /knowledge/relations       – list relation edges
  GET  /knowledge/neighbours      – get neighbours of a named entity
  POST /knowledge/query           – run a Cypher query (Kuzu backend only)
  GET  /knowledge/stats           – graph statistics
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Query

from app.knowledge.knowledge_graph import get_knowledge_graph

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/knowledge", tags=["knowledge"])


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


@router.post("/query")
def run_cypher_query(
    query: str = Body(..., embed=True, description="Cypher query string"),
) -> Dict[str, Any]:
    """Execute a Cypher query against the knowledge graph (Kuzu backend only).

    Example::

        POST /knowledge/query
        {"query": "MATCH (e:Entity) RETURN e.name, e.type LIMIT 10"}
    """
    results = get_knowledge_graph().cypher_query(query)
    return {"results": results, "total": len(results)}


@router.get("/stats")
def graph_stats() -> Dict[str, Any]:
    """Return knowledge graph statistics (node and edge counts)."""
    return get_knowledge_graph().stats()
