"""
Assessment Store
================

SQLite-backed persistence layer for Assessment records.

The database file is stored at ``<BASE_DIR>/data/assessments.db``.
The module exposes a single module-level singleton ``assessment_store``
that is safe to import from any application module.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.config import BASE_DIR
from app.schemas.assessment import (
    Assessment,
    AssessmentCreate,
    AssessmentStatus,
    AssessmentType,
    AssessmentUpdate,
)

logger = logging.getLogger(__name__)

_DB_PATH = Path(BASE_DIR) / "data" / "assessments.db"

_DDL = """
CREATE TABLE IF NOT EXISTS assessments (
    assessment_id   TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    assessment_type TEXT NOT NULL DEFAULT 'structural_watch',
    status          TEXT NOT NULL DEFAULT 'active',
    region_tags     TEXT NOT NULL DEFAULT '[]',
    domain_tags     TEXT NOT NULL DEFAULT '[]',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    last_regime     TEXT,
    last_confidence TEXT,
    alert_count     INTEGER NOT NULL DEFAULT 0,
    analyst_notes   TEXT
);
"""

_UPDATABLE_COLUMNS = frozenset(
    {
        "title",
        "assessment_type",
        "status",
        "region_tags",
        "domain_tags",
        "updated_at",
        "last_regime",
        "last_confidence",
        "alert_count",
        "analyst_notes",
    }
)

_SEED_ASSESSMENT = Assessment(
    assessment_id="ae-204",
    title="Black Sea Energy Corridor \u2013 Structural Watch",
    assessment_type=AssessmentType.structural_watch,
    status=AssessmentStatus.active,
    region_tags=["Eastern Europe", "Black Sea", "Middle East"],
    domain_tags=["energy", "military", "sanctions", "finance"],
    created_at=datetime(2026, 3, 1, 9, 0, 0, tzinfo=timezone.utc),
    updated_at=datetime(2026, 4, 9, 18, 0, 0, tzinfo=timezone.utc),
    last_regime="Nonlinear Escalation",
    last_confidence="High",
    alert_count=3,
    analyst_notes="Pipeline disruption risk elevated following recent naval incidents.",
)


def _row_to_assessment(row: sqlite3.Row) -> Assessment:
    """Deserialise a database row into an Assessment model."""
    return Assessment(
        assessment_id=row["assessment_id"],
        title=row["title"],
        assessment_type=AssessmentType(row["assessment_type"]),
        status=AssessmentStatus(row["status"]),
        region_tags=json.loads(row["region_tags"]),
        domain_tags=json.loads(row["domain_tags"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        last_regime=row["last_regime"],
        last_confidence=row["last_confidence"],
        alert_count=row["alert_count"] or 0,
        analyst_notes=row["analyst_notes"],
    )


class AssessmentStore:
    """SQLite-backed store for Assessment CRUD operations."""

    def __init__(self, db_path: Path = _DB_PATH) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        """Create the table and seed demo data on first run."""
        with self._connect() as conn:
            conn.execute(_DDL)
            conn.commit()
            cursor = conn.execute("SELECT COUNT(*) FROM assessments")
            count = cursor.fetchone()[0]
            if count == 0:
                self._seed(conn)

    def _seed(self, conn: sqlite3.Connection) -> None:
        """Insert the demo assessment so the dashboard has default data."""
        a = _SEED_ASSESSMENT
        conn.execute(
            """
            INSERT OR IGNORE INTO assessments
                (assessment_id, title, assessment_type, status, region_tags,
                 domain_tags, created_at, updated_at, last_regime,
                 last_confidence, alert_count, analyst_notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                a.assessment_id,
                a.title,
                a.assessment_type.value,
                a.status.value,
                json.dumps(list(a.region_tags)),
                json.dumps(list(a.domain_tags)),
                a.created_at.isoformat(),
                a.updated_at.isoformat(),
                a.last_regime,
                a.last_confidence,
                a.alert_count,
                a.analyst_notes,
            ),
        )
        conn.commit()
        logger.info("AssessmentStore: seeded demo assessment %s", a.assessment_id)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_assessments(self) -> list[Assessment]:
        """Return all assessments ordered by updated_at DESC."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM assessments ORDER BY updated_at DESC"
            ).fetchall()
        return [_row_to_assessment(r) for r in rows]

    def get_assessment(self, assessment_id: str) -> Optional[Assessment]:
        """Return a single assessment by ID, or None if not found."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM assessments WHERE assessment_id = ?",
                (assessment_id,),
            ).fetchone()
        if row is None:
            return None
        return _row_to_assessment(row)

    def create_assessment(self, data: AssessmentCreate) -> Assessment:
        """Create a new assessment and return it."""
        now = datetime.now(tz=timezone.utc)
        assessment_id = "ae-" + uuid.uuid4().hex[:8]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO assessments
                    (assessment_id, title, assessment_type, status, region_tags,
                     domain_tags, created_at, updated_at, last_regime,
                     last_confidence, alert_count, analyst_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assessment_id,
                    data.title,
                    data.assessment_type.value,
                    data.status.value,
                    json.dumps(list(data.region_tags)),
                    json.dumps(list(data.domain_tags)),
                    now.isoformat(),
                    now.isoformat(),
                    None,
                    None,
                    0,
                    data.analyst_notes,
                ),
            )
            conn.commit()
        result = self.get_assessment(assessment_id)
        assert result is not None  # just created
        return result

    def update_assessment(
        self, assessment_id: str, data: AssessmentUpdate
    ) -> Optional[Assessment]:
        """Apply partial updates to an assessment and return the updated record."""
        existing = self.get_assessment(assessment_id)
        if existing is None:
            return None

        now = datetime.now(tz=timezone.utc)
        updates: dict = {"updated_at": now.isoformat()}

        if data.title is not None:
            updates["title"] = data.title
        if data.status is not None:
            updates["status"] = data.status.value
        if data.region_tags is not None:
            updates["region_tags"] = json.dumps(list(data.region_tags))
        if data.domain_tags is not None:
            updates["domain_tags"] = json.dumps(list(data.domain_tags))
        if data.last_regime is not None:
            updates["last_regime"] = data.last_regime
        if data.last_confidence is not None:
            updates["last_confidence"] = data.last_confidence
        if data.alert_count is not None:
            updates["alert_count"] = data.alert_count
        if data.analyst_notes is not None:
            updates["analyst_notes"] = data.analyst_notes

        set_clause = ", ".join(
            f"{k} = ?" for k in updates if k in _UPDATABLE_COLUMNS
        )
        filtered_values = [v for k, v in updates.items() if k in _UPDATABLE_COLUMNS]
        values = filtered_values + [assessment_id]

        with self._connect() as conn:
            conn.execute(
                f"UPDATE assessments SET {set_clause} WHERE assessment_id = ?",  # noqa: S608
                values,
            )
            conn.commit()
        return self.get_assessment(assessment_id)

    def delete_assessment(self, assessment_id: str) -> bool:
        """Delete an assessment. Returns True if deleted, False if not found."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM assessments WHERE assessment_id = ?",
                (assessment_id,),
            )
            conn.commit()
        return cursor.rowcount > 0

    def upsert_assessment(self, assessment: Assessment) -> Assessment:
        """Insert or replace an assessment record (used by the auto-generation service)."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO assessments
                    (assessment_id, title, assessment_type, status, region_tags,
                     domain_tags, created_at, updated_at, last_regime,
                     last_confidence, alert_count, analyst_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assessment.assessment_id,
                    assessment.title,
                    assessment.assessment_type.value,
                    assessment.status.value,
                    json.dumps(list(assessment.region_tags)),
                    json.dumps(list(assessment.domain_tags)),
                    assessment.created_at.isoformat(),
                    assessment.updated_at.isoformat(),
                    assessment.last_regime,
                    assessment.last_confidence,
                    assessment.alert_count,
                    assessment.analyst_notes,
                ),
            )
            conn.commit()
        result = self.get_assessment(assessment.assessment_id)
        assert result is not None
        return result


# Module-level singleton – initialised on first import.
assessment_store = AssessmentStore()
