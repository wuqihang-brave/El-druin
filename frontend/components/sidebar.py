"""
EL'druin Intelligence Platform – Sidebar Navigation Component
=============================================================
参考 GraphRAG 思路，集成了：
1. 核心功能导航
2. 推演深度控制 (Inference Control)
3. 知识图谱视图切换
"""

from __future__ import annotations
import streamlit as st

try:
    from streamlit_option_menu import option_menu  # type: ignore[import]
    _OPTION_MENU_AVAILABLE = True
except ImportError:
    _OPTION_MENU_AVAILABLE = False

# 核心导航项：只保留真正在运行的逻辑页面
_NAV_ITEMS: list[tuple[str, str]] = [
    ("🏠 主页", "house-fill"),      # 确保这一行在首位
    ("📰 实时新闻", "newspaper"),
    ("🕸️ 知识图谱", "diagram-3-fill"),
    ("⚙️ 系统状态", "gear-fill"),
]

_LABELS = [item[0] for item in _NAV_ITEMS]
_ICONS = [item[1] for item in _NAV_ITEMS]

def render_sidebar_navigation() -> str:
    """渲染侧边栏并返回选中的页面，同时在侧边栏注入推演配置"""
    
    _prev_page = st.session_state.get("current_page")

    with st.sidebar:
        st.markdown(
            """
            <div style="text-align: center; padding: 10px 0;">
                <h2 style="color: #0047AB; margin-bottom: 0;">EL'druin</h2>
                <p style="color: #606060; font-size: 0.8rem;">Ontological Reasoning v1.0</p>
            </div>
            """, 
            unsafe_allow_html=True
        )

        # ── 1. 页面导航 ────────────────────────────────────────────────────────
        if _OPTION_MENU_AVAILABLE:
            selected_label = option_menu(
                menu_title=None,
                options=_LABELS,
                icons=_ICONS,
                menu_icon="cast",
                default_index=0,
                styles={
                    "container": {"padding": "0!important", "background-color": "#F5F5F5"},
                    "icon": {"color": "#606060", "font-size": "14px"},
                    "nav-link": {
                        "font-size": "13px",
                        "text-align": "left",
                        "margin": "0px",
                        "padding": "10px 16px",
                        "border-bottom": "1px solid #E0E0E0",
                    },
                    "nav-link-selected": {"background-color": "#0047AB", "color": "#FFFFFF"},
                },
            )
            page = selected_label
        else:
            page = st.sidebar.radio("导航菜单", _LABELS, index=0)

        st.markdown("---")

        # ── 2. 推演引擎配置 (参考 GraphRAG 的调优思路) ──────────────────────────
        st.subheader("🧠 推演引擎配置")
        
        # 允许用户控制推演深度，这将直接传递给后端的 sacred-sword 接口
        st.session_state.inference_level = st.select_slider(
            "逻辑推演深度",
            options=["基础", "关联", "本体", "预测"],
            value=st.session_state.get("inference_level", "关联"),
            help="基础：单篇分析；关联：跨篇关联；本体：语义挖掘；预测：因果推断"
        )

        st.session_state.show_hidden_nodes = st.toggle(
            "显示潜在隐变量", 
            value=False,
            help="开启后将显示后端推导出的隐藏逻辑实体"
        )

        st.markdown("---")
        
        # ── 3. 快捷操作 ──────────────────────────────────────────────────────
        if st.button("🔄 刷新全量图谱", use_container_width=True):
            st.toast("正在重新构建本体索引...")

    # 状态更新逻辑
    st.session_state.current_page = page
    if page != _prev_page:
        st.rerun()

    return page