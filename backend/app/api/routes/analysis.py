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
    """Return a KuzuDB connection resolved to an absolute physical path.

    Priority: KUZU_DB_PATH env > settings.kuzu_db_path > project-root fallback.
    Always resolves to an absolute path so that scripts and the server share
    the same physical file regardless of working directory.
    """
    _ensure_intelligence_importable()

    # Step 1: env var (may be relative – resolve it)
    db_path: Optional[str] = os.getenv("KUZU_DB_PATH")

    # Step 2: settings (already absolute after config.py fix)
    if not db_path:
        try:
            from app.core.config import get_settings
            db_path = getattr(get_settings(), "kuzu_db_path", None)
        except (ImportError, AttributeError) as exc:
            logger.debug("kuzu_db_path from settings failed: %s", exc)

    # Step 3: derive from this file's location (backend/app/api/routes/analysis.py)
    if not db_path:
        _here = os.path.abspath(__file__)
        # 5 dirname calls: file → routes/ → api/ → app/ → backend/ → project root
        _project_root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(_here))
        )))
        db_path = os.path.join(_project_root, "data", "el_druin.kuzu")

    # Always resolve to an absolute path so CWD does not affect which file is opened
    db_path = os.path.abspath(db_path)

    logger.info("KuzuDB physical path resolved to: %s", db_path)

    if not os.path.exists(db_path):
        logger.warning(
            "KuzuDB path does not exist: %s – "
            "run checkg.py or kg_init_tools.py to initialise the graph store",
            db_path,
        )
        return None

    try:
        import kuzu
        db = kuzu.Database(db_path)
        conn = kuzu.Connection(db)
        logger.info("KuzuDB connection opened at: %s", db_path)
        return conn
    except Exception as exc:
        logger.warning("KuzuDB connect failed (path=%s): %s", db_path, exc)
        return None


def _cot_deduction_from_text(
    news_fragment: str,
    seed_entities: List[str],
    llm_service: Any,
) -> Dict[str, Any]:
    """
    Chain-of-Thought 兜底推演（当图谱路径为 0 时调用）。

    参考 om_database_matching.py 的推理模板思路：
    - 先让 LLM 识别事件领域（类比 OM 的 ontology alignment check）
    - 再基于领域框架做结构化推演
    - 显式标注 "无图谱路径，CoT 推演" 以区分置信度

    不同于盲目猜测：CoT 要求 LLM 显式写出推演步骤，
    每步都必须引用原文片段，不允许凭空发挥。
    """
    entities_str = ", ".join(seed_entities[:8]) if seed_entities else "（未指定）"

    cot_prompt = f"""
你是一名情报分析官，正在对以下新闻进行结构化推演分析。
【注意】当前知识图谱中没有该事件的直接关系路径，
你必须完全基于原文进行推演，每步推演都必须引用原文证据。

【新闻原文】
{news_fragment}

【已识别实体】
{entities_str}

【Chain-of-Thought 推演步骤（必须按以下格式完成）】

Step 1 - 领域识别：
  这条新闻属于哪个领域？（体育/商业/地缘政治/经济/科技/社会/军事）
  原文证据：引用原文关键词

Step 2 - 核心矛盾/驱动因素：
  事件的核心驱动力是什么？哪个实体在驱动变化？
  原文证据：引用原文句子

Step 3 - Alpha 路径（最可能演化）：
  如果当前驱动因素继续，最可能发生什么？
  4步因果链：[事实] --> [机制] --> [中间效应] --> [最终后果]
  原文支撑：...

Step 4 - Beta 路径（结构性断裂）：
  如果 Alpha 路径的关键节点失效，会发生什么？
  触发条件：...

Step 5 - 数据缺口：
  推演中最关键的不确定信息是什么？

完成以上步骤后，返回严格 JSON：
{{
  "domain": "领域名称",
  "driving_factor": "核心驱动力（引用原文实体）",
  "scenario_alpha": {{
    "name": "路径名称",
    "probability": 0.4-0.65,
    "causal_chain": "A --> [机制] --> B --> C",
    "description": "一句话描述"
  }},
  "scenario_beta": {{
    "name": "路径名称",
    "probability": 0.1-0.35,
    "causal_chain": "A --> [机制] --> B --> C",
    "trigger_condition": "触发条件",
    "description": "一句话描述"
  }},
  "confidence": 0.3-0.55,
  "graph_evidence": "无图谱路径，CoT 基于原文推演",
  "verification_gap": "最关键的数据缺口"
}}

只输出 JSON，不加任何说明。
"""
    try:
        response = llm_service.call(
            prompt=cot_prompt,
            system=(
                "你是严谨的情报分析官。严格按照 Chain-of-Thought 步骤推演，"
                "每步必须引用原文证据。无图谱路径时 confidence 不得超过 0.55。"
            ),
            temperature=0.2,
            max_tokens=1500,
            response_format="json",
        )
        import re, json as _json
        if isinstance(response, dict):
            return response
        text = str(response).strip()
        # 提取 JSON
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            text = text[start: end + 1]
        result = _json.loads(text)
        # 强制限制置信度（CoT 无图谱路径）
        result["confidence"] = min(float(result.get("confidence", 0.45)), 0.55)
        result["graph_evidence"] = "无图谱路径，CoT 基于原文推演"
        return result
    except Exception as exc:
        logger.error("CoT deduction failed: %s", exc)
        return {
            "driving_factor": f"基于原文推演：{news_fragment[:80]}",
            "scenario_alpha": {
                "name": "现状延续路径",
                "probability": 0.55,
                "causal_chain": f"{news_fragment[:60]} --> [事件演化] --> 相关实体调整 --> 格局渐变",
                "description": "CoT 兜底推演",
            },
            "scenario_beta": {
                "name": "结构性断裂路径",
                "probability": 0.25,
                "causal_chain": f"{news_fragment[:60]} --> [关键节点失效] --> 极端博弈 --> 格局重组",
                "trigger_condition": "关键依赖节点被外部冲击打断",
                "description": "CoT 兜底推演（黑天鹅）",
            },
            "confidence": 0.35,
            "graph_evidence": "无图谱路径，CoT 兜底",
            "verification_gap": "需要更多原文细节和图谱路径支撑",
        }


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


