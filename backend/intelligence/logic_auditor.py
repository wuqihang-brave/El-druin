"""
intelligence/logic_auditor.py
==============================
ReasoningPathRecorder — audit trail for Bayesian Bridge inference chains.

Each reasoning path records:
  - Source provenance (SourceInfo)
  - Input evidence items (InputEvidence)
  - Ordered LLM inference steps (InferenceStep)
  - Knowledge-graph mutations produced (GraphChange)

Completed paths are serialised to a JSONL audit log for traceability.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

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
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce_source_type(raw: str) -> SourceType:
    try:
        return SourceType(raw)
    except ValueError:
        logger.warning("Unknown source_type %r — defaulting to 'news_article'", raw)
        return SourceType.NEWS_ARTICLE


def _coerce_reasoning_type(raw: str) -> ReasoningType:
    try:
        return ReasoningType(raw)
    except ValueError:
        logger.warning("Unknown reasoning_type %r — defaulting to 'causal_extraction'", raw)
        return ReasoningType.CAUSAL_EXTRACTION


def _coerce_change_type(raw: str) -> ChangeType:
    try:
        return ChangeType(raw)
    except ValueError:
        logger.warning("Unknown change_type %r — defaulting to 'edge_created'", raw)
        return ChangeType.EDGE_CREATED


def _coerce_audit_status(raw: str) -> AuditStatus:
    try:
        return AuditStatus(raw)
    except ValueError:
        logger.warning("Unknown audit_status %r — defaulting to 'pending_review'", raw)
        return AuditStatus.PENDING_REVIEW


# ---------------------------------------------------------------------------
# ReasoningPathRecorder
# ---------------------------------------------------------------------------

class ReasoningPathRecorder:
    """
    Records the full inference chain for each reasoning path and persists
    completed paths to a JSONL audit log.

    Usage::

        recorder = ReasoningPathRecorder(audit_log=Path("audit.jsonl"))
        path_id = recorder.start_path("news_article", "https://example.com", 0.8)
        recorder.record_evidence(path_id, "ent_1", "Federal Reserve", "mentioned", 0.9)
        recorder.record_inference_step(path_id, prompt, response, 0.85, "causal_extraction")
        recorder.record_graph_change(path_id, "edge_created", "ent_1", "ent_2", "INFLUENCES")
        path = recorder.finalize_path(path_id)
    """

    def __init__(self, audit_log: Union[str, Path] = "audit.jsonl") -> None:
        self._audit_log = Path(audit_log)
        # In-progress paths keyed by path_id
        self._active: Dict[str, Dict[str, Any]] = {}
        # Completed ReasoningPath objects keyed by path_id
        self._completed: Dict[str, ReasoningPath] = {}

    # ------------------------------------------------------------------
    # start_path
    # ------------------------------------------------------------------

    def start_path(
        self,
        source_type: str,
        url: str,
        reliability: float,
    ) -> str:
        """
        Begin recording a new reasoning path.

        Returns the new path_id (UUID string).
        """
        path_id = str(uuid.uuid4())
        src_type = _coerce_source_type(source_type)
        self._active[path_id] = {
            "path_id": path_id,
            "timestamp": _now_iso(),
            "source": {
                "type": src_type.value,
                "url": url,
                "reliability": float(reliability),
            },
            "input_evidence": [],
            "inference_steps": [],
            "graph_changes": [],
        }
        return path_id

    # ------------------------------------------------------------------
    # record_evidence
    # ------------------------------------------------------------------

    def record_evidence(
        self,
        path_id: str,
        entity_id: str,
        entity_name: str,
        context: str,
        confidence: float = 0.7,
    ) -> None:
        """Append an evidence item to the active path. Silently ignores unknown path_ids."""
        if path_id not in self._active:
            logger.warning("record_evidence: unknown path_id %r — ignoring", path_id)
            return
        self._active[path_id]["input_evidence"].append({
            "entity_id": entity_id,
            "entity_name": entity_name,
            "context": context,
            "confidence": float(confidence),
        })

    # ------------------------------------------------------------------
    # record_inference_step
    # ------------------------------------------------------------------

    def record_inference_step(
        self,
        path_id: str,
        prompt: str,
        response: str,
        confidence_score: float,
        reasoning_type: str,
    ) -> None:
        """
        Append one LLM inference step to the active path.
        step_num is assigned sequentially (1-based).
        Unknown reasoning_type strings default to 'causal_extraction'.
        """
        if path_id not in self._active:
            logger.warning("record_inference_step: unknown path_id %r — ignoring", path_id)
            return
        steps = self._active[path_id]["inference_steps"]
        step_num = len(steps) + 1
        rt = _coerce_reasoning_type(reasoning_type)
        steps.append({
            "step_num": step_num,
            "llm_prompt": prompt,
            "llm_response": response,
            "confidence_score": float(confidence_score),
            "reasoning_type": rt.value,
        })

    # ------------------------------------------------------------------
    # record_graph_change
    # ------------------------------------------------------------------

    def record_graph_change(
        self,
        path_id: str,
        change_type: str,
        entity_id: str,
        target_entity_id: str = "",
        relationship_type: str = "",
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Append a graph mutation record to the active path.
        Unknown change_type strings default to 'edge_created'.
        """
        if path_id not in self._active:
            logger.warning("record_graph_change: unknown path_id %r — ignoring", path_id)
            return
        ct = _coerce_change_type(change_type)
        self._active[path_id]["graph_changes"].append({
            "change_type": ct.value,
            "entity_id": entity_id,
            "target_entity_id": target_entity_id,
            "relationship_type": relationship_type,
            "properties": properties if properties is not None else {},
        })

    # ------------------------------------------------------------------
    # finalize_path
    # ------------------------------------------------------------------

    def finalize_path(
        self,
        path_id: str,
        audit_status: str = "pending_review",
    ) -> ReasoningPath:
        """
        Finalise a reasoning path, compute final_confidence, move it from
        _active to _completed, and append it to the JSONL audit log.

        Raises KeyError if path_id is not in _active.
        """
        if path_id not in self._active:
            raise KeyError(f"No active reasoning path with id {path_id!r}")

        raw = self._active.pop(path_id)
        steps = raw["inference_steps"]

        # final_confidence = mean of step confidence scores; fallback = source reliability
        if steps:
            final_confidence = sum(s["confidence_score"] for s in steps) / len(steps)
        else:
            final_confidence = raw["source"]["reliability"]

        status = _coerce_audit_status(audit_status)

        path = ReasoningPath(
            path_id=raw["path_id"],
            timestamp=raw["timestamp"],
            source=SourceInfo(
                type=raw["source"]["type"],
                url=raw["source"]["url"],
                reliability=raw["source"]["reliability"],
            ),
            input_evidence=[InputEvidence(**e) for e in raw["input_evidence"]],
            inference_steps=[InferenceStep(**s) for s in steps],
            graph_changes=[GraphChange(**c) for c in raw["graph_changes"]],
            final_confidence=round(final_confidence, 6),
            audit_status=status,
        )

        self._completed[path_id] = path
        self._write_audit_log(path)
        return path

    # ------------------------------------------------------------------
    # query helpers
    # ------------------------------------------------------------------

    def get_path(self, path_id: str) -> Optional[ReasoningPath]:
        """Return a completed ReasoningPath by id, or None if not found."""
        return self._completed.get(path_id)

    def list_paths(self, limit: Optional[int] = None) -> List[ReasoningPath]:
        """Return completed paths in insertion order, optionally capped at *limit*."""
        paths = list(self._completed.values())
        if limit is not None:
            paths = paths[:limit]
        return paths

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    def _write_audit_log(self, path: ReasoningPath) -> None:
        try:
            self._audit_log.parent.mkdir(parents=True, exist_ok=True)
            with self._audit_log.open("a", encoding="utf-8") as fh:
                fh.write(path.model_dump_json() + "\n")
        except Exception as exc:
            logger.warning("Failed to write audit log entry: %s", exc)
