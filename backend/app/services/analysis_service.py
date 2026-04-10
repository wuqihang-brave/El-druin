"""
Analysis Service v2 – Graph-Grounded Deduction Pipeline

改進重點：
1. perform_deduction 現在在調用 OntologyGroundedAnalyzer 之前，
   先通過 extract_mechanism_labels + DrivingFactorAggregator
   完成「Pre-LLM 機制聚合」，並將聚合結果注入 graph_context。
2. confidence 加成邏輯改為基於「強度≥0.7 的機制標籤數量」，
   而非簡單的字符串前綴判斷。
3. 新增 build_kuzu_schema_ddl() 工具函數：
   生成符合 CAMEO/FIBO 參考本體的 KuzuDB 建表語句，
   供開發者直接執行以初始化強化版圖谱 schema。
4. 新增 enrich_graph_relations_with_mechanisms() 工具函數：
   將現有 KuzuDB 邊批量附加 mechanism 和 domain 屬性。

CAMEO / FIBO 參考本體：
- 節點類型：Entity → 子類 Country, Organization, Person,
             Event, Resource, Technology, FinancialInstrument
- 邊類型：CAUSES, AFFECTS, SUPPORTS, OPPOSES, INVOLVES,
          SANCTIONS, SUPPLIES, LOCATED_IN, PARTICIPATES_IN,
          HOLDS_DEBT, TRADE_FLOW, CENTRAL_BANK_POLICY
- 邊屬性：mechanism (str), domain (str), strength (float),
          event_type (str, CAMEO code), timestamp (str)
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_KNOWN_KEYWORDS: List[str] = [
    "Israel", "Israeli", "Iran", "Iranian", "IRGC",
    "Gaza", "Palestinian", "Hamas", "Hezbollah",
    "Lebanon", "Lebanese", "Syria", "Syrian",
    "Russia", "Russian", "Ukraine", "Ukrainian",
    "China", "Chinese", "USA", "EU", "NATO",
    "AI", "OpenAI", "Google", "Microsoft", "Apple",
    "startup", "chip", "semiconductor", "GPU", "data center",
    "Fed", "ECB", "inflation", "tariff", "trade", "currency",
    "OPEC", "sanctioned", "sanctions",
]


# ---------------------------------------------------------------------------
# 工具函數：KuzuDB Schema DDL（CAMEO + FIBO 融合）
# ---------------------------------------------------------------------------

KUZU_SCHEMA_DDL = """
-- =====================================================================
-- EL-DRUIN KuzuDB 強化 Schema（CAMEO / FIBO 融合）
-- 執行此腳本以初始化或遷移圖谱結構
-- =====================================================================

-- 【節點表】Entity（基類）及子類
CREATE NODE TABLE IF NOT EXISTS Entity (
    id       STRING PRIMARY KEY,
    name     STRING,
    type     STRING,   -- Country | Organization | Person | Event | Resource | Technology | FinancialInstrument
    subtype  STRING,   -- 更細粒度：State | NGO | MNC | Commodity | Cryptocurrency ...
    aliases  STRING,   -- JSON 數組（逗號分隔）
    region   STRING,   -- 地區標籤
    updated  TIMESTAMP
);

-- 【邊表】核心關係類型（附 mechanism + domain 屬性）

-- 因果關係（CAMEO 核心）
CREATE REL TABLE IF NOT EXISTS CAUSES (
    FROM Entity TO Entity,
    mechanism  STRING,   -- 人類可讀的機制描述
    domain     STRING,   -- geopolitics | economics | technology | military | humanitarian | legal
    event_type STRING,   -- CAMEO 代碼，例如 "1032"（制裁）、"1721"（軍事打擊）
    strength   DOUBLE,   -- 關係強度 0.0-1.0（可從 GDELT 頻率衍生）
    direction  STRING,   -- positive | negative | neutral
    timestamp  TIMESTAMP
);

-- 影響關係
CREATE REL TABLE IF NOT EXISTS AFFECTS (
    FROM Entity TO Entity,
    mechanism  STRING,
    domain     STRING,
    strength   DOUBLE,
    direction  STRING,
    timestamp  TIMESTAMP
);

-- 支持 / 反對
CREATE REL TABLE IF NOT EXISTS SUPPORTS (
    FROM Entity TO Entity,
    mechanism  STRING,
    domain     STRING,
    strength   DOUBLE,
    timestamp  TIMESTAMP
);
CREATE REL TABLE IF NOT EXISTS OPPOSES (
    FROM Entity TO Entity,
    mechanism  STRING,
    domain     STRING,
    strength   DOUBLE,
    timestamp  TIMESTAMP
);

