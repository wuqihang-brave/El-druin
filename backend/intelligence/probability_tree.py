"""
Probability Tree Builder
=========================

Generates alternative interpretations of a text fragment and assigns
Bayesian-weighted probability scores to each branch.

Weighting formula::

    calculated_weight = confidence × source_reliability × |t|_p

where ``|t|_p`` is the p-adic absolute value of the current reasoning step t
(imported from ``p_adic_confidence``).  This replaces the previous geometric
decay ``λ^t`` with a non-Archimedean confidence factor grounded in the
ultrametric topology of the pattern space.  Phase transitions (confidence
jumps) occur at structurally significant steps — multiples of p — rather
than uniformly.

All branch weights are then normalised so that they sum to 1.0.

Usage::

    from intelligence.probability_tree import ProbabilityTreeBuilder

    builder = ProbabilityTreeBuilder()
    tree = builder.build_tree(
        text="Fed Chair announces rate hike affecting stock market",
        source_reliability=0.9,
    )
    best_branch = builder.select_best_branch(tree)
    builder.store_tree(tree)
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
# Storage location
# ---------------------------------------------------------------------------
_TREE_STORE_RELATIVE = Path("data/probability_trees.jsonl")


def _resolve_tree_store() -> Path:
    """Resolve the JSONL tree-store path relative to the project root."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "backend").is_dir() and (parent / "frontend").is_dir():
            return parent / _TREE_STORE_RELATIVE
    return Path.cwd() / _TREE_STORE_RELATIVE


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Keyword heuristics for branch detection (no external ML required)
# ---------------------------------------------------------------------------

_CAUSAL_KEYWORDS = frozenset(
    [
        "causes", "leads to", "results in", "triggers", "drives",
        "affects", "impacts", "influences", "raises", "cuts",
        "announces", "hike", "increase", "decrease", "fall", "rise",
        "boosts", "reduces", "threatens", "sparks",
    ]
)

_CONTRADICTION_KEYWORDS = frozenset(
    [
        "contradicts", "reverses", "denies", "refutes", "opposes",
        "disputes", "challenges", "rejects", "overturns", "backtracks",
        "walks back", "flip-flops", "changes position", "reversal",
    ]
)


def _causal_confidence(text: str) -> float:
    """Estimate confidence that *text* contains a causal relationship."""
    lower = text.lower()
    hits = sum(1 for kw in _CAUSAL_KEYWORDS if kw in lower)
    # Sigmoid-like mapping: 0 → 0.2, 1 → 0.55, 2 → 0.75, 3+ → 0.88
    if hits == 0:
        return 0.2
    if hits == 1:
        return 0.55
    if hits == 2:
        return 0.75
    return min(0.88 + (hits - 3) * 0.02, 0.95)


def _contradiction_confidence(text: str) -> float:
    """Estimate confidence that *text* describes a contradiction."""
    lower = text.lower()
    hits = sum(1 for kw in _CONTRADICTION_KEYWORDS if kw in lower)
    if hits == 0:
        return 0.1
    if hits == 1:
        return 0.45
    return min(0.65 + (hits - 2) * 0.05, 0.85)


def _extract_entities_from_text(text: str) -> List[str]:
    """Very lightweight named-entity extraction: capitalised words / phrases."""
    # Find sequences of Title-Cased words (2–5 tokens) as candidate entities
    pattern = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,4})\b")
    entities: List[str] = []
    seen: set[str] = set()
    for match in pattern.finditer(text):
        token = match.group(1).strip()
        if token not in seen and len(token) > 2:
            entities.append(token)
            seen.add(token)
    return entities[:6]  # cap at 6 for brevity


def _lie_sim(A: object, B: object, C: object) -> float:
    """Lie-algebraic similarity of the transition A, B → C.

    Placeholder implementation returning 1.0 (neutral weight).  A full
    implementation should compute the Lie bracket similarity of the pattern
    vectors in the Lie algebra of the pattern space.

    Args:
        A: Source pattern A.
        B: Source pattern B.
        C: Target pattern C.

    Returns:
        Similarity scalar in (0, 1] (currently always 1.0).
    """
    logger.warning(
        "lie_sim(%s, %s, %s) is a placeholder — returns 1.0. "
        "Implement using Lie bracket of pattern vectors.",
        A, B, C,
    )
    return 1.0


# ---------------------------------------------------------------------------
# ProbabilityTreeBuilder
# ---------------------------------------------------------------------------

