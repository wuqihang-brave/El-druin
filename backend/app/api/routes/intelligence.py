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


@router.get("/probability-tree-for-assessment/{assessment_id}")
def get_probability_tree_for_assessment(assessment_id: str) -> Dict[str, Any]:
    """Build or retrieve a probability tree keyed by assessment ID.

    Uses the assessment's ``analyst_notes`` as source text.  The tree is
    stored with ``assessment_id`` as the ``report_id`` so repeated requests
    return the cached result without rebuilding.

    Args:
        assessment_id: The assessment's stable identifier (e.g. "ae-204").

    Returns:
        Serialised ``ProbabilityTree`` dict.  Returns ``is_phase_transition``,
        ``step_t``, ``prime_p``, and ``interpretation_branches`` fields that
        the frontend uses for the p-adic confidence panel.
    """
    _ensure_intelligence_importable()
    builder = _get_builder()

    # Return cached tree if already built for this assessment
    existing = builder.get_tree(assessment_id)
    if existing is not None:
        return existing.model_dump()

    # Load assessment text from store
    try:
        from app.core.assessment_store import assessment_store  # noqa: PLC0415
        assessment = assessment_store.get_assessment(assessment_id)
    except Exception as exc:
        logger.warning("Could not load assessment %s: %s", assessment_id, exc)
        assessment = None

    if assessment is None:
        raise HTTPException(
            status_code=404,
            detail=f"Assessment {assessment_id!r} not found",
        )

    source_text = assessment.analyst_notes or assessment.title or ""
    source_reliability = {
        "High": 0.85,
        "Medium": 0.65,
        "Low": 0.40,
    }.get(str(assessment.last_confidence), 0.60)

    try:
        tree = builder.build_tree(
            text=source_text,
            source_reliability=source_reliability,
            report_id=assessment_id,
        )
        builder.store_tree(tree)
        return tree.model_dump()
    except Exception as exc:
        logger.error(
            "Failed to build probability tree for assessment %s: %s",
            assessment_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc



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
