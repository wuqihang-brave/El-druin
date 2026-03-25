"""
EL'druin Intelligence Platform – Judgment Panel Component
=========================================================

Renders the right-hand 40 % Judgment column on the Truth Monitor home page.

Three sub-tabs:
  🌤️  当前局势 (Alpha)  – high-confidence scenario (≈ 72 %)
  ⚡  冲突演化 (Beta)   – black-swan scenario     (≈ 28 %)
  ✓   自验证 (Audit)   – confidence metrics, data gap, counter-argument

The container carries a Champagne-gold (#D4AF37) border to maintain visual
brand consistency.
"""

from __future__ import annotations

from typing import Any, Dict

import streamlit as st


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_GAP_DISPLAY_LENGTH = 30  # Characters shown in the metric delta for data gap


# ---------------------------------------------------------------------------
# Default / placeholder analysis
# ---------------------------------------------------------------------------

_PLACEHOLDER_ANALYSIS: Dict[str, Any] = {
    "alpha": {
        "description": "点击「🧠 Ingest Intelligence」以生成 Alpha 分支分析。",
        "probability": 0.72,
        "key_assumption": "当前趋势继续",
    },
    "beta": {
        "description": "点击「🧠 Ingest Intelligence」以生成 Beta 分支分析。",
        "probability": 0.28,
        "key_assumption": "关键假设失效",
    },
    "confidence_score": 0.0,
    "evidence_density": 0.0,
    "data_gap": "暂无数据",
    "counter_arg": "暂无反论",
}


# ---------------------------------------------------------------------------
# Judgment Panel renderer
# ---------------------------------------------------------------------------

def render_judgment_panel(analysis: Dict[str, Any] | None = None) -> None:
    """Render the El-druin Judgment & Prediction panel.

    Args:
        analysis: SacredSwordAnalysis-style dict (or compatible).  When
                  *None* / empty, the component shows placeholder text.
    """
    data = analysis if analysis else _PLACEHOLDER_ANALYSIS

    alpha = data.get("alpha") or _PLACEHOLDER_ANALYSIS["alpha"]
    beta = data.get("beta") or _PLACEHOLDER_ANALYSIS["beta"]

    alpha_prob = alpha.get("probability", 0.72)
    beta_prob = beta.get("probability", 0.28)
    alpha_desc = alpha.get("description", "—")
    alpha_assumption = alpha.get("key_assumption", "—")
    beta_desc = beta.get("description", "—")
    beta_assumption = beta.get("key_assumption", "—")
    confidence_score = data.get("confidence_score", 0.0)
    evidence_density = data.get("evidence_density", 0.0)
    data_gap = data.get("data_gap", "—")
    counter_arg = data.get("counter_arg", "—")

    # ── Panel title ───────────────────────────────────────────────────────
    st.subheader("⚖️ El-druin 裁决与预测")

    # ── Champagne-gold border wrapper (CSS injection) ─────────────────────
    st.markdown(
        """
        <style>
        div[data-testid="stTabs"] {
            border: 2px solid #D4AF37 !important;
            border-radius: 6px;
            padding: 12px 16px 16px 16px;
            background: linear-gradient(
                135deg,
                rgba(212,175,55,0.04) 0%,
                rgba(255,255,255,0.9) 100%
            );
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── Three sub-tabs ────────────────────────────────────────────────────
    tab_alpha, tab_beta, tab_audit = st.tabs([
        "🌤️ 当前局势 (Alpha)",
        "⚡ 冲突演化 (Beta)",
        "✓ 自验证 (Audit)",
    ])

    # ── Tab 1: Alpha scenario ─────────────────────────────────────────────
    with tab_alpha:
        st.markdown("**清晰日光路径**")
        st.markdown("当前最可能的演化趋势基于现有事实：")
        st.info(alpha_desc)
        st.caption(f"📊 概率: **{alpha_prob:.0%}**")
        st.caption(f"✓ 假设: {alpha_assumption}")

    # ── Tab 2: Beta scenario ──────────────────────────────────────────────
    with tab_beta:
        st.markdown("**冲突演化分支**")
        st.markdown("如果关键假设失效，将发生：")
        st.warning(beta_desc)
        st.caption(f"⚠️ 概率: **{beta_prob:.0%}**")
        st.caption(f"⚡ 触发条件: {beta_assumption}")

    # ── Tab 3: Audit module ───────────────────────────────────────────────
    with tab_audit:
        st.markdown("**逻辑自验证**")

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.metric(
                "置信度",
                f"{confidence_score:.0%}",
                delta=f"证据密度: {evidence_density:.1f}/5",
            )
        with col_m2:
            gap_short = (data_gap[:_MAX_GAP_DISPLAY_LENGTH] + "…") if len(data_gap) > _MAX_GAP_DISPLAY_LENGTH else data_gap
            st.metric(
                "关键缺口",
                "1",
                delta=gap_short,
            )

        st.divider()

        st.markdown("**📊 数据缺口:**")
        st.markdown(f"> {data_gap}")

        st.divider()

        st.markdown("**⚔️ 最强反论:**")
        st.markdown(f"> {counter_arg}")
