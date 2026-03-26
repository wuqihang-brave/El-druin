"""
API Client – HTTP client for communicating with the EL'druin FastAPI backend.

Usage::

    from utils.api_client import api_client

    articles = api_client.get_latest_news(limit=10, hours=24)
"""

import logging
import os
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv("BACKEND_URL")
if not BACKEND_URL:
    raise RuntimeError(
        "BACKEND_URL environment variable is not set. "
        "Please configure it in your deployment environment. "
        "Expected format: https://your-backend-domain.com/api/v1"
    )
_DEFAULT_BASE_URL = BACKEND_URL
_TIMEOUT = 10  # seconds


class APIClient:
    """Thin HTTP wrapper around the EL'druin FastAPI backend."""

    def __init__(self, base_url: str = _DEFAULT_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = self._session.get(url, params=params, timeout=_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as exc:
            logger.error("Connection error [GET %s]: %s", path, exc)
            return {"error": "Cannot connect to backend. Is it running?"}
        except requests.exceptions.Timeout:
            logger.error("Timeout [GET %s]", path)
            return {"error": "Request timed out."}
        except requests.exceptions.HTTPError as exc:
            logger.error("HTTP error [GET %s]: %s", path, exc)
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected error [GET %s]: %s", path, exc)
            return {"error": str(exc)}

    def _post(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = self._session.post(url, params=params, json=json, timeout=_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as exc:
            logger.error("Connection error [POST %s]: %s", path, exc)
            return {"error": "Cannot connect to backend. Is it running?"}
        except requests.exceptions.Timeout:
            logger.error("Timeout [POST %s]", path)
            return {"error": "Request timed out."}
        except requests.exceptions.HTTPError as exc:
            logger.error("HTTP error [POST %s]: %s", path, exc)
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected error [POST %s]: %s", path, exc)
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # News endpoints
    # ------------------------------------------------------------------

    def get_news_sources(self) -> Dict[str, Any]:
        """Return the list of configured news sources."""
        return self._get("/news/sources")

    def ingest_news(self, include_newsapi: bool = False) -> Dict[str, Any]:
        """Trigger a news ingestion cycle on the backend."""
        return self._post("/news/ingest", params={"include_newsapi": include_newsapi})

    def get_latest_news(
        self,
        category: Optional[str] = None,
        limit: int = 20,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """Fetch the most recent articles.

        Args:
            category: Optional category filter (e.g. ``"politics"``).
            limit: Maximum number of articles to return.
            hours: Only include articles published in the last *hours* hours.

        Returns:
            Dict with key ``"articles"`` containing a list of article dicts.
        """
        params: Dict[str, Any] = {"limit": limit, "hours": hours}
        if category:
            params["category"] = category
        return self._get("/news/latest", params=params)

    def search_news(self, keyword: str, limit: int = 20) -> Dict[str, Any]:
        """Full-text search across ingested articles.

        Args:
            keyword: Search term.
            limit: Maximum number of results.

        Returns:
            Dict with key ``"articles"``.
        """
        return self._get("/news/search", params={"keyword": keyword, "limit": limit})

    # ------------------------------------------------------------------
    # Event endpoints
    # ------------------------------------------------------------------

    def get_extracted_events(
        self,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Return events that have been extracted from ingested articles.

        Args:
            event_type: Optional event-type filter (e.g. ``"自然灾害"``).
            severity: Optional severity filter: ``"high"``, ``"medium"``, or ``"low"``.
            limit: Maximum number of events to return.

        Returns:
            Dict with key ``"events"`` containing a list of event dicts.
        """
        params: Dict[str, Any] = {"limit": limit}
        if event_type:
            params["event_type"] = event_type
        if severity:
            params["severity"] = severity
        return self._get("/news/events/extracted", params=params)

    def get_events(self, limit: int = 20) -> Dict[str, Any]:
        """Return all events from the events store.

        Args:
            limit: Maximum number of events to return.

        Returns:
            Dict with key ``"items"`` containing a list of event dicts.
        """
        return self._get("/events", params={"limit": limit})

    # ------------------------------------------------------------------
    # Knowledge graph endpoints
    # ------------------------------------------------------------------

    def ingest_knowledge_graph(self, limit: int = 100, hours: int = 24) -> Dict[str, Any]:
        """Fetch recent news and ingest it into the knowledge graph."""
        return self._post("/knowledge/ingest", params={"limit": limit, "hours": hours})

    def get_kg_entities(self, limit: int = 100) -> Dict[str, Any]:
        """Return entity nodes from the knowledge graph."""
        return self._get("/knowledge/entities", params={"limit": limit})

    def get_kg_relations(self, limit: int = 200) -> Dict[str, Any]:
        """Return relation edges from the knowledge graph."""
        return self._get("/knowledge/relations", params={"limit": limit})

    def get_kg_neighbours(self, entity: str, depth: int = 1) -> Dict[str, Any]:
        """Return neighbours of a named entity."""
        return self._get("/knowledge/neighbours", params={"entity": entity, "depth": depth})

    def run_kg_query(self, query: str) -> Dict[str, Any]:
        """Run a Cypher query against the knowledge graph."""
        return self._get("/knowledge/query", params={"query": query})

    def get_kg_stats(self) -> Dict[str, Any]:
        """Return knowledge graph statistics."""
        return self._get("/knowledge/stats")

    def get_hierarchical_graph(
        self,
        min_degree: int = 0,
        max_degree: int = 100,
    ) -> Dict[str, Any]:
        """Return a degree-filtered hierarchical view of the knowledge graph.

        Args:
            min_degree: Minimum node degree (inclusive).
            max_degree: Maximum node degree (inclusive).

        Returns:
            Dict with ``"nodes"``, ``"edges"``, ``"degree_map"``,
            ``"total_nodes"``, and ``"total_edges"`` keys.
        """
        return self._get(
            "/knowledge/graph/hierarchy",
            params={"min_degree": min_degree, "max_degree": max_degree},
        )

    def get_node_narrative(self, node_name: str) -> Dict[str, Any]:
        """Return the Order Narrative for a single knowledge graph node.

        Args:
            node_name: The name of the node to look up.

        Returns:
            Dict with narrative fields including ``"node_name"``,
            ``"node_type"``, ``"degree"``, ``"importance_tier"``,
            ``"definition"``, ``"main_connections"``, and ``"global_role"``.
        """
        return self._get(f"/knowledge/graph/node-narrative/{node_name}")

    def extract_knowledge(self, text: str) -> Dict[str, Any]:
        """Extract entities and relations from raw text without persisting.

        Args:
            text: The news article text to analyse.

        Returns:
            Dict with ``"entities"``, ``"relations"``, ``"nodes_count"``,
            and ``"edges_count"`` keys.
        """
        return self._post("/knowledge/extract", json={"text": text})

    def extract_causal_chains(self, text: str, model: str = "llama3-8b-8192") -> Dict[str, Any]:
        """Extract deep causal chains from news text via the backend.

        Uses an enhanced LLM prompt to discover multi-step causal paths that go
        beyond simple subject-predicate-object triples.

        Args:
            text: The news article text to analyse.
            model: LLM model name to use (default ``"llama3-8b-8192"``).

        Returns:
            Dict with ``"entities"``, ``"relations"``, ``"causal_chains"``, and
            ``"overall_order_score"`` keys.
        """
        return self._post("/knowledge/extract-causal-chains", json={"text": text, "model": model})

    def get_order_critique(
        self,
        entities: List[Dict[str, Any]],
        relations: List[Dict[str, Any]],
        causal_chains: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate a philosophical critique of system stability.

        Calls the Order Critic agent on the backend to produce a paragraph-length
        philosophical analysis of the supplied knowledge graph data.

        Args:
            entities: List of entity dicts.
            relations: List of relation dicts.
            causal_chains: List of causal chain dicts.

        Returns:
            Dict with ``"critique"`` (string) and ``"order_score"`` (int 0-100) keys.
        """
        return self._post(
            "/knowledge/critique",
            json={
                "entities": entities,
                "relations": relations,
                "causal_chains": causal_chains,
            },
        )

    def extract_with_interpretation(
        self, news_text: str, news_title: str = ""
    ) -> Dict[str, Any]:
        """Extract entities/relations from news text and generate a philosophical interpretation.

        Args:
            news_text: The news article text to analyse.
            news_title: Optional news title (improves the philosophical interpretation).

        Returns:
            Dict with ``"news_id"``, ``"entities"``, ``"relations"``,
            ``"philosophical_interpretation"``, and ``"extraction_timestamp"`` keys.
        """
        return self._post(
            "/extract/extract-with-interpretation",
            json={"news_text": news_text, "news_title": news_title},
        )

    def save_human_feedback(
        self,
        news_id: str,
        feedback_list: List[Dict[str, Any]],
        user_id: str = "wuqihang-brave",
    ) -> Dict[str, Any]:
        """Persist human accept/reject feedback for RLHF training data collection.

        Args:
            news_id: Unique identifier for the news article.
            feedback_list: List of per-relation feedback dicts, each containing
                ``relation_id``, ``from_entity``, ``to_entity``, ``relation_type``,
                ``action`` ("accept" | "reject"), ``confidence``, and optional ``reason``.
            user_id: User identifier (default ``"wuqihang-brave"``).

        Returns:
            Dict with ``"status"``, ``"feedback_count"``, and ``"saved_to"`` keys.
        """
        return self._post(
            "/extract/save-human-feedback",
            json={
                "news_id": news_id,
                "feedback_list": feedback_list,
                "user_id": user_id,
            },
        )

    # ------------------------------------------------------------------
    # Health / system endpoints
    # ------------------------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        """Ping the backend health endpoint."""
        return self._get("/health")

    # ------------------------------------------------------------------
    # Intelligence / Bayesian Bridge endpoints
    # ------------------------------------------------------------------

    def process_report_with_audit(
        self,
        text: str,
        source_url: str = "",
        source_reliability: float = 0.7,
        source_type: str = "news_article",
    ) -> Dict[str, Any]:
        """Submit a news report for full Bayesian audit processing.

        Args:
            text: Raw news article text.
            source_url: URL of the originating article.
            source_reliability: Reliability score of the source (0.0–1.0).
            source_type: One of ``"news_article"``, ``"user_input"``,
                or ``"inference"``.

        Returns:
            Dict with ``"reasoning_path_id"``, ``"probability_tree"``,
            ``"selected_branch"``, ``"graph_changes"``,
            ``"final_confidence"``, and ``"audit_status"`` keys.
        """
        return self._post(
            "/intelligence/report-with-audit",
            json={
                "text": text,
                "source_url": source_url,
                "source_reliability": source_reliability,
                "source_type": source_type,
            },
        )

    def get_reasoning_path(self, path_id: str) -> Dict[str, Any]:
        """Retrieve a completed reasoning path by UUID.

        Args:
            path_id: UUID of the reasoning path.

        Returns:
            Serialised ``ReasoningPath`` dict.
        """
        return self._get(f"/intelligence/reasoning-path/{path_id}")

    def get_probability_tree(self, report_id: str) -> Dict[str, Any]:
        """Retrieve a stored probability tree by report UUID.

        Args:
            report_id: UUID of the intelligence report.

        Returns:
            Serialised ``ProbabilityTree`` dict.
        """
        return self._get(f"/intelligence/probability-tree/{report_id}")

    def get_audit_log(self, limit: int = 20) -> Dict[str, Any]:
        """Return the most recent completed reasoning paths.

        Args:
            limit: Maximum number of paths to return (default 20).

        Returns:
            Dict with ``"paths"`` list and ``"total"`` count.
        """
        return self._get("/intelligence/audit-log", params={"limit": limit})

    # ------------------------------------------------------------------
    # Provenance endpoints
    # ------------------------------------------------------------------

    def get_relationship_provenance(self, relationship_id: str) -> Dict[str, Any]:
        """Return all source references supporting a specific relationship.

        Args:
            relationship_id: Unique identifier (or composite key) of the
                relationship edge.

        Returns:
            Dict with ``"relationship_id"``, ``"relationship_type"``,
            ``"from_entity"``, ``"to_entity"``, ``"source_refs"`` keys.
        """
        return self._get(f"/provenance/relationship/{relationship_id}")

    def get_entity_provenance(self, entity_id: str) -> Dict[str, Any]:
        """Return all relationships connected to an entity plus their source refs.

        Args:
            entity_id: Entity ID or name.

        Returns:
            Dict with ``"entity_id"``, ``"entity_name"``, ``"outgoing"``,
            ``"incoming"``, ``"property_history"`` keys.
        """
        return self._get(f"/provenance/entity/{entity_id}")

    def get_ontological_explanation(
        self,
        entity: Dict[str, Any],
        connected_entities: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Generate a philosophical explanation for an entity's ontological role.

        Args:
            entity: Entity dict with ``"name"``, ``"type"``, ``"description"`` keys.
            connected_entities: Optional list of connected entity dicts with
                ``"name"``, ``"type"``, ``"relationship"`` keys.

        Returns:
            Dict with ``"explanation"`` string key.
        """
        return self._post(
            "/knowledge/ontological-explanation",
            json={
                "entity": entity,
                "connected_entities": connected_entities or [],
            },
        )


# Module-level singleton – import and use directly in Streamlit pages.
api_client = APIClient()
