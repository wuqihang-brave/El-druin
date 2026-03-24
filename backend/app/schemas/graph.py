"""
Data models for the hierarchical knowledge graph API.
"""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    degree: int
    properties: Dict[str, Any]


class GraphEdge(BaseModel):
    from_node: str
    to_node: str
    relation_type: str
    weight: float


class NodeOrderNarrative(BaseModel):
    node_id: str
    node_name: str
    node_type: str
    degree: int
    importance_tier: str  # Critical, Important, Bridge, Leaf
    definition: str
    main_connections: List[Dict[str, Any]]
    global_role: str
    betweenness_centrality: float


class HierarchicalGraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    degree_map: Dict[str, int]
    total_nodes: int
    total_edges: int
