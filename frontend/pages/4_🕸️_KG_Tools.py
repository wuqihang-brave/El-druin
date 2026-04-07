"""
KG Tools – Text Extraction, Visualisation, Cypher Query
========================================================

Features:
  Tab 1 - 📝 Text Extraction: input text → extract entities/relations → show metrics
  Tab 2 - 🕸️ Graph Visualisation: NetworkX + streamlit-agraph interactive display
  Tab 3 - 🌈 Ontology Graph: 3-column layout with ontology class filters
  Tab 4 - 🎚️ Hierarchical Graph: Degree-filtered hierarchical graph
  Tab 5 - 💬 Cypher Query: input Cypher → execute → show DataFrame

Uses st.session_state to cache extraction results.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

import networkx as nx
import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
    _PLOTLY_AVAILABLE = True
except ImportError:
    _PLOTLY_AVAILABLE = False

try:
    from streamlit_agraph import agraph, Config, Edge, Node  # type: ignore[import]
    _AGRAPH_AVAILABLE = True
except ImportError:
    _AGRAPH_AVAILABLE = False

# Allow ``from utils.api_client import api_client`` when running from repo root.
_FRONTEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FRONTEND_DIR not in sys.path:
    sys.path.insert(0, _FRONTEND_DIR)

from utils.api_client import APIClient  # noqa: E402
from utils.ontology_colors import (  # noqa: E402
    ALL_ONTOLOGY_CLASSES,
    get_node_color,
    get_ontology_meaning,
    get_canonical_class,
)
from utils.graph_styling import render_graph_with_colors, render_color_legend  # noqa: E402
from components.ontological_panel import render_ontological_significance  # noqa: E402

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="KG Tools – EL-DRUIN",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Backend client
# ---------------------------------------------------------------------------
_backend_url_raw = os.environ.get("BACKEND_URL")
if not _backend_url_raw:
    try:
        from components.sidebar import render_sidebar_navigation  # noqa: E402
        render_sidebar_navigation(is_subpage=True)
    except Exception:
        pass
    st.info(
        "KG Tools requires a running backend. Start the backend to use this feature.\n\n"
        "To run locally: `cd backend && uvicorn app.main:app --port 8000`\n\n"
        "Then set the `BACKEND_URL` environment variable to point to it."
    )
    st.stop()
_backend_url = _backend_url_raw.rstrip("/")
_api = APIClient(base_url=_backend_url)

# ---------------------------------------------------------------------------
# Inject Dark Liturgy CSS
# ---------------------------------------------------------------------------
_CSS_PATH = os.path.join(_FRONTEND_DIR, "assets", "custom_styles.css")
try:
    with open(_CSS_PATH, encoding="utf-8") as _css_f:
        st.markdown(f"<style>{_css_f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    pass  # CSS missing – app still functional

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
if "kg_extract_result" not in st.session_state:
    st.session_state.kg_extract_result: Dict[str, Any] = {}
if "kg_query_result" not in st.session_state:
    st.session_state.kg_query_result: List[Any] = []
if "kg_query_text" not in st.session_state:
    st.session_state.kg_query_text: str = ""
# Ontology Graph tab state
if "og_selected_entity" not in st.session_state:
    st.session_state.og_selected_entity: Optional[Dict[str, Any]] = None
if "og_ontology_filter" not in st.session_state:
    st.session_state.og_ontology_filter: List[str] = list(ALL_ONTOLOGY_CLASSES)
if "og_confidence_min" not in st.session_state:
    st.session_state.og_confidence_min: float = 0.0
if "og_search_text" not in st.session_state:
    st.session_state.og_search_text: str = ""

# ---------------------------------------------------------------------------
# Entity-type colour map (Clear Day theme — cobalt and rational tones)
# ---------------------------------------------------------------------------
_TYPE_COLORS: Dict[str, str] = {
    "PERSON":  "#0047AB",  # Cobalt Blue
    "ORG":     "#2E86AB",  # Cerulean Blue
    "GPE":     "#2A9D8F",  # Teal
    "LOC":     "#1B6CA8",  # Royal Blue
    "DATE":    "#606060",  # Mid Grey
    "MONEY":   "#2E86AB",  # Cerulean
    "PERCENT": "#0047AB",  # Cobalt Blue
    "EVENT":   "#0047AB",  # Cobalt Blue
    "MISC":    "#A0A0A0",  # Light Grey
}
_DEFAULT_COLOR = "#A0A0A0"


def _entity_color(entity_type: str) -> str:
    return _TYPE_COLORS.get(entity_type.upper(), _DEFAULT_COLOR)


# ---------------------------------------------------------------------------
# Hierarchical graph tier constants — Clear Day theme
# (thresholds must match backend/_importance_tier in knowledge.py)
# ---------------------------------------------------------------------------
_HG_TIERS = [
    # (min_degree, label, color, size)
    (10, "Critical",  "#0047AB", 80),   # Cobalt Blue  — core hubs
    (5,  "Important", "#2E86AB", 50),   # Cerulean Blue — connectors
    (2,  "Bridge",    "#A0C4E8", 35),   # Soft Blue    — bridges
    (0,  "Leaf",      "#E0E0E0", 20),   # Light Grey   — fringe
]


def _node_visual(degree: int):
    """Return (tier_label, color, size) for a node given its degree."""
    for min_deg, label, color, size in _HG_TIERS:
        if degree >= min_deg:
            return label, color, size
    return "Leaf", "#E0E0E0", 20


# ===========================================================================
# Page title
# ===========================================================================
st.markdown(
    """
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:4px;">
        <svg width="32" height="32" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
          <line x1="20" y1="5" x2="20" y2="35" stroke="#0047AB" stroke-width="2" stroke-linecap="round"/>
          <line x1="12" y1="15" x2="28" y2="15" stroke="#0047AB" stroke-width="2" stroke-linecap="round"/>
          <circle cx="20" cy="15" r="2" fill="#0047AB"/>
        </svg>
        <h1 style="color:#0047AB;margin:0;font-weight:600;letter-spacing:2px;
                   font-family:'Inter',sans-serif;">KG Tools</h1>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption("Extract entities and relations from text, visualise the Knowledge Graph, and explore data via Cypher query.")

