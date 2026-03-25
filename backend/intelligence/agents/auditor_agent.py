"""
Oracle Laboratory – Auditor Agent
===================================

The Auditor agent performs self-verification checks on all round outputs:

  Check 1 – Stereotype Collapse
    • All agents output the same action (echo chamber)
    • An agent's action contradicts its historical style
    • Reasoning is too brief / clichéd

  Check 2 – Logical Hallucination
    • Causal claims lack supporting evidence
    • Confidence is high but reasoning is vague

  Check 3 – Confidence Mismatch
    • High confidence (≥ 0.85) with very short reasoning (<40 chars)
    • Low confidence (< 0.45) but assertive language in reasoning

Outputs a list of AuditFlag objects.
"""

from __future__ import annotations

import re
import uuid
from typing import List

from intelligence.schemas import (
    AgentDecision,
    AgentReaction,
    AgentSynthesis,
    AuditFlag,
)

# ---------------------------------------------------------------------------
# Heuristic constants
# ---------------------------------------------------------------------------

_HIGH_CONFIDENCE_THRESHOLD = 0.85
_LOW_CONFIDENCE_THRESHOLD = 0.45
_MIN_REASONING_LENGTH = 40  # characters

_VAGUE_PHRASES = [
    "as expected",
    "it is clear",
    "obviously",
    "of course",
    "as always",
    "inevitably",
    "certainly",
    "no doubt",
]

_CIRCULAR_PATTERNS = [
    r"because.{5,40}therefore",
    r"leads to.{5,40}which leads to.{5,40}the same",
]

_ASSERTIVE_WORDS = ["will", "must", "definitely", "certainly", "always", "never"]


# ---------------------------------------------------------------------------
# AuditorAgent
# ---------------------------------------------------------------------------


