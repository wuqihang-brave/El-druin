"""Geopolitical analysis and strategic assessment intelligence agent."""

from __future__ import annotations

import time
from typing import Any

from app.agents.base_agent import AgentResult, BaseAgent


class GeopoliticalAgent(BaseAgent):
    """Geopolitical analysis and strategic assessment agent.

    Analyzes power dynamics, evaluates strategic interests of key actors,
    and models diplomatic implications of intelligence events.

    Attributes:
        SYSTEM_PROMPT: Instruction prompt for the LLM.
    """

    SYSTEM_PROMPT = (
        "You are a senior geopolitical analyst and former foreign policy advisor "
        "with expertise in international relations, power dynamics, and strategic "
        "risk assessment. Your task is to:\n"
        "1. Analyze the geopolitical significance of this event.\n"
        "2. Identify the strategic interests of key state and non-state actors.\n"
        "3. Evaluate the diplomatic implications and potential policy responses.\n"
        "4. Assess how this event shifts the regional or global balance of power.\n"
        "5. Provide a confidence score (0.0–1.0) for your geopolitical assessment.\n\n"
        "Respond in JSON with keys: analysis, confidence, evidence (list), "
        "reasoning, key_actors (list), power_shift_direction, "
        "diplomatic_implications (list)."
    )

    _PROMPT_TEMPLATE = (
        "Perform a geopolitical assessment for:\n\n"
        "Event Title: {title}\n"
        "Description: {description}\n"
        "Event Type: {event_type}\n"
        "Severity: {severity}\n"
        "Location: {location}\n"
        "Entities Involved: {entities}\n"
        "Tags: {tags}\n\n"
        "Prediction Type: {prediction_type}\n\n"
        "Provide your geopolitical analysis in JSON format."
    )

    def get_agent_type(self) -> str:
        """Return agent type identifier."""
        return "geopolitical"

    async def analyze(
        self, event_data: dict, context: dict
    ) -> AgentResult:
        """Perform geopolitical analysis on the event.

        Args:
            event_data: Event dict to analyse.
            context: Shared context dict.

        Returns:
            :class:`AgentResult` with geopolitical analysis.
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
            for key in ("key_actors", "power_shift_direction", "diplomatic_implications"):
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