-- 制裁（CAMEO 制裁類事件）
CREATE REL TABLE IF NOT EXISTS SANCTIONS (
    FROM Entity TO Entity,
    sanction_type STRING,  -- export_control | asset_freeze | travel_ban | trade_embargo
    mechanism     STRING,
    strength      DOUBLE,
    effective_date STRING,
    timestamp     TIMESTAMP
);

-- 供應鏈 / 技術轉讓
CREATE REL TABLE IF NOT EXISTS SUPPLIES (
    FROM Entity TO Entity,
    commodity  STRING,   -- chip | oil | wheat | weapon | software ...
    mechanism  STRING,
    domain     STRING,
    volume     DOUBLE,   -- 相對規模（歸一化）
    direction  STRING,   -- export | import
    timestamp  TIMESTAMP
);

-- 地理位置
CREATE REL TABLE IF NOT EXISTS LOCATED_IN (
    FROM Entity TO Entity,
    role      STRING    -- capital | territory | disputed | operational_base
);

-- 參與事件
CREATE REL TABLE IF NOT EXISTS PARTICIPATES_IN (
    FROM Entity TO Entity,
    role      STRING,   -- initiator | target | mediator | observer
    mechanism STRING,
    timestamp TIMESTAMP
);

-- 金融關係（FIBO）
CREATE REL TABLE IF NOT EXISTS HOLDS_DEBT (
    FROM Entity TO Entity,
    amount_usd  DOUBLE,
    currency    STRING,
    maturity    STRING,
    mechanism   STRING,
    timestamp   TIMESTAMP
);

CREATE REL TABLE IF NOT EXISTS TRADE_FLOW (
    FROM Entity TO Entity,
    commodity   STRING,
    volume_usd  DOUBLE,
    direction   STRING,   -- export | import
    mechanism   STRING,
    timestamp   TIMESTAMP
);

