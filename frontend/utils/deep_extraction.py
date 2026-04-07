"""
深度提取工具（Deep Extraction Utilities）

为前端提供因果链相关的辅助函数：
  - extract_causal_chains(): 通过后端 API 提取因果链
  - calculate_order_score(): 本地计算秩序评分
  - visualize_confidence():  Streamlit 置信度可视化
  - calculate_systemic_order_score(): 系统秩序评分（仪表板核心指标）
  - get_order_status():               根据评分返回状态描述
  - calculate_signal_noise_ratio():   信号/噪音比例
  - get_entity_order_importance():    实体秩序重要性
  - categorize_entities_by_order():   按重要性对实体分组

Usage::

    from utils.deep_extraction import extract_causal_chains, calculate_order_score
    from utils.deep_extraction import visualize_confidence
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

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
            logger.warning("Causal chain API returned error: %s", resp["error"])
            return _EMPTY
        return {
            "entities": resp.get("entities", []),
            "relations": resp.get("relations", []),
            "causal_chains": resp.get("causal_chains", []),
            "overall_order_score": resp.get("overall_order_score", 50),
        }
    except Exception as exc:
        logger.error("Causal chain extraction call failed: %s", exc)
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
        st.info("📭 No causal chain data available.")
        return

    try:
        import pandas as pd

        # Build chart data – truncate long chain labels
        chart_data = pd.DataFrame([
            {
                "Causal Chain": (c.get("chain") or f"Chain {i + 1}")[:40],
                "Confidence": float(c.get("confidence", 0.0)),
            }
            for i, c in enumerate(causal_chains)
        ]).set_index("Causal Chain")

        st.bar_chart(chart_data, height=200)
    except ImportError:
        st.warning("⚠️ pandas is not available; confidence chart cannot be rendered.")

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


# ---------------------------------------------------------------------------
# Systemic Order Metrics  (used by the 📊 仪表板 dashboard page)
# ---------------------------------------------------------------------------

def calculate_systemic_order_score(
    relations_count: int,
    entities_count: int,
    news_count: int,
) -> float:
    """计算系统秩序评分（Systemic Order Score）。

    公式::

        Order Score = (Relations / Entities) × log(Total News) × 10

    范围：0-100
      - 0-30：混沌状态
      - 30-60：过渡状态
      - 60-100：秩序状态

    Args:
        relations_count: 知识图谱中的关系总数
        entities_count:  知识图谱中的实体总数
        news_count:      摄入的新闻总数

    Returns:
        0-100 的浮点秩序评分
    """
    if entities_count == 0:
        return 0.0
    relation_density = relations_count / entities_count
    news_factor = math.log(max(news_count, 1))
    # × 10 (not × 100) so that typical values land in the 0-100 range.
    # The problem statement example confirms: (119/78) × ln(71) × 10 ≈ 65.0
    score = relation_density * news_factor * 10.0
    return min(100.0, max(0.0, score))


def get_order_status(score: float) -> str:
    """Return a status label for the given order score.

    Args:
        score: 0-100 order score

    Returns:
        Icon-prefixed English status description
    """
    if score < 30:
        return "🔴 Chaotic"
    elif score < 60:
        return "🟡 Transitional"
    else:
        return "🟢 Ordered"


def calculate_signal_noise_ratio(
    articles_with_entities: int,
    total_articles: int,
) -> Tuple[float, float]:
    """计算信号/噪音比例。

    Signal: 已提取实体的新闻（有知识图谱条目）
    Noise:  尚未处理的原始新闻

    Args:
        articles_with_entities: 已提取到知识图谱的文章数
        total_articles:         摄入的新闻总数

    Returns:
        ``(signal_ratio, noise_ratio)`` 均为 0-1 之间的浮点数
    """
    if total_articles == 0:
        return 0.0, 1.0
    signal_ratio = articles_with_entities / total_articles
    noise_ratio = 1.0 - signal_ratio
    return signal_ratio, noise_ratio


def get_entity_order_importance(entity_degree: int, max_degree: int) -> float:
    """计算实体的秩序重要性（0-100）。

    基于该实体在知识图中的连接度数（degree）。

    Args:
        entity_degree: 该实体的度数（连接边数）
        max_degree:    全图最高度数

    Returns:
        0-100 的浮点重要性分
    """
    if max_degree == 0:
        return 0.0
    return min(100.0, max(0.0, (entity_degree / max_degree) * 100.0))


def categorize_entities_by_order(
    entities: List[Dict[str, Any]],
    degrees: Dict[str, int],
) -> Dict[str, List[Dict[str, Any]]]:
    """按秩序重要性对实体进行分组。

    分组层级：
      - 🌟 Critical Hubs (90-100)
      - ⭐ Important Nodes (70-90)
      - ✦ Bridge Nodes (50-70)
      - · Leaf Nodes (0-50)

    Args:
        entities: 实体列表（每个实体含 ``name`` 键）
        degrees:  实体名称 → 度数的映射字典

    Returns:
        按分组名称分组的实体字典
    """
    max_degree = max(degrees.values()) if degrees else 1
    categories: Dict[str, List[Dict[str, Any]]] = {
        "🌟 Critical Hubs (90-100)": [],
        "⭐ Important Nodes (70-90)": [],
        "✦ Bridge Nodes (50-70)": [],
        "· Leaf Nodes (0-50)": [],
    }

    for entity in entities:
        entity_name = entity.get("name", "")
        degree = degrees.get(entity_name, 0)
        importance = get_entity_order_importance(degree, max_degree)

        if importance >= 90:
            categories["🌟 Critical Hubs (90-100)"].append(entity)
        elif importance >= 70:
            categories["⭐ Important Nodes (70-90)"].append(entity)
        elif importance >= 50:
            categories["✦ Bridge Nodes (50-70)"].append(entity)
        else:
            categories["· Leaf Nodes (0-50)"].append(entity)

    return categories
