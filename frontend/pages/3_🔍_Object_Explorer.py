"""
Object Explorer – EL-DRUIN Intelligence Platform
=================================================

Palantir Maven-style 3-column Object Explorer:

  Left  (1): Faceted Search Panel – entity type, confidence, date, risk, source filters
  Middle (3): Knowledge Graph Visualisation – dark-themed, Agraph or Plotly fallback
  Right  (2): Object View – entity metrics, relationships, timeline, property chart

Run via the Streamlit multi-page app (frontend/app.py).
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional

import streamlit as st

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_FRONTEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FRONTEND_DIR not in sys.path:
    sys.path.insert(0, _FRONTEND_DIR)

from utils.api_client import APIClient  # noqa: E402
from components.faceted_search import render_faceted_search  # noqa: E402
from components.object_view import render_object_view  # noqa: E402
from components.proof_panel import render_proof_panel  # noqa: E402

try:
    from streamlit_agraph import agraph, Config, Edge, Node  # type: ignore[import]
    _AGRAPH = True
except ImportError:
    _AGRAPH = False

try:
    import plotly.graph_objects as go
    import networkx as nx  # type: ignore[import]
    _PLOTLY = True
except ImportError:
    _PLOTLY = False
    nx = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Object Explorer – EL-DRUIN",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# CSS injection
# ---------------------------------------------------------------------------
_CSS_PATH = os.path.join(_FRONTEND_DIR, "assets", "custom_styles.css")
try:
    with open(_CSS_PATH, encoding="utf-8") as _f:
        st.markdown(f"<style>{_f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    pass

# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------
_backend_url = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api/v1"
_api = APIClient(base_url=_backend_url)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "oe_selected_entity" not in st.session_state:
    st.session_state.oe_selected_entity: Optional[Dict[str, Any]] = None
if "oe_proof_rel_id" not in st.session_state:
    st.session_state.oe_proof_rel_id: Optional[str] = None
if "oe_show_proof" not in st.session_state:
    st.session_state.oe_show_proof: bool = False

# ---------------------------------------------------------------------------
# Page title
# ---------------------------------------------------------------------------
st.markdown(
    '<h2 style="color:#D4AF37; font-weight:300; letter-spacing:3px;">🔍 OBJECT EXPLORER</h2>',
    unsafe_allow_html=True,
)
st.markdown(
    '<p style="color:#A8A8A8; font-size:0.9rem; margin-top:-12px;">'
    "Ontology-centric entity search, graph navigation, and object profiling."
    "</p>",
    unsafe_allow_html=True,
)
st.divider()

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


@st.cache_data(ttl=60, show_spinner=False)
def _load_entities() -> List[Dict[str, Any]]:
    resp = _api.get_kg_entities(limit=500)
    return resp.get("entities", []) if isinstance(resp, dict) else []


@st.cache_data(ttl=60, show_spinner=False)
def _load_relations() -> List[Dict[str, Any]]:
    resp = _api.get_kg_relations(limit=1000)
    return resp.get("relations", []) if isinstance(resp, dict) else []


@st.cache_data(ttl=120, show_spinner=False)
def _load_entity_provenance(entity_id: str) -> Dict[str, Any]:
    return _api.get_entity_provenance(entity_id)


@st.cache_data(ttl=120, show_spinner=False)
def _load_relationship_provenance(rel_id: str) -> Dict[str, Any]:
    return _api.get_relationship_provenance(rel_id)


entities = _load_entities()
relations = _load_relations()

# ---------------------------------------------------------------------------
# 3-column layout
# ---------------------------------------------------------------------------
left_col, mid_col, right_col = st.columns([1, 3, 2])

# ===========================================================================
# LEFT COLUMN – Faceted Search
# ===========================================================================
with left_col:
    clicked_entity = render_faceted_search(entities, key_prefix="oe")
    if clicked_entity:
        st.session_state.oe_selected_entity = clicked_entity
        st.session_state.oe_show_proof = False

# ===========================================================================
# MIDDLE COLUMN – Knowledge Graph
# ===========================================================================
with mid_col:
    st.markdown("##### 🕸️ Knowledge Graph")

    # Build node degree map for sizing.
    degree_map: Dict[str, int] = {}
    for rel in relations:
        for key in ("from", "from_entity"):
            n = rel.get(key, "")
            if n:
                degree_map[n] = degree_map.get(n, 0) + 1
        for key in ("to", "to_entity"):
            n = rel.get(key, "")
            if n:
                degree_map[n] = degree_map.get(n, 0) + 1

    selected_name: str = (
        st.session_state.oe_selected_entity.get("name", "")
        if st.session_state.oe_selected_entity
        else ""
    )

    if _AGRAPH and entities:
        # ---- agraph visualisation ----
        agraph_nodes: List[Node] = []
        agraph_edges: List[Edge] = []

        for ent in entities[:120]:
            name = ent.get("name", "?")
            degree = degree_map.get(name, 0)
            size = max(10, min(40, 10 + degree * 3))

            if name == selected_name:
                color = "#D4AF37"
                border_width = 3
            elif degree >= 5:
                color = "#D4AF37"
                border_width = 2
            elif degree >= 2:
                color = "#A8A8A8"
                border_width = 1
            else:
                color = "#E0E0E0"
                border_width = 1

            agraph_nodes.append(
                Node(
                    id=name,
                    label=name,
                    size=size,
                    color=color,
                    font={"color": "#F0F0F0", "size": 10},
                    borderWidth=border_width,
                )
            )

        displayed_names = {n.id for n in agraph_nodes}
        for rel in relations[:300]:
            src = rel.get("from", rel.get("from_entity", ""))
            tgt = rel.get("to", rel.get("to_entity", ""))
            if src in displayed_names and tgt in displayed_names:
                conf = float(rel.get("confidence", rel.get("weight", 0.5)))
                width = max(1, int(conf * 4))
                agraph_edges.append(
                    Edge(
                        source=src,
                        target=tgt,
                        label=rel.get("relation", rel.get("relationship_type", "")),
                        color=f"rgba(212,175,55,{0.4 + conf * 0.6:.2f})",
                        width=width,
                    )
                )

        config = Config(
            width="100%",
            height=520,
            directed=True,
            physics=True,
            hierarchical=False,
            nodeHighlightBehavior=True,
            highlightColor="#D4AF37",
            collapsible=False,
            node={"labelProperty": "label"},
            link={"renderLabel": False, "highlightColor": "#D4AF37"},
            backgroundColor="#0D0D0D",
        )

        clicked_node = agraph(nodes=agraph_nodes, edges=agraph_edges, config=config)
        if clicked_node:
            # Find entity with this name
            for ent in entities:
                if ent.get("name") == clicked_node:
                    st.session_state.oe_selected_entity = ent
                    st.session_state.oe_show_proof = False
                    st.rerun()

    elif _PLOTLY and entities:
        # ---- Plotly network fallback ----
        G = nx.DiGraph()
        for ent in entities[:80]:
            G.add_node(ent.get("name", "?"))
        for rel in relations[:200]:
            src = rel.get("from", rel.get("from_entity", ""))
            tgt = rel.get("to", rel.get("to_entity", ""))
            if src and tgt:
                G.add_edge(src, tgt)

        pos = nx.spring_layout(G, seed=42)

        edge_x, edge_y = [], []
        for u, v in G.edges():
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]

        node_x = [pos[n][0] for n in G.nodes()]
        node_y = [pos[n][1] for n in G.nodes()]
        node_text = list(G.nodes())
        node_colors = [
            "#D4AF37" if n == selected_name or degree_map.get(n, 0) >= 5
            else "#A8A8A8" if degree_map.get(n, 0) >= 2
            else "#E0E0E0"
            for n in G.nodes()
        ]

        fig = go.Figure(
            data=[
                go.Scatter(x=edge_x, y=edge_y, mode="lines",
                           line={"color": "rgba(212,175,55,0.4)", "width": 1},
                           hoverinfo="none"),
                go.Scatter(x=node_x, y=node_y, mode="markers+text",
                           marker={"size": 12, "color": node_colors},
                           text=node_text, textposition="top center",
                           textfont={"color": "#F0F0F0", "size": 9},
                           hoverinfo="text"),
            ]
        )
        fig.update_layout(
            paper_bgcolor="#0D0D0D", plot_bgcolor="#0D0D0D",
            showlegend=False, height=520,
            xaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
            yaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
            margin={"l": 0, "r": 0, "t": 0, "b": 0},
        )
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info(
            "Install `streamlit-agraph` or `plotly` + `networkx` for interactive graph visualisation."
        )
        if entities:
            st.caption(f"Loaded {len(entities)} entities, {len(relations)} relationships")

    # Relationship click / proof toggle
    if st.session_state.oe_selected_entity:
        sel_name = st.session_state.oe_selected_entity.get("name", "")
        nearby_rels = [
            r for r in relations
            if r.get("from", r.get("from_entity", "")) == sel_name
            or r.get("to", r.get("to_entity", "")) == sel_name
        ]
        if nearby_rels:
            st.markdown("**Relationships from/to selected entity:**")
            for rel in nearby_rels[:8]:
                rel_type = rel.get("relation", rel.get("relationship_type", "?"))
                other = (
                    rel.get("to", rel.get("to_entity", "?"))
                    if rel.get("from", rel.get("from_entity", "")) == sel_name
                    else rel.get("from", rel.get("from_entity", "?"))
                )
                rel_id = (
                    rel.get("id")
                    or f"{rel.get('from', '')}|{rel_type}|{rel.get('to', '')}"
                )
                if st.button(
                    f"🔗 `{rel_type}` ↔ **{other}** – show proof",
                    key=f"proof_{rel_id}",
                    use_container_width=True,
                ):
                    st.session_state.oe_proof_rel_id = rel_id
                    st.session_state.oe_show_proof = True

# ===========================================================================
# RIGHT COLUMN – Object View + Proof Panel
# ===========================================================================
with right_col:
    selected = st.session_state.oe_selected_entity

    if st.session_state.oe_show_proof and st.session_state.oe_proof_rel_id:
        # Proof panel mode
        st.markdown("#### 📄 Proof Panel")
        if st.button("← Back to Object View", key="oe_back"):
            st.session_state.oe_show_proof = False
            st.rerun()

        prov = _load_relationship_provenance(st.session_state.oe_proof_rel_id)
        if "error" in prov:
            st.error(f"Could not load provenance: {prov['error']}")
        else:
            render_proof_panel(
                source_refs=prov.get("source_refs", []),
                title=f"Proof: {prov.get('relationship_type', 'relationship')}",
            )

    elif selected:
        # Object view mode
        entity_id = selected.get("id") or selected.get("name", "")
        prov = _load_entity_provenance(entity_id)

        if "error" in prov:
            # Gracefully fall back: show object view without provenance data
            outgoing_rels: List[Dict[str, Any]] = []
            incoming_rels: List[Dict[str, Any]] = []
            prop_history: List[Dict[str, Any]] = []
        else:
            outgoing_rels = prov.get("outgoing", [])
            incoming_rels = prov.get("incoming", [])
            prop_history = prov.get("property_history", [])

        render_object_view(
            entity=selected,
            outgoing=outgoing_rels,
            incoming=incoming_rels,
            property_history=prop_history,
        )

    else:
        st.markdown(
            '<div style="padding:24px; background:#1A1A1A; border:1px solid #30363D; '
            'border-radius:8px; text-align:center;">'
            '<span style="font-size:2rem;">🔷</span><br/>'
            '<span style="color:#A8A8A8;">Select an entity from the left panel or '
            'click a node in the graph to view its profile.</span>'
            "</div>",
            unsafe_allow_html=True,
        )
