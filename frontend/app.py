"""
EL'druin Intelligence Platform – Streamlit Frontend v2
=======================================================

v2 features:
  1. Home: highlights causal chain + deduction results, Tab-based layout
  2. Intelligence Feed: each article has a "Run Ontological Analysis" shortcut button
  3. KG Tools: includes Cartesian Pattern Diagnostic tab
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
    page_title="EL-DRUIN Intelligence Platform",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
_CSS_PATH = os.path.join(_FRONTEND_DIR, "assets", "custom_styles.css")
try:
    with open(_CSS_PATH, encoding="utf-8") as _f:
        st.markdown(f"<style>{_f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    pass

st.markdown("""
<style>
:root {
  --blue: #3B6EA8;         /* muted, not primary */
  --blue-dark: #2A5280;
  --blue-accent: #4A8FD4;  /* active states and highlights */
  --gold: #C8A84B;         /* slightly desaturated */
  --gold-dark: #A8882A;
  --red: #C0392B;          /* deeper, less neon */
  --red-dark: #A93226;
  --bg: #0F1923;           /* dark charcoal */
  --surface: #162030;      /* dark card surface */
  --surface-raised: #1E2D3D; /* slightly raised surfaces */
  --border: #2D3F52;       /* dark border */
  --text: #D4DDE6;         /* light on dark */
  --text-strong: #EDF2F7;  /* for headings */
  --muted: #7A8FA6;        /* muted on dark */
  --tag-bg: #1A2D42;       /* for inline tags/badges */
}
.stApp { background-color: var(--bg); color: var(--text); }
h1, h2, h3, h4 {
  color: var(--text-strong) !important;
  font-weight: 600;
  letter-spacing: -0.01em;
}

[data-testid="stSidebar"] {
  background-color: #0A1520 !important;
  border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] * { color: var(--muted); }

.news-compact {
    background: var(--surface);
    border-left: 3px solid var(--blue);
    border-radius: 3px;
    padding: 9px 12px;
    margin-bottom: 5px;
    box-shadow: none;
    border-top: 1px solid var(--border);
    border-right: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
}
.news-compact:hover { border-left-color: var(--red); }
.news-title { font-weight: 600; font-size: 13px; color: var(--text-strong); }
.news-meta  { font-size: 11px; color: var(--muted); margin-top: 3px; }

.driving-hero {
    background: var(--surface-raised);
    border: 1px solid var(--border);
    border-left: 3px solid var(--blue-accent);
    border-radius: 3px;
    padding: 14px 16px;
    margin-bottom: 14px;
}
.driving-label {
    font-size: 10px; font-weight: 700; letter-spacing: 1.4px;
    color: var(--muted); text-transform: uppercase; margin-bottom: 6px;
}
.driving-text { font-size: 14px; font-weight: 600; color: var(--text-strong); line-height: 1.5; }

