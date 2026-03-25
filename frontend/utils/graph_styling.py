"""
Graph Styling – EL-DRUIN Intelligence Platform
===============================================

Provides :func:`render_graph_with_colors` which builds node/edge lists
suitable for ``streamlit-agraph`` (with a Plotly fallback) and applies
ontology-class color coding, degree-based sizing, and selection glow.

Usage::

    from utils.graph_styling import render_graph_with_colors

    clicked = render_graph_with_colors(
        graph_data={"entities": [...], "relations": [...]},
        selected_name="John Smith",
        height=600,
    )
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from utils.ontology_colors import get_node_color, get_canonical_class

# ---------------------------------------------------------------------------
# Optional imports
# ---------------------------------------------------------------------------
try:
    from streamlit_agraph import agraph, Config, Edge, Node  # type: ignore[import]
    _AGRAPH = True
except ImportError:
    _AGRAPH = False

try:
    import plotly.graph_objects as go
    import networkx as nx  # type: ignore[import]
    _PLOTLY = True
except ImportError:
    _PLOTLY = False
    nx = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Sizing constants
# ---------------------------------------------------------------------------
_BASE_SIZE = 15         # base node size (px)
_SIZE_PER_DEGREE = 3    # additional px per connection
_MAX_SIZE = 60          # cap to avoid huge nodes
_SELECTED_BONUS = 15    # extra size for the selected node
_EDGE_COLOR = "#A0A0A0"  # Light grey — Clear Day theme
_EDGE_ALPHA = 0.6


def _node_size(degree: int, selected: bool) -> int:
    """Compute visual node size from degree and selection state."""
    size = _BASE_SIZE + degree * _SIZE_PER_DEGREE
    if selected:
        size += _SELECTED_BONUS
    return min(size, _MAX_SIZE)


def _build_node(
    name: str,
    ontology_class: str,
    degree: int,
    selected: bool,
) -> "Node":  # type: ignore[name-defined]
    """Build a streamlit-agraph :class:`Node` with ontology color styling."""
    color = get_node_color(ontology_class)
    size = _node_size(degree, selected)
    canonical = get_canonical_class(ontology_class)

    node_kwargs: Dict[str, Any] = dict(
        id=name,
        label=name,
        size=size,
        title=f"{name}\nClass: {canonical}",
        font={"color": "#333333", "size": 11},
    )

    if selected:
        # Cobalt blue selection highlight
        node_kwargs["color"] = {
            "background": color,
            "border": "#003580",
            "highlight": {"background": "#003580", "border": "#0047AB"},
        }
        node_kwargs["borderWidth"] = 3
        node_kwargs["shadow"] = True
    else:
        node_kwargs["color"] = {
            "background": color,
            "border": "#0047AB",
            "highlight": {"background": "#0047AB", "border": "#003580"},
        }
        node_kwargs["borderWidth"] = 1

    return Node(**node_kwargs)


def _build_edge(
    src: str,
    tgt: str,
    label: str,
    confidence: float,
) -> "Edge":  # type: ignore[name-defined]
    """Build a streamlit-agraph :class:`Edge` with consistent dark styling."""
    alpha = max(0.25, min(0.85, 0.25 + confidence * 0.6))
    width = max(1, int(confidence * 4))
    return Edge(
        source=src,
        target=tgt,
        label=label,
        color=f"rgba(85,85,85,{alpha:.2f})",
        width=width,
    )


def render_graph_with_colors(
    graph_data: Dict[str, Any],
    selected_name: str = "",
    height: int = 580,
    max_nodes: int = 120,
    max_edges: int = 300,
) -> Optional[str]:
    """Render an interactive knowledge graph with ontology-class color coding.

    Node color is determined by ``ontology_class`` (falling back to ``type``).
    Node size scales with degree.  The *selected_name* node is larger and
    shows a glow border.

    Args:
        graph_data: Dict with ``"entities"`` and ``"relations"`` lists.
        selected_name: Name of the currently-selected entity (may be empty).
        height: Canvas height in pixels.
        max_nodes: Maximum number of nodes to render.
        max_edges: Maximum number of edges to render.

    Returns:
        The name of the clicked node (or ``None`` if nothing was clicked /
        interactive rendering is unavailable).
    """
    entities: List[Dict[str, Any]] = graph_data.get("entities", [])
    relations: List[Dict[str, Any]] = graph_data.get("relations", [])

    if not entities and not relations:
        st.info("📭 No graph data available.")
        return None

    # ── Compute degree map ────────────────────────────────────────────────
    degree_map: Dict[str, int] = {}
    for rel in relations:
        for key in ("from", "from_entity", "subject"):
            n = rel.get(key, "")
            if n:
                degree_map[n] = degree_map.get(n, 0) + 1
        for key in ("to", "to_entity", "object"):
            n = rel.get(key, "")
            if n:
                degree_map[n] = degree_map.get(n, 0) + 1

    # ── agraph path ──────────────────────────────────────────────────────
    if _AGRAPH:
        ag_nodes: List[Node] = []
        for ent in entities[:max_nodes]:
            name = ent.get("name", "?")
            # Prefer explicit ontology_class; fall back to NLP type field
            onto_class = ent.get("ontology_class") or ent.get("type", "misc")
            degree = degree_map.get(name, 0)
            is_selected = name == selected_name
            ag_nodes.append(_build_node(name, onto_class, degree, is_selected))

        displayed = {n.id for n in ag_nodes}
        ag_edges: List[Edge] = []
        for rel in relations[:max_edges]:
            src = rel.get("from", rel.get("from_entity", rel.get("subject", "")))
            tgt = rel.get("to", rel.get("to_entity", rel.get("object", "")))
            if src in displayed and tgt in displayed:
                label = rel.get("relation", rel.get("relationship_type", rel.get("predicate", "")))
                conf = float(rel.get("confidence", rel.get("weight", 0.5)))
                ag_edges.append(_build_edge(src, tgt, label, conf))

        config = Config(
            width="100%",
            height=height,
            directed=True,
            physics=True,
            hierarchical=False,
            nodeHighlightBehavior=True,
            highlightColor="#003580",
            collapsible=False,
            node={"labelProperty": "label"},
            link={"renderLabel": False, "highlightColor": "#0047AB"},
            backgroundColor="#F0F8FF",
        )

        return agraph(nodes=ag_nodes, edges=ag_edges, config=config)

    # ── Plotly fallback ───────────────────────────────────────────────────
    if _PLOTLY and nx is not None:
        G = nx.DiGraph()
        entity_meta: Dict[str, Dict[str, Any]] = {}
        for ent in entities[:max_nodes]:
            name = ent.get("name", "?")
            onto_class = ent.get("ontology_class") or ent.get("type", "misc")
            entity_meta[name] = {"onto_class": onto_class}
            G.add_node(name)
        for rel in relations[:max_edges]:
            src = rel.get("from", rel.get("from_entity", rel.get("subject", "")))
            tgt = rel.get("to", rel.get("to_entity", rel.get("object", "")))
            if src and tgt:
                G.add_node(src)
                G.add_node(tgt)
                G.add_edge(src, tgt)

        if G.number_of_nodes() == 0:
            st.info("📭 No nodes to display.")
            return None

        pos = nx.spring_layout(G, seed=42)
        edge_x: List[float] = []
        edge_y: List[float] = []
        for u, v in G.edges():
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]

        node_names = list(G.nodes())
        node_x = [pos[n][0] for n in node_names]
        node_y = [pos[n][1] for n in node_names]
        node_colors = [
            get_node_color(entity_meta.get(n, {}).get("onto_class", "misc"))
            for n in node_names
        ]
        node_sizes = [
            _node_size(degree_map.get(n, 0), n == selected_name)
            for n in node_names
        ]
        node_borders = [
            "#003580" if n == selected_name else "#E0E0E0"
            for n in node_names
        ]

        fig = go.Figure(
            data=[
                go.Scatter(
                    x=edge_x, y=edge_y, mode="lines",
                    line={"width": 0.5, "color": f"rgba(160,160,160,{_EDGE_ALPHA})"},
                    hoverinfo="none",
                ),
                go.Scatter(
                    x=node_x, y=node_y, mode="markers+text",
                    text=node_names, textposition="top center",
                    textfont={"color": "#606060", "size": 9},
                    marker={
                        "size": node_sizes,
                        "color": node_colors,
                        "line": {"width": 2, "color": node_borders},
                    },
                    hoverinfo="text",
                    hovertext=node_names,
                ),
            ],
            layout=go.Layout(
                showlegend=False,
                hovermode="closest",
                paper_bgcolor="#F0F8FF",
                plot_bgcolor="#F0F8FF",
                xaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
                yaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
                height=height,
                margin={"t": 10, "b": 0, "l": 0, "r": 0},
            ),
        )
        st.plotly_chart(fig, use_container_width=True)
        return None

    st.warning(
        "Install `streamlit-agraph` or `plotly`+`networkx` for interactive graph rendering."
    )
    return None


def render_color_legend(ontology_classes: List[str]) -> None:
    """Render a horizontal color legend for the given ontology classes.

    Args:
        ontology_classes: List of ontology class names to include in the legend.
    """
    if not ontology_classes:
        return
    cols = st.columns(min(len(ontology_classes), 6))
    for i, cls in enumerate(ontology_classes):
        color = get_node_color(cls)
        cols[i % len(cols)].markdown(
            f"<span style='color:{color};font-size:18px'>●</span> "
            f"<span style='color:#606060;font-size:0.85rem;'>{cls}</span>",
            unsafe_allow_html=True,
        )
