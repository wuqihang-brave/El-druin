"""
Regime Engine Adapter
=====================

Maps raw outputs from the backend intelligence engines (DeductionEngine,
SacredSwordAnalyzer, OntologyForecaster) into the normalised RegimeOutput
schema defined in app.schemas.structural_forecast.

The mapping layer is the key deliverable here: internal algebraic and
probabilistic scores are translated into product-facing structural metrics
without exposing raw model notation to the API layer.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.schemas.structural_forecast import RegimeOutput, RegimeState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regime boundary thresholds
# ---------------------------------------------------------------------------

_REGIME_THRESHOLDS: List[tuple[float, float, RegimeState]] = [
    (0.0,  0.2,  "Linear"),
    (0.2,  0.4,  "Stress Accumulation"),
    (0.4,  0.6,  "Nonlinear Escalation"),
    (0.6,  0.75, "Cascade Risk"),
    (0.75, 0.9,  "Attractor Lock-in"),
    (0.9,  1.01, "Dissipating"),
]

# Upper boundary for each regime (used for threshold_distance)
_REGIME_UPPER: Dict[str, float] = {r: hi for _, hi, r in _REGIME_THRESHOLDS}

# ---------------------------------------------------------------------------
# Forecast implication templates (no raw model notation)
# ---------------------------------------------------------------------------

_FORECAST_TEMPLATES: Dict[str, str] = {
    "Linear": (
        "System is operating within a stable linear band. Coupling between domains "
        "remains low and current damping capacity is sufficient to absorb moderate "
        "shocks without regime transition."
    ),
    "Stress Accumulation": (
        "Structural stress is accumulating across coupled domains. Threshold "
        "proximity is increasing; watch for amplification signals that could "
        "accelerate propagation toward a nonlinear regime."
    ),
    "Nonlinear Escalation": (
        "System is within the nonlinear escalation band. A moderate shock to any "
        "coupled domain is sufficient to trigger cascade propagation. "
        "Damping capacity is constrained; intervention windows are narrowing."
    ),
    "Cascade Risk": (
        "Elevated risk of discontinuous repricing across coupled domains. System is "
        "operating near a transition threshold with limited damping capacity. "
        "Cross-domain coupling amplification is the primary propagation mechanism."
    ),
    "Attractor Lock-in": (
        "The system has entered an attractor basin with high structural inertia. "
        "Transition back to lower-risk regimes requires significant exogenous "
        "intervention. Coupling asymmetry is reinforcing lock-in dynamics."
    ),
    "Dissipating": (
        "Regime has passed the critical threshold into dissipation. Structural "
        "coherence is breaking down and propagation is becoming unpredictable. "
        "Attractor geometry is shifting; new equilibrium is not yet defined."
    ),
}


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp a float to [lo, hi]."""
    return max(lo, min(hi, float(value)))


# ---------------------------------------------------------------------------
# RegimeEngine
# ---------------------------------------------------------------------------

