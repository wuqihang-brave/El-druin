"""pytest configuration and shared fixtures for EL'druin test suite."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ─────────────────────────────────────────────
# pytest-asyncio mode
# ─────────────────────────────────────────────

def pytest_configure(config):
    """Register asyncio_mode so pytest-asyncio works without per-test markers."""
    config.addinivalue_line(
        "markers",
        "asyncio: mark test as async",
    )


# ─────────────────────────────────────────────
# Application / Test Client
# ─────────────────────────────────────────────

@pytest.fixture(scope="session")
def mock_settings(tmp_path_factory):
    """Override settings for the test session so no real services are required."""
    with patch("app.config.settings") as mock_s:
        mock_s.ENVIRONMENT = "test"
        mock_s.LOG_LEVEL = "DEBUG"
        mock_s.DATABASE_URL = "postgresql+asyncpg://eldruin:test@localhost:5432/eldruin_test"
        mock_s.NEO4J_URL = "bolt://localhost:7687"
        mock_s.NEO4J_USER = "neo4j"
        mock_s.NEO4J_PASSWORD = "test"
        mock_s.REDIS_URL = "redis://localhost:6379/1"
        mock_s.JWT_SECRET_KEY = "test-secret-key-for-unit-tests-only"
        mock_s.JWT_ALGORITHM = "HS256"
        mock_s.ACCESS_TOKEN_EXPIRE_MINUTES = 30
        mock_s.CORS_ORIGINS = ["http://localhost:3000"]
        mock_s.KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
        mock_s.KAFKA_TOPIC_EVENTS = "test.events"
        mock_s.KAFKA_TOPIC_PREDICTIONS = "test.predictions"
        mock_s.KAFKA_CONSUMER_GROUP = "test-group"
        mock_s.OPENAI_API_KEY = None
        mock_s.OPENAI_MODEL = "gpt-4-turbo-preview"
        mock_s.PINECONE_API_KEY = None
        mock_s.ANONYMIZATION_SALT = "test-salt"
        yield mock_s


@pytest.fixture()
def test_client(mock_settings):
    """Return a FastAPI TestClient with all external services mocked."""
    with (
        patch("app.db.postgres.init_db", new_callable=AsyncMock),
        patch("app.db.neo4j_client.neo4j_client") as mock_neo4j,
        patch("app.db.redis_client.redis_client") as mock_redis,
    ):
        mock_neo4j.connect = AsyncMock()
        mock_neo4j.close = AsyncMock()
        mock_redis.connect = AsyncMock()
        mock_redis.close = AsyncMock()

        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app, raise_server_exceptions=False) as client:
            yield client


# ─────────────────────────────────────────────
# Database mocks
# ─────────────────────────────────────────────

@pytest.fixture()
def mock_db():
    """Async mock for a SQLAlchemy AsyncSession."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture()
def mock_redis():
    """Async mock Redis client."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.exists = AsyncMock(return_value=0)
    client.sadd = AsyncMock(return_value=1)
    client.sismember = AsyncMock(return_value=False)
    client.ping = AsyncMock(return_value=True)
    return client


@pytest.fixture()
def mock_neo4j():
    """Async mock Neo4j driver / session."""
    driver = AsyncMock()
    session = AsyncMock()
    driver.session.return_value.__aenter__ = AsyncMock(return_value=session)
    driver.session.return_value.__aexit__ = AsyncMock(return_value=False)
    session.run = AsyncMock(return_value=AsyncMock(data=MagicMock(return_value=[])))
    return driver
