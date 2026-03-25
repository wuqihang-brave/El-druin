"""
推演灵魂 (Deduction Soul)

强制 LLM 成为一台"逻辑演算机"：
- 严禁凭空捏造
- 必须基于路径推演
- 输出严格 JSON 结构
- 每个预测都有因果链追溯
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ScenarioType(Enum):
    """Scenario classification"""
    CONTINUATION = "现状延续路径"
    STRUCTURAL_BREAK = "结构性断裂路径"
    BIFURCATION = "分岔演化路径"


@dataclass
class CausalChain:
    """Strict causal chain: A → B → C"""
    source_fact: str          # 事实 A
    triggering_relation: str  # 触发关系 B
    resulting_change: str     # 导致结果 C
    entities_involved: List[str] = field(default_factory=list)  # 涉及的关键实体
    confidence: float = 0.8

    def to_text(self) -> str:
        """Render as: A -> B -> C"""
        return (
            f"{self.source_fact} -> "
            f"{self.triggering_relation} -> "
            f"{self.resulting_change}"
        )


@dataclass
class Scenario:
    """Single evolutionary scenario grounded in ontology"""
    name: str
    scenario_type: ScenarioType
    causal_chain: CausalChain
    probability: float
    grounding_paths: List[str] = field(default_factory=list)
    verification_requirements: List[str] = field(default_factory=list)


@dataclass
class DeductionResult:
    """Strict logical deduction result"""
    driving_factor: str
    scenario_alpha: Scenario
    scenario_beta: Scenario
    verification_gap: str
    deduction_confidence: float

    def to_strict_json(self) -> Dict[str, Any]:
        """Output as strict JSON (no free text)"""
        return {
            "driving_factor": self.driving_factor,
            "scenario_alpha": {
                "name": self.scenario_alpha.name,
                "causal_chain": self.scenario_alpha.causal_chain.to_text(),
                "entities": self.scenario_alpha.causal_chain.entities_involved,
                "grounding_paths": self.scenario_alpha.grounding_paths,
                "probability": self.scenario_alpha.probability,
            },
            "scenario_beta": {
                "name": self.scenario_beta.name,
                "causal_chain": self.scenario_beta.causal_chain.to_text(),
                "trigger_condition": (
                    self.scenario_beta.grounding_paths[0]
                    if self.scenario_beta.grounding_paths
                    else "Unknown"
                ),
                "probability": self.scenario_beta.probability,
            },
            "verification_gap": self.verification_gap,
            "confidence": self.deduction_confidence,
        }


# 【推演灵魂】- 嵌入式系统提示词
DEDUCTION_SOUL_SYSTEM_PROMPT = """\
你是一个极度严谨的"本体论情报分析官"。你必须基于提供的【本体关系路径】，对当前事件进行未来分支推演。

【核心约束条件】
1. 严禁使用"可能发生黑天鹅"、"局势将持续演变"等空洞废话。
2. 你的预测必须明确指出【由于哪个具体关系/状态】，导致了【什么具体实体的行为变化】。
3. 必须输出严格的 JSON 格式。
4. 每个预测都必须追溯到至少一条本体关系路径。
5. 如果无法从已知路径推演，必须明确说明"缺失的关键数据"。

【思维过程】
第一步：识别本体关系中的核心矛盾或纽带（driving_factor）
第二步：沿着该矛盾，推演现状延续路径（scenario_alpha）
第三步：找出该路径的关键节点，推演如果它失效将发生什么（scenario_beta）
第四步：指出当前推演的数据缺口

你必须遵循这个逻辑框架，不允许偏离。"""


class DeductionEngine:
    """
    推演灵魂核心引擎

    强制 LLM 成为逻辑演算机，基于本体路径进行严格推演。
    """

    def __init__(self, llm_service: Any) -> None:
        """Initialize with LLM service."""
        self.llm = llm_service
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
        """【CORE METHOD】推演灵魂激活

        Args:
            news_summary:        触发事件总结
            ontological_context: 本体关系路径（from KuzuDB）
            seed_entities:       涉及的关键实体

        Returns:
            Strict DeductionResult with causal chains tracing back to paths.
        """
        prompt = self._build_deduction_prompt(
            news_summary=news_summary,
            ontological_context=ontological_context,
            seed_entities=seed_entities,
        )

        self.logger.info("Activating Deduction Soul...")
        self.logger.info("Analyzing event: %s...", news_summary[:100])

        response = self.llm.call(
            prompt=prompt,
            system=DEDUCTION_SOUL_SYSTEM_PROMPT,
            temperature=0.2,   # Very low – deterministic logic
            max_tokens=1500,
            response_format="json",
        )

        try:
            deduction_json = json.loads(response)
            result = self._validate_and_structure_deduction(deduction_json)
            self.logger.info("Deduction complete. Output validated as strict JSON.")
            return result
        except (json.JSONDecodeError, ValueError) as exc:
            self.logger.error("LLM failed to output valid JSON: %s", exc)
            return self._fallback_deduction(news_summary, ontological_context)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_deduction_prompt(
        self,
        news_summary: str,
        ontological_context: str,
        seed_entities: List[str],
    ) -> str:
        """Build strict prompt that forces logical deduction."""
        entities_str = ", ".join(seed_entities)

        return f"""\