class ProbabilityTreeBuilder:
    """Generates alternative interpretations and calculates branch weights.

    This implementation uses lightweight keyword heuristics rather than a
    heavyweight ML framework, keeping the module dependency-free beyond the
    standard library and Pydantic.
    """

    def __init__(self, tree_store: Optional[Path] = None, p: int = 7, t: int = 1) -> None:
        self._tree_store: Path = tree_store or _resolve_tree_store()
        self._p: int = p  # prime for p-adic confidence (phase-transition period)
        self._t: int = t  # current reasoning step
        # report_id → ProbabilityTree (in-memory cache)
        self._cache: Dict[str, ProbabilityTree] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_tree(
        self,
        text: str,
        source_reliability: float,
        report_id: Optional[str] = None,
    ) -> ProbabilityTree:
        """Generate multiple interpretations of the same text.

        Branches created:
        1. **Causal relationship** – if the text contains causal language.
        2. **Contradiction** – if contradiction language is detected.
        3. **Insufficient evidence** – default fallback branch.

        Weights are computed as::

            confidence × source_reliability × |t|_p

        where ``|t|_p`` is the p-adic absolute value of the current step t
        (replacing the former geometric decay ``λ^t``).  Phase transitions
        occur at multiples of p.  All weights are then normalised to sum to 1.0.

        Args:
            text: Raw news text to interpret.
            source_reliability: Reliability of the originating source (0.0–1.0).
            report_id: Optional UUID; generated automatically if omitted.

        Returns:
            A fully populated ``ProbabilityTree`` object.
        """
        report_id = report_id or str(uuid.uuid4())
        source_reliability = float(source_reliability)
        entities = _extract_entities_from_text(text)

        # p-adic confidence factor for this step
        t_abs_p = p_adic_abs(self._t, self._p)

        # ── Branch 1: Causal relationship ─────────────────────────────────
        causal_conf = _causal_confidence(text)
        branch1_raw = causal_conf * source_reliability * t_abs_p
        branch1 = InterpretationBranch(
            branch_id=1,
            interpretation="Causal relationship detected — entity A influences entity B",
            evidence_nodes=entities[:2],
            extracted_facts=self._build_causal_facts(entities, causal_conf),
            confidence=round(causal_conf, 4),
            weight=0.0,  # filled after normalisation
            source_reliability=round(source_reliability, 4),
            calculated_weight=round(branch1_raw, 4),
            p_adic_weight=round(t_abs_p, 6),
        )

        # ── Branch 2: Contradiction ────────────────────────────────────────
        contra_conf = _contradiction_confidence(text)
        branch2_raw = contra_conf * source_reliability * t_abs_p
        branch2 = InterpretationBranch(
            branch_id=2,
            interpretation="Contradiction detected — new claim opposes existing knowledge",
            evidence_nodes=entities[:2],
            extracted_facts=self._build_contra_facts(entities, contra_conf),
            confidence=round(contra_conf, 4),
            weight=0.0,
            source_reliability=round(source_reliability, 4),
            calculated_weight=round(branch2_raw, 4),
            p_adic_weight=round(t_abs_p, 6),
        )

        # ── Branch 3: Insufficient evidence ───────────────────────────────
        insuf_conf = 0.2
        branch3_raw = insuf_conf * source_reliability * t_abs_p
        branch3 = InterpretationBranch(
            branch_id=3,
            interpretation="Insufficient evidence — text is ambiguous or uninformative",
            evidence_nodes=[],
            extracted_facts=[],
            confidence=insuf_conf,
            weight=0.0,
            source_reliability=round(source_reliability, 4),
            calculated_weight=round(branch3_raw, 4),
            p_adic_weight=round(t_abs_p, 6),
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

        summary = (
            f"Selected branch {selected_id} "
            f"(weight={selected.get('weight', 0):.2f}) "
            f"based on highest normalised probability."
        )

        tree = ProbabilityTree(
            report_id=report_id,
            timestamp=_now_iso(),
            raw_text=text,
            interpretation_branches=branches,
            total_probability=round(sum(b.weight for b in branches), 4),
            selected_branch=selected_id,
            reasoning_summary=summary,
            step_t=self._t,
            prime_p=self._p,
            is_phase_transition=(self._t % self._p == 0),
        )
        return tree

    def select_best_branch(self, tree: ProbabilityTree) -> Dict[str, Any]:
        """Return the branch dict with the highest normalised weight.

        Args:
            tree: A ``ProbabilityTree`` (branches must already be normalised).

        Returns:
            Dict representation of the winning ``InterpretationBranch``.
        """
        if not tree.interpretation_branches:
            return {}
        best = max(tree.interpretation_branches, key=lambda b: b.weight)
        return best.model_dump(by_alias=True)

    def store_tree(self, tree: ProbabilityTree) -> None:
        """Persist a probability tree to the JSONL store (best-effort).

        Args:
            tree: The ``ProbabilityTree`` to persist.
        """
        self._cache[tree.report_id] = tree
        try:
            self._tree_store.parent.mkdir(parents=True, exist_ok=True)
            with self._tree_store.open("a", encoding="utf-8") as fh:
                fh.write(tree.model_dump_json() + "\n")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not write probability tree to %s: %s", self._tree_store, exc)

    def get_tree(self, report_id: str) -> Optional[ProbabilityTree]:
        """Retrieve a stored probability tree by report ID.

        Checks the in-memory cache first; falls back to scanning the JSONL
        file if the cache misses.

        Args:
            report_id: UUID of the report to look up.

        Returns:
            ``ProbabilityTree`` if found, else ``None``.
        """
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
        """Scan the JSONL file for a matching report_id."""
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
                    except Exception:  # noqa: BLE001
                        continue
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not read tree store %s: %s", self._tree_store, exc)
        return None
