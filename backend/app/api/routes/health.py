"""Health check endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", tags=["system"])
def health_check() -> dict:
    """Return a health-check payload that includes database availability."""
    db_status = _check_db()
    return {
        "status": "ok",
        "service": "EL'druin Intelligence Platform",
        "database": db_status,
    }


def _check_db() -> str:
    """Return a short status string for the KuzuDB connection."""
    try:
        from app.core.db import get_db_connection

        conn = get_db_connection()
        conn.execute("RETURN 1")
        return "ok"
    except Exception as exc:
        logger.warning("Health-check DB probe failed: %s", exc)
        return f"unavailable: {exc}"
