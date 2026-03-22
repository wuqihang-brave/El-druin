"""WebSocket endpoints for real-time event, prediction, and alert streaming."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.api.auth import decode_token

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])


# ---------------------------------------------------------------------------
# Connection manager
# ---------------------------------------------------------------------------


class ConnectionManager:
    """Manages active WebSocket connections grouped by stream type.

    Attributes:
        _connections: Map of stream_type → {client_id → WebSocket}.
    """

    def __init__(self) -> None:
        self._connections: dict[str, dict[str, WebSocket]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        client_id: str,
        stream_type: str,
    ) -> None:
        """Accept a WebSocket connection and register it.

        Args:
            websocket: Incoming WebSocket.
            client_id: Unique client identifier.
            stream_type: Stream category (events | predictions | alerts).
        """
        await websocket.accept()
        self._connections.setdefault(stream_type, {})[client_id] = websocket
        logger.debug("WS connected: client=%s stream=%s", client_id, stream_type)

    def disconnect(self, client_id: str, stream_type: str) -> None:
        """Remove a client from the connection registry.

        Args:
            client_id: Client identifier.
            stream_type: Stream category.
        """
        stream = self._connections.get(stream_type, {})
        stream.pop(client_id, None)
        logger.debug("WS disconnected: client=%s stream=%s", client_id, stream_type)

    async def broadcast(self, message: Any, stream_type: str) -> None:
        """Send a message to all clients in a stream.

        Args:
            message: JSON-serializable message payload.
            stream_type: Target stream category.
        """
        disconnected: list[str] = []
        for client_id, ws in list(self._connections.get(stream_type, {}).items()):
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(client_id)
        for cid in disconnected:
            self.disconnect(cid, stream_type)

    async def send_personal(self, message: Any, client_id: str) -> None:
        """Send a message to a specific client.

        Args:
            message: JSON-serializable message payload.
            client_id: Target client identifier.
        """
        for stream_sockets in self._connections.values():
            ws = stream_sockets.get(client_id)
            if ws:
                try:
                    await ws.send_json(message)
                except Exception:
                    pass
                return


# Module-level connection manager
manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Authentication helper
# ---------------------------------------------------------------------------


async def _authenticate(token: Optional[str]) -> bool:
    """Validate a bearer token from a WebSocket query parameter.

    Args:
        token: JWT token string (may be None).

    Returns:
        True if the token is valid.
    """
    if token is None:
        return False
    token_data = decode_token(token)
    return token_data is not None


# ---------------------------------------------------------------------------
# WS /ws/events/stream
# ---------------------------------------------------------------------------


@router.websocket("/ws/events/stream")
async def events_stream(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
) -> None:
    """Stream real-time events to the client.

    Clients connect with an optional JWT token and optional filter parameters.
    The server broadcasts new events from the Redis events stream.

    Args:
        websocket: WebSocket connection.
        token: Bearer JWT token for authentication.
        event_type: Optional event type filter.
        severity: Optional severity filter.
    """
    if not await _authenticate(token):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    client_id = id(websocket)
    await manager.connect(websocket, str(client_id), "events")

    # Subscribe to Redis pub/sub for new events
    pubsub = None
    try:
        from app.db.redis_client import redis_client

        pubsub = await redis_client.subscribe("events:new")
    except Exception:
        pass

    try:
        while True:
            # Send keepalive ping every 30 seconds
            ping_task = asyncio.create_task(asyncio.sleep(30))
            message_task: Optional[asyncio.Task] = None

            if pubsub:
                message_task = asyncio.create_task(
                    pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                )

            done, pending = await asyncio.wait(
                [ping_task] + ([message_task] if message_task else []),
                return_when=asyncio.FIRST_COMPLETED,
            )

            for t in pending:
                t.cancel()

            if ping_task in done:
                await websocket.send_json({"type": "ping"})
                # Check for pong
                try:
                    data = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
                    if data.get("type") == "pong":
                        continue
                except Exception:
                    break

            if message_task and message_task in done:
                msg = message_task.result()
                if msg and msg.get("type") == "message":
                    event = msg["data"]
                    if isinstance(event, dict):
                        # Apply filters
                        if event_type and event.get("event_type") != event_type:
                            continue
                        if severity and event.get("severity") != severity:
                            continue
                        await websocket.send_json({"type": "event", "data": event})

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("Events WS error: %s", exc)
    finally:
        manager.disconnect(str(client_id), "events")
        if pubsub:
            try:
                await pubsub.unsubscribe()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# WS /ws/predictions/updates
# ---------------------------------------------------------------------------


@router.websocket("/ws/predictions/updates")
async def predictions_updates(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None),
) -> None:
    """Stream prediction status updates to the client.

    Args:
        websocket: WebSocket connection.
        token: Bearer JWT token.
    """
    if not await _authenticate(token):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    client_id = id(websocket)
    await manager.connect(websocket, str(client_id), "predictions")

    pubsub = None
    try:
        from app.db.redis_client import redis_client

        pubsub = await redis_client.subscribe("predictions:updates")
    except Exception:
        pass

    try:
        while True:
            await websocket.send_json({"type": "ping"})
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
                if data.get("type") == "pong":
                    continue
            except asyncio.TimeoutError:
                continue
            except Exception:
                break

            if pubsub:
                msg = await pubsub.get_message(ignore_subscribe_messages=True)
                if msg and msg.get("type") == "message":
                    await websocket.send_json(
                        {"type": "prediction_update", "data": msg["data"]}
                    )

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("Predictions WS error: %s", exc)
    finally:
        manager.disconnect(str(client_id), "predictions")
        if pubsub:
            try:
                await pubsub.unsubscribe()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# WS /ws/watchlist/alerts
# ---------------------------------------------------------------------------


@router.websocket("/ws/watchlist/alerts")
async def watchlist_alerts(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None),
) -> None:
    """Stream watchlist alert notifications to the client.

    Args:
        websocket: WebSocket connection.
        token: Bearer JWT token.
    """
    if not await _authenticate(token):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    token_data = decode_token(token or "")
    user_id = token_data.user_id if token_data else "anonymous"
    client_id = id(websocket)
    await manager.connect(websocket, str(client_id), "alerts")

    pubsub = None
    try:
        from app.db.redis_client import redis_client

        pubsub = await redis_client.subscribe(
            f"alerts:{user_id}", "alerts:broadcast"
        )
    except Exception:
        pass

    try:
        while True:
            await websocket.send_json({"type": "ping"})

            if pubsub:
                try:
                    msg = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=30.0,
                    )
                    if msg and msg.get("type") == "message":
                        await websocket.send_json(
                            {"type": "alert", "data": msg["data"]}
                        )
                except asyncio.TimeoutError:
                    continue
            else:
                # No Redis — sleep between pings
                await asyncio.sleep(30)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("Watchlist alerts WS error: %s", exc)
    finally:
        manager.disconnect(str(client_id), "alerts")
        if pubsub:
            try:
                await pubsub.unsubscribe()
            except Exception:
                pass
