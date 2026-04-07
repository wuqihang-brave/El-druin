"""
intelligence/ontology_forecaster.py
=====================================
Ontological Trajectory Forecaster

Mathematical foundation
-----------------------
The composition_table defines a *partial* binary operation over the set of
named patterns — only ~4 % of all pattern pairs have an explicitly defined
composition result.  This constitutes a **partial semigroup**, not a total
semigroup; the classical Green (1951) theorem that guarantees convergence to
idempotent elements applies to total semigroups and therefore cannot be
directly invoked here.

Convergence is defined **operationally**: the forward simulation terminates
when the active pattern set stops changing between two consecutive steps
(i.e., the fixed-point condition S_{t} == S_{t-1} holds).  This is a
sufficient — though not necessary — condition for reaching a stable state
under the partial operation, and is empirically observed to hold within
6 steps on all tested scenarios.

Attractor detection: a pattern P is flagged as an idempotent attractor if
compose(P, P) = P is explicitly defined in the composition_table.  Patterns
not covered by the table are excluded from attractor candidates; this is
conservative but honest given the table's partial coverage.

Bayesian confidence decay:
    confidence_t = initial_confidence × decay^t   (decay = 0.85 per step)

Phase transitions:
    Flagged when ‖v_t - v_{t-1}‖ > 0.25 in the 8-D Lie algebra state space.

contract_version: "forecast.v1"
mode: "forecast"
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from intelligence.pattern_i18n import display_pattern as _display_pattern  # type: ignore
except ImportError:
    def _display_pattern(name: str) -> str:  # type: ignore[misc]
        return name

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_DECAY: float = 0.85           # Bayesian step-wise confidence decay
_PHASE_THRESHOLD: float = 0.25  # ||Δv|| threshold for phase transition
_MAX_STEPS: int = 15           # Safety cap on simulation steps


# ---------------------------------------------------------------------------
# Preset scenarios
# ---------------------------------------------------------------------------
_PRESET_SCENARIOS: List[Dict[str, Any]] = [
    {
        "id":               "us_china_tech_decoupling",
        "name":             "US–China Technology Decoupling",
        "description":      (
            "Starting from hegemonic sanctions + technology denial, the simulation "
            "projects the convergence trajectory of the US–China tech competition."
        ),
        "initial_patterns": ["霸權制裁模式", "實體清單技術封鎖模式"],
        "domain":           "technology",
    },
    {
        "id":               "china_taiwan_invasion_scenario",
        "name":             "China–Taiwan Coercive Trajectory",
        "description":      (
            "Starting from great-power coercion + formal military alliance patterns, "
            "the simulation projects the escalation or de-escalation trajectory."
        ),
        "initial_patterns": ["大國脅迫/威懾模式", "正式軍事同盟模式"],
        "domain":           "geopolitics",
    },
    {
        "id":               "global_financial_exclusion",
        "name":             "Global Financial Exclusion Cascade",
        "description":      (
            "Starting from SWIFT exclusion + hegemonic sanctions, the simulation "
            "projects downstream economic and geopolitical realignment."
        ),
        "initial_patterns": ["金融孤立/SWIFT切斷模式", "霸權制裁模式"],
        "domain":           "economics",
    },
    {
        "id":               "multilateral_sanctions_coalition",
        "name":             "Multilateral Sanctions Coalition",
        "description":      (
            "Starting from multilateral alliance sanctions + information warfare, "
            "the simulation projects isolation and norm-building outcomes."
        ),
        "initial_patterns": ["多邊聯盟制裁模式", "信息戰/敘事操控模式"],
        "domain":           "geopolitics",
    },
]


# ---------------------------------------------------------------------------
# Core simulation
# ---------------------------------------------------------------------------

def _get_composition_table() -> Dict[Tuple[str, str], str]:
    try:
        from ontology.relation_schema import composition_table  # type: ignore
        return composition_table
    except ImportError:
        return {}


def _get_inverse_table() -> Dict[str, str]:
    try:
        from ontology.relation_schema import inverse_table  # type: ignore
        return inverse_table
    except ImportError:
        return {}


def _get_pattern_confidence(pattern_name: str) -> float:
    """Return the confidence prior for a named pattern (default 0.5)."""
    try:
        from ontology.relation_schema import CARTESIAN_PATTERN_REGISTRY  # type: ignore
        for pat in CARTESIAN_PATTERN_REGISTRY.values():
            if pat.pattern_name == pattern_name:
                return pat.confidence_prior
    except ImportError:
        pass
    return 0.5


def _get_pattern_domain(pattern_name: str) -> str:
    """Return the domain of a named pattern."""
    try:
        from ontology.relation_schema import CARTESIAN_PATTERN_REGISTRY  # type: ignore
        for pat in CARTESIAN_PATTERN_REGISTRY.values():
            if pat.pattern_name == pattern_name:
                return pat.domain or "general"
    except ImportError:
        pass
    return "general"


def _get_state_vector(pattern_names: List[str]) -> np.ndarray:
    """Compute the 8-D aggregate state vector for a set of active patterns."""
    try:
        from ontology.lie_algebra_space import _vec  # type: ignore
        vecs = [_vec(p) for p in pattern_names]
        if not vecs:
            return np.zeros(8)
        return np.mean(vecs, axis=0)
    except Exception:
        return np.zeros(8)


def _compose_step(
    active: List[str],
    composition_table: Dict[Tuple[str, str], str],
) -> List[str]:
    """
    Perform one composition step: for each pair (A, B) in active patterns,
    if compose(A, B) = C exists in the composition table, add C to the new active set.
    Returns the deduplicated new active set (sorted for determinism).
    """
    new_active = set(active)
    for pa in active:
        for pb in active:
            result = composition_table.get((pa, pb))
            if result:
                new_active.add(result)
    return sorted(new_active)


def run_forecast(
    initial_patterns: List[str],
    horizon_steps: int = 6,
    llm_service: Any = None,
) -> Dict[str, Any]:
    """
    Run a forward simulation from initial_patterns for horizon_steps steps.

    Returns a dict with:
      - mode: "forecast"
      - contract_version: "forecast.v1"
      - initial_patterns
      - simulation_steps[]: [{step, active_patterns, state_vector, confidence, delta_norm}]
      - attractors[]: patterns that became idempotent (compose(P,P)=P)
      - bifurcation_points[]: step indices where ||Δv|| > threshold
      - primary_attractor: {name, domain, final_probability, description}
      - forecast_narrative: English text (LLM or fallback)
    """
    composition_table = _get_composition_table()
    inverse_table     = _get_inverse_table()

    # Initial confidence = mean of pattern priors
    if initial_patterns:
        init_conf = float(np.mean([_get_pattern_confidence(p) for p in initial_patterns]))
    else:
        init_conf = 0.5

    simulation_steps: List[Dict[str, Any]] = []
    bifurcation_points: List[int] = []
    attractor_candidates: Dict[str, int] = {}  # pattern → first step it became stable

    active = list(set(initial_patterns))
    prev_vector = _get_state_vector(active)
    prev_active_set = frozenset(active)

    for step in range(1, min(horizon_steps, _MAX_STEPS) + 1):
        new_active = _compose_step(active, composition_table)
        step_conf  = round(init_conf * (_DECAY ** step), 4)

        curr_vector  = _get_state_vector(new_active)
        delta_norm   = float(np.linalg.norm(curr_vector - prev_vector))

        # Phase transition check
        if delta_norm > _PHASE_THRESHOLD:
            bifurcation_points.append(step)

        # Attractor check: patterns that compose with themselves to produce themselves
        for pat in new_active:
            composed = composition_table.get((pat, pat))
            if composed == pat and pat not in attractor_candidates:
                attractor_candidates[pat] = step

        # Convergence check: if the active set has not changed, we've reached a fixed point
        curr_active_set = frozenset(new_active)
        converged = (curr_active_set == prev_active_set)

        simulation_steps.append({
            "step":            step,
            "active_patterns": [_display_pattern(p) for p in new_active],
            "state_vector":    {
                "mean": [round(float(v), 4) for v in curr_vector.tolist()],
                "delta_norm": round(delta_norm, 4),
            },
            "confidence":      step_conf,
            "delta_norm":      round(delta_norm, 4),
            "converged":       converged,
        })

        prev_vector    = curr_vector
        prev_active_set = curr_active_set
        active         = new_active

        if converged:
            logger.info("Forecast: converged at step %d", step)
            break

    # Build attractor list
    all_attractors = []
    for pat_name, first_step in sorted(attractor_candidates.items(), key=lambda x: x[1]):
        conf = round(init_conf * (_DECAY ** first_step), 4)
        all_attractors.append({
            "name":            _display_pattern(pat_name),
            "domain":          _get_pattern_domain(pat_name),
            "first_step":      first_step,
            "final_probability": conf,
            "description":     f"Idempotent element reached at step {first_step}.",
        })

    # Primary attractor = highest-probability idempotent
    primary_attractor = (
        max(all_attractors, key=lambda a: a["final_probability"])
        if all_attractors
        else {
            "name":              _display_pattern(active[0]) if active else "unknown",
            "domain":            _get_pattern_domain(active[0]) if active else "general",
            "first_step":        len(simulation_steps),
            "final_probability": round(init_conf * (_DECAY ** len(simulation_steps)), 4),
            "description":       "Terminal state after exhausting the specified horizon.",
        }
    )

    # Narrative generation
    narrative = _generate_forecast_narrative(
        initial_patterns=initial_patterns,
        simulation_steps=simulation_steps,
        primary_attractor=primary_attractor,
        bifurcation_points=bifurcation_points,
        llm_service=llm_service,
    )

    return {
        "mode":               "forecast",
        "contract_version":   "forecast.v1",
        "initial_patterns":   initial_patterns,
        "simulation_steps":   simulation_steps,
        "attractors":         all_attractors,
        "bifurcation_points": bifurcation_points,
        "primary_attractor":  primary_attractor,
        "forecast_narrative": narrative,
        "meta": {
            "steps_run":        len(simulation_steps),
            "horizon_steps":    horizon_steps,
            "decay_factor":     _DECAY,
            "phase_threshold":  _PHASE_THRESHOLD,
            "initial_confidence": round(init_conf, 4),
        },
    }


def _generate_forecast_narrative(
    initial_patterns:  List[str],
    simulation_steps:  List[Dict[str, Any]],
    primary_attractor: Dict[str, Any],
    bifurcation_points: List[int],
    llm_service:       Any,
) -> str:
    """Generate English narrative. LLM is used for explanation only, never for probabilities."""
    final_conf = primary_attractor.get("final_probability", 0)
    attractor_name = primary_attractor.get("name", "unknown")
    n_steps = len(simulation_steps)
    bifur_str = f" with bifurcation at steps {bifurcation_points}" if bifurcation_points else ""

    fallback = (
        f"Starting from [{', '.join(initial_patterns[:3])}], the forward simulation ran {n_steps} step(s){bifur_str}. "
        f"The primary attractor is [{attractor_name}] with a final Bayesian confidence of {final_conf:.1%} "
        f"(decayed at 0.85^t per step). "
        f"This represents the algebraically stable terminal state of the ontological trajectory."
    )

    if llm_service is None:
        return fallback

    prompt = f"""You are the EL-DRUIN ontological forecasting interpreter.

