"""
intelligence/evented_pipeline.py  –  v3
=========================================
Evented Ontological Reasoning Pipeline

架构变更说明 (v3)：

问题：原版 Stage 3 让 LLM 从零开始写推演结论，confidence 是幻觉值。
     结果等同于"阅读文章后写摘要"，没有超出普通阅读范畴。

核心修复：引入「轨道+可达集合+贝叶斯」三层确定性推理

Stage 1 – 事件提取（不变）
  输入: text → 输出: events[]（至少 1 条，带 event_type / severity）

Stage 2a – 模式激活（增强）
  输入: events[] → 查 CARTESIAN_PATTERN_REGISTRY
  输出: active_patterns[]（每条带 confidence_prior, typical_outcomes）

Stage 2b – 转移枚举（新增）
  输入: active_patterns[] → 查 composition_table + inverse_table
  枚举全部可达模式集合 R = { C : (A,B)→C ∈ composition_table, A∈active }
  输出: top_transitions[]（按贝叶斯后验概率排序）

Stage 2c – Lie 代数状态向量（新增）
  输入: active_patterns[] → lie_algebra_space.compute_pattern_trajectory()
  输出: state_vector（8维 mean_vector，代表当前动力状态）

Stage 2d – 驱动因素聚合（新增，关键！）
  输入: active_patterns[] + their mechanism_class + typical_outcomes
  不依赖 LLM：从 relations 代数聚合 driving_factors[]
  逻辑：对每个 active_pattern 的 typical_outcomes 按 confidence_prior 加权
       → 取 top-3 outcome，构造 "因为 [mechanism_class]，导致 [outcome]" 陈述

Stage 3 – 贝叶斯结论生成（替换 LLM 自由写作）
  输入: state_vector + top_transitions + driving_factors
  确定性贝叶斯：
    P(alpha) = softmax(top_transitions[0].posterior_weight)
    P(beta)  = softmax(top_transitions[1].posterior_weight) if len>=2
  LLM 只被允许：填写 conclusion.text（解释已计算好的字段）
               不允许修改任何数值字段
  输出: conclusion{text, alpha_path, beta_path}
       credibility{verifiability, kg_consistency, composite_score, missing_evidence}

数据契约（response schema）：
  events[]           至少 1，来自 Stage 1
  active_patterns[]  至少 1（或附 explanation 说明为何 0）
  state_vector       8维 mean_vector（来自 Lie 代数）
  top_transitions[]  来自 composition_table / inverse_table（确定性）
  driving_factors[]  从 mechanism_class + typical_outcomes 聚合（确定性）
  conclusion         LLM 对上述字段的解释文本（不含数值）
  credibility        置信度来源：本体先验 × 贝叶斯后验（不是幻觉）
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from intelligence.pattern_i18n import display_pattern, has_cjk, strip_cjk  # noqa: E402

logger = logging.getLogger(__name__)

# ===========================================================================
# 公开契约常量
# ===========================================================================

# T0: confidence below this → hard-reject (event never enters pipeline)
_T0_CONF_THRESHOLD: float = 0.20
# T2: confidence at or above this (and no inferred fields) → T2 tier
_T2_CONF_THRESHOLD: float = 0.70
# Minimum quote length for T2 classification (chars)
_MIN_QUOTE_LEN: int = 15
# Maximum confidence assigned to fallback events (clamped before entering the pipeline)
_FALLBACK_MAX_CONFIDENCE: float = 0.35

# ===========================================================================
# Outcome catalogue: outcome_id → professional English phrasing
# ===========================================================================

OUTCOME_CATALOG: Dict[str, str] = {
    # ── Geopolitical / coercive ──────────────────────────────────────────────
    "target_isolation":               "The targeted actor faces progressive exclusion from multilateral frameworks and diplomatic circuits",
    "collective_defence_formation":   "Aligned states form a coordinated collective defence posture",
    "sanctions_escalation":           "A broadening multilateral sanctions regime takes hold, tightening access to finance and technology",
    "alliance_consolidation":         "Formal and informal alliance commitments consolidate around shared threat perception",
    "diplomatic_rupture":             "Diplomatic relations fracture, with official representatives expelled or recalled",
    "ceasefire_negotiation":          "Parties move toward a negotiated ceasefire or temporary conflict pause",
    "military_deterrence_signal":     "Military posturing intensifies as deterrence signals are deployed along contested boundaries",
    "proxy_conflict_expansion":       "Conflict expands through proxy actor networks, diffusing across borders",
    # From relation_schema typical_outcomes
    "supply_chain_fragmentation":     "Supply chains fracture as actors reroute sourcing, tighten export controls, and build parallel networks",
    "alliance_shift":                 "Sanctioned actors pivot toward alternative partners, reshaping alliance geometry",
    "currency_substitution":          "Alternative settlement currencies and bilateral swap arrangements emerge as dollar alternatives",
    "domestic_consolidation":         "The targeted state consolidates internally, reducing reliance on external markets and technology",
    "third_party_arbitrage":          "Third-party states exploit the gap between sanctioners and target, extracting arbitrage rents",
    "supply_chain_decoupling":        "Supply chains decouple as sourcing relocates away from restricted suppliers",
    "domestic_substitution_push":     "The targeted actor accelerates domestic production to replace blocked imports",
    "third_country_re-export":        "Controlled goods re-enter the target market via third-country transshipment",
    "technology_gap_widening":        "The technology capability gap between sanctioner and target widens over time",
    "alliance_activation":            "Mutual defence commitments activate, drawing allied states into the conflict",
    "sanctions_cascade":              "Sanctions spread rapidly across multiple jurisdictions, cascading into a global regime",
    "refugee_displacement":           "Large-scale population displacement creates regional humanitarian and security pressures",
    "energy_market_disruption":       "Energy supply chains disrupt, triggering price spikes and allocation crises across importing states",
    "regime_change_attempt":          "External actors pursue regime change through overt or covert pressure on the governing authority",
    "policy_capitulation":            "The targeted actor yields to coercive pressure, shifting policy to accommodate the coercer's demands",
    "counter_alliance_formation":     "A counter-alliance forms in direct response to coercive pressure, multiplying the coercer's adversaries",
    "credibility_erosion":            "The coercing actor's deterrence credibility erodes as threats fail to produce the expected compliance",
    "arms_race_acceleration":         "An accelerating arms race unfolds as both sides expand military capabilities",
    "multilateral_compliance_cost":   "Alliance members bear rising compliance costs as sanctions tighten business and financial links",
    "sanctions_fatigue":              "Coalition cohesion weakens over time as member states diverge on compliance and enforcement",
    "gray_zone_evasion":              "The targeted actor deploys grey-zone tactics to evade sanctions and sustain restricted access",
    "state_sponsor_exposure":         "Covert state sponsorship of proxy actors is exposed, inviting sanctions and international condemnation",
    "asymmetric_escalation":          "Non-state actors escalate asymmetrically, raising costs for the state through unconventional attacks",
    "civilian_infrastructure_targeting": "Civilian infrastructure becomes a target, deepening the humanitarian toll and international pressure",
    "regional_spillover":             "Violence and instability spill across borders, destabilising neighbouring states",
    "collective_defense_deterrence":  "Collective defence commitments provide credible deterrence, raising the cost of aggression",
    "alliance_entrapment_risk":       "Alliance obligations pull members into conflicts they would not otherwise enter",
    "burden_sharing_friction":        "Persistent friction over defence spending and burden-sharing strains alliance cohesion",
    "adversary_counter_coalition":    "The adversary assembles a counter-coalition in direct response to the alliance",
    "norm_cascade":                   "International norms spread rapidly across jurisdictions as states align with the new standard",
    "competing_norm_fragmentation":   "Competing normative frameworks fracture the multilateral order into rival blocs",
    "soft_power_accumulation":        "The norm-setting actor accumulates soft power and agenda-setting influence",
    "free_rider_problem":             "States benefit from the norm without contributing to its enforcement, eroding collective action",
    # ── Economic / financial ─────────────────────────────────────────────────
    "mutual_vulnerability_lock_in":   "Deep trade interdependence creates mutual vulnerabilities that lock both actors into the relationship",
    "leverage_accumulation":          "The surplus actor accumulates economic leverage over the deficit counterpart",
    "currency_influence_expansion":   "The dominant partner's currency expands its influence across regional payment systems",
    "decoupling_cost_deterrence":     "The high cost of decoupling deters either party from initiating an economic rupture",
    "emerging_market_capital_outflow":"Capital flows out of emerging markets as tightening policy strengthens the reserve currency",
    "dollar_strengthening":           "The reserve currency strengthens, compressing margins for commodity importers and debtors",
    "debt_service_cost_spike":        "External debt service costs spike as interest rates rise and currencies weaken",
    "commodity_price_denominated_shift": "Commodity pricing shifts toward alternative currency denominations",
    "payment_system_fragmentation":   "The global payments architecture splinters as sanctioned actors build parallel settlement systems",
    "alternative_settlement_push":    "Alternative settlement mechanisms — including digital currencies and bilateral arrangements — gain traction",
    "hyperinflation_risk":            "Monetary instability escalates toward hyperinflation risk in the isolated economy",
    "commodity_barter_resurgence":    "Barter and commodity-based exchange re-emerge as sanctions block conventional payment channels",
    "supply_shock_vulnerability":     "Single-source dependencies create acute vulnerability to supply shocks and coercive cutoffs",
    "just_in_case_inventory_build":   "Firms shift from just-in-time to just-in-case inventory strategies, raising costs",
    "near_shoring_acceleration":      "Production nearshores as firms prioritise supply chain resilience over cost efficiency",
    "margin_compression_from_hedging":"Hedging and diversification costs compress margins across the affected supply chain",
    "energy_coercion_episodes":       "The resource supplier weaponises energy access, triggering coercion episodes against dependent importers",
    "importing_country_diversification": "Importing states accelerate diversification away from a single dominant supplier",
    "pipeline_geopolitics":           "Control over pipeline infrastructure becomes a central instrument of geopolitical leverage",
    "green_transition_acceleration":  "Import dependence spurs accelerated investment in domestic renewable energy capacity",
    # ── Technology ──────────────────────────────────────────────────────────
    "standard_adoption_lock_in":      "A dominant technology standard locks in, foreclosing competing approaches and creating durable advantage",
    "competing_standard_fragmentation": "Competing incompatible technology standards fragment the global ecosystem into rival blocs",
    "licensing_revenue_accumulation": "The standard-setting actor accumulates substantial licensing revenue from global adoption",
    "supply_chain_design_control":    "Control over supply chain architecture concentrates in the hands of the standard-setter",
    "parallel_tech_stack_emergence":  "Parallel technology stacks emerge along geopolitical lines, reducing interoperability",
    "innovation_efficiency_loss":     "Market segmentation reduces innovation efficiency as knowledge flows are severed",
    "semiconductor_chokepoint":       "Strategic chokepoints in the semiconductor supply chain give the holder asymmetric leverage",
    "supplier_pricing_power":         "Oligopoly suppliers strengthen pricing power as diversification alternatives remain limited",
    "buyer_diversification_effort":   "Technology buyers accelerate efforts to diversify sourcing and reduce single-supplier exposure",
    "technology_transfer_leverage":   "Access to critical technology becomes a bargaining chip in broader diplomatic negotiations",
    "digital_sovereignty_push":       "States accelerate digital sovereignty initiatives, building nationally controlled infrastructure",
    # ── Information / institutional ─────────────────────────────────────────
    "public_opinion_polarization":    "Public opinion polarises sharply as competing narratives drive epistemic fragmentation",
    "institutional_trust_erosion":    "Trust in established institutions erodes as information operations undermine credibility",
    "counter_narrative_escalation":   "Rival information operations escalate, each side deploying counter-narratives at scale",
    "epistemic_fragmentation":        "Shared factual foundations fracture, making coordinated international response harder",
    "regulatory_compliance_cost_spike": "Compliance costs spike as firms navigate expanding and often conflicting regulatory regimes",
    "regulatory_arbitrage":           "Firms exploit divergence between jurisdictions, relocating activity to avoid restrictive regimes",
    "market_access_conditionality":   "Market access becomes conditional on regulatory alignment, creating leverage over trade partners",
    "industry_consolidation":         "Smaller actors exit the market as rising compliance costs accelerate industry consolidation",
    # ── Generic fallbacks ────────────────────────────────────────────────────
    "structural_realignment":         "Established economic and political relationships realign under sustained structural pressure",
    "structural_disruption":          "The existing institutional or market order faces disruption from accumulating structural stress",
    "financial_contagion":            "Financial stress spreads across borders, exposing correlated counterparty vulnerabilities",
    "capital_flow_restriction":       "Capital flow restrictions tighten between targeted jurisdictions, fragmenting financial linkages",
    "supply_chain_restructuring":     "Supply chains restructure toward resilience, accepting higher costs to reduce concentrated exposure",
    "joint_rd_resumption":            "Joint research collaboration resumes across previously segmented markets",
    "technology_transfer_flow":       "Cross-border technology transfer flows resume after a period of restriction",
    "innovation_spillover":           "Positive innovation spillovers spread across previously segmented markets",
    "price_competition":              "Intensifying price competition erodes incumbent supplier margins",
    "buyer_bargaining_increase":      "Technology buyers gain bargaining leverage as alternative sources become available",
    "innovation_acceleration":        "Competitive pressure accelerates the pace of innovation across the ecosystem",
    "standard_displacement":          "The incumbent technology standard is displaced by an emerging alternative",
    "market_share_redistribution":    "Market share redistributes across the technology ecosystem as power dynamics shift",
    "technology_fragmentation":       "The technology ecosystem fragments along domain or regional lines",
    "unknown":                        "Available signals are insufficient to determine a dominant trajectory",
}


def _outcome_phrase(outcome_id: str) -> str:
    """Return professional English phrasing for a given outcome_id."""
    if not outcome_id:
        return "an unspecified structural shift"
    phrase = OUTCOME_CATALOG.get(outcome_id)
    if phrase:
        return phrase
    # Humanize snake_case fallback
    return outcome_id.replace("_", " ")


class EventType:
    """Canonical event-type string constants (used by rule-based extractor and tests)."""
    SANCTION_IMPOSED       = "sanction_imposed"
    EXPORT_CONTROL         = "export_control"
    MILITARY_STRIKE        = "military_strike"
    CLASHES                = "clashes"
    MOBILIZATION           = "mobilization"
    CEASEFIRE              = "ceasefire"
    COERCIVE_WARNING       = "coercive_warning"
    WITHDRAWAL             = "withdrawal"
    DIPLOMATIC_EVENT       = "diplomatic_event"
    ECONOMIC_CRISIS        = "economic_crisis"
    TECHNOLOGY_BREAKTHROUGH = "technology_breakthrough"
    SPACE_MISSION          = "space_mission"
    MARKET_ENTRY           = "market_entry"
    PRODUCT_FEATURE_LAUNCH = "product_feature_launch"
    COMPETITIVE_POSITIONING = "competitive_positioning"
    PLATFORM_STRATEGY      = "platform_strategy"


# ===========================================================================
# 数据结构
# ===========================================================================

@dataclass
class EventNode:
    """Stage 1 输出：单条事件节点。"""
    event_type:  str
    severity:    str
    description: str
    entities:    Dict[str, List[str]] = field(default_factory=dict)
    confidence:  float = 0.70
    source_quote: str = ""      # 原文支撑片段
    compound:    bool = False   # 是否来自复合规则


@dataclass
class PatternNode:
    """Stage 2a 输出：激活的本体模式节点。"""
    pattern_name:     str
    domain:           str
    mechanism_class:  str
    confidence_prior: float
    typical_outcomes: List[str]
    source_event:     str        # 触发该模式的事件类型
    # Stage 2c 附加：向量坐标
    vector_coords:    Optional[List[float]] = None
    dominant_dims:    Optional[List[str]]   = None


@dataclass
class TransitionEdge:
    """Stage 2b 输出：composition_table 中的一条转移边。"""
    from_pattern_a:   str
    from_pattern_b:   str
    to_pattern:       str          # composition_table[(A,B)] = C
    transition_type:  str          # "compose" | "inverse" | "self"
    # 贝叶斯后验权重 = confidence_prior(A) × confidence_prior(B) × lie_similarity
    prior_a:          float
    prior_b:          float
    lie_similarity:   float        # 向量加法与目标模式的余弦相似度
    posterior_weight: float        # = prior_a × prior_b × lie_similarity
    typical_outcomes: List[str]    # 目标模式的典型后果
    description:      str          # 人类可读描述


@dataclass
class DrivingFactor:
    """Stage 2d 输出：聚合驱动因素。"""
    factor:           str          # 驱动力陈述
    mechanism_class:  str          # 来源机制类
    supporting_patterns: List[str] # 支撑该驱动力的模式名
    weight:           float        # 聚合权重（加权 confidence_prior 之和）
    outcomes:         List[str]    # 该驱动力的典型后果（top 3）


@dataclass
class PipelineResult:
    """完整 pipeline 输出。"""
    # Stage 1
    events:          List[Dict[str, Any]]
    # Stage 2a
    active_patterns: List[Dict[str, Any]]
    # Stage 2b
    derived_patterns: List[Dict[str, Any]]    # 向后兼容：= top_transitions[0].to_pattern
    top_transitions: List[Dict[str, Any]]      # 新增：完整转移列表
    # Stage 2c
    state_vector:    Dict[str, Any]            # 新增：8维状态向量
    # Stage 2d
    driving_factors: List[Dict[str, Any]]      # 新增：聚合驱动因素
    # Stage 3
    conclusion:      Dict[str, Any]
    credibility:     Dict[str, Any]
    # 兼容字段
    probability_tree: Dict[str, Any] = field(default_factory=dict)


# ===========================================================================
# 公开工具函数（Public Utility Functions）
# ===========================================================================

def _stable_id(event_type: str, quote: str) -> str:
    """Return a stable 8-char hex ID from event_type + quote content."""
    raw = f"{event_type}::{quote}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]


def infer_entity_type_lightweight(name: str) -> str:
    """Classify an entity name into a broad type without external dependencies."""
    if not name or not name.strip():
        return "unknown"
    n = name.strip()
    # Firm / corporation
    if re.search(r"\b(Inc|Corp|Ltd|Holdings|Group|Co\.|Company)\b", n):
        return "firm"
    # Alliances / multilateral bodies
    if re.search(r"\b(NATO|EU|G7|G20|UN|ASEAN|BRICS|AU|WTO|IMF|SCO)\b", n):
        return "alliance"
    # State keywords
    if re.search(
        r"\b(government|ministry|department|senate|congress|parliament|"
        r"China|US|USA|Russia|Germany|France|UK|Japan|India|Iran|Israel)\b",
        n, re.IGNORECASE,
    ):
        return "state"
    # Person heuristics: 2-3 Title-Case tokens
    tokens = n.split()
    if 2 <= len(tokens) <= 3 and all(t[0].isupper() for t in tokens if t):
        return "person"
    return "unknown"


# ---------------------------------------------------------------------------
# Trigger-keyword patterns for rule-based extraction
# ---------------------------------------------------------------------------

_RULE_EVENT_PATTERNS: List[Tuple[str, str, float]] = [
    # (regex, EventType constant, base_confidence)
    (r"\bsanction(s|ed)?\b|\bimpose[sd]?\b.{0,30}\bsanction", EventType.SANCTION_IMPOSED, 0.80),
    (r"\bexport control\b|\bentity list\b|\btech ban\b|\bchip ban\b", EventType.EXPORT_CONTROL, 0.78),
    (r"\bairstrike[s]?\b|\bbombing\b|\bmissile strike\b|\bstrike[sd]?.{0,20}target", EventType.MILITARY_STRIKE, 0.82),
    (r"\bclash(es|ed)?\b|\bfight(ing)?\b|\bskirmish", EventType.CLASHES, 0.75),
    (r"\bmobiliz(e|ed|ation)\b|\btroops? (deploy|mov|mass)\b", EventType.MOBILIZATION, 0.72),
    (r"\bceasefire\b|\bpeace (deal|agreement|accord)\b|\btruce\b", EventType.CEASEFIRE, 0.85),
    (r"\bthreaten(ed|s)?\b|\bwarn(ed|ing)?\b.{0,30}\b(strike|attack|force)", EventType.COERCIVE_WARNING, 0.68),
    (r"\bwithdraw(al|n|ing|s)?\b|\bwithdrew\b|\bpull(ed|ing)? out\b|\bexit(ed)?\b.{0,20}\btroop", EventType.WITHDRAWAL, 0.75),
    (r"\blaunch(ed|ing)?\b.{0,40}\b(technolog|space|mission|satellite)\b"
     r"|\b(space mission|lunar|orbit|astronaut|spacecraft|rocket|liftoff|Kennedy Space|Artemis|SpaceX|NASA.{0,20}launch)\b",
     EventType.SPACE_MISSION, 0.80),
    (r"\bbreakthrough\b|\binnovation\b|\b(technolog.{0,20}breakthrough)\b",
     EventType.TECHNOLOGY_BREAKTHROUGH, 0.70),
    (r"\bmarket entry\b|\bexpand.{0,20}\bmarket\b|\bexpand.{0,30}\binto\b.{0,30}(hosting|podcast|streaming)\b",
     EventType.MARKET_ENTRY, 0.68),
    (r"\b(feature launch|product launch|new (product|feature|service)|launch of a new|new audio|new (tool|capability))\b"
     r"|\blaunch.{0,50}(creator|monetize|subscri)\b|\bnew.{0,30}(audio|podcast|feature).{0,30}(lets|allow|creat)\b",
     EventType.PRODUCT_FEATURE_LAUNCH, 0.70),
    (r"\bcompetitor\b|\bcompetitive\b|\btakes? aim\b|\brival\b|\btaking aim\b", EventType.COMPETITIVE_POSITIONING, 0.65),
    (r"\bplatform\b.{0,50}(strategy|ecosystem|subscription|tiers?|bundl)\b|\bsubscription tiers?\b",
     EventType.PLATFORM_STRATEGY, 0.63),
]

_ACTOR_TARGET_KEYS = {"actor", "target"}


def extract_events_rule_based(text: str) -> List[Dict[str, Any]]:
    """
    Deterministic rule-based event extraction. Returns a list of event dicts
    each with keys: id, type, args, evidence, confidence.

    Empty / off-topic text returns [].
    """
    if not text or not text.strip():
        return []

    results: List[Dict[str, Any]] = []
    seen_ids: set = set()

    for pattern_re, etype, base_conf in _RULE_EVENT_PATTERNS:
        for m in re.finditer(pattern_re, text, re.IGNORECASE):
            # Extract a surrounding window as evidence quote
            start = max(0, m.start() - 30)
            end   = min(len(text), m.end() + 80)
            quote = text[start:end].strip()

            eid = _stable_id(etype, quote)
            if eid in seen_ids:
                continue
            seen_ids.add(eid)

            results.append({
                "id":         eid,
                "type":       etype,
                "args":       {},
                "evidence":   {"quote": quote},
                "confidence": round(base_conf, 4),
            })

    return results


def extract_events_llm(text: str, llm_service: Any) -> List[Dict[str, Any]]:
    """
    LLM-based event extraction. Falls back to [] on any error.
    Returns list of event dicts with id, type, args, evidence, confidence.
    """
    if llm_service is None:
        return []

    prompt = (
        "You are an event extractor for geopolitical and economic news.\n"
        "Extract all significant events from the following text.\n"
        "Return a JSON array where each item has:\n"
        '  {{"type": "<event_type>", "args": {{}}, "evidence": {{"quote": "<relevant excerpt>"}}, "confidence": 0.8}}\n'
        "Event types include: sanction_imposed, export_control, military_strike, ceasefire, "
        "coercive_warning, withdrawal, clashes, mobilization, diplomatic_event, economic_crisis, "
        "technology_breakthrough, market_entry, product_feature_launch, competitive_positioning.\n"
        "Text:\n"
        f"{text[:1500]}\n"
        "Return ONLY a JSON array, no other text."
    )
    try:
        raw = llm_service.call(prompt=prompt, temperature=0.1, max_tokens=800)
        raw_str = str(raw).strip()
        # Strip markdown code fences if present
        raw_str = re.sub(r"^```(?:json)?\s*", "", raw_str)
        raw_str = re.sub(r"\s*```$", "", raw_str)
        parsed = json.loads(raw_str)
        if not isinstance(parsed, list):
            return []
        out: List[Dict[str, Any]] = []
        for ev in parsed:
            if not isinstance(ev, dict):
                continue
            etype = str(ev.get("type", "unknown")).strip()
            quote = str((ev.get("evidence") or {}).get("quote", "")).strip()
            eid   = ev.get("id") or _stable_id(etype, quote)
            out.append({
                "id":         eid,
                "type":       etype,
                "args":       ev.get("args") or {},
                "evidence":   {"quote": quote},
                "confidence": float(ev.get("confidence", 0.65)),
            })
        return out
    except Exception as exc:
        logger.debug("extract_events_llm failed: %s", exc)
        return []


def extract_events(text: str, llm_service: Any = None) -> List[Dict[str, Any]]:
    """
    Hybrid extraction: rule-based first, LLM fills gaps.
    Always returns at least [] (never raises).
    """
    rule_events = extract_events_rule_based(text)
    llm_events  = extract_events_llm(text, llm_service) if llm_service else []

    # Merge: prefer rule-based, add unique LLM events
    seen_ids = {ev["id"] for ev in rule_events}
    merged   = list(rule_events)
    for ev in llm_events:
        if ev.get("id") and ev["id"] not in seen_ids:
            merged.append(ev)
            seen_ids.add(ev["id"])
    return merged


# ---------------------------------------------------------------------------
# Event post-processing: T0 reject, confidence folding, tier assignment
# ---------------------------------------------------------------------------

# Keywords that validate an event type (if present in quote, no penalty)
_EVENT_TRIGGER_KEYWORDS: Dict[str, List[str]] = {
    EventType.SANCTION_IMPOSED:       ["sanction", "penalty", "restrict", "ban", "penalt"],
    EventType.EXPORT_CONTROL:         ["export control", "entity list", "ban", "restrict"],
    EventType.MILITARY_STRIKE:        ["strike", "airstrike", "bomb", "missile", "attack"],
    EventType.CLASHES:                ["clash", "fight", "skirmish", "battle", "conflict"],
    EventType.MOBILIZATION:           ["mobiliz", "deploy", "troops", "forces"],
    EventType.CEASEFIRE:              ["ceasefire", "truce", "peace", "accord"],
    EventType.COERCIVE_WARNING:       ["warn", "threaten", "ultimatum", "demand"],
    EventType.WITHDRAWAL:             ["withdraw", "pull out", "exit", "retreat"],
    EventType.TECHNOLOGY_BREAKTHROUGH: ["breakthrough", "innovation", "launch", "technolog"],
    EventType.MARKET_ENTRY:           ["market", "entry", "expand"],
    EventType.PRODUCT_FEATURE_LAUNCH: ["launch", "feature", "product", "service"],
    EventType.COMPETITIVE_POSITIONING: ["competitor", "rival", "competit"],
    EventType.PLATFORM_STRATEGY:      ["platform", "ecosystem", "subscription"],
}


def _has_trigger_keyword(event_type: str, quote: str) -> bool:
    """Return True if the quote contains at least one trigger keyword for the event type."""
    triggers = _EVENT_TRIGGER_KEYWORDS.get(event_type, [])
    ql = quote.lower()
    return any(kw in ql for kw in triggers)


def postprocess_events(
    candidates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Post-process a list of raw candidate event dicts:
      1. Strip whitespace from type, quote, args strings
      2. Assign stable ID if missing
      3. Deduplicate by ID
      4. Fold confidence (inferred_fields → *0.7, actor/target keys → *0.8 each,
         missing trigger keyword → *0.7)
      5. Hard-reject (T0) events whose folded confidence < _T0_CONF_THRESHOLD
      6. Assign tier: T2 if conf >= _T2_CONF_THRESHOLD AND no inferred_fields, else T1
      7. If quote is empty/short/unverified, add to verification_gap and downgrade to T1

    Returns the filtered and annotated list.
    """
    seen_ids: Dict[str, Dict[str, Any]] = {}  # id → accepted event
    rejected_ids: set = set()  # ids of hard-rejected events

    for raw in candidates:
        if not isinstance(raw, dict):
            continue

        # ── 1. Normalize strings ─────────────────────────────────────────
        ev = dict(raw)
        ev["type"] = str(ev.get("type", "unknown")).strip()

        ev_args = ev.get("args") or {}
        if isinstance(ev_args, dict):
            ev["args"] = {k: str(v).strip() if isinstance(v, str) else v
                          for k, v in ev_args.items()}

        ev_evidence = ev.get("evidence") or {}
        quote = str(ev_evidence.get("quote", "")).strip()
        ev["evidence"] = {**ev_evidence, "quote": quote}

        # ── 2. Assign stable ID ──────────────────────────────────────────
        if not ev.get("id"):
            ev["id"] = _stable_id(ev["type"], quote)

        # ── 3. Deduplicate (keep first occurrence, we process in order) ──
        eid = ev["id"]
        if eid in seen_ids or eid in rejected_ids:
            continue

        # ── 4. Confidence folding ────────────────────────────────────────
        conf = float(ev.get("confidence", 0.0))
        inferred = ev.get("inferred_fields") or []
        verification_gap: List[str] = list(ev.get("verification_gap") or [])

        if inferred:
            conf *= 0.7
            for key in inferred:
                if str(key).lower() in _ACTOR_TARGET_KEYS:
                    conf *= 0.8

        if not _has_trigger_keyword(ev["type"], quote):
            conf *= 0.7

        conf = round(conf, 4)

        # ── 5. T0 hard-reject ────────────────────────────────────────────
        if conf <= 0 or conf < _T0_CONF_THRESHOLD:
            rejected_ids.add(eid)
            continue

        # ── 6. Quote quality checks (add gaps, but don't hard-reject) ────
        if not quote:
            verification_gap.append("quote missing – event not directly observed")
            conf = min(conf, _T2_CONF_THRESHOLD - 0.01)
        elif len(quote) < _MIN_QUOTE_LEN:
            verification_gap.append(
                f"quote too short ({len(quote)} < {_MIN_QUOTE_LEN} chars) – limited evidence"
            )
            conf = min(conf, _T2_CONF_THRESHOLD - 0.01)

        # ── 7. Tier assignment ───────────────────────────────────────────
        has_inferred = bool(inferred)
        if conf >= _T2_CONF_THRESHOLD and not has_inferred:
            tier = "T2"
        else:
            tier = "T1"
            if has_inferred and not any("inferred" in g for g in verification_gap):
                verification_gap.append("one or more fields inferred (not directly stated)")

        ev["confidence"]       = conf
        ev["tier"]             = tier
        ev["verification_gap"] = verification_gap
        seen_ids[eid]          = ev

    return list(seen_ids.values())