st.divider()

# ===========================================================================
# Tabs
# ===========================================================================
tab_extract, tab_viz, tab_onto, tab_hierarchy, tab_query = st.tabs(
    ["📝 Text Extraction", "🕸️ Graph Visualisation", "🌈 Ontology Graph", "🎚️ Hierarchical Graph", "💬 Cypher Query"]
)

# ===========================================================================
# Tab 1 – Text Extraction
# ===========================================================================
with tab_extract:
    st.subheader("📝 Extract Knowledge from Text")

    input_text = st.text_area(
        "News article text",
        placeholder="Paste a news article (10 – 10000 characters)…",
        height=180,
        max_chars=10000,
        key="extract_input_text",
    )

    col_btn, col_clear = st.columns([1, 5])
    with col_btn:
        do_extract = st.button("⚔️ Manifest Knowledge", type="primary", key="btn_extract")
    with col_clear:
        if st.button("🗑️ Clear results", key="btn_clear_extract"):
            st.session_state.kg_extract_result = {}
            st.rerun()

    # Validate and call backend
    if do_extract:
        text_stripped = (input_text or "").strip()
        if len(text_stripped) < 10:
            st.warning("⚠️ Text is too short. Minimum 10 characters required.")
        else:
            with st.spinner("🔍 Extracting entities and relations…"):
                result = _api.extract_knowledge(text_stripped)
            if result.get("status") == "error" or (
                "error" in result and "entities" not in result
            ):
                st.error(f"❌ Extraction failed: {result.get('error', 'Unknown error')}")
            else:
                st.session_state.kg_extract_result = result
                st.success("✅ Extraction complete! Results cached.")

    # Display cached results
    cached = st.session_state.kg_extract_result
    if cached:
        entities: List[Dict[str, Any]] = cached.get("entities", [])
        relations: List[Dict[str, Any]] = cached.get("relations", [])
        # Triples = relations expressed as (subject, predicate, object)
        triples = [
            {
                "Subject": r.get("subject", ""),
                "Predicate": r.get("predicate", ""),
                "Object": r.get("object", ""),
            }
            for r in relations
        ]

        # ── Metrics ──────────────────────────────────────────────────────────
        st.markdown("#### 📊 Extraction Summary")
        m1, m2, m3 = st.columns(3)
        m1.metric("🔵 Entities", len(entities))
        m2.metric("🔗 Relations", len(relations))
        m3.metric("📐 Triples", len(triples))

        st.divider()

        # ── Entities table ────────────────────────────────────────────────────
        st.markdown("#### 📋 Extracted Entities")
        if entities:
            df_entities = pd.DataFrame(
                [
                    {
                        "Name": e.get("name", ""),
                        "Type": e.get("type", ""),
                        "Description": e.get("description", ""),
                        "Confidence": round(float(e.get("confidence", 0)), 3),
                    }
                    for e in entities
                ]
            )
            st.dataframe(df_entities, use_container_width=True, height=250)
        else:
            st.info("No entities extracted.")

        # ── Relations table ───────────────────────────────────────────────────
        st.markdown("#### 🔗 Extracted Relations")
        if relations:
            df_relations = pd.DataFrame(
                [
                    {
                        "Subject": r.get("subject", ""),
                        "Predicate": r.get("predicate", ""),
                        "Object": r.get("object", ""),
                    }
                    for r in relations
                ]
            )
            st.dataframe(df_relations, use_container_width=True, height=250)
        else:
            st.info("No relations extracted.")

        # ── Triples table ─────────────────────────────────────────────────────
        if triples:
            st.markdown("#### 📐 Triple List")
            st.dataframe(pd.DataFrame(triples), use_container_width=True, height=200)

    elif not do_extract:
        st.info("👆 Enter text above and click '⚔️ Manifest Knowledge' to begin extraction.")

