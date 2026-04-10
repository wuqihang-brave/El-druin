"""
Attractor Engine
================

Computes candidate future attractor states by adapting outputs from the
ontology forecaster into the normalized AttractorsOutput schema.

Each attractor represents a converging future state the system may lock into.
pull_strength is derived from scenario branch probability × structural alignment.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from app.schemas.structural_forecast import AttractorOutput, AttractorsOutput

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Trend store – in-memory within a single process lifetime
# ---------------------------------------------------------------------------
_pull_strength_history: Dict[str, float] = {}


# ---------------------------------------------------------------------------
# Canonical attractor taxonomy
# ---------------------------------------------------------------------------

_CANONICAL_ATTRACTORS: List[Dict[str, Any]] = [
    {
        "id": "sanctions_cascade",
        "name": "Sanctions Cascade",
        "keywords": ["sanction", "financial isolation", "multilateral", "swift", "exclusion", "coalition"],
        "counterforces": [
            "Multilateral sanctions require sustained coalition cohesion to remain effective",
            "Secondary sanction compliance pressure weakens as economic interdependence persists",
        ],
        "invalidation_conditions": [
            "Coalition fragmentation removes the critical threshold of participating states",
            "Negotiated exemption framework agreed before full cascade activation",
        ],
        "horizon_default": "3-10d",
    },
    {
        "id": "proxy_escalation",
        "name": "Proxy Escalation",
        "keywords": ["proxy", "indirect", "militia", "coercion", "coerce", "alliance"],
        "counterforces": [
            "Proxy actor autonomy limits principal-agent escalation control",
            "Deterrence threshold constrains direct engagement authorization",
        ],
        "invalidation_conditions": [
            "Principal withdraws materiel support and political cover from proxy actors",
            "Ceasefire framework agreed encompassing proxy forces",
        ],
        "horizon_default": "2-4w",
    },
    {
        "id": "transport_disruption",
        "name": "Transport Disruption",
        "keywords": [
            "transport", "shipping", "logistics", "supply", "corridor",
            "transit", "energy", "tanker", "maritime", "strait",
        ],
        "counterforces": [
            "Alternative routing options absorb partial demand shock and constrain escalation convergence",
            "Insurance market intervention can restore confidence for corridor operators",
        ],
        "invalidation_conditions": [
            "Full corridor reopening confirmed and insurance coverage restored",
            "Naval assets withdrawn and security guarantee ratified by transit parties",
        ],
        "horizon_default": "3-10d",
    },
    {
        "id": "deterrence_stabilization",
        "name": "Deterrence Stabilization",
        "keywords": ["deterrence", "stabilization", "stabilise", "credible", "signal", "de-escalation"],
        "counterforces": [
            "Credibility gaps undermine deterrence signal reception by adversary",
            "Domestic political constraints prevent decisive posture signaling",
        ],
        "invalidation_conditions": [
            "Deterrence threshold crossed by adversary action before stabilization regime locks in",
            "Alliance cohesion fractures under cost-sharing disagreement",
        ],
        "horizon_default": "2-4w",
    },
    {
        "id": "diplomatic_containment",
        "name": "Diplomatic Containment",
        "keywords": ["diplomatic", "containment", "negotiation", "mediation", "multilateral", "agreement"],
        "counterforces": [
            "Ongoing kinetic operations reduce negotiating space for containment",
            "Spoiler actors reject containment framework terms",
        ],
        "invalidation_conditions": [
            "Escalation crosses threshold that renders diplomatic containment irrelevant",
            "Key mediator state withdraws facilitation role",
        ],
        "horizon_default": "2-6w",
    },
    {
        "id": "market_normalization",
        "name": "Market Normalization",
        "keywords": ["market", "normalization", "risk premium", "baseline", "dissipation", "financial"],
        "counterforces": [
            "Structural coupling between financial and geopolitical regimes delays normalization",
            "Persistent uncertainty prevents risk premium from dissipating fully",
        ],
        "invalidation_conditions": [
            "New escalation event resets risk premium before normalization convergence",
            "Contagion from adjacent market disruption sustains volatility regime",
        ],
        "horizon_default": "4-12w",
    },
]


def _match_canonical(name: str, domain: str) -> Optional[Dict[str, Any]]:
    """Match an attractor name/domain to a canonical taxonomy entry."""
    name_lower = name.lower()
    domain_lower = domain.lower()

    best_match: Optional[Dict[str, Any]] = None
    best_score = 0

    for canonical in _CANONICAL_ATTRACTORS:
        score = sum(2 for kw in canonical["keywords"] if kw in name_lower or kw in domain_lower)
        if score > best_score:
            best_score = score
            best_match = canonical

    return best_match if best_score >= 2 else None


def _domain_counterforces(domain: str) -> List[str]:
    """Return generic domain-appropriate counterforces."""
    d = domain.lower()
    if "military" in d or "geopolit" in d:
        return [
            "Escalation cost calculus constrains offensive tempo",
            "Alliance commitment triggers tripwire deterrence",
        ]
    if "economic" in d or "finance" in d or "sanction" in d:
        return [
            "Interdependence costs discipline escalation pathway",
            "Institutional resistance slows regime coupling transition",
        ]
    if "energy" in d or "trade" in d:
        return [
            "Alternative supply routes absorb partial demand shock",
            "Strategic reserve drawdowns buffer short-term supply gap",
        ]
    return [
        "Threshold dynamics constrain convergence velocity",
        "System damping capacity resists full attractor lock-in",
    ]


def _domain_invalidation(attractor_name: str, domain: str) -> List[str]:
    """Return generic domain-appropriate invalidation conditions."""
    name_lower = attractor_name.lower()
    d = domain.lower()
    if "military" in d or "geopolit" in d:
        return [
            "Ceasefire or mutual de-escalation agreement removes kinetic pressure",
            "External actor intervention changes the force balance decisively",
        ]
    if "sanction" in name_lower or "finance" in d:
        return [
            "Sanctions coalition fractures below effectiveness threshold",
            "Negotiated diplomatic offramp accepted before full cascade",
        ]
    if "energy" in d or "transport" in name_lower:
        return [
            "Full corridor reopening confirmed and insurance coverage restored",
            "Alternative routing reduces strategic pressure below critical threshold",
        ]
    return [
        "Structural shock reverses convergence trajectory before attractor lock-in",
        "Counterforce exceeds pull strength, redirecting regime toward alternative state",
    ]


class AttractorEngine:
    """
    Derives candidate future attractor states from the ontology forecaster,
    normalized to the AttractorsOutput schema.
    """

    def __init__(
        self,
        ontology_forecaster: Any = None,
        evented_pipeline: Any = None,
        probability_tree: Any = None,
    ) -> None:
        self._ontology_forecaster = ontology_forecaster
        self._evented_pipeline = evented_pipeline
        self._probability_tree = probability_tree

    async def compute_attractors(
        self,
        assessment_id: str,
        context: dict,
    ) -> AttractorsOutput:
        """
        Compute AttractorsOutput from ontology forecaster outputs.

        Falls back to canonical stubs if the engine cannot run.
        """
        try:
            attractors = self._run_engine(assessment_id, context)
        except Exception as exc:
            logger.warning(
                "AttractorEngine: engine run failed for %s: %s — using fallback",
                assessment_id,
                exc,
            )
            attractors = []

        if len(attractors) < 2:
            attractors = self._fallback_attractors(assessment_id, context, existing=attractors)

        attractors.sort(key=lambda a: a.pull_strength, reverse=True)

        return AttractorsOutput(
            assessment_id=assessment_id,
            attractors=attractors,
            updated_at=datetime.now(tz=timezone.utc),
        )

    # ------------------------------------------------------------------
    # Internal engine

    def _run_engine(self, assessment_id: str, context: dict) -> List[AttractorOutput]:
        """Core engine: pull attractors from the ontology forecaster."""
        from intelligence.ontology_forecaster import (  # type: ignore
            find_attractors,
            run_forecast,
        )

        domain_tags: List[str] = context.get("domain_tags", [])

        # Map assessment domain tags to ontology domain vocabulary
        if "military" in domain_tags or "sanctions" in domain_tags:
            ontology_domain = "geopolitics"
        elif "energy" in domain_tags or "finance" in domain_tags or "trade" in domain_tags:
            ontology_domain = "economics"
        else:
            ontology_domain = "geopolitics"

        # 1. Static attractors from the composition semi-group
        raw_attractors = find_attractors(domain=ontology_domain)
        if not raw_attractors:
            raw_attractors = find_attractors(domain="all")

        # 2. Forward simulation using scenario patterns
        initial_patterns = context.get("initial_patterns") or self._select_scenario_patterns(domain_tags)

        forecast_result: Dict[str, Any] = {}
        if initial_patterns:
            try:
                forecast_result = run_forecast(initial_patterns, horizon_steps=6)
            except Exception as exc:
                logger.warning("AttractorEngine: run_forecast failed: %s", exc)

        # 3. Merge forecast attractors with static attractors
        seen_names: set = set()
        merged: List[Dict[str, Any]] = []

        for a in forecast_result.get("attractors", []):
            if a.get("name") and a["name"] not in seen_names:
                seen_names.add(a["name"])
                merged.append({**a, "_source": "forecast"})

        pa = forecast_result.get("primary_attractor", {})
        if pa and pa.get("name") and pa["name"] not in seen_names:
            seen_names.add(pa["name"])
            merged.append({**pa, "_source": "primary"})

        for a in raw_attractors:
            if a.get("name") and a["name"] not in seen_names:
                seen_names.add(a["name"])
                merged.append({**a, "_source": "static"})

        # 4. Compute structural alignment
        meta = forecast_result.get("meta", {})
        velocity = self._estimate_velocity(forecast_result)
        base_confidence = float(meta.get("initial_confidence", 0.5))
        structural_alignment = min(1.0, max(0.0, base_confidence * (1.0 - velocity * 0.4)))

        # 5. Build AttractorOutput objects (cap at 6, deduplicate by display name)
        evidence_count = int(context.get("evidence_count", 0))
        result: List[AttractorOutput] = []
        seen_display_names: set = set()

        for a in merged:
            if len(result) >= 6:
                break
            name = a.get("name") or "Unknown State"
            # Skip unresolved placeholder names from the forecaster
            if name.startswith("(") or name in ("unknown", "Unknown State"):
                continue
            domain_str = a.get("domain") or ontology_domain
            raw_prob = float(a.get("final_probability", a.get("probability", 0.5)))

            pull = self._compute_pull_strength(a, structural_alignment)
            horizon = self._estimate_horizon(a, velocity)
            canonical = _match_canonical(name, domain_str)

            if canonical:
                display_name = canonical["name"]
                counterforces = list(canonical["counterforces"])
                invalidation = list(canonical["invalidation_conditions"])
            else:
                display_name = name
                counterforces = _domain_counterforces(domain_str)
                invalidation = _domain_invalidation(name, domain_str)

            # Skip duplicate display names
            if display_name in seen_display_names:
                continue
            seen_display_names.add(display_name)

            supporting_count = max(1, int(evidence_count * pull) + max(1, int(raw_prob * 5)))

            trend = self._compute_trend(f"{assessment_id}:{display_name}", pull)

            result.append(
                AttractorOutput(
                    name=display_name,
                    pull_strength=round(pull, 3),
                    horizon=horizon,
                    supporting_evidence_count=supporting_count,
                    counterforces=counterforces,
                    invalidation_conditions=invalidation,
                    trend=trend,
                )
            )

        return result

    def _select_scenario_patterns(self, domain_tags: List[str]) -> List[str]:
        """Select initial patterns from preset scenarios matching domain tags."""
        try:
            from intelligence.ontology_forecaster import (  # type: ignore
                get_preset_scenarios,
                get_scenario_by_id,
            )
        except Exception:
            return []

        domain_map = {
            "military": "geopolitics",
            "sanctions": "geopolitics",
            "energy": "economics",
            "finance": "economics",
            "trade": "economics",
        }
        target_domains = {domain_map.get(t, t) for t in domain_tags}

        try:
            scenarios = get_preset_scenarios()
        except Exception:
            return []

        for sc in scenarios:
            if sc.get("domain") in target_domains:
                try:
                    raw_sc = get_scenario_by_id(sc["id"])
                    if raw_sc:
                        return raw_sc["initial_patterns"]
                except Exception:
                    pass

        if scenarios:
            try:
                raw_sc = get_scenario_by_id(scenarios[0]["id"])
                if raw_sc:
                    return raw_sc["initial_patterns"]
            except Exception:
                pass

        return []

    def _estimate_velocity(self, forecast_result: Dict[str, Any]) -> float:
        """Estimate normalized event velocity from simulation delta norms."""
        steps = forecast_result.get("simulation_steps", [])
        if not steps:
            return 0.5
        delta_norms = [float(s.get("delta_norm", 0.0)) for s in steps]
        mean_delta = sum(delta_norms) / len(delta_norms)
        # _PHASE_THRESHOLD = 0.25 in ontology_forecaster; normalize against it
        return min(1.0, mean_delta / 0.25)

    def _compute_pull_strength(self, scenario: dict, structural_alignment: float) -> float:
        """
        Derive pull_strength from scenario probability × structural alignment.

        pull = base_prob × (0.5 + 0.5 × alignment)
        Bounded to [0.05, 0.95] to avoid degenerate extremes.
        """
        base_prob = float(scenario.get("final_probability", scenario.get("probability", 0.5)))
        factor = 0.5 + 0.5 * max(0.0, min(1.0, structural_alignment))
        return max(0.05, min(0.95, base_prob * factor))

    def _estimate_horizon(self, scenario: dict, velocity: float) -> str:
        """
        Estimate time horizon from attractor step count and event velocity.

        High velocity (fast-moving events) compresses the horizon.
        """
        first_step = int(scenario.get("first_step", 3))

        if first_step <= 2:
            base_min, base_max, unit = 3, 10, "d"
        elif first_step <= 4:
            base_min, base_max, unit = 2, 6, "w"
        else:
            base_min, base_max, unit = 4, 12, "w"

        if velocity > 0.7:
            base_min = max(1, base_min - 1)
            base_max = max(2, base_max - 2)
        elif velocity < 0.3:
            base_max = base_max + 2

        return f"{base_min}-{base_max}{unit}"

    def _extract_counterforces(self, scenario: dict, damping_data: dict) -> List[str]:
        """Extract counterforces from scenario data and damping information."""
        return _domain_counterforces(scenario.get("domain", "general"))[:2]

    def _generate_invalidation_conditions(self, scenario: dict) -> List[str]:
        """Generate invalidation conditions from scenario data."""
        return _domain_invalidation(scenario.get("name", ""), scenario.get("domain", "general"))

    def _compute_trend(
        self,
        attractor_key: str,
        current_pull: float,
    ) -> Literal["up", "down", "stable"]:
        """
        Compare current pull_strength vs. prior run for trend direction.
        Defaults to 'stable' on first run (no prior state available).
        """
        prior = _pull_strength_history.get(attractor_key)
        _pull_strength_history[attractor_key] = current_pull
        if prior is None:
            return "stable"
        diff = current_pull - prior
        if diff > 0.05:
            return "up"
        if diff < -0.05:
            return "down"
        return "stable"

    # ------------------------------------------------------------------
    # Fallback

    def _fallback_attractors(
        self,
        assessment_id: str,
        context: dict,
        existing: List[AttractorOutput],
    ) -> List[AttractorOutput]:
        """
        Guarantee at least 2 attractors by supplementing with canonical defaults
        appropriate for the assessment context.
        """
        existing_names = {a.name for a in existing}
        result: List[AttractorOutput] = list(existing)
        domain_tags = context.get("domain_tags", [])

        has_energy = "energy" in domain_tags
        has_military = "military" in domain_tags
        has_sanctions = "sanctions" in domain_tags or "finance" in domain_tags

        candidates: List[AttractorOutput] = []

        if has_energy or has_military:
            candidates.append(
                AttractorOutput(
                    name="Transport Disruption",
                    pull_strength=0.72,
                    horizon="3-10d",
                    supporting_evidence_count=8,
                    counterforces=[
                        "Alternative routing options constrain escalation convergence",
                        "Insurance market intervention restores confidence for corridor operators",
                    ],
                    invalidation_conditions=[
                        "Full corridor reopening confirmed and insurance coverage restored",
                        "Naval assets withdrawn and security guarantee ratified",
                    ],
                    trend=self._compute_trend(f"{assessment_id}:Transport Disruption", 0.72),
                )
            )

        if has_sanctions or has_military:
            candidates.append(
                AttractorOutput(
                    name="Diplomatic Containment",
                    pull_strength=0.45,
                    horizon="2-6w",
                    supporting_evidence_count=5,
                    counterforces=[
                        "Ongoing kinetic operations reduce negotiating space for containment",
                        "Spoiler actors reject containment framework terms",
                    ],
                    invalidation_conditions=[
                        "Escalation crosses threshold that renders diplomatic containment irrelevant",
                        "Key mediator state withdraws facilitation role",
                    ],
                    trend=self._compute_trend(f"{assessment_id}:Diplomatic Containment", 0.45),
                )
            )

        # Generic fallbacks if still insufficient
        if not candidates:
            candidates = [
                AttractorOutput(
                    name="Deterrence Stabilization",
                    pull_strength=0.58,
                    horizon="2-4w",
                    supporting_evidence_count=6,
                    counterforces=[
                        "Credibility gaps undermine deterrence signal reception",
                        "Domestic political constraints prevent decisive posture signaling",
                    ],
                    invalidation_conditions=[
                        "Deterrence threshold crossed before stabilization locks in",
                        "Alliance cohesion fractures under cost-sharing disagreement",
                    ],
                    trend=self._compute_trend(f"{assessment_id}:Deterrence Stabilization", 0.58),
                ),
                AttractorOutput(
                    name="Sanctions Cascade",
                    pull_strength=0.41,
                    horizon="3-10d",
                    supporting_evidence_count=4,
                    counterforces=[
                        "Multilateral sanctions require sustained coalition cohesion",
                        "Secondary sanction compliance pressure reduces with economic interdependence",
                    ],
                    invalidation_conditions=[
                        "Coalition fragmentation removes critical threshold of participating states",
                        "Negotiated exemption framework agreed before full activation",
                    ],
                    trend=self._compute_trend(f"{assessment_id}:Sanctions Cascade", 0.41),
                ),
            ]

        for c in candidates:
            if c.name not in existing_names:
                result.append(c)
                existing_names.add(c.name)
                if len(result) >= 2:
                    break

        return result
