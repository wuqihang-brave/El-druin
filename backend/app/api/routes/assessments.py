"""
Assessments API routes
======================

Endpoints:
  GET  /assessments                              – list all assessments
  GET  /assessments/{assessment_id}              – single assessment detail
  GET  /assessments/{assessment_id}/brief        – executive brief
  GET  /assessments/{assessment_id}/regime       – regime state output (real engine, PR-4)
  GET  /assessments/{assessment_id}/triggers     – trigger amplification output
  GET  /assessments/{assessment_id}/attractors   – attractor output
  GET  /assessments/{assessment_id}/propagation  – propagation sequence output (real engine, PR-7)
  GET  /assessments/{assessment_id}/delta        – update delta output
  GET  /assessments/{assessment_id}/evidence     – evidence output

The regime endpoint calls the real RegimeEngine adapter (PR-4).
The propagation endpoint calls the real PropagationEngine adapter (PR-7).
All other endpoints remain as stubs keyed to assessment_id "ae-204".
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from app.schemas.assessment import Assessment, AssessmentListResponse, AssessmentStatus, AssessmentType

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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assessments", tags=["assessments"])

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
# Helpers
# ---------------------------------------------------------------------------

def _stub_or_404(assessment_id: str) -> None:
    """Raise 404 for any assessment_id that is not the demo stub."""
    if assessment_id != _DEMO_ID:
        raise HTTPException(
            status_code=404,
            detail=f"Assessment '{assessment_id}' not found. Only '{_DEMO_ID}' is available in stub mode.",
        )


async def _fetch_assessment_context(assessment_id: str) -> dict[str, Any]:
    """
    Fetch the assessment context required by ``TriggerAmplificationEngine``.

    Currently returns a pre-built context for the demo assessment ``ae-204``
    (Black Sea Energy Corridor – Structural Watch).  Returns an empty dict for
    any other assessment ID, which causes the route to fall back to the stub.
    """
    if assessment_id != _DEMO_ID:
        return {}

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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=AssessmentListResponse)
def list_assessments() -> AssessmentListResponse:
    """Return all available assessments."""
    return AssessmentListResponse(assessments=[_DEMO_ASSESSMENT], total=1)


@router.get("/{assessment_id}", response_model=Assessment)
def get_assessment(assessment_id: str) -> Assessment:
    """Return a single assessment by ID."""
    _stub_or_404(assessment_id)
    return _DEMO_ASSESSMENT


@router.get("/{assessment_id}/brief", response_model=BriefOutput)
def get_brief(assessment_id: str) -> BriefOutput:
    """Return the executive brief for an assessment."""
    _stub_or_404(assessment_id)
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

    return _DEMO_TRIGGERS


@router.get("/{assessment_id}/attractors", response_model=AttractorsOutput)
def get_attractors(assessment_id: str) -> AttractorsOutput:
    """Return the attractor output for an assessment."""
    _stub_or_404(assessment_id)
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
                "get_propagation: empty context for %s; returning stub", assessment_id
            )
            return _DEMO_PROPAGATION

        engine = PropagationEngine()
        return await engine.compute_propagation(assessment_id, context)

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "get_propagation: engine error for %s (%s); falling back to stub",
            assessment_id,
            exc,
        )
        return _DEMO_PROPAGATION


@router.get("/{assessment_id}/delta", response_model=DeltaOutput)
def get_delta(assessment_id: str) -> DeltaOutput:
    """Return the update delta output for an assessment."""
    _stub_or_404(assessment_id)
    return _DEMO_DELTA


@router.get("/{assessment_id}/evidence", response_model=EvidenceOutput)
def get_evidence(assessment_id: str) -> EvidenceOutput:
    """Return the evidence items for an assessment."""
    _stub_or_404(assessment_id)
    return _DEMO_EVIDENCE
