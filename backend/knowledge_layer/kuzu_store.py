"""
Strict Minimalist Ontology – KuzuDB Store
==========================================

Implements a rigorous knowledge graph schema with 5 core node types and 3 core
relationship types, enforcing mandatory properties at the database level.

Schema
------

**Node Tables** (all share ``id`` STRING PRIMARY KEY):

* ``Person``       – individual people
* ``Organization`` – companies, agencies, governments, etc.
* ``Location``     – countries, cities, geographic regions
* ``Event``        – occurrences, incidents, conferences, etc.
* ``Concept``      – abstract ideas, topics, themes

Every node carries:

* ``id``                 STRING    – unique identifier (PRIMARY KEY)
* ``name``               STRING    – human-readable label
* ``source_reliability`` DOUBLE    – data-source quality score  [0.0 – 1.0]
* ``timestamp``          TIMESTAMP – when this fact was recorded

**Relationship Tables** (stored on the ``_Entity`` hub table to work around
Kuzu's single-endpoint limitation):

* ``INVOLVED_IN``   Event → (Person | Organization | Location | Concept)

  - ``role``               STRING
  - ``source_reliability`` DOUBLE    [0.0 – 1.0]
  - ``timestamp``          TIMESTAMP

* ``INFLUENCES``    (Person | Organization | Concept) → (Person | Organization | Event | Concept)

  - ``causality_score``    DOUBLE    [0.0 – 1.0]
  - ``source_reliability`` DOUBLE    [0.0 – 1.0]
  - ``timestamp``          TIMESTAMP

* ``LOCATED_AT``    (Person | Organization | Event) → Location

  - ``confidence``         DOUBLE    [0.0 – 1.0]
  - ``source_reliability`` DOUBLE    [0.0 – 1.0]
  - ``timestamp``          TIMESTAMP

Usage
-----
::

    from knowledge_layer.kuzu_store import KuzuStore

    with KuzuStore("./data/knowledge.kuzu") as store:
        store.add_person(
            id="person-1",
            name="Alice",
            source_reliability=0.9,
        )
        store.add_event(
            id="event-1",
            name="Summit 2024",
            source_reliability=0.85,
        )
        store.add_involved_in(
            event_id="event-1",
            entity_id="person-1",
            role="speaker",
            source_reliability=0.9,
        )
        participants = store.get_involved_in("event-1")

Notes
-----
* Kuzu ≥ 0.11 does not support multi-label relation endpoints (e.g. ``FROM
  Event TO Person OR Organization``).  This module works around the limitation
  by writing every node into both its typed table (``Person``, ``Event``, …)
  **and** a lightweight ``_Entity`` hub table.  All three relation tables use
  ``FROM _Entity TO _Entity`` so they can represent any source/target type
  combination.
* Nodes are inserted with create-if-absent semantics; a duplicated primary-key
  error is silently swallowed (idempotent upsert).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_DB_PATH: str = "./data/el_druin_strict.kuzu"

#: All 5 core node types defined by the strict ontology.
NODE_TYPES: Tuple[str, ...] = ("Person", "Organization", "Location", "Event", "Concept")

#: All 3 core relationship types defined by the strict ontology.
RELATION_TYPES: Tuple[str, ...] = ("INVOLVED_IN", "INFLUENCES", "LOCATED_AT", "CONTRADICTS")


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def validate_reliability(value: float, field_name: str = "source_reliability") -> float:
    """Validate that *value* is a float in the range [0.0, 1.0].

    Parameters
    ----------
    value:
        The score to validate.
    field_name:
        Name of the field (used in error messages).

    Returns
    -------
    float
        The validated value.

    Raises
    ------
    ValueError
        If *value* is outside [0.0, 1.0].

    Examples
    --------
    >>> validate_reliability(0.9)
    0.9
    >>> validate_reliability(1.5)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
        ...
    ValueError: source_reliability must be in [0.0, 1.0], got 1.5
    """
    if not (0.0 <= value <= 1.0):
        raise ValueError(f"{field_name} must be in [0.0, 1.0], got {value}")
    return value


def validate_timestamp(ts: Optional[datetime] = None) -> datetime:
    """Return *ts* if valid, or the current UTC time if *ts* is ``None``.

    Parameters
    ----------
    ts:
        A :class:`datetime` object to validate, or ``None`` to use *now*.

    Returns
    -------
    datetime
        A :class:`datetime` instance (timezone-aware when *ts* is ``None``).

    Raises
    ------
    TypeError
        If *ts* is not a :class:`datetime` instance (and not ``None``).

    Examples
    --------
    >>> from datetime import datetime, timezone
    >>> dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
    >>> validate_timestamp(dt) == dt
    True
    >>> isinstance(validate_timestamp(None), datetime)
    True
    """
    if ts is None:
        return datetime.now(tz=timezone.utc)
    if not isinstance(ts, datetime):
        raise TypeError(
            f"timestamp must be a datetime instance, got {type(ts).__name__}"
        )
    return ts


# ---------------------------------------------------------------------------
# KuzuStore
# ---------------------------------------------------------------------------


class KuzuStore:
    """Strict minimalist KuzuDB knowledge graph store.

    Implements a rigorous schema with 5 core node types (Person, Organization,
    Location, Event, Concept) and 3 core relationship types (INVOLVED_IN,
    INFLUENCES, LOCATED_AT).  Every node and edge carries mandatory
    ``source_reliability`` and ``timestamp`` properties.

    Because Kuzu ≥ 0.11 does not support multi-label relation endpoints, all
    relation edges are stored on a generic ``_Entity`` hub table.  Each node is
    written to **both** its typed table (e.g. ``Person``) and the ``_Entity``
    hub so that typed queries (``MATCH (p:Person …)``) still work.

    Parameters
    ----------
    db_path:
        Filesystem path for the Kuzu database directory.
        Created automatically when it does not exist.

    Examples
    --------
    ::

        from knowledge_layer.kuzu_store import KuzuStore

        with KuzuStore("./data/knowledge.kuzu") as store:
            store.add_person(id="p1", name="Alice", source_reliability=0.9)
            store.add_organization(id="org1", name="Acme Corp", source_reliability=0.8)
            store.add_influences(
                from_id="p1",
                to_id="org1",
                causality_score=0.7,
                source_reliability=0.85,
            )
            print(store.stats())
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
    # Schema initialisation
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        """Create all node and relationship tables if they do not already exist.

        Schema guarantees
        ~~~~~~~~~~~~~~~~~
        * Every node table has ``id STRING PRIMARY KEY``, ``name STRING``,
          ``source_reliability DOUBLE``, and ``timestamp TIMESTAMP``.
        * The ``_Entity`` hub table carries ``id STRING PRIMARY KEY`` and
          ``node_type STRING`` so that queries can still filter by semantic type.
        * All three relation tables use ``FROM _Entity TO _Entity`` and carry
          ``source_reliability DOUBLE`` and ``timestamp TIMESTAMP`` as mandatory
          edge properties.
        """
        node_ddl = [
            f"CREATE NODE TABLE IF NOT EXISTS {t}"
            "(id STRING, name STRING, source_reliability DOUBLE,"
            " timestamp TIMESTAMP, PRIMARY KEY(id))"
            for t in NODE_TYPES
        ]

        hub_ddl = (
            "CREATE NODE TABLE IF NOT EXISTS _Entity"
            "(id STRING, node_type STRING, PRIMARY KEY(id))"
        )

        rel_ddl = [
            # INVOLVED_IN: Event → (Person | Organization | Location | Concept)
            "CREATE REL TABLE IF NOT EXISTS INVOLVED_IN"
            "(FROM _Entity TO _Entity,"
            " role STRING, source_reliability DOUBLE, timestamp TIMESTAMP)",

            # INFLUENCES: (Person | Organization | Concept) →
            #             (Person | Organization | Event | Concept)
            "CREATE REL TABLE IF NOT EXISTS INFLUENCES"
            "(FROM _Entity TO _Entity,"
            " causality_score DOUBLE, source_reliability DOUBLE, timestamp TIMESTAMP)",

            # LOCATED_AT: (Person | Organization | Event) → Location
            "CREATE REL TABLE IF NOT EXISTS LOCATED_AT"
            "(FROM _Entity TO _Entity,"
            " confidence DOUBLE, source_reliability DOUBLE, timestamp TIMESTAMP)",

            # CONTRADICTS: any two entities whose asserted facts conflict
            "CREATE REL TABLE IF NOT EXISTS CONTRADICTS"
            "(FROM _Entity TO _Entity,"
            " reason STRING, confidence DOUBLE,"
            " source_reliability DOUBLE, timestamp TIMESTAMP)",
        ]

        for stmt in node_ddl + [hub_ddl] + rel_ddl:
            try:
                self._conn.execute(stmt)
            except Exception as exc:
                logger.debug("Schema init (%s…): %s", stmt[:70], exc)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_hub_node(self, node_id: str, node_type: str) -> None:
        """Insert *node_id* into the ``_Entity`` hub table if absent.

        Silently swallows duplicated-primary-key errors so the method is
        idempotent.
        """
        try:
            self._conn.execute(
                "CREATE (:_Entity {id: $id, node_type: $t})",
                {"id": node_id, "t": node_type},
            )
        except Exception as exc:
            if "duplicated primary key" not in str(exc).lower():
                logger.debug("_ensure_hub_node(%s): %s", node_id, exc)

    def _add_typed_node(
        self,
        node_type: str,
        node_id: str,
        name: str,
        source_reliability: float,
        timestamp: Optional[datetime],
    ) -> None:
        """Insert *node_id* into its typed table and the ``_Entity`` hub.

        Validation is applied to *source_reliability* and *timestamp* before
        any database write.

        Parameters
        ----------
        node_type:
            One of the 5 core node types.
        node_id:
            Unique string identifier (PRIMARY KEY).
        name:
            Human-readable label.
        source_reliability:
            Data-source quality score validated to be in [0.0, 1.0].
        timestamp:
            Recording timestamp; ``None`` defaults to the current UTC time.
        """
        sr = validate_reliability(source_reliability)
        ts = validate_timestamp(timestamp)
        try:
            self._conn.execute(
                f"CREATE (:{node_type}"
                " {id: $id, name: $name,"
                "  source_reliability: $sr, timestamp: $ts})",
                {"id": node_id, "name": name, "sr": sr, "ts": ts},
            )
        except Exception as exc:
            if "duplicated primary key" not in str(exc).lower():
                logger.debug("_add_typed_node %s(%s): %s", node_type, node_id, exc)
        self._ensure_hub_node(node_id, node_type)

    # ------------------------------------------------------------------
    # Node insertion – public API
    # ------------------------------------------------------------------

    def add_person(
        self,
        id: str,
        name: str,
        source_reliability: float = 1.0,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Add a Person node.

        Parameters
        ----------
        id:
            Unique identifier (PRIMARY KEY).
        name:
            Human-readable label.
        source_reliability:
            Data-source quality score in [0.0, 1.0].
        timestamp:
            When this fact was recorded.  Defaults to the current UTC time.

        Raises
        ------
        ValueError
            If *source_reliability* is outside [0.0, 1.0].

        Examples
        --------
        ::

            store.add_person(id="p1", name="Alice", source_reliability=0.9)
        """
        self._add_typed_node("Person", id, name, source_reliability, timestamp)

    def add_organization(
        self,
        id: str,
        name: str,
        source_reliability: float = 1.0,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Add an Organization node.

        Parameters
        ----------
        id:
            Unique identifier (PRIMARY KEY).
        name:
            Human-readable label.
        source_reliability:
            Data-source quality score in [0.0, 1.0].
        timestamp:
            When this fact was recorded.  Defaults to the current UTC time.

        Raises
        ------
        ValueError
            If *source_reliability* is outside [0.0, 1.0].

        Examples
        --------
        ::

            store.add_organization(id="org1", name="Acme Corp", source_reliability=0.85)
        """
        self._add_typed_node("Organization", id, name, source_reliability, timestamp)

    def add_location(
        self,
        id: str,
        name: str,
        source_reliability: float = 1.0,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Add a Location node.

        Parameters
        ----------
        id:
            Unique identifier (PRIMARY KEY).
        name:
            Human-readable label.
        source_reliability:
            Data-source quality score in [0.0, 1.0].
        timestamp:
            When this fact was recorded.  Defaults to the current UTC time.

        Raises
        ------
        ValueError
            If *source_reliability* is outside [0.0, 1.0].

        Examples
        --------
        ::

            store.add_location(id="loc1", name="New York", source_reliability=0.95)
        """
        self._add_typed_node("Location", id, name, source_reliability, timestamp)

    def add_event(
        self,
        id: str,
        name: str,
        source_reliability: float = 1.0,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Add an Event node.

        Parameters
        ----------
        id:
            Unique identifier (PRIMARY KEY).
        name:
            Human-readable label.
        source_reliability:
            Data-source quality score in [0.0, 1.0].
        timestamp:
            When this fact was recorded.  Defaults to the current UTC time.

        Raises
        ------
        ValueError
            If *source_reliability* is outside [0.0, 1.0].

        Examples
        --------
        ::

            store.add_event(id="ev1", name="Summit 2024", source_reliability=0.9)
        """
        self._add_typed_node("Event", id, name, source_reliability, timestamp)

    def add_concept(
        self,
        id: str,
        name: str,
        source_reliability: float = 1.0,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Add a Concept node.

        Parameters
        ----------
        id:
            Unique identifier (PRIMARY KEY).
        name:
            Human-readable label.
        source_reliability:
            Data-source quality score in [0.0, 1.0].
        timestamp:
            When this fact was recorded.  Defaults to the current UTC time.

        Raises
        ------
        ValueError
            If *source_reliability* is outside [0.0, 1.0].

        Examples
        --------
        ::

            store.add_concept(id="con1", name="Democracy", source_reliability=0.8)
        """
        self._add_typed_node("Concept", id, name, source_reliability, timestamp)

    # ------------------------------------------------------------------
    # Relationship insertion – public API
    # ------------------------------------------------------------------

    def add_involved_in(
        self,
        event_id: str,
        entity_id: str,
        role: str,
        source_reliability: float = 1.0,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Create an INVOLVED_IN edge from an Event to an entity.

        Semantics: the entity identified by *entity_id* played *role* in the
        event identified by *event_id*.

        Parameters
        ----------
        event_id:
            ID of the Event node (source endpoint).
        entity_id:
            ID of the target entity node (Person, Organization, Location, or
            Concept).
        role:
            The role the entity played in the event (e.g. ``"organizer"``,
            ``"participant"``).
        source_reliability:
            Data-source quality score in [0.0, 1.0].
        timestamp:
            When this fact was recorded.  Defaults to the current UTC time.

        Raises
        ------
        ValueError
            If *source_reliability* is outside [0.0, 1.0].

        Examples
        --------
        ::

            store.add_involved_in(
                event_id="ev1",
                entity_id="p1",
                role="speaker",
                source_reliability=0.9,
            )
        """
        sr = validate_reliability(source_reliability)
        ts = validate_timestamp(timestamp)
        try:
            self._conn.execute(
                "MATCH (a:_Entity {id: $from_id})"
                " MATCH (b:_Entity {id: $to_id})"
                " CREATE (a)-[:INVOLVED_IN"
                "  {role: $role, source_reliability: $sr, timestamp: $ts}]->(b)",
                {
                    "from_id": event_id,
                    "to_id": entity_id,
                    "role": role,
                    "sr": sr,
                    "ts": ts,
                },
            )
        except Exception as exc:
            logger.debug("add_involved_in %s→%s: %s", event_id, entity_id, exc)

    def add_influences(
        self,
        from_id: str,
        to_id: str,
        causality_score: float,
        source_reliability: float = 1.0,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Create an INFLUENCES edge between two entities.

        Semantics: the entity identified by *from_id* influences the entity
        identified by *to_id* with the given *causality_score*.

        Parameters
        ----------
        from_id:
            ID of the influencing entity (Person, Organization, or Concept).
        to_id:
            ID of the influenced entity (Person, Organization, Event, or
            Concept).
        causality_score:
            Strength of the causal relationship in [0.0, 1.0].
        source_reliability:
            Data-source quality score in [0.0, 1.0].
        timestamp:
            When this fact was recorded.  Defaults to the current UTC time.

        Raises
        ------
        ValueError
            If *causality_score* or *source_reliability* is outside [0.0, 1.0].

        Examples
        --------
        ::

            store.add_influences(
                from_id="org1",
                to_id="ev1",
                causality_score=0.7,
                source_reliability=0.85,
            )
        """
        cs = validate_reliability(causality_score, "causality_score")
        sr = validate_reliability(source_reliability)
        ts = validate_timestamp(timestamp)
        try:
            self._conn.execute(
                "MATCH (a:_Entity {id: $from_id})"
                " MATCH (b:_Entity {id: $to_id})"
                " CREATE (a)-[:INFLUENCES"
                "  {causality_score: $cs, source_reliability: $sr,"
                "   timestamp: $ts}]->(b)",
                {"from_id": from_id, "to_id": to_id, "cs": cs, "sr": sr, "ts": ts},
            )
        except Exception as exc:
            logger.debug("add_influences %s→%s: %s", from_id, to_id, exc)

    def add_located_at(
        self,
        entity_id: str,
        location_id: str,
        confidence: float,
        source_reliability: float = 1.0,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Create a LOCATED_AT edge from an entity to a Location.

        Semantics: the entity identified by *entity_id* is or was located at
        the location identified by *location_id*.

        Parameters
        ----------
        entity_id:
            ID of the entity node (Person, Organization, or Event).
        location_id:
            ID of the target Location node.
        confidence:
            Spatial confidence score in [0.0, 1.0].
        source_reliability:
            Data-source quality score in [0.0, 1.0].
        timestamp:
            When this fact was recorded.  Defaults to the current UTC time.

        Raises
        ------
        ValueError
            If *confidence* or *source_reliability* is outside [0.0, 1.0].

        Examples
        --------
        ::

            store.add_located_at(
                entity_id="org1",
                location_id="loc1",
                confidence=0.95,
                source_reliability=0.9,
            )
        """
        conf = validate_reliability(confidence, "confidence")
        sr = validate_reliability(source_reliability)
        ts = validate_timestamp(timestamp)
        try:
            self._conn.execute(
                "MATCH (a:_Entity {id: $eid})"
                " MATCH (b:_Entity {id: $lid})"
                " CREATE (a)-[:LOCATED_AT"
                "  {confidence: $conf, source_reliability: $sr,"
                "   timestamp: $ts}]->(b)",
                {"eid": entity_id, "lid": location_id, "conf": conf, "sr": sr, "ts": ts},
            )
        except Exception as exc:
            logger.debug("add_located_at %s→%s: %s", entity_id, location_id, exc)

    def add_contradicts(
        self,
        from_id: str,
        to_id: str,
        reason: str,
        confidence: float = 0.8,
        source_reliability: float = 0.7,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Create a CONTRADICTS edge between two entity nodes.

        Semantics: the assertion represented by *from_id* contradicts the
        assertion represented by *to_id*.  Both nodes must already exist in
        the ``_Entity`` hub table.

        Parameters
        ----------
        from_id:
            ID of the first entity (source of the contradiction edge).
        to_id:
            ID of the second entity (target of the contradiction edge).
        reason:
            Human-readable explanation of why these facts contradict.
        confidence:
            Confidence score for this contradiction in [0.0, 1.0].
        source_reliability:
            Reliability of the data source that triggered this contradiction.
        timestamp:
            When the contradiction was recorded.  Defaults to the current UTC
            time.

        Raises
        ------
        ValueError
            If *confidence* or *source_reliability* is outside [0.0, 1.0].

        Examples
        --------
        ::

            store.add_contradicts(
                from_id="ev1",
                to_id="ev2",
                reason="Report A says rate raised; Report B says rate cut",
                confidence=0.9,
                source_reliability=0.8,
            )
        """
        conf = validate_reliability(confidence, "confidence")
        sr = validate_reliability(source_reliability)
        ts = validate_timestamp(timestamp)
        try:
            self._conn.execute(
                "MATCH (a:_Entity {id: $from_id})"
                " MATCH (b:_Entity {id: $to_id})"
                " CREATE (a)-[:CONTRADICTS"
                "  {reason: $reason, confidence: $conf,"
                "   source_reliability: $sr, timestamp: $ts}]->(b)",
                {
                    "from_id": from_id,
                    "to_id": to_id,
                    "reason": reason,
                    "conf": conf,
                    "sr": sr,
                    "ts": ts,
                },
            )
        except Exception as exc:
            logger.debug("add_contradicts %s→%s: %s", from_id, to_id, exc)

    # ------------------------------------------------------------------
    # Query helpers – public API
    # ------------------------------------------------------------------

    def get_node(self, node_type: str, node_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single node by type and ID.

        Parameters
        ----------
        node_type:
            One of the 5 core node types (``"Person"``, ``"Organization"``,
            ``"Location"``, ``"Event"``, ``"Concept"``).
        node_id:
            The primary-key identifier of the node.

        Returns
        -------
        dict or None
            Mapping with keys ``id``, ``name``, ``source_reliability``,
            ``timestamp``; or ``None`` if no matching node is found.

        Raises
        ------
        ValueError
            If *node_type* is not one of the 5 core types.

        Examples
        --------
        ::

            node = store.get_node("Person", "p1")
            if node:
                print(node["name"], node["source_reliability"])
        """
        if node_type not in NODE_TYPES:
            raise ValueError(
                f"Unknown node type '{node_type}'. Must be one of {NODE_TYPES}"
            )
        try:
            result = self._conn.execute(
                f"MATCH (n:{node_type} {{id: $id}})"
                " RETURN n.id, n.name, n.source_reliability, n.timestamp",
                {"id": node_id},
            )
            if result.has_next():
                row = result.get_next()
                return {
                    "id": row[0],
                    "name": row[1],
                    "source_reliability": row[2],
                    "timestamp": row[3],
                }
        except Exception as exc:
            logger.debug("get_node %s(%s): %s", node_type, node_id, exc)
        return None

    def get_involved_in(self, event_id: str) -> List[Dict[str, Any]]:
        """Return all entities involved in a given Event.

        Parameters
        ----------
        event_id:
            ID of the Event node.

        Returns
        -------
        list[dict]
            Each item contains keys ``entity_id``, ``role``,
            ``source_reliability``, and ``timestamp``.

        Examples
        --------
        ::

            participants = store.get_involved_in("ev1")
            for p in participants:
                print(p["entity_id"], p["role"])
        """
        try:
            result = self._conn.execute(
                "MATCH (e:_Entity {id: $eid})-[r:INVOLVED_IN]->(t:_Entity)"
                " RETURN t.id, r.role, r.source_reliability, r.timestamp",
                {"eid": event_id},
            )
            rows: List[Dict[str, Any]] = []
            while result.has_next():
                row = result.get_next()
                rows.append(
                    {
                        "entity_id": row[0],
                        "role": row[1],
                        "source_reliability": row[2],
                        "timestamp": row[3],
                    }
                )
            return rows
        except Exception as exc:
            logger.debug("get_involved_in(%s): %s", event_id, exc)
            return []

    def get_influences(self, entity_id: str) -> List[Dict[str, Any]]:
        """Return all entities influenced by the given entity.

        Parameters
        ----------
        entity_id:
            ID of the influencing entity.

        Returns
        -------
        list[dict]
            Each item contains keys ``target_id``, ``causality_score``,
            ``source_reliability``, and ``timestamp``.

        Examples
        --------
        ::

            influenced = store.get_influences("org1")
            for item in influenced:
                print(item["target_id"], item["causality_score"])
        """
        try:
            result = self._conn.execute(
                "MATCH (a:_Entity {id: $eid})-[r:INFLUENCES]->(b:_Entity)"
                " RETURN b.id, r.causality_score, r.source_reliability, r.timestamp",
                {"eid": entity_id},
            )
            rows: List[Dict[str, Any]] = []
            while result.has_next():
                row = result.get_next()
                rows.append(
                    {
                        "target_id": row[0],
                        "causality_score": row[1],
                        "source_reliability": row[2],
                        "timestamp": row[3],
                    }
                )
            return rows
        except Exception as exc:
            logger.debug("get_influences(%s): %s", entity_id, exc)
            return []

    def get_located_at(self, entity_id: str) -> List[Dict[str, Any]]:
        """Return all locations associated with the given entity.

        Parameters
        ----------
        entity_id:
            ID of the entity (Person, Organization, or Event).

        Returns
        -------
        list[dict]
            Each item contains keys ``location_id``, ``confidence``,
            ``source_reliability``, and ``timestamp``.

        Examples
        --------
        ::

            locations = store.get_located_at("org1")
            for loc in locations:
                print(loc["location_id"], loc["confidence"])
        """
        try:
            result = self._conn.execute(
                "MATCH (a:_Entity {id: $eid})-[r:LOCATED_AT]->(l:_Entity)"
                " RETURN l.id, r.confidence, r.source_reliability, r.timestamp",
                {"eid": entity_id},
            )
            rows: List[Dict[str, Any]] = []
            while result.has_next():
                row = result.get_next()
                rows.append(
                    {
                        "location_id": row[0],
                        "confidence": row[1],
                        "source_reliability": row[2],
                        "timestamp": row[3],
                    }
                )
            return rows
        except Exception as exc:
            logger.debug("get_located_at(%s): %s", entity_id, exc)
            return []

    def cypher_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute an arbitrary Kuzu Cypher query.

        Parameters
        ----------
        query:
            Kuzu-dialect Cypher string.

        Returns
        -------
        list[dict]
            Each item is ``{"values": [col1, col2, …]}``.
            On failure, returns ``[{"error": "<message>"}]``.

        Examples
        --------
        ::

            rows = store.cypher_query(
                "MATCH (p:Person) RETURN p.id, p.name LIMIT 10"
            )
            for row in rows:
                print(row["values"])
        """
        try:
            result = self._conn.execute(query)
            rows: List[Dict[str, Any]] = []
            while result.has_next():
                rows.append({"values": list(result.get_next())})
            return rows
        except Exception as exc:
            logger.warning("cypher_query failed: %s", exc)
            return [{"error": str(exc)}]

    def stats(self) -> Dict[str, Any]:
        """Return row counts for every node and relation table.

        Returns
        -------
        dict
            Keys are table names; values are integer row counts.

        Examples
        --------
        ::

            counts = store.stats()
            # {"Person": 5, "Organization": 3, "Location": 1, "Event": 2,
            #  "Concept": 0, "_Entity": 11,
            #  "INVOLVED_IN": 4, "INFLUENCES": 2, "LOCATED_AT": 3}
            print(counts)
        """
        counts: Dict[str, Any] = {}
        for label in list(NODE_TYPES) + ["_Entity"]:
            try:
                r = self._conn.execute(f"MATCH (n:{label}) RETURN count(n)")
                counts[label] = r.get_next()[0] if r.has_next() else 0
            except Exception:
                counts[label] = 0
        for rel in RELATION_TYPES:
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

    def __enter__(self) -> "KuzuStore":
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------


def create_store(db_path: str = DEFAULT_DB_PATH) -> KuzuStore:
    """Create and return a :class:`KuzuStore` instance.

    Parameters
    ----------
    db_path:
        Filesystem path for the Kuzu database directory.

    Returns
    -------
    KuzuStore

    Examples
    --------
    ::

        store = create_store("./data/knowledge.kuzu")
        store.add_person(id="p1", name="Alice", source_reliability=0.9)
        store.close()
    """
    return KuzuStore(db_path)
