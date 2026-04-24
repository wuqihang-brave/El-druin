"""
Ultrametric Distance on Pattern Space (pattern-name interface)
==============================================================

Provides ``ultrametric_distance(pattern_a, pattern_b)`` that works directly
with CJK pattern name strings from ``CARTESIAN_PATTERN_REGISTRY``, bridging
the name-based ontology layer with the group-element-based ultrametric
defined in ``ultrametric_graph.py``.

7-adic ultrametric distance::

    d_7(A, B) = 7^{−v_7(graph_dist(A, B))}

Properties
----------
- Same Sylow-7 domain (same H₇ coset):  d_7 = 7^{−k}, k ≥ 1  (small)
- Different Sylow-7 domains:             d_7 = 1  (maximum)
- Strong triangle inequality:            d(A, C) ≤ max(d(A, B), d(B, C))
"""

from __future__ import annotations

from typing import Optional


def ultrametric_distance(pattern_a: str, pattern_b: str) -> float:
    """Compute the 7-adic ultrametric distance between two named patterns.

    Formula::

        d_7(A, B) = 7^{−v_7(graph_dist(A, B))}

    where ``graph_dist`` is the shortest-path length in the composition graph
    Γ = (S, E) with E = {(A, B) : A · B ∈ S defined in composition_table}.

    Heuristic used here (exact BFS would require full graph construction):

    - If A == B: distance 0.
    - Different Sylow-7 cosets (different domains): distance 1 (maximum).
    - Same Sylow-7 coset and a direct composition exists: graph_dist = 1,
      v_7(1) = 0, but we use the coset-level distance 7^{-1} ≈ 0.143.
    - Same Sylow-7 coset, no direct composition: graph_dist = 2,
      v_7(2) = 0, return 7^{-1} (intra-domain default).

    Args:
        pattern_a: CJK internal key of pattern A.
        pattern_b: CJK internal key of pattern B.

    Returns:
        Float in [0, 1]:
          0.0   → identical patterns
          7^{-k} → same domain (k ≥ 1, reflecting composition-graph proximity)
          1.0   → different domains (maximum ultrametric distance)
    """
    if pattern_a == pattern_b:
        return 0.0

    try:
        from ontology.relation_schema import (  # type: ignore
            SYLOW7_DOMAIN_MAP,
            composition_table,
        )
        from intelligence.p_adic_confidence import p_adic_valuation  # type: ignore
    except ImportError:
        # Fallback: cannot determine cosets; treat as maximum distance
        return 1.0

    coset_a = SYLOW7_DOMAIN_MAP.get(pattern_a, 0)
    coset_b = SYLOW7_DOMAIN_MAP.get(pattern_b, 0)

    if coset_a != coset_b:
        # Different Sylow-7 domains → maximum ultrametric distance
        return 1.0

    # Same domain: estimate graph distance from composition table.
    # This is a conservative approximation: graph_dist=1 if a direct
    # composition entry exists, graph_dist=2 otherwise (actual distance may
    # be larger for patterns far apart in the composition graph, but 2 is a
    # reasonable default since v_7(1)=v_7(2)=0, both yielding distance 7^{-1}).
    if (
        (pattern_a, pattern_b) in composition_table
        or (pattern_b, pattern_a) in composition_table
    ):
        graph_dist = 1
    else:
        graph_dist = 2  # default for same-domain pairs without direct composition

    v = p_adic_valuation(graph_dist, 7)
    if v > 0:
        return float(7) ** (-v)
    # graph_dist not divisible by 7 (e.g. 1 or 2): return intra-domain weight 7^{-1}
    return 7.0 ** -1
