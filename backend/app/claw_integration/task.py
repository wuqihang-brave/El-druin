"""Task state machine for tracking pipeline operations."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import PortingModule


@dataclass
class PortingTask:
    """Tracks the lifecycle of a single pipeline task.

    States: ``pending`` → ``in_progress`` → ``completed`` | ``failed``

    Attributes:
        name:        Short identifier for the task.
        description: Human-readable explanation of what the task does.
        status:      Current lifecycle state (default: ``'pending'``).
        modules:     Optional list of :class:`PortingModule` objects involved.
    """

    name: str
    description: str
    status: str = "pending"
    modules: list[PortingModule] = field(default_factory=list)

    def start(self) -> None:
        """Transition the task to the *in_progress* state."""
        self.status = "in_progress"

    def complete(self) -> None:
        """Transition the task to the *completed* state."""
        self.status = "completed"

    def fail(self, reason: str = "") -> None:
        """Transition the task to a *failed* state.

        Args:
            reason: Optional description of why the task failed.
        """
        self.status = f"failed: {reason}" if reason else "failed"

    @property
    def is_done(self) -> bool:
        """Return True when the task has reached a terminal state."""
        return self.status in ("completed",) or self.status.startswith("failed")

    def __str__(self) -> str:
        return f"PortingTask({self.name!r}, status={self.status!r})"


__all__ = ["PortingTask"]
