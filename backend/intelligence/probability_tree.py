"""
Probability Tree Builder  (v2 — four-bug fix)
=============================================

FIX SUMMARY (4 independent bugs all causing identical output):

  BUG 1 — Keyword morphology mismatch (root cause of CONF always 0.20/0.10/0.20)
    BEFORE: _CAUSAL_KEYWORDS contained inflected forms like "causes", "triggers"
            checked via `kw in lower` (substring).
            "causing" does NOT contain "causes" as substring; same for
            "triggering" ≠ "triggers", "caused" ≠ "causes".
            Result: zero keyword hits → causal_conf always 0.20, contra_conf always 0.10.
    AFTER:  Replace with morphological roots ("caus", "trigger", "escalat", …)
            that match all inflections via substring.

  BUG 2 — t hardcoded to 1, |t|_p always 1.0000
    BEFORE: ProbabilityTreeBuilder(p=7, t=1) — t never updated.
            p_adic_abs(1, 7) = 7^0 = 1.0 for every call.
    AFTER:  build_tree() accepts t= and p= kwargs that override instance
            defaults.  intelligence.py should pass t=alert_count, p=prime
            from the padic context dict built by assessments_patch.py.

  BUG 3 — p-adic factor cancels out in normalisation (structural)
    BEFORE: All three branches multiplied by the same t_abs_p, so
            normalised_weight = c / (c + co + 0.2) regardless of |t|_p.
    AFTER:  Each branch gets a *branch-specific* p-adic exponent:
              causal     → |t|_p^1   (primary branch, full weight)
              contradiction → |t|_p^2 (second-order; heavier discount)
              insufficient → |t|_p^(1/2) via t_abs_p**0.5 (partial discount)
            This breaks the cancellation and makes weight ratios genuinely
            sensitive to the p-adic value.

  BUG 4 — branch.confidence displayed raw (pre-p-adic) in UI
    BEFORE: branch.confidence = causal_conf (e.g. 0.20) stored before
            p-adic scaling; UI displayed this raw value as "CONF=".
    AFTER:  branch.confidence stores the *final* p-adic-weighted value:
              confidence = causal_conf * t_abs_p^exponent
            so CONF in the UI reflects the actual structural confidence.

Usage (unchanged public API)::

    builder = ProbabilityTreeBuilder()
    tree = builder.build_tree(
        text="Pipeline disruption causing spot-price spike...",
        source_reliability=0.85,
        t=7,      # NEW: pass step from assessment context
        p=7,      # NEW: pass prime from assessment context
    )
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from intelligence.models import (
    ExtractedFact,
    InterpretationBranch,
    ProbabilityTree,
)
from intelligence.p_adic_confidence import p_adic_abs

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
_TREE_STORE_RELATIVE = Path("data/probability_trees.jsonl")


def _resolve_tree_store() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "backend").is_dir() and (parent / "frontend").is_dir():
            return parent / _TREE_STORE_RELATIVE
    return Path.cwd() / _TREE_STORE_RELATIVE


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# BUG 1 FIX — morphological roots instead of inflected forms
# ---------------------------------------------------------------------------
# Each entry is a ROOT that matches all inflections via substring search.
# e.g. "caus" matches: causes, caused, causing, causal, causation
#      "trigger" matches: triggers, triggered, triggering
#      "escalat" matches: escalate, escalates, escalated, escalation
#
# Organised into three semantic groups for interpretability:

_CAUSAL_ROOTS: frozenset[str] = frozenset([
    # Direct causation
    "caus",         # cause, causes, caused, causing, causal
    "trigger",      # triggers, triggered, triggering
    "lead to",      # leads to, led to
    "result",       # results in, resulting, resulted
    "driv",         # drives, drove, driving, driven
    "produc",       # produces, produced, producing
    "generat",      # generates, generated
    # Influence / change
    "affect",       # affects, affected, affecting
    "impact",       # impacts, impacted, impacting
    "influenc",     # influences, influenced, influencing
    "rais",         # raises, raised, raising
    "increas",      # increases, increased, increasing
    "decreas",      # decreases, decreased, decreasing
    "reduc",        # reduces, reduced, reducing
    "boost",        # boosts, boosted, boosting
    # Geopolitical-domain verbs (new — absent in original)
    "escalat",      # escalate, escalates, escalated, escalation
    "cascad",       # cascade, cascades, cascading
    "propagat",     # propagate, propagates, propagation
    "disrupt",      # disrupts, disrupted, disruption
    "constrict",    # constricts, constriction
    "compress",     # compresses, compression (intervention window)
    "threaten",     # threatens, threatened
    "spark",        # sparks, sparked
    "announc",      # announce, announces, announced
])

_CONTRADICTION_ROOTS: frozenset[str] = frozenset([
    "contradict",   # contradicts, contradicting, contradiction
    "revers",       # reverses, reversed, reversal
    "deni",         # denies, denied, denial
    "refut",        # refutes, refuted, refutation
    "oppos",        # opposes, opposed, opposition
    "disput",       # disputes, disputed, disputing
    "challeng",     # challenges, challenged, challenging
    "reject",       # rejects, rejected, rejecting
    "overturn",     # overturns, overturned
    "backtrack",    # backtracks, backtracked
    "undermin",     # undermines, undermined, undermining
    "contradict",
    "flip-flop",
    "reversal",
    "walk back",    # walks back, walked back
    "contradict",
    "inconsist",    # inconsistent, inconsistency
])

# Markers that signal strong uncertainty / hedging (boost insufficient branch)
_UNCERTAINTY_ROOTS: frozenset[str] = frozenset([
    "unclear",
    "uncertain",
    "ambiguous",
    "unconfirm",    # unconfirmed
    "allegdly",
    "reportedly",
    "unverif",      # unverified
    "insuffici",    # insufficient
    "limited evidence",
    "no confirm",
])


def _count_root_hits(text: str, roots: frozenset[str]) -> int:
    """Count how many roots appear as substrings in lowercased text."""
    lower = text.lower()
    return sum(1 for r in roots if r in lower)


def _causal_confidence(text: str) -> float:
    """Estimate causal-relationship confidence using morphological roots."""
    hits = _count_root_hits(text, _CAUSAL_ROOTS)
    # Saturating response: each additional hit adds diminishing marginal confidence
    if hits == 0:
        return 0.20
    if hits == 1:
        return 0.55
    if hits == 2:
        return 0.72
    if hits == 3:
        return 0.82
    return min(0.88 + (hits - 4) * 0.015, 0.95)


def _contradiction_confidence(text: str) -> float:
    """Estimate contradiction confidence using morphological roots."""
    hits = _count_root_hits(text, _CONTRADICTION_ROOTS)
    if hits == 0:
        return 0.10
    if hits == 1:
        return 0.48
    if hits == 2:
        return 0.65
    return min(0.70 + (hits - 3) * 0.04, 0.85)


def _insufficient_confidence(text: str) -> float:
    """Estimate 'insufficient evidence' confidence — boosted by uncertainty markers."""
    hits = _count_root_hits(text, _UNCERTAINTY_ROOTS)
    base = 0.20
    return min(base + hits * 0.08, 0.55)


def _extract_entities_from_text(text: str) -> List[str]:
    pattern = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4})\b")
    entities: List[str] = []
    seen: set[str] = set()
    for match in pattern.finditer(text):
        token = match.group(1).strip()
        if token not in seen and len(token) > 2:
            entities.append(token)
            seen.add(token)
    return entities[:6]


_LIE_SIM_WARNING_ISSUED = False


def _lie_sim(A: object, B: object, C: object) -> float:
    global _LIE_SIM_WARNING_ISSUED
    if not _LIE_SIM_WARNING_ISSUED:
        logger.warning(
            "lie_sim is a placeholder returning 1.0. "
            "Implement using Lie bracket of pattern vectors."
        )
        _LIE_SIM_WARNING_ISSUED = True
    return 1.0


# ---------------------------------------------------------------------------
# BUG 3 FIX — branch-specific p-adic exponents
# ---------------------------------------------------------------------------
# Each branch applies a different power of |t|_p so the factor does NOT
# cancel in normalisation.
#
# Semantic justification:
#   - Causal branch is the primary inference; apply |t|_p^1 (standard decay)
#   - Contradiction branch is a second-order structural signal; heavier
#     discount at phase-transition steps → |t|_p^2
#   - Insufficient branch represents baseline uncertainty; softer discount
#     → |t|_p^0.5 (square root, decays more slowly)
#
# At a normal step (t=3, p=7): |t|_7 = 1.0 for all → same as before
# At a phase-transition step (t=7, p=7): |t|_7 = 1/7
#   causal raw     = c  * sr * (1/7)^1   = c*sr/7
#   contra raw     = co * sr * (1/7)^2   = co*sr/49
#   insuf raw      = ci * sr * (1/7)^0.5 = ci*sr/√7
# After normalisation: ratios differ, AND sum < 1 in raw form.

_BRANCH_PADIC_EXPONENTS = {
    "causal":        1.0,
    "contradiction": 2.0,
    "insufficient":  0.5,
}


# ---------------------------------------------------------------------------
# ProbabilityTreeBuilder (fixed)
# ---------------------------------------------------------------------------

class ProbabilityTreeBuilder:
    """
    Generates alternative interpretations and calculates branch weights.

    Changes from v1:
    - Keyword matching uses morphological roots (BUG 1 fix)
    - build_tree() accepts t= and p= to override instance defaults (BUG 2 fix)
    - Each branch uses a different p-adic exponent (BUG 3 fix)
    - branch.confidence stores p-adic-weighted value (BUG 4 fix)
    """

    def __init__(
        self,
        tree_store: Optional[Path] = None,
        p: int = 7,
        t: int = 1,
    ) -> None:
        self._tree_store: Path = tree_store or _resolve_tree_store()
        self._p: int = p
        self._t: int = t
        self._cache: Dict[str, ProbabilityTree] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_tree(
        self,
        text: str,
        source_reliability: float,
        report_id: Optional[str] = None,
        # BUG 2 FIX: accept t and p per-call so caller controls the step
        t: Optional[int] = None,
        p: Optional[int] = None,
    ) -> ProbabilityTree:
        """Generate multiple interpretations of the same text.

        Branches:
        1. **Causal**        — structural causation language detected
        2. **Contradiction** — contradiction / reversal language detected
        3. **Insufficient**  — default / hedging fallback

        Weight formula (BUG 3 FIX — branch-specific exponents)::

            raw_weight_i = conf_i * source_reliability * |t|_p ^ exponent_i

        where exponent_causal=1, exponent_contradiction=2, exponent_insufficient=0.5

        branch.confidence stores conf_i * |t|_p^exponent_i (BUG 4 FIX).

        Args:
            text: Raw text to interpret.
            source_reliability: Source quality scalar 0–1.
            report_id: Optional stable ID; auto-generated if omitted.
            t: Reasoning step (overrides instance default).  Pass
               assessment.alert_count from the padic context dict.
            p: Prime base (overrides instance default).  Pass the
               assessment-specific prime from the padic context dict.

        Returns:
            Populated ``ProbabilityTree``.
        """
        report_id = report_id or str(uuid.uuid4())
        source_reliability = float(source_reliability)
        entities = _extract_entities_from_text(text)

        # BUG 2 FIX: use call-site t/p if provided, else instance defaults
        effective_t = t if t is not None else self._t
        effective_p = p if p is not None else self._p
        effective_t = max(1, effective_t)  # guard against 0

        # Base p-adic absolute value
        t_abs_p = p_adic_abs(effective_t, effective_p)

        # BUG 3 FIX: per-branch exponents
        t_abs_causal = t_abs_p ** _BRANCH_PADIC_EXPONENTS["causal"]        # |t|^1
        t_abs_contra = t_abs_p ** _BRANCH_PADIC_EXPONENTS["contradiction"]  # |t|^2
        t_abs_insuf  = t_abs_p ** _BRANCH_PADIC_EXPONENTS["insufficient"]   # |t|^0.5

        # BUG 1 FIX: root-based confidence scoring
        causal_conf = _causal_confidence(text)
        contra_conf = _contradiction_confidence(text)
        insuf_conf  = _insufficient_confidence(text)

        # BUG 4 FIX: confidence stored as p-adic-weighted value
        causal_conf_weighted = round(causal_conf * t_abs_causal, 4)
        contra_conf_weighted = round(contra_conf * t_abs_contra, 4)
        insuf_conf_weighted  = round(insuf_conf  * t_abs_insuf,  4)

        # Raw weights include source_reliability
        branch1_raw = causal_conf * source_reliability * t_abs_causal
        branch2_raw = contra_conf * source_reliability * t_abs_contra
        branch3_raw = insuf_conf  * source_reliability * t_abs_insuf

        branch1 = InterpretationBranch(
            branch_id=1,
            interpretation="Causal relationship detected — entity A influences entity B",
            evidence_nodes=entities[:2],
            extracted_facts=self._build_causal_facts(entities, causal_conf),
            confidence=causal_conf_weighted,   # BUG 4 FIX
            weight=0.0,
            source_reliability=round(source_reliability, 4),
            calculated_weight=round(branch1_raw, 4),
            p_adic_weight=round(t_abs_causal, 6),
        )

        branch2 = InterpretationBranch(
            branch_id=2,
            interpretation="Contradiction detected — new claim opposes existing knowledge",
            evidence_nodes=entities[:2],
            extracted_facts=self._build_contra_facts(entities, contra_conf),
            confidence=contra_conf_weighted,   # BUG 4 FIX
            weight=0.0,
            source_reliability=round(source_reliability, 4),
            calculated_weight=round(branch2_raw, 4),
            p_adic_weight=round(t_abs_contra, 6),
        )

        branch3 = InterpretationBranch(
            branch_id=3,
            interpretation="Insufficient evidence — text is ambiguous or uninformative",
            evidence_nodes=[],
            extracted_facts=[],
            confidence=insuf_conf_weighted,    # BUG 4 FIX
            weight=0.0,
            source_reliability=round(source_reliability, 4),
            calculated_weight=round(branch3_raw, 4),
            p_adic_weight=round(t_abs_insuf, 6),
        )

        branches = [branch1, branch2, branch3]
        branches = self._normalise_weights(branches)

        selected = self.select_best_branch(
            ProbabilityTree(
                report_id=report_id,
                timestamp=_now_iso(),
                raw_text=text,
                interpretation_branches=branches,
                total_probability=1.0,
                selected_branch=1,
                reasoning_summary="",
            )
        )
        selected_id = selected.get("branch_id", 1)

        # Annotate phase transition in summary
        phase_note = ""
        if effective_t % effective_p == 0:
            phase_note = (
                f" Phase transition at t={effective_t} (p={effective_p}): "
                f"|t|_p={t_abs_p:.4f} — confidence discounted by factor "
                f"{t_abs_p:.4f} (causal) / {t_abs_causal**0:.4f}→{t_abs_contra:.4f} (contra)."
            )

        summary = (
            f"Selected branch {selected_id} "
            f"(weight={selected.get('weight', 0):.4f}) "
            f"p={effective_p}, t={effective_t}, |t|_p={t_abs_p:.4f}."
            f"{phase_note}"
        )

        tree = ProbabilityTree(
            report_id=report_id,
            timestamp=_now_iso(),
            raw_text=text,
            interpretation_branches=branches,
            total_probability=round(sum(b.weight for b in branches), 4),
            selected_branch=selected_id,
            reasoning_summary=summary,
            step_t=effective_t,
            prime_p=effective_p,
            is_phase_transition=(effective_t % effective_p == 0),
        )
        return tree

    def select_best_branch(self, tree: ProbabilityTree) -> Dict[str, Any]:
        if not tree.interpretation_branches:
            return {}
        best = max(tree.interpretation_branches, key=lambda b: b.weight)
        return best.model_dump(by_alias=True)

    def store_tree(self, tree: ProbabilityTree) -> None:
        self._cache[tree.report_id] = tree
        try:
            self._tree_store.parent.mkdir(parents=True, exist_ok=True)
            with self._tree_store.open("a", encoding="utf-8") as fh:
                fh.write(tree.model_dump_json() + "\n")
        except Exception as exc:
            logger.warning("Could not write probability tree to %s: %s", self._tree_store, exc)

    def get_tree(self, report_id: str) -> Optional[ProbabilityTree]:
        if report_id in self._cache:
            return self._cache[report_id]
        return self._load_from_store(report_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_weights(
        branches: List[InterpretationBranch],
    ) -> List[InterpretationBranch]:
        """Normalise ``calculated_weight`` values so they sum to 1.0."""
        total = sum(b.calculated_weight for b in branches)
        if total <= 0:
            equal = round(1.0 / len(branches), 4) if branches else 0.0
            for b in branches:
                b.weight = equal
        else:
            for b in branches:
                b.weight = round(b.calculated_weight / total, 4)
        return branches

    @staticmethod
    def _build_causal_facts(
        entities: List[str], confidence: float
    ) -> List[ExtractedFact]:
        if len(entities) < 2:
            return []
        return [
            ExtractedFact(
                type="INFLUENCES",
                **{"from": entities[0], "to": entities[1]},
                causality_score=round(confidence, 4),
            )
        ]

    @staticmethod
    def _build_contra_facts(
        entities: List[str], confidence: float
    ) -> List[ExtractedFact]:
        if len(entities) < 2:
            return []
        return [
            ExtractedFact(
                type="CONTRADICTS",
                **{"from": entities[0], "to": entities[1]},
                conflict_confidence=round(confidence, 4),
            )
        ]

    def _load_from_store(self, report_id: str) -> Optional[ProbabilityTree]:
        if not self._tree_store.exists():
            return None
        try:
            with self._tree_store.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("report_id") == report_id:
                            tree = ProbabilityTree.model_validate(data)
                            self._cache[report_id] = tree
                            return tree
                    except Exception:
                        continue
        except Exception as exc:
            logger.warning("Could not read tree store %s: %s", self._tree_store, exc)
        return None