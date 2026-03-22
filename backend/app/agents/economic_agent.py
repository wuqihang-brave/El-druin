"""Economic impact assessment intelligence agent."""

from __future__ import annotations

import time
from typing import Any

from app.agents.base_agent import AgentResult, BaseAgent


class EconomicAgent(BaseAgent):
    """Economic impact assessment agent.

    Assesses economic impacts, models market reactions, and evaluates
    potential supply chain disruptions from intelligence events.

    Attributes:
        SYSTEM_PROMPT: Instruction prompt for the LLM.
    """

    SYSTEM_PROMPT = (
        "You are a senior economic analyst and former central bank advisor with "
        "expertise in macroeconomic modeling, market dynamics, and supply chain "
        "analysis. Your task is to:\n"
        "1. Assess the direct and indirect economic impacts of this event.\n"
        "2. Model likely market reactions (equity, currency, commodity markets).\n"
        "3. Evaluate potential supply chain disruptions and trade flow changes.\n"
        "4. Identify economic actors most exposed to risk or opportunity.\n"
        "5. Provide a confidence score (0.0–1.0) for your economic assessment.\n\n"
        "Respond in JSON with keys: analysis, confidence, evidence (list), "
        "reasoning, gdp_impact_direction (positive/negative/neutral), "
        "affected_markets (list), supply_chain_risks (list)."
    )

    _PROMPT_TEMPLATE = (
        "Conduct an economic impact assessment for:\n\n"
        "Event Title: {title}\n"
        "Description: {description}\n"
        "Event Type: {event_type}\n"
        "Severity: {severity}\n"
        "Location: {location}\n"
        "Entities Involved: {entities}\n"
        "Tags: {tags}\n\n"
        "Prediction Type: {prediction_type}\n\n"
        "Provide your economic analysis in JSON format."
    )

    def get_agent_type(self) -> str:
        """Return agent type identifier."""
        return "economic"

    async def analyze(
        self, event_data: dict, context: dict
    ) -> AgentResult:
        """Perform economic impact analysis on the event.

        Args:
            event_data: Event dict to analyse.
            context: Shared context dict.

        Returns:
            :class:`AgentResult` with economic analysis.
        """
        start_ms = time.monotonic() * 1000

        entities = event_data.get("entities", [])
        entity_summary = ", ".join(
            e.get("name", str(e)) for e in entities[:5]
        ) or "None identified"

        prompt = self._format_prompt(
            self._PROMPT_TEMPLATE,
            title=event_data.get("title", ""),
            description=event_data.get("description", ""),
            event_type=event_data.get("event_type", ""),
            severity=event_data.get("severity", ""),
            location=str(event_data.get("location", "")),
            entities=entity_summary,
            tags=", ".join(event_data.get("tags", [])),
            prediction_type=context.get("prediction_type", "general"),
        )

        try:
            response_text, token_usage = await self._call_llm(
                prompt, self.SYSTEM_PROMPT
            )
            parsed = self._parse_response(response_text)
            confidence = self._calibrate_confidence(
                parsed.get("confidence", 0.5)
            )
            metadata: dict = {}
            for key in ("gdp_impact_direction", "affected_markets", "supply_chain_risks"):
                if key in parsed:
                    metadata[key] = parsed[key]
            return AgentResult(
                agent_type=self.get_agent_type(),
                analysis=parsed.get("analysis", response_text),
                confidence=confidence,
                evidence=parsed.get("evidence", []),
                reasoning=parsed.get("reasoning", ""),
                token_usage=token_usage,
                execution_time_ms=time.monotonic() * 1000 - start_ms,
                metadata=metadata,
            )
        except Exception:
            result = self._stub_result(event_data)
            result.execution_time_ms = time.monotonic() * 1000 - start_ms
            return result
