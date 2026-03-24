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
        <div style="text-align:center;padding:16px 0 10px 0;">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40" width="40" height="40"
                 style="display:block;margin:0 auto 8px auto;">
              <circle cx="20" cy="20" r="16" fill="none" stroke="#D4AF37" stroke-width="0.8"
                      stroke-dasharray="2 3.2"/>
              <line x1="20" y1="4" x2="20" y2="36" stroke="#D4AF37" stroke-width="1.6" stroke-linecap="round"/>
              <line x1="12" y1="14" x2="28" y2="14" stroke="#D4AF37" stroke-width="1.6" stroke-linecap="round"/>
              <line x1="16" y1="16" x2="24" y2="16" stroke="#D4AF37" stroke-width="0.8" stroke-linecap="round"/>
            </svg>
            <h3 style="color:#D4AF37;margin:4px 0 2px 0;font-size:1.05rem;
                       font-weight:300;letter-spacing:3px;font-family:'Inter',sans-serif;">
                EL-DRUIN
            </h3>
            <p style="color:#A8A8A8;font-size:0.72rem;margin:0;font-style:italic;
                      font-family:'Inter',sans-serif;">
                Ontological Intelligence &amp; Systematic Order
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        "<hr style='border-color:#2D333B;margin:4px 0 8px 0'/>",
        unsafe_allow_html=True,
    )

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
                        "background-color": "#0A0A0A",
                    },
                    "icon": {"color": "#D4AF37", "font-size": "15px"},
                    "nav-link": {
                        "color": "#F0F0F0",
                        "font-size": "13px",
                        "padding": "10px 16px",
                        "--hover-color": "rgba(212,175,55,0.10)",
                        "border-radius": "0",
                        "background-color": "#2D333B",
                        "border-bottom": "1px solid #1a1e24",
                    },
                    "nav-link-selected": {
                        "background-color": "#D4AF37",
                        "color": "#0D0D0D",
                        "border-left": "none",
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

    # ── Footer quote ──────────────────────────────────────────────────────────
    st.sidebar.markdown(
        """
        <div style="position:absolute;bottom:16px;left:0;right:0;
                    text-align:center;padding:0 12px;">
            <p style="color:#8B8B8B;font-size:10px;font-style:italic;
                      margin:0;font-family:'Inter',sans-serif;line-height:1.5;">
                "I fear no evil, for Thou art with me."
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    return page
