"""
Intelligence Logic Audit API routes.

Endpoints:
  POST /intelligence/report-with-audit   – process a news report with full Bayesian audit trail
  GET  /intelligence/reasoning-path/{path_id}  – retrieve a recorded reasoning path
  GET  /intelligence/probability-tree/{report_id}  – retrieve a stored probability tree
  GET  /intelligence/audit-log           – list recent reasoning paths
"""

from __future__ import annotations

import logging
import sys
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/intelligence", tags=["intelligence"])

# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class ReportWithAuditRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=10,
        max_length=20000,
        description="Raw news article text to process",
    )
    source_url: str = Field(
        default="",
        description="URL of the originating article",
    )
    source_reliability: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Reliability score of the source (0.0–1.0)",
    )
    source_type: str = Field(
        default="news_article",
        description="Source type: 'news_article', 'user_input', or 'inference'",
    )


# ---------------------------------------------------------------------------
# Lazy singletons for recorder / builder
# ---------------------------------------------------------------------------

_recorder = None
_builder = None


def _get_recorder():
    global _recorder  # noqa: PLW0603
    if _recorder is None:
        # Ensure intelligence package is importable regardless of working dir
        _ensure_intelligence_importable()
        from intelligence.logic_auditor import ReasoningPathRecorder
        _recorder = ReasoningPathRecorder()
    return _recorder


def _get_builder():
    global _builder  # noqa: PLW0603
    if _builder is None:
        _ensure_intelligence_importable()
        from intelligence.probability_tree import ProbabilityTreeBuilder
        _builder = ProbabilityTreeBuilder()
    return _builder


def _ensure_intelligence_importable() -> None:
    """Add the backend directory to sys.path so the intelligence package is importable."""
    here = os.path.abspath(__file__)
    # Walk up from routes/intelligence.py → routes → api → app → backend
    backend_dir = os.path.dirname(  # backend/
        os.path.dirname(  # app/
            os.path.dirname(  # api/
                os.path.dirname(here)  # routes/
            )
        )
    )
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/report-with-audit")
def process_report_with_audit(request: ReportWithAuditRequest) -> Dict[str, Any]:
    """Process a news report through the full Bayesian audit pipeline.

    Steps:
    1. Start a ``ReasoningPath`` (provenance tracking)
    2. Build a ``ProbabilityTree`` (alternative interpretations)
    3. Select the highest-weight branch
    4. Record inference steps for each entity extracted from the text
    5. Record the resulting graph change
    6. Finalise the ``ReasoningPath`` and persist both objects

    Returns:
        Dict with ``reasoning_path_id``, ``probability_tree``,
        ``selected_branch``, and ``graph_changes``.
    """
    recorder = _get_recorder()
    builder = _get_builder()

    # 1. Start reasoning path
    path_id = recorder.start_path(
        source_type=request.source_type,
        source_url=request.source_url,
        source_reliability=request.source_reliability,
    )

    # 2. Build probability tree (use path_id as report_id for unified lookup)
    tree = builder.build_tree(
        text=request.text,
        source_reliability=request.source_reliability,
        report_id=path_id,
    )

    # 3. Select best branch
    best_branch = builder.select_best_branch(tree)

    # 4. Record evidence from entity extraction (lightweight heuristic)
    from intelligence.probability_tree import _extract_entities_from_text
    entities = _extract_entities_from_text(request.text)
    for i, ent_name in enumerate(entities[:4]):
        recorder.record_evidence(
            path_id=path_id,
            entity_id=f"entity_{i}_{ent_name.lower().replace(' ', '_')}",
            entity_name=ent_name,
            context=request.text[:120],
            confidence=request.source_reliability,
        )

    # 5. Record inference steps
    recorder.record_inference_step(
        path_id=path_id,
        llm_prompt=f"Extract entities and causal links from: {request.text[:80]}…",
        llm_response=f"Detected {len(entities)} entities; selected branch: {best_branch.get('interpretation', '')}",
        confidence_score=best_branch.get("confidence", request.source_reliability),
        reasoning_type="causal_extraction",
    )
    recorder.record_inference_step(
        path_id=path_id,
        llm_prompt=f"Check for contradictions in: {request.text[:80]}…",
        llm_response=f"Contradiction confidence: {tree.interpretation_branches[1].confidence if len(tree.interpretation_branches) > 1 else 0:.2f}",
        confidence_score=tree.interpretation_branches[1].confidence if len(tree.interpretation_branches) > 1 else 0.1,
        reasoning_type="conflict_detection",
    )

    # 6. Record graph change based on selected branch
    extracted_facts = best_branch.get("extracted_facts", [])
    graph_changes: List[Dict[str, Any]] = []

    if extracted_facts:
        fact = extracted_facts[0]
        rel_type = fact.get("type", "INFLUENCES")
        change_type = (
            "contradicts_edge_created" if rel_type == "CONTRADICTS" else "edge_created"
        )
        from_ent = fact.get("from", "")
        to_ent = fact.get("to", "")
        props: Dict[str, Any] = {
            "source_reliability": request.source_reliability,
        }
        if fact.get("causality_score") is not None:
            props["causality_score"] = fact["causality_score"]
        if fact.get("conflict_confidence") is not None:
            props["conflict_confidence"] = fact["conflict_confidence"]

        recorder.record_graph_change(
            path_id=path_id,
            change_type=change_type,
            entity_id=from_ent,
            target_entity_id=to_ent,
            relationship_type=rel_type,
            properties=props,
        )
        graph_changes.append(
            {
                "change_type": change_type,
                "from": from_ent,
                "to": to_ent,
                "relationship_type": rel_type,
                "properties": props,
            }
        )
    else:
        # No strong facts extracted – still record a node-creation attempt
        if entities:
            recorder.record_graph_change(
                path_id=path_id,
                change_type="node_created",
                entity_id=entities[0],
                target_entity_id="",
                relationship_type="",
                properties={"source_reliability": request.source_reliability},
            )

    # 7. Finalise path
    audit_status = "approved" if best_branch.get("confidence", 0) >= 0.5 else "flagged"
    reasoning_path = recorder.finalize_path(path_id, audit_status=audit_status)

    # 8. Persist tree
    builder.store_tree(tree)

    return {
        "reasoning_path_id": path_id,
        "probability_tree": tree.model_dump(),
        "selected_branch": best_branch,
        "graph_changes": graph_changes,
        "final_confidence": reasoning_path.final_confidence,
        "audit_status": reasoning_path.audit_status,
    }


