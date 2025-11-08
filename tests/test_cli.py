"""Tests for the CLI module."""

import functools
import io
import socket
import subprocess
from io import StringIO
from textwrap import dedent
from typing import TYPE_CHECKING, Any
from unittest.mock import ANY, Mock, create_autospec, patch

import pytest
import typer.testing

from tuick.cli import app
from tuick.reload_socket import ReloadSocketServer

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    # typer.testing.Result is not explicitly exported and is an alias for
    # click.testing.Result
    from click.testing import Result as TestingResult

    from .conftest import ConsoleFixture, ServerFixture


class CliRunner(typer.testing.CliRunner):
    """Typer CLI runner that patches sys.argv."""

    def invoke(  # type: ignore[override]
        self,
        app: typer.Typer,
        args: str | Sequence[str] | None,
        *args_,  # noqa: ANN002
        **kwargs,  # noqa: ANN003
    ) -> TestingResult:
        """Invoke the CLI with patched sys.argv."""
        if isinstance(args, str):
            args = [args]
        elif args is None:
            args = []
        with patch("sys.argv", ["tuick", *args]):  # type: ignore[call-overload]
            result = super().invoke(app, args, *args_, **kwargs)
            exception = result.exception
            if isinstance(exception, Exception) and not isinstance(
                exception, typer.Exit
            ):
                raise exception
            return result

    functools.update_wrapper(invoke, typer.testing.CliRunner.invoke)


runner = CliRunner()


def track(seq: list[str], action: str, ret: Any = None):  # noqa: ANN401
    """Append action to sequence, return value."""
    return lambda *a: (seq.append(action), ret)[1]  # type: ignore[func-returns-value]


def make_cmd_proc(
    sequence: list[str], name: str, lines: list[str], returncode: int = 0
) -> Mock:
    """Create mocked command subprocess with tracking."""

    def stdout_iter() -> Iterator[str]:
        for line in lines:
            sequence.append(f"{name}:{line.strip()}")
            yield line

    proc: Mock = create_autospec(subprocess.Popen, instance=True)
    proc.returncode = returncode
    proc.stdout = stdout_iter()
    proc.__enter__.side_effect = track(sequence, f"{name}:enter", ret=proc)
    proc.__exit__.side_effect = track(sequence, f"{name}:exit", ret=False)
    proc.wait.side_effect = track(sequence, f"{name}:wait")
    return proc


def make_fzf_proc(sequence: list[str], returncode: int = 0) -> Mock:
    """Create a mocked fzf subprocess that tracks stdin writes and events."""
    proc: Mock = create_autospec(subprocess.Popen, instance=True)
    proc.returncode = returncode
    proc.stdin = create_autospec(io.TextIOWrapper, instance=True)
    proc.__enter__.side_effect = track(sequence, "fzf:enter", ret=proc)
    proc.__exit__.side_effect = track(sequence, "fzf:exit", ret=False)
    proc.stdin.write.side_effect = lambda d: None
    proc.stdin.close.side_effect = track(sequence, "fzf:close")
    return proc


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


def test_cli_reload_option(console_out: ConsoleFixture) -> None:
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
    mock_process.returncode = 1
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
            result = runner.invoke(
                app, ["--reload", "-v", "--", "mypy", "src/"]
            )
        assert result.exit_code == 0
        assert result.stdout == "src/test.py:1: error: Test"
        assert "> Terminating reload command\n" in console_out.getvalue()
        # Verify sequence: terminate → wait → popen
        assert sequence == ["terminate", "wait", "popen", "exit"]
    finally:
        # Shutdown server
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect(("127.0.0.1", port))
            sock.sendall(f"secret: {api_key}\nshutdown\n".encode())


def test_cli_select_plain(console_out: ConsoleFixture) -> None:
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


def test_cli_select_verbose(console_out: ConsoleFixture) -> None:
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
            "> tuick '(mock argv)'\n  $ vi +10 '+normal! 5l' src/test.py\n"
        )
        mock_run.assert_called_once()


def test_cli_select_error(console_out: ConsoleFixture) -> None:
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


def test_cli_select_no_location_found(console_out: ConsoleFixture) -> None:
    """--select with no location does nothing."""
    with patch("tuick.cli.subprocess.run") as mock_run:
        result = runner.invoke(
            app, ["--select", "plain text without location"]
        )
        assert result.exit_code == 0
        assert console_out.getvalue() == ""
        # Verify editor was not called
        mock_run.assert_not_called()


