"""
EL'druin Intelligence Platform – Streamlit Frontend
====================================================

Multi-page application providing:
  📰  Real-time News   – aggregated news with filtering and search
  🔍  Event Monitoring – extracted events with severity breakdown
  📊  Dashboard        – system-wide metrics and trend overview
  ⚙️   System Status   – backend health and source configuration

Run::

    streamlit run frontend/app.py

The app expects the FastAPI backend to be reachable at
http://localhost:8001/api/v1 (configurable via BACKEND_URL env var).
"""

import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import streamlit as st

# Allow ``from utils.api_client import api_client`` when the working directory
# is the repo root *or* the frontend directory.
_FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _FRONTEND_DIR not in sys.path:
    sys.path.insert(0, _FRONTEND_DIR)

from utils.api_client import APIClient  # noqa: E402 – after sys.path patch

# streamlit-agraph (optional – graceful degradation when absent)
try:
    from streamlit_agraph import agraph, Config, Edge, Node  # type: ignore[import]

    _AGRAPH_AVAILABLE = True
except ImportError:
    _AGRAPH_AVAILABLE = False

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page configuration (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="EL'druin Intelligence Platform",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Minimal custom CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .main { padding: 0rem 1rem; }
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 5px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Backend URL (env-configurable)
# ---------------------------------------------------------------------------
_backend_url = os.environ.get("BACKEND_URL", "http://localhost:8001/api/v1")
_api = APIClient(base_url=_backend_url)

# ---------------------------------------------------------------------------
# Sidebar – navigation
# ---------------------------------------------------------------------------
st.sidebar.title("🧠 EL'druin")
st.sidebar.markdown("---")
st.sidebar.subheader("企业级智能平台")

page = st.sidebar.radio(
    "导航菜单",
    [
        "📰 实时新闻",
        "🔍 事件监控",
        "🕸️ 知识图谱",
        "📊 仪表板",
        "⚙️ 系统状态",
    ],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
st.sidebar.info(
    "**EL'druin Intelligence Platform**\n\n"
    "- 实时新闻聚合\n"
    "- 自动事件提取\n"
    "- 知识图谱分析\n"
    "- 预测和预警"
)

# ===========================================================================
# Knowledge graph helpers
# ===========================================================================

# Entity-type → colour mapping (shared across all graph renders)
_KG_TYPE_COLORS: Dict[str, str] = {
    "PERSON": "#e74c3c",
    "ORG": "#3498db",
    "GPE": "#2ecc71",
    "LOC": "#f39c12",
    "DATE": "#9b59b6",
    "MONEY": "#1abc9c",
    "PERCENT": "#e67e22",
    "EVENT": "#e91e63",
    "ENTITY": "#3498db",
    "ARTICLE": "#f39c12",
    "MISC": "#95a5a6",
}
_KG_DEFAULT_COLOR = "#95a5a6"


def render_graph(data: Dict[str, Any]) -> None:
    """Render an interactive knowledge graph using streamlit-agraph.

    Converts the standardised backend response format into agraph Node / Edge
    objects and displays a physics-enabled, zoomable, draggable graph.

    Args:
        data: Dict with two keys:

            * ``nodes`` – list of dicts ``{id, label, properties}``
            * ``edges`` – list of dicts ``{from, to, type}``

    The function shows a friendly info banner instead of raising when data is
    empty or when the optional ``streamlit-agraph`` package is unavailable.
    """
    raw_nodes: List[Dict[str, Any]] = data.get("nodes", []) if data else []
    raw_edges: List[Dict[str, Any]] = data.get("edges", []) if data else []

    if not raw_nodes and not raw_edges:
        st.info("📭 暂无图谱数据。请先进行数据摄入或执行 Cypher 查询。")
        return

    if not _AGRAPH_AVAILABLE:
        st.warning(
            "⚠️ `streamlit-agraph` 未安装，无法显示交互图谱。"
            " 请执行 `pip install streamlit-agraph>=0.0.45`"
        )
        return

    # ── Pre-compute node degree for size scaling ──────────────────────────
    degree: Dict[str, int] = {}
    for edge in raw_edges:
        src = str(edge.get("from", "") or "")
        tgt = str(edge.get("to", "") or "")
        if src:
            degree[src] = degree.get(src, 0) + 1
        if tgt:
            degree[tgt] = degree.get(tgt, 0) + 1

    # ── Build agraph Node objects ─────────────────────────────────────────
    ag_nodes: List[Node] = []
    for node in raw_nodes:
        node_id = str(node.get("id", "") or "")
        if not node_id:
            continue
        label_type = str(node.get("label", "MISC") or "MISC")
        color = _KG_TYPE_COLORS.get(label_type.upper(), _KG_DEFAULT_COLOR)
        # Size: base 20 plus up to 20 extra points scaled by degree (capped)
        node_degree = degree.get(node_id, 0)
        size = 20 + min(node_degree * 3, 20)
        props: Dict[str, Any] = node.get("properties") or {}
        display_name = str(props.get("name", node_id))
        tooltip_lines = [f"{display_name}", f"类型: {label_type}"]
        for k, v in list(props.items())[:5]:
            if k != "name":
                tooltip_lines.append(f"{k}: {v}")
        ag_nodes.append(
            Node(
                id=node_id,
                label=display_name,
                size=size,
                color=color,
                title="\n".join(tooltip_lines),
            )
        )

    # ── Build agraph Edge objects ─────────────────────────────────────────
    ag_edges: List[Edge] = []
    for edge in raw_edges:
        src = str(edge.get("from", "") or "")
        tgt = str(edge.get("to", "") or "")
        edge_type = str(edge.get("type", "") or "")
        if src and tgt:
            ag_edges.append(
                Edge(
                    source=src,
                    target=tgt,
                    label=edge_type,
                    color="#888888",
                )
            )

    if not ag_nodes:
        st.info("📭 节点数据为空，无法渲染图谱。")
        return

    config = Config(
        width="100%",
        height=550,
        directed=True,
        physics=True,
        hierarchical=False,
        nodeHighlightBehavior=True,
        highlightColor="#f1c40f",
        collapsible=False,
    )

    with st.container():
        agraph(nodes=ag_nodes, edges=ag_edges, config=config)


# ===========================================================================
# Page: 📰 实时新闻
# ===========================================================================
if page == "📰 实时新闻":
    st.title("📰 实时世界新闻")

    # ── Top controls ────────────────────────────────────────────────────────
    col_title, col_refresh = st.columns([3, 1])
    with col_title:
        st.subheader("新闻源和筛选")
    with col_refresh:
        if st.button("🔄 立即刷新", key="refresh_news"):
            with st.spinner("📡 正在聚合新闻…"):
                result = _api.ingest_news()
                if "error" not in result:
                    st.success("✅ 新闻聚合完成！")
                else:
                    st.error(f"❌ 错误：{result['error']}")

    # ── Filter sliders ───────────────────────────────────────────────────────
    col_hours, col_limit = st.columns(2)
    with col_hours:
        hours = st.slider("时间范围（小时）", min_value=1, max_value=168, value=24)
    with col_limit:
        limit = st.slider("显示条数", min_value=5, max_value=100, value=20)

    search_query = st.text_input("🔍 关键词搜索", placeholder="输入关键词…")

    # ── Fetch articles ───────────────────────────────────────────────────────
    st.subheader("最新文章")

    if search_query:
        data = _api.search_news(search_query, limit=limit)
    else:
        data = _api.get_latest_news(limit=limit, hours=hours)

    if "error" in data:
        st.error(
            f"❌ 无法获取新闻：{data['error']}\n\n"
            "请确认后端正在运行：`python -m uvicorn app.main:app --port 8001`"
        )
    else:
        articles: List[Dict[str, Any]] = data.get("articles", [])

        if search_query:
            st.info(f"🔍 共找到 {len(articles)} 条结果")

        # ── Metrics ─────────────────────────────────────────────────────────
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📰 文章总数", len(articles))
        m2.metric("📂 分类数", len({a.get("category", "?") for a in articles}))
        m3.metric("🏢 新闻源数", len({a.get("source", "?") for a in articles}))
        m4.metric("⏰ 时间范围", f"{hours} 小时")

        st.divider()

        # Session-state cache: {article_cache_key -> kg extraction result}
        if "kg_cache" not in st.session_state:
            st.session_state.kg_cache = {}

        import hashlib as _hashlib  # stable across process restarts (unlike built-in hash())

        if articles:
            for i, article in enumerate(articles, 1):
                title_preview = (article.get("title") or "（无标题）")[:80]
                # Stable cache key: hashlib md5 of article URL or title (not process-bound)
                _key_src = (article.get("link") or article.get("title") or str(i)).encode("utf-8", errors="replace")
                _cache_key = f"kg_{_hashlib.md5(_key_src).hexdigest()}"

                with st.expander(f"🔹 [{i}] {title_preview}…", expanded=False):
                    c1, c2, c3 = st.columns(3)
                    c1.caption(f"📌 来源：{article.get('source', 'N/A')}")
                    c2.caption(f"📍 分类：{article.get('category', 'N/A')}")
                    c3.caption(f"⏰ 时间：{str(article.get('published', 'N/A'))[:10]}")
                    st.write(article.get("description") or "（暂无摘要）")
                    if article.get("link"):
                        st.markdown(f"[📖 阅读原文]({article['link']})")

                    # ── Knowledge Graph extraction ────────────────────────────
                    already_extracted = _cache_key in st.session_state.kg_cache
                    btn_label = "✅ 已提取知识图" if already_extracted else "🧠 提取知识图"
                    if st.button(btn_label, key=f"kg_btn_{i}"):
                        _text = " ".join(
                            filter(None, [
                                article.get("title", ""),
                                article.get("description", ""),
                            ])
                        ).strip()
                        if _text:
                            with st.spinner("提取中..."):
                                _kg_resp = _api.extract_knowledge(_text)
                            if _kg_resp.get("status") == "error" or (
                                "error" in _kg_resp and "entities" not in _kg_resp
                            ):
                                st.error(f"❌ 知识图提取失败：{_kg_resp['error']}")
                            else:
                                st.session_state.kg_cache[_cache_key] = _kg_resp
                                st.rerun()
                        else:
                            st.warning("⚠️ 该文章暂无文本内容可供提取。")

                    # ── Display cached KG results ─────────────────────────────
                    if _cache_key in st.session_state.kg_cache:
                        _kg_data = st.session_state.kg_cache[_cache_key]
                        _entities_kg: List[Dict[str, Any]] = _kg_data.get("entities", [])
                        _relations_kg: List[Dict[str, Any]] = _kg_data.get("relations", [])

                        with st.expander(
                            f"🕸️ 知识图谱结果（实体: {len(_entities_kg)}, 关系: {len(_relations_kg)}）",
                            expanded=True,
                        ):
                            if _entities_kg:
                                st.write("**📋 实体**")
                                try:
                                    import pandas as pd
                                    _ent_df = pd.DataFrame([
                                        {
                                            "name": e.get("name", ""),
                                            "type": e.get("type", ""),
                                            "description": e.get("description", ""),
                                            "confidence": e.get("confidence", ""),
                                        }
                                        for e in _entities_kg
                                    ])
                                    st.dataframe(_ent_df, use_container_width=True)
                                except ImportError:
                                    for _e in _entities_kg:
                                        st.write(f"- **{_e.get('name')}** ({_e.get('type', '?')})")
                            else:
                                st.info("未提取到实体。")

                            if _relations_kg:
                                st.write("**🔗 关系**")
                                try:
                                    import pandas as pd
                                    _rel_df = pd.DataFrame([
                                        {
                                            "subject": r.get("subject", ""),
                                            "predicate": r.get("predicate", ""),
                                            "object": r.get("object", ""),
                                        }
                                        for r in _relations_kg
                                    ])
                                    st.dataframe(_rel_df, use_container_width=True)
                                except ImportError:
                                    for _r in _relations_kg:
                                        st.write(
                                            f"- {_r.get('subject')} "
                                            f"–[{_r.get('predicate')}]→ "
                                            f"{_r.get('object')}"
                                        )

                            # ── Interactive graph visualisation ────────────────
                            if _entities_kg and _relations_kg:
                                st.write("**🌐 图谱可视化**")
                                _COLOR_MAP = {
                                    "PERSON": "#e74c3c",
                                    "ORG": "#3498db",
                                    "GPE": "#2ecc71",
                                    "EVENT": "#f39c12",
                                }
                                try:
                                    from streamlit_agraph import (
                                        Config,
                                        Edge,
                                        Node,
                                        agraph,
                                    )

                                    _ag_nodes = [
                                        Node(
                                            id=_e["name"],
                                            label=_e["name"],
                                            size=25,
                                            color=_COLOR_MAP.get(_e.get("type", ""), "#95a5a6"),
                                        )
                                        for _e in _entities_kg
                                    ]
                                    _ag_edges = [
                                        Edge(
                                            source=_r["subject"],
                                            target=_r["object"],
                                            label=_r.get("predicate", ""),
                                        )
                                        for _r in _relations_kg
                                        if _r.get("subject") and _r.get("object")
                                    ]
                                    _ag_config = Config(
                                        width=700,
                                        height=400,
                                        directed=True,
                                        physics=True,
                                        hierarchical=False,
                                    )
                                    agraph(nodes=_ag_nodes, edges=_ag_edges, config=_ag_config)
                                except ImportError:
                                    # Fallback: plotly + networkx (already in requirements)
                                    try:
                                        import networkx as nx
                                        import plotly.graph_objects as go

                                        _G = nx.DiGraph()
                                        for _r in _relations_kg:
                                            if _r.get("subject") and _r.get("object"):
                                                _G.add_edge(
                                                    _r["subject"],
                                                    _r["object"],
                                                    label=_r.get("predicate", ""),
                                                )
                                        if _G.nodes():
                                            _pos = nx.spring_layout(_G, seed=42)
                                            _ex, _ey = [], []
                                            for _u, _v in _G.edges():
                                                _x0, _y0 = _pos[_u]
                                                _x1, _y1 = _pos[_v]
                                                _ex += [_x0, _x1, None]
                                                _ey += [_y0, _y1, None]
                                            _fig_kg = go.Figure(
                                                data=[
                                                    go.Scatter(
                                                        x=_ex, y=_ey, mode="lines",
                                                        line={"width": 1, "color": "#888"},
                                                        hoverinfo="none",
                                                    ),
                                                    go.Scatter(
                                                        x=[_pos[n][0] for n in _G.nodes()],
                                                        y=[_pos[n][1] for n in _G.nodes()],
                                                        mode="markers+text",
                                                        text=list(_G.nodes()),
                                                        textposition="top center",
                                                        marker={"size": 12, "color": "#3498db"},
                                                        hoverinfo="text",
                                                    ),
                                                ],
                                                layout=go.Layout(
                                                    showlegend=False,
                                                    hovermode="closest",
                                                    height=400,
                                                    xaxis={
                                                        "showgrid": False,
                                                        "zeroline": False,
                                                        "showticklabels": False,
                                                    },
                                                    yaxis={
                                                        "showgrid": False,
                                                        "zeroline": False,
                                                        "showticklabels": False,
                                                    },
                                                ),
                                            )
                                            st.plotly_chart(_fig_kg, use_container_width=True)
                                    except ImportError:
                                        pass
        else:
            st.warning("⚠️ 暂无文章，请先点击「立即刷新」聚合新闻。")

# ===========================================================================
# Page: 🔍 事件监控
# ===========================================================================
elif page == "🔍 事件监控":
    st.title("🔍 实时事件监控")

    col_title, col_refresh = st.columns([3, 1])
    with col_title:
        st.subheader("已提取的事件")
    with col_refresh:
        if st.button("🔄 刷新事件", key="refresh_events"):
            st.rerun()

    # ── Filters ─────────────────────────────────────────────────────────────
    _EVENT_TYPES = [
        "全部", "政治冲突", "经济危机", "自然灾害",
        "恐怖袭击", "技术突破", "军事行动", "贸易摩擦",
        "外交事件", "人道危机",
    ]

    f1, f2 = st.columns(2)
    with f1:
        selected_type = st.selectbox("事件类型", _EVENT_TYPES)
    with f2:
        selected_severity = st.selectbox("严重级别", ["全部", "high", "medium", "low"])

    event_type_param: Optional[str] = None if selected_type == "全部" else selected_type
    severity_param: Optional[str] = None if selected_severity == "全部" else selected_severity

    # ── Fetch events ─────────────────────────────────────────────────────────
    data = _api.get_extracted_events(
        event_type=event_type_param,
        severity=severity_param,
        limit=50,
    )

    if "error" in data:
        st.error(
            f"❌ 无法获取事件：{data['error']}\n\n"
            "请确认后端正在运行。"
        )
    else:
        events: List[Dict[str, Any]] = data.get("events", [])

        if events:
            # ── Metrics ─────────────────────────────────────────────────────
            high_count = sum(1 for e in events if e.get("severity") == "high")
            confidences = [float(e["confidence"]) for e in events if "confidence" in e]
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

            m1, m2, m3 = st.columns(3)
            m1.metric("🎯 事件总数", len(events))
            m2.metric("🔴 高危事件", high_count)
            m3.metric("📊 平均置信度", f"{avg_conf:.1%}")

            st.divider()

            _SEV_ICON = {"high": "🔴", "medium": "🟡", "low": "🟢"}

            for event in events:
                sev = event.get("severity", "")
                icon = _SEV_ICON.get(sev, "⚪")
                label = (
                    f"{icon} {event.get('event_type', '?')} – "
                    f"{str(event.get('title', '（无标题）'))[:60]}…"
                )
                with st.expander(label, expanded=False):
                    c1, c2, c3 = st.columns(3)
                    c1.metric("事件类型", event.get("event_type", "?"))
                    c2.metric("严重级别", sev.upper() if sev else "?")
                    c3.metric("置信度", f"{event.get('confidence', 0):.1%}")

                    st.write(event.get("description") or "（暂无描述）")

                    entities = event.get("entities") or {}
                    if any(entities.values()):
                        st.write("**提取的实体：**")
                        ec1, ec2 = st.columns(2)
                        with ec1:
                            if entities.get("PERSON"):
                                st.write(f"👤 人物：{', '.join(entities['PERSON'][:3])}")
                            if entities.get("ORG"):
                                st.write(f"🏢 组织：{', '.join(entities['ORG'][:3])}")
                        with ec2:
                            if entities.get("GPE"):
                                st.write(f"🌍 地点：{', '.join(entities['GPE'][:3])}")
                            if entities.get("EVENT"):
                                st.write(f"📌 事件：{', '.join(entities['EVENT'][:3])}")
        else:
            st.info("📭 暂无相关事件。请先聚合新闻并触发事件提取。")

# ===========================================================================
# Page: 🕸️ 知识图谱
# ===========================================================================
elif page == "🕸️ 知识图谱":
    st.title("🕸️ 知识图谱")

    col_title, col_btn = st.columns([3, 1])
    with col_title:
        st.subheader("实体与关系网络")
    with col_btn:
        if st.button("🔄 更新图谱", key="ingest_kg"):
            with st.spinner("📡 正在提取实体并构建知识图谱…"):
                result = _api.ingest_knowledge_graph(limit=100, hours=24)
                if "error" not in result:
                    ingested = result.get("ingested", {})
                    st.success(
                        f"✅ 知识图谱已更新！"
                        f" 文章: {ingested.get('articles_added', 0)}"
                        f" | 实体: {ingested.get('entities_added', 0)}"
                        f" | 关系: {ingested.get('relations_added', 0)}"
                    )
                else:
                    st.error(f"❌ 错误：{result['error']}")

    # ── Stats ─────────────────────────────────────────────────────────────────
    stats_resp = _api.get_kg_stats()
    if "error" not in stats_resp:
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("🔵 实体节点", stats_resp.get("entities", 0))
        s2.metric("📰 文章节点", stats_resp.get("articles", 0))
        s3.metric("🔗 提及关系", stats_resp.get("mentions", 0))
        s4.metric("⚡ 实体关系", stats_resp.get("relations", 0))
    else:
        st.warning("⚠️ 无法获取图谱统计，请确认后端正在运行。")

    st.divider()

    # ── Main layout: interactive graph (left) | Cypher chat (right) ──────────
    col_graph, col_chat = st.columns([3, 2], gap="medium")

    with col_graph:
        st.subheader("🕸️ 图谱可视化")

        # Fetch entities and relations from the backend
        with st.spinner("📡 加载图谱数据…"):
            _ent_resp = _api.get_kg_entities(limit=200)
            _rel_resp = _api.get_kg_relations(limit=300)

        if "error" in _ent_resp or "error" in _rel_resp:
            st.warning("⚠️ 无法加载图谱数据，请确认后端正在运行。")
        else:
            _entities_for_graph: List[Dict[str, Any]] = _ent_resp.get("entities", [])
            _relations_for_graph: List[Dict[str, Any]] = _rel_resp.get("relations", [])

            # ── Colour legend ─────────────────────────────────────────────
            _present_types = sorted({
                str(e.get("type", "MISC")).upper()
                for e in _entities_for_graph
            })
            if _present_types:
                _legend_cols = st.columns(min(len(_present_types), 6))
                for _idx, _etype in enumerate(_present_types):
                    _col = _legend_cols[_idx % len(_legend_cols)]
                    _col.markdown(
                        f"<span style='color:{_KG_TYPE_COLORS.get(_etype, _KG_DEFAULT_COLOR)};"
                        f"font-size:16px'>●</span> **{_etype}**",
                        unsafe_allow_html=True,
                    )

            # Convert API response to render_graph format:
            #   nodes: {id, label, properties}
            #   edges: {from, to, type}
            _known_node_ids = {
                e.get("name", "") for e in _entities_for_graph if e.get("name")
            }
            _graph_data: Dict[str, Any] = {
                "nodes": [
                    {
                        "id": e.get("name", ""),
                        "label": str(e.get("type", "MISC")).upper(),
                        "properties": e,
                    }
                    for e in _entities_for_graph
                    if e.get("name")
                ],
                "edges": [
                    {
                        "from": r.get("from", ""),
                        "to": r.get("to", ""),
                        "type": r.get("relation", ""),
                    }
                    for r in _relations_for_graph
                    if r.get("from") in _known_node_ids
                    and r.get("to") in _known_node_ids
                ],
            }

            st.caption(
                f"图谱共 **{len(_graph_data['nodes'])}** 个节点，"
                f"**{len(_graph_data['edges'])}** 条边"
            )
            render_graph(_graph_data)

    # ── Right column: Cypher chat panel ──────────────────────────────────────
    with col_chat:
        st.subheader("💬 Cypher 查询")
        st.caption("仅 Kuzu 后端支持 Cypher 查询（需设置 `GRAPH_BACKEND=kuzu`）。")

        # Session state for chat-style query history
        if "kg_chat_history" not in st.session_state:
            st.session_state.kg_chat_history: List[Dict[str, Any]] = []

        _default_cypher = "MATCH (e:Entity) RETURN e.name, e.type LIMIT 10"
        _cypher_input = st.text_area(
            "Cypher 查询语句",
            value=_default_cypher,
            height=100,
            key="kg_cypher_input_main",
            placeholder="MATCH (e:Entity) RETURN e.name, e.type LIMIT 10",
        )

        _c1, _c2 = st.columns([1, 1])
        with _c1:
            _run_query = st.button("▶ 执行查询", type="primary", key="kg_run_query_main")
        with _c2:
            if st.button("🗑️ 清除历史", key="kg_clear_history"):
                st.session_state.kg_chat_history = []
                st.rerun()

        if _run_query:
            _q = (_cypher_input or "").strip()
            if not _q:
                st.warning("⚠️ 请输入 Cypher 查询语句。")
            else:
                with st.spinner("⏳ 执行中…"):
                    _qr = _api.run_kg_query(_q)
                _entry: Dict[str, Any] = {"query": _q, "response": _qr}
                st.session_state.kg_chat_history.insert(0, _entry)

        # Display chat-style history
        _chat_container = st.container()
        with _chat_container:
            for _item in st.session_state.kg_chat_history:
                st.markdown(
                    f"<div style='background:#f0f2f6;border-radius:6px;"
                    f"padding:8px 12px;margin-bottom:4px;font-family:monospace;"
                    f"font-size:13px'>{_item['query']}</div>",
                    unsafe_allow_html=True,
                )
                _resp = _item["response"]
                if "error" in _resp and "results" not in _resp:
                    st.error(f"❌ {_resp['error']}")
                else:
                    _results = _resp.get("results", [])
                    if _results:
                        st.success(f"✅ {len(_results)} 条结果")
                        try:
                            import pandas as pd
                            st.dataframe(
                                pd.DataFrame(_results),
                                use_container_width=True,
                                height=200,
                            )
                        except Exception:
                            st.caption("（表格渲染失败，以 JSON 格式展示）")
                            st.json(_results)
                    else:
                        st.info("查询成功，但无结果。")
                st.markdown("---")

    st.divider()

    # ── Detail tabs: entities, relations, neighbours ──────────────────────────
    tab_entities, tab_relations, tab_neighbours = st.tabs(
        ["📋 实体列表", "🔗 关系列表", "🔍 邻居查询"]
    )

    # ── Entities ─────────────────────────────────────────────────────────────
    with tab_entities:
        entities_resp = _api.get_kg_entities(limit=200)
        if "error" in entities_resp:
            st.error(f"❌ {entities_resp['error']}")
        else:
            entities_list: List[Dict[str, Any]] = entities_resp.get("entities", [])
            if entities_list:
                try:
                    import pandas as pd
                    df = pd.DataFrame(entities_list)
                    st.dataframe(df, use_container_width=True, height=400)
                except ImportError:
                    for e in entities_list:
                        st.write(f"**{e.get('name')}** ({e.get('type', '?')})")
            else:
                st.info("📭 图谱中暂无实体。请点击「更新图谱」按钮先进行数据摄入。")

    # ── Relations ─────────────────────────────────────────────────────────────
    with tab_relations:
        relations_resp = _api.get_kg_relations(limit=300)
        if "error" in relations_resp:
            st.error(f"❌ {relations_resp['error']}")
        else:
            relations_list: List[Dict[str, Any]] = relations_resp.get("relations", [])
            if relations_list:
                try:
                    import pandas as pd
                    df_rel = pd.DataFrame(relations_list)
                    st.dataframe(df_rel, use_container_width=True, height=400)
                except ImportError:
                    for r in relations_list:
                        st.write(f"**{r.get('from')}** –[{r.get('relation')}]→ **{r.get('to')}**")
            else:
                st.info("📭 图谱中暂无关系。请先进行数据摄入。")

    # ── Neighbours ────────────────────────────────────────────────────────────
    with tab_neighbours:
        entity_query = st.text_input("输入实体名称", placeholder="例如：Federal Reserve")
        if entity_query:
            nbr_resp = _api.get_kg_neighbours(entity_query)
            if "error" in nbr_resp:
                st.error(f"❌ {nbr_resp['error']}")
            else:
                neighbours: List[Dict[str, Any]] = nbr_resp.get("neighbours", [])
                if neighbours:
                    st.success(f"找到 {len(neighbours)} 个邻居节点")
                    try:
                        import pandas as pd
                        st.dataframe(pd.DataFrame(neighbours), use_container_width=True)
                    except ImportError:
                        for n in neighbours:
                            st.write(f"→ **{n.get('name')}** ({n.get('type')}) via [{n.get('relation')}]")

# ===========================================================================
# Page: 📊 仪表板
# ===========================================================================
elif page == "📊 仪表板":
    st.title("📊 系统仪表板")

    # ── Try to pull live data; fall back to placeholder values ───────────────
    news_data = _api.get_latest_news(limit=100, hours=24)
    events_data = _api.get_extracted_events(limit=100)

    articles_live = news_data.get("articles", []) if "error" not in news_data else []
    events_live = events_data.get("events", []) if "error" not in events_data else []

    total_news = len(articles_live) if articles_live else "–"
    total_events = len(events_live) if events_live else "–"
    high_events = (
        sum(1 for e in events_live if e.get("severity") == "high")
        if events_live
        else "–"
    )
    avg_conf_str = (
        f"{sum(float(e.get('confidence', 0)) for e in events_live) / len(events_live):.1%}"
        if events_live
        else "–"
    )

    # ── Top-line metrics ─────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📰 今日新闻", total_news)
    m2.metric("🎯 提取事件", total_events)
    m3.metric("🔴 高危事件", high_events)
    m4.metric("📊 平均置信度", avg_conf_str)

    # ── Knowledge graph metrics ───────────────────────────────────────────────
    kg_stats_resp = _api.get_kg_stats()
    if "error" not in kg_stats_resp:
        st.subheader("🕸️ 知识图谱")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("🔵 实体", kg_stats_resp.get("entities", 0))
        k2.metric("📰 文章", kg_stats_resp.get("articles", 0))
        k3.metric("🔗 提及", kg_stats_resp.get("mentions", 0))
        k4.metric("⚡ 关系", kg_stats_resp.get("relations", 0))

    st.divider()

    # ── Event type breakdown (requires plotly) ───────────────────────────────
    if events_live:
        try:
            import plotly.express as px
            import pandas as pd

            df_types = (
                pd.DataFrame(events_live)
                .groupby("event_type", as_index=False)
                .size()
                .rename(columns={"size": "count"})
            )

            st.subheader("事件类型分布")
            fig = px.bar(
                df_types,
                x="event_type",
                y="count",
                labels={"event_type": "事件类型", "count": "数量"},
                color="count",
                color_continuous_scale="reds",
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

            # Severity pie
            df_sev = (
                pd.DataFrame(events_live)
                .groupby("severity", as_index=False)
                .size()
                .rename(columns={"size": "count"})
            )
            st.subheader("严重级别分布")
            fig2 = px.pie(
                df_sev,
                names="severity",
                values="count",
                color="severity",
                color_discrete_map={"high": "#e74c3c", "medium": "#f39c12", "low": "#2ecc71"},
            )
            st.plotly_chart(fig2, use_container_width=True)

        except ImportError:
            st.info("安装 plotly 和 pandas 可以查看图表：`pip install plotly pandas`")
    else:
        st.info("🚧 请先聚合新闻和提取事件，仪表板将显示实时统计。")

# ===========================================================================
# Page: ⚙️ 系统状态
# ===========================================================================
elif page == "⚙️ 系统状态":
    st.title("⚙️ 系统状态与配置")

    # ── Backend connectivity ─────────────────────────────────────────────────
    st.subheader("🔌 后端服务")

    sources_resp = _api.get_news_sources()

    if "error" in sources_resp:
        st.error(
            f"❌ 无法连接到 FastAPI 后端：{sources_resp['error']}\n\n"
            "启动后端：`python -m uvicorn app.main:app --reload --port 8001`"
        )
    else:
        st.success(f"✅ FastAPI 后端：正常 ({_backend_url})")

        sources_list: List[Dict[str, Any]] = sources_resp.get("sources", [])

        m1, m2 = st.columns(2)
        m1.metric("配置新闻源数", len(sources_list))
        m2.metric("系统状态", "🟢 正常")

        if sources_list:
            st.subheader("新闻源列表")
            for source in sources_list:
                with st.expander(f"📡 {source.get('name', '未知')}"):
                    st.write(f"**分类：** {source.get('category', 'N/A')}")
                    st.write(f"**优先级：** {source.get('priority', 'N/A')}")
                    st.caption(source.get("url", "N/A"))

    st.subheader("📊 系统信息")
    st.info(
        f"**版本：** 1.0.0  \n"
        f"**后端地址：** {_backend_url}  \n"
        f"**页面刷新时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n"
        "**平台：** EL'druin Intelligence Platform  \n"
        "**知识图谱：** Kuzu（嵌入式）/ NetworkX（备用）"
    )
