"""
EL'druin Intelligence Platform – Judgment Panel Component
=========================================================

Renders the right-hand 40 % Judgment column on the Truth Monitor home page.

Three sub-tabs:
  🌤️  Current Situation (Alpha)  – high-confidence scenario (≈ 72 %)
  ⚡  Conflict Escalation (Beta)   – black-swan scenario     (≈ 28 %)
  ✓   Self-Verification (Audit)   – confidence metrics, data gap, counter-argument

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
        "description": "Click '🧠 Ingest Intelligence' to generate the Alpha scenario analysis.",
        "probability": 0.72,
        "key_assumption": "Current trends continue",
    },
    "beta": {
        "description": "Click '🧠 Ingest Intelligence' to generate the Beta scenario analysis.",
        "probability": 0.28,
        "key_assumption": "Key assumptions fail",
    },
    "confidence_score": 0.0,
    "evidence_density": 0.0,
    "data_gap": "No data yet",
    "counter_arg": "No counter-argument yet",
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
    st.subheader("⚖️ El-druin Judgment & Forecast")

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
        "🌤️ Current Situation (Alpha)",
        "⚡ Conflict Escalation (Beta)",
        "✓ Self-Verification (Audit)",
    ])

    # ── Tab 1: Alpha scenario ─────────────────────────────────────────────
    with tab_alpha:
        st.markdown("**Clear-day Path**")
        st.markdown("Most probable evolution trajectory based on available evidence:")
        st.info(alpha_desc)
        st.caption(f"📊 Probability: **{alpha_prob:.0%}**")
        st.caption(f"✓ Assumption: {alpha_assumption}")

    # ── Tab 2: Beta scenario ──────────────────────────────────────────────
    with tab_beta:
        st.markdown("**Conflict Escalation Branch**")
        st.markdown("If key assumptions fail, the following outcome is projected:")
        st.warning(beta_desc)
        st.caption(f"⚠️ Probability: **{beta_prob:.0%}**")
        st.caption(f"⚡ Trigger condition: {beta_assumption}")

    # ── Tab 3: Audit module ───────────────────────────────────────────────
    with tab_audit:
        st.markdown("**Logic Self-Verification**")

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.metric(
                "Confidence",
                f"{confidence_score:.0%}",
                delta=f"Evidence density: {evidence_density:.1f}/5",
            )
        with col_m2:
            gap_short = (data_gap[:_MAX_GAP_DISPLAY_LENGTH] + "…") if len(data_gap) > _MAX_GAP_DISPLAY_LENGTH else data_gap
            st.metric(
                "Key Gap",
                "1",
                delta=gap_short,
            )

        st.divider()

        st.markdown("**📊 Data Gap:**")
        st.markdown(f"> {data_gap}")

        st.divider()

        st.markdown("**⚔️ Strongest Counter-Argument:**")
        st.markdown(f"> {counter_arg}")
