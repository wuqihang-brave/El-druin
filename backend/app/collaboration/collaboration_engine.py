"""Multi-user investigation workspace engine."""

from __future__ import annotations

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
class Note:
    """A note added to a workspace.

    Attributes:
        id: Note identifier.
        workspace_id: Parent workspace.
        user_id: Author user ID.
        content: Note text content.
        created_at: Creation timestamp.
    """

    id: str
    workspace_id: str
    user_id: str
    content: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class WorkspaceMember:
    """A member of a workspace.

    Attributes:
        user_id: Member user ID.
        role: Member role (owner | editor | viewer).
        added_at: When the member was added.
    """

    user_id: str
    role: str = "viewer"
    added_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class Workspace:
    """Investigation workspace shared between analysts.

    Attributes:
        id: Workspace identifier.
        name: Human-readable name.
        owner_id: Owner user ID.
        members: List of workspace members.
        event_ids: IDs of events pinned to this workspace.
        notes: Notes added to this workspace.
        metadata: Arbitrary extra data.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    id: str
    name: str
    owner_id: str
    members: list[WorkspaceMember] = field(default_factory=list)
    event_ids: list[str] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class CollaborationEngine:
    """Multi-user investigation workspace manager.

    Workspaces are stored in Redis for fast access and mirrored to
    PostgreSQL for persistence.

    Attributes:
        _REDIS_PREFIX: Redis key namespace for workspaces.
    """

    _REDIS_PREFIX = "workspace"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create_workspace(
        self, name: str, owner_id: str
    ) -> Workspace:
        """Create a new investigation workspace.

        Args:
            name: Human-readable workspace name.
            owner_id: Owning user's ID.

        Returns:
            Newly created :class:`Workspace`.
        """
        workspace = Workspace(
            id=str(uuid.uuid4()),
            name=name,
            owner_id=owner_id,
            members=[WorkspaceMember(user_id=owner_id, role="owner")],
        )
        await self._save(workspace)
        logger.info("Workspace %s created by %s", workspace.id, owner_id)
        return workspace

    async def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """Retrieve a workspace by ID.

        Args:
            workspace_id: Workspace identifier.

        Returns:
            :class:`Workspace` or *None* if not found.
        """
        return await self._load(workspace_id)

    async def list_workspaces(self, user_id: str) -> list[Workspace]:
        """List all workspaces where the user is a member.

        Args:
            user_id: User identifier.

        Returns:
            List of :class:`Workspace` instances.
        """
        workspaces: list[Workspace] = []
        try:
            from app.db.postgres import fetch_all
            import json as _json

            rows = await fetch_all(
                """
                SELECT id FROM workspaces
                WHERE owner_id = :uid
                   OR data::jsonb -> 'members' @> :member_filter
                ORDER BY updated_at DESC
                """,
                {
                    "uid": user_id,
                    "member_filter": _json.dumps([{"user_id": user_id}]),
                },
            )
            for row in rows:
                ws = await self._load(row["id"])
                if ws:
                    workspaces.append(ws)
        except Exception as exc:
            logger.warning("list_workspaces DB query failed: %s", exc)
            # Fallback: return from Redis scan (best effort)
        return workspaces

    # ------------------------------------------------------------------
    # Membership
    # ------------------------------------------------------------------

    async def add_member(
        self, workspace_id: str, user_id: str, role: str = "viewer"
    ) -> bool:
        """Add a user as a member of the workspace.

        Args:
            workspace_id: Target workspace ID.
            user_id: User to add.
            role: Role to assign (owner | editor | viewer).

        Returns:
            True if added successfully, False otherwise.
        """
        workspace = await self._load(workspace_id)
        if workspace is None:
            return False
        existing = {m.user_id for m in workspace.members}
        if user_id not in existing:
            workspace.members.append(
                WorkspaceMember(user_id=user_id, role=role)
            )
            workspace.updated_at = datetime.now(UTC)
            await self._save(workspace)
        return True

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    async def add_event_to_workspace(
        self, workspace_id: str, event_id: str, added_by: str
    ) -> bool:
        """Pin an event to a workspace.

        Args:
            workspace_id: Target workspace ID.
            event_id: Event ID to pin.
            added_by: User ID performing the action.

        Returns:
            True if added, False if workspace not found.
        """
        workspace = await self._load(workspace_id)
        if workspace is None:
            return False
        if event_id not in workspace.event_ids:
            workspace.event_ids.append(event_id)
            workspace.updated_at = datetime.now(UTC)
            await self._save(workspace)
        return True

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------

    async def add_note(
        self, workspace_id: str, user_id: str, content: str
    ) -> Note:
        """Add a text note to a workspace.

        Args:
            workspace_id: Target workspace ID.
            user_id: Authoring user ID.
            content: Note text.

        Returns:
            Newly created :class:`Note`.
        """
        workspace = await self._load(workspace_id)
        note = Note(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            user_id=user_id,
            content=content,
        )
        if workspace is not None:
            workspace.notes.append(note)
            workspace.updated_at = datetime.now(UTC)
            await self._save(workspace)
        return note

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    async def _save(self, workspace: Workspace) -> None:
        """Persist a workspace to Redis and PostgreSQL.

        Args:
            workspace: Workspace to save.
        """
        import dataclasses, json

        def _serialise(obj: Any) -> Any:
            if dataclasses.is_dataclass(obj):
                return dataclasses.asdict(obj)
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Not serializable: {type(obj)}")

        data = json.dumps(dataclasses.asdict(workspace), default=_serialise)

        try:
            from app.db.redis_client import redis_client

            await redis_client.set(
                f"{self._REDIS_PREFIX}:{workspace.id}",
                data,
                ttl=86400,
            )
        except Exception as exc:
            logger.warning("Redis workspace save failed: %s", exc)

        try:
            from app.db.postgres import execute

            await execute(
                """
                INSERT INTO workspaces (id, name, owner_id, data, created_at, updated_at)
                VALUES (:id, :name, :owner_id, :data, :created_at, :updated_at)
                ON CONFLICT (id) DO UPDATE
                    SET name       = EXCLUDED.name,
                        data       = EXCLUDED.data,
                        updated_at = EXCLUDED.updated_at
                """,
                {
                    "id": workspace.id,
                    "name": workspace.name,
                    "owner_id": workspace.owner_id,
                    "data": data,
                    "created_at": workspace.created_at,
                    "updated_at": workspace.updated_at,
                },
            )
        except Exception as exc:
            logger.warning("PostgreSQL workspace save failed: %s", exc)

    async def _load(self, workspace_id: str) -> Optional[Workspace]:
        """Load a workspace from Redis (with PostgreSQL fallback).

        Args:
            workspace_id: Workspace identifier.

        Returns:
            :class:`Workspace` or *None*.
        """
        import json, dataclasses

        raw: Optional[str] = None

        # Redis first
        try:
            from app.db.redis_client import redis_client

            raw = await redis_client.get(
                f"{self._REDIS_PREFIX}:{workspace_id}"
            )
        except Exception:
            pass

        # PostgreSQL fallback
        if raw is None:
            try:
                from app.db.postgres import fetch_one

                row = await fetch_one(
                    "SELECT data FROM workspaces WHERE id = :id",
                    {"id": workspace_id},
                )
                if row:
                    raw = row["data"]
            except Exception:
                pass

        if raw is None:
            return None

        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
            members = [
                WorkspaceMember(**m) for m in data.pop("members", [])
            ]
            notes = [Note(**n) for n in data.pop("notes", [])]
            ws = Workspace(**data, members=members, notes=notes)
            return ws
        except Exception as exc:
            logger.warning("Workspace deserialise failed: %s", exc)
            return None


# Module-level singleton
collaboration_engine = CollaborationEngine()
