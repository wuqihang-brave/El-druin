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

# All nav items in display order
_ALL_LABELS: list[str] = ["Dashboard", "Assessments", "Streams", "Knowledge"]

# Labels that navigate to a dedicated pages/ file instead of rendering inline
_PAGE_FILE_LABELS: dict[str, str] = {
    "Dashboard": "pages/1_Dashboard.py",
    "Assessments": "pages/2_Assessments.py",
    "Streams": "pages/4_Streams.py",
    "Knowledge": "pages/3_Knowledge.py",
}
# Public alias for use by app.py router
PAGE_FILE_LABELS = _PAGE_FILE_LABELS

# Labels rendered inline inside app.py (derived; do not edit directly)
_INLINE_LABELS: list[str] = [l for l in _ALL_LABELS if l not in _PAGE_FILE_LABELS]


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

        # ── Route dedicated pages (always, regardless of is_subpage) ───────
        if selected in _PAGE_FILE_LABELS:
            if selected != st.session_state.get("current_page"):
                st.session_state.current_page = selected
                st.switch_page(_PAGE_FILE_LABELS[selected])

        # ── Route inline pages when called from a sub-page ─────────────────
        if is_subpage and selected in _INLINE_LABELS:
            if selected != st.session_state.get("current_page"):
                st.session_state.current_page = selected
                st.switch_page("app.py")

        st.markdown("---")

        # ── Intelligence Feed control panel ────────────────────────────────
        st.markdown(
            """
            <div style="padding:8px 16px 4px 16px;font-size:0.65rem;text-transform:uppercase;
                        letter-spacing:0.1em;color:#4A6A8A;font-weight:600;">
              Intelligence Feed
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Ingest status
        try:
            from utils.api_client import get_scheduler_status as _get_status
            from datetime import datetime as _datetime
            _status = _get_status()
            if "error" in _status:
                _sync_label = "Signal Feed: connection error"
            elif _status.get("last_run_at"):
                _last_raw = _status["last_run_at"]
                try:
                    _last_dt = _datetime.fromisoformat(_last_raw.replace("Z", "+00:00"))
                    _sync_label = "Last sync: " + _last_dt.strftime("%Y-%m-%d %H:%M") + " UTC"
                except Exception:
                    _sync_label = "Last sync: " + str(_last_raw)
            else:
                _sync_label = "Signal Feed: never synced"
        except Exception:
            _sync_label = "Signal Feed: unavailable"

        st.markdown(
            f"""
            <div style="padding:2px 16px 6px 16px;font-size:0.72rem;color:#5A7A9A;">
              {_sync_label}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Button CSS for dark intelligence aesthetic
        st.markdown(
            """
            <style>
            div[data-testid="stSidebar"] .stButton > button {
                background: #0D1B2A;
                color: #7B9EB8;
                border: 1px solid #1E3050;
                font-size: 0.72rem;
                padding: 5px 10px;
                text-transform: uppercase;
                letter-spacing: 0.06em;
            }
            div[data-testid="stSidebar"] .stButton > button:hover {
                background: #162030;
                color: #C8D8E8;
                border-color: #2E4060;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        # Initialise persistent status state
        if "ingest_status" not in st.session_state:
            st.session_state.ingest_status = None
        if "gen_assess_status" not in st.session_state:
            st.session_state.gen_assess_status = None

        if st.button("Force Ingest Cycle", use_container_width=True, key="sidebar_force_ingest"):
            try:
                from utils.api_client import trigger_ingest_cycle as _trigger
                _result = _trigger()
                if "error" in _result:
                    st.session_state.ingest_status = f"❌ {_result['error']}"
                else:
                    st.session_state.ingest_status = "✅ Ingest cycle dispatched"
            except Exception as _exc:
                st.session_state.ingest_status = f"❌ {_exc}"

        if st.session_state.ingest_status:
            st.sidebar.caption(st.session_state.ingest_status)

        if st.button("Generate Assessments", use_container_width=True, key="sidebar_gen_assessments"):
            try:
                import time as _time
                from utils.api_client import trigger_assessment_generation as _trigger_gen
                from utils.api_client import get_assessment_job_status as _job_status
                _resp = _trigger_gen(min_events=1)
                _job_id = _resp.get("job_id")
                if not _job_id:
                    st.session_state.gen_assess_status = f"❌ Unexpected response: {_resp}"
                else:
                    _status: dict = {"status": "queued"}
                    with st.sidebar:
                        with st.spinner("Generating assessments…"):
                            for _ in range(40):  # poll for up to 2 minutes
                                _status = _job_status(_job_id)
                                if _status.get("status") in ("completed", "failed", "error"):
                                    break
                                _time.sleep(3)
                    if _status.get("status") == "completed":
                        _n = _status.get("result", {}).get("generated", 0)
                        _u = _status.get("result", {}).get("updated", 0)
                        st.session_state.gen_assess_status = f"✅ Generated {_n} new, updated {_u} assessments"
                    elif _status.get("status") in ("failed", "error"):
                        _err = _status.get("error", "unknown error")
                        st.session_state.gen_assess_status = f"❌ Generation failed: {_err}"
                    else:
                        st.session_state.gen_assess_status = "⏳ Generation still running — check back soon"
            except Exception as _exc:
                st.session_state.gen_assess_status = f"❌ {_exc}"

        if st.session_state.gen_assess_status:
            st.sidebar.caption(st.session_state.gen_assess_status)

    st.session_state.current_page = selected
    return selected