def _fallback_top_events(
    candidates: List[Dict[str, Any]],
    max_keep: int = 3,
) -> List[Dict[str, Any]]:
    """
    When all candidates are T0-rejected, keep the top max_keep candidates
    by raw confidence (ignoring folding), clamped to T1 max confidence and
    tagged with a 'fallback' verification gap.

    Returns [] if candidates is empty or all have confidence <= 0.
    """
    valid = [c for c in candidates if float(c.get("confidence", 0)) > 0]
    if not valid:
        return []

    top = sorted(valid, key=lambda c: c["confidence"], reverse=True)[:max_keep]
    result = []
    for ev in top:
        ev2 = dict(ev)
        ev2["confidence"] = round(min(float(ev2.get("confidence", 0.3)), _FALLBACK_MAX_CONFIDENCE), 4)
        ev2["tier"]       = "T1"
        gap = list(ev2.get("verification_gap") or [])
        if not any("fallback" in g for g in gap):
            gap.append("fallback event – all stronger candidates rejected by T0 filter")
        ev2["verification_gap"] = gap
        if not ev2.get("id"):
            ev2["id"] = _stable_id(ev2.get("type", "unknown"), "")
        result.append(ev2)
    return result


# ---------------------------------------------------------------------------
# derive_active_patterns: event dicts → active pattern dicts
# ---------------------------------------------------------------------------

