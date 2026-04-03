"""
EL'druin Intelligence Platform – Sidebar Navigation Component
=============================================================

Provides a unified, English-first navigation sidebar with:
  1. Page navigation (inline pages handled by app.py + external pages/ files)
  2. Reasoning engine configuration (Engine, Deep Ontology level, Hypothesis toggle)
  3. Single refresh control

Usage
-----
In ``app.py`` (main script)::

    page = render_sidebar_navigation()

In ``pages/`` files (sub-pages)::

    render_sidebar_navigation(is_subpage=True)
"""

from __future__ import annotations

import streamlit as st

try:
    from streamlit_option_menu import option_menu  # type: ignore[import]
    _OPTION_MENU_AVAILABLE = True
except ImportError:
    _OPTION_MENU_AVAILABLE = False

# ---------------------------------------------------------------------------
# Navigation configuration
# ---------------------------------------------------------------------------

# Labels for pages rendered inline inside app.py
_INLINE_LABELS: list[str] = [
    "🏠 Home",
    "📝 Custom Analysis",
    "📰 Intelligence Feed",
    "🕸 KG Tools",
    "⚙️ System Status",
]

# Pages living in the pages/ directory – (label, bootstrap-icon, relative path from root)
_EXTERNAL_PAGES: list[tuple[str, str, str]] = [
    ("🔍 Object Explorer", "search",          "pages/3_🔍_Object_Explorer.py"),
    ("🔬 Logic Audit",     "binoculars-fill", "pages/5_🔍_Logic_Audit.py"),
    ("🔮 Oracle Lab (Beta)","stars",           "pages/10_🔮_Oracle_Laboratory.py"),
]

_EXTERNAL_LABELS: list[str] = [ep[0] for ep in _EXTERNAL_PAGES]

_ALL_LABELS: list[str] = _INLINE_LABELS + _EXTERNAL_LABELS
_ALL_ICONS: list[str] = [
    "house-fill",      # Home
    "pencil-square",   # Custom Analysis
    "newspaper",       # Intelligence Feed
    "diagram-3-fill",  # KG Tools
    "gear-fill",       # System Status
    "search",          # Object Explorer
    "binoculars-fill", # Logic Audit
    "stars",           # Oracle Lab
]


def render_sidebar_navigation(is_subpage: bool = False) -> str:
    """Render the unified sidebar and return the selected inline-page label.

    Parameters
    ----------
    is_subpage:
        Set to ``True`` when called from a ``pages/`` file.  In that case,
        selecting an inline page will store the target in session state and
        call ``st.switch_page("app.py")`` to navigate back to the main app.

    Returns
    -------
    str
        The selected page label (only meaningful for inline pages when called
        from ``app.py``).  When ``is_subpage=True`` this function may not
        return if ``st.switch_page`` is triggered.
    """
    _current = st.session_state.get("current_page", "🏠 Home")
    _default_idx = _ALL_LABELS.index(_current) if _current in _ALL_LABELS else 0

    with st.sidebar:
        # ── Brand header ──────────────────────────────────────────────────
        st.markdown(
            """
            <div style="text-align:center;padding:10px 0 4px 0;">
                <h2 style="color:#0047AB;margin:0 0 2px 0;">EL&#39;druin</h2>
                <p style="color:#606060;font-size:0.78rem;margin:0;">
                    Ontological Intelligence v1.0
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Navigation menu ────────────────────────────────────────────────
        if _OPTION_MENU_AVAILABLE:
            selected = option_menu(
                menu_title=None,
                options=_ALL_LABELS,
                icons=_ALL_ICONS,
                default_index=_default_idx,
                styles={
                    "container": {
                        "padding": "0!important",
                        "background-color": "#F5F5F5",
                    },
                    "icon": {"color": "#606060", "font-size": "14px"},
                    "nav-link": {
                        "font-size": "13px",
                        "text-align": "left",
                        "margin": "0px",
                        "padding": "8px 14px",
                        "border-bottom": "1px solid #E8E8E8",
                    },
                    "nav-link-selected": {
                        "background-color": "#0047AB",
                        "color": "#FFFFFF",
                    },
                },
            )
        else:
            selected = st.radio(
                "Navigation",
                _ALL_LABELS,
                index=_default_idx,
                label_visibility="collapsed",
            )

        # ── Route to external pages ────────────────────────────────────────
        for label, _, path in _EXTERNAL_PAGES:
            if selected == label:
                st.session_state.current_page = selected
                st.switch_page(path)

        # ── Route inline pages when called from a sub-page ─────────────────
        if is_subpage and selected in _INLINE_LABELS:
            st.session_state.current_page = selected
            st.switch_page("app.py")

        st.markdown("---")

        # ── Reasoning Engine section ───────────────────────────────────────
        st.markdown(
            "<p style='font-weight:700;font-size:0.82rem;color:#0047AB;"
            "text-transform:uppercase;letter-spacing:0.6px;margin-bottom:6px'>"
            "🧠 Reasoning Engine</p>",
            unsafe_allow_html=True,
        )

        st.radio(
            "Engine",
            options=["Evented", "Grounded"],
            index=0,
            horizontal=True,
            key="cfg_engine",
            help=(
                "**Evented** – event-based three-stage pipeline "
                "(recommended; works without a Knowledge Graph).\n\n"
                "**Grounded** – knowledge-graph-grounded reasoning "
                "(requires a populated KuzuDB)."
            ),
            label_visibility="collapsed",
        )
        if st.session_state.get("cfg_engine") == "Grounded":
            st.caption("⚠️ Grounded requires a non-empty Knowledge Graph.")

        st.markdown(
            "<p style='font-size:0.78rem;color:#444;margin:8px 0 2px 0'>"
            "Deep Ontology Level</p>",
            unsafe_allow_html=True,
        )
        st.slider(
            "Deep level",
            min_value=0,
            max_value=3,
            value=st.session_state.get("cfg_deep_level", 0),
            key="cfg_deep_level",
            help=(
                "0 = Normal  ·  1 = Local metadata enrichment  ·  "
                "2 = + Fetch source URL  ·  3 = + Web search"
            ),
            label_visibility="collapsed",
        )
        _level_desc = {0: "Normal", 1: "Local metadata", 2: "+ Fetch source", 3: "+ Web search"}
        st.caption(
            f"Mode: **{_level_desc.get(st.session_state.get('cfg_deep_level', 0), 'Normal')}**"
        )

        st.toggle(
            "Show hypothesis path (hidden variables)",
            value=True,
            key="cfg_show_hidden",
            help="Display the T1 hypothesis path in the Evented conclusion panel.",
        )

        st.markdown("---")

        # ── Refresh control ───────────────────────────────────────────────
        if st.button(
            "🔄 Refresh Knowledge Graph",
            use_container_width=True,
            key="sidebar_kg_refresh",
        ):
            st.session_state.graph_data = {
                "entities": [], "relations": [], "status": "not_loaded"
            }
            st.session_state["_kg_cache_clear"] = True
            st.rerun()

    st.session_state.current_page = selected
    return selected