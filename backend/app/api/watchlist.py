"""Watchlist API router."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.postgres import get_db
from app.models.schemas import (
    AlertRuleCreate,
    AlertRuleResponse,
    TokenData,
    WatchlistCreate,
    WatchlistResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/watchlist", tags=["Watchlist"])


# ---------------------------------------------------------------------------
# In-memory backing store (replaced by proper ORM model in full production)
# ---------------------------------------------------------------------------

# Key: user_id → list[dict]
_WATCHLIST_STORE: dict[str, list[dict]] = {}
# Key: watchlist_id → list[dict]
_ALERT_RULES_STORE: dict[str, list[dict]] = {}


def _get_user_watchlist(user_id: str) -> list[dict]:
    return _WATCHLIST_STORE.setdefault(user_id, [])


def _find_watchlist_item(user_id: str, item_id: str) -> dict | None:
    for item in _get_user_watchlist(user_id):
        if item["id"] == item_id:
            return item
    return None


# ---------------------------------------------------------------------------
# GET /watchlist/
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=list[WatchlistResponse],
    summary="Get current user's watchlist",
)
async def get_watchlist(
    current_user: TokenData = Depends(get_current_user),
) -> list[WatchlistResponse]:
    """Return all watchlist items for the authenticated user.

    Args:
        current_user: Authenticated user.

    Returns:
        List of :class:`WatchlistResponse`.
    """
    user_id = current_user.user_id or "anonymous"
    items = _get_user_watchlist(user_id)
    result: list[WatchlistResponse] = []
    for item in items:
        rules = [
            AlertRuleResponse(**r)
            for r in _ALERT_RULES_STORE.get(item["id"], [])
        ]
        result.append(
            WatchlistResponse(
                id=item["id"],
                user_id=user_id,
                entity_id=item["entity_id"],
                entity_type=item["entity_type"],
                criteria=item.get("criteria", {}),
                alert_rules=rules,
                created_at=item["created_at"],
            )
        )
    return result


# ---------------------------------------------------------------------------
# POST /watchlist/
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=WatchlistResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add entity to watchlist",
)
async def add_to_watchlist(
    payload: WatchlistCreate,
    current_user: TokenData = Depends(get_current_user),
) -> WatchlistResponse:
    """Add an entity to the current user's watchlist.

    Args:
        payload: Watchlist item creation payload.
        current_user: Authenticated user.

    Returns:
        Created :class:`WatchlistResponse`.
    """
    from datetime import UTC, datetime

    user_id = current_user.user_id or "anonymous"
    item_id = str(uuid.uuid4())
    created_at = datetime.now(UTC)

    item: dict[str, Any] = {
        "id": item_id,
        "entity_id": payload.entity_id,
        "entity_type": payload.entity_type,
        "criteria": payload.criteria,
        "created_at": created_at,
    }
    _get_user_watchlist(user_id).append(item)

    # Persist initial alert rules
    rules: list[AlertRuleResponse] = []
    for rule_payload in payload.alert_rules:
        rule_id = str(uuid.uuid4())
        rule_dict: dict[str, Any] = {
            "id": rule_id,
            "watchlist_id": item_id,
            "condition_type": rule_payload.condition_type,
            "threshold": rule_payload.threshold,
            "notification_channels": rule_payload.notification_channels,
            "is_active": rule_payload.is_active,
        }
        _ALERT_RULES_STORE.setdefault(item_id, []).append(rule_dict)
        rules.append(AlertRuleResponse(**rule_dict))

    # Persist to Redis for cross-instance availability
    try:
        from app.db.redis_client import redis_client
        import json

        await redis_client.hset(
            f"watchlist:{user_id}",
            item_id,
            json.dumps(item, default=str),
        )
    except Exception as exc:
        logger.warning("Redis watchlist persist failed: %s", exc)

    return WatchlistResponse(
        id=item_id,
        user_id=user_id,
        entity_id=payload.entity_id,
        entity_type=payload.entity_type,
        criteria=payload.criteria,
        alert_rules=rules,
        created_at=created_at,
    )


# ---------------------------------------------------------------------------
# DELETE /watchlist/{item_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove item from watchlist",
)
async def remove_from_watchlist(
    item_id: str,
    current_user: TokenData = Depends(get_current_user),
) -> None:
    """Remove an item from the current user's watchlist.

    Args:
        item_id: Watchlist item ID.
        current_user: Authenticated user.

    Raises:
        HTTPException: 404 if not found.
    """
    user_id = current_user.user_id or "anonymous"
    items = _get_user_watchlist(user_id)
    original_len = len(items)
    _WATCHLIST_STORE[user_id] = [i for i in items if i["id"] != item_id]
    if len(_WATCHLIST_STORE[user_id]) == original_len:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist item not found"
        )
    _ALERT_RULES_STORE.pop(item_id, None)

    try:
        from app.db.redis_client import redis_client

        await redis_client.hdel(f"watchlist:{user_id}", item_id)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# GET /watchlist/alerts
# ---------------------------------------------------------------------------


@router.get(
    "/alerts",
    response_model=list[dict],
    summary="Get active alerts for watchlist",
)
async def get_watchlist_alerts(
    current_user: TokenData = Depends(get_current_user),
) -> list[dict]:
    """Return active alerts triggered for the user's watchlist.

    Args:
        current_user: Authenticated user.

    Returns:
        List of alert dicts.
    """
    user_id = current_user.user_id or "anonymous"
    alerts: list[dict] = []

    try:
        from app.db.redis_client import redis_client

        raw_alerts = await redis_client.lrange(f"alerts:{user_id}", 0, 50)
        alerts = [a for a in raw_alerts if isinstance(a, dict)]
    except Exception as exc:
        logger.warning("Alert fetch failed: %s", exc)

    return alerts


# ---------------------------------------------------------------------------
# POST /watchlist/{item_id}/alert-rules
# ---------------------------------------------------------------------------


@router.post(
    "/{item_id}/alert-rules",
    response_model=AlertRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an alert rule to a watchlist item",
)
async def add_alert_rule(
    item_id: str,
    payload: AlertRuleCreate,
    current_user: TokenData = Depends(get_current_user),
) -> AlertRuleResponse:
    """Add an alert rule to a watchlist item.

    Args:
        item_id: Watchlist item ID.
        payload: Alert rule creation payload.
        current_user: Authenticated user.

    Returns:
        Created :class:`AlertRuleResponse`.

    Raises:
        HTTPException: 404 if watchlist item not found.
    """
    user_id = current_user.user_id or "anonymous"
    item = _find_watchlist_item(user_id, item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist item not found"
        )

    rule_id = str(uuid.uuid4())
    rule_dict: dict[str, Any] = {
        "id": rule_id,
        "watchlist_id": item_id,
        "condition_type": payload.condition_type,
        "threshold": payload.threshold,
        "notification_channels": payload.notification_channels,
        "is_active": payload.is_active,
    }
    _ALERT_RULES_STORE.setdefault(item_id, []).append(rule_dict)
    return AlertRuleResponse(**rule_dict)