CREATE REL TABLE IF NOT EXISTS CENTRAL_BANK_POLICY (
    FROM Entity TO Entity,
    policy_type  STRING,  -- rate_hike | qe | currency_swap | reserve_requirement
    mechanism    STRING,
    impact_score DOUBLE,
    timestamp    TIMESTAMP
);
"""


def get_kuzu_schema_ddl() -> str:
    """返回 CAMEO/FIBO 融合 KuzuDB schema DDL 字符串。"""
    return KUZU_SCHEMA_DDL


# ---------------------------------------------------------------------------
# 工具函數：批量附加 mechanism 屬性到現有邊
# ---------------------------------------------------------------------------

def enrich_graph_relations_with_mechanisms(
    kuzu_conn: Any,
    rel_table: str,
    mechanism_updates: List[Dict[str, Any]],
) -> int:
    """
    批量為 KuzuDB 邊附加 mechanism 和 domain 屬性。

    Args:
        kuzu_conn:          KuzuDB 連接對象
        rel_table:          邊表名稱（例如 "CAUSES"）
        mechanism_updates:  List of {"from_id": str, "to_id": str,
                                      "mechanism": str, "domain": str,
                                      "strength": float}

    Returns:
        成功更新的邊數量
    """
    if kuzu_conn is None or not mechanism_updates:
        return 0

    updated = 0
    for upd in mechanism_updates:
        try:
            query = f"""
                MATCH (a:Entity)-[r:{rel_table}]->(b:Entity)
                WHERE a.id = '{upd["from_id"]}' AND b.id = '{upd["to_id"]}'
                SET r.mechanism = '{upd.get("mechanism", "")}',
                    r.domain    = '{upd.get("domain", "")}',
                    r.strength  = {upd.get("strength", 0.7)}
            """
            kuzu_conn.execute(query)
            updated += 1
        except Exception as exc:
            logger.warning(
                "Failed to enrich relation %s->%s: %s",
                upd.get("from_id"), upd.get("to_id"), exc,
            )
    logger.info("Enriched %d/%d relations with mechanism labels", updated, len(mechanism_updates))
    return updated


# ---------------------------------------------------------------------------
# 內部工具
# ---------------------------------------------------------------------------

def _ensure_backend_on_path() -> None:
    here        = os.path.abspath(__file__)
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)


async def extract_entities_from_text(text: str) -> List[str]:
    """從新聞文本中提取命名實體（輕量啟發式）。"""

    def _extract(t: str) -> List[str]:
        entities: List[str] = []
        seen: set = set()

        for kw in _KNOWN_KEYWORDS:
            pattern = re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE)
            if pattern.search(t):
                canonical = kw
                if canonical not in seen:
                    entities.append(canonical)
                    seen.add(canonical)

        cap_pattern = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4})\b")
        for match in cap_pattern.finditer(t):
            token = match.group(1).strip()
            if token not in seen and len(token) > 2:
                entities.append(token)
                seen.add(token)

        return entities[:8]

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _extract, text)


def get_graph_context(kuzu_conn: Any, entities: List[str]) -> str:
    """
    從 KuzuDB 中檢索實體的本體上下文路徑（1-hop + 2-hop）。

    v2 改動：查詢結果中若包含 mechanism / domain 屬性，
    會以 "[domain] source --(relation)--> target | 機制: mechanism" 格式
    拼接到上下文字符串，以便 extract_mechanism_labels() 正確解析。
    """
    if kuzu_conn is None or not entities:
        return "【知識圖谱暫無數據】將基於新聞內容和通用領域知識進行推演"

    _ensure_backend_on_path()

    try:
        from ontology.kuzu_context_extractor import get_ontological_context  # type: ignore
    except ImportError:
        logger.warning("ontology.kuzu_context_extractor not importable; skipping graph context")
        return ""

    context_parts: List[str] = []
    for entity in entities[:4]:
        try:
            part = get_ontological_context(kuzu_conn, entity)
            if part.strip():
                context_parts.append(part)
        except Exception as exc:
            logger.debug("Could not get context for %s: %s", entity, exc)

    return "\n".join(context_parts)


# ---------------------------------------------------------------------------
# 主推演入口
# ---------------------------------------------------------------------------

async def perform_deduction(
    news_content: str,
    kuzu_conn: Any,
) -> Dict[str, Any]:
    """
    Graph-Grounded Deduction Pipeline v2

    新增步驟（在調用 OntologyGroundedAnalyzer 之前）：
    Step 2b – 通過 extract_mechanism_labels 提取機制標籤
    Step 2c – 通過 DrivingFactorAggregator 聚合驅動因素
    Step 2d – 將機制標籤列表注入 graph_context（供 GroundedAnalyzer 使用）
    """
    _ensure_backend_on_path()

    # Step 1 – 提取實體
    entities = await extract_entities_from_text(news_content)
    logger.info("Extracted entities for deduction: %s", entities)

    # Step 2 – 從 KuzuDB 獲取本體上下文
    graph_context_str = get_graph_context(kuzu_conn, entities)
    path_count = graph_context_str.count("\n") + 1 if graph_context_str.strip() else 0
    logger.info("GraphContext retrieved: %d paths", path_count)

    if not graph_context_str.strip():
        graph_context_str = "注意：當前知識圖谱庫中暫無直接關聯路徑，請基於通用本體邏輯進行推演。"
        logger.info("GraphContext empty; using fallback instruction")

    # ── v2 新增：Pre-LLM 機制提取與聚合 ──────────────────────────
    try:
        from intelligence.deduction_engine import (  # type: ignore
            DrivingFactorAggregator,
            extract_mechanism_labels,
        )
        mechanisms = extract_mechanism_labels(
            graph_context=graph_context_str,
            news_text=news_content,
            seed_entities=entities,
        )
        aggregator     = DrivingFactorAggregator()
        pre_driving    = aggregator.aggregate(mechanisms)
        mechanism_ctx  = aggregator.build_mechanism_context_for_prompt(mechanisms)

        logger.info(
            "Pre-LLM mechanism extraction: %d labels | driving: %s",
            len(mechanisms), pre_driving,
        )
    except ImportError:
        mechanisms    = []
        pre_driving   = ""
        mechanism_ctx = ""
        logger.warning("deduction_engine not importable; skipping pre-LLM mechanism extraction")

    logger.info(
        "Final graph_context length: %d chars | starts with: %s",
        len(graph_context_str),
        graph_context_str[:80],
    )

    # Step 3 – 構建 LLM 服務
    try:
        from app.api.routes.analysis import _get_llm_service  # type: ignore
        llm_service = _get_llm_service()
    except Exception as exc:
        logger.warning("Could not obtain LLM service: %s", exc)

        class _StubLLM:
            def call(self, **kwargs: Any) -> str:
                return "{}"

        llm_service = _StubLLM()

    # Step 4 – 調用 OntologyGroundedAnalyzer
    # 將機制上下文追加到本體上下文中，使分析器感知到機制標籤
    enriched_context = (
        graph_context_str
        + ("\n\n" + mechanism_ctx if mechanism_ctx else "")
        + ("\n\n【預聚合驅動因素】" + pre_driving if pre_driving else "")
    )

    from intelligence.grounded_analyzer import OntologyGroundedAnalyzer  # type: ignore
    try:
        analyzer = OntologyGroundedAnalyzer(
            llm_service=llm_service,
            kuzu_conn=kuzu_conn,
        )
        result = analyzer.analyze_with_ontological_grounding(
            news_fragment=news_content,
            seed_entities=entities if entities else ["系統要素"],
            claim="此事件對現有秩序及相關實體的潛在連鎖影響是什麼？",
            # v2：將機制上下文作為額外參數傳入（如果分析器支持）
            extra_context=enriched_context,
        )

        deduction: Dict[str, Any] = result.get("deduction_result", {})

        # ── v2 置信度加成：基於機制標籤強度，而非字符串前綴判斷 ──
        evidence_boost = 0
        if mechanisms:
            strong_count   = sum(1 for m in mechanisms if m.strength >= 0.7)
            evidence_boost = min(strong_count * 7, 21)   # 每條強機制 +7%，最多 +21%
            logger.info(
                "Mechanism evidence boost: +%d%% (%d strong labels)",
                evidence_boost, strong_count,
            )
        elif graph_context_str.startswith("事實:") or graph_context_str.startswith("推演:"):
            # 兼容舊版邏輯
            evidence_boost = 20
            logger.info("Legacy graph evidence detected; applying +%d%% boost", evidence_boost)

        current_conf = deduction.get("confidence", 0.5)
        boosted_conf = min(0.95, current_conf + (evidence_boost / 100.0))
        deduction["confidence"] = boosted_conf

        # 附加圖谱證據（含機制摘要）
        deduction["graph_evidence"]    = enriched_context
        deduction["mechanism_summary"] = pre_driving
        deduction["mechanism_count"]   = len(mechanisms)

        logger.info(
            "Deduction completed. Confidence: %.2f | mechanisms: %d",
            boosted_conf, len(mechanisms),
        )

        # ── PR-4: emit regime metrics as a side-effect ─────────────────
        deduction["regime_metrics"] = _compute_regime_side_effect(
            mechanisms=mechanisms,
            deduction=deduction,
        )

        return deduction

    except Exception as e:
        logger.error("Deduction failed: %s", e)
        return {
            "driving_factor":    pre_driving or "系統暫時無法提取驅動因素",
            "mechanism_summary": pre_driving,
            "scenario_alpha":    "推演引擎響應異常",
            "scenario_beta":     "請檢查後端日誌",
            "verification_gap":  str(e),
            "confidence":        0.0,
            "graph_evidence":    "",
            "mechanism_count":   0,
        }


# ---------------------------------------------------------------------------
# PR-4: Regime side-effect helper
# ---------------------------------------------------------------------------

def _compute_regime_side_effect(
    mechanisms: List[Any],
    deduction: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compute a lightweight regime metrics dict as a side-effect of the main
    deduction pipeline.

    This keeps regime output co-located with deduction output so callers
    (e.g. analysis endpoints) can access both without a second round-trip.
    The heavy per-request computation is handled by RegimeEngine; this helper
    provides a fast synchronous summary.
    """
    try:
        from app.services.regime_engine import RegimeEngine  # type: ignore

        engine = RegimeEngine()
        context = {
            "mechanisms": mechanisms,
            "deduction":  deduction,
        }
        raw = engine._extract_raw_metrics(context)
        score = engine._compute_structural_score(raw)
        regime = engine._map_structural_score_to_regime(score)

        return {
            "structural_score":    round(score, 4),
            "current_regime":      regime,
            "threshold_distance":  round(engine._compute_threshold_distance(score), 4),
            "transition_volatility": round(engine._compute_transition_volatility(raw), 4),
            "reversibility_index": round(engine._compute_reversibility_index(raw), 4),
            "coupling_asymmetry":  round(engine._compute_coupling_asymmetry(raw), 4),
            "damping_capacity":    round(engine._compute_damping_capacity(raw), 4),
            "dominant_axis":       engine._derive_dominant_axis(mechanisms),
        }
    except Exception as exc:
        logger.warning("_compute_regime_side_effect failed: %s", exc)
        return {}