"""
Knowledge Graph – high-level interface combining entity extraction and graph storage.

This is the primary entry-point for Phase 1 knowledge-layer operations:
  1. Ingest articles → extract entities/relations → store in graph
  2. Query the graph (neighbours, Cypher, stats)

Usage::

    from app.knowledge.knowledge_graph import KnowledgeGraph

    kg = KnowledgeGraph()
    kg.ingest_articles(articles)
    neighbours = kg.get_neighbours("Federal Reserve")
    print(kg.stats())
"""

from __future__ import annotations

import hashlib
import logging
from functools import lru_cache
from typing import Any, Dict, List, Optional

from app.knowledge.entity_extractor import EntityRelationExtractor
from app.knowledge.graph_store import GraphStore

logger = logging.getLogger(__name__)


def _article_id(link: str, title: str) -> str:
    return hashlib.sha256(f"{link}:{title}".encode()).hexdigest()[:24]


class KnowledgeGraph:
    """High-level knowledge graph manager."""

    def __init__(self, graph_backend: Optional[str] = None) -> None:
        self._store = GraphStore(backend=graph_backend)
        self._extractor = EntityRelationExtractor()

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest_articles(self, articles: List[Dict[str, Any]]) -> Dict[str, int]:
        """Extract entities/relations from *articles* and populate the graph.

        Args:
            articles: List of article dicts (title, description, source, …).

        Returns:
            Dict with counts: entities_added, relations_added, articles_added.
        """
        entities_added = 0
        relations_added = 0
        articles_added = 0

        for article in articles:
            title = article.get("title", "")
            description = article.get("description", "")
            text = f"{title} {description}".strip()
            link = article.get("link", "")
            art_id = _article_id(link, title)

            # Store article node
            self._store.add_article(
                article_id=art_id,
                title=title[:200],
                source=article.get("source", ""),
                published=article.get("published", ""),
                link=link,
                category=article.get("category", "general"),
            )
            articles_added += 1

            # Extract and store entities / relations
            result = self._extractor.extract(text)

            for entity in result.get("entities", []):
                name = entity.get("name", "").strip()
                etype = entity.get("type", "MISC")
                if not name:
                    continue
                self._store.add_entity(name, etype)
                self._store.add_mention(name, art_id, confidence=0.8)
                entities_added += 1

            for rel in result.get("relations", []):
                from_name = rel.get("from", "").strip()
                to_name = rel.get("to", "").strip()
                relation_type = rel.get("relation", "related_to")
                weight = float(rel.get("weight", 0.5))
                if not from_name or not to_name:
                    continue
                self._store.add_relation(
                    from_name=from_name,
                    from_type="MISC",
                    to_name=to_name,
                    to_type="MISC",
                    relation_type=relation_type,
                    weight=weight,
                )
                relations_added += 1

        logger.info(
            "Ingested %d articles → %d entities, %d relations",
            articles_added, entities_added, relations_added,
        )
        return {
            "entities_added": entities_added,
            "relations_added": relations_added,
            "articles_added": articles_added,
        }

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def get_entities(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return all entity nodes."""
        return self._store.get_entities(limit=limit)

    def get_relations(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Return all relation edges."""
        return self._store.get_relations(limit=limit)

    def get_neighbours(self, entity_name: str, depth: int = 1) -> List[Dict[str, Any]]:
        """Return neighbour entities of *entity_name*."""
        return self._store.get_neighbours(entity_name, depth=depth)

    def cypher_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute a raw Cypher (Kuzu) query."""
        return self._store.cypher_query(query)

    def stats(self) -> Dict[str, Any]:
        """Return graph statistics."""
        return self._store.stats()

    def add_entity(self, name: str, entity_type: str) -> None:
        """Add a single entity node to the graph."""
        self._store.add_entity(name, entity_type)

    def add_relation(
        self,
        from_name: str,
        from_type: str,
        to_name: str,
        to_type: str,
        relation_type: str,
        weight: float = 0.5,
    ) -> None:
        """Add a single relation edge to the graph."""
        self._store.add_relation(
            from_name=from_name,
            from_type=from_type,
            to_name=to_name,
            to_type=to_type,
            relation_type=relation_type,
            weight=weight,
        )

    def add_contradicts(
        self,
        from_name: str,
        to_name: str,
        reason: str,
        confidence: float = 0.8,
        source_reliability: float = 0.7,
    ) -> None:
        """Add a CONTRADICTS edge between two entity nodes."""
        self._store.add_contradicts(
            from_name=from_name,
            to_name=to_name,
            reason=reason,
            confidence=confidence,
            source_reliability=source_reliability,
        )

    def get_contradicts(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Return all CONTRADICTS edges stored in the knowledge graph."""
        return self._store.get_contradicts(limit=limit)


@lru_cache(maxsize=1)
def get_knowledge_graph() -> KnowledgeGraph:
    """Return the cached singleton KnowledgeGraph instance."""
    return KnowledgeGraph()
