"""
assessments_patch.py
====================

Drop-in replacements for the degenerate fallback context builder and
probability-tree text builder in assessments.py / intelligence.py.
"""

from __future__ import annotations

from typing import Any

_RICH_EVENT_TEMPLATES: dict[str, list[tuple[str, str]]] = {
    "energy": [
        (
            "Energy transit corridor disruption",
            (
                "Pipeline pressure anomalies confirmed across the primary transit corridor, "
                "causing spot-market prices to spike sharply as traders price in supply "
                "uncertainty. Insurance market withdrawal from corridor shipments has directly "
                "caused downstream trade-finance disruption, triggering emergency reserve "
                "drawdown protocols in downstream states."
            ),
        ),
        (
            "Emergency reserve drawdown activated",
            (
                "Governments in the affected region have authorised emergency strategic "
                "reserve releases after supply volumes fell below the 30-day threshold, "
                "indicating the disruption is structural rather than temporary. The causal "
                "chain from supply shortfall to reserve depletion confirms the nonlinear "
                "escalation trajectory is already in motion."
            ),
        ),
    ],
    "military": [
        (
            "Force repositioning detected",
            (
                "Satellite imagery and open-source analysis confirm repositioning of military "
                "assets toward the contested boundary, directly causing alliance partners to "
                "convene emergency consultations. The capability demonstration has triggered "
                "a proportional readiness escalation that, if sustained, will cascade into "
                "diplomatic channel breakdown within 72 hours."
            ),
        ),
        (
            "Alliance consultation threshold breached",
            (
                "Emergency alliance consultations convened following confirmation of force "
                "repositioning, with partners debating Article 5 applicability thresholds. "
                "The contradiction between stated de-escalatory intent and observed military "
                "posture has undermined confidence in diplomatic back-channels, narrowing the "
                "intervention window."
            ),
        ),
    ],
    "sanctions": [
        (
            "Secondary sanctions package expansion signalled",
            (
                "Pre-designation briefings circulating in financial capitals indicate a "
                "secondary sanctions package targeting corridor financial institutions is "
                "imminent, directly causing correspondent banking withdrawal to accelerate "
                "before formal announcement. This causal sequence confirms the escalatory "
                "ladder observed in prior sanctions rounds."
            ),
        ),
        (
            "Correspondent banking withdrawal accelerating",
            (
                "Major international correspondent banks have issued withdrawal notices to "
                "regional counterparts, triggering a liquidity crunch that contradicts "
                "official statements of continued financial access. The structural isolation "
                "is now self-reinforcing: withdrawal causes further withdrawal as counterparty "
                "risk assessment models update in real time."
            ),
        ),
    ],
    "finance": [
        (
            "Sovereign spread widening beyond stress threshold",
            (
                "Five-year sovereign CDS spreads have widened beyond the historical stress "
                "threshold, directly causing capital outflow acceleration as institutional "
                "investors re-weight regional exposure. The causal link between spread "
                "widening and reserve depletion is now operating on a sub-48-hour cycle, "
                "compressing the policy response window."
            ),
        ),
        (
            "Currency support operation detected",
            (
                "Central bank reserve data indicates a currency support operation was "
                "activated overnight. The contradiction between intervention scale and "
                "publicly stated reserve adequacy figures raises questions about remaining "
                "ammunition for future stabilisation."
            ),
        ),
    ],
    "technology": [
        (
            "Export control entity list expansion confirmed",
            (
                "Commerce Department entity list additions targeting semiconductor supply "
                "chain actors have directly caused procurement contract renegotiations. "
                "Allied jurisdiction mirroring of the controls within 48 hours confirms a "
                "coordinated escalation intent, triggering emergency sourcing reviews in "
                "downstream industrial sectors."
            ),
        ),
        (
            "Supply chain fragmentation threshold crossed",
            (
                "Lead time monitoring data confirms supply chain fragmentation has crossed "
                "the structural threshold beyond which near-term recovery is not feasible "
                "without government intervention. The causal chain from export controls to "
                "industrial capacity reduction is now operating across multiple tiers."
            ),
        ),
    ],
    "trade": [
        (
            "Trade route chokepoint congestion critical",
            (
                "Port congestion indices at the primary chokepoint have reached critical "
                "levels, directly causing shipping insurance premiums to spike and triggering "
                "emergency rerouting decisions by major carriers. The causal link between "
                "route disruption and consumer price pressure will manifest within two to "
                "three weeks given current inventory buffer levels."
            ),
        ),
        (
            "Strategic stockpile drawdown orders issued",
            (
                "Multiple governments have issued strategic stockpile drawdown orders for "
                "trade-critical commodities. The contradiction between stated short-term "
                "disruption framing and the structural nature of the drawdown orders signals "
                "that official communications are lagging behind operational decision-making."
            ),
        ),
    ],
    "political": [
        (
            "Coalition stability threshold breach",
            (
                "Coalition partner withdrawal signals have emerged from two minor parties, "
                "directly causing financial markets to price in early election risk. The "
                "causal chain from coalition fragmentation to policy paralysis is already "
                "visible in the failure to advance three scheduled legislative votes, "
                "triggering investor confidence deterioration."
            ),
        ),
        (
            "Legitimacy crisis deepening",
            (
                "Mass protest events exceeding historical mobilisation thresholds have "
                "occurred in three major cities simultaneously, contradicting official "
                "assessments of contained civil unrest. The causal link between legitimacy "
                "erosion and institutional capacity deterioration is compressing the "
                "governance response window."
            ),
        ),
    ],
    "cyber": [
        (
            "Critical infrastructure anomaly confirmed",
            (
                "CERT emergency alerts have been issued following confirmation of a critical "
                "infrastructure anomaly consistent with a state-attributed cyber operation, "
                "directly causing emergency isolation of affected systems. The causal chain "
                "from initial access to operational impact occurred within 6 hours, indicating "
                "a pre-positioned threat actor."
            ),
        ),
        (
            "Attribution assessment initiated",
            (
                "Technical attribution analysis has identified signatures consistent with "
                "a known state-linked actor, triggering formal diplomatic consultation "
                "processes. The contradiction between the scale of impact and the absence "
                "of a public attribution statement indicates deliberate escalation management."
            ),
        ),
    ],
    "health": [
        (
            "Epidemic threshold breach confirmed",
            (
                "WHO emergency committee has convened following confirmed epidemic threshold "
                "breach in three urban centres, directly causing border health screening "
                "escalation and trade flow disruption. The causal progression from local "
                "outbreak to systemic public health emergency is occurring faster than modelled."
            ),
        ),
    ],
    "social": [
        (
            "Civil unrest escalation threshold exceeded",
            (
                "Protest mobilisation has exceeded the historical threshold at which "
                "security force containment becomes structurally inadequate, directly causing "
                "emergency cabinet sessions. The causal link between unmet economic grievances "
                "and sustained mobilisation capacity indicates a structural instability dynamic."
            ),
        ),
    ],
    "insurance": [
        (
            "Insurance market withdrawal from region",
            (
                "Lloyd's and major reinsurance syndicates have issued withdrawal notices "
                "for corridor coverage, directly causing freight rate spikes that make "
                "transit economically unviable for marginal operators. The causal sequence "
                "from risk repricing to effective embargo is self-reinforcing."
            ),
        ),
    ],
    "logistics": [
        (
            "Alternative routing capacity insufficient",
            (
                "Logistics modelling confirms that alternative routing capacity is "
                "insufficient to absorb the diverted volume from the primary disrupted "
                "route, causing a structural bottleneck. This insufficiency directly causes "
                "cost cascades into downstream supply chains across multiple dependent sectors."
            ),
        ),
    ],
}

