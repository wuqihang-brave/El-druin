"""
Propagation Engine
==================

Computes a cross-domain propagation sequence from assessment context.

Design principle
----------------
The engine derives a time-ordered sequence of domain transfer events by
following canonical coupling rules (military → diplomatic → sanctions →
energy/finance/trade → …) and adjusting lag estimates using velocity signals
from the assessment context.  Bottlenecks and second-order effects are
inferred from the causal graph rather than computed statistically, so no raw
model notation (sigma, Bayesian p=, manifold) ever surfaces in output strings.

Usage::

    from app.services.propagation_engine import PropagationEngine

    engine = PropagationEngine()
    output = await engine.compute_propagation(assessment_id, context)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.schemas.structural_forecast import PropagationOutput, PropagationStep

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Allowed domain list
# ---------------------------------------------------------------------------

_ALLOWED_DOMAINS = frozenset(
    [
        "military",
        "diplomatic",
        "sanctions",
        "energy",
        "finance",
        "trade",
        "insurance",
        "political",
        "logistics",
        "market",
    ]
)

# ---------------------------------------------------------------------------
# Time-bucket ordering (index = temporal position)
# ---------------------------------------------------------------------------

_TIME_BUCKET_ORDER = ["T+0", "T+24h", "T+72h", "T+7d", "T+2-6w"]

# ---------------------------------------------------------------------------
# Canonical domain propagation graph
# Each entry: (source_domain, target_domain, default_time_bucket, coupling_strength)
# ---------------------------------------------------------------------------

_PROPAGATION_GRAPH: list[tuple[str, str, str, float]] = [
    # Tier 1 — immediate military → diplomatic escalation
    ("military",   "diplomatic",  "T+24h",  0.82),
    # Tier 2 — diplomatic pressure into formal coercion instruments
    ("diplomatic", "sanctions",   "T+72h",  0.71),
    # Tier 3 — sanctions fan-out into real-economy domains
    ("sanctions",  "energy",      "T+72h",  0.78),
    ("sanctions",  "finance",     "T+7d",   0.65),
    ("sanctions",  "trade",       "T+7d",   0.62),
    # Tier 4 — energy shock propagation
    ("energy",     "insurance",   "T+24h",  0.74),
    ("energy",     "logistics",   "T+72h",  0.58),
    ("insurance",  "market",      "T+7d",   0.67),
    # Tier 5 — finance and trade downstream
    ("finance",    "trade",       "T+7d",   0.60),
    ("trade",      "political",   "T+2-6w", 0.53),
    ("logistics",  "market",      "T+2-6w", 0.50),
]

# Coupling strength lookup: (src, tgt) → strength
_COUPLING: dict[tuple[str, str], float] = {
    (src, tgt): strength for src, tgt, _, strength in _PROPAGATION_GRAPH
}

# Default time-bucket for each transition
_DEFAULT_BUCKET: dict[tuple[str, str], str] = {
    (src, tgt): bucket for src, tgt, bucket, _ in _PROPAGATION_GRAPH
}

# ---------------------------------------------------------------------------
# Domain-event templates (PRD vocabulary only)
# ---------------------------------------------------------------------------

_DOMAIN_EVENT_TEMPLATES: dict[str, list[str]] = {
    "military": [
        "Force posture shift triggers cascade onset; direct control of transit corridor contested",
        "Military deployment establishes domain dominance; propagation threshold crossed",
        "Naval assets enforce access denial; cross-domain coupling with energy sector activated",
    ],
    "diplomatic": [
        "Diplomatic channel breakdown accelerates coupling transfer to sanction instruments",
        "Formal attribution exchanged between counterparties; diplomatic attractor weakening",
        "Third-party mediation window opens; lag to sanctions domain begins narrowing",
    ],
    "sanctions": [
        "Sanctions package activated; cascading domain transfer to energy and finance corridors",
        "Secondary sanctions designation initiates propagation into correspondent banking networks",
        "Sanctions threshold crossed; coupling intensity with trade domain increases",
    ],
    "energy": [
        "Energy corridor disruption propagates to insurance and logistics domains",
        "Supply-route chokepoint triggers spot-price cascade in downstream markets",
        "Transit interruption activates insurance market exit and logistics re-routing",
    ],
    "finance": [
        "Sovereign spread widening signals propagation into trade financing and political domains",
        "Correspondent banking withdrawal cascades across regional financial attractor basin",
        "Liquidity stress amplifies cross-domain coupling with trade renegotiation cycle",
    ],
    "trade": [
        "Supply-chain re-routing triggers political escalation via domestic rationing pressure",
        "Trade disruption propagates regime-level instability into political attractor",
        "Contract renegotiations absorb market shock; lag to political domain begins",
    ],
    "insurance": [
        "War-risk premium breach triggers underwriter exit; market attractor destabilises",
        "Lloyd's corridor coverage withdrawal cascades into market repricing",
        "Insurance market concentration amplifies coupling to downstream market domain",
    ],
    "political": [
        "Political attractor shifted by domestic cost accumulation from upstream cascade",
        "Emergency legislative session signals regime-level response to propagation sequence",
        "Political coupling locks in; policy response narrows structural damping capacity",
    ],
    "logistics": [
        "Logistics re-routing adds structural lag to downstream market propagation",
        "Chokepoint bypass activated; transit-cost amplification propagates to market domain",
        "Alternative routing capacity insufficient to absorb domain transfer shock",
    ],
    "market": [
        "Market repricing cascade absorbs upstream propagation from insurance and logistics",
        "Cross-domain coupling consolidates at market level; attractor equilibrium reassessed",
        "Spot-price dislocation signals terminal propagation step in current cascade sequence",
    ],
}


def _domain_event(domain: str, index: int) -> str:
    """Return a domain event description from the template catalogue."""
    templates = _DOMAIN_EVENT_TEMPLATES.get(domain, [f"{domain} domain transfer event"])
    return templates[index % len(templates)]


# ---------------------------------------------------------------------------
# Bottleneck templates
# ---------------------------------------------------------------------------

_BOTTLENECK_TEMPLATES: dict[str, str] = {
    "military":  "Single force-posture chokepoint with no viable short-term military bypass",
    "energy":    "Energy corridor concentration: limited alternative routing capacity within lag window",
    "insurance": "Insurance market concentration in London market amplifies coupling to market domain",
    "finance":   "Correspondent banking withdrawal rate exceeds liquidity injection capacity",
    "trade":     "Re-routing volume exceeds alternative transit infrastructure threshold",
    "sanctions": "Secondary sanctions designation speed exceeds diplomatic damping window",
    "diplomatic": "Attribution timeline constrains diplomatic channel throughput",
    "political": "Domestic political cost accumulation rate limits policy response bandwidth",
    "logistics": "Alternative logistics capacity insufficient to absorb re-routing demand within lag",
    "market":    "Market liquidity depth insufficient to absorb rapid propagation without repricing",
}

_DEFAULT_BOTTLENECK = (
    "Cross-domain coupling rate exceeds structural damping capacity at propagation node"
)

# ---------------------------------------------------------------------------
# Second-order effect templates
# ---------------------------------------------------------------------------

_SECOND_ORDER_TEMPLATES: list[str] = [
    "Accelerated permitting for alternative supply corridors in downstream states",
    "Domestic energy rationing measures activated in states dependent on disrupted corridor",
    "LNG spot demand spike in regional markets as pipeline alternative is sought",
    "Increased diplomatic pressure on neutral transit states to declare corridor allegiance",
    "Insurance premium contagion spreading to adjacent corridors not directly affected",
    "Capital reallocation from corridor-exposed assets into safe-haven instruments",
    "Political attractor shift in downstream states toward self-sufficiency policy",
    "Parallel propagation pathway via logistics domain activates secondary market dislocation",
    "Sanctions counter-measures accelerate regional de-dollarisation attractor",
    "Structural novelty of cascade sequence elevates watch-signal density in adjacent domains",
]

# Domain-specific second-order effects that supersede generic templates
_SECOND_ORDER_BY_DOMAIN: dict[str, str] = {
    "military":  "Parallel military escalation path activated in adjacent theatre",
    "diplomatic": "Diplomatic isolation attractor strengthens as coupling sequence advances",
    "sanctions": "Secondary sanctions trigger retaliatory economic countermeasures",
    "energy":    "LNG spot demand spike propagates to downstream states not in primary sequence",
    "finance":   "Capital flight attractor activates in region-adjacent markets",
    "trade":     "Supply-chain de-coupling accelerates structural re-alignment in downstream states",
    "insurance": "Corridor-adjacent insurance market contagion emerges as second-order signal",
    "political": "Domestic rationing pressure creates political second-order attractor shift",
    "logistics": "Parallel re-routing cascade creates logistics bottleneck in adjacent corridor",
    "market":    "Market dislocation extends into adjacent asset classes via coupling transfer",
}


# ---------------------------------------------------------------------------
# PropagationEngine
# ---------------------------------------------------------------------------


class PropagationEngine:
    """
    Computes a time-ordered cross-domain propagation sequence.

    The engine:
    1. Identifies the initial domain from the assessment context
       (``domain_tags`` field or inferred from ``events``).
    2. Walks the canonical propagation graph using those domains as seeds.
    3. Adjusts time_bucket assignments using velocity signals when available.
    4. Detects bottlenecks from graph chokepoints and causal concentration.
    5. Extracts second-order effects from downstream domains beyond the
       primary sequence.
    """

    async def compute_propagation(
        self, assessment_id: str, context: dict
    ) -> PropagationOutput:
        """
        Compute a cross-domain propagation sequence for the given assessment.

        Args:
            assessment_id: Unique assessment identifier.
            context:        Assessment context dict with keys such as
                            ``domain_tags``, ``events``, ``velocity_data``,
                            ``kg_paths``, ``regime_state``.

        Returns:
            ``PropagationOutput`` with at least 3 ordered ``PropagationStep``
            entries, a non-empty ``bottlenecks`` list, and a non-empty
            ``second_order_effects`` list.
        """
        domain_tags: list[str] = context.get("domain_tags", [])
        events: list[dict] = context.get("events", [])
        velocity_data: dict[str, float] = context.get("velocity_data", {})
        kg_paths: list[dict] = context.get("kg_paths", [])
        regime_state: dict = context.get("regime_state", {})

        # 1. Determine seed domains
        seed_domains = self._resolve_seed_domains(domain_tags, events)

        # 2. Build causal chain via graph walk
        causal_chain = self._build_causal_chain(seed_domains)

        # 3. Derive velocity: use regime damping_capacity as a global modifier
        damping = float(regime_state.get("damping_capacity", 0.5))
        velocity = 1.0 - damping  # higher damping → slower propagation

        # 4. Build ordered PropagationStep list
        sequence = self._build_domain_sequence(causal_chain, domain_tags, velocity_data, velocity)

        # 5. Detect bottlenecks
        graph_data: dict[str, Any] = {"kg_paths": kg_paths, "velocity_data": velocity_data}
        bottlenecks = self._detect_bottlenecks(sequence, graph_data)

        # 6. Extract second-order effects
        second_order = self._extract_second_order(sequence, context)

        return PropagationOutput(
            assessment_id=assessment_id,
            sequence=sequence,
            bottlenecks=bottlenecks,
            second_order_effects=second_order,
            updated_at=datetime.now(tz=timezone.utc),
        )

    # ------------------------------------------------------------------
    # Seed domain resolution
    # ------------------------------------------------------------------

    def _resolve_seed_domains(
        self, domain_tags: list[str], events: list[dict]
    ) -> list[str]:
        """
        Identify the initial seed domain(s) for the propagation walk.

        Priority order:
        1. ``domain_tags`` from the assessment context (first recognised domain).
        2. ``domains`` field of the highest-causal-weight event.
        3. Default to ``["military"]`` when no domain can be determined.
        """
        # Filter to allowed domains, preserving order
        valid_tags = [d for d in domain_tags if d in _ALLOWED_DOMAINS]
        if valid_tags:
            return valid_tags[:2]  # at most 2 seeds to bound sequence length

        # Fall back to events
        if events:
            best_event = max(events, key=lambda e: float(e.get("causal_weight", 0.0)))
            event_domains = [
                d for d in best_event.get("domains", []) if d in _ALLOWED_DOMAINS
            ]
            if event_domains:
                return event_domains[:1]

        return ["military"]

    # ------------------------------------------------------------------
    # Causal chain construction
    # ------------------------------------------------------------------

    def _build_causal_chain(self, seed_domains: list[str]) -> list[str]:
        """
        Walk the propagation graph from ``seed_domains`` using BFS up to
        a depth that produces at least 4 distinct domain nodes.

        Returns an ordered list of domain names representing the causal chain.
        """
        visited: list[str] = []
        seen: set[str] = set()
        queue: list[str] = []

        for seed in seed_domains:
            if seed not in seen:
                visited.append(seed)
                seen.add(seed)
                queue.append(seed)

        # BFS over propagation graph
        while queue and len(visited) < 8:
            current = queue.pop(0)
            # Sort outgoing edges by coupling strength (highest first)
            outgoing = sorted(
                [(tgt, strength) for (src, tgt), strength in _COUPLING.items() if src == current],
                key=lambda x: x[1],
                reverse=True,
            )
            for tgt, _ in outgoing:
                if tgt not in seen:
                    visited.append(tgt)
                    seen.add(tgt)
                    queue.append(tgt)

        # Ensure minimum depth of 4
        if len(visited) < 4:
            extras = [d for d in ["diplomatic", "sanctions", "energy", "finance", "trade"] if d not in seen]
            for d in extras:
                if len(visited) >= 4:
                    break
                visited.append(d)
                seen.add(d)

        return visited

    # ------------------------------------------------------------------
    # PropagationStep construction
    # ------------------------------------------------------------------

    def _build_domain_sequence(
        self,
        causal_chain: list[str],
        domain_tags: list[str],
        velocity_data: dict[str, float],
        global_velocity: float,
    ) -> list[PropagationStep]:
        """
        Convert a causal domain chain into an ordered list of
        ``PropagationStep`` objects.

        Steps are sorted by time_bucket (ascending temporal order), then
        by coupling strength for steps in the same bucket.
        """
        steps: list[PropagationStep] = []
        for i, domain in enumerate(causal_chain):
            # Compute per-domain velocity
            domain_vel = float(velocity_data.get(domain, global_velocity))
            bucket = self._assign_time_bucket(i, domain, domain_vel)
            event_text = _domain_event(domain, i)
            steps.append(
                PropagationStep(
                    step=i + 1,
                    domain=domain,
                    event=event_text,
                    time_bucket=bucket,
                )
            )

        # Sort by temporal order, then by coupling strength (domain position)
        steps.sort(
            key=lambda s: (
                _TIME_BUCKET_ORDER.index(s.time_bucket),
                _domain_coupling_strength(s.domain),
            )
        )

        # Re-number steps after sort
        for idx, step in enumerate(steps):
            step.step = idx + 1

        return steps

    # ------------------------------------------------------------------
    # Time-bucket assignment
    # ------------------------------------------------------------------

    def _assign_time_bucket(
        self, step_index: int, domain: str, velocity: float
    ) -> str:
        """
        Assign a time_bucket to a propagation step.

        Logic:
        - Step 0 (the initiating domain) is always T+0.
        - Subsequent steps use the default bucket from the propagation graph
          for transitions into this domain; if no entry exists the bucket
          advances by one position per step.
        - High velocity (≥0.7) promotes a step one bucket earlier.
        - Low velocity (≤0.2) demotes a step one bucket later.
        """
        if step_index == 0:
            return "T+0"

        # Derive bucket from canonical graph: look for an incoming edge to this domain
        incoming_bucket: str | None = None
        for (src, tgt), bucket in _DEFAULT_BUCKET.items():
            if tgt == domain:
                incoming_bucket = bucket
                break

        if incoming_bucket is None:
            # No canonical edge — advance one position per step
            bucket_idx = min(step_index, len(_TIME_BUCKET_ORDER) - 1)
            base_bucket = _TIME_BUCKET_ORDER[bucket_idx]
        else:
            base_bucket = incoming_bucket

        bucket_idx = _TIME_BUCKET_ORDER.index(base_bucket)

        # Velocity adjustment
        if velocity >= 0.7:
            bucket_idx = max(0, bucket_idx - 1)
        elif velocity <= 0.2:
            bucket_idx = min(len(_TIME_BUCKET_ORDER) - 1, bucket_idx + 1)

        return _TIME_BUCKET_ORDER[bucket_idx]

    # ------------------------------------------------------------------
    # Bottleneck detection
    # ------------------------------------------------------------------

    def _detect_bottlenecks(
        self, sequence: list[PropagationStep], graph_data: dict
    ) -> list[str]:
        """
        Identify chokepoints and rate-limiting factors in the propagation chain.

        Bottleneck sources:
        1. High-centrality nodes: domains that appear in multiple propagation paths
           in the canonical graph (detected by in-degree).
        2. Explicit KG paths with high coupling strength (strength ≥ 0.7).
        3. Domains with low default velocity — these form time-compression
           bottlenecks when multiple upstream shocks arrive simultaneously.
        """
        bottlenecks: list[str] = []
        seen_bottlenecks: set[str] = set()

        # In-degree from canonical graph
        in_degree: dict[str, int] = {}
        for (_, tgt), _ in _COUPLING.items():
            in_degree[tgt] = in_degree.get(tgt, 0) + 1

        for step in sequence:
            domain = step.domain

            # High in-degree → structural concentration bottleneck
            if in_degree.get(domain, 0) >= 2:
                msg = _BOTTLENECK_TEMPLATES.get(domain, _DEFAULT_BOTTLENECK)
                if msg not in seen_bottlenecks:
                    bottlenecks.append(msg)
                    seen_bottlenecks.add(msg)

        # KG-path bottlenecks
        for path in graph_data.get("kg_paths", []):
            strength = float(path.get("strength", 0.0))
            path_domain = path.get("domain", "")
            if strength >= 0.7 and path_domain in _ALLOWED_DOMAINS:
                msg = _BOTTLENECK_TEMPLATES.get(path_domain, _DEFAULT_BOTTLENECK)
                if msg not in seen_bottlenecks:
                    bottlenecks.append(msg)
                    seen_bottlenecks.add(msg)

        # Velocity bottleneck: slow domain with multiple upstream inputs
        velocity_data: dict[str, float] = graph_data.get("velocity_data", {})
        for step in sequence:
            vel = float(velocity_data.get(step.domain, 0.5))
            if vel <= 0.25 and in_degree.get(step.domain, 0) >= 1:
                msg = (
                    f"Low propagation velocity in {step.domain} domain creates "
                    "temporal bottleneck where upstream cascade energy accumulates"
                )
                if msg not in seen_bottlenecks:
                    bottlenecks.append(msg)
                    seen_bottlenecks.add(msg)

        # Always guarantee at least one bottleneck
        if not bottlenecks:
            domains_in_sequence = [s.domain for s in sequence]
            primary = domains_in_sequence[0] if domains_in_sequence else "cross-domain"
            bottlenecks.append(
                _BOTTLENECK_TEMPLATES.get(primary, _DEFAULT_BOTTLENECK)
            )

        return bottlenecks

    # ------------------------------------------------------------------
    # Second-order effect extraction
    # ------------------------------------------------------------------

    def _extract_second_order(
        self, sequence: list[PropagationStep], context: dict
    ) -> list[str]:
        """
        Derive downstream second-order effects from the propagation sequence.

        Sources:
        1. Domain-specific second-order entries for domains in the sequence.
        2. Generic cross-domain effects selected to fill a minimum of 3 items.
        """
        effects: list[str] = []
        seen: set[str] = set()

        # Domain-specific second-order effects for domains in sequence
        for step in sequence:
            domain_effect = _SECOND_ORDER_BY_DOMAIN.get(step.domain)
            if domain_effect and domain_effect not in seen:
                effects.append(domain_effect)
                seen.add(domain_effect)

        # Supplement with generic cross-domain effects up to 3 total
        for generic in _SECOND_ORDER_TEMPLATES:
            if len(effects) >= 3:
                break
            if generic not in seen:
                effects.append(generic)
                seen.add(generic)

        # Ensure minimum of 2 items (per acceptance criteria)
        if len(effects) < 2:
            for generic in _SECOND_ORDER_TEMPLATES:
                if generic not in seen:
                    effects.append(generic)
                    seen.add(generic)
                if len(effects) >= 2:
                    break

        return effects


# ---------------------------------------------------------------------------
# Helper: coupling strength for sort key
# ---------------------------------------------------------------------------


def _domain_coupling_strength(domain: str) -> float:
    """
    Return the maximum outgoing coupling strength for a domain in the
    canonical graph.  Used as a secondary sort key (higher strength →
    earlier in the sequence within the same time bucket).
    """
    strengths = [
        strength
        for (src, _), strength in _COUPLING.items()
        if src == domain
    ]
    return max(strengths) if strengths else 0.0
