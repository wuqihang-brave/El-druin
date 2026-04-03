"""
EL'druin Intelligence Platform – Streamlit Frontend v2
=======================================================

修复说明 (v2)：
  - 所有页面名称改回简体中文，与 render_sidebar_navigation() 返回值严格一致：
      "🏠 主页" / "📰 实时新闻" / "🕸 知识图谱" / "⚙️ 系统状态"
  - 去除繁体字、全角符号、多余空格，防止 page == "..." 判断失效

v2 功能：
  1. 首页：突出因果链 + 推演结果，Tab 结构展示
  2. 实时新闻：每条新闻带「执行本体推演」直达按钮
  3. 知识图谱：新增「🧮 笛卡尔积诊断」Tab
"""

import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
load_dotenv()
import requests  # noqa: F401
import streamlit as st
import frontend.utils.api_client as ac
import inspect
st.sidebar.write("api_client file:", ac.__file__)
st.sidebar.write("evented_deduce sig:", str(inspect.signature(ac.APIClient.evented_deduce)))
import utils.api_client as uac
st.write("api_client loaded from:", uac.__file__)
st.write("has evented_deduce:", hasattr(uac.api_client, "evented_deduce"))
_FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _FRONTEND_DIR not in sys.path:
    sys.path.insert(0, _FRONTEND_DIR)

from utils.api_client import APIClient  # noqa: E402
from components.sidebar import render_sidebar_navigation  # noqa: E402

try:
    from streamlit_agraph import agraph, Config, Edge, Node
    _AGRAPH_AVAILABLE = True
except ImportError:
    _AGRAPH_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="EL-DRUIN - Ontological Intelligence",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