_PRIMES: list[int] = [3, 5, 7, 11, 13]


def _select_prime(assessment_id: str, domain_count: int, alert_count: int) -> int:
    """Select a deterministic prime base for p-adic calculation from assessment metadata."""
    id_hash = sum(ord(c) for c in assessment_id) % len(_PRIMES)
    domain_bias = min(domain_count, len(_PRIMES) - 1)
    idx = (id_hash + domain_bias) % len(_PRIMES)
    return _PRIMES[idx]


_FALLBACK_EVENT_TEMPLATE: tuple[str, str] = (
    "Structural stress indicators confirmed",
    (
        "Multiple structural stress indicators have confirmed escalation beyond the "
        "threshold at which linear stabilisation mechanisms remain effective. The "
        "causal chain from initial trigger to systemic stress is now operating across "
        "interdependent domains, directly causing constraint on available intervention "
        "options. Evidence of contradiction between official stabilisation narratives "
        "and observed system behaviour indicates the situation is underweighted in "
        "public assessments."
    ),
)

_REGIME_IMPLICATION_TEMPLATES: dict[str, str] = {
    "Nonlinear Escalation": (
        "System is within the nonlinear escalation band for {domains} dynamics "
        "in {regions}. A moderate shock to any coupled domain is sufficient to "
        "trigger cascade propagation. Damping capacity is constrained at {damping:.0%}; "
        "intervention windows for {primary_domain} stabilisation are narrowing."
    ),
    "Stress Accumulation": (
        "Stress is accumulating across {domains} domains in {regions} without "
        "reaching the nonlinear threshold. Current damping capacity of {damping:.0%} "
        "provides a partial buffer, but the {primary_domain} coupling axis is "
        "tightening. Early intervention can still prevent threshold breach."
    ),
    "Cascade Risk": (
        "System is at immediate cascade risk. {domains} domains in {regions} are "
        "structurally coupled above the critical threshold. Damping capacity has "
        "deteriorated to {damping:.0%}. The {primary_domain} axis is the primary "
        "transmission channel; containment requires simultaneous multi-domain action."
    ),
    "Attractor Lock-in": (
        "System has entered attractor lock-in. {domains} dynamics in {regions} "
        "are now self-reinforcing with damping capacity at {damping:.0%}. "
        "The {primary_domain} equilibrium state is consolidating. Reversal "
        "requires structural intervention beyond incremental policy adjustment."
    ),
    "Linear": (
        "System remains in a linear regime across {domains} domains in {regions}. "
        "Current damping capacity of {damping:.0%} is sufficient to absorb "
        "moderate shocks. Standard monitoring protocols remain adequate."
    ),
    "Dissipating": (
        "Stress is dissipating across {domains} domains in {regions}. "
        "Damping capacity has recovered to {damping:.0%}. "
        "The {primary_domain} trajectory is stabilising; downside risk is reducing "
        "but vigilance on {secondary_domain} coupling remains warranted."
    ),
}


