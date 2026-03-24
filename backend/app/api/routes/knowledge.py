"""
Knowledge Graph API routes.

Endpoints:
  POST /knowledge/ingest                       – ingest articles into the knowledge graph
  GET  /knowledge/entities                     – list entity nodes
  GET  /knowledge/relations                    – list relation edges
  GET  /knowledge/neighbours                   – get neighbours of a named entity
  POST /knowledge/query                        – run a Cypher query (Kuzu backend only)
  GET  /knowledge/query                        – run a Cypher query via query parameter (cached)
  GET  /knowledge/stats                        – graph statistics
  POST /knowledge/extract                      – extract entities/relations from text and persist
  POST /knowledge/extract-incremental          – incremental delta-update extraction with conflict detection
  POST /knowledge/filter                       – evaluate and filter triples via Order Critic Agent
  GET  /knowledge/graph/hierarchy              – degree-filtered hierarchical graph
  GET  /knowledge/graph/node-narrative/{name}  – Order Narrative for a single node
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


class FilterRequest(BaseModel):
    triples: List[Dict[str, Any]] = Field(
        ...,
        description=(
            "List of raw triples to evaluate. Each triple should contain "
            "'subject' (or 'from'), 'relation' (or 'predicate'), and 'object' (or 'to') keys."
        ),
    )
    min_order_score: float = Field(
        default=50.0,
        ge=0.0,
        le=100.0,
        description="Minimum order score threshold (overridden by mode if provided)",
    )
    mode: str = Field(
        default="balanced",
        description="Filter mode: 'strict' (keep score>=80) or 'balanced' (keep score>=50)",
    )


class CausalChainRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=10,
        max_length=10000,
        description="News text to extract causal chains from",
    )
    model: str = Field(
        default="llama3-8b-8192",
        description="LLM model name to use for extraction",
    )


class IncrementalExtractRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=10,
        max_length=10000,
        description="Raw text to extract entities and relations from",
    )
    source_url: str = Field(
        default="",
        description="URL of the source article (used in audit logs)",
    )
    source_reliability: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Reliability of the source (0.0–1.0)",
    )
    incremental: bool = Field(
        default=True,
        description="When True (default) use incremental update logic; "
                    "when False fall back to simple insert behaviour",
    )


class CritiqueRequest(BaseModel):
    entities: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of extracted entities",
    )
    relations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of extracted relations",
    )
    causal_chains: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of causal chains extracted from the text",
    )


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


@router.post("/extract-incremental")
def extract_incremental(
    request: IncrementalExtractRequest,
) -> Dict[str, Any]:
    """Extract entities/relations with incremental delta-update logic.

    Unlike the basic ``/extract`` endpoint which always inserts or overwrites,
    this endpoint:

    * Performs **entity disambiguation** via fuzzy string matching to detect
      whether a newly extracted entity already exists in the graph.
    * Performs **conflict detection** on relations: if a new relation
      contradicts an existing one (e.g. *raises* vs *cuts* for the same pair),
      a ``CONTRADICTS`` edge is created instead of inserting the new relation.
    * Returns a structured summary with counts of insertions and conflicts.

    Set ``incremental=false`` to fall back to the simple insert behaviour of
    the ``/extract`` endpoint.

    Request body::

        {
            "text": "The ECB cut interest rates today despite earlier guidance...",
            "source_url": "https://example.com/article",
            "source_reliability": 0.8,
            "incremental": true
        }

    Returns entities, relations, and a metrics summary including
    ``conflicts_found`` and ``contradicts_created``.
    """
    from app.knowledge.entity_extractor import EntityRelationExtractor

    try:
        result = EntityRelationExtractor().extract(request.text)

        def _safe_float(val: Any, default: float) -> float:
            try:
                return float(val)
            except (TypeError, ValueError):
                return default

        entities = [
            {
                "name": e.get("name", ""),
                "type": e.get("type", ""),
                "description": e.get("description", ""),
                "confidence": _safe_float(e.get("confidence"), 0.7),
            }
            for e in result.get("entities", [])
        ]
        relations = [
            {
                "from": r.get("from", ""),
                "relation": r.get("relation", ""),
                "to": r.get("to", ""),
                "weight": _safe_float(r.get("weight"), _DEFAULT_RELATION_WEIGHT),
            }
            for r in result.get("relations", [])
        ]

        if request.incremental:
            from knowledge_layer.incremental_extractor import incremental_update

            kg = get_knowledge_graph()
            summary = incremental_update(
                entities=entities,
                relations=relations,
                source_reliability=request.source_reliability,
                source_url=request.source_url,
                store=kg,
            )
        else:
            # Non-incremental path: simple insert (mirrors /extract behaviour)
            kg = get_knowledge_graph()
            for entity in entities:
                name = entity["name"].strip()
                if name:
                    kg.add_entity(name, entity["type"] or _DEFAULT_ENTITY_TYPE)
            for rel in relations:
                from_name = rel["from"].strip()
                to_name = rel["to"].strip()
                if from_name and to_name:
                    kg.add_relation(
                        from_name=from_name,
                        from_type=_DEFAULT_ENTITY_TYPE,
                        to_name=to_name,
                        to_type=_DEFAULT_ENTITY_TYPE,
                        relation_type=rel["relation"] or "related_to",
                        weight=rel["weight"],
                    )
            summary = {
                "entities_added": len([e for e in entities if e["name"].strip()]),
                "entities_merged": 0,
                "relations_added": len(
                    [r for r in relations if r["from"].strip() and r["to"].strip()]
                ),
                "conflicts_found": 0,
                "contradicts_created": 0,
                "contradictions": [],
            }

        return {
            "status": "ok",
            "incremental": request.incremental,
            "source_url": request.source_url,
            "source_reliability": request.source_reliability,
            "entities": entities,
            "relations": relations,
            **summary,
        }
    except Exception as exc:
        logger.error("Incremental extraction error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/filter")
def filter_triples(
    request: FilterRequest,
) -> Dict[str, Any]:
    """Evaluate and filter knowledge triples using the Order Critic Agent.

    The Order Critic assigns an *order score* (0–100) to each triple, reflecting
    how structurally significant the knowledge is for civilisation-level reasoning.
    Trivial information (celebrity gossip, market noise) is filtered out; triples
    about technology breakthroughs, geopolitical shifts, institutional changes, and
    causal chains are preserved.

    Request body::

        {
            "triples": [
                {"subject": "Federal Reserve", "relation": "raises", "object": "interest rates"},
                {"subject": "Taylor Swift",    "relation": "attends", "object": "Grammy Awards"}
            ],
            "min_order_score": 50,
            "mode": "balanced"
        }

    Returns a list of evaluated triples that passed the threshold, sorted by
    order_score descending.
    """
    try:
        from knowledge_layer.order_critic import OrderCritic

        valid_modes = {"strict", "balanced"}
        mode = request.mode if request.mode in valid_modes else "balanced"

        critic = OrderCritic()
        ordered = critic.filter_triples(
            triples=request.triples,
            min_order_score=request.min_order_score,
            mode=mode,  # type: ignore[arg-type]
        )
        return {
            "status": "ok",
            "mode": mode,
            "threshold": 80.0 if mode == "strict" else 50.0,
            "total_input": len(request.triples),
            "total_passed": len(ordered),
            "triples": [t.to_dict() for t in ordered],
        }
    except Exception as exc:
        logger.error("Order Critic filter error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/extract-causal-chains")
def extract_causal_chains(
    request: CausalChainRequest,
) -> Dict[str, Any]:
    """Extract deep causal chains from news text using an enhanced LLM prompt.

    Unlike the basic ``/extract`` endpoint which only captures surface-level
    subject-predicate-object triples, this endpoint uses a specialised causal-chain
    extraction prompt to uncover multi-step influence paths hidden in the text.

    Request body::

        {"text": "美国对中国芯片产业实施新制裁…", "model": "llama3-8b-8192"}

    Returns entities, direct relations, causal chains with confidence scores,
    longevity, impact scope, reversibility, and an overall order score.
    """
    try:
        from knowledge_layer.causal_chain_extractor import extract_causal_chains as _extract

        result = _extract(news_text=request.text, model=request.model)
        return {"status": "ok", **result}
    except Exception as exc:
        logger.error("Causal chain extraction error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/critique")
def generate_order_critique(
    request: CritiqueRequest,
) -> Dict[str, Any]:
    """Generate a philosophical critique of system stability from knowledge graph data.

    Calls the Order Critic agent to produce a paragraph-length philosophical
    explanation of why the supplied entities, relations, and causal chains are
    important for civilisational-level reasoning and system stability.

    Request body::

        {
            "entities":      [{"name": "...", "type": "..."}],
            "relations":     [{"from": "...", "to": "...", "type": "..."}],
            "causal_chains": [{"chain": "A → B → C", "confidence": 0.85, ...}]
        }

    Returns a ``critique`` string and an ``order_score`` integer (0–100).
    """
    try:
        from knowledge_layer.causal_chain_extractor import calculate_overall_order_score
        from knowledge_layer.order_critic import OrderCritic

        critic = OrderCritic()
        critique_text = critic.generate_philosophical_critique(
            entities=request.entities,
            relations=request.relations,
            causal_chains=request.causal_chains,
        )
        order_score = calculate_overall_order_score(
            request.entities, request.relations, request.causal_chains
        )
        return {
            "status": "ok",
            "critique": critique_text,
            "order_score": order_score,
        }
    except Exception as exc:
        logger.error("Order critique generation error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Hierarchical graph endpoints
# ---------------------------------------------------------------------------

def _compute_degree_map(relations: List[Dict[str, Any]]) -> Dict[str, int]:
    """Return a mapping from node name to its total degree (in + out)."""
    degree: Dict[str, int] = {}
    for rel in relations:
        from_node = rel.get("from", "")
        to_node = rel.get("to", "")
        if from_node:
            degree[from_node] = degree.get(from_node, 0) + 1
        if to_node:
            degree[to_node] = degree.get(to_node, 0) + 1
    return degree


def _importance_tier(degree: int) -> str:
    """Map a node degree to an importance tier label."""
    if degree >= 10:
        return "Critical"
    if degree >= 5:
        return "Important"
    if degree >= 2:
        return "Bridge"
    return "Leaf"


def _global_role_narrative(
    node_name: str,
    importance_tier: str,
    degree: int,
    connections: List[Dict[str, Any]],
) -> str:
    """Generate a short narrative describing a node's role in the global order."""
    tier_descriptions = {
        "Critical": f"{node_name} is a **critical hub** in the global order network",
        "Important": f"{node_name} is an **important node** driving order transitions",
        "Bridge": f"{node_name} connects different domains as an **information bridge**",
        "Leaf": f"{node_name} is an **information source** at the edge of the network",
    }
    base = tier_descriptions.get(importance_tier, f"{node_name} is part of the network")
    if importance_tier == "Critical":
        return (
            f"{base}, with {degree} connections. "
            "This entity's actions directly reshape the global order."
        )
    if importance_tier == "Important":
        return (
            f"{base}, with {degree} connections. "
            "It is a key link between multiple domains."
        )
    if importance_tier == "Bridge":
        return (
            f"{base}, with {degree} connections. "
            f"It integrates different order dimensions through {len(connections)} main links."
        )
    return f"{base}, with {degree} connections. It provides foundational information to the network."


