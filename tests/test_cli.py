"""Tests for the CLI module."""

import os
import subprocess
from io import StringIO
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console
from typer.testing import CliRunner

from tuick.cli import app

runner = CliRunner()


@pytest.fixture
def console_out():
    """Patch console with test console using StringIO (no colors)."""
    output = StringIO()
    test_console = Console(file=output, force_terminal=False)
    with patch("tuick.cli.console", test_console):
        yield output


def track(seq: list[str], action: str, ret: Any = None):  # noqa: ANN401
    """Append action to sequence, return value."""
    return lambda *a: (seq.append(action), ret)[1]  # type: ignore[func-returns-value]


def test_cli_default_launches_fzf() -> None:
    """Default command streams data incrementally to fzf stdin."""
    sequence: list[str] = []

    def cmd_stdout():
        for line in ["test.py:1: error\n", "test.py:2: warning\n"]:
            sequence.append(f"read:{line.strip()}")
            yield line
        sequence.append("stopiteration")

    cmd_proc = MagicMock(returncode=0, stdout=cmd_stdout())  # type: ignore[no-untyped-call]
    cmd_proc.__enter__.side_effect = track(
        sequence, "command:enter", ret=cmd_proc
    )
    cmd_proc.__exit__.side_effect = track(sequence, "command:exit", ret=False)

    fzf_proc = MagicMock(returncode=0)
    fzf_proc.__enter__.side_effect = track(sequence, "fzf:enter", ret=fzf_proc)
    fzf_proc.__exit__.side_effect = track(sequence, "fzf:exit", ret=False)
    fzf_proc.stdin.write.side_effect = lambda d: (
        sequence.append(f"write:{d!r}"),  # type: ignore[func-returns-value]
        None,
    )[1]
    fzf_proc.stdin.close.side_effect = track(sequence, "close")

    with (
        patch(
            "tuick.cli.subprocess.Popen",
            autospec=True,
            side_effect=[cmd_proc, fzf_proc],
        ) as popen_mock,
        patch("tuick.cli.MonitorThread"),
    ):
        runner.invoke(app, ["--", "ruff", "check", "src/"])

    assert popen_mock.call_args_list[0].args[0] == ["ruff", "check", "src/"]
    assert popen_mock.call_args_list[0].kwargs["stdout"] == subprocess.PIPE
    assert popen_mock.call_args_list[1].args[0][0] == "fzf"
    assert popen_mock.call_args_list[1].kwargs["stdin"] == subprocess.PIPE

    assert sequence == [
        "command:enter",
        "read:test.py:1: error",
        "fzf:enter",
        "write:'test.py:1: error'",
        "read:test.py:2: warning",
        "write:'\\x00'",
        "write:'test.py:2: warning'",
        "stopiteration",
        "close",
        "fzf:exit",
        "command:exit",
    ]


def test_cli_no_output_no_fzf() -> None:
    """When command produces no output, fzf is not started."""
    sequence: list[str] = []

    cmd_proc = MagicMock(returncode=0, stdout=iter([]))
    cmd_proc.__enter__.side_effect = track(
        sequence, "command:enter", ret=cmd_proc
    )
    cmd_proc.__exit__.side_effect = track(sequence, "command:exit", ret=False)

    with (
        patch(
            "tuick.cli.subprocess.Popen",
            autospec=True,
            side_effect=[cmd_proc],
        ) as popen_mock,
        patch("tuick.cli.MonitorThread"),
    ):
        runner.invoke(app, ["--", "ruff", "check", "src/"])

    assert popen_mock.call_count == 1
    assert sequence == ["command:enter", "command:exit"]


def test_cli_reload_option() -> None:
    """--reload option runs command with FORCE_COLOR=1."""
    captured_env: dict[str, str] = {}

    def mock_popen(*args: Any, **kwargs: Any) -> MagicMock:  # noqa: ANN401
        captured_env.update(kwargs.get("env", {}))
        mock_process = MagicMock()
        mock_process.stdout = iter(["src/test.py:1: error: Test\n"])
        mock_process.__enter__ = MagicMock(return_value=mock_process)
        mock_process.__exit__ = MagicMock(return_value=False)
        return mock_process

    with patch("tuick.cli.subprocess.Popen", side_effect=mock_popen):
        result = runner.invoke(app, ["--reload", "--", "mypy", "src/"])
        assert captured_env["FORCE_COLOR"] == "1"
        assert result.stdout == "src/test.py:1: error: Test"


def test_cli_select_option(console_out: StringIO) -> None:
    """--select option opens editor at location and prints command."""
    with (
        patch("tuick.cli.subprocess.run") as mock_run,
        patch("tuick.cli.get_editor_from_env", return_value="vi"),
    ):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = runner.invoke(
            app, ["--verbose", "--select", "src/test.py:10:5: error: Test"]
        )
        assert result.exit_code == 0
        assert console_out.getvalue() == "vi +10 '+normal! 5l' src/test.py\n"
        assert mock_run.call_args[0] == (
            ["vi", "+10", "+normal! 5l", "src/test.py"],
        )


def test_cli_select_no_location_found(console_out: StringIO) -> None:
    """--select with no location prints message and exits 0 (no-op)."""
    with patch("tuick.cli.subprocess.run") as mock_run:
        result = runner.invoke(
            app, ["--select", "plain text without location"]
        )
        assert result.exit_code == 0
        assert console_out.getvalue() == "No location found\n"
        # Verify editor was not called
        mock_run.assert_not_called()


def test_cli_select_verbose_no_location(console_out: StringIO) -> None:
    """--select --verbose with no location prints repr of input."""
    with patch("tuick.cli.subprocess.run") as mock_run:
        result = runner.invoke(app, ["--select", "plain text", "--verbose"])
        assert result.exit_code == 0
        assert console_out.getvalue() == "No location found\n'plain text'\n"
        # Verify editor was not called
        mock_run.assert_not_called()


def test_cli_exclusive_options() -> None:
    """--reload and --select are mutually exclusive."""
    result = runner.invoke(
        app, ["--reload", "--select", "foo", "--", "mypy", "src/"]
    )
    assert result.exit_code != 0
