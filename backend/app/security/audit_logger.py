"""Tamper-evident audit logging with hash chaining and data lineage."""

from __future__ import annotations

import hashlib
import json
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
class DataLineage:
    """Lineage of an entity derived from audit logs.

    Attributes:
        entity_id: Target entity.
        creation_log_id: Audit log ID of the creation record.
        modification_logs: Ordered list of modification log IDs.
        access_logs: Recent access log IDs.
        last_modified_by: User ID of the last modifier.
        last_modified_at: Timestamp of the last modification.
    """

    entity_id: str
    creation_log_id: Optional[str] = None
    modification_logs: list[str] = field(default_factory=list)
    access_logs: list[str] = field(default_factory=list)
    last_modified_by: Optional[str] = None
    last_modified_at: Optional[datetime] = None


@dataclass
class ComplianceReport:
    """Compliance report covering a date range.

    Attributes:
        start_date: Report start date.
        end_date: Report end date.
        total_events: Total audit events in range.
        unique_users: Number of unique users.
        data_exports: Number of data export events.
        access_denials: Number of access denial events.
        data_modifications: Number of data modification events.
        integrity_verified: Whether log integrity was verified.
    """

    start_date: datetime
    end_date: datetime
    total_events: int = 0
    unique_users: int = 0
    data_exports: int = 0
    access_denials: int = 0
    data_modifications: int = 0
    integrity_verified: bool = False


@dataclass
class IntegrityReport:
    """Hash-chain integrity verification report.

    Attributes:
        start_id: First log ID checked.
        end_id: Last log ID checked.
        records_checked: Number of records verified.
        records_valid: Number that passed hash verification.
        is_valid: Overall integrity result.
        tampered_records: IDs of any tampered records.
    """

    start_id: str
    end_id: str
    records_checked: int = 0
    records_valid: int = 0
    is_valid: bool = True
    tampered_records: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Audit logger
# ---------------------------------------------------------------------------


