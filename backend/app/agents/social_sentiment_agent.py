"""Social sentiment intelligence agent."""

from __future__ import annotations

import time
from typing import Any

from app.agents.base_agent import AgentResult, BaseAgent


class SocialSentimentAgent(BaseAgent):
    """Social sentiment and public opinion tracking agent.

    Analyzes sentiment trends, identifies dominant narratives and
    influencers, and tracks shifts in public opinion dynamics.

    Attributes:
        SYSTEM_PROMPT: Instruction prompt for the LLM.
    """

    SYSTEM_PROMPT = (
        "You are an expert social media and public opinion analyst with deep "
        "expertise in sentiment analysis, narrative identification, and influence "
        "network mapping. Your task is to:\n"
        "1. Analyze the likely public sentiment and media narrative around this event.\n"
        "2. Identify key narratives that will emerge in public discourse.\n"
        "3. Assess which actors or groups are likely to shape the narrative.\n"
        "4. Predict how public opinion may evolve over the relevant timeframe.\n"
        "5. Provide a confidence score (0.0–1.0) for your sentiment assessment.\n\n"
        "Respond in JSON with keys: analysis, confidence, evidence (list), "
        "reasoning, dominant_narrative, sentiment_direction (positive/negative/mixed), "
        "key_influencers (list)."
    )

    _PROMPT_TEMPLATE = (
        "Analyze the social sentiment and public discourse dynamics for:\n\n"
        "Event Title: {title}\n"
        "Description: {description}\n"
        "Event Type: {event_type}\n"
        "Severity: {severity}\n"
        "Location: {location}\n"
        "Tags: {tags}\n\n"
        "Prediction Type: {prediction_type}\n\n"
        "Provide your social sentiment analysis in JSON format."
    )

    def get_agent_type(self) -> str:
        """Return agent type identifier."""
        return "sentiment"

    async def analyze(
        self, event_data: dict, context: dict
    ) -> AgentResult:
        """Perform social sentiment analysis on the event.

        Args:
            event_data: Event dict to analyse.
            context: Shared context dict.

        Returns:
            :class:`AgentResult` with sentiment analysis.
        """
        start_ms = time.monotonic() * 1000

        prompt = self._format_prompt(
            self._PROMPT_TEMPLATE,
            title=event_data.get("title", ""),
            description=event_data.get("description", ""),
            event_type=event_data.get("event_type", ""),
            severity=event_data.get("severity", ""),
            location=str(event_data.get("location", "")),
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
            if "dominant_narrative" in parsed:
                metadata["dominant_narrative"] = parsed["dominant_narrative"]
            if "sentiment_direction" in parsed:
                metadata["sentiment_direction"] = parsed["sentiment_direction"]
            if "key_influencers" in parsed:
                metadata["key_influencers"] = parsed["key_influencers"]
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
