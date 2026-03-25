"""
Ontological Panel – EL-DRUIN Intelligence Platform
===================================================

Renders the "🏛️ Ontological Significance" section in the right-side
information panel of the Knowledge Graph page.

The panel displays:
  1. Colored badge — ontology class + philosophical meaning
  2. LLM-generated semantic explanation
  3. List of connected entity types

Usage::

    from components.ontological_panel import render_ontological_significance

    render_ontological_significance(
        entity={"name": "Federal Reserve", "type": "ORG", ...},
        connected_entities=[...],
        api_client=_api,   # optional – used to call the backend explainer
    )
"""

from __future__ import annotations

import sys
import os
from typing import Any, Dict, List, Optional

import streamlit as st

# Ensure frontend package root is importable
_FRONTEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FRONTEND_DIR not in sys.path:
    sys.path.insert(0, _FRONTEND_DIR)

from utils.ontology_colors import (
    get_node_color,
    get_ontology_meaning,
    get_canonical_class,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _badge_html(ontology_class: str) -> str:
    """Return HTML for a colored ontology-class badge."""
    color = get_node_color(ontology_class)
    label = get_canonical_class(ontology_class)
    return (
        f'<span style="'
        f"background:{color}33; "  # color + 20% alpha
        f"border:1px solid {color}; "
        f"color:{color}; "
        f"padding:3px 10px; "
        f"border-radius:12px; "
        f'font-size:0.8rem; font-weight:700;">'
        f"{label}</span>"
    )


def _significance_box(color: str, content_html: str) -> str:
    """Wrap *content_html* in the styled significance container."""
    return (
        f'<div style="'
        f"background:{color}22; "
        f"border-left:4px solid {color}; "
        f"padding:12px; "
        f"border-radius:4px; "
        f'margin-top:8px;">'
        f"{content_html}"
        f"</div>"
    )


def _get_explanation_from_backend(
    entity: Dict[str, Any],
    connected: List[Dict[str, Any]],
    api_client: Any,
) -> str:
    """Try to fetch the ontological explanation via the backend API."""
    try:
        payload = {
            "entity": entity,
            "connected_entities": connected,
        }
        resp = api_client._post("/knowledge/ontological-explanation", json=payload)
        if isinstance(resp, dict) and "explanation" in resp:
            return resp["explanation"]
    except Exception:  # noqa: BLE001
        pass
    return ""


def _get_explanation_direct(
    entity: Dict[str, Any],
    connected: List[Dict[str, Any]],
) -> str:
    """Try to generate explanation directly via backend intelligence module."""
    try:
        # Try importing from backend if running in a context where it is available
        _backend_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "backend",
        )
        if _backend_dir not in sys.path:
            sys.path.insert(0, _backend_dir)
        from intelligence.semantic_explainer import (  # type: ignore[import]
            generate_ontological_explanation,
        )
        return generate_ontological_explanation(entity, connected)
    except Exception:  # noqa: BLE001
        pass
    return ""


def _static_explanation(entity: Dict[str, Any]) -> str:
    """Return a static fallback explanation."""
    name = entity.get("name", "This entity")
    etype = get_canonical_class(entity.get("ontology_class") or entity.get("type", "entity"))
    return (
        f"{name} stands as a **{etype}** within the knowledge graph — "
        "a node whose connections define its significance in the larger order. "
        "Each relationship is a thread of meaning, binding it to other entities "
        "through influence, causality, or shared context. "
        "Its ontological essence emerges from these patterns of connection."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_ontological_significance(
    entity: Dict[str, Any],
    connected_entities: Optional[List[Dict[str, Any]]] = None,
    api_client: Optional[Any] = None,
    degree: int = 0,
) -> None:
    """Render the 🏛️ Ontological Significance panel for *entity*.

    Args:
        entity: Entity dict with at least ``"name"`` and ``"type"``/
            ``"ontology_class"`` keys.
        connected_entities: List of dicts with ``"name"``, ``"type"``,
            ``"relationship"`` keys.
        api_client: Optional :class:`~utils.api_client.APIClient` instance.
            When supplied, the LLM explanation is fetched via the backend API.
            Falls back to a direct import of the backend module if absent.
        degree: Number of connections for this entity.
    """
    if connected_entities is None:
        connected_entities = []

    onto_class = entity.get("ontology_class") or entity.get("type", "misc")
    color = get_node_color(onto_class)
    meaning = get_ontology_meaning(onto_class)

    st.markdown("#### 🏛️ Ontological Significance")

    # ── 1. Colored class badge + meaning ─────────────────────────────────
    badge = _badge_html(onto_class)
    meaning_html = (
        f"{badge}<br/>"
        f'<span style="color:#A8A8A8;font-size:0.82rem;margin-top:4px;display:block;">'
        f"{meaning}"
        f"</span>"
    )
    st.markdown(_significance_box(color, meaning_html), unsafe_allow_html=True)

    # ── 2. LLM-generated semantic explanation ────────────────────────────
    st.markdown(
        '<span style="color:#D4AF37;font-size:0.85rem;font-weight:600;">📜 Semantic Explanation</span>',
        unsafe_allow_html=True,
    )

    cache_key = f"onto_expl_{entity.get('name', '')}_{degree}"
    if cache_key not in st.session_state:
        with st.spinner("Generating ontological explanation…"):
            explanation = ""
            if api_client is not None:
                explanation = _get_explanation_from_backend(entity, connected_entities, api_client)
            if not explanation:
                explanation = _get_explanation_direct(entity, connected_entities)
            if not explanation:
                explanation = _static_explanation(entity)
        st.session_state[cache_key] = explanation

    explanation_text = st.session_state[cache_key]
    st.markdown(
        _significance_box(
            color,
            f'<span style="color:#E0E0E0;font-size:0.85rem;line-height:1.5;">'
            f"{explanation_text}"
            f"</span>",
        ),
        unsafe_allow_html=True,
    )

    # ── 3. Connected entity types ─────────────────────────────────────────
    if connected_entities:
        st.markdown(
            '<span style="color:#D4AF37;font-size:0.85rem;font-weight:600;">🔗 Connected Classes</span>',
            unsafe_allow_html=True,
        )

        # Group connections by type/class
        class_counts: Dict[str, int] = {}
        for conn in connected_entities:
            conn_class = get_canonical_class(
                conn.get("ontology_class") or conn.get("type", "misc")
            )
            class_counts[conn_class] = class_counts.get(conn_class, 0) + 1

        badges_html = " ".join(
            f'<span style="'
            f"background:{get_node_color(cls)}22; "
            f"border:1px solid {get_node_color(cls)}; "
            f"color:{get_node_color(cls)}; "
            f"padding:2px 8px; border-radius:8px; "
            f'font-size:0.75rem; margin-right:4px;">'
            f"{cls} ×{count}"
            f"</span>"
            for cls, count in sorted(class_counts.items(), key=lambda x: -x[1])
        )
        st.markdown(
            _significance_box(color, badges_html),
            unsafe_allow_html=True,
        )
