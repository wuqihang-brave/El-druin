"""
EL'druin Intelligence Platform – Streamlit Frontend
====================================================

Multi-page application providing:
  📰  Real-time News   – aggregated news with filtering and search
  ⚙️   System Status   – backend health and source configuration

Run::

    streamlit run frontend/app.py

The app expects the FastAPI backend to be reachable at the URL
configured via the BACKEND_URL environment variable.
"""

import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

# Allow ``from utils.api_client import api_client`` when the working directory
# is the repo root *or* the frontend directory.
_FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _FRONTEND_DIR not in sys.path:
    sys.path.insert(0, _FRONTEND_DIR)

from utils.api_client import APIClient  # noqa: E402 – after sys.path patch
from components.sidebar import render_sidebar_navigation  # noqa: E402

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
    page_title="EL-DRUIN • Ontological Intelligence",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS – Light Blue Rational / Ratio Lucis theme
# ---------------------------------------------------------------------------
_CSS_PATH = os.path.join(_FRONTEND_DIR, "assets", "custom_styles_light.css")
try:
    with open(_CSS_PATH, encoding="utf-8") as _css_file:
        _css_content = _css_file.read()
    st.markdown(f"<style>{_css_content}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    logger.warning("custom_styles_light.css not found at %s; using inline fallback.", _CSS_PATH)
    st.markdown(
        """
        <style>
        :root {
          --color-bg-primary: #F0F8FF; --color-bg-secondary: #FFFFFF;
          --color-text-primary: #333333; --color-text-secondary: #606060;
          --color-accent: #0047AB; --color-accent-dark: #003580;
          --color-border: #E0E0E0; --color-sidebar-bg: #F5F5F5;
        }
        .stApp, .main, body { background-color: var(--color-bg-primary) !important; color: var(--color-text-primary) !important; }
        [data-testid="stAppViewContainer"] { background-color: var(--color-bg-primary) !important; }
        section[data-testid="stSidebar"] { background-color: var(--color-sidebar-bg) !important; border-right: 1px solid var(--color-border) !important; }
        section[data-testid="stSidebar"] * { color: var(--color-accent) !important; }
        h1, h2, h3, h4, h5, h6 { color: var(--color-accent) !important; }
        .stMarkdown, .stMarkdown p { color: var(--color-text-primary) !important; }
        a { color: var(--color-accent) !important; }
        a:hover { color: var(--color-accent-dark) !important; text-decoration: underline !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Elite Scenario Simulation Dashboard – Additional Styles
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    .stApp { background-color: #F8FAFB; }
    .stApp p, .stApp span { color: #2C3E50; }
    .news-card {
        background: white; border-radius: 6px; padding: 16px;
        border-left: 4px solid #0047AB;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 12px;
        transition: all 0.2s ease;
    }
    .news-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.12); border-left-color: #003580; }
    .scenario-alpha {
        background: #FFFBF0; border-left: 4px solid #D4AF37;
        padding: 16px; border-radius: 6px; margin-bottom: 16px;
    }
    .scenario-alpha-header {
        color: #B8860B; font-weight: 600; font-size: 14px;
        text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;
    }
    .scenario-beta {
        background: #FEF5F5; border-left: 4px solid #DC3545;
        padding: 16px; border-radius: 6px; margin-bottom: 16px;
    }
    .scenario-beta-header {
        color: #C82333; font-weight: 600; font-size: 14px;
        text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;
    }
    .causal-chain {
        background: #F5F5F5; border: 1px solid #E0E0E0; border-radius: 4px;
        padding: 12px; font-family: 'Courier New', monospace; font-size: 12px;
        color: #333; line-height: 1.6;
    }
    .entity-tag {
        display: inline-block; background: #E8F0FE; color: #0047AB;
        padding: 4px 8px; border-radius: 3px; font-size: 11px;
        margin-right: 6px; margin-bottom: 4px; font-weight: 500;
    }
   
    .metric-value { font-size: 28px; font-weight: 700; color: #0047AB; }
    .metric-label {
        font-size: 12px; color: #999; margin-top: 4px;
        text-transform: uppercase; letter-spacing: 0.3px;
    }
    .elite-divider {
        height: 1px;
        background: linear-gradient(to right, transparent, #DDD, transparent);
        margin: 24px 0;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Backend URL (env-configurable)
# ---------------------------------------------------------------------------
_backend_url_raw = os.environ.get("BACKEND_URL")
if not _backend_url_raw:
    raise RuntimeError(
        "BACKEND_URL environment variable is not set. "
        "Please configure it in your deployment environment. "
        "Expected format: https://your-backend-domain.com/api/v1"
    )
_backend_url = _backend_url_raw.rstrip("/")

def get_graph_context_for_news(query_text):
    """从 KuzuDB 获取与新闻关键词相关的图谱事实"""
    import kuzu
    db_path = './data/kuzu_db.db'
    if not os.path.exists(db_path):
        return "数据库尚未初始化。"
    try:
        db = kuzu.Database(db_path)
        conn = kuzu.Connection(db)
        # 提取标题前两个词作为关键词
        keywords = [w for w in query_text.split() if len(w) > 2][:2] 
        context_facts = []
        for word in keywords:
            # 这里的模糊匹配逻辑
            cypher = f"MATCH (s)-[r]->(t) WHERE s.name CONTAINS '{word}' OR t.name CONTAINS '{word}' RETURN s.name, label(r), t.name, r.logic_weight LIMIT 3"
            res = conn.execute(cypher)
            while res.has_next():
                row = res.get_next()
                context_facts.append(f"- 事实: {row[0]} --[{row[1]}]--> {row[2]} (权重: {row[3]})")
        return "\n".join(set(context_facts)) if context_facts else "未找到关联图谱事实。"
    except Exception as e:
        return f"查询提示: {str(e)}"

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
        "<hr style='border-color:#E0E0E0;margin:4px 0 6px 0'/>",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        "<p style='color:#0047AB;font-size:0.78rem;margin:0 0 4px 0;"
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
# Sidebar – Configuration Panel (collapsed expander)
# ---------------------------------------------------------------------------
st.sidebar.markdown(
    "<hr style='border-color:#E0E0E0;margin:8px 0 6px 0'/>",
    unsafe_allow_html=True,
)
with st.sidebar.expander("⚙️ 配置面板", expanded=False):
    from datetime import date as _date

    st.markdown("**📡 数据源**")
    _sidebar_data_source = st.selectbox(
        "选择数据源",
        ["实时新闻", "历史数据", "自定义输入"],
        key="cfg_data_source",
        label_visibility="collapsed",
    )
    st.markdown("**📅 日期范围**")
    _today_cfg = _date.today()
    _dcol1, _dcol2 = st.columns(2)
    with _dcol1:
        _cfg_date_from = st.date_input(
            "开始",
            value=_date(_today_cfg.year, _today_cfg.month, 1),
            key="cfg_date_from",
            label_visibility="collapsed",
        )
    with _dcol2:
        _cfg_date_to = st.date_input(
            "结束",
            value=_today_cfg,
            key="cfg_date_to",
            label_visibility="collapsed",
        )
    st.markdown("**🤖 分析模式**")
    _cfg_model_mode = st.radio(
        "模式",
        ["本体论模式", "快速模式", "深度模式"],
        key="cfg_model_mode",
        label_visibility="collapsed",
    )

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
    "<hr style='border-color:#E0E0E0;margin:8px 0 6px 0'/>",
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
_KG_EDGE_COLOR = "#A0A0A0"  # Ultra-thin light grey edge colour (Clear Day theme)

# Node colour constants – three-layer hierarchy (leaf → bridge → hub)
# Clear Day theme: cobalt blue hubs, soft grey bridge, light fringe
_NODE_COLOR_LEAF   = "#E0E0E0"  # Light Grey   – isolated / leaf nodes
_NODE_COLOR_BRIDGE = "#A0C4E8"  # Soft Blue    – bridge / connector nodes
_NODE_COLOR_HUB    = "#0047AB"  # Cobalt Blue  – central hub nodes


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
            border: 1px solid #E0E0E0;
            border-radius: 4px;
            padding: 14px 16px 14px 20px;
            background-color: #FFFFFF;
            margin-bottom: 14px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
            border-left: 4px solid {color};
        ">
            <div style="display:flex; justify-content:space-between; align-items:baseline;">
                <strong style="font-size:1.02rem; color:#333333; font-family:'Inter',sans-serif;">{title}</strong>
                <span style="
                    background:{color};
                    color:#FFFFFF;
                    border-radius:12px;
                    padding:2px 10px;
                    font-size:0.75rem;
                    font-weight:600;
                    white-space:nowrap;
                    margin-left:8px;
                ">{cat_label}</span>
            </div>
            <p style="color:#606060; font-size:0.87rem; margin:6px 0 4px 0; font-family:'Inter',sans-serif;">{summary}</p>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:6px;">
                <span style="font-size:0.78rem; color:#A0A0A0; font-family:'Inter',sans-serif;">
                    {("📌 " + source) if source else ""}{"&nbsp;&nbsp;" if source and pub else ""}
                    {("⏰ " + pub) if pub else ""}
                </span>
                {"<a href='" + url + "' target='_blank' style='font-size:0.82rem;color:#0047AB;'>View Full →</a>" if url else ""}
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
# Page: 🏠 主页  –  Elite Scenario Simulation Dashboard
# ===========================================================================
if page == "🏠 主页":
    # ── 1. 注入紧凑型与预测风格 CSS ─────────────────────────────────────────
    st.markdown("""
        <style>
        .compact-news { 
            padding: 10px 12px; border-left: 3px solid #0047AB; 
            background: #ffffff; margin-bottom: 6px; 
            box-shadow: 0 1px 2px rgba(0,0,0,0.05); border-radius: 4px;
        }
        .compact-news:hover { border-left-color: #d94949; background: #fdfdfd; }
        .prediction-box { 
            border-left: 4px solid #d94949; background: #FEF5F5; 
            padding: 16px; border-radius: 4px; margin: 10px 0;
            color: #C82333; font-size: 1.05rem; line-height: 1.5;
        }
        .math-logic { 
            font-family: 'JetBrains Mono', 'Courier New', monospace; 
            background: #1e1e1e; color: #4af626; 
            padding: 12px; font-size: 0.85rem; border-radius: 6px; 
            letter-spacing: 0.5px; margin-top: 10px;
        }
        .elite-divider { height: 1px; background: linear-gradient(to right, transparent, #DDD, transparent); margin: 20px 0; }
        </style>
    """, unsafe_allow_html=True)

    # ── Page header ──────────────────────────────────────────────────────────
    _col_header1, _col_header2 = st.columns([4, 1])
    with _col_header1:
        st.markdown("# 🎯 EL-DRUIN 核心预测与本体推演")
    with _col_header2:
        st.markdown(f"**Update:** {datetime.now().strftime('%H:%M CST')}")
    st.markdown('<div class="elite-divider"></div>', unsafe_allow_html=True)

    # ── Session-state defaults ───────────────────────────────────────────────
    if "selected_news" not in st.session_state:
        st.session_state.selected_news: Optional[Dict[str, Any]] = None
    if "deduction_result" not in st.session_state:
        st.session_state.deduction_result: Optional[Dict[str, Any]] = None

    # ── Main content: 40/60 split ────────────────────────────────────────────
    col_feed, col_deduction = st.columns([4, 6], gap="large")

    # ─── LEFT COLUMN: 高密度关键情报流 (40%) ─────────────────────────────────
    with col_feed:
        st.subheader("📍 重要情报摘要")

        _feed_news: List[Dict[str, Any]] = []
        try:
            _news_resp = _api.get_latest_news(limit=6, hours=72) # 增加条数以体现紧凑
            _feed_news = _news_resp.get("articles", [])
        except Exception:
            pass

        # 降级备用数据
        if not _feed_news:
            _feed_news = [
                {"title": "European Commission Announces AI Regulation", "source": "Reuters", "published": "2026-03-25", "description": "The EU unveiled strict new AI regulations..."},
                {"title": "Federal Reserve Signals Rate Hike", "source": "Bloomberg", "published": "2026-03-24", "description": "The US Federal Reserve signaled a possible interest rate increase citing inflation..."}
            ]

        for _idx, _article in enumerate(_feed_news[:6]):
            _title = _article.get("title") or "（无标题）"
            _source = _article.get("source", "")
            _pub = str(_article.get("published") or _article.get("date", ""))[:10]
            _summary = (_article.get("description") or _article.get("summary", ""))[:60] + "..."

            st.markdown(f"""
            <div class="compact-news">
                <div style="font-weight:600; font-size:14px; color:#333; margin-bottom:4px;">{_title[:45]}...</div>
                <div style="font-size:12px; color:#666; margin-bottom:6px;">{_summary}</div>
                <div style="font-size:11px; color:#999; display:flex; justify-content:space-between;">
                    <span>{_source}</span><span>{_pub}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if st.button("🎯 执行本体推演", key=f"deduce_{_idx}_{_article.get('link', _title)}", use_container_width=True):
                st.session_state.selected_news = _article
                st.session_state.deduction_result = None
                st.rerun()

    # ─── RIGHT COLUMN: 确切推论与预测引擎 (60%) ────────────────────────────────
       # ─── RIGHT COLUMN: 确切推论与预测引擎 (60%) ─────────────────
    with col_deduction:
        st.subheader("🧠 本体论预测分析")

        _selected = st.session_state.get("selected_news")
        if _selected:
            _sel_title = _selected.get("title", "（无标题）")
            _sel_desc = _selected.get("description") or _selected.get("summary") or ""
            st.markdown(f"**针对事件：** `{_sel_title}`")
            st.markdown('<div class="elite-divider"></div>', unsafe_allow_html=True)

            _deduction_result: Optional[Dict[str, Any]] = st.session_state.get(
                "deduction_result"
            )
            _deduction_error: Optional[str] = None

            # === 1. 首次点击时，真正调用后端推理 ===
            if _deduction_result is None:
                with st.status("🔍 正在构建因果链条（LLM + 本体 + KuzuDB）...", expanded=True) as _status:
                    try:
                        st.write("📡 调用后端 grounded_deduce 接口，并检索 KuzuDB 证据...")

                        # 建议：显式传入文本字段，避免后端拿到奇怪的结构
                        _payload = {
                            "title": _sel_title,
                            "text": _sel_desc or _sel_title,
                            "source": _selected.get("source"),
                            "published": str(_selected.get("published", "")),
                            "raw": _selected,   # 原始对象一并传给后端（如果不需要可在后端忽略）
                        }
                        _resp = _api.grounded_deduce(_payload)

                        # 兼容两种返回格式：
                        #  1) {"deduction_result": {...}}
                        #  2) 直接返回 {...}
                        if "error" in _resp and "deduction_result" not in _resp:
                            _deduction_error = str(_resp["error"])
                            _status.update(label="⚠ 推演失败", state="error")
                        else:
                            _deduction_result = _resp.get(
                                "deduction_result", _resp
                            )
                            st.session_state.deduction_result = _deduction_result
                            st.write("✅ 已获取本体推理结果与图谱证据，正在渲染...")
                            _status.update(label="✅ 推演完成", state="complete")
                    except Exception as _exc:
                        _deduction_error = str(_exc)
                        _status.update(label="⚠ 连接失败", state="error")

            # === 2. 处理错误  ===
            if _deduction_error:
                st.error(f"推演失败：{_deduction_error}")

            # === 3. 正常展示推理结果 ===
            elif _deduction_result is not None:
                _dr = _deduction_result

                # -------- 3.1 提取后端字段（尽量不用占位文本） --------
                # 主预测 / 核心情景
                _alpha = _dr.get("scenario_alpha") or _dr.get("primary_scenario") or {}
                _alpha_desc = (
                    _alpha.get("description")
                    or _dr.get("prediction")
                    or _dr.get("summary")
                    or ""
                )
                if not _alpha_desc:
                    # 仍然没有任何说明时，再用占位文本兜底
                    _alpha_desc = "（后端未返回场景描述，请检查 grounded_deduce 返回结构。）"

                # 因果链 / 驱动路径
                _causal_chain = (
                    _alpha.get("causal_chain")
                    or _dr.get("causal_chain")
                    or _dr.get("driving_factor")
                    or _dr.get("inference_path")
                    or ""
                )

                # 置信度
                _conf_raw = (
                    _dr.get("confidence")
                    or _alpha.get("confidence")
                    or 0.5
                )
                try:
                    _conf_raw = float(_conf_raw)
                except Exception:
                    _conf_raw = 0.5
                _conf_pct = int(round(_conf_raw * 100)) if _conf_raw <= 1.0 else int(
                    round(_conf_raw)
                )

                # 图谱证据（后端优先，其次用本地 Kuzu 查询补充）
                _graph_evidence = (
                    _dr.get("graph_evidence")
                    or _dr.get("graph_facts")
                    or _dr.get("evidence_paths")
                    or []
                )
                if not _graph_evidence:
                    # 使用前面定义的本地函数，从 KuzuDB 拉一些相关事实
                    _graph_evidence = get_graph_context_for_news(
                        _sel_title + " " + _sel_desc
                    )

                # 如果后端给了完整子图结构（nodes/edges），我们可以直接画图
                _subgraph = _dr.get("graph_subgraph") or {}
                # 期望格式：
                #   {"nodes": [...], "edges": [...]}
                # 与 render_graph 所需格式一致即可直接渲染

                # -------- 3.2 确切推论（替代固定占位文案） --------
                st.markdown("### 🔮 确切推论")
                st.markdown(
                    f"""
                    <div class="prediction-box">
                        <b>预测演化：</b> {_alpha_desc}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.markdown("---")

                # -------- 3.3 成因与逻辑硬度 --------
                st.markdown("### 📊 推论成因与逻辑硬度")
                _col_logic, _col_math = st.columns([3, 2])

                with _col_logic:
                    st.write("**逻辑成因**")
                    items: List[str] = []

                    if isinstance(_causal_chain, str) and _causal_chain.strip():
                        items.append(_causal_chain)
                    elif isinstance(_causal_chain, list):
                        items.extend([str(x) for x in _causal_chain if x])

                    # 如果后端有更结构化的 "reasoning_steps" 字段，也一并展示
                    _steps = _dr.get("reasoning_steps") or _alpha.get("steps") or []
                    if isinstance(_steps, list):
                        items.extend([str(x) for x in _steps if x])

                    if not items:
                        items.append("（后端未提供详细因果链，请在 backend.grounded_deduce 中补充 'causal_chain' 或 'reasoning_steps' 字段。）")

                    for idx, text in enumerate(items[:4], start=1):
                        st.caption(f"{idx}. {text}")

                    if len(items) > 4:
                        st.caption(f"... 等 {len(items)} 条推理步骤")

                with _col_math:
                    st.write("**预测概率**")
                    st.metric(
                        label="Pr(Event | Graph)",
                        value=f"{_conf_pct}%",
                        delta=f"+{max(1, _conf_pct % 4)}% 动量累积",
                    )

                st.markdown("**本体论计算模型**")
                st.markdown(
                    f"""
                    <div class="math-logic">
                    # Inference Trajectory<br>
                    Pr(E|K) = ∑ [W(n) * R(p)] / Ω <br>
                    Confidence = Δ(Ontology_Density) / Threshold = {_conf_pct / 100:.2f} <br>
                    [System State] -> Converging
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # -------- 3.4 图谱证据 可视化 / 列表 --------
                st.markdown("---")
                st.markdown("### 🕸 图谱证据与路径")

                # 3.4.1 如果后端返回了子图（graph_subgraph），直接画
                if isinstance(_subgraph, dict) and _subgraph.get("nodes"):
                    st.caption("来自后端 grounded_deduce 的聚焦子图：")
                    try:
                        render_graph(_subgraph)
                    except Exception as _e:
                        st.warning(f"子图渲染失败：{_e}")

                # 3.4.2 若没有子图，但有字符串 / 列表形式的事实，则文本展示
                elif _graph_evidence:
                    st.caption("相关图谱事实：")
                    if isinstance(_graph_evidence, str):
                        st.text(_graph_evidence)
                    elif isinstance(_graph_evidence, list):
                        for fact in _graph_evidence:
                            st.write(f"- {fact}")
                    else:
                        st.json(_graph_evidence)

                else:
                    st.info("未从本体图谱中检索到显式证据，请检查 KuzuDB 同步及后端推理逻辑。")

                # -------- 3.5 调试用：显示原始返回结构，方便你后续调整字段映射 --------
                with st.expander("🛠 调试：查看后端原始推理结果 JSON", expanded=False):
                    st.json(_dr)

            if st.button("🔄 重新选择情报", key="clear_selection"):
                st.session_state.selected_news = None
                st.session_state.deduction_result = None
                st.rerun()
        else:
            st.info("👈 请在左侧选择一个重要事件执行本体推演")


    # ─── FOOTER: 知识储备 (替代报错的谍报缺口) ──────────────────────────────
    st.markdown('<div class="elite-divider"></div>', unsafe_allow_html=True)
    with st.expander("ℹ️ 相关本体知识储备 (Active Sub-Graphs)"):
        st.write("""
        **当前关联逻辑库引擎在线状态：**
        * 🟢 **[宏观经济本体]**：流动性、杠杆率、抵押品价值链。
        * 🟢 **[地缘政治本体]**：供应链节点、关税杠杆、能源与资源依赖度。
        * 🟡 **[技术变迁本体]**：技术扩散率、政策阻力、合规成本矩阵 (待深度构建)。
        *(上述底层图谱持续为预测引擎提供路径支撑)*
        """)

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
                    f"<div style='background:#F5F5F5;border:1px solid #E0E0E0;border-radius:4px;"
                    f"padding:8px 12px;margin-bottom:4px;font-family:\"JetBrains Mono\",monospace;"
                    f"font-size:13px;color:#606060'>{_item['query']}</div>",
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
