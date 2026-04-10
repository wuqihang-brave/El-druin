"""
EL'druin Intelligence Platform – Streamlit Frontend v2
=======================================================

v2 features:
  1. Dashboard: landing page with navigation cards (Assessments, Streams, Knowledge)
  2. Evidence Streams: each article has a quick assessment shortcut button
  3. Knowledge Graph: includes Cartesian Pattern Diagnostic tab
  4. Assessments: fully rendered in pages/2_Assessments.py
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


def _domain_class(domain: str) -> str:
    return {"geopolitics": "domain-geo", "economics": "domain-econ",
            "technology": "domain-tech", "military": "domain-mil"}.get(domain.lower(), "")


# ===========================================================================
# Page: Dashboard
# ===========================================================================
if page == "Dashboard":
    st.markdown(
        """
        <div style="padding:24px 0 8px 0;">
            <h2 style="color:#4A8FD4;margin:0 0 4px 0;font-size:1.6rem;letter-spacing:0.5px;">
                EL'DRUIN Intelligence Platform
            </h2>
            <p style="color:#7A8FA6;font-size:0.85rem;margin:0;">
                Structural forecast and intelligence analysis
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="elite-divider"></div>', unsafe_allow_html=True)

    _dash_col1, _dash_col2, _dash_col3 = st.columns(3, gap="medium")

    with _dash_col1:
        st.markdown(
            """
            <div style="background:var(--surface,#162030);border:1px solid var(--border,#2D3F52);
            border-left:3px solid #4A8FD4;border-radius:3px;padding:18px 16px;">
                <div style="font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;
                color:#4A8FD4;margin-bottom:8px">Assessments</div>
                <div style="font-size:13px;color:#C8D8E8;line-height:1.55;">
                    Compose structural forecasts, explore scenario stacks, and
                    review intelligence briefs.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("→ Open Assessments", key="dash_goto_assessments", use_container_width=True):
            st.session_state.current_page = "Assessments"
            st.switch_page("pages/2_Assessments.py")

    with _dash_col2:
        st.markdown(
            """
            <div style="background:var(--surface,#162030);border:1px solid var(--border,#2D3F52);
            border-left:3px solid #C8A84B;border-radius:3px;padding:18px 16px;">
                <div style="font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;
                color:#C8A84B;margin-bottom:8px">Evidence Streams</div>
                <div style="font-size:13px;color:#C8D8E8;line-height:1.55;">
                    Monitor live intelligence feeds, ingest articles, and
                    route evidence to the knowledge graph.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("→ Open Streams", key="dash_goto_streams", use_container_width=True):
            st.session_state.current_page = "Streams"
            st.rerun()

    with _dash_col3:
        st.markdown(
            """
            <div style="background:var(--surface,#162030);border:1px solid var(--border,#2D3F52);
            border-left:3px solid #4CAF72;border-radius:3px;padding:18px 16px;">
                <div style="font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;
                color:#4CAF72;margin-bottom:8px">Knowledge Graph</div>
                <div style="font-size:13px;color:#C8D8E8;line-height:1.55;">
                    Query the entity-relationship graph, explore object provenance,
                    and audit ingestion results.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("→ Open Knowledge", key="dash_goto_knowledge", use_container_width=True):
            st.session_state.current_page = "Knowledge"
            st.rerun()


# ===========================================================================
# Page: Streams
# ===========================================================================
elif page == "Streams":
    st.markdown("""
<div style="margin-bottom:2px">
    <span style="font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;
    color:var(--muted,#7A8FA6)">EVIDENCE INTAKE — INTELLIGENCE STREAMS</span>
</div>
""", unsafe_allow_html=True)
    st.markdown("## Streams Monitor")
    st.caption(
        "Incoming evidence is automatically classified by domain and assessed for signal quality. "
        "Attach articles to an active assessment or route directly to the Dashboard for full analysis."
    )

    # ── Compact filter bar ────────────────────────────────────────────────────
    _sf_col1, _sf_col2, _sf_col3, _sf_col4 = st.columns([4, 1, 1, 1])
    with _sf_col1:
        search_query = st.text_input(
            "Search", placeholder="🔍 Filter by keyword…", label_visibility="collapsed",
            key="streams_search",
        )
    with _sf_col2:
        hours = st.number_input(
            "Hours", min_value=1, max_value=168, value=24, step=1,
            label_visibility="collapsed", key="streams_hours",
            help="Time range in hours",
        )
    with _sf_col3:
        limit = st.number_input(
            "Limit", min_value=5, max_value=100, value=20, step=5,
            label_visibility="collapsed", key="streams_limit",
            help="Max articles to display",
        )
    with _sf_col4:
        if st.button("Refresh", key="refresh_news", use_container_width=True):
            with st.spinner("📡 Aggregating news…"):
                result = _api.ingest_news()
                if "error" not in result:
                    st.success("✅ Aggregation complete!")
                else:
                    st.error(f"❌ Error: {result['error']}")

    if search_query:
        data = _api.search_news(search_query, limit=int(limit))
    else:
        data = _api.get_latest_news(limit=int(limit), hours=int(hours))

    if "error" in data:
        st.warning(
            "⚠️ Backend is currently unavailable. Intelligence Streams requires a running backend.\n\n"
            "To run locally: `cd backend && uvicorn app.main:app --port 8000`"
        )
        if st.button("🔄 Retry", key="feed_retry"):
            st.rerun()
    else:
        articles: List[Dict[str, Any]] = data.get("articles", [])
        if search_query:
            st.info(f"🔍 Found {len(articles)} results")

        import hashlib as _hashlib

        # Domain auto-tag mapping based on category field
        _DOMAIN_TAG_MAP: Dict[str, str] = {
            "geopolitics": "GEOPOLITICS",
            "geopolitical": "GEOPOLITICS",
            "military": "MILITARY",
            "defense": "MILITARY",
            "defence": "MILITARY",
            "economic": "ECONOMIC",
            "economics": "ECONOMIC",
            "finance": "ECONOMIC",
            "financial": "ECONOMIC",
            "technology": "TECHNOLOGY",
            "tech": "TECHNOLOGY",
            "science": "TECHNOLOGY",
        }

        def _domain_tag(article: Dict[str, Any]) -> str:
            _cat = (article.get("category") or "").lower()
            for _key, _label in _DOMAIN_TAG_MAP.items():
                if _key in _cat:
                    return _label
            return "GENERAL"

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Articles", len(articles))
        m2.metric("Categories", len({a.get("category", "?") for a in articles}))
        m3.metric("Sources", len({a.get("source", "?") for a in articles}))
        m4.metric("Time Range", f"{int(hours)} h")

        _domains_found: Dict[str, int] = {}
        for _a in articles:
            _d = _domain_tag(_a)
            _domains_found[_d] = _domains_found.get(_d, 0) + 1

        # Signal quality strip
        _sq_col1, _sq_col2 = st.columns([3, 2])
        with _sq_col1:
            st.markdown(
                '<div style="font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;'
                'color:var(--muted,#7A8FA6);margin-bottom:8px">DOMAIN DISTRIBUTION</div>',
                unsafe_allow_html=True,
            )
            _domain_colors = {
                "GEOPOLITICS": "#C8A84B",
                "MILITARY":    "#E05050",
                "ECONOMIC":    "#4CAF72",
                "TECHNOLOGY":  "#4A8FD4",
                "GENERAL":     "#7A8FA6",
            }
            for _dn, _dc in _domains_found.items():
                _dcolor = _domain_colors.get(_dn, "#7A8FA6")
                _dpct = _dc / max(len(articles), 1)
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">'
                    f'<span style="font-size:11px;color:{_dcolor};min-width:100px">{_dn}</span>'
                    f'<div style="flex:1;background:var(--surface,#162030);border-radius:2px;height:6px;">'
                    f'<div style="background:{_dcolor};width:{int(_dpct*100)}%;height:6px;border-radius:2px;"></div>'
                    f'</div>'
                    f'<span style="font-size:11px;color:var(--muted,#7A8FA6);min-width:20px;text-align:right">{_dc}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        with _sq_col2:
            st.markdown(
                '<div style="font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;'
                'color:var(--muted,#7A8FA6);margin-bottom:8px">INTAKE STATUS</div>',
                unsafe_allow_html=True,
            )
            _high_signal = sum(1 for _a in articles if len(_a.get("description") or "") > 100)
            _low_signal  = len(articles) - _high_signal
            st.markdown(
                f'<div style="background:var(--surface,#162030);border:1px solid var(--border,#2D3F52);'
                f'border-radius:3px;padding:10px 12px;">'
                f'<div style="font-size:12px;color:var(--text-strong,#EDF2F7);font-weight:600;margin-bottom:4px">'
                f'High signal: <span style="color:#4CAF72">{_high_signal}</span></div>'
                f'<div style="font-size:12px;color:var(--text,#D4DDE6);">'
                f'Low signal: <span style="color:var(--muted,#7A8FA6)">{_low_signal}</span></div>'
                f'<div style="font-size:10px;color:var(--muted,#7A8FA6);margin-top:6px">'
                f'Signal = description length > 100 chars</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.divider()

        _all_domains = sorted(set(_domain_tag(a) for a in articles))
        _selected_domain = st.selectbox(
            "Filter by domain",
            options=["All"] + _all_domains,
            index=0,
            key="streams_domain_filter",
            label_visibility="collapsed",
        )
        _display_articles = articles
        if _selected_domain != "All":
            _display_articles = [a for a in articles if _domain_tag(a) == _selected_domain]

        if not articles:
            st.info("No articles found. Adjust filters or refresh.")

        for i, article in enumerate(_display_articles, 1):
            title_preview = (article.get("title") or "(no title)")[:100]
            _key_src   = (article.get("link") or article.get("title") or str(i)).encode("utf-8", errors="replace")
            _cache_key = f"kg_{_hashlib.md5(_key_src).hexdigest()}"
            _src_name  = article.get("source") or "Unknown"
            _pub_date  = str(article.get("published", ""))[:10]
            _dom_tag   = _domain_tag(article)
            _kg_done   = _cache_key in st.session_state.kg_cache

            with st.expander(f"[{i}] {title_preview}", expanded=False):
                _ic1, _ic2, _ic3, _ic4 = st.columns([2, 2, 2, 1])
                with _ic1:
                    st.markdown(
                        f'<span style="background:var(--tag-bg,#1A2D42);color:var(--text,#D4DDE6);'
                        f'font-size:10px;font-weight:700;padding:2px 7px;border-radius:2px;'
                        f'border:1px solid var(--border,#2D3F52)">{_src_name}</span>',
                        unsafe_allow_html=True,
                    )
                with _ic2:
                    st.markdown(
                        f'<span style="background:var(--tag-bg,#1A2D42);color:var(--blue-accent,#4A8FD4);'
                        f'font-size:10px;font-weight:700;padding:2px 7px;border-radius:2px;'
                        f'border:1px solid var(--border,#2D3F52)">{_dom_tag}</span>',
                        unsafe_allow_html=True,
                    )
                with _ic3:
                    st.caption(f"{_pub_date}" if _pub_date else "N/A")
                with _ic4:
                    if _kg_done:
                        st.markdown(
                            '<span style="color:var(--gold,#C8A84B);font-size:10px">● attached</span>',
                            unsafe_allow_html=True,
                        )

                st.write(article.get("description") or "(no summary)")
                _desc_len = len(article.get("description") or "")
                _has_link = bool(article.get("link"))
                _signal_label = "High" if _desc_len > 100 else "Low"
                _signal_color = "#4CAF72" if _desc_len > 100 else "#7A8FA6"
                st.markdown(
                    f'<div style="font-size:10px;color:var(--muted,#7A8FA6);margin-top:4px;margin-bottom:6px;">'
                    f'Signal quality: <span style="color:{_signal_color};font-weight:700">{_signal_label}</span>'
                    f' &nbsp;·&nbsp; Description: {_desc_len} chars'
                    + (f' &nbsp;·&nbsp; <a href="{article["link"]}" target="_blank" style="color:#4A8FD4">Source →</a>' if _has_link else '')
                    + f'</div>',
                    unsafe_allow_html=True,
                )

                _btn_c1, _btn_c2 = st.columns(2)
                # Run Assessment button
                with _btn_c1:
                    if st.button("▶ Run Assessment", key=f"news_deduce_{i}", type="primary"):
                        st.session_state.selected_news    = article
                        st.session_state.deduction_result = None
                        st.session_state.evented_result   = None
                        st.session_state.current_page     = "Assessments"
                        st.switch_page("pages/2_Assessments.py")

                # Attach to Assessment (KG extraction)
                with _btn_c2:
                    _attach_lbl = "✅ Attached" if _kg_done else "🔬 Attach to Assessment"
                    if st.button(_attach_lbl, key=f"kg_btn_{i}"):
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
                        f"KG Result (entities: {len(_entities_kg)}, relations: {len(_relations_kg)})",
                        expanded=True,
                    ):
                        if _entities_kg:
                            st.write("**Entities**")
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
                            st.write("**Relations**")
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
# Page: Knowledge
# ===========================================================================
elif page == "Knowledge":
    st.title("Knowledge")
    st.caption(
        "View and query the Knowledge Graph stored in KuzuDB. "
        "The graph is populated by the intelligence ingestion pipeline. "
        "Use the Cypher query panel to explore entity relationships directly."
    )

    col_graph, col_chat = st.columns([3, 2], gap="large")

    with col_graph:
        st.subheader("Entity Network")
        if st.button("Refresh Knowledge Graph", type="primary", key="kg_update"):
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
        st.subheader("Advanced Query")
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
                f"<div style='background:var(--surface-raised,#1E2D3D);border:1px solid var(--border,#2D3F52);border-radius:4px;"
                f"padding:8px 12px;margin-bottom:4px;font-family:monospace;font-size:13px;"
                f"color:var(--muted,#7A8FA6)'>{_item['query']}</div>",
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
        "Entity List", "Relation List", "Neighbour Query", "Structural Diagnostic"
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
                st.info("No entities in the graph. Click **Refresh Knowledge Graph** to ingest data first.")

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
        st.markdown("### Evaluate Structural Impact")
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

            if st.button("Evaluate Structural Impact", type="primary", key="run_diag"):
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
# Page: Audit  (Model Audit – visible when FEATURE_EXPERIMENTAL=true)
# ===========================================================================
elif page == "Audit":
    _experimental_enabled = os.environ.get("FEATURE_EXPERIMENTAL", "").lower() in ("1", "true", "yes")

    st.title("Audit")
    st.caption(
        "Model Audit — inspect reasoning chain integrity, credibility scores, "
        "and attractor-state consistency across recent assessments."
    )

    if not _experimental_enabled:
        st.info(
            "The Audit workspace is currently restricted. "
            "Set the `FEATURE_EXPERIMENTAL=true` environment variable to enable full audit capabilities."
        )
        st.markdown("---")
        st.markdown("**Available audit summaries**")

    # ── Recent assessments audit log ──────────────────────────────────────
    _audit_resp = _api._get("/intelligence/audit/recent") if hasattr(_api, "_get") else {"error": "unavailable"}
    if "error" not in _audit_resp:
        _audit_entries = _audit_resp.get("entries", [])
        if _audit_entries:
            try:
                import pandas as pd
                st.dataframe(pd.DataFrame(_audit_entries), use_container_width=True, height=400)
            except ImportError:
                for _entry in _audit_entries:
                    st.write(_entry)
        else:
            st.info("No audit entries found. Run assessments from the Dashboard to populate the audit log.")
    else:
        st.info(
            "Audit log requires a running backend. "
            "Start the backend and run assessments to populate this view.\n\n"
            "To run locally: `cd backend && uvicorn app.main:app --port 8000`"
        )

    if _experimental_enabled:
        st.markdown("---")
        st.markdown("### Structural Integrity Checks")
        st.caption("Advanced diagnostic tools for model validation — experimental.")

        _int_col1, _int_col2 = st.columns(2)
        with _int_col1:
            st.markdown("**Credibility Score Distribution**")
            st.caption("Verifiability, KG consistency, and overall credibility across recent assessments.")
        with _int_col2:
            st.markdown("**Hypothesis Ratio Trend**")
            st.caption("Tracks the ratio of supported vs. unsupported hypotheses over time.")
