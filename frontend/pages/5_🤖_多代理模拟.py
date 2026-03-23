"""
多代理危机模拟页面 – LangGraph 驱动的台海危机场景模拟
=========================================================

功能:
  - 注入新闻事件触发器
  - 运行 5–10 步多代理 LangGraph 模拟
  - 可视化代理对话历史、紧张度曲线、分支路径和概率估算

代理:
  LeaderA  – 强硬派领导人（进攻性）
  LeaderB  – 防御派领导人（防守性）
  Ally     – 盟友（支持性）
  Analyst  – 中立分析师（评估概率）
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
    _PLOTLY_AVAILABLE = True
except ImportError:
    _PLOTLY_AVAILABLE = False

_FRONTEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FRONTEND_DIR not in sys.path:
    sys.path.insert(0, _FRONTEND_DIR)

from utils.api_client import APIClient  # noqa: E402

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="多代理模拟 – EL'druin",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Backend client
# ---------------------------------------------------------------------------
_backend_url = os.environ.get("BACKEND_URL", "http://localhost:8001/api/v1")
_api = APIClient(base_url=_backend_url)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "sim_result" not in st.session_state:
    st.session_state.sim_result: Dict[str, Any] = {}

# ---------------------------------------------------------------------------
# Agent colour map
# ---------------------------------------------------------------------------
_AGENT_COLORS: Dict[str, str] = {
    "LeaderA": "#e74c3c",
    "LeaderB": "#3498db",
    "Ally": "#f39c12",
    "Analyst": "#2ecc71",
}
_AGENT_ICONS: Dict[str, str] = {
    "LeaderA": "⚔️",
    "LeaderB": "🛡️",
    "Ally": "🤝",
    "Analyst": "🔬",
}


def _agent_color(agent: str) -> str:
    return _AGENT_COLORS.get(agent, "#95a5a6")


# ===========================================================================
# Page header
# ===========================================================================
st.title("🤖 多代理危机模拟")
st.caption(
    "基于 **LangGraph StateGraph** 的台海危机微型多代理模拟。"
    "注入新闻事件，观察四个代理如何交互并演化出不同的分支结局。"
)

st.divider()

# ===========================================================================
# Sidebar – Agent legend
# ===========================================================================
with st.sidebar:
    st.markdown("### 🎭 代理角色")
    for agent, color in _AGENT_COLORS.items():
        icon = _AGENT_ICONS.get(agent, "🤖")
        st.markdown(
            f"<div style='border-left: 4px solid {color}; padding-left: 8px; "
            f"margin-bottom: 6px'><b>{icon} {agent}</b></div>",
            unsafe_allow_html=True,
        )
    st.divider()
    st.markdown("### ℹ️ 关于模拟")
    st.info(
        "**场景**: 抽象台海危机（CountryA vs CountryB）\n\n"
        "**框架**: LangGraph StateGraph\n\n"
        "**节点** = 代理执行\n\n"
        "**边** = 条件路由（基于紧张度）\n\n"
        "**步数**: 5–10 步\n\n"
        "**输出**: 分支路径 + 概率估算"
    )

# ===========================================================================
# Main area – Input panel
# ===========================================================================
st.subheader("📰 注入新闻事件")

_DEFAULT_EVENT = (
    "CountryA 宣布在争议海峡附近进行大规模实弹演习，部署了三支航母编队，"
    "并向 CountryB 发出 24 小时撤离警告。国际社会高度关注，"
    "盟友 Ally 表示将增加在该地区的军事存在。"
)

col_input, col_settings = st.columns([3, 1])

with col_input:
    news_event = st.text_area(
        "新闻事件摘要",
        value=_DEFAULT_EVENT,
        height=120,
        max_chars=2000,
        key="sim_news_event",
        help="描述触发危机的初始新闻事件，将作为所有代理的共同背景。",
    )

with col_settings:
    max_steps = st.slider("模拟步数", min_value=5, max_value=10, value=8, key="sim_steps")
    initial_tension = st.slider(
        "初始紧张度",
        min_value=0.0,
        max_value=1.0,
        value=0.45,
        step=0.05,
        key="sim_tension",
        help="0.0 = 完全和平，1.0 = 公开冲突",
    )
    use_seed = st.checkbox("固定随机种子", value=False, key="sim_use_seed")
    seed_val = st.number_input("种子值", value=42, step=1, key="sim_seed", disabled=not use_seed)

col_run, col_clear = st.columns([1, 5])
with col_run:
    run_btn = st.button("▶ 运行模拟", type="primary", key="btn_run_sim")
with col_clear:
    if st.button("🗑️ 清除结果", key="btn_clear_sim"):
        st.session_state.sim_result = {}
        st.rerun()

# ===========================================================================
# Run simulation
# ===========================================================================
if run_btn:
    text_stripped = (news_event or "").strip()
    if len(text_stripped) < 10:
        st.warning("⚠️ 事件描述至少需要 10 个字符。")
    else:
        with st.spinner("⏳ 正在运行多代理模拟…"):
            seed = int(seed_val) if use_seed else None
            result = _api.run_simulation(
                news_event=text_stripped,
                max_steps=max_steps,
                initial_tension=initial_tension,
                seed=seed,
            )
        if "error" in result:
            st.error(f"❌ 模拟失败：{result['error']}")
        else:
            st.session_state.sim_result = result
            st.success(f"✅ 模拟完成！共 {result.get('steps_run', '?')} 步。")

# ===========================================================================
# Display results
# ===========================================================================
res = st.session_state.sim_result
if res and "error" not in res:
    st.divider()

    # ── Summary metrics ───────────────────────────────────────────────────
    st.subheader("📊 模拟摘要")
    m1, m2, m3, m4 = st.columns(4)
    tension = res.get("tension_level", 0.0)
    steps_run = res.get("steps_run", 0)
    messages: List[Dict[str, Any]] = res.get("messages", [])
    path: List[str] = res.get("path", [])
    probs: Dict[str, float] = res.get("resolution_probabilities", {})

    tension_color = "#e74c3c" if tension > 0.7 else ("#f39c12" if tension > 0.4 else "#2ecc71")
    m1.metric("⚡ 最终紧张度", f"{tension:.3f}")
    m2.metric("🔄 已执行步数", steps_run)
    m3.metric("💬 消息总数", len(messages))
    dominant_path = max(set(path), key=path.count) if path else "—"
    m4.metric("🛤️ 主分支", dominant_path)

    st.divider()

    # ── Tabs ──────────────────────────────────────────────────────────────
    tab_msg, tab_tension, tab_path, tab_prob, tab_agents = st.tabs(
        ["💬 对话历史", "📈 紧张度曲线", "🛤️ 分支路径", "🎲 概率估算", "🎭 代理档案"]
    )

    # ── Tab 1: Message history ────────────────────────────────────────────
    with tab_msg:
        st.subheader("💬 代理交互历史")
        if messages:
            for msg in messages:
                agent = msg.get("agent", "?")
                color = _agent_color(agent)
                icon = _AGENT_ICONS.get(agent, "🤖")
                role = msg.get("role", "")
                content = msg.get("content", "")
                step_num = msg.get("step", "?")
                delta = msg.get("tension_delta", 0.0)
                delta_str = f"+{delta:.3f}" if delta >= 0 else f"{delta:.3f}"
                delta_color = "#e74c3c" if delta > 0 else ("#2ecc71" if delta < 0 else "#95a5a6")

                st.markdown(
                    f"""<div style='border-left: 4px solid {color}; padding: 10px 14px;
                    margin-bottom: 10px; background-color: #1e1e2e; border-radius: 4px;'>
                    <div style='display:flex; justify-content:space-between; margin-bottom:4px;'>
                        <span style='color:{color}; font-weight:bold;'>{icon} {agent}
                        <span style='color:#aaa; font-weight:normal;'> – {role}</span></span>
                        <span style='color:#888; font-size:0.85em;'>Step {step_num} &nbsp;
                        <span style='color:{delta_color}'>Δ{delta_str}</span></span>
                    </div>
                    <div style='color:#e0e0e0;'>{content}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
        else:
            st.info("无消息。")

    # ── Tab 2: Tension chart ───────────────────────────────────────────────
    with tab_tension:
        st.subheader("📈 紧张度演化曲线")
        if messages and _PLOTLY_AVAILABLE:
            # Reconstruct tension over time from tension_deltas
            tension_history = [res.get("initial_tension", initial_tension)]
            labels = ["初始"]
            for msg in messages:
                prev = tension_history[-1]
                nxt = max(0.0, min(1.0, prev + msg.get("tension_delta", 0.0)))
                tension_history.append(nxt)
                labels.append(f"Step {msg.get('step', '?')} ({msg.get('agent', '?')})")

            # Colour zones
            fig = go.Figure()

            # Background zones
            fig.add_hrect(y0=0.7, y1=1.0, fillcolor="rgba(231,76,60,0.08)", line_width=0)
            fig.add_hrect(y0=0.35, y1=0.7, fillcolor="rgba(243,156,18,0.08)", line_width=0)
            fig.add_hrect(y0=0.0, y1=0.35, fillcolor="rgba(46,204,113,0.08)", line_width=0)

            # Tension line
            fig.add_trace(go.Scatter(
                x=list(range(len(tension_history))),
                y=tension_history,
                mode="lines+markers",
                name="紧张度",
                line={"color": "#e74c3c", "width": 2.5},
                marker={"size": 7},
                hovertext=labels,
                hoverinfo="text+y",
            ))

            # Threshold lines
            fig.add_hline(y=0.7, line_dash="dash", line_color="#e74c3c",
                          annotation_text="升级阈值 (0.7)", annotation_position="top right")
            fig.add_hline(y=0.35, line_dash="dash", line_color="#2ecc71",
                          annotation_text="降级阈值 (0.35)", annotation_position="bottom right")

            fig.update_layout(
                xaxis_title="模拟步骤",
                yaxis_title="紧张度",
                yaxis={"range": [0, 1]},
                height=380,
                margin={"t": 30, "b": 40},
                showlegend=False,
                plot_bgcolor="#0e1117",
                paper_bgcolor="#0e1117",
                font={"color": "#e0e0e0"},
            )
            st.plotly_chart(fig, use_container_width=True)

            # Zone legend
            lc1, lc2, lc3 = st.columns(3)
            lc1.markdown("🔴 **升级区** (>0.7): 冲突风险高")
            lc2.markdown("🟡 **谈判区** (0.35–0.7): 外交博弈")
            lc3.markdown("🟢 **缓和区** (<0.35): 紧张缓解")
        elif not _PLOTLY_AVAILABLE:
            st.info("安装 `plotly` 以显示紧张度曲线。")
        else:
            st.info("无数据。")

    # ── Tab 3: Branch path ────────────────────────────────────────────────
    with tab_path:
        st.subheader("🛤️ 分支路径轨迹")
        if path:
            # Visual path timeline
            path_colors = {
                "escalation": "#e74c3c",
                "negotiation": "#f39c12",
                "de-escalation": "#2ecc71",
            }
            path_icons = {
                "escalation": "⬆️ 升级",
                "negotiation": "🤝 谈判",
                "de-escalation": "⬇️ 降级",
            }

            # Count transitions
            path_counts: Dict[str, int] = {}
            for p in path:
                path_counts[p] = path_counts.get(p, 0) + 1

            cols = st.columns(min(len(path), 8))
            for idx, branch in enumerate(path):
                color = path_colors.get(branch, "#95a5a6")
                label = path_icons.get(branch, branch)
                with cols[idx % len(cols)]:
                    st.markdown(
                        f"<div style='text-align:center; background:{color}22; "
                        f"border: 2px solid {color}; border-radius:8px; padding:8px; "
                        f"margin-bottom:4px; font-size:0.85em;'>"
                        f"<b>{label}</b><br/>评估 #{idx + 1}</div>",
                        unsafe_allow_html=True,
                    )

            st.markdown("---")
            st.markdown("**分支频率统计**")
            df_path = pd.DataFrame(
                [{"分支类型": k, "出现次数": v, "占比": f"{v/len(path)*100:.1f}%"}
                 for k, v in path_counts.items()]
            )
            st.dataframe(df_path, use_container_width=True, hide_index=True)

            # Describe final state
            final_branch = path[-1]
            if final_branch == "escalation":
                st.error("🔴 模拟以**升级**状态结束 — 危机处于高度紧张阶段。")
            elif final_branch == "de-escalation":
                st.success("🟢 模拟以**降级**状态结束 — 紧张局势趋于缓和。")
            else:
                st.warning("🟡 模拟以**谈判**状态结束 — 局势悬而未决，外交斡旋仍在进行。")
        else:
            st.info("无分支路径数据。")

    # ── Tab 4: Probability estimates ─────────────────────────────────────
    with tab_prob:
        st.subheader("🎲 最终概率估算")
        if probs and _PLOTLY_AVAILABLE:
            labels_p = list(probs.keys())
            values_p = list(probs.values())
            colors_p = ["#e74c3c", "#3498db", "#f39c12"][: len(labels_p)]

            # Pie chart
            fig_pie = go.Figure(go.Pie(
                labels=labels_p,
                values=values_p,
                hole=0.45,
                marker={"colors": colors_p},
                textinfo="label+percent",
                hoverinfo="label+value",
            ))
            fig_pie.update_layout(
                height=350,
                margin={"t": 20, "b": 20},
                paper_bgcolor="#0e1117",
                font={"color": "#e0e0e0"},
                showlegend=True,
            )
            st.plotly_chart(fig_pie, use_container_width=True)

            # Table
            df_probs = pd.DataFrame(
                [{"结局类型": k, "概率": f"{v:.1%}"} for k, v in probs.items()]
            )
            st.dataframe(df_probs, use_container_width=True, hide_index=True)

            # Dominant outcome
            dominant = max(probs, key=probs.get)  # type: ignore[arg-type]
            dom_prob = probs[dominant]
            st.markdown(f"**最可能结局**: `{dominant}` ({dom_prob:.1%})")
        elif probs:
            for k, v in probs.items():
                st.metric(k, f"{v:.1%}")
        else:
            st.info("概率数据尚不可用（分析师尚未运行）。")

    # ── Tab 5: Agent profiles ─────────────────────────────────────────────
    with tab_agents:
        st.subheader("🎭 代理档案")
        agents_meta: Dict[str, Any] = res.get("agents", {})
        if agents_meta:
            for agent_name, meta in agents_meta.items():
                color = _agent_color(agent_name)
                icon = _AGENT_ICONS.get(agent_name, "🤖")
                with st.expander(f"{icon} **{agent_name}** – {meta.get('role', '')}"):
                    st.markdown(f"**目标 (Goal)**: {meta.get('goal', '')}")
                    st.markdown(f"**背景 (Backstory)**: {meta.get('backstory', '')}")

    # ── KG context ────────────────────────────────────────────────────────
    kg_ctx = res.get("kg_context", "")
    if kg_ctx and kg_ctx != "Knowledge graph context unavailable.":
        with st.expander("🕸️ 知识图谱上下文"):
            st.text(kg_ctx)

    # ── Elapsed time ─────────────────────────────────────────────────────
    elapsed = res.get("elapsed_ms", 0)
    st.caption(f"⏱️ 模拟耗时: {elapsed} ms")

elif not run_btn:
    st.info("👆 在上方输入新闻事件，设置参数后点击「▶ 运行模拟」开始。")