def _write_extracted_entities_to_kg(entity_names: List[str]) -> int:
    """Write extracted entities into the shared KG so future queries find them.

    Returns the number of entities successfully written.
    Each entity is written as type "Entity" (generic) so the context extractor
    can find them with MATCH (a:Entity {name: ...}).
    """
    if not entity_names:
        return 0
    try:
        from app.knowledge.graph_store import GraphStore
        from app.core.config import get_settings
        settings = get_settings()
        db_path = settings.kuzu_db_path
        logger.info("Auto-writing %d extracted entities to KG at: %s", len(entity_names), db_path)
        store = GraphStore()
        count = 0
        for name in entity_names:
            if name:
                store.add_entity(name, "Entity")
                count += 1
        logger.info("Auto-write complete: %d entities written to KG", count)
        return count
    except Exception as exc:
        logger.warning("Auto-write entities to KG failed: %s", exc)
        return 0


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

        # ===== Step 1b: 自动将抽取实体写入KG（保证下次查询可找到）=====
        if effective_entities:
            written = _write_extracted_entities_to_kg(effective_entities)
            logger.info("Auto-wrote %d entities to KG before context extraction", written)

        # ===== Step 2: 获取本体路径 =====
        from ontology.kuzu_context_extractor import KuzuContextExtractor, get_ontological_context
        extracted_graph_context = []
        if kuzu_conn is None:
            logger.warning(
                "⚠️ KuzuDB connection is None – all entities will return 0 paths. "
                "Check that the DB file exists (run kg_init_tools.py to initialise)."
            )
        for entity in effective_entities:
            if kuzu_conn is None:
                extracted_graph_context.append(
                    f"\n【本体路径上下文】\n中心实体: {entity} (UNKNOWN)\n"
                    "⚠️ 数据库连接不可用，无法查询路径\n"
                )
                continue
            ctx = get_ontological_context(kuzu_conn, entity)
            if ctx:
                extracted_graph_context.append(ctx)

        # ===== Step 2b: 检查路径质量 =====
        # 判断是否所有实体都返回了 0 路径（"0 1-hop + 0 2-hop" 是空图谱的标志）
        non_empty_contexts = [
            c for c in extracted_graph_context
            if "0 1-hop + 0 2-hop" not in c
        ]
        has_real_graph_evidence = len(non_empty_contexts) > 0

        logger.info(
            "Graph context: %d total, %d non-empty",
            len(extracted_graph_context), len(non_empty_contexts),
        )

        # ===== Step 3: 路径为 0 时走 CoT 兜底，不进入 grounded_analyzer =====
        if not has_real_graph_evidence:
            logger.warning(
                "⚠️ 所有实体图谱路径均为 0，启动 CoT 兜底推演"
                "（参考 om_database_matching.py 推理模板）"
            )
            deduction_result = _cot_deduction_from_text(
                news_fragment=request.news_fragment,
                seed_entities=effective_entities,
                llm_service=llm_service,
            )
            return {
                "status": "success_cot_fallback",
                "ontological_grounding": {
                    "seed_entities":          effective_entities,
                    "graph_evidence":         extracted_graph_context,
                    "total_paths_extracted":  0,
                    "note": "图谱路径为 0，使用 CoT 兜底推演（置信度已限制至 ≤0.55）",
                },
                "deduction_result": deduction_result,
                "timestamp": datetime.now().isoformat(),
            }

        # ===== Step 4: 有图谱路径时走 grounded_analyzer =====
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