"""
Object Inspector — EL-DRUIN Intelligence Platform
==================================================

Renders the semi-transparent right-panel 'Object Inspector' in the
Light Blue Rational (Ratio Lucis) aesthetic.

Sections rendered:
  1. Entity Identity  — icon, name, type badge, last-updated, confidence
  2. Core Properties  — borderless property table
  3. Linked Evidences — vertical timeline of source articles with timestamps

Usage::

    from components.object_inspector import render_object_inspector

    render_object_inspector(
        entity={"name": "John Smith", "type": "Person", "confidence": 0.92, ...},
        source_refs=[{"source": "Reuters", "title": "...", "timestamp": "..."}],
    )
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

# ---------------------------------------------------------------------------
# Type-icon mapping (unicode symbols for common ontology classes)
# ---------------------------------------------------------------------------
_TYPE_ICONS: Dict[str, str] = {
    "person":       "👤",
    "organization": "🏢",
    "location":     "📍",
    "event":        "⚡",
    "concept":      "💡",
    "article":      "📰",
    "misc":         "◇",
}
_DEFAULT_ICON = "◇"

# Risk-level colour coding
_RISK_COLORS: Dict[str, str] = {
    "critical": "#e74c3c",
    "high":     "#f39c12",
    "medium":   "#2E86AB",
    "low":      "#27ae60",
    "unknown":  "#A0A0A0",
}


def _get_type_icon(entity_type: str) -> str:
    """Return a unicode icon for *entity_type* (case-insensitive)."""
    return _TYPE_ICONS.get(entity_type.lower(), _DEFAULT_ICON)


def _risk_badge(risk_level: str) -> str:
    """Return an inline HTML badge for a risk level string."""
    color = _RISK_COLORS.get(risk_level.lower(), _RISK_COLORS["unknown"])
    label = risk_level.upper() if risk_level else "—"
    # Use dark text on lighter backgrounds (low=green, medium=amber)
    text_color = "#FFFFFF" if risk_level.lower() in ("high", "critical", "unknown") else "#333333"
    return (
        f"<span style='background:{color};color:{text_color};border-radius:4px;"
        f"padding:2px 8px;font-size:0.72rem;font-weight:700;'>{label}</span>"
    )


def render_object_inspector(
    entity: Optional[Dict[str, Any]],
    source_refs: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Render the Object Inspector panel.

    Displays three sections:
      1. **Entity Identity** — icon, name, type badge, last updated, confidence
      2. **Core Properties** — borderless table of arbitrary entity properties
      3. **Linked Evidences Timeline** — vertical timeline of source articles

    Args:
        entity:      Entity dict containing at minimum ``name`` and ``type``.
                     Optional keys: ``confidence``, ``risk_level``,
                     ``last_updated``, ``order_score``, ``influence_score``,
                     ``data_quality``, plus any additional properties.
        source_refs: List of source-reference dicts, each with optional keys
                     ``timestamp``, ``source``, ``title``, ``url``.
                     Defaults to an empty list when ``None``.
    """
    source_refs = source_refs or []

    if not entity:
        st.markdown(
            "<div style='color:#606060;font-size:0.9rem;padding:16px 0;text-align:center;'>"
            "Select an entity to inspect.</div>",
            unsafe_allow_html=True,
        )
        return

    # ── 1. Entity Identity ────────────────────────────────────────────────
    entity_name = entity.get("name", "Unknown")
    entity_type = entity.get("type", entity.get("ontology_class", "misc"))
    confidence  = float(entity.get("confidence", entity.get("order_score", 0)) or 0)
    risk_level  = str(entity.get("risk_level", "unknown")).lower()
    last_updated = entity.get("last_updated", entity.get("updated_at", ""))
    icon = _get_type_icon(entity_type)
    conf_pct = f"{confidence:.0%}" if confidence <= 1.0 else f"{confidence:.0f}"

    # Type badge
    type_badge = (
        f"<span style='background:rgba(0,71,171,0.1);color:#0047AB;"
        f"border-radius:4px;padding:2px 8px;font-size:0.75rem;font-weight:600;"
        f"margin-left:6px;'>{entity_type.title()}</span>"
    )
    ts_html = (
        f"<span style='color:#A0A0A0;font-size:0.75rem;margin-left:8px;'>"
        f"⏱ {str(last_updated)[:16]}</span>"
        if last_updated else ""
    )

    st.markdown(
        f"""
        <div style='background:rgba(255,255,255,0.95);border:1px solid #E0E0E0;
                    border-radius:4px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,0.05);
                    margin-bottom:12px;'>
          <div style='display:flex;align-items:center;gap:8px;margin-bottom:4px;'>
            <span style='font-size:1.5rem;'>{icon}</span>
            <span style='font-size:1.15rem;font-weight:600;color:#0047AB;'>{entity_name}</span>
            {type_badge}
            {ts_html}
          </div>
          <div style='display:flex;align-items:center;gap:12px;margin-top:8px;'>
            <span style='font-size:0.82rem;color:#606060;'>
              Confidence:
              <span style='color:#0047AB;font-weight:700;'>{conf_pct}</span>
            </span>
            {_risk_badge(risk_level)}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── 2. Core Properties ────────────────────────────────────────────────
    _SKIP_KEYS = {
        "name", "type", "ontology_class", "confidence", "risk_level",
        "last_updated", "updated_at", "property_history", "source_refs",
    }
    core_props = {k: v for k, v in entity.items() if k not in _SKIP_KEYS and v is not None}

    if core_props:
        with st.expander("📋 Core Properties", expanded=True):
            for prop_name, prop_value in list(core_props.items())[:12]:
                col_label, col_val = st.columns([2, 3])
                col_label.markdown(
                    f"<span style='color:#606060;font-size:0.82rem;'>{prop_name}</span>",
                    unsafe_allow_html=True,
                )
                # Numerical values rendered in cobalt blue
                if isinstance(prop_value, (int, float)):
                    col_val.markdown(
                        f"<span style='color:#0047AB;font-weight:600;font-size:0.85rem;'>"
                        f"{prop_value}</span>",
                        unsafe_allow_html=True,
                    )
                else:
                    col_val.markdown(
                        f"<span style='color:#333333;font-size:0.85rem;'>"
                        f"{str(prop_value)[:80]}</span>",
                        unsafe_allow_html=True,
                    )

    # ── 3. Linked Evidences Timeline ──────────────────────────────────────
    if source_refs:
        with st.expander("📎 Linked Evidences", expanded=True):
            for ref in source_refs[:8]:
                timestamp  = str(ref.get("timestamp", ref.get("published", "")))[:16]
                source     = ref.get("source", ref.get("source_name", "Unknown"))
                title      = ref.get("title", ref.get("snippet", "—"))
                url        = ref.get("url", ref.get("link", ""))
                conf_score = float(ref.get("confidence", ref.get("source_reliability", 0)) or 0)

                title_html = (
                    f"<a href='{url}' target='_blank' "
                    f"style='color:#0047AB;text-decoration:none;font-size:0.82rem;'>"
                    f"{title[:80]}{'…' if len(str(title)) > 80 else ''}</a>"
                    if url
                    else f"<span style='color:#333333;font-size:0.82rem;'>"
                         f"{str(title)[:80]}</span>"
                )
                conf_html = (
                    f" <span style='color:#0047AB;font-size:0.72rem;font-weight:600;'>"
                    f"({conf_score:.0%})</span>"
                    if conf_score > 0 else ""
                )

                st.markdown(
                    f"""
                    <div style='border-left:2px solid #E0E0E0;padding:4px 0 4px 12px;
                                margin-bottom:8px;position:relative;'>
                      <div style='position:absolute;left:-5px;top:8px;width:8px;height:8px;
                                  border-radius:50%;background:#0047AB;'></div>
                      <div style='color:#A0A0A0;font-size:0.72rem;'>
                        {("⏱ " + timestamp) if timestamp else ""}
                        {(" · " + source) if source else ""}
                        {conf_html}
                      </div>
                      <div style='margin-top:2px;'>{title_html}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    if not source_refs and not core_props:
        st.markdown(
            "<p style='color:#A0A0A0;font-size:0.82rem;'>No additional data available.</p>",
            unsafe_allow_html=True,
        )
