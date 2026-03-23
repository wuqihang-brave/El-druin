"""
Knowledge-graph builder for EL'druin.

Persists extracted :class:`~kg.models.Triple` objects in two stores:

1. **NetworkX DiGraph** – fast in-memory graph for analysis and traversal.
2. **Kuzu** embedded graph database – persistent triple store.

The Kuzu store is optional: if the ``kuzu`` package is not installed the
builder silently skips that step and logs a warning.

Parameters
----------
kuzu_db_path:
    File-system path for the Kuzu database directory.  Defaults to
    ``./kg_database``.  Set to ``None`` to disable Kuzu persistence.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Tuple

import networkx as nx  # type: ignore

from kg.models import Triple

logger = logging.getLogger(__name__)

_DEFAULT_KUZU_PATH = os.getenv("KUZU_DB_PATH", "./kg_database")

# ---------------------------------------------------------------------------
# Kuzu schema DDL
# ---------------------------------------------------------------------------

_KUZU_SCHEMA_DDL = [
    # Node tables
    "CREATE NODE TABLE IF NOT EXISTS Entity "
    "(name STRING, entity_type STRING, description STRING, PRIMARY KEY (name))",
    # Edge table
    "CREATE REL TABLE IF NOT EXISTS Relation "
    "(FROM Entity TO Entity, relation_type STRING, description STRING, "
    "confidence DOUBLE, source_text STRING)",
]


# ---------------------------------------------------------------------------
# GraphBuilder
# ---------------------------------------------------------------------------

class GraphBuilder:
    """Build and query a knowledge graph from extracted triples.

    The graph is simultaneously maintained in:
    * a ``networkx.DiGraph`` (always available, in-memory only), and
    * a Kuzu embedded database (persistent, optional).

    Parameters
    ----------
    kuzu_db_path:
        Path for the Kuzu database directory.  Pass ``None`` to disable.
    """

    def __init__(self, kuzu_db_path: Optional[str] = _DEFAULT_KUZU_PATH) -> None:
        self._nx_graph: nx.DiGraph = nx.DiGraph()
        self._kuzu_db_path = kuzu_db_path
        self._kuzu_db = None
        self._kuzu_conn = None

        if kuzu_db_path is not None:
            self._init_kuzu(kuzu_db_path)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def add_triple(self, triple: Triple) -> None:
        """Insert a single triple into both NetworkX and Kuzu stores.

        Args:
            triple: The :class:`~kg.models.Triple` to insert.
        """
        self._add_to_networkx(triple)
        if self._kuzu_conn is not None:
            self._add_to_kuzu(triple)

    def add_triples(self, triples: List[Triple]) -> None:
        """Bulk-insert a list of triples.

        Args:
            triples: Iterable of :class:`~kg.models.Triple` objects.
        """
        for triple in triples:
            self.add_triple(triple)
        logger.info("Added %d triples to graph (total nodes: %d, edges: %d)",
                    len(triples),
                    self._nx_graph.number_of_nodes(),
                    self._nx_graph.number_of_edges())

    def get_networkx_graph(self) -> nx.DiGraph:
        """Return the in-memory NetworkX DiGraph.

        Returns:
            A ``networkx.DiGraph`` where each node carries ``entity_type``
            and ``description`` attributes, and each edge carries
            ``relation_type``, ``description``, ``confidence``, and
            ``source_text`` attributes.
        """
        return self._nx_graph

    def query_neighbors(
        self, entity_name: str, relation_type: Optional[str] = None
    ) -> List[Tuple[str, str, Dict]]:
        """Return immediate neighbours of *entity_name*.

        Args:
            entity_name:   The entity to look up.
            relation_type: Optional filter (e.g. ``"WORKS_FOR"``).

        Returns:
            List of ``(source, target, edge_data)`` tuples.
        """
        if entity_name not in self._nx_graph:
            return []

        results: List[Tuple[str, str, Dict]] = []
        for src, tgt, data in self._nx_graph.out_edges(entity_name, data=True):
            if relation_type and data.get("relation_type") != relation_type:
                continue
            results.append((src, tgt, data))
        for src, tgt, data in self._nx_graph.in_edges(entity_name, data=True):
            if relation_type and data.get("relation_type") != relation_type:
                continue
            results.append((src, tgt, data))
        return results

    def get_entity_info(self, entity_name: str) -> Optional[Dict]:
        """Return node attributes for *entity_name*, or ``None`` if absent.

        Args:
            entity_name: The entity to look up.

        Returns:
            Dict of node attributes or ``None``.
        """
        if entity_name not in self._nx_graph:
            return None
        return dict(self._nx_graph.nodes[entity_name])

    def summary(self) -> Dict:
        """Return a summary dict with graph statistics.

        Returns:
            Dict with ``nodes``, ``edges``, and ``density`` keys.
        """
        n = self._nx_graph.number_of_nodes()
        e = self._nx_graph.number_of_edges()
        return {
            "nodes": n,
            "edges": e,
            "density": nx.density(self._nx_graph) if n > 1 else 0.0,
        }

    def close(self) -> None:
        """Close the Kuzu database connection."""
        if self._kuzu_conn is not None:
            try:
                self._kuzu_conn.close()
            except Exception:
                pass
            self._kuzu_conn = None
        if self._kuzu_db is not None:
            self._kuzu_db = None

    # ------------------------------------------------------------------
    # NetworkX helpers
    # ------------------------------------------------------------------

    def _add_to_networkx(self, triple: Triple) -> None:
        subj = triple.subject
        obj = triple.obj
        pred = triple.predicate

        if subj.name not in self._nx_graph:
            self._nx_graph.add_node(
                subj.name,
                entity_type=subj.entity_type,
                description=subj.description or "",
            )
        if obj.name not in self._nx_graph:
            self._nx_graph.add_node(
                obj.name,
                entity_type=obj.entity_type,
                description=obj.description or "",
            )

        self._nx_graph.add_edge(
            subj.name,
            obj.name,
            relation_type=pred.relation_type,
            description=pred.description or "",
            confidence=triple.confidence,
            source_text=triple.source_text or "",
        )

    # ------------------------------------------------------------------
    # Kuzu helpers
    # ------------------------------------------------------------------

    def _init_kuzu(self, db_path: str) -> None:
        """Initialise the Kuzu database and create schema if needed."""
        try:
            import kuzu  # type: ignore

            os.makedirs(db_path, exist_ok=True)
            self._kuzu_db = kuzu.Database(db_path)
            self._kuzu_conn = kuzu.Connection(self._kuzu_db)
            self._ensure_schema()
            logger.info("Kuzu database initialised at %s", db_path)
        except ImportError:
            logger.warning(
                "kuzu package not installed – persistent triple store disabled. "
                "Install with: pip install kuzu"
            )
        except Exception as exc:
            logger.error("Failed to initialise Kuzu database: %s", exc, exc_info=True)
            self._kuzu_db = None
            self._kuzu_conn = None

    def _ensure_schema(self) -> None:
        """Run DDL statements to create node/edge tables if they don't exist."""
        for ddl in _KUZU_SCHEMA_DDL:
            try:
                self._kuzu_conn.execute(ddl)  # type: ignore[union-attr]
            except Exception as exc:
                logger.debug("Schema DDL skipped (%s): %s", ddl[:60], exc)

    def _add_to_kuzu(self, triple: Triple) -> None:
        """Insert a triple into Kuzu, upserting nodes first."""
        try:
            self._upsert_entity(triple.subject)
            self._upsert_entity(triple.obj)

            rel_query = (
                "MATCH (s:Entity {name: $src}), (t:Entity {name: $tgt}) "
                "CREATE (s)-[:Relation {relation_type: $rel_type, "
                "description: $desc, confidence: $conf, source_text: $src_text}]->(t)"
            )
            self._kuzu_conn.execute(  # type: ignore[union-attr]
                rel_query,
                parameters={
                    "src": triple.subject.name,
                    "tgt": triple.obj.name,
                    "rel_type": triple.predicate.relation_type,
                    "desc": triple.predicate.description or "",
                    "conf": triple.confidence,
                    "src_text": (triple.source_text or "")[:500],
                },
            )
        except Exception as exc:
            logger.error(
                "Failed to insert triple (%s → %s) into Kuzu: %s",
                triple.subject_name,
                triple.object_name,
                exc,
            )

    def _upsert_entity(self, entity) -> None:
        """Insert entity node if it does not already exist."""
        try:
            # Kuzu does not have MERGE; use a conditional INSERT
            check_q = "MATCH (e:Entity {name: $name}) RETURN e.name LIMIT 1"
            result = self._kuzu_conn.execute(check_q, parameters={"name": entity.name})  # type: ignore[union-attr]
            if not result.has_next():
                insert_q = (
                    "CREATE (:Entity {name: $name, entity_type: $etype, description: $desc})"
                )
                self._kuzu_conn.execute(  # type: ignore[union-attr]
                    insert_q,
                    parameters={
                        "name": entity.name,
                        "etype": entity.entity_type,
                        "desc": entity.description or "",
                    },
                )
        except Exception as exc:
            logger.error("Failed to upsert entity %s: %s", entity.name, exc)
