"""Knowledge layer: entity extraction, graph storage, and querying."""

from app.knowledge.kuzu_graph import (  # noqa: F401
    KuzuKnowledgeGraph,
    insert_triples,
    query_graph,
)
