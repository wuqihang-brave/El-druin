"""
Assessment Context Fetcher
==========================

Builds the context dict required by RegimeEngine.compute_regime() for a
given assessment_id.

In the current architecture there is no persistent assessment-specific event
store, so this helper constructs a best-effort context from the available
intelligence modules using the demo data as a seed.  When no data can be
obtained the function returns an empty dict and the caller (the regime route)
will fall back gracefully to the stub response.

The returned dict has the following keys (all optional):

    ``mechanisms``   – List[MechanismLabel] from deduction_engine
    ``deduction``    – dict from DeductionResult.to_strict_json()
    ``forecast``     – dict from run_forecast()
    ``sacred_sword`` – dict with at least a ``confidence_score`` key
    ``events``       – List[str] of raw event text
"""

from __future__ import annotations

import logging
import sys
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Demo seed data (used as context when no real event store is available)
# ---------------------------------------------------------------------------

_DEMO_ASSESSMENT_ID = "ae-204"

_DEMO_EVENTS: List[str] = [
    "Naval assets deployed in contested Black Sea strait; tanker transit suspended.",
    "Insurance premiums spike following corridor blockade reports.",
    "EU emergency energy council convened; secondary sanctions expansion tabled.",
    "Diplomatic back-channel communications reported but unconfirmed.",
    "Regional sovereign bond spreads widened 40 basis points on news.",
]

_DEMO_GRAPH_CONTEXT: Dict[str, Any] = {
    "entities": ["Russia", "Ukraine", "EU", "NATO", "Black Sea", "Energy Corridor"],
    "relations": [
        {
            "source": "Russia",
            "type": "military_action",
            "target": "Black Sea",
            "mechanism": "Naval blockade of energy transit routes",
        },
        {
            "source": "EU",
            "type": "sanctions",
            "target": "Russia",
            "mechanism": "Secondary sanctions on corridor transit",
        },
        {
            "source": "Energy Corridor",
            "type": "affects",
            "target": "EU",
            "mechanism": "Supply disruption propagation to spot markets",
        },
    ],
}


def _ensure_backend_on_path() -> None:
    """Add backend directory to sys.path if not already present."""
    here = os.path.abspath(__file__)
    # traverse up to find backend/
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)


