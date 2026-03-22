"""Async Neo4j client for knowledge-graph operations."""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession as Neo4jSession
    _NEO4J_AVAILABLE = True
except ImportError:  # pragma: no cover
    _NEO4J_AVAILABLE = False
    logger.warning("neo4j driver not installed; Neo4j features disabled")

from app.config import settings


class Neo4jClient:
    """Thin async wrapper around the official Neo4j async driver.

    All public methods are safe to call even if the driver is unavailable
    (they will log a warning and return empty results instead of raising).

    Attributes:
        _driver: Underlying :class:`AsyncDriver` instance once connected.
    """

    def __init__(self) -> None:
        self._driver: Optional[Any] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open the driver connection to Neo4j."""
        if not _NEO4J_AVAILABLE:
            logger.warning("Neo4j driver not available; skipping connect")
            return
        self._driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URL,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            max_connection_pool_size=50,
        )
        await self._driver.verify_connectivity()
        logger.info("Connected to Neo4j at %s", settings.NEO4J_URL)

    async def close(self) -> None:
        """Close the driver and release all connections."""
        if self._driver:
            await self._driver.close()
            self._driver = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_driver(self) -> bool:
        """Return True if the driver is available, log warning otherwise."""
        if not self._driver:
            logger.warning("Neo4j driver not initialised")
            return False
        return True

    async def run_cypher(
        self,
        cypher: str,
        parameters: Optional[dict] = None,
    ) -> list[dict]:
        """Execute an arbitrary Cypher statement and return all records.

        Args:
            cypher: Cypher query string.
            parameters: Optional parameter dict for the query.

        Returns:
            List of records as plain dicts.
        """
        if not self._check_driver():
            return []
        async with self._driver.session() as session:
            result = await session.run(cypher, parameters or {})
            records = await result.data()
            return records  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # CRUD helpers
    # ------------------------------------------------------------------

    async def create_node(
        self,
        entity_class: str,
        properties: dict[str, Any],
    ) -> Optional[dict]:
        """Create a node with the given label and properties.

        Args:
            entity_class: Node label (e.g. "Person", "Organization").
            properties: Property dict; must include an ``id`` key.

        Returns:
            Created node as a plain dict, or *None* on failure.
        """
        if not self._check_driver():
            return None
        cypher = (
            f"MERGE (n:{entity_class} {{id: $id}}) "
            "SET n += $props "
            "RETURN n"
        )
        props = dict(properties)
        entity_id = props.pop("id", None)
        records = await self.run_cypher(
            cypher, {"id": entity_id, "props": props}
        )
        return records[0].get("n") if records else None

    async def create_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        properties: Optional[dict] = None,
    ) -> bool:
        """Create (or merge) a directed relationship between two nodes.

        Args:
            source_id: ID property of the source node.
            target_id: ID property of the target node.
            relationship_type: Relationship label (e.g. "AFFILIATED_WITH").
            properties: Optional relationship properties.

        Returns:
            True if the relationship was created/merged, False otherwise.
        """
        if not self._check_driver():
            return False
        cypher = (
            "MATCH (a {id: $source_id}), (b {id: $target_id}) "
            f"MERGE (a)-[r:{relationship_type}]->(b) "
            "SET r += $props "
            "RETURN r"
        )
        records = await self.run_cypher(
            cypher,
            {
                "source_id": source_id,
                "target_id": target_id,
                "props": properties or {},
            },
        )
        return bool(records)

    async def get_node(self, entity_id: str) -> Optional[dict]:
        """Fetch a node by its ``id`` property.

        Args:
            entity_id: Value of the node's ``id`` property.

        Returns:
            Node dict or *None* if not found.
        """
        records = await self.run_cypher(
            "MATCH (n {id: $id}) RETURN n", {"id": entity_id}
        )
        return records[0].get("n") if records else None

    async def get_neighbors(
        self,
        entity_id: str,
        relationship_type: Optional[str] = None,
        direction: str = "both",
    ) -> list[dict]:
        """Return immediate neighbours of a node.

        Args:
            entity_id: Node ID to start from.
            relationship_type: Optional relationship label filter.
            direction: "in", "out", or "both".

        Returns:
            List of neighbour node dicts.
        """
        rel_pattern = f"[r:{relationship_type}]" if relationship_type else "[r]"
        if direction == "out":
            pattern = f"(n {{id: $id}})-{rel_pattern}->(m)"
        elif direction == "in":
            pattern = f"(n {{id: $id}})<-{rel_pattern}-(m)"
        else:
            pattern = f"(n {{id: $id}})-{rel_pattern}-(m)"

        records = await self.run_cypher(
            f"MATCH {pattern} RETURN m, type(r) AS rel_type",
            {"id": entity_id},
        )
        return records

    async def get_subgraph(
        self,
        entity_id: str,
        depth: int = 2,
    ) -> dict[str, list]:
        """Return nodes and relationships within *depth* hops of a node.

        Args:
            entity_id: Root node ID.
            depth: Maximum traversal depth.

        Returns:
            Dict with ``nodes`` and ``relationships`` keys.
        """
        cypher = (
            "MATCH path = (root {id: $id})-[*0.."
            + str(depth)
            + "]-(other) "
            "RETURN nodes(path) AS nodes, relationships(path) AS rels"
        )
        records = await self.run_cypher(cypher, {"id": entity_id})
        seen_nodes: dict = {}
        seen_rels: dict = {}
        for record in records:
            for node in record.get("nodes", []):
                nid = node.get("id", str(node))
                seen_nodes[nid] = node
            for rel in record.get("rels", []):
                rid = str(rel)
                seen_rels[rid] = rel
        return {
            "nodes": list(seen_nodes.values()),
            "relationships": list(seen_rels.values()),
        }


# Module-level singleton
neo4j_client = Neo4jClient()
