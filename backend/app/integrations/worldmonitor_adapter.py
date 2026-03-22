"""WorldMonitor data source integration adapter."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

try:
    import aiohttp  # type: ignore
    _AIOHTTP_AVAILABLE = True
except ImportError:  # pragma: no cover
    _AIOHTTP_AVAILABLE = False
    logger.warning("aiohttp not installed; WorldMonitor adapter disabled")

from app.config import settings


# ---------------------------------------------------------------------------
# Field mapping
# ---------------------------------------------------------------------------

_FIELD_MAP: dict[str, str] = {
    "id": "id",
    "headline": "title",
    "body": "description",
    "category": "event_type",
    "risk_level": "severity",
    "geo": "location",
    "actors": "entities",
    "keywords": "tags",
    "published_at": "created_at",
}

_SEVERITY_MAP: dict[str, str] = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "very high": "critical",
    "critical": "critical",
}


class WorldMonitorAdapter:
    """WorldMonitor data source integration.

    Fetches events and entities from the WorldMonitor API, normalises
    them to the EL'druin internal format, and supports real-time feed
    subscriptions.

    Args:
        base_url: WorldMonitor API base URL (override default via env).
        api_key: WorldMonitor API key (override default via env).

    Attributes:
        _subscriptions: Active subscription ID → callback mappings.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self._base_url = (
            base_url
            or getattr(settings, "WORLDMONITOR_BASE_URL", "https://api.worldmonitor.example.com/v1")
        )
        self._api_key = (
            api_key or getattr(settings, "WORLDMONITOR_API_KEY", "")
        )
        self._subscriptions: dict[str, dict] = {}
        self._session: Optional[Any] = None

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def _get_session(self) -> Any:
        """Return a lazily-created aiohttp session."""
        if not _AIOHTTP_AVAILABLE:
            raise RuntimeError("aiohttp is required for WorldMonitor adapter")
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self._session

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Any:
        """Make an authenticated API request with retry.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: API path (will be joined with base URL).
            **kwargs: Additional kwargs forwarded to aiohttp.

        Returns:
            Parsed JSON response.

        Raises:
            RuntimeError: If the request fails after retries.
        """
        import asyncio

        url = f"{self._base_url.rstrip('/')}/{path.lstrip('/')}"
        session = await self._get_session()
        last_exc: Optional[Exception] = None

        for attempt in range(1, 4):
            try:
                async with session.request(method, url, **kwargs) as resp:
                    resp.raise_for_status()
                    return await resp.json()
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "WorldMonitor request attempt %d failed: %s", attempt, exc
                )
                if attempt < 3:
                    await asyncio.sleep(2 ** attempt)

        raise RuntimeError(
            f"WorldMonitor request failed after 3 attempts"
        ) from last_exc

    # ------------------------------------------------------------------
    # Event fetching
    # ------------------------------------------------------------------

    async def fetch_events(
        self,
        since: datetime,
        event_types: Optional[list[str]] = None,
    ) -> list[dict]:
        """Fetch events updated since a given timestamp.

        Args:
            since: Fetch events created after this datetime.
            event_types: Optional list of category filters.

        Returns:
            List of normalised event dicts.
        """
        params: dict[str, Any] = {
            "since": since.isoformat(),
            "limit": 100,
        }
        if event_types:
            params["categories"] = ",".join(event_types)

        try:
            data = await self._request("GET", "/events", params=params)
            raw_events: list[dict] = data.get("events", data) if isinstance(data, dict) else data
            return [self.normalize_event(e) for e in raw_events]
        except Exception as exc:
            logger.error("WorldMonitor fetch_events failed: %s", exc)
            return []

    async def fetch_entity(self, entity_id: str) -> dict:
        """Fetch a single entity by ID.

        Args:
            entity_id: WorldMonitor entity identifier.

        Returns:
            Normalised entity dict or empty dict on failure.
        """
        try:
            data = await self._request("GET", f"/entities/{entity_id}")
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            logger.error("WorldMonitor fetch_entity %s failed: %s", entity_id, exc)
            return {}

    # ------------------------------------------------------------------
    # Subscriptions
    # ------------------------------------------------------------------

    async def subscribe_feed(
        self,
        callback: Callable[[dict], None],
        event_types: Optional[list[str]] = None,
    ) -> str:
        """Subscribe to a live feed of events.

        Args:
            callback: Async or sync callable invoked per event.
            event_types: Optional category filters.

        Returns:
            Subscription identifier.
        """
        import uuid, asyncio

        sub_id = str(uuid.uuid4())
        self._subscriptions[sub_id] = {
            "callback": callback,
            "event_types": event_types or [],
            "active": True,
        }
        asyncio.create_task(self._poll_loop(sub_id))
        return sub_id

    async def unsubscribe_feed(self, subscription_id: str) -> bool:
        """Cancel a live feed subscription.

        Args:
            subscription_id: ID returned by :meth:`subscribe_feed`.

        Returns:
            True if cancelled, False if not found.
        """
        if subscription_id in self._subscriptions:
            self._subscriptions[subscription_id]["active"] = False
            del self._subscriptions[subscription_id]
            return True
        return False

    async def _poll_loop(self, sub_id: str) -> None:
        """Background task that polls the API and invokes the callback.

        Args:
            sub_id: Subscription identifier.
        """
        import asyncio, inspect

        last_fetch = datetime.now(UTC)
        while self._subscriptions.get(sub_id, {}).get("active", False):
            try:
                sub = self._subscriptions[sub_id]
                events = await self.fetch_events(
                    since=last_fetch, event_types=sub["event_types"] or None
                )
                last_fetch = datetime.now(UTC)
                for event in events:
                    cb = sub["callback"]
                    if inspect.iscoroutinefunction(cb):
                        await cb(event)
                    else:
                        cb(event)
            except Exception as exc:
                logger.warning("Poll loop error: %s", exc)
            await asyncio.sleep(60)

    # ------------------------------------------------------------------
    # Normalisation
    # ------------------------------------------------------------------

    def normalize_event(self, raw_event: dict) -> dict:
        """Map a WorldMonitor event dict to the internal format.

        Args:
            raw_event: Raw WorldMonitor event dict.

        Returns:
            Normalised event dict ready for :class:`~app.core.event_processor.EventProcessor`.
        """
        normalized: dict = {}
        for wm_field, internal_field in _FIELD_MAP.items():
            if wm_field in raw_event:
                normalized[internal_field] = raw_event[wm_field]

        # Severity normalisation
        raw_sev = str(normalized.get("severity", "medium")).lower()
        normalized["severity"] = _SEVERITY_MAP.get(raw_sev, "medium")

        # Source tag
        normalized["source"] = "worldmonitor"

        # Preserve extra fields in metadata
        known_fields = set(_FIELD_MAP.values())
        extra = {
            k: v for k, v in raw_event.items()
            if k not in _FIELD_MAP and k not in known_fields
        }
        normalized.setdefault("metadata", {}).update(extra)

        return normalized


# Module-level singleton
worldmonitor_adapter = WorldMonitorAdapter()
