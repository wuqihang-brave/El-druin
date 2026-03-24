"""
EL'druin Intelligence Platform – Sidebar Navigation Component
=============================================================

Provides an interactive sidebar navigation menu using streamlit-option-menu.
Replaces static ``st.sidebar.markdown`` placeholders with real clickable controls.
"""

from __future__ import annotations

import streamlit as st

try:
    from streamlit_option_menu import option_menu  # type: ignore[import]

    _OPTION_MENU_AVAILABLE = True
except ImportError:
    _OPTION_MENU_AVAILABLE = False


# Ordered list of navigation pages: (label, bootstrap-icon)
_NAV_ITEMS: list[tuple[str, str]] = [
    ("🏠 主页", "house-fill"),
    ("📰 实时新闻", "newspaper"),
    ("🔍 事件监控", "search"),
    ("🕸️ 知识图谱", "diagram-3-fill"),
    ("📊 仪表板", "bar-chart-fill"),
    ("⚙️ 系统状态", "gear-fill"),
]

_LABELS = [item[0] for item in _NAV_ITEMS]
_ICONS = [item[1] for item in _NAV_ITEMS]


def render_sidebar_navigation() -> str:
    """Render the interactive sidebar navigation and return the selected page key.

    Uses ``streamlit_option_menu`` when available, and falls back to
    ``st.sidebar.radio`` so the app remains functional even if the package
    has not been installed yet.

    The selected page is also stored in ``st.session_state.current_page``.
    """

    # ── Header ────────────────────────────────────────────────────────────────
    st.sidebar.markdown(
        """
        <div style="text-align:center;padding:12px 0 8px 0;">
            <span style="font-size:2rem;">🧠</span>
            <h3 style="color:#d4af37;margin:4px 0 2px 0;font-size:1.1rem;">EL'druin</h3>
            <p style="color:#aaa;font-size:0.78rem;margin:0;">Intelligence Platform</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.markdown("---")

    # ── Initialise session state ───────────────────────────────────────────
    if "current_page" not in st.session_state:
        st.session_state.current_page = _LABELS[0]

    # Determine the default index from the current session state
    try:
        default_index = _LABELS.index(st.session_state.current_page)
    except ValueError:
        default_index = 0

    # ── Navigation menu ───────────────────────────────────────────────────────
    if _OPTION_MENU_AVAILABLE:
        with st.sidebar:
            selected_label = option_menu(
                menu_title=None,
                options=_LABELS,
                icons=_ICONS,
                default_index=default_index,
                orientation="vertical",
                styles={
                    "container": {
                        "padding": "0 !important",
                        "background-color": "#0d1b2a",
                    },
                    "icon": {"color": "#d4af37", "font-size": "16px"},
                    "nav-link": {
                        "color": "#e8e8e8",
                        "font-size": "14px",
                        "padding": "10px 16px",
                        "--hover-color": "rgba(212,175,55,0.12)",
                        "border-radius": "0",
                    },
                    "nav-link-selected": {
                        "background-color": "rgba(212,175,55,0.18)",
                        "color": "#d4af37",
                        "border-left": "4px solid #d4af37",
                        "font-weight": "600",
                    },
                },
            )
        page = selected_label
    else:
        # Graceful fallback – plain radio widget
        page = st.sidebar.radio(
            "导航菜单",
            _LABELS,
            index=default_index,
            label_visibility="collapsed",
        )

    st.session_state.current_page = page
    return page
