"""
EL'druin Intelligence Platform – Sidebar Navigation Component
=============================================================

Provides a unified, English-first navigation sidebar with page navigation.

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
    st.session_state["cfg_engine"] = "Evented"

    _current = st.session_state.get("current_page", "Dashboard")
    _default_idx = _ALL_LABELS.index(_current) if _current in _ALL_LABELS else 0

    with st.sidebar:
        # ── Brand header ──────────────────────────────────────────────────
        st.markdown(
            """
            <div style="text-align:center;padding:10px 0 4px 0;">
                <h2 style="color:#4A8FD4;margin:0 0 2px 0;">EL&#39;DRUIN</h2>
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

    st.session_state.current_page = selected
    return selected