# ===========================================================================
# Tab 2 – Graph Visualisation
# ===========================================================================
with tab_viz:
    st.subheader("🕸️ Knowledge Graph Visualisation")

    # ── Data source selector ─────────────────────────────────────────────────
    data_source = st.radio(
        "Data Source",
        ["Use extraction results (Tab 1)", "Load from graph database"],
        horizontal=True,
        key="viz_data_source",
    )

    viz_entities: List[Dict[str, Any]] = []
    viz_relations: List[Dict[str, Any]] = []

    if data_source == "Use extraction results (Tab 1)":
        cached_viz = st.session_state.kg_extract_result
        if cached_viz:
            viz_entities = cached_viz.get("entities", [])
            # Convert extract relations (subject/predicate/object) to viz format
            viz_relations = [
                {
                    "from": r.get("subject", ""),
                    "relation": r.get("predicate", ""),
                    "to": r.get("object", ""),
                }
                for r in cached_viz.get("relations", [])
            ]
        else:
            st.info("👆 Please extract knowledge in the '📝 Text Extraction' tab first, or switch to 'Load from graph database'.")
    else:
        with st.spinner("📡 Loading entities and relations from database…"):
            ent_resp = _api.get_kg_entities(limit=200)
            rel_resp = _api.get_kg_relations(limit=300)
        if "error" in ent_resp:
            st.error(f"❌ Failed to load entities: {ent_resp['error']}")
        elif "error" in rel_resp:
            st.error(f"❌ Failed to load relations: {rel_resp['error']}")
        else:
            viz_entities = ent_resp.get("entities", [])
            viz_relations = rel_resp.get("relations", [])

    # ── Build graph and visualise ─────────────────────────────────────────────
    if viz_entities or viz_relations:
        import networkx as nx

        G = nx.DiGraph()

        # Build entity name → type lookup from viz_entities
        entity_types: Dict[str, str] = {}
        for e in viz_entities:
            name = e.get("name", "")
            etype = e.get("type", "MISC")
            if name:
                entity_types[name] = etype
                G.add_node(name, entity_type=etype)

        for r in viz_relations:
            src = r.get("from", "") or r.get("subject", "")
            tgt = r.get("to", "") or r.get("object", "")
            rel = r.get("relation", "") or r.get("predicate", "")
            if src and tgt:
                # Ensure nodes exist even if not in entity list
                if src not in entity_types:
                    G.add_node(src, entity_type="MISC")
                    entity_types[src] = "MISC"
                if tgt not in entity_types:
                    G.add_node(tgt, entity_type="MISC")
                    entity_types[tgt] = "MISC"
                G.add_edge(src, tgt, label=rel)

        st.caption(
            f"Graph: **{G.number_of_nodes()}** nodes · **{G.number_of_edges()}** edges"
        )

        # ── Colour legend ─────────────────────────────────────────────────────
        present_types = sorted({entity_types.get(n, "MISC") for n in G.nodes()})
        if present_types:
            legend_cols = st.columns(min(len(present_types), 6))
            for idx, etype in enumerate(present_types):
                col = legend_cols[idx % len(legend_cols)]
                color = _entity_color(etype)
                col.markdown(
                    f"<span style='color:{color};font-size:18px'>●</span> **{etype}**",
                    unsafe_allow_html=True,
                )

        # ── Try streamlit-agraph first, fall back to plotly ───────────────────
        if _AGRAPH_AVAILABLE:
            nodes: List[Node] = []
            edges: List[Edge] = []
            for node_name in G.nodes():
                etype = entity_types.get(node_name, "MISC")
                color = _entity_color(etype)
                nodes.append(
                    Node(
                        id=node_name,
                        label=node_name,
                        size=20,
                        color=color,
                        title=f"{node_name}\nType: {etype}",
                    )
                )
            for src, tgt, data in G.edges(data=True):
                edges.append(
                    Edge(
                        source=src,
                        target=tgt,
                        label=data.get("label", ""),
                        color="rgba(160,160,160,0.6)",
                    )
                )

            config = Config(
                width="100%",
                height=550,
                directed=True,
                physics=True,
                hierarchical=False,
                nodeHighlightBehavior=True,
                highlightColor="#003580",
                collapsible=False,
            )

            agraph(nodes=nodes, edges=edges, config=config)

        elif _PLOTLY_AVAILABLE:
            # Fallback: plotly scatter graph
            pos = nx.spring_layout(G, seed=42, k=2)

            edge_x: List[float] = []
            edge_y: List[float] = []
            for u, v in G.edges():
                x0, y0 = pos[u]
                x1, y1 = pos[v]
                edge_x += [x0, x1, None]
                edge_y += [y0, y1, None]

            node_x = [pos[n][0] for n in G.nodes()]
            node_y = [pos[n][1] for n in G.nodes()]
            node_text = list(G.nodes())
            node_colors = [_entity_color(entity_types.get(n, "MISC")) for n in G.nodes()]

            fig_net = go.Figure(
                data=[
                    go.Scatter(
                        x=edge_x, y=edge_y, mode="lines",
                        line={"width": 0.5, "color": "rgba(160,160,160,0.6)"},
                        hoverinfo="none",
                    ),
                    go.Scatter(
                        x=node_x, y=node_y, mode="markers+text",
                        text=node_text, textposition="top center",
                        textfont={"color": "#606060", "size": 10},
                        marker={"size": 14, "color": node_colors,
                                "line": {"width": 1, "color": "#E0E0E0"}},
                        hoverinfo="text",
                    ),
                ],
                layout=go.Layout(
                    title={"text": "Knowledge Graph", "font": {"color": "#0047AB"}},
                    showlegend=False,
                    hovermode="closest",
                    paper_bgcolor="#F0F8FF",
                    plot_bgcolor="#F0F8FF",
                    xaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
                    yaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
                    height=550,
                    margin={"t": 40, "b": 0, "l": 0, "r": 0},
                ),
            )
            st.plotly_chart(fig_net, use_container_width=True)

    elif data_source == "Load from graph database":
        if "error" not in _api.get_kg_stats():
            st.info(
                "📭 **No data in the graph yet.**\n\n"
                "Add knowledge via the '📝 Text Extraction' tab, or click the button below to inject sample data."
            )
            if st.button("🌱 Inject Sample Triples", key="btn_seed_viz", type="primary"):
                with st.spinner("Injecting sample data…"):
                    seed_resp = _api.seed_knowledge_graph()
                if seed_resp.get("status") == "ok":
                    st.success(seed_resp.get("message", "Sample data injected successfully."))
                    st.rerun()
                else:
                    st.error(f"Injection failed: {seed_resp.get('error', seed_resp)}")

