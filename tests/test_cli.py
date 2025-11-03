"""Tests for the CLI module."""

import io
import socket
import subprocess
from io import StringIO
from textwrap import dedent
from typing import TYPE_CHECKING, Any
from unittest.mock import ANY, Mock, create_autospec, patch

if TYPE_CHECKING:
    from collections.abc import Iterator

from typer.testing import CliRunner

from tuick.cli import app
from tuick.reload_socket import ReloadSocketServer

runner = CliRunner()


def track(seq: list[str], action: str, ret: Any = None):  # noqa: ANN401
    """Append action to sequence, return value."""
    return lambda *a: (seq.append(action), ret)[1]  # type: ignore[func-returns-value]


def test_cli_default_launches_fzf() -> None:
    """Default command streams data incrementally to fzf stdin."""
    sequence: list[str] = []

    def cmd_stdout() -> Iterator[str]:
        for line in ["test.py:1: error\n", "test.py:2: warning\n"]:
            sequence.append(f"read:{line.strip()}")
            yield line
        sequence.append("stopiteration")

    cmd_proc = create_autospec(subprocess.Popen, instance=True)
    cmd_proc.returncode = 0
    cmd_proc.stdout = cmd_stdout()
    cmd_proc.__enter__.side_effect = track(
        sequence, "command:enter", ret=cmd_proc
    )
    cmd_proc.__exit__.side_effect = track(sequence, "command:exit", ret=False)

    fzf_proc = create_autospec(subprocess.Popen, instance=True)
    fzf_proc.returncode = 0
    fzf_proc.stdin = create_autospec(io.TextIOWrapper, instance=True)
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

    cmd_proc = create_autospec(subprocess.Popen, instance=True)
    cmd_proc.returncode = 0
    cmd_proc.stdout = iter([])
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
    """--reload waits for go response before starting command subprocess."""
    sequence: list[str] = []

    # Create reload server with mock cmd_proc
    server = ReloadSocketServer()
    api_key = server.get_server_info().api_key
    mock_cmd_proc = Mock(spec=subprocess.Popen)
    mock_cmd_proc.poll.return_value = None  # Still running
    mock_cmd_proc.terminate.side_effect = track(sequence, "terminate")
    mock_cmd_proc.wait.side_effect = track(sequence, "wait")
    server.cmd_proc = mock_cmd_proc
    server.start()
    port = server.server_address[1]

    mock_process = create_autospec(subprocess.Popen, instance=True)
    mock_process.stdout = iter(["src/test.py:1: error: Test\n"])
    mock_process.__enter__.side_effect = track(
        sequence, "popen", ret=mock_process
    )
    mock_process.__exit__.side_effect = track(sequence, "exit", ret=False)

    try:
        env = {"TUICK_PORT": str(port), "TUICK_API_KEY": api_key}

        with (
            patch("tuick.cli.subprocess.Popen", return_value=mock_process),
            patch.dict("os.environ", env),
        ):
            result = runner.invoke(app, ["--reload", "--", "mypy", "src/"])
            assert result.stdout == "src/test.py:1: error: Test"

        # Verify sequence: terminate → wait → popen
        assert sequence == ["terminate", "wait", "popen", "exit"]
    finally:
        # Shutdown server
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect(("127.0.0.1", port))
            sock.sendall(f"secret: {api_key}\nshutdown\n".encode())


def test_cli_select_plain(console_out: StringIO) -> None:
    """--select option opens editor at location and prints nothing."""
    with (
        patch("tuick.cli.subprocess.run") as mock_run,
        patch("tuick.cli.get_editor_from_env", return_value="vi"),
    ):
        mock_run.return_value = create_autospec(
            subprocess.CompletedProcess,
            instance=True,
        )
        mock_run.return_value.returncode = 0
        args = app, ["--select", "src/test.py:10:5: error: Test"]
        result = runner.invoke(*args)
        assert result.exit_code == 0
        assert console_out.getvalue() == ""
        command = ["vi", "+10", "+normal! 5l", "src/test.py"]
        mock_run.assert_called_once_with(command, check=True)


def test_cli_select_verbose(console_out: StringIO) -> None:
    """--verbose --select prints the command to execute."""
    with (
        patch("tuick.cli.subprocess.run") as mock_run,
        patch("tuick.cli.get_editor_from_env", return_value="vi"),
        patch("sys.argv", ["tuick", "(mock argv)"]),
    ):
        mock_run.return_value = create_autospec(
            subprocess.CompletedProcess, instance=True
        )
        mock_run.return_value.returncode = 0
        args = app, ["--verbose", "--select", "src/test.py:10:5: error: Test"]
        result = runner.invoke(*args)
        assert result.exit_code == 0
        assert console_out.getvalue() == (
            "> tuick '(mock argv)'\n$ vi +10 '+normal! 5l' src/test.py\n"
        )
        mock_run.assert_called_once()


def test_cli_select_error(console_out: StringIO) -> None:
    """--select prints a message if the editor exits with error."""
    with (
        patch("tuick.cli.subprocess.run") as mock_run,
        patch("tuick.cli.get_editor_from_env", return_value="vi"),
    ):
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd="whatever"
        )
        mock_run.return_value = create_autospec(
            subprocess.CompletedProcess, instance=True
        )
        mock_run.return_value.returncode = 1
        args = app, ["--select", "src/test.py:10:5: error: Test"]
        result = runner.invoke(*args)
        assert result.exit_code == 1
        mock_run.assert_called_once_with(ANY, check=True)
        assert console_out.getvalue() == "Error: Editor exit status: 1\n"


def test_cli_select_no_location_found(console_out: StringIO) -> None:
    """--select with no location does nothing."""
    with patch("tuick.cli.subprocess.run") as mock_run:
        result = runner.invoke(
            app, ["--select", "plain text without location"]
        )
        assert result.exit_code == 0
        assert console_out.getvalue() == ""
        # Verify editor was not called
        mock_run.assert_not_called()


def test_cli_select_verbose_no_location(console_out: StringIO) -> None:
    """--verbose --select with no location prints a message with input."""
    with (
        patch("tuick.cli.subprocess.run") as mock_run,
        patch("sys.argv", ["tuick", "(mock argv)"]),
    ):
        result = runner.invoke(app, ["--select", "plain text", "--verbose"])
        assert result.exit_code == 0
        assert console_out.getvalue() == dedent("""\
            > tuick '(mock argv)'
            No location found: 'plain text'
        """)
        # Verify editor was not called
        mock_run.assert_not_called()


def test_cli_exclusive_options() -> None:
    """--reload and --select are mutually exclusive."""
    result = runner.invoke(
        app, ["--reload", "--select", "foo", "--", "mypy", "src/"]
    )
    assert result.exit_code != 0
