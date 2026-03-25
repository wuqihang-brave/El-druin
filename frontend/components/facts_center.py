"""
EL'druin Intelligence Platform – Facts Center Component
=======================================================

Renders the left-hand 60 % Facts column on the Truth Monitor home page.

Features:
  - Top-5 structural news cards
  - Three-layer ontological entity tags per card (Layer 1 type / Layer 2 role /
    Layer 3 virtue) rendered with a Cobalt-Blue left border
  - Link to full analysis for each article
"""

from __future__ import annotations

from typing import Any, Dict, List


import streamlit as st


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_SUMMARY_LENGTH = 250  # Characters to display before truncating summary text


# ---------------------------------------------------------------------------
# Entity tag renderer
# ---------------------------------------------------------------------------

def render_entity_tag(entity: Dict[str, Any]) -> None:
    """Render a minimalist three-layer entity tag.

    Expected keys: ``name``, ``layer1``, ``layer2``, ``layer3``.
    Any missing key is substituted with a dash.
    """
    name = entity.get("name", "—")
    layer1 = entity.get("layer1") or entity.get("type", "—")
    layer2 = entity.get("layer2") or entity.get("role", "—")
    layer3 = entity.get("layer3") or entity.get("virtue", "—")

    st.markdown(
        f"""
        <div style='
            background: #FFFFFF;
            border-left: 4px solid #0047AB;
            border-radius: 2px;
            padding: 10px 12px;
            font-size: 11px;
            line-height: 1.6;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            margin-bottom: 6px;
        '>
        <b style="color: #0047AB;">{name}</b><br/>
        <span style="color: #606060;">📍 {layer1}</span><br/>
        <span style="color: #0047AB;">⚔️ {layer2}</span><br/>
        <span style="color: #8B4513;">💎 {layer3}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# News card renderer
# ---------------------------------------------------------------------------

def render_news_card_with_entities(news: Dict[str, Any], idx: int) -> None:
    """Render a single news card with three-layer entity tags.

    Args:
        news: dict with keys ``title``, ``source``, ``date``, ``summary``,
              ``link``, and optional ``entities`` list.
        idx:  1-based card index used for display numbering.
    """
    title = news.get("title", "—")
    source = news.get("source") or news.get("publisher") or "Unknown"
    date_str = news.get("date") or news.get("published_at") or ""
    summary = news.get("summary") or news.get("description") or ""
    link = news.get("link") or news.get("url") or "#"
    entities: List[Dict[str, Any]] = news.get("entities") or []

    # ── Header row ────────────────────────────────────────────────────────
    col_title, col_date = st.columns([4, 1])
    with col_title:
        st.markdown(f"**{idx}. {title}**")
    with col_date:
        if date_str:
            st.caption(f"📅 {date_str[:10]}")

    st.caption(f"📰 {source}")

    # ── Summary ───────────────────────────────────────────────────────────
    if summary:
        display_summary = summary[:_MAX_SUMMARY_LENGTH] + "…" if len(summary) > _MAX_SUMMARY_LENGTH else summary
        st.markdown(display_summary)

    # ── Entity tags ───────────────────────────────────────────────────────
    if entities:
        st.markdown("**🏷️ Key Entities:**")
        entity_slice = entities[:3]
        entity_cols = st.columns(len(entity_slice))
        for col_idx, entity in enumerate(entity_slice):
            with entity_cols[col_idx]:
                render_entity_tag(entity)

    # ── Link ──────────────────────────────────────────────────────────────
    st.markdown(f"[🔗 View full analysis →]({link})")


# ---------------------------------------------------------------------------
# Top-level Facts Center renderer
# ---------------------------------------------------------------------------

def render_facts_center(top_5_news: List[Dict[str, Any]]) -> None:
    """Render the Facts Center column.

    Args:
        top_5_news: list of up to 5 news dicts (see ``render_news_card_with_entities``
                    for expected shape).
    """
    st.subheader("📰 Top 5 Structural News")

    if not top_5_news:
        st.info("▶ 点击「🧠 Ingest Intelligence」以加载最新结构性新闻。")
        return

    for idx, news in enumerate(top_5_news[:5], 1):
        render_news_card_with_entities(news, idx)
        if idx < min(5, len(top_5_news)):
            st.divider()