def build_regime_implication(
    regime: str,
    domain_tags: list[str],
    region_tags: list[str],
    damping_capacity: float,
) -> str:
    """Build a differentiated forecast_implication string for RegimeOutput."""
    template = _REGIME_IMPLICATION_TEMPLATES.get(
        regime, _REGIME_IMPLICATION_TEMPLATES["Stress Accumulation"]
    )
    domains_str = " / ".join(domain_tags[:3]) if domain_tags else "multi-domain"
    regions_str = ", ".join(region_tags[:2]) if region_tags else "the affected region"
    primary = domain_tags[0] if domain_tags else "structural"
    secondary = domain_tags[1] if len(domain_tags) > 1 else primary
    return template.format(
        domains=domains_str,
        regions=regions_str,
        damping=damping_capacity,
        primary_domain=primary,
        secondary_domain=secondary,
    )


def build_probability_tree_text(assessment: Any) -> str:
    """
    Build rich text for ProbabilityTreeBuilder so keyword classifiers fire.

    Replaces the original skeleton [title + analyst_notes + "Domains: ..."]
    which contained zero causal/contradiction keywords, causing branch CONF
    to be stuck at 0.20/0.10/0.20.
    """
    domain_tags: list[str] = list(assessment.domain_tags or [])
    region_tags: list[str] = list(assessment.region_tags or [])
    analyst_notes: str = assessment.analyst_notes or ""
    title: str = assessment.title or ""

    parts: list[str] = [title]
    if analyst_notes:
        parts.append(analyst_notes)

    region_phrase = region_tags[0] if region_tags else "the affected region"

    for domain in domain_tags[:3]:
        templates = _RICH_EVENT_TEMPLATES.get(domain, [_FALLBACK_EVENT_TEMPLATE])
        for _, evt_text in templates[:1]:
            personalised = evt_text.replace("the affected region", region_phrase)
            parts.append(personalised)

    return " ".join(parts)


