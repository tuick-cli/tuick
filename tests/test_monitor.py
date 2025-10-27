r"""Tests for filesystem monitoring."""

import contextlib
import http.server
import socketserver
import tempfile
import threading
from pathlib import Path
from queue import Queue
from typing import TYPE_CHECKING, Any

import pytest

from tuick.monitor import FilesystemMonitor, MonitorEvent, MonitorThread

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def event_queue(
    request: pytest.FixtureRequest, tmp_path: Path
) -> Iterator[Queue[MonitorEvent]]:
    """Start filesystem monitor and return synchronized event queue."""
    initial_files = getattr(request, "param", {})
    for filename, content in initial_files.items():
        (tmp_path / filename).write_text(content)

    monitor = FilesystemMonitor(tmp_path, testing=True)
    monitor.sync()

    queue: Queue[MonitorEvent] = Queue()

    def consume_events() -> None:
        for event in monitor.iter_changes():
            queue.put(event)

    thread = threading.Thread(target=consume_events, daemon=True)
    thread.start()

    yield queue

    monitor.stop()


@pytest.fixture
def http_socket() -> Iterator[tuple[Path, Queue[str]]]:
    """HTTP server on Unix socket, returns socket path and request queue."""
    request_queue: Queue[str] = Queue()

    class TestHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode()
            request_queue.put(body)
            self.send_response(200)
            self.end_headers()

        def log_message(
            self,
            format: str,  # noqa: A002
            *args: Any,  # noqa: ANN401
        ) -> None:
            pass

    with contextlib.ExitStack() as stack:
        tmpdir = stack.enter_context(tempfile.TemporaryDirectory())
        socket_path = Path(tmpdir) / "fzf.sock"
        server = socketserver.UnixStreamServer(str(socket_path), TestHandler)
        stack.enter_context(server)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        stack.callback(server.shutdown)
        yield socket_path, request_queue


def test_monitor_without_gitignore_detects_all_files(
    tmp_path: Path, event_queue: Queue[MonitorEvent]
) -> None:
    """Detects both files when no gitignore present."""
    (tmp_path / "test.log").touch()
    (tmp_path / "test.txt").touch()

    event1 = event_queue.get(timeout=1)
    event2 = event_queue.get(timeout=1)

    all_paths = [change.path.name for change in event1.changes] + [
        change.path.name for change in event2.changes
    ]
    assert sorted(all_paths) == ["test.log", "test.txt"]


@pytest.mark.parametrize(
    "event_queue", [{".gitignore": "*.log\n"}], indirect=True
)
def test_monitor_with_gitignore_filters_ignored_files(
    tmp_path: Path, event_queue: Queue[MonitorEvent]
) -> None:
    """Detects only non-ignored file when gitignore present."""
    (tmp_path / "test.log").touch()
    (tmp_path / "test.txt").touch()

    event = event_queue.get(timeout=1)
    paths = [change.path.name for change in event.changes]
    assert paths == ["test.txt"]


def test_monitor_thread_sends_reload_to_socket(
    tmp_path: Path, http_socket: tuple[Path, Queue[str]]
) -> None:
    """MonitorThread sends POST reload(command) to socket on file change."""
    socket_path, request_queue = http_socket
    reload_cmd = "ruff check src/"

    monitor_thread = MonitorThread(
        socket_path, reload_cmd, path=tmp_path, testing=True
    )
    monitor_thread.start()

    try:
        (tmp_path / "test.py").touch()

        body = request_queue.get(timeout=1)
        assert body == f"reload('{reload_cmd}')"
    finally:
        monitor_thread.stop()
