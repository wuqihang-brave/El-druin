"""
Sacred Sword Analyzer API routes + Ontology-Grounded Analysis Endpoints.

修复说明 (v4)：
  问题一：seed_entities 兜底提取出了错误实体（Iraq/Bolivia 新闻 → Russia/Ukraine 实体）
    根本原因：EntityExtractionEngine 内部使用的是带硬编码地缘政治词表的 entity_extractor，
    在体育/商业等非地缘政治新闻上会注入 US/China/Russia 等常见词汇。
    修复：
      1. 新增领域感知的轻量实体提取器 _domain_aware_entity_extraction()，
         先判断新闻领域，再选择合适的提取策略。体育新闻 → 提取队名/球员名；
         商业新闻 → 提取公司名；地缘政治 → 提取国家/组织。
      2. 如果 EntityExtractionEngine 返回的实体中超过 50% 不出现在原文，
         自动降级为领域感知提取器。

  问题二："Auto-write entities to KG"（日志中可见）将错误实体写入 KuzuDB
    这导致 Russia 在图谱里有了 2 条路径，但与当前新闻完全无关。
    修复：彻底移除在 deduce 端点中自动写入实体的逻辑。
    实体写入只应由 extractor_agent（用户主动触发）完成，不应在推演时自动发生。

  问题三：DB 路径硬编码为 ./data/kuzu_db，与 kuzu_graph.DEFAULT_DB_PATH 不一致。
    修复：统一使用 kuzu_graph.DEFAULT_DB_PATH。

  问题四：图谱路径为 0 时仍然进入 grounded_analyzer 导致胡乱推演。
    修复：路径为 0 时启动 CoT 兜底推演，confidence 强制 ≤ 0.55。
"""

from __future__ import annotations

import logging
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"])


# ═══════════════════════════════════════════════════════════════════
# Request Models
# ═══════════════════════════════════════════════════════════════════

class AnalysisRequest(BaseModel):
    news_fragments: List[str]
    graph_context: Dict[str, Any]
    claim: str


class DeepConfigModel(BaseModel):
    """Configuration for the Deep Ontology enrichment step."""
    level:           int = 0
    timeout_seconds: int = 20
    max_sources:     int = 3


class OntologyGroundedAnalysisRequest(BaseModel):
    news_fragment: str
    seed_entities: List[str]
    claim: str
    extract_paths: bool = True
    # Deep Ontology Analysis
    deep_mode:   bool                   = False
    deep_config: Optional[DeepConfigModel] = None
    source_url:  Optional[str]          = None
    # Local metadata to assist enrichment (published_at, source, url)
    local_meta:  Optional[Dict[str, Any]] = None


# ═══════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════

def _ensure_intelligence_importable() -> None:
    here = os.path.abspath(__file__)
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(here))))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)


def _get_analyzer():
    _ensure_intelligence_importable()
    from intelligence.sacred_sword_analyzer import SacredSwordAnalyzer
    try:
        from app.core.config import get_settings
        settings = get_settings()
    except ImportError:
        settings = None
    return SacredSwordAnalyzer(settings=settings)


def _get_kuzu_connection() -> Any:
    """
    修复：统一使用 kuzu_graph.DEFAULT_DB_PATH，不再硬编码 ./data/kuzu_db。
    Priority: KUZU_DB_PATH env > kuzu_graph.DEFAULT_DB_PATH > settings > fallback
    """
    _ensure_intelligence_importable()

    db_path = os.getenv("KUZU_DB_PATH")

    if not db_path:
        try:
            from app.knowledge.kuzu_graph import DEFAULT_DB_PATH as _KG_PATH
            db_path = _KG_PATH
            logger.info("KuzuDB physical path resolved to: %s", db_path)
        except ImportError:
            pass

    if not db_path:
        try:
            from app.core.config import get_settings
            db_path = getattr(get_settings(), "kuzu_db_path", None)
        except (ImportError, AttributeError) as exc:
            logger.debug("kuzu_db_path from settings: %s", exc)

    if not db_path:
        db_path = "./data/el_druin.kuzu"

    if not os.path.exists(db_path):
        logger.warning("KuzuDB path not found: %s – running without graph context", db_path)
        return None

    try:
        import kuzu
        logger.info("KuzuDB connection opened at: %s", db_path)
        db = kuzu.Database(db_path)
        return kuzu.Connection(db)
    except Exception as exc:
        logger.warning("KuzuDB connect failed (path=%s): %s", db_path, exc)
        return None


