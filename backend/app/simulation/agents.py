"""
Agent definitions for the Taiwan-Strait crisis simulation.

Each agent is a callable that receives the current ``SimulationState`` and
returns a *partial* state update (only the fields it wants to modify).

Agents
------
* **LeaderA**  – aggressive leader of CountryA, seeks to extend influence.
* **LeaderB**  – defensive leader of CountryB, seeks to protect sovereignty.
* **Ally**     – ally of CountryA, provides diplomatic / military support.
* **Analyst**  – neutral intelligence analyst, estimates resolution probabilities.

When an LLM is configured (LLM_PROVIDER != "none"), agents call the LLM to
generate richer messages.  Otherwise a deterministic rule-based fallback is
used so the simulation works with no API key.
"""

from __future__ import annotations

import logging
import random
from typing import Any, Dict, List

from app.simulation.state import AgentMessage, SimulationState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent metadata registry
# ---------------------------------------------------------------------------

AGENT_REGISTRY: Dict[str, Dict[str, Any]] = {
    "LeaderA": {
        "role": "Aggressive Leader (CountryA)",
        "goal": "Expand CountryA's influence and assert territorial claims.",
        "backstory": (
            "A hawkish leader who views military strength as the cornerstone "
            "of national security. Believes that showing resolve deters adversaries."
        ),
        "tension_bias": +0.12,   # tends to raise tension
    },
    "LeaderB": {
        "role": "Defensive Leader (CountryB)",
        "goal": "Protect CountryB's sovereignty and avoid open conflict.",
        "backstory": (
            "A pragmatic leader who prioritises economic stability and "
            "international law. Willing to negotiate but will defend if threatened."
        ),
        "tension_bias": -0.08,   # tends to lower tension
    },
    "Ally": {
        "role": "Supportive Ally",
        "goal": "Back CountryA diplomatically while preventing full-scale war.",
        "backstory": (
            "A regional power aligned with CountryA. Provides intelligence "
            "sharing and naval presence, but fears wider escalation."
        ),
        "tension_bias": +0.06,   # slight escalation from presence
    },
    "Analyst": {
        "role": "Neutral Intelligence Analyst",
        "goal": "Provide an objective assessment of the situation.",
        "backstory": (
            "A senior analyst at a multilateral research institute. Synthesises "
            "open-source intelligence to estimate conflict probabilities."
        ),
        "tension_bias": 0.0,    # neutral
    },
}

# Ordered rotation of agents across simulation steps
_AGENT_TURN_ORDER: List[str] = ["LeaderA", "LeaderB", "Ally", "Analyst"]

# ---------------------------------------------------------------------------
# Deterministic rule-based message templates
# ---------------------------------------------------------------------------

_TEMPLATES: Dict[str, List[str]] = {
    "LeaderA": [
        "CountryA is mobilising naval forces in response to provocation. "
        "We will not tolerate incursions into our maritime zone.",
        "Our patience is exhausted. A live-fire exercise will commence within 48 hours "
        "near the contested strait.",
        "We issue a final warning: withdraw immediately or face consequences. "
        "The People's Military stands ready.",
        "CountryA's red lines have been crossed. We are escalating our response.",
        "We call on our allies to stand with us in this hour of resolve.",
    ],
    "LeaderB": [
        "CountryB urges restraint and calls for immediate dialogue. "
        "All aggressive manoeuvres must cease.",
        "We have activated additional air-defence systems as a precautionary measure. "
        "We remain committed to peaceful resolution.",
        "CountryB is pursuing emergency back-channel communications to defuse tensions.",
        "We categorically reject unilateral assertions of sovereignty over international waters.",
        "A bilateral ceasefire framework is on the table; we urge CountryA to engage.",
    ],
    "Ally": [
        "The Ally has deployed a carrier strike group to the region "
        "as a show of solidarity with CountryA.",
        "We are providing real-time intelligence to our partner. "
        "Diplomatic channels with CountryB remain open.",
        "Ally officials have contacted CountryB, warning against miscalculation.",
        "We support CountryA's right to self-determination but advocate for de-escalation.",
        "Joint military exercises with CountryA are being expanded in scope.",
    ],
    "Analyst": [
        "Current indicators suggest a 35% probability of kinetic exchange "
        "within 72 hours if tensions remain unchanged.",
        "Diplomatic back-channels are active. Historical precedent suggests "
        "a 55% chance of negotiated de-escalation.",
        "Both sides have raised readiness levels. Miscalculation risk is elevated.",
        "Economic interdependence acts as a deterrent. War probability estimated at 20%.",
        "Key inflection point: the next 24 hours will determine whether "
        "the crisis stabilises or escalates.",
    ],
}

# ---------------------------------------------------------------------------
# LLM helper (optional)
# ---------------------------------------------------------------------------

def _build_prompt(agent_name: str, state: SimulationState) -> str:
    meta = AGENT_REGISTRY[agent_name]
    recent = state["messages"][-3:] if state["messages"] else []
    history = "\n".join(
        f"[{m['agent']}] {m['content']}" for m in recent
    )
    return (
        f"You are {agent_name}, {meta['role']}.\n"
        f"Goal: {meta['goal']}\n"
        f"Backstory: {meta['backstory']}\n\n"
        f"Current situation (crisis summary):\n{state['news_event']}\n\n"
        f"Knowledge graph context:\n{state.get('kg_context', 'N/A')}\n\n"
        f"Tension level: {state['tension_level']:.2f} / 1.0\n\n"
        f"Recent messages:\n{history}\n\n"
        "Respond in 1-2 sentences with your action or statement. "
        "Be concise and in-character."
    )


