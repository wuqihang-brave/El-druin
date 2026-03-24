"""
Logic Auditor – ReasoningPathRecorder
======================================

Records the complete inference chain from raw evidence through each LLM step
to the final knowledge-graph mutation.  Every ``ReasoningPath`` is stored as
JSON in an in-memory registry and can be serialised to a JSONL audit log on
disk.

Usage::

    from intelligence.logic_auditor import ReasoningPathRecorder

    recorder = ReasoningPathRecorder()
    path_id = recorder.start_path("news_article", "https://reuters.com/...", 0.9)
    recorder.record_evidence(path_id, "entity_fed", "Federal Reserve", "mentioned in article", 0.95)
    recorder.record_inference_step(path_id, "prompt text", "Fed raises rates", 0.88, "causal_extraction")
    recorder.record_graph_change(path_id, "edge_created", "entity_fed", "entity_rates", "INFLUENCES",
                                 {"causality_score": 0.88})
    path = recorder.finalize_path(path_id, audit_status="approved")
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from intelligence.models import (
    AuditStatus,
    ChangeType,
    GraphChange,
    InferenceStep,
    InputEvidence,
    ReasoningPath,
    ReasoningType,
    SourceInfo,
    SourceType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default audit log location (relative to repo root when resolved at runtime)
# ---------------------------------------------------------------------------
_AUDIT_LOG_RELATIVE = Path("data/reasoning_audit_log.jsonl")


def _resolve_audit_log() -> Path:
    """Resolve the JSONL audit log path relative to the project root."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "backend").is_dir() and (parent / "frontend").is_dir():
            return parent / _AUDIT_LOG_RELATIVE
    return Path.cwd() / _AUDIT_LOG_RELATIVE


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# ReasoningPathRecorder
# ---------------------------------------------------------------------------

