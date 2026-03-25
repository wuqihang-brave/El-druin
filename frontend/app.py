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
from components.order_critique import display_order_critique  # noqa: E402
from components.sidebar import render_sidebar_navigation  # noqa: E402
from utils.deep_extraction import (  # noqa: E402
    extract_causal_chains,
    visualize_confidence,
    calculate_systemic_order_score,
    get_order_status,
    calculate_signal_noise_ratio,
    categorize_entities_by_order,
)

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
    page_title="EL-DRUIN",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS – Dark Liturgy / Elite Intelligence theme
# ---------------------------------------------------------------------------
_CSS_PATH = os.path.join(_FRONTEND_DIR, "assets", "custom_styles.css")
try:
    with open(_CSS_PATH, encoding="utf-8") as _css_file:
        _css_content = _css_file.read()
    st.markdown(f"<style>{_css_content}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    logger.warning("custom_styles.css not found at %s; using inline fallback.", _CSS_PATH)
    st.markdown(
        """
        <style>
        :root {
          --color-gold: #D4AF37; --color-black: #0D1117;
          --color-white: #F0F0F0; --color-elevated: #161B22;
          --color-border: #30363D; --color-silver: #A8A8A8;
        }
        .stApp, .main, body { background-color: var(--color-black) !important; color: var(--color-white) !important; }
        [data-testid="stAppViewContainer"] { background-color: var(--color-black) !important; }
        section[data-testid="stSidebar"] { background-color: var(--color-black) !important; border-right: 1px solid var(--color-border) !important; }
        section[data-testid="stSidebar"] * { color: var(--color-white) !important; }
        h1, h2, h3, h4, h5, h6 { color: var(--color-white) !important; }
        .stMarkdown, .stMarkdown p { color: var(--color-white) !important; }
        a { color: var(--color-gold) !important; }
        a:hover { color: #FFE066 !important; }
        a:visited { color: #C9A227 !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Backend URL (env-configurable)
# ---------------------------------------------------------------------------
_backend_url = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api/v1"
_api = APIClient(base_url=_backend_url)

# ---------------------------------------------------------------------------
# Session State Initialization (must happen before any other logic)
# ---------------------------------------------------------------------------
if "initialized" not in st.session_state:
    st.session_state.initialized = False
if "current_page" not in st.session_state:
    st.session_state.current_page = "🏠 主页"
if "selected_entity" not in st.session_state:
    st.session_state.selected_entity = ""
if "graph_data" not in st.session_state:
    st.session_state.graph_data: Dict[str, Any] = {
        "entities": [], "relations": [], "status": "not_loaded"
    }
if "entity_cache" not in st.session_state:
    st.session_state.entity_cache: Dict[str, Any] = {}
if "last_update" not in st.session_state:
    st.session_state.last_update: Optional[datetime] = None
if "nav_state" not in st.session_state:
    st.session_state.nav_state: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Knowledge Graph Data Loading (must happen before sidebar renders)
# ---------------------------------------------------------------------------

@st.cache_resource
def load_knowledge_graph() -> Dict[str, Any]:
    """Query KuzuDB for all entities (limit 1000) and relations (limit 2000).

    Returns:
        Structured dict with keys:
          * ``entities``  – list of entity dicts
          * ``relations`` – list of relation dicts
          * ``status``    – "loaded" | "error"
    """
    try:
        ent_r = _api.get_kg_entities(limit=1000)
        rel_r = _api.get_kg_relations(limit=2000)
        if "error" not in ent_r and "error" not in rel_r:
            return {
                "entities": ent_r.get("entities", []),
                "relations": rel_r.get("relations", []),
                "status": "loaded",
            }
        return {"entities": [], "relations": [], "status": "error"}
    except Exception as exc:
        logger.error("load_knowledge_graph failed: %s", exc)
        return {"entities": [], "relations": [], "status": "error", "error": str(exc)}


# Load graph data into session_state BEFORE the sidebar renders
with st.spinner("Loading Knowledge Graph..."):
    if st.session_state.graph_data.get("status") != "loaded":
        st.session_state.graph_data = load_knowledge_graph()
        if st.session_state.last_update is None:
            st.session_state.last_update = datetime.now()
        # Build entity cache for fast name lookups
        st.session_state.entity_cache = {
            e.get("name", ""): e
            for e in st.session_state.graph_data.get("entities", [])
            if e.get("name")
        }
        st.session_state.initialized = True


# ---------------------------------------------------------------------------
# Sidebar – navigation
# ---------------------------------------------------------------------------
page = render_sidebar_navigation()

# ---------------------------------------------------------------------------
# Sidebar – Entity Search (safe access via pre-loaded graph_data)
# ---------------------------------------------------------------------------
_sidebar_entity_names: List[str] = [
    e.get("name", "")
    for e in st.session_state.graph_data.get("entities", [])
    if e.get("name")
]
if _sidebar_entity_names:
    st.sidebar.markdown(
        "<hr style='border-color:#2D333B;margin:4px 0 6px 0'/>",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        "<p style='color:#A8A8A8;font-size:0.78rem;margin:0 0 4px 0;"
        "font-family:\"Inter\",sans-serif;'>🔎 实体搜索</p>",
        unsafe_allow_html=True,
    )
    _sidebar_sel = st.sidebar.selectbox(
        "搜索实体",
        [""] + _sidebar_entity_names,
        index=0,
        key="sidebar_entity_select",
        label_visibility="collapsed",
    )
    if _sidebar_sel and _sidebar_sel != st.session_state.selected_entity:
        st.session_state.selected_entity = _sidebar_sel
        st.rerun()

# ---------------------------------------------------------------------------
# Sidebar – Footer Buttons
# ---------------------------------------------------------------------------
# Only buttons with backend callbacks implemented are enabled.
_footer_buttons: Dict[str, bool] = {
    "🔄 Refresh Data": True,    # clears cache and reloads graph
    "📤 Export Graph": False,   # not yet implemented
    "📊 Run Analytics": False,  # not yet implemented
    "⚙️ Settings": False,       # not yet implemented
}
st.sidebar.markdown(
    "<hr style='border-color:#2D333B;margin:8px 0 6px 0'/>",
    unsafe_allow_html=True,
)
for _btn_label, _btn_enabled in _footer_buttons.items():
    if _btn_enabled:
        if st.sidebar.button(
            _btn_label, use_container_width=True, key=f"footer_btn_{_btn_label}"
        ):
            # clear() invalidates the @st.cache_resource cache so the next
            # run fetches fresh data from KuzuDB.
            load_knowledge_graph.clear()
            st.session_state.graph_data = {
                "entities": [], "relations": [], "status": "not_loaded"
            }
            st.session_state.entity_cache = {}
            st.session_state.last_update = None
            st.rerun()
    else:
        st.sidebar.button(
            _btn_label,
            use_container_width=True,
            disabled=True,
            key=f"footer_btn_{_btn_label}",
        )

# ===========================================================================
# Knowledge graph helpers
# ===========================================================================

# Entity-type → colour mapping (shared across all graph renders)
# Soft, harmonious palette replacing harsh primary colours
_KG_TYPE_COLORS: Dict[str, str] = {
    "PERSON": "#E8AB5D",    # warm earth
    "ORG": "#4A90E2",       # intellect blue
    "GPE": "#7ED321",       # vitality green
    "LOC": "#BD10E0",       # deep violet
    "DATE": "#9B8EA8",      # muted purple
    "MONEY": "#50C8A8",     # soft teal
    "PERCENT": "#F5A623",   # soft amber
    "EVENT": "#E8AB5D",     # warm earth
    "ENTITY": "#4A90E2",    # intellect blue
    "ARTICLE": "#5B7FA6",   # slate blue
    "MISC": "#C8C8C8",      # neutral grey
}
_KG_DEFAULT_COLOR = "#C8C8C8"

# Graph rendering constants
_KG_MAIN_HEIGHT = 800    # Main knowledge graph canvas height (px)
_KG_MINI_HEIGHT = 600    # In-article mini-graph canvas height (px)
_KG_EDGE_COLOR = "#555555"  # Ultra-thin semi-transparent edge colour (Dark Matter)

# Node colour constants – three-layer hierarchy (leaf → bridge → hub)
# Dark Matter theme: gold hubs, muted bridge, cold-white fringe
_NODE_COLOR_LEAF   = "#E0E0E0"  # Cold White   – isolated / leaf nodes
_NODE_COLOR_BRIDGE = "#2D333B"  # Dark Grey-Blue – bridge / connector nodes
_NODE_COLOR_HUB    = "#D4AF37"  # Apostolic Gold – central hub nodes

# Theme palette
_THEME_DARK_BLUE   = "#0D0D0D"
_THEME_ACCENT_GOLD = "#D4AF37"

# Order-Chaos gradient (used by dashboard charts)
# Runs from deep order-blue (most ordered) → deep chaos-red (most chaotic)
_ORDER_CHAOS_GRADIENT: List[str] = [
    "#1a365d",  # 秩序蓝（最秩序）
    "#2d5a8c",
    "#4a90e2",  # 浅蓝
    "#7ab8f0",
    "#f5a623",  # 琥珀
    "#e8705c",
    "#d94949",
    "#722f37",  # 混沌红（最混沌）
]

# Signal green – used in Signal vs Noise donut chart
_SIGNAL_GREEN = "#92cc1e"

# Category colour mapping for news cards
_NEWS_CATEGORY_COLORS: Dict[str, str] = {
    "technology": "#4A90E2",    # intellect blue
    "geopolitics": "#E8AB5D",   # warm earth
    "institution": "#7ED321",   # vitality green
    "causality": "#BD10E0",     # deep violet
    "unknown": "#C8C8C8",       # neutral grey
}
_NEWS_CATEGORY_DEFAULT_COLOR = "#C8C8C8"


def _get_color_by_category(category: str) -> str:
    """Return a soft-palette colour hex for a news category."""
    return _NEWS_CATEGORY_COLORS.get(category.lower(), _NEWS_CATEGORY_DEFAULT_COLOR)


def _score_article_locally(article: Dict[str, Any]) -> tuple:
    """Compute a heuristic order score (0–100) and category for a news article.

    Used when no backend scoring is available.  Weights:
    - Keyword matching for high-value structural topics (technology, geopolitics …)
    - Article length (longer descriptions → more context → slightly higher score)
    - Presence of a URL (source credibility proxy)
    """
    _HIGH_VALUE: Dict[str, str] = {
        "technology": ("tech", "ai", "artificial intelligence", "quantum", "innovation",
                        "breakthrough", "科技", "人工智能", "量子", "技术突破"),
        "geopolitics": ("war", "sanction", "treaty", "election", "invasion", "diplomacy",
                         "geopolit", "战争", "制裁", "条约", "选举", "入侵", "外交"),
        "institution": ("regulation", "legislation", "reform", "merger", "acquisition",
                         "法规", "立法", "改革", "并购", "收购"),
        "causality": ("crisis", "collapse", "revolution", "climate", "nuclear",
                       "危机", "崩溃", "革命", "气候", "核"),
    }
    _LOW_VALUE_KW = ("celebrity", "gossip", "award", "concert", "selfie",
                     "明星", "八卦", "颁奖", "演唱会")

    combined = " ".join(filter(None, [
        article.get("title", ""),
        article.get("description", ""),
        article.get("category", ""),
    ])).lower()

    # Disqualify entertainment fluff immediately
    if any(kw in combined for kw in _LOW_VALUE_KW):
        return 15.0, "unknown"

    best_score = 40.0
    best_category = "unknown"
    for cat, keywords in _HIGH_VALUE.items():
        hits = sum(1 for kw in keywords if kw in combined)
        if hits:
            score = min(40.0 + hits * 12.0, 95.0)
            if score > best_score:
                best_score = score
                best_category = cat

    # Slight bonus for longer descriptions (up to +5 pts)
    desc_len = len(article.get("description") or "")
    best_score = min(best_score + min(desc_len / 200, 5.0), 100.0)

    return round(best_score, 1), best_category


def render_news_card(article: Dict[str, Any], order_score: float, category: str) -> None:
    """Render a single news article as a styled card.

    Args:
        article: News article dict with keys ``title``, ``description``,
                 ``source``, ``published``, ``link``.
        order_score: Structural importance score (0–100) computed by the
                     order scoring heuristic.
        category: Computed semantic category string (e.g. ``"technology"``),
                  as returned by ``_score_article_locally()``.  This may
                  differ from ``article.get("category")``.
    """
    color = _get_color_by_category(category)
    score_int = int(round(order_score))
    title = article.get("title") or "（无标题）"
    summary = (article.get("description") or "（暂无摘要）")[:200]
    if len(article.get("description") or "") > 200:
        summary += "…"
    source = article.get("source", "")
    pub = str(article.get("published", ""))[:10]
    url = article.get("link", "")
    cat_label = category.capitalize()

    st.markdown(
        f"""
        <div style="
            border: 1px solid #2D333B;
            border-radius: 6px;
            padding: 14px 16px 14px 20px;
            background-color: rgba(20, 20, 20, 0.6);
            margin-bottom: 14px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
            border-left: 4px solid {color};
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
        ">
            <div style="display:flex; justify-content:space-between; align-items:baseline;">
                <strong style="font-size:1.02rem; color:#F0F0F0; font-family:'Inter',sans-serif;">{title}</strong>
                <span style="
                    background:{color};
                    color:#0D0D0D;
                    border-radius:12px;
                    padding:2px 10px;
                    font-size:0.75rem;
                    font-weight:600;
                    white-space:nowrap;
                    margin-left:8px;
                ">{cat_label}</span>
            </div>
            <p style="color:#A8A8A8; font-size:0.87rem; margin:6px 0 4px 0; font-family:'Inter',sans-serif;">{summary}</p>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:6px;">
                <span style="font-size:0.78rem; color:#8B8B8B; font-family:'Inter',sans-serif;">
                    {("📌 " + source) if source else ""}{"&nbsp;&nbsp;" if source and pub else ""}
                    {("⏰ " + pub) if pub else ""}
                </span>
                {"<a href='" + url + "' target='_blank' style='font-size:0.82rem;color:#D4AF37;'>View Full →</a>" if url else ""}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.progress(score_int / 100, text=f"Order Score: {score_int}/100")


def _node_size_and_color(
    label_type: str,
    node_degree: int,
    is_center: bool = False,
) -> tuple:
    """Return (size, color) for a node based on its degree (three-layer hierarchy).

    Three-layer colour hierarchy:
      - Central Hubs  (is_center or degree > 5): Glowing Gold #FFD700, size 65
      - Bridge Nodes  (2 < degree ≤ 5):          Deep Navy #0A1F2E, size 38
      - Leaf Nodes    (degree ≤ 2):               Neutral Grey #D0D0D0, size 20
    """
    if is_center or node_degree > 5:
        return 65, _NODE_COLOR_HUB       # Central hubs – highly interconnected
    if node_degree > 2:
        return 38, _NODE_COLOR_BRIDGE    # Bridge nodes – connecting different domains
    return 20, _NODE_COLOR_LEAF          # Leaf nodes – information sources / endpoints


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

    # Centre node = node with highest degree
    center_id = max(degree, key=lambda k: degree[k]) if degree else None

    # ── Build agraph Node objects ─────────────────────────────────────────
    ag_nodes: List[Node] = []
    for node in raw_nodes:
        node_id = str(node.get("id", "") or "")
        if not node_id:
            continue
        label_type = str(node.get("label", "MISC") or "MISC")
        node_degree = degree.get(node_id, 0)
        is_center = node_id == center_id
        size, color = _node_size_and_color(label_type, node_degree, is_center)
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
                    color=_KG_EDGE_COLOR,
                )
            )

    if not ag_nodes:
        st.info("📭 节点数据为空，无法渲染图谱。")
        return

    try:
        config = Config(
            width=800,
            height=_KG_MAIN_HEIGHT,
            directed=True,
            physics=True,
            hierarchical=False,
            nodeHighlightBehavior=True,
            highlightColor=_NODE_COLOR_HUB,
            collapsible=False,
        )
        with st.container():
            agraph(nodes=ag_nodes, edges=ag_edges, config=config)
    except (TypeError, ValueError) as exc:
        logger.error("render_graph Config error (%s): %s", type(exc).__name__, exc)
        st.error(f"⚠️ 知识图谱渲染失败：{exc}")
    except Exception as exc:
        logger.error("render_graph unexpected error (%s): %s", type(exc).__name__, exc)
        st.error(f"⚠️ 知识图谱渲染失败：{exc}")



