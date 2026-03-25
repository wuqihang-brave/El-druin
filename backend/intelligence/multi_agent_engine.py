"""
Oracle Laboratory – Multi-Agent Engine
=======================================

Core orchestration layer that runs the three-round simulation, detects
divergence, creates scenario branches, and persists everything to KuzuDB.

Public API::

    from intelligence.multi_agent_engine import MultiAgentEngine

    engine = MultiAgentEngine()
    state  = engine.run_simulation("Fed raises rates 75 bps amid stagflation fears")

    print(state.simulation_id)
    print(state.audit_flags)

KuzuDB Integration
------------------
The engine creates four node tables and three relationship tables in the
configured KuzuDB database path (defaults to ``./data/oracle_lab.kuzu``).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from intelligence.schemas import (
    AgentDecision,
    AgentReaction,
    AgentSynthesis,
    AuditFlag,
    SimulationBranch,
    SimulationState,
)
from intelligence.agents.base_agent import AGENT_PROFILES, build_agent_registry
from intelligence.agents.auditor_agent import AuditorAgent

logger = logging.getLogger(__name__)

_DIVERGENCE_THRESHOLD = 0.6
_DEFAULT_DB_PATH = "./data/oracle_lab.kuzu"


# ---------------------------------------------------------------------------
# KuzuDB schema helpers
# ---------------------------------------------------------------------------

_SCHEMA_DDL = [
    # Node tables
    """CREATE NODE TABLE IF NOT EXISTS Agent(
        agent_id STRING PRIMARY KEY,
        name STRING,
        expertise_domain STRING,
        decision_style STRING,
        historical_accuracy DOUBLE,
        bias_profile STRING,
        reasoning_framework STRING,
        created_at STRING
    )""",
    """CREATE NODE TABLE IF NOT EXISTS OracleSimulation(
        simulation_id STRING PRIMARY KEY,
        seed_event STRING,
        created_at STRING,
        scenario_type STRING,
        parent_simulation_id STRING,
        status STRING,
        divergence_detected BOOLEAN,
        divergence_round INT64
    )""",
    """CREATE NODE TABLE IF NOT EXISTS OracleDecision(
        decision_id STRING PRIMARY KEY,
        simulation_id STRING,
        agent_id STRING,
        round_number INT64,
        action_type STRING,
        target STRING,
        confidence DOUBLE,
        reasoning STRING,
        created_at STRING
    )""",
    """CREATE NODE TABLE IF NOT EXISTS OracleAuditFlag(
        flag_id STRING PRIMARY KEY,
        simulation_id STRING,
        agent_id STRING,
        issue_type STRING,
        severity STRING,
        description STRING,
        flagged_text STRING,
        created_at STRING
    )""",
    # Relationship tables
    """CREATE REL TABLE IF NOT EXISTS AGENT_DECIDED(
        FROM Agent TO OracleDecision,
        timestamp STRING
    )""",
    """CREATE REL TABLE IF NOT EXISTS SIMULATION_BRANCHES(
        FROM OracleSimulation TO OracleSimulation,
        branch_reason STRING,
        created_at STRING
    )""",
    """CREATE REL TABLE IF NOT EXISTS FLAG_FOUND_IN(
        FROM OracleAuditFlag TO OracleDecision,
        timestamp STRING
    )""",
]


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# KuzuDB wrapper
# ---------------------------------------------------------------------------

class _OracleKuzuStore:
    """Minimal KuzuDB wrapper for the Oracle simulation tables."""

    def __init__(self, db_path: str = _DEFAULT_DB_PATH) -> None:
        self._db_path = db_path
        self._db: Optional[Any] = None
        self._conn: Optional[Any] = None
        self._available = False
        self._init_db()

    def _init_db(self) -> None:
        try:
            import kuzu  # type: ignore[import]

            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            self._db = kuzu.Database(self._db_path)
            self._conn = kuzu.Connection(self._db)
            for ddl in _SCHEMA_DDL:
                self._conn.execute(ddl)
            self._available = True
            logger.info("OracleKuzuStore initialised at %s", self._db_path)
        except ImportError:
            logger.warning("kuzu not installed – simulation will run without persistence")
        except Exception as exc:
            logger.warning("OracleKuzuStore init failed: %s – running without persistence", exc)

    def execute(self, query: str, params: Optional[Dict[str, Any]] = None) -> None:
        if not self._available or self._conn is None:
            return
        try:
            if params:
                self._conn.execute(query, params)
            else:
                self._conn.execute(query)
        except Exception as exc:
            logger.debug("Kuzu execute error (ignored): %s | query: %s", exc, query[:80])

    @property
    def available(self) -> bool:
        return self._available

    def persist_agents(self, profiles: list) -> None:
        for p in profiles:
            self.execute(
                "MERGE (a:Agent {agent_id: $aid}) "
                "SET a.name = $name, a.expertise_domain = $ed, "
                "a.decision_style = $ds, a.historical_accuracy = $ha, "
                "a.bias_profile = $bp, a.reasoning_framework = $rf, "
                "a.created_at = $ca",
                {
                    "aid": p.agent_id,
                    "name": p.name,
                    "ed": p.expertise_domain,
                    "ds": p.decision_style,
                    "ha": p.historical_accuracy,
                    "bp": p.bias_profile,
                    "rf": p.reasoning_framework,
                    "ca": p.created_at,
                },
            )

    def persist_simulation(self, state: SimulationState) -> None:
        self.execute(
            "MERGE (s:OracleSimulation {simulation_id: $sid}) "
            "SET s.seed_event = $se, s.created_at = $ca, "
            "s.scenario_type = $st, s.parent_simulation_id = $pid, "
            "s.status = $status, s.divergence_detected = $dd, "
            "s.divergence_round = $dr",
            {
                "sid": state.simulation_id,
                "se": state.seed_event[:500],
                "ca": state.created_at,
                "st": "main",
                "pid": "",
                "status": state.status,
                "dd": state.divergence_detected,
                "dr": state.divergence_round,
            },
        )

    def persist_decision(
        self, simulation_id: str, decision: Any, round_number: int
    ) -> str:
        did = str(uuid.uuid4())
        action = getattr(decision, "action_type", None) or getattr(decision, "reaction_type", None) or ""
        target = getattr(decision, "target_entity", None) or str(getattr(decision, "affected_entities", []))
        self.execute(
            "CREATE (d:OracleDecision {"
            "decision_id: $did, simulation_id: $sid, agent_id: $aid, "
            "round_number: $rn, action_type: $at, target: $tgt, "
            "confidence: $conf, reasoning: $rsn, created_at: $ca})",
            {
                "did": did,
                "sid": simulation_id,
                "aid": decision.agent_id,
                "rn": round_number,
                "at": action,
                "tgt": target[:200] if target else "",
                "conf": decision.confidence,
                "rsn": decision.reasoning[:500] if decision.reasoning else "",
                "ca": _now_iso(),
            },
        )
        return did

    def persist_audit_flag(self, simulation_id: str, flag: AuditFlag) -> None:
        self.execute(
            "CREATE (f:OracleAuditFlag {"
            "flag_id: $fid, simulation_id: $sid, agent_id: $aid, "
            "issue_type: $it, severity: $sev, description: $desc, "
            "flagged_text: $ft, created_at: $ca})",
            {
                "fid": flag.flag_id,
                "sid": simulation_id,
                "aid": flag.agent_id,
                "it": flag.issue_type,
                "sev": flag.severity,
                "desc": flag.description[:500],
                "ft": flag.flagged_text[:300],
                "ca": flag.created_at,
            },
        )


# ---------------------------------------------------------------------------
# MultiAgentEngine
# ---------------------------------------------------------------------------


class MultiAgentEngine:
    """Orchestrates the three-round simulation with divergence branching."""

    def __init__(
        self,
        settings: Optional[Any] = None,
        db_path: str = _DEFAULT_DB_PATH,
    ) -> None:
        self._settings = settings or self._load_settings()
        self._registry = build_agent_registry(self._settings)
        self._auditor = AuditorAgent()
        self._store = _OracleKuzuStore(db_path)
        # Persist the fixed agent profiles on startup
        self._store.persist_agents(AGENT_PROFILES)

    @staticmethod
    def _load_settings() -> Any:
        try:
            from app.core.config import get_settings

            return get_settings()
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run_simulation(self, seed_event: str) -> SimulationState:
        """Run a complete three-round simulation and return the final state."""
        state = SimulationState(seed_event=seed_event)
        try:
            state = self._round1(state)
            if state.divergence_detected:
                state = self._create_branches(state)
            else:
                state = self._round2(state)
                state = self._round3(state)

            state = self._run_audit(state)
            state.status = "completed"
        except Exception as exc:
            logger.error("Simulation failed: %s", exc, exc_info=True)
            state.status = "error"
        finally:
            self._store.persist_simulation(state)
        return state

    # ------------------------------------------------------------------
    # Round execution helpers
    # ------------------------------------------------------------------

    def _round1(self, state: SimulationState) -> SimulationState:
        state.round_number = 1
        decisions: List[AgentDecision] = []
        for agent_id, agent in self._registry.items():
            decision = agent.decide(state.seed_event)
            decisions.append(decision)
            state.confidence_scores[agent_id] = decision.confidence
            self._store.persist_decision(state.simulation_id, decision, 1)

        state.round1_decisions = decisions
        state.simulation_history.append(
            {"round": 1, "decisions": [d.model_dump() for d in decisions]}
        )

        # Divergence check
        low_conf = [(aid, c) for aid, c in state.confidence_scores.items() if c < _DIVERGENCE_THRESHOLD]
        if low_conf:
            state.divergence_detected = True
            state.divergence_agent = low_conf[0][0]
            state.divergence_round = 1

        return state

    def _round2(self, state: SimulationState) -> SimulationState:
        state.round_number = 2
        reactions: List[AgentReaction] = []
        for agent_id, agent in self._registry.items():
            reaction = agent.react(state.seed_event, state.round1_decisions)
            reactions.append(reaction)
            state.confidence_scores[agent_id] = reaction.confidence
            self._store.persist_decision(state.simulation_id, reaction, 2)

        state.round2_reactions = reactions
        state.simulation_history.append(
            {"round": 2, "reactions": [r.model_dump() for r in reactions]}
        )

        # Divergence check after round 2
        low_conf = [(aid, c) for aid, c in state.confidence_scores.items() if c < _DIVERGENCE_THRESHOLD]
        if low_conf and not state.divergence_detected:
            state.divergence_detected = True
            state.divergence_agent = low_conf[0][0]
            state.divergence_round = 2

        return state

    def _round3(self, state: SimulationState) -> SimulationState:
        state.round_number = 3
        syntheses: List[AgentSynthesis] = []
        for agent_id, agent in self._registry.items():
            synthesis = agent.synthesize(
                state.seed_event, state.round1_decisions, state.round2_reactions
            )
            syntheses.append(synthesis)
            state.confidence_scores[agent_id] = synthesis.confidence
            self._store.persist_decision(state.simulation_id, synthesis, 3)

        state.round3_syntheses = syntheses
        state.simulation_history.append(
            {"round": 3, "syntheses": [s.model_dump() for s in syntheses]}
        )
        return state

    def _run_audit(self, state: SimulationState) -> SimulationState:
        flags = self._auditor.audit(
            state.round1_decisions,
            state.round2_reactions,
            state.round3_syntheses,
        )
        state.audit_flags = flags
        for flag in flags:
            self._store.persist_audit_flag(state.simulation_id, flag)
        return state

    # ------------------------------------------------------------------
    # Divergence branching
    # ------------------------------------------------------------------

    def _create_branches(self, state: SimulationState) -> SimulationState:
        """Create two sub-simulations: high-risk (A) and status-quo (B)."""
        branch_a = self._run_branch(state, "high_risk")
        branch_b = self._run_branch(state, "status_quo")
        state.scenario_branches = {"A": branch_a, "B": branch_b}

        # Register parent→child relationships in KuzuDB
        self._store.persist_simulation(state)
        for branch in [branch_a, branch_b]:
            sub_state = SimulationState(
                simulation_id=branch.branch_id,
                seed_event=state.seed_event,
                status="completed",
            )
            self._store.persist_simulation(sub_state)

        return state

    def _run_branch(
        self, parent_state: SimulationState, scenario_type: str
    ) -> SimulationBranch:
        """Run a single scenario branch (all rounds) with biased assumptions."""
        branch_seed = f"[{scenario_type.upper()} SCENARIO] {parent_state.seed_event}"
        if scenario_type == "high_risk":
            branch_seed += " — assume worst-case escalation."
        else:
            branch_seed += " — assume minimal change, continuity."

        decisions: List[Dict[str, Any]] = []
        for agent_id, agent in self._registry.items():
            d = agent.decide(branch_seed)
            r = agent.react(branch_seed, [d])
            s = agent.synthesize(branch_seed, [d], [r])
            decisions.append(
                {
                    "agent_id": agent_id,
                    "action": d.model_dump(),
                    "reaction": r.model_dump(),
                    "synthesis": s.model_dump(),
                }
            )

        confs = [item["synthesis"]["confidence"] for item in decisions]
        conf_range = (min(confs), max(confs)) if confs else (0.0, 1.0)

        return SimulationBranch(
            parent_simulation_id=parent_state.simulation_id,
            scenario_type=scenario_type,
            agents_decisions=decisions,
            confidence_range=conf_range,
        )
