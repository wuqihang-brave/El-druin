"""
推演灵魂 (Deduction Soul) – v3
================================

修复说明：
1. extract_mechanism_labels 默认 relation 硬编码为 CAMEOEventType.OPPOSE：
   原版当没有关键词匹配时，仍然给每条行赋予 OPPOSE + GEOPOLITICS。
   一篇板球新闻会被打上「公开反对/地缘政治」的标签，LLM 被强制做
   地缘政治分析，与内容完全无关。
   修复：没有关键词命中时跳过该行，不生成 MechanismLabel。

2. _KEYWORD_MECHANISM_MAP 缺少体育、商业、社会领域关键词：
   新增 SPORTS / BUSINESS / SOCIETY / SCIENCE 四个领域，防止这类
   新闻被强行映射到地缘政治框架。

3. DrivingFactorAggregator.aggregate 在没有机制标签时直接返回通用文案，
   不再硬造地缘政治驱动力。

4. _validate_and_structure_deduction 中 confidence 未做惩罚：
   若图谱路径为 0，LLM 仍可返回 confidence=0.9，造成幻觉置信度。
   修复：图谱路径为空时对 LLM 返回的 confidence 施加惩罚（最高 0.6）。

5. DEDUCTION_SOUL_SYSTEM_PROMPT 更新为 v3：
   明确要求 LLM 先判断新闻领域，再选择相应的本体框架推演，
   不允许把非地缘政治事件套用地缘政治模板。
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    from ontology.relation_schema import (  # type: ignore
        enrich_mechanism_labels_with_patterns,
        build_pattern_context_for_prompt,
    )
except ImportError:
    def enrich_mechanism_labels_with_patterns(labels):  # type: ignore
        return labels
    def build_pattern_context_for_prompt(labels):  # type: ignore
        return ""

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

_FALLBACK_SNIPPET_LENGTH = 120


# ---------------------------------------------------------------------------
# 1. 本体类型枚举 – CAMEO + FIBO + 扩展领域
# ---------------------------------------------------------------------------

class CAMEOEventType(str, Enum):
    SANCTION              = "制裁/经济封锁"
    MILITARY_ACTION       = "军事行动/武力威胁"
    DIPLOMATIC            = "外交接触/谈判"
    AID                   = "提供援助/资源转让"
    PROTEST               = "抗议/民间抵制"
    ARREST                = "逮捕/司法行动"
    AGREE                 = "达成协议/条约"
    OPPOSE                = "公开反对/谴责"
    SUPPLY_CHAIN          = "供应链调整/技术管控"
    INTEL_OP              = "情报操作/信息战"
    SPORTS_EVENT          = "体育竞技/赛事"
    BUSINESS_OP           = "商业运营/市场行为"
    SOCIAL_EVENT          = "社会事件/文化活动"
    SCIENCE_TECH          = "科学技术/研究发现"
    ECONOMIC_COOPERATION  = "经济合作/能源协议"
    ASSAULT               = "攻击/网络战"
    PROVIDE_AID           = "提供人道援助"
    TECHNOLOGY_TRANSFER   = "技术转让/出口管制"
    POLITICAL_EVENT       = "政治事件/选举"


class FIBORelationType(str, Enum):
    HOLDS_DEBT       = "持有债务"
    OWNS_EQUITY      = "持有股权"
    CURRENCY_PEG     = "货币挂钩/汇率联动"
    TRADE_FLOW       = "贸易往来"
    SANCTIONS_LIST   = "制裁名单列入"
    CENTRAL_BANK     = "央行政策传导"
    COMMODITY_LINK   = "大宗商品联动"
    CORPORATE_ACTION = "企业行为/并购重组"
    MARKET_EVENT     = "市场事件/金融波动"


class RelationDomain(str, Enum):
    GEOPOLITICS  = "geopolitics"
    ECONOMICS    = "economics"
    TECHNOLOGY   = "technology"
    MILITARY     = "military"
    HUMANITARIAN = "humanitarian"
    LEGAL        = "legal"
    SPORTS       = "sports"
    BUSINESS     = "business"
    SOCIETY      = "society"
    SCIENCE      = "science"
    ENERGY       = "energy"
    POLITICS     = "politics"


# ---------------------------------------------------------------------------
# 2. 机制标签
# ---------------------------------------------------------------------------

@dataclass
class MechanismLabel:
    source:    str
    target:    str
    relation:  str
    mechanism: str
    domain:    RelationDomain
    strength:  float = 0.75
    evidence:  str   = ""

    def to_prompt_line(self) -> str:
        return (
            f"[{self.domain.value}] {self.source} --({self.relation})--> {self.target} "
            f"| 机制: {self.mechanism} | 强度: {self.strength:.2f}"
        )


# ---------------------------------------------------------------------------
# 3. 驱动因素聚合器
# ---------------------------------------------------------------------------

class DrivingFactorAggregator:

    AGGREGATION_TEMPLATES: Dict[str, str] = {
        "制裁/经济封锁":      "{source}对{target}的制裁升级，导致{domain}领域脱钩加速",
        "军事行动/武力威胁":   "{source}对{target}的军事行动，触发区域安全格局重组",
        "供应链调整/技术管控": "{source}对{target}的技术/供应链管控，强化战略竞争态势",
        "达成协议/条约":       "{source}与{target}达成协议，为{domain}领域合作提供制度框架",
        "公开反对/谴责":       "{source}公开反对{target}立场，外交摩擦烈度上升",
        "提供援助/资源转让":   "{source}向{target}提供援助，改变{domain}领域力量对比",
        "贸易往来":            "{source}与{target}贸易往来变化，引发{domain}联动效应",
        "央行政策传导":        "{source}央行政策传导至{target}，{domain}市场流动性重分布",
        "企业行为/并购重组":   "{source}对{target}的并购/投资行为，重塑{domain}市场格局",
        "体育竞技/赛事":       "{source}在{domain}领域的赛事表现，影响相关实体的战略定位",
        "商业运营/市场行为":   "{source}的{domain}领域商业行为，驱动市场结构调整",
        "社会事件/文化活动":   "{source}相关的{domain}领域社会事件，影响舆论与政策走向",
        "科学技术/研究发现":   "{source}在{domain}领域的技术突破，推动相关生态重组",
        "DEFAULT":             "{source}与{target}之间的{relation}关系，驱动{domain}领域结构性变化",
    }

    def aggregate(self, mechanisms: List[MechanismLabel]) -> str:
        if not mechanisms:
            return "无直接图谱路径，基于通用本体逻辑推演"

        counter: Counter = Counter()
        for m in mechanisms:
            counter[(m.domain.value, m.relation)] += 1

        (top_domain, top_relation), _ = counter.most_common(1)[0]

        best: MechanismLabel = max(
            (m for m in mechanisms if m.domain.value == top_domain and m.relation == top_relation),
            key=lambda x: x.strength,
        )

        template = self.AGGREGATION_TEMPLATES.get(top_relation,
                   self.AGGREGATION_TEMPLATES["DEFAULT"])
        return template.format(
            source=best.source,
            target=best.target,
            relation=top_relation,
            domain=top_domain,
        )

    def build_mechanism_context_for_prompt(self, mechanisms: List[MechanismLabel]) -> str:
        if not mechanisms:
            return "【无直接图谱机制路径，请基于通用本体逻辑推演】"
        lines = ["【已提取机制标签（用于锚定推演）】"]
        for i, m in enumerate(mechanisms[:8], 1):
            lines.append(f"  {i}. {m.to_prompt_line()}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4. 关键词映射 – 扩展领域（体育/商业/社会/科学优先匹配）
# ---------------------------------------------------------------------------

_KEYWORD_MECHANISM_MAP: List[Tuple[List[str], Any, RelationDomain]] = [
    # ── 体育（放在最前，防止被地缘政治关键词淹没）────────────────────
    (["score", "cricket", "football", "soccer", "tennis", "basketball",
      "match", "tournament", "championship", "league", "player", "team",
      "goal", "wicket", "innings", "over", "run", "fifty", "century",
      "ipl", "nba", "nfl", "fifa", "olympics", "athlete", "coach",
      "stadium", "sport", "game", "win", "defeat", "beat", "bowling",
      "batting", "batter", "bowler", "squad", "series", "test match",
      "分", "进球", "比赛", "联赛", "球队", "运动员", "冠军", "得分"],
     CAMEOEventType.SPORTS_EVENT, RelationDomain.SPORTS),

    # ── 商业/企业 ─────────────────────────────────────────────────
    (["revenue", "profit", "earnings", "ipo", "merger", "acquisition",
      "startup", "ceo", "company", "corporation", "market share",
      "quarterly", "fiscal", "dividend", "stock", "shares", "listing",
      "投资", "营收", "上市", "并购", "企业", "股价", "财报", "利润"],
     FIBORelationType.CORPORATE_ACTION, RelationDomain.BUSINESS),

    # ── 科学/技术突破 ─────────────────────────────────────────────
    (["discovery", "breakthrough", "research", "study", "published",
      "scientists", "researchers", "laboratory", "experiment", "vaccine",
      "drug", "clinical", "genome", "quantum", "astronomy", "space",
      "rocket", "satellite", "probe",
      "研究", "发现", "突破", "科学家", "实验", "疫苗", "药物", "卫星"],
     CAMEOEventType.SCIENCE_TECH, RelationDomain.SCIENCE),

    # ── 社会/文化/选举 ─────────────────────────────────────────────
    (["election", "vote", "demonstration", "rally",
      "festival", "culture", "entertainment", "celebrity", "music",
      "film", "media", "social media", "viral",
      "选举", "投票", "文化", "娱乐", "名人", "社交媒体"],
     CAMEOEventType.SOCIAL_EVENT, RelationDomain.SOCIETY),

    # ── 地缘政治 ─────────────────────────────────────────────────
    (["sanction", "制裁", "embargo", "封锁"],
     CAMEOEventType.SANCTION, RelationDomain.GEOPOLITICS),
    (["export control", "出口管制", "供应链", "supply chain",
      "chip", "半导体", "技术封锁"],
     CAMEOEventType.SUPPLY_CHAIN, RelationDomain.TECHNOLOGY),
    (["military", "军事", "strike", "missile", "troops",
      "warplane", "airstrike", "navy", "army", "airspace"],
     CAMEOEventType.MILITARY_ACTION, RelationDomain.MILITARY),
    (["aid", "援助", "humanitarian", "人道"],
     CAMEOEventType.AID, RelationDomain.HUMANITARIAN),
    (["agree", "treaty", "协议", "deal", "协定", "accord", "agreement"],
     CAMEOEventType.AGREE, RelationDomain.GEOPOLITICS),
    (["oppose", "反对", "condemn", "谴责", "protest"],
     CAMEOEventType.OPPOSE, RelationDomain.GEOPOLITICS),

    # ── 经济/金融 ─────────────────────────────────────────────────
    (["trade", "贸易", "tariff", "关税"],
     FIBORelationType.TRADE_FLOW, RelationDomain.ECONOMICS),
    (["rate", "利率", "inflation", "通胀", "central bank", "央行",
      "fed", "ecb", "interest"],
     FIBORelationType.CENTRAL_BANK, RelationDomain.ECONOMICS),
    (["debt", "债务", "bond", "bonds", "credit"],
     FIBORelationType.HOLDS_DEBT, RelationDomain.ECONOMICS),

    # ── 能源与资源 ────────────────────────────────────────────────
    (["oil", "gas", "lng", "pipeline", "opec", "crude", "energy crisis",
      "power outage", "electricity", "nuclear power", "renewable", "solar",
      "wind energy", "coal", "fuel", "refinery", "petrochemical",
      "natural resources", "energy security", "energy transition",
      "carbon", "emissions", "decarbonization"],
     CAMEOEventType.ECONOMIC_COOPERATION, RelationDomain.ENERGY),

    # ── 气候与环境 ────────────────────────────────────────────────
    (["climate change", "global warming", "greenhouse", "carbon neutral",
      "net zero", "cop28", "cop29", "cop30", "paris agreement",
      "deforestation", "biodiversity", "sea level", "glacier", "permafrost",
      "methane", "carbon tax", "green deal", "climate summit", "extreme weather"],
     CAMEOEventType.PROTEST, RelationDomain.SOCIETY),

    # ── 网络安全与数字战 ──────────────────────────────────────────
    (["cyberattack", "hacking", "ransomware", "data breach", "malware",
      "phishing", "espionage", "spyware", "zero-day", "cybersecurity",
      "disinformation", "fake news", "influence operation", "information warfare",
      "election interference", "social media manipulation", "deepfake",
      "cyber warfare", "critical infrastructure attack"],
     CAMEOEventType.ASSAULT, RelationDomain.MILITARY),

    # ── 粮食与人道 ────────────────────────────────────────────────
    (["famine", "food security", "food crisis", "hunger", "malnutrition",
      "starvation", "aid convoy", "humanitarian corridor", "refugee camp",
      "displacement", "internally displaced", "idp", "unhcr", "wfp",
      "food prices", "grain supply", "harvest failure", "locust"],
     CAMEOEventType.PROVIDE_AID, RelationDomain.SOCIETY),

    # ── 金融与货币 ────────────────────────────────────────────────
    (["interest rate", "fed rate", "ecb rate", "rate hike", "rate cut",
      "monetary policy", "quantitative easing", "deflation",
      "currency crisis", "debt default", "sovereign debt", "imf bailout",
      "world bank", "bond yield", "credit rating", "capital flight",
      "foreign exchange", "forex", "dollar", "euro", "yuan", "yen",
      "banking crisis", "bank run", "financial contagion"],
     FIBORelationType.MARKET_EVENT, RelationDomain.ECONOMICS),

    # ── 科技与半导体 ──────────────────────────────────────────────
    (["semiconductor", "wafer", "tsmc", "nvidia", "ai chip",
      "tech ban", "entity list", "foundry", "fab",
      "lithography", "asml", "5g", "6g", "quantum computing",
      "artificial intelligence", "machine learning", "large language model",
      "chatgpt", "space launch", "space race"],
     CAMEOEventType.TECHNOLOGY_TRANSFER, RelationDomain.TECHNOLOGY),

    # ── 选举与政治变动 ────────────────────────────────────────────
    (["ballot", "polling", "referendum", "coup",
      "impeachment", "resignation", "cabinet reshuffle",
      "parliament", "congress", "senate", "political crisis",
      "demonstration", "uprising", "civil unrest", "martial law"],
     CAMEOEventType.POLITICAL_EVENT, RelationDomain.POLITICS),

    # ── 制裁扩展 ──────────────────────────────────────────────────
    (["secondary sanctions", "ofac", "sdn list", "treasury department",
      "asset freeze", "visa ban", "travel restriction", "arms embargo",
      "technology embargo", "financial exclusion", "swift exclusion",
      "correspondent banking", "de-dollarization"],
     CAMEOEventType.SANCTION, RelationDomain.GEOPOLITICS),
]

_ENTITY_PAIR_PATTERN = re.compile(
    r"([A-Za-z\u4e00-\u9fff][A-Za-z\u4e00-\u9fff\s]{1,30}?)"
    r"\s*(?:->|→|--\(?\w*\)?-->|CAUSES|AFFECTS|OPPOSES|SUPPORTS|INVOLVES)\s*"
    r"([A-Za-z\u4e00-\u9fff][A-Za-z\u4e00-\u9fff\s]{1,30})"
)


def _infer_domain_from_text(text: str) -> Optional[Tuple[Any, RelationDomain]]:
    """
    从文本推断领域，返回 (relation_type, domain) 或 None。
    修复：原版在没有命中时返回硬编码的 OPPOSE + GEOPOLITICS，
    现在改为返回 None，调用者负责跳过。
    """
    text_lower = text.lower()
    for keywords, relation, domain in _KEYWORD_MECHANISM_MAP:
        if any(kw in text_lower for kw in keywords):
            return (relation, domain)
    return None


def extract_mechanism_labels(
    graph_context: str,
    news_text: str = "",
    seed_entities: Optional[List[str]] = None,
) -> List[MechanismLabel]:
    """
    从图谱上下文和新闻文本中提取 MechanismLabel 列表。

    修复核心：
    - 没有关键词命中时跳过该行，不再默认注入 OPPOSE + GEOPOLITICS。
    - 先对整个 news_text 做全局领域推断，用于没有实体对的行的领域 fallback。
    """
    combined = (graph_context or "") + "\n" + (news_text or "")
    seeds = set(e.lower() for e in (seed_entities or []))
    labels: List[MechanismLabel] = []

    # 全局领域推断（基于完整新闻文本，比单行更稳定）
    global_domain_result = _infer_domain_from_text(news_text or "")

    for line in combined.splitlines():
        line = line.strip()
        if not line:
            continue

        pair_match = _ENTITY_PAIR_PATTERN.search(line)
        if pair_match:
            src = pair_match.group(1).strip()
            tgt = pair_match.group(2).strip()
        elif seeds:
            matched_seed = next((s for s in seeds if s in line.lower()), None)
            if not matched_seed:
                continue
            src = matched_seed.title()
            tgt = "相关实体"
        else:
            continue

        if len(src) < 2 or len(tgt) < 2:
            continue

        # 行级领域推断 → 全局 fallback → 跳过（不再硬写 OPPOSE）
        domain_result = _infer_domain_from_text(line)
        if domain_result is None:
            domain_result = global_domain_result
        if domain_result is None:
            logger.debug("No domain match for line, skipping: %s", line[:80])
            continue

        matched_relation, matched_domain = domain_result
        strength = 0.80 if any(s in line.lower() for s in seeds) else 0.65

        labels.append(MechanismLabel(
            source=src,
            target=tgt,
            relation=matched_relation if isinstance(matched_relation, str) else matched_relation.value,
            mechanism=line[:100],
            domain=matched_domain,
            strength=strength,
            evidence=line[:200],
        ))

    deduped: Dict[Tuple[str, str, str], MechanismLabel] = {}
    for lbl in labels:
        key = (lbl.source.lower(), lbl.target.lower(), lbl.relation)
        if key not in deduped or lbl.strength > deduped[key].strength:
            deduped[key] = lbl

    return list(deduped.values())


# ---------------------------------------------------------------------------
# 5. 数据类
# ---------------------------------------------------------------------------

class ScenarioType(Enum):
    CONTINUATION     = "现状延续路径"
    STRUCTURAL_BREAK = "结构性断裂路径"
    BIFURCATION      = "分岔演化路径"


@dataclass
class CausalChain:
    source_fact:         str
    mechanism:           str
    intermediate_effect: str
    final_outcome:       str
    entities_involved:   List[str] = field(default_factory=list)
    confidence:          float = 0.8

    def to_text(self) -> str:
        return (
            f"{self.source_fact} "
            f"--[{self.mechanism}]--> "
            f"{self.intermediate_effect} "
            f"--> {self.final_outcome}"
        )


@dataclass
class Scenario:
    name:                      str
    scenario_type:             ScenarioType
    causal_chain:              CausalChain
    probability:               float
    description:               str = ""
    grounding_paths:           List[str] = field(default_factory=list)
    verification_requirements: List[str] = field(default_factory=list)
    mechanism_labels:          List[MechanismLabel] = field(default_factory=list)


@dataclass
class DeductionResult:
    driving_factor:       str
    scenario_alpha:       Scenario
    scenario_beta:        Scenario
    verification_gap:     str
    deduction_confidence: float
    graph_evidence:       str = ""
    mechanism_summary:    str = ""

    def to_strict_json(self) -> Dict[str, Any]:
        return {
            "driving_factor":    self.driving_factor,
            "mechanism_summary": self.mechanism_summary,
            "scenario_alpha": {
                "name":            self.scenario_alpha.name,
                "description":     self.scenario_alpha.description,
                "causal_chain":    self.scenario_alpha.causal_chain.to_text(),
                "mechanism":       self.scenario_alpha.causal_chain.mechanism,
                "entities":        self.scenario_alpha.causal_chain.entities_involved,
                "grounding_paths": self.scenario_alpha.grounding_paths,
                "probability":     self.scenario_alpha.probability,
            },
            "scenario_beta": {
                "name":              self.scenario_beta.name,
                "description":       self.scenario_beta.description,
                "causal_chain":      self.scenario_beta.causal_chain.to_text(),
                "mechanism":         self.scenario_beta.causal_chain.mechanism,
                "trigger_condition": (
                    self.scenario_beta.grounding_paths[0]
                    if self.scenario_beta.grounding_paths else "Unknown"
                ),
                "probability": self.scenario_beta.probability,
            },
            "verification_gap": self.verification_gap,
            "confidence":        self.deduction_confidence,
            "graph_evidence":    self.graph_evidence,
        }


# ---------------------------------------------------------------------------
# 6. System Prompt v3 – 域自适应推演
# ---------------------------------------------------------------------------

DEDUCTION_SOUL_SYSTEM_PROMPT_V3 = """\
你是 EL'druin，一台极度严谨的"本体论情报推演机"。

