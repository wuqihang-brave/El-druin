"""
Sacred Sword Analyzer API routes + Ontology-Grounded Analysis Endpoints.

Endpoints:
  POST /analysis/sacred-sword              – run the 4-step ontological analysis
  POST /analysis/grounded/analyze          – ontology-grounded news analysis  
  POST /analysis/grounded/deduce           – activate Deduction Soul for strict inference
  GET  /analysis/ontological-context/{entity_name} – 1-hop + 2-hop KG paths
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import time
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"])


# ═══════════════════════════════════════════════════════════════════
# Request Models (Consolidated)
# ═══════════════════════════════════════════════════════════════════

class AnalysisRequest(BaseModel):
    """Sacred Sword Analyzer request."""
    news_fragments: List[str]
    graph_context: Dict[str, Any]
    claim: str


class OntologyGroundedAnalysisRequest(BaseModel):
    """Request for ontology-grounded analysis (both grounded/analyze and grounded/deduce)."""
    news_fragment: str
    seed_entities: List[str]
    claim: str
    extract_paths: bool = True


# ═══════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════

def _ensure_intelligence_importable() -> None:
    """Add the backend directory to sys.path."""
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
    """Return a SacredSwordAnalyzer instance."""
    _ensure_intelligence_importable()
    from intelligence.sacred_sword_analyzer import SacredSwordAnalyzer
    try:
        from app.core.config import get_settings
        settings = get_settings()
    except ImportError:
        settings = None
    return SacredSwordAnalyzer(settings=settings)


def _get_kuzu_connection() -> Any:
    """Return a KuzuDB connection to the main application database.

    Reads the database path from the ``KUZU_DB_PATH`` environment variable so
    the service works in cloud deployments (e.g. Streamlit Cloud / Railway)
    where ``./data/kuzu_db`` does not exist.  Falls back to the settings value
    and then to the hard-coded default.  Returns ``None`` – instead of raising –
    when the path does not exist or the connection fails, so callers can degrade
    gracefully.

    Priority: KUZU_DB_PATH env var > settings.kuzu_db_path > ``./data/kuzu_db``
    """
    _ensure_intelligence_importable()
    # Priority: env var > settings > hard-coded default
    kuzu_db_path_env = os.getenv("KUZU_DB_PATH")
    if kuzu_db_path_env:
        db_path = kuzu_db_path_env
    else:
        db_path = "./data/kuzu_db"
        try:
            from app.core.config import get_settings
            settings = get_settings()
            db_path = getattr(settings, "kuzu_db_path", None) or db_path
        except (ImportError, AttributeError) as exc:
            logger.debug("Could not read kuzu_db_path from settings: %s", exc)

    if not os.path.exists(db_path):
        logger.warning("KuzuDB path not found: %s – running without graph context", db_path)
        return None

    try:
        import kuzu
        logger.debug("Opening KuzuDB at path: %s", db_path)
        db = kuzu.Database(db_path)
        return kuzu.Connection(db)
    except Exception as exc:
        logger.warning("Failed to connect to KuzuDB (path=%s): %s", db_path, exc)
        return None


def _get_llm_service() -> Any:
    """Return an LLM service adapter."""
    _ensure_intelligence_importable()
    try:
        from app.core.config import get_settings
        settings = get_settings()
        if not getattr(settings, "llm_enabled", False):
            raise RuntimeError("LLM not enabled")
        
        from intelligence.sacred_sword_analyzer import SacredSwordAnalyzer
        class _LLMAdapter:
            def __init__(self, cfg: Any) -> None:
                self._analyzer = SacredSwordAnalyzer(settings=cfg)
            
            def call(
                self,
                prompt: str,
                system: str = "",
                temperature: float = 0.2,
                max_tokens: int = 1500,
                **kwargs: Any
            ) -> str:
                # 这一行缩进 1 个 Tab (或 4 个空格)
                full_prompt = f"System: {system}\n\nUser Request: {prompt}"
                
                # 这一行必须和上面的 full_prompt 对齐！
                result = self._analyzer._llm_call(
                    prompt=full_prompt, 
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                # 这一行也必须对齐！
                return result or "{}"
        return _LLMAdapter(settings)
    except Exception:
        class _StubLLM:
            def call(self, **kwargs: Any) -> str:
                return "{}"
        return _StubLLM()




# ═══════════════════════════════════════════════════════════════════
# Endpoint 1: Sacred Sword Analyzer (4-step protocol)
# ═══════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════
# Endpoint 2: Grounded Analysis (Ontology-aware LLM reasoning)
# ═══════════════════════════════════════════════════════════════════

@router.post("/grounded/analyze")
def analyze_with_ontological_grounding(
    request: OntologyGroundedAnalysisRequest,
) -> Dict[str, Any]:
    """Analyze news grounded in knowledge graph ontology.
    
    Ensures LLM reasoning is based on actual KG structure 
    (1-hop + 2-hop relationship paths).
    
    Input:
    - news_fragment:  Raw news text
    - seed_entities:  List of entity names to ground
    - claim:          Statement to evaluate
    - extract_paths:  Whether to extract KG paths
    
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





