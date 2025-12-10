"""Tests for console logging behavior."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

from tuick import console

if TYPE_CHECKING:
    import pytest


def test_setup_log_file_nested_does_not_dump_to_stderr(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Nested tuick should append to log file without printing to stderr."""
    log_path = tmp_path / "tuick.log"
    original_file = console._console.file

    try:
        console._console.file = sys.stderr
        with (
            patch.dict(os.environ, {console.TUICK_LOG_FILE: str(log_path)}),
            console.setup_log_file(),
        ):
            console._console.print("hello")
    finally:
        console._console.file = original_file

    captured = capsys.readouterr()
    assert captured.err == ""
    assert "hello" in log_path.read_text()


def test_setup_log_file_top_replays_log_to_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Top-level tuick copies log contents to stderr on exit."""
    original_file = console._console.file
    try:
        console._console.file = sys.stderr
        with console.setup_log_file():
            log_path = Path(os.environ[console.TUICK_LOG_FILE])
            log_path.write_text("child output\n")
            console.set_verbose()
            console.print_verbose("top output")
    finally:
        console._console.file = original_file

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "child output" in captured.err
    assert "top output" in captured.err