def test_cli_select_verbose_no_location(console_out: ConsoleFixture) -> None:
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


def test_cli_exclusive_options(console_out: ConsoleFixture) -> None:
    """--reload and --select are mutually exclusive."""
    result = runner.invoke(
        app, ["--reload", "--select", "foo", "--", "mypy", "src/"]
    )
    assert result.exit_code != 0


def test_cli_abort_after_initial_load_prints_output(
    console_out: ConsoleFixture,
) -> None:
    """On fzf abort (exit 130) after initial load, print initial output."""
    sequence: list[str] = []

    # Command completes before fzf starts
    cmd_proc = make_cmd_proc(
        sequence, "cmd", ["initial.py:1: error\n", "initial.py:2: warning\n"]
    )
    fzf_proc = make_fzf_proc(sequence, returncode=130)  # User abort

    with (
        patch("tuick.cli.subprocess.Popen", side_effect=[cmd_proc, fzf_proc]),
        patch("tuick.cli.MonitorThread"),
    ):
        result = runner.invoke(app, ["--", "mypy", "src/"])

    assert result.exit_code == 0

    # Verify initial output was printed after abort
    assert "initial.py:1: error" in result.stdout
    assert "initial.py:2: warning" in result.stdout

    # Verify cmd was waited before fzf exit
    assert sequence.index("cmd:wait") < sequence.index("fzf:exit")


@pytest.mark.xfail(reason="needs proper integration test")
def test_cli_abort_after_reload_prints_reload_output(
    server_with_key: ServerFixture,
) -> None:
    """On fzf abort after reload, print reload output."""
    # list_command overwrites saved_output_file
    saved_file = StringIO("reloaded.py:1: new error\nreloaded.py:2: fixed\n")
    server_with_key.server.saved_output_file = saved_file  # type: ignore[assignment]

    # Initial load and fzf abort
    initial_proc = create_autospec(subprocess.Popen, instance=True)
    initial_proc.returncode = 0
    initial_proc.stdout = iter(["initial.py:1: error\n"])
    initial_proc.wait.return_value = None

    fzf_proc = create_autospec(subprocess.Popen, instance=True)
    fzf_proc.returncode = 130  # User abort
    fzf_proc.stdin = create_autospec(io.TextIOWrapper, instance=True)

    with (
        patch(
            "tuick.cli.subprocess.Popen", side_effect=[initial_proc, fzf_proc]
        ),
        patch("tuick.cli.MonitorThread"),
        patch(
            "tuick.cli.ReloadSocketServer",
            return_value=server_with_key.server,
        ),
    ):
        result = runner.invoke(app, ["-v", "--", "mypy", "src/"])

    assert result.exit_code == 0

    # Verify reload output printed (not initial)
    assert "reloaded.py:1: new error" in result.stdout
    assert "reloaded.py:2: fixed" in result.stdout
    assert "initial.py:1: error" not in result.stdout


@pytest.mark.xfail(reason="needs proper integration test")
def test_cli_abort_after_initial_terminated_prints_nothing(
    server_with_key: ServerFixture,
) -> None:
    """On fzf abort after initial terminated, print nothing."""
    # list_command overwrites saved_output_file
    # No saved output file (process was terminated before reload)
    server_with_key.server.saved_output_file = None

    # Initial load and fzf abort
    initial_proc = create_autospec(subprocess.Popen, instance=True)
    initial_proc.returncode = 0
    initial_proc.stdout = iter(["initial.py:1: error\n"])
    initial_proc.wait.return_value = None

    fzf_proc = create_autospec(subprocess.Popen, instance=True)
    fzf_proc.returncode = 130  # User abort
    fzf_proc.stdin = create_autospec(io.TextIOWrapper, instance=True)

    with (
        patch(
            "tuick.cli.subprocess.Popen", side_effect=[initial_proc, fzf_proc]
        ),
        patch("tuick.cli.MonitorThread"),
    ):
        result = runner.invoke(app, ["--", "mypy", "src/"])

    assert result.exit_code == 0

    # Verify nothing printed (no saved output file)
    assert result.stdout.strip() == ""
