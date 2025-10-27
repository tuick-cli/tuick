"""Tests for the CLI module."""

from subprocess import CompletedProcess
from typing import Any
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from tuick.cli import app

runner = CliRunner()


def test_cli_default_launches_fzf() -> None:
    """Default command launches fzf with --listen socket argument."""
    captured_env: dict[str, str] = {}
    captured_args: list[Any] = []

    def capture_call(*args: Any, **kwargs: Any) -> CompletedProcess[str]:  # noqa: ANN401
        captured_env.update(kwargs.get("env", {}))
        captured_args.extend(args)
        return CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    with (
        patch("tuick.cli.subprocess.run", side_effect=capture_call),
        patch("tuick.cli.sys.argv", ["tuick", "ruff"]),
        patch("tuick.cli.MonitorThread"),
    ):
        runner.invoke(app, ["--", "ruff", "check", "src/"])
        assert "FZF_DEFAULT_COMMAND" in captured_env
        assert (
            "tuick --reload -- ruff check src/"
            in captured_env["FZF_DEFAULT_COMMAND"]
        )
        fzf_args = captured_args[0]
        listen_arg = [arg for arg in fzf_args if arg.startswith("--listen=")]
        assert len(listen_arg) == 1
        socket_path = listen_arg[0].removeprefix("--listen=")
        assert socket_path.endswith(".sock")


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


def test_cli_select_option() -> None:
    """--select option opens editor at location and prints command."""
    with (
        patch("tuick.cli.subprocess.run") as mock_run,
        patch("tuick.cli.get_editor_from_env", return_value="vi"),
    ):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = runner.invoke(
            app, ["--select", "src/test.py:10:5: error: Test"]
        )
        assert result.exit_code == 0
        assert result.stdout == "vi +10 '+normal! 5l' src/test.py\n"
        assert mock_run.call_args[0] == (
            ["vi", "+10", "+normal! 5l", "src/test.py"],
        )


def test_cli_select_no_location_found() -> None:
    """--select with no location prints message and exits 0 (no-op)."""
    with patch("tuick.cli.subprocess.run") as mock_run:
        result = runner.invoke(
            app, ["--select", "plain text without location"]
        )
        assert result.exit_code == 0
        assert result.stdout == "No location found\n"
        # Verify editor was not called
        mock_run.assert_not_called()


def test_cli_select_verbose_no_location() -> None:
    """--select --verbose with no location prints repr of input."""
    with patch("tuick.cli.subprocess.run") as mock_run:
        result = runner.invoke(app, ["--select", "plain text", "--verbose"])
        assert result.exit_code == 0
        assert result.stdout == "No location found\n'plain text'\n"
        # Verify editor was not called
        mock_run.assert_not_called()


def test_cli_exclusive_options() -> None:
    """--reload and --select are mutually exclusive."""
    result = runner.invoke(
        app, ["--reload", "--select", "foo", "--", "mypy", "src/"]
    )
    assert result.exit_code != 0