【核心约束】
1. 首先判断新闻事件的领域（体育/商业/地缘政治/经济/科技/社会），
   然后在该领域的本体框架内推演，严禁跨领域套用模板。
   - 体育新闻 → 赛事结果/运动员表现/联赛影响 框架
   - 商业新闻 → 市场/竞争/盈利/投资 框架
   - 地缘政治 → 国家/联盟/制裁/军事 框架
   - 科学技术 → 研究影响/产业应用/标准竞争 框架
2. 你的推演必须锚定到【已提取机制标签】中的具体 relation/mechanism。
3. 若机制标签为空或与新闻内容不符，基于新闻文本本身推演，
   在 graph_evidence 中注明"无直接KG路径，基于文本推演"。
4. causal_chain 必须是4步结构：source_fact → mechanism → intermediate_effect → final_outcome。
5. 严禁输出"可能"、"局势将持续演变"等空洞短语。
6. 严格输出 JSON，不加任何 markdown、说明文字或前言。
7. confidence 字段必须诚实反映证据强度：
   - 有多条KG路径支撑 → 0.65-0.85
   - 仅新闻文本，无KG路径 → 0.35-0.60
   - 完全猜测 → 低于0.35
   禁止返回 0.9 以上的置信度，除非有多条KG路径证据。