class AuditorAgent:
    """Runs all three audit checks and returns a list of AuditFlag objects."""

    def audit(
        self,
        round1: List[AgentDecision],
        round2: List[AgentReaction],
        round3: List[AgentSynthesis],
    ) -> List[AuditFlag]:
        flags: List[AuditFlag] = []
        flags.extend(self._check_stereotype_collapse(round1))
        flags.extend(self._check_logical_hallucination(round1, round3))
        flags.extend(self._check_confidence_mismatch(round1, round2, round3))
        return flags

    # ------------------------------------------------------------------
    # Check 1 – Stereotype Collapse
    # ------------------------------------------------------------------

    def _check_stereotype_collapse(
        self, decisions: List[AgentDecision]
    ) -> List[AuditFlag]:
        flags: List[AuditFlag] = []
        if not decisions:
            return flags

        action_types = [d.action_type for d in decisions]
        unique_actions = set(action_types)

        # Echo chamber: all agents chose the same action
        if len(unique_actions) == 1:
            flags.append(
                AuditFlag(
                    flag_id=str(uuid.uuid4()),
                    agent_id="all",
                    issue_type="stereotype_collapse",
                    severity="high",
                    description=(
                        "Echo Chamber detected: all five agents produced the same action "
                        f'"{action_types[0]}". This suggests groupthink or insufficient '
                        "diversity in the agent reasoning profiles."
                    ),
                    flagged_text=f"All agents: {action_types[0]}",
                )
            )

        # Flag agents with very short / clichéd reasoning
        for d in decisions:
            reasoning_lower = d.reasoning.lower()
            hit = next(
                (phrase for phrase in _VAGUE_PHRASES if phrase in reasoning_lower),
                None,
            )
            if hit:
                flags.append(
                    AuditFlag(
                        flag_id=str(uuid.uuid4()),
                        agent_id=d.agent_id,
                        issue_type="stereotype_collapse",
                        severity="low",
                        description=(
                            f"Agent {d.agent_id} used a clichéd phrase in their reasoning: "
                            f'"{hit}". This may indicate over-simplified analysis.'
                        ),
                        flagged_text=d.reasoning[:120],
                    )
                )

        return flags

    # ------------------------------------------------------------------
    # Check 2 – Logical Hallucination
    # ------------------------------------------------------------------

    def _check_logical_hallucination(
        self,
        round1: List[AgentDecision],
        round3: List[AgentSynthesis],
    ) -> List[AuditFlag]:
        flags: List[AuditFlag] = []

        # High confidence + vague reasoning (round 1)
        for d in round1:
            if d.confidence >= _HIGH_CONFIDENCE_THRESHOLD and len(d.reasoning) < _MIN_REASONING_LENGTH:
                flags.append(
                    AuditFlag(
                        flag_id=str(uuid.uuid4()),
                        agent_id=d.agent_id,
                        issue_type="logical_hallucination",
                        severity="high",
                        description=(
                            f"Agent {d.agent_id} expresses high confidence "
                            f"({d.confidence:.2f}) but provides very short reasoning "
                            f"({len(d.reasoning)} chars). Confidence appears unsupported."
                        ),
                        flagged_text=d.reasoning[:120],
                    )
                )

        # Circular reasoning detection (round 3 synthesis)
        for s in round3:
            text = s.outcome_prediction + " " + s.reasoning
            for pattern in _CIRCULAR_PATTERNS:
                if re.search(pattern, text, re.IGNORECASE):
                    flags.append(
                        AuditFlag(
                            flag_id=str(uuid.uuid4()),
                            agent_id=s.agent_id,
                            issue_type="logical_hallucination",
                            severity="medium",
                            description=(
                                f"Potential circular reasoning detected in {s.agent_id}'s "
                                "synthesis: a causal chain appears to loop back on itself."
                            ),
                            flagged_text=(s.outcome_prediction + " " + s.reasoning)[:120],
                        )
                    )
                    break

        return flags

    # ------------------------------------------------------------------
    # Check 3 – Confidence Mismatch
    # ------------------------------------------------------------------

    def _check_confidence_mismatch(
        self,
        round1: List[AgentDecision],
        round2: List[AgentReaction],
        round3: List[AgentSynthesis],
    ) -> List[AuditFlag]:
        flags: List[AuditFlag] = []

        # Combine all rounds for confidence-mismatch checking
        all_outputs: list = list(round1) + list(round2) + list(round3)

        for item in all_outputs:
            confidence = getattr(item, "confidence", 0.5)
            reasoning = getattr(item, "reasoning", "")
            agent_id = item.agent_id

            # High confidence but very short reasoning
            if confidence >= _HIGH_CONFIDENCE_THRESHOLD and len(reasoning) < _MIN_REASONING_LENGTH:
                flags.append(
                    AuditFlag(
                        flag_id=str(uuid.uuid4()),
                        agent_id=agent_id,
                        issue_type="confidence_mismatch",
                        severity="high",
                        description=(
                            f"Agent {agent_id} reports confidence {confidence:.2f} "
                            f"but reasoning is only {len(reasoning)} characters. "
                            "High confidence requires substantive justification."
                        ),
                        flagged_text=reasoning[:120],
                    )
                )

            # Low confidence but assertive language
            elif confidence < _LOW_CONFIDENCE_THRESHOLD:
                reasoning_lower = reasoning.lower()
                assertive_hit = next(
                    (w for w in _ASSERTIVE_WORDS if w in reasoning_lower), None
                )
                if assertive_hit:
                    flags.append(
                        AuditFlag(
                            flag_id=str(uuid.uuid4()),
                            agent_id=agent_id,
                            issue_type="confidence_mismatch",
                            severity="medium",
                            description=(
                                f"Agent {agent_id} has low confidence ({confidence:.2f}) "
                                f'but uses assertive language ("{assertive_hit}") in their '
                                "reasoning. This inconsistency warrants review."
                            ),
                            flagged_text=reasoning[:120],
                        )
                    )

        return flags
