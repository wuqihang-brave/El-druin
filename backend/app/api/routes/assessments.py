"""
Assessments API routes
======================

Endpoints:
  GET  /assessments                              – list all assessments
  GET  /assessments/{assessment_id}              – single assessment detail
  GET  /assessments/{assessment_id}/brief        – executive brief
  GET  /assessments/{assessment_id}/regime       – regime state output (real engine, PR-4)
  GET  /assessments/{assessment_id}/triggers     – trigger amplification output (real engine, PR-5)
  GET  /assessments/{assessment_id}/attractors   – attractor output (real engine, PR-6)
  GET  /assessments/{assessment_id}/propagation  – propagation sequence output (real engine, PR-7)
  GET  /assessments/{assessment_id}/delta        – update delta output (real engine, PR-8)
  GET  /assessments/{assessment_id}/evidence     – evidence output

The regime endpoint calls the real RegimeEngine adapter (PR-4).
The triggers endpoint calls the real TriggerAmplificationEngine adapter (PR-5).
The attractors endpoint calls the real AttractorEngine adapter (PR-6).
The propagation endpoint calls the real PropagationEngine adapter (PR-7).
The delta endpoint calls the real DeltaEngine adapter (PR-8).
Live engine endpoints fall back to stub data when context is unavailable.
All other endpoints remain as stubs keyed to assessment_id "ae-204".
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response

from app.schemas.assessment import (
    Assessment,
    AssessmentCreate,
    AssessmentListResponse,
    AssessmentStatus,
    AssessmentType,
    AssessmentUpdate,
)
from app.core.assessment_store import assessment_store

logger = logging.getLogger(__name__)

try:
    from app.services.trigger_engine import TriggerAmplificationEngine as _TriggerEngine
    _TRIGGER_ENGINE_AVAILABLE = True
except Exception as _te_exc:  # noqa: BLE001
    logger.warning("TriggerAmplificationEngine not available: %s", _te_exc)
    _TriggerEngine = None  # type: ignore[assignment,misc]
    _TRIGGER_ENGINE_AVAILABLE = False

from app.schemas.structural_forecast import (
    AttractorOutput,
    AttractorsOutput,
    BriefOutput,
    CouplingOutput,
    CouplingPair,
    DeltaField,
    DeltaOutput,
    EvidenceItem,
    EvidenceOutput,
    PropagationOutput,
    PropagationStep,
    RegimeOutput,
    TriggerOutput,
    TriggersOutput,
)

router = APIRouter(prefix="/assessments", tags=["assessments"])

# ---------------------------------------------------------------------------
# Async job store – used by POST /trigger and GET /status/{job_id}
# In-memory; replace with Redis in production for multi-worker deployments.
# ---------------------------------------------------------------------------
_jobs: dict[str, dict[str, Any]] = {}


async def _run_generation_job(job_id: str, hours: int, min_events: int, max_assessments: int) -> None:
    """Background task: run the full assessment generation pipeline."""
    _jobs[job_id]["status"] = "running"
    try:
        from app.services.assessment_generator import AssessmentGenerator  # noqa: PLC0415

        result = AssessmentGenerator().generate_from_news(
            hours=hours,
            min_events_per_cluster=min_events,
            max_assessments=max_assessments,
        )
        _jobs[job_id].update({"status": "completed", "result": result})
        logger.info("Job %s completed: %s", job_id, result)
    except Exception as exc:  # noqa: BLE001
        _jobs[job_id].update({"status": "failed", "error": str(exc)})
        logger.error("Job %s failed: %s", job_id, exc)


# ---------------------------------------------------------------------------
# Demo stub data – keyed to assessment "ae-204"
# ---------------------------------------------------------------------------

_DEMO_ID = "ae-204"
_NOW = datetime(2026, 4, 9, 18, 0, 0, tzinfo=timezone.utc)

_DEMO_ASSESSMENT = Assessment(
    assessment_id=_DEMO_ID,
    title="Black Sea Energy Corridor – Structural Watch",
    assessment_type=AssessmentType.structural_watch,
    status=AssessmentStatus.active,
    region_tags=["Eastern Europe", "Black Sea", "Middle East"],
    domain_tags=["energy", "military", "sanctions", "finance"],
    created_at=datetime(2026, 3, 1, 9, 0, 0, tzinfo=timezone.utc),
    updated_at=_NOW,
    last_regime="Nonlinear Escalation",
    last_confidence="High",
    alert_count=3,
    analyst_notes="Pipeline disruption risk elevated following recent naval incidents.",
)

_DEMO_BRIEF = BriefOutput(
    assessment_id=_DEMO_ID,
    forecast_posture="Upward-skewed energy risk",
    time_horizon="3-7 days",
    confidence="High",
    why_it_matters=(
        "A disruption to the Black Sea energy corridor would cascade into EU "
        "spot-market prices within 24 hours and increase sanctions pressure on "
        "transit states within 72 hours."
    ),
    dominant_driver="Naval interdiction pressure on energy transit routes",
    strengthening_conditions=[
        "Additional naval assets deployed in contested waters",
        "Insurance market withdrawal from corridor tankers",
        "Diplomatic channel breakdown between transit states",
    ],
    weakening_conditions=[
        "Ceasefire or de-escalation agreement signed",
        "Alternative pipeline capacity comes online",
        "Third-party mediation accepted by all parties",
    ],
    invalidation_conditions=[
        "Full corridor reopening confirmed by all transit operators",
        "Regional security guarantee treaty ratified",
    ],
    updated_at=_NOW,
)

_DEMO_REGIME = RegimeOutput(
    assessment_id=_DEMO_ID,
    current_regime="Nonlinear Escalation",
    threshold_distance=0.18,
    transition_volatility=0.74,
    reversibility_index=0.31,
    dominant_axis="military -> sanctions -> energy",
    coupling_asymmetry=0.62,
    damping_capacity=0.29,
    forecast_implication=(
        "System is within the nonlinear escalation band. A moderate shock to "
        "any coupled domain is sufficient to trigger cascade propagation. "
        "Damping capacity is low; diplomatic interventions have a narrow window."
    ),
    updated_at=_NOW,
)

_DEMO_TRIGGERS = TriggersOutput(
    assessment_id=_DEMO_ID,
    triggers=[
        TriggerOutput(
            name="Naval incident in contested strait",
            amplification_factor=0.87,
            jump_potential="Critical",
            impacted_domains=["military", "energy", "insurance", "finance"],
            expected_lag_hours=6,
            confidence=0.81,
            watch_signals=[
                "AIS dark zones expanding",
                "Insurance premium spike >20%",
                "Emergency UNSC session called",
            ],
            damping_opportunities=[
                "Bilateral hotline activation",
                "Neutral maritime observer deployment",
            ],
        ),
        TriggerOutput(
            name="Secondary sanctions package announced",
            amplification_factor=0.71,
            jump_potential="High",
            impacted_domains=["finance", "energy", "trade"],
            expected_lag_hours=48,
            confidence=0.68,
            watch_signals=[
                "Treasury OFAC pre-designation briefings",
                "Correspondent banking withdrawals from region",
            ],
            damping_opportunities=[
                "Carve-out negotiations via EU intermediaries",
                "Humanitarian exemption framework agreed",
            ],
        ),
    ],
    updated_at=_NOW,
)

_DEMO_ATTRACTORS = AttractorsOutput(
    assessment_id=_DEMO_ID,
    attractors=[
        AttractorOutput(
            name="Protracted low-level blockade equilibrium",
            pull_strength=0.78,
            horizon="3-10d",
            supporting_evidence_count=14,
            counterforces=[
                "Economic cost to blocking state",
                "NATO maritime presence",
            ],
            invalidation_conditions=[
                "Full unilateral withdrawal of naval assets",
                "Internationally brokered corridor guarantee",
            ],
            trend="up",
        ),
        AttractorOutput(
            name="Fragile corridor reopening under third-party guarantee",
            pull_strength=0.41,
            horizon="10-21d",
            supporting_evidence_count=6,
            counterforces=[
                "Domestic political constraints on concessions",
                "Ongoing military operations in adjacent theatre",
            ],
            invalidation_conditions=[
                "Escalation to direct state-on-state naval exchange",
            ],
            trend="stable",
        ),
    ],
    updated_at=_NOW,
)

_DEMO_PROPAGATION = PropagationOutput(
    assessment_id=_DEMO_ID,
    sequence=[
        PropagationStep(step=1, domain="military", event="Naval assets block strait access", time_bucket="T+0"),
        PropagationStep(step=2, domain="energy", event="Tanker transit suspended; spot prices spike 12%", time_bucket="T+24h"),
        PropagationStep(step=3, domain="insurance", event="Lloyd's withdraws corridor coverage", time_bucket="T+24h"),
        PropagationStep(step=4, domain="finance", event="Regional sovereign spreads widen 40bps", time_bucket="T+72h"),
        PropagationStep(step=5, domain="trade", event="Alternative routing adds $3.2/bbl cost; contract renegotiations begin", time_bucket="T+7d"),
        PropagationStep(step=6, domain="political", event="Emergency EU energy council; sanctions expansion tabled", time_bucket="T+2-6w"),
    ],
    bottlenecks=[
        "Single strait chokepoint with no viable short-term alternative",
        "Insurance market concentration in London market",
    ],
    second_order_effects=[
        "Increased LNG spot demand in Mediterranean markets",
        "Accelerated permitting for alternative pipeline routes",
        "Domestic energy rationing measures in downstream states",
    ],
    updated_at=_NOW,
)

_DEMO_DELTA = DeltaOutput(
    assessment_id=_DEMO_ID,
    regime_changed=True,
    threshold_direction="narrowing",
    trigger_ranking_changes=[
        DeltaField(
            field="Naval incident trigger rank",
            previous=2,
            current=1,
            direction="increased",
        ),
        DeltaField(
            field="Sanctions trigger rank",
            previous=1,
            current=2,
            direction="decreased",
        ),
    ],
    attractor_pull_changes=[
        DeltaField(
            field="Protracted blockade pull_strength",
            previous=0.61,
            current=0.78,
            direction="increased",
        ),
    ],
    damping_capacity_delta=-0.12,
    confidence_delta=0.07,
    new_evidence_count=4,
    summary=(
        "Regime shifted from Stress Accumulation to Nonlinear Escalation "
        "following confirmation of naval asset deployment. Damping capacity "
        "deteriorated by 12 points. Four new high-quality evidence items "
        "incorporated, raising overall confidence."
    ),
    updated_at=_NOW,
)

_DEMO_EVIDENCE = EvidenceOutput(
    assessment_id=_DEMO_ID,
    evidence=[
        EvidenceItem(
            evidence_id="ev-1001",
            source="Lloyd's List Intelligence – AIS Feed",
            timestamp=datetime(2026, 4, 9, 6, 14, 0, tzinfo=timezone.utc),
            source_quality="Primary",
            impacted_area="energy / maritime",
            structural_novelty=0.82,
            confidence_contribution=0.19,
            provenance_link="/api/v1/provenance/entity/ev-1001",
        ),
        EvidenceItem(
            evidence_id="ev-1002",
            source="Reuters – Diplomatic correspondent",
            timestamp=datetime(2026, 4, 9, 9, 45, 0, tzinfo=timezone.utc),
            source_quality="High",
            impacted_area="political / sanctions",
            structural_novelty=0.54,
            confidence_contribution=0.11,
            provenance_link="/api/v1/provenance/entity/ev-1002",
        ),
        EvidenceItem(
            evidence_id="ev-1003",
            source="EU Commission energy market daily bulletin",
            timestamp=datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc),
            source_quality="Primary",
            impacted_area="energy / finance",
            structural_novelty=0.67,
            confidence_contribution=0.14,
            provenance_link="/api/v1/provenance/entity/ev-1003",
        ),
        EvidenceItem(
            evidence_id="ev-1004",
            source="Regional think-tank analysis",
            timestamp=datetime(2026, 4, 8, 17, 30, 0, tzinfo=timezone.utc),
            source_quality="Medium",
            impacted_area="military / political",
            structural_novelty=0.39,
            confidence_contribution=0.06,
            provenance_link=None,
        ),
    ],
    updated_at=_NOW,
)

# ---------------------------------------------------------------------------
# Domain-specific lookup tables for assessment-specific output generation
# ---------------------------------------------------------------------------

_REGION_SOURCE_MAP: dict[str, list[str]] = {
    "Asia Pacific": ["Regional security monitor – CSIS Asia", "Bloomberg Asia Markets", "Reuters Asia correspondent"],
    "Southeast Asia": ["ASEAN Regional Forum report", "Nikkei Asia markets", "Bloomberg SE Asia"],
    "East Asia": ["East Asia security review", "Financial Times Asia", "Reuters Tokyo bureau"],
    "Middle East": ["Al-Monitor regional analyst", "Bloomberg Gulf markets", "Reuters Middle East correspondent"],
    "Eastern Europe": ["EURACTIV Eastern Europe", "Bloomberg CEE markets", "Reuters Eastern Europe bureau"],
    "Western Europe": ["Financial Times Europe", "Bloomberg European markets", "Reuters Berlin bureau"],
    "North America": ["POLITICO national security", "WSJ US markets", "Reuters Washington bureau"],
    "South America": ["Americas Quarterly", "Bloomberg LatAm", "Reuters LatAm correspondent"],
    "Africa": ["ISS Africa security monitor", "Bloomberg Africa", "Reuters Africa bureau"],
    "Black Sea": ["Lloyd's List Intelligence – AIS Feed", "Reuters Diplomatic correspondent", "EU Commission energy market daily bulletin"],
    "South China Sea": ["Asia Maritime Transparency Initiative", "Bloomberg Asia Pacific", "Reuters Singapore bureau"],
    "Indo-Pacific": ["IISS Asia Security Summit report", "Bloomberg Indo-Pacific", "Reuters Singapore bureau"],
    "Central Asia": ["Eurasianet security monitor", "Bloomberg Central Asia", "Reuters Almaty bureau"],
    "South Asia": ["IISS South Asia brief", "Bloomberg South Asia", "Reuters New Delhi bureau"],
    "Pacific": ["Lowy Institute Pacific monitor", "Reuters Pacific correspondent", "Bloomberg Pacific markets"],
    "Europe": ["European Council on Foreign Relations report", "Bloomberg Europe", "Reuters Brussels bureau"],
    "Australia": ["ASPI strategic insight", "AFR markets", "Reuters Sydney bureau"],
}

_DOMAIN_BRIEF_MAP: dict[str, dict] = {
    "technology": {
        "posture": "Elevated technology sector risk",
        "driver": "Technology access restriction and supply chain fragmentation pressure",
        "matters_fmt": (
            "Structural technology decoupling across {regions} would cascade into "
            "capability gaps and trade competitiveness pressures within weeks, with "
            "downstream effects on allied industrial production and strategic stockpiles."
        ),
        "strengthening": [
            "Export control escalation by major supplier states",
            "Technology sector investment restrictions tightened",
            "Supply chain relocation accelerating beyond recovery threshold",
        ],
        "weakening": [
            "Bilateral technology trade agreement negotiated",
            "Alternative supplier emerges with sufficient capacity",
            "Exemption framework agreed for critical components",
        ],
        "invalidation": [
            "Full technology access restoration confirmed by all parties",
            "Comprehensive technology cooperation agreement ratified",
        ],
    },
    "military": {
        "posture": "Elevated military escalation risk",
        "driver": "Military posture shift and capability demonstration pressure",
        "matters_fmt": (
            "Military escalation in {regions} would trigger alliance obligation reviews "
            "and force posture adjustments within 72 hours, with cascading effects on "
            "regional security guarantees and diplomatic relations."
        ),
        "strengthening": [
            "Additional military assets deployed to contested zones",
            "Alliance commitment ambiguity increasing",
            "Civilian infrastructure at risk of targeting",
        ],
        "weakening": [
            "De-escalation commitment agreed by principal parties",
            "Third-party military observer presence established",
            "Diplomatic back-channel confirmed active",
        ],
        "invalidation": [
            "Formal ceasefire or security agreement signed",
            "Independent verification of force withdrawal confirmed",
        ],
    },
    "energy": {
        "posture": "Upward-skewed energy risk",
        "driver": "Energy supply disruption and infrastructure vulnerability pressure",
        "matters_fmt": (
            "Energy supply disruption in {regions} would cascade into spot-market "
            "price spikes within 24 hours and trigger emergency reserve releases "
            "within 72 hours, with sustained downstream pressure on trade balances."
        ),
        "strengthening": [
            "Infrastructure attack or failure in energy transit network",
            "Insurance market withdrawal from region",
            "Emergency reserve drawdown signals supply stress",
        ],
        "weakening": [
            "Alternative supply route confirmed operational",
            "Emergency intergovernmental energy sharing agreement",
            "Demand reduction measures reducing pressure",
        ],
        "invalidation": [
            "Full energy supply restoration confirmed by all operators",
            "Long-term alternative supply agreement ratified",
        ],
    },
    "sanctions": {
        "posture": "Elevated sanctions cascade risk",
        "driver": "Secondary sanctions pressure and financial isolation escalation",
        "matters_fmt": (
            "Secondary sanctions escalation targeting {regions} would trigger correspondent "
            "banking withdrawal within 48 hours and accelerate capital outflows, constraining "
            "import capacity and reserve adequacy."
        ),
        "strengthening": [
            "OFAC pre-designation briefings circulating",
            "Correspondent banking withdrawal accelerating",
            "Multilateral sanctions coordination gaining momentum",
        ],
        "weakening": [
            "Carve-out or humanitarian exemption framework agreed",
            "Third-party mediation accepted by sanctioning parties",
            "Compliance pathway offered by sanctions authority",
        ],
        "invalidation": [
            "Full sanctions relief package announced",
            "Verified compliance with core sanctions conditions",
        ],
    },
    "finance": {
        "posture": "Elevated financial stability risk",
        "driver": "Capital flight pressure and banking sector stress accumulation",
        "matters_fmt": (
            "Financial contagion in {regions} would trigger cross-border capital flow "
            "restrictions within 72 hours and sovereign spread widening, with downstream "
            "pressure on trade financing and investment flows."
        ),
        "strengthening": [
            "Banking sector liquidity stress indicators rising",
            "Sovereign spread widening beyond threshold",
            "Capital controls considered by monetary authorities",
        ],
        "weakening": [
            "IMF emergency liquidity facility activated",
            "Coordinated central bank intervention agreed",
            "Investor confidence restored by policy commitment",
        ],
        "invalidation": [
            "Comprehensive financial stability package delivered",
            "Independent sovereign credit assessment upgraded",
        ],
    },
    "political": {
        "posture": "Elevated political instability risk",
        "driver": "Governance stress and political legitimacy pressure",
        "matters_fmt": (
            "Political instability in {regions} would undermine institutional confidence "
            "and create policy uncertainty, cascading into foreign investment withdrawal "
            "and alliance credibility questions within weeks."
        ),
        "strengthening": [
            "Governing coalition fracturing under policy pressure",
            "Public legitimacy crisis deepening",
            "Opposition coalition forming with broad support",
        ],
        "weakening": [
            "Political compromise agreement brokered",
            "Electoral calendar providing resolution mechanism",
            "External mediation accepted by key parties",
        ],
        "invalidation": [
            "Stable governing coalition confirmed with full mandate",
            "Constitutional resolution mechanism successfully invoked",
        ],
    },
    "trade": {
        "posture": "Elevated trade disruption risk",
        "driver": "Trade decoupling pressure and supply chain reorientation stress",
        "matters_fmt": (
            "Trade decoupling in {regions} would cascade into supply chain cost increases "
            "within weeks and accelerate strategic stockpile depletion, with sustained "
            "downstream pressure on industrial production capacity."
        ),
        "strengthening": [
            "Tariff escalation announced beyond critical threshold",
            "Trade route disruption confirmed",
            "Strategic supply chain relocation accelerating",
        ],
        "weakening": [
            "Trade negotiations resumed with credible framework",
            "Tariff exemption or reduction agreed",
            "Alternative supply chain capacity operational",
        ],
        "invalidation": [
            "Comprehensive trade agreement signed and ratified",
            "Full market access restoration confirmed",
        ],
    },
    "cyber": {
        "posture": "Elevated cyber threat risk",
        "driver": "Critical infrastructure cyber exposure and state-attributed attack pressure",
        "matters_fmt": (
            "Cyber escalation targeting {regions} critical infrastructure would disrupt "
            "government and financial systems within hours, with cascading effects on "
            "public services and commercial continuity."
        ),
        "strengthening": [
            "Critical infrastructure vulnerability exploitation confirmed",
            "State-attributed cyber operation detected",
            "Incident response capacity overwhelmed",
        ],
        "weakening": [
            "Diplomatic cyber norms agreement reached",
            "Incident attribution and deterrence response established",
            "Critical systems hardened beyond attacker capability",
        ],
        "invalidation": [
            "Formal cyber non-aggression commitment verified",
            "Full system restoration and security audit completed",
        ],
    },
    "health": {
        "posture": "Elevated public health risk",
        "driver": "Disease threshold pressure and health system capacity stress",
        "matters_fmt": (
            "Public health deterioration in {regions} would cascade into labour market "
            "disruption within weeks and supply chain delays, with downstream effects "
            "on regional economic output and trade capacity."
        ),
        "strengthening": [
            "Epidemic threshold breached in key urban centres",
            "Health system capacity approaching critical limit",
            "International health authority alert issued",
        ],
        "weakening": [
            "Emergency health response capacity expanded",
            "International medical assistance coordinated",
            "Containment measures demonstrably effective",
        ],
        "invalidation": [
            "Sustained epidemic containment confirmed",
            "Health system capacity normalised",
        ],
    },
    "social": {
        "posture": "Elevated social stability risk",
        "driver": "Social cohesion stress and civil unrest pressure",
        "matters_fmt": (
            "Social stability deterioration in {regions} would cascade into governance "
            "paralysis within weeks, with downstream effects on investor confidence "
            "and policy implementation capacity."
        ),
        "strengthening": [
            "Mass protest or civil unrest events escalating",
            "Social media coordination enabling rapid mobilisation",
            "Security force response disproportionate and inflaming tensions",
        ],
        "weakening": [
            "Government concession addressing core grievance",
            "Civil society dialogue mechanism established",
            "Economic relief measure reducing immediate pressure",
        ],
        "invalidation": [
            "Social compact agreement broadly accepted",
            "Independent verification of grievance resolution",
        ],
    },
}

_DOMAIN_TRIGGER_MAP: dict[str, dict] = {
    "technology": {
        "name": "Technology export restriction escalation",
        "impacted": ["technology", "trade", "finance"],
        "watch": ["Commerce Dept Entity List additions", "Allied jurisdiction mirroring measures", "Corporate delisting announcements"],
        "damping": ["Bilateral technology dialogue channel reopened", "Exemption framework for critical components negotiated"],
        "lag_hours": 24,
        "jump": "High",
        "confidence": 0.70,
    },
    "military": {
        "name": "Military capability demonstration event",
        "impacted": ["military", "political", "finance"],
        "watch": ["Force repositioning via satellite imagery", "Naval asset deployment orders", "Emergency alliance consultation triggered"],
        "damping": ["Hotline activation between commands", "Neutral observer deployment agreed"],
        "lag_hours": 6,
        "jump": "High",
        "confidence": 0.72,
    },
    "energy": {
        "name": "Energy supply disruption event",
        "impacted": ["energy", "finance", "trade"],
        "watch": ["Pipeline pressure anomaly detected", "Insurance premium spike >15%", "Emergency IEA release discussions"],
        "damping": ["Alternative supply route activation", "Emergency reserve drawdown authorised"],
        "lag_hours": 12,
        "jump": "Critical",
        "confidence": 0.74,
    },
    "sanctions": {
        "name": "Secondary sanctions package announced",
        "impacted": ["finance", "trade", "energy"],
        "watch": ["Treasury OFAC pre-designation briefings", "Correspondent banking withdrawal notices", "Allied jurisdiction coordination signals"],
        "damping": ["Carve-out negotiations via neutral intermediaries", "Humanitarian exemption framework agreed"],
        "lag_hours": 48,
        "jump": "High",
        "confidence": 0.68,
    },
    "finance": {
        "name": "Banking sector stress crystallisation",
        "impacted": ["finance", "trade", "political"],
        "watch": ["Sovereign credit rating review initiated", "Capital outflow velocity exceeds threshold", "Currency support operation detected"],
        "damping": ["Central bank emergency facility deployed", "IMF consultation formally requested"],
        "lag_hours": 24,
        "jump": "High",
        "confidence": 0.66,
    },
    "political": {
        "name": "Government stability threshold breach",
        "impacted": ["political", "finance", "trade"],
        "watch": ["Coalition partner withdrawal signals", "No-confidence motion tabled", "Emergency cabinet session called"],
        "damping": ["Cross-party dialogue facilitated", "Early election commitment announced"],
        "lag_hours": 48,
        "jump": "Medium",
        "confidence": 0.62,
    },
    "trade": {
        "name": "Trade route disruption event",
        "impacted": ["trade", "finance", "energy"],
        "watch": ["Port or chokepoint congestion index spike", "Shipping insurance rate surge", "Strategic stockpile drawdown orders"],
        "damping": ["Alternative routing capacity confirmed", "Emergency trade corridor agreement"],
        "lag_hours": 24,
        "jump": "High",
        "confidence": 0.64,
    },
    "cyber": {
        "name": "Critical infrastructure cyber incident",
        "impacted": ["cyber", "political", "finance"],
        "watch": ["CERT emergency alert issued", "Critical system anomaly reports", "Attribution analysis initiated"],
        "damping": ["International cyber incident response team deployed", "System isolation and failover enacted"],
        "lag_hours": 4,
        "jump": "Critical",
        "confidence": 0.68,
    },
    "health": {
        "name": "Epidemic threshold breach event",
        "impacted": ["health", "trade", "political"],
        "watch": ["WHO emergency committee convened", "Border health screening escalated", "Hospital capacity alert issued"],
        "damping": ["International medical assistance coordinated", "Emergency containment protocol activated"],
        "lag_hours": 72,
        "jump": "Medium",
        "confidence": 0.60,
    },
    "social": {
        "name": "Mass civil unrest escalation event",
        "impacted": ["social", "political", "finance"],
        "watch": ["Protest size exceeding historical threshold", "Security force mobilisation order", "Infrastructure disruption by protesters"],
        "damping": ["Government concession announcement", "Civil society dialogue mechanism established"],
        "lag_hours": 12,
        "jump": "Medium",
        "confidence": 0.60,
    },
}

_DOMAIN_ATTRACTOR_MAP: dict[str, list[dict]] = {
    "technology": [
        {
            "name": "Technology Transfer Restriction Cascade",
            "counterforces": ["Allied exemption negotiations ongoing", "Domestic production ramp-up in progress"],
            "invalidation": ["Full technology access restoration agreed", "Comprehensive bilateral technology pact"],
        },
        {
            "name": "Supply Chain Fragmentation Equilibrium",
            "counterforces": ["Market incentives for supply chain diversification", "Government subsidies for domestic production"],
            "invalidation": ["Multilateral supply chain coordination framework", "Alternative supplier achieves full capacity"],
        },
    ],
    "military": [
        {
            "name": "Military Capability Asymmetry Equilibrium",
            "counterforces": ["Alliance balancing measures active", "Diplomatic engagement tracks open"],
            "invalidation": ["Arms control or limitation agreement", "Verified force reduction commitment"],
        },
        {
            "name": "Deterrence Breakdown Lock-in",
            "counterforces": ["Third-party security guarantee offered", "Economic cost of escalation recognised"],
            "invalidation": ["Security architecture agreement ratified", "Independent verification mechanism accepted"],
        },
    ],
    "energy": [
        {
            "name": "Supply Disruption Equilibrium",
            "counterforces": ["Alternative supply routes available", "Emergency reserves sufficient for 30 days"],
            "invalidation": ["Full supply restoration confirmed", "Long-term alternative supply contract"],
        },
        {
            "name": "Energy Price Spike Lock-in",
            "counterforces": ["Demand reduction measures active", "Strategic reserve release coordinated"],
            "invalidation": ["Market price normalisation sustained", "New supply capacity operational"],
        },
    ],
    "sanctions": [
        {
            "name": "Secondary Sanctions Cascade",
            "counterforces": ["Sanctions fatigue among allied states", "Economic costs to sanctioning states mounting"],
            "invalidation": ["Sanctions relief framework agreed", "Verified compliance achieved"],
        },
        {
            "name": "Economic Isolation Equilibrium",
            "counterforces": ["Alternative trading partner network emerging", "Domestic economic adaptation underway"],
            "invalidation": ["Full economic reintegration pathway agreed", "Multilateral economic normalisation"],
        },
    ],
    "finance": [
        {
            "name": "Financial Contagion Equilibrium",
            "counterforces": ["Central bank liquidity backstop in place", "IMF program negotiations advanced"],
            "invalidation": ["Comprehensive financial stabilisation package", "Market confidence sustainably restored"],
        },
        {
            "name": "Capital Flight Lock-in",
            "counterforces": ["Higher interest rate defence mechanism", "Government capital control toolkit available"],
            "invalidation": ["Sustained capital inflow confirmed", "Credit rating stabilisation"],
        },
    ],
    "political": [
        {
            "name": "Political Polarisation Lock-in",
            "counterforces": ["Electoral mechanism providing relief valve", "Civil society mediation active"],
            "invalidation": ["Stable governing majority confirmed", "Cross-party agreement on key policy"],
        },
        {
            "name": "Governance Crisis Equilibrium",
            "counterforces": ["International pressure for stability", "Economic costs of instability recognised"],
            "invalidation": ["Constitutional resolution invoked successfully", "Independent election outcome accepted"],
        },
    ],
    "trade": [
        {
            "name": "Trade Decoupling Equilibrium",
            "counterforces": ["Economic interdependence providing brake", "Industry lobbying for trade restoration"],
            "invalidation": ["Comprehensive trade agreement signed", "Bilateral tariff reduction agreed"],
        },
        {
            "name": "Supply Chain Reorientation Lock-in",
            "counterforces": ["Transition costs slowing complete decoupling", "Third-party alternative hub developing"],
            "invalidation": ["Full supply chain reintegration achieved", "New multilateral trade framework"],
        },
    ],
    "cyber": [
        {
            "name": "Cyber Escalation Equilibrium",
            "counterforces": ["Mutual vulnerability limiting full escalation", "International cyber norms framework developing"],
            "invalidation": ["Formal cyber non-aggression treaty", "Verified attribution and deterrence established"],
        },
        {
            "name": "Critical Infrastructure Disruption Lock-in",
            "counterforces": ["Redundancy systems activated", "International incident response cooperation"],
            "invalidation": ["Full system restoration and hardening confirmed", "Security audit independently verified"],
        },
    ],
    "health": [
        {
            "name": "Pandemic Containment Failure Equilibrium",
            "counterforces": ["International health assistance coordinated", "Containment measures partially effective"],
            "invalidation": ["Sustained epidemic containment confirmed", "Vaccine or treatment coverage threshold reached"],
        },
        {
            "name": "Health System Cascade Lock-in",
            "counterforces": ["Emergency medical capacity expansion", "International surge support deployed"],
            "invalidation": ["Health system capacity normalised", "Treatment protocol standardised and scaled"],
        },
    ],
    "social": [
        {
            "name": "Social Fragmentation Equilibrium",
            "counterforces": ["Civil society dialogue maintaining cohesion", "Economic conditions improving marginally"],
            "invalidation": ["Social compact broadly accepted", "Sustained economic improvement reducing grievances"],
        },
        {
            "name": "Civil Unrest Cascade Lock-in",
            "counterforces": ["Security force restraint preventing mass casualties", "Government partial concession reducing tension"],
            "invalidation": ["Credible governance reform commitment", "Independent mediation accepted by all parties"],
        },
    ],
}

_DOMAIN_PROPAGATION_MAP: dict[str, list[tuple[str, str, str]]] = {
    "technology": [
        ("technology", "Export controls or access restrictions block critical technology flows", "T+0"),
        ("trade", "Supply chain disruption forces emergency sourcing; lead times extend sharply", "T+24h"),
        ("finance", "Technology sector valuations reprice; investment capital redirected", "T+72h"),
        ("political", "Alliance consultation on coordinated response; diplomatic pressure mounts", "T+7d"),
        ("military", "Defence capability assessment initiated; procurement timeline extended", "T+2-6w"),
    ],
    "military": [
        ("military", "Force repositioning or capability demonstration event occurs", "T+0"),
        ("political", "Alliance obligation review triggered; emergency consultation called", "T+24h"),
        ("finance", "Defence spending reallocation announced; bond markets reprice risk", "T+72h"),
        ("trade", "Dual-use export restrictions tightened; supply chain review initiated", "T+7d"),
        ("energy", "Strategic reserve posture adjusted; energy security review commenced", "T+2-6w"),
    ],
    "energy": [
        ("energy", "Supply disruption event detected; transit route at risk", "T+0"),
        ("finance", "Spot price spike cascades into derivative markets; insurance reprices", "T+24h"),
        ("trade", "Alternative routing initiated; logistics cost premium increases", "T+72h"),
        ("political", "Emergency energy council convened; strategic reserve release authorised", "T+7d"),
        ("military", "Energy security mandate activates defence posture review", "T+2-6w"),
    ],
    "sanctions": [
        ("finance", "Correspondent banking withdrawal accelerates; liquidity channels narrow", "T+0"),
        ("trade", "Trade finance withdrawal cascades into import capacity reduction", "T+24h"),
        ("energy", "Energy payment channels disrupted; spot-market alternatives sought", "T+72h"),
        ("political", "Diplomatic response coordinated; multilateral coalition building", "T+7d"),
        ("military", "Security force budget under pressure from economic contraction", "T+2-6w"),
    ],
    "finance": [
        ("finance", "Banking system liquidity stress emerges; interbank rate spike", "T+0"),
        ("trade", "Trade finance withdrawal forces supply chain payment restructuring", "T+24h"),
        ("political", "Emergency fiscal response announced; confidence vote triggered", "T+72h"),
        ("energy", "Energy import payment capacity constrained by reserve decline", "T+7d"),
        ("military", "Defence budget pressure escalates; capability programme delays", "T+2-6w"),
    ],
    "political": [
        ("political", "Governance legitimacy crisis crystallises; policy paralysis risk", "T+0"),
        ("finance", "Political uncertainty drives risk-off; capital outflow accelerates", "T+24h"),
        ("trade", "Policy uncertainty freezes investment and trade contract renewals", "T+72h"),
        ("energy", "Energy policy commitments under review; supply contract uncertainty", "T+7d"),
        ("military", "Defence and security policy uncertainty triggers alliance review", "T+2-6w"),
    ],
    "trade": [
        ("trade", "Trade route disruption or tariff shock cascades into supply bottleneck", "T+0"),
        ("finance", "Trade finance costs rise; currency pressure from balance of payments shift", "T+24h"),
        ("energy", "Energy logistics costs increase; alternative routing adds cost pressure", "T+72h"),
        ("political", "Emergency trade policy response; diplomatic engagement initiated", "T+7d"),
        ("military", "Strategic supply chain security review; defence-critical goods prioritised", "T+2-6w"),
    ],
    "cyber": [
        ("cyber", "Critical infrastructure cyber incident detected; systems isolated", "T+0"),
        ("political", "Attribution assessment initiated; emergency response activated", "T+24h"),
        ("finance", "Financial system availability disrupted; emergency continuity measures", "T+72h"),
        ("trade", "Commercial system disruption cascades into supply chain delays", "T+7d"),
        ("military", "Cyber escalation response options assessed; deterrence posture reviewed", "T+2-6w"),
    ],
    "health": [
        ("health", "Epidemic threshold breach confirmed; public health emergency declared", "T+0"),
        ("trade", "Border health screening escalates; trade flow disruption begins", "T+24h"),
        ("finance", "Market confidence declines; consumer demand shock begins", "T+72h"),
        ("political", "Emergency health governance measures activate; policy response debated", "T+7d"),
        ("social", "Public behaviour change accelerates; social and economic disruption deepens", "T+2-6w"),
    ],
    "social": [
        ("social", "Civil unrest escalation confirmed; protests exceed containment capacity", "T+0"),
        ("political", "Government emergency response activated; legitimacy crisis deepening", "T+24h"),
        ("finance", "Risk-off sentiment triggers capital outflow; currency pressure", "T+72h"),
        ("trade", "Supply chain disruption from civil unrest; logistics network affected", "T+7d"),
        ("military", "Internal security force deployment; international attention and pressure", "T+2-6w"),
    ],
}

_DOMAIN_BOTTLENECKS: dict[str, list[str]] = {
    "technology": [
        "Concentration of critical technology production in limited supplier states",
        "Dual-use technology export licensing bottleneck",
    ],
    "military": [
        "Escalation control communication channel reliability",
        "Alliance solidarity under competing national interests",
    ],
    "energy": [
        "Single-source supply dependency with limited short-term alternatives",
        "Insurance market concentration limiting coverage options",
    ],
    "sanctions": [
        "Correspondent banking concentration in major financial centres",
        "Multilateral coordination speed vs. unilateral action pressure",
    ],
    "finance": [
        "Liquidity concentration in counterparty exposure networks",
        "Speed of contagion vs. policy response capacity",
    ],
    "political": [
        "Constitutional mechanism speed vs. crisis escalation rate",
        "Coalition maintenance under external pressure",
    ],
    "trade": [
        "Critical trade route concentration with no rapid alternative",
        "Trade finance credit concentration in limited institutions",
    ],
    "cyber": [
        "Legacy system vulnerability concentration in critical infrastructure",
        "Attribution certainty vs. response speed trade-off",
    ],
    "health": [
        "Medical supply chain concentration and distribution bottlenecks",
        "Diagnostic and treatment capacity concentration in urban centres",
    ],
    "social": [
        "Public trust deficit in institutional response mechanisms",
        "Information environment fragmentation impeding coordinated response",
    ],
}

_DOMAIN_SECOND_ORDER: dict[str, list[str]] = {
    "technology": [
        "Accelerated domestic technology sovereignty investment",
        "Emergence of alternative technology ecosystem",
        "Talent migration between competing technology blocs",
    ],
    "military": [
        "Accelerated defence procurement in neighbouring states",
        "Alliance architecture review and force posture adjustment",
        "Neutral state security guarantee demand increasing",
    ],
    "energy": [
        "Accelerated permitting for alternative energy infrastructure",
        "Demand-side efficiency measures reducing structural dependence",
        "New supplier market entry at premium pricing",
    ],
    "sanctions": [
        "Shadow financial system development by sanctioned entities",
        "Alternative currency settlement mechanism acceleration",
        "Third-country arbitrage opportunity emerging",
    ],
    "finance": [
        "Accelerated capital controls normalisation in affected region",
        "Regional development bank lending stepping in",
        "Sovereign wealth fund reallocation from affected markets",
    ],
    "political": [
        "Civil society mobilisation and street-level pressure increasing",
        "Media and information environment polarisation",
        "International election observation or mediation demand",
    ],
    "trade": [
        "Strategic stockpile accumulation accelerating in dependent states",
        "Regional trade bloc formation incentivised",
        "Domestic production subsidisation to reduce import dependence",
    ],
    "cyber": [
        "Accelerated critical infrastructure hardening across allied states",
        "International cyber norms framework negotiation intensified",
        "Private sector cybersecurity investment surge",
    ],
    "health": [
        "Accelerated domestic pharmaceutical and medical supply investment",
        "Regional health cooperation framework strengthened",
        "Public health preparedness investment surge",
    ],
    "social": [
        "Civil society organisation capacity building",
        "Social media platform governance reform pressure",
        "Government legitimacy reform investment",
    ],
}

_DOMAIN_ONTOLOGY_PATTERNS: dict[str, list[str]] = {
    "technology": ["Technology Transfer Restriction Pattern", "Supply Chain Fragmentation Pattern"],
    "military": ["Military Coercion Pattern", "Deterrence Breakdown Pattern"],
    "energy": ["Energy Supply Disruption Pattern", "Resource Leverage Pattern"],
    "sanctions": ["Hegemonic Sanctions Pattern", "Financial Isolation Pattern"],
    "finance": ["Capital Flight Pattern", "Financial Contagion Pattern"],
    "political": ["Political Polarisation Pattern", "Governance Crisis Pattern"],
    "trade": ["Trade Decoupling Pattern", "Supply Chain Reorientation Pattern"],
    "cyber": ["Cyber Escalation Pattern", "Critical Infrastructure Disruption Pattern"],
    "health": ["Pandemic Threshold Pattern", "Health System Cascade Pattern"],
    "social": ["Social Fragmentation Pattern", "Civil Unrest Cascade Pattern"],
}

_REGIME_STATE_DEFAULTS: dict[str, dict] = {
    "Nonlinear Escalation": {
        "damping_capacity": 0.29,
        "reversibility_index": 0.31,
        "threshold_distance": 0.18,
    },
    "Stress Accumulation": {
        "damping_capacity": 0.50,
        "reversibility_index": 0.55,
        "threshold_distance": 0.35,
    },
    "Cascade Risk": {
        "damping_capacity": 0.15,
        "reversibility_index": 0.20,
        "threshold_distance": 0.08,
    },
    "Attractor Lock-in": {
        "damping_capacity": 0.12,
        "reversibility_index": 0.15,
        "threshold_distance": 0.05,
    },
    "Linear": {
        "damping_capacity": 0.75,
        "reversibility_index": 0.80,
        "threshold_distance": 0.65,
    },
    "Dissipating": {
        "damping_capacity": 0.65,
        "reversibility_index": 0.70,
        "threshold_distance": 0.50,
    },
}

_CONFIDENCE_VELOCITY: dict[str, float] = {
    "Very High": 0.85,
    "High": 0.72,
    "Medium": 0.52,
    "Low": 0.32,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stub_or_404(assessment_id: str) -> None:
    """Raise 404 for any assessment_id that is not present in the store."""
    if assessment_store.get_assessment(assessment_id) is None:
        raise HTTPException(
            status_code=404,
            detail=f"Assessment '{assessment_id}' not found.",
        )


def _build_assessment_specific_outputs(assessment_id: str) -> dict[str, Any]:
    """
    Build assessment-specific stub outputs for non-demo assessments.

    Generates differentiated ``BriefOutput``, ``EvidenceOutput``,
    ``TriggersOutput``, ``AttractorsOutput``, and ``PropagationOutput``
    from the assessment's stored ``domain_tags``, ``region_tags``,
    ``analyst_notes``, and confidence metadata.  Called as the fallback
    when engines are unavailable, replacing the hardcoded Black Sea demo
    data for all assessments other than ``ae-204``.

    Returns an empty dict when the assessment cannot be found in the store.
    """
    assessment = assessment_store.get_assessment(assessment_id)
    if assessment is None:
        return {}

    domain_tags = list(assessment.domain_tags or [])
    region_tags = list(assessment.region_tags or [])
    analyst_notes = assessment.analyst_notes or ""
    now = datetime.now(timezone.utc)

    # Select primary and secondary domains, defaulting to "political" and "trade"
    primary_domain = domain_tags[0] if domain_tags else "political"
    secondary_domain = domain_tags[1] if len(domain_tags) > 1 else primary_domain

    region_str = ", ".join(region_tags) if region_tags else "the affected region"

    # Map last_confidence to a valid BriefOutput confidence literal
    _conf_map = {"Very High": "Very High", "High": "High", "Medium": "Medium", "Low": "Low"}
    confidence = _conf_map.get(assessment.last_confidence or "", "Medium")  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Brief
    # ------------------------------------------------------------------
    brief_tmpl = _DOMAIN_BRIEF_MAP.get(primary_domain, _DOMAIN_BRIEF_MAP["political"])
    brief = BriefOutput(
        assessment_id=assessment_id,
        forecast_posture=brief_tmpl["posture"],
        time_horizon="3-7 days",
        confidence=confidence,
        why_it_matters=brief_tmpl["matters_fmt"].format(regions=region_str),
        dominant_driver=brief_tmpl["driver"],
        strengthening_conditions=brief_tmpl["strengthening"],
        weakening_conditions=brief_tmpl["weakening"],
        invalidation_conditions=brief_tmpl["invalidation"],
        updated_at=now,
    )

    # ------------------------------------------------------------------
    # Evidence — synthesised from region sources and domain context
    # ------------------------------------------------------------------
    # Pick sources for the first known region, falling back to generic
    _default_sources = [
        "Regional security monitor",
        "Financial news wire",
        "Academic / think-tank analysis",
        "Analyst synthesis — internal assessment",
    ]
    first_region = region_tags[0] if region_tags else ""
    sources = _REGION_SOURCE_MAP.get(first_region, _default_sources)

    _quality_order = ["Primary", "High", "High", "Medium"]
    evidence_items: list[EvidenceItem] = []
    from datetime import timedelta  # noqa: PLC0415 – local import avoids top-level cost
    for i, domain in enumerate(domain_tags[:4]):
        src = sources[i % len(sources)]
        area_domains = domain_tags[max(0, i - 1): i + 2]
        evidence_items.append(
            EvidenceItem(
                evidence_id=f"ev-{assessment_id[:8]}-{i + 1:03d}",
                source=src,
                timestamp=now - timedelta(hours=(i + 1) * 6),
                source_quality=_quality_order[i % 4],  # type: ignore[arg-type]
                impacted_area=" / ".join(area_domains),
                structural_novelty=round(max(0.20, 0.78 - i * 0.10), 2),
                confidence_contribution=round(max(0.04, 0.18 - i * 0.04), 2),
                provenance_link=f"/api/v1/provenance/entity/ev-{assessment_id[:8]}-{i + 1:03d}",
            )
        )
    # Append an analyst-synthesis item when notes are present
    if analyst_notes and len(evidence_items) < 4:
        evidence_items.append(
            EvidenceItem(
                evidence_id=f"ev-{assessment_id[:8]}-{len(evidence_items) + 1:03d}",
                source="Analyst synthesis — internal assessment",
                timestamp=now - timedelta(hours=2),
                source_quality="Medium",
                impacted_area=" / ".join(domain_tags[:2]) if domain_tags else "general",
                structural_novelty=0.45,
                confidence_contribution=0.08,
                provenance_link=None,
            )
        )

    evidence = EvidenceOutput(
        assessment_id=assessment_id,
        evidence=evidence_items,
        updated_at=now,
    )

    # ------------------------------------------------------------------
    # Triggers
    # ------------------------------------------------------------------
    _default_trigger = _DOMAIN_TRIGGER_MAP["political"]
    trig1 = _DOMAIN_TRIGGER_MAP.get(primary_domain, _default_trigger)
    trig2 = _DOMAIN_TRIGGER_MAP.get(secondary_domain, _default_trigger)

    triggers = TriggersOutput(
        assessment_id=assessment_id,
        triggers=[
            TriggerOutput(
                name=trig1["name"],
                amplification_factor=0.78,
                jump_potential=trig1["jump"],  # type: ignore[arg-type]
                impacted_domains=trig1["impacted"],
                expected_lag_hours=trig1["lag_hours"],
                confidence=trig1["confidence"],
                watch_signals=trig1["watch"],
                damping_opportunities=trig1["damping"],
            ),
            TriggerOutput(
                name=trig2["name"],
                amplification_factor=0.58,
                jump_potential=trig2["jump"],  # type: ignore[arg-type]
                impacted_domains=trig2["impacted"],
                expected_lag_hours=trig2["lag_hours"],
                confidence=round(trig2["confidence"] - 0.08, 2),
                watch_signals=trig2["watch"],
                damping_opportunities=trig2["damping"],
            ),
        ],
        updated_at=now,
    )

    # ------------------------------------------------------------------
    # Attractors
    # ------------------------------------------------------------------
    _default_attractors = _DOMAIN_ATTRACTOR_MAP["political"]
    attr1_list = _DOMAIN_ATTRACTOR_MAP.get(primary_domain, _default_attractors)
    attr2_list = _DOMAIN_ATTRACTOR_MAP.get(secondary_domain, _default_attractors)
    attr1 = attr1_list[0]
    # For the secondary attractor, prefer the secondary domain's second entry
    # if available; otherwise use the primary domain's second entry.
    if len(attr2_list) > 1:
        attr2 = attr2_list[1]
    elif len(attr1_list) > 1:
        attr2 = attr1_list[1]
    else:
        attr2 = attr2_list[0]

    evidence_count = max(2, assessment.alert_count or 2)
    attractors = AttractorsOutput(
        assessment_id=assessment_id,
        attractors=[
            AttractorOutput(
                name=attr1["name"],
                pull_strength=0.72,
                horizon="3-10d",
                supporting_evidence_count=evidence_count,
                counterforces=attr1["counterforces"],
                invalidation_conditions=attr1["invalidation"],
                trend="up",
            ),
            AttractorOutput(
                name=attr2["name"],
                pull_strength=0.44,
                horizon="10-21d",
                supporting_evidence_count=max(1, evidence_count // 2),
                counterforces=attr2["counterforces"],
                invalidation_conditions=attr2["invalidation"],
                trend="stable",
            ),
        ],
        updated_at=now,
    )

    # ------------------------------------------------------------------
    # Propagation
    # ------------------------------------------------------------------
    prop_steps_tmpl = _DOMAIN_PROPAGATION_MAP.get(primary_domain, _DOMAIN_PROPAGATION_MAP["political"])
    sequence = [
        PropagationStep(step=i + 1, domain=dom, event=evt, time_bucket=tb)  # type: ignore[arg-type]
        for i, (dom, evt, tb) in enumerate(prop_steps_tmpl)
    ]
    bottlenecks = _DOMAIN_BOTTLENECKS.get(primary_domain, ["Structural bottleneck in primary domain pathway"])
    second_order = _DOMAIN_SECOND_ORDER.get(primary_domain, ["Systemic adaptation emerging in affected region"])

    propagation = PropagationOutput(
        assessment_id=assessment_id,
        sequence=sequence,
        bottlenecks=bottlenecks,
        second_order_effects=second_order,
        updated_at=now,
    )

    return {
        "brief": brief,
        "evidence": evidence,
        "triggers": triggers,
        "attractors": attractors,
        "propagation": propagation,
    }


async def _fetch_assessment_context(assessment_id: str) -> dict[str, Any]:
    """
    Fetch the assessment context required by the intelligence engines.

    Returns pre-built context for the demo assessment ``ae-204``.  For all
    other assessments, fetches real data from the assessment store and
    builds a context dict sufficient for the engine adapters.
    """
    if assessment_id == _DEMO_ID:
        return {
            "events": [
                {
                    "name": "Naval incident in contested strait",
                    "title": "Naval incident in contested strait",
                    "text": (
                        "Naval forces have deployed additional assets that block tanker transit "
                        "through the contested strait, triggering insurance withdrawal and causing "
                        "energy spot-price escalation across the corridor."
                    ),
                    "domains": ["military", "energy", "insurance", "finance"],
                    "entities": ["Naval Forces", "Contested Strait", "Transit Route"],
                    "source_reliability": 0.88,
                    "causal_weight": 0.82,
                    "confidence": 0.81,
                },
                {
                    "name": "Secondary sanctions package announced",
                    "title": "Secondary sanctions package announced",
                    "text": (
                        "The administration announces a secondary sanctions package targeting "
                        "financial institutions that facilitate corridor transit payments, "
                        "affecting energy trade financing and driving correspondent banking withdrawal."
                    ),
                    "domains": ["sanctions", "finance", "energy", "trade"],
                    "entities": ["Administration", "Financial Institutions", "Trade Finance"],
                    "source_reliability": 0.78,
                    "causal_weight": 0.65,
                    "confidence": 0.68,
                },
            ],
            "kg_paths": [
                {
                    "from_entity": "Naval Forces",
                    "to_entity": "Energy Corridor",
                    "relation": "BLOCKS",
                    "domain": "energy",
                    "strength": 0.85,
                },
                {
                    "from_entity": "Energy Corridor",
                    "to_entity": "Insurance Markets",
                    "relation": "AFFECTS",
                    "domain": "insurance",
                    "strength": 0.72,
                },
                {
                    "from_entity": "Sanctions Package",
                    "to_entity": "Banking Sector",
                    "relation": "AFFECTS",
                    "domain": "finance",
                    "strength": 0.68,
                },
            ],
            "causal_weights": {
                "Naval incident in contested strait": 0.82,
                "Secondary sanctions package announced": 0.65,
            },
            "velocity_data": {
                "military": 0.85,
                "energy": 0.60,
                "sanctions": 0.45,
                "finance": 0.35,
            },
            "ontology_activations": {
                "Hegemonic Sanctions Pattern": 0.71,
                "Naval Coercion Pattern": 0.68,
                "Financial Isolation Pattern": 0.64,
            },
            "regime_state": {
                "regime": "Nonlinear Escalation",
                "damping_capacity": 0.29,
                "reversibility_index": 0.31,
                "threshold_distance": 0.18,
            },
        }

    # For real assessments, fetch from store and build a usable context
    assessment = assessment_store.get_assessment(assessment_id)
    if assessment is None:
        return {}

    domain_tags = list(assessment.domain_tags or [])
    region_tags = list(assessment.region_tags or [])
    analyst_notes = assessment.analyst_notes or ""

    # Derive base velocity from last_confidence and alert_count
    base_velocity = _CONFIDENCE_VELOCITY.get(assessment.last_confidence or "", 0.52)
    alert_boost = min(0.15, (assessment.alert_count or 0) * 0.03)

    # Synthesise events from assessment metadata
    events: list[dict[str, Any]] = []
    event_confidence = round(min(0.90, base_velocity + alert_boost), 2)
    if analyst_notes:
        events.append(
            {
                "name": assessment.title,
                "title": assessment.title,
                "text": analyst_notes,
                "domains": domain_tags,
                "entities": region_tags,
                "source_reliability": round(min(0.90, base_velocity + 0.05), 2),
                "causal_weight": round(min(0.85, base_velocity + alert_boost), 2),
                "confidence": event_confidence,
            }
        )
    if domain_tags and region_tags:
        summary_text = (
            f"Structural activity detected across {', '.join(domain_tags)} domains "
            f"in {', '.join(region_tags)} regions."
        )
        events.append(
            {
                "name": f"{assessment.title} – structural signal",
                "title": f"{assessment.title} – structural signal",
                "text": summary_text,
                "domains": domain_tags,
                "entities": region_tags,
                "source_reliability": round(min(0.85, base_velocity), 2),
                "causal_weight": round(min(0.80, base_velocity + alert_boost - 0.05), 2),
                "confidence": round(min(0.85, event_confidence - 0.05), 2),
            }
        )

    # Build velocity data varying by domain priority and assessment confidence
    velocity_data = {}
    for i, d in enumerate(domain_tags):
        v = base_velocity + alert_boost - (i * 0.06)
        velocity_data[d] = round(max(0.20, min(0.95, v)), 2)

    # Populate ontology_activations with domain-appropriate patterns
    ontology_activations: dict[str, float] = {}
    for i, d in enumerate(domain_tags[:3]):
        patterns = _DOMAIN_ONTOLOGY_PATTERNS.get(d, [f"{d.title()} Structural Pattern"])
        activation = base_velocity + alert_boost - (i * 0.08)
        ontology_activations[patterns[0]] = round(max(0.35, min(0.90, activation)), 2)

    # Build KG paths between domain pairs
    kg_paths: list[dict[str, Any]] = []
    for i in range(len(domain_tags) - 1):
        kg_paths.append({
            "from_entity": f"{domain_tags[i].title()} Sector",
            "to_entity": f"{domain_tags[i + 1].title()} Sector",
            "relation": "AFFECTS",
            "domain": domain_tags[i],
            "strength": round(max(0.40, 0.75 - i * 0.10), 2),
        })

    # Build regime_state from assessment's last_regime
    last_regime = assessment.last_regime or "Stress Accumulation"
    regime_defaults = _REGIME_STATE_DEFAULTS.get(last_regime, _REGIME_STATE_DEFAULTS["Stress Accumulation"])
    regime_state = {
        "regime": last_regime,
        "damping_capacity": round(max(0.10, regime_defaults["damping_capacity"] - alert_boost), 2),
        "reversibility_index": round(max(0.10, regime_defaults["reversibility_index"] - alert_boost * 0.5), 2),
        "threshold_distance": round(max(0.05, regime_defaults["threshold_distance"] - alert_boost), 2),
    }

    return {
        "events": events,
        "kg_paths": kg_paths,
        "causal_weights": {ev["name"]: ev["causal_weight"] for ev in events},
        "velocity_data": velocity_data,
        "ontology_activations": ontology_activations,
        "regime_state": regime_state,
    }


def _build_assessment_context(assessment_id: str) -> dict:
    """Build context dict for the AttractorEngine from available assessment data."""
    if assessment_id == _DEMO_ID:
        return {
            "assessment_id": assessment_id,
            "title": _DEMO_ASSESSMENT.title,
            "domain_tags": list(_DEMO_ASSESSMENT.domain_tags),
            "region_tags": list(_DEMO_ASSESSMENT.region_tags),
            "evidence_count": len(_DEMO_EVIDENCE.evidence),
        }

    # For real assessments, fetch from store
    assessment = assessment_store.get_assessment(assessment_id)
    if assessment is None:
        return {}
    return {
        "assessment_id": assessment_id,
        "title": assessment.title,
        "domain_tags": list(assessment.domain_tags or []),
        "region_tags": list(assessment.region_tags or []),
        "evidence_count": assessment.alert_count or 0,
        "analyst_notes": assessment.analyst_notes or "",
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/trigger", response_model=dict)
async def trigger_assessment_generation(
    background_tasks: BackgroundTasks,
    hours: int = 48,
    min_events: int = 1,
    max_assessments: int = 10,
) -> dict:
    """
    Trigger Assessment auto-generation from recent news clusters (async).

    Returns a job_id immediately. Poll ``GET /assessments/status/{job_id}``
    to track progress.

    Query params:
    - ``hours``: look-back window for news articles (default 48).
    - ``min_events``: minimum events to form a cluster (default 1).
    - ``max_assessments``: cap on assessments generated per run (default 10).
    """
    job_id = f"job-{uuid4().hex[:8]}"
    _jobs[job_id] = {
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    background_tasks.add_task(_run_generation_job, job_id, hours, min_events, max_assessments)
    return {"job_id": job_id, "status": "queued"}


@router.get("/status/{job_id}", response_model=dict)
def get_job_status(job_id: str) -> dict:
    """Return the current status of an assessment generation job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job


