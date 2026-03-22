"""Automated intelligence briefing generator."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Briefing:
    """A generated intelligence briefing document.

    Attributes:
        id: Unique briefing identifier.
        title: Briefing title.
        executive_summary: Short executive summary (2-3 sentences).
        key_findings: Bullet-point key findings list.
        detailed_analysis: Full analytical narrative.
        recommendations: Actionable recommendations.
        metadata: Extra metadata (analyst_id, source_events, etc.).
        generated_at: Generation timestamp.
    """

    id: str
    title: str
    executive_summary: str
    key_findings: list[str]
    detailed_analysis: str
    recommendations: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ThreatAssessment:
    """A regional threat assessment.

    Attributes:
        id: Assessment identifier.
        region: Target region.
        timeframe_days: Days ahead the assessment covers.
        overall_threat_level: low | medium | high | critical.
        threat_categories: Breakdown by threat category.
        top_threats: Ordered list of top threat summaries.
        mitigating_factors: Factors that reduce threat severity.
        generated_at: Generation timestamp.
    """

    id: str
    region: str
    timeframe_days: int
    overall_threat_level: str
    threat_categories: dict[str, str]
    top_threats: list[str]
    mitigating_factors: list[str]
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class BriefingGenerator:
    """Auto-generate intelligence briefing reports using LLM synthesis.

    Uses the configured LLM (if available) to synthesize platform data into
    professional briefing documents. Falls back to structured stub content
    when the LLM is not configured.
    """

    # ------------------------------------------------------------------
    # Briefing generation
    # ------------------------------------------------------------------

    async def generate_daily_briefing(
        self, analyst_id: str, date: datetime
    ) -> Briefing:
        """Generate a daily intelligence briefing for an analyst.

        Args:
            analyst_id: Requesting analyst's user ID.
            date: Target date for the briefing.

        Returns:
            :class:`Briefing` synthesizing that day's events.
        """
        events: list[dict] = []
        try:
            from app.db.postgres import fetch_all

            rows = await fetch_all(
                """
                SELECT id, title, description, event_type, severity, created_at
                FROM events
                WHERE created_at::date = :date
                ORDER BY severity DESC, created_at DESC
                LIMIT 20
                """,
                {"date": date.date()},
            )
            events = rows
        except Exception as exc:
            logger.warning("Daily briefing event fetch failed: %s", exc)

        summary_text = await self._synthesize_briefing(
            events,
            title=f"Daily Intelligence Briefing — {date.strftime('%d %B %Y')}",
            context={"analyst_id": analyst_id, "date": date.isoformat()},
        )
        return summary_text

    async def generate_event_briefing(self, event_id: str) -> Briefing:
        """Generate a briefing focused on a single event.

        Args:
            event_id: Target event ID.

        Returns:
            :class:`Briefing` for the event.
        """
        event_data: dict = {}
        try:
            from app.db.postgres import fetch_one

            row = await fetch_one(
                "SELECT * FROM events WHERE id = :id",
                {"id": event_id},
            )
            if row:
                event_data = dict(row)
        except Exception as exc:
            logger.warning("Event briefing fetch failed: %s", exc)

        title = event_data.get("title", f"Event {event_id}")
        return await self._synthesize_briefing(
            [event_data] if event_data else [],
            title=f"Event Briefing: {title}",
            context={"event_id": event_id},
        )

    async def generate_entity_briefing(self, entity_id: str) -> Briefing:
        """Generate a briefing for a specific entity.

        Args:
            entity_id: Target entity ID.

        Returns:
            :class:`Briefing` summarizing activity related to the entity.
        """
        entity_data: dict = {}
        related_events: list[dict] = []
        try:
            from app.db.neo4j_client import neo4j_client

            entity_data = await neo4j_client.get_node(entity_id) or {}
            subgraph = await neo4j_client.get_subgraph(entity_id, depth=1)
            related_events = subgraph.get("nodes", [])[:10]
        except Exception as exc:
            logger.warning("Entity briefing KG fetch failed: %s", exc)

        return await self._synthesize_briefing(
            related_events,
            title=f"Entity Briefing: {entity_id}",
            context={"entity_id": entity_id, "entity_data": entity_data},
        )

    async def generate_threat_assessment(
        self, region: str, timeframe_days: int
    ) -> ThreatAssessment:
        """Generate a regional threat assessment.

        Args:
            region: Target geographic region.
            timeframe_days: Days ahead to assess.

        Returns:
            :class:`ThreatAssessment` for the region and timeframe.
        """
        events: list[dict] = []
        try:
            from app.db.postgres import fetch_all

            rows = await fetch_all(
                """
                SELECT id, title, event_type, severity
                FROM events
                WHERE location::text ILIKE :region
                ORDER BY severity DESC
                LIMIT 15
                """,
                {"region": f"%{region}%"},
            )
            events = rows
        except Exception as exc:
            logger.warning("Threat assessment fetch failed: %s", exc)

        # Simple heuristic threat level
        high_count = sum(
            1 for e in events if e.get("severity") in ("high", "critical")
        )
        if high_count >= 5:
            threat_level = "critical"
        elif high_count >= 3:
            threat_level = "high"
        elif high_count >= 1:
            threat_level = "medium"
        else:
            threat_level = "low"

        categories: dict[str, str] = {}
        for e in events:
            etype = e.get("event_type", "general")
            categories[etype] = categories.get(etype, "low")
            if e.get("severity") in ("high", "critical"):
                categories[etype] = "high"

        top_threats = [
            f"{e.get('event_type', 'unknown')} — {e.get('title', 'Untitled')}"
            for e in events[:5]
        ]

        return ThreatAssessment(
            id=str(uuid.uuid4()),
            region=region,
            timeframe_days=timeframe_days,
            overall_threat_level=threat_level,
            threat_categories=categories,
            top_threats=top_threats,
            mitigating_factors=[
                "International monitoring presence",
                "Active diplomatic channels",
            ],
        )

    # ------------------------------------------------------------------
    # LLM synthesis helper
    # ------------------------------------------------------------------

    async def _synthesize_briefing(
        self,
        events: list[dict],
        title: str,
        context: dict[str, Any],
    ) -> Briefing:
        """Use the LLM to synthesize a structured briefing from events.

        Falls back to structured content when LLM is unavailable.

        Args:
            events: List of event dicts to include.
            title: Briefing title.
            context: Additional context.

        Returns:
            :class:`Briefing` instance.
        """
        event_summaries = "\n".join(
            f"- [{e.get('severity', '?').upper()}] {e.get('title', 'Untitled')}: "
            f"{(e.get('description') or '')[:200]}"
            for e in events[:10]
        ) or "No events found for this period."

        prompt = (
            f"Generate a professional intelligence briefing titled '{title}'.\n\n"
            f"Events:\n{event_summaries}\n\n"
            f"Context: {context}\n\n"
            "Provide a JSON response with keys: executive_summary, key_findings "
            "(list of strings), detailed_analysis, recommendations (list of strings)."
        )

        key_findings: list[str] = []
        detailed_analysis: str = ""
        executive_summary: str = ""
        recommendations: list[str] = []

        try:
            from app.config import settings as _settings
            from langchain_openai import ChatOpenAI  # type: ignore
            from langchain_core.messages import SystemMessage, HumanMessage  # type: ignore

            if _settings.OPENAI_API_KEY:
                llm = ChatOpenAI(
                    model=_settings.OPENAI_MODEL,
                    api_key=_settings.OPENAI_API_KEY,
                    temperature=0.3,
                    max_tokens=2000,
                )
                import asyncio, json

                messages = [
                    SystemMessage(
                        content=(
                            "You are a senior intelligence analyst producing concise, "
                            "professional briefings. Always respond in valid JSON."
                        )
                    ),
                    HumanMessage(content=prompt),
                ]
                response = await asyncio.to_thread(llm.invoke, messages)
                raw = response.content
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start != -1 and end > start:
                    parsed = json.loads(raw[start:end])
                    executive_summary = parsed.get("executive_summary", "")
                    key_findings = parsed.get("key_findings", [])
                    detailed_analysis = parsed.get("detailed_analysis", "")
                    recommendations = parsed.get("recommendations", [])
        except Exception as exc:
            logger.warning("LLM briefing synthesis failed: %s", exc)

        # Fallback / supplement with structured content
        if not executive_summary:
            executive_summary = (
                f"This briefing covers {len(events)} intelligence event(s) "
                f"for the period in question. "
                f"{len([e for e in events if e.get('severity') in ('high','critical')])} "
                f"events are classified as high or critical severity."
            )
        if not key_findings:
            key_findings = [
                f"{e.get('event_type', 'General')} event: {e.get('title', 'Untitled')}"
                for e in events[:5]
            ] or ["No significant events detected."]
        if not detailed_analysis:
            detailed_analysis = "\n\n".join(
                f"**{e.get('title', 'Event')}** [{e.get('severity', '?')}]\n"
                f"{e.get('description', 'No description available.')}"
                for e in events[:10]
            ) or "No detailed analysis available."
        if not recommendations:
            recommendations = [
                "Continue monitoring for developments.",
                "Review related entities in the knowledge graph.",
            ]

        return Briefing(
            id=str(uuid.uuid4()),
            title=title,
            executive_summary=executive_summary,
            key_findings=key_findings,
            detailed_analysis=detailed_analysis,
            recommendations=recommendations,
            metadata=context,
        )


# Module-level singleton
briefing_generator = BriefingGenerator()
