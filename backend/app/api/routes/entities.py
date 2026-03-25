"""
Entity extraction API routes.

Endpoints:
  POST /entities/extract/three-layer  – extract with three-layer ontological labels
  POST /entities/extract/to-graph     – extract and add results to knowledge graph
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/entities", tags=["entities"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ExtractionRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=50000, description="News article text")
    include_context: bool = Field(False, description="Include narrative context in response")


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------

def _get_llm_service() -> Any:
    """Return a configured LLM service, falling back to a stub when unavailable."""
    try:
        from app.core.config import get_settings
        settings = get_settings()
        if not getattr(settings, "llm_enabled", False):
            raise RuntimeError("LLM not enabled")
        # Re-use the same LLM bridge already used by SacredSwordAnalyzer
        return _LLMServiceAdapter(settings)
    except Exception:  # noqa: BLE001
        return _StubLLMService()


class _LLMServiceAdapter:
    """Thin adapter so EntityExtractionEngine can call the existing LLM helpers."""

    def __init__(self, settings: Any) -> None:
        self._settings = settings

    def call(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        response_format: str = "json",
    ) -> str:
        from intelligence.sacred_sword_analyzer import SacredSwordAnalyzer
        analyzer = SacredSwordAnalyzer(settings=self._settings)
        result = analyzer._llm_call(prompt, temperature=temperature)
        return result or "[]"


class _StubLLMService:
    """No-op LLM service used when no provider is configured."""

    def call(self, **_kwargs: Any) -> str:  # noqa: ANN401
        return "[]"


def _get_graph_service() -> Any:
    """Return a graph service stub (real implementation would connect to the graph DB)."""
    return _StubGraphService()


class _StubGraphService:
    def add_node(self, node: Dict[str, Any]) -> None:
        logger.debug("Graph stub: add_node %s", node.get("id"))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/extract/three-layer")
def extract_entities_three_layer(request: ExtractionRequest) -> Dict[str, Any]:
    """Extract entities with three-layer ontological labelling.

    Three Layers:
    1. Physical Type: WHAT entity IS (PERSON, COUNTRY, etc.)
    2. Structural Role: HOW it functions (AGGRESSOR, PIVOT, etc.)
    3. Virtue/Vice: WHAT it represents (DECEPTIVE, RESILIENT, etc.)

    Example response entity::

        {
          "name": "Iran",
          "layer1": {"value": "COUNTRY", "description": "Geopolitical state"},
          "layer2": {"roles": ["CATALYST", "AGGRESSOR"], ...},
          "layer3": {"virtues": ["DECEPTIVE", "RESILIENT"], ...},
          "confidence": 0.92
        }
    """
    try:
        from intelligence.entity_extraction import EntityExtractionEngine

        llm_service = _get_llm_service()
        extractor = EntityExtractionEngine(llm_service)

        request_id = f"extract_{datetime.now(timezone.utc).timestamp()}"
        entities = extractor.extract(request.text, request_id)

        return {
            "status": "success",
            "count": len(entities),
            "request_id": request_id,
            "entities": [e.to_dict() for e in entities],
        }

    except Exception as exc:  # noqa: BLE001
        logger.error("three-layer extraction failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/extract/to-graph")
def extract_and_add_to_graph(request: ExtractionRequest) -> Dict[str, Any]:
    """Extract entities with three-layer labels and add them to the knowledge graph."""
    try:
        from intelligence.entity_extraction import EntityExtractionEngine

        llm_service = _get_llm_service()
        graph_service = _get_graph_service()
        extractor = EntityExtractionEngine(llm_service)

        request_id = f"extract_graph_{datetime.now(timezone.utc).timestamp()}"
        entities = extractor.extract(request.text, request_id)

        for entity in entities:
            graph_service.add_node(entity.to_graph_node())

        return {
            "status": "success",
            "extracted": len(entities),
            "added_to_graph": len(entities),
            "request_id": request_id,
        }

    except Exception as exc:  # noqa: BLE001
        logger.error("extract-to-graph failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
