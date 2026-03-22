"""Integration tests for the /health endpoint."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient with all external services mocked for integration tests."""
    with (
        patch("app.db.postgres.init_db", new_callable=AsyncMock),
        patch("app.db.postgres.engine") as mock_engine,
        patch("app.db.neo4j_client.neo4j_client") as mock_neo4j,
        patch("app.db.redis_client.redis_client") as mock_redis,
    ):
        mock_engine.dispose = AsyncMock()
        mock_neo4j.connect = AsyncMock()
        mock_neo4j.close = AsyncMock()
        mock_redis.connect = AsyncMock()
        mock_redis.close = AsyncMock()

        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app, raise_server_exceptions=False) as tc:
            yield tc


# ─────────────────────────────────────────────
# /health
# ─────────────────────────────────────────────

class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_returns_200(self, client):
        """Health check returns HTTP 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_is_json(self, client):
        """Health check returns valid JSON."""
        response = client.get("/health")
        data = response.json()
        assert isinstance(data, dict)

    def test_health_response_has_status_ok(self, client):
        """Health check payload includes status == 'ok'."""
        response = client.get("/health")
        data = response.json()
        assert data.get("status") == "ok"

    def test_health_response_has_timestamp(self, client):
        """Health check payload includes an ISO-format timestamp."""
        response = client.get("/health")
        data = response.json()
        assert "timestamp" in data
        assert isinstance(data["timestamp"], str)
        # Basic ISO-8601 sanity check
        assert "T" in data["timestamp"]

    def test_health_response_has_environment(self, client):
        """Health check payload includes the current environment string."""
        response = client.get("/health")
        data = response.json()
        assert "environment" in data
        assert isinstance(data["environment"], str)


# ─────────────────────────────────────────────
# API prefix sanity checks
# ─────────────────────────────────────────────

class TestAPIRoutes:
    """Smoke tests that registered API routes respond (not 404/405)."""

    def test_events_list_requires_auth(self, client):
        """GET /api/v1/events without a token returns 401 or 403, not 404."""
        response = client.get("/api/v1/events/")
        assert response.status_code in (401, 403, 422)

    def test_predictions_list_requires_auth(self, client):
        """GET /api/v1/predictions without a token returns 401 or 403, not 404."""
        response = client.get("/api/v1/predictions/")
        assert response.status_code in (401, 403, 422)

    def test_kg_entities_requires_auth(self, client):
        """GET /api/v1/kg/entities without a token returns 401 or 403, not 404."""
        response = client.get("/api/v1/kg/entities")
        assert response.status_code in (401, 403, 422)

    def test_nonexistent_route_returns_404(self, client):
        """A completely unknown path returns HTTP 404."""
        response = client.get("/api/v1/does-not-exist")
        assert response.status_code == 404