@router.get("/reasoning-path/{path_id}")
def get_reasoning_path(path_id: str) -> Dict[str, Any]:
    """Retrieve a completed reasoning path by ID.

    Args:
        path_id: UUID of the reasoning path.

    Returns:
        Serialised ``ReasoningPath`` dict, or 404 if not found.
    """
    recorder = _get_recorder()
    path = recorder.get_path(path_id)
    if path is None:
        raise HTTPException(status_code=404, detail=f"Reasoning path {path_id!r} not found")
    return path.model_dump()


@router.get("/probability-tree/{report_id}")
def get_probability_tree(report_id: str) -> Dict[str, Any]:
    """Retrieve a stored probability tree by report ID.

    Args:
        report_id: UUID of the intelligence report.

    Returns:
        Serialised ``ProbabilityTree`` dict, or 404 if not found.
    """
    builder = _get_builder()
    tree = builder.get_tree(report_id)
    if tree is None:
        raise HTTPException(status_code=404, detail=f"Probability tree {report_id!r} not found")
    return tree.model_dump()


@router.get("/audit-log")
def list_audit_log(
    limit: int = Query(20, ge=1, le=100, description="Maximum number of paths to return"),
) -> Dict[str, Any]:
    """Return the most recent completed reasoning paths.

    Args:
        limit: Number of paths to return (default 20, max 100).

    Returns:
        Dict with ``"paths"`` list and ``"total"`` count.
    """
    recorder = _get_recorder()
    paths = recorder.list_paths(limit=limit)
    return {
        "paths": [p.model_dump() for p in paths],
        "total": len(paths),
    }