@router.post("/generate-from-news", response_model=dict)
async def generate_assessments_from_news(
    hours: int = 48,
    min_events: int = 1,
    max_assessments: int = 10,
    max_articles: int = 30,
) -> dict:
    """
    Auto-generate Assessment records from the news event pipeline (synchronous).

    .. deprecated::
        Use ``POST /assessments/trigger`` instead. This endpoint is retained for
        backward compatibility but will time out when the LLM pipeline is slow.

    Query params:
    - ``hours``: look-back window for news articles (default 48).
    - ``min_events``: minimum events to form a cluster (default 1).
    - ``max_assessments``: cap on assessments generated per run (default 10).
    - ``max_articles``: cap on articles sent to LLM extraction (default 30).
    """
    import asyncio as _asyncio

    try:
        from app.services.assessment_generator import AssessmentGenerator  # noqa: PLC0415

        result = await _asyncio.wait_for(
            _asyncio.to_thread(
                AssessmentGenerator().generate_from_news,
                hours=hours,
                min_events_per_cluster=min_events,
                max_assessments=max_assessments,
                max_articles=max_articles,
            ),
            timeout=55.0,  # 55s: Railway default HTTP timeout is 60s; 5s margin for response overhead
        )
        return {"status": "ok", **result}
    except _asyncio.TimeoutError:
        logger.warning("generate_assessments_from_news timed out after 55s")
        return {
            "status": "timeout",
            "message": "Assessment generation timed out. Use POST /assessments/trigger for async generation.",
            "generated": 0,
            "updated": 0,
            "assessment_ids": [],
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("generate_assessments_from_news failed: %s", exc)
        return {
            "status": "error",
            "message": "Assessment generation failed. See server logs for details.",
        }


@router.get("", response_model=AssessmentListResponse)
def list_assessments() -> AssessmentListResponse:
    """Return all available assessments ordered by last updated."""
    items = assessment_store.list_assessments()
    return AssessmentListResponse(assessments=items, total=len(items))


@router.get("/{assessment_id}", response_model=Assessment)
def get_assessment(assessment_id: str) -> Assessment:
    """Return a single assessment by ID."""
    item = assessment_store.get_assessment(assessment_id)
    if item is None:
        raise HTTPException(
            status_code=404,
            detail=f"Assessment '{assessment_id}' not found",
        )
    return item


@router.post("", response_model=Assessment, status_code=201)
def create_assessment(data: AssessmentCreate) -> Assessment:
    """Create a new assessment and return it with a generated ID."""
    return assessment_store.create_assessment(data)


@router.patch("/{assessment_id}", response_model=Assessment)
def update_assessment(assessment_id: str, data: AssessmentUpdate) -> Assessment:
    """Apply partial updates to an existing assessment."""
    item = assessment_store.update_assessment(assessment_id, data)
    if item is None:
        raise HTTPException(
            status_code=404,
            detail=f"Assessment '{assessment_id}' not found",
        )
    return item


@router.delete("/{assessment_id}", status_code=204)
def delete_assessment(assessment_id: str) -> Response:
    """Delete an assessment. Returns 204 No Content on success."""
    deleted = assessment_store.delete_assessment(assessment_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Assessment '{assessment_id}' not found",
        )
    return Response(status_code=204)


@router.get("/{assessment_id}/brief", response_model=BriefOutput)
def get_brief(assessment_id: str) -> BriefOutput:
    """Return the executive brief for an assessment."""
    _stub_or_404(assessment_id)
    if assessment_id == _DEMO_ID:
        return _DEMO_BRIEF
    outputs = _build_assessment_specific_outputs(assessment_id)
    if outputs:
        return outputs["brief"]
    return _DEMO_BRIEF


@router.get("/{assessment_id}/regime", response_model=RegimeOutput)
async def get_regime(assessment_id: str) -> RegimeOutput:
    """
    Return the current regime state for an assessment.

    Calls the RegimeEngine adapter to compute real structural metrics from
    the backend intelligence engines.  Falls back to the demo stub when the
    assessment is not found or when context fetching fails.
    """
    _stub_or_404(assessment_id)

    try:
        from app.services.regime_engine import RegimeEngine  # noqa: PLC0415
        from app.services.assessment_context import fetch_assessment_context  # noqa: PLC0415

        context = await fetch_assessment_context(assessment_id)
        if not context:
            # Empty context – use stub data so the endpoint still returns a
            # valid response rather than an error.
            logger.info(
                "get_regime: empty context for %s; returning stub", assessment_id
            )
            return _DEMO_REGIME

        engine = RegimeEngine()
        return await engine.compute_regime(assessment_id, context)

    except Exception as exc:
        logger.warning(
            "get_regime: engine error for %s (%s); falling back to stub",
            assessment_id,
            exc,
        )
        return _DEMO_REGIME


@router.get("/{assessment_id}/triggers", response_model=TriggersOutput)
async def get_triggers(assessment_id: str) -> TriggersOutput:
    """Return the trigger amplification output for an assessment.

    When assessment context is available the response is computed by
    ``TriggerAmplificationEngine``, ranked by structural ``amplification_factor``
    (causal / nonlinear consequence weight), not by media salience or source count.

    Falls back to the stub response if the engine is unavailable or the
    context cannot be fetched.
    """
    _stub_or_404(assessment_id)

    if _TRIGGER_ENGINE_AVAILABLE and _TriggerEngine is not None:
        try:
            context = await _fetch_assessment_context(assessment_id)
            if context.get("events"):
                engine = _TriggerEngine()
                return await engine.compute_triggers(assessment_id, context)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "TriggerAmplificationEngine failed for %s, falling back to stub: %s",
                assessment_id,
                exc,
            )

    if assessment_id != _DEMO_ID:
        outputs = _build_assessment_specific_outputs(assessment_id)
        if outputs:
            return outputs["triggers"]
    return _DEMO_TRIGGERS


