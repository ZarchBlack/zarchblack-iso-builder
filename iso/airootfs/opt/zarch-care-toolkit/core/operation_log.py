"""
core/operation_log.py
=====================
In-memory session operation log.

Tracks what the user has done during this session (scans, cleanups, updates …)
with timestamps and outcomes.  The log is NOT persisted between sessions —
it resets on each application launch.

Usage:
    from core.operation_log import op_log

    op_log.record("Cache cleaned", success=True, detail="paccache -rk1")
    entries = op_log.entries          # list of OperationEntry
    text    = op_log.as_text()        # human-readable multiline string
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class OperationEntry:
    timestamp:  datetime.datetime
    action:     str
    success:    bool
    detail:     str = ""

    @property
    def icon(self) -> str:
        return "✅" if self.success else "❌"

    def __str__(self) -> str:
        ts = self.timestamp.strftime("%H:%M:%S")
        detail = f"  ↳ {self.detail}" if self.detail else ""
        return f"[{ts}] {self.icon} {self.action}{detail}"


class OperationLog:
    """Thread-safe (append-only) in-memory session log."""

    def __init__(self, max_entries: int = 500) -> None:
        self._entries: list[OperationEntry] = []
        self._max_entries = max_entries

    @property
    def entries(self) -> list[OperationEntry]:
        return list(self._entries)

    def record(
        self,
        action: str,
        *,
        success: bool = True,
        detail: str = "",
    ) -> None:
        """Add a new entry to the log."""
        entry = OperationEntry(
            timestamp=datetime.datetime.now(),
            action=action,
            success=success,
            detail=detail,
        )
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]
        log_fn = logger.info if success else logger.warning
        log_fn("op_log: %s", entry)

    def clear(self) -> None:
        """Clear all entries."""
        self._entries.clear()
        logger.debug("OperationLog cleared")

    def as_text(self) -> str:
        """Return all entries as a human-readable multiline string."""
        if not self._entries:
            return "No operations recorded in this session."
        return "\n".join(str(e) for e in self._entries)

    def as_text_reversed(self) -> str:
        """Return entries newest-first."""
        if not self._entries:
            return "No operations recorded in this session."
        return "\n".join(str(e) for e in reversed(self._entries))

    def export(self) -> str:
        """Return a full export string with header."""
        header = (
            f"ZarchCare Session Log — {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            + "=" * 60 + "\n"
        )
        return header + self.as_text()

    @property
    def count(self) -> int:
        return len(self._entries)

    @property
    def success_count(self) -> int:
        return sum(1 for e in self._entries if e.success)

    @property
    def failure_count(self) -> int:
        return sum(1 for e in self._entries if not e.success)


# Module-level singleton — import and use directly
op_log = OperationLog()
