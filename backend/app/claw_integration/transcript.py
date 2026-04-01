"""In-memory transcript store with flush and compact support."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TranscriptStore:
    """Stores the chronological sequence of user messages for a session.

    Attributes:
        entries: Ordered list of message strings.
        flushed: Set to True after the transcript has been flushed to disk
                 (or otherwise marked as persisted).
    """

    entries: list[str] = field(default_factory=list)
    flushed: bool = False

    def append(self, message: str) -> None:
        """Add a message to the end of the transcript."""
        self.entries.append(message)

    def replay(self) -> tuple[str, ...]:
        """Return all current entries as an immutable tuple."""
        return tuple(self.entries)

    def flush(self) -> None:
        """Mark the transcript as flushed (persisted externally)."""
        self.flushed = True

    def compact(self, keep_last: int) -> None:
        """Trim the transcript to the *keep_last* most recent entries.

        If the transcript is already shorter than *keep_last*, it is left
        unchanged.
        """
        if len(self.entries) > keep_last:
            self.entries[:] = self.entries[-keep_last:]