# Tier-aware event-type → pattern name mapping
# T2 events map to "strong" patterns, T1 events map to "weak" / policy patterns
_T2_EVENT_TO_PATTERNS: Dict[str, List[str]] = {
    EventType.SANCTION_IMPOSED:        ["霸權制裁模式"],
    EventType.EXPORT_CONTROL:          ["實體清單技術封鎖模式"],
    EventType.MILITARY_STRIKE:         ["國家間武力衝突模式"],
    EventType.CLASHES:                 ["國家間武力衝突模式", "非國家武裝代理衝突模式"],
    EventType.MOBILIZATION:            ["大國脅迫 / 威懾模式"],
    EventType.CEASEFIRE:               ["停火 / 和平協議模式"],
    EventType.COERCIVE_WARNING:        ["大國脅迫 / 威懾模式"],
    EventType.WITHDRAWAL:              ["外交讓步 / 去升級模式"],
    EventType.SPACE_MISSION:           ["技術突破 / 太空探索模式", "技術標準主導模式"],
    EventType.TECHNOLOGY_BREAKTHROUGH: ["技術標準主導模式", "關鍵零部件寡頭供應模式"],
    EventType.MARKET_ENTRY:            ["產品能力擴張模式"],
    EventType.PRODUCT_FEATURE_LAUNCH:  ["產品能力擴張模式", "平台競爭 / 生態位擴張模式"],
    EventType.COMPETITIVE_POSITIONING: ["平台競爭 / 生態位擴張模式"],
    EventType.PLATFORM_STRATEGY:       ["平台競爭 / 生態位擴張模式", "創作者經濟整合模式"],
}

_T1_EVENT_TO_PATTERNS: Dict[str, List[str]] = {
    EventType.SANCTION_IMPOSED:        ["政策性貿易限制模式"],
    EventType.EXPORT_CONTROL:          ["跨國監管 / 合規約束模式"],
    EventType.MILITARY_STRIKE:         ["非國家武裝代理衝突模式"],
    EventType.CLASHES:                 ["非國家武裝代理衝突模式"],
    EventType.MOBILIZATION:            ["非國家武裝代理衝突模式"],
    EventType.CEASEFIRE:               ["停火 / 和平協議模式"],
    EventType.COERCIVE_WARNING:        ["信息戰 / 敘事操控模式"],
    EventType.WITHDRAWAL:              ["外交讓步 / 去升級模式"],
    EventType.SPACE_MISSION:           ["技術突破 / 太空探索模式"],
    EventType.TECHNOLOGY_BREAKTHROUGH: ["技術標準主導模式"],
    EventType.MARKET_ENTRY:            ["產品能力擴張模式"],
    EventType.PRODUCT_FEATURE_LAUNCH:  ["產品能力擴張模式"],
    EventType.COMPETITIVE_POSITIONING: ["平台競爭 / 生態位擴張模式"],
    EventType.PLATFORM_STRATEGY:       ["平台競爭 / 生態位擴張模式"],
}

# Fallback for unknown event types
_DEFAULT_PATTERNS_T2 = ["雙邊貿易依存模式"]
_DEFAULT_PATTERNS_T1 = ["雙邊貿易依存模式"]