# ═══════════════════════════════════════════════════════════════════
# Endpoint 3: Deduction Soul (Ontology-Grounded)
# ═══════════════════════════════════════════════════════════════════

@router.post("/grounded/deduce")
def analyze_with_deduction_soul(
    request: OntologyGroundedAnalysisRequest,
) -> Dict[str, Any]:
    """
    严格依赖本体路径推理��并在 seed_entities 为空时自动调抽取器兜底
    """
    try:
        _ensure_intelligence_importable()
        kuzu_conn = _get_kuzu_connection()
        llm_service = _get_llm_service()

        # ===== Step 1: 兜底保证 seed_entities 非空 =====
        effective_entities = request.seed_entities

        if not effective_entities or len(effective_entities) == 0:
            logger.warning("⚠️ seed_entities 为空，自动调用实体抽取兜底")
            try:
                from intelligence.entity_extraction import EntityExtractionEngine
                extractor = EntityExtractionEngine(llm_service)
                req_id = f"deduce_{int(time.time() * 1000)}"
                extracted = extractor.extract(request.news_fragment, req_id)
                temp_seed = []
                if isinstance(extracted, list):
                    for ent in extracted:
                        if hasattr(ent, "name"):
                            temp_seed.append(ent.name)
                        elif isinstance(ent, dict) and "name" in ent:
                            temp_seed.append(ent["name"])
                else:
                    logger.error(f"抽取器返回值不是 list，而是: {type(extracted)}，内容: {repr(extracted)}")
                effective_entities = [x for x in temp_seed if x]
                logger.info(f"✅ 实体兜底生效, 得到实体: {effective_entities}")
            except Exception as exc:
                logger.exception(f"自动实体抽取失败，无法兜底: {exc}")

        # ===== Step 2: 获取本体路径 =====
        from ontology.kuzu_context_extractor import get_ontological_context
        extracted_graph_context = []
        for entity in effective_entities:
            ctx = get_ontological_context(kuzu_conn, entity)
            if ctx:
                extracted_graph_context.append(ctx)

        # ===== Step 3: 用原有流转，走 grounded_analyzer 分析器 =====
        from intelligence.grounded_analyzer import OntologyGroundedAnalyzer
        analyzer = OntologyGroundedAnalyzer(
            llm_service=llm_service,
            kuzu_conn=kuzu_conn,
        )
        raw_result = analyzer.analyze_with_ontological_grounding(
            news_fragment=request.news_fragment,
            seed_entities=effective_entities,
            claim=f"【本体关系证据】：{str(extracted_graph_context)}\n\n推演问题：{request.claim}",
        )

        deduction_result = raw_result.get("deduction_result", {})

        return {
            "status": "success",
            "ontological_grounding": {
                "seed_entities": effective_entities,
                "graph_evidence": extracted_graph_context,
                "total_paths_extracted": len(extracted_graph_context),
            },
            "deduction_result": deduction_result,
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Deduction Soul analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))

# Endpoint 4: Get Ontological Context


@router.get("/ontological-context/{entity_name}")
def get_entity_ontological_context(entity_name: str) -> Dict[str, Any]:
    """Get ontological context (1-hop + 2-hop KG paths) for an entity.
    
    Returns relationship paths from the knowledge graph that ground
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