@router.get("/{assessment_id}/attractors", response_model=AttractorsOutput)
async def get_attractors(assessment_id: str) -> AttractorsOutput:
    """Return the attractor output for an assessment (live engine with stub fallback)."""
    _stub_or_404(assessment_id)
    context = _build_assessment_context(assessment_id)
    if context:
        try:
            from app.services.attractor_engine import AttractorEngine
            engine = AttractorEngine()
            return await engine.compute_attractors(assessment_id, context)
        except Exception:
            logger.warning(
                "get_attractors: engine unavailable for %s, returning stub", assessment_id
            )
    if assessment_id != _DEMO_ID:
        outputs = _build_assessment_specific_outputs(assessment_id)
        if outputs:
            return outputs["attractors"]
    return _DEMO_ATTRACTORS


@router.get("/{assessment_id}/propagation", response_model=PropagationOutput)
async def get_propagation(assessment_id: str) -> PropagationOutput:
    """
    Return the cross-domain propagation sequence for an assessment.

    Calls the PropagationEngine to compute a time-ordered domain transfer
    sequence with bottleneck and second-order effect analysis.  Falls back
    to the demo stub on any engine failure so the endpoint never returns a
    500 error.
    """
    _stub_or_404(assessment_id)

    try:
        from app.services.propagation_engine import PropagationEngine  # noqa: PLC0415

        context = await _fetch_assessment_context(assessment_id)
        if not context:
            logger.info(
                "get_propagation: empty context for %s; falling back", assessment_id
            )
            if assessment_id != _DEMO_ID:
                outputs = _build_assessment_specific_outputs(assessment_id)
                if outputs:
                    return outputs["propagation"]
            return _DEMO_PROPAGATION

        engine = PropagationEngine()
        return await engine.compute_propagation(assessment_id, context)

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "get_propagation: engine error for %s (%s); falling back to stub",
            assessment_id,
            exc,
        )

    if assessment_id != _DEMO_ID:
        outputs = _build_assessment_specific_outputs(assessment_id)
        if outputs:
            return outputs["propagation"]
    return _DEMO_PROPAGATION