_CONFIDENCE_VELOCITY: dict[str, float] = {
    "Very High": 0.85,
    "High": 0.72,
    "Medium": 0.52,
    "Low": 0.32,
}

_REGIME_STATE_DEFAULTS: dict[str, dict] = {
    "Nonlinear Escalation": {"damping_capacity": 0.29, "reversibility_index": 0.31, "threshold_distance": 0.18},
    "Stress Accumulation":  {"damping_capacity": 0.50, "reversibility_index": 0.55, "threshold_distance": 0.35},
    "Cascade Risk":          {"damping_capacity": 0.15, "reversibility_index": 0.20, "threshold_distance": 0.08},
    "Attractor Lock-in":     {"damping_capacity": 0.12, "reversibility_index": 0.15, "threshold_distance": 0.05},
    "Linear":                {"damping_capacity": 0.75, "reversibility_index": 0.80, "threshold_distance": 0.65},
    "Dissipating":           {"damping_capacity": 0.65, "reversibility_index": 0.70, "threshold_distance": 0.50},
}

_DOMAIN_ONTOLOGY_PATTERNS: dict[str, list[str]] = {
    "technology": ["Technology Transfer Restriction Pattern", "Supply Chain Fragmentation Pattern"],
    "military":   ["Military Coercion Pattern", "Deterrence Breakdown Pattern"],
    "energy":     ["Energy Supply Disruption Pattern", "Resource Leverage Pattern"],
    "sanctions":  ["Hegemonic Sanctions Pattern", "Financial Isolation Pattern"],
    "finance":    ["Capital Flight Pattern", "Financial Contagion Pattern"],
    "political":  ["Political Polarisation Pattern", "Governance Crisis Pattern"],
    "trade":      ["Trade Decoupling Pattern", "Supply Chain Reorientation Pattern"],
    "cyber":      ["Cyber Escalation Pattern", "Critical Infrastructure Disruption Pattern"],
    "health":     ["Pandemic Threshold Pattern", "Health System Cascade Pattern"],
    "social":     ["Social Fragmentation Pattern", "Civil Unrest Cascade Pattern"],
    "insurance":  ["Insurance Market Withdrawal Pattern", "Risk Repricing Pattern"],
    "logistics":  ["Logistics Bottleneck Pattern", "Alternative Routing Insufficiency Pattern"],
}


