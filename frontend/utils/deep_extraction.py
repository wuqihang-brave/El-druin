"""
深度提取工具（Deep Extraction Utilities）

为前端提供因果链相关的辅助函数：
  - extract_causal_chains(): 通过后端 API 提取因果链
  - calculate_order_score(): 本地计算秩序评分
  - visualize_confidence():  Streamlit 置信度可视化

Usage::

    from utils.deep_extraction import extract_causal_chains, calculate_order_score
    from utils.deep_extraction import visualize_confidence
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from utils.api_client import APIClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Order score calculation (mirrors backend logic; used for local fallback)
# ---------------------------------------------------------------------------

def calculate_order_score(
    entities: List[Dict[str, Any]],
    relations: List[Dict[str, Any]],
    causal_chains: List[Dict[str, Any]],
) -> int:
    """计算秩序评分（0-100）。

    公式：
      Base Score = min(100, (Relation Count / Entity Count) * 50 + 50)

      Modifiers:
        + Causal Chain Bonus:    len(causal_chains) * 2
        + Structural Bonus:      count(long_term chains) * 5
        + Confidence Bonus:      avg(confidence) * 10
        - Reversibility Penalty: count(reversible chains) * 2

    Args:
        entities:      提取的实体列表
        relations:     提取的关系列表
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
# Backend API call wrapper
# ---------------------------------------------------------------------------

def extract_causal_chains(news_text: str, api_client: "APIClient") -> Dict[str, Any]:
    """从新闻文本中通过后端 API 深度提取因果链条。

    若后端返回错误（例如 LLM API key 未配置），则返回带有空列表的兜底结构。

    Args:
        news_text:  新闻原文
        api_client: APIClient 实例

    Returns:
        包含以下键的字典：
        - ``entities``:           提取的实体列表
        - ``relations``:          提取的关系列表
        - ``causal_chains``:      因果链条列表
        - ``overall_order_score``: 整体秩序评分（0-100）
    """
    _EMPTY: Dict[str, Any] = {
        "entities": [],
        "relations": [],
        "causal_chains": [],
        "overall_order_score": 50,
    }

    if not news_text or not news_text.strip():
        return _EMPTY

    try:
        resp = api_client.extract_causal_chains(news_text)
        if "error" in resp:
            logger.warning("因果链 API 返回错误: %s", resp["error"])
            return _EMPTY
        return {
            "entities": resp.get("entities", []),
            "relations": resp.get("relations", []),
            "causal_chains": resp.get("causal_chains", []),
            "overall_order_score": resp.get("overall_order_score", 50),
        }
    except Exception as exc:
        logger.error("因果链提取调用失败: %s", exc)
        return _EMPTY


# ---------------------------------------------------------------------------
# Streamlit visualisation
# ---------------------------------------------------------------------------

def visualize_confidence(causal_chains: List[Dict[str, Any]]) -> None:
    """展示因果链的置信度分布（Streamlit 可视化）。

    使用 st.bar_chart 展示多个因果链的置信度，并用三列 st.metric 展示汇总统计。

    Args:
        causal_chains: 因果链条列表，每条需包含 ``chain``、``confidence``、
                       ``longevity`` 和 ``impact_scope`` 字段。
    """
    import streamlit as st

    if not causal_chains:
        st.info("📭 暂无因果链数据。")
        return

    try:
        import pandas as pd

        # Build chart data – truncate long chain labels
        chart_data = pd.DataFrame([
            {
                "因果链": (c.get("chain") or f"Chain {i + 1}")[:40],
                "置信度": float(c.get("confidence", 0.0)),
            }
            for i, c in enumerate(causal_chains)
        ]).set_index("因果链")

        st.bar_chart(chart_data, height=200)
    except ImportError:
        st.warning("⚠️ pandas 不可用，无法渲染置信度图表。")

    # Summary metrics
    avg_confidence = sum(float(c.get("confidence", 0)) for c in causal_chains) / len(causal_chains)
    long_term_count = sum(1 for c in causal_chains if c.get("longevity") == "long_term")
    global_scope = sum(1 for c in causal_chains if c.get("impact_scope") == "global")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Avg Confidence", f"{avg_confidence:.0%}")
    with col2:
        st.metric("Structural Chains", long_term_count)
    with col3:
        st.metric("Global Impact", global_scope)