class RegimeEngine:
    """
    Adapts outputs from the backend intelligence engines into the normalised
    RegimeOutput schema.

    Parameters
    ----------
    deduction_engine:
        Optional DeductionEngine instance.  When present its outputs are used
        for continuation/break probabilities and mechanism labels.
    sacred_sword:
        Optional SacredSwordAnalyzer instance.  When present its confidence
        score is incorporated into the damping estimate.
    ontology_forecaster:
        Reserved for future use (run_forecast is called as a module function).
    """

    def __init__(
        self,
        deduction_engine: Any = None,
        sacred_sword: Any = None,
        ontology_forecaster: Any = None,
    ) -> None:
        self._deduction = deduction_engine
        self._sacred_sword = sacred_sword
        self._forecaster = ontology_forecaster

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def compute_regime(
        self,
        assessment_id: str,
        context: Dict[str, Any],
    ) -> RegimeOutput:
        """
        Compute a RegimeOutput from the provided assessment context dict.

        The context dict is expected to contain any subset of:
          - ``mechanisms``: List[MechanismLabel] from deduction_engine
          - ``deduction``:  dict from DeductionResult.to_strict_json()
          - ``forecast``:   dict from run_forecast()
          - ``sacred_sword``: dict with ``confidence_score`` key
          - ``events``:     List[str] of raw event text fragments

        Missing keys are handled gracefully with sensible defaults.
        """
        try:
            raw = self._extract_raw_metrics(context)
            structural_score = self._compute_structural_score(raw)
            current_regime   = self._map_structural_score_to_regime(structural_score)

            metrics: Dict[str, float] = {
                "structural_score":    structural_score,
                "threshold_distance":  self._compute_threshold_distance(structural_score),
                "transition_volatility": self._compute_transition_volatility(raw),
                "reversibility_index": self._compute_reversibility_index(raw),
                "coupling_asymmetry":  self._compute_coupling_asymmetry(raw),
                "damping_capacity":    self._compute_damping_capacity(raw),
            }

            dominant_axis       = self._derive_dominant_axis(raw.get("mechanisms", []))
            forecast_implication = self._generate_forecast_implication(
                current_regime, metrics
            )

            return RegimeOutput(
                assessment_id=assessment_id,
                current_regime=current_regime,
                threshold_distance=metrics["threshold_distance"],
                transition_volatility=metrics["transition_volatility"],
                reversibility_index=metrics["reversibility_index"],
                dominant_axis=dominant_axis,
                coupling_asymmetry=metrics["coupling_asymmetry"],
                damping_capacity=metrics["damping_capacity"],
                forecast_implication=forecast_implication,
                updated_at=datetime.now(tz=timezone.utc),
            )
        except Exception as exc:
            logger.warning(
                "RegimeEngine.compute_regime failed for %s: %s. Returning fallback.",
                assessment_id,
                exc,
            )
            raise

    # ------------------------------------------------------------------
    # Internal: extract normalised raw metric bag from context
    # ------------------------------------------------------------------

    def _extract_raw_metrics(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pull and normalise the relevant sub-fields from the context dict into
        a flat raw-metrics bag consumed by all ``_compute_*`` helpers.
        """
        deduction  = context.get("deduction",    {}) or {}
        forecast   = context.get("forecast",     {}) or {}
        sword_out  = context.get("sacred_sword", {}) or {}
        mechanisms = context.get("mechanisms",   []) or []

        # ── deduction sub-fields ───────────────────────────────────────
        alpha_prob = float(
            deduction.get("scenario_alpha", {}).get("probability", 0.65)
        )
        beta_prob  = float(
            deduction.get("scenario_beta",  {}).get("probability", 0.35)
        )
        deduction_conf = float(deduction.get("confidence", 0.5))

        # ── forecast sub-fields ────────────────────────────────────────
        simulation_steps = forecast.get("simulation_steps", []) or []
        bifurcation_pts  = forecast.get("bifurcation_points", []) or []
        attractors       = forecast.get("attractors", []) or []
        delta_norms = [
            float(s.get("delta_norm", 0.0))
            for s in simulation_steps
            if isinstance(s, dict)
        ]

        # ── sacred sword confidence ────────────────────────────────────
        sword_conf = float(sword_out.get("confidence_score", 0.5))

        # ── mechanism stats ────────────────────────────────────────────
        mech_strengths: List[float] = []
        mech_domains:   List[str]   = []
        for m in mechanisms:
            try:
                mech_strengths.append(float(m.strength))
                # RelationDomain enum or plain string
                dom = m.domain
                mech_domains.append(dom.value if hasattr(dom, "value") else str(dom))
            except Exception:
                pass

        mean_strength = float(sum(mech_strengths) / len(mech_strengths)) if mech_strengths else 0.5
        strength_std  = _std(mech_strengths)

        return {
            "alpha_prob":       _clamp(alpha_prob),
            "beta_prob":        _clamp(beta_prob),
            "deduction_conf":   _clamp(deduction_conf),
            "sword_conf":       _clamp(sword_conf),
            "bifurcation_pts":  bifurcation_pts,
            "delta_norms":      delta_norms,
            "n_attractors":     len(attractors),
            "mean_strength":    _clamp(mean_strength),
            "strength_std":     _clamp(strength_std),
            "mech_domains":     mech_domains,
            "mechanisms":       mechanisms,
        }

    # ------------------------------------------------------------------
    # Regime classification
    # ------------------------------------------------------------------

    def _map_structural_score_to_regime(self, score: float) -> RegimeState:
        """
        Map a normalised structural score [0, 1] to the 6-state RegimeState
        taxonomy.

          score < 0.2   → "Linear"
          0.2 – 0.4     → "Stress Accumulation"
          0.4 – 0.6     → "Nonlinear Escalation"
          0.6 – 0.75    → "Cascade Risk"
          0.75 – 0.9    → "Attractor Lock-in"
          > 0.9         → "Dissipating"
        """
        for lo, hi, regime in _REGIME_THRESHOLDS:
            if score < hi:
                return regime
        return "Dissipating"

    def _compute_structural_score(self, raw: Dict[str, Any]) -> float:
        """
        Derive an overall structural activation score from available engine
        outputs.

        Weights:
          50 % – beta (break) probability from deduction engine
          30 % – mean mechanism strength
          20 % – bifurcation density (number of phase transitions / 5, capped at 1)
        """
        beta_prob       = raw["beta_prob"]
        mean_strength   = raw["mean_strength"]
        bifurc_density  = _clamp(len(raw["bifurcation_pts"]) / 5.0)

        score = 0.5 * beta_prob + 0.3 * mean_strength + 0.2 * bifurc_density
        return _clamp(score)

    # ------------------------------------------------------------------
    # Metric computation helpers
    # ------------------------------------------------------------------

    def _compute_threshold_distance(self, structural_score: float) -> float:
        """
        Distance to the upper (escalation) regime boundary for the current
        band, normalised to [0, 1].

        A low value means the system is close to transitioning into the next
        higher-risk regime.  Example: a score of 0.42 in the Nonlinear
        Escalation band (upper=0.60) gives distance 0.18.
        """
        regime = self._map_structural_score_to_regime(structural_score)
        upper  = _REGIME_UPPER.get(regime, 1.0)
        # Normalise by the width of the widest regime band (0.25) so the
        # output spans a meaningful portion of [0, 1]
        raw_dist = upper - structural_score
        return _clamp(raw_dist / 0.25)

    def _compute_transition_volatility(self, raw: Dict[str, Any]) -> float:
        """
        Rate of structural change, proxied by:
          - Mean delta_norm across forecaster simulation steps (primary)
          - Mechanism strength standard deviation (secondary)

        delta_norm of 0.5 in the 8-D Lie algebra space corresponds to full
        volatility; empirically delta_norm rarely exceeds 0.8.
        """
        delta_norms  = raw["delta_norms"]
        strength_std = raw["strength_std"]

        if delta_norms:
            mean_delta = sum(delta_norms) / len(delta_norms)
            # Normalize: 0.4 empirically corresponds to high volatility
            primary = _clamp(mean_delta / 0.4)
        else:
            primary = _clamp(strength_std * 2.0)

        # Bifurcation events boost volatility estimate
        bifurc_boost = _clamp(len(raw["bifurcation_pts"]) * 0.1)
        return _clamp(primary + bifurc_boost)

    def _compute_reversibility_index(self, raw: Dict[str, Any]) -> float:
        """
        How easily the system can return to a lower-risk regime.

        Proxied by:
          alpha (continuation) probability – high alpha means the status-quo
          path is dominant and structural change is still reversible.
          Attractor lock-in (number of attractor candidates) reduces
          reversibility.
        """
        alpha_prob   = raw["alpha_prob"]
        n_attractors = raw["n_attractors"]

        attractor_penalty = _clamp(n_attractors * 0.08)
        return _clamp(alpha_prob - attractor_penalty)

    def _compute_coupling_asymmetry(self, raw: Dict[str, Any]) -> float:
        """
        Measure of how unevenly distributed the coupling is across domains.

        A perfectly symmetric system (equal coupling across all domains) scores
        0.0; a system dominated by a single domain scores close to 1.0.
        """
        domains = raw["mech_domains"]
        if not domains:
            return 0.5  # no information – assume moderate asymmetry

        counts = list(Counter(domains).values())
        total  = sum(counts)
        n_dom  = len(counts)

        if n_dom == 1:
            return 1.0  # entirely concentrated in one domain

        # Herfindahl-Hirschman index (HHI) minus equal-share baseline
        hhi      = sum((c / total) ** 2 for c in counts)
        baseline = 1.0 / n_dom
        # Rescale HHI from [baseline, 1] to [0, 1]
        asymmetry = (hhi - baseline) / max(1.0 - baseline, 1e-9)
        return _clamp(asymmetry)

    def _compute_damping_capacity(self, raw: Dict[str, Any]) -> float:
        """
        Resistance of the system to perturbation amplification.

        Higher alpha probability and sacred-sword confidence both indicate
        that the dominant narrative is stable (more damping).
        Bifurcation events reduce damping capacity.
        """
        alpha_prob   = raw["alpha_prob"]
        sword_conf   = raw["sword_conf"]
        n_bifurc     = len(raw["bifurcation_pts"])

        base_damping = 0.6 * alpha_prob + 0.4 * sword_conf
        bifurc_penalty = _clamp(n_bifurc * 0.08)
        return _clamp(base_damping - bifurc_penalty)

    # ------------------------------------------------------------------
    # Dominant axis derivation
    # ------------------------------------------------------------------

    def _derive_dominant_axis(self, mechanisms: List[Any]) -> str:
        """
        Build the dominant causal-domain chain from the strongest mechanism
        labels.

        Produces strings like ``"military -> sanctions -> energy"`` using the
        top-3 domains ranked by mean mechanism strength.
        """
        if not mechanisms:
            return "general"

        # Group by domain and compute mean strength
        domain_scores: Dict[str, List[float]] = {}
        for m in mechanisms:
            try:
                dom = m.domain
                dom_key = dom.value if hasattr(dom, "value") else str(dom)
                domain_scores.setdefault(dom_key, []).append(float(m.strength))
            except Exception:
                pass

        if not domain_scores:
            return "general"

        ranked = sorted(
            domain_scores.items(),
            key=lambda kv: sum(kv[1]) / len(kv[1]),
            reverse=True,
        )

        top_domains = [dom for dom, _ in ranked[:3]]
        return " -> ".join(top_domains)

    # ------------------------------------------------------------------
    # Forecast implication generation
    # ------------------------------------------------------------------

    def _generate_forecast_implication(
        self,
        regime: RegimeState,
        metrics: Dict[str, float],
    ) -> str:
        """
        Return a concise, human-readable forecast implication string.

        Language rules:
          - No raw numeric probability expressions (e.g. "p=0.86")
          - No internal model jargon ("Bayesian p=", "sigma", "manifold",
            "singular vectors", "commutators", "structural emergence")
          - Preferred vocabulary: regime, threshold, amplification, attractor,
            coupling, damping, propagation, transition
        """
        base = _FORECAST_TEMPLATES.get(regime, _FORECAST_TEMPLATES["Nonlinear Escalation"])

        td = metrics.get("threshold_distance", 0.5)
        dc = metrics.get("damping_capacity", 0.5)
        tv = metrics.get("transition_volatility", 0.5)

        # Append a tailored qualifier based on the most salient metric
        if td < 0.15:
            addendum = (
                " Threshold proximity is critically high; the system is near "
                "a regime transition boundary."
            )
        elif dc < 0.25:
            addendum = (
                " Damping capacity is critically low; exogenous shocks are "
                "likely to propagate with limited attenuation."
            )
        elif tv > 0.75:
            addendum = (
                " Transition volatility is elevated, reflecting rapid "
                "structural change across coupled domains."
            )
        else:
            addendum = ""

        return base.rstrip(".") + ("." if addendum else ".") + addendum


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _std(values: List[float]) -> float:
    """Population standard deviation, returns 0.0 for empty/singleton lists."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    return math.sqrt(variance)


def compute_regime_from_raw(
    assessment_id: str,
    mechanisms: Optional[List[Any]] = None,
    deduction: Optional[Dict[str, Any]] = None,
    forecast: Optional[Dict[str, Any]] = None,
    sacred_sword: Optional[Dict[str, Any]] = None,
) -> RegimeOutput:
    """
    Synchronous convenience wrapper around ``RegimeEngine.compute_regime``.

    Useful for calling from synchronous analysis pipeline code that already
    holds individual engine outputs.
    """
    import asyncio

    context: Dict[str, Any] = {}
    if mechanisms is not None:
        context["mechanisms"] = mechanisms
    if deduction is not None:
        context["deduction"] = deduction
    if forecast is not None:
        context["forecast"] = forecast
    if sacred_sword is not None:
        context["sacred_sword"] = sacred_sword

    engine = RegimeEngine()

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    asyncio.run,
                    engine.compute_regime(assessment_id, context),
                )
                return future.result(timeout=10)
        else:
            return asyncio.run(engine.compute_regime(assessment_id, context))
    except Exception as exc:
        logger.error("compute_regime_from_raw failed: %s", exc)
        raise
