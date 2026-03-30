"""
推演灵魂 (Deduction Soul) – v2
================================
强化版本：从"展示"转向"推演"

核心改进：
1. 引入「机制标签」(MechanismLabel)：每条因果边都附加 mechanism + domain
2. 引入「驱动因素聚合器」(DrivingFactorAggregator)：
   从图谱关系中归纳结构性驱动力（而非靠 LLM 猜测）
3. CAMEO / FIBO 事件类型枚举：统一事件本体类型
4. 更严格的因果链结构：source → mechanism → target → effect（4步）
5. 推演时 LLM 被强制锚定到具体的 mechanism 标签上

参考本体：
- CAMEO (Conflict and Mediation Event Observations) 事件类型体系
- FIBO (Financial Industry Business Ontology) 金融实体关系
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

_FALLBACK_SNIPPET_LENGTH = 120


# ---------------------------------------------------------------------------
# 1. 本体类型枚举 – CAMEO + FIBO 融合
# ---------------------------------------------------------------------------

class CAMEOEventType(str, Enum):
    """CAMEO 事件类型（国际关系核心动词）"""
    SANCTION        = "制裁/经济封锁"
    MILITARY_ACTION = "军事行动/武力威胁"
    DIPLOMATIC      = "外交接触/谈判"
    AID             = "提供援助/资源转让"
    PROTEST         = "抗议/民间抵制"
    ARREST          = "逮捕/司法行动"
    AGREE           = "达成协议/条约"
    OPPOSE          = "公开反对/谴责"
    SUPPLY_CHAIN    = "供应链调整/技术管控"
    INTEL_OP        = "情报操作/信息战"


class FIBORelationType(str, Enum):
    """FIBO 金融本体关系类型"""
    HOLDS_DEBT      = "持有债务"
    OWNS_EQUITY     = "持有股权"
    CURRENCY_PEG    = "货币挂钩/汇率联动"
    TRADE_FLOW      = "贸易往来"
    SANCTIONS_LIST  = "制裁名单列入"
    CENTRAL_BANK    = "央行政策传导"
    COMMODITY_LINK  = "大宗商品联动"


class RelationDomain(str, Enum):
    GEOPOLITICS  = "geopolitics"
    ECONOMICS    = "economics"
    TECHNOLOGY   = "technology"
    MILITARY     = "military"
    HUMANITARIAN = "humanitarian"
    LEGAL        = "legal"


# ---------------------------------------------------------------------------
# 2. 机制标签 – 附加在每条因果边上
# ---------------------------------------------------------------------------

@dataclass
class MechanismLabel:
    """
    描述一条因果边的「驱动机制」。

    示例：
        source="US", target="China",
        relation="SANCTION",
        mechanism="技术出口管制升级",
        domain="technology",
        strength=0.85
    """
    source:    str
    target:    str
    relation:  str                   # 来自 CAMEOEventType / FIBORelationType
    mechanism: str                   # 人类可读的机制描述（1句话）
    domain:    RelationDomain
    strength:  float = 0.75          # 关系强度（从图谱路径或启发式估算）
    evidence:  str   = ""            # 支持证据片段

    def to_prompt_line(self) -> str:
        return (
            f"[{self.domain.value}] {self.source} --({self.relation})--> {self.target} "
            f"| 机制: {self.mechanism} | 强度: {self.strength:.2f}"
        )


# ---------------------------------------------------------------------------
# 3. 驱动因素聚合器
# ---------------------------------------------------------------------------

class DrivingFactorAggregator:
    """
    从已提取的 MechanismLabel 列表中，归纳「结构性驱动力」。

    逻辑：
    - 统计出现最多的 domain 和 relation 组合
    - 将同方向的多条边聚合成一个 driving_factor 陈述
    - 例如：3条 US→China SANCTION/SUPPLY_CHAIN 边 →
        "美国对华制裁升级与供应链脱钩构成本轮事件的技术-地缘双重驱动力"
    """

    AGGREGATION_TEMPLATES: Dict[str, str] = {
        "SANCTION":        "{source}对{target}的制裁升级，导致{domain}领域脱钩加速",
        "MILITARY_ACTION": "{source}对{target}的军事行动，触发区域安全格局重组",
        "SUPPLY_CHAIN":    "{source}对{target}的技术/供应链管控，强化战略竞争态势",
        "AGREE":           "{source}与{target}达成协议，为{domain}领域合作提供制度框架",
        "OPPOSE":          "{source}公开反对{target}立场，外交摩擦烈度上升",
        "AID":             "{source}向{target}提供援助，改变{domain}领域力量对比",
        "TRADE_FLOW":      "{source}与{target}贸易往来变化，引发{domain}联动效应",
        "CENTRAL_BANK":    "{source}央行政策传导至{target}，{domain}市场流动性重分布",
        "DEFAULT":         "{source}与{target}之间的{relation}关系，驱动{domain}领域结构性变化",
    }

    def aggregate(self, mechanisms: List[MechanismLabel]) -> str:
        if not mechanisms:
            return "无直接图谱路径，基于通用本体逻辑推演"

        # 按 domain + relation 分组计数
        counter: Counter = Counter()
        for m in mechanisms:
            counter[(m.domain.value, m.relation)] += 1

        # 取频率最高的组合
        (top_domain, top_relation), _ = counter.most_common(1)[0]

        # 找该组合中强度最高的一条边
        best: MechanismLabel = max(
            (m for m in mechanisms if m.domain.value == top_domain and m.relation == top_relation),
            key=lambda x: x.strength,
        )

        template = self.AGGREGATION_TEMPLATES.get(
            top_relation, self.AGGREGATION_TEMPLATES["DEFAULT"]
        )
        return template.format(
            source=best.source,
            target=best.target,
            relation=top_relation,
            domain=top_domain,
        )

    def build_mechanism_context_for_prompt(self, mechanisms: List[MechanismLabel]) -> str:
        """将 MechanismLabel 列表转为结构化 prompt 片段。"""
        if not mechanisms:
            return "【无直接图谱机制路径，请基于通用本体逻辑推演】"
        lines = ["【已提取机制标签（用于锚定推演）】"]
        for i, m in enumerate(mechanisms[:8], 1):
            lines.append(f"  {i}. {m.to_prompt_line()}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4. 从图谱上下文字符串中提取 MechanismLabel
# ---------------------------------------------------------------------------

# 关键词 → (CAMEOEventType, RelationDomain)
_KEYWORD_MECHANISM_MAP: List[Tuple[List[str], str, RelationDomain]] = [
    (["sanction", "制裁", "embargo", "封锁", "ban"],
     CAMEOEventType.SANCTION, RelationDomain.GEOPOLITICS),
    (["export control", "出口管制", "供应链", "supply chain", "chip", "半导体", "技术封锁"],
     CAMEOEventType.SUPPLY_CHAIN, RelationDomain.TECHNOLOGY),
    (["military", "军事", "strike", "attack", "missile", "troops"],
     CAMEOEventType.MILITARY_ACTION, RelationDomain.MILITARY),
    (["aid", "援助", "humanitarian", "人道"],
     CAMEOEventType.AID, RelationDomain.HUMANITARIAN),
    (["agree", "treaty", "协议", "deal", "协定", "accord"],
     CAMEOEventType.AGREE, RelationDomain.GEOPOLITICS),
    (["oppose", "反对", "condemn", "谴责", "protest"],
     CAMEOEventType.OPPOSE, RelationDomain.GEOPOLITICS),
    (["trade", "贸易", "tariff", "关税", "import", "export"],
     FIBORelationType.TRADE_FLOW, RelationDomain.ECONOMICS),
    (["rate", "利率", "inflation", "通胀", "central bank", "央行", "fed", "ecb"],
     FIBORelationType.CENTRAL_BANK, RelationDomain.ECONOMICS),
    (["debt", "债务", "bond", "bonds", "credit"],
     FIBORelationType.HOLDS_DEBT, RelationDomain.ECONOMICS),
]

# 实体对提取正则：匹配 "EntityA -> rel -> EntityB" 或 "EntityA CAUSES EntityB" 形式
_ENTITY_PAIR_PATTERN = re.compile(
    r"([A-Za-z\u4e00-\u9fff][A-Za-z\u4e00-\u9fff\s]{1,30}?)"
    r"\s*(?:->|→|--\(?\w*\)?-->|CAUSES|AFFECTS|OPPOSES|SUPPORTS|INVOLVES)\s*"
    r"([A-Za-z\u4e00-\u9fff][A-Za-z\u4e00-\u9fff\s]{1,30})"
)


def extract_mechanism_labels(
    graph_context: str,
    news_text: str = "",
    seed_entities: Optional[List[str]] = None,
) -> List[MechanismLabel]:
    """
    从图谱上下文（字符串格式）中提取 MechanismLabel 列表。

    策略：
    1. 在 graph_context + news_text 中扫描实体对
    2. 对每个句子做关键词匹配，分配 relation + domain
    3. 如果有 seed_entities，优先保留与之相关的边
    """
    combined = (graph_context or "") + "\n" + (news_text or "")
    seeds = set(e.lower() for e in (seed_entities or []))
    labels: List[MechanismLabel] = []

    for line in combined.splitlines():
        line = line.strip()
        if not line:
            continue

        # 尝试提取实体对
        pair_match = _ENTITY_PAIR_PATTERN.search(line)
        if pair_match:
            src = pair_match.group(1).strip()
            tgt = pair_match.group(2).strip()
        elif seeds:
            # 没有匹配到箭头，尝试从 seed 实体 + 行内容构造单向边
            matched_seed = next((s for s in seeds if s in line.lower()), None)
            if not matched_seed:
                continue
            src = matched_seed.title()
            tgt = "相关实体"
        else:
            continue

        # 跳过非常短的"实体"（可能是误匹配）
        if len(src) < 2 or len(tgt) < 2:
            continue

        # 关键词匹配确定 relation + domain
        line_lower = line.lower()
        matched_relation, matched_domain = CAMEOEventType.OPPOSE, RelationDomain.GEOPOLITICS
        for keywords, relation, domain in _KEYWORD_MECHANISM_MAP:
            if any(kw in line_lower for kw in keywords):
                matched_relation = relation
                matched_domain = domain
                break

        # 估算强度（暂用固定值；可接入 KuzuDB 权重字段）
        strength = 0.80 if any(s in line.lower() for s in seeds) else 0.65

        labels.append(MechanismLabel(
            source=src,
            target=tgt,
            relation=matched_relation if isinstance(matched_relation, str) else matched_relation.value,
            mechanism=line[:100],   # 原始行作为机制描述
            domain=matched_domain,
            strength=strength,
            evidence=line[:200],
        ))

    # 去重（source+target+relation 相同则保留强度最高的）
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
    """
    严格四步因果链：source_fact → mechanism → intermediate_effect → final_outcome

    对应推演逻辑：
        "由于 [source_fact]，通过 [mechanism] 机制，
         首先导致 [intermediate_effect]，最终引发 [final_outcome]"
    """
    source_fact:          str
    mechanism:            str   # 驱动机制（对应 MechanismLabel.mechanism）
    intermediate_effect:  str   # 中间效应
    final_outcome:        str   # 最终结果
    entities_involved:    List[str] = field(default_factory=list)
    confidence:           float = 0.8

    def to_text(self) -> str:
        return (
            f"{self.source_fact} "
            f"--[{self.mechanism}]--> "
            f"{self.intermediate_effect} "
            f"--> {self.final_outcome}"
        )


@dataclass
class Scenario:
    name:                    str
    scenario_type:           ScenarioType
    causal_chain:            CausalChain
    probability:             float
    description:             str = ""
    grounding_paths:         List[str] = field(default_factory=list)
    verification_requirements: List[str] = field(default_factory=list)
    mechanism_labels:        List[MechanismLabel] = field(default_factory=list)


@dataclass
class DeductionResult:
    driving_factor:      str
    scenario_alpha:      Scenario
    scenario_beta:       Scenario
    verification_gap:    str
    deduction_confidence: float
    graph_evidence:      str = ""
    mechanism_summary:   str = ""   # 聚合后的机制摘要（供前端展示）

    def to_strict_json(self) -> Dict[str, Any]:
        return {
            "driving_factor":    self.driving_factor,
            "mechanism_summary": self.mechanism_summary,
            "scenario_alpha": {
                "name":           self.scenario_alpha.name,
                "description":    self.scenario_alpha.description,
                "causal_chain":   self.scenario_alpha.causal_chain.to_text(),
                "mechanism":      self.scenario_alpha.causal_chain.mechanism,
                "entities":       self.scenario_alpha.causal_chain.entities_involved,
                "grounding_paths": self.scenario_alpha.grounding_paths,
                "probability":    self.scenario_alpha.probability,
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
# 6. 推演灵魂 System Prompt（v2 – 强制锚定机制标签）
# ---------------------------------------------------------------------------

DEDUCTION_SOUL_SYSTEM_PROMPT_V2 = """\
你是 EL'druin，一台极度严谨的"本体论情报推演机"。