【分析任务】
请基于以下本体关系路径，对当前事件进行严格的逻辑推演。

【当前触发事件】
{news_summary}

【涉及的关键实体】
{entities_str}

【本体关系路径】
{ontological_context}

【要求输出的 JSON 结构】
{{
  "driving_factor": "指出本体关系路径中，最能决定局势走向的核心矛盾或纽带（必须是上述路径中明确存在的）",
  "scenario_alpha": {{
    "name": "现状延续路径",
    "causal_chain": "事实 A -> 触发关系 B -> 导致结果 C （其中 A、B、C 都必须来自本体路径）",
    "entities": ["实体1", "实体2"],
    "grounding_paths": ["本体路径1", "本体路径2"],
    "probability": 0.8
  }},
  "scenario_beta": {{
    "name": "结构性断裂路径",
    "causal_chain": "假设前提节点 X 崩溃 -> 导致关系 Y 逆转 -> 最终状态 Z",
    "trigger_condition": "触发此路径所需的最小黑天鹅事件（必须说明与已知路径的偏离）",
    "probability": 0.2
  }},
  "verification_gap": "指出当前推演中，本体路径中缺失的、需要进一步监测的关键实体数据或关系",
  "confidence": 0.85
}}

【严格要求】
1. 不允许使用模糊表述如"可能会"、"有可能"。必须说"由于 X，所以 Y"。
2. scenario_alpha 和 scenario_beta 的因果链必须完整可追溯。
3. 如果某个预测无法从本体路径推演，必须在 verification_gap 中说明缺失的数据。
4. 输出必须是有效的 JSON 格式。
"""

    def _validate_and_structure_deduction(
        self, json_response: Dict[str, Any]
    ) -> DeductionResult:
        """Validate LLM output conforms to strict structure."""
        driving_factor = json_response.get("driving_factor", "Unknown")

        alpha_data = json_response.get("scenario_alpha") or {}
        alpha_chain = self._parse_causal_chain(
            alpha_data.get("causal_chain", ""),
            alpha_data.get("entities", []),
        )
        alpha = Scenario(
            name=alpha_data.get("name", "现状延续路径"),
            scenario_type=ScenarioType.CONTINUATION,
            causal_chain=alpha_chain,
            probability=float(alpha_data.get("probability", 0.8)),
            grounding_paths=alpha_data.get("grounding_paths") or [],
        )

        beta_data = json_response.get("scenario_beta") or {}
        beta_chain = self._parse_causal_chain(
            beta_data.get("causal_chain", ""),
            [],
        )
        trigger = beta_data.get("trigger_condition", "")
        beta = Scenario(
            name=beta_data.get("name", "结构性断裂路径"),
            scenario_type=ScenarioType.STRUCTURAL_BREAK,
            causal_chain=beta_chain,
            probability=float(beta_data.get("probability", 0.2)),
            grounding_paths=[trigger] if trigger else [],
        )

        verification_gap = json_response.get("verification_gap", "No gaps identified")
        confidence = float(json_response.get("confidence", 0.75))

        self.logger.info("Deduction validated. Confidence: %s", confidence)
        return DeductionResult(
            driving_factor=driving_factor,
            scenario_alpha=alpha,
            scenario_beta=beta,
            verification_gap=verification_gap,
            deduction_confidence=confidence,
        )

    def _parse_causal_chain(
        self, chain_text: str, entities: List[str]
    ) -> CausalChain:
        """Parse causal chain from text like 'A -> B -> C'."""
        parts = [p.strip() for p in chain_text.split("->")]
        return CausalChain(
            source_fact=parts[0] if len(parts) > 0 else "",
            triggering_relation=parts[1] if len(parts) > 1 else "",
            resulting_change=parts[2] if len(parts) > 2 else "",
            entities_involved=list(entities),
            confidence=0.8,
        )

    def _fallback_deduction(
        self, news_summary: str, ontological_context: str  # noqa: ARG002
    ) -> DeductionResult:
        """Fallback deduction if JSON parsing fails."""
        self.logger.warning("Falling back to structured deduction...")

        alpha_chain = CausalChain(
            source_fact="当前状态",
            triggering_relation="延续",
            resulting_change="维持原状",
        )
        beta_chain = CausalChain(
            source_fact="关键假设",
            triggering_relation="崩溃",
            resulting_change="状态反转",
        )

        return DeductionResult(
            driving_factor="Unable to determine from LLM response",
            scenario_alpha=Scenario(
                name="现状延续路径",
                scenario_type=ScenarioType.CONTINUATION,
                causal_chain=alpha_chain,
                probability=0.7,
            ),
            scenario_beta=Scenario(
                name="结构性断裂路径",
                scenario_type=ScenarioType.STRUCTURAL_BREAK,
                causal_chain=beta_chain,
                probability=0.3,
            ),
            verification_gap="LLM 回应格式错误，建议重新分析",
            deduction_confidence=0.0,
        )
