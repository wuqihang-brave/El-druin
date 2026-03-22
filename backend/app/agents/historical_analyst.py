"""Historical analyst intelligence agent."""

from __future__ import annotations

import time
from typing import Any

from app.agents.base_agent import AgentResult, BaseAgent


class HistoricalAnalystAgent(BaseAgent):
    """Analyzes historical patterns and precedents.

    Searches for similar historical events, identifies recurring patterns
    and cycles, and grounds predictions in documented precedents.

    Attributes:
        SYSTEM_PROMPT: Instruction prompt for the LLM.
    """

    SYSTEM_PROMPT = (
        "You are an expert historical analyst specializing in identifying "
        "patterns and precedents in geopolitical, economic, and social events. "
        "Your task is to:\n"
        "1. Identify similar historical events and their outcomes.\n"
        "2. Detect recurring patterns and cycles that apply to the current event.\n"
        "3. Assess the strength of historical precedent.\n"
        "4. Provide a confidence score (0.0–1.0) based on the strength of precedent.\n\n"
        "Respond in JSON with keys: analysis, confidence, evidence (list), reasoning."
    )

    _PROMPT_TEMPLATE = (
        "Analyze the following event from a historical perspective:\n\n"
        "Event Title: {title}\n"
        "Description: {description}\n"
        "Event Type: {event_type}\n"
        "Severity: {severity}\n"
        "Location: {location}\n"
        "Tags: {tags}\n\n"
        "Prediction Type Requested: {prediction_type}\n\n"
        "Historical Context (similar past events):\n{historical_context}\n\n"
        "Provide your historical analysis in JSON format."
    )

    def get_agent_type(self) -> str:
        """Return agent type identifier."""
        return "historical"

    async def analyze(
        self, event_data: dict, context: dict
    ) -> AgentResult:
        """Perform historical pattern analysis on the event.

        Args:
            event_data: Event dict to analyse.
            context: Shared context including historical_context and
                prediction_type.

        Returns:
            :class:`AgentResult` with historical analysis.
        """
        start_ms = time.monotonic() * 1000

        historical_context = context.get("context", {})
        similar_events = ""
        if hasattr(historical_context, "similar_events"):
            for ev in historical_context.similar_events[:3]:
                similar_events += f"- ID: {ev.get('id')}, Score: {ev.get('score', 0):.2f}\n"
        if not similar_events:
            similar_events = "No directly comparable historical events found."

        prompt = self._format_prompt(
            self._PROMPT_TEMPLATE,
            title=event_data.get("title", ""),
            description=event_data.get("description", ""),
            event_type=event_data.get("event_type", ""),
            severity=event_data.get("severity", ""),
            location=str(event_data.get("location", "")),
            tags=", ".join(event_data.get("tags", [])),
            prediction_type=context.get("prediction_type", "general"),
            historical_context=similar_events,
        )

        try:
            response_text, token_usage = await self._call_llm(
                prompt, self.SYSTEM_PROMPT
            )
            parsed = self._parse_response(response_text)
            confidence = self._calibrate_confidence(
                parsed.get("confidence", 0.5)
            )
            return AgentResult(
                agent_type=self.get_agent_type(),
                analysis=parsed.get("analysis", response_text),
                confidence=confidence,
                evidence=parsed.get("evidence", []),
                reasoning=parsed.get("reasoning", ""),
                token_usage=token_usage,
                execution_time_ms=time.monotonic() * 1000 - start_ms,
            )
        except Exception:
            result = self._stub_result(event_data)
            result.execution_time_ms = time.monotonic() * 1000 - start_ms
            return result
