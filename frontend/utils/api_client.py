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

# Read backend URL from environment variable, defaults to localhost for local development
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8001")
_DEFAULT_BASE_URL = f"{BACKEND_URL}/api/v1"
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

    def extract_knowledge(self, text: str) -> Dict[str, Any]:
        """Extract entities and relations from raw text without persisting.

        Args:
            text: The news article text to analyse.

        Returns:
            Dict with ``"entities"``, ``"relations"``, ``"nodes_count"``,
            and ``"edges_count"`` keys.
        """
        return self._post("/knowledge/extract", json={"text": text})

    # ------------------------------------------------------------------
    # Simulation endpoints
    # ------------------------------------------------------------------

    def run_simulation(
        self,
        news_event: str,
        max_steps: int = 8,
        initial_tension: float = 0.45,
        seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run the multi-agent crisis simulation.

        Args:
            news_event:      Triggering event text to inject into the simulation.
            max_steps:       Number of simulation steps (5–10).
            initial_tension: Starting tension level [0.0, 1.0].
            seed:            Optional random seed for reproducibility.

        Returns:
            Dict with ``"messages"``, ``"path"``, ``"tension_level"``,
            ``"resolution_probabilities"``, ``"steps_run"``, and more.
        """
        payload: Dict[str, Any] = {
            "news_event": news_event,
            "max_steps": max_steps,
            "initial_tension": initial_tension,
        }
        if seed is not None:
            payload["seed"] = seed
        return self._post("/simulation/run", json=payload)

    def get_simulation_agents(self) -> Dict[str, Any]:
        """Return metadata for all simulation agents."""
        return self._get("/simulation/agents")

    # ------------------------------------------------------------------
    # Health / system endpoints
    # ------------------------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        """Ping the backend health endpoint."""
        return self._get("/health")


# Module-level singleton – import and use directly in Streamlit pages.
api_client = APIClient()