@router.get("/graph/hierarchy")
def get_hierarchical_graph(
    min_degree: int = Query(0, ge=0, description="Minimum node degree (inclusive)"),
    max_degree: int = Query(100, ge=0, description="Maximum node degree (inclusive)"),
) -> Dict[str, Any]:
    """Return a degree-filtered hierarchical view of the knowledge graph.

    Each node is annotated with its computed degree and importance tier so the
    frontend can apply size/colour styling without further computation.
    """
    kg = get_knowledge_graph()
    entities = kg.get_entities(limit=1000)
    relations = kg.get_relations(limit=2000)

    degree_map = _compute_degree_map(relations)

    # Filter nodes by degree range
    filtered_entities = [
        e for e in entities
        if min_degree <= degree_map.get(e.get("name", ""), 0) <= max_degree
    ]
    filtered_names = {e.get("name", "") for e in filtered_entities}

    # Only keep edges whose both endpoints are in the filtered set
    filtered_relations = [
        r for r in relations
        if r.get("from") in filtered_names and r.get("to") in filtered_names
    ]

    nodes_out = [
        {
            "id": e.get("name", ""),
            "label": e.get("name", ""),
            "type": e.get("type", _DEFAULT_ENTITY_TYPE),
            "degree": degree_map.get(e.get("name", ""), 0),
            "properties": e,
        }
        for e in filtered_entities
    ]

    edges_out = [
        {
            "from": r.get("from", ""),
            "to": r.get("to", ""),
            "type": r.get("relation", ""),
            "weight": r.get("weight", _DEFAULT_RELATION_WEIGHT),
        }
        for r in filtered_relations
    ]

    return {
        "nodes": nodes_out,
        "edges": edges_out,
        "degree_map": degree_map,
        "total_nodes": len(nodes_out),
        "total_edges": len(edges_out),
    }


