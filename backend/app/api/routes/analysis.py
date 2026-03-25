"""
Sacred Sword Analyzer API routes.

Endpoints:
  POST /analysis/sacred-sword      – run the 4-step ontological analysis
  POST /analysis/grounded/deduce   – activate Deduction Soul for strict
                                     ontology-grounded scenario inference
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


# ---------------------------------------------------------------------------
# Request model – Deduction Soul
# ---------------------------------------------------------------------------

class OntologyGroundedAnalysisRequest(BaseModel):
    """Request for ontology-grounded analysis with Deduction Soul."""
    news_fragment: str
    seed_entities: List[str]
    claim: str
    extract_paths: bool = True


# ---------------------------------------------------------------------------
# Helpers – Deduction Soul
# ---------------------------------------------------------------------------

def _get_llm_service_for_deduction() -> Any:
    """Return a configured LLM service, falling back to a stub."""
    _ensure_intelligence_importable()
    try:
        from app.core.config import get_settings
        settings = get_settings()
        if not getattr(settings, "llm_enabled", False):
            raise RuntimeError("LLM not enabled")
        from intelligence.sacred_sword_analyzer import SacredSwordAnalyzer

        class _Adapter:
            def __init__(self, cfg: Any) -> None:
                self._analyzer = SacredSwordAnalyzer(settings=cfg)

            def call(
                self,
                prompt: str,
                system: str = "",  # noqa: ARG002
                temperature: float = 0.2,
                max_tokens: int = 1500,  # noqa: ARG002
                response_format: str = "json",  # noqa: ARG002
            ) -> str:
                result = self._analyzer.llm_call(prompt, temperature=temperature)
                return result or "{}"

        return _Adapter(settings)
    except Exception:  # noqa: BLE001
        class _Stub:
            def call(self, **_kwargs: Any) -> str:  # noqa: ANN401
                return "{}"
        return _Stub()


# ---------------------------------------------------------------------------
# Route – Deduction Soul
# ---------------------------------------------------------------------------

@router.post("/grounded/deduce")
def analyze_with_deduction_soul(
    request: OntologyGroundedAnalysisRequest,
) -> Dict[str, Any]:
    """【推演灵魂激活】Analyze news with strict ontological deduction.

    LLM is forced to:
    1. Base all predictions on explicit ontological paths
    2. Trace every inference to specific relationships
    3. Output strict JSON with causal chains
    4. Never invent—only deduce

    Request body::

        {
            "news_fragment": "The European Commission announced strict AI regulations...",
            "seed_entities": ["European Commission", "AI Regulation", "EU"],
            "claim": "What will be the impact on tech companies?"
        }

    Response::

        {
            "status": "success",
            "ontological_grounding": {...},
            "deduction_result": {
                "driving_factor": "...",
                "scenario_alpha": {...},
                "scenario_beta": {...},
                "verification_gap": "...",
                "confidence": 0.85
            },
            "timestamp": "..."
        }
    """
    try:
        _ensure_intelligence_importable()
        from intelligence.grounded_analyzer import OntologyGroundedAnalyzer

        llm_service = _get_llm_service_for_deduction()
        analyzer = OntologyGroundedAnalyzer(
            llm_service=llm_service,
            kuzu_conn=None,  # KuzuDB connection is optional; None triggers fallback paths
        )

        result = analyzer.analyze_with_ontological_grounding(
            news_fragment=request.news_fragment,
            seed_entities=request.seed_entities,
            claim=request.claim,
        )
        return result

    except Exception as exc:
        logger.exception("Deduction Soul analysis failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
