"""
Proof Panel – Streamlit component.

Displays a side panel showing all supporting source articles for a selected
relationship edge or entity.  Each article shows its title, URL, snippet
(highlighted by extraction confidence), and the extraction timestamp.

Usage::

    from components.proof_panel import render_proof_panel

    render_proof_panel(source_refs, title="Relationship Provenance")
"""

from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st


def _confidence_color(confidence: float) -> str:
    """Return a CSS color string that reflects the confidence level."""
    if confidence >= 0.85:
        return "#D4AF37"   # Gold – high confidence
    if confidence >= 0.65:
        return "#A8A8A8"   # Silver – medium confidence
    return "#E0E0E0"       # Cold white – low confidence


def render_proof_panel(
    source_refs: List[Dict[str, Any]],
    title: str = "📄 Source Provenance",
) -> None:
    """Render a proof panel showing supporting articles for a relationship.

    Parameters
    ----------
    source_refs:
        List of source reference dicts. Each may contain:
        ``article_hash``, ``article_title``, ``article_url``, ``snippet``,
        ``source_reliability``, ``extraction_confidence``, ``snippet_start_char``,
        ``snippet_end_char``.
    title:
        Panel heading.
    """
    st.markdown(f"#### {title}")

    if not source_refs:
        st.info("No source references available for this relationship.")
        return

    st.caption(f"{len(source_refs)} supporting source(s)")

    for idx, ref in enumerate(source_refs, start=1):
        article_title = ref.get("article_title") or ref.get("title") or f"Source {idx}"
        article_url = ref.get("article_url") or ref.get("url") or ""
        snippet = ref.get("snippet") or ""
        confidence = float(ref.get("extraction_confidence", ref.get("confidence", 0.7)))
        reliability = float(ref.get("source_reliability", ref.get("reliability", 0.7)))
        article_hash = ref.get("article_hash", "")
        timestamp = ref.get("timestamp", ref.get("extracted_at", ""))

        color = _confidence_color(confidence)

        with st.expander(f"[{idx}] {article_title}", expanded=(idx == 1)):
            # Metadata row
            cols = st.columns([2, 2, 2])
            cols[0].metric("Extraction Confidence", f"{confidence:.0%}")
            cols[1].metric("Source Reliability", f"{reliability:.0%}")
            if article_hash:
                cols[2].caption(f"Hash: `{article_hash[:12]}…`")

            # Snippet
            if snippet:
                st.markdown(
                    f'<div style="border-left: 3px solid {color}; padding: 8px 12px; '
                    f'margin: 8px 0; background: #1A1A1A; border-radius: 0 4px 4px 0;">'
                    f'<em style="color: {color}; font-size: 0.85rem;">{snippet}</em>'
                    f"</div>",
                    unsafe_allow_html=True,
                )

            # Footer row
            footer_cols = st.columns([3, 1])
            if article_url:
                footer_cols[0].markdown(f"[🔗 Open Original Source]({article_url})")
            if timestamp:
                footer_cols[1].caption(f"Extracted: {timestamp}")