def derive_active_patterns(
    events: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Map post-processed event dicts to active pattern dicts.

    Each output item has:
      pattern, from_event (event ID), tier, inferred, confidence

    T2 events activate strong patterns; T1 events activate weak/policy patterns.
    No duplicate pattern names are emitted.
    """
    seen_patterns: set = set()
    result: List[Dict[str, Any]] = []

    for ev in events:
        etype    = str(ev.get("type", "unknown")).strip()
        eid      = ev.get("id", _stable_id(etype, ""))
        tier     = ev.get("tier", "T2")
        conf     = float(ev.get("confidence", 0.65))
        inferred = bool(ev.get("inferred_fields"))

        mapping = _T2_EVENT_TO_PATTERNS if tier == "T2" else _T1_EVENT_TO_PATTERNS
        patterns = mapping.get(etype)
        if not patterns:
            patterns = _DEFAULT_PATTERNS_T2 if tier == "T2" else _DEFAULT_PATTERNS_T1

        for pname in patterns:
            if pname in seen_patterns:
                continue
            seen_patterns.add(pname)
            result.append({
                "pattern":    pname,
                "from_event": eid,
                "tier":       tier,
                "inferred":   inferred,
                "confidence": round(conf * (0.9 if inferred else 1.0), 4),
            })

    return result


# ---------------------------------------------------------------------------
# derive_composed_patterns: active pattern dicts → derived pattern dicts
# ---------------------------------------------------------------------------

def derive_composed_patterns(
    active: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Look up all (A, B) → C entries in composition_table where A or B is in active.

    Each derived entry has:
      derived, rule, inputs, derived_tier, derived_inferred, derived_confidence

    derived_confidence = min(conf_A, conf_B) * 0.9 (* 0.8 if any input is inferred)
    derived_tier: T2 if derived_confidence >= _T2_CONF_THRESHOLD else T1
    """
    try:
        from ontology.relation_schema import composition_table as _ctable
    except ImportError:
        logger.warning("derive_composed_patterns: relation_schema unavailable")
        return []

    active_map: Dict[str, Dict[str, Any]] = {
        ap["pattern"]: ap for ap in active if ap.get("pattern")
    }
    active_names = set(active_map.keys())
    seen_derived: set = set()
    result: List[Dict[str, Any]] = []

    for (pa, pb), pc in _ctable.items():
        if pa not in active_names and pb not in active_names:
            continue
        if pc in seen_derived:
            continue

        ap_a = active_map.get(pa) or {}
        ap_b = active_map.get(pb) or {}
        conf_a = float(ap_a.get("confidence", 0.60))
        conf_b = float(ap_b.get("confidence", 0.60))
        inferred_a = bool(ap_a.get("inferred"))
        inferred_b = bool(ap_b.get("inferred"))
        any_inferred = inferred_a or inferred_b

        derived_conf = round(min(conf_a, conf_b) * 0.9 * (0.8 if any_inferred else 1.0), 4)
        derived_tier = "T2" if derived_conf >= _T2_CONF_THRESHOLD else "T1"

        seen_derived.add(pc)
        result.append({
            "derived":           pc,
            "rule":              f"{pa} + {pb} -> {pc}",
            "inputs":            [pa, pb],
            "derived_tier":      derived_tier,
            "derived_inferred":  any_inferred,
            "derived_confidence": derived_conf,
            # backward-compatible aliases
            "pattern":           pc,
            "pattern_name":      pc,
        })

    return result


# ---------------------------------------------------------------------------
# compute_credibility: standalone credibility computation
# ---------------------------------------------------------------------------

def compute_credibility(
    text: str,
    active: List[Dict[str, Any]],
    derived: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Compute a credibility report from the text and active/derived patterns.

    Returns a dict with:
      verifiability_score, kg_consistency_score, missing_evidence,
      contradictions, supporting_paths, hypothesis_ratio, overall_score
    """
    # ── Verifiability anchors ────────────────────────────────────────────
    has_date = bool(re.search(
        r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}|\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b",
        text, re.IGNORECASE,
    ))
    has_inst = bool(re.search(
        r"\b(NASA|ESA|Pentagon|NATO|UN|Congress|Senate|Ministry|Reuters|BBC|OFAC|Treasury)\b",
        text, re.IGNORECASE,
    ))
    has_url  = bool(re.search(r"https?://\S+|official|report|document", text, re.IGNORECASE))
    verifiability_score = round(0.30 + 0.25 * has_date + 0.25 * has_inst + 0.20 * has_url, 4)

    missing_evidence: List[str] = []
    if not has_date:
        missing_evidence.append("specific_date")
    if not has_inst:
        missing_evidence.append("named_institution_or_official_source")
    if not has_url:
        missing_evidence.append("official_document_or_url_reference")

    # ── KG consistency (contradiction detection) ─────────────────────────
    try:
        from ontology.relation_schema import inverse_table as _itable
        active_names = [ap.get("pattern", "") for ap in active]
        contradictions = []
        for name in active_names:
            inv = _itable.get(name)
            if inv and inv in active_names:
                pair = tuple(sorted([name, inv]))
                if pair not in [tuple(sorted(c)) for c in contradictions]:
                    contradictions.append([name, inv])
    except ImportError:
        contradictions = []

    kg_consistency_score = round(1.0 - 0.3 * min(len(contradictions), 3), 4)

    # ── Hypothesis ratio ─────────────────────────────────────────────────
    n_active = len(active)
    n_t1 = sum(1 for ap in active if ap.get("tier") == "T1")
    hypothesis_ratio = round(n_t1 / n_active, 4) if n_active > 0 else 0.0

    # ── Overall score ────────────────────────────────────────────────────
    overall_score = round(
        verifiability_score * kg_consistency_score * (1.0 - 0.4 * hypothesis_ratio),
        4,
    )

    # ── Supporting paths ─────────────────────────────────────────────────
    supporting_paths = [ap.get("pattern", "") for ap in active if ap.get("tier") == "T2"]

    return {
        "verifiability_score":  verifiability_score,
        "kg_consistency_score": kg_consistency_score,
        "missing_evidence":     missing_evidence,
        "contradictions":       contradictions,
        "supporting_paths":     supporting_paths,
        "hypothesis_ratio":     hypothesis_ratio,
        "overall_score":        overall_score,
    }


# ---------------------------------------------------------------------------
# generate_conclusion: events + patterns → conclusion dict
# ---------------------------------------------------------------------------

def generate_conclusion(
    text: str,
    events: List[Dict[str, Any]],
    active: List[Dict[str, Any]],
    derived: List[Dict[str, Any]],
    llm_service: Any,
) -> Dict[str, Any]:
    """
    Generate a structured conclusion from events and patterns.

    Returns a dict with at least:
      conclusion (str), evidence_path, hypothesis_path, mode
    """
    t2_active = [ap for ap in active if ap.get("tier") == "T2"]
    t1_active = [ap for ap in active if ap.get("tier") != "T2"]

    evidence_summary = (
        "T2 grounded patterns activated: "
        + ", ".join(ap["pattern"] for ap in t2_active[:3])
        if t2_active
        else "No T2-grounded patterns found."
    )
    hypothesis_summary = (
        "Inferred / T1 patterns: "
        + ", ".join(ap["pattern"] for ap in t1_active[:3])
        if t1_active
        else "No hypothesis-only patterns."
    )

    if llm_service is None:
        conclusion_text = (
            f"Deterministic analysis: {evidence_summary}. "
            f"Hypothesis path: {hypothesis_summary}. "
            f"Derived patterns: {', '.join(d['derived'] for d in derived[:2]) or 'none'}."
        )
        mode = "deterministic_fallback"
    else:
        prompt = (
            f"Summarize the following geopolitical analysis in 2-3 sentences:\n"
            f"Evidence path: {evidence_summary}\n"
            f"Hypothesis path: {hypothesis_summary}\n"
            f"Text excerpt: {text[:300]}\n"
            "Return plain text only."
        )
        try:
            conclusion_text = str(llm_service.call(prompt=prompt, temperature=0.1, max_tokens=250)).strip()
            mode = "llm_constrained"
        except Exception as exc:
            logger.warning("generate_conclusion LLM call failed: %s", exc)
            conclusion_text = (
                f"Deterministic analysis: {evidence_summary}. "
                f"Hypothesis path: {hypothesis_summary}."
            )
            mode = "deterministic_fallback"

    return {
        "conclusion": conclusion_text,
        "evidence_path": {
            "summary":  evidence_summary,
            "patterns": t2_active[:5],
        },
        "hypothesis_path": {
            "summary":           hypothesis_summary,
            "verification_gaps": [ap["pattern"] for ap in t1_active[:3]],
        },
        "beta_path_algebra": {"algebra_used": False},
        "mode": mode,
    }


# ===========================================================================
# Stage 1: 事件提取
# ===========================================================================

def _run_stage1(text: str, llm_service: Any) -> List[EventNode]:
    """调用 EventExtractor（含复合规则）提取事件节点。"""
    raw_events: List[Dict[str, Any]] = []
    try:
        from app.data_ingestion.event_extractor import EventExtractor
        extractor = EventExtractor()
        raw_events = extractor.extract_events(text)
    except ImportError:
        try:
            from intelligence.event_extractor import EventExtractor
            extractor = EventExtractor()
            raw_events = extractor.extract_events(text)
        except ImportError:
            raw_events = []

    # If no events from the external extractor, use the built-in rule-based extractor
    if not raw_events:
        rule_evs = extract_events_rule_based(text)
        for rev in rule_evs:
            raw_events.append({
                "event_type": rev.get("type", "其他事件"),
                "severity":   "medium",
                "description": rev.get("evidence", {}).get("quote", text[:200]),
                "entities":   {},
                "confidence": rev.get("confidence", 0.65),
            })

    if not raw_events:
        raw_events = _rule_fallback_events(text)

    nodes: List[EventNode] = []
    for ev in raw_events:
        nodes.append(EventNode(
            event_type=ev.get("event_type", "其他事件"),
            severity=ev.get("severity", "medium"),
            description=ev.get("description", text[:200]),
            entities=ev.get("entities", {}),
            confidence=float(ev.get("confidence", 0.65)),
            source_quote=ev.get("description", "")[:120],
            compound=ev.get("compound", False),
        ))

    if not nodes:
        # 保证至少 1 个事件
        nodes.append(EventNode(
            event_type="其他事件",
            severity="medium",
            description=text[:200],
            confidence=0.50,
            source_quote=text[:120],
        ))
        logger.warning("Stage1: no events extracted, using fallback")

    logger.info("Stage1: %d events extracted", len(nodes))
    return nodes


def _rule_fallback_events(text: str) -> List[Dict[str, Any]]:
    """极简规则兜底，不依赖任何外部模块。"""
    kw_map = {
        "military": "军事行动", "strike": "军事行动", "sanction": "贸易摩擦",
        "inflation": "经济危机", "election": "政治冲突", "earthquake": "自然灾害",
    }
    tl = text.lower()
    for kw, et in kw_map.items():
        if kw in tl:
            return [{"event_type": et, "severity": "high",
                     "description": text[:200], "confidence": 0.60}]
    return [{"event_type": "其他事件", "severity": "medium",
             "description": text[:200], "confidence": 0.50}]


# ===========================================================================
# Stage 2a: 模式激活（事件 → 本体模式）
# ===========================================================================

# 事件类型 → 可能激活的 (EntityType 粗粒度, RelationType 粗粒度) 对
_EVENT_TO_PATTERN_HINTS: Dict[str, List[Tuple[str, str, str]]] = {
    "军事行动": [
        ("state", "military_strike", "state"),
        ("paramilitary", "military_strike", "state"),
        ("state", "coerce", "state"),
    ],
    "贸易摩擦": [
        ("state", "sanction", "state"),
        ("state", "sanction", "firm"),
        ("alliance", "sanction", "state"),
        ("state", "trade_flow", "state"),
    ],
    "政治冲突": [
        ("state", "coerce", "state"),
        ("media", "propaganda", "trust"),
        ("state", "ally", "state"),
    ],
    "经济危机": [
        ("financial_org", "regulate", "currency"),
        ("state", "sanction", "financial_org"),
        ("state", "trade_flow", "state"),
        ("firm", "dependency", "supply_chain"),
    ],
    "外交事件": [
        ("state", "ally", "state"),
        ("state", "legitimize", "norm"),
        ("institution", "regulate", "firm"),
    ],
    "人道危机": [
        ("paramilitary", "military_strike", "state"),
        ("state", "military_strike", "state"),
        ("resource", "dependency", "state"),
    ],
    "技术突破": [
        ("state", "standardize", "tech"),
        ("firm", "supply", "firm"),
        ("state", "exclude", "tech"),
    ],
    "恐怖袭击": [
        ("paramilitary", "military_strike", "state"),
        ("state", "coerce", "state"),
    ],
    "自然灾害": [
        ("resource", "dependency", "state"),
        ("institution", "regulate", "firm"),
    ],
    "其他事件": [
        ("state", "trade_flow", "state"),
    ],
}


def _run_stage2a(events: List[EventNode]) -> List[PatternNode]:
    """
    将事件节点映射到本体模式节点。

    策略：
    1. 根据 event_type 查 _EVENT_TO_PATTERN_HINTS 获候选 (e_src, r, e_tgt)
    2. 用 lookup_pattern_by_strings 精确查询 CARTESIAN_PATTERN_REGISTRY
    3. 失败则用 fuzzy_lookup_pattern
    """
    try:
        from ontology.relation_schema import (
            lookup_pattern_by_strings,
            fuzzy_lookup_pattern,
        )
    except ImportError:
        logger.warning("Stage2a: relation_schema not available")
        return []

    activated: List[PatternNode] = []
    seen: set = set()

    for ev in events:
        hints = _EVENT_TO_PATTERN_HINTS.get(ev.event_type, [("state", "sanction", "state")])
        for e_src, r, e_tgt in hints:
            pat = lookup_pattern_by_strings(e_src, r, e_tgt)
            if pat is None:
                fuzzy = fuzzy_lookup_pattern(e_src, r, e_tgt)
                if fuzzy and fuzzy[0][2] >= 0.4:
                    pat = fuzzy[0][1]

            if pat and pat.pattern_name not in seen:
                seen.add(pat.pattern_name)
                activated.append(PatternNode(
                    pattern_name=pat.pattern_name,
                    domain=pat.domain,
                    mechanism_class=pat.mechanism_class,
                    confidence_prior=pat.confidence_prior * ev.confidence,
                    typical_outcomes=pat.typical_outcomes,
                    source_event=ev.event_type,
                ))

    if not activated:
        logger.warning("Stage2a: no patterns activated from events")

    logger.info("Stage2a: %d patterns activated", len(activated))
    return activated


# ===========================================================================
# Stage 2b: 转移枚举（composition_table + inverse_table）
# ===========================================================================

def _run_stage2b(
    active: List[PatternNode],
) -> List[TransitionEdge]:
    """
    枚举所有从 active_patterns 可达的转移。

    可达集合 R = {
      C : (A, B) → C ∈ composition_table,
          A ∈ active_patterns 或 B ∈ active_patterns
    }

    后验权重 = prior_A × prior_B × lie_similarity
    其中 lie_similarity 来自向量空间的余弦相似度。
    """
    if not active:
        return []

    try:
        from ontology.relation_schema import (
            composition_table,
            inverse_table,
            CARTESIAN_PATTERN_REGISTRY,
        )
        from ontology.lie_algebra_space import LieAlgebraSpace, _vec
    except ImportError as exc:
        logger.warning("Stage2b: import failed: %s", exc)
        return []

    space       = LieAlgebraSpace()
    active_names= {p.pattern_name for p in active}
    prior_map   = {p.pattern_name: p.confidence_prior for p in active}

    # 默认 prior（用于不在 active 中但出现在 composition 右边的模式）
    def _get_prior(name: str) -> float:
        if name in prior_map:
            return prior_map[name]
        # 从 registry 查
        for pat in CARTESIAN_PATTERN_REGISTRY.values():
            if pat.pattern_name == name:
                return pat.confidence_prior
        return 0.50

    edges: List[TransitionEdge] = []
    seen_target: set = set()

    # ── A. composition_table 中涉及 active 模式的所有 (A,B)→C ──────────
    for (pa, pb), pc in composition_table.items():
        a_active = pa in active_names
        b_active = pb in active_names
        if not (a_active or b_active):
            continue

        prior_a   = _get_prior(pa)
        prior_b   = _get_prior(pb)

        # Lie 代数：向量加法与目标向量的余弦相似度
        v_sum = _vec(pa) + _vec(pb)
        v_tgt = _vec(pc)
        n_sum = np.linalg.norm(v_sum)
        n_tgt = np.linalg.norm(v_tgt)
        if n_sum < 1e-9 or n_tgt < 1e-9:
            lie_sim = 0.5
        else:
            lie_sim = float(np.dot(v_sum / n_sum, v_tgt / n_tgt))
            # Clip negative but keep a minimum epsilon so posterior is never 0
            lie_sim = max(0.05, lie_sim)

        posterior = prior_a * prior_b * lie_sim
        # Ensure posterior is never rounded to exactly 0
        posterior = max(posterior, 1e-4)

        # Typical outcomes for target pattern
        outcomes: List[str] = []
        for pat in CARTESIAN_PATTERN_REGISTRY.values():
            if pat.pattern_name == pc:
                outcomes = pat.typical_outcomes
                break

        t_type = "self" if pc == pa or pc == pb else "compose"

        edges.append(TransitionEdge(
            from_pattern_a=pa,
            from_pattern_b=pb,
            to_pattern=pc,
            transition_type=t_type,
            prior_a=round(prior_a, 3),
            prior_b=round(prior_b, 3),
            lie_similarity=round(lie_sim, 3),
            posterior_weight=round(posterior, 4),
            typical_outcomes=outcomes[:3],
            description=(
                f"{pa} \u2295 {pb} \u2192 [{pc}] "
                f"(posterior={posterior:.4f}, lie_sim={lie_sim:.3f})"
            ),
        ))

    # ── B. inverse_table 中 active 模式的逆（低概率但高冲击 = beta 路径候选）─
    for pa in active_names:
        pc = inverse_table.get(pa)
        if pc and pc not in active_names:
            prior_a  = prior_map[pa]
            v_inv    = -_vec(pa)          # 逆元 ≈ 负向量
            v_tgt    = _vec(pc)
            n_inv    = np.linalg.norm(v_inv)
            n_tgt    = np.linalg.norm(v_tgt)
            lie_sim  = float(np.dot(v_inv / max(n_inv, 1e-9), v_tgt / max(n_tgt, 1e-9)))
            lie_sim  = max(0.0, lie_sim)
            # Use epsilon floor to prevent zero posterior for inverse paths
            lie_sim  = max(0.05, lie_sim)
            # Inverse-mode confidence discount (low-probability high-impact)
            posterior = prior_a * 0.35 * lie_sim
            # Ensure posterior is never exactly 0
            posterior = max(posterior, 1e-4)

            outcomes = []
            for pat in CARTESIAN_PATTERN_REGISTRY.values():
                if pat.pattern_name == pc:
                    outcomes = pat.typical_outcomes
                    break

            edges.append(TransitionEdge(
                from_pattern_a=pa,
                from_pattern_b="(inverse)",
                to_pattern=pc,
                transition_type="inverse",
                prior_a=round(prior_a, 3),
                prior_b=0.35,
                lie_similarity=round(lie_sim, 3),
                posterior_weight=round(posterior, 4),
                typical_outcomes=outcomes[:3],
                description=(
                    f"Inverse of [{pa}] \u2192 [{pc}] "
                    f"(posterior={posterior:.4f}, low-probability high-impact)"
                ),
            ))

    # 按后验权重排序，返回 top 5
    edges.sort(key=lambda e: e.posterior_weight, reverse=True)
    result = edges[:5]
    logger.info("Stage2b: %d transitions enumerated, top: %s",
                len(edges), [e.to_pattern for e in result])
    return result


# ===========================================================================
# Stage 2c: Lie 代数状态向量
# ===========================================================================

def _run_stage2c(active: List[PatternNode]) -> Dict[str, Any]:
    """计算 8D 状态向量 + PCA 坐标。"""
    if not active:
        return {
            "enabled": False,
            "reason": "no_active_patterns",
            "mean_vector": {},
            "dominant_dim": "unknown",
            "coercion": 0.0,
            "cooperation": 0.0,
        }

    try:
        from ontology.lie_algebra_space import (
            compute_pattern_trajectory,
            SEMANTIC_DIMS,
            _vec,
        )
        result = compute_pattern_trajectory(
            active_pattern_names=[p.pattern_name for p in active],
        )
        return result
    except Exception as exc:
        logger.warning("Stage2c: Lie algebra failed: %s", exc)
        return {"enabled": False, "reason": str(exc)}


# ===========================================================================
# Stage 2d: 驱动因素聚合（确定性，不依赖 LLM）
# ===========================================================================

def _run_stage2d(
    active: List[PatternNode],
    transitions: List[TransitionEdge],
) -> List[DrivingFactor]:
    """
    从 active_patterns 的 mechanism_class + typical_outcomes 聚合驱动因素。

    算法：
    1. 按 mechanism_class 对所有 active_patterns 分组
    2. 对每组：加权 confidence_prior 求和 → group_weight
    3. 对每组的 typical_outcomes 按 confidence_prior 加权计数
    4. 取 top-3 outcomes 构造 DrivingFactor
    5. 额外：若 transitions 中有高后验的目标模式，其 typical_outcomes 也注入

    关键：所有驱动因素均来自关系代数（mechanism_class + outcomes），
         不依赖 LLM 臆造。
    """
    if not active:
        return []

    # ── A. 按 mechanism_class 聚合 ──────────────────────────────────────
    groups: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "patterns": [],
        "total_weight": 0.0,
        "outcome_weights": defaultdict(float),
    })

    for pat in active:
        mclass = pat.mechanism_class or "unknown"
        g = groups[mclass]
        g["patterns"].append(pat.pattern_name)
        g["total_weight"] += pat.confidence_prior
        for outcome in pat.typical_outcomes:
            g["outcome_weights"][outcome] += pat.confidence_prior

    # ── B. 从高后验 transitions 注入额外 outcomes ───────────────────────
    for edge in transitions[:3]:
        if edge.posterior_weight >= 0.15:
            # 找目标模式的 mechanism_class
            try:
                from ontology.relation_schema import CARTESIAN_PATTERN_REGISTRY
                for pat in CARTESIAN_PATTERN_REGISTRY.values():
                    if pat.pattern_name == edge.to_pattern:
                        mclass = pat.mechanism_class or "transition_derived"
                        g = groups[mclass]
                        if edge.to_pattern not in g["patterns"]:
                            g["patterns"].append(edge.to_pattern + " (derived)")
                        g["total_weight"] += edge.posterior_weight * 0.5
                        for outcome in edge.typical_outcomes:
                            g["outcome_weights"][outcome] += edge.posterior_weight * 0.5
                        break
            except ImportError:
                pass

    # ── C. 构造 DrivingFactor 列表 ──────────────────────────────────────
    factors: List[DrivingFactor] = []
    for mclass, gdata in groups.items():
        if gdata["total_weight"] < 0.1:
            continue
        # top-3 outcomes by weight
        top_outcomes = sorted(
            gdata["outcome_weights"].items(),
            key=lambda x: x[1], reverse=True,
        )[:3]
        outcomes_list = [o for o, _ in top_outcomes]

        # Construct readable driving force statement (use English display names in user-visible text)
        patterns_en  = [display_pattern(p) for p in gdata["patterns"][:2]]
        patterns_str = ", ".join(patterns_en)
        factor_text  = _mechanism_to_statement(mclass, patterns_str, outcomes_list)

        factors.append(DrivingFactor(
            factor=factor_text,
            mechanism_class=mclass,
            supporting_patterns=gdata["patterns"][:3],
            weight=round(gdata["total_weight"], 3),
            outcomes=outcomes_list,
        ))

    # 按权重排序
    factors.sort(key=lambda f: f.weight, reverse=True)
    logger.info("Stage2d: %d driving factors aggregated", len(factors))
    return factors[:4]


def _mechanism_to_statement(
    mclass: str,
    patterns: str,
    outcomes: List[str],
) -> str:
    """Map mechanism class + pattern names → readable English driving statement (no LLM)."""
    _MCLASS_TEMPLATES = {
        "coercive_leverage":       "Coercive leverage mechanism active ({patterns}), driving {outcome0}",
        "tech_denial":             "Technology denial mechanism active ({patterns}), driving {outcome0}",
        "kinetic_escalation":      "Kinetic escalation mechanism active ({patterns}), driving {outcome0}",
        "proxy_warfare":           "Proxy warfare mechanism active ({patterns}), driving {outcome0}",
        "economic_interdependence":"Economic interdependence mechanism ({patterns}), constraining toward {outcome0}",
        "monetary_transmission":   "Monetary policy transmission mechanism ({patterns}), leading to {outcome0}",
        "financial_exclusion":     "Financial exclusion mechanism active ({patterns}), driving {outcome0}",
        "supply_chain_resilience": "Supply chain resilience pressure ({patterns}), triggering {outcome0}",
        "resource_leverage":       "Resource leverage mechanism active ({patterns}), driving {outcome0}",
        "tech_governance":         "Technology governance mechanism ({patterns}), driving {outcome0}",
        "tech_decoupling":         "Technology decoupling mechanism accelerating ({patterns}), driving {outcome0}",
        "oligopoly_supply":        "Oligopoly supply structure ({patterns}), constraining toward {outcome0}",
        "epistemic_warfare":       "Epistemic warfare mechanism ({patterns}), leading to {outcome0}",
        "regulatory_pressure":     "Regulatory constraint mechanism ({patterns}), triggering {outcome0}",
        "alliance_dynamics":       "Alliance dynamics mechanism ({patterns}), forming {outcome0}",
        "norm_diffusion":          "Norm diffusion mechanism ({patterns}), reinforcing {outcome0}",
        "multilateral_pressure":   "Multilateral pressure mechanism ({patterns}), driving {outcome0}",
    }
    template = _MCLASS_TEMPLATES.get(
        mclass,
        "{mclass} mechanism active ({patterns}), driving {outcome0}",
    )
    outcome0 = outcomes[0].replace("_", " ") if outcomes else "structural realignment"
    return template.format(
        patterns=patterns,
        outcome0=outcome0,
        mclass=mclass,
    )


# ===========================================================================
# Stage 3: 贝叶斯结论生成
# ===========================================================================

def _run_stage3(
    text: str,
    events:          List[EventNode],
    active:          List[PatternNode],
    transitions:     List[TransitionEdge],
    state_vector:    Dict[str, Any],
    driving_factors: List[DrivingFactor],
    llm_service:     Any,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    贝叶斯后验推演 + LLM 解释文本生成。

    确定性部分（不依赖 LLM）：
      P(alpha) = transitions[0].posterior_weight / Z
      P(beta)  = transitions[1].posterior_weight / Z（若存在）
      Z        = sum(posterior_weights)
      composite_confidence = mean([active patterns' confidence_prior])

    LLM 部分（仅限填写解释文本）：
      只被允许写 conclusion.text，解释已计算好的 alpha/beta 路径。
      所有数值字段在 LLM 调用前已确定，LLM 无法修改。
    """
    # ── A. 贝叶斯归一化概率计算 ─────────────────────────────────────────
    weights   = [t.posterior_weight for t in transitions if t.posterior_weight > 0]
    Z         = sum(weights) if weights else 1.0

    alpha_prob = round(transitions[0].posterior_weight / Z, 3) if transitions else 0.6
    beta_prob  = round(transitions[1].posterior_weight / Z, 3) if len(transitions) >= 2 else (1 - alpha_prob)

    # Alpha 路径 = 最高后验转移
    alpha_transition = transitions[0] if transitions else None
    beta_transition  = transitions[1] if len(transitions) >= 2 else None

    # 若 beta 是 inverse 类型，提高其主观权重（低概率但高冲击）
    if beta_transition and beta_transition.transition_type == "inverse":
        beta_prob = min(beta_prob * 1.5, 0.45)
        alpha_prob = max(alpha_prob - (beta_prob - (1 - alpha_prob)), 0.3)

    # ── B. 置信度计算（来自本体先验，不是幻觉）──────────────────────────
    if active:
        base_confidence = float(np.mean([p.confidence_prior for p in active]))
    else:
        base_confidence = 0.40

    # KG 一致性（有无图谱路径）
    kg_consistency = min(1.0, len(active) / max(1, len(events)) * 0.8)

    # 可验证性（有无具体证据锚点）
    text_has_date = bool(re.search(
        r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}|\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b",
        text, re.IGNORECASE,
    ))
    text_has_inst = bool(re.search(
        r"\b(NASA|ESA|Pentagon|NATO|UN|Congress|Senate|Ministry|Reuters|BBC)\b",
        text, re.IGNORECASE,
    ))
    verifiability = 0.3 + 0.35 * text_has_date + 0.35 * text_has_inst

    # 综合置信度 = 本体先验 × √(可验证性 × KG一致性)
    composite = round(
        base_confidence * (verifiability * kg_consistency) ** 0.5, 3
    )

    # ── C. 缺失证据锚点检测 ─────────────────────────────────────────────
    missing_evidence: List[str] = []
    if not text_has_date:
        missing_evidence.append("specific_date")
    if not text_has_inst:
        missing_evidence.append("named_institution_or_official_source")
    if not re.search(r"https?://\S+|official|report|document", text, re.IGNORECASE):
        missing_evidence.append("official_document_or_url_reference")

    # ── D. Construct structured Alpha / Beta paths (deterministic) ─────
    if alpha_transition:
        alpha_outcomes = alpha_transition.typical_outcomes
        alpha_path = {
            "name":           display_pattern(alpha_transition.to_pattern),
            "probability":    round(alpha_prob, 3),
            "mechanism":      _get_transition_mechanism(alpha_transition),
            "typical_outcomes": alpha_outcomes,
            "primary_outcome": alpha_outcomes[0] if alpha_outcomes else "structural_realignment",
            "evidence_basis": (
                f"Derived via composition table "
                f"(posterior_weight={alpha_transition.posterior_weight:.4f}, "
                f"prior_a={alpha_transition.prior_a:.3f}, prior_b={alpha_transition.prior_b:.3f}, "
                f"lie_sim={alpha_transition.lie_similarity:.3f})"
            ),
        }
    else:
        alpha_path = {
            "name": "Status Quo Continuation",
            "probability": 0.60,
            "mechanism": "insufficient_pattern_activation",
            "typical_outcomes": ["structural_realignment"],
            "primary_outcome": "structural_realignment",
            "evidence_basis": "No ontological path found; CoT fallback applied",
        }

    if beta_transition:
        beta_outcomes = beta_transition.typical_outcomes
        beta_path = {
            "name":           display_pattern(beta_transition.to_pattern),
            "probability":    round(beta_prob, 3),
            "mechanism":      _get_transition_mechanism(beta_transition),
            "typical_outcomes": beta_outcomes,
            "primary_outcome": beta_outcomes[0] if beta_outcomes else "structural_disruption",
            "trigger_condition": (
                "reversal of dominant pattern node"
                if beta_transition.transition_type == "inverse"
                else f"co-activation of {display_pattern(beta_transition.from_pattern_b)}"
            ),
            "evidence_basis": (
                f"{'inverse_table path' if beta_transition.transition_type == 'inverse' else 'composition_table path'} "
                f"(posterior_weight={beta_transition.posterior_weight:.4f})"
            ),
        }
    else:
        beta_path = {
            "name": "Structural Fracture Path",
            "probability": round(1 - alpha_prob, 3),
            "mechanism": "inverse_pattern_activation",
            "typical_outcomes": ["structural_realignment"],
            "primary_outcome": "structural_disruption",
            "trigger_condition": "external shock triggering inverse pattern",
            "evidence_basis": "Low-probability high-impact path based on inverse_table",
        }

    # ── E. LLM 调用：仅写解释文本，数值已锁定 ──────────────────────────
    conclusion_text = _generate_conclusion_text(
        text=text,
        alpha_path=alpha_path,
        beta_path=beta_path,
        driving_factors=driving_factors,
        state_vector=state_vector,
        composite_confidence=composite,
        llm_service=llm_service,
    )

    # ── Determine adaptive number of outcomes based on reliability ──────
    # Dense reliable: ≥3 active patterns + high confidence → 3 outcomes
    # Low reliability: ≤1 pattern or low confidence → 1 outcome
    # Normal: 2 outcomes
    n_active = len(active)
    if n_active >= 3 and composite >= 0.5:
        n_outcomes = 3
    elif n_active <= 1 or composite < 0.25:
        n_outcomes = 1
    else:
        n_outcomes = 2

    # Build outcome lists for the conclusion struct using the outcome catalog
    ev_outcomes = [
        {
            "id": o,
            "text": _outcome_phrase(o),
            "probability": round(alpha_prob / n_outcomes, 3),
        }
        for o in alpha_path.get(
            "typical_outcomes", [alpha_path.get("primary_outcome", "structural_realignment")]
        )[:n_outcomes]
    ]
    hyp_outcomes = [
        {
            "id": o,
            "text": _outcome_phrase(o),
            "probability": round(
                beta_prob / max(1, min(n_outcomes, len(beta_path.get("typical_outcomes", [])))), 3
            ),
        }
        for o in beta_path.get(
            "typical_outcomes", [beta_path.get("primary_outcome", "structural_disruption")]
        )[:n_outcomes]
    ]

    # Sanitize trigger_condition: strip Chinese characters and internal pattern chain notation
    _raw_trigger = beta_path.get("trigger_condition", "reversal of dominant pattern node")
    # Remove bracketed content that may contain raw pattern names, e.g. "[pattern_name]"
    _trigger_clean = re.sub(r"\[[^\]]*\]", "", _raw_trigger).strip(" ,")
    # Remove any remaining CJK characters
    _trigger_clean = re.sub(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]+", "", _trigger_clean).strip()
    if not _trigger_clean:
        _trigger_clean = "a significant reversal of the current dominant trajectory"

    # Ensure executive_judgement is always a plain string
    if not isinstance(conclusion_text, str):
        conclusion_text = str(conclusion_text)

    # Build outcome-first evidence/hypothesis path summaries
    _alpha_primary_phrase = _outcome_phrase(alpha_path.get("primary_outcome", "structural_realignment"))
    _beta_primary_phrase  = _outcome_phrase(beta_path.get("primary_outcome", "structural_disruption"))

    # ── Raw (deterministic) summary strings ─────────────────────────────────

    _evidence_summary_raw = (
        f"Primary projected outcome: {_alpha_primary_phrase} "
        f"(p={alpha_path['probability']:.0%})."
    )
    _hypothesis_summary_raw = (
        f"Contingent alternative (p={beta_path.get('probability', 0.0):.0%}): "
        f"{_beta_primary_phrase}, "
        f"if {_trigger_clean}."
    )
    # executive_judgement_raw: pure deterministic fallback (no LLM)
    _executive_judgement_raw = _fallback_conclusion_text(
        alpha_path, beta_path, driving_factors, composite
    )

    # ── LLM rendering pass (post-deterministic paraphrase) ──────────────────
    # Extract entity strings from events for the allowed-entity list
    _allowed_entities: List[str] = []
    for ev in events:
        _args = ev.args if hasattr(ev, "args") else {}
        for _v in _args.values():
            if isinstance(_v, str) and _v:
                _allowed_entities.append(_v)
    # Deduplicate, keep order
    _seen: set = set()
    _allowed_entities_dedup: List[str] = []
    for _e in _allowed_entities:
        if _e not in _seen:
            _seen.add(_e)
            _allowed_entities_dedup.append(_e)

    _rendered = render_conclusion_with_llm(
        news_fragment=text,
        executive_judgement_raw=_executive_judgement_raw,
        evidence_summary_raw=_evidence_summary_raw,
        hypothesis_summary_raw=_hypothesis_summary_raw,
        alpha_prob=alpha_prob,
        beta_prob=beta_prob,
        composite_confidence=composite,
        verification_gaps=[_trigger_clean],
        allowed_entities=_allowed_entities_dedup,
        llm_service=llm_service,
    )

    conclusion = {
        # ── professional intelligence judgement struct (rendered) ─────────
        "executive_judgement": _rendered["executive_judgement"],
        "executive_judgement_raw": _executive_judgement_raw,
        "evidence_path": {
            "summary": _rendered["evidence_path_summary"],
            "summary_raw": _evidence_summary_raw,
            "outcomes": ev_outcomes,
        },
        "hypothesis_path": {
            "summary": _rendered["hypothesis_path_summary"],
            "summary_raw": _hypothesis_summary_raw,
            "outcomes": hyp_outcomes,
            "verification_gaps": [_trigger_clean],
        },
        "rendering_meta": _rendered["rendering_meta"],
        "final": {
            "overall_confidence": composite,
            "compute_trace_ref": f"bayesian_posterior|Z={sum(t.posterior_weight for t in transitions):.4f}",
        },
        "beta_path_algebra": {"algebra_used": False},
        # ── canonical frontend keys (backward compat) ────────────────────
        "conclusion": _rendered["executive_judgement"],
        "text":       _rendered["executive_judgement"],
        "alpha_path": alpha_path,
        "beta_path":  beta_path,
        "confidence": composite,
        "mode":       "llm_constrained" if llm_service is not None else "deterministic_fallback",
    }

    # Compute credibility with canonical field names
    hypothesis_ratio = 0.0  # no T1/T2 distinction at this stage (EventNode level)
    credibility = {
        # ── canonical frontend keys ──────────────────────────────────────
        "verifiability_score":  round(verifiability, 3),
        "kg_consistency_score": round(kg_consistency, 3),
        "overall_score":        composite,
        "hypothesis_ratio":     hypothesis_ratio,
        "missing_evidence":     missing_evidence,
        "contradictions":       [],
        "supporting_paths":     [],
        # ── backward-compatible keys ─────────────────────────────────────
        "verifiability":        round(verifiability, 3),
        "kg_consistency":       round(kg_consistency, 3),
        "composite_score":      composite,
        "active_pattern_count": len(active),
        "transition_count":     len(transitions),
        "confidence_source":    "ontology_prior × bayesian_posterior",
        "note": (
            "Confidence derived from ontology priors × Bayesian posterior normalisation. "
            "Missing evidence anchors reduce verifiability score."
        ),
    }

    return conclusion, credibility


def _get_transition_mechanism(edge: TransitionEdge) -> str:
    """从转移边提取机制描述。"""
    try:
        from ontology.relation_schema import CARTESIAN_PATTERN_REGISTRY
        for pat in CARTESIAN_PATTERN_REGISTRY.values():
            if pat.pattern_name == edge.to_pattern:
                return pat.mechanism_class
    except ImportError:
        pass
    return "composition_derived"


def _generate_conclusion_text(
    text: str,
    alpha_path: Dict[str, Any],
    beta_path: Dict[str, Any],
    driving_factors: List[DrivingFactor],
    state_vector: Dict[str, Any],
    composite_confidence: float,
    llm_service: Any,
) -> str:
    """
    LLM is only allowed to write explanatory text; all numerical fields are
    pre-computed and locked.  Falls back to a deterministic template when
    LLM is unavailable.

    The output is ALWAYS a plain English string — never a dict or JSON blob.
    """
    alpha_outcome_phrase = _outcome_phrase(
        alpha_path.get("primary_outcome", "structural_realignment")
    )
    beta_outcome_phrase = _outcome_phrase(
        beta_path.get("primary_outcome", "structural_disruption")
    )

    dominant = state_vector.get("mean_vector", {}).get("dominant_dim", "unknown")
    coercion = state_vector.get("mean_vector", {}).get("coercion", 0.0)

    prompt = f"""You are the EL-DRUIN intelligence analyst. Deterministic algorithms have computed
the outcomes below. Write 1–2 sentences of outcome-first intelligence commentary anchored to
the actual news events described in the fragment.

[ORIGINAL NEWS FRAGMENT]
{text[:600]}

[COMPUTED OUTCOMES — DO NOT MODIFY THESE VALUES]
- Most likely trajectory (p={composite_confidence:.0%}): {alpha_outcome_phrase}
- Contingent alternative: {beta_outcome_phrase}
- Dominant state dimension: {dominant} (coercion index {coercion:+.2f})

[REQUIREMENTS]
1. Start with the outcome stated as a concrete action, naming the actors from the news fragment.
   BAD:  "The primary actor will face structural pressure."
   GOOD: "With US export controls tightening, Chinese suppliers are accelerating domestic substitution."
2. One sentence covers the contingent alternative — what would have to change for it to materialise.
3. Do NOT explain how confidence was calculated. Do NOT mention patterns, mechanisms, algebra, or Bayesian.
4. Plain English only. No JSON, no markdown.
"""
    try:
        response = llm_service.call(
            prompt=prompt,
            system=(
                "You are a rigorous intelligence analyst. State outcomes directly. "
                "Never output pattern names, mechanism names, JSON, or probabilities as numbers."
            ),
            temperature=0.10,
            max_tokens=300,
        )
        text_out = str(response).strip()
        # Strip any JSON/markdown wrapping that a non-compliant LLM might add
        if text_out.startswith("{") or text_out.startswith("["):
            import json as _json
            try:
                parsed = _json.loads(text_out)
                if isinstance(parsed, dict):
                    text_out = parsed.get("text", parsed.get("conclusion", str(parsed)))
                elif isinstance(parsed, list) and parsed:
                    first = parsed[0]
                    if isinstance(first, str):
                        text_out = first
                    elif isinstance(first, dict):
                        text_out = first.get("text", first.get("conclusion", str(first)))
                    else:
                        text_out = str(first)
            except Exception:
                pass
        # Ensure we return a plain string
        if not isinstance(text_out, str):
            text_out = str(text_out)
        return text_out if text_out else _fallback_conclusion_text(
            alpha_path, beta_path, driving_factors, composite_confidence
        )
    except Exception as exc:
        logger.warning("Stage3 LLM conclusion text failed: %s", exc)
        return _fallback_conclusion_text(
            alpha_path, beta_path, driving_factors, composite_confidence
        )


def _fallback_conclusion_text(
    alpha_path: Dict[str, Any],
    beta_path: Dict[str, Any],
    driving_factors: List[DrivingFactor],
    confidence: float,
) -> str:
    """Deterministic template fallback when LLM is unavailable.

    Outcome-first, action-sentence intelligence language.
    No internal jargon, no self-explanation of methodology.
    Numbers (confidence, methodology) belong in the Probability Tree tab.
    """
    primary_id = alpha_path.get("primary_outcome", "structural_realignment")
    primary    = _outcome_phrase(primary_id)
    beta_id    = beta_path.get("primary_outcome", "structural_disruption")
    beta_desc  = _outcome_phrase(beta_id)
    alpha_prob = alpha_path.get("probability", confidence)
    beta_prob  = beta_path.get("probability", 1 - alpha_prob)

    # Build a one-line driver hint from driving_factors if available
    driver_hint = ""
    if driving_factors:
        top_outcome = driving_factors[0].outcomes[0] if driving_factors[0].outcomes else ""
        if top_outcome and top_outcome != primary_id:
            driver_hint = f" driven by {_outcome_phrase(top_outcome).lower()}"

    return (
        f"Most likely near-term trajectory (p={alpha_prob:.0%}): "
        f"{primary}{driver_hint}. "
        f"A lower-probability but high-impact alternative (p={beta_prob:.0%}): "
        f"{beta_desc}."
    )

# ---------------------------------------------------------------------------
# render_conclusion_with_llm: real-world paraphrase layer (post-deterministic)
# ---------------------------------------------------------------------------

# Substrings that must never appear in rendered output (internal ontology jargon
# or meta-commentary that does not belong in a real-world intelligence judgement)
_RENDER_DISALLOWED = [
    "⊕", "pattern", "mechanism", "composition_derived", "tech_decoupling",
    "coercive_leverage", "kinetic_escalation", "oligopoly_supply",
    "inverse_pattern", "algebra", "ontolog", "bayesian", "posterior",
    "calibrated", "calibration", "normalisation", "normalization",
    "deterministic", "prior", "semigroup", "attractor",
    # Real-world phrasing guardrails: block meta-commentary
    "assessed based on", "corroborating evidence", "evidence signals",
    "based on corroborating", "corroborating", "evidence signal",
    "computed from", "derived from ontology",
]

# Precision for rounding numeric values in guardrail comparison
_NUMERIC_PRECISION = 4

# Maximum number of allowed entities to include in the rendering prompt
_MAX_ENTITIES_IN_PROMPT = 10

# Minimum length for a capitalised token to be treated as a proper noun
_PROPER_NOUN_MIN_LEN = 3

# Stop-words / common sentence starters that must not be mistaken for proper nouns
_PROPER_NOUN_STOPWORDS: frozenset = frozenset({
    "The", "A", "An", "This", "That", "These", "Those", "It", "Its",
    "In", "On", "At", "By", "For", "With", "To", "Of", "As", "If",
    "And", "But", "Or", "Nor", "So", "Yet", "Both", "Either", "Neither",
    "Facing", "According", "Based", "Given", "While", "When", "Where",
    "Under", "Over", "After", "Before", "During", "Since", "Until",
    "Between", "Among", "Against", "Through", "Without", "Within",
    "Primary", "Secondary", "Final", "Overall", "Key", "Major", "New",
    "High", "Low", "Strong", "Weak", "Full", "Large", "Small", "Long",
    "Short", "Main", "Likely", "Potential", "Possible", "Significant",
    "Supply", "Trade", "Energy", "Market", "Financial", "Economic",
    "Military", "Political", "National", "Global", "Regional", "Local",
    "State", "Government", "Policy", "Security", "Export", "Import",
    "Sanctions", "Tariffs", "Investment", "Technology", "Alliance",
    "Conflict", "Pressure", "Escalation", "Tension", "Agreement",
    "Projected", "Assessed", "Estimated", "Reported", "Confirmed",
    "Imposed", "Announced", "Warning", "Following", "Continued",
    # Sentence-starting verbs and common words
    "Facing", "Citing", "Following", "Amid", "Despite", "Although",
    "However", "Therefore", "Moreover", "Furthermore", "Additionally",
    "Analysts", "Officials", "Experts", "Leaders", "Authorities",
    "Washington", "Beijing", "Moscow", "Brussels", "London",
    "Supply", "Demand", "Production", "Exports", "Imports",
    "Corporate", "Private", "Public", "Federal", "Central",
    "Strategic", "Tactical", "Structural", "Systemic", "Bilateral",
    "Multilateral", "Unilateral", "International", "Domestic",
    "Contingent", "Conditional", "Alternative", "Reversal",
    "Escalation", "Stabilisation", "Stabilization", "Resolution",
    "Trajectory", "Projection", "Assessment", "Analysis", "Forecast",
    "Continued", "Ongoing", "Persistent", "Growing", "Rising",
    "Declining", "Increasing", "Decreasing", "Stable", "Volatile",
    "Comprehensive", "Sweeping", "Targeted", "Broad", "Narrow",
    "Imminent", "Immediate", "Near", "Long", "Medium", "Short",
    "Critical", "Essential", "Important", "Relevant", "Significant",
    "Potential", "Possible", "Probable", "Likely", "Unlikely",
    "Expected", "Anticipated", "Predicted", "Forecast", "Projected",
})


def _extract_proper_nouns(text: str) -> frozenset:
    """Return mid-sentence capitalised tokens from *text* that are likely proper nouns.

    Strategy: split on sentence boundaries, then within each sentence extract
    tokens that are capitalised but do NOT appear at position 0 (sentence start).
    Additionally apply a stop-word filter and length filter.

    This approach avoids false-positives from sentence-initial common words like
    "Supply", "Facing", "Analysts" etc.  It errs on the side of false negatives
    (missing real proper nouns) to keep guardrail precision high.
    """
    import re as _re_pn

    # Split into sentences at . ? ! or newline
    _sent_splitter = _re_pn.compile(r"(?<=[.?!\n])\s+")
    sentences = _sent_splitter.split(text.strip())

    tokens: set = set()
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        words = sent.split()
        # Skip the first word of each sentence (capitalised by grammar, not by proper-noun status)
        for word in words[1:]:
            # Strip surrounding punctuation
            clean = word.strip(".,;:!?\"'()[]{}").rstrip("'s")
            if len(clean) < _PROPER_NOUN_MIN_LEN:
                continue
            if not clean[0].isupper():
                continue
            # Must have at least one lowercase letter (exclude ALL-CAPS acronyms like "US", "EU")
            if not any(c.islower() for c in clean):
                continue
            if clean in _PROPER_NOUN_STOPWORDS:
                continue
            tokens.add(clean)
    return frozenset(tokens)


def _extract_numeric_values(text: str) -> set:
    """Return all numeric values found in *text* (as rounded floats).

    Supports percentages (e.g. "73%") and plain decimals (e.g. "0.73").
    Values are normalised to [0,1] floats for comparison.
    """
    import re as _re
    found: set = set()
    # Percentages like 73% or 73.4%
    for m in _re.finditer(r"(\d+(?:\.\d+)?)\s*%", text):
        found.add(round(float(m.group(1)) / 100, _NUMERIC_PRECISION))
    # Plain decimals 0.xx that look like probabilities (0. prefix)
    for m in _re.finditer(r"\b(0\.\d+)\b", text):
        found.add(round(float(m.group(1)), _NUMERIC_PRECISION))
    return found


def _count_sentences(text: str) -> int:
    """Rough sentence count: split on sentence-ending punctuation."""
    import re as _re
    parts = _re.split(r"(?<=[.!?])\s+", text.strip())
    return len([p for p in parts if p])


def render_conclusion_with_llm(
    news_fragment: str,
    executive_judgement_raw: str,
    evidence_summary_raw: str,
    hypothesis_summary_raw: str,
    alpha_prob: float,
    beta_prob: float,
    composite_confidence: float,
    verification_gaps: List[str],
    allowed_entities: List[str],
    llm_service: Any,
) -> Dict[str, Any]:
    """Apply a real-world paraphrase / rendering pass over deterministic raw fields.

    The LLM is given strict constraints:
    - Must not change any numeric value (probabilities, confidence).
    - Must not invent new entities beyond *allowed_entities* or the *news_fragment*.
    - Must not include pattern names, mechanism_class names, or internal jargon.
    - Output must be outcome-first professional intelligence judgement, ≤ 3 sentences.

    Guardrails post-validate the rendered text and fall back to raw on violation.

    Returns a dict with:
    - executive_judgement   (rendered or raw fallback)
    - evidence_path_summary (rendered or raw fallback)
    - hypothesis_path_summary (rendered or raw fallback)
    - rendering_meta        {enabled, guardrails_triggered, quoted_spans_used}
    """
    rendering_meta: Dict[str, Any] = {
        "enabled": False,
        "guardrails_triggered": False,
        "quoted_spans_used": False,
    }

    # Collect allowed numeric values (alpha/beta probs + composite)
    allowed_nums = {
        round(alpha_prob, _NUMERIC_PRECISION),
        round(beta_prob, _NUMERIC_PRECISION),
        round(composite_confidence, _NUMERIC_PRECISION),
    }

    # Build the full set of "anchored" tokens from which the LLM may draw proper
    # nouns: (a) the news fragment itself, (b) the explicit allowed_entities list.
    _anchor_text = news_fragment + " " + " ".join(allowed_entities)
    _anchor_proper_nouns: frozenset = _extract_proper_nouns(_anchor_text)
    # Also allow first-word tokens of entity strings (e.g. "United" from "United States")
    _anchor_words: frozenset = frozenset(
        w for e in allowed_entities for w in e.split() if len(w) >= _PROPER_NOUN_MIN_LEN
    )

    def _guardrail_check(rendered: str, raw: str) -> str:
        """Return rendered if all guardrails pass, else return raw."""
        nonlocal rendering_meta

        # 1. Length guard: must be ≤ 3 sentences
        if _count_sentences(rendered) > 3:
            logger.debug("Rendering guardrail: too many sentences (%d)", _count_sentences(rendered))
            rendering_meta["guardrails_triggered"] = True
            return raw

        # 2. Numeric guard: all numbers in rendered must be in allowed_nums
        found_nums = _extract_numeric_values(rendered)
        if found_nums - allowed_nums:
            logger.debug(
                "Rendering guardrail: unexpected numeric values %s not in %s",
                found_nums - allowed_nums,
                allowed_nums,
            )
            rendering_meta["guardrails_triggered"] = True
            return raw

        # 3. Disallowed substring guard (jargon / ontology internals)
        rendered_lower = rendered.lower()
        for token in _RENDER_DISALLOWED:
            if token.lower() in rendered_lower:
                logger.debug("Rendering guardrail: disallowed token %r found", token)
                rendering_meta["guardrails_triggered"] = True
                return raw

        # 4. CJK leakage guard: no CJK characters allowed in rendered output
        from intelligence.pattern_i18n import has_cjk as _has_cjk
        if _has_cjk(rendered):
            logger.debug("Rendering guardrail: CJK characters detected in rendered output")
            rendering_meta["guardrails_triggered"] = True
            return raw

        # 5. Invented entity guard: proper nouns not anchored to the news fragment
        #    or allowed_entities list must not appear in the rendered text.
        rendered_nouns = _extract_proper_nouns(rendered)
        # For hyphenated compounds (e.g. "US-China"), check if every component
        # part that looks like a proper noun is individually anchored — if so,
        # the compound as a whole is considered anchored (not invented).
        _all_anchor = _anchor_proper_nouns | _anchor_words
        _all_anchor_lower = frozenset(a.lower() for a in _all_anchor)
        truly_invented: set = set()
        for noun in rendered_nouns:
            if noun in _all_anchor:
                continue  # directly anchored
            # Check hyphenated compound: all alphabetic parts must be anchored
            parts = [p for p in noun.split("-") if p]
            if parts and all(
                p.lower() in _all_anchor_lower
                # Allow ALL-CAPS acronyms (e.g. "US", "EU", "NATO") in compounds
                or all(c.isupper() or not c.isalpha() for c in p)
                for p in parts
            ):
                continue  # all parts are anchored → whole compound is anchored
            truly_invented.add(noun)
        if truly_invented:
            logger.debug(
                "Rendering guardrail: invented proper nouns %s not in anchor set",
                truly_invented,
            )
            rendering_meta["guardrails_triggered"] = True
            rendering_meta["invented_entities"] = sorted(truly_invented)
            return raw

        return rendered

    if llm_service is None:
        return {
            "executive_judgement": executive_judgement_raw,
            "evidence_path_summary": evidence_summary_raw,
            "hypothesis_path_summary": hypothesis_summary_raw,
            "rendering_meta": rendering_meta,
        }

    rendering_meta["enabled"] = True

    # Build the set of allowed entity strings for the prompt
    entities_str = "; ".join(allowed_entities[:_MAX_ENTITIES_IN_PROMPT]) if allowed_entities else "(none specified)"
    gaps_str = "; ".join(verification_gaps[:3]) if verification_gaps else "(none)"

    prompt = f"""You are a professional intelligence analyst performing a final rendering pass.

You have been given pre-computed deterministic intelligence assessments and the original news fragment.
Your task: rewrite each field into a concrete, news-anchored intelligence sentence — one that a
policymaker could read without knowing what "ontology" or "Bayesian" means.

[ORIGINAL NEWS FRAGMENT — you MUST anchor your output to named actors and events from here]
{news_fragment[:800]}

[ALLOWED ENTITIES — you may only reference proper nouns from this list or the news fragment above]
{entities_str}

[DETERMINISTIC ASSESSMENTS — probability values are locked and must not change]
Evidence path (most likely, p={alpha_prob:.0%}): {evidence_summary_raw}
Hypothesis path (contingent, p={beta_prob:.0%}): {hypothesis_summary_raw}
Executive judgement (raw): {executive_judgement_raw}
Verification gaps: {gaps_str}

[RENDERING REQUIREMENTS]
1. Each rendered field must be 1–2 sentences. Start with the outcome, not with a subject clause.
2. Use specific named actors, countries, or events from the news fragment — do not write generically.
   Example of WRONG: "The primary actor will face structural pressure."
   Example of RIGHT: "Facing tightened US export controls, Chinese chipmakers accelerate domestic substitution."
3. You MAY quote short phrases (≤ 8 words) verbatim from the news fragment to anchor the sentence.
4. Preserve probability values exactly (e.g. {alpha_prob:.0%} stays {alpha_prob:.0%}).
5. Do NOT mention "ontology", "Bayesian", "confidence calibration", "pattern", "mechanism", or any internal jargon.
6. Do NOT add a sentence explaining how confidence was calculated — that belongs in the Probability Tree tab.
7. CRITICAL: Do NOT introduce any proper noun (person, place, organisation, facility) that does not
   appear in the news fragment or the allowed entities list above. Any invented proper noun will
   cause automatic fallback to a deterministic conclusion.
8. Output ONLY valid JSON in this exact format, nothing else:
{{"executive_judgement": "...", "evidence_path_summary": "...", "hypothesis_path_summary": "..."}}
"""

    try:
        response = llm_service.call(
            prompt=prompt,
            system=(
                "You are a rigorous intelligence analyst performing a rendering pass. "
                "Preserve all numeric values exactly. Output only the requested JSON."
            ),
            temperature=0.15,
            max_tokens=400,
        )
        raw_response = str(response).strip()

        # Parse JSON response
        import json as _json
        # Strip markdown code fences if present
        if raw_response.startswith("```"):
            lines = raw_response.splitlines()
            raw_response = "\n".join(
                l for l in lines
                if not l.strip().startswith("```")
            ).strip()

        parsed = _json.loads(raw_response)
        if not isinstance(parsed, dict):
            raise ValueError("LLM response is not a JSON object")

        rendered_ej  = str(parsed.get("executive_judgement", "")).strip()
        rendered_ep  = str(parsed.get("evidence_path_summary", "")).strip()
        rendered_hp  = str(parsed.get("hypothesis_path_summary", "")).strip()

        # Detect whether the LLM quoted spans from the news fragment.
        # Check for double-quoted substrings in rendered fields that appear in news_fragment.
        import re as _re_q
        _quote_pattern = _re_q.compile(r'"([^"]{4,40})"')
        _quoted_spans_used = False
        for _field in [rendered_ej, rendered_ep, rendered_hp]:
            for _match in _re_q.finditer(_quote_pattern, _field):
                if _match.group(1) in news_fragment:
                    _quoted_spans_used = True
                    break
            if _quoted_spans_used:
                break
        rendering_meta["quoted_spans_used"] = _quoted_spans_used

        return {
            "executive_judgement": _guardrail_check(rendered_ej, executive_judgement_raw) if rendered_ej else executive_judgement_raw,
            "evidence_path_summary": _guardrail_check(rendered_ep, evidence_summary_raw) if rendered_ep else evidence_summary_raw,
            "hypothesis_path_summary": _guardrail_check(rendered_hp, hypothesis_summary_raw) if rendered_hp else hypothesis_summary_raw,
            "rendering_meta": rendering_meta,
        }

    except Exception as exc:
        logger.warning("render_conclusion_with_llm failed: %s", exc)
        rendering_meta["enabled"] = False
        return {
            "executive_judgement": executive_judgement_raw,
            "evidence_path_summary": evidence_summary_raw,
            "hypothesis_path_summary": hypothesis_summary_raw,
            "rendering_meta": rendering_meta,
        }


# ===========================================================================
# 主入口
# ===========================================================================

def run_evented_pipeline(
    text: str,
    llm_service: Any = None,
) -> PipelineResult:
    """
    执行完整的五阶段本体推演管线。

    返回的 PipelineResult 严格遵循数据契约：
      events[]           ≥1，Stage 1
      active_patterns[]  ≥0（附说明）
      state_vector       Stage 2c
      top_transitions[]  Stage 2b
      driving_factors[]  Stage 2d（确定性聚合）
      conclusion         Stage 3（LLM 仅填解释文本）
      credibility        置信度来源：本体先验 × 贝叶斯后验
    """
    logger.info("EventedPipeline: starting on %d chars", len(text))

    # ── Stage 1 ──────────────────────────────────────────────────────
    events = _run_stage1(text, llm_service)
    logger.info("EventedPipeline: %d events extracted", len(events))

    # ── Stage 2a ─────────────────────────────────────────────────────
    active = _run_stage2a(events)
    logger.info("EventedPipeline: %d active patterns", len(active))

    # ── Stage 2b ─────────────────────────────────────────────────────
    transitions = _run_stage2b(active)
    logger.info("EventedPipeline: %d derived patterns (transitions)", len(transitions))

    # ── Stage 2c ─────────────────────────────────────────────────────
    state_vector = _run_stage2c(active)
    # Ensure mean_vector is a list[float] of length 8 (contract requirement)
    _sv_mean = state_vector.get("mean_vector", {})
    if isinstance(_sv_mean, dict) and "dim_values" in _sv_mean:
        _dim_list = list(_sv_mean["dim_values"].values())
    elif isinstance(_sv_mean, list):
        _dim_list = _sv_mean
    else:
        _dim_list = [0.0] * 8
    # Pad / truncate to exactly 8 floats
    _dim_list = [float(v) for v in _dim_list[:8]] + [0.0] * max(0, 8 - len(_dim_list))
    state_vector["mean_vector_list"] = _dim_list

    # ── Stage 2d ─────────────────────────────────────────────────────
    driving_factors = _run_stage2d(active, transitions)

    # ── Stage 3 ──────────────────────────────────────────────────────
    conclusion, credibility = _run_stage3(
        text=text,
        events=events,
        active=active,
        transitions=transitions,
        state_vector=state_vector,
        driving_factors=driving_factors,
        llm_service=llm_service,
    )

    # ── 序列化 ──────────────────────────────────────────────────────
    def _pat_to_dict(p: PatternNode) -> Dict[str, Any]:
        en_name = display_pattern(p.pattern_name)
        return {
            # v3 canonical keys (display-safe English labels)
            "pattern_name":     en_name,
            "domain":           p.domain,
            "mechanism_class":  p.mechanism_class,
            "confidence_prior": round(p.confidence_prior, 3),
            "typical_outcomes": p.typical_outcomes[:3],
            "source_event":     p.source_event,
            # canonical frontend keys
            "pattern":          en_name,
            "tier":             "T2",   # active patterns derived from ontology are T2 by default
            "confidence":       round(p.confidence_prior, 3),
            "from_event":       p.source_event,
            "inferred":         False,
        }

    def _trans_to_dict(t: TransitionEdge) -> Dict[str, Any]:
        en_a  = display_pattern(t.from_pattern_a)
        en_b  = display_pattern(t.from_pattern_b)
        en_c  = display_pattern(t.to_pattern)
        # Rebuild description with English names (original uses CJK keys)
        desc = (
            f"{en_a} \u2295 {en_b} \u2192 [{en_c}] "
            f"(posterior={t.posterior_weight:.4f}, lie_sim={t.lie_similarity:.3f})"
            if t.transition_type != "inverse"
            else (
                f"Inverse of [{en_a}] \u2192 [{en_c}] "
                f"(posterior={t.posterior_weight:.4f}, low-probability high-impact)"
            )
        )
        return {
            "from_pattern_a":   en_a,
            "from_pattern_b":   en_b,
            "to_pattern":       en_c,
            "transition_type":  t.transition_type,
            "posterior_weight": t.posterior_weight,
            "lie_similarity":   t.lie_similarity,
            "typical_outcomes": t.typical_outcomes,
            "description":      desc,
            "tier":             "T1" if t.transition_type == "inverse" else "T2",
        }

    def _df_to_dict(d: DrivingFactor) -> Dict[str, Any]:
        en_patterns = [display_pattern(p) for p in d.supporting_patterns]
        return {
            # canonical backend keys
            "factor":              d.factor,
            "mechanism_class":     d.mechanism_class,
            "supporting_patterns": en_patterns,
            "weight":              d.weight,
            "outcomes":            d.outcomes,
            # canonical frontend alias keys
            "label":      d.factor,
            "count":      len(en_patterns),
            "confidence": round(min(d.weight, 1.0), 3),
            "evidence":   d.outcomes[:2],
        }

    def _ev_to_dict(e: EventNode) -> Dict[str, Any]:
        # Determine tier from confidence
        tier = "T2" if e.confidence >= _T2_CONF_THRESHOLD else "T1"
        quote = e.source_quote or e.description[:120]
        return {
            # v3 canonical keys
            "event_type":   e.event_type,
            "severity":     e.severity,
            "description":  e.description,
            "entities":     e.entities,
            "confidence":   e.confidence,
            "source_quote": quote,
            # canonical frontend keys
            "type":             e.event_type,
            "tier":             tier,
            "evidence":         {"quote": quote, "source": ""},
            "inferred_fields":  [],
            "verification_gap": [] if tier == "T2" else ["tier downgraded by confidence threshold"],
        }

    active_dicts     = [_pat_to_dict(p)  for p in active]
    transition_dicts = [_trans_to_dict(t) for t in transitions]
    df_dicts         = [_df_to_dict(d)   for d in driving_factors]
    event_dicts      = [_ev_to_dict(e)   for e in events]

    # derived_patterns backward-compat field (top transitions → derived pattern list)
    derived_compat = [
        {
            # canonical keys (display-safe English labels)
            "pattern_name":       display_pattern(t.to_pattern),
            "derived":            display_pattern(t.to_pattern),
            "pattern":            display_pattern(t.to_pattern),
            "derived_confidence": round(t.posterior_weight, 3),
            "rule":               t.transition_type,
            "derived_tier":       "T1" if t.transition_type == "inverse" else "T2",
            "derived_inferred":   t.transition_type == "inverse",
            "inputs":             [display_pattern(t.from_pattern_a), display_pattern(t.from_pattern_b)],
        }
        for t in transitions[:3]
    ]

    # ── Probability tree: nodes/edges format with Bayesian compute trace ─
    prob_tree: Dict[str, Any] = {}
    if transitions:
        Z = sum(t.posterior_weight for t in transitions)
        if Z < 1e-9:
            Z = 1.0
        credibility_overall = round(
            credibility.get("overall_score", 0.4), 3
        )

        # Root node
        pt_nodes = [{
            "id":          "root",
            "label":       "Ontological Analysis",
            "type":        "root",
            "probability": 1.0,
            "evidence":    f"{len(active)} active patterns | {len(transitions)} transitions | Z={Z:.4f}",
        }]
        pt_edges = []

        for idx, t in enumerate(transitions[:5]):
            node_id = f"t{idx}"
            prob = round(t.posterior_weight / Z, 4)
            en_a = display_pattern(t.from_pattern_a)
            en_b = display_pattern(t.from_pattern_b)
            en_c = display_pattern(t.to_pattern)
            pt_nodes.append({
                "id":                node_id,
                "label":             en_c,
                "type":              "T2" if t.transition_type != "inverse" else "T1",
                "probability":       prob,
                "evidence":          (
                    f"prior_a={t.prior_a:.3f} × prior_b={t.prior_b:.3f} "
                    f"× lie_sim={t.lie_similarity:.3f} = {t.posterior_weight:.4f} / Z={Z:.4f} = {prob:.4f}"
                ),
                "verification_gap":  "low-probability high-impact path" if t.transition_type == "inverse" else "",
                "typical_outcomes":  t.typical_outcomes[:2],
            })
            pt_edges.append({
                "from":             "root",
                "to":               node_id,
                "weight":           prob,
                "transition_type":  t.transition_type,
                "posterior_weight": t.posterior_weight,
                "posterior_contribution": round(t.posterior_weight / Z, 4),
                "compute_trace":    (
                    f"prior_a({en_a})={t.prior_a:.3f} "
                    f"× prior_b({en_b})={t.prior_b:.3f} "
                    f"× lie_sim={t.lie_similarity:.3f} = {t.posterior_weight:.4f}"
                ),
            })

        selected = f"t0" if transitions else None

        prob_tree = {
            # Frontend nodes/edges format
            "nodes":               pt_nodes,
            "edges":               pt_edges,
            "selected_branch":     selected,
            "overall_credibility": credibility_overall,
            "summary": (
                f"Bayesian posterior: Z={Z:.4f} | "
                f"Evidence path p={round(transitions[0].posterior_weight / Z, 3):.0%} | "
                f"Overall confidence={credibility_overall:.0%}"
            ),
            # Backward-compat alpha/beta keys
            "alpha": {
                "name":        display_pattern(transitions[0].to_pattern),
                "probability": round(transitions[0].posterior_weight / Z, 3),
                "outcomes":    transitions[0].typical_outcomes[:2],
            },
            "beta": {
                "name": display_pattern(transitions[1].to_pattern) if len(transitions) >= 2 else "Structural Fracture",
                "probability": round(
                    transitions[1].posterior_weight / Z if len(transitions) >= 2 else 0.3, 3
                ),
                "outcomes": (transitions[1].typical_outcomes[:2] if len(transitions) >= 2 else []),
            },
            # Bayesian compute trace
            "compute_trace": {
                "Z":               round(Z, 6),
                "n_transitions":   len(transitions),
                "n_active":        len(active),
                "normalization":   "sum of all posterior_weights",
                "posterior_formula": "prior_a × prior_b × lie_similarity",
                "epsilon_floor":   1e-4,
            },
        }

    result = PipelineResult(
        events=event_dicts,
        active_patterns=active_dicts,
        derived_patterns=derived_compat,
        top_transitions=transition_dicts,
        state_vector=state_vector,
        driving_factors=df_dicts,
        conclusion=conclusion,
        credibility=credibility,
        probability_tree=prob_tree,
    )

    logger.info(
        "EventedPipeline: complete | events=%d active=%d transitions=%d "
        "driving_factors=%d confidence=%.2f",
        len(events), len(active), len(transitions),
        len(driving_factors), credibility.get("composite_score", 0),
    )
    return result