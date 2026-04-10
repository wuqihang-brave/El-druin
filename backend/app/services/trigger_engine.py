"""
Trigger Amplification Engine
============================

Derives structurally-ranked trigger events from probability tree branch
weights, ontology propagation paths, and causal chain analysis.

Design principle
----------------
Triggers are ranked by ``amplification_factor`` — a measure of structural
nonlinear consequence derived from causal chain weights and Bayesian path
confidence.  They are **NOT** ranked by media salience, source count, or
recent-mention frequency.  This is a core intelligence moat differentiator.

Usage::

    from app.services.trigger_engine import TriggerAmplificationEngine

    engine = TriggerAmplificationEngine()
    output = await engine.compute_triggers(assessment_id, context)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.schemas.structural_forecast import TriggerOutput, TriggersOutput

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Jump potential taxonomy (per spec)
# ---------------------------------------------------------------------------

def _jump_potential(amplification_factor: float) -> str:
    """Map amplification_factor [0.0–1.0] to a categorical jump potential level."""
    if amplification_factor > 0.75:
        return "Critical"
    if amplification_factor >= 0.5:
        return "High"
    if amplification_factor >= 0.3:
        return "Medium"
    return "Low"


# ---------------------------------------------------------------------------
# Domain catalogue – PRD-vocabulary signals and damping opportunities
# ---------------------------------------------------------------------------

# Default lag hours by primary domain when velocity data is unavailable
_DOMAIN_LAG_HOURS: dict[str, int] = {
    "military":   6,
    "energy":    24,
    "insurance": 24,
    "finance":   48,
    "trade":     72,
    "sanctions": 48,
    "political": 48,
}

# Domain-specific watch signals using PRD vocabulary only
# (no raw probability notation)
_DOMAIN_WATCH_SIGNALS: dict[str, list[str]] = {
    "military": [
        "Escalation threshold approached via sequential force-posture signalling",
        "Cross-domain coupling to energy sector observable via transit corridor disruptions",
        "Regime shift precursor: rapid attribution signals from sequential military deployments",
    ],
    "energy": [
        "Propagation onset traceable through insurance-premium amplification in corridor markets",
        "Attractor decoupling from baseline throughput: transit-volume drop exceeding threshold",
        "Coupling intensification: spot-price divergence relative to seasonal corridor attractor",
    ],
    "insurance": [
        "Amplification via underwriter exit from risk pool, narrowing corridor coverage attractor",
        "Threshold crossover: war-risk premium exceeding regime-change level in Lloyd's market",
    ],
    "finance": [
        "Attribution signals: sovereign spread widening beyond escalation threshold",
        "Propagation coupling: correspondent-bank withdrawal cascades across regional attractor",
    ],
    "trade": [
        "Attractor shift detectable via re-routing volume amplification beyond threshold",
        "Regime-level disruption propagating through supply-chain coupling nodes",
    ],
    "sanctions": [
        "Escalation cascade observable through correspondent-banking attribution channel closures",
        "Regime intensification: pre-designation briefing signals upstream of formal announcement",
    ],
    "political": [
        "Escalation attractor: multilateral forum activation following bilateral channel breakdown",
        "Regime transition signal: emergency session convening within the threshold window",
    ],
}

_DEFAULT_WATCH_SIGNALS: list[str] = [
    "Escalation threshold proximity observable via cross-domain coupling signals",
    "Amplification onset traceable through structural attractor deviation patterns",
]

# Domain-specific damping opportunities using PRD vocabulary only
_DOMAIN_DAMPING: dict[str, list[str]] = {
    "military": [
        "Bilateral damping activation through direct hotline engagement between regime actors",
        "Coupling attenuation via neutral third-party maritime observer deployment",
        "Threshold roll-back through sequential de-escalation signalling from both sides",
    ],
    "energy": [
        "Attractor stabilisation via alternative corridor capacity announcement",
        "Propagation dampening through transit-guarantee framework agreed by corridor states",
        "Amplification attenuation: insurance market re-entry conditioned on ceasefire attractor",
    ],
    "insurance": [
        "Damping via sovereign war-risk backstop restoring market-attractor equilibrium",
        "Coupling reduction through coordinated underwriter re-entry into corridor risk pool",
    ],
    "finance": [
        "Propagation dampening via coordinated central-bank liquidity injection attractor",
        "Threshold stabilisation: multilateral credit-facility activation dampening spread escalation",
    ],
    "trade": [
        "Attractor restoration via alternative routing capacity exceeding threshold diversion volume",
        "Escalation damping through multilateral consultation mechanism activation",
    ],
    "sanctions": [
        "Coupling reduction through targeted carve-out agreement lowering attribution pressure",
        "Escalation damping via humanitarian-exemption framework agreed before threshold crossing",
    ],
    "political": [
        "Regime de-escalation via multilateral mediation channel activation by neutral attractor state",
        "Damping through confidence-building measure deployment before threshold breach",
    ],
}

_DEFAULT_DAMPING: list[str] = [
    "Damping via coordinated multi-party threshold management agreement",
    "Coupling attenuation through structured de-escalation framework activation",
]


# ---------------------------------------------------------------------------
# Lazy loader for ProbabilityTreeBuilder
# ---------------------------------------------------------------------------

def _load_default_prob_tree() -> Optional[Any]:
    try:
        from intelligence.probability_tree import ProbabilityTreeBuilder  # type: ignore
        return ProbabilityTreeBuilder()
    except Exception as exc:
        logger.debug("ProbabilityTreeBuilder unavailable: %s", exc)
        return None


# ---------------------------------------------------------------------------
# TriggerAmplificationEngine
# ---------------------------------------------------------------------------

class TriggerAmplificationEngine:
    """
    Derives structurally-ranked trigger amplification scores.

    Triggers are ranked by ``amplification_factor`` (structural nonlinear
    consequence derived from causal chain weights and Bayesian path confidence),
    **not** by media salience, source count, or recent-mention frequency.

    Args:
        probability_tree: Optional pre-built ``ProbabilityTreeBuilder`` instance.
            If ``None``, one is constructed automatically.
        ontology_forecaster: Optional callable accepting ``initial_patterns`` list;
            currently reserved for future phase-transition weighting.
        multi_agent: Optional ``MultiAgentEngine`` instance; reserved for
            cross-agent confidence aggregation.
    """

    def __init__(
        self,
        probability_tree: Optional[Any] = None,
        ontology_forecaster: Optional[Any] = None,
        multi_agent: Optional[Any] = None,
    ) -> None:
        self._prob_tree = probability_tree if probability_tree is not None else _load_default_prob_tree()
        self._forecaster = ontology_forecaster
        self._multi_agent = multi_agent

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def compute_triggers(
        self, assessment_id: str, context: dict
    ) -> TriggersOutput:
        """
        Compute structurally-ranked triggers from assessment context.

        The context dict may contain:

        * ``events`` – list of event dicts (name, text, domains, entities,
          source_reliability, causal_weight)
        * ``kg_paths`` – list of KG propagation path dicts
          (from_entity, to_entity, relation, domain, strength)
        * ``causal_weights`` – dict mapping trigger name → structural causal weight
        * ``velocity_data`` – dict mapping domain → velocity score (0.0–1.0)
        * ``ontology_activations`` – dict mapping pattern name → activation score
        * ``regime_state`` – dict with regime, damping_capacity, reversibility_index

        Returns:
            ``TriggersOutput`` with triggers sorted by amplification_factor descending.
        """
        events: list[dict] = context.get("events", [])
        kg_paths: list[dict] = context.get("kg_paths", [])
        causal_weights: dict[str, float] = context.get("causal_weights", {})
        velocity_data: dict[str, float] = context.get("velocity_data", {})
        ontology_activations: dict[str, float] = context.get("ontology_activations", {})
        regime_state: dict = context.get("regime_state", {})

        triggers: list[TriggerOutput] = []
        for event in events:
            text = event.get("text") or event.get("title", "")
            reliability = float(event.get("source_reliability", 0.75))

            # Build probability tree once per event; reuse for both amp and confidence
            causal_branch_weight, tree_confidence = self._compute_tree_scores(
                text, reliability
            )

            amp = self._score_amplification(event, causal_weights, causal_branch_weight)
            confidence = float(event.get("confidence", tree_confidence))

            domains = self._identify_impacted_domains(event, kg_paths)
            lag = self._estimate_lag_hours(event, velocity_data)
            watch_signals = self._extract_watch_signals(event, ontology_activations)
            damping_opps = self._extract_damping_opportunities(event, regime_state)

            triggers.append(
                TriggerOutput(
                    name=event.get("name") or event.get("title", "Unknown trigger"),
                    amplification_factor=round(min(1.0, max(0.0, amp)), 3),
                    jump_potential=_jump_potential(amp),
                    impacted_domains=domains,
                    expected_lag_hours=lag,
                    confidence=round(min(1.0, max(0.0, confidence)), 3),
                    watch_signals=watch_signals,
                    damping_opportunities=damping_opps,
                )
            )

        # Sort by amplification_factor descending — structural ranking, not media frequency
        triggers.sort(key=lambda t: t.amplification_factor, reverse=True)

        return TriggersOutput(
            assessment_id=assessment_id,
            triggers=triggers,
            updated_at=datetime.now(tz=timezone.utc),
        )

    # ------------------------------------------------------------------
    # Probability tree helpers
    # ------------------------------------------------------------------

    def _compute_tree_scores(
        self, text: str, reliability: float
    ) -> tuple[float, float]:
        """
        Build a probability tree for the given text and extract
        ``(causal_branch_weight, best_branch_confidence)``.

        Returns default ``(0.5, reliability * 0.7)`` when the tree builder is
        unavailable or the text is empty.
        """
        if self._prob_tree is None or not text:
            return 0.5, round(reliability * 0.7, 4)

        try:
            tree = self._prob_tree.build_tree(text, reliability)
            causal_branch = next(
                (b for b in tree.interpretation_branches if b.branch_id == 1),
                None,
            )
            causal_weight = causal_branch.weight if causal_branch is not None else 0.5

            if tree.interpretation_branches:
                best = max(tree.interpretation_branches, key=lambda b: b.weight)
                conf = round(best.confidence * reliability, 4)
            else:
                conf = round(reliability * 0.5, 4)

            return causal_weight, conf
        except Exception as exc:
            logger.debug("Probability tree computation failed: %s", exc)
            return 0.5, round(reliability * 0.7, 4)

    # ------------------------------------------------------------------
    # Amplification scoring
    # ------------------------------------------------------------------

    def _score_amplification(
        self,
        trigger_event: dict,
        causal_weights: dict[str, float],
        causal_branch_weight: float = 0.5,
    ) -> float:
        """
        Derive amplification_factor from the causal-relationship branch weight
        of the probability tree, blended with any externally provided KG causal
        weight.

        The causal branch weight is the structural proxy — it reflects how
        strongly the event text exhibits causal relationship language, scaled by
        source reliability.  It is **not** a media-frequency or source-count
        measure.

        Domain multipliers add a small structural boost for domains with
        historically higher nonlinear propagation potential.
        """
        base_score = causal_branch_weight

        # Blend with externally supplied KG-derived causal weight when available
        name = trigger_event.get("name") or trigger_event.get("title", "")
        external = causal_weights.get(name, 0.0)
        if external > 0.0:
            # External structural weight provides partial grounding correction
            base_score = 0.6 * base_score + 0.4 * external

        # Small structural domain multiplier for historically high-amplification domains
        primary_domain = _primary_domain(trigger_event)
        domain_boost: dict[str, float] = {
            "military":  0.15,
            "sanctions": 0.10,
            "energy":    0.08,
            "finance":   0.05,
        }
        base_score += domain_boost.get(primary_domain, 0.0)

        return min(1.0, base_score)

    # ------------------------------------------------------------------
    # Domain identification
    # ------------------------------------------------------------------

    def _identify_impacted_domains(
        self, trigger: dict, kg_paths: list[dict]
    ) -> list[str]:
        """
        Identify domains impacted by this trigger.

        Sources (in priority order):
        1. Explicit ``domains`` list on the event dict.
        2. KG propagation paths whose ``from_entity`` is involved in this
           trigger, or whose edge strength ≥ 0.6.
        """
        domains: list[str] = list(trigger.get("domains") or [])
        trigger_entities: set[str] = set(trigger.get("entities") or [])

        for path in kg_paths:
            if (
                path.get("from_entity") in trigger_entities
                or float(path.get("strength", 0)) >= 0.6
            ):
                path_domain = path.get("domain")
                if path_domain and path_domain not in domains:
                    domains.append(path_domain)

        # Deduplicate while preserving insertion order
        seen: set[str] = set()
        result: list[str] = []
        for d in domains:
            if d not in seen:
                seen.add(d)
                result.append(d)
        return result or ["general"]

    # ------------------------------------------------------------------
    # Lag estimation
    # ------------------------------------------------------------------

    def _estimate_lag_hours(
        self, trigger: dict, velocity_data: dict[str, float]
    ) -> int:
        """
        Estimate hours until impact manifests.

        Derived from event velocity (if available in ``velocity_data``) or
        domain-specific ontology temporal defaults.  Higher velocity shortens
        the lag; at velocity = 1.0 the lag is halved relative to the default.
        """
        primary_domain = _primary_domain(trigger)
        default_lag = _DOMAIN_LAG_HOURS.get(primary_domain, 48)

        velocity = float(velocity_data.get(primary_domain, 0.0))
        if velocity > 0.0:
            lag = int(default_lag * (1.0 - 0.5 * min(velocity, 1.0)))
            return max(1, lag)

        return default_lag

    # ------------------------------------------------------------------
    # Watch signals
    # ------------------------------------------------------------------

    def _extract_watch_signals(
        self, trigger: dict, ontology_activations: dict[str, float]
    ) -> list[str]:
        """
        Derive observable precursor signals using PRD vocabulary.

        Base signals are drawn from the domain catalogue.  Additional signals
        are appended for ontology patterns whose activation score is at or
        above the near-threshold level (0.65).
        """
        primary_domain = _primary_domain(trigger)
        signals: list[str] = list(
            _DOMAIN_WATCH_SIGNALS.get(primary_domain, _DEFAULT_WATCH_SIGNALS)
        )

        _NEAR_THRESHOLD = 0.65
        near_threshold = sorted(
            ((pat, score) for pat, score in ontology_activations.items() if score >= _NEAR_THRESHOLD),
            key=lambda x: x[1],
            reverse=True,
        )
        for pat, _ in near_threshold[:2]:
            signal = (
                f"Escalation attractor approaching regime threshold: "
                f"coupling propagation via {pat} activation pathway"
            )
            if signal not in signals:
                signals.append(signal)

        return signals[:4]  # cap at 4 per trigger

    # ------------------------------------------------------------------
    # Damping opportunities
    # ------------------------------------------------------------------

    def _extract_damping_opportunities(
        self, trigger: dict, regime_state: dict
    ) -> list[str]:
        """
        Identify conditions that would dampen this trigger's effect.

        Base opportunities come from the domain catalogue.  A structural
        attractor reversibility opportunity is appended when the regime
        reversibility_index indicates sufficient residual damping headroom.
        """
        primary_domain = _primary_domain(trigger)
        opps: list[str] = list(
            _DOMAIN_DAMPING.get(primary_domain, _DEFAULT_DAMPING)
        )

        reversibility = float(regime_state.get("reversibility_index", 0.0))
        if reversibility >= 0.4:
            opps.append(
                "Structural attractor reversibility sufficient for coordinated "
                "damping intervention before threshold cascade onset"
            )

        return opps[:3]  # cap at 3 per trigger


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------

def _primary_domain(event: dict) -> str:
    """Return the first domain tag of an event, or empty string if none."""
    domains = event.get("domains") or []
    return domains[0] if domains else ""