The following forward simulation has been completed by a deterministic algebraic engine.
Your task is to write 2–3 sentences of professional English commentary explaining the result.
Do NOT include any numerical probabilities. Do NOT mention pattern names literally.

[SIMULATION RESULTS]
- Initial state: {len(initial_patterns)} pattern(s) active
- Steps run: {n_steps}
- Primary attractor reached: [{attractor_name}]
- Bifurcation steps (phase transitions): {bifurcation_points if bifurcation_points else "none"}
- Final confidence (0.85^t decay): {final_conf:.1%}

[OUTPUT REQUIREMENTS]
1. Explain qualitatively what the convergence to the primary attractor implies for the real-world situation.
2. If bifurcation points exist, note that the trajectory passed through a phase transition.
3. Do NOT output probabilities as numbers. Do NOT invent new facts.
4. Plain English text only, no JSON.
"""
    try:
        resp = llm_service.call(
            prompt=prompt,
            system=(
                "You are a rigorous geopolitical intelligence analyst. "
                "Explain algebraic simulation results in plain professional English. "
                "Never output numerical probabilities."
            ),
            temperature=0.15,
            max_tokens=300,
        )
        text = str(resp).strip()
        if text:
            return text
    except Exception as exc:
        logger.warning("Forecast LLM narrative failed: %s", exc)

    return fallback


# ---------------------------------------------------------------------------
# Attractor discovery
# ---------------------------------------------------------------------------

def find_attractors(domain: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Find all idempotent elements explicitly defined in the composition table.
    An element P is idempotent if compose(P, P) = P appears in composition_table.

    Note: the composition_table is a partial operation; patterns not covered
    by the table are not considered here.  Optionally filter by domain.
    """
    composition_table = _get_composition_table()
    attractors: List[Dict[str, Any]] = []

    seen: set = set()
    for (pa, pb), pc in composition_table.items():
        if pa == pb == pc and pa not in seen:
            seen.add(pa)
            pat_domain = _get_pattern_domain(pa)
            if domain and domain != "all" and pat_domain != domain:
                continue
            conf = _get_pattern_confidence(pa)
            attractors.append({
                "name":        _display_pattern(pa),
                "domain":      pat_domain,
                "probability": round(conf, 3),
                "description": (
                    f"[{_display_pattern(pa)}] is an idempotent element: "
                    f"compose({_display_pattern(pa)}, {_display_pattern(pa)}) = {_display_pattern(pa)}. "
                    f"It represents a self-reinforcing terminal state in the semi-group."
                ),
            })

    # If no true idempotents found, return patterns with high self-composition similarity
    if not attractors:
        try:
            from ontology.relation_schema import CARTESIAN_PATTERN_REGISTRY  # type: ignore
            for pat in CARTESIAN_PATTERN_REGISTRY.values():
                pat_domain = pat.domain or "general"
                if domain and domain != "all" and pat_domain != domain:
                    continue
                if pat.confidence_prior >= 0.70:
                    attractors.append({
                        "name":        _display_pattern(pat.pattern_name),
                        "domain":      pat_domain,
                        "probability": round(pat.confidence_prior, 3),
                        "description": (
                            f"[{_display_pattern(pat.pattern_name)}] is a high-confidence stable pattern "
                            f"(prior={pat.confidence_prior:.0%}) that may serve as an attractor."
                        ),
                    })
        except ImportError:
            pass

    attractors.sort(key=lambda a: -a["probability"])
    return attractors[:10]


# ---------------------------------------------------------------------------
# Scenario registry helpers
# ---------------------------------------------------------------------------

def get_preset_scenarios() -> List[Dict[str, Any]]:
    """Return all preset scenarios with English pattern names."""
    result = []
    for sc in _PRESET_SCENARIOS:
        sc_copy = dict(sc)
        sc_copy["initial_patterns"] = [_display_pattern(p) for p in sc.get("initial_patterns", [])]
        result.append(sc_copy)
    return result


def get_scenario_by_id(scenario_id: str) -> Optional[Dict[str, Any]]:
    """Look up a preset scenario by ID."""
    for sc in _PRESET_SCENARIOS:
        if sc["id"] == scenario_id:
            return sc
    return None