【推演步骤】
Step 1: 识别新闻的核心领域和主要参与实体。
Step 2: 从机制标签中找出与新闻领域最匹配的关系类型 → 这是 driving_factor 的来源。
Step 3: 沿 driving_factor 推演"如果该机制继续强化"的路径 → scenario_alpha。
Step 4: 推演关键节点失效时的路径 → scenario_beta。
Step 5: 指出当前推演中最大的数据空白 → verification_gap。
"""


# Backwards-compatible alias so callers that import DEDUCTION_SOUL_SYSTEM_PROMPT
# (without the _V3 suffix) continue to work.
DEDUCTION_SOUL_SYSTEM_PROMPT = DEDUCTION_SOUL_SYSTEM_PROMPT_V3

# ---------------------------------------------------------------------------
# 7. DeductionEngine v3
# ---------------------------------------------------------------------------

class DeductionEngine:

    def __init__(self, llm_service: Any) -> None:
        self.llm        = llm_service
        self.aggregator = DrivingFactorAggregator()
        self.logger     = logger

    def deduce_from_ontological_paths(
        self,
        news_summary: str,
        ontological_context: str,
        seed_entities: List[str],
    ) -> DeductionResult:
        """推演灵魂激活 v3"""
        mechanisms = extract_mechanism_labels(
            graph_context=ontological_context,
            news_text=news_summary,
            seed_entities=seed_entities,
        )
        try:
            mechanisms = enrich_mechanism_labels_with_patterns(mechanisms)
            pattern_context = build_pattern_context_for_prompt(mechanisms)
        except Exception:
            pattern_context = ""

        self.logger.info(
            "Extracted %d mechanism labels: %s",
            len(mechanisms),
            [m.relation for m in mechanisms[:5]],
        )

        # 记录是否有图谱证据，用于 confidence 惩罚
        has_graph_evidence = (
            len(mechanisms) > 0
            and bool(ontological_context.strip())
            and "0 1-hop + 0 2-hop" not in ontological_context
        )

        pre_driving_factor = self.aggregator.aggregate(mechanisms)
        mechanism_context  = self.aggregator.build_mechanism_context_for_prompt(mechanisms)
        self.logger.info("Pre-LLM driving factor: %s", pre_driving_factor)

        prompt = self._build_deduction_prompt(
            news_text=news_summary,
            ontological_context=ontological_context,
            mechanism_context=mechanism_context,
            pre_driving_factor=pre_driving_factor,
            pattern_context=pattern_context,
        )
        self.logger.info("Activating Deduction Soul v3...")

        response: Any = None
        try:
            response = self.llm.call(
                prompt=prompt,
                system=DEDUCTION_SOUL_SYSTEM_PROMPT_V3,
                temperature=0.15,
                max_tokens=1800,
                response_format="json",
            )

            if isinstance(response, dict):
                deduction_json = response
            else:
                text = self._clean_json_text(str(response))
                deduction_json = json.loads(text)

            result = self._validate_and_structure_deduction(
                deduction_json,
                mechanisms=mechanisms,
                pre_driving_factor=pre_driving_factor,
                has_graph_evidence=has_graph_evidence,
            )
            self.logger.info("Deduction complete. Confidence: %.2f", result.deduction_confidence)
            return result

        except (json.JSONDecodeError, ValueError) as exc:
            self.logger.error("LLM returned invalid JSON: %s", exc)
            try:
                fixed = self._heuristic_json_fix(str(response))
                deduction_json = json.loads(fixed)
                return self._validate_and_structure_deduction(
                    deduction_json,
                    mechanisms=mechanisms,
                    pre_driving_factor=pre_driving_factor,
                    has_graph_evidence=has_graph_evidence,
                )
            except Exception:
                return self._fallback_deduction(
                    news_summary, ontological_context,
                    mechanisms=mechanisms, pre_driving_factor=pre_driving_factor,
                )
        except Exception as exc:
            self.logger.error("Deduction Soul failed unexpectedly: %s", exc)
            return self._fallback_deduction(
                news_summary, ontological_context,
                mechanisms=mechanisms, pre_driving_factor=pre_driving_factor,
            )

    # ------------------------------------------------------------------
    # Prompt builder
    # ------------------------------------------------------------------

    def _build_deduction_prompt(
        self,
        news_text: str,
        ontological_context: str,
        mechanism_context: str,
        pre_driving_factor: str,
        pattern_context: str,
    ) -> str:
        kg_section = (
            ontological_context.strip()
            if ontological_context.strip() and "0 1-hop + 0 2-hop" not in ontological_context
            else "（当前无图谱路径数据，请基于新闻文本推演，confidence 不得超过 0.60）"
        )
        return f"""\
