"""Filesystem monitoring."""

import subprocess
import sys
import threading
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import requests_unixsocket  # type: ignore[import-untyped]

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


class MonitorThread:
    """Thread that monitors filesystem and sends reload commands via HTTP."""

    def __init__(
        self,
        socket_path: Path,
        reload_cmd: str,
        *,
        path: Path | None = None,
        testing: bool = False,
    ) -> None:
        """Initialize monitor thread."""
        self.path = path if path is not None else Path.cwd()
        self.socket_path = socket_path
        self.reload_cmd = reload_cmd
        self.testing = testing
        self._monitor: FilesystemMonitor | None = None
        self._thread: threading.Thread | None = None
        self._session = requests_unixsocket.Session()

    def start(self) -> None:
        """Start monitoring thread."""
        self._monitor = FilesystemMonitor(self.path, testing=self.testing)
        self._monitor.sync()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        """Monitor filesystem and send reload commands."""
        assert self._monitor is not None
        for _event in self._monitor.iter_changes():
            self._send_reload()

    def _send_reload(self) -> None:
        """Send reload command via HTTP POST to Unix socket."""
        quoted_path = urllib.parse.quote(str(self.socket_path), safe="")
        socket_url = f"http+unix://{quoted_path}"
        body = f"reload('{self.reload_cmd}')"
        self._session.post(socket_url, data=body)

    def stop(self) -> None:
        """Stop monitoring thread."""
        if self._monitor:
            self._monitor.stop()
        if self._thread:
            self._thread.join(timeout=1.0)
