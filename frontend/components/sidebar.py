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

Navigation note
---------------
``streamlit_option_menu`` is intentionally **not used** for navigation because
its JavaScript component calls ``window.history.pushState()`` on every Streamlit
rerun.  On advanced sub-pages this causes the browser to exceed Chrome/Firefox's
100 pushState-per-10-seconds limit and crashes the page with::

    Bad message format: Attempt to use history.pushState() more than 100 times
    per 10 seconds

Native ``st.radio`` is used instead – it carries no browser-history side-effects.
"""

from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Navigation configuration
# ---------------------------------------------------------------------------

# Labels for pages rendered inline inside app.py
_INLINE_LABELS: list[str] = [
    "Dashboard",
    "Assessments",
    "Streams",
    "Knowledge",
]

_ALL_LABELS: list[str] = _INLINE_LABELS


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
    _current = st.session_state.get("current_page", "Dashboard")
    _default_idx = _ALL_LABELS.index(_current) if _current in _ALL_LABELS else 0

    with st.sidebar:
        # ── Brand header ──────────────────────────────────────────────────
        st.markdown(
            """
            <div style="text-align:center;padding:10px 0 4px 0;">
                <h2 style="color:#0047AB;margin:0 0 2px 0;">EL&#39;DRUIN</h2>
                <p style="color:#606060;font-size:0.78rem;margin:0;">
                    Intelligence Platform
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Navigation menu (native radio – no browser history side-effects) ──
        # CSS to make the radio look like a nav list
        st.markdown(
            """
            <style>
            div[data-testid="stRadio"] > label { display: none; }
            div[data-testid="stRadio"] > div { gap: 0 !important; }
            div[data-testid="stRadio"] > div > label {
                display: flex; align-items: center;
                font-size: 12px; font-weight: 500;
                padding: 9px 16px;
                border-bottom: 1px solid #1E2D3D;
                cursor: pointer; width: 100%;
                background: transparent;
                color: #8DA4B8;
                text-transform: uppercase;
                letter-spacing: 0.8px;
            }
            div[data-testid="stRadio"] > div > label:hover {
                background: #162030;
                color: #C8D8E8;
            }
            div[data-testid="stRadio"] > div > label[data-baseweb="radio"]:has(input:checked) {
                background: transparent !important;
                color: #E2EBF3 !important;
                font-weight: 700;
                border-left: 3px solid #4A8FD4 !important;
                padding-left: 13px !important;
            }
            div[data-testid="stRadio"] > div > label[data-baseweb="radio"]:has(input:checked) * {
                color: #E2EBF3 !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        selected = st.radio(
            "Navigation",
            _ALL_LABELS,
            index=_default_idx,
            key="sidebar_nav_radio",
            label_visibility="collapsed",
        )

        # ── Route inline pages when called from a sub-page ─────────────────
        if is_subpage and selected in _INLINE_LABELS:
            st.session_state.current_page = selected
            st.switch_page("app.py")

        st.markdown("---")

        # ── Analysis Engine section ────────────────────────────────────────
        st.markdown(
            "<p style='font-weight:700;font-size:0.82rem;color:#0047AB;"
            "text-transform:uppercase;letter-spacing:0.6px;margin-bottom:6px'>"
            "ANALYSIS ENGINE</p>",
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
            "Refresh Graph",
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