# ===========================================================================
# Page: 🏠 主页  –  three-column command centre
# ===========================================================================
if page == "🏠 主页":
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:14px;margin-bottom:4px;">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40" width="36" height="36">
              <circle cx="20" cy="20" r="16" fill="none" stroke="#D4AF37" stroke-width="0.8"
                      stroke-dasharray="2 3.2"/>
              <line x1="20" y1="4" x2="20" y2="36" stroke="#D4AF37" stroke-width="1.6" stroke-linecap="round"/>
              <line x1="12" y1="14" x2="28" y2="14" stroke="#D4AF37" stroke-width="1.6" stroke-linecap="round"/>
              <line x1="16" y1="16" x2="24" y2="16" stroke="#D4AF37" stroke-width="0.8" stroke-linecap="round"/>
            </svg>
            <div>
              <h1 style="color:#F0F0F0;margin:0;font-weight:300;letter-spacing:3px;
                         font-family:'Inter',sans-serif;">EL-DRUIN</h1>
              <p style="color:#D4AF37;font-size:0.88rem;margin:0;font-style:italic;
                        font-family:'Inter',sans-serif;">
                Ontological Intelligence &amp; Systematic Order
              </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    # ── Session-state defaults ───────────────────────────────────────────────
    if "home_logs" not in st.session_state:
        st.session_state.home_logs: List[str] = []
    if "home_graph_data" not in st.session_state:
        st.session_state.home_graph_data: Dict[str, Any] = {"nodes": [], "edges": []}
    if "home_analysis" not in st.session_state:
        st.session_state.home_analysis: Dict[str, Any] = {}
    if "home_causal_chains" not in st.session_state:
        st.session_state.home_causal_chains: Dict[str, Any] = {
            "entities": [],
            "relations": [],
            "causal_chains": [],
            "overall_order_score": 50,
        }

    # ── Three-column layout ──────────────────────────────────────────────────
    col_left, col_mid, col_right = st.columns([2, 5, 3], gap="medium")

    # ════════════════════════════════════════════════════════════════════════
    # LEFT COLUMN – configuration & status
    # ════════════════════════════════════════════════════════════════════════
    with col_left:
        st.markdown("#### ⚙️ 配置面板")

        # ── Data source ──────────────────────────────────────────────────────
        with st.container(border=True):
            st.markdown("**📡 数据源**")
            data_source = st.selectbox(
                "选择数据源",
                ["实时新闻", "历史数据", "自定义输入"],
                key="home_data_source",
                label_visibility="collapsed",
            )

        # ── Date range ───────────────────────────────────────────────────────
        with st.container(border=True):
            st.markdown("**📅 日期范围**")
            from datetime import date as _date
            _today = _date.today()
            _date_col1, _date_col2 = st.columns(2)
            with _date_col1:
                date_from = st.date_input("开始", value=_date(_today.year, _today.month, 1), key="home_date_from", label_visibility="collapsed")
            with _date_col2:
                date_to = st.date_input("结束", value=_today, key="home_date_to", label_visibility="collapsed")

        # ── API config ───────────────────────────────────────────────────────
        with st.container(border=True):
            st.markdown("**🔧 API 配置**")
            api_endpoint = st.text_input(
                "API 端点",
                value=_backend_url,
                key="home_api_endpoint",
            )
            _c1, _c2 = st.columns(2)
            with _c1:
                api_timeout = st.number_input("超时 (秒)", min_value=5, max_value=120, value=30, key="home_api_timeout")
            with _c2:
                api_retries = st.number_input("重试次数", min_value=0, max_value=5, value=2, key="home_api_retries")

        # ── Model selection ──────────────────────────────────────────────────
        with st.container(border=True):
            st.markdown("**🤖 模型选择**")
            model_mode = st.radio(
                "分析模式",
                ["本体论模式", "快速模式", "深度模式"],
                key="home_model_mode",
                label_visibility="collapsed",
            )

        # ── API connection status ────────────────────────────────────────────
        with st.container(border=True):
            st.markdown("**🔌 API 连接状态**")
            _sources_check = _api.get_news_sources()
            if "error" not in _sources_check:
                st.markdown(
                    "<span class='status-ok'>● 正常</span> &nbsp; 后端连接成功",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    "<span class='status-err'>● 异常</span> &nbsp; 后端无响应",
                    unsafe_allow_html=True,
                )

        # ── Actions ──────────────────────────────────────────────────────────
        st.markdown("")
        if st.button("🚀 开始分析", type="primary", key="home_run", use_container_width=True):
            with st.spinner("正在处理…"):
                _log_entry = f"[{datetime.now().strftime('%H:%M:%S')}] 触发分析 · 数据源={data_source} · 模式={model_mode}"
                st.session_state.home_logs.insert(0, _log_entry)

                # Fetch KG data from backend to populate the graph
                _ent_r = _api.get_kg_entities(limit=80)
                _rel_r = _api.get_kg_relations(limit=120)
                if "error" not in _ent_r and "error" not in _rel_r:
                    _ents = _ent_r.get("entities", [])
                    _rels = _rel_r.get("relations", [])
                    _known = {e.get("name", "") for e in _ents if e.get("name")}
                    st.session_state.home_graph_data = {
                        "nodes": [
                            {"id": e["name"], "label": str(e.get("type", "MISC")).upper(), "properties": e}
                            for e in _ents if e.get("name")
                        ],
                        "edges": [
                            {"from": r.get("from", ""), "to": r.get("to", ""), "type": r.get("relation", "")}
                            for r in _rels if r.get("from") in _known and r.get("to") in _known
                        ],
                    }
                    # Build analysis summary from graph data
                    _entity_names = [e.get("name", "") for e in _ents[:10] if e.get("name")]
                    # Order score: entities contribute 3 pts each (richer concepts),
                    # relations contribute 2 pts each (connections imply coherence).
                    _ENTITY_WEIGHT = 3
                    _RELATION_WEIGHT = 2
                    _order_score = min(100, len(_ents) * _ENTITY_WEIGHT + len(_rels) * _RELATION_WEIGHT)
                    # Confidence: baseline 60 %, rising 0.5 % per entity, capped at 98 %.
                    _BASE_CONFIDENCE = 0.60
                    _CONFIDENCE_PER_ENTITY = 0.005
                    _MAX_CONFIDENCE = 0.98
                    _confidence = min(_MAX_CONFIDENCE, _BASE_CONFIDENCE + len(_ents) * _CONFIDENCE_PER_ENTITY)
                    st.session_state.home_analysis = {
                        "logic_points": [
                            f"发现 {len(_ents)} 个核心实体节点",
                            f"建立 {len(_rels)} 条语义关系链",
                            f"主要实体类型分布均衡，信息熵较低",
                            "时序关联显示事件演化路径清晰",
                        ],
                        "conclusions": [
                            f"关键实体 **{_entity_names[0]}** 处于信息网络中心" if _entity_names else "暂无核心实体",
                            "知识图谱拓扑结构趋于稳定",
                        ],
                        "order_score": _order_score,
                        "confidence": _confidence,
                        "key_entities": _entity_names,
                    }
                    _log_entry2 = f"[{datetime.now().strftime('%H:%M:%S')}] 图谱加载完成 · {len(_ents)} 节点 · {len(_rels)} 边"
                    st.session_state.home_logs.insert(0, _log_entry2)

                    # ── Deep causal chain extraction from latest news ──────────
                    _news_r = _api.get_latest_news(limit=3, hours=24)
                    _news_articles = _news_r.get("articles", []) if "error" not in _news_r else []
                    if _news_articles:
                        # Aggregate text from the most recent articles for causal extraction
                        _combined_text = " ".join(
                            filter(None, [
                                _a.get("title", "") + ". " + (_a.get("description") or "")
                                for _a in _news_articles[:3]
                            ])
                        ).strip()
                        if _combined_text:
                            _causal_resp = extract_causal_chains(_combined_text, _api)
                            st.session_state.home_causal_chains = _causal_resp
                            # Clear stale philosophical critique cache
                            st.session_state.pop("order_critique_text", None)
                            st.session_state.pop("_critique_signal", None)
                            _log_entry3 = (
                                f"[{datetime.now().strftime('%H:%M:%S')}] 因果链提取完成 · "
                                f"{len(_causal_resp.get('causal_chains', []))} 条因果链"
                            )
                            st.session_state.home_logs.insert(0, _log_entry3)
                else:
                    st.warning("⚠️ 后端无数据，请先摄入新闻。")
            st.rerun()

    # ════════════════════════════════════════════════════════════════════════
    # MIDDLE COLUMN – knowledge graph + processing status
    # ════════════════════════════════════════════════════════════════════════
    with col_mid:
        # ── Upper section: knowledge graph ───────────────────────────────────
        with st.container(border=True):
            st.markdown("#### 🕸️ 知识图谱")
            _gd = st.session_state.home_graph_data
            _node_count = len(_gd.get("nodes", []))
            _edge_count = len(_gd.get("edges", []))
            if _node_count:
                st.caption(
                    f"<span class='gold-label'>{_node_count}</span> 节点 &nbsp;·&nbsp;"
                    f"<span class='gold-label'>{_edge_count}</span> 边",
                    unsafe_allow_html=True,
                )
            render_graph(_gd)

        # ── Lower section: processing status ─────────────────────────────────
        with st.container(border=True):
            st.markdown("#### 📊 实时处理状态")

            # Progress bar – derived from graph size (cosmetic placeholder)
            _pct = min(1.0, (_node_count + _edge_count) / 200) if _node_count else 0.0
            st.progress(_pct, text=f"图谱构建进度: {int(_pct * 100)}%")

            # Stats
            _s1, _s2, _s3 = st.columns(3)
            _kg_stats = _api.get_kg_stats()
            _processed = _kg_stats.get("articles", 0) if "error" not in _kg_stats else 0
            _concepts  = _kg_stats.get("entities", 0) if "error" not in _kg_stats else 0
            _relations = _kg_stats.get("relations", 0) if "error" not in _kg_stats else 0
            _s1.metric("📰 已处理事件", _processed)
            _s2.metric("💡 提取概念数", _concepts)
            _s3.metric("🔗 建立关系数", _relations)

            # Processing log
            st.markdown("**🪵 处理日志**")
            _log_lines = st.session_state.home_logs[:8]  # show last 8 entries
            if _log_lines:
                _log_html = "".join(
                    f"<div style='font-family:\"JetBrains Mono\",\"Fira Code\",monospace;"
                    f"font-size:0.76rem;color:#A8A8A8;padding:2px 0'>{line}</div>"
                    for line in _log_lines
                )
                st.markdown(
                    f"<div style='background:#111111;border:1px solid #2D333B;border-radius:4px;"
                    f"padding:8px 12px;max-height:160px;overflow-y:auto'>{_log_html}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.caption("暂无日志。点击「开始分析」按钮后日志将显示在此处。")

    # ════════════════════════════════════════════════════════════════════════
    # RIGHT COLUMN – El-druin 秩序分析
    # ════════════════════════════════════════════════════════════════════════
    with col_right:
        with st.container(border=True):
            st.markdown(
                "<h4 style='color:#D4AF37;font-weight:300;letter-spacing:0.08em;'>⚖️ EL-DRUIN 秩序分析</h4>",
                unsafe_allow_html=True,
            )

            _analysis = st.session_state.home_analysis
            _causal_data = st.session_state.home_causal_chains

            if not _analysis:
                st.info("▶ 点击左侧「开始分析」以生成秩序报告。")
            else:
                # ── Determine whether deep causal data is available ──────────
                _causal_chains_list = _causal_data.get("causal_chains", [])
                _causal_entities = _causal_data.get("entities", [])
                _causal_relations = _causal_data.get("relations", [])

                _has_causal = bool(_causal_chains_list)

                if _has_causal:
                    # ── Deep analysis: display_order_critique ────────────────
                    display_order_critique(
                        entities=_causal_entities,
                        relations=_causal_relations,
                        causal_chains=_causal_chains_list,
                        api_client=_api,
                    )

                    # ── Confidence visualisation ──────────────────────────────
                    st.markdown("### 📊 因果链置信度")
                    visualize_confidence(_causal_chains_list)

                else:
                    # ── Fallback: classic logic / conclusion view ─────────────
                    st.markdown("**🔍 深层逻辑**")
                    for _pt in _analysis.get("logic_points", []):
                        st.markdown(f"• {_pt}")

                    st.markdown("")

                    st.markdown("**💡 核心结论**")
                    for _c in _analysis.get("conclusions", []):
                        st.markdown(
                            f"<div style='background:rgba(20,20,20,0.8);border-left:3px solid #D4AF37;"
                            f"padding:6px 10px;border-radius:4px;margin:4px 0;color:#F0F0F0'>{_c}</div>",
                            unsafe_allow_html=True,
                        )

                    st.markdown("")

                    _score = _analysis.get("order_score", 0)
                    st.markdown(
                        f"**📐 秩序评分** &nbsp;"
                        f"<span class='score-label'>{_score}</span>"
                        f"<span style='color:#999;font-size:0.9rem'> / 100</span>",
                        unsafe_allow_html=True,
                    )
                    st.progress(_score / 100)

                    _conf = _analysis.get("confidence", 0.0)
                    _conf_color = (
                        "#27ae60" if _conf >= 0.75
                        else ("#f39c12" if _conf >= 0.5 else "#e74c3c")
                    )
                    st.markdown(
                        f"**🎯 置信度** &nbsp;"
                        f"<span style='color:{_conf_color};font-weight:700'>{_conf:.1%}</span>",
                        unsafe_allow_html=True,
                    )

                    st.markdown("")

                    _entities_list = _analysis.get("key_entities", [])
                    if _entities_list:
                        st.markdown("**🏷️ 关键实体**")
                        _tags_html = " ".join(
                            f"<span class='entity-tag'>{e}</span>"
                            for e in _entities_list[:12]
                        )
                        st.markdown(_tags_html, unsafe_allow_html=True)

        # ── Export buttons ────────────────────────────────────────────────────
        if st.session_state.home_analysis:
            st.markdown("")
            st.markdown("**📤 导出**")
            _exp1, _exp2 = st.columns(2)
            with _exp1:
                import json as _json
                _export_payload = {
                    "analysis": st.session_state.home_analysis,
                    "graph": st.session_state.home_graph_data,
                    "causal_chains": st.session_state.home_causal_chains,
                }
                st.download_button(
                    "⬇ JSON",
                    data=_json.dumps(_export_payload, ensure_ascii=False, indent=2),
                    file_name="el_druin_analysis.json",
                    mime="application/json",
                    key="home_export_json",
                    use_container_width=True,
                )
            with _exp2:
                try:
                    import pandas as _pd
                    _nodes_df = _pd.DataFrame(st.session_state.home_graph_data.get("nodes", []))
                    _csv_data = _nodes_df.to_csv(index=False)
                except Exception:
                    _csv_data = "id,label\n"
                st.download_button(
                    "⬇ CSV",
                    data=_csv_data,
                    file_name="el_druin_nodes.csv",
                    mime="text/csv",
                    key="home_export_csv",
                    use_container_width=True,
                )

# ===========================================================================
# Page: 📰 实时新闻
# ===========================================================================
elif page == "📰 实时新闻":
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

    search_query = st.text_input("⚔️ Discern Truth — 关键词搜索", placeholder="输入关键词…")

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

        # ── Raw News Stream (folded by default) ──────────────────────────────
        import hashlib as _hashlib  # stable across process restarts (unlike built-in hash())

        # Session-state cache: {article_cache_key -> kg extraction result}
        if "kg_cache" not in st.session_state:
            st.session_state.kg_cache = {}

        # Session state for order analysis result
        if "news_order_analysis" not in st.session_state:
            st.session_state.news_order_analysis = None

        with st.expander("🌊 Raw News Stream (Entropic Data) — 原始数据流", expanded=False):
            st.caption(
                "⚠️ 以下为未经秩序过滤的原始数据流。信息密度高，认知负担大。"
                " 点击下方「🎯 Analyze Order」提取结构性重要信息。"
            )
            if articles:
                for i, article in enumerate(articles, 1):
                    title_preview = (article.get("title") or "（无标题）")[:80]
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

                        # ── Knowledge Graph extraction ────────────────────────
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

                        # ── Display cached KG results ─────────────────────────
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

                                # ── Interactive graph visualisation ────────────
                                if _entities_kg and _relations_kg:
                                    st.write("**🌐 图谱可视化**")
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
                                                size=_node_size_and_color(
                                                    _e.get("type", "MISC"), 0
                                                )[0],
                                                color=_node_size_and_color(
                                                    _e.get("type", "MISC"), 0
                                                )[1],
                                            )
                                            for _e in _entities_kg
                                        ]
                                        _ag_edges = [
                                            Edge(
                                                source=_r["subject"],
                                                target=_r["object"],
                                                label=_r.get("predicate", ""),
                                                color=_KG_EDGE_COLOR,
                                            )
                                            for _r in _relations_kg
                                            if _r.get("subject") and _r.get("object")
                                        ]
                                        _ag_config = Config(
                                            width=700,
                                            height=_KG_MINI_HEIGHT,
                                            directed=True,
                                            physics=True,
                                            hierarchical=False,
                                            nodeHighlightBehavior=True,
                                            highlightColor="#E8AB5D",
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
                                                            line={"width": 1, "color": _KG_EDGE_COLOR},
                                                            hoverinfo="none",
                                                        ),
                                                        go.Scatter(
                                                            x=[_pos[n][0] for n in _G.nodes()],
                                                            y=[_pos[n][1] for n in _G.nodes()],
                                                            mode="markers+text",
                                                            text=list(_G.nodes()),
                                                            textposition="top center",
                                                            marker={"size": 12, "color": "#4A90E2"},
                                                            hoverinfo="text",
                                                        ),
                                                    ],
                                                    layout=go.Layout(
                                                        showlegend=False,
                                                        hovermode="closest",
                                                        height=_KG_MINI_HEIGHT,
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

        # ── Analyze Order button ─────────────────────────────────────────────
        st.markdown("---")
        _analyze_col, _ = st.columns([1, 2])
        with _analyze_col:
            if st.button(
                "🎯 Analyze Order — 提取秩序",
                type="primary",
                use_container_width=True,
                key="analyze_order_btn",
            ):
                if articles:
                    with st.spinner("🔍 正在评估新闻的结构性重要度…"):
                        _scored = [
                            (article, *_score_article_locally(article))
                            for article in articles
                        ]
                        _scored.sort(key=lambda x: x[1], reverse=True)
                        st.session_state.news_order_analysis = _scored[:5]
                else:
                    st.warning("⚠️ 暂无文章可供分析，请先点击「立即刷新」。")

        # ── Top 5 Structurally Important News Cards ──────────────────────────
        if st.session_state.news_order_analysis:
            st.subheader("🏆 Top 5 结构性重要新闻")
            st.caption("经过秩序评分筛选，以下新闻具有最高的结构性信息价值。")
            for _art, _score, _cat in st.session_state.news_order_analysis:
                render_news_card(_art, _score, _cat)
        else:
            st.info(
                "点击上方「🎯 Analyze Order」按钮，从原始数据流中提取最具结构性价值的新闻。"
            )

    # ── Human Feedback Loop (RLHF Foundation) ───────────────────────────────
    st.divider()
    st.subheader("🧠 Human Feedback Loop — RLHF 数据收集")
    st.caption(
        "输入新闻文本，系统自动提取实体与关系，并生成 El-druin 的哲学解读。"
        " 对每条关系标记 ✅ Accept 或 👎 Reject，数据将保存用于未来的 RLHF 模型训练。"
    )

    # ── Input ────────────────────────────────────────────────────────────────
    _hf_col1, _hf_col2 = st.columns([4, 1])
    with _hf_col1:
        _hf_query = st.text_input(
            "📰 输入新闻文本或标题",
            placeholder="粘贴新闻内容或关键词…",
            key="hf_news_input",
        )
    with _hf_col2:
        _hf_extract = st.button(
            "🔍 提取 & 解读",
            key="hf_extract_btn",
            use_container_width=True,
        )

    # ── Session state ─────────────────────────────────────────────────────────
    if "hf_extraction_result" not in st.session_state:
        st.session_state.hf_extraction_result = None
    if "hf_feedback_data" not in st.session_state:
        st.session_state.hf_feedback_data = []

    # ── Trigger extraction ────────────────────────────────────────────────────
    if _hf_extract and _hf_query:
        with st.spinner("🤖 提取实体与关系，生成哲学解读…"):
            _hf_result = _api.extract_with_interpretation(
                news_text=_hf_query,
                news_title=_hf_query[:100],
            )
        if "error" in _hf_result:
            st.error(f"❌ 提取失败：{_hf_result['error']}")
        else:
            st.session_state.hf_extraction_result = _hf_result
            st.session_state.hf_feedback_data = []

    # ── Display results ───────────────────────────────────────────────────────
    if st.session_state.hf_extraction_result:
        _hf_res = st.session_state.hf_extraction_result

        # --- Philosophical interpretation ------------------------------------
        st.markdown("#### 🧠 El-druin's Interpretation")
        _interpretation = _hf_res.get("philosophical_interpretation", "")
        st.text_area(
            label="Philosophical Summary",
            value=_interpretation,
            height=100,
            help="LLM 生成的哲学解读（可手动编辑）",
            key="hf_interpretation_display",
        )

        st.divider()

        # --- Extracted entities ---------------------------------------------
        st.markdown("#### 🏷️ Extracted Entities")
        _hf_entities: List[Dict[str, Any]] = _hf_res.get("entities", [])
        if _hf_entities:
            try:
                import pandas as _pd_hf
                _ent_hf_df = _pd_hf.DataFrame([
                    {
                        "Entity": e.get("name", ""),
                        "Type": e.get("type", ""),
                        "Confidence": (
                            f"{float(e['confidence']):.0%}"
                            if e.get("confidence") is not None
                            else "N/A"
                        ),
                    }
                    for e in _hf_entities
                ])
                st.dataframe(_ent_hf_df, use_container_width=True)
            except Exception:
                for _e in _hf_entities:
                    st.write(f"- **{_e.get('name')}** ({_e.get('type', '?')})")
        else:
            st.info("未提取到实体。")

        st.divider()

        # --- Relations + feedback buttons ------------------------------------
        st.markdown("#### 🔗 Extracted Relations with Feedback")
        _hf_relations: List[Dict[str, Any]] = _hf_res.get("relations", [])

        if _hf_relations:
            # Header row
            _hdr = st.columns([2, 2, 2, 1, 1, 1])
            _hdr[0].write("**From**")
            _hdr[1].write("**Relation**")
            _hdr[2].write("**To**")
            _hdr[3].write("**Conf.**")
            _hdr[4].write("**✅**")
            _hdr[5].write("**👎**")
            st.divider()

            # Per-relation rows
            for _ri, _rel in enumerate(_hf_relations):
                _rel_id = _rel.get("id", f"rel_{_ri}")
                _from_e = _rel.get("from", _rel.get("subject", ""))
                _rel_type = _rel.get("relation", _rel.get("predicate", ""))
                _to_e = _rel.get("to", _rel.get("object", ""))
                _conf = float(_rel.get("weight", _rel.get("confidence", 0.5)))

                _rcols = st.columns([2, 2, 2, 1, 1, 1])
                _rcols[0].write(_from_e)
                _rcols[1].write(_rel_type)
                _rcols[2].write(_to_e)
                _rcols[3].write(f"{_conf:.0%}")

                with _rcols[4]:
                    if st.button("✅", key=f"hf_accept_{_ri}", help="Accept this relation"):
                        # Avoid duplicate entries for the same relation
                        _existing_ids = [f["relation_id"] for f in st.session_state.hf_feedback_data]
                        if _rel_id not in _existing_ids:
                            st.session_state.hf_feedback_data.append({
                                "relation_id": _rel_id,
                                "from_entity": _from_e,
                                "to_entity": _to_e,
                                "relation_type": _rel_type,
                                "action": "accept",
                                "confidence": _conf,
                                "reason": None,
                            })
                        else:
                            # Update existing entry
                            for _fb in st.session_state.hf_feedback_data:
                                if _fb["relation_id"] == _rel_id:
                                    _fb["action"] = "accept"
                                    _fb["reason"] = None
                        st.rerun()

                with _rcols[5]:
                    if st.button("👎", key=f"hf_reject_{_ri}", help="Reject this relation"):
                        _existing_ids = [f["relation_id"] for f in st.session_state.hf_feedback_data]
                        if _rel_id not in _existing_ids:
                            st.session_state.hf_feedback_data.append({
                                "relation_id": _rel_id,
                                "from_entity": _from_e,
                                "to_entity": _to_e,
                                "relation_type": _rel_type,
                                "action": "reject",
                                "confidence": _conf,
                                "reason": None,
                            })
                        else:
                            for _fb in st.session_state.hf_feedback_data:
                                if _fb["relation_id"] == _rel_id:
                                    _fb["action"] = "reject"
                        st.rerun()
        else:
            st.info("未提取到关系。")

        st.divider()

        # --- Feedback summary + save/clear ----------------------------------
        if st.session_state.hf_feedback_data:
            st.markdown("#### 📊 Feedback Summary")
            _hf_accepts = sum(1 for f in st.session_state.hf_feedback_data if f["action"] == "accept")
            _hf_rejects = sum(1 for f in st.session_state.hf_feedback_data if f["action"] == "reject")
            _fm1, _fm2 = st.columns(2)
            _fm1.metric("✅ Accepted", _hf_accepts)
            _fm2.metric("👎 Rejected", _hf_rejects)

            # Show pending feedback items
            for _fb in st.session_state.hf_feedback_data:
                _icon = "✅" if _fb["action"] == "accept" else "👎"
                st.caption(f"{_icon} {_fb['from_entity']} → {_fb['to_entity']} ({_fb['action']})")

        _fsave_col, _fclear_col = st.columns(2)
        with _fsave_col:
            if st.button("💾 Save Feedback", key="hf_save_btn", use_container_width=True):
                if st.session_state.hf_feedback_data:
                    with st.spinner("保存反馈数据…"):
                        _save_resp = _api.save_human_feedback(
                            news_id=_hf_res.get("news_id", "unknown"),
                            feedback_list=st.session_state.hf_feedback_data,
                        )
                    if _save_resp.get("status") == "success":
                        st.success(
                            f"✅ 已保存 {_save_resp.get('feedback_count', 0)} 条反馈！"
                            f"（{_save_resp.get('saved_to', '')}）"
                        )
                        st.session_state.hf_feedback_data = []
                    else:
                        st.error(f"❌ 保存失败：{_save_resp.get('error', _save_resp.get('message', ''))}")
                else:
                    st.warning("⚠️ 暂无反馈数据。请先对关系进行 Accept / Reject 标记。")
        with _fclear_col:
            if st.button("🔄 Clear Feedback", key="hf_clear_btn", use_container_width=True):
                st.session_state.hf_feedback_data = []
                st.info("反馈数据已清空。")

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
            _run_query = st.button("⚔️ Reveal Order", type="primary", key="kg_run_query_main")
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
                    f"<div style='background:#111111;border:1px solid #2D333B;border-radius:4px;"
                    f"padding:8px 12px;margin-bottom:4px;font-family:\"JetBrains Mono\",monospace;"
                    f"font-size:13px;color:#A8A8A8'>{_item['query']}</div>",
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

    # ── Fetch live data ───────────────────────────────────────────────────────
    news_data = _api.get_latest_news(limit=100, hours=24)
    events_data = _api.get_extracted_events(limit=100)
    kg_stats_resp = _api.get_kg_stats()

    articles_live = news_data.get("articles", []) if "error" not in news_data else []
    events_live = events_data.get("events", []) if "error" not in events_data else []

    total_news = len(articles_live)
    total_events = len(events_live)
    high_events = sum(1 for e in events_live if e.get("severity") == "high") if events_live else 0
    confidences = [float(e.get("confidence", 0)) for e in events_live if "confidence" in e]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

    _kg_entities = kg_stats_resp.get("entities", 0) if "error" not in kg_stats_resp else 0
    _kg_relations = kg_stats_resp.get("relations", 0) if "error" not in kg_stats_resp else 0
    _kg_articles = kg_stats_resp.get("articles", 0) if "error" not in kg_stats_resp else 0
    _kg_mentions = kg_stats_resp.get("mentions", 0) if "error" not in kg_stats_resp else 0

    # ── Compute Systemic Order Score ──────────────────────────────────────────
    # Formula: (Relations / Entities) × log(Total News) × 10
    _news_for_score = max(total_news, _kg_articles)
    _order_score = calculate_systemic_order_score(
        relations_count=_kg_relations,
        entities_count=_kg_entities,
        news_count=_news_for_score,
    )
    _order_status = get_order_status(_order_score)
    _rel_ent_ratio = _kg_relations / max(_kg_entities, 1)
    _has_data = bool(articles_live or events_live or _kg_entities)

    # ── Section 1: Systemic Order Score ───────────────────────────────────────
    st.markdown("## 📊 Systemic Order Score")
    try:
        import plotly.graph_objects as _go

        _gauge_col, _status_col = st.columns([2, 1])
        with _gauge_col:
            _gauge_fig = _go.Figure(_go.Indicator(
                mode="gauge+number+delta",
                value=_order_score if _has_data else 0,
                domain={"x": [0, 1], "y": [0, 1]},
                title={
                    "text": "Systemic Order Score",
                    "font": {"size": 18, "color": _THEME_DARK_BLUE},
                },
                delta={"reference": 60},
                gauge={
                    "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": _THEME_DARK_BLUE},
                    "bar": {"color": _ORDER_CHAOS_GRADIENT[1]},
                    "bgcolor": "white",
                    "borderwidth": 2,
                    "bordercolor": "#2c5282",
                    "steps": [
                        {"range": [0, 30], "color": "#fce8e6"},
                        {"range": [30, 60], "color": "#fff8e1"},
                        {"range": [60, 100], "color": "#e8f5e9"},
                    ],
                    "threshold": {
                        "line": {"color": _ORDER_CHAOS_GRADIENT[0], "width": 4},
                        "thickness": 0.75,
                        "value": 90,
                    },
                },
                number={
                    "suffix": "/100",
                    "font": {"size": 28, "color": _THEME_DARK_BLUE},
                },
            ))
            _gauge_fig.update_layout(
                height=280,
                margin={"t": 70, "b": 20, "l": 20, "r": 20},
                paper_bgcolor="#ffffff",
            )
            st.plotly_chart(_gauge_fig, use_container_width=True)

        with _status_col:
            _conf_display = f"{avg_conf:.1%}" if _has_data else "–"
            st.markdown(
                f"<div class='order-card'>"
                f"<h3>系统状态</h3>"
                f"<p style='color:#d4af37;font-size:1.1rem;font-weight:700'>{_order_status}</p>"
                f"<hr style='border-color:#2D333B;margin:8px 0'>"
                f"<p>📰 今日新闻: <strong style='color:#d4af37'>{total_news or '–'}</strong></p>"
                f"<p>🎯 提取事件: <strong style='color:#d4af37'>{total_events or '–'}</strong></p>"
                f"<p>🔴 高危事件: <strong style='color:#d4af37'>{high_events or '–'}</strong></p>"
                f"<p>📊 平均置信度: <strong style='color:#d4af37'>{_conf_display}</strong></p>"
                f"<hr style='border-color:#2D333B;margin:8px 0'>"
                f"<p>💡 实体节点: <strong style='color:#d4af37'>{_kg_entities}</strong></p>"
                f"<p>🔗 语义关系: <strong style='color:#d4af37'>{_kg_relations}</strong></p>"
                f"<p>⚖️ 关系/实体比: <strong style='color:#d4af37'>{_rel_ent_ratio:.2f}</strong></p>"
                f"</div>",
                unsafe_allow_html=True,
            )
    except ImportError:
        _val_str = f"{_order_score:.1f}/100" if _has_data else "–"
        st.metric("秩序指数 (Systemic Order Score)", _val_str)

    st.divider()

    # ── Section 2: Signal vs Noise Balance ───────────────────────────────────
    st.markdown("## 📡 Signal vs Noise Balance")
    _signal_articles = _kg_articles   # KG-processed articles = signal
    _total_for_ratio = max(total_news, _kg_articles)
    _signal_ratio, _noise_ratio = calculate_signal_noise_ratio(
        articles_with_entities=_signal_articles,
        total_articles=_total_for_ratio,
    )
    _noise_articles = max(0, _total_for_ratio - _signal_articles)

    try:
        import plotly.graph_objects as _go

        _sn_col1, _sn_col2 = st.columns([1, 2])
        with _sn_col1:
            st.metric(
                label="Signal Rate",
                value=f"{_signal_ratio:.0%}",
                delta=f"{_signal_articles} articles processed",
            )
            st.metric(
                label="Noise Rate",
                value=f"{_noise_ratio:.0%}",
                delta=f"{_noise_articles} articles pending",
            )
        with _sn_col2:
            if _total_for_ratio > 0:
                _fig_signal = _go.Figure(data=[
                    _go.Pie(
                        labels=["✅ Signal (Processed)", "⚠️ Noise (Raw)"],
                        values=[max(_signal_articles, 0), max(_noise_articles, 0)],
                        hole=0.4,
                        marker=dict(
                            colors=[_SIGNAL_GREEN, _ORDER_CHAOS_GRADIENT[-1]],
                            line=dict(color="#ffffff", width=2),
                        ),
                        textinfo="label+percent",
                        hovertemplate="%{label}<br>%{value} articles<br>%{percent}<extra></extra>",
                    )
                ])
                _fig_signal.update_layout(
                    height=280,
                    margin=dict(l=0, r=0, t=30, b=0),
                    paper_bgcolor="#ffffff",
                    font=dict(color=_THEME_DARK_BLUE),
                    legend=dict(font=dict(size=11)),
                )
                st.plotly_chart(_fig_signal, use_container_width=True)
            else:
                st.info("📭 暂无新闻数据，请先聚合新闻。")
    except ImportError:
        st.info("安装 plotly 可以查看 Signal/Noise 图：`pip install plotly`")

    st.divider()

    # ── Section 3: Event type breakdown (Order-Chaos gradient) ───────────────
    if events_live:
        try:
            import plotly.express as _px
            import plotly.graph_objects as _go
            import pandas as _pd

            # Impact-weight mapping: long-term / global / irreversible = higher weight.
            _EVENT_WEIGHTS: Dict[str, float] = {
                "地缘政治": 2.5, "政治冲突": 2.5, "军事行动": 2.5, "geopolitics": 2.5,
                "外交事件": 2.0,
                "科技突破": 2.0, "技术突破": 2.0, "technology": 2.0,
                "制度创新": 1.8, "institution": 1.8,
                "经济波动": 1.2, "贸易摩擦": 1.2, "economic": 1.2,
                "自然灾害": 1.0, "人道危机": 1.0, "恐怖袭击": 1.0,
            }
            _DEFAULT_WEIGHT = 0.8

            _df_events = _pd.DataFrame(events_live)
            _df_types = (
                _df_events
                .groupby("event_type", as_index=False)
                .size()
                .rename(columns={"size": "count"})
            )
            _df_types["weight"] = _df_types["event_type"].map(
                lambda t: _EVENT_WEIGHTS.get(str(t), _DEFAULT_WEIGHT)
            )
            _df_types["weighted_score"] = (_df_types["count"] * _df_types["weight"]).round(1)
            _df_types = _df_types.sort_values("weighted_score", ascending=False)

            # Map each bar to an Order-Chaos gradient colour based on its weighted score
            _max_ws = float(_df_types["weighted_score"].max()) if len(_df_types) > 0 else 1.0
            _bar_colors = [
                _ORDER_CHAOS_GRADIENT[
                    int((v / max(_max_ws, 0.01)) * (len(_ORDER_CHAOS_GRADIENT) - 1))
                ]
                for v in _df_types["weighted_score"].tolist()
            ]

            _chart_col, _pie_col = st.columns(2)

            with _chart_col:
                st.subheader("📊 事件分布（影响力权重 · 秩序-混沌渐变）")
                st.caption("各类事件按影响力权重排序，颜色从蓝（秩序）→ 红（混沌）")
                _fig_w = _go.Figure(data=[
                    _go.Bar(
                        x=_df_types["event_type"].tolist(),
                        y=_df_types["weighted_score"].tolist(),
                        marker=dict(
                            color=_bar_colors,
                            line=dict(color=_THEME_ACCENT_GOLD, width=1),
                        ),
                        text=_df_types["weighted_score"].tolist(),
                        textposition="auto",
                        hovertemplate="%{x}<br>%{y:.1f} 加权分<extra></extra>",
                    )
                ])
                _fig_w.update_layout(
                    showlegend=False,
                    plot_bgcolor="#f8f9fa",
                    paper_bgcolor="#ffffff",
                    xaxis_tickangle=-30,
                    xaxis_title="事件类型",
                    yaxis_title="影响力加权分",
                )
                st.plotly_chart(_fig_w, use_container_width=True)

            with _pie_col:
                st.subheader("📊 严重级别分布")
                _df_sev = (
                    _df_events
                    .groupby("severity", as_index=False)
                    .size()
                    .rename(columns={"size": "count"})
                )
                _fig_sev = _px.pie(
                    _df_sev,
                    names="severity",
                    values="count",
                    color="severity",
                    color_discrete_map={
                        "high": "#e74c3c",
                        "medium": "#f39c12",
                        "low": "#2ecc71",
                    },
                )
                st.plotly_chart(_fig_sev, use_container_width=True)

        except ImportError:
            st.info("安装 plotly 和 pandas 可以查看图表：`pip install plotly pandas`")
    else:
        st.info("🚧 请先聚合新闻和提取事件，仪表板将显示实时统计。")

    st.divider()

    # ── Section 4: Entity Order Importance distribution ───────────────────────
    st.markdown("## 🌐 Entity Order Importance Distribution")
    if _kg_entities > 0:
        try:
            import plotly.graph_objects as _go

            # Fetch entities and relations to compute per-entity degree
            _entities_resp = _api.get_kg_entities(limit=500)
            _relations_resp = _api.get_kg_relations(limit=1000)

            _entities_list = (
                _entities_resp.get("entities", [])
                if "error" not in _entities_resp else []
            )
            _relations_list = (
                _relations_resp.get("relations", [])
                if "error" not in _relations_resp else []
            )

            if _entities_list:
                # Compute undirected degree from relations (subject + object)
                _degrees: Dict[str, int] = {}
                for _rel in _relations_list:
                    _subj = _rel.get("subject", _rel.get("from", ""))
                    _obj = _rel.get("object", _rel.get("to", ""))
                    if _subj:
                        _degrees[_subj] = _degrees.get(_subj, 0) + 1
                    if _obj:
                        _degrees[_obj] = _degrees.get(_obj, 0) + 1

                _entity_groups = categorize_entities_by_order(_entities_list, _degrees)
                _group_names = list(_entity_groups.keys())
                _group_counts = [len(_entity_groups[g]) for g in _group_names]

                if any(c > 0 for c in _group_counts):
                    _fig_importance = _go.Figure(data=[
                        _go.Pie(
                            labels=_group_names,
                            values=_group_counts,
                            marker=dict(
                                colors=_ORDER_CHAOS_GRADIENT[:len(_group_names)],
                                line=dict(color="#ffffff", width=2),
                            ),
                            textposition="auto",
                            hovertemplate=(
                                "%{label}<br>%{value} entities<br>%{percent}<extra></extra>"
                            ),
                        )
                    ])
                    _fig_importance.update_layout(
                        height=380,
                        title_text="Entities by Order Importance Tier",
                        title_font=dict(size=16, color=_THEME_DARK_BLUE),
                        paper_bgcolor="#ffffff",
                        font=dict(color=_THEME_DARK_BLUE),
                        legend=dict(font=dict(size=11)),
                        margin=dict(l=20, r=20, t=60, b=20),
                    )

                    _imp_col1, _imp_col2 = st.columns([2, 1])
                    with _imp_col1:
                        st.plotly_chart(_fig_importance, use_container_width=True)
                    with _imp_col2:
                        st.markdown("**秩序重要性等级**")
                        for _gname, _gcount in zip(_group_names, _group_counts):
                            if _gcount > 0:
                                st.markdown(f"- **{_gname}**: {_gcount} 个实体")
                else:
                    st.info("📭 实体度数数据不足，请先构建知识图谱。")
            else:
                st.info("📭 暂无实体数据，请先聚合新闻并提取知识图谱。")
        except ImportError:
            st.info("安装 plotly 可以查看实体重要性图：`pip install plotly`")
    else:
        st.info("📭 知识图谱为空，请先聚合新闻并提取实体。")

    st.divider()

    # ── Knowledge graph summary metrics ──────────────────────────────────────
    if "error" not in kg_stats_resp:
        with st.container(border=True):
            st.subheader("🕸️ 知识图谱")
            _k1, _k2, _k3, _k4 = st.columns(4)
            _k1.metric("🔵 实体", _kg_entities)
            _k2.metric("📰 文章", _kg_articles)
            _k3.metric("🔗 提及", _kg_mentions)
            _k4.metric("⚡ 关系", _kg_relations)

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
