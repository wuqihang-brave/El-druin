"""
Graph Store – abstract interface over Kuzu (primary) and NetworkX (fallback).

The graph models two node types:
  - **Entity**  (name, type, description)
  - **Article** (title, source, published, link, category)

And two relationship types:
  - Entity –[MENTIONED_IN]→ Article
  - Entity –[RELATED_TO]→ Entity  (with relation_type and weight attributes)

Usage::

    from app.knowledge.graph_store import GraphStore

    store = GraphStore()
    store.add_entity("Federal Reserve", "ORG", "US central bank")
    store.add_article("...", "Reuters", ...)
    store.add_mention("Federal Reserve", "article-id-123")
    store.add_relation("Federal Reserve", "ORG", "USA", "GPE", "operates_in", 0.9)
    neighbours = store.get_neighbours("Federal Reserve")
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Kuzu-backed store
# ---------------------------------------------------------------------------

class _KuzuStore:
    """Graph store backed by an embedded Kuzu database."""

    def __init__(self, db_path: str) -> None:
        import kuzu  # type: ignore

        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._db = kuzu.Database(db_path)
        self._conn = kuzu.Connection(self._db)
        self._init_schema()

    def _init_schema(self) -> None:
        stmts = [
            "CREATE NODE TABLE IF NOT EXISTS Entity(name STRING, type STRING, description STRING, PRIMARY KEY(name))",
            "CREATE NODE TABLE IF NOT EXISTS Article(id STRING, title STRING, source STRING, published STRING, link STRING, category STRING, PRIMARY KEY(id))",
            "CREATE REL TABLE IF NOT EXISTS MENTIONED_IN(FROM Entity TO Article, confidence DOUBLE)",
            "CREATE REL TABLE IF NOT EXISTS RELATED_TO(FROM Entity TO Entity, relation_type STRING, weight DOUBLE)",
            "CREATE REL TABLE IF NOT EXISTS CONTRADICTS(FROM Entity TO Entity,"
            " reason STRING, confidence DOUBLE, source_reliability DOUBLE, timestamp TIMESTAMP)",
        ]
        for stmt in stmts:
            try:
                self._conn.execute(stmt)
            except Exception as exc:
                logger.debug("Schema init: %s", exc)

    def add_entity(self, name: str, entity_type: str, description: str = "") -> None:
        try:
            self._conn.execute(
                "MERGE (e:Entity {name: $name}) SET e.type = $type, e.description = $desc",
                {"name": name, "type": entity_type, "desc": description},
            )
        except Exception:
            try:
                self._conn.execute(
                    "CREATE (e:Entity {name: $name, type: $type, description: $desc})",
                    {"name": name, "type": entity_type, "desc": description},
                )
            except Exception as exc:
                logger.debug("add_entity: %s", exc)

    def add_article(
        self,
        article_id: str,
        title: str,
        source: str,
        published: str,
        link: str,
        category: str,
    ) -> None:
        try:
            self._conn.execute(
                "MERGE (a:Article {id: $id}) SET a.title=$title, a.source=$source, "
                "a.published=$pub, a.link=$link, a.category=$cat",
                {"id": article_id, "title": title, "source": source,
                 "pub": published, "link": link, "cat": category},
            )
        except Exception:
            try:
                self._conn.execute(
                    "CREATE (a:Article {id:$id,title:$title,source:$source,"
                    "published:$pub,link:$link,category:$cat})",
                    {"id": article_id, "title": title, "source": source,
                     "pub": published, "link": link, "cat": category},
                )
            except Exception as exc:
                logger.debug("add_article: %s", exc)

    def add_mention(self, entity_name: str, article_id: str, confidence: float = 0.8) -> None:
        try:
            self._conn.execute(
                "MATCH (e:Entity {name:$ename}), (a:Article {id:$aid}) "
                "CREATE (e)-[:MENTIONED_IN {confidence:$conf}]->(a)",
                {"ename": entity_name, "aid": article_id, "conf": confidence},
            )
        except Exception as exc:
            logger.debug("add_mention: %s", exc)

    def add_relation(
        self,
        from_name: str,
        from_type: str,
        to_name: str,
        to_type: str,
        relation_type: str,
        weight: float = 0.5,
    ) -> None:
        self.add_entity(from_name, from_type)
        self.add_entity(to_name, to_type)
        try:
            self._conn.execute(
                "MATCH (a:Entity {name:$fn}), (b:Entity {name:$tn}) "
                "CREATE (a)-[:RELATED_TO {relation_type:$rt, weight:$w}]->(b)",
                {"fn": from_name, "tn": to_name, "rt": relation_type, "w": weight},
            )
        except Exception as exc:
            logger.debug("add_relation: %s", exc)

    def get_neighbours(self, entity_name: str, depth: int = 1) -> List[Dict[str, Any]]:
        try:
            result = self._conn.execute(
                "MATCH (e:Entity {name:$name})-[r:RELATED_TO]-(n:Entity) "
                "RETURN n.name, n.type, r.relation_type, r.weight",
                {"name": entity_name},
            )
            rows = []
            while result.has_next():
                row = result.get_next()
                rows.append({
                    "name": row[0], "type": row[1],
                    "relation": row[2], "weight": row[3],
                })
            return rows
        except Exception as exc:
            logger.debug("get_neighbours: %s", exc)
            return []

    def get_entities(self, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            result = self._conn.execute(
                "MATCH (e:Entity) RETURN e.name, e.type, e.description LIMIT $lim",
                {"lim": limit},
            )
            rows = []
            while result.has_next():
                r = result.get_next()
                rows.append({"name": r[0], "type": r[1], "description": r[2]})
            return rows
        except Exception as exc:
            logger.debug("get_entities: %s", exc)
            return []

    def get_relations(self, limit: int = 200) -> List[Dict[str, Any]]:
        try:
            result = self._conn.execute(
                "MATCH (a:Entity)-[r:RELATED_TO]->(b:Entity) "
                "RETURN a.name, r.relation_type, b.name, r.weight LIMIT $lim",
                {"lim": limit},
            )
            rows = []
            while result.has_next():
                r = result.get_next()
                rows.append({
                    "from": r[0], "relation": r[1],
                    "to": r[2], "weight": r[3],
                })
            return rows
        except Exception as exc:
            logger.debug("get_relations: %s", exc)
            return []

    def cypher_query(self, query: str) -> List[Dict[str, Any]]:
        try:
            result = self._conn.execute(query)
            rows = []
            while result.has_next():
                row = result.get_next()
                rows.append({"values": list(row)})
            return rows
        except Exception as exc:
            logger.warning("Cypher query failed: %s", exc)
            return [{"error": str(exc)}]

    def add_contradicts(
        self,
        from_name: str,
        to_name: str,
        reason: str,
        confidence: float = 0.8,
        source_reliability: float = 0.7,
    ) -> None:
        """Create a CONTRADICTS edge between two Entity nodes.

        Both entity nodes are created (if absent) before the edge is written.

        Parameters
        ----------
        from_name:
            Name of the first entity node.
        to_name:
            Name of the second entity node.
        reason:
            Human-readable explanation of the contradiction.
        confidence:
            Confidence that this is a genuine contradiction (0.0–1.0).
        source_reliability:
            Reliability of the source that reported the contradicting fact.
        """
        import datetime as _dt

        self.add_entity(from_name, "MISC")
        self.add_entity(to_name, "MISC")
        ts = _dt.datetime.now(_dt.timezone.utc)
        try:
            self._conn.execute(
                "MATCH (a:Entity {name:$fn}), (b:Entity {name:$tn})"
                " CREATE (a)-[:CONTRADICTS"
                "  {reason:$reason, confidence:$conf,"
                "   source_reliability:$sr, timestamp:$ts}]->(b)",
                {
                    "fn": from_name,
                    "tn": to_name,
                    "reason": reason,
                    "conf": confidence,
                    "sr": source_reliability,
                    "ts": ts,
                },
            )
        except Exception as exc:
            logger.debug("add_contradicts %s→%s: %s", from_name, to_name, exc)

    def get_contradicts(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Return all CONTRADICTS edges stored in the graph."""
        try:
            result = self._conn.execute(
                "MATCH (a:Entity)-[r:CONTRADICTS]->(b:Entity)"
                " RETURN a.name, b.name, r.reason, r.confidence,"
                "        r.source_reliability, r.timestamp"
                " LIMIT $lim",
                {"lim": limit},
            )
            rows = []
            while result.has_next():
                r = result.get_next()
                rows.append(
                    {
                        "from": r[0],
                        "to": r[1],
                        "reason": r[2],
                        "confidence": r[3],
                        "source_reliability": r[4],
                        "timestamp": str(r[5]) if r[5] else None,
                    }
                )
            return rows
        except Exception as exc:
            logger.debug("get_contradicts: %s", exc)
            return []

    def stats(self) -> Dict[str, Any]:
        counts: Dict[str, Any] = {}
        for label, col in [("entities", "Entity"), ("articles", "Article")]:
            try:
                r = self._conn.execute(f"MATCH (n:{col}) RETURN count(n)")
                if r.has_next():
                    counts[label] = r.get_next()[0]
                else:
                    counts[label] = 0
            except Exception:
                counts[label] = 0
        for label, rel in [("mentions", "MENTIONED_IN"), ("relations", "RELATED_TO"), ("contradicts", "CONTRADICTS")]:
            try:
                r = self._conn.execute(f"MATCH ()-[r:{rel}]->() RETURN count(r)")
                if r.has_next():
                    counts[label] = r.get_next()[0]
                else:
                    counts[label] = 0
            except Exception:
                counts[label] = 0
        return counts


