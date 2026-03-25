"""
Sacred Sword Analyzer API routes.

Endpoint:
  POST /analysis/sacred-sword  – run the 4-step ontological analysis
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"])


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

class AnalysisRequest(BaseModel):
    news_fragments: List[str]  # Raw news snippets
    graph_context: Dict[str, Any]  # Current entities & relations
    claim: str                 # Claim to analyze


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_intelligence_importable() -> None:
    """Add the backend directory to sys.path so intelligence is importable."""
    here = os.path.abspath(__file__)
    backend_dir = os.path.dirname(  # backend/
        os.path.dirname(  # app/
            os.path.dirname(  # api/
                os.path.dirname(here)  # routes/
            )
        )
    )
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)


def _get_analyzer():
    """Return a SacredSwordAnalyzer instance using the app settings."""
    _ensure_intelligence_importable()
    from intelligence.sacred_sword_analyzer import SacredSwordAnalyzer
    try:
        from app.core.config import get_settings
        settings = get_settings()
    except ImportError:
        settings = None
    return SacredSwordAnalyzer(settings=settings)


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("/sacred-sword")
def sacred_sword_analysis(request: AnalysisRequest) -> Dict[str, Any]:
    """Execute Sacred Sword Analyzer protocol.

    Input:
    - news_fragments: List of raw news text
    - graph_context:  Current knowledge graph state
    - claim:          Statement to analyze

    Output:
    - Full SacredSwordAnalysis with 4 steps
    """
    try:
        analyzer = _get_analyzer()
        result = analyzer.analyze(
            news_fragments=request.news_fragments,
            graph_context=request.graph_context,
            claim=request.claim,
        )
        return {
            "status": "success",
            "analysis": {
                "facts": [
                    {
                        "statement": f.statement,
                        "source": f.source,
                        "confidence": f.confidence,
                    }
                    for f in result.facts
                ],
                "conflict": result.conflict.value,
                "alpha": {
                    "name": result.alpha.name,
                    "description": result.alpha.description,
                    "probability": result.alpha.probability,
                    "key_assumption": result.alpha.key_assumption,
                },
                "beta": {
                    "name": result.beta.name,
                    "description": result.beta.description,
                    "probability": result.beta.probability,
                    "key_assumption": result.beta.key_assumption,
                },
                "confidence_score": result.confidence_score,
                "data_gap": result.data_gap,
                "counter_arg": result.counter_arg,
            },
        }
    except Exception as exc:
        logger.exception("Sacred Sword analysis failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