@router.get("/{assessment_id}/delta", response_model=DeltaOutput)
async def get_delta(assessment_id: str) -> DeltaOutput:
    """Return the update delta output for an assessment (live engine with stub fallback)."""
    _stub_or_404(assessment_id)
    try:
        from app.services.delta_engine import AssessmentSnapshot, DeltaEngine  # noqa: PLC0415

        engine = DeltaEngine()
        context = _build_assessment_context(assessment_id)
        snapshot = AssessmentSnapshot(
            assessment_id=assessment_id,
            regime=_DEMO_REGIME.current_regime,
            threshold_distance=_DEMO_REGIME.threshold_distance,
            damping_capacity=_DEMO_REGIME.damping_capacity,
            confidence=0.72,
            trigger_rankings=[
                {
                    "name": t.name,
                    "rank": i + 1,
                    "amplification_factor": t.amplification_factor,
                }
                for i, t in enumerate(_DEMO_TRIGGERS.triggers)
            ],
            attractor_rankings=[
                {
                    "name": a.name,
                    "rank": i + 1,
                    "pull_strength": a.pull_strength,
                }
                for i, a in enumerate(_DEMO_ATTRACTORS.attractors)
            ],
            evidence_count=len(_DEMO_EVIDENCE.evidence),
        )
        return await engine.compute_delta(assessment_id, snapshot)
    except Exception:
        logger.warning(
            "get_delta: engine unavailable for %s, returning stub", assessment_id
        )
    return _DEMO_DELTA