class ReasoningPathRecorder:
    """Records the entire inference chain from evidence to graph update.

    All active and completed paths are kept in an in-memory dict.  Completed
    paths are also appended to a JSONL audit log so they survive restarts.
    """

    def __init__(self, audit_log: Optional[Path] = None) -> None:
        self._audit_log: Path = audit_log or _resolve_audit_log()
        # path_id → dict (mutable working copy)
        self._active: Dict[str, Dict[str, Any]] = {}
        # path_id → ReasoningPath (finalised)
        self._completed: Dict[str, ReasoningPath] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_path(
        self,
        source_type: str,
        source_url: str,
        source_reliability: float,
    ) -> str:
        """Initialise a new reasoning path.

        Args:
            source_type: One of "news_article", "user_input", or "inference".
            source_url: URL of the source document.
            source_reliability: Reliability score (0.0–1.0).

        Returns:
            Unique ``path_id`` string (UUID4).
        """
        path_id = str(uuid.uuid4())
        try:
            s_type = SourceType(source_type)
        except ValueError:
            logger.warning("Unknown source_type %r; defaulting to 'news_article'", source_type)
            s_type = SourceType.NEWS_ARTICLE

        self._active[path_id] = {
            "path_id": path_id,
            "timestamp": _now_iso(),
            "source": {
                "type": s_type.value,
                "url": source_url,
                "reliability": float(source_reliability),
            },
            "input_evidence": [],
            "inference_steps": [],
            "graph_changes": [],
        }
        logger.debug("Started reasoning path %s", path_id)
        return path_id

    def record_evidence(
        self,
        path_id: str,
        entity_id: str,
        entity_name: str,
        context: str,
        confidence: float,
    ) -> None:
        """Add an input evidence item to an active path.

        Args:
            path_id: The path to extend.
            entity_id: Identifier of the entity.
            entity_name: Human-readable entity name.
            context: Sentence/context where the entity was found.
            confidence: Confidence in this evidence (0.0–1.0).
        """
        path = self._get_active(path_id)
        if path is None:
            return
        path["input_evidence"].append(
            {
                "entity_id": entity_id,
                "entity_name": entity_name,
                "context": context,
                "confidence": float(confidence),
            }
        )

    def record_inference_step(
        self,
        path_id: str,
        llm_prompt: str,
        llm_response: str,
        confidence_score: float,
        reasoning_type: str,
    ) -> None:
        """Record one LLM inference step.

        Args:
            path_id: The path to extend.
            llm_prompt: The prompt sent to the LLM (or a summary thereof).
            llm_response: The LLM's response (or a summary thereof).
            confidence_score: Confidence produced by this step (0.0–1.0).
            reasoning_type: One of the ``ReasoningType`` enum values.
        """
        path = self._get_active(path_id)
        if path is None:
            return
        try:
            r_type = ReasoningType(reasoning_type)
        except ValueError:
            logger.warning("Unknown reasoning_type %r; defaulting to 'causal_extraction'", reasoning_type)
            r_type = ReasoningType.CAUSAL_EXTRACTION

        step_num = len(path["inference_steps"]) + 1
        path["inference_steps"].append(
            {
                "step_num": step_num,
                "llm_prompt": llm_prompt,
                "llm_response": llm_response,
                "confidence_score": float(confidence_score),
                "reasoning_type": r_type.value,
            }
        )

    def record_graph_change(
        self,
        path_id: str,
        change_type: str,
        entity_id: str,
        target_entity_id: str,
        relationship_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a knowledge-graph mutation.

        Args:
            path_id: The path to extend.
            change_type: One of "node_created", "edge_created",
                "contradicts_edge_created".
            entity_id: Primary entity involved.
            target_entity_id: Target entity (for edge changes).
            relationship_type: Edge label (e.g. ``"INFLUENCES"``).
            properties: Optional extra properties stored on the node/edge.
        """
        path = self._get_active(path_id)
        if path is None:
            return
        try:
            c_type = ChangeType(change_type)
        except ValueError:
            logger.warning("Unknown change_type %r; defaulting to 'edge_created'", change_type)
            c_type = ChangeType.EDGE_CREATED

        path["graph_changes"].append(
            {
                "change_type": c_type.value,
                "entity_id": entity_id,
                "target_entity_id": target_entity_id,
                "relationship_type": relationship_type,
                "properties": properties or {},
            }
        )

    def finalize_path(
        self,
        path_id: str,
        audit_status: str = "approved",
    ) -> ReasoningPath:
        """Close the active path and return the complete ``ReasoningPath``.

        The ``final_confidence`` is computed as the **weighted average** of all
        inference step confidence scores (equal weights).  If there are no steps
        the source reliability is used as a fallback.

        The completed path is appended to the JSONL audit log and moved from
        the active registry to the completed registry.

        Args:
            path_id: The path to finalise.
            audit_status: One of "approved", "flagged", or "pending_review".

        Returns:
            Validated ``ReasoningPath`` Pydantic object.
        """
        path = self._get_active(path_id)
        if path is None:
            # Return whatever we have in completed, or raise
            if path_id in self._completed:
                return self._completed[path_id]
            raise KeyError(f"No active reasoning path with id={path_id!r}")

        # Compute final_confidence
        steps: List[Dict[str, Any]] = path.get("inference_steps", [])
        if steps:
            final_confidence = sum(s["confidence_score"] for s in steps) / len(steps)
        else:
            final_confidence = path["source"].get("reliability", 0.5)

        try:
            a_status = AuditStatus(audit_status)
        except ValueError:
            logger.warning("Unknown audit_status %r; defaulting to 'pending_review'", audit_status)
            a_status = AuditStatus.PENDING_REVIEW

        path["final_confidence"] = round(final_confidence, 4)
        path["audit_status"] = a_status.value

        reasoning_path = ReasoningPath.model_validate(path)
        self._completed[path_id] = reasoning_path
        del self._active[path_id]

        # Persist to audit log
        self._append_to_log(reasoning_path)

        logger.info("Finalized reasoning path %s (confidence=%.3f)", path_id, final_confidence)
        return reasoning_path

    def get_path(self, path_id: str) -> Optional[ReasoningPath]:
        """Retrieve a previously recorded (completed) path.

        Args:
            path_id: UUID of the path to fetch.

        Returns:
            ``ReasoningPath`` if found, else ``None``.
        """
        return self._completed.get(path_id)

    def list_paths(self, limit: int = 50) -> List[ReasoningPath]:
        """Return the most recent completed paths (up to *limit*)."""
        paths = list(self._completed.values())
        return paths[-limit:]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_active(self, path_id: str) -> Optional[Dict[str, Any]]:
        path = self._active.get(path_id)
        if path is None:
            logger.warning("No active reasoning path with id=%r", path_id)
        return path

    def _append_to_log(self, path: ReasoningPath) -> None:
        """Append a finalised path to the JSONL audit log (best-effort)."""
        try:
            self._audit_log.parent.mkdir(parents=True, exist_ok=True)
            with self._audit_log.open("a", encoding="utf-8") as fh:
                fh.write(path.model_dump_json() + "\n")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not write to audit log %s: %s", self._audit_log, exc)
