"""
秩序分析组件（Order Critique Component）

展示秩序分析的完整视图：不仅仅列出数据，而是输出"判断力"。

包含：
  - Order Score、Relation Density、Structural Stability 三项 st.metric
  - 哲学层面的解释（由 OrderCritic Agent 生成）
  - 因果链详细展示（可折叠）
  - 稳定性指标 bar chart

Usage::

    from components.order_critique import display_order_critique

    display_order_critique(
        entities=entities,
        relations=relations,
        causal_chains=causal_chains,
        api_client=api_client,
    )
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from utils.api_client import APIClient

logger = logging.getLogger(__name__)


def display_order_critique(
    entities: List[Dict[str, Any]],
    relations: List[Dict[str, Any]],
    causal_chains: List[Dict[str, Any]],
    api_client: "APIClient",
) -> None:
    """展示秩序分析：不仅仅列出数据，而是输出"判断力"。

    Args:
        entities:      提取的实体列表
        relations:     提取的关系列表
        causal_chains: 因果链条列表
        api_client:    APIClient 实例（用于调用后端 critique 端点）
    """
    import streamlit as st
    from utils.deep_extraction import calculate_order_score

    st.markdown("## 🏛️ 秩序分析")

    # ── 1. Top-line metrics ────────────────────────────────────────────────
    order_score = calculate_order_score(entities, relations, causal_chains)
    relation_density = len(relations) / max(len(entities), 1)
    structural_stability = (
        sum(1 for c in causal_chains if c.get("longevity") == "long_term")
        / max(len(causal_chains), 1)
        if causal_chains
        else 0.0
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Order Score", f"{order_score}/100")
    with col2:
        st.metric("Relation Density", f"{relation_density:.2f}")
    with col3:
        st.metric("Structural Stability", f"{structural_stability:.0%}")

    st.markdown("")

    # ── 2. Philosophical explanation ──────────────────────────────────────
    st.markdown("### 📖 系统判断")

    _CRITIQUE_STATE_KEY = "order_critique_text"

    # Try to fetch a new critique only when the data changes (use entity+chain
    # counts as a lightweight change signal, stored in session state).
    _change_signal = f"{len(entities)}_{len(relations)}_{len(causal_chains)}"
    if (
        _CRITIQUE_STATE_KEY not in st.session_state
        or st.session_state.get("_critique_signal") != _change_signal
    ):
        with st.spinner("🤔 正在生成哲学分析…"):
            resp = api_client.get_order_critique(
                entities=entities,
                relations=relations,
                causal_chains=causal_chains,
            )
            if "error" in resp:
                # Construct a local fallback text
                critique_text = _local_fallback_critique(
                    len(entities), len(relations), len(causal_chains)
                )
            else:
                critique_text = resp.get("critique", "")
                if not critique_text:
                    critique_text = _local_fallback_critique(
                        len(entities), len(relations), len(causal_chains)
                    )

        st.session_state[_CRITIQUE_STATE_KEY] = critique_text
        st.session_state["_critique_signal"] = _change_signal

    st.info(st.session_state[_CRITIQUE_STATE_KEY])

    # ── 3. Causal chain details ───────────────────────────────────────────
    if causal_chains:
        st.markdown("### 🔗 因果链条")

        for i, chain in enumerate(causal_chains[:5], 1):
            chain_label = chain.get("chain") or f"Chain {i}"
            with st.expander(f"Chain {i}: {chain_label}", expanded=(i == 1)):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Confidence", f"{float(chain.get('confidence', 0)):.0%}")
                with c2:
                    st.metric("Longevity", chain.get("longevity", "unknown"))
                with c3:
                    st.metric("Scope", chain.get("impact_scope", "unknown"))

                desc = chain.get("description", "")
                if desc:
                    st.write(desc)

    # ── 4. Stability bar chart ────────────────────────────────────────────
    if causal_chains:
        st.markdown("### ⚖️ 稳定性评估")

        n = max(len(causal_chains), 1)
        reversible_ratio = sum(
            1 for c in causal_chains if c.get("reversibility") == "reversible"
        ) / n
        local_ratio = sum(
            1 for c in causal_chains if c.get("impact_scope") == "local"
        ) / n
        short_term_ratio = sum(
            1 for c in causal_chains if c.get("longevity") == "short_term"
        ) / n

        try:
            import pandas as pd

            _stability_df = pd.DataFrame(
                {
                    "Ratio": [reversible_ratio, local_ratio, short_term_ratio],
                },
                index=["Reversibility", "Localization", "Short-term Impact"],
            )
            st.bar_chart(_stability_df, height=180)
        except ImportError:
            st.write(
                f"- Reversibility: {reversible_ratio:.0%}  "
                f"- Localization: {local_ratio:.0%}  "
                f"- Short-term: {short_term_ratio:.0%}"
            )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _local_fallback_critique(
    entity_count: int,
    relation_count: int,
    chain_count: int,
) -> str:
    """Generate a simple fallback philosophical paragraph without calling the backend.

    Note: A similar fallback exists in ``backend/knowledge_layer/order_critic.py``.
    The frontend version is needed for resilience when the backend is completely
    unreachable; both fallbacks are intentionally kept in sync textually.
    """
    density = relation_count / max(entity_count, 1)
    if chain_count > 3 and density > 1.5:
        outlook = "系统正处于结构性重组阶段，短期内波动不可避免，但长期演化方向尚待确认。"
    elif chain_count > 0:
        outlook = "系统呈现出初步的秩序化趋势，关键节点的稳定性将决定整体演化走向。"
    else:
        outlook = "当前数据揭示的关系较为表面，深层因果机制有待进一步挖掘。"

    return (
        f"从本体论视角审视，当前知识图谱所呈现的 {entity_count} 个实体节点与 "
        f"{relation_count} 条语义关系构成了一个信息网络。"
        f"提取到的 {chain_count} 条因果链条揭示了事件背后的驱动机制，"
        f"这些链条是否具有结构性意义，取决于其时间跨度与影响传播范围。"
        f"{outlook}"
        f"El-druin 将持续追踪这些连接的演化，以评估文明体系骨架的稳定性。"
    )
