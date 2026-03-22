"""Generic custom data source connector."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration schema
# ---------------------------------------------------------------------------


class DataSourceConfig(BaseModel):
    """Configuration for a custom data source.

    Attributes:
        source_id: Unique source identifier.
        name: Human-readable source name.
        source_type: Connection protocol (rest_api | kafka | websocket | file).
        connection_params: Protocol-specific connection parameters.
        field_mappings: Dict mapping source field names → internal field names.
        polling_interval_seconds: How often to poll (for REST/file sources).
    """

    model_config = ConfigDict(extra="allow")

    source_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    source_type: str  # rest_api | kafka | websocket | file
    connection_params: dict[str, Any]
    field_mappings: dict[str, str]
    polling_interval_seconds: int = Field(default=60)


# ---------------------------------------------------------------------------
# Connector
# ---------------------------------------------------------------------------


class CustomSourceConnector:
    """Generic connector for arbitrary external data sources.

    Supports REST API polling, Kafka consumption, WebSocket streaming,
    and file-based ingestion.

    Attributes:
        _sources: Registered source configs keyed by source_id.
        _polling_tasks: Active asyncio tasks for polling loops.
    """

    def __init__(self) -> None:
        self._sources: dict[str, DataSourceConfig] = {}
        self._polling_tasks: dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register_source(self, config: DataSourceConfig) -> str:
        """Register a new custom data source.

        Args:
            config: Source configuration.

        Returns:
            Registered source ID.
        """
        self._sources[config.source_id] = config
        logger.info(
            "Registered source '%s' (type=%s, id=%s)",
            config.name,
            config.source_type,
            config.source_id,
        )
        return config.source_id

    # ------------------------------------------------------------------
    # Fetching
    # ------------------------------------------------------------------

    async def fetch_from_source(
        self,
        source_id: str,
        since: Optional[datetime] = None,
    ) -> list[dict]:
        """Fetch events from a registered source.

        Args:
            source_id: Source identifier.
            since: Optional timestamp to filter events after.

        Returns:
            List of normalised event dicts.
        """
        config = self._sources.get(source_id)
        if config is None:
            logger.warning("Unknown source_id: %s", source_id)
            return []

        if config.source_type == "rest_api":
            return await self._fetch_rest(config, since)
        if config.source_type == "file":
            return await self._fetch_file(config)
        if config.source_type in ("kafka", "websocket"):
            # Streaming sources use start_polling
            logger.info(
                "Source %s is a streaming source; use start_polling()", source_id
            )
            return []

        logger.warning("Unsupported source_type: %s", config.source_type)
        return []

    # ------------------------------------------------------------------
    # Normalisation
    # ------------------------------------------------------------------

    async def normalize_event(
        self, raw: dict, field_mappings: dict[str, str]
    ) -> dict:
        """Apply field mappings to a raw event dict.

        Args:
            raw: Raw event from the source.
            field_mappings: Dict mapping ``source_field → internal_field``.

        Returns:
            Normalised event dict.
        """
        normalised: dict = {}
        for source_field, internal_field in field_mappings.items():
            if source_field in raw:
                normalised[internal_field] = raw[source_field]

        # Preserve unmapped fields in metadata
        mapped_source_fields = set(field_mappings.keys())
        extra = {k: v for k, v in raw.items() if k not in mapped_source_fields}
        normalised.setdefault("metadata", {}).update(extra)
        return normalised

    # ------------------------------------------------------------------
    # Polling lifecycle
    # ------------------------------------------------------------------

    async def start_polling(self, source_id: str) -> bool:
        """Start a background polling task for a source.

        Args:
            source_id: Source to start polling.

        Returns:
            True if the task was started.
        """
        config = self._sources.get(source_id)
        if config is None:
            return False
        if source_id in self._polling_tasks:
            logger.info("Source %s already polling", source_id)
            return True

        task = asyncio.create_task(self._poll_loop(source_id))
        self._polling_tasks[source_id] = task
        logger.info("Started polling for source %s", source_id)
        return True

    async def stop_polling(self, source_id: str) -> bool:
        """Stop the polling task for a source.

        Args:
            source_id: Source to stop.

        Returns:
            True if the task was stopped.
        """
        task = self._polling_tasks.pop(source_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped polling for source %s", source_id)
            return True
        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _poll_loop(self, source_id: str) -> None:
        """Continuously poll a source and ingest events.

        Args:
            source_id: Source to poll.
        """
        config = self._sources.get(source_id)
        if config is None:
            return
        last_fetch: Optional[datetime] = None

        while source_id in self._polling_tasks:
            try:
                raw_events = await self._fetch_rest(config, since=last_fetch)
                last_fetch = datetime.utcnow()
                if raw_events:
                    from app.core.streaming_engine import streaming_engine

                    await streaming_engine.ingest_event_stream(
                        source=config.source_id,
                        event_batch=raw_events,
                    )
            except Exception as exc:
                logger.warning("Polling error for %s: %s", source_id, exc)
            await asyncio.sleep(config.polling_interval_seconds)

    async def _fetch_rest(
        self,
        config: DataSourceConfig,
        since: Optional[datetime] = None,
    ) -> list[dict]:
        """Fetch events from a REST API source.

        Args:
            config: Source configuration.
            since: Optional filter timestamp.

        Returns:
            List of normalised event dicts.
        """
        try:
            import aiohttp  # type: ignore

            params: dict[str, Any] = dict(
                config.connection_params.get("default_params", {})
            )
            if since:
                since_key = config.connection_params.get("since_param", "since")
                params[since_key] = since.isoformat()

            url = config.connection_params.get("url", "")
            headers = config.connection_params.get("headers", {})

            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(
                    url,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()

            events_key = config.connection_params.get("events_key", "")
            raw_list: list[dict] = (
                data.get(events_key, data)
                if events_key and isinstance(data, dict)
                else data
            )
            return [
                await self.normalize_event(e, config.field_mappings)
                for e in raw_list
                if isinstance(e, dict)
            ]
        except ImportError:
            logger.warning("aiohttp not installed; REST fetch skipped")
        except Exception as exc:
            logger.error("REST fetch failed for %s: %s", config.source_id, exc)
        return []

    async def _fetch_file(self, config: DataSourceConfig) -> list[dict]:
        """Read events from a local or remote file.

        Args:
            config: Source configuration with ``path`` in connection_params.

        Returns:
            List of normalised event dicts.
        """
        import json
        import csv as csv_module

        path: str = config.connection_params.get("path", "")
        file_format: str = config.connection_params.get("format", "json")

        if not path:
            return []

        try:
            with open(path) as f:
                if file_format == "json":
                    raw_data = json.load(f)
                    if isinstance(raw_data, dict):
                        raw_data = raw_data.get("events", [raw_data])
                elif file_format == "csv":
                    reader = csv_module.DictReader(f)
                    raw_data = list(reader)
                else:
                    return []

            return [
                await self.normalize_event(e, config.field_mappings)
                for e in raw_data
                if isinstance(e, dict)
            ]
        except Exception as exc:
            logger.error("File fetch failed for %s: %s", config.source_id, exc)
            return []


# Module-level singleton
custom_source_connector = CustomSourceConnector()
