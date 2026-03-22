"""Causal analyst intelligence agent."""

from __future__ import annotations

import time
from typing import Any

from app.agents.base_agent import AgentResult, BaseAgent


class CausalAnalystAgent(BaseAgent):
    """Root cause and causal chain analysis agent.

    Builds causal chains, identifies root causes and contributing factors,
    and maps cascading downstream effects.

    Attributes:
        SYSTEM_PROMPT: Instruction prompt for the LLM.
    """

    SYSTEM_PROMPT = (
        "You are an expert causal analyst specializing in root cause analysis "
        "and causal chain modeling for complex geopolitical and socioeconomic events. "
        "Your task is to:\n"
        "1. Identify the root causes of the event.\n"
        "2. Build a causal chain showing how factors led to this outcome.\n"
        "3. Map potential cascading effects and second-order consequences.\n"
        "4. Assess contributing factors and their relative weights.\n"
        "5. Provide a confidence score (0.0–1.0) for your causal model.\n\n"
        "Respond in JSON with keys: analysis, confidence, evidence (list), "
        "reasoning, root_causes (list), cascading_effects (list)."
    )

    _PROMPT_TEMPLATE = (
        "Perform causal chain analysis on the following event:\n\n"
        "Event Title: {title}\n"
        "Description: {description}\n"
        "Event Type: {event_type}\n"
        "Severity: {severity}\n"
        "Location: {location}\n"
        "Entities Involved: {entities}\n"
        "Tags: {tags}\n\n"
        "Prediction Type: {prediction_type}\n\n"
        "Provide your causal analysis in JSON format."
    )

    def get_agent_type(self) -> str:
        """Return agent type identifier."""
        return "causal"

    async def analyze(
        self, event_data: dict, context: dict
    ) -> AgentResult:
        """Perform causal chain analysis on the event.

        Args:
            event_data: Event dict to analyse.
            context: Shared context dict.

        Returns:
            :class:`AgentResult` with causal analysis.
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
            if "root_causes" in parsed:
                metadata["root_causes"] = parsed["root_causes"]
            if "cascading_effects" in parsed:
                metadata["cascading_effects"] = parsed["cascading_effects"]
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
