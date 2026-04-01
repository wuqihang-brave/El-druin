"""Permission context for tool access control."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToolPermissionContext:
    """Tracks which tools are blocked for a given request or session."""

    blocked_tools: set[str] = field(default_factory=set)

    def blocks(self, tool_name: str) -> bool:
        """Return True if *tool_name* is blocked in this context."""
        return tool_name in self.blocked_tools

    def block(self, tool_name: str) -> None:
        """Add *tool_name* to the blocked set."""
        self.blocked_tools.add(tool_name)

    def unblock(self, tool_name: str) -> None:
        """Remove *tool_name* from the blocked set (no-op if absent)."""
        self.blocked_tools.discard(tool_name)

    @classmethod
    def allow_all(cls) -> "ToolPermissionContext":
        """Return a context that blocks nothing."""
        return cls()

    @classmethod
    def deny(cls, *tool_names: str) -> "ToolPermissionContext":
        """Return a context that blocks the given tool names."""
        return cls(blocked_tools=set(tool_names))
