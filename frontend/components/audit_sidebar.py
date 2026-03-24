"""
EL'druin Intelligence Platform – Logic Audit Sidebar Component
==============================================================

Renders the Bayesian Bridge audit trail when a user clicks on a knowledge
graph node or provides a reasoning path / probability tree object.

Usage::

    from components.audit_sidebar import render_audit_sidebar

    render_audit_sidebar(reasoning_path=path_dict, probability_tree=tree_dict)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _confidence_bar(label: str, value: float, color: str = "#D4AF37") -> None:
    """Render a labelled progress bar with an Apostolic Gold accent."""
    col_label, col_bar = st.columns([2, 3])
    with col_label:
        st.markdown(
            f"<span style='color:#A8A8A8;font-size:0.8rem'>{label}</span>",
            unsafe_allow_html=True,
        )
    with col_bar:
        pct = min(max(int(value * 100), 0), 100)
        st.markdown(
            f"""
            <div style="background:#1a1e24;border-radius:4px;height:10px;margin-top:6px;">
              <div style="background:{color};width:{pct}%;height:10px;border-radius:4px;"></div>
            </div>
            <span style='color:#D4AF37;font-size:0.75rem;'>{value:.2f}</span>
            """,
            unsafe_allow_html=True,
        )


def _audit_badge(status: str) -> None:
    """Render a coloured badge for the audit status."""
    colours = {
        "approved": ("#22c55e", "#0D0D0D"),
        "flagged": ("#ef4444", "#F0F0F0"),
        "pending_review": ("#D4AF37", "#0D0D0D"),
    }
    bg, fg = colours.get(status, ("#6b7280", "#F0F0F0"))
    label = status.replace("_", " ").upper()
    st.markdown(
        f"""<span style="background:{bg};color:{fg};padding:2px 10px;
            border-radius:12px;font-size:0.75rem;font-weight:600;
            font-family:'Inter',sans-serif;">{label}</span>""",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------

def render_audit_sidebar(
    reasoning_path: Optional[Dict[str, Any]] = None,
    probability_tree: Optional[Dict[str, Any]] = None,
    container=None,
) -> None:
    """Render the Logic Audit Trail in a sidebar or container.

    Args:
        reasoning_path: Serialised ``ReasoningPath`` dict (from the API).
        probability_tree: Serialised ``ProbabilityTree`` dict (from the API).
        container: Streamlit container to render into (defaults to
            ``st.sidebar`` when ``None``).
    """
    ctx = container if container is not None else st.sidebar

    ctx.markdown(
        "<h4 style='color:#D4AF37;font-family:Inter,sans-serif;letter-spacing:2px;"
        "font-weight:300;margin-bottom:4px;'>⚖️ LOGIC AUDIT TRAIL</h4>",
        unsafe_allow_html=True,
    )
    ctx.markdown(
        "<hr style='border-color:#2D333B;margin:4px 0 12px 0'/>",
        unsafe_allow_html=True,
    )

    if reasoning_path is None and probability_tree is None:
        ctx.info("Click a graph node to load its audit trail.")
        return

    # ── Reasoning Path section ────────────────────────────────────────────
    if reasoning_path:
        _render_reasoning_path(reasoning_path, ctx)

    # ── Probability Tree section ──────────────────────────────────────────
    if probability_tree:
        _render_probability_tree(probability_tree, ctx)