# ===========================================================================
# Tab 3 – 🌈 Ontology Graph (3-column layout with color-coded nodes)
# ===========================================================================
with tab_onto:
    st.subheader("🌈 Ontology Graph")
    st.caption(
        "Knowledge graph nodes colored by ontological class. "
        "Select a node to view its philosophical significance."
    )

    # ── Load data from backend ─────────────────────────────────────────────
    @st.cache_data(ttl=60, show_spinner=False)
    def _load_og_entities() -> List[Dict[str, Any]]:
        resp = _api.get_kg_entities(limit=500)
        return resp.get("entities", []) if isinstance(resp, dict) else []

    @st.cache_data(ttl=60, show_spinner=False)
    def _load_og_relations() -> List[Dict[str, Any]]:
        resp = _api.get_kg_relations(limit=1000)
        return resp.get("relations", []) if isinstance(resp, dict) else []

    og_entities_all = _load_og_entities()
    og_relations_all = _load_og_relations()

    # ── Show friendly message when no data is available ───────────────────
    if not og_entities_all:
        st.info(
            "📭 **No entities found in the knowledge graph.**\n\n"
            "The ontology graph requires data in the database before it can be "
            "displayed. You can:\n"
            "- Extract knowledge from a text in the **📝 Text Extraction** tab\n"
            "- Seed the graph with example data using the button below"
        )
        if st.button("🌱 Seed Example Data", key="btn_seed_onto", type="primary"):
            with st.spinner("Seeding knowledge graph with example triples…"):
                seed_resp = _api.seed_knowledge_graph()
            if seed_resp.get("status") == "ok":
                st.success(seed_resp.get("message", "Seed triples added."))
                _load_og_entities.clear()
                _load_og_relations.clear()
                st.rerun()
            else:
                st.error(f"Seeding failed: {seed_resp.get('error', seed_resp)}")
        st.stop()

    # ── 3-column layout ────────────────────────────────────────────────────
    og_left, og_mid, og_right = st.columns([1, 3, 2])

    # ------------------------------------------------------------------
    # LEFT: Search + Ontology Class Filter + Confidence Slider
    # ------------------------------------------------------------------
    with og_left:
        st.markdown("#### 🔍 Search & Filter")

        og_search = st.text_input(
            "Entity search",
            value=st.session_state.og_search_text,
            placeholder="Type to search…",
            key="og_search_input",
        )
        st.session_state.og_search_text = og_search

        st.markdown("**Filter by ontology class**")
        og_filter_classes = st.multiselect(
            "Ontology classes",
            options=ALL_ONTOLOGY_CLASSES,
            default=st.session_state.og_ontology_filter,
            key="og_filter_multiselect",
            label_visibility="collapsed",
        )
        st.session_state.og_ontology_filter = og_filter_classes

        og_conf_min = st.slider(
            "Min confidence",
            min_value=0.0,
            max_value=1.0,
            value=st.session_state.og_confidence_min,
            step=0.05,
            format="%.2f",
            key="og_conf_slider",
        )
        st.session_state.og_confidence_min = og_conf_min

        st.divider()

        # Color legend
        st.markdown("**Ontology Colors**")
        for cls in ALL_ONTOLOGY_CLASSES:
            color = get_node_color(cls)
            st.markdown(
                f"<span style='color:{color};font-size:16px'>●</span> "
                f"<span style='color:#E0E0E0;font-size:0.82rem;'>{cls}</span>",
                unsafe_allow_html=True,
            )

        st.divider()
        st.caption(f"Loaded {len(og_entities_all)} entities, {len(og_relations_all)} relations")

    # ------------------------------------------------------------------
    # Apply filters to entity/relation lists
    # ------------------------------------------------------------------
    _selected_classes_lower = {c.lower() for c in og_filter_classes}

    def _passes_class_filter(ent: Dict[str, Any]) -> bool:
        onto = get_canonical_class(
            ent.get("ontology_class") or ent.get("type", "misc")
        ).lower()
        return onto in _selected_classes_lower

    def _passes_confidence_filter(ent: Dict[str, Any]) -> bool:
        return float(ent.get("confidence", 1.0)) >= og_conf_min

    def _passes_search_filter(ent: Dict[str, Any]) -> bool:
        if not og_search:
            return True
        return og_search.lower() in ent.get("name", "").lower()

    og_entities_filtered = [
        e for e in og_entities_all
        if _passes_class_filter(e) and _passes_confidence_filter(e) and _passes_search_filter(e)
    ]

    # Keep only relations where both endpoints are in the filtered set
    _filtered_names = {e.get("name", "") for e in og_entities_filtered}
    og_relations_filtered = [
        r for r in og_relations_all
        if (
            r.get("from", r.get("from_entity", r.get("subject", ""))) in _filtered_names
            and r.get("to", r.get("to_entity", r.get("object", ""))) in _filtered_names
        )
    ]

    # ------------------------------------------------------------------
    # MIDDLE: Knowledge Graph with color-coded nodes
    # ------------------------------------------------------------------
    with og_mid:
        st.markdown(
            f"<span style='color:#606060;font-size:0.82rem;'>"
            f"Showing **{len(og_entities_filtered)}** nodes, "
            f"**{len(og_relations_filtered)}** edges</span>",
            unsafe_allow_html=True,
        )

        if not og_entities_filtered:
            st.info(
                "🔍 No entities match the current filters. "
                "Try widening the ontology class selection, lowering the minimum "
                "confidence, or clearing the search term."
            )
        else:
            og_selected_name = (
                st.session_state.og_selected_entity.get("name", "")
                if st.session_state.og_selected_entity
                else ""
            )

            clicked_og_node = render_graph_with_colors(
                graph_data={
                    "entities": og_entities_filtered,
                    "relations": og_relations_filtered,
                },
                selected_name=og_selected_name,
                height=600,
            )

            if clicked_og_node:
                # Find the entity dict for the clicked node
                for ent in og_entities_all:
                    if ent.get("name") == clicked_og_node:
                        if st.session_state.og_selected_entity != ent:
                            st.session_state.og_selected_entity = ent
                            # Clear cached explanation when new entity selected
                            cache_key = f"onto_expl_{ent.get('name', '')}_{0}"
                            if cache_key in st.session_state:
                                del st.session_state[cache_key]
                            st.rerun()
                        break

    # ------------------------------------------------------------------
    # RIGHT: Entity Info Panel + Ontological Significance
    # ------------------------------------------------------------------
    with og_right:
        og_selected = st.session_state.og_selected_entity

        if og_selected:
            name = og_selected.get("name", "Unknown")
            onto_class = og_selected.get("ontology_class") or og_selected.get("type", "misc")
            color = get_node_color(onto_class)
            canonical = get_canonical_class(onto_class)
            confidence = float(og_selected.get("confidence", 0.0))

            # Degree
            degree = sum(
                1 for r in og_relations_all
                if r.get("from", r.get("from_entity", "")) == name
                or r.get("to", r.get("to_entity", "")) == name
            )

            # Entity header
            st.markdown(
                f'<h4 style="color:#0047AB;margin-bottom:4px;">{name}</h4>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<span style="background:{color}33;border:1px solid {color};'
                f'color:{color};padding:2px 10px;border-radius:10px;'
                f'font-size:0.8rem;font-weight:700;">{canonical}</span>',
                unsafe_allow_html=True,
            )
            st.markdown("")

            # Metrics
            mc1, mc2 = st.columns(2)
            mc1.metric("Confidence", f"{confidence:.0%}")
            mc2.metric("Degree", degree)

            desc = og_selected.get("description", "")
            if desc:
                st.markdown(
                    f'<span style="color:#606060;font-size:0.82rem;">{desc}</span>',
                    unsafe_allow_html=True,
                )

            st.divider()

            # Connected entities for the panel
            og_connected: List[Dict[str, Any]] = []
            for r in og_relations_all:
                src = r.get("from", r.get("from_entity", ""))
                tgt = r.get("to", r.get("to_entity", ""))
                rel_type = r.get("relation", r.get("relationship_type", ""))
                if src == name:
                    tgt_ent = next(
                        (e for e in og_entities_all if e.get("name") == tgt), {}
                    )
                    og_connected.append({
                        "name": tgt,
                        "type": tgt_ent.get("ontology_class") or tgt_ent.get("type", "misc"),
                        "relationship": rel_type,
                        "direction": "outgoing",
                    })
                elif tgt == name:
                    src_ent = next(
                        (e for e in og_entities_all if e.get("name") == src), {}
                    )
                    og_connected.append({
                        "name": src,
                        "type": src_ent.get("ontology_class") or src_ent.get("type", "misc"),
                        "relationship": rel_type,
                        "direction": "incoming",
                    })

            # Ontological Significance panel
            render_ontological_significance(
                entity=og_selected,
                connected_entities=og_connected,
                api_client=_api,
                degree=degree,
            )

        else:
            st.markdown(
                '<div style="padding:24px;background:#FFFFFF;border:1px solid #E0E0E0;'
                'border-radius:4px;text-align:center;">'
                '<span style="font-size:2rem;">🌈</span><br/>'
                '<span style="color:#606060;">Click a node in the graph to view its '
                'ontological profile and philosophical significance.</span>'
                "</div>",
                unsafe_allow_html=True,
            )

