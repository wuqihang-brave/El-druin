"""
秩序评论家（Order Critic Agent）

作为知识提取层的质量控制机制，使用 LangChain + Groq LLM 对
LLMGraphTransformer 提取的原始三元组进行"熵值评估"，
过滤瞬时噪音、琐碎信息，保留具有长期因果律和结构性影响的知识。

用法示例::

    from knowledge_layer.order_critic import OrderCritic

    critic = OrderCritic()
    raw_triples = [
        {"subject": "Federal Reserve", "relation": "raises", "object": "interest rates"},
        {"subject": "Taylor Swift", "relation": "attends", "object": "Grammy Awards"},
    ]
    ordered = critic.filter_triples(raw_triples, min_order_score=50, mode="balanced")
    # 只保留 order_score >= 50 的三元组
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Literal, Optional

from knowledge_layer.order_models import CategoryType, OrderedTriple

logger = logging.getLogger(__name__)

# 操作模式类型
ModeType = Literal["strict", "balanced"]

# 各模式对应的最低秩序评分阈值
_MODE_THRESHOLDS: Dict[str, float] = {
    "strict": 80.0,
    "balanced": 50.0,
}

# 系统提示词：赋予 AI "首席秩序官"身份
_SYSTEM_PROMPT = """你是 El-druin 的首席秩序官（Chief Order Officer）。
你的职责是评估新闻事件中提取的实体和关系，判断其是否符合以下标准：
- 是否能加固文明体系的骨架
- 是否具有长期因果律
- 是否体现系统性影响（而非瞬时噪音）

对于每一个知识三元组（entity - relation - entity），你需要进行"熵值评估"，
给出 0-100 的秩序评分，并说明理由。

评分标准：
- 80-100：核心秩序知识。包括：技术突破（新的科学发现、技术创新）、地缘逻辑（国际关系变迁、政治经济结构变化）、制度创新（新法律框架、新商业模式）、因果链条（能追溯影响链的复杂事件）。
- 50-79：有一定结构性价值，但影响范围有限或因果链不够清晰。
- 0-49：瞬时噪音或琐碎信息。包括：明星八卦、娱乐花边、日常市场波动、天气预报等无结构性意义的信息、单纯转述或重复报道。

知识分类（category）说明：
- "technology"  – 技术突破、科学发现、工程创新
- "geopolitics" – 地缘政治、国际关系变迁、外交政策
- "institution" – 制度创新、法律框架、商业模式变革
- "causality"   – 因果链条、系统性事件、结构性影响
- "unknown"     – 无法归类或明确属于噪音的信息