def _render_reasoning_path(path: Dict[str, Any], ctx) -> None:
    """Render the ReasoningPath section."""
    ctx.markdown(
        "<h5 style='color:#F0F0F0;font-size:0.85rem;font-weight:600;"
        "letter-spacing:1px;margin:8px 0 4px 0;'>📍 Reasoning Path</h5>",
        unsafe_allow_html=True,
    )

    # Metadata row
    source = path.get("source", {})
    col1, col2 = ctx.columns(2)
    with col1:
        ctx.markdown(
            f"<span style='color:#A8A8A8;font-size:0.75rem'>Source type</span><br>"
            f"<span style='color:#F0F0F0;font-size:0.82rem'>{source.get('type','—')}</span>",
            unsafe_allow_html=True,
        )
    with col2:
        status = path.get("audit_status", "pending_review")
        ctx.markdown(
            "<span style='color:#A8A8A8;font-size:0.75rem'>Status</span><br>",
            unsafe_allow_html=True,
        )
        _audit_badge(status)

    ctx.markdown("<div style='margin:6px 0'/>", unsafe_allow_html=True)

    # Confidence meter
    final_conf = path.get("final_confidence", 0.0)
    ctx.markdown(
        "<span style='color:#A8A8A8;font-size:0.75rem'>Final confidence</span>",
        unsafe_allow_html=True,
    )
    _confidence_bar("", final_conf)

    # Source reliability
    source_rel = source.get("reliability", 0.0)
    ctx.markdown(
        "<span style='color:#A8A8A8;font-size:0.75rem'>Source reliability</span>",
        unsafe_allow_html=True,
    )
    _confidence_bar("", source_rel, color="#7c9dc7")

    # Source URL
    url = source.get("url", "")
    if url:
        ctx.markdown(
            f"<a href='{url}' target='_blank' style='color:#7c9dc7;font-size:0.75rem;"
            f"text-decoration:none;'>🔗 {url[:50]}{'…' if len(url) > 50 else ''}</a>",
            unsafe_allow_html=True,
        )

    ctx.markdown("<div style='margin:8px 0'/>", unsafe_allow_html=True)

    # Evidence chain
    evidence = path.get("input_evidence", [])
    if evidence:
        with ctx.expander(f"📄 Evidence Chain ({len(evidence)} items)", expanded=False):
            for ev in evidence:
                st.markdown(
                    f"**{ev.get('entity_name','?')}** "
                    f"<span style='color:#A8A8A8;font-size:0.75rem'>({ev.get('entity_id','?')})</span>",
                    unsafe_allow_html=True,
                )
                _confidence_bar("confidence", ev.get("confidence", 0.0))
                st.markdown(
                    f"<span style='color:#8B8B8B;font-size:0.72rem;font-style:italic'>"
                    f"{ev.get('context','')[:100]}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown("---")

    # Inference steps timeline
    steps = path.get("inference_steps", [])
    if steps:
        with ctx.expander(f"🔬 Inference Steps ({len(steps)} steps)", expanded=False):
            for step in steps:
                st.markdown(
                    f"**Step {step.get('step_num','?')}** "
                    f"— <span style='color:#D4AF37;font-size:0.75rem'>"
                    f"{step.get('reasoning_type','?')}</span>",
                    unsafe_allow_html=True,
                )
                _confidence_bar("confidence", step.get("confidence_score", 0.0))
                response = step.get("llm_response", "")
                if response:
                    st.markdown(
                        f"<span style='color:#A8A8A8;font-size:0.75rem;font-style:italic'>"
                        f"{response[:120]}</span>",
                        unsafe_allow_html=True,
                    )
                st.markdown("---")

    # Graph changes
    changes = path.get("graph_changes", [])
    if changes:
        with ctx.expander(f"🕸️ Graph Changes ({len(changes)} mutations)", expanded=False):
            for ch in changes:
                change_icon = {
                    "node_created": "🟢",
                    "edge_created": "🔵",
                    "contradicts_edge_created": "🔴",
                }.get(ch.get("change_type", ""), "⚪")
                st.markdown(
                    f"{change_icon} **{ch.get('change_type','?')}**<br>"
                    f"<span style='color:#A8A8A8;font-size:0.75rem'>"
                    f"{ch.get('entity_id','?')} → {ch.get('target_entity_id','?')} "
                    f"[{ch.get('relationship_type','?')}]</span>",
                    unsafe_allow_html=True,
                )
                props = ch.get("properties", {})
                if props:
                    for k, v in props.items():
                        st.markdown(
                            f"<span style='color:#8B8B8B;font-size:0.72rem'>{k}: {v}</span>",
                            unsafe_allow_html=True,
                        )
                st.markdown("---")

    ctx.markdown(
        "<hr style='border-color:#2D333B;margin:12px 0'/>",
        unsafe_allow_html=True,
    )


def _render_probability_tree(tree: Dict[str, Any], ctx) -> None:
    """Render the ProbabilityTree section."""
    ctx.markdown(
        "<h5 style='color:#F0F0F0;font-size:0.85rem;font-weight:600;"
        "letter-spacing:1px;margin:8px 0 4px 0;'>🌳 Probability Tree</h5>",
        unsafe_allow_html=True,
    )

    branches: List[Dict[str, Any]] = tree.get("interpretation_branches", [])
    selected_id = tree.get("selected_branch", 1)
    summary = tree.get("reasoning_summary", "")

    if summary:
        ctx.markdown(
            f"<span style='color:#8B8B8B;font-size:0.75rem;font-style:italic'>{summary}</span>",
            unsafe_allow_html=True,
        )
        ctx.markdown("<div style='margin:4px 0'/>", unsafe_allow_html=True)

    for branch in branches:
        bid = branch.get("branch_id", 0)
        is_selected = bid == selected_id
        weight = branch.get("weight", 0.0)
        conf = branch.get("confidence", 0.0)
        interpretation = branch.get("interpretation", "—")

        border = "2px solid #D4AF37" if is_selected else "1px solid #2D333B"
        selected_label = " ✓ Selected" if is_selected else ""

        with ctx.expander(
            f"Branch {bid}: {int(weight * 100)}% weight{selected_label}",
            expanded=is_selected,
        ):
            st.markdown(
                f"<span style='color:#F0F0F0;font-size:0.8rem'>{interpretation}</span>",
                unsafe_allow_html=True,
            )
            st.markdown("<div style='margin:4px 0'/>", unsafe_allow_html=True)
            _confidence_bar("confidence", conf)

            raw_w = branch.get("calculated_weight", 0.0)
            src_rel = branch.get("source_reliability", 0.0)
            st.markdown(
                f"<span style='color:#8B8B8B;font-size:0.72rem'>"
                f"calc_weight = {conf:.2f} × {src_rel:.2f} = {raw_w:.3f}<br>"
                f"normalised weight = {weight:.3f}</span>",
                unsafe_allow_html=True,
            )

            facts: List[Dict[str, Any]] = branch.get("extracted_facts", [])
            if facts:
                st.markdown(
                    "<span style='color:#A8A8A8;font-size:0.75rem'>Extracted facts:</span>",
                    unsafe_allow_html=True,
                )
                for fact in facts:
                    from_e = fact.get("from", "?")
                    to_e = fact.get("to", "?")
                    rel = fact.get("type", "?")
                    score_key = (
                        "causality_score" if "causality_score" in fact else "conflict_confidence"
                    )
                    score_val = fact.get(score_key, "—")
                    st.markdown(
                        f"<code style='font-size:0.7rem'>{from_e} →[{rel}]→ {to_e} "
                        f"({score_key}={score_val})</code>",
                        unsafe_allow_html=True,
                    )

    total_prob = tree.get("total_probability", 1.0)
    ctx.markdown(
        f"<span style='color:#8B8B8B;font-size:0.72rem'>Σ weights = {total_prob:.4f}</span>",
        unsafe_allow_html=True,
    )
