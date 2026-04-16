"""
Intelligence API routes.

Endpoints:
  GET  /intelligence/reasoning-path/{path_id}  – retrieve a recorded reasoning path
  GET  /intelligence/probability-tree/{report_id}  – retrieve a stored probability tree
  GET  /intelligence/tool-registry       – list registered CLAW tools
  POST /intelligence/dispatch-tool       – execute a registered CLAW tool by name

Note: The /report-with-audit and /audit-log endpoints have been removed.
Trace/audit data access is available only within the Assessment Workspace
Trace panel (via the assessments API).
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


@router.get("/probability-tree/assessment/{assessment_id}")
def get_probability_tree_for_assessment(assessment_id: str) -> Dict[str, Any]:
    """Build and return a p-adic probability tree for the given assessment.

    This endpoint generates a probability tree on-the-fly from the assessment's
    title and analyst notes.  It does not persist the tree – the result is
    computed fresh on each request.

    Args:
        assessment_id: The assessment's stable ID (e.g. ``ae-XXXXXXXX``).

    Returns:
        Serialised ``ProbabilityTree`` dict, or 404 if the assessment is unknown.
    """
    try:
        from app.core.assessment_store import assessment_store as _store  # noqa: PLC0415

        assessment = _store.get_assessment(assessment_id)
        if assessment is None:
            raise HTTPException(
                status_code=404,
                detail=f"Assessment {assessment_id!r} not found",
            )

        # Build a structured text description for the probability tree builder.
        # Use explicit labels and sentence separators to aid keyword parsing.
        text_parts = [assessment.title or ""]
        if assessment.analyst_notes:
            text_parts.append(assessment.analyst_notes)
        if assessment.domain_tags:
            text_parts.append("Domains: " + ", ".join(assessment.domain_tags) + ".")
        if assessment.region_tags:
            text_parts.append("Regions: " + ", ".join(assessment.region_tags) + ".")
        text = " ".join(text_parts)

        # Use last_confidence to derive source_reliability (High→0.85, Medium→0.70, Low→0.55)
        _reliability_map = {"High": 0.85, "Medium": 0.70, "Low": 0.55}
        source_reliability = _reliability_map.get(assessment.last_confidence or "", 0.70)

        builder = _get_builder()
        tree = builder.build_tree(
            text=text,
            source_reliability=source_reliability,
            report_id=assessment_id,
        )
        return tree.model_dump()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error building probability tree for %s: %s", assessment_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# CLAW Integration – Tool registry and dispatch
# ---------------------------------------------------------------------------

class ToolDispatchRequest(BaseModel):
    """Request body for dispatching a single registered CLAW tool."""

    name: str = Field(
        ...,
        min_length=1,
        description="Name of the registered tool to invoke (case-insensitive)",
    )
    payload: str = Field(
        default="",
        description="Optional string payload forwarded to the tool",
    )


@router.get("/tool-registry")
def list_tool_registry(
    query: Optional[str] = Query(
        default=None,
        description="Optional search string to filter tools by name or source hint",
    ),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum tools to return"),
) -> Dict[str, Any]:
    """List tools registered in the CLAW tool registry.

    Returns the tool surface loaded from ``claw_integration/reference_data/tools_snapshot.json``.
    Optionally filter by a search *query* (matched against name and source_hint).

    Returns:
        Dict with ``tools`` list and ``total`` count.
    """
    try:
        from app.claw_integration.tools import find_tools, tool_names, PORTED_TOOLS

        if query:
            modules = find_tools(query, limit=limit)
        else:
            modules = list(PORTED_TOOLS[:limit])

        return {
            "tools": [
                {
                    "name": m.name,
                    "responsibility": m.responsibility,
                    "source_hint": m.source_hint,
                    "status": m.status,
                }
                for m in modules
            ],
            "total": len(modules),
            "registry_size": len(PORTED_TOOLS),
        }
    except Exception as exc:
        logger.error("Tool registry listing error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/dispatch-tool")
def dispatch_tool(request: ToolDispatchRequest) -> Dict[str, Any]:
    """Execute a registered CLAW tool by name.

    Looks up the tool in the CLAW registry and returns a
    :class:`~app.claw_integration.tools.ToolExecution` result.
    The tool is *mirrored* – it records the invocation and returns metadata;
    actual backend operations should be performed through the dedicated API
    endpoints.

    Request body::

        {"name": "KnowledgeGraphTool", "payload": "list entities"}

    Returns:
        Dict with ``name``, ``source_hint``, ``handled``, and ``message``.
    """
    try:
        from app.claw_integration.tools import execute_tool
        from app.claw_integration.task import PortingTask

        task = PortingTask(
            name=f"dispatch:{request.name}",
            description=f"Dispatch tool '{request.name}' with payload: {request.payload!r}",
        )
        task.start()

        result = execute_tool(name=request.name, payload=request.payload)

        if result.handled:
            task.complete()
        else:
            task.fail(reason=result.message)

        return {
            "name": result.name,
            "source_hint": result.source_hint,
            "payload": result.payload,
            "handled": result.handled,
            "message": result.message,
            "task_status": task.status,
        }
    except Exception as exc:
        logger.error("Tool dispatch error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
