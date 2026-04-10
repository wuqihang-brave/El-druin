"""
EL'druin Intelligence Platform — Main Entry Point
=================================================
Pure navigation router. All page content lives in pages/.
"""

import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict

from dotenv import load_dotenv
load_dotenv()

import streamlit as st

# ── Path setup ────────────────────────────────────────────────────────────────
_FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _FRONTEND_DIR not in sys.path:
    sys.path.insert(0, _FRONTEND_DIR)

from utils.api_client import APIClient
from components.sidebar import render_sidebar_navigation

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EL-DRUIN Intelligence Platform",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS design tokens (dark intelligence theme) ───────────────────────────────
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
    top: calc(100% + 6px);
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

# ── Backend setup ─────────────────────────────────────────────────────────────
_backend_url_raw = os.environ.get("BACKEND_URL", "")
if not _backend_url_raw:
    st.error("BACKEND_URL is not set.")
    st.stop()
_backend_url = _backend_url_raw.rstrip("/")
_api = APIClient(base_url=_backend_url)

# ── Session state defaults ────────────────────────────────────────────────────
_STATE_DEFAULTS: Dict[str, Any] = {
    "initialized": False,
    "current_page": "Dashboard",
    "selected_entity": "",
    "graph_data": {"entities": [], "relations": [], "status": "not_loaded"},
    "entity_cache": {},
    "last_update": None,
    "nav_state": {},
    "kg_cache": {},
    "kg_chat_history": [],
}
for _k, _v in _STATE_DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── Knowledge Graph loader (shared across pages) ──────────────────────────────
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

# ── Sidebar navigation ────────────────────────────────────────────────────────
page = render_sidebar_navigation()

# ── Page routing ──────────────────────────────────────────────────────────────
if page == "Dashboard":
    st.markdown("## ⚔️ EL'DRUIN Intelligence Platform")
    st.info(
        "**Dashboard** (PR-C) — Structural regime monitoring, trigger amplification, "
        "attractor forecasting, and change feed will be available here once 1_Dashboard.py "
        "is implemented."
    )

elif page == "Streams":
    st.switch_page("pages/4_Streams.py")

elif page == "Knowledge":
    st.switch_page("pages/3_Knowledge.py")

elif page == "Assessments":
    st.switch_page("pages/2_Assessments.py")
