"""
Delta Engine
============

Computes machine-readable deltas between successive assessment snapshots.

For each assessment run, the engine:
1. Stores the current snapshot in memory (keyed by assessment_id).
2. Compares it against the prior snapshot to produce a DeltaOutput.

On the first run (no prior snapshot), a stable baseline delta is returned
without any populated change lists.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List

from app.schemas.structural_forecast import DeltaField, DeltaOutput

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Materiality thresholds
# ---------------------------------------------------------------------------

# Trigger rank / amplification_factor change threshold (>0.05 = material)
_TRIGGER_CHANGE_THRESHOLD: float = 0.05

# Attractor pull_strength change threshold (>0.05 = material)
_ATTRACTOR_CHANGE_THRESHOLD: float = 0.05

# Threshold distance change boundary that separates "stable" from directional
_THRESHOLD_BAND: float = 0.02

# ---------------------------------------------------------------------------
# AssessmentSnapshot dataclass
# ---------------------------------------------------------------------------


@dataclass
class AssessmentSnapshot:
    """Lightweight snapshot of a single assessment run.

    Holds the minimum set of structural dimensions needed by DeltaEngine.
    """

    assessment_id: str
    regime: str
    threshold_distance: float
    damping_capacity: float
    confidence: float
    trigger_rankings: List[dict] = field(default_factory=list)
    # each dict: {"name": str, "rank": int, "amplification_factor": float}
    attractor_rankings: List[dict] = field(default_factory=list)
    # each dict: {"name": str, "rank": int, "pull_strength": float}
    evidence_count: int = 0
    captured_at: datetime = field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )


# ---------------------------------------------------------------------------
# DeltaEngine
# ---------------------------------------------------------------------------


class DeltaEngine:
    """Computes assessment-to-assessment change deltas.

    Stores prior snapshots in memory for the lifetime of the process.
    Thread-safety is not required; all state is in a single-process dict.
    """

    def __init__(self) -> None:
        self._snapshot_store: dict[str, AssessmentSnapshot] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def compute_delta(
        self, assessment_id: str, current_snapshot: AssessmentSnapshot
    ) -> DeltaOutput:
        """Return a DeltaOutput by comparing current snapshot to the prior.

        If no prior snapshot exists (first run), returns a stable baseline
        delta with empty change lists and an explanatory summary.
        """
        prior = self._snapshot_store.get(assessment_id)

        if prior is None:
            # First run: record snapshot and return empty baseline delta
            self.record_snapshot(assessment_id, current_snapshot)
            return DeltaOutput(
                assessment_id=assessment_id,
                regime_changed=False,
                threshold_direction="stable",
                trigger_ranking_changes=[],
                attractor_pull_changes=[],
                damping_capacity_delta=0.0,
                confidence_delta=0.0,
                new_evidence_count=0,
                summary="First assessment run. No prior state available for comparison.",
                updated_at=current_snapshot.captured_at,
            )

        # Compute delta fields
        regime_changed = self._compare_regime(prior.regime, current_snapshot.regime)
        threshold_direction = self._compare_threshold(
            prior.threshold_distance, current_snapshot.threshold_distance
        )
        trigger_changes = self._compare_triggers(
            prior.trigger_rankings, current_snapshot.trigger_rankings
        )
        attractor_changes = self._compare_attractors(
            prior.attractor_rankings, current_snapshot.attractor_rankings
        )
        damping_delta = current_snapshot.damping_capacity - prior.damping_capacity
        confidence_delta = current_snapshot.confidence - prior.confidence
        new_evidence = max(
            0, current_snapshot.evidence_count - prior.evidence_count
        )

        delta = DeltaOutput(
            assessment_id=assessment_id,
            regime_changed=regime_changed,
            threshold_direction=threshold_direction,
            trigger_ranking_changes=trigger_changes,
            attractor_pull_changes=attractor_changes,
            damping_capacity_delta=round(damping_delta, 4),
            confidence_delta=round(confidence_delta, 4),
            new_evidence_count=new_evidence,
            summary="",
            updated_at=current_snapshot.captured_at,
        )
        delta.summary = self._generate_summary(delta, prior, current_snapshot)

        # Advance the snapshot store to the current run
        self.record_snapshot(assessment_id, current_snapshot)
        return delta

    def record_snapshot(
        self, assessment_id: str, snapshot: AssessmentSnapshot
    ) -> None:
        """Store or overwrite the snapshot for the given assessment."""
        self._snapshot_store[assessment_id] = snapshot

    # ------------------------------------------------------------------
    # Comparison helpers
    # ------------------------------------------------------------------

    def _compare_regime(self, prior: str, current: str) -> bool:
        """Return True when the regime label has changed between runs."""
        return prior != current

    def _compare_threshold(self, prior: float, current: float) -> str:
        """Classify the direction of threshold distance movement.

        Returns "narrowing", "widening", or "stable".
        """
        if current < prior - _THRESHOLD_BAND:
            return "narrowing"
        if current > prior + _THRESHOLD_BAND:
            return "widening"
        return "stable"

    def _compare_triggers(
        self, prior: list, current: list
    ) -> list[DeltaField]:
        """Emit a DeltaField for each trigger whose rank or amplification
        changed materially (delta > 0.05)."""
        changes: list[DeltaField] = []

        prior_map = {t["name"]: t for t in prior}
        current_map = {t["name"]: t for t in current}

        # Check triggers that exist in the current snapshot
        for name, cur_t in current_map.items():
            if name not in prior_map:
                # Newly appeared trigger
                changes.append(
                    DeltaField(
                        field=f"{name} trigger rank",
                        previous=None,
                        current=cur_t.get("rank"),
                        direction="new",
                    )
                )
                continue

            pri_t = prior_map[name]

            # Rank change
            pri_rank = pri_t.get("rank")
            cur_rank = cur_t.get("rank")
            if pri_rank is not None and cur_rank is not None and pri_rank != cur_rank:
                direction = "increased" if cur_rank < pri_rank else "decreased"
                changes.append(
                    DeltaField(
                        field=f"{name} trigger rank",
                        previous=pri_rank,
                        current=cur_rank,
                        direction=direction,
                    )
                )

            # Amplification factor change
            pri_amp = pri_t.get("amplification_factor", 0.0)
            cur_amp = cur_t.get("amplification_factor", 0.0)
            if abs(cur_amp - pri_amp) > _TRIGGER_CHANGE_THRESHOLD:
                direction = "increased" if cur_amp > pri_amp else "decreased"
                changes.append(
                    DeltaField(
                        field=f"{name} amplification factor",
                        previous=round(pri_amp, 4),
                        current=round(cur_amp, 4),
                        direction=direction,
                    )
                )

        return changes

    def _compare_attractors(
        self, prior: list, current: list
    ) -> list[DeltaField]:
        """Emit a DeltaField for each attractor whose pull_strength changed
        by more than 0.05."""
        changes: list[DeltaField] = []

        prior_map = {a["name"]: a for a in prior}
        current_map = {a["name"]: a for a in current}

        for name, cur_a in current_map.items():
            if name not in prior_map:
                changes.append(
                    DeltaField(
                        field=f"{name} pull_strength",
                        previous=None,
                        current=cur_a.get("pull_strength"),
                        direction="new",
                    )
                )
                continue

            pri_a = prior_map[name]
            pri_ps = pri_a.get("pull_strength", 0.0)
            cur_ps = cur_a.get("pull_strength", 0.0)
            if abs(cur_ps - pri_ps) > _ATTRACTOR_CHANGE_THRESHOLD:
                direction = "increased" if cur_ps > pri_ps else "decreased"
                changes.append(
                    DeltaField(
                        field=f"{name} pull_strength",
                        previous=round(pri_ps, 4),
                        current=round(cur_ps, 4),
                        direction=direction,
                    )
                )

        return changes

    # ------------------------------------------------------------------
    # Summary generation
    # ------------------------------------------------------------------

    def _generate_summary(
        self,
        delta: DeltaOutput,
        prior: AssessmentSnapshot,
        current: AssessmentSnapshot,
    ) -> str:
        """Compose a human-readable summary using PRD vocabulary.

        Uses only approved vocabulary: regime, threshold, attractor, trigger,
        damping, propagation, coupling, delta, transition.
        Never exposes raw numeric notation or model internals.
        """
        parts: list[str] = []

        # Regime transition
        if delta.regime_changed:
            parts.append(
                f"Regime transitioned from {prior.regime} to {current.regime}."
            )

        # Threshold direction
        if delta.threshold_direction == "narrowing":
            parts.append(
                "Threshold distance is narrowing — proximity to a regime transition "
                "has increased."
            )
        elif delta.threshold_direction == "widening":
            parts.append(
                "Threshold distance is widening — the system has moved further from "
                "an imminent regime transition."
            )

        # Damping capacity
        if abs(delta.damping_capacity_delta) >= 0.05:
            direction_word = (
                "deteriorated" if delta.damping_capacity_delta < 0 else "strengthened"
            )
            pct = abs(round(delta.damping_capacity_delta * 100))
            parts.append(
                f"Damping capacity {direction_word} by {pct} points."
            )

        # Trigger ranking changes
        if delta.trigger_ranking_changes:
            n = len(delta.trigger_ranking_changes)
            parts.append(
                f"{n} trigger ranking {'change' if n == 1 else 'changes'} detected."
            )

        # Attractor pull changes
        if delta.attractor_pull_changes:
            n = len(delta.attractor_pull_changes)
            parts.append(
                f"{n} attractor pull {'shift' if n == 1 else 'shifts'} detected."
            )

        # New evidence
        if delta.new_evidence_count > 0:
            n = delta.new_evidence_count
            parts.append(
                f"{n} new evidence {'item' if n == 1 else 'items'} incorporated."
            )

        # Confidence delta
        if abs(delta.confidence_delta) >= 0.05:
            direction_word = (
                "increased" if delta.confidence_delta > 0 else "decreased"
            )
            parts.append(f"Overall confidence {direction_word}.")

        if not parts:
            return (
                "No material structural changes detected since the prior assessment run."
            )

        return " ".join(parts)
