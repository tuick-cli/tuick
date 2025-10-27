r"""Tests for filesystem monitoring."""

import threading
from queue import Queue
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

from tuick.monitor import FilesystemMonitor, MonitorEvent


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
