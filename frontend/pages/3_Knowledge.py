"""
Knowledge – EL-DRUIN Intelligence Platform
==========================================

3-column Knowledge Graph explorer:

  Left  (1): Faceted Search Panel – entity type, confidence, date, risk, source filters
  Middle (3): Knowledge Graph Visualisation – dark-themed, Agraph or Plotly fallback
  Right  (2): Object View – entity metrics, relationships, timeline, property chart

Run via the Streamlit multi-page app (frontend/app.py).

FIXES APPLIED (v2):
  - Dark theme throughout: all backgrounds #0D1117 / #161B22, no more #F0F8FF
  - agraph node font color changed to #E6EDF3 (readable on dark)
  - agraph backgroundColor set to #0D1117
  - Plotly fallback uses dark background #0D1117
  - Empty-state card uses dark background
  - Removed custom_styles_light.css injection (was overriding dark theme)
  - Added inline dark-theme CSS injection
  - Added Entity Editor panel (add / edit / delete entities and relations)
  - Graph controls: neighbour-expand toggle, search-highlight, layout selector
  - Node colour legend rendered below graph
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from typing import Any, Dict, List, Optional

import streamlit as st

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_FRONTEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FRONTEND_DIR not in sys.path:
    sys.path.insert(0, _FRONTEND_DIR)

from utils.api_client import APIClient, get_assessments, get_propagation, get_triggers, get_attractors  # noqa: E402
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
    page_title="Knowledge – EL-DRUIN",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Shared sidebar navigation
# ---------------------------------------------------------------------------
try:
    from components.sidebar import render_sidebar_navigation  # noqa: E402
    render_sidebar_navigation(is_subpage=True)
except Exception:
    pass

# ---------------------------------------------------------------------------
# FIX 1: Dark-theme CSS – replaces the old custom_styles_light.css injection
# All backgrounds, text, and borders are now dark-mode compatible.
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* ── Global dark canvas ── */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        background-color: #0D1117 !important;
        color: #E6EDF3 !important;
    }
    [data-testid="stSidebar"] {
        background-color: #161B22 !important;
        border-right: 1px solid #30363D;
    }
    /* ── Cards / containers ── */
    .dark-card {
        background: #161B22;
        border: 1px solid #30363D;
        border-radius: 8px;
        padding: 16px;
    }
    /* ── Buttons ── */
    [data-testid="stButton"] > button {
        background: #21262D !important;
        color: #E6EDF3 !important;
        border: 1px solid #30363D !important;
        border-radius: 6px !important;
    }
    [data-testid="stButton"] > button:hover {
        background: #30363D !important;
        border-color: #58A6FF !important;
    }
    /* ── Inputs ── */
    [data-testid="stTextInput"] input,
    [data-testid="stSelectbox"] > div,
    [data-testid="stNumberInput"] input {
        background: #21262D !important;
        color: #E6EDF3 !important;
        border: 1px solid #30363D !important;
        border-radius: 6px !important;
    }
    /* ── Info / divider ── */
    [data-testid="stInfo"] {
        background: #1C2128 !important;
        border-left: 3px solid #58A6FF !important;
        color: #C9D1D9 !important;
    }
    .stDivider { border-color: #30363D !important; }
    /* ── Metric cards ── */
    [data-testid="stMetric"] {
        background: #161B22;
        border: 1px solid #30363D;
        border-radius: 8px;
        padding: 12px;
    }
    /* ── Streamlit toggle ── */
    [data-testid="stToggle"] { color: #E6EDF3 !important; }
    /* ── Tabs ── */
    [data-testid="stTabs"] [role="tab"] {
        color: #8B949E !important;
    }
    [data-testid="stTabs"] [role="tab"][aria-selected="true"] {
        color: #58A6FF !important;
        border-bottom: 2px solid #58A6FF !important;
    }
    /* ── Expander ── */
    details summary {
        color: #C9D1D9 !important;
    }
    /* ── Legend chip ── */
    .legend-chip {
        display: inline-block;
        width: 12px; height: 12px;
        border-radius: 50%;
        margin-right: 6px;
        vertical-align: middle;
    }
    /* ── Edit panel ── */
    .edit-panel-header {
        font-size: 0.85rem;
        font-weight: 600;
        color: #58A6FF;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------
_backend_url_raw = os.environ.get("BACKEND_URL")
if not _backend_url_raw:
    raise RuntimeError(
        "BACKEND_URL environment variable is not set. "
        "Please configure it in your deployment environment. "
        "Expected format: https://your-backend-domain.com/api/v1"
    )
_backend_url = _backend_url_raw.rstrip("/")
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
if "active_assessment_id" not in st.session_state:
    st.session_state.active_assessment_id = None
# FIX / NEW: editor state
if "kg_edit_mode" not in st.session_state:
    st.session_state.kg_edit_mode: bool = False
if "kg_pending_entities" not in st.session_state:
    st.session_state.kg_pending_entities: List[Dict[str, Any]] = []
if "kg_pending_relations" not in st.session_state:
    st.session_state.kg_pending_relations: List[Dict[str, Any]] = []
if "kg_graph_highlight" not in st.session_state:
    st.session_state.kg_graph_highlight: str = ""
if "kg_layout" not in st.session_state:
    st.session_state.kg_layout: str = "Force"
if "kg_expand_neighbours" not in st.session_state:
    st.session_state.kg_expand_neighbours: bool = True

# ---------------------------------------------------------------------------
# Active assessment context bar
# ---------------------------------------------------------------------------
_all_assessments = get_assessments()
_assess_options: Dict[str, str] = {
    a.get("assessment_id", ""): a.get("title", "—")
    for a in _all_assessments
    if a.get("assessment_id", "").strip()
}

_ctx_l, _ctx_m, _ctx_r = st.columns([3, 1, 1])
with _ctx_l:
    if _assess_options:
        _active_id_kg = st.selectbox(
            "Active Assessment",
            options=["—"] + list(_assess_options.keys()),
            format_func=lambda x: "— No active assessment —" if x == "—" else _assess_options.get(x, x),
            key="kg_active_assessment_selector",
        )
        st.session_state.active_assessment_id = _active_id_kg if _active_id_kg != "—" else None
    else:
        st.caption("No assessments available — connect backend to scope the graph")

with _ctx_m:
    _show_full_graph = st.toggle(
        "Show full graph",
        value=st.session_state.active_assessment_id is None,
        key="kg_show_full_graph",
    )

with _ctx_r:
    # NEW: Edit mode toggle
    _edit_mode = st.toggle(
        "✏️ Edit mode",
        value=st.session_state.kg_edit_mode,
        key="kg_edit_mode_toggle",
    )
    st.session_state.kg_edit_mode = _edit_mode

_active_assessment_id_kg = st.session_state.active_assessment_id

# ---------------------------------------------------------------------------
# Compute node relevance
# ---------------------------------------------------------------------------
_relevant_domains: set = set()
_path_domains: set = set()
_relevant_entities: set = set()

if _active_assessment_id_kg and not _show_full_graph:
    try:
        _prop_data_kg = get_propagation(_active_assessment_id_kg)
        _seq = _prop_data_kg.get("sequence", []) if isinstance(_prop_data_kg, dict) else []
        for _s in _seq:
            _d = _s.get("domain", "")
            if _d:
                _path_domains.add(_d.lower())
                _relevant_domains.add(_d.lower())
    except Exception:
        pass
    try:
        _trig_data_kg = get_triggers(_active_assessment_id_kg)
        _trigs = _trig_data_kg.get("triggers", []) if isinstance(_trig_data_kg, dict) else []
        for _t in _trigs:
            for _d in _t.get("impacted_domains", []):
                _relevant_domains.add(_d.lower())
    except Exception:
        pass
    try:
        _attr_data_kg = get_attractors(_active_assessment_id_kg)
        _attrs = _attr_data_kg.get("attractors", []) if isinstance(_attr_data_kg, dict) else []
        for _a in _attrs:
            _aname = _a.get("name", "").lower()
            if _aname:
                _relevant_entities.add(_aname)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Graph title
# ---------------------------------------------------------------------------
_graph_title = "Knowledge Graph"
if _active_assessment_id_kg and not _show_full_graph:
    _assess_title = _assess_options.get(_active_assessment_id_kg, "Selected Assessment")
    _graph_title = f"Knowledge Graph — scoped to: {_assess_title}"

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.markdown(
    f'<h2 style="color:#58A6FF; font-weight:700; letter-spacing:1px; margin-bottom:2px;">'
    f'⚔️ {_graph_title}</h2>',
    unsafe_allow_html=True,
)
st.markdown(
    '<p style="color:#8B949E; font-size:0.9rem; margin-top:0;">',
    unsafe_allow_html=True,
)
if _active_assessment_id_kg and not _show_full_graph:
    st.info(
        "Graph is scoped to domains and entities relevant to the active assessment. "
        "Use 'Show full graph' toggle to view all nodes."
    )
else:
    st.info(
        "**Browse** the Knowledge Graph as typed objects (entities from news and reports). "
        "**Left panel**: filter by type / confidence / date. "
        "**Click a node** to inspect its profile in the right panel. "
        "Enable **Edit mode** to add or modify entities and relationships."
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

# Merge any pending (locally added) entities and relations from the editor
_all_entities = entities + st.session_state.kg_pending_entities
_all_relations = relations + st.session_state.kg_pending_relations

# ---------------------------------------------------------------------------
# 3-column layout
# ---------------------------------------------------------------------------
left_col, mid_col, right_col = st.columns([1, 3, 2])

# ===========================================================================
# LEFT COLUMN – Faceted Search
# ===========================================================================
with left_col:
    clicked_entity = render_faceted_search(_all_entities, key_prefix="oe")
    if clicked_entity:
        st.session_state.oe_selected_entity = clicked_entity
        st.session_state.oe_show_proof = False

    # NEW: Graph controls section
    st.divider()
    st.markdown('<div class="edit-panel-header">Graph Controls</div>', unsafe_allow_html=True)

    # Highlight search
    _highlight = st.text_input(
        "🔍 Highlight node",
        value=st.session_state.kg_graph_highlight,
        placeholder="Type entity name…",
        key="kg_highlight_input",
    )
    st.session_state.kg_graph_highlight = _highlight

    # Layout selector
    _layout_choice = st.selectbox(
        "Layout",
        options=["Force", "Hierarchical", "Circular"],
        index=["Force", "Hierarchical", "Circular"].index(st.session_state.kg_layout),
        key="kg_layout_selector",
    )
    st.session_state.kg_layout = _layout_choice

    # Expand neighbours toggle
    _expand_nb = st.toggle(
        "Expand neighbours on click",
        value=st.session_state.kg_expand_neighbours,
        key="kg_expand_nb_toggle",
    )
    st.session_state.kg_expand_neighbours = _expand_nb

    # Colour legend
    st.divider()
    st.markdown('<div class="edit-panel-header">Node Legend</div>', unsafe_allow_html=True)
    legend_items = [
        ("#58A6FF", "Path node (assessment)"),
        ("#3FB950", "Relevant / attractor"),
        ("#F78166", "Selected"),
        ("#8B949E", "Standard node"),
        ("#484F58", "Low-relevance (dimmed)"),
    ]
    for colour, label in legend_items:
        st.markdown(
            f'<span class="legend-chip" style="background:{colour};"></span>'
            f'<span style="color:#C9D1D9; font-size:0.8rem;">{label}</span><br/>',
            unsafe_allow_html=True,
        )

# ===========================================================================
# MIDDLE COLUMN – Knowledge Graph (dark-themed)
# ===========================================================================
with mid_col:
    st.markdown(f'<h4 style="color:#C9D1D9; margin-bottom:8px;">{_graph_title}</h4>', unsafe_allow_html=True)

    # Build degree map
    degree_map: Dict[str, int] = {}
    for rel in _all_relations:
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
    _highlight_name = st.session_state.kg_graph_highlight.strip().lower()

    def _node_relevance(entity_name: str) -> str:
        if not _active_assessment_id_kg or _show_full_graph:
            return "normal"
        name_lower = entity_name.lower()
        if name_lower in _path_domains:
            return "path"
        if name_lower in _relevant_domains or name_lower in _relevant_entities:
            return "relevant"
        return "normal"

    # Filter display entities
    _display_entities = _all_entities
    if _active_assessment_id_kg and not _show_full_graph and (
        _path_domains or _relevant_domains or _relevant_entities
    ):
        _relevant_names = {
            e.get("name", "") for e in _all_entities
            if _node_relevance(e.get("name", "")) in ("path", "relevant")
        }
        if st.session_state.kg_expand_neighbours:
            _neighbor_names: set = set()
            for r in _all_relations:
                src = r.get("from", r.get("from_entity", ""))
                tgt = r.get("to", r.get("to_entity", ""))
                if src in _relevant_names:
                    _neighbor_names.add(tgt)
                if tgt in _relevant_names:
                    _neighbor_names.add(src)
            _included_names = _relevant_names | _neighbor_names
        else:
            _included_names = _relevant_names
        _display_entities = [e for e in _all_entities if e.get("name", "") in _included_names]

    # ------------------------------------------------------------------
    # FIX 2 + FIX 3: Agraph with dark theme
    # ------------------------------------------------------------------
    if _AGRAPH and _display_entities:
        agraph_nodes: List[Node] = []
        agraph_edges: List[Edge] = []

        for ent in _display_entities[:150]:
            name = ent.get("name", "?")
            degree = degree_map.get(name, 0)
            size = max(10, min(45, 10 + degree * 3))
            relevance = _node_relevance(name)
            is_highlighted = _highlight_name and _highlight_name in name.lower()

            # FIX: dark-mode colour scheme
            if name == selected_name:
                color = "#F78166"        # red-orange for selected
                border_width = 3
                border_color = "#FF8080"
            elif is_highlighted:
                color = "#E3B341"        # amber for search highlight
                border_width = 3
                border_color = "#F0C060"
                size = max(size, 20)
            elif relevance == "path":
                color = "#58A6FF"        # blue for path
                border_width = 3
                border_color = "#79C0FF"
                size = max(size, 18)
            elif relevance == "relevant":
                color = "#3FB950"        # green for relevant
                border_width = 2
                border_color = "#56D364"
            else:
                # degree-based shading on dark palette
                if degree >= 8:
                    color = "#6E7681"
                elif degree >= 3:
                    color = "#484F58"
                else:
                    color = "#30363D"
                border_width = 1
                border_color = "#484F58"

            agraph_nodes.append(
                Node(
                    id=name,
                    label=name,
                    size=size,
                    color=color,
                    # FIX: font must be light for dark background
                    font={"color": "#E6EDF3", "size": 10},
                    borderWidth=border_width,
                )
            )

        displayed_names = {n.id for n in agraph_nodes}
        for rel in _all_relations[:400]:
            src = rel.get("from", rel.get("from_entity", ""))
            tgt = rel.get("to", rel.get("to_entity", ""))
            if src in displayed_names and tgt in displayed_names:
                conf = float(rel.get("confidence", rel.get("weight", 0.5)))
                width = max(1, int(conf * 4))
                is_pending = rel.get("_pending", False)
                edge_color = (
                    f"rgba(88,166,255,{0.5 + conf * 0.4:.2f})"   # blue tint for pending
                    if is_pending
                    else f"rgba(139,148,158,{0.3 + conf * 0.4:.2f})"  # grey for normal
                )
                agraph_edges.append(
                    Edge(
                        source=src,
                        target=tgt,
                        label=rel.get("relation", rel.get("relationship_type", "")),
                        color=edge_color,
                        width=width,
                    )
                )

        _hierarchical = st.session_state.kg_layout == "Hierarchical"

        # FIX: backgroundColor must be dark
        config = Config(
            width="100%",
            height=540,
            directed=True,
            physics=st.session_state.kg_layout == "Force",
            hierarchical=_hierarchical,
            nodeHighlightBehavior=True,
            highlightColor="#F78166",
            collapsible=False,
            node={"labelProperty": "label"},
            link={"renderLabel": False, "highlightColor": "#58A6FF"},
            backgroundColor="#0D1117",   # FIX: dark background
        )

        clicked_node = agraph(nodes=agraph_nodes, edges=agraph_edges, config=config)
        if clicked_node:
            for ent in _all_entities:
                if ent.get("name") == clicked_node:
                    st.session_state.oe_selected_entity = ent
                    st.session_state.oe_show_proof = False
                    st.rerun()

        st.caption(
            f"Showing {len(agraph_nodes)} nodes · {len(agraph_edges)} edges"
            + (" · Pending edits highlighted in blue" if st.session_state.kg_pending_entities or st.session_state.kg_pending_relations else "")
        )

    # ------------------------------------------------------------------
    # FIX 4: Plotly fallback – dark background
    # ------------------------------------------------------------------
    elif _PLOTLY and _display_entities:
        G = nx.DiGraph()
        for ent in _display_entities[:100]:
            G.add_node(ent.get("name", "?"))
        for rel in _all_relations[:250]:
            src = rel.get("from", rel.get("from_entity", ""))
            tgt = rel.get("to", rel.get("to_entity", ""))
            if src and tgt and src in G.nodes and tgt in G.nodes:
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
        node_colors = []
        for n in G.nodes():
            rel_n = _node_relevance(n)
            hl = _highlight_name and _highlight_name in n.lower()
            if n == selected_name:
                node_colors.append("#F78166")
            elif hl:
                node_colors.append("#E3B341")
            elif rel_n == "path":
                node_colors.append("#58A6FF")
            elif rel_n == "relevant":
                node_colors.append("#3FB950")
            elif degree_map.get(n, 0) >= 5:
                node_colors.append("#6E7681")
            elif degree_map.get(n, 0) >= 2:
                node_colors.append("#484F58")
            else:
                node_colors.append("#30363D")

        # FIX: dark paper_bgcolor and plot_bgcolor
        fig = go.Figure(
            data=[
                go.Scatter(
                    x=edge_x, y=edge_y, mode="lines",
                    line={"color": "rgba(139,148,158,0.5)", "width": 0.8},
                    hoverinfo="none",
                ),
                go.Scatter(
                    x=node_x, y=node_y, mode="markers+text",
                    marker={"size": 12, "color": node_colors, "line": {"width": 1, "color": "#30363D"}},
                    text=node_text, textposition="top center",
                    # FIX: light text on dark background
                    textfont={"color": "#C9D1D9", "size": 9},
                    hoverinfo="text",
                ),
            ]
        )
        fig.update_layout(
            # FIX: dark backgrounds
            paper_bgcolor="#0D1117",
            plot_bgcolor="#0D1117",
            showlegend=False,
            height=540,
            xaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
            yaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
            margin={"l": 0, "r": 0, "t": 0, "b": 0},
            font={"color": "#C9D1D9"},
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Plotly fallback · {len(list(G.nodes()))} nodes")

    else:
        st.info(
            "Install `streamlit-agraph` or `plotly` + `networkx` for interactive graph visualisation."
        )
        if _display_entities:
            st.caption(f"Loaded {len(_display_entities)} entities, {len(_all_relations)} relationships")

    # ------------------------------------------------------------------
    # Relationship buttons (dark-themed)
    # ------------------------------------------------------------------
    if st.session_state.oe_selected_entity:
        sel_name = st.session_state.oe_selected_entity.get("name", "")
        nearby_rels = [
            r for r in _all_relations
            if r.get("from", r.get("from_entity", "")) == sel_name
            or r.get("to", r.get("to_entity", "")) == sel_name
        ]
        if nearby_rels:
            st.markdown(
                f'<div style="color:#8B949E; font-size:0.8rem; margin-top:8px; margin-bottom:4px;">'
                f'Relationships connected to <b style="color:#E6EDF3">{sel_name}</b></div>',
                unsafe_allow_html=True,
            )
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
                    f"🔗 `{rel_type}` ↔ **{other}**",
                    key=f"proof_{rel_id}",
                    use_container_width=True,
                ):
                    st.session_state.oe_proof_rel_id = rel_id
                    st.session_state.oe_show_proof = True

# ===========================================================================
# RIGHT COLUMN – Object View / Proof Panel / Editor
# ===========================================================================
with right_col:
    selected = st.session_state.oe_selected_entity

    # ------------------------------------------------------------------
    # NEW: Edit mode panel
    # ------------------------------------------------------------------
    if st.session_state.kg_edit_mode:
        with st.expander("✏️ Entity & Relation Editor", expanded=True):
            edit_tab1, edit_tab2 = st.tabs(["Add Entity", "Add Relation"])

            # -- Add entity --
            with edit_tab1:
                st.markdown('<div class="edit-panel-header">New Entity</div>', unsafe_allow_html=True)
                _new_name = st.text_input("Name", key="edit_new_entity_name", placeholder="e.g. TSMC")
                _new_type = st.selectbox(
                    "Entity Type",
                    ["STATE", "FIRM", "TECH", "PERSON", "ALLIANCE", "MEDIA",
                     "FINANCIAL_ORG", "RESOURCE", "CURRENCY", "SUPPLY_CHAIN",
                     "STANDARD", "TRUST", "INSTITUTION", "CONFLICT", "NORM", "UNKNOWN"],
                    key="edit_new_entity_type",
                )
                _new_conf = st.slider("Confidence", 0.0, 1.0, 0.7, 0.05, key="edit_new_entity_conf")
                _new_domain = st.selectbox(
                    "Domain",
                    ["geopolitics", "economics", "technology", "military", "information"],
                    key="edit_new_entity_domain",
                )
                _new_risk = st.selectbox(
                    "Risk Level",
                    ["low", "medium", "high", "critical"],
                    key="edit_new_entity_risk",
                )
                if st.button("➕ Add Entity", key="edit_add_entity_btn", use_container_width=True):
                    if _new_name.strip():
                        st.session_state.kg_pending_entities.append({
                            "id": f"pending_{uuid.uuid4().hex[:8]}",
                            "name": _new_name.strip(),
                            "type": _new_type,
                            "confidence": _new_conf,
                            "domain": _new_domain,
                            "risk_level": _new_risk,
                            "_pending": True,
                        })
                        st.success(f"Entity '{_new_name}' staged. Save to backend to persist.")
                        st.rerun()
                    else:
                        st.warning("Entity name cannot be empty.")

            # -- Add relation --
            with edit_tab2:
                st.markdown('<div class="edit-panel-header">New Relation</div>', unsafe_allow_html=True)
                _all_names = sorted({e.get("name", "") for e in _all_entities if e.get("name")})
                _rel_from = st.selectbox("From Entity", _all_names, key="edit_rel_from")
                _rel_type = st.selectbox(
                    "Relation Type",
                    ["SANCTION", "MILITARY_STRIKE", "COERCE", "BLOCKADE",
                     "SUPPORT", "ALLY", "AID", "AGREE",
                     "DEPENDENCY", "TRADE_FLOW", "SUPPLY", "FINANCE",
                     "SIGNAL", "PROPAGANDA", "LEGITIMIZE", "DELEGITIMIZE",
                     "REGULATE", "STANDARDIZE", "EXCLUDE", "INTEGRATE"],
                    key="edit_rel_type",
                )
                _rel_to = st.selectbox("To Entity", _all_names, key="edit_rel_to")
                _rel_conf = st.slider("Confidence", 0.0, 1.0, 0.7, 0.05, key="edit_rel_conf")
                if st.button("➕ Add Relation", key="edit_add_rel_btn", use_container_width=True):
                    if _rel_from and _rel_to and _rel_from != _rel_to:
                        st.session_state.kg_pending_relations.append({
                            "id": f"rel_pending_{uuid.uuid4().hex[:8]}",
                            "from": _rel_from,
                            "to": _rel_to,
                            "relation": _rel_type,
                            "confidence": _rel_conf,
                            "_pending": True,
                        })
                        st.success(f"Relation '{_rel_from} →[{_rel_type}]→ {_rel_to}' staged.")
                        st.rerun()
                    else:
                        st.warning("Select two different entities.")

            # Pending changes summary
            if st.session_state.kg_pending_entities or st.session_state.kg_pending_relations:
                st.divider()
                st.markdown(
                    f'<div style="color:#E3B341; font-size:0.85rem;">⚠️ '
                    f'{len(st.session_state.kg_pending_entities)} pending entities, '
                    f'{len(st.session_state.kg_pending_relations)} pending relations '
                    f'(not yet saved to backend)</div>',
                    unsafe_allow_html=True,
                )
                _save_col, _clear_col = st.columns(2)
                with _save_col:
                    if st.button("💾 Save to backend", key="edit_save_btn", use_container_width=True):
                        # Attempt to push pending items via API
                        _save_errors = []
                        for _pe in st.session_state.kg_pending_entities:
                            try:
                                _api.create_kg_entity(_pe)
                            except Exception as _e:
                                _save_errors.append(str(_e))
                        for _pr in st.session_state.kg_pending_relations:
                            try:
                                _api.create_kg_relation(_pr)
                            except Exception as _e:
                                _save_errors.append(str(_e))
                        if _save_errors:
                            st.error("Some saves failed: " + "; ".join(_save_errors[:3]))
                        else:
                            st.session_state.kg_pending_entities = []
                            st.session_state.kg_pending_relations = []
                            _load_entities.clear()
                            _load_relations.clear()
                            st.success("Saved. Cache cleared.")
                            st.rerun()
                with _clear_col:
                    if st.button("🗑 Discard all", key="edit_discard_btn", use_container_width=True):
                        st.session_state.kg_pending_entities = []
                        st.session_state.kg_pending_relations = []
                        st.rerun()

        st.divider()

    # ------------------------------------------------------------------
    # Proof panel or Object view (unchanged logic, FIX 5: dark empty state)
    # ------------------------------------------------------------------
    if st.session_state.oe_show_proof and st.session_state.oe_proof_rel_id:
        st.markdown(
            '<h4 style="color:#58A6FF;">🔍 Proof Panel</h4>',
            unsafe_allow_html=True,
        )
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
        entity_id = selected.get("id") or selected.get("name", "")
        prov = _load_entity_provenance(entity_id)

        if "error" in prov:
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

        # Delete button for pending entities
        if selected.get("_pending"):
            st.divider()
            if st.button("🗑 Remove this pending entity", key="oe_delete_pending", use_container_width=True):
                st.session_state.kg_pending_entities = [
                    e for e in st.session_state.kg_pending_entities
                    if e.get("name") != selected.get("name")
                ]
                st.session_state.oe_selected_entity = None
                st.rerun()

    else:
        # FIX 5: dark background empty state (was white #FFFFFF)
        st.markdown(
            '<div class="dark-card" style="text-align:center; padding:40px 16px;">'
            '<span style="font-size:2.5rem; opacity:0.4;">◇</span><br/><br/>'
            '<span style="color:#8B949E; font-size:0.9rem;">'
            'Select an entity from the left panel or click a node in the graph to view its profile.'
            '</span>'
            '</div>',
            unsafe_allow_html=True,
        )