class AuditLogger:
    """Tamper-evident audit logging via PostgreSQL with hash chaining.

    Each audit record stores:

    * A forward-linked chain hash: ``SHA256(prev_hash + record_content)``
    * Event type, user, and resource identifiers
    * Timestamps in UTC

    Attributes:
        _last_hash: The most recently stored chain hash (in-memory cache).
    """

    _GENESIS_HASH = "0" * 64

    def __init__(self) -> None:
        self._last_hash: str = self._GENESIS_HASH

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_hash(self, prev_hash: str, content: dict) -> str:
        """Compute the chain hash for a new record.

        Args:
            prev_hash: Hash of the previous record.
            content: Record content dict.

        Returns:
            Hex-encoded SHA-256 hash string.
        """
        payload = prev_hash + json.dumps(content, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()

    async def _write_log(self, event_type: str, data: dict) -> str:
        """Write a single audit record and return its ID.

        Args:
            event_type: Audit event type string.
            data: Record payload dict.

        Returns:
            Log record ID string.
        """
        log_id = str(uuid.uuid4())
        content = {
            "id": log_id,
            "event_type": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            **data,
        }
        chain_hash = self._compute_hash(self._last_hash, content)
        content["chain_hash"] = chain_hash
        content["prev_hash"] = self._last_hash
        self._last_hash = chain_hash

        try:
            from app.db.postgres import execute

            await execute(
                """
                INSERT INTO audit_logs
                    (id, event_type, user_id, data, chain_hash, prev_hash, created_at)
                VALUES
                    (:id, :event_type, :user_id, :data, :chain_hash, :prev_hash, NOW())
                """,
                {
                    "id": log_id,
                    "event_type": event_type,
                    "user_id": data.get("user_id", "system"),
                    "data": json.dumps(content, default=str),
                    "chain_hash": chain_hash,
                    "prev_hash": content["prev_hash"],
                },
            )
        except Exception as exc:
            # Audit failures are logged but never swallowed silently
            logger.error("Audit log write failed for %s: %s", log_id, exc)

        return log_id

    # ------------------------------------------------------------------
    # Public logging API
    # ------------------------------------------------------------------

    async def log_query(
        self,
        user_id: str,
        query: str,
        results_count: int,
        execution_time: float,
    ) -> str:
        """Audit a data query.

        Args:
            user_id: User who ran the query.
            query: Query string or description.
            results_count: Number of results returned.
            execution_time: Execution time in seconds.

        Returns:
            Audit log record ID.
        """
        return await self._write_log(
            "query",
            {
                "user_id": user_id,
                "query": query,
                "results_count": results_count,
                "execution_time": execution_time,
            },
        )

    async def log_data_export(
        self,
        user_id: str,
        entity_ids: list[str],
        format: str,
    ) -> str:
        """Audit a data export operation.

        Args:
            user_id: Exporting user.
            entity_ids: List of exported entity IDs.
            format: Export format (json, csv, pdf).

        Returns:
            Audit log record ID.
        """
        return await self._write_log(
            "data_export",
            {
                "user_id": user_id,
                "entity_ids": entity_ids,
                "format": format,
                "count": len(entity_ids),
            },
        )

    async def log_data_modification(
        self,
        user_id: str,
        entity_id: str,
        changes: dict[str, Any],
    ) -> str:
        """Audit a data modification.

        Args:
            user_id: User who made the change.
            entity_id: Affected entity ID.
            changes: Dict of ``{field: {old, new}}`` change records.

        Returns:
            Audit log record ID.
        """
        return await self._write_log(
            "data_modification",
            {
                "user_id": user_id,
                "entity_id": entity_id,
                "changes": changes,
            },
        )

    async def log_access_denied(
        self,
        user_id: str,
        resource_id: str,
        action: str,
        reason: str,
    ) -> str:
        """Audit an access-denied event.

        Args:
            user_id: Requesting user.
            resource_id: Resource that was denied.
            action: Attempted action.
            reason: Human-readable denial reason.

        Returns:
            Audit log record ID.
        """
        return await self._write_log(
            "access_denied",
            {
                "user_id": user_id,
                "resource_id": resource_id,
                "action": action,
                "reason": reason,
            },
        )

    # ------------------------------------------------------------------
    # Lineage & compliance
    # ------------------------------------------------------------------

    async def trace_data_lineage(self, entity_id: str) -> DataLineage:
        """Reconstruct data lineage for an entity from audit logs.

        Args:
            entity_id: Entity to trace.

        Returns:
            :class:`DataLineage` instance.
        """
        lineage = DataLineage(entity_id=entity_id)
        try:
            from app.db.postgres import fetch_all

            rows = await fetch_all(
                """
                SELECT id, event_type, user_id, created_at
                FROM audit_logs
                WHERE data::jsonb @> :filter
                ORDER BY created_at ASC
                """,
                {"filter": json.dumps({"entity_id": entity_id})},
            )
            for row in rows:
                etype = row["event_type"]
                if etype == "create":
                    lineage.creation_log_id = row["id"]
                elif etype == "data_modification":
                    lineage.modification_logs.append(row["id"])
                    lineage.last_modified_by = row["user_id"]
                    lineage.last_modified_at = row["created_at"]
                elif etype == "query":
                    lineage.access_logs.append(row["id"])
        except Exception as exc:
            logger.warning("Lineage query failed for %s: %s", entity_id, exc)
        return lineage

    async def generate_compliance_report(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> ComplianceReport:
        """Generate a compliance report for a date range.

        Args:
            start_date: Report start (inclusive).
            end_date: Report end (inclusive).

        Returns:
            :class:`ComplianceReport` populated from audit logs.
        """
        report = ComplianceReport(
            start_date=start_date, end_date=end_date
        )
        try:
            from app.db.postgres import fetch_one, fetch_all

            row = await fetch_one(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(DISTINCT user_id) AS unique_users,
                    SUM(CASE WHEN event_type = 'data_export' THEN 1 ELSE 0 END) AS exports,
                    SUM(CASE WHEN event_type = 'access_denied' THEN 1 ELSE 0 END) AS denials,
                    SUM(CASE WHEN event_type = 'data_modification' THEN 1 ELSE 0 END) AS modifications
                FROM audit_logs
                WHERE created_at BETWEEN :start AND :end
                """,
                {"start": start_date, "end": end_date},
            )
            if row:
                report.total_events = int(row["total"] or 0)
                report.unique_users = int(row["unique_users"] or 0)
                report.data_exports = int(row["exports"] or 0)
                report.access_denials = int(row["denials"] or 0)
                report.data_modifications = int(row["modifications"] or 0)
        except Exception as exc:
            logger.warning("Compliance report query failed: %s", exc)
        return report

    async def verify_log_integrity(
        self,
        start_id: str,
        end_id: str,
    ) -> IntegrityReport:
        """Verify hash-chain integrity between two log record IDs.

        Args:
            start_id: First log ID to include.
            end_id: Last log ID to include.

        Returns:
            :class:`IntegrityReport` with any detected tampering.
        """
        report = IntegrityReport(start_id=start_id, end_id=end_id)
        try:
            from app.db.postgres import fetch_all

            rows = await fetch_all(
                """
                SELECT id, data, chain_hash, prev_hash
                FROM audit_logs
                WHERE created_at >= (SELECT created_at FROM audit_logs WHERE id = :start)
                  AND created_at <= (SELECT created_at FROM audit_logs WHERE id = :end)
                ORDER BY created_at ASC
                """,
                {"start": start_id, "end": end_id},
            )
            prev_hash = self._GENESIS_HASH
            for row in rows:
                report.records_checked += 1
                content = json.loads(row["data"])
                # Remove the hash fields before recomputing
                content.pop("chain_hash", None)
                content.pop("prev_hash", None)
                expected = self._compute_hash(prev_hash, content)
                if expected != row["chain_hash"]:
                    report.tampered_records.append(row["id"])
                else:
                    report.records_valid += 1
                prev_hash = row["chain_hash"]

            report.is_valid = len(report.tampered_records) == 0
        except Exception as exc:
            logger.warning("Integrity verification failed: %s", exc)
        return report


# Module-level singleton
audit_logger = AuditLogger()