def _call_llm(prompt: str) -> str:
    """Call the configured LLM. Returns empty string on failure."""
    try:
        from app.core.config import get_settings
        cfg = get_settings()
        if not cfg.llm_enabled:
            return ""
        if cfg.llm_provider == "openai":
            from langchain_openai import ChatOpenAI  # type: ignore
            llm = ChatOpenAI(
                model=cfg.llm_model,
                temperature=cfg.llm_temperature,
                openai_api_key=cfg.openai_api_key,
            )
        elif cfg.llm_provider == "groq":
            from langchain_groq import ChatGroq  # type: ignore
            llm = ChatGroq(
                model=cfg.llm_model,
                temperature=cfg.llm_temperature,
                groq_api_key=cfg.groq_api_key,
            )
        else:
            return ""
        from langchain_core.messages import HumanMessage
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content.strip()
    except Exception as exc:
        logger.warning("LLM call failed, using template fallback: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# Agent node implementations
# ---------------------------------------------------------------------------

def _agent_node(agent_name: str, state: SimulationState) -> Dict[str, Any]:
    """Generic agent node logic; returns a partial SimulationState update."""
    meta = AGENT_REGISTRY[agent_name]
    step = state["step"]

    # ── Generate message content ─────────────────────────────────────────
    prompt = _build_prompt(agent_name, state)
    content = _call_llm(prompt)
    if not content:
        # Fallback: random choice from templates to vary responses across steps
        templates = _TEMPLATES[agent_name]
        content = random.choice(templates)

    # ── Compute tension delta ─────────────────────────────────────────────
    base_delta = meta["tension_bias"]
    # Add slight randomness (±0.03) to make each run unique
    noise = random.uniform(-0.03, 0.03)
    tension_delta = round(base_delta + noise, 4)

    # ── Build message ─────────────────────────────────────────────────────
    msg: AgentMessage = {
        "agent": agent_name,
        "role": meta["role"],
        "content": content,
        "step": step,
        "tension_delta": tension_delta,
    }

    new_tension = max(0.0, min(1.0, state["tension_level"] + tension_delta))

    # ── Determine next agent in rotation ─────────────────────────────────
    current_idx = _AGENT_TURN_ORDER.index(agent_name)
    next_agent = _AGENT_TURN_ORDER[(current_idx + 1) % len(_AGENT_TURN_ORDER)]

    return {
        "messages": state["messages"] + [msg],
        "tension_level": new_tension,
        "current_agent": next_agent,
    }


def leader_a_node(state: SimulationState) -> Dict[str, Any]:
    return _agent_node("LeaderA", state)


def leader_b_node(state: SimulationState) -> Dict[str, Any]:
    return _agent_node("LeaderB", state)


def ally_node(state: SimulationState) -> Dict[str, Any]:
    return _agent_node("Ally", state)


def analyst_node(state: SimulationState) -> Dict[str, Any]:
    """Analyst node also updates resolution probabilities and branch path."""
    update = _agent_node("Analyst", state)
    tension = update["tension_level"]

    # ── Update branch path ────────────────────────────────────────────────
    if tension > 0.7:
        branch = "escalation"
    elif tension < 0.35:
        branch = "de-escalation"
    else:
        branch = "negotiation"

    new_path = state["path"] + [branch]

    # ── Update resolution probabilities ──────────────────────────────────
    war_prob = round(min(0.95, tension * 0.9), 3)
    neg_prob = round(max(0.05, (1.0 - tension) * 0.6), 3)
    stalemate_prob = round(max(0.0, 1.0 - war_prob - neg_prob), 3)
    # Normalise to sum = 1
    total = war_prob + neg_prob + stalemate_prob
    if total > 0:
        war_prob = round(war_prob / total, 3)
        neg_prob = round(neg_prob / total, 3)
        stalemate_prob = round(1.0 - war_prob - neg_prob, 3)

    update["path"] = new_path
    update["resolution_probabilities"] = {
        "war / open conflict": war_prob,
        "negotiated resolution": neg_prob,
        "stalemate / frozen conflict": stalemate_prob,
    }
    return update


# ── Step counter / termination node ─────────────────────────────────────────

def step_counter_node(state: SimulationState) -> Dict[str, Any]:
    """Increment the step counter and check termination condition."""
    new_step = state["step"] + 1
    finished = new_step >= state["max_steps"] or state["tension_level"] >= 0.95
    return {"step": new_step, "finished": finished}


# ── Knowledge graph query tool ───────────────────────────────────────────────

def query_kg_context(news_event: str) -> str:
    """Query the knowledge graph for entities/relations relevant to the event."""
    try:
        from app.knowledge.knowledge_graph import get_knowledge_graph
        kg = get_knowledge_graph()
        # Try to find entities mentioned in the news event
        keywords = ["Taiwan", "Strait", "Military", "Navy", "US", "China", "Conflict"]
        neighbours = []
        for kw in keywords:
            found = kg.get_neighbours(kw, depth=1)
            neighbours.extend(found)
            if len(neighbours) >= 10:
                break
        if not neighbours:
            return "No relevant knowledge graph context available."
        lines = []
        for n in neighbours[:8]:
            name = n.get("name", "")
            rel = n.get("relation", "related_to")
            target = n.get("target", "")
            if name and target:
                lines.append(f"  • {name} –[{rel}]→ {target}")
        return "Knowledge graph context:\n" + "\n".join(lines) if lines else "No KG context."
    except Exception as exc:
        logger.debug("KG context query failed: %s", exc)
        return "Knowledge graph context unavailable."