async def fetch_assessment_context_v2(assessment_id: str) -> dict[str, Any]:
    """
    Replacement for the non-demo branch of _fetch_assessment_context().

    Generates 5-8 rich events (vs. 2 skeleton stubs) with causal/contradiction
    keywords so downstream engine classifiers produce differentiated outputs.
    """
    from app.core.assessment_store import assessment_store  # noqa: PLC0415 — local import avoids circular dependency at module load

    assessment = assessment_store.get_assessment(assessment_id)
    if assessment is None:
        return {}

    domain_tags: list[str] = list(assessment.domain_tags or [])
    region_tags: list[str] = list(assessment.region_tags or [])
    analyst_notes: str = assessment.analyst_notes or ""
    alert_count: int = assessment.alert_count or 0
    last_regime: str = assessment.last_regime or "Stress Accumulation"
    last_confidence: str = assessment.last_confidence or "Medium"

    base_velocity = _CONFIDENCE_VELOCITY.get(last_confidence, 0.52)
    alert_boost = min(0.15, alert_count * 0.03)

    # Build rich events: up to 2 events per domain (max 4 domains = 8 events)
    events: list[dict[str, Any]] = []
    for d_idx, domain in enumerate(domain_tags[:4]):
        templates = _RICH_EVENT_TEMPLATES.get(domain, [_FALLBACK_EVENT_TEMPLATE])
        for t_idx, (evt_name, evt_text) in enumerate(templates[:2]):
            causal_decay = d_idx * 0.06 + t_idx * 0.04
            source_rel = round(min(0.92, base_velocity + alert_boost - causal_decay * 0.5), 2)
            causal_weight = round(min(0.88, base_velocity + alert_boost - causal_decay), 2)
            confidence_val = round(min(0.90, base_velocity + alert_boost - causal_decay * 0.8), 2)
            region_phrase = region_tags[0] if region_tags else "the affected region"
            personalised_text = evt_text.replace("the affected region", region_phrase)
            events.append({
                "name": f"{evt_name} — {region_phrase}",
                "title": evt_name,
                "text": personalised_text,
                "domains": domain_tags[max(0, d_idx - 1): d_idx + 2],
                "entities": region_tags[:3],
                "source_reliability": source_rel,
                "causal_weight": causal_weight,
                "confidence": confidence_val,
                "domain_primary": domain,
            })

    if analyst_notes and len(analyst_notes) > 40:
        events.insert(0, {
            "name": f"{assessment.title} — analyst assessment",
            "title": assessment.title,
            "text": analyst_notes,
            "domains": domain_tags,
            "entities": region_tags,
            "source_reliability": round(min(0.95, base_velocity + alert_boost + 0.05), 2),
            "causal_weight": round(min(0.90, base_velocity + alert_boost), 2),
            "confidence": round(min(0.92, base_velocity + alert_boost), 2),
            "domain_primary": domain_tags[0] if domain_tags else "general",
        })

    # velocity_data
    velocity_data: dict[str, float] = {}
    for i, d in enumerate(domain_tags):
        v = base_velocity + alert_boost - i * 0.06
        velocity_data[d] = round(max(0.20, min(0.95, v)), 2)

    # ontology_activations: 2 patterns per domain
    ontology_activations: dict[str, float] = {}
    for i, d in enumerate(domain_tags[:4]):
        patterns = _DOMAIN_ONTOLOGY_PATTERNS.get(d, [f"{d.title()} Structural Pattern"])
        base_act = base_velocity + alert_boost - i * 0.08
        for j, pat in enumerate(patterns[:2]):
            ontology_activations[pat] = round(max(0.30, min(0.92, base_act - j * 0.05)), 2)

    # kg_paths
    kg_paths: list[dict[str, Any]] = []
    for i in range(len(domain_tags) - 1):
        kg_paths.append({
            "from_entity": f"{domain_tags[i].title()} Sector",
            "to_entity": f"{domain_tags[i + 1].title()} Sector",
            "relation": "AFFECTS",
            "domain": domain_tags[i],
            "strength": round(max(0.40, 0.78 - i * 0.08), 2),
        })
    for i, region in enumerate(region_tags[:2]):
        if domain_tags:
            kg_paths.append({
                "from_entity": region,
                "to_entity": f"{domain_tags[0].title()} Sector",
                "relation": "EXPOSED_TO",
                "domain": domain_tags[0],
                "strength": round(max(0.45, 0.80 - i * 0.10), 2),
            })

    causal_weights = {ev["name"]: ev["causal_weight"] for ev in events}

    # regime_state with differentiated forecast_implication
    regime_defaults = _REGIME_STATE_DEFAULTS.get(last_regime, _REGIME_STATE_DEFAULTS["Stress Accumulation"])
    damping = round(max(0.10, regime_defaults["damping_capacity"] - alert_boost), 2)
    regime_state = {
        "regime": last_regime,
        "damping_capacity": damping,
        "reversibility_index": round(max(0.10, regime_defaults["reversibility_index"] - alert_boost * 0.5), 2),
        "threshold_distance": round(max(0.05, regime_defaults["threshold_distance"] - alert_boost), 2),
        "forecast_implication": build_regime_implication(
            last_regime, domain_tags, region_tags, damping,
        ),
    }

    return {
        "events": events,
        "kg_paths": kg_paths,
        "causal_weights": causal_weights,
        "velocity_data": velocity_data,
        "ontology_activations": ontology_activations,
        "regime_state": regime_state,
    }
