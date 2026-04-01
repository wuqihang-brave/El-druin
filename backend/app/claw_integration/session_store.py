"""Persist and restore QueryEnginePort sessions to/from disk."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

# Allow overriding the sessions directory via the environment.
# Defaults to ``<package>/sessions/`` when unset.
_DEFAULT_SESSIONS_DIR = Path(__file__).resolve().parent / "sessions"
_SESSIONS_DIR = Path(os.environ.get("CLAW_SESSIONS_DIR", str(_DEFAULT_SESSIONS_DIR)))


@dataclass(frozen=True)
class StoredSession:
    """Serialisable snapshot of a query-engine session."""

    session_id: str
    messages: tuple[str, ...]
    input_tokens: int
    output_tokens: int


def save_session(session: StoredSession) -> Path:
    """Persist *session* to ``<package>/sessions/<session_id>.json``.

    The sessions directory is created automatically if it does not exist.

    Returns:
        Path to the written JSON file.
    """
    _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = _SESSIONS_DIR / f"{session.session_id}.json"
    payload = {
        "session_id": session.session_id,
        "messages": list(session.messages),
        "input_tokens": session.input_tokens,
        "output_tokens": session.output_tokens,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_session(session_id: str) -> StoredSession:
    """Load and deserialise a previously saved session.

    Args:
        session_id: UUID hex string used as the file name.

    Raises:
        FileNotFoundError: If no session with *session_id* has been saved.

    Returns:
        The reconstructed :class:`StoredSession`.
    """
    path = _SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Session {session_id!r} not found at {path}. "
            "Use QueryEnginePort.from_workspace() to start a new session."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return StoredSession(
        session_id=data["session_id"],
        messages=tuple(data.get("messages", [])),
        input_tokens=data.get("input_tokens", 0),
        output_tokens=data.get("output_tokens", 0),
    )
