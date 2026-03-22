"""Abstract base class for all intelligence agents."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from langchain_openai import ChatOpenAI  # type: ignore
    from langchain_core.messages import HumanMessage, SystemMessage  # type: ignore
    _LANGCHAIN_AVAILABLE = True
except ImportError:  # pragma: no cover
    _LANGCHAIN_AVAILABLE = False
    logger.warning("langchain-openai not installed; LLM agents will return stubs")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class AgentResult:
    """Result produced by a single intelligence agent.

    Attributes:
        agent_type: Identifying agent type string.
        analysis: Narrative analysis text.
        confidence: Confidence score in [0.0, 1.0].
        evidence: List of evidence strings supporting the analysis.
        reasoning: Step-by-step reasoning explanation.
        token_usage: LLM token usage breakdown.
        execution_time_ms: Wall-clock execution time in milliseconds.
        metadata: Optional additional metadata.
    """

    agent_type: str
    analysis: str
    confidence: float
    evidence: list[str]
    reasoning: str
    token_usage: dict[str, int]
    execution_time_ms: float
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Base agent
# ---------------------------------------------------------------------------


class BaseAgent(ABC):
    """Abstract base for all EL'druin intelligence agents.

    Subclasses must implement :meth:`analyze` and :meth:`get_agent_type`.

    Args:
        settings: Application :class:`~app.config.Settings` instance.

    Attributes:
        _llm: LangChain :class:`ChatOpenAI` instance (lazy).
        _max_retries: Maximum LLM call retry attempts.
        _base_retry_delay: Base backoff delay in seconds.
    """

    _max_retries: int = 3
    _base_retry_delay: float = 1.0

    def __init__(self, settings: Any) -> None:
        self._settings = settings
        self._llm: Optional[Any] = None

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def analyze(
        self, event_data: dict, context: dict
    ) -> AgentResult:
        """Run agent analysis on the supplied event.

        Args:
            event_data: Event dict to analyse.
            context: Shared context dict (historical data, prediction type, etc.).

        Returns:
            :class:`AgentResult` with analysis and confidence.
        """

    @abstractmethod
    def get_agent_type(self) -> str:
        """Return the unique type identifier for this agent.

        Returns:
            Agent type string (e.g. ``"historical"``).
        """

    # ------------------------------------------------------------------
    # LLM interaction
    # ------------------------------------------------------------------

    def _get_llm(self) -> Any:
        """Lazily instantiate the LangChain LLM."""
        if self._llm is None:
            if not _LANGCHAIN_AVAILABLE:
                raise RuntimeError("langchain-openai is not installed")
            if not self._settings.OPENAI_API_KEY:
                raise RuntimeError("OPENAI_API_KEY is not configured")
            self._llm = ChatOpenAI(
                model=self._settings.OPENAI_MODEL,
                api_key=self._settings.OPENAI_API_KEY,
                temperature=0.2,
                max_tokens=2000,
            )
        return self._llm

    async def _call_llm(
        self, prompt: str, system_prompt: str
    ) -> tuple[str, dict[str, int]]:
        """Call the LLM with retry and exponential backoff.

        Args:
            prompt: User-facing prompt text.
            system_prompt: System instruction prompt.

        Returns:
            Tuple of (response text, token usage dict).

        Raises:
            RuntimeError: If all retries are exhausted.
        """
        delay = self._base_retry_delay
        last_exc: Optional[Exception] = None

        for attempt in range(1, self._max_retries + 1):
            try:
                llm = self._get_llm()
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=prompt),
                ]
                response = await asyncio.to_thread(llm.invoke, messages)
                token_usage: dict[str, int] = {}
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    token_usage = {
                        "prompt_tokens": response.usage_metadata.get(
                            "input_tokens", 0
                        ),
                        "completion_tokens": response.usage_metadata.get(
                            "output_tokens", 0
                        ),
                        "total_tokens": response.usage_metadata.get(
                            "total_tokens", 0
                        ),
                    }
                return response.content, token_usage
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "%s attempt %d/%d failed: %s",
                    self.get_agent_type(),
                    attempt,
                    self._max_retries,
                    exc,
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(delay)
                    delay *= 2

        raise RuntimeError(
            f"{self.get_agent_type()} LLM call failed after {self._max_retries} attempts"
        ) from last_exc

    # ------------------------------------------------------------------
    # Prompt helpers
    # ------------------------------------------------------------------

    def _format_prompt(self, template: str, **kwargs: Any) -> str:
        """Format a prompt template with keyword arguments.

        Args:
            template: Prompt template string with ``{key}`` placeholders.
            **kwargs: Values to inject into the template.

        Returns:
            Formatted prompt string.
        """
        return template.format(**kwargs)

    def _parse_response(self, response: str) -> dict[str, Any]:
        """Attempt to parse a JSON object from an LLM response.

        Args:
            response: Raw LLM response string.

        Returns:
            Parsed dict or ``{"text": response}`` fallback.
        """
        # Try to extract JSON block
        start = response.find("{")
        end = response.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(response[start:end])
            except json.JSONDecodeError:
                pass
        return {"text": response}

    # ------------------------------------------------------------------
    # Calibration
    # ------------------------------------------------------------------

    @staticmethod
    def _calibrate_confidence(raw_confidence: float) -> float:
        """Clamp and calibrate a raw confidence value.

        Args:
            raw_confidence: Uncalibrated confidence value.

        Returns:
            Confidence clamped to [0.05, 0.95].
        """
        return max(0.05, min(0.95, float(raw_confidence)))

    # ------------------------------------------------------------------
    # Stub fallback (used when LLM is unavailable)
    # ------------------------------------------------------------------

    def _stub_result(self, event_data: dict) -> AgentResult:
        """Return a placeholder result when the LLM is not available.

        Args:
            event_data: Event dict.

        Returns:
            :class:`AgentResult` with placeholder content.
        """
        return AgentResult(
            agent_type=self.get_agent_type(),
            analysis=f"[{self.get_agent_type()} — LLM unavailable] Analysis pending.",
            confidence=0.5,
            evidence=[],
            reasoning="LLM not configured or unavailable.",
            token_usage={},
            execution_time_ms=0.0,
        )
