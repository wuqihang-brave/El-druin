"""
Kuzu Embedded Knowledge Graph Store.

Stores extracted knowledge graph triples in an embedded Kuzu database at
``./data/el_druin.kuzu``.

Schema
------
Node tables (each has ``name``, ``description``, ``confidence`` properties):

* ``Person``       – individual people
* ``Organization`` – companies, agencies, governments, etc.
* ``Location``     – countries, cities, geographic regions
* ``Event``        – occurrences, incidents, conferences, etc.
* ``Entity``       – catch-all for nodes whose type cannot be inferred;
                     also carries an ``entity_type`` STRING column that
                     records the semantic type used by the caller.

Relation tables (all ``FROM Entity TO Entity`` to remain compatible with
Kuzu ≥ 0.11 which does not support multi-label relation tables):

* ``RELATED_TO``      – generic association (``relation_type`` STRING, ``confidence`` DOUBLE)
* ``LOCATED_IN``      – geographic containment or origin (``confidence`` DOUBLE)
* ``PARTICIPATES_IN`` – participation or involvement  (``confidence`` DOUBLE)
* ``WORKS_FOR``       – employment / membership      (``confidence`` DOUBLE)
* ``MEMBER_OF``       – group membership             (``confidence`` DOUBLE)

Usage
-----
::

    from app.knowledge.kuzu_graph import KuzuKnowledgeGraph

    with KuzuKnowledgeGraph() as kg:
        kg.insert_triples([
            ("Xi Jinping", "LOCATED_IN", "China"),
            ("United Nations", "RELATED_TO", "Security Council"),
        ])
        results = kg.query_graph(
            "MATCH (p:Entity {entity_type: 'Person'})-[:LOCATED_IN]->"
            "(l:Entity {entity_type: 'Location'}) RETURN p.name, l.name"
        )
        for row in results:
            print(row["values"])

Notes
-----
* ``insert_triples`` infers node types from the predicate where possible
  (e.g. the object of ``LOCATED_IN`` is classified as a Location).  When
  the type cannot be determined the node falls back to the ``Entity`` table.
* Each entity is written to **both** the typed table (e.g. ``Person``) and
  the generic ``Entity`` table so that both
  ``MATCH (p:Person)``-style and
  ``MATCH (p:Entity {entity_type: 'Person'})``-style queries work.
* Relation edges are stored on the ``Entity`` table so that a single
  relation table covers all node-type combinations (Kuzu 0.11.3 limitation).
* Duplicate nodes are handled with MERGE semantics (try MERGE, fall back to
  CREATE and silently swallow the primary-key conflict).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_DB_PATH: str = "./data/el_druin.kuzu"

#: Typed node tables recognised by the schema.
TYPED_NODE_TABLES: Tuple[str, ...] = ("Person", "Organization", "Location", "Event")

#: Supported relation types (stored as ``FROM Entity TO Entity``).
SUPPORTED_RELATIONS: Tuple[str, ...] = (
    "RELATED_TO",
    "LOCATED_IN",
    "PARTICIPATES_IN",
    "WORKS_FOR",
    "MEMBER_OF",
)

# Predicate → (subject_type_hint, object_type_hint)
# ``None`` means "cannot infer from the predicate alone".
_RELATION_TYPE_HINTS: Dict[str, Tuple[Optional[str], Optional[str]]] = {
    "LOCATED_IN": (None, "Location"),
    "PARTICIPATES_IN": (None, "Event"),
    "WORKS_FOR": ("Person", "Organization"),
    "MEMBER_OF": ("Person", "Organization"),
    "PART_OF": (None, "Organization"),
    "HAPPENED_IN": ("Event", "Location"),
    "BORN_IN": ("Person", "Location"),
    "BASED_IN": ("Organization", "Location"),
}


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class KuzuKnowledgeGraph:
    """Embedded Kuzu knowledge graph with typed nodes and generic relations.

    Parameters
    ----------
    db_path:
        Path to the Kuzu database *file* (e.g. ``./data/el_druin.kuzu``).
        The parent directory is created automatically if it does not exist.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        import kuzu  # type: ignore

        self._db_path = db_path
        parent = os.path.dirname(os.path.abspath(db_path))
        os.makedirs(parent, exist_ok=True)

        self._db = kuzu.Database(db_path)
        self._conn = kuzu.Connection(self._db)
        self._init_schema()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        """Create node and relation tables if they do not already exist."""
        # Typed node tables
        typed_node_stmts = [
            f"CREATE NODE TABLE IF NOT EXISTS {tbl}"
            f"(name STRING, description STRING, confidence DOUBLE,"
            f" PRIMARY KEY(name))"
            for tbl in TYPED_NODE_TABLES
        ]

        # Generic Entity table used as the hub for all relation edges.
        # ``entity_type`` records the semantic type (Person / Organization /
        # Location / Event / unknown) as a plain string column.
        generic_node_stmt = (
            "CREATE NODE TABLE IF NOT EXISTS Entity"
            "(name STRING, entity_type STRING, description STRING,"
            " confidence DOUBLE, PRIMARY KEY(name))"
        )

        # Relation tables – all FROM Entity TO Entity so that a single table
        # can hold edges regardless of the source/target semantic type.
        rel_stmts = [
            "CREATE REL TABLE IF NOT EXISTS RELATED_TO"
            "(FROM Entity TO Entity, relation_type STRING, confidence DOUBLE)",
            "CREATE REL TABLE IF NOT EXISTS LOCATED_IN"
            "(FROM Entity TO Entity, confidence DOUBLE)",
            "CREATE REL TABLE IF NOT EXISTS PARTICIPATES_IN"
            "(FROM Entity TO Entity, confidence DOUBLE)",
            "CREATE REL TABLE IF NOT EXISTS WORKS_FOR"
            "(FROM Entity TO Entity, confidence DOUBLE)",
            "CREATE REL TABLE IF NOT EXISTS MEMBER_OF"
            "(FROM Entity TO Entity, confidence DOUBLE)",
        ]

        for stmt in typed_node_stmts + [generic_node_stmt] + rel_stmts:
            try:
                self._conn.execute(stmt)
            except Exception as exc:
                logger.debug("Schema init (%s): %s", stmt[:60], exc)

    # ------------------------------------------------------------------
    # Node helpers
    # ------------------------------------------------------------------

    def _infer_node_type(
        self,
        predicate: str,
        position: str,  # "subject" | "object"
    ) -> str:
        """Return the inferred node type for *position* given *predicate*.

        Falls back to ``"Entity"`` when no hint is available.
        """
        hints = _RELATION_TYPE_HINTS.get(predicate.upper(), (None, None))
        if position == "subject" and hints[0]:
            return hints[0]
        if position == "object" and hints[1]:
            return hints[1]
        return "Entity"

    def _ensure_typed_node(
        self,
        name: str,
        node_type: str,
        description: str = "",
        confidence: float = 0.8,
    ) -> None:
        """Insert *name* into its typed table using create-if-absent semantics.

        Silently ignores primary-key conflicts (node already exists).

        Note: Kuzu 0.11.3 supports query parameters inside property-map literals
        (e.g. ``{name: $n}``) but **not** in ``SET`` clauses.  We therefore
        use ``CREATE`` and swallow the duplicate-primary-key error.
        """
        if node_type not in TYPED_NODE_TABLES:
            return  # Unknown type → only written to Entity table

        try:
            self._conn.execute(
                f"CREATE (:{node_type}"
                " {name: $n, description: $d, confidence: $c})",
                {"n": name, "d": description, "c": confidence},
            )
        except Exception as exc:
            if "duplicated primary key" not in str(exc).lower():
                logger.debug("_ensure_typed_node %s(%s): %s", node_type, name, exc)

    def _ensure_entity_node(
        self,
        name: str,
        entity_type: str = "Entity",
        description: str = "",
        confidence: float = 0.8,
    ) -> None:
        """Insert *name* into the generic ``Entity`` table using create-if-absent
        semantics.

        If the node already exists with the generic ``"Entity"`` type and we
        now have a more specific type (Person / Organization / Location /
        Event), the ``entity_type`` column is updated in-place.

        Note: Kuzu 0.11.3 allows query parameters in MATCH property-map filters
        but not in SET clause values.  The entity_type literal is therefore
        embedded directly into the SET query string; it is safe because the
        value is always one of the controlled constants in ``TYPED_NODE_TABLES``
        or the literal string ``"Entity"``.
        """
        try:
            self._conn.execute(
                "CREATE (:Entity"
                " {name: $n, entity_type: $t, description: $d, confidence: $c})",
                {
                    "n": name,
                    "t": entity_type,
                    "d": description,
                    "c": confidence,
                },
            )
        except Exception as exc:
            if "duplicated primary key" in str(exc).lower():
                # Node exists; upgrade the entity_type if we now have a more
                # specific classification.  The new type is a controlled literal
                # so embedding it directly in the query string is safe.
                if entity_type in TYPED_NODE_TABLES:
                    safe_type = entity_type  # value is from TYPED_NODE_TABLES
                    try:
                        self._conn.execute(
                            f"MATCH (e:Entity {{name: $n}}) "
                            f"SET e.entity_type = '{safe_type}'",
                            {"n": name},
                        )
                    except Exception as update_exc:
                        logger.debug(
                            "_ensure_entity_node update %s: %s", name, update_exc
                        )
            else:
                logger.debug("_ensure_entity_node(%s): %s", name, exc)

    def _ensure_node(
        self,
        name: str,
        node_type: str,
        description: str = "",
        confidence: float = 0.8,
    ) -> None:
        """Insert *name* into both its typed table and the generic Entity table."""
        self._ensure_typed_node(name, node_type, description, confidence)
        self._ensure_entity_node(name, node_type, description, confidence)

    # ------------------------------------------------------------------
    # Relation helpers
    # ------------------------------------------------------------------

    def _insert_relation(
        self,
        subject: str,
        predicate: str,
        obj: str,
        confidence: float = 0.8,
    ) -> None:
        """Create a directed relation edge between two Entity nodes.

        Uses check-then-create semantics to avoid duplicate edges (MERGE-like).
        Unrecognised predicates are stored as ``RELATED_TO`` with the original
        predicate string preserved in the ``relation_type`` column.

        Note: ``$on`` is a reserved keyword in Kuzu's query parser; we use
        ``$tgt`` for the object node name to avoid the clash.
        """
        pred_upper = predicate.upper()
        rel_type = pred_upper if pred_upper in SUPPORTED_RELATIONS else "RELATED_TO"

        # Check if the edge already exists to implement MERGE-like deduplication.
        try:
            check_result = self._conn.execute(
                f"MATCH (a:Entity {{name: $subj}})"
                f" MATCH (b:Entity {{name: $tgt}})"
                f" MATCH (a)-[r:{rel_type}]->(b)"
                f" RETURN count(r)",
                {"subj": subject, "tgt": obj},
            )
            if check_result.has_next() and check_result.get_next()[0] > 0:
                logger.debug(
                    "_insert_relation skipped (exists): %s -[%s]-> %s",
                    subject, rel_type, obj,
                )
                return
        except Exception as exc:
            logger.debug("_insert_relation existence check failed: %s", exc)

        if rel_type == "RELATED_TO":
            cypher = (
                "MATCH (a:Entity {name: $subj})"
                " MATCH (b:Entity {name: $tgt})"
                " CREATE (a)-[:RELATED_TO {relation_type: $rt, confidence: $conf}]->(b)"
            )
            params: Dict[str, Any] = {
                "subj": subject,
                "tgt": obj,
                "rt": predicate,
                "conf": confidence,
            }
        else:
            cypher = (
                "MATCH (a:Entity {name: $subj})"
                f" MATCH (b:Entity {{name: $tgt}})"
                f" CREATE (a)-[:{rel_type} {{confidence: $conf}}]->(b)"
            )
            params = {"subj": subject, "tgt": obj, "conf": confidence}

        try:
            self._conn.execute(cypher, params)
        except Exception as exc:
            logger.debug(
                "_insert_relation %s -[%s]-> %s: %s", subject, rel_type, obj, exc
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def insert_triples(
        self,
        triples: List[Tuple[str, str, str]],
        default_confidence: float = 0.8,
    ) -> None:
        """Insert a list of (subject, predicate, object) triples.

        Node types are inferred from the predicate when possible:

        * ``LOCATED_IN``      → object classified as ``Location``
        * ``PARTICIPATES_IN`` → object classified as ``Event``
        * ``WORKS_FOR``       → subject ``Person``, object ``Organization``
        * ``MEMBER_OF``       → subject ``Person``, object ``Organization``
        * Other predicates    → both nodes classified as ``Entity``

        Each node is written to **both** its typed table (e.g. ``Person``)
        and the generic ``Entity`` table.  Relations are stored on the
        ``Entity`` table so that a single relation table covers all
        node-type combinations.

        Duplicate nodes are handled with MERGE semantics and will not raise
        an error.

        Parameters
        ----------
        triples:
            List of ``(subject_name, predicate, object_name)`` tuples.
        default_confidence:
            Confidence score applied to newly created nodes and edges when
            none is provided by the caller.
        """
        for subject, predicate, obj in triples:
            subject_type = self._infer_node_type(predicate, "subject")
            object_type = self._infer_node_type(predicate, "object")

            self._ensure_node(subject, subject_type, confidence=default_confidence)
            self._ensure_node(obj, object_type, confidence=default_confidence)
            self._insert_relation(subject, predicate, obj, default_confidence)

    def query_graph(self, query: str) -> List[Dict[str, Any]]:
        """Execute a Kuzu Cypher query and return the results.

        Parameters
        ----------
        query:
            A Kuzu-dialect Cypher query string, e.g.::

                MATCH (p:Entity {entity_type: 'Person'})
                -[:LOCATED_IN]->
                (l:Entity {entity_type: 'Location'})
                RETURN p.name, l.name

        Returns
        -------
        list[dict]
            Each item is ``{"values": [col1, col2, ...]}``.
            On query failure, returns ``[{"error": "<message>"}]``.
        """
        try:
            result = self._conn.execute(query)
            rows: List[Dict[str, Any]] = []
            while result.has_next():
                rows.append({"values": list(result.get_next())})
            return rows
        except Exception as exc:
            logger.warning("query_graph failed: %s", exc)
            return [{"error": str(exc)}]

    def stats(self) -> Dict[str, Any]:
        """Return node and relation counts for each table."""
        counts: Dict[str, Any] = {}

        for label in list(TYPED_NODE_TABLES) + ["Entity"]:
            try:
                r = self._conn.execute(f"MATCH (n:{label}) RETURN count(n)")
                counts[label] = r.get_next()[0] if r.has_next() else 0
            except Exception:
                counts[label] = 0

        for rel in SUPPORTED_RELATIONS:
            try:
                r = self._conn.execute(f"MATCH ()-[r:{rel}]->() RETURN count(r)")
                counts[rel] = r.get_next()[0] if r.has_next() else 0
            except Exception:
                counts[rel] = 0

        return counts

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the database connection and release resources."""
        try:
            self._conn.close()
        except Exception:
            pass

    def __enter__(self) -> "KuzuKnowledgeGraph":
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------


def insert_triples(
    triples: List[Tuple[str, str, str]],
    db_path: str = DEFAULT_DB_PATH,
    default_confidence: float = 0.8,
) -> None:
    """Open the default knowledge graph and insert *triples*.

    This is a convenience wrapper; prefer using ``KuzuKnowledgeGraph`` as a
    context manager for more control::

        with KuzuKnowledgeGraph() as kg:
            kg.insert_triples([...])

    Parameters
    ----------
    triples:
        List of ``(subject_name, predicate, object_name)`` tuples.
    db_path:
        Path to the Kuzu database file.
    default_confidence:
        Default confidence score for created nodes/edges.
    """
    with KuzuKnowledgeGraph(db_path) as kg:
        kg.insert_triples(triples, default_confidence=default_confidence)


def query_graph(
    query: str,
    db_path: str = DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    """Open the default knowledge graph and execute *query*.

    This is a convenience wrapper; prefer using ``KuzuKnowledgeGraph`` as a
    context manager::

        with KuzuKnowledgeGraph() as kg:
            results = kg.query_graph("MATCH ...")

    Parameters
    ----------
    query:
        Kuzu Cypher query string.
    db_path:
        Path to the Kuzu database file.

    Returns
    -------
    list[dict]
        Query results; see :meth:`KuzuKnowledgeGraph.query_graph`.
    """
    with KuzuKnowledgeGraph(db_path) as kg:
        return kg.query_graph(query)
