"""
claw_integration – Tool porting and query orchestration layer.

Provides:
  - models      : Frozen dataclasses for tools, commands, and usage tracking.
  - tools       : Tool registry loaded from a snapshot JSON; execute_tool().
  - commands    : Built-in command surface for knowledge-graph operations.
  - permissions : ToolPermissionContext for per-request access control.
  - port_manifest: Workspace manifest summarising all subsystems.
  - session_store: Persist and reload QueryEnginePort sessions to/from disk.
  - transcript  : In-memory transcript with flush/compact support.
  - task        : PortingTask state machine for tracking pipeline tasks.
  - query_engine: QueryEnginePort – session-aware multi-turn query engine.
"""

from __future__ import annotations

from .models import (
    PermissionDenial,
    PortingBacklog,
    PortingModule,
    Subsystem,
    UsageSummary,
)
from .task import PortingTask
from .permissions import ToolPermissionContext
from .commands import build_command_backlog, get_command
from .tools import (
    build_tool_backlog,
    execute_tool,
    find_tools,
    get_tool,
    get_tools,
    render_tool_index,
    tool_names,
    ToolExecution,
)
from .port_manifest import PortManifest, build_port_manifest
from .session_store import StoredSession, load_session, save_session
from .transcript import TranscriptStore
from .query_engine import QueryEngineConfig, QueryEnginePort, TurnResult

__all__ = [
    # models
    "PermissionDenial",
    "PortingBacklog",
    "PortingModule",
    "Subsystem",
    "UsageSummary",
    # task
    "PortingTask",
    # permissions
    "ToolPermissionContext",
    # commands
    "build_command_backlog",
    "get_command",
    # tools
    "build_tool_backlog",
    "execute_tool",
    "find_tools",
    "get_tool",
    "get_tools",
    "render_tool_index",
    "tool_names",
    "ToolExecution",
    # port_manifest
    "PortManifest",
    "build_port_manifest",
    # session_store
    "StoredSession",
    "load_session",
    "save_session",
    # transcript
    "TranscriptStore",
    # query_engine
    "QueryEngineConfig",
    "QueryEnginePort",
    "TurnResult",
]
