"""
Sacred Sword Analyzer – EL-DRUIN Intelligence Platform v2
==========================================================

強化版本：從「輕量事實錨定 + LLM 推測」轉向「本體約束驅動推演」

核心改進：
1. _extract_core_facts 現在從圖谱中提取 MechanismLabel，
   並將機制標籤注入 Fact.statement（不再只是實體名稱匹配）。
2. _generate_alpha_branch / _generate_beta_branch 被重寫：
   必須從 graph_context["mechanisms"] 中選取驅動機制錨點，
   不再允許 LLM 自由發揮「趨勢將持續演變」式廢話。
3. 新增 _extract_driving_mechanisms：
   從 graph_context dict 中聚合 MechanismLabel 列表。
4. 新增 _build_mechanism_anchored_prompt：
   生成帶有機制約束的 LLM 提示詞。
5. confidence 計算加入「機制覆蓋率」權重：
   有更多機制標籤錨定的分析，置信度更高。

參考本體：
- CAMEO 事件類型體系（地緣政治）
- FIBO 金融行業業務本體（經濟/金融）
- GDELT 事件類型（新聞情報）
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from ontology.relation_schema import enrich_mechanism_labels_with_patterns, build_pattern_context_for_prompt
from intelligence.deduction_engine import (  # type: ignore[import]
    DrivingFactorAggregator,
    MechanismLabel,
    RelationDomain,
    extract_mechanism_labels,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_KNOWN_ENTITY_CONFIDENCE   = 0.95
_UNKNOWN_ENTITY_CONFIDENCE = 0.75
_CONFIDENCE_THRESHOLD      = 0.85
_MAX_FACTS                 = 5
_ALPHA_PROBABILITY         = 0.72
_BETA_PROBABILITY          = 0.28
_CONFLICT_PENALTY          = 0.20
_MECHANISM_COVERAGE_BONUS  = 0.05   # 每個有效機制標籤增加置信度

# 已知高信號術語（與 analysis_service 保持同步）
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
# Data classes
# ---------------------------------------------------------------------------

class ConflictStatus(Enum):
    CONSISTENT = "CONSISTENT"
    CONFLICT   = "CONFLICT"


@dataclass
class Fact:
    statement:  str    # 單條清晰陳述
    source:     str    # 來源行（前 60 字元）
    confidence: float  # 0.0-1.0
    # v2 新增：該 Fact 錨定的機制標籤（可為空）
    mechanism:  Optional[MechanismLabel] = None

    def has_mechanism_anchor(self) -> bool:
        return self.mechanism is not None


@dataclass
class Branch:
    name:              str      # "Alpha" 或 "Beta"
    description:       str      # 一句話路徑描述
    probability:       float    # 0.72 或 0.28
    key_assumption:    str      # 核心假設（一句話）
    causal_chain:      str = "" # v2 新增：4步因果鏈文字
    mechanism_anchor:  str = "" # v2 新增：本次推演的機制錨點


@dataclass
class SacredSwordAnalysis:
    facts:            List[Fact]       # 3-5 條事實
    conflict:         ConflictStatus   # 二元衝突判斷
    alpha:            Branch           # 高置信路徑
    beta:             Branch           # 黑天鵝情景
    confidence_score: float            # 0.0-1.0
    data_gap:         str              # 最關鍵的單個缺口
    counter_arg:      str              # 最強反駁論點（100字以內）
    # v2 新增
    driving_factor:   str = ""         # 由 DrivingFactorAggregator 生成
    mechanism_labels: List[MechanismLabel] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class SacredSwordAnalyzer:
    """
    Sacred Sword Analyzer v2 – 機制錨定本體推演引擎

    4步分析協議（升級版）：
    1. Fact Anchoring       – 從新聞片段提取事實，並錨定 MechanismLabel
    2. Conflict Detection   – 二元 [CONSISTENT] / [CONFLICT] 判斷
    3. Causal Branching     – Alpha（機制延伸）和 Beta（機制失效）路徑
       ↳ 必須引用具體的 mechanism，不允許空洞描述
    4. Self-Audit           – 置信度（含機制覆蓋率加權）、數據缺口、反駁論點
    """

    def __init__(self, settings: Any = None) -> None:
        self._settings    = settings
        self._client_type = None
        self._client      = None
        self._aggregator  = DrivingFactorAggregator()

        if self._settings is not None:
            self._client_type = getattr(self._settings, "llm_provider", None)

        if self._client_type == "groq":
            import groq
            self._client = groq.Groq(api_key=self._settings.groq_api_key)
        elif self._client_type == "openai":
            import openai
            self._client = openai.OpenAI(api_key=self._settings.openai_api_key)
        elif self._client_type == "deepseek":
            import openai
            self._client = openai.OpenAI(
                api_key=self._settings.deepseek_api_key,
                base_url=self._settings.deepseek_base_url,
            )

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def analyze(
        self,
        news_fragments: List[str],
        graph_context: Dict[str, Any],
        claim: str,
    ) -> SacredSwordAnalysis:
        """
        執行完整 4 步 Sacred Sword 分析協議。

        v2 改動：
        - graph_context 可以包含 "mechanisms" 鍵（List[MechanismLabel]），
          也可以包含傳統的 "entities"/"nodes" 鍵，兩者都支持。
        - 若 graph_context 不含 "mechanisms"，自動從其文字表示
          （graph_context.get("raw_text", "")）中提取 MechanismLabel。
        """
        # ── 預處理：提取/接收機制標籤 ──────────────────────────────
        mechanisms = self._extract_driving_mechanisms(news_fragments, graph_context)
        driving_factor = self._aggregator.aggregate(mechanisms)
        logger.info(
            "SacredSword v2: %d mechanism labels | driving_factor: %s",
            len(mechanisms), driving_factor,
        )

        # Step 1: Fact anchoring（帶機制錨定）
        facts = self._extract_core_facts(news_fragments, graph_context, mechanisms)

        # Step 2: Conflict detection
        conflict = self._detect_conflict(facts)

        # Step 3: Causal branching（機制錨定版）
        alpha = self._generate_alpha_branch(facts, claim, mechanisms)
        beta  = self._generate_beta_branch(facts, claim, alpha, mechanisms)

        # Step 4: Self-audit
        confidence_score = self._calculate_confidence(facts, conflict, mechanisms)
        data_gap    = self._identify_one_critical_gap(facts, claim)
        counter_arg = self._find_strongest_counter_arg(facts, claim)

        return SacredSwordAnalysis(
            facts=facts,
            conflict=conflict,
            alpha=alpha,
            beta=beta,
            confidence_score=confidence_score,
            data_gap=data_gap,
            counter_arg=counter_arg,
            driving_factor=driving_factor,
            mechanism_labels=mechanisms,
        )

    # ------------------------------------------------------------------
    # v2 新增：提取/整合機制標籤
    # ------------------------------------------------------------------

    def _extract_driving_mechanisms(
        self,
        news_fragments: List[str],
        graph_context: Dict[str, Any],
    ) -> List[MechanismLabel]:
        """
        從 graph_context 中獲取 MechanismLabel 列表。

        優先級：
        1. graph_context["mechanisms"]（已由上游 DeductionEngine 提取）
        2. graph_context["raw_text"] + news_fragments（實時提取）
        3. 從 graph_context["relations"] 提取（舊格式兼容）
        """
        # 1) 已有預提取的機制標籤
        if "mechanisms" in graph_context:
            raw = graph_context["mechanisms"]
            if raw and isinstance(raw[0], MechanismLabel):
                return raw

        # 2) 從原始文字中提取
        raw_text    = graph_context.get("raw_text", "")
        news_joined = "\n".join(news_fragments)

        # 嘗試從 relations 字段構造文字
        relations_text = ""
        for rel in graph_context.get("relations", []):
            if isinstance(rel, dict):
                relations_text += (
                    f"{rel.get('source', '')} -> "
                    f"{rel.get('type', '')} -> "
                    f"{rel.get('target', '')}: "
                    f"{rel.get('mechanism', '')}\n"
                )
            elif isinstance(rel, str):
                relations_text += rel + "\n"

        combined_context = "\n".join(filter(None, [raw_text, relations_text]))

        # 用於確定 seed entities
        seed_entities = []
        for key in ("entities", "nodes"):
            for item in graph_context.get(key, []):
                if isinstance(item, dict):
                    name = item.get("name") or item.get("id") or ""
                else:
                    name = str(item)
                if name:
                    seed_entities.append(name)
        # === 1. 先提取 MechanismLabel 列表 ===
        mechanisms = extract_mechanism_labels(
            graph_context=combined_context,
            news_text=news_joined,
            seed_entities=seed_entities or None,
        )

        # ==== 2. enrich patterns，把本体/先验信息注入 ===
        from ontology.relation_schema import enrich_mechanism_labels_with_patterns
        mechanisms = enrich_mechanism_labels_with_patterns(mechanisms)

        # === 3. 返回 enrich 后的新 mechanism_labels ===
        return mechanisms
        return extract_mechanism_labels(
            graph_context=combined_context,
            news_text=news_joined,
            seed_entities=seed_entities or None,
        )

    # ------------------------------------------------------------------
    # Step 1: Fact anchoring（v2：帶機制錨定）
    # ------------------------------------------------------------------

    def _extract_core_facts(
        self,
        news: List[str],
        graph: Dict[str, Any],
        mechanisms: List[MechanismLabel],
    ) -> List[Fact]:
        """
        解析新聞片段，將事實錨定到知識圖谱。

        v2 改動：
        - 優先嘗試將 fragment 匹配到某個 MechanismLabel
        - 匹配到機制標籤的 Fact 置信度 = 0.95，且附帶機制信息
        - 沒有匹配機制但有實體的 Fact 置信度 = 0.88
        - 無任何匹配 → 置信度 0.75（低於閾值，丟棄）
        """
        known_entities: set[str] = set()
        for key in ("entities", "nodes"):
            for item in graph.get(key, []):
                if isinstance(item, dict):
                    name = item.get("name") or item.get("id") or ""
                else:
                    name = str(item)
                if name:
                    known_entities.add(name.lower())

        # 把機制標籤的 source/target 也加入已知實體
        for m in mechanisms:
            known_entities.add(m.source.lower())
            known_entities.add(m.target.lower())

        facts: List[Fact] = []
        for fragment in news:
            if len(facts) >= _MAX_FACTS:
                break
            fragment = fragment.strip()
            if not fragment:
                continue

            source = fragment[:60].rstrip(" .") + ("…" if len(fragment) > 60 else "")
            fragment_lower = fragment.lower()

            # 嘗試匹配 MechanismLabel
            matched_mechanism: Optional[MechanismLabel] = None
            for m in mechanisms:
                if m.source.lower() in fragment_lower or m.target.lower() in fragment_lower:
                    matched_mechanism = m
                    break

            if matched_mechanism:
                conf = 0.95
                statement = (
                    f"{fragment} "
                    f"[機制: {matched_mechanism.source}→{matched_mechanism.target} "
                    f"via {matched_mechanism.relation} | {matched_mechanism.domain.value}]"
                )
            elif any(ent in fragment_lower for ent in known_entities):
                conf = 0.88
                statement = fragment
            else:
                conf = _UNKNOWN_ENTITY_CONFIDENCE

                if conf < _CONFIDENCE_THRESHOLD:
                    logger.debug(
                        "Fragment rejected (conf %.2f < threshold): %s",
                        conf, fragment[:60],
                    )
                    continue
                statement = fragment

            facts.append(Fact(
                statement=statement,
                source=source,
                confidence=conf,
                mechanism=matched_mechanism,
            ))

        # LLM 精煉（若可用）
        if self._settings is not None and getattr(self._settings, "llm_enabled", False):
            facts = self._llm_refine_facts(facts, news, graph)
            facts = self._enrich_facts_with_entity_labels(facts, news)

        return facts[:_MAX_FACTS]

    # ------------------------------------------------------------------
    # Step 2: Conflict detection
    # ------------------------------------------------------------------

    def _detect_conflict(self, facts: List[Fact]) -> ConflictStatus:
        """二元衝突判斷，通過 LLM 實現，兜底返回 CONSISTENT。"""
        if not facts:
            return ConflictStatus.CONSISTENT

        if self._settings is not None and getattr(self._settings, "llm_enabled", False):
            statements = "\n".join(f"- {f.statement}" for f in facts)
            prompt = (
                "Do these facts logically contradict each other? "
                "Reply with YES or NO only.\n\n" + statements
            )
            response = self._llm_call(prompt, temperature=0.1)
            if response and response.strip().upper().startswith("YES"):
                return ConflictStatus.CONFLICT

        return ConflictStatus.CONSISTENT

    # ------------------------------------------------------------------
    # Step 3: Causal branching（v2：機制錨定版）
    # ------------------------------------------------------------------

    def _generate_alpha_branch(
        self,
        facts: List[Fact],
        claim: str,
        mechanisms: List[MechanismLabel],
    ) -> Branch:
        """
        生成高置信因果路徑（Alpha）。

        v2：LLM 被強制引用 mechanisms 中強度最高的機制作為驅動錨點。
        """
        mechanism_anchor = ""
        anchor_description = ""

        if mechanisms:
            best = max(mechanisms, key=lambda m: m.strength)
            mechanism_anchor    = best.relation
            anchor_description  = best.to_prompt_line()

        prompt = self._build_mechanism_anchored_prompt(
            facts=facts,
            claim=claim,
            anchor_description=anchor_description,
            scenario_type="Alpha（現狀延伸路徑）",
            instruction=(
                "基於上述機制錨點，推演：如果該機制繼續強化，"
                "最可能的演化路徑是什麼？\n"
                "要求：必須引用具體實體和機制，格式：\n"
                "  causal_chain: A --> [機制] --> B --> C\n"
                "  description: 一句話總結\n"
                "  key_assumption: 該路徑成立的核心假設\n"
                "只輸出這三個字段，純文字，不加 JSON 包裝。"
            ),
        )

        response = self._llm_call(prompt, temperature=0.25, max_tokens=400)

        if response:
            # 解析 LLM 輸出
            causal_chain   = self._parse_field(response, "causal_chain")
            description    = self._parse_field(response, "description")
            key_assumption = self._parse_field(response, "key_assumption")
        else:
            causal_chain   = f"現有{mechanism_anchor or '結構性'}矛盾 --> 持續強化 --> 相關實體調整立場 --> 現有格局漸進演變"
            description    = f"'{claim}' 的現有趨勢沿既有機制軌道延伸"
            key_assumption = f"{mechanism_anchor or '當前驅動機制'}保持現有方向和烈度"

        return Branch(
            name="Alpha",
            description=description.strip(),
            probability=_ALPHA_PROBABILITY,
            key_assumption=key_assumption.strip(),
            causal_chain=causal_chain.strip(),
            mechanism_anchor=mechanism_anchor,
        )

    def _generate_beta_branch(
        self,
        facts: List[Fact],
        claim: str,
        alpha: Branch,
        mechanisms: List[MechanismLabel],
    ) -> Branch:
        """
        生成黑天鵝情景（Beta）：Alpha 的關鍵假設失效時的路徑。

        v2：明確指定「哪個機制節點失效」作為觸發條件。
        """
        mechanism_anchor = alpha.mechanism_anchor or (
            mechanisms[0].relation if mechanisms else ""
        )

        prompt = self._build_mechanism_anchored_prompt(
            facts=facts,
            claim=claim,
            anchor_description=f"Alpha路徑機制錨點: {mechanism_anchor}\nAlpha假設: {alpha.key_assumption}",
            scenario_type="Beta（關鍵節點失效路徑）",
            instruction=(
                f"如果 Alpha 路徑的關鍵假設「{alpha.key_assumption}」失效，"
                f"具體而言某個關鍵的 [{mechanism_anchor}] 機制節點被逆轉或中斷，"
                "推演最嚴峻的結構性斷裂路徑。\n"
                "要求：必須具體說明是哪個實體/節點的失效觸發了斷裂，格式：\n"
                "  causal_chain: A --> [機制失效] --> B --> C\n"
                "  description: 一句話總結\n"
                "  trigger_condition: 觸發黑天鵝的具體條件\n"
                "只輸出這三個字段，純文字，不加 JSON 包裝。"
            ),
        )

        response = self._llm_call(prompt, temperature=0.4, max_tokens=400)

        if response:
            causal_chain     = self._parse_field(response, "causal_chain")
            description      = self._parse_field(response, "description")
            trigger_condition = self._parse_field(response, "trigger_condition")
        else:
            causal_chain      = (
                f"{mechanism_anchor or '關鍵機制'}節點逆轉 --> "
                f"[{alpha.key_assumption}假設失效] --> "
                "相關實體陷入極端對抗 --> 現有格局系統性崩解"
            )
            description       = f"'{alpha.key_assumption}' 假設失效導致結構性斷裂"
            trigger_condition = f"{mechanism_anchor or '關鍵機制'} 節點被逆轉或外部衝擊打斷"

        return Branch(
            name="Beta",
            description=description.strip(),
            probability=_BETA_PROBABILITY,
            key_assumption=trigger_condition.strip(),
            causal_chain=causal_chain.strip(),
            mechanism_anchor=mechanism_anchor,
        )

    # ------------------------------------------------------------------
    # Step 4: Self-audit（v2：機制覆蓋率加權置信度）
    # ------------------------------------------------------------------

    def _calculate_confidence(
        self,
        facts: List[Fact],
        conflict: ConflictStatus,
        mechanisms: Optional[List[MechanismLabel]] = None,
    ) -> float:
        """
        置信度 = 平均事實置信度 − 衝突懲罰 + 機制覆蓋率獎勵

        機制覆蓋率獎勵：
        - 每個有效機制標籤增加 MECHANISM_COVERAGE_BONUS（最多 3 個）
        - 有效 = strength >= 0.7
        """
        if not facts:
            return 0.0

        avg     = sum(f.confidence for f in facts) / len(facts)
        penalty = _CONFLICT_PENALTY if conflict == ConflictStatus.CONFLICT else 0.0

        mechanism_bonus = 0.0
        if mechanisms:
            strong_mechanisms = [m for m in mechanisms if m.strength >= 0.7]
            mechanism_bonus = min(
                len(strong_mechanisms) * _MECHANISM_COVERAGE_BONUS,
                _MECHANISM_COVERAGE_BONUS * 3,
            )
            logger.debug(
                "Mechanism coverage bonus: +%.3f (%d strong mechanisms)",
                mechanism_bonus, len(strong_mechanisms),
            )

        return round(max(0.0, min(1.0, avg - penalty + mechanism_bonus)), 4)

    def _identify_one_critical_gap(self, facts: List[Fact], claim: str) -> str:
        result = self._llm_call(
            f"What is the SINGLE most critical missing data to analyze: {claim}? "
            "(one sentence, cite specific entity or relationship type)\n\n"
            + "\n".join(f"- {f.statement}" for f in facts),
            temperature=0.2,
        )
        return (result or f"'{claim}' 推演中最關鍵的缺失：直接量化衡量驅動機制強度的指標數據").strip()

    def _find_strongest_counter_arg(self, facts: List[Fact], claim: str) -> str:
        result = self._llm_call(
            f"What is the STRONGEST counter-argument that could prove this analysis of "
            f"'{claim}' wrong? Cite a specific mechanism or entity that undermines the "
            "causal chain. (100 words max)\n\n"
            + "\n".join(f"- {f.statement}" for f in facts),
            temperature=0.5,
        )
        return (
            result or
            f"'{claim}' 分析的最強反駁：知識圖谱中尚未納入的第三方實體可能通過反向機制"
            "抵消當前驅動力，導致推演結論失效。"
        ).strip()

    # ------------------------------------------------------------------
    # Prompt helpers（v2 新增）
    # ------------------------------------------------------------------

    def _build_mechanism_anchored_prompt(
        self,
        facts: List[Fact],
        claim: str,
        anchor_description: str,
        scenario_type: str,
        instruction: str,
    ) -> str:
        """構建帶機制約束的推演提示詞。"""
        facts_text = "\n".join(f"- {f.statement}" for f in facts)
        return (
            f"【分析目標】{claim}\n\n"
            f"【已錨定機制】\n{anchor_description}\n\n"
            f"【事實基礎】\n{facts_text}\n\n"
            f"【任務：生成 {scenario_type}】\n"
            f"{instruction}"
        )

    @staticmethod
    def _parse_field(text: str, field_name: str) -> str:
        """從 LLM 輸出中提取指定字段的值（格式：field_name: value）。"""
        pattern = re.compile(
            rf"{re.escape(field_name)}\s*[:\uff1a]\s*(.+?)(?:\n|$)",
            re.IGNORECASE,
        )
        m = pattern.search(text)
        return m.group(1).strip() if m else ""

    # ------------------------------------------------------------------
    # LLM helpers
    # ------------------------------------------------------------------

    def llm_call(self, prompt: str, temperature: float = 0.3) -> Optional[str]:
        """Public LLM call entry point."""
        return self._llm_call(prompt, temperature=temperature)

    def _llm_call(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 1500,
        response_format: str = "json",
    ) -> Optional[str]:
        """統一 LLM 調用分發器。"""
        if self._client_type == "groq":
            return self._call_groq(prompt, temperature, max_tokens)
        if self._client_type == "openai":
            return self._call_openai(prompt, temperature, max_tokens)
        return None

    def _call_groq(
        self, prompt: str, temperature: float, max_tokens: int
    ) -> Optional[str]:
        if not self._client:
            return None
        try:
            model_name = getattr(self._settings, "llm_model", "llama-3.1-8b-instant")
            chat_completion = self._client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            return chat_completion.choices[0].message.content
        except Exception as exc:
            logger.error("Groq API call failed: %s", exc)
            return None

    def _call_openai(
        self, prompt: str, temperature: float, max_tokens: int
    ) -> Optional[str]:
        if not self._client:
            return None
        try:
            model_name = getattr(self._settings, "llm_model", "gpt-4o-mini")
            response = self._client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as exc:
            logger.error("OpenAI API call failed: %s", exc)
            return None

    def _llm_refine_facts(
        self,
        facts: List[Fact],
        news: List[str],
        graph: Dict[str, Any],
    ) -> List[Fact]:
        """LLM 精煉事實（可選，默認直接返回）。"""
        return facts

    def _enrich_facts_with_entity_labels(
        self,
        facts: List[Fact],
        news: List[str],
    ) -> List[Fact]:
        """
        用三層實體上下文（EntityExtractionEngine）豐富事實陳述。

        格式：<entity> [LAYER1] functions as ROLE1/ROLE2 with VIRTUE1/VIRTUE2 nature
        """
        try:
            from intelligence.entity_extraction import EntityExtractionEngine  # type: ignore

            class _DirectLLMService:
                def __init__(self, analyzer: "SacredSwordAnalyzer") -> None:
                    self._analyzer = analyzer

                def call(
                    self,
                    prompt: str,
                    temperature: float = 0.2,
                    max_tokens: int = 2000,
                    response_format: str = "json",
                ) -> str:
                    result = self._analyzer._llm_call(prompt, temperature=temperature)
                    return result or "[]"

            extractor    = EntityExtractionEngine(_DirectLLMService(self))
            combined_text = "\n".join(news)
            entities     = extractor.extract(combined_text, "sacred_sword_analysis")
            entity_map   = {e.name.lower(): e for e in entities}

            enriched: List[Fact] = []
            for fact in facts:
                statement_lower = fact.statement.lower()
                matched = next(
                    (e for name, e in entity_map.items() if name in statement_lower),
                    None,
                )
                if matched:
                    roles   = "/".join(matched.structural_roles)
                    virtues = "/".join(matched.philosophical_nature)
                    label   = (
                        f" [{matched.physical_type}] functions as {roles}"
                        f" with {virtues} nature"
                    )
                    base = fact.statement.rstrip(".")
                    enriched.append(Fact(
                        statement=base + label,
                        source=fact.source,
                        confidence=fact.confidence,
                        mechanism=fact.mechanism,
                    ))
                else:
                    enriched.append(fact)
            return enriched

        except Exception as exc:
            logger.warning("Entity label enrichment failed: %s", exc)
            return facts