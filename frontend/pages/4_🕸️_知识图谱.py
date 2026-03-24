"""
知识图谱页面 – 文本提取、可视化、Cypher 查询
================================================

功能:
  Tab 1 - 📝 文本提取: 输入文本 → 提取实体/关系 → 显示 Metrics 和表格
  Tab 2 - 🕸️ 图谱可视化: NetworkX 构建图 + streamlit-agraph 交互展示
  Tab 3 - 💬 Cypher 查询: 输入 Cypher → 执行 → 显示 DataFrame 结果

使用 st.session_state 缓存提取结果，避免重复调用后端。
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

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

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="知识图谱 – EL-DRUIN",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Backend client
# ---------------------------------------------------------------------------
_backend_url = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api/v1"
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

# ---------------------------------------------------------------------------
# Entity-type colour map (Dark Matter theme — muted tones on dark background)
# ---------------------------------------------------------------------------
_TYPE_COLORS: Dict[str, str] = {
    "PERSON":  "#D4AF37",  # Apostolic Gold
    "ORG":     "#A8A8A8",  # Dimmed Silver
    "GPE":     "#E0E0E0",  # Cold White
    "LOC":     "#B8931F",  # Dark Gold
    "DATE":    "#8B8B8B",  # Muted Grey
    "MONEY":   "#C8A85A",  # Warm Gold-Tan
    "PERCENT": "#D4AF37",  # Apostolic Gold
    "EVENT":   "#F0F0F0",  # Altar White
    "MISC":    "#555555",  # Dark Neutral
}
_DEFAULT_COLOR = "#555555"


def _entity_color(entity_type: str) -> str:
    return _TYPE_COLORS.get(entity_type.upper(), _DEFAULT_COLOR)


# ---------------------------------------------------------------------------
# Hierarchical graph tier constants — Dark Matter theme
# (thresholds must match backend/_importance_tier in knowledge.py)
# ---------------------------------------------------------------------------
_HG_TIERS = [
    # (min_degree, label, color, size)
    (10, "Critical",  "#D4AF37", 80),   # Apostolic Gold — core hubs
    (5,  "Important", "#2D333B", 50),   # Dark Grey-Blue — connectors
    (2,  "Bridge",    "#A8A8A8", 35),   # Dimmed Silver  — bridges
    (0,  "Leaf",      "#E0E0E0", 20),   # Cold White     — fringe
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
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40" width="32" height="32">
          <circle cx="20" cy="20" r="16" fill="none" stroke="#D4AF37" stroke-width="0.8"
                  stroke-dasharray="2 3.2"/>
          <line x1="20" y1="4" x2="20" y2="36" stroke="#D4AF37" stroke-width="1.6" stroke-linecap="round"/>
          <line x1="12" y1="14" x2="28" y2="14" stroke="#D4AF37" stroke-width="1.6" stroke-linecap="round"/>
          <line x1="16" y1="16" x2="24" y2="16" stroke="#D4AF37" stroke-width="0.8" stroke-linecap="round"/>
        </svg>
        <h1 style="color:#F0F0F0;margin:0;font-weight:300;letter-spacing:2px;
                   font-family:'Inter',sans-serif;">知识图谱</h1>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption("从文本中提取实体与关系，可视化知识图谱，并通过 Cypher 查询探索数据。")

st.divider()

# ===========================================================================
# Tabs
# ===========================================================================
tab_extract, tab_viz, tab_hierarchy, tab_query = st.tabs(
    ["📝 文本提取", "🕸️ 图谱可视化", "🎚️ 层级图谱", "💬 Cypher 查询"]
)

# ===========================================================================
# Tab 1 – 文本提取
# ===========================================================================
with tab_extract:
    st.subheader("📝 从文本中提取知识")

    input_text = st.text_area(
        "输入新闻文本",
        placeholder="请粘贴新闻文章内容（10 – 10000 字符）…",
        height=180,
        max_chars=10000,
        key="extract_input_text",
    )

    col_btn, col_clear = st.columns([1, 5])
    with col_btn:
        do_extract = st.button("⚔️ Manifest Knowledge", type="primary", key="btn_extract")
    with col_clear:
        if st.button("🗑️ 清除结果", key="btn_clear_extract"):
            st.session_state.kg_extract_result = {}
            st.rerun()

    # Validate and call backend
    if do_extract:
        text_stripped = (input_text or "").strip()
        if len(text_stripped) < 10:
            st.warning("⚠️ 文本太短，至少需要 10 个字符。")
        else:
            with st.spinner("🔍 正在提取实体和关系…"):
                result = _api.extract_knowledge(text_stripped)
            if result.get("status") == "error" or (
                "error" in result and "entities" not in result
            ):
                st.error(f"❌ 提取失败：{result.get('error', '未知错误')}")
            else:
                st.session_state.kg_extract_result = result
                st.success("✅ 提取完成！结果已缓存。")

    # Display cached results
    cached = st.session_state.kg_extract_result
    if cached:
        entities: List[Dict[str, Any]] = cached.get("entities", [])
        relations: List[Dict[str, Any]] = cached.get("relations", [])
        # Triples = relations expressed as (subject, predicate, object)
        triples = [
            {
                "主体 (Subject)": r.get("subject", ""),
                "关系 (Predicate)": r.get("predicate", ""),
                "客体 (Object)": r.get("object", ""),
            }
            for r in relations
        ]

        # ── Metrics ──────────────────────────────────────────────────────────
        st.markdown("#### 📊 提取摘要")
        m1, m2, m3 = st.columns(3)
        m1.metric("🔵 实体数", len(entities))
        m2.metric("🔗 关系数", len(relations))
        m3.metric("📐 三元组数", len(triples))

        st.divider()

        # ── Entities table ────────────────────────────────────────────────────
        st.markdown("#### 📋 提取的实体")
        if entities:
            df_entities = pd.DataFrame(
                [
                    {
                        "名称": e.get("name", ""),
                        "类型": e.get("type", ""),
                        "描述": e.get("description", ""),
                        "置信度": round(float(e.get("confidence", 0)), 3),
                    }
                    for e in entities
                ]
            )
            st.dataframe(df_entities, use_container_width=True, height=250)
        else:
            st.info("未提取到实体。")

        # ── Relations table ───────────────────────────────────────────────────
        st.markdown("#### 🔗 提取的关系")
        if relations:
            df_relations = pd.DataFrame(
                [
                    {
                        "源 (Subject)": r.get("subject", ""),
                        "关系类型 (Predicate)": r.get("predicate", ""),
                        "目标 (Object)": r.get("object", ""),
                    }
                    for r in relations
                ]
            )
            st.dataframe(df_relations, use_container_width=True, height=250)
        else:
            st.info("未提取到关系。")

        # ── Triples table ─────────────────────────────────────────────────────
        if triples:
            st.markdown("#### 📐 三元组列表")
            st.dataframe(pd.DataFrame(triples), use_container_width=True, height=200)

    elif not do_extract:
        st.info("👆 在上方输入文本，然后点击「🔄 提取并存储」按钮开始提取。")

# ===========================================================================
# Tab 2 – 图谱可视化
# ===========================================================================
with tab_viz:
    st.subheader("🕸️ 知识图谱可视化")

    # ── Data source selector ─────────────────────────────────────────────────
    data_source = st.radio(
        "数据来源",
        ["使用提取结果（Tab 1）", "从图数据库加载"],
        horizontal=True,
        key="viz_data_source",
    )

    viz_entities: List[Dict[str, Any]] = []
    viz_relations: List[Dict[str, Any]] = []

    if data_source == "使用提取结果（Tab 1）":
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
            st.info("👆 请先在「📝 文本提取」标签中提取知识，或切换到「从图数据库加载」。")
    else:
        with st.spinner("📡 正在从数据库加载实体和关系…"):
            ent_resp = _api.get_kg_entities(limit=200)
            rel_resp = _api.get_kg_relations(limit=300)
        if "error" in ent_resp:
            st.error(f"❌ 加载实体失败：{ent_resp['error']}")
        elif "error" in rel_resp:
            st.error(f"❌ 加载关系失败：{rel_resp['error']}")
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
            f"图谱共 **{G.number_of_nodes()}** 个节点，**{G.number_of_edges()}** 条边"
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
                        title=f"{node_name}\n类型: {etype}",
                    )
                )
            for src, tgt, data in G.edges(data=True):
                edges.append(
                    Edge(
                        source=src,
                        target=tgt,
                        label=data.get("label", ""),
                        color="rgba(85,85,85,0.4)",
                    )
                )

            config = Config(
                width="100%",
                height=550,
                directed=True,
                physics=True,
                hierarchical=False,
                nodeHighlightBehavior=True,
                highlightColor="#D4AF37",
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
                        line={"width": 0.5, "color": "rgba(85,85,85,0.4)"},
                        hoverinfo="none",
                    ),
                    go.Scatter(
                        x=node_x, y=node_y, mode="markers+text",
                        text=node_text, textposition="top center",
                        textfont={"color": "#A8A8A8", "size": 10},
                        marker={"size": 14, "color": node_colors,
                                "line": {"width": 1, "color": "#2D333B"}},
                        hoverinfo="text",
                    ),
                ],
                layout=go.Layout(
                    title={"text": "知识图谱网络图", "font": {"color": "#F0F0F0"}},
                    showlegend=False,
                    hovermode="closest",
                    paper_bgcolor="#0D0D0D",
                    plot_bgcolor="#0D0D0D",
                    xaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
                    yaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
                    height=550,
                    margin={"t": 40, "b": 0, "l": 0, "r": 0},
                ),
            )
            st.plotly_chart(fig_net, use_container_width=True)

    elif data_source == "从图数据库加载":
        if "error" not in _api.get_kg_stats():
            st.info("📭 图谱中暂无数据。请先通过「更新图谱」进行数据摄入。")

# ===========================================================================
# Tab 3 – 层级图谱 (Hierarchical Graph)
# ===========================================================================
with tab_hierarchy:
    st.subheader("🎚️ Hierarchical Knowledge Graph")
    st.caption("通过度数过滤器调整节点可见性，点击节点查看其「秩序叙事」。")

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
                help="只显示度数 ≥ 此值的节点",
                key="hg_slider_min",
            )
            st.session_state.hg_min_degree = hg_min
        with filter_col2:
            hg_max = st.slider(
                "Max Degree",
                min_value=0,
                max_value=100,
                value=st.session_state.hg_max_degree,
                help="只显示度数 ≤ 此值的节点",
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

            # ── Build agraph nodes ────────────────────────────────────────
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

                # ── Build agraph edges ────────────────────────────────────
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

                # ── Render graph ──────────────────────────────────────────
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
# Tab 4 – Cypher 查询
# ===========================================================================
with tab_query:
    st.subheader("💬 Cypher 查询")
    st.caption("仅 Kuzu 后端支持 Cypher 查询（需设置 `GRAPH_BACKEND=kuzu`）。")

    default_cypher = "MATCH (e:Entity) RETURN e.name, e.type LIMIT 10"
    cypher_input = st.text_area(
        "Cypher 查询语句",
        value=st.session_state.kg_query_text or default_cypher,
        height=120,
        key="cypher_query_input",
        placeholder="MATCH (e:Entity) RETURN e.name, e.type LIMIT 10",
    )

    col_run, col_clr = st.columns([1, 5])
    with col_run:
        run_query = st.button("▶ 执行查询", type="primary", key="btn_run_query")
    with col_clr:
        if st.button("🗑️ 清除结果", key="btn_clear_query"):
            st.session_state.kg_query_result = []
            st.session_state.kg_query_text = ""
            st.rerun()

    if run_query:
        query_stripped = (cypher_input or "").strip()
        if not query_stripped:
            st.warning("⚠️ 请输入 Cypher 查询语句。")
        else:
            st.session_state.kg_query_text = query_stripped
            with st.spinner("⏳ 正在执行查询…"):
                query_resp = _api.run_kg_query(query_stripped)
            if "error" in query_resp and "results" not in query_resp:
                st.error(f"❌ 查询失败：{query_resp['error']}")
            else:
                results = query_resp.get("results", [])
                st.session_state.kg_query_result = results
                if results:
                    st.success(f"✅ 返回 {len(results)} 条结果。")
                else:
                    st.info("查询成功，但无结果。")

    # Display cached query results
    cached_qr = st.session_state.kg_query_result
    if cached_qr:

        try:
            df_qr = pd.DataFrame(cached_qr)
            st.dataframe(df_qr, use_container_width=True, height=400)
        except Exception:
            st.json(cached_qr)
