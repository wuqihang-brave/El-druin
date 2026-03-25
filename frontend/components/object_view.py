"""
Object View – Streamlit component (Palantir Maven-style).

Renders a detailed entity profile panel with:
  - Entity identity (icon, name, type badge, last updated)
  - Key metrics grid (Order Index, Risk Level, Influence Score, Data Quality)
  - Relationships summary (outgoing / incoming count)
  - Recent activity timeline (property changes with sources)
  - Property history chart (Plotly line chart, if available)

Usage::

    from components.object_view import render_object_view

    render_object_view(entity, outgoing=[], incoming=[])
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

try:
    import plotly.graph_objects as go

    _PLOTLY = True
except ImportError:
    _PLOTLY = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ENTITY_ICONS: Dict[str, str] = {
    "person": "👤",
    "organization": "🏛️",
    "location": "📍",
    "event": "⚡",
    "concept": "💡",
    "org": "🏛️",
    "gpe": "🗺️",
    "misc": "🔷",
}

_RISK_COLORS: Dict[str, str] = {
    "low": "#4CAF50",
    "medium": "#FFC107",
    "high": "#FF5722",
    "critical": "#F44336",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entity_icon(entity_type: str) -> str:
    return _ENTITY_ICONS.get(entity_type.lower(), "🔷")


def _risk_badge(risk_level: str) -> str:
    color = _RISK_COLORS.get(risk_level.lower(), "#A0A0A0")
    label = risk_level.upper()
    # Use dark text on lighter backgrounds (low=green, medium=amber)
    text_color = "#FFFFFF" if risk_level.lower() in ("high", "critical", "unknown") else "#333333"
    return (
        f'<span style="background:{color}; color:{text_color}; padding:2px 8px; '
        f'border-radius:4px; font-size:0.75rem; font-weight:700;">{label}</span>'
    )


def _type_badge(entity_type: str) -> str:
    return (
        f'<span style="background:rgba(0,71,171,0.1); color:#0047AB; padding:2px 8px; '
        f'border-radius:4px; font-size:0.75rem; font-weight:600;">'
        f"{entity_type.upper()}</span>"
    )


def _format_change(old_val: Any, new_val: Any) -> str:
    """Format an old→new value pair for display."""
    if old_val is None:
        return f"→ {new_val}"
    return f"{old_val} → {new_val}"


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------


def render_object_view(
    entity: Dict[str, Any],
    outgoing: Optional[List[Dict[str, Any]]] = None,
    incoming: Optional[List[Dict[str, Any]]] = None,
    property_history: Optional[List[Dict[str, Any]]] = None,
    on_relationship_click: Optional[Any] = None,
) -> None:
    """Render the full Palantir Maven-style Object View panel.

    Parameters
    ----------
    entity:
        Entity dict with keys such as ``name``, ``type``, ``order_index``,
        ``risk_level``, ``confidence``, ``updated_at``, etc.
    outgoing:
        List of outgoing relationship dicts.
    incoming:
        List of incoming relationship dicts.
    property_history:
        List of property history entry dicts (from the entity resolver).
    on_relationship_click:
        Optional callable(relationship_dict) triggered when a relationship
        row is clicked.  Not used directly in Streamlit but reserved for
        session_state patterns.
    """
    outgoing = outgoing or []
    incoming = incoming or []
    property_history = property_history or []

    entity_name: str = entity.get("name", "Unknown Entity")
    entity_type: str = entity.get("type", entity.get("entity_type", "MISC"))
    icon = _entity_icon(entity_type)
    updated_at: str = entity.get("updated_at", entity.get("timestamp", ""))

    updated_html = (
        f'&nbsp;&nbsp;<span style="color:#606060; font-size:0.8rem;">Updated: {updated_at}</span>'
        if updated_at
        else ""
    )

    # ------------------------------------------------------------------
    # Section 1: Entity Identity
    # ------------------------------------------------------------------
    st.markdown(
        f'<div style="padding:12px; background:#FFFFFF; border:1px solid #E0E0E0; '
        f'border-radius:4px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.05);">'
        f'<span style="font-size:2rem;">{icon}</span> '
        f'<span style="font-size:1.4rem; font-weight:700; color:#0047AB;">{entity_name}</span>'
        f"<br/>"
        f"{_type_badge(entity_type)}"
        f"{updated_html}"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------
    # Section 2: Key Metrics
    # ------------------------------------------------------------------
    st.markdown("**KEY METRICS**")

    order_index = entity.get("order_index", entity.get("order_score"))
    risk_level: str = str(entity.get("risk_level", "—"))
    influence_score = entity.get("influence_score", entity.get("confidence"))
    data_quality = entity.get("data_quality", entity.get("source_reliability"))

    col1, col2 = st.columns(2)
    with col1:
        if order_index is not None:
            st.metric("Order Index", f"{float(order_index):.0f} / 100")
        if risk_level and risk_level != "—":
            st.markdown(
                f'Risk Level: {_risk_badge(risk_level)}',
                unsafe_allow_html=True,
            )
    with col2:
        if influence_score is not None:
            st.metric("Influence Score", f"{float(influence_score):.2f}")
        if data_quality is not None:
            st.metric("Data Quality", f"{float(data_quality) * 100:.0f}%")

    st.divider()

    # ------------------------------------------------------------------
    # Section 3: Relationships Summary
    # ------------------------------------------------------------------
    st.markdown("**RELATIONSHIPS**")
    rel_col1, rel_col2 = st.columns(2)
    rel_col1.metric("Outgoing →", len(outgoing))
    rel_col2.metric("← Incoming", len(incoming))

    all_rels = outgoing + incoming
    if all_rels:
        with st.expander(f"Show all {len(all_rels)} relationships", expanded=False):
            for rel in all_rels[:20]:
                direction = "→" if rel in outgoing else "←"
                other = rel.get("to_entity" if rel in outgoing else "from_entity", "?")
                rel_type = rel.get("relationship_type", rel.get("relation", "relates_to"))
                conf = rel.get("confidence", rel.get("causality_score", 0.5))
                st.markdown(
                    f"- **{direction}** `{rel_type}` **{other}**"
                    f"&nbsp;_(conf: {float(conf):.0%})_",
                    unsafe_allow_html=False,
                )

    st.divider()

    # ------------------------------------------------------------------
    # Section 4: Recent Activity Timeline
    # ------------------------------------------------------------------
    st.markdown("**RECENT ACTIVITY TIMELINE**")

    if property_history:
        # Sort descending by timestamp.
        sorted_history = sorted(
            property_history,
            key=lambda e: e.get("timestamp", ""),
            reverse=True,
        )
        for entry in sorted_history[:8]:
            ts = entry.get("timestamp", "")
            prop = entry.get("property_name", "?")
            old_v = entry.get("old_value")
            new_v = entry.get("new_value")
            src = entry.get("source_ref", "")
            conf = entry.get("confidence", 1.0)
            conf_color = "#0047AB" if float(conf) >= 0.85 else "#A0A0A0"

            change_str = _format_change(old_v, new_v)
            source_label = f"From: {src}" if src else ""
            source_html = (
                f'<br/><span style="color:#A0A0A0; font-size:0.75rem;">{source_label}</span>'
                if source_label
                else ""
            )

            st.markdown(
                f'<div style="padding:8px; background:#FFFFFF; border-left:2px solid {conf_color}; '
                f'margin-bottom:6px; border-radius:0 4px 4px 0; border:1px solid #E0E0E0;">'
                f'<span style="color:#A0A0A0; font-size:0.75rem;">{ts}</span><br/>'
                f'<strong style="color:#333333;">{prop}</strong>'
                f'<span style="color:{conf_color};"> {change_str}</span>'
                f"{source_html}"
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No property history recorded yet.")

    # ------------------------------------------------------------------
    # Section 5: Property History Chart (Plotly)
    # ------------------------------------------------------------------
    _render_property_chart(property_history)


def _render_property_chart(property_history: List[Dict[str, Any]]) -> None:
    """Render a multi-property Plotly trend chart from history entries."""
    if not property_history:
        return

    # Collect numeric properties only.
    prop_series: Dict[str, List[Any]] = {}
    for entry in property_history:
        prop = entry.get("property_name", "")
        new_v = entry.get("new_value")
        ts = entry.get("timestamp", "")
        if prop.startswith("_") or new_v is None:
            continue
        try:
            numeric = float(new_v)
        except (TypeError, ValueError):
            continue
        if prop not in prop_series:
            prop_series[prop] = []
        prop_series[prop].append({"ts": ts, "value": numeric})

    if not prop_series:
        return

    st.markdown("**PROPERTY HISTORY CHART**")

    if not _PLOTLY:
        st.caption("Install plotly for interactive charts.")
        return

    fig = go.Figure()
    colors = ["#0047AB", "#2E86AB", "#2A9D8F", "#1B6CA8", "#606060"]

    for i, (prop_name, points) in enumerate(prop_series.items()):
        sorted_points = sorted(points, key=lambda p: p["ts"])
        xs = [p["ts"] for p in sorted_points]
        ys = [p["value"] for p in sorted_points]
        color = colors[i % len(colors)]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="lines+markers",
                name=prop_name,
                line={"color": color, "width": 2},
                marker={"size": 6, "color": color},
            )
        )

    fig.update_layout(
        paper_bgcolor="#F0F8FF",
        plot_bgcolor="#F0F8FF",
        font={"color": "#333333", "family": "Inter"},
        legend={"bgcolor": "#FFFFFF", "bordercolor": "#E0E0E0"},
        xaxis={"gridcolor": "#E0E0E0", "linecolor": "#E0E0E0"},
        yaxis={"gridcolor": "#E0E0E0", "linecolor": "#E0E0E0"},
        margin={"l": 40, "r": 20, "t": 20, "b": 40},
        height=220,
    )

    st.plotly_chart(fig, use_container_width=True)
