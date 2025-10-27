"""Filesystem monitoring."""

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

# ruff: noqa: TRY003


@dataclass
class MonitorChange:
    """A filesystem changes."""

    type: str
    path: Path

    @classmethod
    def from_line(cls, line: str) -> MonitorChange:
        """Create a MonitorChange from a single watchexec output line."""
        text = line.removesuffix("\n")
        if ":" not in text:
            raise ValueError(
                f"Expected colon-separated change, received: {text!r}"
            )
        parts = text.split(":", maxsplit=1)
        return cls(parts[0], Path(parts[1]))


@dataclass
class MonitorEvent:
    """A group of filesystem changes in a single event."""

    changes: Iterable[MonitorChange]

    @classmethod
    def from_lines(cls, lines: Iterable[str]) -> MonitorEvent:
        """Create MonitorEvent from a group of watchexec output lines."""
        return cls([MonitorChange.from_line(x) for x in lines])


class FilesystemMonitor:
    """Filesystem monitor using watchexec."""

    def __init__(self, path: Path, *, testing: bool = False) -> None:
        """Initialize and start the filesystem monitor subprocess."""
        cmd = [
            "watchexec",
            "--only-emit-events",
            "--emit-events-to=stdio",
            "--no-meta",
        ]
        if testing:
            cmd.append("--debounce=0")

        self._proc = subprocess.Popen(
            cmd,
            cwd=str(path),
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
        )
        assert self._proc.stdout is not None

    def sync(self) -> None:
        """Block until initial empty event from watchexec."""
        assert self._proc.stdout is not None
        line = self._proc.stdout.readline()
        if line != "\n":
            raise ValueError(f"Expected blank line, received: {line!r}")

    def iter_changes(self) -> Iterator[MonitorEvent]:
        """Iterate over filesystem change events."""
        assert self._proc.stdout is not None

        lines: list[str] = []
        while True:
            for line in self._proc.stdout:
                if line == "\n":  # Empty line, group separator
                    break
                lines.append(line)
            else:  # End of stream
                break
            yield MonitorEvent.from_lines(lines)
            lines = []
        if lines:
            yield MonitorEvent.from_lines(lines)

    def stop(self) -> None:
        """Send SIGTERM to the subprocess and wait for it to terminate."""
        self._proc.terminate()
        self._proc.wait()