【核心约束】
1. 你的推演必须锚定到【已提取机制标签】中的具体 relation/mechanism，绝不允许脱离这些标签说废话。
2. 若机制标签为空，可基于通用本体逻辑（CAMEO/FIBO），但必须在 graph_evidence 中注明"无直接KG路径"。
3. causal_chain 必须是4步结构：source_fact → mechanism → intermediate_effect → final_outcome。
4. driving_factor 必须引用至少一个机制标签的 source/target/relation 三元组。
5. 严禁输出"可能"、"局势将持续演变"、"黑天鹅事件"等空洞短语。
6. 严格输出 JSON，不加任何 markdown、说明文字或前言。

【推演步骤】
Step 1: 从机制标签中找出强度最高、出现最多的关系类型 → 这是 driving_factor 的来源。
Step 2: 沿 driving_factor 的主要机制，推演"如果该机制继续强化"的路径 → scenario_alpha。
Step 3: 找出 scenario_alpha 的关键依赖节点，推演"如果该节点失效/逆转"的路径 → scenario_beta。
Step 4: 指出当前推演中最大的数据空白 → verification_gap。
"""


# ---------------------------------------------------------------------------
# 7. DeductionEngine v2
# ---------------------------------------------------------------------------

class DeductionEngine:
    """
    推演灵魂核心引擎 v2

    新增能力：
    - 在调用 LLM 前，先通过 extract_mechanism_labels + DrivingFactorAggregator
      从图谱上下文中归纳结构性驱动力，将其作为强约束注入 prompt。
    - LLM 被强制从机制标签中选取锚点，而非自由发挥。
    """

    def __init__(self, llm_service: Any) -> None:
        self.llm = llm_service
        self.aggregator = DrivingFactorAggregator()
        self.logger = logger

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def deduce_from_ontological_paths(
        self,
        news_summary: str,
        ontological_context: str,
        seed_entities: List[str],
    ) -> DeductionResult:
        """【CORE METHOD】推演灵魂激活 v2"""
        # ── Pre-LLM: 从图谱上下文中提取机制标签 ──────────────────────
        mechanisms = extract_mechanism_labels(
            graph_context=ontological_context,
            news_text=news_summary,
            seed_entities=seed_entities,
        )
        self.logger.info(
            "Extracted %d mechanism labels: %s",
            len(mechanisms),
            [m.relation for m in mechanisms[:5]],
        )

        # 归纳驱动因素（不依赖 LLM）
        pre_driving_factor = self.aggregator.aggregate(mechanisms)
        mechanism_context  = self.aggregator.build_mechanism_context_for_prompt(mechanisms)
        self.logger.info("Pre-LLM driving factor: %s", pre_driving_factor)

        # ── Build & call LLM ──────────────────────────────────────────
        prompt = self._build_deduction_prompt(
            news_text=news_summary,
            ontological_context=ontological_context,
            mechanism_context=mechanism_context,
            pre_driving_factor=pre_driving_factor,
        )
        self.logger.info("Activating Deduction Soul v2...")
        self.logger.info("Analyzing event: %s...", news_summary[:100])
        self.logger.info("Ontological context length: %d", len(ontological_context))

        response: Any = None
        try:
            response = self.llm.call(
                prompt=prompt,
                system=DEDUCTION_SOUL_SYSTEM_PROMPT_V2,
                temperature=0.15,
                max_tokens=1800,
                response_format="json",
            )

            self.logger.debug(
                "Raw LLM response (type=%s): %r",
                type(response), response,
            )

            if isinstance(response, dict):
                deduction_json = response
            else:
                text = self._clean_json_text(str(response))
                self.logger.debug("Cleaned LLM JSON: %r", text)
                deduction_json = json.loads(text)

            self.logger.debug(
                "Parsed JSON: %s",
                json.dumps(deduction_json, ensure_ascii=False),
            )

            result = self._validate_and_structure_deduction(
                deduction_json,
                mechanisms=mechanisms,
                pre_driving_factor=pre_driving_factor,
            )
            self.logger.info(
                "Deduction complete. Confidence: %.2f", result.deduction_confidence
            )
            return result

        except (json.JSONDecodeError, ValueError) as exc:
            self.logger.error("LLM returned invalid JSON: %s", exc)
            self.logger.error("Raw response: %r", response)
            try:
                fixed = self._heuristic_json_fix(str(response))
                deduction_json = json.loads(fixed)
                self.logger.info("Heuristic JSON fix succeeded.")
                return self._validate_and_structure_deduction(
                    deduction_json,
                    mechanisms=mechanisms,
                    pre_driving_factor=pre_driving_factor,
                )
            except Exception as fix_exc:
                self.logger.error("Heuristic fix failed: %s", fix_exc)
                return self._fallback_deduction(
                    news_summary, ontological_context,
                    mechanisms=mechanisms,
                    pre_driving_factor=pre_driving_factor,
                )

        except Exception as exc:  # noqa: BLE001
            self.logger.error("Deduction Soul failed unexpectedly: %s", exc)
            self.logger.error("Raw response: %r", response)
            return self._fallback_deduction(
                news_summary, ontological_context,
                mechanisms=mechanisms,
                pre_driving_factor=pre_driving_factor,
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
    ) -> str:
        return f"""\