你正在执行本体论因果推演任务。

【新闻事件】
{news_text}

【知识图谱本体路径（1-hop & 2-hop）】
{kg_section}

{mechanism_context}

{pattern_context if pattern_context else ""}

【预提取驱动因素（基于图谱统计归纳，供你参考和细化）】
{pre_driving_factor}

【重要提醒】
- 先判断新闻领域（体育/商业/地缘政治/经济/科技/社会），在该领域框架内推演。
- 如果上方图谱路径为空，confidence 不得超过 0.60。
- 只输出 JSON，不加任何说明。

JSON schema:
{{
  "driving_factor": "...",
  "scenario_alpha": {{
    "name": "...",
    "probability": 0.0-1.0,
    "causal_chain": "A --> [机制] --> B --> C",
    "description": "..."
  }},
  "scenario_beta": {{
    "name": "...",
    "probability": 0.0-1.0,
    "causal_chain": "A --> [机制] --> B --> C",
    "trigger_condition": "...",
    "description": "..."
  }},
  "confidence": 0.0-1.0,
  "graph_evidence": "...",
  "verification_gap": "..."
}}
"""

    # ------------------------------------------------------------------
    # Validation & structuring
    # ------------------------------------------------------------------

    def _validate_and_structure_deduction(
        self,
        json_response: Dict[str, Any],
        mechanisms: List[MechanismLabel],
        pre_driving_factor: str,
        has_graph_evidence: bool = False,
    ) -> DeductionResult:
        driving_factor = json_response.get("driving_factor", "").strip()
        if not driving_factor or driving_factor.lower() in ("unknown", "unable to determine"):
            driving_factor = pre_driving_factor

        alpha_data  = json_response.get("scenario_alpha") or {}
        alpha_chain = self._parse_causal_chain_v2(
            alpha_data.get("causal_chain", ""),
            alpha_data.get("entities", []),
        )
        alpha = Scenario(
            name=alpha_data.get("name", "现状延续路径"),
            scenario_type=ScenarioType.CONTINUATION,
            causal_chain=alpha_chain,
            probability=float(alpha_data.get("probability", 0.65)),
            description=alpha_data.get("description", ""),
            grounding_paths=alpha_data.get("grounding_paths") or [],
            mechanism_labels=mechanisms,
        )

        beta_data  = json_response.get("scenario_beta") or {}
        beta_chain = self._parse_causal_chain_v2(
            beta_data.get("causal_chain", ""),
            [],
        )
        trigger = beta_data.get("trigger_condition", "")
        beta = Scenario(
            name=beta_data.get("name", "结构性断裂路径"),
            scenario_type=ScenarioType.STRUCTURAL_BREAK,
            causal_chain=beta_chain,
            probability=float(beta_data.get("probability", 0.35)),
            description=beta_data.get("description", ""),
            grounding_paths=[trigger] if trigger else [],
            mechanism_labels=mechanisms,
        )

        verification_gap = json_response.get("verification_gap", "未指定数据空白")

        # ── 修复：诚实 confidence 约束 ─────────────────────────────────
        raw_conf = float(json_response.get("confidence", 0.5))
        if not has_graph_evidence:
            confidence = min(raw_conf, 0.60)
            if raw_conf > 0.60:
                self.logger.warning(
                    "Confidence hallucination: LLM returned %.2f but graph evidence is empty. "
                    "Capping at 0.60.", raw_conf,
                )
        else:
            confidence = min(raw_conf, 0.90)

        self.logger.info(
            "Deduction validated. Confidence: %.2f (raw=%.2f, has_graph=%s)",
            confidence, raw_conf, has_graph_evidence,
        )
        return DeductionResult(
            driving_factor=driving_factor,
            scenario_alpha=alpha,
            scenario_beta=beta,
            verification_gap=verification_gap,
            deduction_confidence=confidence,
            graph_evidence=json_response.get("graph_evidence", ""),
            mechanism_summary=self.aggregator.aggregate(mechanisms),
        )

    def _parse_causal_chain_v2(
        self, chain_text: str, entities: List[str]
    ) -> CausalChain:
        parts = [p.strip() for p in chain_text.split("-->")]
        mechanism = ""
        cleaned_parts: List[str] = []
        for p in parts:
            bracket = re.search(r"\[(.+?)\]", p)
            if bracket:
                mechanism = bracket.group(1)
                cleaned_parts.append(re.sub(r"\[.+?\]", "", p).strip())
            else:
                cleaned_parts.append(p)
        return CausalChain(
            source_fact=cleaned_parts[0] if len(cleaned_parts) > 0 else chain_text,
            mechanism=mechanism or (cleaned_parts[1] if len(cleaned_parts) > 1 else ""),
            intermediate_effect=cleaned_parts[2] if len(cleaned_parts) > 2 else "",
            final_outcome=cleaned_parts[3] if len(cleaned_parts) > 3 else (
                cleaned_parts[-1] if cleaned_parts else ""
            ),
            entities_involved=list(entities),
            confidence=0.8,
        )

    @staticmethod
    def _clean_json_text(text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z0-9]*\n?", "", text)
            if text.endswith("```"):
                text = text[:-3].strip()
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start: end + 1]
        return text

    @staticmethod
    def _heuristic_json_fix(raw_text: str) -> str:
        fixed = re.sub(
            r'"confidence"\s*:\s*([\'"])?\s*$',
            '"confidence": 0.5',
            raw_text,
            flags=re.MULTILINE,
        )
        start, end = fixed.find("{"), fixed.rfind("}")
        if start != -1 and end != -1 and end > start:
            fixed = fixed[start: end + 1]
        return fixed

    # ------------------------------------------------------------------
    # Fallback deduction
    # ------------------------------------------------------------------

    def _fallback_deduction(
        self,
        news_summary: str,
        ontological_context: str,
        mechanisms: Optional[List[MechanismLabel]] = None,
        pre_driving_factor: str = "",
    ) -> DeductionResult:
        self.logger.warning("Falling back to structured deduction...")
        mechanisms = mechanisms or []
        snippet = news_summary[:_FALLBACK_SNIPPET_LENGTH].strip() if news_summary else "当前新闻事件"
        driving_factor = pre_driving_factor or f"基于新闻摘要推演：{snippet}"

        if mechanisms:
            best = max(mechanisms, key=lambda m: m.strength)
            alpha_chain = CausalChain(
                source_fact=f"{best.source}对{best.target}的{best.relation}",
                mechanism=best.mechanism[:60],
                intermediate_effect=f"{best.domain.value}领域格局收紧",
                final_outcome="相关实体被迫调整战略定位，维持现有均衡",
            )
            beta_chain = CausalChain(
                source_fact=f"{best.source}对{best.target}的{best.relation}升级",
                mechanism=f"{best.mechanism[:60]}（极端情景）",
                intermediate_effect="关键节点断裂，第三方被迫选边站队",
                final_outcome="现有格局加速重组，出现系统性断裂",
            )
        else:
            alpha_chain = CausalChain(
                source_fact=snippet,
                mechanism="现有格局延续",
                intermediate_effect="相关实体维持当前行为模式",
                final_outcome="局势渐进演变，无系统性断裂",
            )
            beta_chain = CausalChain(
                source_fact=snippet,
                mechanism="关键节点出现突变或外部冲击",
                intermediate_effect="现有均衡被打破，极端博弈激活",
                final_outcome="相关实体被迫采取对抗或撤退策略",
            )

        return DeductionResult(
            driving_factor=driving_factor,
            scenario_alpha=Scenario(
                name="现状延续路径",
                scenario_type=ScenarioType.CONTINUATION,
                causal_chain=alpha_chain,
                probability=0.65,
                description="基于现有机制标签的延续路径（兜底推演）",
                grounding_paths=[],
                mechanism_labels=mechanisms,
            ),
            scenario_beta=Scenario(
                name="结构性断裂路径",
                scenario_type=ScenarioType.STRUCTURAL_BREAK,
                causal_chain=beta_chain,
                probability=0.35,
                description="关键节点失效路径（兜底推演）",
                grounding_paths=[],
                mechanism_labels=mechanisms,
            ),
            verification_gap="LLM 回应格式错误；推演基于兜底逻辑，建议补充 KuzuDB 数据后重新分析",
            deduction_confidence=0.40,
            graph_evidence="通用本体逻辑推演（无直接KG路径）",
            mechanism_summary=self.aggregator.aggregate(mechanisms),
        )