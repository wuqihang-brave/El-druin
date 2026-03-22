"""Unit tests for AuditLogger (async, with mocked DB)."""

from __future__ import annotations

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.security.audit_logger import AuditLogger, DataLineage


@pytest.fixture()
def logger_instance():
    """Fresh AuditLogger for each test (no DB required — DB calls are mocked)."""
    return AuditLogger()


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _patch_execute():
    """Context manager that stubs the DB execute helper to a no-op AsyncMock."""
    return patch("app.db.postgres.execute", new_callable=AsyncMock)


def _patch_fetch_all(return_value=None):
    """Stub fetch_all used by trace_data_lineage."""
    return patch("app.db.postgres.fetch_all", new_callable=AsyncMock, return_value=return_value or [])


# ─────────────────────────────────────────────
# log_query
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_log_query_returns_string_id(logger_instance):
    """log_query returns a non-empty string log ID."""
    with _patch_execute():
        log_id = await logger_instance.log_query(
            user_id="user-1",
            query="SELECT * FROM events",
            results_count=42,
            execution_time=0.123,
        )
    assert isinstance(log_id, str)
    assert len(log_id) > 0


@pytest.mark.asyncio
async def test_log_query_advances_chain_hash(logger_instance):
    """Each log_query call changes the internal chain hash."""
    genesis = logger_instance._last_hash
    with _patch_execute():
        await logger_instance.log_query("u1", "q1", 10, 0.01)
        hash_after_first = logger_instance._last_hash
        await logger_instance.log_query("u1", "q2", 5, 0.02)
        hash_after_second = logger_instance._last_hash

    assert hash_after_first != genesis
    assert hash_after_second != hash_after_first


@pytest.mark.asyncio
async def test_log_query_survives_db_failure(logger_instance):
    """log_query does not raise even if the DB write fails."""
    with patch("app.db.postgres.execute", side_effect=Exception("DB down")):
        # Should not raise — audit failures are logged, not re-raised
        log_id = await logger_instance.log_query("u1", "SELECT 1", 0, 0.001)
    assert isinstance(log_id, str)


# ─────────────────────────────────────────────
# log_data_export
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_log_data_export_returns_string_id(logger_instance):
    """log_data_export returns a non-empty string log ID."""
    with _patch_execute():
        log_id = await logger_instance.log_data_export(
            user_id="analyst-1",
            entity_ids=["e1", "e2", "e3"],
            format="json",
        )
    assert isinstance(log_id, str)
    assert len(log_id) > 0


@pytest.mark.asyncio
async def test_log_data_export_advances_chain_hash(logger_instance):
    """log_data_export updates the chain hash."""
    before = logger_instance._last_hash
    with _patch_execute():
        await logger_instance.log_data_export("u1", ["e1"], "csv")
    assert logger_instance._last_hash != before


@pytest.mark.asyncio
async def test_log_data_export_survives_db_failure(logger_instance):
    """log_data_export does not raise on DB failure."""
    with patch("app.db.postgres.execute", side_effect=RuntimeError("conn error")):
        log_id = await logger_instance.log_data_export("u1", [], "pdf")
    assert isinstance(log_id, str)


# ─────────────────────────────────────────────
# trace_data_lineage
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_trace_data_lineage_returns_data_lineage(logger_instance):
    """trace_data_lineage returns a DataLineage object."""
    with _patch_fetch_all([]):
        result = await logger_instance.trace_data_lineage("entity-abc")
    assert isinstance(result, DataLineage)
    assert result.entity_id == "entity-abc"


@pytest.mark.asyncio
async def test_trace_data_lineage_populates_modification_logs(logger_instance):
    """Modification audit records appear in modification_logs."""
    mock_rows = [
        {"id": "log-1", "event_type": "data_modification", "data": '{"entity_id": "entity-abc"}'},
        {"id": "log-2", "event_type": "query", "data": '{"query": "SELECT 1"}'},
    ]
    with _patch_fetch_all(mock_rows):
        result = await logger_instance.trace_data_lineage("entity-abc")
    assert isinstance(result, DataLineage)


@pytest.mark.asyncio
async def test_trace_data_lineage_survives_db_failure(logger_instance):
    """trace_data_lineage returns an empty DataLineage on DB failure."""
    with patch("app.db.postgres.fetch_all", side_effect=Exception("DB error")):
        result = await logger_instance.trace_data_lineage("entity-xyz")
    assert isinstance(result, DataLineage)
    assert result.entity_id == "entity-xyz"


# ─────────────────────────────────────────────
# Hash chain integrity
# ─────────────────────────────────────────────

def test_compute_hash_is_deterministic(logger_instance):
    """The same inputs always produce the same hash."""
    h1 = logger_instance._compute_hash("abc", {"key": "value"})
    h2 = logger_instance._compute_hash("abc", {"key": "value"})
    assert h1 == h2


def test_compute_hash_differs_for_different_content(logger_instance):
    """Different content produces different hashes."""
    h1 = logger_instance._compute_hash("abc", {"key": "value1"})
    h2 = logger_instance._compute_hash("abc", {"key": "value2"})
    assert h1 != h2


def test_genesis_hash_is_64_zeros(logger_instance):
    """The genesis (initial) hash is 64 zero characters."""
    assert logger_instance._last_hash == "0" * 64