@router.get("/{assessment_id}/evidence", response_model=EvidenceOutput)
def get_evidence(assessment_id: str) -> EvidenceOutput:
    """Return the evidence items for an assessment."""
    _stub_or_404(assessment_id)
    if assessment_id == _DEMO_ID:
        return _DEMO_EVIDENCE
    outputs = _build_assessment_specific_outputs(assessment_id)
    if outputs:
        return outputs["evidence"]
    return _DEMO_EVIDENCE


# ---------------------------------------------------------------------------
# Coupling endpoint (PR-14)
# ---------------------------------------------------------------------------

_DEMO_COUPLING = CouplingOutput(
    assessment_id=_DEMO_ID,
    pairs=[
        CouplingPair(
            domain_a="military",
            domain_b="energy",
            coupling_strength=2.14,
            is_amplifying=True,
            amplification_label="High amplification",
        ),
        CouplingPair(
            domain_a="finance",
            domain_b="sanctions",
            coupling_strength=1.87,
            is_amplifying=True,
            amplification_label="High amplification",
        ),
        CouplingPair(
            domain_a="energy",
            domain_b="trade",
            coupling_strength=1.12,
            is_amplifying=False,
            amplification_label="Moderate coupling",
        ),
    ],
    updated_at=_NOW,
)


@router.get("/{assessment_id}/coupling", response_model=CouplingOutput)
def get_coupling(assessment_id: str) -> CouplingOutput:
    """
    Return the top structural coupling pairs for an assessment.

    Surfaces domain pairs with highest nonlinear coupling pressure derived
    from the Lie algebra commutator.  Falls back to stub data when the
    coupling engine is unavailable.
    """
    _stub_or_404(assessment_id)
    try:
        from app.services.coupling_detector import CouplingDetector  # noqa: PLC0415

        # For the demo assessment, supply representative active pattern pairs
        if assessment_id == _DEMO_ID:
            active_pairs = [
                ("Naval Coercion Pattern", "Hegemonic Sanctions Pattern"),
                ("Financial Isolation Pattern", "Energy Disruption Pattern"),
            ]
        else:
            active_pairs = []

        detector = CouplingDetector()
        result = detector.compute_coupling(assessment_id, active_pairs)
        if result.pairs:
            return result
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "get_coupling: engine error for %s (%s); falling back to stub",
            assessment_id,
            exc,
        )
    return _DEMO_COUPLING
