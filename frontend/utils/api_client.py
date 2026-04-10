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

# --- 修改开始 ---
# 优先级：环境变量 > 默认本地地址
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8001")

# 核心修复：自动清理掉可能导致 404 的旧前缀
if BACKEND_URL.endswith("/api/v1"):
    BACKEND_URL = BACKEND_URL.replace("/api/v1", "")

_DEFAULT_BASE_URL = BACKEND_URL.rstrip("/")
_TIMEOUT = 40  # 增加一点超时时间，防止 502
# --- 修改结束 ---
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

    def seed_knowledge_graph(self) -> Dict[str, Any]:
        """Populate the knowledge graph with baseline example triples.

        Useful when the graph is empty and the user wants to explore the
        visualisation features with representative data.

        Returns:
            Dict with ``"status"``, ``"triples_added"``, and ``"message"`` keys.
        """
        return self._post("/knowledge/seed-triples")

    def dispatch_query_engine(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        matched_commands: Optional[List[str]] = None,
        matched_tools: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Dispatch a prompt through the CLAW QueryEnginePort.

        Args:
            prompt: Natural-language prompt or command string.
            session_id: Optional session UUID to resume an existing session.
            matched_commands: Pre-matched command names to attach to the turn.
            matched_tools: Pre-matched tool names to attach to the turn.

        Returns:
            Dict with ``"session_id"``, ``"output"``, ``"stop_reason"``,
            ``"usage"``, and ``"turns_used"`` keys.
        """
        body: Dict[str, Any] = {
            "prompt": prompt,
            "matched_commands": matched_commands or [],
            "matched_tools": matched_tools or [],
        }
        if session_id:
            body["session_id"] = session_id
        return self._post("/knowledge/query-engine", json=body)

    def get_tool_registry(self, query: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        """List tools registered in the CLAW tool registry.

        Args:
            query: Optional search string to filter tools by name or source hint.
            limit: Maximum number of tools to return.

        Returns:
            Dict with ``"tools"`` list, ``"total"``, and ``"registry_size"`` keys.
        """
        params: Dict[str, Any] = {"limit": limit}
        if query:
            params["query"] = query
        return self._get("/intelligence/tool-registry", params=params)

    def dispatch_tool(self, name: str, payload: str = "") -> Dict[str, Any]:
        """Execute a registered CLAW tool by name.

        Args:
            name: Name of the registered tool (case-insensitive).
            payload: Optional string payload forwarded to the tool.

        Returns:
            Dict with ``"name"``, ``"source_hint"``, ``"handled"``,
            ``"message"``, and ``"task_status"`` keys.
        """
        return self._post("/intelligence/dispatch-tool", json={"name": name, "payload": payload})

    def grounded_deduce(self, news: Dict[str, Any]) -> Dict[str, Any]:
        """Call the graph-grounded deduction endpoint for a news item.

        Sends the news summary and extracted entities to
        ``POST /analysis/grounded/deduce`` and returns the full deduction
        result including ``graph_evidence`` from KuzuDB.

        Args:
            news: News item dict.  Recognised keys:

                * ``"summary"`` / ``"description"`` – news body text
                * ``"title"``                       – news headline
                * ``"entities"``                    – list of entity name strings
                  (if pre-extracted; falls back to empty list)

        Returns:
            Full response dict from the backend, containing
            ``"status"``, ``"deduction_result"`` (with ``driving_factor``,
            ``scenario_alpha``, ``scenario_beta``, ``verification_gap``,
            ``confidence``, ``graph_evidence``), and ``"ontological_grounding"``.
        """
        news_body = news.get("summary") or news.get("description") or ""
        title = news.get("title", "")
        # Combine title and body so the backend has richer text for domain
        # detection and entity extraction.  Fall back to title alone if the
        # body is empty.
        if news_body:
            news_fragment = f"{title}\n\n{news_body}".strip() if title else news_body
        else:
            news_fragment = title
        claim_title = title or "this event"
        raw_entities = news.get("entities", [])
        # Accept either a list of strings or a list of entity dicts.
        # The `and len(raw_entities) > 0` guard makes the non-empty check explicit
        # and avoids any ambiguity around the isinstance access.
        if raw_entities and len(raw_entities) > 0 and isinstance(raw_entities[0], dict):
            seed_entities = [e.get("name", "") for e in raw_entities if e.get("name")]
        else:
            seed_entities = [str(e) for e in raw_entities if e]

        return self._post(
            "/analysis/grounded/deduce",
            json={
                "news_fragment": news_fragment,
                "seed_entities": seed_entities,
                "claim": f"What will be the impact of {claim_title}?",
            },
        )

    def evented_deduce(
        self,
        news: Dict[str, Any],
        deep_mode: bool = False,
        deep_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Call the evented reasoning pipeline endpoint for a news item.

        Sends the news summary to ``POST /analysis/evented/deduce`` and returns
        the three-stage result: events → active/derived patterns → conclusion +
        credibility.  When *deep_mode* is enabled the backend will also run the
        evidence enrichment pipeline and include an ``"enrichment"`` key in the
        response.

        Args:
            news:        News item dict.  Recognised keys:
                           * ``"summary"`` / ``"description"`` – news body text
                           * ``"title"``                       – news headline
                           * ``"entities"``                    – list of entity name strings
                           * ``"url"``                         – article URL (used as source_url)
                           * ``"published"`` / ``"published_at"`` – publish date
                           * ``"source"``                      – publisher name
            deep_mode:   Enable Deep Ontology Analysis (enrichment + re-reasoning).
            deep_config: Optional dict with keys: level (0-3), timeout_seconds,
                         max_sources.

        Returns:
            Full response dict from the backend.  In deep mode this includes
            an ``"enrichment"`` key with provenance and cache-hit status.
        """
        news_body = news.get("summary") or news.get("description") or ""
        title = news.get("title", "")
        if news_body:
            news_fragment = f"{title}\n\n{news_body}".strip() if title else news_body
        else:
            news_fragment = title
        claim_title = title or "this event"
        raw_entities = news.get("entities", [])
        if raw_entities and len(raw_entities) > 0 and isinstance(raw_entities[0], dict):
            seed_entities = [e.get("name", "") for e in raw_entities if e.get("name")]
        else:
            seed_entities = [str(e) for e in raw_entities if e]

        payload: Dict[str, Any] = {
            "news_fragment": news_fragment,
            "seed_entities": seed_entities,
            "claim": f"What will be the impact of {claim_title}?",
            "deep_mode": deep_mode,
        }

        if deep_mode:
            if deep_config:
                payload["deep_config"] = deep_config
            # Pass source URL for level-2+ enrichment
            article_url = news.get("url") or news.get("link") or ""
            if article_url:
                payload["source_url"] = article_url
            # Pass local metadata for level-1 enrichment
            published = (
                news.get("published_at")
                or news.get("published")
                or ""
            )
            source_name = news.get("source") or ""
            if published or source_name or article_url:
                payload["local_meta"] = {
                    "published_at": str(published) if published else "",
                    "source":       source_name,
                    "url":          article_url,
                }

        return self._post("/analysis/evented/deduce", json=payload)

    # ------------------------------------------------------------------
    # Assessment workspace endpoints
    # ------------------------------------------------------------------

    def get_assessments(self) -> list:
        """Return all available assessments.

        Returns:
            List of assessment dicts.  Falls back to a minimal stub list when
            the backend is unreachable so the UI always renders.
        """
        result = self._get("/api/v1/assessments")
        if "error" in result:
            return _ASSESSMENT_LIST_STUB
        return result.get("assessments", [])

    def get_assessment(self, assessment_id: str) -> Dict[str, Any]:
        """Return a single assessment by ID.

        Returns:
            Assessment dict or a stub fallback.
        """
        result = self._get(f"/api/v1/assessments/{assessment_id}")
        if "error" in result:
            return _ASSESSMENT_STUB
        return result

    def get_brief(self, assessment_id: str) -> Dict[str, Any]:
        """Return the executive brief for an assessment."""
        result = self._get(f"/api/v1/assessments/{assessment_id}/brief")
        if "error" in result:
            return _BRIEF_STUB
        return result

    def get_regime(self, assessment_id: str) -> Dict[str, Any]:
        """Return the current regime state for an assessment."""
        result = self._get(f"/api/v1/assessments/{assessment_id}/regime")
        if "error" in result:
            return _REGIME_STUB
        return result

    def get_triggers(self, assessment_id: str) -> Dict[str, Any]:
        """Return the trigger amplification output for an assessment."""
        result = self._get(f"/api/v1/assessments/{assessment_id}/triggers")
        if "error" in result:
            return _TRIGGERS_STUB
        return result

    def get_attractors(self, assessment_id: str) -> Dict[str, Any]:
        """Return the attractor output for an assessment."""
        result = self._get(f"/api/v1/assessments/{assessment_id}/attractors")
        if "error" in result:
            return _ATTRACTORS_STUB
        return result

    def get_propagation(self, assessment_id: str) -> Dict[str, Any]:
        """Return the propagation sequence for an assessment."""
        result = self._get(f"/api/v1/assessments/{assessment_id}/propagation")
        if "error" in result:
            return _PROPAGATION_STUB
        return result

    def get_delta(self, assessment_id: str) -> Dict[str, Any]:
        """Return the update delta output for an assessment."""
        result = self._get(f"/api/v1/assessments/{assessment_id}/delta")
        if "error" in result:
            return _DELTA_STUB
        return result

    def get_evidence(self, assessment_id: str) -> Dict[str, Any]:
        """Return the evidence items for an assessment."""
        result = self._get(f"/api/v1/assessments/{assessment_id}/evidence")
        if "error" in result:
            return _EVIDENCE_STUB
        return result

    def get_coupling(self, assessment_id: str) -> Dict[str, Any]:
        """Return the structural coupling pairs for an assessment."""
        result = self._get(f"/api/v1/assessments/{assessment_id}/coupling")
        if "error" in result:
            return _COUPLING_STUB
        return result


# ---------------------------------------------------------------------------
# Offline fallback stubs – returned when backend is unreachable
# These match the shape of the backend schemas so the UI always renders.
# ---------------------------------------------------------------------------

_ASSESSMENT_STUB: Dict[str, Any] = {
    "assessment_id": "ae-204",
    "title": "Black Sea Energy Corridor – Structural Watch",
    "assessment_type": "structural_watch",
    "status": "active",
    "region_tags": ["Eastern Europe", "Black Sea", "Middle East"],
    "domain_tags": ["energy", "military", "sanctions", "finance"],
    "created_at": "2026-03-01T09:00:00Z",
    "updated_at": "2026-04-09T18:00:00Z",
    "last_regime": "Nonlinear Escalation",
    "last_confidence": "High",
    "alert_count": 3,
    "analyst_notes": "Pipeline disruption risk elevated following recent naval incidents.",
}

_ASSESSMENT_LIST_STUB: list = [_ASSESSMENT_STUB]

_BRIEF_STUB: Dict[str, Any] = {
    "assessment_id": "ae-204",
    "forecast_posture": "Upward-skewed energy risk",
    "time_horizon": "3-7 days",
    "confidence": "High",
    "why_it_matters": (
        "A disruption to the Black Sea energy corridor would cascade into EU "
        "spot-market prices within 24 hours and increase sanctions pressure on "
        "transit states within 72 hours."
    ),
    "dominant_driver": "Naval interdiction pressure on energy transit routes",
    "strengthening_conditions": [
        "Additional naval assets deployed in contested waters",
        "Insurance market withdrawal from corridor tankers",
        "Diplomatic channel breakdown between transit states",
    ],
    "weakening_conditions": [
        "Ceasefire or de-escalation agreement signed",
        "Alternative pipeline capacity comes online",
        "Third-party mediation accepted by all parties",
    ],
    "invalidation_conditions": [
        "Full corridor reopening confirmed by all transit operators",
        "Regional security guarantee treaty ratified",
    ],
    "reasoning_path_id": None,  # set to a real UUID when backend is live
    "updated_at": "2026-04-09T18:00:00Z",
}

_REGIME_STUB: Dict[str, Any] = {
    "assessment_id": "ae-204",
    "current_regime": "Nonlinear Escalation",
    "threshold_distance": 0.18,
    "transition_volatility": 0.74,
    "reversibility_index": 0.31,
    "dominant_axis": "military -> sanctions -> energy",
    "coupling_asymmetry": 0.62,
    "damping_capacity": 0.29,
    "forecast_implication": (
        "System is within the nonlinear escalation band. A moderate shock to "
        "any coupled domain is sufficient to trigger cascade propagation. "
        "Damping capacity is low; diplomatic interventions have a narrow window."
    ),
    "updated_at": "2026-04-09T18:00:00Z",
}

_TRIGGERS_STUB: Dict[str, Any] = {
    "assessment_id": "ae-204",
    "triggers": [
        {
            "name": "Naval incident in contested strait",
            "amplification_factor": 0.87,
            "jump_potential": "Critical",
            "impacted_domains": ["military", "energy", "insurance", "finance"],
            "expected_lag_hours": 6,
            "confidence": 0.81,
            "watch_signals": [
                "AIS dark zones expanding",
                "Insurance premium spike >20%",
                "Emergency UNSC session called",
            ],
            "damping_opportunities": [
                "Bilateral hotline activation",
                "Neutral maritime observer deployment",
            ],
        },
        {
            "name": "Secondary sanctions package announced",
            "amplification_factor": 0.71,
            "jump_potential": "High",
            "impacted_domains": ["finance", "energy", "trade"],
            "expected_lag_hours": 48,
            "confidence": 0.68,
            "watch_signals": [
                "Treasury OFAC pre-designation briefings",
                "Correspondent banking withdrawals from region",
            ],
            "damping_opportunities": [
                "Carve-out negotiations via EU intermediaries",
                "Humanitarian exemption framework agreed",
            ],
        },
    ],
    "updated_at": "2026-04-09T18:00:00Z",
}

_ATTRACTORS_STUB: Dict[str, Any] = {
    "assessment_id": "ae-204",
    "attractors": [
        {
            "name": "Protracted low-level blockade equilibrium",
            "pull_strength": 0.78,
            "horizon": "3-10d",
            "supporting_evidence_count": 14,
            "counterforces": [
                "Economic cost to blocking state",
                "NATO maritime presence",
            ],
            "invalidation_conditions": [
                "Full unilateral withdrawal of naval assets",
                "Internationally brokered corridor guarantee",
            ],
            "trend": "up",
        },
        {
            "name": "Fragile corridor reopening under third-party guarantee",
            "pull_strength": 0.41,
            "horizon": "10-21d",
            "supporting_evidence_count": 6,
            "counterforces": [
                "Domestic political constraints on concessions",
                "Ongoing military operations in adjacent theatre",
            ],
            "invalidation_conditions": [
                "Escalation to direct state-on-state naval exchange",
            ],
            "trend": "stable",
        },
    ],
    "updated_at": "2026-04-09T18:00:00Z",
}

_PROPAGATION_STUB: Dict[str, Any] = {
    "assessment_id": "ae-204",
    "sequence": [
        {"step": 1, "domain": "military", "event": "Naval assets block strait access", "time_bucket": "T+0"},
        {"step": 2, "domain": "energy", "event": "Tanker transit suspended; spot prices spike 12%", "time_bucket": "T+24h"},
        {"step": 3, "domain": "insurance", "event": "Lloyd's withdraws corridor coverage", "time_bucket": "T+24h"},
        {"step": 4, "domain": "finance", "event": "Regional sovereign spreads widen 40bps", "time_bucket": "T+72h"},
        {"step": 5, "domain": "trade", "event": "Alternative routing adds $3.2/bbl cost; contract renegotiations begin", "time_bucket": "T+7d"},
        {"step": 6, "domain": "political", "event": "Emergency EU energy council; sanctions expansion tabled", "time_bucket": "T+2-6w"},
    ],
    "bottlenecks": [
        "Single strait chokepoint with no viable short-term alternative",
        "Insurance market concentration in London market",
    ],
    "second_order_effects": [
        "Increased LNG spot demand in Mediterranean markets",
        "Accelerated permitting for alternative pipeline routes",
        "Domestic energy rationing measures in downstream states",
    ],
    "updated_at": "2026-04-09T18:00:00Z",
}

_DELTA_STUB: Dict[str, Any] = {
    "assessment_id": "ae-204",
    "regime_changed": True,
    "threshold_direction": "narrowing",
    "trigger_ranking_changes": [
        {"field": "Naval incident trigger rank", "previous": 2, "current": 1, "direction": "increased"},
        {"field": "Sanctions trigger rank", "previous": 1, "current": 2, "direction": "decreased"},
    ],
    "attractor_pull_changes": [
        {"field": "Protracted blockade pull_strength", "previous": 0.61, "current": 0.78, "direction": "increased"},
    ],
    "damping_capacity_delta": -0.12,
    "confidence_delta": 0.07,
    "new_evidence_count": 4,
    "summary": (
        "Regime shifted from Stress Accumulation to Nonlinear Escalation "
        "following confirmation of naval asset deployment. Damping capacity "
        "deteriorated by 12 points. Four new high-quality evidence items "
        "incorporated, raising overall confidence."
    ),
    "updated_at": "2026-04-09T18:00:00Z",
}

_EVIDENCE_STUB: Dict[str, Any] = {
    "assessment_id": "ae-204",
    "evidence": [
        {
            "evidence_id": "ev-1001",
            "source": "Lloyd's List Intelligence – AIS Feed",
            "timestamp": "2026-04-09T06:14:00Z",
            "source_quality": "Primary",
            "impacted_area": "energy / maritime",
            "structural_novelty": 0.82,
            "confidence_contribution": 0.19,
            "provenance_link": "/api/v1/provenance/entity/ev-1001",
        },
        {
            "evidence_id": "ev-1002",
            "source": "Reuters – Diplomatic correspondent",
            "timestamp": "2026-04-09T09:45:00Z",
            "source_quality": "High",
            "impacted_area": "political / sanctions",
            "structural_novelty": 0.54,
            "confidence_contribution": 0.11,
            "provenance_link": "/api/v1/provenance/entity/ev-1002",
        },
        {
            "evidence_id": "ev-1003",
            "source": "EU Commission energy market daily bulletin",
            "timestamp": "2026-04-09T12:00:00Z",
            "source_quality": "Primary",
            "impacted_area": "energy / finance",
            "structural_novelty": 0.67,
            "confidence_contribution": 0.14,
            "provenance_link": "/api/v1/provenance/entity/ev-1003",
        },
        {
            "evidence_id": "ev-1004",
            "source": "Regional think-tank analysis",
            "timestamp": "2026-04-08T17:30:00Z",
            "source_quality": "Medium",
            "impacted_area": "military / political",
            "structural_novelty": 0.39,
            "confidence_contribution": 0.06,
            "provenance_link": None,
        },
    ],
    "updated_at": "2026-04-09T18:00:00Z",
}


_COUPLING_STUB: Dict[str, Any] = {
    "assessment_id": "ae-204",
    "pairs": [
        {
            "domain_a": "military",
            "domain_b": "energy",
            "coupling_strength": 2.14,
            "is_amplifying": True,
            "amplification_label": "High amplification",
        },
        {
            "domain_a": "finance",
            "domain_b": "sanctions",
            "coupling_strength": 1.87,
            "is_amplifying": True,
            "amplification_label": "High amplification",
        },
        {
            "domain_a": "energy",
            "domain_b": "trade",
            "coupling_strength": 1.12,
            "is_amplifying": False,
            "amplification_label": "Moderate coupling",
        },
    ],
    "updated_at": "2026-04-09T18:00:00Z",
}


# ---------------------------------------------------------------------------
# Module-level convenience functions (functional-style API)
# ---------------------------------------------------------------------------

def get_assessments() -> list:
    """Return all available assessments (module-level convenience function)."""
    return api_client.get_assessments()


def get_assessment(assessment_id: str) -> Dict[str, Any]:
    """Return a single assessment by ID (module-level convenience function)."""
    return api_client.get_assessment(assessment_id)


def get_brief(assessment_id: str) -> Dict[str, Any]:
    """Return the executive brief for an assessment."""
    return api_client.get_brief(assessment_id)


def get_regime(assessment_id: str) -> Dict[str, Any]:
    """Return the current regime state for an assessment."""
    return api_client.get_regime(assessment_id)


def get_triggers(assessment_id: str) -> Dict[str, Any]:
    """Return the trigger amplification output for an assessment."""
    return api_client.get_triggers(assessment_id)


def get_attractors(assessment_id: str) -> Dict[str, Any]:
    """Return the attractor output for an assessment."""
    return api_client.get_attractors(assessment_id)


def get_propagation(assessment_id: str) -> Dict[str, Any]:
    """Return the propagation sequence for an assessment."""
    return api_client.get_propagation(assessment_id)


def get_delta(assessment_id: str) -> Dict[str, Any]:
    """Return the update delta output for an assessment."""
    return api_client.get_delta(assessment_id)


def get_evidence(assessment_id: str) -> Dict[str, Any]:
    """Return the evidence items for an assessment."""
    return api_client.get_evidence(assessment_id)


def get_coupling(assessment_id: str) -> Dict[str, Any]:
    """Return the structural coupling pairs for an assessment."""
    return api_client.get_coupling(assessment_id)


# Module-level singleton – import and use directly in Streamlit pages.
api_client = APIClient()