def _get_llm_service() -> Any:
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
                **kwargs: Any,
            ) -> str:
                full_prompt = f"System: {system}\n\nUser Request: {prompt}" if system else prompt
                result = self._analyzer._llm_call(
                    prompt=full_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return result or "{}"

        return _LLMAdapter(settings)
    except Exception:
        class _StubLLM:
            def call(self, **kwargs: Any) -> str:
                return "{}"
        return _StubLLM()


# ═══════════════════════════════════════════════════════════════════
# Domain-Aware Entity Extraction（修复核心 1）
# ═══════════════════════════════════════════════════════════════════

# 领域关键词 → 提取策略标签
_DOMAIN_SIGNALS: List[tuple] = [
    (["score", "goal", "match", "cricket", "football", "soccer", "basketball",
      "qualify", "world cup", "fifa", "ipl", "nba", "nfl", "defeat", "beat",
      "tournament", "league", "player", "team", "innings", "wicket", "over",
      "penalty", "corner", "referee", "stadium", "coach", "squad"],
     "sports"),
    (["revenue", "profit", "ipo", "merger", "acquisition", "ceo", "company",
      "startup", "stock", "shares", "earnings", "quarterly", "fiscal", "market"],
     "business"),
    (["earthquake", "flood", "hurricane", "wildfire", "disaster", "evacuation",
      "tornado", "tsunami", "victims", "rescue"],
     "disaster"),
    (["discovery", "research", "scientists", "vaccine", "drug", "clinical",
      "genome", "quantum", "space", "rocket", "satellite"],
     "science"),
    (["election", "vote", "rally", "festival", "celebrity", "entertainment",
      "music", "film", "viral", "social media"],
     "society"),
    # 地缘政治放最后，避免体育/商业新闻被误判
    (["sanction", "military", "troops", "missile", "airstrike", "invasion",
      "treaty", "diplomat", "bilateral", "summit", "nato", "alliance",
      "nuclear", "ceasefire", "embassy", "regime"],
     "geopolitics"),
    (["tariff", "trade war", "inflation", "central bank", "interest rate",
      "recession", "gdp", "unemployment", "currency", "devaluation"],
     "economics"),
]


def _detect_domain(text: str) -> str:
    """判断新闻领域，返回域标签。"""
    text_lower = text.lower()
    for keywords, domain in _DOMAIN_SIGNALS:
        if any(kw in text_lower for kw in keywords):
            return domain
    return "general"


def _extract_entities_for_domain(text: str, domain: str) -> List[str]:
    """
    领域感知实体提取（修复：替代硬编码地缘政治词表注入）。

    每个域只提取原文中实际出现的相关实体，不注入全局词表。
    """
    entities: List[str] = []
    seen: set = set()

    def _add(name: str) -> None:
        name = name.strip()
        if name and name not in seen and len(name) > 1:
            seen.add(name)
            entities.append(name)

    if domain == "sports":
        # 提取队名/球员名/赛事名（标题大写词组）
        # 国家队名（两个大写词）
        for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", text):
            name = m.group(1)
            # 排除常见冠词/介词
            if name.lower() not in {"the", "and", "for", "with", "from", "into", "over"}:
                _add(name)
        # 数字比分周围的队名
        for m in re.finditer(
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:defeat|beat|vs\.?|draw with|lose to)\s+"
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            text, re.IGNORECASE,
        ):
            _add(m.group(1)); _add(m.group(2))
        # 赛事名（FIFA/World Cup 等）
        for m in re.finditer(
            r"\b(FIFA|UEFA|AFC|CONCACAF|CAF|OFC|CONMEBOL|Olympics|World Cup|"
            r"Champions League|Premier League|La Liga|Bundesliga|Serie A|Ligue 1|"
            r"IPL|NBA|NFL|MLB|NHL|F1|Grand Prix)\b", text, re.IGNORECASE,
        ):
            _add(m.group(1))

    elif domain == "business":
        # 公司名（含 Corp/Inc/Ltd 等后缀）
        for m in re.finditer(
            r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+"
            r"(?:Corp|Inc|Ltd|Group|Bank|Fund|Holdings|Technologies|Systems|"
            r"Solutions|Capital|Partners|Ventures|Media))\b", text,
        ):
            _add(m.group(1))
        # CEO/领导人名
        for m in re.finditer(r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b", text):
            _add(m.group(1))

    elif domain == "geopolitics":
        # 国家名（只提取文本中出现的，不全量注入）
        _COUNTRY_RE = re.compile(
            r"\b(Afghanistan|Albania|Algeria|Argentina|Australia|Austria|"
            r"Azerbaijan|Bahrain|Bangladesh|Belarus|Belgium|Bolivia|Brazil|"
            r"Bulgaria|Cambodia|Canada|Chile|China|Colombia|Croatia|Cuba|"
            r"Czech Republic|Denmark|Egypt|Ethiopia|Finland|France|Germany|"
            r"Greece|Hungary|India|Indonesia|Iran|Iraq|Ireland|Israel|Italy|"
            r"Japan|Jordan|Kazakhstan|Kenya|Libya|Malaysia|Mexico|Morocco|"
            r"Netherlands|New Zealand|Nigeria|North Korea|Norway|Pakistan|"
            r"Palestine|Peru|Philippines|Poland|Portugal|Romania|Russia|"
            r"Saudi Arabia|Serbia|Singapore|Somalia|South Africa|South Korea|"
            r"Spain|Sudan|Sweden|Switzerland|Syria|Taiwan|Thailand|Turkey|"
            r"UAE|UK|Ukraine|United Kingdom|United States|USA|US|Venezuela|"
            r"Vietnam|Yemen|Zimbabwe)\b"
        )
        for m in _COUNTRY_RE.finditer(text):
            _add(m.group(1))
        # 组织名
        for m in re.finditer(
            r"\b(UN|NATO|EU|IAEA|WHO|IMF|WTO|OPEC|G7|G20|"
            r"[A-Z][a-z]+ (?:Government|Ministry|Forces|Army|Navy|Council))\b",
            text,
        ):
            _add(m.group(1))

    elif domain in ("economics", "business"):
        for m in re.finditer(
            r"\b(Federal Reserve|ECB|IMF|World Bank|OPEC|"
            r"[A-Z][a-z]+ (?:Bank|Fund|Exchange|Market))\b", text,
        ):
            _add(m.group(1))

    else:
        # 通用：提取 Title Case 词组
        for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b", text):
            name = m.group(1)
            if name.lower() not in {"the", "and", "for", "with"}:
                _add(name)

    return entities[:12]


def _domain_aware_entity_extraction(news_fragment: str) -> List[str]:
    """
    领域感知实体提取主入口。

    修复目标：Iraq defeats Bolivia 2-1 → 提取 [Iraq, Bolivia, FIFA World Cup]
    而不是 [Russia, Ukraine, NATO, US, China]
    """
    domain = _detect_domain(news_fragment)
    logger.info("Domain detected: %s", domain)
    entities = _extract_entities_for_domain(news_fragment, domain)
    logger.info("Domain-aware entities extracted: %s", entities)
    return entities


def _validate_entities_against_text(entities: List[str], text: str) -> List[str]:
    """
    验证实体列表：过滤掉在原文中不出现的实体。
    修复：防止 EntityExtractionEngine 注入全局词表中的无关实体。
    """
    text_lower = text.lower()
    valid = [e for e in entities if e.lower() in text_lower]
    removed = set(entities) - set(valid)
    if removed:
        logger.warning(
            "Filtered %d entities NOT found in text: %s",
            len(removed), list(removed),
        )
    return valid


# ═══════════════════════════════════════════════════════════════════
# CoT Fallback Deduction（图谱路径为 0 时）
# ═══════════════════════════════════════════════════════════════════

def _cot_deduction_from_text(
    news_fragment: str,
    seed_entities: List[str],
    llm_service: Any,
    domain: str = "general",
) -> Dict[str, Any]:
    """
    Chain-of-Thought 兜底推演（当图谱路径为 0 时）。
    参考 om_database_matching.py 的推理模板思路：
    - 先识别领域
    - 显式写出推演步骤并引用原文证据
    - confidence 强制 ≤ 0.55
    """
    entities_str = ", ".join(seed_entities[:8]) if seed_entities else "（未指定）"

    # 根据领域调整推演框架
    domain_framework = {
        "sports": "赛事结果/运动表现/联赛影响",
        "business": "市场竞争/盈利能力/投资价值",
        "geopolitics": "国家关系/制裁/军事",
        "economics": "货币政策/贸易/通胀",
        "science": "技术突破/产业应用/标准竞争",
        "society": "社会影响/舆论/政策",
        "disaster": "人员伤亡/救援响应/恢复重建",
    }.get(domain, "事件背景/影响/后续发展")

    cot_prompt = f"""
你是一名情报分析官，正在对以下新闻进行结构化推演分析。
【注意】当前知识图谱中没有该事件的直接关系路径，你必须完全基于原文进行推演。
每步推演都必须引用原文中的实际内容，不允许添加原文未提及的实体。

【新闻原文】
{news_fragment}

【已识别实体（来自原文）】
{entities_str}

【新闻领域】{domain}
【推演框架】{domain_framework}

【Chain-of-Thought 推演（每步必须引用原文）】

Step 1 领域确认：这条新闻的核心领域是什么？（引用原文关键词）

Step 2 核心事实：事件的核心驱动因素是什么？哪个实体在驱动变化？（引用原文）

Step 3 Alpha 路径（最可能演化）：
  - 如果当前趋势继续，最可能发生什么？
  - 4步因果链：[事实] --> [机制] --> [中间效应] --> [最终后果]
  - 原文支撑：...

Step 4 Beta 路径（结构性断裂）：
  - 如果 Alpha 路径的关键节点失效，触发条件是什么？

Step 5 数据缺口：推演中最关键的不确定信息？

完成后输出严格 JSON：
{{
  "domain": "{domain}",
  "driving_factor": "核心驱动力（必须引用原文实体和事件）",
  "scenario_alpha": {{
    "name": "路径名称",
    "probability": 0.4-0.65,
    "causal_chain": "A --> [机制] --> B --> C",
    "description": "一句话描述（必须与新闻领域一致）"
  }},
  "scenario_beta": {{
    "name": "路径名称",
    "probability": 0.1-0.35,
    "causal_chain": "A --> [机制] --> B --> C",
    "trigger_condition": "触发条件",
    "description": "一句话描述"
  }},
  "confidence": 0.3-0.55,
  "graph_evidence": "无图谱路径，CoT 基于原文推演（领域：{domain}）",
  "verification_gap": "最关键的数据缺口"
}}

只输出 JSON，不加任何说明。
"""
    try:
        response = llm_service.call(
            prompt=cot_prompt,
            system=(
                f"你是严谨的{domain}领域情报分析官。"
                "严格基于原文推演，每步必须引用原文证据。"
                "无图谱路径时 confidence 不得超过 0.55。"
                "推演结果必须与新闻的实际领域一致，不得套用无关领域模板。"
            ),
            temperature=0.2,
            max_tokens=1500,
            response_format="json",
        )
        if isinstance(response, dict):
            result = response
        else:
            text = str(response).strip()
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end > start:
                text = text[start: end + 1]
            import json as _json
            result = _json.loads(text)

        # 强制置信度上限
        result["confidence"] = min(float(result.get("confidence", 0.45)), 0.55)
        result["graph_evidence"] = f"无图谱路径，CoT 基于原文推演（领域：{domain}）"
        return result
    except Exception as exc:
        logger.error("CoT deduction failed: %s", exc)
        snippet = news_fragment[:80]
        return {
            "domain": domain,
            "driving_factor": f"基于原文推演：{snippet}",
            "scenario_alpha": {
                "name": "现状延续路径",
                "probability": 0.55,
                "causal_chain": f"{snippet} --> [事件演化] --> 相关实体调整 --> 格局渐变",
                "description": "CoT 兜底推演",
            },
            "scenario_beta": {
                "name": "结构性断裂路径",
                "probability": 0.25,
                "causal_chain": f"{snippet} --> [关键节点失效] --> 极端博弈 --> 格局重组",
                "trigger_condition": "关键依赖节点被外部冲击打断",
                "description": "CoT 兜底推演（断裂）",
            },
            "confidence": 0.35,
            "graph_evidence": f"无图谱路径，CoT 兜底（领域：{domain}）",
            "verification_gap": "需要更多原文细节和图谱路径支撑",
        }


# ═══════════════════════════════════════════════════════════════════
# Endpoint 1: Sacred Sword Analyzer
# ═══════════════════════════════════════════════════════════════════

@router.post("/sacred-sword")
def sacred_sword_analysis(request: AnalysisRequest) -> Dict[str, Any]:
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
                    {"statement": f.statement, "source": f.source, "confidence": f.confidence}
                    for f in result.facts
                ],
                "conflict":       result.conflict.value,
                "alpha": {
                    "name":           result.alpha.name,
                    "description":    result.alpha.description,
                    "probability":    result.alpha.probability,
                    "key_assumption": result.alpha.key_assumption,
                },
                "beta": {
                    "name":           result.beta.name,
                    "description":    result.beta.description,
                    "probability":    result.beta.probability,
                    "key_assumption": result.beta.key_assumption,
                },
                "confidence_score": result.confidence_score,
                "data_gap":         result.data_gap,
                "counter_arg":      result.counter_arg,
            },
        }
    except Exception as exc:
        logger.exception("Sacred Sword analysis failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ═══════════════════════════════════════════════════════════════════
# Endpoint 2: Grounded Analysis
# ═══════════════════════════════════════════════════════════════════

@router.post("/grounded/analyze")
def analyze_with_ontological_grounding(
    request: OntologyGroundedAnalysisRequest,
) -> Dict[str, Any]:
    try:
        _ensure_intelligence_importable()
        kuzu_conn   = _get_kuzu_connection()
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
# Endpoint 3: Deduction Soul（完整修复版）
# ═══════════════════════════════════════════════════════════════════

@router.post("/grounded/deduce")
def analyze_with_deduction_soul(
    request: OntologyGroundedAnalysisRequest,
) -> Dict[str, Any]:
    """
    本体路径推演端点 v4。

    修复流程：
    1. seed_entities 为空 → 领域感知提取（不再注入全局地缘政治词表）
    2. 验证提取的实体是否在原文中实际出现（过滤幻觉实体）
    3. 注意：不再自动写入实体到 KuzuDB（移除 auto-write 逻辑）
    4. 图谱路径为 0 → CoT 兜底（而不是进入 grounded_analyzer 乱推）
    5. 有图谱路径 → 走 grounded_analyzer
    """
    try:
        _ensure_intelligence_importable()
        kuzu_conn   = _get_kuzu_connection()
        llm_service = _get_llm_service()

        # ── Step 0：检测新闻领域（先于实体提取）─────────────────────────
        news_domain = _detect_domain(request.news_fragment)
        logger.info("News domain detected: %s", news_domain)

        # ── Step 1：获取有效实体（优先用请求中的，否则领域感知提取）──────
        effective_entities = list(request.seed_entities or [])

        if not effective_entities:
            logger.warning("⚠️ seed_entities 为空，启动领域感知实体提取")
            try:
                # 首选：领域感知提取（修复核心）
                effective_entities = _domain_aware_entity_extraction(request.news_fragment)
                logger.info("✅ 领域感知提取, 得到实体: %s", effective_entities)
            except Exception as exc:
                logger.warning("域感知提取失败: %s", exc)

            # 如果领域感知提取也失败，再尝试 EntityExtractionEngine
            if not effective_entities:
                logger.warning("领域感知提取为空，尝试 EntityExtractionEngine")
                try:
                    from intelligence.entity_extraction import EntityExtractionEngine
                    extractor = EntityExtractionEngine(llm_service)
                    req_id    = f"deduce_{int(time.time() * 1000)}"
                    extracted = extractor.extract(request.news_fragment, req_id)
                    raw_entities = []
                    if isinstance(extracted, list):
                        for ent in extracted:
                            name = ent.name if hasattr(ent, "name") else ent.get("name", "")
                            if name:
                                raw_entities.append(name)
                    # 关键修复：验证实体是否出现在原文（过滤幻觉注入）
                    effective_entities = _validate_entities_against_text(
                        raw_entities, request.news_fragment
                    )
                    logger.info("EntityExtractionEngine → validated: %s", effective_entities)
                except Exception as exc:
                    logger.exception("EntityExtractionEngine failed: %s", exc)

        # 兜底 A：EntityRelationExtractor（规则 + LLM，文本校验）
        if not effective_entities:
            logger.warning("领域感知/EntityExtractionEngine 均失败，尝试 EntityRelationExtractor")
            try:
                from app.knowledge.entity_extractor import EntityRelationExtractor
                er_result = EntityRelationExtractor().extract(request.news_fragment)
                raw_er = [e.get("name", "") for e in er_result.get("entities", []) if e.get("name")]
                effective_entities = _validate_entities_against_text(raw_er, request.news_fragment)
                logger.info(
                    "EntityRelationExtractor fallback → validated %d entities: %s",
                    len(effective_entities), effective_entities,
                )
            except Exception as exc:
                logger.warning("EntityRelationExtractor fallback failed: %s", exc)

        # 兜底 B：通用大写词（最后防线）
        if not effective_entities:
            logger.warning("所有提取方式均失败，使用通用大写词兜底")
            for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", request.news_fragment):
                name = m.group(1)
                if name.lower() not in {"the","and","for","with","from","into","over","that","this"}:
                    effective_entities.append(name)
            effective_entities = list(dict.fromkeys(effective_entities))[:8]

        # ── Step 2：查询图谱路径（不再写入任何实体）─────────────────────
        # 修复：移除之前的 auto-write 逻辑（写入应由 extractor_agent 完成）
        # 若 kuzu/ontology 模块不可用，跳过图谱查询直接进入 CoT 兜底
        extracted_graph_context: List[str] = []
        try:
            from ontology.kuzu_context_extractor import get_ontological_context
            for entity in effective_entities:
                ctx = get_ontological_context(kuzu_conn, entity)
                if ctx:
                    extracted_graph_context.append(ctx)
        except Exception as exc:
            logger.warning("图谱路径查询失败，将直接进入 CoT 兜底: %s", exc)

        # ── Step 3：判断图谱路径质量 ─────────────────────────────────────
        non_empty_contexts = [
            c for c in extracted_graph_context
            if "0 1-hop + 0 2-hop" not in c
        ]
        has_real_graph_evidence = len(non_empty_contexts) > 0

        logger.info(
            "Graph contexts: %d total / %d non-empty (domain=%s)",
            len(extracted_graph_context), len(non_empty_contexts), news_domain,
        )

        # ── Step 4：路径为 0 → CoT 兜底（不进入 grounded_analyzer）────────
        if not has_real_graph_evidence:
            logger.warning(
                "⚠️ 图谱路径全为 0，启动 CoT 兜底推演 (domain=%s)",
                news_domain,
            )
            deduction_result = _cot_deduction_from_text(
                news_fragment=request.news_fragment,
                seed_entities=effective_entities,
                llm_service=llm_service,
                domain=news_domain,
            )
            return {
                "status": "success",
                "mode": "cot_fallback",
                "ontological_grounding": {
                    "seed_entities":         effective_entities,
                    "graph_evidence":        extracted_graph_context,
                    "total_paths_extracted": 0,
                    "domain":                news_domain,
                    "note": (
                        f"图谱路径为 0（领域：{news_domain}），"
                        "使用 CoT 兜底推演，confidence ≤ 0.55"
                    ),
                },
                "deduction_result": deduction_result,
                "timestamp": datetime.now().isoformat(),
            }

        # ── Step 5：有图谱路径 → grounded_analyzer ──────────────────────
        from intelligence.grounded_analyzer import OntologyGroundedAnalyzer
        analyzer = OntologyGroundedAnalyzer(
            llm_service=llm_service,
            kuzu_conn=kuzu_conn,
        )
        raw_result = analyzer.analyze_with_ontological_grounding(
            news_fragment=request.news_fragment,
            seed_entities=effective_entities,
            claim=(
                f"【本体关系证据】：{str(non_empty_contexts)}\n\n"
                f"推演问题：{request.claim}"
            ),
        )
        deduction_result = raw_result.get("deduction_result", {})

        return {
            "status": "success",
            "ontological_grounding": {
                "seed_entities":         effective_entities,
                "graph_evidence":        non_empty_contexts,
                "total_paths_extracted": len(non_empty_contexts),
                "domain":                news_domain,
            },
            "deduction_result": deduction_result,
            "timestamp":        datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Deduction Soul analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ═══════════════════════════════════════════════════════════════════
# Endpoint 4: Evented Reasoning Pipeline  (three-stage)
# POST /api/v1/analysis/evented/deduce
# ═══════════════════════════════════════════════════════════════════

@router.post("/evented/deduce")
def analyze_with_evented_pipeline(
    request: OntologyGroundedAnalysisRequest,
) -> Dict[str, Any]:
    """
    Evented reasoning pipeline – three-stage verifiable deduction.

    Reuses the same request model as ``POST /analysis/grounded/deduce``
    for API compatibility.  The ``news_fragment`` field is used as the
    primary text input; ``claim`` and ``seed_entities`` are recorded but
    not required for the evented pipeline.

    Response structure
    ------------------
    ::

        {
          "status": "success",
          "events": [...],           # Stage 1 – extracted event nodes
          "active_patterns": [...],  # Stage 2a – deterministic event→pattern
          "derived_patterns": [...], # Stage 2b – composition_table derivation
          "conclusion": {...},       # Stage 3a – LLM-constrained or fallback
          "credibility": {...},      # Stage 3b – verifiability + KG consistency
          "timestamp": "..."
        }
    """
    try:
        _ensure_intelligence_importable()
        llm_service = _get_llm_service()

        # Combine title / claim context with the main news fragment
        text = request.news_fragment
        if request.claim and request.claim not in text:
            text = f"{request.news_fragment}\n{request.claim}"

        from intelligence.evented_pipeline import run_evented_pipeline

        # ── Normal mode run ──────────────────────────────────────────
        result = run_evented_pipeline(text=text, llm_service=llm_service)

        enrichment_dict: Optional[Dict[str, Any]] = None

        # ── Deep Ontology enrichment (if requested) ──────────────────
        if request.deep_mode:
            missing_before = result.credibility.get("missing_evidence", [])

            if missing_before:
                try:
                    from intelligence.evidence_enricher import (
                        DeepConfig,
                        enrich_missing_anchors,
                    )

                    cfg_dict = (request.deep_config.model_dump()
                                if request.deep_config else {})
                    deep_cfg = DeepConfig.from_dict(cfg_dict)

                    enrichment = enrich_missing_anchors(
                        text=text,
                        missing_before=missing_before,
                        deep_config=deep_cfg,
                        source_url=request.source_url,
                        local_meta=request.local_meta or {},
                    )
                    enrichment_dict = enrichment.to_dict()

                    # Rerun pipeline with enriched context appended
                    if enrichment.extra_context:
                        enriched_text = (
                            text
                            + "\n\n"
                            + enrichment.extra_context
                        )
                        result = run_evented_pipeline(
                            text=enriched_text,
                            llm_service=llm_service,
                        )

                except Exception as enrich_exc:
                    logger.warning(
                        "Deep enrichment failed, returning Normal results: %s",
                        enrich_exc,
                    )
                    enrichment_dict = {
                        "enabled": True,
                        "level": (request.deep_config.level
                                  if request.deep_config else 0),
                        "timeout_seconds": (request.deep_config.timeout_seconds
                                            if request.deep_config else 20),
                        "missing_before": missing_before,
                        "missing_after": missing_before,
                        "provenance": [],
                        "enriched_context_summary": "",
                        "cache_hit": False,
                        "limits": {
                            "searched": False,
                            "fetched_urls": 0,
                            "total_sources_used": 0,
                            "truncated": False,
                        },
                        "error": str(enrich_exc),
                    }
            else:
                # No missing anchors – return a minimal enrichment object
                enrichment_dict = {
                    "enabled": True,
                    "level": (request.deep_config.level
                              if request.deep_config else 0),
                    "timeout_seconds": (request.deep_config.timeout_seconds
                                        if request.deep_config else 20),
                    "missing_before": [],
                    "missing_after": [],
                    "provenance": [],
                    "enriched_context_summary": "All evidence anchors already present; no enrichment needed.",
                    "cache_hit": False,
                    "limits": {
                        "searched": False,
                        "fetched_urls": 0,
                        "total_sources_used": 0,
                        "truncated": False,
                    },
                }

        response: Dict[str, Any] = {
            "status":           "success",
            "events":           result.events,
            "active_patterns":  result.active_patterns,
            "derived_patterns": result.derived_patterns,
            "top_transitions":  result.top_transitions,
            "state_vector":     result.state_vector,
            "conclusion":       result.conclusion,
            "credibility":      result.credibility,
            "probability_tree": result.probability_tree,
            "driving_factors":  result.driving_factors,
            "timestamp":        datetime.now().isoformat(),
            "meta": {
                "seed_entities":   list(request.seed_entities),
                "text_length":     len(text),
                "event_count":     len(result.events),
                "pattern_count":   len(result.active_patterns),
                "derived_count":   len(result.derived_patterns),
                "deep_mode":       request.deep_mode,
            },
        }

        # Lie algebra vector space analysis (bounded, optional)
        try:
            from ontology.lie_algebra_space import compute_pattern_trajectory  # type: ignore
            active_names  = [ap.get("pattern", ap.get("pattern_name", "")) for ap in result.active_patterns]
            derived_names = [dp.get("pattern", dp.get("pattern_name", "")) for dp in result.derived_patterns]
            lie_algebra = compute_pattern_trajectory(active_names, derived_names)
        except Exception as lie_exc:
            logger.debug("Lie algebra computation skipped: %s", lie_exc)
            lie_algebra = {"enabled": False, "reason": "computation_unavailable"}
        response["lie_algebra"] = lie_algebra

        if enrichment_dict is not None:
            response["enrichment"] = enrichment_dict

        return response

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Evented pipeline analysis failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ═══════════════════════════════════════════════════════════════════
# Endpoint 5: Get Ontological Context
# ═══════════════════════════════════════════════════════════════════

@router.get("/ontological-context/{entity_name}")
def get_entity_ontological_context(entity_name: str) -> Dict[str, Any]:
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