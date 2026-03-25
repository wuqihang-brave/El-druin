"""
Sacred Sword Analyzer API routes.

Endpoints:
  POST /analysis/sacred-sword              – run the 4-step ontological analysis
  POST /analysis/grounded/analyze          – ontology-grounded news analysis
  GET  /analysis/ontological-context/{entity_name} – 1-hop + 2-hop KG paths
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, List, Optional

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


class OntologyGroundedAnalysisRequest(BaseModel):
    """Request body for ontology-grounded news analysis."""

    news_fragment: str
    seed_entities: List[str]
    claim: str
    extract_paths: bool = True


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
# Kuzu connection helper
# ---------------------------------------------------------------------------

def _get_kuzu_connection() -> Any:
    """Return a KuzuDB connection, falling back gracefully when unavailable."""
    _ensure_intelligence_importable()
    try:
        import kuzu  # type: ignore

        # Use the configured DB path when available; otherwise a default path.
        try:
            from app.core.config import get_settings
            settings = get_settings()
            db_path = getattr(settings, "kuzu_db_path", None) or "./data/el_druin.kuzu"
        except Exception:  # noqa: BLE001
            db_path = "./data/el_druin.kuzu"

        db = kuzu.Database(db_path)
        return kuzu.Connection(db)
    except Exception as exc:  # noqa: BLE001
        logger.warning("KuzuDB connection unavailable: %s", exc)
        raise


def _get_llm_service() -> Any:
    """Return an LLM service adapter, falling back to a stub when unavailable."""
    _ensure_intelligence_importable()
    try:
        from app.core.config import get_settings
        settings = get_settings()
        if not getattr(settings, "llm_enabled", False):
            raise RuntimeError("LLM not enabled")
        return _LLMServiceAdapter(settings)
    except Exception:  # noqa: BLE001
        return _StubLLMService()


class _LLMServiceAdapter:
    def __init__(self, settings: Any) -> None:
        self._settings = settings

    def call(self, prompt: str, temperature: float = 0.3, max_tokens: int = 1000, **_: Any) -> str:
        from intelligence.sacred_sword_analyzer import SacredSwordAnalyzer
        analyzer = SacredSwordAnalyzer(settings=self._settings)
        return analyzer._llm_call(prompt, temperature=temperature) or ""


class _StubLLMService:
    def call(self, prompt: str, **_: Any) -> str:  # noqa: ANN401
        return "[LLM not configured – ontological context extracted successfully]"


# ---------------------------------------------------------------------------
# Ontology-grounded routes
# ---------------------------------------------------------------------------

@router.post("/grounded/analyze")
def analyze_with_ontological_grounding(
    request: OntologyGroundedAnalysisRequest,
) -> Dict[str, Any]:
    """Analyze news grounded in knowledge graph ontology.

    Ensures LLM reasoning is based on actual knowledge graph structure
    (1-hop + 2-hop relationship paths) rather than raw text alone.

    Input:
    - news_fragment:  Raw news text
    - seed_entities:  List of entity names to ground the analysis on
    - claim:          Statement to evaluate
    - extract_paths:  Whether to extract KG paths (default: true)

    Output:
    - Ontological grounding metadata + LLM grounded analysis
    """
    try:
        _ensure_intelligence_importable()
        kuzu_conn = _get_kuzu_connection()
        llm_service = _get_llm_service()

        from intelligence.grounded_analyzer import OntologyGroundedAnalyzer

        analyzer = OntologyGroundedAnalyzer(
            llm_service=llm_service,
            kuzu_conn=kuzu_conn,
        )
        return analyzer.analyze_with_ontological_grounding(
            news_fragment=request.news_fragment,
            seed_entities=request.seed_entities,
            claim=request.claim,
        )
    except Exception as exc:
        logger.exception("Ontology-grounded analysis failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/ontological-context/{entity_name}")
def get_entity_ontological_context(entity_name: str) -> Dict[str, Any]:
    """Get ontological context (1-hop + 2-hop KG paths) for an entity.

    Returns the relationship paths from the knowledge graph that ground
    downstream LLM reasoning about this entity.
    """
    try:
        _ensure_intelligence_importable()
        kuzu_conn = _get_kuzu_connection()

        from ontology.kuzu_context_extractor import get_ontological_context

        context = get_ontological_context(kuzu_conn, entity_name)
        return {
            "status": "success",
            "entity": entity_name,
            "ontological_context": context,
        }
    except Exception as exc:
        logger.exception("Ontological context retrieval failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