# ---------------------------------------------------------------------------
# NetworkX fallback store (in-memory)
# ---------------------------------------------------------------------------

class _NetworkXStore:
    """In-memory graph store backed by NetworkX. Used as fallback."""

    def __init__(self) -> None:
        import networkx as nx  # type: ignore

        self._graph: Any = nx.MultiDiGraph()
        self._articles: Dict[str, Dict[str, Any]] = {}

    def add_entity(self, name: str, entity_type: str, description: str = "") -> None:
        if not self._graph.has_node(name):
            self._graph.add_node(name, node_type="entity", type=entity_type, description=description)
        else:
            self._graph.nodes[name].update({"type": entity_type, "description": description})

    def add_article(self, article_id: str, title: str, source: str, published: str, link: str, category: str) -> None:
        self._articles[article_id] = {
            "id": article_id, "title": title, "source": source,
            "published": published, "link": link, "category": category,
        }
        if not self._graph.has_node(f"article:{article_id}"):
            self._graph.add_node(
                f"article:{article_id}",
                node_type="article",
                **self._articles[article_id],
            )

    def add_mention(self, entity_name: str, article_id: str, confidence: float = 0.8) -> None:
        self._graph.add_edge(entity_name, f"article:{article_id}", edge_type="MENTIONED_IN", confidence=confidence)

    def add_relation(self, from_name: str, from_type: str, to_name: str, to_type: str, relation_type: str, weight: float = 0.5) -> None:
        self.add_entity(from_name, from_type)
        self.add_entity(to_name, to_type)
        self._graph.add_edge(from_name, to_name, edge_type="RELATED_TO", relation_type=relation_type, weight=weight)

    def add_contradicts(
        self,
        from_name: str,
        to_name: str,
        reason: str,
        confidence: float = 0.8,
        source_reliability: float = 0.7,
    ) -> None:
        """Create a CONTRADICTS edge in the in-memory graph."""
        import datetime as _dt

        self.add_entity(from_name, "MISC")
        self.add_entity(to_name, "MISC")
        self._graph.add_edge(
            from_name,
            to_name,
            edge_type="CONTRADICTS",
            reason=reason,
            confidence=confidence,
            source_reliability=source_reliability,
            timestamp=_dt.datetime.now(_dt.timezone.utc).isoformat(),
        )

    def get_contradicts(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Return all CONTRADICTS edges from the in-memory graph."""
        rows = []
        for u, v, data in self._graph.edges(data=True):
            if data.get("edge_type") == "CONTRADICTS":
                rows.append(
                    {
                        "from": u,
                        "to": v,
                        "reason": data.get("reason", ""),
                        "confidence": data.get("confidence", 0.8),
                        "source_reliability": data.get("source_reliability", 0.7),
                        "timestamp": data.get("timestamp"),
                    }
                )
                if len(rows) >= limit:
                    break
        return rows

    def get_neighbours(self, entity_name: str, depth: int = 1) -> List[Dict[str, Any]]:
        rows = []
        for _, nbr, data in self._graph.out_edges(entity_name, data=True):
            if data.get("edge_type") == "RELATED_TO":
                nbr_data = self._graph.nodes.get(nbr, {})
                rows.append({
                    "name": nbr, "type": nbr_data.get("type", ""),
                    "relation": data.get("relation_type", ""),
                    "weight": data.get("weight", 0.5),
                })
        return rows

    def get_entities(self, limit: int = 100) -> List[Dict[str, Any]]:
        rows = []
        for node, data in self._graph.nodes(data=True):
            if data.get("node_type") == "entity":
                rows.append({
                    "name": node,
                    "type": data.get("type", ""),
                    "description": data.get("description", ""),
                })
                if len(rows) >= limit:
                    break
        return rows

    def get_relations(self, limit: int = 200) -> List[Dict[str, Any]]:
        rows = []
        for u, v, data in self._graph.edges(data=True):
            if data.get("edge_type") == "RELATED_TO":
                rows.append({
                    "from": u, "relation": data.get("relation_type", ""),
                    "to": v, "weight": data.get("weight", 0.5),
                })
                if len(rows) >= limit:
                    break
        return rows

    def cypher_query(self, query: str) -> List[Dict[str, Any]]:
        return [{"error": "Cypher queries not supported in NetworkX mode. Use get_entities() / get_relations()."}]

    def stats(self) -> Dict[str, Any]:
        entity_count = sum(1 for _, d in self._graph.nodes(data=True) if d.get("node_type") == "entity")
        article_count = sum(1 for _, d in self._graph.nodes(data=True) if d.get("node_type") == "article")
        mention_count = sum(1 for _, _, d in self._graph.edges(data=True) if d.get("edge_type") == "MENTIONED_IN")
        relation_count = sum(1 for _, _, d in self._graph.edges(data=True) if d.get("edge_type") == "RELATED_TO")
        contradicts_count = sum(1 for _, _, d in self._graph.edges(data=True) if d.get("edge_type") == "CONTRADICTS")
        return {
            "entities": entity_count,
            "articles": article_count,
            "mentions": mention_count,
            "relations": relation_count,
            "contradicts": contradicts_count,
        }


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------

def create_graph_store(backend: Optional[str] = None) -> Any:
    """Return the appropriate graph store based on configuration.

    Tries Kuzu first; falls back to NetworkX if Kuzu is unavailable.
    """
    settings = get_settings()
    chosen = backend or settings.graph_backend

    if chosen == "kuzu":
        try:
            store = _KuzuStore(settings.kuzu_db_path)
            logger.info("Using Kuzu graph store at %s", settings.kuzu_db_path)
            return store
        except ImportError:
            logger.warning("kuzu not installed; falling back to NetworkX store")
        except Exception as exc:
            logger.warning("Kuzu init failed (%s); falling back to NetworkX", exc)

    if chosen == "neo4j":
        logger.warning("Neo4j backend not yet implemented; falling back to NetworkX")

    logger.info("Using in-memory NetworkX graph store")
    return _NetworkXStore()


class GraphStore:
    """Public façade that delegates to the backend-specific implementation."""

    def __init__(self, backend: Optional[str] = None) -> None:
        self._impl = create_graph_store(backend)

    def add_entity(self, name: str, entity_type: str, description: str = "") -> None:
        self._impl.add_entity(name, entity_type, description)

    def add_article(self, article_id: str, title: str, source: str, published: str, link: str, category: str) -> None:
        self._impl.add_article(article_id, title, source, published, link, category)

    def add_mention(self, entity_name: str, article_id: str, confidence: float = 0.8) -> None:
        self._impl.add_mention(entity_name, article_id, confidence)

    def add_relation(self, from_name: str, from_type: str, to_name: str, to_type: str, relation_type: str, weight: float = 0.5) -> None:
        self._impl.add_relation(from_name, from_type, to_name, to_type, relation_type, weight)

    def add_contradicts(
        self,
        from_name: str,
        to_name: str,
        reason: str,
        confidence: float = 0.8,
        source_reliability: float = 0.7,
    ) -> None:
        """Create a CONTRADICTS edge between two entity nodes."""
        self._impl.add_contradicts(from_name, to_name, reason, confidence, source_reliability)

    def get_contradicts(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Return all CONTRADICTS edges stored in the knowledge graph."""
        return self._impl.get_contradicts(limit)

    def get_neighbours(self, entity_name: str, depth: int = 1) -> List[Dict[str, Any]]:
        return self._impl.get_neighbours(entity_name, depth)

    def get_entities(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._impl.get_entities(limit)

    def get_relations(self, limit: int = 200) -> List[Dict[str, Any]]:
        return self._impl.get_relations(limit)

    def cypher_query(self, query: str) -> List[Dict[str, Any]]:
        return self._impl.cypher_query(query)

    def stats(self) -> Dict[str, Any]:
        return self._impl.stats()
