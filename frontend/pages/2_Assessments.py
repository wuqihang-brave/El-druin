"""
Assessments – EL-DRUIN Intelligence Platform
=============================================

Stub page that redirects to the Assessments view in the main app.
"""

import os
import sys
import streamlit as st

_FRONTEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FRONTEND_DIR not in sys.path:
    sys.path.insert(0, _FRONTEND_DIR)

st.set_page_config(
    page_title="Assessments – EL-DRUIN",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    from components.sidebar import render_sidebar_navigation  # noqa: E402
    st.session_state["current_page"] = "Assessments"
    render_sidebar_navigation(is_subpage=True)
except Exception:
    st.switch_page("app.py")