.mech-tag {
    display: inline-block; background: var(--tag-bg); color: var(--blue-accent);
    padding: 2px 8px; border-radius: 2px; font-size: 10px;
    font-weight: 700; margin: 2px; border: 1px solid #2D4A66;
    text-transform: uppercase; letter-spacing: 0.6px;
}
.domain-geo  { background: #1F1A0A; color: #C8954A; border-color: #4A3520; }
.domain-econ { background: #0A1A0F; color: #4CAF72; border-color: #1E4228; }
.domain-tech { background: #170D20; color: #9B72CF; border-color: #3A2050; }
.domain-mil  { background: #1A0808; color: #C04040; border-color: #4A1818; }

.causal-chain {
    background: #080E14; color: #4ADE80; font-family: 'JetBrains Mono', 'Courier New', monospace;
    font-size: 11.5px; padding: 12px 14px; border-radius: 3px;
    line-height: 1.9; overflow-x: auto;
    border: 1px solid #1A2D1A;
}

.scenario-alpha {
    background: #1A160A; border-left: 4px solid var(--gold);
    padding: 12px 14px; border-radius: 3px; margin-bottom: 10px;
    border-top: 1px solid #2A2010; border-right: 1px solid #2A2010; border-bottom: 1px solid #2A2010;
}
.scenario-alpha-hdr {
    color: var(--gold); font-weight: 700; font-size: 10px;
    text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px;
}
.scenario-beta {
    background: #1A0A0A; border-left: 4px solid var(--red);
    padding: 12px 14px; border-radius: 3px; margin-bottom: 10px;
    border-top: 1px solid #2A1010; border-right: 1px solid #2A1010; border-bottom: 1px solid #2A1010;
}
.scenario-beta-hdr {
    color: var(--red); font-weight: 700; font-size: 10px;
    text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px;
}

.diag-pattern-name { font-size: 18px; font-weight: 700; color: var(--text-strong); margin-bottom: 4px; }
.diag-domain-badge {
    display: inline-block; background: var(--blue); color: var(--text-strong);
    padding: 2px 9px; border-radius: 2px; font-size: 10px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.6px;
}
.outcome-pill {
    display: inline-block; background: var(--tag-bg); color: var(--text);
    border: 1px solid var(--border); border-radius: 2px;
    padding: 3px 9px; margin: 2px; font-size: 11px; font-weight: 500;
}
.diag-note {
    background: #1A1500; border-left: 3px solid var(--gold);
    padding: 10px 14px; border-radius: 3px; font-size: 12px; color: var(--text);
}
.conf-bar-wrap { background: #1A2D3D; border-radius: 2px; height: 6px; overflow: hidden; margin: 6px 0; }
.conf-bar { background: var(--blue-accent); height: 6px; border-radius: 2px; }

.elite-divider { height: 1px; background: var(--border); margin: 16px 0; opacity: 0.6; }
.confidence-big { font-size: 36px; font-weight: 800; color: var(--blue-accent); }
.confidence-label { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.8px; }

.math-logic {
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    background: #080E14; color: #4AF626;
    padding: 12px; font-size: 0.82rem; border-radius: 3px; margin-top: 10px;
    border: 1px solid #1A2D1A;
}

/* ── Probability hover tooltip ─────────────────────────────────────────── */
/* Override Streamlit container overflow so the absolutely-positioned
   tooltip box is not clipped by parent layout elements. */
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdown"],
.stMarkdown,
div[data-testid="column"],
.stTabs [data-baseweb="tab-panel"],
[data-testid="stTabsContent"] {
    overflow: visible !important;
}
.prob-tooltip-wrap {
    display: inline-block;
    position: relative;
    cursor: help;
}
.prob-tooltip-val {
    font-weight: 700;
    color: var(--blue-accent);
    border-bottom: 1.5px dashed var(--blue-accent);
    padding-bottom: 1px;
}
.prob-tooltip-box {
    display: none;
    position: absolute;
    left: 0;
    top: calc(100% + 6px);  /* show BELOW to avoid clipping from top-overflow */
    bottom: auto;
    width: 400px;
    max-width: 92vw;
    background: var(--surface-raised);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 14px;
    font-size: 12px;
    line-height: 1.6;
    z-index: 99999;
    box-shadow: 0 4px 20px rgba(0,0,0,0.18);
    pointer-events: none;
    text-align: left;
    white-space: normal;
    color: var(--text);
}
.prob-tooltip-wrap:hover .prob-tooltip-box {
    display: block;
}
.prob-tooltip-section { font-weight: 700; color: var(--blue-accent); margin-top: 6px; }
.prob-tooltip-hr { border: 0; border-top: 1px solid var(--border); margin: 5px 0; }
.prob-tooltip-mono {
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    background: var(--tag-bg); padding: 2px 5px; border-radius: 2px;
    font-size: 11px; word-break: break-all;
}
/* out-of-scope warning card */
.out-of-scope-card {
    background: #1A1500; border-left: 4px solid var(--gold);
    border-radius: 3px; padding: 14px 16px; margin: 10px 0;
    border-top: 1px solid #2A2010; border-right: 1px solid #2A2010; border-bottom: 1px solid #2A2010;
}
.out-of-scope-title { font-weight: 700; font-size: 14px; color: var(--gold); margin-bottom: 6px; }
.out-of-scope-body  { font-size: 13px; color: var(--text); line-height: 1.6; }

/* ── Regime badge ──────────────────────────────────────────────────────── */
.regime-badge {
    display: inline-block;
    padding: 4px 12px; border-radius: 2px;
    font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px;
}
.regime-linear       { background: #0A1520; color: #4A8FD4; border: 1px solid #2D4A66; }
.regime-stress       { background: #1A1500; color: #C8A84B; border: 1px solid #4A3820; }
.regime-nonlinear    { background: #1A0808; color: #E05050; border: 1px solid #4A1818; }
.regime-cascade      { background: #1A0808; color: #FF4444; border: 1px solid #5A1010; }
.regime-convergence  { background: #0F1A2A; color: #9B72CF; border: 1px solid #3A2050; }
.regime-dissipating  { background: #0F1A0F; color: #4CAF72; border: 1px solid #1E4228; }

/* ── Delta change indicators ────────────────────────────────────────────── */
.delta-row {
    display: flex; align-items: center; gap: 10px;
    padding: 5px 0; border-bottom: 1px solid var(--border);
    font-size: 12px; color: var(--text);
}
.delta-up   { color: #E05050; font-weight: 700; }
.delta-down { color: #4CAF72; font-weight: 700; }
.delta-same { color: var(--muted); font-weight: 400; }

/* ── Scenario card ──────────────────────────────────────────────────────── */
.scenario-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 12px 14px;
    margin-bottom: 8px;
}
.scenario-card-hdr {
    font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 1px; color: var(--muted); margin-bottom: 8px;
}

/* ── Evidence item ──────────────────────────────────────────────────────── */
.evidence-item {
    background: var(--surface);
    border-left: 3px solid var(--border);
    border-radius: 0 3px 3px 0;
    padding: 8px 10px;
    margin-bottom: 5px;
    font-size: 12px;
}
.evidence-item:hover { border-left-color: var(--blue-accent); }

/* ── Streamlit component overrides ──────────────────────────────────────── */
.stTextInput input, .stTextArea textarea, .stSelectbox select {
    background-color: var(--surface-raised) !important;
    border-color: var(--border) !important;
    color: var(--text) !important;
}
.stButton button[kind="primary"] {
    background: var(--blue) !important;
    border: 1px solid var(--blue-dark) !important;
    color: var(--text-strong) !important;
    border-radius: 2px !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    letter-spacing: 0.4px !important;
}
.stButton button[kind="primary"]:hover {
    background: var(--blue-accent) !important;
}
.stButton button:not([kind="primary"]) {
    background: var(--surface-raised) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    border-radius: 2px !important;
    font-size: 12px !important;
}
[data-testid="stMetric"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 10px 14px;
}
[data-testid="stMetricLabel"] { color: var(--muted) !important; font-size: 10px !important; text-transform: uppercase; letter-spacing: 0.6px; }
[data-testid="stMetricValue"] { color: var(--text-strong) !important; }
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--muted) !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.6px !important;
    border-bottom: 2px solid transparent !important;
}
.stTabs [aria-selected="true"] {
    color: var(--text-strong) !important;
    border-bottom: 2px solid var(--blue-accent) !important;
    background: transparent !important;
}
[data-testid="stExpander"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 3px !important;
}
.stAlert { border-radius: 3px !important; }
hr { border-color: var(--border) !important; opacity: 0.5; }
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
# Probability hover tooltip helper
# ---------------------------------------------------------------------------

def _prob_tooltip_html(prob: float, tooltip_node: Dict[str, Any]) -> str:
    """Return HTML for a probability badge with a simplified hover tooltip.

    The tooltip explains how the Bayesian and Lie algebra results combine into
    the final dual confidence score, and directs users to the detail tabs for
    full computation traces.

    Args:
        prob: Probability value in [0, 1].
        tooltip_node: A probability-tree node dict that contains a
            ``tooltip_data`` sub-dict produced by the backend.
    """
    td = tooltip_node.get("tooltip_data", {})
    bayes  = td.get("bayesian", {})
    lie_al = td.get("lie_algebra", {})
    dual   = td.get("dual_integration", {})

    # ── Bayesian brief ───────────────────────────────────────────────
    k          = bayes.get("amplification", 4)
    prior_a    = bayes.get("prior_a", "—")
    prior_b    = bayes.get("prior_b", "—")
    lie_sim    = bayes.get("lie_sim", "—")
    Z_val      = bayes.get("Z", "—")

    # ── Lie algebra brief ────────────────────────────────────────────
    cos_sim    = lie_al.get("cosine_similarity", lie_sim)
    mat_norm   = lie_al.get("matrix_norm", None)

    # ── Dual integration brief ───────────────────────────────────────
    consistency = dual.get("consistency_score", None)
    verdict     = dual.get("verdict", "")
    conf_final  = dual.get("confidence_final", None)

    # ── Tooltip content ──────────────────────────────────────────────
    tooltip_content = (
        f"<div class='prob-tooltip-section'>🔗 Dual Confidence: p = {prob:.1%}</div>"
        f"<div style='font-size:10.5px;color:#555;margin-bottom:4px'>"
        f"confidence_final = P_Bayes &times; (1 + &alpha; &times; consistency) / (1 + &alpha;), &alpha;=0.3"
        f"</div>"
        f"<hr class='prob-tooltip-hr'>"
        f"<div class='prob-tooltip-section'>📐 Bayesian &nbsp;<span style='font-weight:400;color:#777;font-size:10.5px'>(full detail → 🌳 Probability Tree tab)</span></div>"
        f"<div style='font-size:11px'>"
        f"P_Bayes = prior_A &times; prior_B &times; lie_sim^{k} / Z"
        f"<br><span class='prob-tooltip-mono'>{prior_a} &times; {prior_b} &times; {lie_sim}^{k} / {Z_val}</span>"
        f" = <b>{prob:.1%}</b>"
        f"</div>"
        f"<hr class='prob-tooltip-hr'>"
        f"<div class='prob-tooltip-section'>🧮 Lie Algebra &nbsp;<span style='font-weight:400;color:#777;font-size:10.5px'>(full detail → 🧮 Lie Algebra tab)</span></div>"
        f"<div style='font-size:11px'>cos(v_A + v_B, v_C) = <b>{cos_sim}</b>"
    )
    if mat_norm is not None and mat_norm != 0.0:
        tooltip_content += f" &nbsp; ‖[A,B]‖_F = <b>{mat_norm:.4f}</b>"
    tooltip_content += "</div>"

    if consistency is not None:
        consist_str = f"{consistency:.3f}" if isinstance(consistency, float) else str(consistency)
        tooltip_content += (
            f"<hr class='prob-tooltip-hr'>"
            f"<div class='prob-tooltip-section'>∫ Integration</div>"
            f"<div style='font-size:11px'>consistency = <b>{consist_str}</b>"
        )
        if verdict:
            tooltip_content += f" &nbsp; verdict: <b>{verdict}</b>"
        if conf_final is not None:
            cf_str = f"{conf_final:.3f}" if isinstance(conf_final, float) else str(conf_final)
            tooltip_content += f" &nbsp; conf_final = <b>{cf_str}</b>"
        tooltip_content += "</div>"

    tooltip_content += (
        f"<hr class='prob-tooltip-hr'>"
        f"<div style='font-size:10.5px;color:#777'>"
        f"See <b>🌳 Probability Tree</b> and <b>🧮 Lie Algebra</b> tabs for full computation traces."
        f"</div>"
    )

    return (
        f"<span class='prob-tooltip-wrap'>"
        f"<span class='prob-tooltip-val'>{prob:.1%}</span>"
        f"<div class='prob-tooltip-box'>{tooltip_content}</div>"
        f"</span>"
    )


# ---------------------------------------------------------------------------
# KuzuDB graph context helper (used in homepage deduction panel)
# ---------------------------------------------------------------------------
def get_graph_context_for_news(query_text: str) -> str:
    import kuzu
    db_path = "./data/kuzu_db.db"
    if not os.path.exists(db_path):
        return "Database not yet initialised."
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
                context_facts.append(f"- Fact: {row[0]} --[{row[1]}]--> {row[2]} (weight: {row[3]})")
        return "\n".join(set(context_facts)) if context_facts else "No related graph facts found."
    except Exception as e:
        return f"Graph query note: {str(e)}"


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
_STATE_DEFAULTS = {
    "initialized": False,
    "current_page": "Dashboard",
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
    if st.session_state.pop("_kg_cache_clear", False):
        load_knowledge_graph.clear()
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
        st.info("📭 No graph data available.")
        return
    if not _AGRAPH_AVAILABLE:
        st.warning("⚠️ `streamlit-agraph` is not installed. Interactive graph is unavailable.")
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
        st.info("📭 No node data found.")
        return
    try:
        config = Config(
            width=800, height=_KG_MAIN_HEIGHT, directed=True, physics=True,
            hierarchical=False, nodeHighlightBehavior=True, highlightColor=_NODE_COLOR_HUB,
        )
        agraph(nodes=ag_nodes, edges=ag_edges, config=config)
    except Exception as exc:
        st.error(f"⚠️ Knowledge graph rendering failed: {exc}")


def _render_causal_chain(chain_text: str) -> None:
    """Render a 4-step causal chain (terminal style)."""
    if not chain_text:
        st.caption("(No causal chain returned by backend)")
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
# Page: Dashboard
# ===========================================================================
if page == "Dashboard":
    st.markdown("""
    <style>
    .compact-news { padding:9px 12px; border-left:3px solid var(--blue); background:var(--surface);
        margin-bottom:5px; box-shadow:none; border-radius:3px;
        border-top:1px solid var(--border); border-right:1px solid var(--border); border-bottom:1px solid var(--border); }
    .compact-news:hover { border-left-color:var(--red); }
    .prediction-box { border-left:4px solid var(--red); background:#1A0808;
        padding:14px 16px; border-radius:3px; margin:10px 0; color:var(--text);
        font-size:1rem; line-height:1.5;
        border-top:1px solid #2A1010; border-right:1px solid #2A1010; border-bottom:1px solid #2A1010; }
    </style>
    """, unsafe_allow_html=True)

    _col_h1, _col_h2 = st.columns([4, 1])
    with _col_h1:
        st.markdown("# ⚔️ EL-DRUIN — Core Prediction & Ontological Reasoning")
    with _col_h2:
        st.markdown(f"**{datetime.now().strftime('%H:%M UTC')}**")
    st.caption(
        "Select an article from the left feed, choose your reasoning engine from the sidebar, "
        "and click **Run Ontological Analysis** to generate a causal deduction."
    )
    st.markdown('<div class="elite-divider"></div>', unsafe_allow_html=True)

    col_feed, col_deduction = st.columns([4, 6], gap="large")

    # ─── LEFT: 情报流 ─────────────────────────────────────────────────────
    with col_feed:
        st.subheader("📍 Intelligence Feed")

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
            _title   = (_article.get("title") or "(no title)")[:55]
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

            if st.button("🎯 Run Ontological Analysis", key=f"deduce_{_idx}_{_article.get('title','')[:20]}", use_container_width=True):
                st.session_state.selected_news    = _article
                st.session_state.deduction_result = None
                st.session_state.evented_result   = None
                st.rerun()

    # ─── RIGHT: Deduction panel ───────────────────────────────────────────
    with col_deduction:
        st.subheader("🧠 Ontological Prediction & Analysis")

        # --- Engine selection is driven by the sidebar (cfg_engine) ---
        _prev_mode = st.session_state.get("_prev_engine", "Evented")
        _mode_key  = st.session_state.get("cfg_engine", "Evented")
        # Clear stale results when engine changes
        if _mode_key != _prev_mode:
            st.session_state._prev_engine    = _mode_key
            st.session_state.deduction_result = None
            st.session_state.evented_result   = None

        _engine_badge = (
            '<span style="background:#0047AB;color:#fff;padding:2px 8px;'
            'border-radius:10px;font-size:11px;margin-left:8px">'
            f'{_mode_key}</span>'
        )
        st.markdown(
            f"Engine: {_engine_badge}  ·  Use the sidebar to change engine or Deep Ontology level.",
            unsafe_allow_html=True,
        )
        st.markdown('<div class="elite-divider"></div>', unsafe_allow_html=True)

        _selected: Optional[Dict[str, Any]] = st.session_state.get("selected_news")

        if not _selected:
            st.markdown("""
            <div style="text-align:center;padding:60px 20px;color:#999;">
                <div style="font-size:40px;margin-bottom:12px;">⚔️</div>
                <div style="font-size:16px;font-weight:500;">Select an article on the left to run ontological analysis</div>
                <div style="font-size:13px;margin-top:8px;">The system will use the KuzuDB graph + Cartesian pattern library for causal reasoning</div>
            </div>
            """, unsafe_allow_html=True)
        elif _mode_key == "Grounded":
            _sel_title = _selected.get("title", "(no title)")
            _sel_desc  = _selected.get("description") or _selected.get("summary") or ""
            st.markdown(f"**Analysing event:** `{_sel_title}`")
            st.markdown('<div class="elite-divider"></div>', unsafe_allow_html=True)

            _dr: Optional[Dict[str, Any]] = st.session_state.get("deduction_result")
            _err: Optional[str] = None

            # First-time trigger
            if _dr is None:
                with st.status("🔍 Building causal chain (LLM + Ontology + KuzuDB)...", expanded=True) as _status:
                    try:
                        st.write("📡 Calling backend grounded_deduce endpoint, retrieving KuzuDB evidence...")
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
                            _status.update(label="⚠ Analysis failed", state="error")
                        else:
                            _dr = _resp.get("deduction_result", _resp)
                            st.session_state.deduction_result = _dr
                            st.write("✅ Ontological reasoning result obtained. Rendering...")
                            _status.update(label="✅ Analysis complete", state="complete")
                    except Exception as _exc:
                        _err = str(_exc)
                        _status.update(label="⚠ Connection failed", state="error")

            if _err:
                st.error(f"Grounded analysis failed: {_err}")

            elif _dr is not None:
                # ── A. Hero: driving factor ───────────────────────────────
                _driving = _dr.get("driving_factor") or _dr.get("mechanism_summary") or "(Engine returned no driving factor)"
                st.markdown(f"""
                <div class="driving-hero">
                    <div class="driving-label">⚡ Core Driving Factor</div>
                    <div class="driving-text">{_driving}</div>
                </div>
                """, unsafe_allow_html=True)

                # ── B. Mechanism domain tags + confidence ─────────────────
                _conf_raw = _dr.get("confidence") or 0.5
                try:
                    _conf_raw = float(_conf_raw)
                except Exception:
                    _conf_raw = 0.5
                _conf_pct = int(round(_conf_raw * 100))
                _mech_count = _dr.get("mechanism_count", 0)

                _b1, _b2, _b3 = st.columns([3, 2, 2])
                with _b1:
                    st.markdown("**🏷 Mechanism Domain**")
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
                        st.caption(f"🔗 {_mech_count} mechanism labels")
                with _b2:
                    st.markdown("**📊 Deduction Confidence**")
                    st.markdown(
                        f'<div class="confidence-big">{_conf_pct}%</div>'
                        f'<div class="confidence-label">Pr(E | KG)</div>',
                        unsafe_allow_html=True,
                    )
                with _b3:
                    st.markdown("**⚖️ Logic State**")
                    _conf_color = "#2E7D32" if _conf_pct >= 65 else "#E65100" if _conf_pct >= 45 else "#B71C1C"
                    _conf_label = "Converging" if _conf_pct >= 65 else "Diverging" if _conf_pct >= 45 else "Uncertain"
                    st.markdown(
                        f'<div style="font-size:22px;font-weight:700;color:{_conf_color}">{_conf_label}</div>',
                        unsafe_allow_html=True,
                    )

                st.markdown('<div class="elite-divider"></div>', unsafe_allow_html=True)

                # ── C. Tab structure ──────────────────────────────────────
                _tab_causal, _tab_scenarios, _tab_evidence, _tab_debug = st.tabs([
                    "⛓ Causal Chain", "🔮 Scenario Forecast", "🕸 Graph Evidence", "🛠 Debug"
                ])

                # Tab 1: Causal chain
                with _tab_causal:
                    _alpha = _dr.get("scenario_alpha") or {}
                    _beta  = _dr.get("scenario_beta") or {}
                    _alpha_chain = _alpha.get("causal_chain") or _dr.get("causal_chain") or _driving
                    _beta_chain  = _beta.get("causal_chain") or ""

                    st.markdown("#### 🟡 Alpha Path (Highest Probability)")
                    _alpha_prob = float(_alpha.get("probability", 0.72) or 0.72)
                    st.progress(_alpha_prob, text=f"Alpha Pr = {int(_alpha_prob*100)}%")
                    _render_causal_chain(_alpha_chain)
                    if _alpha.get("mechanism"):
                        st.markdown(
                            f'**Anchored mechanism:** <span class="mech-tag">{_alpha["mechanism"]}</span>',
                            unsafe_allow_html=True,
                        )

                    st.markdown('<div style="height:12px"/>', unsafe_allow_html=True)
                    st.markdown("#### 🔴 Beta Path (Structural Break)")
                    _beta_prob = float(_beta.get("probability", 0.28) or 0.28)
                    st.progress(_beta_prob, text=f"Beta Pr = {int(_beta_prob*100)}%")
                    if _beta_chain:
                        _render_causal_chain(_beta_chain)
                    else:
                        st.caption("(Backend did not return a Beta path causal chain)")
                    if _beta.get("trigger_condition"):
                        st.info(f"⚡ Trigger condition: {_beta['trigger_condition']}")

                    _vgap = _dr.get("verification_gap", "")
                    if _vgap:
                        st.markdown('<div class="elite-divider"></div>', unsafe_allow_html=True)
                        st.warning(f"**🔍 Verification gap:** {_vgap}")

                # Tab 2: Scenario forecast
                with _tab_scenarios:
                    _alpha_desc = _alpha.get("description") or _dr.get("prediction") or ""
                    _beta_desc  = _beta.get("description") or ""
                    st.markdown(f"""
                    <div class="scenario-alpha">
                        <div class="scenario-alpha-hdr">
                            🟡 Scenario Alpha — {_alpha.get("name","Status Quo Continuation")}
                        </div>
                        <p style="color:#5D4037;margin:0;font-size:14px;line-height:1.6">
                            {_alpha_desc or "(Backend returned no scenario description)"}
                        </p>
                    </div>
                    <div class="scenario-beta">
                        <div class="scenario-beta-hdr">
                            🔴 Scenario Beta — {_beta.get("name","Structural Break")}
                        </div>
                        <p style="color:#5D4037;margin:0;font-size:14px;line-height:1.6">
                            {_beta_desc or "(Backend returned no scenario description)"}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

                    _outcomes = _dr.get("pattern_outcomes") or []
                    if _outcomes:
                        st.markdown("**🎯 Cartesian Pattern Library Expected Outcomes**")
                        st.markdown(
                            " ".join(f'<span class="outcome-pill">{o}</span>' for o in _outcomes[:6]),
                            unsafe_allow_html=True,
                        )

                    st.markdown("**Ontological Computation Model**")
                    st.markdown(f"""
                    <div class="math-logic">
                    # Inference Trajectory<br>
                    Pr(E|K) = &#8721; [W(n) * R(p)] / &#937; <br>
                    Confidence = &#916;(Ontology_Density) / Threshold = {_conf_raw:.2f} <br>
                    [System State] -&gt; {"Converging" if _conf_pct >= 65 else "Diverging"}
                    </div>
                    """, unsafe_allow_html=True)

                # Tab 3: Graph evidence
                with _tab_evidence:
                    _gev  = _dr.get("graph_evidence", "")
                    _subg = _dr.get("graph_subgraph") or {}
                    if isinstance(_subg, dict) and _subg.get("nodes"):
                        render_graph(_subg)
                    elif _gev:
                        st.caption("Relevant graph paths:")
                        if isinstance(_gev, str):
                            st.text(_gev[:2000])
                        elif isinstance(_gev, list):
                            for f in _gev:
                                st.write(f"- {f}")
                    else:
                        _fallback = get_graph_context_for_news(_sel_title + " " + _sel_desc)
                        if _fallback and "No related" not in _fallback:
                            st.text(_fallback)
                        else:
                            st.info("No explicit evidence retrieved from the ontology graph. Check KuzuDB sync and backend reasoning logic.")

                # Tab 4: Debug
                with _tab_debug:
                    with st.expander("🛠 Raw Backend deduction_result JSON", expanded=False):
                        st.json(_dr)

            if st.button("🔄 Clear selection", key="clear_selection"):
                st.session_state.selected_news    = None
                st.session_state.deduction_result = None
                st.session_state.evented_result   = None
                st.rerun()

        elif _mode_key == "Evented":
            # ─── Evented three-stage reasoning panel ───────────────────────
            _sel_title = _selected.get("title", "(no title)")
            _sel_desc  = _selected.get("description") or _selected.get("summary") or ""

            # Read engine config from sidebar session state
            _deep_level     = int(st.session_state.get("cfg_deep_level", 0))
            _show_hidden    = bool(st.session_state.get("cfg_show_hidden", True))
            _is_deep_mode   = _deep_level > 0

            _mode_label = "🔬 Deep Ontology Analysis" if _is_deep_mode else "⚙️ Normal Reasoning"
            st.markdown(
                f"**Analysing event:** `{_sel_title}`"
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
                    "🔬 Running Deep Ontology Analysis (event extraction → evidence enrichment → re-reasoning)..."
                    if _is_deep_mode
                    else "⚙️ Running Evented reasoning pipeline (event extraction → pattern mapping → dual-path conclusion)..."
                )
                with st.status(_status_msg, expanded=True) as _ev_status:
                    try:
                        st.write("📡 Calling backend evented_deduce endpoint…")
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
                            st.write(f"🔬 Deep Ontology level {_deep_level} activated, enriching evidence anchors…")
                        _ev_resp = _api.evented_deduce(
                            _ev_payload,
                            deep_mode=_is_deep_mode,
                            deep_config=_deep_cfg,
                        )
                        if _ev_resp.get("status") == "success" or "events" in _ev_resp:
                            _er = _ev_resp
                            st.session_state.evented_result = _er
                            st.write("✅ Three-stage reasoning complete. Rendering…")
                            _ev_status.update(label="✅ Analysis complete", state="complete")
                        else:
                            _evented_err = str(_ev_resp.get("error") or _ev_resp.get("detail", "Unknown error"))
                            _ev_status.update(label="⚠ Analysis failed", state="error")
                    except Exception as _exc:
                        _evented_err = str(_exc)
                        _ev_status.update(label="⚠ Connection failed", state="error")

            if _evented_err:
                st.error(f"Evented analysis failed: {_evented_err}")

            elif _er is not None:
                _ev_events   = _er.get("events", [])
                _ev_active   = _er.get("active_patterns", [])
                _ev_derived  = _er.get("derived_patterns", [])
                _ev_concl    = _er.get("conclusion", {})
                _ev_cred     = _er.get("credibility", {})
                _ev_enrich   = _er.get("enrichment")
                _ev_ptree    = _er.get("probability_tree", {})
                _ev_la       = _er.get("lie_algebra", {})

                # ── Out-of-scope early exit ──────────────────────────────────
                if _ev_concl.get("out_of_scope"):
                    _oos_domain = _ev_concl.get("out_of_scope_domain", "unknown")
                    st.markdown(
                        f'<div class="out-of-scope-card">'
                        f'<div class="out-of-scope-title">⚠️ Content Outside Analysis Scope</div>'
                        f'<div class="out-of-scope-body">'
                        f'{_ev_concl.get("executive_judgement", "")}'
                        f'<br><br>'
                        f'<b>Detected domain:</b> <code>{_oos_domain}</code><br>'
                        f'<b>Supported domains:</b> geopolitics · economics · technology · military'
                        f'</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    st.caption(
                        "💡 Try submitting a news article about geopolitical events, economic policy, "
                        "technology competition, or military developments to see the full ontological analysis."
                    )
                    if st.button("🔄 Clear & try another article", key="clear_oos"):
                        st.session_state.selected_news   = None
                        st.session_state.evented_result  = None
                        st.rerun()
                    # Skip rest of analysis rendering for out-of-scope
                else:

                    # ── Tab layout: Conclusion first ─────────────────────────
                    _tab_labels = [
                        "① Conclusion",
                        f"② Events ({len(_ev_events)})",
                        f"③ Patterns ({len(_ev_active)}+{len(_ev_derived)})",
                        "🌳 Probability Tree",
                        "🧮 Lie Algebra",
                    ]
                    _tabs_ev = st.tabs(_tab_labels)
                    _tab_concl   = _tabs_ev[0]
                    _tab_ev1     = _tabs_ev[1]
                    _tab_ev2     = _tabs_ev[2]
                    _tab_ptree   = _tabs_ev[3]
                    _tab_lie     = _tabs_ev[4]

                    # ── ① Conclusion (first/default tab) ─────────────────────────
                    with _tab_concl:
                        _ev_path  = _ev_concl.get("evidence_path", {})
                        _hyp_path = _ev_concl.get("hypothesis_path", {})

                        # Evidence Path (T2 grounded)
                        st.markdown("#### 🟢 Evidence Path — T2 Grounded")
                        _ev_summary = _ev_path.get("summary") or "(No grounded evidence path available)"

                        # Change E: Show both Bayesian and Lie algebra results in the summary box
                        _alpha_path_data = _ev_concl.get("alpha_path") or {}
                        _alpha_prob_val  = _alpha_path_data.get("probability", 0)
                        _alpha_lie_em    = _alpha_path_data.get("lie_emergence", {})
                        _alpha_lie_label = _alpha_lie_em.get("nonlinear_label", "")
                        _alpha_integ     = _alpha_path_data.get("integration", {})
                        _alpha_conf_final = _alpha_integ.get("confidence_final")
                        _alpha_verdict   = _alpha_integ.get("verdict", "")
                        _ev_summary_html = (
                            f'<div style="background:#E8F5E9;border-left:4px solid #2E7D32;'
                            f'padding:10px 14px;border-radius:4px;font-size:14px">'
                            f'<b>Bayesian (p={_alpha_prob_val:.0%}):</b> {_ev_summary}'
                            + (f'<br><br><b>Structural emergence:</b> {_alpha_lie_label}' if _alpha_lie_label else '')
                            + (f'<br><span style="font-size:12px;color:#555">Integration verdict: {_alpha_verdict}'
                               f' | final confidence: {_alpha_conf_final:.0%}</span>' if _alpha_conf_final is not None else '')
                            + f'</div>'
                        )
                        st.markdown(_ev_summary_html, unsafe_allow_html=True)

                        # Change A: Move outcome bars into a collapsed expander
                        _ep_outcomes = _ev_path.get("outcomes", [])
                        if _ep_outcomes:
                            with st.expander("📊 Supporting evidence chains", expanded=False):
                                for _oc in _ep_outcomes:
                                    _oc_text = _oc.get("text") or _oc.get("id", "")
                                    _oc_prob = _oc.get("probability", 0)
                                    _oc_bar  = max(4, int(_oc_prob * 100))
                                    st.markdown(
                                        f'<div style="margin:4px 0;">'
                                        f'<span style="font-size:13px;font-weight:600">{_oc_text}</span>'
                                        f'<div style="background:#E0E0E0;border-radius:4px;height:5px;margin-top:3px;">'
                                        f'<div style="background:#2E7D32;width:{_oc_bar}%;height:5px;border-radius:4px;"></div>'
                                        f'</div></div>',
                                        unsafe_allow_html=True,
                                    )

                        # Hypothesis Path (T1 inferred)
                        if _show_hidden:
                            st.markdown("#### 🟡 Hypothesis Path — T1 Inferred")
                            _hyp_summary = _hyp_path.get("summary") or "(No hypothesis path available)"
                            _beta_path_data = _ev_concl.get("beta_path") or {}
                            _beta_prob_val  = _beta_path_data.get("probability", 0)
                            _beta_lie_em    = _beta_path_data.get("lie_emergence", {})
                            _beta_lie_label = _beta_lie_em.get("nonlinear_label", "")
                            _hyp_summary_html = (
                                f'<div style="background:#FFF8E1;border-left:4px solid #F9A825;'
                                f'padding:10px 14px;border-radius:4px;font-size:14px">'
                                f'<b>Bayesian (p={_beta_prob_val:.0%}):</b> {_hyp_summary}'
                                + (f'<br><br><b>Structural emergence:</b> {_beta_lie_label}' if _beta_lie_label else '')
                                + f'</div>'
                            )
                            st.markdown(_hyp_summary_html, unsafe_allow_html=True)

                            # Change A: Move hypothesis outcome bars into a collapsed expander
                            _hyp_outcomes = _hyp_path.get("outcomes", [])
                            if _hyp_outcomes:
                                with st.expander("📊 Alternative scenario evidence", expanded=False):
                                    for _oc in _hyp_outcomes:
                                        _oc_text = _oc.get("text") or _oc.get("id", "")
                                        _oc_prob = _oc.get("probability", 0)
                                        _oc_bar  = max(4, int(_oc_prob * 100))
                                        st.markdown(
                                            f'<div style="margin:4px 0;">'
                                            f'<span style="font-size:13px;font-weight:600">{_oc_text}</span>'
                                            f'<div style="background:#E0E0E0;border-radius:4px;height:5px;margin-top:3px;">'
                                            f'<div style="background:#F9A825;width:{_oc_bar}%;height:5px;border-radius:4px;"></div>'
                                            f'</div></div>',
                                            unsafe_allow_html=True,
                                        )
                            _hyp_gaps = _hyp_path.get("verification_gaps", [])
                            if _hyp_gaps:
                                st.caption("Verification gaps: " + " · ".join(_hyp_gaps))
                        else:
                            st.caption("💡 Hypothesis path hidden — enable 'Show hypothesis path' in the sidebar.")

                        # Executive Judgement
                        st.markdown("#### 📋 Executive Judgement")
                        _exec_j = (
                            _ev_concl.get("executive_judgement")
                            or _ev_concl.get("conclusion")
                            or "(No judgement available)"
                        )
                        # Guard: if backend returns a dict instead of str, convert defensively
                        if not isinstance(_exec_j, str):
                            _exec_j = str(_exec_j)
                        st.info(_exec_j)

                        # Show raw (deterministic) fields in an expander
                        _render_meta = _ev_concl.get("rendering_meta", {})
                        _raw_ej  = _ev_concl.get("executive_judgement_raw", "")
                        _raw_ep  = (_ev_concl.get("evidence_path") or {}).get("summary_raw", "")
                        _raw_hp  = (_ev_concl.get("hypothesis_path") or {}).get("summary_raw", "")
                        if _raw_ej or _raw_ep or _raw_hp:
                            with st.expander("🔍 Show raw (deterministic)", expanded=False):
                                if _render_meta.get("enabled"):
                                    _guard_note = "⚠️ Guardrails triggered — raw text was used for one or more fields." if _render_meta.get("guardrails_triggered") else "✅ All rendered fields passed guardrails."
                                    st.caption(_guard_note)
                                if _raw_ej:
                                    st.markdown("**Executive Judgement (raw)**")
                                    st.text(_raw_ej)
                                if _raw_ep:
                                    st.markdown("**Evidence Path Summary (raw)**")
                                    st.text(_raw_ep)
                                if _raw_hp:
                                    st.markdown("**Hypothesis Path Summary (raw)**")
                                    st.text(_raw_hp)

                        # Confidence from Bayesian posterior
                        _final = _ev_concl.get("final", {})
                        _overall_conf = _final.get("overall_confidence") or _ev_concl.get("confidence", 0)
                        _compute_ref  = _final.get("compute_trace_ref", "")

                        # ── Key Computation Process (always visible, non-hover) ──────
                        # Extract top probability-tree node and dual inference data
                        _concl_ptree = _ev_ptree.get("nodes", [])
                        _top_node = next(
                            (n for n in _concl_ptree if n.get("id") not in ("root",) and n.get("tooltip_data")),
                            None,
                        )
                        _ev_dual_list = _er.get("dual_inference", [])
                        _top_dual     = _ev_dual_list[0] if _ev_dual_list else {}

                        if _top_node:
                            _td = _top_node.get("tooltip_data", {})
                            _kc_bayes = _td.get("bayesian", {})
                            _kc_lie   = _td.get("lie_algebra", {})
                            _kc_dual  = _td.get("dual_integration", {})

                            st.markdown("#### 📐 Key Computation Process")
                            _kca_col, _kcb_col = st.columns(2)

                            # ── A: Bayesian path (Change B: correct formula, no lie_sim^k) ────
                            with _kca_col:
                                _kc_prior_a   = _kc_bayes.get("prior_a", 0)
                                _kc_prior_b   = _kc_bayes.get("prior_b", 0)
                                _kc_lie_sim   = _kc_bayes.get("lie_sim", 0)
                                _kc_posterior = _kc_bayes.get("posterior", 0)
                                _kc_Z         = _kc_bayes.get("Z", 1)
                                _kc_p         = _kc_bayes.get("probability", 0)
                                # Minimum 4% width so even tiny probabilities render a visible bar sliver
                                _kc_bar_pct   = max(4, int(_kc_p * 100))

                                st.markdown("**A · Bayesian Path — Transition Probability**")
                                st.markdown(
                                    f'<div style="font-size:11px;font-family:monospace;background:#F0F4FF;'
                                    f'padding:8px 10px;border-radius:4px;margin-bottom:6px;border-left:3px solid #0047AB">'
                                    f'<b>Question: Which pattern C is most likely activated next?</b><br>'
                                    f'w(A,B→C) = &pi;(A) &times; &pi;(B) &times; cos(v_A + v_B, v_C)<br>'
                                    f'= {_kc_prior_a:.3f} &times; {_kc_prior_b:.3f} &times; {_kc_lie_sim:.3f}<br>'
                                    f'P_Bayes(C) = w / Z = {_kc_posterior:.4f} / {_kc_Z:.4f}'
                                    f' &nbsp;→&nbsp; <b>p = {_kc_p:.1%}</b>'
                                    f'</div>'
                                    # horizontal bar: fill from left, length proportional to p
                                    f'<div style="background:#D8E4F8;border-radius:4px;height:10px;margin:4px 0;">'
                                    f'<div style="background:#0047AB;width:{_kc_bar_pct}%;height:10px;'
                                    f'border-radius:4px;"></div></div>'
                                    f'<div style="font-size:11px;color:#555">'
                                    f'p = <b>{_kc_p:.1%}</b> &nbsp;|&nbsp; Z = {_kc_Z:.4f}'
                                    f' &nbsp;|&nbsp; '
                                    + (_prob_tooltip_html(_kc_p, _top_node) if _top_node else f'{_kc_p:.1%}')
                                    + '</div>',
                                    unsafe_allow_html=True,
                                )

                            # ── B: Lie algebra path (Change C: parallel independent path with emergence) ──
                            with _kcb_col:
                                _kc_mat_norm  = _kc_lie.get("matrix_norm") or _top_dual.get("lie_algebra", {}).get("matrix_norm", 0.0)
                                _kc_sigma1    = _kc_lie.get("sigma1") or _top_dual.get("lie_algebra", {}).get("sigma1", 0.0)
                                _kc_top_dims  = _kc_lie.get("top_emergent_dims") or _top_dual.get("lie_algebra", {}).get("top_emergent_dims", [])
                                _kc_top_vals  = _kc_lie.get("top_emergent_values") or _top_dual.get("lie_algebra", {}).get("top_emergent_values", [])

                                st.markdown("**B · Lie Algebra Path — Emergence Detection (parallel, independent)**")
                                _kc_mat_str   = f"‖[A,B]‖_F = {_kc_mat_norm:.4f}" if _kc_mat_norm else "‖[A,B]‖_F = —"
                                _kc_sigma_str = f" &nbsp;|&nbsp; σ₁ = {_kc_sigma1:.4f}" if _kc_sigma1 else ""
                                st.markdown(
                                    f'<div style="font-size:11px;font-family:monospace;background:#F5F0FF;'
                                    f'padding:8px 10px;border-radius:4px;margin-bottom:6px;border-left:3px solid #7B1FA2">'
                                    f'<b>Question: Which dimensions show non-linear structural effects?</b><br>'
                                    f'C = [X_A, X_B] = X_A @ X_B &minus; X_B @ X_A &nbsp;(8&times;8 commutator)<br>'
                                    f'nonlinear_activation[i] = ‖C[i,:]‖₂ per dimension<br>'
                                    f'<b>{_kc_mat_str}</b>{_kc_sigma_str}'
                                    f'</div>',
                                    unsafe_allow_html=True,
                                )

                                # Show top emergent dimensions as bars
                                if _kc_top_dims and _kc_top_vals:
                                    _max_v = max(_kc_top_vals) if _kc_top_vals else 1.0
                                    # Bar width scaled to 80px max; minimum 2px for visibility
                                    _dim_bar_max_px = 80
                                    for _dim, _val in zip(_kc_top_dims[:3], _kc_top_vals[:3]):
                                        _dim_bar = max(2, int(_val / max(_max_v, 1e-9) * _dim_bar_max_px))
                                        st.markdown(
                                            f'<div style="font-size:11px;margin:2px 0;display:flex;align-items:center;gap:6px">'
                                            f'<span style="display:inline-block;min-width:72px;color:#555">{_dim}</span>'
                                            f'<span style="display:inline-block;background:#7B1FA2;height:6px;'
                                            f'width:{_dim_bar}px;border-radius:2px"></span>'
                                            f'<span style="color:#555">{_val:.3f}</span>'
                                            f'</div>',
                                            unsafe_allow_html=True,
                                        )

                                # Expand/collapse: inspect 8x8 bracket matrix
                                _kc_bracket = _top_dual.get("lie_algebra", {}).get("bracket_matrix")
                                if _kc_bracket:
                                    import json as _json
                                    _mat_json = _json.dumps(_kc_bracket, separators=(",", ":"))
                                    with st.expander("🔎 Inspect 8×8 bracket matrix [X_A, X_B]", expanded=False):
                                        st.caption(
                                            "C = [X_A, X_B] = X_A @ X_B − X_B @ X_A (8×8 antisymmetric matrix). "
                                            "Row i shows non-linear interference of dimension i on all others."
                                        )
                                        _rows = ["coercion", "cooperation", "dependency", "information",
                                                 "regulation", "military", "economic", "technology"]
                                        for _ri, _row in enumerate(_kc_bracket):
                                            _row_vals = "  ".join(f"{v:+.3f}" for v in _row)
                                            _row_label = _rows[_ri] if _ri < len(_rows) else f"dim{_ri}"
                                            st.markdown(
                                                f'<div style="font-size:10px;font-family:monospace;'
                                                f'color:#333;padding:1px 0">'
                                                f'<span style="color:#555;display:inline-block;width:80px">{_row_label}</span>'
                                                f'{_row_vals}'
                                                f'</div>',
                                                unsafe_allow_html=True,
                                            )
                                        st.download_button(
                                            label="⬇️ Download matrix JSON",
                                            data=_mat_json,
                                            file_name="bracket_matrix.json",
                                            mime="application/json",
                                        )

                            # ── C: Integration Layer (Change D) ───────────────────────────
                            st.markdown("**C · Integration Layer**")
                            _kc_dual_integ = _kc_dual if _kc_dual else (_ev_concl.get("final", {}).get("dual_integration", {}))
                            _consist       = _kc_dual_integ.get("consistency_score")
                            _verdict       = _kc_dual_integ.get("verdict", "")
                            _conf_final    = _kc_dual_integ.get("confidence_final")
                            _conf_formula  = _kc_dual_integ.get("confidence_formula", "")
                            if _consist is not None:
                                st.markdown(
                                    f'<div style="font-size:11px;font-family:monospace;background:#F0FFF0;'
                                    f'padding:8px 10px;border-radius:4px;border-left:3px solid #2E7D32">'
                                    f'consistency = cos(nonlinear_activation, v_C) = <b>{_consist:.3f}</b>'
                                    f' &nbsp; verdict: <b>{_verdict}</b><br>'
                                    f'confidence_final = P_Bayes &times; (1 + 0.3 &times; max(0, consistency)) / 1.3<br>'
                                    + (f'= <b>{_conf_formula}</b>' if _conf_formula else (f'= <b>{_conf_final:.3f}</b>' if _conf_final is not None else ''))
                                    + f'</div>',
                                    unsafe_allow_html=True,
                                )
                            else:
                                st.caption("Integration layer data not available for this result.")
                        else:
                            st.caption(
                                "📐 Run an analysis to see the Key Computation Process "
                                "(Bayesian formula + Lie algebra results) displayed here."
                            )

                        # Confidence metric row
                        _c1, _c2 = st.columns(2)
                        with _c1:
                            st.metric("Overall Confidence", f"{_overall_conf:.0%}")
                        with _c2:
                            st.caption(f"Compute trace: `{_compute_ref}`")

                        with st.expander("🛠 Raw JSON (Evented result)", expanded=False):
                            st.json(_er)

                    # ── ② Events ─────────────────────────────────────────────────
                    with _tab_ev1:
                        if not _ev_events:
                            st.info("No valid events extracted from the text (all candidates rejected by T0 filter).")
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
                                f'&nbsp;&nbsp;<span style="color:#666;font-size:11px">confidence {_ev_conf:.0%}</span>'
                                f'<div style="font-size:12px;color:#555;margin-top:4px">📎 {_ev_quote}</div>'
                                f'<div style="font-size:11px;color:#888;margin-top:2px">Inferred fields: {_ev_inf}</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                    # ── ③ Patterns ────────────────────────────────────────────────
                    with _tab_ev2:
                        if _ev_active:
                            st.markdown("**🔵 Active Patterns**")
                            for _ap in _ev_active:
                                _ap_tier  = _ap.get("tier", "T2")
                                _ap_conf  = _ap.get("confidence", 0)
                                _ap_inf   = _ap.get("inferred", False)
                                _ap_color = "#2E7D32" if _ap_tier == "T2" else "#E65100"
                                st.markdown(
                                    f'<div style="border-left:3px solid {_ap_color};'
                                    f'padding:6px 10px;margin-bottom:6px;background:#FAFAFA;">'
                                    f'<b>{_ap.get("pattern", _ap.get("pattern_name", ""))}</b>'
                                    f'&nbsp;<span style="background:{_ap_color};color:#fff;'
                                    f'padding:1px 6px;border-radius:8px;font-size:11px">{_ap_tier}</span>'
                                    f'&nbsp;<span style="color:#888;font-size:11px">Pr={_ap_conf:.0%}'
                                    f'{" · inferred" if _ap_inf else ""}</span>'
                                    f'&nbsp;<span style="color:#aaa;font-size:10px">← {_ap.get("from_event","")}</span>'
                                    f'</div>',
                                    unsafe_allow_html=True,
                                )
                        else:
                            st.info("No active patterns.")

                        if _ev_derived:
                            st.markdown("**🟣 Derived Patterns (via Composition)**")
                            for _dp in _ev_derived:
                                _dp_tier  = _dp.get("derived_tier", "T1")
                                _dp_conf  = _dp.get("derived_confidence", 0)
                                _dp_rule  = _dp.get("rule", "")
                                _dp_color = "#2E7D32" if _dp_tier == "T2" else "#7B1FA2"
                                st.markdown(
                                    f'<div style="border-left:3px solid {_dp_color};'
                                    f'padding:6px 10px;margin-bottom:6px;background:#F8F0FF;">'
                                    f'<b>{_dp.get("derived", _dp.get("pattern_name", ""))}</b>'
                                    f'&nbsp;<span style="background:{_dp_color};color:#fff;'
                                    f'padding:1px 6px;border-radius:8px;font-size:11px">{_dp_tier}</span>'
                                    f'&nbsp;<span style="color:#888;font-size:11px">Pr={_dp_conf:.0%}</span>'
                                    f'<div style="font-size:10px;color:#aaa;margin-top:2px">rule: {_dp_rule}</div>'
                                    f'</div>',
                                    unsafe_allow_html=True,
                                )
                        else:
                            st.caption("No derived patterns (requires at least two composable active patterns).")

                        # Logic chain showing how conclusion was derived
                        _ev_top_trans = _er.get("top_transitions", [])
                        if _ev_top_trans:
                            st.markdown("**⛓ Composition Logic Chain**")
                            st.caption(
                                "Shows how active patterns combine via the composition table "
                                "to derive projected transitions. Each row is one edge in the inference graph."
                            )
                            for _tx in _ev_top_trans[:5]:
                                _tx_a = _tx.get("from_pattern_a", "")
                                _tx_b = _tx.get("from_pattern_b", "")
                                _tx_c = _tx.get("to_pattern", "")
                                _tx_pw = _tx.get("posterior_weight", 0)
                                _tx_tt = _tx.get("transition_type", "compose")
                                _tx_color = "#7B1FA2" if _tx_tt == "inverse" else "#1565C0"
                                st.markdown(
                                    f'<div style="border-left:3px solid {_tx_color};'
                                    f'padding:4px 10px;margin-bottom:4px;background:#FAFAFA;font-size:12px;">'
                                    f'<b>[{_tx_tt.upper()}]</b> '
                                    f'{_tx_a} ⊕ {_tx_b} → <b>{_tx_c}</b>'
                                    f'&nbsp;<span style="color:#888">posterior={_tx_pw:.4f}</span>'
                                    f'</div>',
                                    unsafe_allow_html=True,
                                )

                    # ── 🌳 Probability Tree (with credibility merged) ─────────────
                    with _tab_ptree:
                        if _ev_ptree:
                            _pt_nodes    = _ev_ptree.get("nodes", [])
                            _pt_edges    = _ev_ptree.get("edges", [])
                            _pt_cred_ov  = _ev_ptree.get("overall_credibility", _ev_cred.get("overall_score", 0))
                            _pt_selected = _ev_ptree.get("selected_branch")
                            _pt_summary  = _ev_ptree.get("summary", "")
                            _pt_trace    = _ev_ptree.get("compute_trace", {})

                            st.markdown("#### 🌳 Probability Tree — Bayesian Posterior")
                            st.caption(
                                "Probabilities are computed as: **posterior = prior_A × prior_B × lie_similarity**, "
                                "then normalised by Z = Σ(all posterior weights). "
                                "All values are derived from the ontology prior + Lie algebra similarity."
                            )
                            if _pt_summary:
                                st.info(_pt_summary)

                            # Bayesian compute trace
                            if _pt_trace:
                                with st.expander("📐 Bayesian Compute Trace", expanded=False):
                                    _tc1, _tc2, _tc3 = st.columns(3)
                                    _tc1.metric("Z (partition function)", f"{_pt_trace.get('Z', 0):.6f}")
                                    _tc2.metric("Active patterns", _pt_trace.get("n_active", 0))
                                    _tc3.metric("Transitions evaluated", _pt_trace.get("n_transitions", 0))
                                    st.caption(f"Formula: **{_pt_trace.get('posterior_formula', '')}**")
                                    st.caption(f"Normalisation: {_pt_trace.get('normalization', '')}")
                                    st.caption(f"Epsilon floor: {_pt_trace.get('epsilon_floor', 1e-4)}")

                            # Render root node
                            _root = next((n for n in _pt_nodes if n.get("id") == "root"), None)
                            if _root:
                                st.markdown(
                                    f'<div style="background:#E3F2FD;border-left:4px solid #0047AB;'
                                    f'padding:8px 12px;border-radius:4px;margin-bottom:8px;">'
                                    f'<b>ROOT:</b> {_root.get("evidence", "")}'
                                    f'</div>',
                                    unsafe_allow_html=True,
                                )

                            # Render child nodes
                            _child_nodes = [n for n in _pt_nodes if n.get("id") != "root"]
                            for _cn in sorted(_child_nodes, key=lambda x: -x.get("probability", 0)):
                                _cn_prob  = _cn.get("probability", 0)
                                _cn_label = _cn.get("label", "")
                                _cn_type  = _cn.get("type", "")
                                _cn_evid  = _cn.get("evidence", "")
                                _cn_gap   = _cn.get("verification_gap", "")
                                _is_best  = (_cn.get("id") == _pt_selected)
                                _cn_bg    = "#E8F5E9" if _is_best else "#FAFAFA"
                                _cn_bdr   = "#2E7D32" if _is_best else "#90A4AE"
                                _bar_w    = max(4, int(_cn_prob * 100))
                                _star_html = "&nbsp; ⭐ <em>highest probability</em>" if _is_best else ""
                                _evid_html = (
                                    f'<div style="font-size:11px;color:#777;margin-top:3px">'
                                    f'🧮 {_cn_evid[:120]}</div>'
                                ) if _cn_evid else ""
                                _gap_html = (
                                    f'<div style="font-size:10px;color:#E65100;margin-top:2px">'
                                    f'⚠ {str(_cn_gap)[:80]}</div>'
                                ) if _cn_gap else ""
                                # Use hover tooltip when tooltip_data is available
                                _has_tooltip = bool(_cn.get("tooltip_data"))
                                _prob_html = (
                                    _prob_tooltip_html(_cn_prob, _cn)
                                    if _has_tooltip
                                    else f'<span style="font-size:11px;color:#555">p = {_cn_prob:.2%}</span>'
                                )
                                st.markdown(
                                    f'<div style="background:{_cn_bg};border-left:4px solid {_cn_bdr};'
                                    f'padding:8px 12px;border-radius:4px;margin-bottom:6px;">'
                                    f'<b>{_cn_label}</b>{_star_html}'
                                    f'<div style="margin:4px 0;background:#E0E0E0;border-radius:4px;height:6px;">'
                                    f'<div style="background:{_cn_bdr};width:{_bar_w}%;height:6px;border-radius:4px;"></div>'
                                    f'</div>'
                                    f'{_prob_html}'
                                    f'<span style="font-size:11px;color:#555"> · tier: {_cn_type}</span>'
                                    f'{_evid_html}{_gap_html}'
                                    f'</div>',
                                    unsafe_allow_html=True,
                                )

                            st.divider()
                            # Credibility metrics (merged into this tab)
                            st.markdown("#### 📊 Credibility Metrics")
                            _vc1, _vc2, _vc3 = st.columns(3)
                            with _vc1:
                                _vs = _ev_cred.get("verifiability_score", 0)
                                st.metric("Verifiability", f"{_vs:.0%}")
                            with _vc2:
                                _ks = _ev_cred.get("kg_consistency_score", 0)
                                st.metric("KG Consistency", f"{_ks:.0%}")
                            with _vc3:
                                _os = _pt_cred_ov
                                st.metric("Overall Score", f"{_os:.0%}")
                            _missing = _ev_cred.get("missing_evidence", [])
                            if _missing:
                                st.warning("Missing evidence anchors: " + ", ".join(_missing))
                            _contras = _ev_cred.get("contradictions", [])
                            if _contras:
                                st.error("Contradictions detected: " + " | ".join(_contras))
                            _cred_note = _ev_cred.get("note", "")
                            if _cred_note:
                                st.caption(_cred_note)
                        else:
                            st.info(
                                "Probability tree not available. "
                                "Run an Evented analysis to generate causal branching."
                            )

                    # ── 🧮 Lie Algebra ────────────────────────────────────────────
                    with _tab_lie:
                        _sv = _er.get("state_vector", {})
                        _la = _er.get("lie_algebra", {})

                        st.markdown("#### 🧮 Lie Algebra — 8D Ontological State Vector")
                        st.caption(
                            "The ontological state is modelled as a vector in an 8-dimensional Lie algebra space. "
                            "Each active pattern contributes a vector **v** ∈ ℝ⁸. "
                            "The aggregate state is **v̄** = Σᵢ wᵢ·vᵢ, where wᵢ is the pattern's confidence prior. "
                            "Phase transitions occur when ‖vₜ − vₜ₋₁‖ > 0.25."
                        )

                        # Cartesian product explanation
                        with st.expander("📐 Cartesian Product & Lie Group Theory", expanded=False):
                            st.markdown("""
    **Cartesian product mapping**: The pattern library defines a mapping

    > **E × R × E → Pattern**

    where E is the set of ontological entities and R is the set of relations.
    Each triple (entity₁, relation, entity₂) projects to a named dynamic pattern.

    **Continuous projection to Lie space**: Each pattern P maps to a vector **v_P** ∈ ℝ⁸
    encoding its intensity across 8 semantic dimensions:
    `coercion · cooperation · dependency · information · regulation · military · economic · technology`

    **Composition as vector addition**: In the Lie algebra approximation,
    composing two patterns A ⊕ B corresponds to **v_A + v_B**, and the target pattern C
    is selected by maximising cosine similarity: `cos(v_A + v_B, v_C)`.

    **Lie bracket [v_A, v_B]** (antisymmetric part) captures higher-order interaction effects
    — when two patterns reinforce each other, the bracket term is large; when they oppose,
    it is small. This reflects the *structure constants* of the underlying finite group.

    **Phase transitions**: A transition is flagged when the aggregate state vector shifts
    by more than ‖Δv‖ > 0.25, indicating that a continuous change in weights has
    caused a *discontinuous* shift in the dominant semantic regime.
                            """)

                        # 8D state vector display
                        _sv_mean = _sv.get("mean_vector") or {}
                        _dim_values = _sv_mean.get("dim_values") if isinstance(_sv_mean, dict) else {}
                        _dominant = _sv_mean.get("dominant_dim") if isinstance(_sv_mean, dict) else _sv.get("dominant_dim", "unknown")
                        _mean_list = _er.get("state_vector", {}).get("mean_vector_list", [])

                        if _dim_values or _mean_list:
                            st.markdown("**8D State Vector**")
                            _dims = ["coercion", "cooperation", "dependency", "information",
                                     "regulation", "military", "economic", "technology"]
                            _cols = st.columns(4)
                            for _di, _dname in enumerate(_dims):
                                _dval = (
                                    _dim_values.get(_dname, 0)
                                    if _dim_values
                                    else (_mean_list[_di] if _di < len(_mean_list) else 0)
                                )
                                _col = _cols[_di % 4]
                                _bar_w = max(4, int(abs(_dval) * 100))
                                _col.markdown(
                                    f'<div style="font-size:11px;font-weight:600">{_dname}</div>'
                                    f'<div style="background:#E0E0E0;border-radius:3px;height:5px;margin:2px 0 4px 0;">'
                                    f'<div style="background:{"#0047AB" if _dval >= 0 else "#DC3545"};'
                                    f'width:{_bar_w}%;height:5px;border-radius:3px;"></div></div>'
                                    f'<div style="font-size:10px;color:#555">{_dval:+.3f}</div>',
                                    unsafe_allow_html=True,
                                )

                            if _dominant:
                                st.markdown(f"**Dominant dimension:** `{_dominant}`")
                        else:
                            st.info("State vector not available (no active patterns or Lie algebra computation failed).")

                        # Lie algebra outputs
                        _phase_transitions = _la.get("phase_transitions") or _sv.get("phase_transitions", [])
                        if _phase_transitions:
                            st.markdown("**⚡ Phase Transitions Detected**")
                            for _pt_item in _phase_transitions:
                                if isinstance(_pt_item, dict):
                                    st.markdown(
                                        f'<div style="border-left:3px solid #DC3545;padding:4px 10px;'
                                        f'margin-bottom:4px;background:#FFF0F0;font-size:12px;">'
                                        f'Step {_pt_item.get("step","?")}: ‖Δv‖ = {_pt_item.get("delta_norm", 0):.3f}'
                                        f' &gt; 0.25 → transition at <b>{_pt_item.get("dimension","?")}</b>'
                                        f'</div>',
                                        unsafe_allow_html=True,
                                    )
                                else:
                                    st.caption(str(_pt_item))

                        # Evidence Enrichment (collapsible, collapsed by default)
                        if _ev_enrich is not None:
                            st.divider()
                            with st.expander("🔬 Evidence Enrichment (Deep Ontology)", expanded=False):
                                _enr_missing_before = _ev_enrich.get("missing_before", [])
                                _enr_missing_after  = _ev_enrich.get("missing_after", [])
                                _enr_provenance     = _ev_enrich.get("provenance", [])
                                _enr_summary        = _ev_enrich.get("enriched_context_summary", "")
                                _enr_cache_hit      = _ev_enrich.get("cache_hit", False)
                                _enr_limits         = _ev_enrich.get("limits", {})
                                _enr_error          = _ev_enrich.get("error")
                                _enr_level          = _ev_enrich.get("level", 0)

                                _level_labels = {0: "Off", 1: "Local metadata", 2: "+Fetch source", 3: "+Web search"}
                                st.markdown(
                                    f"**🔬 Deep Ontology Analysis** · Level {_enr_level} "
                                    f"({_level_labels.get(_enr_level, '')})"
                                    + (" &nbsp; 🗄️ `cache hit`" if _enr_cache_hit else ""),
                                    unsafe_allow_html=True,
                                )

                                if _enr_error:
                                    st.error(f"Enrichment failed (fell back to normal result): {_enr_error}")

                                _filled = [a for a in _enr_missing_before if a not in _enr_missing_after]
                                _col_a, _col_b = st.columns(2)
                                with _col_a:
                                    st.markdown("**Missing anchors before enrichment**")
                                    for _anc in _enr_missing_before:
                                        _ok = _anc in _filled
                                        st.markdown(
                                            f'<span style="color:{"#2E7D32" if _ok else "#C62828"}">'
                                            f'{"✅" if _ok else "❌"} {_anc}</span>',
                                            unsafe_allow_html=True,
                                        )
                                with _col_b:
                                    st.markdown("**Still missing after enrichment**")
                                    if _enr_missing_after:
                                        for _anc in _enr_missing_after:
                                            st.markdown(f"• {_anc}")
                                    else:
                                        st.success("All anchors filled ✓")

                                if _enr_summary:
                                    st.caption(_enr_summary)

                                if _enr_provenance:
                                    st.markdown("**📋 Evidence Provenance**")
                                    for _prov in _enr_provenance:
                                        _p_anchor  = _prov.get("anchor_type", "")
                                        _p_snippet = _prov.get("snippet", "")
                                        _p_url     = _prov.get("source_url", "")
                                        _p_title   = _prov.get("title", "")
                                        _p_conf    = _prov.get("confidence", 0)
                                        st.markdown(
                                            f'<div style="border-left:3px solid #1565C0;'
                                            f'padding:6px 12px;margin-bottom:6px;background:#E3F2FD;border-radius:4px;">'
                                            f'<span style="font-weight:700;font-size:12px;color:#1565C0">{_p_anchor}</span>'
                                            f'&nbsp;&nbsp;<span style="color:#555;font-size:11px">confidence {_p_conf:.0%}</span>'
                                            f'<div style="font-size:13px;margin-top:3px">{_p_snippet}</div>'
                                            + (f'<div style="font-size:11px;color:#888;margin-top:2px">'
                                               f'Source: <a href="{_p_url}" target="_blank">{_p_title or _p_url}</a>'
                                               f'</div>' if _p_url else "")
                                            + f'</div>',
                                            unsafe_allow_html=True,
                                        )
                                else:
                                    st.info("No new evidence sources extracted.")

                                if _enr_limits:
                                    _lim_parts = []
                                    if _enr_limits.get("searched"):
                                        _lim_parts.append("web search executed")
                                    _furl = _enr_limits.get("fetched_urls", 0)
                                    if _furl:
                                        _lim_parts.append(f"fetched {_furl} URL(s)")
                                    if _enr_limits.get("truncated"):
                                        _lim_parts.append("⚠️ truncated due to timeout")
                                    if _lim_parts:
                                        st.caption("Limits: " + " · ".join(_lim_parts))

            if st.button("🔄 Clear selection", key="clear_selection_evented"):
                st.session_state.selected_news  = None
                st.session_state.evented_result = None
                st.rerun()

    st.markdown('<div class="elite-divider"></div>', unsafe_allow_html=True)
    with st.expander("ℹ️ Active Ontology Sub-Graphs", expanded=False):
        st.write("""
        **Current ontology engine status:**
        * 🟢 **[Geopolitics Ontology]**: Sanctions, alliance, coercion pattern library loaded
        * 🟢 **[Economics & Finance Ontology]**: Trade dependency, central bank transmission, supply chain patterns loaded
        * 🟢 **[Technology Ontology]**: Tech decoupling, standards dominance, technology blockade patterns loaded
        * 🟡 **[Technology Transition Ontology]**: Tech diffusion rate, policy resistance, compliance cost matrix (pending deep build)
        """)


# ===========================================================================
# Page: Streams
# ===========================================================================
elif page == "Streams":
    st.title("📰 Real-Time Intelligence Feed")
    st.caption(
        "Aggregated news from monitored sources. Click **Run Ontological Analysis** "
        "on any article to send it to the Home page analysis panel."
    )

    col_title, col_refresh = st.columns([3, 1])
    with col_refresh:
        if st.button("🔄 Refresh Now", key="refresh_news"):
            with st.spinner("📡 Aggregating news…"):
                result = _api.ingest_news()
                if "error" not in result:
                    st.success("✅ News aggregation complete!")
                else:
                    st.error(f"❌ Error: {result['error']}")

    col_hours, col_limit = st.columns(2)
    with col_hours:
        hours = st.slider("Time range (hours)", min_value=1, max_value=168, value=24)
    with col_limit:
        limit = st.slider("Articles to display", min_value=5, max_value=100, value=20)

    search_query = st.text_input("🔍 Keyword search", placeholder="Enter keywords…")

    if search_query:
        data = _api.search_news(search_query, limit=limit)
    else:
        data = _api.get_latest_news(limit=limit, hours=hours)

    if "error" in data:
        st.warning(
            "⚠️ Backend is currently unavailable. Intelligence Feed requires a running backend.\n\n"
            "To run locally: `cd backend && uvicorn app.main:app --port 8000`"
        )
        if st.button("🔄 Retry", key="feed_retry"):
            st.rerun()
    else:
        articles: List[Dict[str, Any]] = data.get("articles", [])
        if search_query:
            st.info(f"🔍 Found {len(articles)} results")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📰 Articles", len(articles))
        m2.metric("📂 Categories", len({a.get("category", "?") for a in articles}))
        m3.metric("🏢 Sources", len({a.get("source", "?") for a in articles}))
        m4.metric("⏰ Time range", f"{hours} h")
        st.divider()

        import hashlib as _hashlib

        with st.expander("🌊 Raw News Stream", expanded=False):
            st.caption("⚠️ Unfiltered raw data stream.")
            if articles:
                for i, article in enumerate(articles, 1):
                    title_preview = (article.get("title") or "(no title)")[:80]
                    _key_src  = (article.get("link") or article.get("title") or str(i)).encode("utf-8", errors="replace")
                    _cache_key = f"kg_{_hashlib.md5(_key_src).hexdigest()}"

                    with st.expander(f"🔹 [{i}] {title_preview}…", expanded=False):
                        c1, c2, c3 = st.columns(3)
                        c1.caption(f"📌 Source: {article.get('source', 'N/A')}")
                        c2.caption(f"📍 Category: {article.get('category', 'N/A')}")
                        c3.caption(f"⏰ Date: {str(article.get('published', 'N/A'))[:10]}")
                        st.write(article.get("description") or "(no summary)")
                        if article.get("link"):
                            st.markdown(f"[📖 Read original]({article['link']})")

                        # Navigate to analysis
                        if st.button("⚔️ Run Ontological Analysis", key=f"news_deduce_{i}"):
                            st.session_state.selected_news    = article
                            st.session_state.deduction_result = None
                            st.session_state.evented_result   = None
                            st.session_state.current_page     = "Dashboard"
                            st.rerun()

                        # Knowledge graph extraction
                        already = _cache_key in st.session_state.kg_cache
                        btn_lbl = "✅ KG extracted" if already else "🧠 Extract KG"
                        if st.button(btn_lbl, key=f"kg_btn_{i}"):
                            _text = " ".join(filter(None, [
                                article.get("title", ""), article.get("description", ""),
                            ])).strip()
                            if _text:
                                with st.spinner("Extracting…"):
                                    _kg_resp = _api.extract_knowledge(_text)
                                if _kg_resp.get("status") == "error" or (
                                    "error" in _kg_resp and "entities" not in _kg_resp
                                ):
                                    st.error(f"❌ KG extraction failed: {_kg_resp.get('error')}")
                                else:
                                    st.session_state.kg_cache[_cache_key] = _kg_resp
                                    st.rerun()
                            else:
                                st.warning("⚠️ No text content available for this article.")

                        if _cache_key in st.session_state.kg_cache:
                            _kg_data = st.session_state.kg_cache[_cache_key]
                            _entities_kg  = _kg_data.get("entities", [])
                            _relations_kg = _kg_data.get("relations", [])
                            with st.expander(
                                f"🕸️ KG Result (entities: {len(_entities_kg)}, relations: {len(_relations_kg)})",
                                expanded=True,
                            ):
                                if _entities_kg:
                                    st.write("**📋 Entities**")
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
                                    st.write("**🔗 Relations**")
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
# Page: Assessments
# ===========================================================================
elif page == "Assessments":
    st.title("📝 Custom Content Analysis")
    st.caption(
        "Analyse your own text content (and optionally a source URL) using the "
        "Evented or Grounded reasoning engine. Results are displayed below."
    )
    st.info(
        "**How to use:** Paste or type any text (news, report, article excerpt) in the box below. "
        "Optionally add a source URL for Deep Ontology enrichment (level ≥ 2). "
        "Select your engine and click **Run Analysis**."
    )

    _ca_col1, _ca_col2 = st.columns([3, 2], gap="large")

    with _ca_col1:
        _ca_text = st.text_area(
            "Content to analyse",
            height=200,
            placeholder="Paste article text, news summary, or any relevant content here…",
            key="ca_text",
        )
        _ca_url = st.text_input(
            "Source URL (optional)",
            placeholder="https://example.com/article",
            key="ca_url",
            help="Providing a URL enables Deep Ontology level 2+ enrichment (fetch original source).",
        )

        _ca_engine = st.session_state.get("cfg_engine", "Evented")
        _ca_deep   = int(st.session_state.get("cfg_deep_level", 0))
        _ca_btn_c1, _ca_btn_c2 = st.columns(2)
        with _ca_btn_c1:
            _ca_run_ev = st.button(
                "▶ Run Evented",
                type="primary",
                use_container_width=True,
                key="ca_run_evented",
            )
        with _ca_btn_c2:
            _ca_run_gr = st.button(
                "▶ Run Grounded",
                use_container_width=True,
                key="ca_run_grounded",
            )
        if _ca_run_gr:
            st.caption("⚠️ Grounded mode requires a non-empty Knowledge Graph in KuzuDB.")

    with _ca_col2:
        st.markdown("**Engine settings (from sidebar)**")
        st.markdown(
            f"Engine: **{_ca_engine}** · Deep level: **{_ca_deep}** · "
            f"Hypothesis: **{'on' if st.session_state.get('cfg_show_hidden', True) else 'off'}**"
        )
        st.caption("Change engine and Deep Ontology level in the sidebar's Reasoning Engine section.")

    if _ca_run_ev or _ca_run_gr:
        _ca_text_val = (_ca_text or "").strip()
        _ca_url_val  = (_ca_url or "").strip()

        if not _ca_text_val:
            st.warning("⚠️ Please enter some content to analyse.")
        else:
            _ca_news = {
                "title":       _ca_text_val[:120],
                "summary":     _ca_text_val,
                "description": _ca_text_val,
                "url":         _ca_url_val,
                "entities":    [],
            }
            _ca_is_deep = _ca_deep > 0
            _ca_deep_cfg = (
                {"level": _ca_deep, "timeout_seconds": 20, "max_sources": 3}
                if _ca_is_deep else None
            )

            if _ca_run_ev:
                with st.status("⚙️ Running Evented analysis…", expanded=True) as _ca_st:
                    try:
                        st.write("📡 Calling evented_deduce…")
                        _ca_ev_resp = _api.evented_deduce(
                            _ca_news,
                            deep_mode=_ca_is_deep,
                            deep_config=_ca_deep_cfg,
                        )
                        if _ca_ev_resp.get("status") == "success" or "events" in _ca_ev_resp:
                            _ca_st.update(label="✅ Evented analysis complete", state="complete")
                        else:
                            _ca_st.update(label="⚠ Analysis failed", state="error")
                            st.error(str(_ca_ev_resp.get("error") or _ca_ev_resp.get("detail", "Unknown error")))
                            _ca_ev_resp = None
                    except Exception as _ca_exc:
                        _ca_st.update(label="⚠ Connection failed", state="error")
                        st.error(str(_ca_exc))
                        _ca_ev_resp = None

                if _ca_ev_resp:
                    _ca_concl   = _ca_ev_resp.get("conclusion", {})
                    _ca_cred    = _ca_ev_resp.get("credibility", {})
                    _ca_evts    = _ca_ev_resp.get("events", [])
                    _ca_pats    = _ca_ev_resp.get("active_patterns", [])
                    _ca_ptree   = _ca_ev_resp.get("probability_tree", {})

                    st.subheader("Evented Result")
                    _ca_c1, _ca_c2 = st.columns(2)
                    with _ca_c1:
                        st.metric("Events extracted", len(_ca_evts))
                        st.metric("Active patterns", len(_ca_pats))
                    with _ca_c2:
                        _ov = _ca_cred.get("overall_score", 0)
                        st.metric("Credibility", f"{_ov:.0%}")
                        _ca_final = _ca_concl.get("final", {})
                        _ca_conf  = _ca_final.get("overall_confidence") or _ca_concl.get("confidence", 0)
                        st.metric("Overall Confidence", f"{_ca_conf:.0%}")

                    st.markdown("**Executive Judgement**")
                    _ca_exec_j = (
                        _ca_concl.get("executive_judgement")
                        or _ca_concl.get("conclusion")
                        or "(No judgement available)"
                    )
                    if not isinstance(_ca_exec_j, str):
                        _ca_exec_j = str(_ca_exec_j)
                    st.info(_ca_exec_j)

                    # Show raw (deterministic) fields in an expander
                    _ca_render_meta = _ca_concl.get("rendering_meta", {})
                    _ca_raw_ej = _ca_concl.get("executive_judgement_raw", "")
                    _ca_raw_ep = (_ca_concl.get("evidence_path") or {}).get("summary_raw", "")
                    _ca_raw_hp = (_ca_concl.get("hypothesis_path") or {}).get("summary_raw", "")
                    if _ca_raw_ej or _ca_raw_ep or _ca_raw_hp:
                        with st.expander("🔍 Show raw (deterministic)", expanded=False):
                            if _ca_render_meta.get("enabled"):
                                _ca_guard_note = "⚠️ Guardrails triggered — raw text was used for one or more fields." if _ca_render_meta.get("guardrails_triggered") else "✅ All rendered fields passed guardrails."
                                st.caption(_ca_guard_note)
                            if _ca_raw_ej:
                                st.markdown("**Executive Judgement (raw)**")
                                st.text(_ca_raw_ej)
                            if _ca_raw_ep:
                                st.markdown("**Evidence Path Summary (raw)**")
                                st.text(_ca_raw_ep)
                            if _ca_raw_hp:
                                st.markdown("**Hypothesis Path Summary (raw)**")
                                st.text(_ca_raw_hp)

                    _ca_ev_path = _ca_concl.get("evidence_path", {})
                    if _ca_ev_path.get("summary"):
                        st.markdown("**Evidence Path (T2 grounded)**")
                        st.success(_ca_ev_path["summary"])

                    if st.session_state.get("cfg_show_hidden", True):
                        _ca_hyp = _ca_concl.get("hypothesis_path", {})
                        if _ca_hyp.get("summary"):
                            st.markdown("**Hypothesis Path (T1 inferred)**")
                            st.warning(_ca_hyp["summary"])

                    # Probability tree summary
                    if _ca_ptree:
                        _ca_pt_summary = _ca_ptree.get("summary", "")
                        _ca_pt_cred    = _ca_ptree.get("overall_credibility", 0)
                        with st.expander(
                            f"🌳 Probability Tree (credibility {_ca_pt_cred:.0%})",
                            expanded=False,
                        ):
                            if _ca_pt_summary:
                                st.info(_ca_pt_summary)
                            for _cn in sorted(
                                [n for n in _ca_ptree.get("nodes", []) if n.get("id") != "root"],
                                key=lambda x: -x.get("probability", 0),
                            ):
                                _bar = max(4, int(_cn.get("probability", 0) * 100))
                                st.markdown(
                                    f'<div style="border-left:3px solid #0047AB;'
                                    f'padding:4px 8px;margin-bottom:4px;background:#F5F5F5;">'
                                    f'<b>{_cn.get("label","")}</b> &nbsp;'
                                    f'<span style="color:#555;font-size:11px">p={_cn.get("probability",0):.2%}</span>'
                                    f'<div style="background:#E0E0E0;height:4px;border-radius:2px;margin-top:3px;">'
                                    f'<div style="background:#0047AB;width:{_bar}%;height:4px;border-radius:2px;"></div>'
                                    f'</div></div>',
                                    unsafe_allow_html=True,
                                )

                    with st.expander("📋 Full JSON response", expanded=False):
                        st.json(_ca_ev_resp)

            elif _ca_run_gr:
                with st.status("⚙️ Running Grounded analysis…", expanded=True) as _ca_st:
                    try:
                        st.write("📡 Calling grounded_deduce…")
                        _ca_gr_resp = _api.grounded_deduce(_ca_news)
                        if "error" in _ca_gr_resp and "deduction_result" not in _ca_gr_resp:
                            _ca_st.update(label="⚠ Analysis failed", state="error")
                            st.error(str(_ca_gr_resp["error"]))
                            _ca_gr_resp = None
                        else:
                            _ca_st.update(label="✅ Grounded analysis complete", state="complete")
                    except Exception as _ca_exc:
                        _ca_st.update(label="⚠ Connection failed", state="error")
                        st.error(str(_ca_exc))
                        _ca_gr_resp = None

                if _ca_gr_resp:
                    _ca_dr = _ca_gr_resp.get("deduction_result", _ca_gr_resp)
                    _ca_driv = _ca_dr.get("driving_factor") or _ca_dr.get("mechanism_summary") or "(No driving factor)"
                    _ca_conf = float(_ca_dr.get("confidence") or 0.5)

                    st.subheader("Grounded Result")
                    _cg1, _cg2 = st.columns(2)
                    with _cg1:
                        st.metric("Confidence", f"{int(_ca_conf * 100)}%")
                    with _cg2:
                        _ca_logstate = "Converging" if _ca_conf >= 0.65 else "Diverging" if _ca_conf >= 0.45 else "Uncertain"
                        st.metric("Logic state", _ca_logstate)

                    st.markdown("**Core driving factor**")
                    st.info(_ca_driv)

                    _ca_vgap = _ca_dr.get("verification_gap", "")
                    if _ca_vgap:
                        st.warning(f"Verification gap: {_ca_vgap}")

                    with st.expander("📋 Full JSON response", expanded=False):
                        st.json(_ca_gr_resp)


# ===========================================================================
# Page: Knowledge
# ===========================================================================
elif page == "Knowledge":
    st.title("🕸 Knowledge Graph Tools")
    st.caption(
        "View and query the Knowledge Graph stored in KuzuDB. "
        "The graph is populated by the intelligence ingestion pipeline. "
        "Use the Cypher query panel to explore entity relationships directly."
    )

    col_graph, col_chat = st.columns([3, 2], gap="large")

    with col_graph:
        st.subheader("🌐 Knowledge Graph View")
        if st.button("🔄 Update Graph", type="primary", key="kg_update"):
            with st.spinner("Ingesting graph data…"):
                _resp = _api.ingest_news()
                st.success("✅ Done" if "error" not in _resp else f"❌ {_resp['error']}")

        _ents = st.session_state.graph_data.get("entities", [])
        _rels = st.session_state.graph_data.get("relations", [])
        _known_ids = {e.get("name", "") for e in _ents if e.get("name")}
        _gdata = {
            "nodes": [{"id": e.get("name",""), "label": str(e.get("type","MISC")).upper(),
                       "properties": e} for e in _ents if e.get("name")],
            "edges": [{"from": r.get("from",""), "to": r.get("to",""), "type": r.get("relation","")}
                      for r in _rels if r.get("from") in _known_ids and r.get("to") in _known_ids],
        }
        st.caption(f"Graph: **{len(_gdata['nodes'])}** nodes · **{len(_gdata['edges'])}** edges")
        render_graph(_gdata)

    with col_chat:
        st.subheader("💬 Cypher Query")
        st.caption("Cypher queries are supported with KuzuDB backend (`GRAPH_BACKEND=kuzu`).")
        _default_cypher = "MATCH (e:Entity) RETURN e.name, e.type LIMIT 10"
        _cypher_input = st.text_area(
            "Cypher query", value=_default_cypher, height=100,
            key="kg_cypher_input_main", placeholder=_default_cypher,
        )
        _c1, _c2 = st.columns([1, 1])
        with _c1:
            _run_query = st.button("▶ Run Query", type="primary", key="kg_run_query_main")
        with _c2:
            if st.button("🗑️ Clear history", key="kg_clear_history"):
                st.session_state.kg_chat_history = []
                st.rerun()

        if _run_query:
            _q = (_cypher_input or "").strip()
            if not _q:
                st.warning("⚠️ Please enter a Cypher query.")
            else:
                with st.spinner("⏳ Running…"):
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
                    st.success(f"✅ {len(_results)} results")
                    try:
                        import pandas as pd
                        st.dataframe(pd.DataFrame(_results), use_container_width=True, height=200)
                    except Exception:
                        st.json(_results)
                else:
                    st.info("Query succeeded but returned no results.")
            st.markdown("---")

    st.divider()

    # Detail tabs
    tab_entities, tab_relations, tab_neighbours, tab_diagnostic = st.tabs([
        "📋 Entity List", "🔗 Relation List", "🔍 Neighbour Query", "🧮 Cartesian Diagnostic"
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
                st.info("📭 No entities in the graph. Click **Update Graph** to ingest data first.")

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
                st.info("📭 No relations in the graph. Ingest data first.")

    with tab_neighbours:
        entity_query = st.text_input("Entity name", placeholder="e.g. Federal Reserve")
        if entity_query:
            nbr_resp = _api.get_kg_neighbours(entity_query)
            if "error" in nbr_resp:
                st.error(f"❌ {nbr_resp['error']}")
            else:
                neighbours: List[Dict[str, Any]] = nbr_resp.get("neighbours", [])
                if neighbours:
                    st.success(f"Found {len(neighbours)} neighbour nodes")
                    try:
                        import pandas as pd
                        st.dataframe(pd.DataFrame(neighbours), use_container_width=True)
                    except ImportError:
                        for n in neighbours:
                            st.write(f"→ **{n.get('name')}** ({n.get('type')}) via [{n.get('relation')}]")

    # ── Cartesian Diagnostic Tab ────────────────────────────────────────────
    with tab_diagnostic:
        st.markdown("### 🧮 Cartesian Dynamic Pattern Diagnostic")
        st.caption(
            "Enter a triple (source entity type, relation type, target entity type) "
            "to query the pattern library for matching dynamic patterns, typical outcomes, and prior confidence."
        )

        try:
            from ontology.relation_schema import (  # type: ignore
                EntityType, RelationType,
                generate_diagnostic_report, CARTESIAN_PATTERN_REGISTRY,
            )
            _schema_available = True
        except ImportError:
            _schema_available = False
            st.info(
                "🔌 Connect to a running backend to use this feature.\n\n"
                "The Cartesian Diagnostic requires the backend ontology module. "
                "To run locally: `cd backend && uvicorn app.main:app --port 8000`"
            )

        if _schema_available:
            _e_types = [e.value for e in EntityType]
            _r_types = [r.value for r in RelationType]

            col_d1, col_d2, col_d3 = st.columns(3)
            with col_d1:
                _d_src = st.selectbox(
                    "🔵 Source entity type", _e_types,
                    index=_e_types.index("state") if "state" in _e_types else 0,
                    key="diag_src",
                )
            with col_d2:
                _d_rel = st.selectbox(
                    "⚡ Relation type", _r_types,
                    index=_r_types.index("sanction") if "sanction" in _r_types else 0,
                    key="diag_rel",
                )
            with col_d3:
                _d_tgt = st.selectbox(
                    "🔴 Target entity type", _e_types,
                    index=_e_types.index("state") if "state" in _e_types else 0,
                    key="diag_tgt",
                )

            if st.button("🧮 Run Cartesian Diagnostic", type="primary", key="run_diag"):
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
                        f"**Triple:** `{_rpt.input_triple[0]}` × `{_rpt.input_triple[1]}` × `{_rpt.input_triple[2]}`"
                    )
                    _cp = _rpt.confidence_prior
                    st.markdown(f"**Prior confidence:** {_cp:.0%}")
                    st.markdown(
                        f'<div class="conf-bar-wrap"><div class="conf-bar" style="width:{int(_cp*100)}%"></div></div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown('<div class="elite-divider"></div>', unsafe_allow_html=True)
                    st.markdown("**📋 Typical outcomes (descending probability)**")
                    st.markdown(
                        " ".join(f'<span class="outcome-pill">{o}</span>' for o in _rpt.typical_outcomes),
                        unsafe_allow_html=True,
                    )
                    st.markdown('<div class="elite-divider"></div>', unsafe_allow_html=True)
                    c_comp, c_inv = st.columns(2)
                    with c_comp:
                        st.markdown("**🔗 Higher-order composition effects**")
                        if _rpt.composition_chain:
                            for hint in _rpt.composition_chain:
                                st.markdown(f"- `{hint}`")
                        else:
                            st.caption("No composition records")
                    with c_inv:
                        st.markdown("**↩️ Inverse dynamic pattern (group-theory inverse)**")
                        if _rpt.inverse_pattern:
                            st.markdown(f"`{_rpt.inverse_pattern}`")
                            st.caption("When the inverse pattern activates, outcomes of the current pattern are reversed.")
                        else:
                            st.caption("No inverse pattern defined")
                else:
                    st.warning("No exact match. Showing fuzzy matches:")
                    for (src, rel, tgt), pat, score in _rpt.fuzzy_matches:
                        with st.expander(f"Fuzzy match: {pat.pattern_name} (score={score:.2f})", expanded=False):
                            st.write(f"**Triple:** {src.value} × {rel.value} × {tgt.value}")
                            st.write(f"**Domain:** {pat.domain}")
                            for o in pat.typical_outcomes:
                                st.write(f"  - {o}")

                st.markdown(f'<div class="diag-note">📝 {_rpt.diagnostic_note}</div>', unsafe_allow_html=True)

            st.markdown('<div class="elite-divider"></div>', unsafe_allow_html=True)
            with st.expander("📚 Full Pattern Library", expanded=False):
                try:
                    import pandas as pd
                    _df_pats = pd.DataFrame([
                        {"src": k[0].value, "relation": k[1].value, "tgt": k[2].value,
                         "pattern_name": v.pattern_name, "domain": v.domain,
                         "mechanism_class": v.mechanism_class, "prior_confidence": f"{v.confidence_prior:.0%}"}
                        for k, v in CARTESIAN_PATTERN_REGISTRY.items()
                    ])
                    st.dataframe(_df_pats, use_container_width=True, height=400)
                except ImportError:
                    for (src, rel, tgt), pat in CARTESIAN_PATTERN_REGISTRY.items():
                        st.write(f"**{pat.pattern_name}** — {src.value} × {rel.value} × {tgt.value}")

            with st.expander("💡 How the Cartesian Diagnostic integrates with the reasoning pipeline", expanded=False):
                st.markdown("""
                **Integration flow:**
                1. `analysis_service.perform_deduction` extracts a `MechanismLabel` list
                2. `relation_schema.enrich_mechanism_labels_with_patterns()` queries the pattern library for each label
                3. `build_pattern_context_for_prompt()` generates a "prior outcomes" fragment injected into the LLM prompt
                4. The LLM is constrained to choose from "typical outcomes" rather than generating freely

                **Group-theory analogy (long-term direction):**
                - Current: E × R × E → DynamicPattern (finite set mapping)
                - Next: Define a "composition law" for Patterns: Pattern_A ∘ Pattern_B = Pattern_C
                - Long-term: Introduce Lie group continuous symmetry to describe pattern manifold evolution over time
                """)



# ===========================================================================
# Page: Audit
# ===========================================================================
elif page == "Audit":
    st.title("🔮 Ontological Forecast")
    st.caption(
        "Forward simulation of ontological trajectories. Starting from a named relationship or scenario, "
        "the engine performs algebraic iteration over the finite semi-group defined by the composition table, "
        "converging to attractors (algebraic fixed points). Confidence decays as 0.85^t per step."
    )

    _fc_tab_scenarios, _fc_tab_relationship, _fc_tab_custom, _fc_tab_attractors = st.tabs([
        "📋 Preset Scenarios", "🔗 Relationship Forecast", "✏️ Custom Forecast", "🎯 Attractors"
    ])

    with _fc_tab_scenarios:
        st.markdown("#### 📋 Preset Geopolitical Scenarios")
        st.caption("Select a pre-defined scenario to run a forward simulation.")
        _fc_scenarios_resp = _api._get("/analysis/forecast/scenarios")
        if "error" in _fc_scenarios_resp:
            st.warning(f"Forecast backend unavailable: {_fc_scenarios_resp.get('error')}")
            st.info("Start the backend with forecast routes enabled.")
        else:
            _fc_scenarios = _fc_scenarios_resp.get("scenarios", [])
            if not _fc_scenarios:
                st.info("No preset scenarios available.")
            for _sc in _fc_scenarios:
                _sc_id   = _sc.get("id", "")
                _sc_name = _sc.get("name", _sc_id)
                _sc_desc = _sc.get("description", "")
                _sc_pats = _sc.get("initial_patterns", [])
                with st.expander(f"**{_sc_name}**", expanded=False):
                    st.caption(_sc_desc)
                    st.caption(f"Initial patterns: {', '.join(_sc_pats)}")
                    _fc_horizon = st.slider(
                        "Horizon (steps)", 1, 12, 6,
                        key=f"fc_horizon_{_sc_id}"
                    )
                    if st.button(f"▶ Run Forecast", key=f"fc_run_{_sc_id}"):
                        with st.spinner("Running forward simulation…"):
                            _fc_result = _api._post(
                                "/analysis/forecast/relationship",
                                json={"scenario_id": _sc_id, "horizon_steps": _fc_horizon}
                            )
                            if "error" in _fc_result:
                                st.error(_fc_result["error"])
                            else:
                                st.session_state[f"fc_result_{_sc_id}"] = _fc_result

                    _fc_res = st.session_state.get(f"fc_result_{_sc_id}")
                    if _fc_res:
                        _fc_attractor = _fc_res.get("primary_attractor") or {}
                        _fc_narrative = _fc_res.get("forecast_narrative", "")
                        _fc_confidence = _fc_attractor.get("final_probability", 0)
                        _fc_steps = _fc_res.get("simulation_steps", [])
                        _fc_bifur = _fc_res.get("bifurcation_points", [])

                        st.markdown(f"**Primary Attractor:** `{_fc_attractor.get('name', 'unknown')}`")
                        st.metric("Final Confidence (0.85^t decay)", f"{_fc_confidence:.1%}")

                        if _fc_narrative:
                            st.info(_fc_narrative)

                        if _fc_steps:
                            st.markdown("**Simulation Steps:**")
                            for _step in _fc_steps:
                                _sn = _step.get("step", "?")
                                _sp = _step.get("active_patterns", [])
                                _sv = _step.get("state_vector", {})
                                _sc_conf = _step.get("confidence", 0)
                                st.markdown(
                                    f'<div style="border-left:3px solid #1565C0;padding:4px 10px;'
                                    f'margin-bottom:4px;background:#E3F2FD;font-size:12px;">'
                                    f'<b>Step {_sn}</b> (conf={_sc_conf:.0%}) — {", ".join(_sp[:3])}'
                                    f'</div>',
                                    unsafe_allow_html=True,
                                )

                        if _fc_bifur:
                            st.warning(f"⚡ Bifurcation points at steps: {_fc_bifur}")

    with _fc_tab_relationship:
        st.markdown("#### 🔗 Relationship Forecast")
        st.caption(
            "Enter a scenario ID and horizon to run a trajectory simulation. "
            "The engine iterates the composition table until convergence or the horizon is reached."
        )
        _fc_rel_col1, _fc_rel_col2 = st.columns([3, 1])
        with _fc_rel_col1:
            _fc_rel_scenario = st.text_input(
                "Scenario ID", value="us_china_tech_decoupling",
                key="fc_rel_scenario",
                help="Use an ID from the Preset Scenarios tab, e.g. us_china_tech_decoupling"
            )
        with _fc_rel_col2:
            _fc_rel_horizon = st.number_input("Steps", 1, 15, 6, key="fc_rel_horizon")

        _fc_extra_pats = st.text_input(
            "Extra patterns (comma-separated, optional)", value="",
            key="fc_rel_extra"
        )

        if st.button("▶ Run Relationship Forecast", type="primary", key="fc_rel_run"):
            _extra = [p.strip() for p in _fc_extra_pats.split(",") if p.strip()]
            with st.spinner("Running forward simulation…"):
                _fc_rel_result = _api._post(
                    "/analysis/forecast/relationship",
                    json={"scenario_id": _fc_rel_scenario, "horizon_steps": _fc_rel_horizon, "extra_patterns": _extra}
                )
                st.session_state["fc_rel_result"] = _fc_rel_result

        _fc_rel_res = st.session_state.get("fc_rel_result")
        if _fc_rel_res:
            if "error" in _fc_rel_res:
                st.error(_fc_rel_res["error"])
            else:
                st.json(_fc_rel_res)

    with _fc_tab_custom:
        st.markdown("#### ✏️ Custom Pattern Forecast")
        st.caption("Specify initial patterns directly to run a custom forward simulation.")
        _fc_custom_pats = st.text_area(
            "Initial patterns (one per line)",
            value="",
            key="fc_custom_pats",
            help="Enter pattern names, one per line. These will be the starting state of the simulation."
        )
        _fc_custom_horizon = st.slider("Horizon (steps)", 1, 12, 6, key="fc_custom_horizon")

        if st.button("▶ Run Custom Forecast", type="primary", key="fc_custom_run"):
            _custom_pats = [p.strip() for p in _fc_custom_pats.split("\n") if p.strip()]
            if not _custom_pats:
                st.warning("Please enter at least one initial pattern.")
            else:
                with st.spinner("Running custom forward simulation…"):
                    _fc_custom_result = _api._post(
                        "/analysis/forecast/custom",
                        json={"initial_patterns": _custom_pats, "horizon_steps": _fc_custom_horizon}
                    )
                    st.session_state["fc_custom_result"] = _fc_custom_result

        _fc_cust_res = st.session_state.get("fc_custom_result")
        if _fc_cust_res:
            if "error" in _fc_cust_res:
                st.error(_fc_cust_res["error"])
            else:
                st.json(_fc_cust_res)

    with _fc_tab_attractors:
        st.markdown("#### 🎯 Known Attractors")
        st.caption(
            "Attractors are the algebraic fixed points of the composition semi-group. "
            "An element P is an attractor if compose(P, P) = P (idempotent). "
            "These represent stable terminal states of the ontological system."
        )
        _fc_domain = st.selectbox(
            "Domain filter",
            options=["all", "geopolitics", "economics", "technology", "military"],
            key="fc_attractor_domain"
        )
        if st.button("🔍 Find Attractors", key="fc_attractor_run"):
            _domain_param = "" if _fc_domain == "all" else f"?domain={_fc_domain}"
            _fc_attr_resp = _api._get(f"/analysis/forecast/attractors{_domain_param}")
            st.session_state["fc_attractors"] = _fc_attr_resp

        _fc_attrs = st.session_state.get("fc_attractors")
        if _fc_attrs:
            if "error" in _fc_attrs:
                st.error(_fc_attrs["error"])
            else:
                _attr_list = _fc_attrs.get("attractors", [])
                if not _attr_list:
                    st.info("No attractors found for the selected domain.")
                for _attr in _attr_list:
                    _attr_name = _attr.get("name", "")
                    _attr_domain = _attr.get("domain", "")
                    _attr_prob = _attr.get("probability", 0)
                    _attr_desc = _attr.get("description", "")
                    st.markdown(
                        f'<div style="border-left:4px solid #D4AF37;padding:8px 12px;'
                        f'margin-bottom:8px;background:#FFFDE7;border-radius:4px;">'
                        f'<b>{_attr_name}</b>'
                        f'&nbsp;<span style="font-size:11px;color:#888">domain={_attr_domain}</span>'
                        f'&nbsp;<span style="font-size:11px;color:#555">p={_attr_prob:.0%}</span>'
                        f'<div style="font-size:12px;color:#555;margin-top:4px">{_attr_desc}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
