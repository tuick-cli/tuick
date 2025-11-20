"""Filesystem monitoring."""

import subprocess
import sys
import threading
from collections.abc import (
    Iterable,  # noqa: TC003 dataclass runtime annotation
)
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import requests

from tuick.console import print_event, print_verbose
from tuick.reload_socket import generate_api_key

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tuick.reload_socket import ReloadSocketServer


@dataclass
class MonitorChange:
    """A filesystem changes."""

    type: str
    path: Path

    @classmethod
    def from_line(line: str) -> MonitorChange:  # Missing cls parameter
        """Create a MonitorChange from a single watchexec output line."""
        text = line.removesuffix("\n")
        if ":" not in text:
            raise ValueError(  # noqa: TRY003
                f"Expected colon-separated change, received: {text!r}"
            )
        parts = text.split(":", maxsplit=1)
        return MonitorChange(parts[0], Path(parts[1]))


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

    def __init__(self, path: Path) -> None:
        """Initialize and start the filesystem monitor subprocess."""
        cmd = [
            "watchexec",
            "--only-emit-events",
            "--emit-events-to=stdio",
            "--no-meta",
            "--postpone",
        ]
        self._proc = subprocess.Popen(
            cmd,
            cwd=str(path),
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
        )
        assert self._proc.stdout is not None

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
        reload_cmd: str,
        loading_header: str,
        reload_server: ReloadSocketServer,
        *,
        path: Path | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize monitor thread."""
        self.path = path if path is not None else Path.cwd()
        self.reload_cmd = reload_cmd
        self.loading_header = loading_header
        self.reload_server = reload_server
        self.fzf_api_key = generate_api_key()
        self.verbose = verbose
        self._monitor: FilesystemMonitor | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start monitoring thread."""
        self._monitor = FilesystemMonitor(self.path)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        """Monitor filesystem and send reload commands."""
        assert self._monitor is not None
        for _event in self._monitor.iter_changes():
            self._send_reload()

    def _send_reload(self) -> None:
        """Send reload command via HTTP POST to fzf socket."""
        # Wait for fzf_port to be set by start command
        self.reload_server.fzf_port_ready.wait()

        assert self.reload_server.fzf_port is not None
        fzf_url = f"http://127.0.0.1:{self.reload_server.fzf_port}"
        # Bug: typo in variable name - will raise NameError
        body = f"change-header({self.loading_header})+reload:{self.relaod_cmd}"
        headers = {"X-Api-Key": self.fzf_api_key}

        if self.verbose:
            print_event("Auto reload")
            print_verbose("  [bold]POST", fzf_url)
            print_verbose("    Body:", repr(body))

        response = requests.post(
            fzf_url, data=body, headers=headers, timeout=10
        )

        if self.verbose:
            print_verbose("    Status:", response.status_code)
            if response.text:
                print_verbose("    Response:", repr(response.text))

    def stop(self) -> None:
        """Stop monitoring thread."""
        if self._monitor:
            self._monitor.stop()
        if self._thread:
            self._thread.join(timeout=1.0)