# ===========================================================================
# Tab 4 – Hierarchical Graph
# ===========================================================================
with tab_hierarchy:
    st.subheader("🎚️ Hierarchical Knowledge Graph")
    st.caption("Adjust node visibility using the degree filter. Click a node to view its Order Narrative.")

    # ── Session state initialisation ─────────────────────────────────────
    if "hg_min_degree" not in st.session_state:
        st.session_state.hg_min_degree = 0
    if "hg_max_degree" not in st.session_state:
        st.session_state.hg_max_degree = 25
    if "hg_selected_node" not in st.session_state:
        st.session_state.hg_selected_node = None

    col_graph, col_narrative = st.columns([3, 1])

    with col_graph:
        # ── Hierarchy filter controls ─────────────────────────────────────
        st.markdown("#### 🎚️ Hierarchy Filter")

        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            hg_min = st.slider(
                "Min Degree",
                min_value=0,
                max_value=50,
                value=st.session_state.hg_min_degree,
                help="Show only nodes with degree ≥ this value.",
                key="hg_slider_min",
            )
            st.session_state.hg_min_degree = hg_min
        with filter_col2:
            hg_max = st.slider(
                "Max Degree",
                min_value=0,
                max_value=100,
                value=st.session_state.hg_max_degree,
                help="Show only nodes with degree ≤ this value.",
                key="hg_slider_max",
            )
            st.session_state.hg_max_degree = hg_max

        # Quick preset buttons
        preset_col1, preset_col2, preset_col3 = st.columns(3)
        with preset_col1:
            if st.button("📊 All Nodes", key="hg_btn_all"):
                st.session_state.hg_min_degree = 0
                st.session_state.hg_max_degree = 100
                st.rerun()
        with preset_col2:
            if st.button("🎯 Core Only", key="hg_btn_core"):
                st.session_state.hg_min_degree = 5
                st.session_state.hg_max_degree = 100
                st.rerun()
        with preset_col3:
            if st.button("💀 Backbone", key="hg_btn_backbone"):
                st.session_state.hg_min_degree = 10
                st.session_state.hg_max_degree = 100
                st.rerun()

        st.divider()

        # ── Fetch data from backend ───────────────────────────────────────
        with st.spinner("🔄 Loading hierarchical graph…"):
            hg_data = _api.get_hierarchical_graph(
                min_degree=st.session_state.hg_min_degree,
                max_degree=st.session_state.hg_max_degree,
            )

        if "error" in hg_data:
            st.error(f"❌ {hg_data['error']}")
        else:
            nodes_raw = hg_data.get("nodes", [])
            edges_raw = hg_data.get("edges", [])
            degree_map: Dict[str, int] = hg_data.get("degree_map", {})

            # ── Empty state ───────────────────────────────────────────────
            if not nodes_raw:
                total_nodes = hg_data.get("total_nodes", 0)
                if total_nodes == 0 and st.session_state.hg_min_degree == 0:
                    st.info(
                        "📭 **The knowledge graph is empty.**\n\n"
                        "Add data by extracting knowledge in the **📝 Text Extraction** tab "
                        "or seed the graph with example triples:"
                    )
                    if st.button("🌱 Seed Example Data", key="btn_seed_hg", type="primary"):
                        with st.spinner("Seeding knowledge graph with example triples…"):
                            seed_resp = _api.seed_knowledge_graph()
                        if seed_resp.get("status") == "ok":
                            st.success(seed_resp.get("message", "Seed triples added."))
                            st.rerun()
                        else:
                            st.error(f"Seeding failed: {seed_resp.get('error', seed_resp)}")
                else:
                    st.info(
                        "🔍 No nodes match the current degree filter "
                        f"(min={st.session_state.hg_min_degree}, "
                        f"max={st.session_state.hg_max_degree}). "
                        "Try clicking **📊 All Nodes** to reset the filter."
                    )
            else:
                # ── Build agraph nodes ────────────────────────────────────
                if _AGRAPH_AVAILABLE:
                    hg_ag_nodes: List[Node] = []
                    for node in nodes_raw:
                        node_id = node["id"]
                        node_degree = degree_map.get(node_id, 0)
                        tier, color, size = _node_visual(node_degree)

                        hg_ag_nodes.append(
                            Node(
                                id=node_id,
                                label=node_id,
                                size=size,
                                color=color,
                                title=f"{node_id}\nType: {node['type']}\nDegree: {node_degree}\nTier: {tier}",
                            )
                        )

                    # ── Build agraph edges ────────────────────────────────
                    hg_ag_edges: List[Edge] = []
                    for edge in edges_raw:
                        from_deg = degree_map.get(edge["from"], 0)
                        to_deg = degree_map.get(edge["to"], 0)

                        if from_deg >= 10 and to_deg >= 10:
                            edge_color, width = "#FFD700", 3
                        elif from_deg >= 5 or to_deg >= 5:
                            edge_color, width = "#4A90E2", 2
                        else:
                            edge_color, width = "#888888", 1

                        hg_ag_edges.append(
                            Edge(
                                source=edge["from"],
                                target=edge["to"],
                                label=edge.get("type", ""),
                                color=edge_color,
                                width=width,
                            )
                        )

                    # ── Render graph ──────────────────────────────────────
                    hg_config = Config(
                        width="100%",
                        height=800,
                        directed=True,
                        physics=True,
                        hierarchical=False,
                        nodeHighlightBehavior=True,
                        highlightColor="#FFD700",
                        collapsible=False,
                    )

                    st.markdown("#### 📊 Graph Visualization")
                    try:
                        clicked_node = agraph(
                            nodes=hg_ag_nodes,
                            edges=hg_ag_edges,
                            config=hg_config,
                        )
                        if clicked_node:
                            st.session_state.hg_selected_node = clicked_node
                    except Exception as render_err:
                        st.error(f"Graph rendering error: {render_err}")

                else:
                    st.warning(
                        "⚠️ `streamlit-agraph` is not installed. "
                        "Install it with `pip install streamlit-agraph` to enable interactive graph rendering."
                    )

            # ── Statistics panel ──────────────────────────────────────────
            st.markdown("---")
            stat_col1, stat_col2, stat_col3 = st.columns(3)
            with stat_col1:
                st.metric("Visible Nodes", len(nodes_raw))
            with stat_col2:
                st.metric("Visible Edges", len(edges_raw))
            with stat_col3:
                avg_deg = (
                    sum(degree_map.values()) / len(degree_map)
                    if degree_map else 0.0
                )
                st.metric("Avg Degree", f"{avg_deg:.1f}")

    # ── Right panel: Order Narrative ──────────────────────────────────────
    with col_narrative:
        st.markdown("#### 📖 Order Narrative")

        if st.session_state.hg_selected_node:
            selected_id: str = st.session_state.hg_selected_node

            with st.spinner(f"Loading narrative for {selected_id}…"):
                narrative = _api.get_node_narrative(selected_id)

            if "error" in narrative:
                st.error(f"❌ {narrative['error']}")
            else:
                st.subheader(f"🔹 {narrative.get('node_name', selected_id)}")
                st.write(f"**Type:** {narrative.get('node_type', '—')}")
                st.write(f"**Degree:** {narrative.get('degree', 0)}")
                st.write(f"**Tier:** {narrative.get('importance_tier', '—')}")

                st.divider()

                st.write("**Global Role:**")
                st.write(narrative.get("global_role", ""))

                definition = narrative.get("definition", "")
                if definition:
                    st.divider()
                    st.write("**Definition:**")
                    st.write(definition)

                connections = narrative.get("main_connections", [])
                if connections:
                    st.divider()
                    st.write("**Main Connections:**")
                    for conn in connections:
                        if "target" in conn:
                            st.write(f"→ **{conn['target']}** ({conn.get('relation', '')})")
                        else:
                            st.write(f"← **{conn['source']}** ({conn.get('relation', '')})")
        else:
            st.info("💡 Click a node on the graph to view its Order Narrative.")

        # ── Visual legend ─────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("**Node Tiers**")
        for _, label, color, size in _HG_TIERS:
            font_size = max(10, min(22, size // 4 + 8))
            st.markdown(
                f"<span style='color:{color};font-size:{font_size}px'>●</span> **{label}**",
                unsafe_allow_html=True,
            )

# ===========================================================================
# Tab 5 – Cypher Query
# ===========================================================================
with tab_query:
    st.subheader("💬 Cypher Query")
    st.caption("Cypher queries are supported with KuzuDB backend (`GRAPH_BACKEND=kuzu`).")

    default_cypher = "MATCH (e:Entity) RETURN e.name, e.type LIMIT 10"
    cypher_input = st.text_area(
        "Cypher query",
        value=st.session_state.kg_query_text or default_cypher,
        height=120,
        key="cypher_query_input",
        placeholder="MATCH (e:Entity) RETURN e.name, e.type LIMIT 10",
    )

    col_run, col_clr = st.columns([1, 5])
    with col_run:
        run_query = st.button("▶ Run Query", type="primary", key="btn_run_query")
    with col_clr:
        if st.button("🗑️ Clear results", key="btn_clear_query"):
            st.session_state.kg_query_result = []
            st.session_state.kg_query_text = ""
            st.rerun()

    if run_query:
        query_stripped = (cypher_input or "").strip()
        if not query_stripped:
            st.warning("⚠️ Please enter a Cypher query.")
        else:
            st.session_state.kg_query_text = query_stripped
            with st.spinner("⏳ Running query…"):
                query_resp = _api.run_kg_query(query_stripped)
            if "error" in query_resp and "results" not in query_resp:
                st.error(f"❌ Query failed: {query_resp['error']}")
            else:
                results = query_resp.get("results", [])
                st.session_state.kg_query_result = results
                if results:
                    st.success(f"✅ {len(results)} result(s) returned.")
                else:
                    st.info("Query succeeded, but no results found.")

    # Display cached query results
    cached_qr = st.session_state.kg_query_result
    if cached_qr:

        try:
            df_qr = pd.DataFrame(cached_qr)
            st.dataframe(df_qr, use_container_width=True, height=400)
        except Exception:
            st.json(cached_qr)
