"""
深度因果链提取器（Deep Causal Chain Extractor）

从新闻文本中提取深层因果关系链，而不仅仅是表面的主谓宾三元组。
使用增强的 Prompt 强制 LLM 发现隐藏的、多步骤的影响路径。

用法示例::

    from knowledge_layer.causal_chain_extractor import extract_causal_chains

    result = extract_causal_chains("美国对中国芯片产业实施新制裁……")
    print(result["causal_chains"])
    print(result["overall_order_score"])
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enhanced LLM prompt for deep causal chain extraction
# ---------------------------------------------------------------------------

_CAUSAL_CHAIN_SYSTEM_PROMPT = """你是一个因果链条识别专家（Causal Chain Expert）。分析以下新闻事件，提取：

1. 主要实体（Person, Organization, Location, Technology, Policy）
2. 直接关系（immediate relations）
3. **因果链条**（causal chains）：找出隐藏的、多步骤的影响路径

对每个因果链，评估其：
- 长期性（是否影响系统结构，而非瞬时波动）
- 传播性（影响是否会扩散到其他领域）
- 可逆性（是否是不可逆的结构性变化）

请严格按照如下 JSON 格式返回，不要包含任何额外文字：
{
  "entities": [
    {"name": "...", "type": "Person|Organization|Location|Technology|Policy|Other", "importance": 0.0}
  ],
  "relations": [
    {"from": "...", "to": "...", "type": "direct", "strength": 0.0}
  ],
  "causal_chains": [
    {
      "chain": "A → B → C → D",
      "description": "具体的因果机制说明",
      "confidence": 0.85,
      "longevity": "long_term",
      "impact_scope": "global",
      "reversibility": "irreversible"
    }
  ]
}

注意：
- longevity 只能是 "short_term" 或 "long_term"
- impact_scope 只能是 "local"、"regional" 或 "global"
- reversibility 只能是 "reversible" 或 "irreversible"
- confidence 是 0.0-1.0 的小数
- importance 和 strength 是 0.0-1.0 的小数"""

_CAUSAL_CHAIN_HUMAN_TEMPLATE = (
    "请从以下新闻文本中提取因果链条和深层结构关系：\n\n{text}\n\n"
    "请返回 JSON 格式的分析结果。"
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_llm(api_key: str, model: str, temperature: float = 0.1) -> Any:
    """Build an LLM instance supporting DeepSeek, Groq, or OpenAI."""
    try:
        from app.core.config import get_settings
        settings = get_settings()
        provider = settings.llm_provider
    except Exception:
        provider = "groq"

    if provider == "deepseek":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=settings.openai_api_key,
        )
    else:
        from langchain_groq import ChatGroq
        return ChatGroq(model=model, temperature=temperature, api_key=api_key)


def _parse_response(raw: str) -> Dict[str, Any]:
    """解析 LLM 返回的 JSON，处理常见格式异常。"""
    text = raw.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        text = text[start:end]
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("因果链 JSON 解析失败: %s | 原始响应: %.200s", exc, raw)
        return {}


def _fallback_extraction() -> Dict[str, Any]:
    """当 LLM 不可用时，返回空结构。"""
    return {
        "entities": [],
        "relations": [],
        "causal_chains": [],
    }


def _resolve_api_key() -> Optional[str]:
    """从应用配置或环境变量中读取 API key。"""
    try:
        from app.core.config import get_settings
        settings = get_settings()
        if settings.llm_provider == "deepseek" and settings.deepseek_api_key:
            return settings.deepseek_api_key
        if settings.llm_provider == "openai" and settings.openai_api_key:
            return settings.openai_api_key
        if settings.groq_api_key:
            return settings.groq_api_key
    except ImportError:
        pass
    return os.getenv("GROQ_API_KEY")


# ---------------------------------------------------------------------------
# Order score calculation
# ---------------------------------------------------------------------------

def calculate_overall_order_score(
    entities: List[Dict[str, Any]],
    relations: List[Dict[str, Any]],
    causal_chains: List[Dict[str, Any]],
) -> int:
    """计算整体秩序评分（0-100）。

    公式：
      Base Score = min(100, (Relation Count / Entity Count) * 50 + 50)

      Modifiers:
        + Causal Chain Bonus:   len(causal_chains) * 2
        + Structural Bonus:     count(long_term chains) * 5
        + Confidence Bonus:     avg(confidence) * 10
        - Reversibility Penalty: count(reversible chains) * 2

    Args:
        entities: 提取的实体列表
        relations: 提取的关系列表
        causal_chains: 因果链条列表

    Returns:
        0-100 的整数评分
    """
    relation_density = len(relations) / max(len(entities), 1)
    base_score = min(100.0, relation_density * 50.0 + 50.0)

    chain_bonus = len(causal_chains) * 2
    structural_bonus = sum(5 for c in causal_chains if c.get("longevity") == "long_term")
    confidence_bonus = (
        sum(float(c.get("confidence", 0.0)) for c in causal_chains)
        / max(len(causal_chains), 1)
        * 10.0
        if causal_chains
        else 0.0
    )
    reversibility_penalty = sum(
        2 for c in causal_chains if c.get("reversibility") == "reversible"
    )

    final = min(
        100.0,
        base_score + chain_bonus + structural_bonus + confidence_bonus - reversibility_penalty,
    )
    return int(final)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_causal_chains(
    news_text: str,
    api_key: Optional[str] = None,
    model: str = "llama3-8b-8192",
) -> Dict[str, Any]:
    """从新闻文本中深度提取因果链条。

    使用增强的 Prompt 调用 LLM，提取实体、关系和多步骤因果链。

    Args:
        news_text: 新闻原文
        api_key: Groq API 密钥（None 时从环境变量读取）
        model: 使用的 LLM 模型名称

    Returns:
        包含以下键的字典：
        - ``entities``:          提取的实体列表
        - ``relations``:         提取的关系列表
        - ``causal_chains``:     因果链条列表（含 confidence、longevity 等属性）
        - ``overall_order_score``: 整体秩序评分（0-100）
    """
    resolved_key = api_key or _resolve_api_key()

    if not resolved_key:
        logger.warning("未配置 Groq API key，返回空因果链结果")
        result = _fallback_extraction()
        result["overall_order_score"] = 50
        return result

    try:
        from langchain_core.prompts import ChatPromptTemplate

        prompt = ChatPromptTemplate.from_messages([
            ("system", _CAUSAL_CHAIN_SYSTEM_PROMPT),
            ("human", _CAUSAL_CHAIN_HUMAN_TEMPLATE),
        ])
        llm = _build_llm(resolved_key, model)
        chain = prompt | llm

        # Limit text length to avoid token overflow
        response = chain.invoke({"text": news_text[:4000]})
        raw_content = response.content if hasattr(response, "content") else str(response)
        parsed = _parse_response(raw_content)

        entities: List[Dict[str, Any]] = parsed.get("entities", [])
        relations: List[Dict[str, Any]] = parsed.get("relations", [])
        causal_chains: List[Dict[str, Any]] = parsed.get("causal_chains", [])

        overall_score = calculate_overall_order_score(entities, relations, causal_chains)

        return {
            "entities": entities,
            "relations": relations,
            "causal_chains": causal_chains,
            "overall_order_score": overall_score,
        }

    except Exception as exc:
        logger.error("因果链提取失败: %s", exc, exc_info=True)
        result = _fallback_extraction()
        result["overall_order_score"] = 50
        return result
