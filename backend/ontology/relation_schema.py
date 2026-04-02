"""
ontology/relation_schema.py
============================
EL-DRUIN Ontological Relation Schema
三元組類型系統 + 笛卡爾積模式庫 + 本體映射

設計哲學：
  仿群論思維（Group-Theoretic Ontology）

  - 把關係類型 R 和實體類型 E 抽象成有限集合
  - 三元組 (e_src, r, e_tgt) ∈ E × R × E 對應一個「動力模式」
  - 每個動力模式有：
      • pattern_name   ── 命名（例如「霸權制裁模式」）
      • domain         ── 領域（地緣政治 / 經濟 / 技術 / 軍事）
      • typical_outcomes ── 典型後果列表（供 LLM 錨定推演）
      • inverse_pattern  ── 逆動力模式名稱（群論反元素類比）
      • composition_hints ── 與哪些模式組合後形成更高階效應

長遠目標：引入 Lie group / Lie algebra 的連續對稱性描述
  本文件是第一步：有限集合 + 離散模式（李群的有限子群近似）

引用資料：
  - CAMEO (Conflict and Mediation Event Observations) 動詞類型
  - FIBO (Financial Industry Business Ontology) 關係類型
  - Schema.org 類型層次（schemaorg-current-https-types.csv 中的頂層類）
  - entity_labels.py 三層本體標籤體系
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ===========================================================================
# 1. 有限集合 E：實體類型
# ===========================================================================

class EntityType(str, Enum):
    """
    有限實體類型集合 E。
    
    類比群論：E 的元素是「群的基底元素」，
    不同的 EntityType 組合決定三元組的「代數結構空間」。
    
    設計參考：
      - CAMEO Actor 分類體系
      - Schema.org Organization / Person / Place 層次
      - entity_labels.py LAYER1_PHYSICAL_TYPES
    """
    # 地緣政治主體
    STATE           = "state"           # 主權國家
    ALLIANCE        = "alliance"        # 聯盟 / 集團（NATO, EU, ASEAN）
    PARAMILITARY    = "paramilitary"    # 準軍事組織 / 非國家武裝
    IDEOLOGY        = "ideology"        # 意識形態 / 政治運動
    # 經濟 / 金融主體
    FIRM            = "firm"            # 企業（含跨國公司）
    FINANCIAL_ORG   = "financial_org"  # 央行 / 主權基金 / IMF
    RESOURCE        = "resource"        # 能源 / 礦物 / 農業等大宗資源
    CURRENCY        = "currency"        # 貨幣 / 數字資產
    SUPPLY_CHAIN    = "supply_chain"    # 供應鏈節點（工廠、港口、路線）
    # 技術主體
    TECH            = "tech"            # 技術系統 / 平台 / 算法
    STANDARD        = "standard"        # 技術標準 / 協議 / 規範
    # 社會 / 認知主體
    PERSON          = "person"          # 個體政治人物 / 關鍵決策者
    MEDIA           = "media"           # 媒體 / 信息來源
    TRUST           = "trust"           # 信任體系 / 社會契約（抽象節點）
    INSTITUTION     = "institution"     # 多邊機構 / 國際組織（WTO, UN）
    # 事件主體（可作為三元組的一端）
    CONFLICT        = "conflict"        # 戰爭 / 武裝衝突事件
    NORM            = "norm"            # 國際規範 / 法律 / 條約
    # 未知 / 無法分類
    UNKNOWN         = "unknown"         # 無法推斷類型（不參與笛卡爾積匹配）


# ===========================================================================
# 2. 有限集合 R：關係類型
# ===========================================================================

class RelationType(str, Enum):
    """
    有限關係類型集合 R。
    
    類比群論：R 的元素是「群運算符」，
    描述實體間的「作用方式」（類似李代數的生成元）。
    
    設計參考：
      - CAMEO 動詞類型體系（事件編碼）
      - FIBO 金融關係
      - analysis_service.py / deduction_engine.py 中使用的 CAMEOEventType
    """
    # 強制 / 對抗類
    SANCTION        = "sanction"        # 制裁 / 經濟封鎖
    MILITARY_STRIKE = "military_strike" # 軍事打擊
    COERCE          = "coerce"          # 脅迫 / 威懾
    BLOCKADE        = "blockade"        # 封鎖（海峽、貿易路線）
    # 合作 / 協調類
    SUPPORT         = "support"         # 政治 / 外交支持
    ALLY            = "ally"            # 結盟 / 軍事盟約
    AID             = "aid"             # 援助（資金、武器、物資）
    AGREE           = "agree"           # 達成協議 / 條約
    # 依賴 / 流通類
    DEPENDENCY      = "dependency"      # 結構性依賴（能源、技術）
    TRADE_FLOW      = "trade_flow"      # 貿易往來
    SUPPLY          = "supply"          # 供應（零件、資源、信息）
    FINANCE         = "finance"         # 融資 / 投資
    # 信息 / 認知類
    SIGNAL          = "signal"          # 發出信號（外交聲明、軍事演習）
    PROPAGANDA      = "propaganda"      # 信息操作 / 敘事構建
    LEGITIMIZE      = "legitimize"      # 賦予合法性
    DELEGITIMIZE    = "delegitimize"    # 去合法性 / 孤立
    # 結構 / 制度類
    REGULATE        = "regulate"        # 監管 / 制度約束
    STANDARDIZE     = "standardize"     # 制定標準
    EXCLUDE         = "exclude"         # 排除 / 踢出機制
    INTEGRATE       = "integrate"       # 整合 / 納入


# ===========================================================================
# 3. 動力模式：三元組 (EntityType, RelationType, EntityType) → Pattern
# ===========================================================================

@dataclass
class DynamicPattern:
    """
    一個三元組類型對應的「動力模式」。
    
    群論類比：
      pattern = e_src ⊗ r ⊗ e_tgt（張量積）
      代表一種特定的「力學空間」，在該空間中長期演化有統計規律。
    
    typical_outcomes 是推演的「先驗知識錨點」，
    讓 LLM 從「A sanction B」轉向：
    「在 state × sanction × state 模式下，長期通常出現 supply_chain_fragmentation」。
    """
    pattern_name:       str                    # 模式命名（中文）
    domain:             str                    # 領域標籤
    typical_outcomes:   List[str]              # 典型後果（按概率降序）
    mechanism_class:    str                    # 驅動機制類別（粗粒度）
    inverse_pattern:    Optional[str] = None   # 逆動力模式（群論反元素）
    composition_hints:  List[str] = field(default_factory=list)  # 與哪些模式組合形成高階效應
    confidence_prior:   float = 0.7            # 該模式後果的先驗置信度


# ===========================================================================
# 4. 笛卡爾積模式庫
#    Key: (EntityType, RelationType, EntityType)
#    Value: DynamicPattern
# ===========================================================================

# 類型別名
Triple = Tuple[EntityType, RelationType, EntityType]

CARTESIAN_PATTERN_REGISTRY: Dict[Triple, DynamicPattern] = {}


def _reg(
    e_src: EntityType,
    r: RelationType,
    e_tgt: EntityType,
    pattern_name: str,
    domain: str,
    typical_outcomes: List[str],
    mechanism_class: str,
    inverse_pattern: Optional[str] = None,
    composition_hints: Optional[List[str]] = None,
    confidence_prior: float = 0.72,
) -> None:
    """Helper to register a pattern without verbosity."""
    CARTESIAN_PATTERN_REGISTRY[(e_src, r, e_tgt)] = DynamicPattern(
        pattern_name=pattern_name,
        domain=domain,
        typical_outcomes=typical_outcomes,
        mechanism_class=mechanism_class,
        inverse_pattern=inverse_pattern,
        composition_hints=composition_hints or [],
        confidence_prior=confidence_prior,
    )


# ---------------------------------------------------------------------------
# 4.1 地緣政治 × 強制 / 對抗類
# ---------------------------------------------------------------------------

_reg(
    EntityType.STATE, RelationType.SANCTION, EntityType.STATE,
    pattern_name="霸權制裁模式",
    domain="geopolitics",
    typical_outcomes=[
        "supply_chain_fragmentation",   # 供應鏈碎片化
        "alliance_shift",               # 受制裁方尋求替代盟友
        "currency_substitution",        # 美元結算替代嘗試
        "domestic_consolidation",       # 目標國內部政治整合
        "third_party_arbitrage",        # 第三方從制裁中獲利
    ],
    mechanism_class="coercive_leverage",
    inverse_pattern="制裁解除 / 正常化模式",
    composition_hints=["技術封鎖模式", "金融孤立模式"],
    confidence_prior=0.78,
)

_reg(
    EntityType.STATE, RelationType.SANCTION, EntityType.FIRM,
    pattern_name="實體清單技術封鎖模式",
    domain="technology",
    typical_outcomes=[
        "supply_chain_decoupling",      # 供應鏈脫鉤
        "domestic_substitution_push",   # 目標國加速國產替代
        "third_country_re-export",      # 通過第三國迂迴輸出
        "technology_gap_widening",      # 技術差距擴大
    ],
    mechanism_class="tech_denial",
    inverse_pattern="技術許可 / 解禁模式",
    composition_hints=["霸權制裁模式", "標準排除模式"],
    confidence_prior=0.80,
)

_reg(
    EntityType.STATE, RelationType.MILITARY_STRIKE, EntityType.STATE,
    pattern_name="國家間武力衝突模式",
    domain="military",
    typical_outcomes=[
        "alliance_activation",          # 盟約觸發（集體防衛條款）
        "sanctions_cascade",            # 制裁瀑布
        "refugee_displacement",         # 難民流動
        "energy_market_disruption",     # 能源市場衝擊
        "regime_change_attempt",        # 政權更迭嘗試
    ],
    mechanism_class="kinetic_escalation",
    inverse_pattern="停火 / 和平協議模式",
    composition_hints=["霸權制裁模式", "信息戰模式"],
    confidence_prior=0.75,
)

_reg(
    EntityType.STATE, RelationType.COERCE, EntityType.STATE,
    pattern_name="大國脅迫 / 威懾模式",
    domain="geopolitics",
    typical_outcomes=[
        "policy_capitulation",          # 目標國讓步
        "counter_alliance_formation",   # 反制聯盟形成
        "credibility_erosion",          # 脅迫方公信力消耗
        "arms_race_acceleration",       # 軍備競賽加速
    ],
    mechanism_class="coercive_leverage",
    inverse_pattern="外交讓步 / 去升級模式",
    composition_hints=["霸權制裁模式", "信息戰模式"],
    confidence_prior=0.70,
)

_reg(
    EntityType.ALLIANCE, RelationType.SANCTION, EntityType.STATE,
    pattern_name="多邊聯盟制裁模式",
    domain="geopolitics",
    typical_outcomes=[
        "target_isolation",             # 目標國國際孤立
        "multilateral_compliance_cost", # 成員國合規成本上升
        "sanctions_fatigue",            # 聯盟制裁疲勞（長期）
        "gray_zone_evasion",            # 目標國灰色地帶規避
    ],
    mechanism_class="multilateral_pressure",
    inverse_pattern="多邊制裁解除模式",
    composition_hints=["霸權制裁模式", "金融孤立模式"],
    confidence_prior=0.73,
)

_reg(
    EntityType.PARAMILITARY, RelationType.MILITARY_STRIKE, EntityType.STATE,
    pattern_name="非國家武裝代理衝突模式",
    domain="military",
    typical_outcomes=[
        "state_sponsor_exposure",       # 幕後國家曝光 / 制裁壓力
        "asymmetric_escalation",        # 非對稱升級
        "civilian_infrastructure_targeting", # 平民基礎設施攻擊
        "regional_spillover",           # 區域溢出效應
    ],
    mechanism_class="proxy_warfare",
    inverse_pattern="代理武裝解除模式",
    composition_hints=["信息戰模式", "人道危機模式"],
    confidence_prior=0.68,
)

# ---------------------------------------------------------------------------
# 4.2 經濟 / 金融類
# ---------------------------------------------------------------------------

_reg(
    EntityType.STATE, RelationType.TRADE_FLOW, EntityType.STATE,
    pattern_name="雙邊貿易依存模式",
    domain="economics",
    typical_outcomes=[
        "mutual_vulnerability_lock_in",     # 雙向脆弱性鎖定
        "leverage_accumulation",            # 貿易順差方積累槓桿
        "currency_influence_expansion",     # 強勢方貨幣影響擴大
        "decoupling_cost_deterrence",       # 脫鉤成本形成威懾
    ],
    mechanism_class="economic_interdependence",
    inverse_pattern="貿易戰 / 脫鉤模式",
    composition_hints=["霸權制裁模式", "金融孤立模式"],
    confidence_prior=0.71,
)

_reg(
    EntityType.FINANCIAL_ORG, RelationType.REGULATE, EntityType.CURRENCY,
    pattern_name="央行貨幣政策傳導模式",
    domain="economics",
    typical_outcomes=[
        "emerging_market_capital_outflow",  # 新興市場資本外流
        "dollar_strengthening",             # 美元強勢週期
        "debt_service_cost_spike",          # 外債還款成本激增
        "commodity_price_denominated_shift",# 大宗商品計價重組
    ],
    mechanism_class="monetary_transmission",
    inverse_pattern="寬鬆週期模式",
    composition_hints=["主權債務危機模式", "雙邊貿易依存模式"],
    confidence_prior=0.76,
)

_reg(
    EntityType.STATE, RelationType.SANCTION, EntityType.FINANCIAL_ORG,
    pattern_name="金融孤立 / SWIFT 切斷模式",
    domain="economics",
    typical_outcomes=[
        "payment_system_fragmentation",     # 支付體系碎片化
        "alternative_settlement_push",      # 替代結算機制推進（CIPS、數字貨幣）
        "hyperinflation_risk",              # 通脹失控風險
        "commodity_barter_resurgence",      # 以貨易貨回潮
    ],
    mechanism_class="financial_exclusion",
    inverse_pattern="金融再整合模式",
    composition_hints=["霸權制裁模式", "央行貨幣政策傳導模式"],
    confidence_prior=0.79,
)

_reg(
    EntityType.FIRM, RelationType.DEPENDENCY, EntityType.SUPPLY_CHAIN,
    pattern_name="企業供應鏈單點依賴模式",
    domain="economics",
    typical_outcomes=[
        "supply_shock_vulnerability",       # 供應衝擊脆弱性
        "just_in_case_inventory_build",     # 安全庫存策略轉型
        "near_shoring_acceleration",        # 近岸生產加速
        "margin_compression_from_hedging",  # 對沖成本擠壓利潤
    ],
    mechanism_class="supply_chain_resilience",
    inverse_pattern="供應鏈多元化模式",
    composition_hints=["實體清單技術封鎖模式", "貿易戰 / 脫鉤模式"],
    confidence_prior=0.74,
)

_reg(
    EntityType.RESOURCE, RelationType.DEPENDENCY, EntityType.STATE,
    pattern_name="資源依賴 / 能源武器化模式",
    domain="geopolitics",
    typical_outcomes=[
        "energy_coercion_episodes",         # 能源脅迫事件
        "importing_country_diversification",# 進口國加速多元化
        "pipeline_geopolitics",             # 管道地緣政治
        "green_transition_acceleration",    # 可再生能源轉型加速（長期）
    ],
    mechanism_class="resource_leverage",
    inverse_pattern="能源多元化 / 去依賴模式",
    composition_hints=["霸權制裁模式", "大國脅迫模式"],
    confidence_prior=0.77,
)

# ---------------------------------------------------------------------------
# 4.3 技術類
# ---------------------------------------------------------------------------

_reg(
    EntityType.STATE, RelationType.STANDARDIZE, EntityType.TECH,
    pattern_name="技術標準主導模式",
    domain="technology",
    typical_outcomes=[
        "standard_adoption_lock_in",        # 標準鎖定效應
        "competing_standard_fragmentation", # 競爭標準分裂（技術巴爾幹化）
        "licensing_revenue_accumulation",   # 專利授權收入積累
        "supply_chain_design_control",      # 供應鏈設計主導權
    ],
    mechanism_class="tech_governance",
    inverse_pattern="標準競爭失敗 / 替代標準崛起模式",
    composition_hints=["實體清單技術封鎖模式", "科技脫鉤模式"],
    confidence_prior=0.72,
)

_reg(
    EntityType.FIRM, RelationType.SUPPLY, EntityType.FIRM,
    pattern_name="關鍵零部件寡頭供應模式",
    domain="technology",
    typical_outcomes=[
        "supplier_pricing_power",           # 供應方議價能力強化
        "buyer_diversification_effort",     # 採購方多元化努力
        "technology_transfer_leverage",     # 技術轉讓為籌碼
        "monopoly_rent_extraction",         # 壟斷租金提取
    ],
    mechanism_class="oligopoly_supply",
    inverse_pattern="供應市場競爭充分化模式",
    composition_hints=["企業供應鏈單點依賴模式", "技術標準主導模式"],
    confidence_prior=0.73,
)

_reg(
    EntityType.STATE, RelationType.EXCLUDE, EntityType.TECH,
    pattern_name="科技脫鉤 / 技術鐵幕模式",
    domain="technology",
    typical_outcomes=[
        "parallel_tech_stack_emergence",    # 平行技術生態形成
        "innovation_efficiency_loss",       # 創新效率損失（雙方）
        "semiconductor_chokepoint",         # 半導體卡脖子效應
        "digital_sovereignty_push",         # 數字主權強化
    ],
    mechanism_class="tech_decoupling",
    inverse_pattern="技術合作再融合模式",
    composition_hints=["技術標準主導模式", "實體清單技術封鎖模式"],
    confidence_prior=0.76,
)

# ---------------------------------------------------------------------------
# 4.4 信任 / 信息 / 制度類
# ---------------------------------------------------------------------------

_reg(
    EntityType.MEDIA, RelationType.PROPAGANDA, EntityType.TRUST,
    pattern_name="信息戰 / 敘事操控模式",
    domain="information",
    typical_outcomes=[
        "public_opinion_polarization",      # 輿論極化
        "institutional_trust_erosion",      # 制度信任侵蝕
        "counter_narrative_escalation",     # 對抗性敘事升級
        "epistemic_fragmentation",          # 認知空間碎片化
    ],
    mechanism_class="epistemic_warfare",
    inverse_pattern="信息環境修復模式",
    composition_hints=["大國脅迫模式", "代理武裝衝突模式"],
    confidence_prior=0.68,
)

_reg(
    EntityType.INSTITUTION, RelationType.REGULATE, EntityType.FIRM,
    pattern_name="跨國監管 / 合規約束模式",
    domain="legal",
    typical_outcomes=[
        "regulatory_compliance_cost_spike", # 合規成本上升
        "regulatory_arbitrage",             # 監管套利（轉移司法管轄）
        "market_access_conditionality",     # 市場准入條件化
        "industry_consolidation",           # 行業整合（小企業淘汰）
    ],
    mechanism_class="regulatory_pressure",
    inverse_pattern="監管放鬆 / 去規制模式",
    composition_hints=["技術標準主導模式", "金融孤立模式"],
    confidence_prior=0.71,
)

_reg(
    EntityType.STATE, RelationType.ALLY, EntityType.STATE,
    pattern_name="正式軍事同盟模式",
    domain="geopolitics",
    typical_outcomes=[
        "collective_defense_deterrence",    # 集體防衛威懾效果
        "alliance_entrapment_risk",         # 同盟拖拽風險（entrapment）
        "burden_sharing_friction",          # 責任分擔摩擦
        "adversary_counter_coalition",      # 對手反制聯盟形成
    ],
    mechanism_class="alliance_dynamics",
    inverse_pattern="同盟瓦解 / 中立化模式",
    composition_hints=["多邊聯盟制裁模式", "大國脅迫模式"],
    confidence_prior=0.74,
)

_reg(
    EntityType.STATE, RelationType.LEGITIMIZE, EntityType.NORM,
    pattern_name="國際規範建構模式",
    domain="geopolitics",
    typical_outcomes=[
        "norm_cascade",                     # 規範擴散（norm cascade 效應）
        "competing_norm_fragmentation",     # 競爭性規範出現
        "soft_power_accumulation",          # 軟實力積累
        "free_rider_problem",               # 搭便車問題
    ],
    mechanism_class="norm_diffusion",
    inverse_pattern="規範侵蝕 / 去合法化模式",
    composition_hints=["技術標準主導模式", "信息戰模式"],
    confidence_prior=0.67,
)


# ---------------------------------------------------------------------------
# 4.5 逆元佔位模式（B1 嚴格模式：確保每個 inverse_pattern 引用均已注冊）
# ---------------------------------------------------------------------------
# 每個現有模式的 inverse_pattern 字段引用了一個逆模式名稱，
# 但這些逆模式尚未作為 CARTESIAN_PATTERN_REGISTRY 條目存在。
# 在此以「佔位動力模式」形式注冊它們，讓 validate_inverses() 通過，
# 並使逆元推演查詢可以找到其典型後果。

_reg(
    EntityType.STATE, RelationType.AGREE, EntityType.STATE,
    pattern_name="制裁解除 / 正常化模式",
    domain="geopolitics",
    typical_outcomes=[
        "trade_normalization",          # 貿易關係正常化
        "diplomatic_restoration",       # 外交關係恢復
        "investment_flows_resumption",  # 投資流動恢復
    ],
    mechanism_class="diplomatic_normalization",
    inverse_pattern="霸權制裁模式",
    confidence_prior=0.65,
)

_reg(
    EntityType.STATE, RelationType.AGREE, EntityType.FIRM,
    pattern_name="技術許可 / 解禁模式",
    domain="technology",
    typical_outcomes=[
        "technology_transfer_resumption",   # 技術轉讓恢復
        "market_access_restoration",        # 市場准入恢復
        "supply_chain_reintegration",       # 供應鏈重新整合
    ],
    mechanism_class="tech_normalization",
    inverse_pattern="實體清單技術封鎖模式",
    confidence_prior=0.60,
)

_reg(
    EntityType.CONFLICT, RelationType.AGREE, EntityType.CONFLICT,
    pattern_name="停火 / 和平協議模式",
    domain="military",
    typical_outcomes=[
        "hostility_cessation",          # 敵對行動停止
        "humanitarian_access",          # 人道救援通道開放
        "reconstruction_process",       # 重建進程啟動
        "political_negotiation",        # 政治談判啟動
    ],
    mechanism_class="conflict_resolution",
    inverse_pattern="國家間武力衝突模式",
    confidence_prior=0.62,
)

_reg(
    EntityType.STATE, RelationType.SIGNAL, EntityType.STATE,
    pattern_name="外交讓步 / 去升級模式",
    domain="geopolitics",
    typical_outcomes=[
        "tension_reduction",            # 緊張態勢降低
        "face_saving_compromise",       # 體面妥協
        "negotiation_resumption",       # 談判恢復
    ],
    mechanism_class="de_escalation",
    inverse_pattern="大國脅迫 / 威懾模式",
    confidence_prior=0.60,
)

_reg(
    EntityType.ALLIANCE, RelationType.AGREE, EntityType.STATE,
    pattern_name="多邊制裁解除模式",
    domain="geopolitics",
    typical_outcomes=[
        "multilateral_normalization",   # 多邊關係正常化
        "coalition_pressure_release",   # 聯盟壓力釋放
        "international_reintegration",  # 國際再融合
    ],
    mechanism_class="multilateral_normalization",
    inverse_pattern="多邊聯盟制裁模式",
    confidence_prior=0.60,
)

_reg(
    EntityType.PARAMILITARY, RelationType.AGREE, EntityType.STATE,
    pattern_name="代理武裝解除模式",
    domain="military",
    typical_outcomes=[
        "proxy_disarmament",            # 代理武裝解除
        "conflict_freeze",              # 衝突凍結
        "political_integration",        # 政治整合
    ],
    mechanism_class="proxy_disarmament",
    inverse_pattern="非國家武裝代理衝突模式",
    confidence_prior=0.55,
)

_reg(
    EntityType.STATE, RelationType.EXCLUDE, EntityType.STATE,
    pattern_name="貿易戰 / 脫鉤模式",
    domain="economics",
    typical_outcomes=[
        "bilateral_trade_collapse",     # 雙邊貿易崩潰
        "supply_chain_fragmentation",   # 供應鏈碎片化
        "third_country_trade_diversion",# 第三國貿易轉移
        "inflation_pressure",           # 通脹壓力
    ],
    mechanism_class="economic_decoupling",
    inverse_pattern="雙邊貿易依存模式",
    confidence_prior=0.68,
)

_reg(
    EntityType.FINANCIAL_ORG, RelationType.AID, EntityType.CURRENCY,
    pattern_name="寬鬆週期模式",
    domain="economics",
    typical_outcomes=[
        "credit_expansion",             # 信貸擴張
        "asset_price_inflation",        # 資產價格通脹
        "emerging_market_inflows",      # 新興市場資本流入
        "currency_depreciation",        # 貨幣貶值壓力
    ],
    mechanism_class="monetary_easing",
    inverse_pattern="央行貨幣政策傳導模式",
    confidence_prior=0.68,
)

_reg(
    EntityType.STATE, RelationType.INTEGRATE, EntityType.FINANCIAL_ORG,
    pattern_name="金融再整合模式",
    domain="economics",
    typical_outcomes=[
        "payment_system_reintegration", # 支付體系再整合
        "credit_access_restoration",    # 信貸獲取恢復
        "trade_finance_resumption",     # 貿易融資恢復
    ],
    mechanism_class="financial_normalization",
    inverse_pattern="金融孤立 / SWIFT 切斷模式",
    confidence_prior=0.60,
)

_reg(
    EntityType.FIRM, RelationType.SUPPLY, EntityType.SUPPLY_CHAIN,
    pattern_name="供應鏈多元化模式",
    domain="economics",
    typical_outcomes=[
        "resilience_improvement",       # 韌性提升
        "cost_increase_short_term",     # 短期成本上升
        "geopolitical_risk_reduction",  # 地緣政治風險降低
    ],
    mechanism_class="supply_chain_diversification",
    inverse_pattern="企業供應鏈單點依賴模式",
    confidence_prior=0.65,
)

_reg(
    EntityType.STATE, RelationType.TRADE_FLOW, EntityType.RESOURCE,
    pattern_name="能源多元化 / 去依賴模式",
    domain="geopolitics",
    typical_outcomes=[
        "energy_security_improvement",  # 能源安全改善
        "supplier_bargaining_reduction",# 供應商議價能力下降
        "green_transition_acceleration",# 可再生能源轉型加速
    ],
    mechanism_class="energy_diversification",
    inverse_pattern="資源依賴 / 能源武器化模式",
    confidence_prior=0.65,
)

_reg(
    EntityType.STATE, RelationType.DELEGITIMIZE, EntityType.TECH,
    pattern_name="標準競爭失敗 / 替代標準崛起模式",
    domain="technology",
    typical_outcomes=[
        "standard_displacement",        # 標準替代
        "market_share_redistribution",  # 市場份額重新分配
        "technology_fragmentation",     # 技術碎片化
    ],
    mechanism_class="standard_disruption",
    inverse_pattern="技術標準主導模式",
    confidence_prior=0.58,
)

_reg(
    EntityType.FIRM, RelationType.TRADE_FLOW, EntityType.FIRM,
    pattern_name="供應市場競爭充分化模式",
    domain="technology",
    typical_outcomes=[
        "price_competition",            # 價格競爭
        "buyer_bargaining_increase",    # 採購方議價增強
        "innovation_acceleration",      # 創新加速
    ],
    mechanism_class="market_competition",
    inverse_pattern="關鍵零部件寡頭供應模式",
    confidence_prior=0.62,
)

_reg(
    EntityType.STATE, RelationType.INTEGRATE, EntityType.TECH,
    pattern_name="技術合作再融合模式",
    domain="technology",
    typical_outcomes=[
        "joint_rd_resumption",          # 聯合研發恢復
        "technology_transfer_flow",     # 技術轉讓流動
        "innovation_spillover",         # 創新溢出效應
    ],
    mechanism_class="tech_reintegration",
    inverse_pattern="科技脫鉤 / 技術鐵幕模式",
    confidence_prior=0.58,
)

_reg(
    EntityType.MEDIA, RelationType.LEGITIMIZE, EntityType.TRUST,
    pattern_name="信息環境修復模式",
    domain="information",
    typical_outcomes=[
        "public_trust_restoration",     # 公眾信任恢復
        "epistemic_common_ground",      # 認知共識形成
        "media_credibility_recovery",   # 媒體公信力恢復
    ],
    mechanism_class="information_repair",
    inverse_pattern="信息戰 / 敘事操控模式",
    confidence_prior=0.55,
)

_reg(
    EntityType.INSTITUTION, RelationType.AID, EntityType.FIRM,
    pattern_name="監管放鬆 / 去規制模式",
    domain="legal",
    typical_outcomes=[
        "compliance_cost_reduction",    # 合規成本降低
        "market_entry_facilitation",    # 市場進入促進
        "regulatory_risk_reduction",    # 監管風險降低
    ],
    mechanism_class="deregulation",
    inverse_pattern="跨國監管 / 合規約束模式",
    confidence_prior=0.60,
)

_reg(
    EntityType.STATE, RelationType.DELEGITIMIZE, EntityType.STATE,
    pattern_name="同盟瓦解 / 中立化模式",
    domain="geopolitics",
    typical_outcomes=[
        "alliance_fragmentation",       # 同盟碎片化
        "strategic_autonomy_pursuit",   # 戰略自主尋求
        "collective_defense_weakening", # 集體防衛削弱
    ],
    mechanism_class="alliance_dissolution",
    inverse_pattern="正式軍事同盟模式",
    confidence_prior=0.58,
)

_reg(
    EntityType.STATE, RelationType.DELEGITIMIZE, EntityType.NORM,
    pattern_name="規範侵蝕 / 去合法化模式",
    domain="geopolitics",
    typical_outcomes=[
        "international_order_erosion",  # 國際秩序侵蝕
        "norm_fragmentation",           # 規範碎片化
        "rule_based_order_weakening",   # 規則體系削弱
    ],
    mechanism_class="norm_erosion",
    inverse_pattern="國際規範建構模式",
    confidence_prior=0.55,
)


# ===========================================================================
# 5. 查詢 API
# ===========================================================================

def lookup_pattern(
    e_src: EntityType,
    r: RelationType,
    e_tgt: EntityType,
) -> Optional[DynamicPattern]:
    """
    精確查詢三元組對應的動力模式。

    Returns None if no pattern is registered for this triple.
    """
    return CARTESIAN_PATTERN_REGISTRY.get((e_src, r, e_tgt))


def lookup_pattern_by_strings(
    e_src: str,
    r: str,
    e_tgt: str,
) -> Optional[DynamicPattern]:
    """
    字符串接口版本（不區分大小寫）。

    Args:
        e_src: 源實體類型字符串，例如 "state"
        r:     關係類型字符串，例如 "sanction"
        e_tgt: 目標實體類型字符串

    Returns:
        DynamicPattern or None
    """
    try:
        src = EntityType(e_src.lower().strip())
        rel = RelationType(r.lower().strip())
        tgt = EntityType(e_tgt.lower().strip())
        return lookup_pattern(src, rel, tgt)
    except ValueError:
        return None


def fuzzy_lookup_pattern(
    e_src_hint: str,
    r_hint: str,
    e_tgt_hint: str,
) -> List[Tuple[Triple, DynamicPattern, float]]:
    """
    模糊查詢：當精確匹配失敗時，返回最相近的模式列表。

    匹配策略：
    1. 精確匹配 relation（最重要）
    2. 實體類型部分匹配（字符串包含）
    3. 返回 (triple, pattern, score) 列表，按分數降序
    """
    results: List[Tuple[Triple, DynamicPattern, float]] = []

    r_hint_lower = r_hint.lower().strip()
    src_hint_lower = e_src_hint.lower().strip()
    tgt_hint_lower = e_tgt_hint.lower().strip()

    for (src, rel, tgt), pattern in CARTESIAN_PATTERN_REGISTRY.items():
        score = 0.0

        # Relation 精確匹配：+0.6
        if rel.value == r_hint_lower:
            score += 0.6
        elif r_hint_lower in rel.value or rel.value in r_hint_lower:
            score += 0.3

        # 源實體類型匹配：+0.2
        if src.value == src_hint_lower:
            score += 0.2
        elif src_hint_lower in src.value or src.value in src_hint_lower:
            score += 0.1

        # 目標實體類型匹配：+0.2
        if tgt.value == tgt_hint_lower:
            score += 0.2
        elif tgt_hint_lower in tgt.value or tgt.value in tgt_hint_lower:
            score += 0.1

        if score > 0:
            results.append(((src, rel, tgt), pattern, score))

    results.sort(key=lambda x: x[2], reverse=True)
    return results[:5]  # 返回 top 5


def get_all_patterns_for_domain(domain: str) -> List[Tuple[Triple, DynamicPattern]]:
    """返回指定領域的所有已注冊模式。"""
    return [
        (triple, pattern)
        for triple, pattern in CARTESIAN_PATTERN_REGISTRY.items()
        if pattern.domain == domain
    ]


def get_outcomes_for_triple(
    e_src: str,
    r: str,
    e_tgt: str,
    fallback_generic: bool = True,
) -> List[str]:
    """
    獲取三元組的典型後果列表。

    先嘗試精確查詢，失敗則模糊查詢，最後返回通用兜底後果。
    """
    pattern = lookup_pattern_by_strings(e_src, r, e_tgt)
    if pattern:
        return pattern.typical_outcomes

    fuzzy = fuzzy_lookup_pattern(e_src, r, e_tgt)
    if fuzzy:
        best_triple, best_pattern, score = fuzzy[0]
        if score >= 0.4:
            return best_pattern.typical_outcomes

    if fallback_generic:
        return [
            "structural_realignment",       # 結構性重組
            "third_party_opportunity",      # 第三方機會窗口
            "uncertainty_premium",          # 不確定性溢價上升
        ]
    return []


# ===========================================================================
# 6. 笛卡爾積診斷報告
# ===========================================================================

@dataclass
class CartesianDiagnosticReport:
    """
    笛卡爾積診斷報告：針對輸入的三元組，輸出完整診斷信息。
    供前端「笛卡爾積診斷視圖」展示。
    """
    input_triple:       Tuple[str, str, str]
    matched_pattern:    Optional[DynamicPattern]
    fuzzy_matches:      List[Tuple[Triple, DynamicPattern, float]]
    typical_outcomes:   List[str]
    mechanism_class:    str
    domain:             str
    confidence_prior:   float
    composition_chain:  List[str]   # 高階效應組合
    inverse_pattern:    Optional[str]
    diagnostic_note:    str         # 文字說明


def generate_diagnostic_report(
    e_src: str,
    r: str,
    e_tgt: str,
) -> CartesianDiagnosticReport:
    """
    生成完整笛卡爾積診斷報告。

    這是供前端「診斷視圖」調用的核心函數。
    當 e_src 或 e_tgt 為 "unknown" 時短路返回無匹配報告，
    避免以 unknown 污染笛卡爾積空間。
    """
    # UNKNOWN 短路：entity type 未能推斷時直接返回無匹配報告
    if e_src == "unknown" or e_tgt == "unknown":
        unknown_side = "e_src" if e_src == "unknown" else "e_tgt"
        return CartesianDiagnosticReport(
            input_triple=(e_src, r, e_tgt),
            matched_pattern=None,
            fuzzy_matches=[],
            typical_outcomes=["structural_realignment", "third_party_opportunity", "uncertainty_premium"],
            mechanism_class="unknown",
            domain="unknown",
            confidence_prior=0.5,
            composition_chain=[],
            inverse_pattern=None,
            diagnostic_note=(
                f"[UNKNOWN_ENTITY_TYPE] {unknown_side}='{e_src if e_src == 'unknown' else e_tgt}' "
                f"無法推斷實體類型，笛卡爾積匹配已跳過。"
                f"請確認實體名稱是否在 _ENTITY_NAME_HINTS 覆蓋範圍內。"
            ),
        )

    exact = lookup_pattern_by_strings(e_src, r, e_tgt)
    fuzzy = fuzzy_lookup_pattern(e_src, r, e_tgt)

    if exact:
        inv = get_inverse_pattern(exact.pattern_name)
        inv_note = f" 逆模式：「{inv}」。" if inv else ""
        note = (
            f"精確匹配：三元組 ({e_src} × {r} × {e_tgt}) "
            f"對應「{exact.pattern_name}」。"
            f"先驗置信度 {exact.confidence_prior:.0%}。"
            f"{inv_note}"
        )
        return CartesianDiagnosticReport(
            input_triple=(e_src, r, e_tgt),
            matched_pattern=exact,
            fuzzy_matches=fuzzy,
            typical_outcomes=exact.typical_outcomes,
            mechanism_class=exact.mechanism_class,
            domain=exact.domain,
            confidence_prior=exact.confidence_prior,
            composition_chain=exact.composition_hints,
            inverse_pattern=exact.inverse_pattern,
            diagnostic_note=note,
        )

    if fuzzy:
        best_triple, best_pat, score = fuzzy[0]
        note = (
            f"無精確匹配。模糊匹配分數 {score:.2f}，"
            f"最近模式：「{best_pat.pattern_name}」"
            f"（{best_triple[0].value} × {best_triple[1].value} × {best_triple[2].value}）。"
            f"建議在 relation_schema.py 中補充新模式。"
        )
        return CartesianDiagnosticReport(
            input_triple=(e_src, r, e_tgt),
            matched_pattern=best_pat,
            fuzzy_matches=fuzzy,
            typical_outcomes=best_pat.typical_outcomes,
            mechanism_class=best_pat.mechanism_class,
            domain=best_pat.domain,
            confidence_prior=best_pat.confidence_prior * 0.8,  # 模糊匹配降低置信度
            composition_chain=best_pat.composition_hints,
            inverse_pattern=best_pat.inverse_pattern,
            diagnostic_note=note,
        )

    return CartesianDiagnosticReport(
        input_triple=(e_src, r, e_tgt),
        matched_pattern=None,
        fuzzy_matches=[],
        typical_outcomes=["structural_realignment", "third_party_opportunity", "uncertainty_premium"],
        mechanism_class="unknown",
        domain="unknown",
        confidence_prior=0.5,
        composition_chain=[],
        inverse_pattern=None,
        diagnostic_note=(
            f"三元組 ({e_src} × {r} × {e_tgt}) 在模式庫中無任何匹配。"
            "後果推演退化為通用本體邏輯。建議補充領域專家知識。"
        ),
    )


# ===========================================================================
# 7. 與 deduction_engine 的整合接口
# ===========================================================================

def enrich_mechanism_labels_with_patterns(
    mechanism_labels: list,
) -> list:
    """
    接受 deduction_engine.MechanismLabel 列表，
    為每條標籤查詢笛卡爾積模式庫，並將典型後果注入 mechanism 字段。

    Args:
        mechanism_labels: List[MechanismLabel]（鴨子類型，不強依賴導入）

    Returns:
        增強後的 MechanismLabel 列表（原地修改 evidence 字段）
    """
    for lbl in mechanism_labels:
        outcomes = get_outcomes_for_triple(
            e_src=getattr(lbl, "source", ""),
            r=getattr(lbl, "relation", ""),
            e_tgt=getattr(lbl, "target", ""),
            fallback_generic=True,
        )
        if outcomes:
            outcome_text = " | ".join(outcomes[:3])
            existing_evidence = getattr(lbl, "evidence", "")
            object.__setattr__(
                lbl, "evidence",
                f"{existing_evidence} [模式後果: {outcome_text}]",
            ) if hasattr(lbl, "__setattr__") else None
            try:
                lbl.evidence = (
                    f"{existing_evidence} [模式後果: {outcome_text}]"
                )
            except AttributeError:
                pass
    return mechanism_labels


def build_pattern_context_for_prompt(
    mechanism_labels: list,
) -> str:
    """
    從 MechanismLabel 列表中提取動力模式，生成結構化的 prompt 上下文片段。

    示例輸出：
        【笛卡爾積動力模式】
        1. state × sanction × state → 霸權制裁模式 (geopolitics)
           典型後果: supply_chain_fragmentation | alliance_shift | currency_substitution
           先驗置信度: 78%
    """
    if not mechanism_labels:
        return ""

    lines = ["【笛卡爾積動力模式（用於錨定推演後果先驗）】"]
    seen: set = set()

    for lbl in mechanism_labels:
        src = getattr(lbl, "source", "")
        rel = getattr(lbl, "relation", "")
        tgt = getattr(lbl, "target", "")

        # 嘗試將實體名映射到 EntityType
        src_type = _infer_entity_type(src)
        tgt_type = _infer_entity_type(tgt)

        # UNKNOWN 短路：無法推斷類型時跳過笛卡爾積匹配
        if src_type == "unknown" or tgt_type == "unknown":
            continue

        diag = generate_diagnostic_report(src_type, rel, tgt_type)
        key  = (src_type, rel, tgt_type)
        if key in seen:
            continue
        seen.add(key)

        if diag.matched_pattern:
            outcomes_str = " | ".join(diag.typical_outcomes[:3])
            lines.append(
                f"  • {src_type} × {rel} × {tgt_type} "
                f"→ 【{diag.matched_pattern.pattern_name}】({diag.domain})\n"
                f"    典型後果: {outcomes_str}\n"
                f"    先驗置信度: {diag.confidence_prior:.0%}"
            )

    return "\n".join(lines) if len(lines) > 1 else ""


# ---------------------------------------------------------------------------
# 內部工具：實體名 → EntityType 粗粒度映射
# ---------------------------------------------------------------------------

_ENTITY_NAME_HINTS: List[Tuple[List[str], str]] = [
    (["usa", "us", "china", "russia", "eu", "uk", "iran", "israel",
      "ukraine", "nato", "state", "country", "government", "nation", "republic"],
     "state"),
    (["fed", "ecb", "imf", "world bank", "bank", "fund", "reserve", "treasury",
      "financial", "central bank"], "financial_org"),
    (["oil", "gas", "coal", "mineral", "wheat", "semiconductor", "rare earth",
      "resource", "energy", "commodity"], "resource"),
    (["tech", "ai", "chip", "software", "platform", "algorithm", "5g", "cloud",
      "cyber", "internet", "system"], "tech"),
    (["corp", "inc", "ltd", "company", "firm", "enterprise", "startup"], "firm"),
    (["nato", "eu", "asean", "g7", "g20", "alliance", "coalition", "bloc"], "alliance"),
    (["militia", "paramilitary", "hamas", "hezbollah", "irgc", "wagner"], "paramilitary"),
    (["media", "news", "press", "broadcast", "propaganda"], "media"),
    (["un", "wto", "who", "iaea", "institution", "organization", "org"], "institution"),
    (["dollar", "euro", "yuan", "rmb", "ruble", "currency", "crypto"], "currency"),
    (["supply chain", "port", "factory", "logistics", "pipeline"], "supply_chain"),
    (["ideology", "belief", "movement", "nationalism", "marxism"], "ideology"),
    (["norm", "treaty", "law", "convention", "protocol", "rule"], "norm"),
    (["trust", "legitimacy", "credibility", "reputation"], "trust"),
    (["war", "conflict", "battle", "crisis", "attack"], "conflict"),
]


def _infer_entity_type(name: str) -> str:
    """從實體名稱推斷 EntityType 字符串（粗粒度）。"""
    name_lower = name.lower()
    for hints, entity_type in _ENTITY_NAME_HINTS:
        if any(h in name_lower for h in hints):
            return entity_type
    return "unknown"  # 無法推斷時返回 unknown，避免污染笛卡爾積匹配


# ===========================================================================
# 8. 逆元表 & 組合表（群論代數結構）
# ===========================================================================

def _build_inverse_table() -> Dict[str, str]:
    """從 CARTESIAN_PATTERN_REGISTRY 構建逆元表（模式名 → 逆模式名）。"""
    table: Dict[str, str] = {}
    for _, pattern in CARTESIAN_PATTERN_REGISTRY.items():
        if pattern.inverse_pattern:
            table[pattern.pattern_name] = pattern.inverse_pattern
    return table


# 逆元表：pattern_name → inverse_pattern_name
# 在模式注冊完成後由 _build_inverse_table() 初始化
inverse_table: Dict[str, str] = {}

# 組合表（Cayley Table）：(pattern_A, pattern_B) → 合成結果模式名
# 顯式定義兩個動力模式連續作用的高階效應，供 DeductionEngine 查詢
composition_table: Dict[Tuple[str, str], str] = {
    # 制裁 + 同盟 → 多邊制裁
    ("霸權制裁模式", "正式軍事同盟模式"):   "多邊聯盟制裁模式",
    # 軍事同盟 + 軍事打擊 → 代理衝突
    ("正式軍事同盟模式", "國家間武力衝突模式"): "非國家武裝代理衝突模式",
    # 制裁 + 技術封鎖 → 科技脫鉤
    ("霸權制裁模式", "實體清單技術封鎖模式"):  "科技脫鉤 / 技術鐵幕模式",
    # 信息戰 + 大國脅迫 → 代理衝突升級
    ("信息戰 / 敘事操控模式", "大國脅迫 / 威懾模式"): "非國家武裝代理衝突模式",
    # 金融孤立 + 制裁 → 主權债务危机（通用後果）
    ("金融孤立 / SWIFT 切斷模式", "霸權制裁模式"): "霸權制裁模式",
}


def get_inverse_pattern(pattern_name: str) -> Optional[str]:
    """查詢模式的逆元。

    Args:
        pattern_name: 動力模式名稱（中文）

    Returns:
        逆元模式名稱，若無逆元則返回 None。
    """
    return inverse_table.get(pattern_name)


def compose_patterns(pattern_a: str, pattern_b: str) -> Optional[str]:
    """查詢兩個模式合成的結果（Cayley Table 查詢）。

    Args:
        pattern_a: 第一個動力模式名稱
        pattern_b: 第二個動力模式名稱

    Returns:
        合成後的模式名稱，若無明確定義則返回 None。
    """
    return composition_table.get((pattern_a, pattern_b))


# ===========================================================================
# 9. 本體代數驗證
# ===========================================================================

def validate_inverses() -> List[str]:
    """驗證逆元表的一致性：若 A.inverse=B，則必須 B.inverse=A。

    Returns:
        驗證錯誤列表（空列表表示通過）。
    """
    errors: List[str] = []
    all_pattern_names = {p.pattern_name for p in CARTESIAN_PATTERN_REGISTRY.values()}

    for pattern in CARTESIAN_PATTERN_REGISTRY.values():
        inv = pattern.inverse_pattern
        if inv is None:
            continue

        # 逆模式名必須存在於模式庫中
        if inv not in all_pattern_names:
            errors.append(
                f"[MISSING_INVERSE] '{pattern.pattern_name}'.inverse = '{inv}'"
                f" but '{inv}' is not registered in CARTESIAN_PATTERN_REGISTRY"
            )
            continue

        # 逆模式的逆應指回原模式
        inv_pattern = next(
            (p for p in CARTESIAN_PATTERN_REGISTRY.values() if p.pattern_name == inv),
            None,
        )
        if inv_pattern and inv_pattern.inverse_pattern != pattern.pattern_name:
            errors.append(
                f"[ASYMMETRIC_INVERSE] '{pattern.pattern_name}'.inverse = '{inv}'"
                f" but '{inv}'.inverse = '{inv_pattern.inverse_pattern}'"
                f" (expected '{pattern.pattern_name}')"
            )

    return errors


def validate_composition_closure() -> List[str]:
    """驗證組合表中所有引用的模式名均已注冊。

    Returns:
        驗證錯誤列表（空列表表示通過）。
    """
    errors: List[str] = []
    all_pattern_names = {p.pattern_name for p in CARTESIAN_PATTERN_REGISTRY.values()}

    for (pa, pb), result in composition_table.items():
        for name in (pa, pb, result):
            if name not in all_pattern_names:
                errors.append(
                    f"[MISSING_PATTERN] composition_table references unknown"
                    f" pattern: '{name}'"
                )

    return errors


def run_ontology_validation(strict: bool = False) -> bool:
    """執行完整的本體代數驗證，並記錄結果。

    Args:
        strict: 若為 True，驗證失敗時拋出 ValueError；
                否則僅記錄警告（適合生產環境）。

    Returns:
        True 表示驗證通過，False 表示有錯誤（非 strict 模式）。

    Raises:
        ValueError: 僅在 strict=True 且驗證有誤時拋出。
    """
    inv_errors = validate_inverses()
    comp_errors = validate_composition_closure()
    all_errors = inv_errors + comp_errors

    if not all_errors:
        logger.info(
            "✅ Ontology algebra validation passed: %d patterns, %d inverses, %d compositions",
            len(CARTESIAN_PATTERN_REGISTRY),
            sum(1 for p in CARTESIAN_PATTERN_REGISTRY.values() if p.inverse_pattern),
            len(composition_table),
        )
        return True

    for err in all_errors:
        logger.warning("Ontology validation error: %s", err)

    if strict:
        raise ValueError(
            f"Ontology algebra validation failed with {len(all_errors)} error(s):\n"
            + "\n".join(all_errors)
        )

    logger.warning(
        "⚠️ Ontology algebra validation: %d error(s) found (non-strict mode – continuing)",
        len(all_errors),
    )
    return False


# ---------------------------------------------------------------------------
# Initialize inverse_table after all patterns are registered
# ---------------------------------------------------------------------------
inverse_table.update(_build_inverse_table())