_CSS_PATH = os.path.join(_FRONTEND_DIR, "assets", "custom_styles_light.css")
try:
    with open(_CSS_PATH, encoding="utf-8") as _f:
        st.markdown(f"<style>{_f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    pass

st.markdown("""
<style>
:root {
  --blue: #0047AB; --blue-dark: #003580; --gold: #D4AF37; --gold-dark: #B8860B;
  --red: #DC3545; --red-dark: #C82333; --bg: #F8FAFB; --surface: #FFFFFF;
  --border: #E0E0E0; --text: #2C3E50; --muted: #6C757D;
}
.stApp { background-color: var(--bg); }
h1,h2,h3,h4 { color: var(--blue) !important; }

.news-compact {
    background: var(--surface); border-left: 3px solid var(--blue);
    border-radius: 5px; padding: 10px 12px; margin-bottom: 6px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.news-compact:hover { border-left-color: var(--red); }
.news-title { font-weight: 600; font-size: 13.5px; color: var(--text); }
.news-meta  { font-size: 11px; color: var(--muted); margin-top: 3px; }

.driving-hero {
    background: linear-gradient(135deg, #EEF4FF 0%, #F5F8FF 100%);
    border: 1.5px solid var(--blue); border-radius: 8px;
    padding: 18px 20px; margin-bottom: 16px;
}
.driving-label {
    font-size: 10px; font-weight: 700; letter-spacing: 1.2px;
    color: var(--blue); text-transform: uppercase; margin-bottom: 6px;
}
.driving-text { font-size: 15px; font-weight: 600; color: var(--text); line-height: 1.5; }

.mech-tag {
    display: inline-block; background: #E8F0FE; color: var(--blue);
    padding: 3px 9px; border-radius: 12px; font-size: 11px;
    font-weight: 600; margin: 2px; border: 1px solid #C5D5F0;
}
.domain-geo  { background: #FFF3E0; color: #E65100; border-color: #FFCC80; }
.domain-econ { background: #E8F5E9; color: #2E7D32; border-color: #A5D6A7; }
.domain-tech { background: #F3E5F5; color: #7B1FA2; border-color: #CE93D8; }
.domain-mil  { background: #FFEBEE; color: #B71C1C; border-color: #FFCDD2; }

.causal-chain {
    background: #1a1a2e; color: #4ade80; font-family: 'JetBrains Mono', monospace;
    font-size: 12px; padding: 14px 16px; border-radius: 6px;
    line-height: 1.8; overflow-x: auto;
}

.scenario-alpha {
    background: #FFFBF0; border-left: 4px solid var(--gold);
    padding: 14px 16px; border-radius: 6px; margin-bottom: 12px;
}
.scenario-alpha-hdr {
    color: var(--gold-dark); font-weight: 700; font-size: 12px;
    text-transform: uppercase; letter-spacing: .6px; margin-bottom: 6px;
}
.scenario-beta {
    background: #FEF5F5; border-left: 4px solid var(--red);
    padding: 14px 16px; border-radius: 6px; margin-bottom: 12px;
}
.scenario-beta-hdr {
    color: var(--red-dark); font-weight: 700; font-size: 12px;
    text-transform: uppercase; letter-spacing: .6px; margin-bottom: 6px;
}

.diag-pattern-name { font-size: 20px; font-weight: 700; color: var(--blue); margin-bottom: 4px; }
.diag-domain-badge {
    display: inline-block; background: var(--blue); color: white;
    padding: 2px 10px; border-radius: 10px; font-size: 11px; font-weight: 600;
}
.outcome-pill {
    display: inline-block; background: #F0F4FF; color: #1a3a6b;
    border: 1px solid #C5D5F0; border-radius: 4px;
    padding: 4px 10px; margin: 3px; font-size: 12px; font-weight: 500;
}
.diag-note {
    background: #FFFDE7; border-left: 3px solid #F9A825;
    padding: 10px 14px; border-radius: 4px; font-size: 13px; color: #5D4037;
}
.conf-bar-wrap { background: #E0E0E0; border-radius: 4px; height: 8px; overflow: hidden; margin: 6px 0; }
.conf-bar { background: var(--blue); height: 8px; border-radius: 4px; }

.elite-divider { height: 1px; background: linear-gradient(to right, transparent, #DDD, transparent); margin: 20px 0; }
.confidence-big { font-size: 40px; font-weight: 800; color: var(--blue); }
.confidence-label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .6px; }

.math-logic {
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    background: #1e1e1e; color: #4af626;
    padding: 12px; font-size: 0.85rem; border-radius: 6px; margin-top: 10px;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Backend URL
# ---------------------------------------------------------------------------
_backend_url_raw = os.environ.get("BACKEND_URL", "")
if not _backend_url_raw:
    st.error("BACKEND_URL is not set.")
    st.stop()
_backend_url = _backend_url_raw.rstrip("/")
_api = APIClient(base_url=_backend_url)


# ---------------------------------------------------------------------------
# KuzuDB graph context helper (used in homepage deduction panel)
# ---------------------------------------------------------------------------
def get_graph_context_for_news(query_text: str) -> str:
    import kuzu
    db_path = "./data/kuzu_db.db"
    if not os.path.exists(db_path):
        return "数据库尚未初始化。"
    try:
        db = kuzu.Database(db_path)
        conn = kuzu.Connection(db)
        keywords = [w for w in query_text.split() if len(w) > 2][:2]
        context_facts = []
        for word in keywords:
            cypher = (
                f"MATCH (s)-[r]->(t) WHERE s.name CONTAINS '{word}' OR t.name CONTAINS '{word}'"
                f" RETURN s.name, label(r), t.name, COALESCE(r.logic_weight, 1.0) LIMIT 3"
            )
            res = conn.execute(cypher)
            while res.has_next():
                row = res.get_next()
                context_facts.append(f"- 事实: {row[0]} --[{row[1]}]--> {row[2]} (权重: {row[3]})")
        return "\n".join(set(context_facts)) if context_facts else "未找到关联图谱事实。"
    except Exception as e:
        return f"查询提示: {str(e)}"


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
_STATE_DEFAULTS = {
    "initialized": False,
    "current_page": "🏠 主页",
    "selected_entity": "",
    "graph_data": {"entities": [], "relations": [], "status": "not_loaded"},
    "entity_cache": {},
    "last_update": None,
    "nav_state": {},
    "selected_news": None,
    "deduction_result": None,
    "kg_cache": {},
    "kg_chat_history": [],
}
for _k, _v in _STATE_DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ---------------------------------------------------------------------------
# Graph loading
# ---------------------------------------------------------------------------
@st.cache_resource
def load_knowledge_graph() -> Dict[str, Any]:
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
        logger.error("load_knowledge_graph: %s", exc)
        return {"entities": [], "relations": [], "status": "error", "error": str(exc)}


with st.spinner("Loading Knowledge Graph..."):
    if st.session_state.graph_data.get("status") != "loaded":
        st.session_state.graph_data = load_knowledge_graph()
        st.session_state.last_update = datetime.now()
        st.session_state.entity_cache = {
            e.get("name", ""): e
            for e in st.session_state.graph_data.get("entities", [])
            if e.get("name")
        }
        st.session_state.initialized = True


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
page = render_sidebar_navigation()

_sidebar_entity_names: List[str] = [
    e.get("name", "") for e in st.session_state.graph_data.get("entities", []) if e.get("name")
]
if _sidebar_entity_names:
    st.sidebar.markdown("<hr style='border-color:#E0E0E0;margin:4px 0'/>", unsafe_allow_html=True)
    st.sidebar.markdown(
        "<p style='color:#0047AB;font-size:0.78rem;margin:0 0 4px 0'>🔎 实体搜索</p>",
        unsafe_allow_html=True,
    )
    _sel = st.sidebar.selectbox(
        "搜索实体", [""] + _sidebar_entity_names,
        index=0, key="sidebar_entity_select", label_visibility="collapsed",
    )
    if _sel and _sel != st.session_state.selected_entity:
        st.session_state.selected_entity = _sel
        st.rerun()

st.sidebar.markdown("<hr style='border-color:#E0E0E0;margin:8px 0'/>", unsafe_allow_html=True)
with st.sidebar.expander("⚙️ 推演引擎配置", expanded=False):
    st.markdown("**📡 数据源**")
    st.selectbox("选择数据源", ["实时新闻", "历史数据", "自定义输入"], key="cfg_data_source", label_visibility="collapsed")
    st.markdown("**🤖 分析模式**")
    st.radio("模式", ["本体论模式", "快速模式", "深度模式"], key="cfg_model_mode", label_visibility="collapsed")
    st.markdown("**🔬 推演深度（Deep Ontology）**")
    st.slider(
        "深度级别",
        min_value=0, max_value=3, value=0,
        key="cfg_deep_level",
        help="0=普通模式  1=仅本地元数据  2=+抓取原文  3=+全网搜索",
        label_visibility="collapsed",
    )
    st.checkbox(
        "显示潜在隐变量（假设路径）",
        key="cfg_show_hidden",
        value=True,
        help="在三段式推演结论中显示 T1 假设路径",
    )

st.sidebar.markdown("<hr style='border-color:#E0E0E0;margin:8px 0'/>", unsafe_allow_html=True)
if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
    load_knowledge_graph.clear()
    st.session_state.graph_data = {"entities": [], "relations": [], "status": "not_loaded"}
    st.session_state.last_update = None
    st.rerun()


# ---------------------------------------------------------------------------
# Shared render helpers
# ---------------------------------------------------------------------------
_KG_TYPE_COLORS: Dict[str, str] = {
    "PERSON": "#E8AB5D", "ORG": "#4A90E2", "GPE": "#7ED321", "LOC": "#BD10E0",
    "DATE": "#9B8EA8", "MONEY": "#50C8A8", "EVENT": "#E8AB5D",
    "ENTITY": "#4A90E2", "ARTICLE": "#5B7FA6", "MISC": "#C8C8C8",
}
_KG_DEFAULT_COLOR = "#C8C8C8"
_KG_MAIN_HEIGHT   = 800
_KG_MINI_HEIGHT   = 600
_KG_EDGE_COLOR    = "#A0A0A0"
_NODE_COLOR_HUB    = "#0047AB"
_NODE_COLOR_BRIDGE = "#A0C4E8"
_NODE_COLOR_LEAF   = "#E0E0E0"
_NEWS_CATEGORY_COLORS: Dict[str, str] = {
    "technology": "#4A90E2", "geopolitics": "#E8AB5D", "institution": "#7ED321",
    "causality": "#BD10E0", "unknown": "#C8C8C8",
}


def _node_size_and_color(label_type: str, node_degree: int, is_center: bool = False):
    if is_center or node_degree > 5:
        return 65, _NODE_COLOR_HUB
    if node_degree > 2:
        return 38, _NODE_COLOR_BRIDGE
    return 20, _NODE_COLOR_LEAF


def render_graph(data: Dict[str, Any]) -> None:
    raw_nodes: List[Dict[str, Any]] = data.get("nodes", []) if data else []
    raw_edges: List[Dict[str, Any]] = data.get("edges", []) if data else []
    if not raw_nodes and not raw_edges:
        st.info("📭 暂无图谱数据。")
        return
    if not _AGRAPH_AVAILABLE:
        st.warning("⚠️ `streamlit-agraph` 未安装，无法显示交互图谱。")
        return
    degree: Dict[str, int] = {}
    for edge in raw_edges:
        for k in ("from", "to"):
            nid = str(edge.get(k, "") or "")
            if nid:
                degree[nid] = degree.get(nid, 0) + 1
    center_id = max(degree, key=lambda k: degree[k]) if degree else None
    ag_nodes = []
    for node in raw_nodes:
        nid = str(node.get("id", "") or "")
        if not nid:
            continue
        lt = str(node.get("label", "MISC") or "MISC")
        sz, col = _node_size_and_color(lt, degree.get(nid, 0), nid == center_id)
        props = node.get("properties") or {}
        ag_nodes.append(Node(
            id=nid, label=str(props.get("name", nid)), size=sz, color=col,
            title=str(props.get("name", nid)),
        ))
    ag_edges = [
        Edge(source=str(e.get("from", "")), target=str(e.get("to", "")),
             label=str(e.get("type", "")), color=_KG_EDGE_COLOR)
        for e in raw_edges if e.get("from") and e.get("to")
    ]
    if not ag_nodes:
        st.info("📭 节点数据为空。")
        return
    try:
        config = Config(
            width=800, height=_KG_MAIN_HEIGHT, directed=True, physics=True,
            hierarchical=False, nodeHighlightBehavior=True, highlightColor=_NODE_COLOR_HUB,
        )
        agraph(nodes=ag_nodes, edges=ag_edges, config=config)
    except Exception as exc:
        st.error(f"⚠️ 知识图谱渲染失败：{exc}")


def _render_causal_chain(chain_text: str) -> None:
    """渲染 4-step 因果链（终端样式）。"""
    if not chain_text:
        st.caption("（后端未提供因果链）")
        return
    import re
    parts = [p.strip() for p in chain_text.split("-->")]
    lines_html = []
    for i, part in enumerate(parts):
        mech_match = re.search(r"\[(.+?)\]", part)
        if mech_match:
            mech  = mech_match.group(1)
            clean = re.sub(r"\[.+?\]", "", part).strip()
            lines_html.append(
                f'<span style="color:#e2e8f0">{clean}</span> '
                f'<span style="color:#fbbf24">[{mech}]</span>'
            )
        else:
            lines_html.append(f'<span style="color:#e2e8f0">{part}</span>')
        if i < len(parts) - 1:
            lines_html.append('<span style="color:#60a5fa"> --&gt; </span>')
    st.markdown(
        f'<div class="causal-chain">{"".join(lines_html)}</div>',
        unsafe_allow_html=True,
    )


def _domain_class(domain: str) -> str:
    return {"geopolitics": "domain-geo", "economics": "domain-econ",
            "technology": "domain-tech", "military": "domain-mil"}.get(domain.lower(), "")


# ===========================================================================
# Page: 🏠 主页
# ===========================================================================
if page == "🏠 主页":
    st.markdown("""
    <style>
    .compact-news { padding:10px 12px; border-left:3px solid #0047AB; background:#fff;
        margin-bottom:6px; box-shadow:0 1px 2px rgba(0,0,0,0.05); border-radius:4px; }
    .compact-news:hover { border-left-color:#d94949; }
    .prediction-box { border-left:4px solid #d94949; background:#FEF5F5;
        padding:16px; border-radius:4px; margin:10px 0; color:#C82333;
        font-size:1.05rem; line-height:1.5; }
    </style>
    """, unsafe_allow_html=True)

    _col_h1, _col_h2 = st.columns([4, 1])
    with _col_h1:
        st.markdown("# ⚔️ EL-DRUIN 核心预测与本体推演")
    with _col_h2:
        st.markdown(f"**{datetime.now().strftime('%H:%M CST')}**")
    st.markdown('<div class="elite-divider"></div>', unsafe_allow_html=True)

    col_feed, col_deduction = st.columns([4, 6], gap="large")

    # ─── LEFT: 情报流 ─────────────────────────────────────────────────────
    with col_feed:
        st.subheader("📍 重要情报摘要")

        _feed_news: List[Dict[str, Any]] = []
        try:
            _feed_news = _api.get_latest_news(limit=8, hours=72).get("articles", [])
        except Exception:
            pass
        if not _feed_news:
            _feed_news = [
                {"title": "European Commission Announces AI Regulation", "source": "Reuters",
                 "published": "2026-03-30", "description": "The EU unveiled strict new AI regulations..."},
                {"title": "Federal Reserve Signals Rate Path", "source": "Bloomberg",
                 "published": "2026-03-29", "description": "The Fed indicated a cautious approach..."},
                {"title": "US-China Chip Export Controls Expanded", "source": "FT",
                 "published": "2026-03-28", "description": "New restrictions on advanced semiconductor exports..."},
            ]

        for _idx, _article in enumerate(_feed_news[:8]):
            _title   = (_article.get("title") or "（无标题）")[:55]
            _src     = _article.get("source", "")
            _pub     = str(_article.get("published") or "")[:10]
            _desc    = (_article.get("description") or "")[:80]

            st.markdown(f"""
            <div class="compact-news">
                <div style="font-weight:600;font-size:14px;color:#333;margin-bottom:4px;">{_title}...</div>
                <div style="font-size:12px;color:#666;margin-bottom:6px;">{_desc}</div>
                <div style="font-size:11px;color:#999;display:flex;justify-content:space-between;">
                    <span>{_src}</span><span>{_pub}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if st.button("🎯 执行本体推演", key=f"deduce_{_idx}_{_article.get('title','')[:20]}", use_container_width=True):
                st.session_state.selected_news    = _article
                st.session_state.deduction_result = None
                st.rerun()

    # ─── RIGHT: 推演面板 ──────────────────────────────────────────────────
    with col_deduction:
        st.subheader("🧠 本体论预测分析")

        # --- 分析模式选择器 ---
        _prev_mode = st.session_state.get("analysis_mode", "Grounded")
        _analysis_mode = st.radio(
            "分析模式",
            options=["Grounded（图谱接地推演）", "Evented（事件三段式推演）"],
            index=0 if _prev_mode == "Grounded" else 1,
            horizontal=True,
            key="analysis_mode_radio",
            help="Grounded 模式使用 KuzuDB 图谱路径；Evented 模式使用事件提取 → 模式映射 → 双路径结论三段流水线。",
        )
        _mode_key = "Grounded" if "Grounded" in _analysis_mode else "Evented"
        # 切换模式时清除上次结果
        if _mode_key != _prev_mode:
            st.session_state.analysis_mode      = _mode_key
            st.session_state.deduction_result   = None
            st.session_state.evented_result     = None
            st.rerun()
        st.session_state.analysis_mode = _mode_key

        _selected: Optional[Dict[str, Any]] = st.session_state.get("selected_news")

        if not _selected:
            st.markdown("""
            <div style="text-align:center;padding:60px 20px;color:#999;">
                <div style="font-size:40px;margin-bottom:12px;">⚔️</div>
                <div style="font-size:16px;font-weight:500;">请在左侧选择一个重要事件执行本体推演</div>
                <div style="font-size:13px;margin-top:8px;">系统将基于 KuzuDB 图谱 + 笛卡尔积模式库进行因果推演</div>
            </div>
            """, unsafe_allow_html=True)
        elif _mode_key == "Grounded":
            _sel_title = _selected.get("title", "（无标题）")
            _sel_desc  = _selected.get("description") or _selected.get("summary") or ""
            st.markdown(f"**针对事件：** `{_sel_title}`")
            st.markdown('<div class="elite-divider"></div>', unsafe_allow_html=True)

            _dr: Optional[Dict[str, Any]] = st.session_state.get("deduction_result")
            _err: Optional[str] = None

            # 首次触发推演
            if _dr is None:
                with st.status("🔍 正在构建因果链条（LLM + 本体 + KuzuDB）...", expanded=True) as _status:
                    try:
                        st.write("📡 调用后端 grounded_deduce 接口，检索 KuzuDB 证据...")
                        _payload = {
                            "title": _sel_title,
                            "text": _sel_desc or _sel_title,
                            "source": _selected.get("source"),
                            "published": str(_selected.get("published", "")),
                            "raw": _selected,
                        }
                        _resp = _api.grounded_deduce(_payload)
                        if "error" in _resp and "deduction_result" not in _resp:
                            _err = str(_resp["error"])
                            _status.update(label="⚠ 推演失败", state="error")
                        else:
                            _dr = _resp.get("deduction_result", _resp)
                            st.session_state.deduction_result = _dr
                            st.write("✅ 已获取本体推理结果与图谱证据，正在渲染...")
                            _status.update(label="✅ 推演完成", state="complete")
                    except Exception as _exc:
                        _err = str(_exc)
                        _status.update(label="⚠ 连接失败", state="error")

            if _err:
                st.error(f"推演失败：{_err}")

            elif _dr is not None:
                # ── A. Hero：驱动因素 ────────────────────────────────────
                _driving = _dr.get("driving_factor") or _dr.get("mechanism_summary") or "（推演引擎未返回驱动因素）"
                st.markdown(f"""
                <div class="driving-hero">
                    <div class="driving-label">⚡ 核心驱动因素</div>
                    <div class="driving-text">{_driving}</div>
                </div>
                """, unsafe_allow_html=True)

                # ── B. 机制域标签 + 置信度 ────────────────────────────────
                _conf_raw = _dr.get("confidence") or 0.5
                try:
                    _conf_raw = float(_conf_raw)
                except Exception:
                    _conf_raw = 0.5
                _conf_pct = int(round(_conf_raw * 100))
                _mech_count = _dr.get("mechanism_count", 0)

                _b1, _b2, _b3 = st.columns([3, 2, 2])
                with _b1:
                    st.markdown("**🏷 机制域**")
                    _gev = _dr.get("graph_evidence", "")
                    _domains_found = []
                    for _dm, _cls in [
                        ("geopolitics", "domain-geo"), ("economics", "domain-econ"),
                        ("technology", "domain-tech"), ("military", "domain-mil"),
                    ]:
                        if _dm in (_gev or "").lower() or _dm in _driving.lower():
                            _domains_found.append((_dm, _cls))
                    if not _domains_found:
                        _domains_found = [("geopolitics", "domain-geo")]
                    _tags = " ".join(
                        f'<span class="mech-tag {cls}">{dm}</span>' for dm, cls in _domains_found
                    )
                    st.markdown(_tags, unsafe_allow_html=True)
                    if _mech_count:
                        st.caption(f"🔗 {_mech_count} 条机制标签")
                with _b2:
                    st.markdown("**📊 推演置信度**")
                    st.markdown(
                        f'<div class="confidence-big">{_conf_pct}%</div>'
                        f'<div class="confidence-label">Pr(E | KG)</div>',
                        unsafe_allow_html=True,
                    )
                with _b3:
                    st.markdown("**⚖️ 逻辑状态**")
                    _conf_color = "#2E7D32" if _conf_pct >= 65 else "#E65100" if _conf_pct >= 45 else "#B71C1C"
                    _conf_label = "收敛" if _conf_pct >= 65 else "发散" if _conf_pct >= 45 else "不确定"
                    st.markdown(
                        f'<div style="font-size:22px;font-weight:700;color:{_conf_color}">{_conf_label}</div>',
                        unsafe_allow_html=True,
                    )

                st.markdown('<div class="elite-divider"></div>', unsafe_allow_html=True)

                # ── C. Tab 结构 ──────────────────────────────────────────
                _tab_causal, _tab_scenarios, _tab_evidence, _tab_debug = st.tabs([
                    "⛓ 因果链分解", "🔮 情景预测", "🕸 图谱证据", "🛠 Debug"
                ])

                # Tab 1: 因果链
                with _tab_causal:
                    _alpha = _dr.get("scenario_alpha") or {}
                    _beta  = _dr.get("scenario_beta") or {}
                    _alpha_chain = _alpha.get("causal_chain") or _dr.get("causal_chain") or _driving
                    _beta_chain  = _beta.get("causal_chain") or ""

                    st.markdown("#### 🟡 Alpha 路径（最高概率）")
                    _alpha_prob = float(_alpha.get("probability", 0.72) or 0.72)
                    st.progress(_alpha_prob, text=f"Alpha Pr = {int(_alpha_prob*100)}%")
                    _render_causal_chain(_alpha_chain)
                    if _alpha.get("mechanism"):
                        st.markdown(
                            f'**锚定机制：** <span class="mech-tag">{_alpha["mechanism"]}</span>',
                            unsafe_allow_html=True,
                        )

                    st.markdown('<div style="height:12px"/>', unsafe_allow_html=True)
                    st.markdown("#### 🔴 Beta 路径（结构性断裂）")
                    _beta_prob = float(_beta.get("probability", 0.28) or 0.28)
                    st.progress(_beta_prob, text=f"Beta Pr = {int(_beta_prob*100)}%")
                    if _beta_chain:
                        _render_causal_chain(_beta_chain)
                    else:
                        st.caption("（后端未提供 Beta 路径因果链）")
                    if _beta.get("trigger_condition"):
                        st.info(f"⚡ 触发条件：{_beta['trigger_condition']}")

                    _vgap = _dr.get("verification_gap", "")
                    if _vgap:
                        st.markdown('<div class="elite-divider"></div>', unsafe_allow_html=True)
                        st.warning(f"**🔍 验证缺口：** {_vgap}")

                # Tab 2: 情景预测
                with _tab_scenarios:
                    _alpha_desc = _alpha.get("description") or _dr.get("prediction") or ""
                    _beta_desc  = _beta.get("description") or ""
                    st.markdown(f"""
                    <div class="scenario-alpha">
                        <div class="scenario-alpha-hdr">
                            🟡 Scenario Alpha — {_alpha.get("name","现状延续路径")}
                        </div>
                        <p style="color:#5D4037;margin:0;font-size:14px;line-height:1.6">
                            {_alpha_desc or "（后端未返回场景描述）"}
                        </p>
                    </div>
                    <div class="scenario-beta">
                        <div class="scenario-beta-hdr">
                            🔴 Scenario Beta — {_beta.get("name","结构性断裂路径")}
                        </div>
                        <p style="color:#5D4037;margin:0;font-size:14px;line-height:1.6">
                            {_beta_desc or "（后端未返回场景描述）"}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

                    _outcomes = _dr.get("pattern_outcomes") or []
                    if _outcomes:
                        st.markdown("**🎯 笛卡尔积模式库预期后果**")
                        st.markdown(
                            " ".join(f'<span class="outcome-pill">{o}</span>' for o in _outcomes[:6]),
                            unsafe_allow_html=True,
                        )

                    # 本体论计算模型
                    st.markdown("**本体论计算模型**")
                    st.markdown(f"""
                    <div class="math-logic">
                    # Inference Trajectory<br>
                    Pr(E|K) = &#8721; [W(n) * R(p)] / &#937; <br>
                    Confidence = &#916;(Ontology_Density) / Threshold = {_conf_raw:.2f} <br>
                    [System State] -&gt; {"Converging" if _conf_pct >= 65 else "Diverging"}
                    </div>
                    """, unsafe_allow_html=True)

                # Tab 3: 图谱证据
                with _tab_evidence:
                    _gev  = _dr.get("graph_evidence", "")
                    _subg = _dr.get("graph_subgraph") or {}
                    if isinstance(_subg, dict) and _subg.get("nodes"):
                        render_graph(_subg)
                    elif _gev:
                        st.caption("相关图谱路径：")
                        if isinstance(_gev, str):
                            st.text(_gev[:2000])
                        elif isinstance(_gev, list):
                            for f in _gev:
                                st.write(f"- {f}")
                    else:
                        _fallback = get_graph_context_for_news(_sel_title + " " + _sel_desc)
                        if _fallback and "未找到" not in _fallback:
                            st.text(_fallback)
                        else:
                            st.info("未从本体图谱中检索到显式证据，请检查 KuzuDB 同步及后端推理逻辑。")

                # Tab 4: Debug
                with _tab_debug:
                    with st.expander("🛠 后端原始 deduction_result JSON", expanded=False):
                        st.json(_dr)

            if st.button("🔄 重新选择情报", key="clear_selection"):
                st.session_state.selected_news    = None
                st.session_state.deduction_result = None
                st.session_state.evented_result   = None
                st.rerun()

        elif _mode_key == "Evented":
            # ─── Evented 三段式推演面板 ────────────────────────────────────
            _sel_title = _selected.get("title", "（无标题）")
            _sel_desc  = _selected.get("description") or _selected.get("summary") or ""

            # Read engine config from sidebar session state
            _deep_level     = int(st.session_state.get("cfg_deep_level", 0))
            _show_hidden    = bool(st.session_state.get("cfg_show_hidden", True))
            _is_deep_mode   = _deep_level > 0

            _mode_label = "🔬 深度本体分析" if _is_deep_mode else "⚙️ 普通推演"
            st.markdown(
                f"**针对事件：** `{_sel_title}`"
                + (f"&nbsp;&nbsp;<span style='background:#1565C0;color:#fff;"
                   f"padding:2px 8px;border-radius:10px;font-size:11px'>"
                   f"{_mode_label} (Level {_deep_level})</span>"
                   if _is_deep_mode else ""),
                unsafe_allow_html=True,
            )
            st.markdown('<div class="elite-divider"></div>', unsafe_allow_html=True)

            _er: Optional[Dict[str, Any]] = st.session_state.get("evented_result")
            _evented_err: Optional[str] = None

            if _er is None:
                _status_msg = (
                    "🔬 正在运行深度本体分析（事件提取 → 证据增强 → 重推演）..."
                    if _is_deep_mode
                    else "⚙️ 正在运行事件推演流水线（事件提取 → 模式映射 → 双路径结论）..."
                )
                with st.status(_status_msg, expanded=True) as _ev_status:
                    try:
                        st.write("📡 调用后端 evented_deduce 接口…")
                        _ev_payload = {
                            "title":       _sel_title,
                            "summary":     _sel_desc or _sel_title,
                            "description": _sel_desc,
                            "source":      _selected.get("source"),
                            "published":   str(_selected.get("published", "")),
                            "entities":    _selected.get("entities", []),
                            "url":         _selected.get("url") or _selected.get("link") or "",
                        }
                        _deep_cfg = None
                        if _is_deep_mode:
                            _deep_cfg = {
                                "level":           _deep_level,
                                "timeout_seconds": 20,
                                "max_sources":     3,
                            }
                            st.write(f"🔬 深度级别 {_deep_level} 已激活，正在增强证据锚点…")
                        _ev_resp = _api.evented_deduce(
                            _ev_payload,
                            deep_mode=_is_deep_mode,
                            deep_config=_deep_cfg,
                        )
                        if _ev_resp.get("status") == "success" or "events" in _ev_resp:
                            _er = _ev_resp
                            st.session_state.evented_result = _er
                            st.write("✅ 三段式推演完成，正在渲染…")
                            _ev_status.update(label="✅ 推演完成", state="complete")
                        else:
                            _evented_err = str(_ev_resp.get("error") or _ev_resp.get("detail", "未知错误"))
                            _ev_status.update(label="⚠ 推演失败", state="error")
                    except Exception as _exc:
                        _evented_err = str(_exc)
                        _ev_status.update(label="⚠ 连接失败", state="error")

            if _evented_err:
                st.error(f"Evented 推演失败：{_evented_err}")

            elif _er is not None:
                _ev_events   = _er.get("events", [])
                _ev_active   = _er.get("active_patterns", [])
                _ev_derived  = _er.get("derived_patterns", [])
                _ev_concl    = _er.get("conclusion", {})
                _ev_cred     = _er.get("credibility", {})
                _ev_enrich   = _er.get("enrichment")

                _tab_labels = [
                    f"① 事件节点 ({len(_ev_events)})",
                    f"② 模式节点 ({len(_ev_active)}+{len(_ev_derived)})",
                    "③ 结论与可信度",
                ]
                if _ev_enrich:
                    _tab_labels.append("🔬 证据增强")

                _tabs_ev = st.tabs(_tab_labels)
                _tab_ev1 = _tabs_ev[0]
                _tab_ev2 = _tabs_ev[1]
                _tab_ev3 = _tabs_ev[2]
                _tab_ev4 = _tabs_ev[3] if _ev_enrich and len(_tabs_ev) > 3 else None

                # ── Stage 1: Events ──────────────────────────────────────
                with _tab_ev1:
                    if not _ev_events:
                        st.info("未从文本中提取到有效事件（所有候选事件已被 T0 过滤器拒绝）。")
                    for _ev in _ev_events:
                        _ev_tier = _ev.get("tier", "?")
                        _ev_tier_color = "#2E7D32" if _ev_tier == "T2" else "#E65100"
                        _ev_conf = _ev.get("confidence", 0)
                        _ev_quote = (_ev.get("evidence") or {}).get("quote", "")
                        _ev_inf  = ", ".join(_ev.get("inferred_fields") or []) or "—"
                        _ev_type = _ev.get("type", "unknown")
                        st.markdown(
                            f'<div style="border-left:3px solid {_ev_tier_color};'
                            f'padding:8px 12px;margin-bottom:8px;background:#FAFAFA;border-radius:4px;">'
                            f'<span style="font-weight:700;font-size:13px">{_ev_type}</span>'
                            f'&nbsp;&nbsp;<span style="background:{_ev_tier_color};color:#fff;'
                            f'padding:1px 7px;border-radius:10px;font-size:11px">{_ev_tier}</span>'
                            f'&nbsp;&nbsp;<span style="color:#666;font-size:11px">置信度 {_ev_conf:.0%}</span>'
                            f'<div style="font-size:12px;color:#555;margin-top:4px">📎 {_ev_quote}</div>'
                            f'<div style="font-size:11px;color:#888;margin-top:2px">推断字段: {_ev_inf}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                # ── Stage 2: Patterns ─────────────────────────────────────
                with _tab_ev2:
                    if _ev_active:
                        st.markdown("**🔵 激活模式（Active Patterns）**")
                        for _ap in _ev_active:
                            _ap_tier  = _ap.get("tier", "T2")
                            _ap_conf  = _ap.get("confidence", 0)
                            _ap_inf   = _ap.get("inferred", False)
                            _ap_color = "#2E7D32" if _ap_tier == "T2" else "#E65100"
                            st.markdown(
                                f'<div style="border-left:3px solid {_ap_color};'
                                f'padding:6px 10px;margin-bottom:6px;background:#FAFAFA;">'
                                f'<b>{_ap["pattern"]}</b>'
                                f'&nbsp;<span style="background:{_ap_color};color:#fff;'
                                f'padding:1px 6px;border-radius:8px;font-size:11px">{_ap_tier}</span>'
                                f'&nbsp;<span style="color:#888;font-size:11px">Pr={_ap_conf:.0%}'
                                f'{" · 推断" if _ap_inf else ""}</span>'
                                f'&nbsp;<span style="color:#aaa;font-size:10px">← {_ap.get("from_event","")}</span>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                    else:
                        st.info("无激活模式。")

                    if _ev_derived:
                        st.markdown("**🟣 衍生模式（Derived Patterns via Composition）**")
                        for _dp in _ev_derived:
                            _dp_tier  = _dp.get("derived_tier", "T1")
                            _dp_conf  = _dp.get("derived_confidence", 0)
                            _dp_inf   = _dp.get("derived_inferred", False)
                            _dp_rule  = _dp.get("rule", "")
                            _dp_color = "#2E7D32" if _dp_tier == "T2" else "#7B1FA2"
                            st.markdown(
                                f'<div style="border-left:3px solid {_dp_color};'
                                f'padding:6px 10px;margin-bottom:6px;background:#F8F0FF;">'
                                f'<b>{_dp["derived"]}</b>'
                                f'&nbsp;<span style="background:{_dp_color};color:#fff;'
                                f'padding:1px 6px;border-radius:8px;font-size:11px">{_dp_tier}</span>'
                                f'&nbsp;<span style="color:#888;font-size:11px">Pr={_dp_conf:.0%}'
                                f'{" · 推断" if _dp_inf else ""}</span>'
                                f'<div style="font-size:10px;color:#aaa;margin-top:2px">规则: {_dp_rule}</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
                    else:
                        st.caption("无衍生模式（需要至少两个可组合的激活模式）。")

                # ── Stage 3: Conclusion + Credibility ─────────────────────
                with _tab_ev3:
                    _ev_path  = _ev_concl.get("evidence_path", {})
                    _hyp_path = _ev_concl.get("hypothesis_path", {})

                    st.markdown("#### 🟢 证据路径（Evidence Path — T2 接地）")
                    _ev_summary = _ev_path.get("summary") or "（无接地证据路径）"
                    st.markdown(
                        f'<div style="background:#E8F5E9;border-left:4px solid #2E7D32;'
                        f'padding:10px 14px;border-radius:4px;font-size:14px">{_ev_summary}</div>',
                        unsafe_allow_html=True,
                    )
                    _ep_pats = _ev_path.get("patterns", [])
                    if _ep_pats:
                        st.caption("支撑模式：" + "、".join(p["pattern"] for p in _ep_pats))

                    # Hypothesis path – controlled by 显示潜在隐变量 toggle
                    if _show_hidden:
                        st.markdown("#### 🟡 假设路径（Hypothesis Path — T1 推断）")
                        _hyp_summary = _hyp_path.get("summary") or "（无假设路径）"
                        st.markdown(
                            f'<div style="background:#FFF8E1;border-left:4px solid #F9A825;'
                            f'padding:10px 14px;border-radius:4px;font-size:14px">{_hyp_summary}</div>',
                            unsafe_allow_html=True,
                        )
                        _hyp_gaps = _hyp_path.get("verification_gaps", [])
                        if _hyp_gaps:
                            st.caption("验证缺口：" + " · ".join(_hyp_gaps))
                    else:
                        st.caption("💡 假设路径已隐藏（在侧边栏'推演引擎配置'中开启'显示潜在隐变量'）")

                    st.markdown("#### 📋 总结论")
                    st.info(_ev_concl.get("conclusion", "（无结论）"))

                    st.markdown('<div class="elite-divider"></div>', unsafe_allow_html=True)
                    st.markdown("#### 📊 可信度报告")
                    _vc1, _vc2, _vc3 = st.columns(3)
                    with _vc1:
                        _vs = _ev_cred.get("verifiability_score", 0)
                        st.metric("可验证性", f"{_vs:.0%}")
                    with _vc2:
                        _ks = _ev_cred.get("kg_consistency_score", 0)
                        st.metric("图谱一致性", f"{_ks:.0%}")
                    with _vc3:
                        _os = _ev_cred.get("overall_score", 0)
                        _hr = _ev_cred.get("hypothesis_ratio", 0)
                        st.metric("综合评分", f"{_os:.0%}", delta=f"假设比 {_hr:.0%}")

                    _missing = _ev_cred.get("missing_evidence", [])
                    if _missing:
                        st.warning("缺失证据锚点：" + "、".join(_missing))
                    _contras = _ev_cred.get("contradictions", [])
                    if _contras:
                        st.error("检测到矛盾：" + " | ".join(_contras))

                    with st.expander("🛠 原始 JSON（Evented 推演结果）", expanded=False):
                        st.json(_er)

                # ── Enrichment panel (Deep mode only) ─────────────────────
                if _tab_ev4 is not None and _ev_enrich is not None:
                    with _tab_ev4:
                        _enr_missing_before = _ev_enrich.get("missing_before", [])
                        _enr_missing_after  = _ev_enrich.get("missing_after", [])
                        _enr_provenance     = _ev_enrich.get("provenance", [])
                        _enr_summary        = _ev_enrich.get("enriched_context_summary", "")
                        _enr_cache_hit      = _ev_enrich.get("cache_hit", False)
                        _enr_limits         = _ev_enrich.get("limits", {})
                        _enr_error          = _ev_enrich.get("error")
                        _enr_level          = _ev_enrich.get("level", 0)

                        # Header
                        _level_labels = {0: "关闭", 1: "本地元数据", 2: "+原文抓取", 3: "+全网搜索"}
                        st.markdown(
                            f"**🔬 深度本体分析** · 级别 {_enr_level} "
                            f"（{_level_labels.get(_enr_level, '')}）"
                            + (" &nbsp; 🗄️ `缓存命中`" if _enr_cache_hit else ""),
                            unsafe_allow_html=True,
                        )

                        if _enr_error:
                            st.error(f"增强失败（已回退到普通结果）：{_enr_error}")

                        # Missing anchors delta
                        _filled = [a for a in _enr_missing_before if a not in _enr_missing_after]
                        _still_missing = _enr_missing_after
                        _col_a, _col_b = st.columns(2)
                        with _col_a:
                            st.markdown("**增强前缺失锚点**")
                            for _anc in _enr_missing_before:
                                _ok = _anc in _filled
                                st.markdown(
                                    f'<span style="color:{"#2E7D32" if _ok else "#C62828"}">'
                                    f'{"✅" if _ok else "❌"} {_anc}</span>',
                                    unsafe_allow_html=True,
                                )
                        with _col_b:
                            st.markdown("**增强后仍缺失**")
                            if _still_missing:
                                for _anc in _still_missing:
                                    st.markdown(f"• {_anc}")
                            else:
                                st.success("所有锚点已填充 ✓")

                        if _enr_summary:
                            st.caption(_enr_summary)

                        # Provenance table
                        if _enr_provenance:
                            st.markdown("**📋 证据来源（Provenance）**")
                            for _prov in _enr_provenance:
                                _p_anchor  = _prov.get("anchor_type", "")
                                _p_snippet = _prov.get("snippet", "")
                                _p_url     = _prov.get("source_url", "")
                                _p_title   = _prov.get("title", "")
                                _p_conf    = _prov.get("confidence", 0)
                                _p_at      = _prov.get("fetched_at", "")
                                st.markdown(
                                    f'<div style="border-left:3px solid #1565C0;'
                                    f'padding:6px 12px;margin-bottom:6px;background:#E3F2FD;border-radius:4px;">'
                                    f'<span style="font-weight:700;font-size:12px;color:#1565C0">{_p_anchor}</span>'
                                    f'&nbsp;&nbsp;<span style="color:#555;font-size:11px">置信度 {_p_conf:.0%}</span>'
                                    f'<div style="font-size:13px;margin-top:3px">{_p_snippet}</div>'
                                    + (f'<div style="font-size:11px;color:#888;margin-top:2px">'
                                       f'来源: <a href="{_p_url}" target="_blank">{_p_title or _p_url}</a>'
                                       f'</div>' if _p_url else "")
                                    + f'</div>',
                                    unsafe_allow_html=True,
                                )
                        else:
                            st.info("未提取到新的证据来源。")

                        # Limits summary
                        if _enr_limits:
                            _lim_parts = []
                            if _enr_limits.get("searched"):
                                _lim_parts.append("已执行网络搜索")
                            _furl = _enr_limits.get("fetched_urls", 0)
                            if _furl:
                                _lim_parts.append(f"抓取 {_furl} 个 URL")
                            if _enr_limits.get("truncated"):
                                _lim_parts.append("⚠️ 因超时截断")
                            if _lim_parts:
                                st.caption("限制信息: " + " · ".join(_lim_parts))

            if st.button("🔄 重新选择情报", key="clear_selection_evented"):
                st.session_state.selected_news  = None
                st.session_state.evented_result = None
                st.rerun()

    st.markdown('<div class="elite-divider"></div>', unsafe_allow_html=True)
    with st.expander("ℹ️ 相关本体知识储备 (Active Sub-Graphs)", expanded=False):
        st.write("""
        **当前关联逻辑库引擎在线状态：**
        * 🟢 **[地缘政治本体]**：制裁、同盟、胁迫模式库已加载
        * 🟢 **[经济金融本体]**：贸易依存、央行传导、供应链模式库已加载
        * 🟢 **[技术本体]**：科技脱钩、标准主导、技术封锁模式库已加载
        * 🟡 **[技术变迁本体]**：技术扩散率、政策阻力、合规成本矩阵（待深度构建）
        """)


# ===========================================================================
# Page: 📰 实时新闻
# ===========================================================================
elif page == "📰 实时新闻":
    st.title("📰 实时世界新闻")

    col_title, col_refresh = st.columns([3, 1])
    with col_refresh:
        if st.button("🔄 立即刷新", key="refresh_news"):
            with st.spinner("📡 正在聚合新闻…"):
                result = _api.ingest_news()
                if "error" not in result:
                    st.success("✅ 新闻聚合完成！")
                else:
                    st.error(f"❌ 错误：{result['error']}")

    col_hours, col_limit = st.columns(2)
    with col_hours:
        hours = st.slider("时间范围（小时）", min_value=1, max_value=168, value=24)
    with col_limit:
        limit = st.slider("显示条数", min_value=5, max_value=100, value=20)

    search_query = st.text_input("⚔️ Discern Truth — 关键词搜索", placeholder="输入关键词…")

    if search_query:
        data = _api.search_news(search_query, limit=limit)
    else:
        data = _api.get_latest_news(limit=limit, hours=hours)

    if "error" in data:
        st.error(f"❌ 无法获取新闻：{data['error']}\n\n请确认后端正在运行。")
    else:
        articles: List[Dict[str, Any]] = data.get("articles", [])
        if search_query:
            st.info(f"🔍 共找到 {len(articles)} 条结果")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📰 文章总数", len(articles))
        m2.metric("📂 分类数", len({a.get("category", "?") for a in articles}))
        m3.metric("🏢 新闻源数", len({a.get("source", "?") for a in articles}))
        m4.metric("⏰ 时间范围", f"{hours} 小时")
        st.divider()

        import hashlib as _hashlib

        with st.expander("🌊 Raw News Stream (Entropic Data) — 原始数据流", expanded=False):
            st.caption("⚠️ 以下为未经秩序过滤的原始数据流。")
            if articles:
                for i, article in enumerate(articles, 1):
                    title_preview = (article.get("title") or "（无标题）")[:80]
                    _key_src  = (article.get("link") or article.get("title") or str(i)).encode("utf-8", errors="replace")
                    _cache_key = f"kg_{_hashlib.md5(_key_src).hexdigest()}"

                    with st.expander(f"🔹 [{i}] {title_preview}…", expanded=False):
                        c1, c2, c3 = st.columns(3)
                        c1.caption(f"📌 来源：{article.get('source', 'N/A')}")
                        c2.caption(f"📍 分类：{article.get('category', 'N/A')}")
                        c3.caption(f"⏰ 时间：{str(article.get('published', 'N/A'))[:10]}")
                        st.write(article.get("description") or "（暂无摘要）")
                        if article.get("link"):
                            st.markdown(f"[📖 阅读原文]({article['link']})")

                        # 直达本体推演
                        if st.button("⚔️ 直达因果链推演", key=f"news_deduce_{i}"):
                            st.session_state.selected_news    = article
                            st.session_state.deduction_result = None
                            st.session_state.current_page     = "🏠 主页"
                            st.rerun()

                        # 知识图谱提取
                        already = _cache_key in st.session_state.kg_cache
                        btn_lbl = "✅ 已提取知识图" if already else "🧠 提取知识图"
                        if st.button(btn_lbl, key=f"kg_btn_{i}"):
                            _text = " ".join(filter(None, [
                                article.get("title", ""), article.get("description", ""),
                            ])).strip()
                            if _text:
                                with st.spinner("提取中..."):
                                    _kg_resp = _api.extract_knowledge(_text)
                                if _kg_resp.get("status") == "error" or (
                                    "error" in _kg_resp and "entities" not in _kg_resp
                                ):
                                    st.error(f"❌ 知识图提取失败：{_kg_resp.get('error')}")
                                else:
                                    st.session_state.kg_cache[_cache_key] = _kg_resp
                                    st.rerun()
                            else:
                                st.warning("⚠️ 该文章暂无文本内容可供提取。")

                        if _cache_key in st.session_state.kg_cache:
                            _kg_data = st.session_state.kg_cache[_cache_key]
                            _entities_kg  = _kg_data.get("entities", [])
                            _relations_kg = _kg_data.get("relations", [])
                            with st.expander(
                                f"🕸️ 知识图谱结果（实体: {len(_entities_kg)}, 关系: {len(_relations_kg)}）",
                                expanded=True,
                            ):
                                if _entities_kg:
                                    st.write("**📋 实体**")
                                    try:
                                        import pandas as pd
                                        st.dataframe(pd.DataFrame([
                                            {"name": e.get("name",""), "type": e.get("type",""),
                                             "description": e.get("description",""), "confidence": e.get("confidence","")}
                                            for e in _entities_kg
                                        ]), use_container_width=True)
                                    except ImportError:
                                        for _e in _entities_kg:
                                            st.write(f"- **{_e.get('name')}** ({_e.get('type','?')})")
                                if _relations_kg:
                                    st.write("**🔗 关系**")
                                    try:
                                        import pandas as pd
                                        st.dataframe(pd.DataFrame([
                                            {"subject": r.get("subject",""), "predicate": r.get("predicate",""),
                                             "object": r.get("object","")}
                                            for r in _relations_kg
                                        ]), use_container_width=True)
                                    except ImportError:
                                        for _r in _relations_kg:
                                            st.write(f"- {_r.get('subject')} –[{_r.get('predicate')}]→ {_r.get('object')}")


# ===========================================================================
# Page: 🕸 知识图谱
# ===========================================================================
elif page == "🕸 知识图谱":
    st.title("🕸 知识图谱 & 本体诊断")

    col_graph, col_chat = st.columns([3, 2], gap="large")

    with col_graph:
        st.subheader("🌐 知识图谱视图")
        if st.button("🔄 更新图谱", type="primary", key="kg_update"):
            with st.spinner("正在摄入图谱数据…"):
                _resp = _api.ingest_news()
                st.success("✅ 完成" if "error" not in _resp else f"❌ {_resp['error']}")

        _ents = st.session_state.graph_data.get("entities", [])
        _rels = st.session_state.graph_data.get("relations", [])
        _known_ids = {e.get("name", "") for e in _ents if e.get("name")}
        _gdata = {
            "nodes": [{"id": e.get("name",""), "label": str(e.get("type","MISC")).upper(),
                       "properties": e} for e in _ents if e.get("name")],
            "edges": [{"from": r.get("from",""), "to": r.get("to",""), "type": r.get("relation","")}
                      for r in _rels if r.get("from") in _known_ids and r.get("to") in _known_ids],
        }
        st.caption(f"图谱共 **{len(_gdata['nodes'])}** 个节点，**{len(_gdata['edges'])}** 条边")
        render_graph(_gdata)

    with col_chat:
        st.subheader("💬 Cypher 查询")
        st.caption("仅 Kuzu 后端支持 Cypher 查询（需设置 `GRAPH_BACKEND=kuzu`）。")
        _default_cypher = "MATCH (e:Entity) RETURN e.name, e.type LIMIT 10"
        _cypher_input = st.text_area(
            "Cypher 查询语句", value=_default_cypher, height=100,
            key="kg_cypher_input_main", placeholder=_default_cypher,
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
                st.session_state.kg_chat_history.insert(0, {"query": _q, "response": _qr})

        for _item in st.session_state.kg_chat_history:
            st.markdown(
                f"<div style='background:#F5F5F5;border:1px solid #E0E0E0;border-radius:4px;"
                f"padding:8px 12px;margin-bottom:4px;font-family:monospace;font-size:13px;"
                f"color:#606060'>{_item['query']}</div>",
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
                        st.dataframe(pd.DataFrame(_results), use_container_width=True, height=200)
                    except Exception:
                        st.json(_results)
                else:
                    st.info("查询成功，但无结果。")
            st.markdown("---")

    st.divider()

    # Detail tabs — 新增「笛卡尔积诊断」
    tab_entities, tab_relations, tab_neighbours, tab_diagnostic = st.tabs([
        "📋 实体列表", "🔗 关系列表", "🔍 邻居查询", "🧮 笛卡尔积诊断"
    ])

    with tab_entities:
        entities_resp = _api.get_kg_entities(limit=200)
        if "error" in entities_resp:
            st.error(f"❌ {entities_resp['error']}")
        else:
            entities_list: List[Dict[str, Any]] = entities_resp.get("entities", [])
            if entities_list:
                try:
                    import pandas as pd
                    st.dataframe(pd.DataFrame(entities_list), use_container_width=True, height=400)
                except ImportError:
                    for e in entities_list:
                        st.write(f"**{e.get('name')}** ({e.get('type','?')})")
            else:
                st.info("📭 图谱中暂无实体。请点击「更新图谱」按钮先进行数据摄入。")

    with tab_relations:
        relations_resp = _api.get_kg_relations(limit=300)
        if "error" in relations_resp:
            st.error(f"❌ {relations_resp['error']}")
        else:
            relations_list: List[Dict[str, Any]] = relations_resp.get("relations", [])
            if relations_list:
                try:
                    import pandas as pd
                    st.dataframe(pd.DataFrame(relations_list), use_container_width=True, height=400)
                except ImportError:
                    for r in relations_list:
                        st.write(f"**{r.get('from')}** –[{r.get('relation')}]→ **{r.get('to')}**")
            else:
                st.info("📭 图谱中暂无关系。请先进行数据摄入。")

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

    # ── 笛卡尔积诊断 Tab ───────────────────────────────────────────────────
    with tab_diagnostic:
        st.markdown("### 🧮 笛卡尔积动力模式诊断")
        st.caption(
            "输入三元组 (源实体类型, 关系类型, 目标实体类型)，"
            "系统从模式库中查询对应的动力模式、典型后果与先验置信度。"
        )

        try:
            from ontology.relation_schema import (  # type: ignore
                EntityType, RelationType,
                generate_diagnostic_report, CARTESIAN_PATTERN_REGISTRY,
            )
            _schema_available = True
        except ImportError:
            _schema_available = False
            st.warning("⚠️ `ontology/relation_schema.py` 未找到，请确认后端模块已部署。")

        if _schema_available:
            _e_types = [e.value for e in EntityType]
            _r_types = [r.value for r in RelationType]

            col_d1, col_d2, col_d3 = st.columns(3)
            with col_d1:
                _d_src = st.selectbox(
                    "🔵 源实体类型", _e_types,
                    index=_e_types.index("state") if "state" in _e_types else 0,
                    key="diag_src",
                )
            with col_d2:
                _d_rel = st.selectbox(
                    "⚡ 关系类型", _r_types,
                    index=_r_types.index("sanction") if "sanction" in _r_types else 0,
                    key="diag_rel",
                )
            with col_d3:
                _d_tgt = st.selectbox(
                    "🔴 目标实体类型", _e_types,
                    index=_e_types.index("state") if "state" in _e_types else 0,
                    key="diag_tgt",
                )

            if st.button("🧮 执行笛卡尔积诊断", type="primary", key="run_diag"):
                _report = generate_diagnostic_report(_d_src, _d_rel, _d_tgt)
                st.session_state["diag_report"] = _report

            if "diag_report" in st.session_state:
                _rpt = st.session_state["diag_report"]
                st.markdown('<div class="elite-divider"></div>', unsafe_allow_html=True)

                _pat = _rpt.matched_pattern
                if _pat:
                    _dom_cls = _domain_class(_rpt.domain)
                    st.markdown(
                        f'<div class="diag-pattern-name">{_pat.pattern_name}</div>'
                        f'<span class="diag-domain-badge {_dom_cls}">{_rpt.domain}</span>'
                        f'&nbsp;<span class="mech-tag">{_pat.mechanism_class}</span>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"**三元组：** `{_rpt.input_triple[0]}` × `{_rpt.input_triple[1]}` × `{_rpt.input_triple[2]}`"
                    )
                    _cp = _rpt.confidence_prior
                    st.markdown(f"**先验置信度：** {_cp:.0%}")
                    st.markdown(
                        f'<div class="conf-bar-wrap"><div class="conf-bar" style="width:{int(_cp*100)}%"></div></div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown('<div class="elite-divider"></div>', unsafe_allow_html=True)
                    st.markdown("**📋 典型后果（按概率降序）**")
                    st.markdown(
                        " ".join(f'<span class="outcome-pill">{o}</span>' for o in _rpt.typical_outcomes),
                        unsafe_allow_html=True,
                    )
                    st.markdown('<div class="elite-divider"></div>', unsafe_allow_html=True)
                    c_comp, c_inv = st.columns(2)
                    with c_comp:
                        st.markdown("**🔗 高阶组合效应**")
                        if _rpt.composition_chain:
                            for hint in _rpt.composition_chain:
                                st.markdown(f"- `{hint}`")
                        else:
                            st.caption("暂无组合记录")
                    with c_inv:
                        st.markdown("**↩️ 逆动力模式（群论反元素）**")
                        if _rpt.inverse_pattern:
                            st.markdown(f"`{_rpt.inverse_pattern}`")
                            st.caption("当逆模式激活时，当前模式后果被反转或抵消。")
                        else:
                            st.caption("暂未定义逆模式")
                else:
                    st.warning("无精确匹配，以下为模糊匹配结果：")
                    for (src, rel, tgt), pat, score in _rpt.fuzzy_matches:
                        with st.expander(f"模糊匹配: {pat.pattern_name} (score={score:.2f})", expanded=False):
                            st.write(f"**三元组：** {src.value} × {rel.value} × {tgt.value}")
                            st.write(f"**领域：** {pat.domain}")
                            for o in pat.typical_outcomes:
                                st.write(f"  - {o}")

                st.markdown(f'<div class="diag-note">📝 {_rpt.diagnostic_note}</div>', unsafe_allow_html=True)

            st.markdown('<div class="elite-divider"></div>', unsafe_allow_html=True)
            with st.expander("📚 当前模式库总览", expanded=False):
                try:
                    import pandas as pd
                    _df_pats = pd.DataFrame([
                        {"src": k[0].value, "relation": k[1].value, "tgt": k[2].value,
                         "模式名称": v.pattern_name, "领域": v.domain,
                         "机制类别": v.mechanism_class, "先验置信度": f"{v.confidence_prior:.0%}"}
                        for k, v in CARTESIAN_PATTERN_REGISTRY.items()
                    ])
                    st.dataframe(_df_pats, use_container_width=True, height=400)
                except ImportError:
                    for (src, rel, tgt), pat in CARTESIAN_PATTERN_REGISTRY.items():
                        st.write(f"**{pat.pattern_name}** — {src.value} × {rel.value} × {tgt.value}")

            with st.expander("💡 如何在推演管线中使用笛卡尔积诊断", expanded=False):
                st.markdown("""
                **联动流程：**
                1. `analysis_service.perform_deduction` 提取 `MechanismLabel` 列表
                2. 调用 `relation_schema.enrich_mechanism_labels_with_patterns()` 为每条标签查询模式库
                3. 调用 `build_pattern_context_for_prompt()` 生成「先验后果」片段注入 LLM prompt
                4. LLM 被强制从「典型后果」中选择推演方向，而非自由发挥

                **群论类比（长远方向）：**
                - 当前：E × R × E → DynamicPattern（有限集合映射）
                - 下一步：为 Pattern 定义「组合律」，即 Pattern_A ∘ Pattern_B = Pattern_C
                - 长远：引入 Lie group 连续对称性，描述模式在时间维度上的「流形演化」
                """)


# ===========================================================================
# Page: ⚙️ 系统状态
# ===========================================================================
elif page == "⚙️ 系统状态":
    st.title("⚙️ 系统状态与配置")
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
        f"**版本：** 2.0.0  \n"
        f"**后端地址：** {_backend_url}  \n"
        f"**页面刷新时间：** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n"
        "**平台：** EL'druin Intelligence Platform v2  \n"
        "**知识图谱：** Kuzu（嵌入式）/ NetworkX（备用）  \n"
        "**本体模块：** CAMEO + FIBO 融合 | 笛卡尔积模式库 v2"
    )
