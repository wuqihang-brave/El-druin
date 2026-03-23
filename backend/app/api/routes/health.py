"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["system"])
def health_check() -> dict:
    """Return a simple health-check payload."""
    return {"status": "ok", "service": "EL'druin Intelligence Platform"}