@router.get("/graph/node-narrative/{node_name}")
def get_node_order_narrative(node_name: str) -> Dict[str, Any]:
    """Return the Order Narrative for a single node.

    Includes its definition, degree, importance tier, main connections, and a
    short philosophical description of its role in the global order.
    """
    kg = get_knowledge_graph()
    entities = kg.get_entities(limit=1000)
    entity = next((e for e in entities if e.get("name") == node_name), None)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Node '{node_name}' not found")

    relations = kg.get_relations(limit=2000)
    degree = sum(
        1 for r in relations
        if r.get("from") == node_name or r.get("to") == node_name
    )

    # Collect up to 5 main connections
    main_connections: List[Dict[str, Any]] = []
    for rel in relations:
        if len(main_connections) >= 5:
            break
        if rel.get("from") == node_name:
            main_connections.append({
                "target": rel.get("to", ""),
                "relation": rel.get("relation", ""),
                "weight": rel.get("weight", _DEFAULT_RELATION_WEIGHT),
            })
        elif rel.get("to") == node_name:
            main_connections.append({
                "source": rel.get("from", ""),
                "relation": rel.get("relation", ""),
                "weight": rel.get("weight", _DEFAULT_RELATION_WEIGHT),
            })

    tier = _importance_tier(degree)
    global_role = _global_role_narrative(node_name, tier, degree, main_connections)

    node_type = entity.get("type", _DEFAULT_ENTITY_TYPE)
    return {
        "node_id": node_name,
        "node_name": node_name,
        "node_type": node_type,
        "degree": degree,
        "importance_tier": tier,
        "definition": entity.get("definition", f"An entity of type {node_type}"),
        "main_connections": main_connections,
        "global_role": global_role,
        "betweenness_centrality": 0.0,  # placeholder for future centrality computation
    }
