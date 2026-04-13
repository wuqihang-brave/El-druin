"""
Oracle Laboratory – Base Simulation Agent
==========================================

Defines the five fixed persistent agents with unique expertise domains and
provides a lightweight LLM-backed inference method with graceful fallback to
heuristic responses when no LLM is configured.

Five fixed agents
-----------------
1. Financial Analyst      – economic systems, market dynamics, risk assessment
2. Geopolitical Strategist – power dynamics, international relations, conflict
3. Technology Futurist    – innovation impact, disruption, emergence
4. Institutional Analyst  – regulatory structures, organisational behaviour
5. Sentiment Monitor      – public perception, social dynamics, mood
"""

from __future__ import annotations

import json
import logging
import random
import re
from typing import Any, Dict, List, Optional

from intelligence.schemas import (
    AgentDecision,
    AgentProfile,
    AgentReaction,
    AgentSynthesis,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fixed agent profiles
# ---------------------------------------------------------------------------

AGENT_PROFILES: List[AgentProfile] = [
    AgentProfile(
        agent_id="analyst_1",
        name="Financial Analyst",
        expertise_domain="Economic systems, market dynamics, risk assessment",
        decision_style="Risk-averse, Data-driven",
        historical_accuracy=0.82,
        bias_profile="Conservative, skeptical of rapid changes",
        reasoning_framework="Quantitative modelling, scenario stress-testing",
    ),
    AgentProfile(
        agent_id="analyst_2",
        name="Geopolitical Strategist",
        expertise_domain="Power dynamics, international relations, conflict",
        decision_style="Realist, Long-horizon",
        historical_accuracy=0.78,
        bias_profile="State-centric, balance-of-power oriented",
        reasoning_framework="Structural realism, historical analogy",
    ),
    AgentProfile(
        agent_id="analyst_3",
        name="Technology Futurist",
        expertise_domain="Innovation impact, disruption, emergence",
        decision_style="Optimistic, Disruptive",
        historical_accuracy=0.71,
        bias_profile="Technology-positive, underestimates incumbents",
        reasoning_framework="Exponential thinking, S-curve analysis",
    ),
    AgentProfile(
        agent_id="analyst_4",
        name="Institutional Analyst",
        expertise_domain="Regulatory structures, organisational behaviour",
        decision_style="Process-oriented, Cautious",
        historical_accuracy=0.80,
        bias_profile="Institutional inertia bias, rule-following",
        reasoning_framework="Institutional theory, path-dependence",
    ),
    AgentProfile(
        agent_id="analyst_5",
        name="Sentiment Monitor",
        expertise_domain="Public perception, social dynamics, mood",
        decision_style="Adaptive, Crowd-following",
        historical_accuracy=0.68,
        bias_profile="Recency bias, over-weights viral signals",
        reasoning_framework="Behavioural economics, narrative analysis",
    ),
]


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_ROUND1_TEMPLATE = """\
You are {name}, a {expertise_domain} agent in a multi-agent geopolitical simulation.
Decision style: {decision_style}. Historical accuracy: {accuracy:.0%}.
Known bias: {bias_profile}.
Reasoning framework: {reasoning_framework}.

SEED EVENT: {seed_event}

Provide your ACTION recommendation. Reply ONLY with valid JSON (no markdown):
{{
  "action_type": "escalate | stabilize | observe | intervene",
  "target_entity": "<entity>",
  "confidence": <0.0-1.0>,
  "reasoning": "<1-2 sentences>"
}}"""

_ROUND2_TEMPLATE = """\
You are {name}, a {expertise_domain} agent.

SEED EVENT: {seed_event}

Round 1 decisions by all agents:
{round1_summary}

How will key entities REACT? Reply ONLY with valid JSON:
{{
  "reaction_type": "counteract | align | neutral",
  "affected_entities": ["<Entity1>", "<Entity2>"],
  "confidence": <0.0-1.0>,
  "reasoning": "<1-2 sentences>"
}}"""

_ROUND3_TEMPLATE = """\
You are {name}, a {expertise_domain} agent.

SEED EVENT: {seed_event}

Round 1 actions: {round1_summary}
Round 2 reactions: {round2_summary}

What is the likely EQUILIBRIUM? Reply ONLY with valid JSON:
{{
  "outcome_prediction": "<concise prediction>",
  "risk_level": "low | medium | high | critical",
  "confidence": <0.0-1.0>,
  "reasoning": "<1-2 sentences>"
}}"""


# ---------------------------------------------------------------------------
# Heuristic fallback helpers
# ---------------------------------------------------------------------------

def _heuristic_action(agent_id: str, seed_event: str) -> Dict[str, Any]:
    """Rule-based fallback for round 1 when no LLM is available."""
    text = seed_event.lower()
    risk_keywords = {"crisis", "attack", "collapse", "war", "crash", "threat", "conflict"}
    has_risk = any(kw in text for kw in risk_keywords)

    style_map = {
        "analyst_1": ("stabilize", "Market"),
        "analyst_2": ("observe", "Government"),
        "analyst_3": ("observe", "Technology Sector"),
        "analyst_4": ("intervene", "Regulatory Bodies"),
        "analyst_5": ("escalate" if has_risk else "observe", "Public"),
    }
    action_type, target = style_map.get(agent_id, ("observe", "General"))
    base_conf = 0.65 + random.uniform(-0.05, 0.15)
    if has_risk:
        base_conf = min(base_conf + 0.05, 1.0)

    return {
        "action_type": action_type,
        "target_entity": target,
        "confidence": round(base_conf, 2),
        "reasoning": f"Based on initial event assessment, {action_type} appears appropriate for {target}.",
    }


def _heuristic_reaction(agent_id: str, round1_decisions: list) -> Dict[str, Any]:
    """Rule-based fallback for round 2."""
    escalate_count = sum(
        1 for d in round1_decisions if d.get("action_type") == "escalate"
    )
    reaction = "align" if escalate_count >= 2 else "neutral"
    return {
        "reaction_type": reaction,
        "affected_entities": ["Market", "Government"],
        "confidence": round(0.60 + random.uniform(0.0, 0.15), 2),
        "reasoning": f"Majority signals suggest a {reaction} response from key entities.",
    }


def _heuristic_synthesis(agent_id: str, round1_decisions: list, round2_reactions: list) -> Dict[str, Any]:
    """Rule-based fallback for round 3."""
    escalate_count = sum(
        1 for d in round1_decisions if d.get("action_type") == "escalate"
    )
    risk_level = "high" if escalate_count >= 3 else ("medium" if escalate_count >= 2 else "low")
    return {
        "outcome_prediction": f"Moderate systemic adjustment expected with {risk_level} risk of prolonged instability.",
        "risk_level": risk_level,
        "confidence": round(0.62 + random.uniform(0.0, 0.12), 2),
        "reasoning": "Synthesis of action/reaction rounds suggests equilibrium with residual tail risk.",
    }


# ---------------------------------------------------------------------------
# LLM caller (mirrors semantic_explainer.py pattern)
# ---------------------------------------------------------------------------

def _call_llm(settings: Any, prompt: str) -> str:
    """Call LLM via LangChain; raises if unavailable."""
    provider = getattr(settings, "llm_provider", "none")
    if provider == "groq":
        from langchain_groq import ChatGroq  # type: ignore[import]
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = ChatGroq(
            model=getattr(settings, "llm_model", "llama3-8b-8192"),
            temperature=0.4,
            api_key=settings.groq_api_key,
            max_tokens=300,
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        return str(response.content).strip()

    if provider == "openai":
        from langchain_openai import ChatOpenAI  # type: ignore[import]
        from langchain_core.messages import HumanMessage

        llm = ChatOpenAI(
            model=getattr(settings, "llm_model", "gpt-4o-mini"),
            temperature=0.4,
            api_key=settings.openai_api_key,
            max_tokens=300,
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        return str(response.content).strip()

    if provider == "deepseek":
        from langchain_openai import ChatOpenAI  # type: ignore[import]
        from langchain_core.messages import HumanMessage

        llm = ChatOpenAI(
            model=getattr(settings, "llm_model", "deepseek-chat"),
            temperature=0.4,
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            max_tokens=300,
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        return str(response.content).strip()

    raise RuntimeError("No LLM configured")


def _parse_json_response(raw: str) -> Dict[str, Any]:
    """Extract JSON object from raw LLM response (handles markdown fences)."""
    # Strip markdown code fences
    cleaned = re.sub(r"```[a-z]*\n?", "", raw).replace("```", "").strip()
    # Find first { ... }
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# BaseSimulationAgent
# ---------------------------------------------------------------------------

class BaseSimulationAgent:
    """Wraps an AgentProfile and provides round 1/2/3 inference methods."""

    def __init__(self, profile: AgentProfile, settings: Optional[Any] = None) -> None:
        self.profile = profile
        self._settings = settings

    # ------------------------------------------------------------------
    # Public round methods
    # ------------------------------------------------------------------

    def decide(self, seed_event: str) -> AgentDecision:
        """Round 1 – produce an ACTION decision."""
        data = self._run_round1(seed_event)
        return AgentDecision(
            agent_id=self.profile.agent_id,
            action_type=data.get("action_type", "observe"),
            target_entity=data.get("target_entity", ""),
            confidence=float(data.get("confidence", 0.5)),
            reasoning=data.get("reasoning", ""),
        )

    def react(
        self, seed_event: str, round1_decisions: List[AgentDecision]
    ) -> AgentReaction:
        """Round 2 – produce a REACTION prediction."""
        r1_raw = [
            {
                "agent": d.agent_id,
                "action": d.action_type,
                "target": d.target_entity,
                "conf": d.confidence,
            }
            for d in round1_decisions
        ]
        data = self._run_round2(seed_event, r1_raw)
        return AgentReaction(
            agent_id=self.profile.agent_id,
            reaction_type=data.get("reaction_type", "neutral"),
            affected_entities=data.get("affected_entities", []),
            confidence=float(data.get("confidence", 0.5)),
            reasoning=data.get("reasoning", ""),
        )

    def synthesize(
        self,
        seed_event: str,
        round1_decisions: List[AgentDecision],
        round2_reactions: List[AgentReaction],
    ) -> AgentSynthesis:
        """Round 3 – produce a SYNTHESIS / equilibrium prediction."""
        r1_raw = [{"agent": d.agent_id, "action": d.action_type} for d in round1_decisions]
        r2_raw = [{"agent": r.agent_id, "reaction": r.reaction_type} for r in round2_reactions]
        data = self._run_round3(seed_event, r1_raw, r2_raw)
        return AgentSynthesis(
            agent_id=self.profile.agent_id,
            outcome_prediction=data.get("outcome_prediction", ""),
            risk_level=data.get("risk_level", "medium"),
            confidence=float(data.get("confidence", 0.5)),
            reasoning=data.get("reasoning", ""),
        )

    # ------------------------------------------------------------------
    # Internal LLM / fallback helpers
    # ------------------------------------------------------------------

    def _run_round1(self, seed_event: str) -> Dict[str, Any]:
        if self._settings and getattr(self._settings, "llm_enabled", False):
            prompt = _ROUND1_TEMPLATE.format(
                name=self.profile.name,
                expertise_domain=self.profile.expertise_domain,
                decision_style=self.profile.decision_style,
                accuracy=self.profile.historical_accuracy,
                bias_profile=self.profile.bias_profile,
                reasoning_framework=self.profile.reasoning_framework,
                seed_event=seed_event,
            )
            try:
                raw = _call_llm(self._settings, prompt)
                return _parse_json_response(raw)
            except Exception as exc:
                logger.warning("LLM round1 failed for %s: %s – using heuristic", self.profile.agent_id, exc)
        return _heuristic_action(self.profile.agent_id, seed_event)

    def _run_round2(self, seed_event: str, r1_raw: list) -> Dict[str, Any]:
        if self._settings and getattr(self._settings, "llm_enabled", False):
            r1_summary = json.dumps(r1_raw, indent=2)
            prompt = _ROUND2_TEMPLATE.format(
                name=self.profile.name,
                expertise_domain=self.profile.expertise_domain,
                seed_event=seed_event,
                round1_summary=r1_summary,
            )
            try:
                raw = _call_llm(self._settings, prompt)
                return _parse_json_response(raw)
            except Exception as exc:
                logger.warning("LLM round2 failed for %s: %s – using heuristic", self.profile.agent_id, exc)
        return _heuristic_reaction(self.profile.agent_id, r1_raw)

    def _run_round3(
        self, seed_event: str, r1_raw: list, r2_raw: list
    ) -> Dict[str, Any]:
        if self._settings and getattr(self._settings, "llm_enabled", False):
            prompt = _ROUND3_TEMPLATE.format(
                name=self.profile.name,
                expertise_domain=self.profile.expertise_domain,
                seed_event=seed_event,
                round1_summary=json.dumps(r1_raw, indent=2),
                round2_summary=json.dumps(r2_raw, indent=2),
            )
            try:
                raw = _call_llm(self._settings, prompt)
                return _parse_json_response(raw)
            except Exception as exc:
                logger.warning("LLM round3 failed for %s: %s – using heuristic", self.profile.agent_id, exc)
        return _heuristic_synthesis(self.profile.agent_id, r1_raw, r2_raw)


# ---------------------------------------------------------------------------
# Registry factory
# ---------------------------------------------------------------------------

def build_agent_registry(
    settings: Optional[Any] = None,
) -> Dict[str, BaseSimulationAgent]:
    """Return a dict of {agent_id: BaseSimulationAgent} for all five agents."""
    return {p.agent_id: BaseSimulationAgent(p, settings) for p in AGENT_PROFILES}