请严格按照如下 JSON 格式返回评估结果，不要包含任何额外文字：
{
  "order_score": <0-100 的数字>,
  "reasoning": "<简明的评分理由，不超过 100 字>",
  "category": "<technology|geopolitics|institution|causality|unknown>",
  "confidence": <0.0-1.0 的小数>
}"""

# 人类提示词模板
_HUMAN_PROMPT_TEMPLATE = (
    "请评估以下知识三元组：\n"
    "主体（Subject）：{subject}\n"
    "关系（Relation）：{relation}\n"
    "客体（Object）：{object}\n\n"
    "请进行熵值评估并返回 JSON 格式的结果。"
)


def _build_llm(api_key: Optional[str], model: str, temperature: float) -> Any:
    """构建 ChatGroq LLM 实例。"""
    from langchain_groq import ChatGroq

    return ChatGroq(
        model=model,
        temperature=temperature,
        api_key=api_key,
    )


class OrderCritic:
    """秩序评论家：对知识三元组进行熵值评估与质量筛选。

    使用 LangChain 和 Groq LLM 驱动，赋予 AI "首席秩序官"身份，
    对输入的三元组逐一评估其秩序价值，并根据阈值过滤低质量信息。

    Args:
        api_key: Groq API 密钥。若为 None，则从 ``app.core.config`` 或环境变量读取。
        model: 所使用的 Groq 模型名称，默认 ``"llama3-8b-8192"``。
        temperature: LLM 温度参数，默认 0.0（确定性输出）。
        rate_limit_delay: 相邻 API 调用之间的最小间隔秒数，默认 0.5s（避免速率限制）。

    Example::

        critic = OrderCritic()
        results = critic.filter_triples(
            triples=[{"subject": "OpenAI", "relation": "releases", "object": "GPT-5"}],
            mode="balanced",
        )
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "llama3-8b-8192",
        temperature: float = 0.0,
        rate_limit_delay: float = 0.5,
    ) -> None:
        self._model = model
        self._temperature = temperature
        self._rate_limit_delay = rate_limit_delay
        self._last_call_time: float = 0.0

        # 解析 API key
        if api_key:
            self._api_key = api_key
        else:
            self._api_key = self._resolve_api_key()

        # LLM 实例（延迟初始化）
        self._llm: Optional[Any] = None

        # 内存缓存：key = (subject, relation, object)，value = OrderedTriple
        self._cache: Dict[tuple, OrderedTriple] = {}

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_api_key() -> Optional[str]:
        """从应用配置或环境变量中读取 Groq API key。"""
        try:
            from app.core.config import get_settings
            settings = get_settings()
            if settings.groq_api_key:
                return settings.groq_api_key
        except ImportError:
            pass

        import os
        return os.getenv("GROQ_API_KEY")

    def _get_llm(self) -> Any:
        """懒加载 LLM 实例。"""
        if self._llm is None:
            self._llm = _build_llm(self._api_key, self._model, self._temperature)
        return self._llm

    def _rate_limit(self) -> None:
        """确保相邻 API 调用之间有足够间隔。"""
        now = time.monotonic()
        elapsed = now - self._last_call_time
        if elapsed < self._rate_limit_delay:
            time.sleep(self._rate_limit_delay - elapsed)
        self._last_call_time = time.monotonic()

    def _parse_llm_response(self, raw: str) -> Dict[str, Any]:
        """解析 LLM 返回的 JSON 字符串，处理常见格式异常。"""
        # 尝试提取 JSON 块（LLM 有时会在 JSON 前后加额外文字）
        text = raw.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            text = text[start:end]
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            logger.warning("LLM 返回的 JSON 解析失败: %s | 原始响应: %.200s", exc, raw)
            return {}

    def _fallback_evaluation(self, subject: str, relation: str, obj: str) -> OrderedTriple:
        """当 LLM 不可用时，使用规则兜底评估。"""
        # 简单关键词匹配：高价值词汇
        high_value_keywords = {
            "technology", "breakthrough", "innovation", "treaty", "sanctions",
            "invasion", "election", "merger", "acquisition", "regulation",
            "legislation", "revolution", "crisis", "quantum", "ai", "nuclear",
            "climate", "trade", "agreement", "reform",
            "技术", "突破", "创新", "条约", "制裁", "入侵", "选举", "并购",
            "监管", "立法", "革命", "危机", "量子", "核", "气候", "贸易", "协议", "改革",
        }
        low_value_keywords = {
            "gossip", "celebrity", "award", "party", "concert", "selfie",
            "八卦", "明星", "颁奖", "派对", "演唱会",
        }
        combined = f"{subject} {relation} {obj}".lower()
        if any(kw in combined for kw in low_value_keywords):
            score, category, reasoning = 20.0, "unknown", "关键词匹配：娱乐/琐碎信息，无结构性价值"
        elif any(kw in combined for kw in high_value_keywords):
            score, category, reasoning = 70.0, "causality", "关键词匹配：含高价值关键词，疑似结构性信息"
        else:
            score, category, reasoning = 50.0, "unknown", "规则兜底：无法判断，给予中性评分"
        return OrderedTriple(
            subject=subject,
            relation=relation,
            object=obj,
            order_score=score,
            reasoning=reasoning,
            category=category,  # type: ignore[arg-type]
            confidence=0.4,
        )

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def evaluate_triple(self, subject: str, relation: str, obj: str) -> OrderedTriple:
        """对单个三元组进行秩序评估。

        Args:
            subject: 主体实体名称。
            relation: 关系类型。
            obj: 客体实体名称。

        Returns:
            填充了 order_score、reasoning、category、confidence 的 OrderedTriple。
        """
        cache_key = (subject.strip().lower(), relation.strip().lower(), obj.strip().lower())

        # 命中缓存
        if cache_key in self._cache:
            logger.debug("缓存命中: %s -[%s]-> %s", subject, relation, obj)
            return self._cache[cache_key]

        # 若无 API key，走兜底逻辑
        if not self._api_key:
            logger.warning("未配置 Groq API key，使用规则兜底评估")
            result = self._fallback_evaluation(subject, relation, obj)
            self._cache[cache_key] = result
            return result

        # 速率控制
        self._rate_limit()

        try:
            from langchain_core.prompts import ChatPromptTemplate

            prompt = ChatPromptTemplate.from_messages([
                ("system", _SYSTEM_PROMPT),
                ("human", _HUMAN_PROMPT_TEMPLATE),
            ])
            chain = prompt | self._get_llm()
            response = chain.invoke({
                "subject": subject,
                "relation": relation,
                "object": obj,
            })
            raw_content = response.content if hasattr(response, "content") else str(response)
            parsed = self._parse_llm_response(raw_content)

            # 提取字段，提供安全默认值
            order_score = float(parsed.get("order_score", 50.0))
            reasoning = str(parsed.get("reasoning", "LLM 未提供理由"))
            category_raw = str(parsed.get("category", "unknown"))
            valid_categories = {"technology", "geopolitics", "institution", "causality", "unknown"}
            category: CategoryType = category_raw if category_raw in valid_categories else "unknown"  # type: ignore[assignment]
            confidence = float(parsed.get("confidence", 0.7))

            result = OrderedTriple(
                subject=subject,
                relation=relation,
                object=obj,
                order_score=order_score,
                reasoning=reasoning,
                category=category,
                confidence=confidence,
            )

        except Exception as exc:
            logger.error("LLM 评估失败: %s | 三元组: %s -[%s]-> %s", exc, subject, relation, obj)
            result = self._fallback_evaluation(subject, relation, obj)

        self._cache[cache_key] = result
        return result

    def filter_triples(
        self,
        triples: List[Dict[str, Any]],
        min_order_score: float = 50.0,
        mode: ModeType = "balanced",
    ) -> List[OrderedTriple]:
        """对原始三元组列表进行熵值评估并过滤。

        Args:
            triples: 原始三元组列表，每个元素为包含以下键的字典：
                - ``"subject"`` 或 ``"from"``：主体实体
                - ``"relation"`` 或 ``"predicate"``：关系类型
                - ``"object"`` 或 ``"to"``：客体实体
            min_order_score: 秩序评分的最低阈值，默认 50。
                若 ``mode`` 参数被设置，则此参数会被模式对应的阈值覆盖。
            mode: 过滤模式：
                - ``"strict"``   – 严格模式，保留评分 >= 80 的三元组
                - ``"balanced"`` – 平衡模式，保留评分 >= 50 的三元组

        Returns:
            经过评估和过滤后的 OrderedTriple 列表，按 order_score 降序排列。
        """
        # 确定实际阈值：mode 优先于 min_order_score
        threshold = _MODE_THRESHOLDS.get(mode, min_order_score)

        if not triples:
            logger.info("传入空三元组列表，直接返回空结果")
            return []

        logger.info(
            "开始评估 %d 个三元组 | 模式: %s | 阈值: %.0f",
            len(triples),
            mode,
            threshold,
        )

        results: List[OrderedTriple] = []
        filtered_count = 0

        for i, triple in enumerate(triples):
            # 兼容多种字段命名
            subject = str(triple.get("subject") or triple.get("from") or "").strip()
            relation = str(triple.get("relation") or triple.get("predicate") or "").strip()
            obj = str(triple.get("object") or triple.get("to") or "").strip()

            if not subject or not obj:
                logger.debug("跳过无效三元组（缺少主体或客体）: %s", triple)
                filtered_count += 1
                continue

            ordered = self.evaluate_triple(subject, relation, obj)

            if ordered.order_score >= threshold:
                results.append(ordered)
                logger.debug(
                    "[%d/%d] ✅ 保留 (%.0f): %s -[%s]-> %s",
                    i + 1, len(triples), ordered.order_score, subject, relation, obj,
                )
            else:
                filtered_count += 1
                logger.debug(
                    "[%d/%d] ❌ 过滤 (%.0f): %s -[%s]-> %s | %s",
                    i + 1, len(triples), ordered.order_score, subject, relation, obj,
                    ordered.reasoning[:60],
                )

        # 按 order_score 降序排列
        results.sort(key=lambda t: t.order_score, reverse=True)

        logger.info(
            "评估完成 | 保留: %d | 过滤: %d | 总计: %d",
            len(results),
            filtered_count,
            len(triples),
        )
        return results

    def clear_cache(self) -> None:
        """清除内存评估缓存。"""
        self._cache.clear()
        logger.info("评估缓存已清空")
