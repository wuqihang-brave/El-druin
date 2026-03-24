"""
Faceted Search Panel – Streamlit component.

Renders the left-column Entity Explorer panel with type filters, confidence
slider, date range, risk level buttons, data source multiselect, and a
free-text name search.

Usage::

    from components.faceted_search import render_faceted_search

    selected_entity = render_faceted_search(entities)
    # Returns the selected entity dict, or None.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import streamlit as st

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ENTITY_TYPES = ["All", "Person", "Organization", "Location", "Event", "Concept"]
_RISK_LEVELS = ["All", "Low", "Medium", "High", "Critical"]
_DATA_SOURCES = ["Reuters", "Bloomberg", "User Input", "LLM Inference", "Other"]

_RISK_COLORS: Dict[str, str] = {
    "low": "#4CAF50",
    "medium": "#FFC107",
    "high": "#FF5722",
    "critical": "#F44336",
    "all": "#D4AF37",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_updated_at(ts_str: str) -> Optional[datetime]:
    """Parse ISO-8601 or fallback timestamp string to a datetime."""
    if not ts_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(ts_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def _matches_time_filter(entity: Dict[str, Any], time_filter: str) -> bool:
    """Return True if the entity was updated within the selected time window."""
    if time_filter == "All time":
        return True

    ts_str = entity.get("updated_at", entity.get("timestamp", ""))
    updated = _parse_updated_at(str(ts_str)) if ts_str else None

    if updated is None:
        return True  # Can't filter what we don't know

    now = datetime.now(tz=timezone.utc)
    windows = {
        "Last 1h": timedelta(hours=1),
        "Last 24h": timedelta(hours=24),
        "Last 7d": timedelta(days=7),
    }
    delta = windows.get(time_filter)
    if delta is None:
        return True
    return updated >= (now - delta)


def _confidence_bar(score: float) -> str:
    """Return an inline HTML mini progress bar for a confidence score."""
    pct = int(score * 100)
    color = "#D4AF37" if score >= 0.85 else "#A8A8A8" if score >= 0.65 else "#E0E0E0"
    return (
        f'<div style="background:#30363D; border-radius:2px; height:4px; width:80px;">'
        f'<div style="background:{color}; width:{pct}%; height:4px; border-radius:2px;"></div>'
        f"</div>"
    )


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------


def render_faceted_search(
    entities: List[Dict[str, Any]],
    key_prefix: str = "faceted",
) -> Optional[Dict[str, Any]]:
    """Render the Entity Explorer faceted search panel.

    Parameters
    ----------
    entities:
        List of entity dicts from the knowledge graph.
    key_prefix:
        Prefix added to all widget keys (allows multiple instances on one page).

    Returns
    -------
    Optional[Dict[str, Any]]
        The entity dict that was clicked/selected, or ``None`` if nothing is
        selected.
    """
    st.markdown("### 🔍 Entity Explorer")

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------
    entity_type = st.selectbox(
        "Entity Type",
        options=_ENTITY_TYPES,
        key=f"{key_prefix}_type",
    )

    conf_range = st.slider(
        "Confidence Range",
        min_value=0.0,
        max_value=1.0,
        value=(0.0, 1.0),
        step=0.05,
        key=f"{key_prefix}_conf",
    )

    time_filter = st.selectbox(
        "Last Updated",
        options=["All time", "Last 1h", "Last 24h", "Last 7d"],
        key=f"{key_prefix}_time",
    )

    # Risk level buttons (horizontal)
    st.markdown("**Risk Level**")
    risk_cols = st.columns(len(_RISK_LEVELS))
    selected_risk: str = st.session_state.get(f"{key_prefix}_risk", "All")
    for i, level in enumerate(_RISK_LEVELS):
        color = _RISK_COLORS.get(level.lower(), "#D4AF37")
        if risk_cols[i].button(
            level,
            key=f"{key_prefix}_risk_{level}",
            use_container_width=True,
            type="primary" if selected_risk == level else "secondary",
        ):
            selected_risk = level
            st.session_state[f"{key_prefix}_risk"] = level

    data_sources = st.multiselect(
        "Data Source",
        options=_DATA_SOURCES,
        default=[],
        key=f"{key_prefix}_sources",
    )

    name_query = st.text_input(
        "🔎 Search entities…",
        value="",
        key=f"{key_prefix}_search",
    )

    # ------------------------------------------------------------------
    # Apply filters
    # ------------------------------------------------------------------
    filtered: List[Dict[str, Any]] = []
    for ent in entities:
        ent_type = ent.get("type", ent.get("entity_type", ""))
        if entity_type != "All" and ent_type.lower() != entity_type.lower():
            continue

        conf = float(ent.get("confidence", ent.get("source_reliability", 0.5)))
        if not (conf_range[0] <= conf <= conf_range[1]):
            continue

        risk = str(ent.get("risk_level", "")).lower()
        if selected_risk != "All" and risk != selected_risk.lower():
            continue

        if not _matches_time_filter(ent, time_filter):
            continue

        if name_query and name_query.lower() not in ent.get("name", "").lower():
            continue

        filtered.append(ent)

    st.caption(f"**{len(filtered)}** entities match filters")

    # ------------------------------------------------------------------
    # Results list
    # ------------------------------------------------------------------
    selected: Optional[Dict[str, Any]] = None
    current_selection = st.session_state.get(f"{key_prefix}_selected_name", "")

    for ent in filtered[:50]:  # Show max 50 to avoid UI overload
        ent_name = ent.get("name", "?")
        ent_type = ent.get("type", "MISC").upper()
        conf = float(ent.get("confidence", ent.get("source_reliability", 0.5)))
        updated = ent.get("updated_at", ent.get("timestamp", ""))

        is_selected = ent_name == current_selection
        bg_color = "#1E2A1E" if is_selected else "#1A1A1A"
        border_color = "#D4AF37" if is_selected else "#30363D"

        col_btn, col_meta = st.columns([3, 1])
        with col_btn:
            if st.button(
                f"**{ent_name}** `{ent_type}`",
                key=f"{key_prefix}_btn_{ent_name}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                st.session_state[f"{key_prefix}_selected_name"] = ent_name
                selected = ent

        with col_meta:
            st.markdown(
                _confidence_bar(conf),
                unsafe_allow_html=True,
            )
            if updated:
                st.caption(str(updated)[:16])

    # Return the previously selected entity if the button was not just clicked.
    if selected is None and current_selection:
        for ent in filtered:
            if ent.get("name") == current_selection:
                selected = ent
                break

    return selected