你正在执行本体论因果推演任务。

【新闻事件】
{news_text}

【知识图谱本体路径（1-hop & 2-hop）】
{ontological_context}

{mechanism_context}

【预提取驱动因素（基于图谱统计归纳，供你参考和细化）】
{pre_driving_factor}

【任务要求】
1. 基于以上【已提取机制标签】中的具体 relation/mechanism，细化 driving_factor（引用具体实体三元组）。
2. 生成 scenario_alpha：现状延续路径（最高概率）。
   - causal_chain 必须是4步结构，用 " --> " 分隔，格式：
     "source_fact --> [mechanism机制] --> intermediate_effect --> final_outcome"
3. 生成 scenario_beta：关键节点失效路径（低概率但高冲击）。
4. 指出最大的推演数据空白。
5. 只输出 JSON，不加任何说明。

JSON schema（必须严格遵守）：
{{
  "driving_factor": "引用具体实体三元组的驱动力陈述",
  "scenario_alpha": {{
    "name": "路径名称",
    "probability": 0.0-1.0,
    "causal_chain": "A --> [机制] --> B --> C",
    "description": "一句话描述"
  }},
  "scenario_beta": {{
    "name": "路径名称",
    "probability": 0.0-1.0,
    "causal_chain": "A --> [机制] --> B --> C",
    "trigger_condition": "触发条件",
    "description": "一句话描述"
  }},
  "confidence": 0.0-1.0,
  "graph_evidence": "引用了哪些图谱路径/机制标签",
  "verification_gap": "最关键的数据空白"
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
    ) -> DeductionResult:
        # driving_factor: 优先用 LLM 的细化结果，若为空则用预提取的
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
            probability=float(alpha_data.get("probability", 0.72)),
            description=alpha_data.get("description", ""),
            grounding_paths=alpha_data.get("grounding_paths") or [],
            mechanism_labels=mechanisms,
        )

        beta_data   = json_response.get("scenario_beta") or {}
        beta_chain  = self._parse_causal_chain_v2(
            beta_data.get("causal_chain", ""),
            [],
        )
        trigger = beta_data.get("trigger_condition", "")
        beta = Scenario(
            name=beta_data.get("name", "结构性断裂路径"),
            scenario_type=ScenarioType.STRUCTURAL_BREAK,
            causal_chain=beta_chain,
            probability=float(beta_data.get("probability", 0.28)),
            description=beta_data.get("description", ""),
            grounding_paths=[trigger] if trigger else [],
            mechanism_labels=mechanisms,
        )

        verification_gap = json_response.get("verification_gap", "未指定数据空白")
        confidence       = float(json_response.get("confidence", 0.6))

        self.logger.info("Deduction validated. Confidence: %s", confidence)
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
        """解析4步因果链：A --> [mechanism] --> B --> C"""
        parts = [p.strip() for p in chain_text.split("-->")]

        # 提取机制标签（方括号内）
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

    # ------------------------------------------------------------------
    # JSON helpers
    # ------------------------------------------------------------------

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
            '"confidence": 0.6',
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

        # 如果有机制标签，用最强的那条构造因果链
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
                final_outcome="现有联盟/供应链格局加速重组，出现系统性断裂",
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
            verification_gap="LLM 回应格式错误；推演基于图谱机制标签兜底逻辑，建议补充 KuzuDB 数据后重新分析",
            deduction_confidence=0.45,
            graph_evidence="通用本体逻辑推演（无直接KG路径）",
            mechanism_summary=self.aggregator.aggregate(mechanisms),
        )