async def fetch_assessment_context(assessment_id: str) -> Dict[str, Any]:
    """
    Fetch KG nodes, recent events, ontology activations, and evidence
    relevant to ``assessment_id``.

    Returns a context dict usable by all engine adapters (primarily
    RegimeEngine).  Returns an empty dict if nothing can be fetched so
    that callers can fall back gracefully.
    """
    _ensure_backend_on_path()

    context: Dict[str, Any] = {}
    _assessment = None  # kept for later use in deduction step

    # ── 1. Determine seed events ──────────────────────────────────────────
    if assessment_id == _DEMO_ASSESSMENT_ID:
        events = _DEMO_EVENTS
        graph_context = _DEMO_GRAPH_CONTEXT
    else:
        # Fetch real assessment from the store
        from app.core.assessment_store import assessment_store  # noqa: PLC0415

        assessment = assessment_store.get_assessment(assessment_id)
        _assessment = assessment
        if assessment is None:
            logger.info(
                "fetch_assessment_context: assessment %s not found",
                assessment_id,
            )
            return {}

        # Synthesise seed events from assessment metadata
        domain_tags = list(assessment.domain_tags or [])
        region_tags = list(assessment.region_tags or [])
        analyst_notes = assessment.analyst_notes or ""

        events = []
        if analyst_notes:
            events.append(analyst_notes)
        if domain_tags and region_tags:
            events.append(
                f"Structural activity detected across {', '.join(domain_tags)} domains "
                f"in {', '.join(region_tags)} regions."
            )

        # Query KuzuDB for related entities and relations
        graph_context: Dict[str, Any] = {"entities": [], "relations": []}
        try:
            from app.knowledge.knowledge_graph import get_knowledge_graph  # noqa: PLC0415

            kg = get_knowledge_graph()
            # Get entities related to assessment regions/domains
            for region in region_tags[:3]:
                neighbours = kg.get_neighbours(region, depth=1)
                for n in neighbours[:5]:
                    entity_name = n.get("name") or n.get("entity_name", "")
                    if entity_name and entity_name not in graph_context["entities"]:
                        graph_context["entities"].append(entity_name)
            # Add domain tags as seed entities too
            graph_context["entities"].extend(
                [t for t in domain_tags if t not in graph_context["entities"]]
            )
            # Get relations from KG
            relations = kg.get_relations(limit=20)
            graph_context["relations"] = relations[:10]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not fetch KG context for %s: %s", assessment_id, exc)

        logger.info(
            "fetch_assessment_context: built context for %s (%d events, %d entities)",
            assessment_id,
            len(events),
            len(graph_context["entities"]),
        )

    context["events"] = events

    # ── 2. Extract mechanism labels (no LLM, pure heuristic) ─────────────
    try:
        from intelligence.deduction_engine import (  # type: ignore
            extract_mechanism_labels,
            DrivingFactorAggregator,
        )
        news_text      = " ".join(events)
        graph_text_raw = _graph_context_to_text(graph_context)
        mechanisms     = extract_mechanism_labels(
            graph_context=graph_text_raw,
            news_text=news_text,
            seed_entities=graph_context.get("entities", []),
        )
        context["mechanisms"] = mechanisms

        aggregator  = DrivingFactorAggregator()
        driving     = aggregator.aggregate(mechanisms)
        context["driving_factor"] = driving

        logger.info(
            "fetch_assessment_context: extracted %d mechanism labels for %s",
            len(mechanisms),
            assessment_id,
        )
    except Exception as exc:
        logger.warning("Could not extract mechanism labels: %s", exc)
        context["mechanisms"] = []

    # ── 3. Build a lightweight deduction dict from available signals ──────
    # We do NOT call the LLM here; we synthesise a minimal deduction dict
    # from the mechanism labels and demo signals that is sufficient for the
    # regime engine's metric computations.
    try:
        mechanisms = context.get("mechanisms", [])
        if mechanisms:
            # Use the strongest mechanism to estimate scenario probabilities
            best_mech = max(mechanisms, key=lambda m: getattr(m, "strength", 0.5))
            alpha_prob = round(1.0 - best_mech.strength * 0.4, 3)   # higher strength → lower alpha
            beta_prob  = round(best_mech.strength * 0.5, 3)
        elif _assessment is not None and _assessment.last_regime:
            # Map the assessment's stored regime to plausible beta-scenario probability
            # priors so each assessment produces differentiated deduction outputs even
            # when no mechanism labels can be extracted.  "Dissipating" intentionally
            # uses a low value because it indicates de-escalation, not escalation.
            _REGIME_BETA: Dict[str, float] = {
                "Linear": 0.15,
                "Stress Accumulation": 0.32,
                "Nonlinear Escalation": 0.52,
                "Cascade Risk": 0.68,
                "Attractor Lock-in": 0.82,
                "Dissipating": 0.12,
            }
            beta_prob  = _REGIME_BETA.get(_assessment.last_regime, 0.35)
            alpha_prob = round(1.0 - beta_prob * 0.6, 3)
            beta_prob  = round(beta_prob, 3)
        else:
            alpha_prob = 0.65
            beta_prob  = 0.35

        # Vary probabilities by alert_count so assessments with more events
        # trend towards higher beta (escalation) probability.
        _MAX_ALERT_BOOST = 0.15      # cap on total boost regardless of event count
        _ALERT_BOOST_FACTOR = 0.005  # beta boost per additional alert event
        if _assessment is not None and _assessment.alert_count:
            alert_boost = min(_MAX_ALERT_BOOST, _assessment.alert_count * _ALERT_BOOST_FACTOR)
            beta_prob  = round(min(0.95, beta_prob + alert_boost), 3)
            alpha_prob = round(max(0.05, alpha_prob - alert_boost * 0.5), 3)

        context["deduction"] = {
            "confidence":      round((alpha_prob + beta_prob) / 2.0, 3),
            "driving_factor":  context.get("driving_factor", ""),
            "scenario_alpha":  {"probability": alpha_prob},
            "scenario_beta":   {"probability": beta_prob},
            "mechanism_count": len(mechanisms),
        }
    except Exception as exc:
        logger.warning("Could not build deduction dict: %s", exc)

    # ── 4. Run a lightweight ontology forecast (no LLM) ──────────────────
    try:
        from intelligence.ontology_forecaster import run_forecast  # type: ignore
        # Use domain-matched initial patterns from mechanism labels
        domains = list({
            (m.domain.value if hasattr(m.domain, "value") else str(m.domain))
            for m in context.get("mechanisms", [])
        })
        if not domains:
            domains = ["geopolitics"]

        forecast = run_forecast(
            initial_patterns=_domains_to_initial_patterns(domains),
            horizon_steps=4,
            llm_service=None,
        )
        context["forecast"] = forecast
        logger.info(
            "fetch_assessment_context: forecast ran %d steps for %s",
            len(forecast.get("simulation_steps", [])),
            assessment_id,
        )
    except Exception as exc:
        logger.warning("Could not run ontology forecast: %s", exc)
        context["forecast"] = {}

    return context


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _graph_context_to_text(graph_context: Dict[str, Any]) -> str:
    """Convert a graph-context dict to the plain-text format expected by
    extract_mechanism_labels."""
    lines: List[str] = []

    for rel in graph_context.get("relations", []):
        if isinstance(rel, dict):
            src  = rel.get("source", "")
            rtype = rel.get("type", "")
            tgt  = rel.get("target", "")
            mech = rel.get("mechanism", "")
            lines.append(f"{src} -> {tgt}: {mech} [{rtype}]")
        elif isinstance(rel, str):
            lines.append(rel)

    for ent in graph_context.get("entities", []):
        lines.append(str(ent))

    return "\n".join(lines)


# Mapping from domain names to representative initial patterns that exist in
# the ontology composition table (using English display names that are valid
# internal keys when translated back via internal_pattern).
_DOMAIN_TO_PATTERNS: Dict[str, List[str]] = {
    "geopolitics":  ["霸權制裁模式", "大國脅迫/威懾模式"],
    "military":     ["正式軍事同盟模式", "大國脅迫/威懾模式"],
    "economics":    ["金融孤立/SWIFT切斷模式", "霸權制裁模式"],
    "technology":   ["實體清單技術封鎖模式"],
    "humanitarian": [],
    "legal":        [],
    "sports":       [],
    "business":     [],
    "society":      [],
    "science":      [],
}


def _domains_to_initial_patterns(domains: List[str]) -> List[str]:
    """Return a list of initial ontology patterns for the given domains."""
    patterns: List[str] = []
    seen: set = set()
    for dom in domains:
        for p in _DOMAIN_TO_PATTERNS.get(dom, []):
            if p not in seen:
                patterns.append(p)
                seen.add(p)
    return patterns if patterns else ["霸權制裁模式"]
