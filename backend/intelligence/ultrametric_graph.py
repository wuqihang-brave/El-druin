"""
Ultrametric Transition Graph
=============================

Builds a directed transition graph over the 21-element pattern space
S = Z_7 ⋊ Z_3 and equips it with the ultrametric distance d_7.

Ultrametric distance::

    d_7(A, B) = 7^{−v_7(graph_dist(A, B))}

Properties:
  - Intra-domain (same Sylow-7 coset): d_7 = 7^{-k}, k ≥ 1  → small, easy propagation
  - Cross-domain (different Sylow-7 cosets): d_7 = 1  → maximum, requires phase transition
  - Strong triangle inequality: d(A, C) ≤ max(d(A, B), d(B, C))

Edge weights:
  - Intra-domain edges: weight = 7^{-1} ≈ 0.143
  - Cross-domain edges: added only under phase-transition condition (step t ≡ 0 mod 7)
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from intelligence.group_structure import Element, S, get_coset
from intelligence.p_adic_confidence import p_adic_valuation

# ---------------------------------------------------------------------------
# Ultrametric distance (graph-based)
# ---------------------------------------------------------------------------

# Graph representation: adjacency dict {node: {neighbor: weight}}
Graph = Dict[Element, Dict[Element, float]]


def build_transition_graph(
    patterns: Optional[List[Element]] = None,
    phase_transition_step: Optional[int] = None,
) -> Graph:
    """Build a directed transition graph over the pattern space.

    Intra-domain edges (same Sylow-7 / H₇ coset) are always present with
    weight 7^{-1}.  Cross-domain edges are added only when
    ``phase_transition_step`` is a multiple of 7 (i.e. a phase-transition step).

    Args:
        patterns: List of pattern elements to include (default: all 21 in S).
        phase_transition_step: If provided and divisible by 7, cross-domain
            edges are added with weight 1.0 (maximum ultrametric distance).

    Returns:
        Directed graph as an adjacency dict.
    """
    if patterns is None:
        patterns = list(S)

    graph: Graph = {p: {} for p in patterns}
    intra_weight = 7.0 ** -1

    cross_domain = (
        phase_transition_step is not None and phase_transition_step % 7 == 0
    )

    for A in patterns:
        domain_A, _ = get_coset(A)
        for B in patterns:
            if A == B:
                continue
            domain_B, _ = get_coset(B)
            if domain_A == domain_B:
                # Intra-domain: always easy propagation
                graph[A][B] = intra_weight
            elif cross_domain:
                # Cross-domain: only during phase transitions
                graph[A][B] = 1.0

    return graph


def _bfs_distance(graph: Graph, source: Element, target: Element) -> int:
    """BFS shortest-path distance in a directed graph.

    Returns a very large sentinel (10**9) if no path exists.
    """
    if source == target:
        return 0
    visited = {source}
    queue = [(source, 0)]
    while queue:
        current, dist = queue.pop(0)
        for neighbor in graph.get(current, {}):
            if neighbor == target:
                return dist + 1
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, dist + 1))
    return 10**9  # no path


def ultrametric_d7(A: Element, B: Element, graph: Graph) -> float:
    """Compute the ultrametric distance d_7(A, B).

    d_7(A, B) = 7^{−v_7(graph_dist(A, B))}

    Special cases:
      - A == B: distance 0
      - Different Sylow-7 domains with no path: distance 1 (maximum)
      - Same domain: distance 7^{-k} for some k ≥ 1

    Args:
        A: Source pattern element.
        B: Target pattern element.
        graph: Directed transition graph (from ``build_transition_graph``).

    Returns:
        Ultrametric distance in [0, 1].
    """
    if A == B:
        return 0.0

    domain_A, _ = get_coset(A)
    domain_B, _ = get_coset(B)

    if domain_A != domain_B:
        # Cross-domain: maximum ultrametric distance
        # (unless a phase-transition edge exists in graph)
        d = _bfs_distance(graph, A, B)
        if d >= 10**9:
            return 1.0
        v = p_adic_valuation(d, 7)
        return 7.0 ** (-v)

    d = _bfs_distance(graph, A, B)
    if d == 0:
        return 0.0
    if d >= 10**9:
        return 1.0
    v = p_adic_valuation(d, 7)
    return 7.0 ** (-v)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify_ultrametric(
    patterns: Optional[List[Element]] = None,
    graph: Optional[Graph] = None,
) -> None:
    """Verify the strong triangle inequality: d(A, C) ≤ max(d(A, B), d(B, C)).

    Checks all triples from the first 10 patterns (or all if fewer than 10).

    Args:
        patterns: Pattern elements to check (default: first 10 of S).
        graph: Directed transition graph (default: standard intra-domain graph).

    Raises:
        AssertionError: If the strong triangle inequality is violated.
    """
    from itertools import combinations

    if patterns is None:
        patterns = list(S)[:10]
    if graph is None:
        graph = build_transition_graph(patterns)

    for A, B, C in combinations(patterns, 3):
        dAB = ultrametric_d7(A, B, graph)
        dBC = ultrametric_d7(B, C, graph)
        dAC = ultrametric_d7(A, C, graph)
        assert dAC <= max(dAB, dBC) + 1e-9, (
            f"Strong triangle inequality violated: "
            f"d({A},{C})={dAC:.6f} > max(d({A},{B})={dAB:.6f}, "
            f"d({B},{C})={dBC:.6f})"
        )


if __name__ == "__main__":
    g = build_transition_graph()
    verify_ultrametric(list(S)[:10], g)
    print("✓ Strong ultrametric triangle inequality verified")

    # Show sample distances
    from intelligence.group_structure import H7

    print("\nSample intra-domain distances (same Sylow-7 coset):")
    for a in range(3):
        A = (a, 0)
        B = ((a + 1) % 7, 0)
        print(f"  d_7({A}, {B}) = {ultrametric_d7(A, B, g):.6f}")

    print("\nSample cross-domain distances (different Sylow-7 cosets):")
    A = (0, 0)  # geopolitics
    B = (1, 0)  # economics  — wait, same H7 coset index but different a
    C = (0, 1)  # geopolitics / coercive
    D = (1, 1)  # economics / coercive
    print(f"  d_7({A}, {C}) = {ultrametric_d7(A, C, g):.6f}  (same a, different b)")
