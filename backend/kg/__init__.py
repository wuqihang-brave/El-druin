"""
Knowledge Layer for EL'druin Intelligence Platform
====================================================

Extracts entities and relations from news text using LangChain's
LLMGraphTransformer, stores the resulting graph in both NetworkX
(in-memory) and Kuzu (embedded persistent triple store).

Typical usage::

    from kg import KGExtractor, GraphBuilder

    extractor = KGExtractor()
    triples = extractor.extract("Apple CEO Tim Cook announced new iPhone.")

    builder = GraphBuilder()
    builder.add_triples(triples)
    G = builder.get_networkx_graph()
"""

from kg.models import Entity, Relation, Triple  # noqa: F401
from kg.llm_extractor import KGExtractor  # noqa: F401
from kg.graph_builder import GraphBuilder  # noqa: F401
from kg.cache import cached_extract  # noqa: F401

__all__ = [
    "Entity",
    "Relation",
    "Triple",
    "KGExtractor",
    "GraphBuilder",
    "cached_extract",
]
