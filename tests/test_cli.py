"""Integration tests for the CLI module.

These tests verify end-to-end CLI behavior including command execution, output
formatting, and interaction with subprocesses.
"""

import functools
import io
import os
import socket
import subprocess
import sys
import typing
from textwrap import dedent
from typing import TYPE_CHECKING, Any
from unittest.mock import ANY, Mock, create_autospec, patch

import pytest
import typer.testing

import tuick
from tuick import console
from tuick.ansi import strip_ansi
from tuick.cli import app
from tuick.console import set_verbose
from tuick.reload_socket import ReloadSocketServer

from .test_data import MYPY_BLOCKS
from .test_errorformat import Block, BlockList, parse_blocks

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    # typer.testing.Result is not explicitly exported and is an alias for
    # click.testing.Result
    from click.testing import Result as TestingResult

    from .conftest import ServerFixture


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
        with patch("sys.argv", ["tuick", *args]):
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
    proc.stdin.write.side_effect = lambda d: (
        sequence.append(f"write:{d}"),  # type: ignore[func-returns-value]
        None,
    )[1]
    proc.stdin.close.side_effect = track(sequence, "fzf:close")
    proc.wait.side_effect = track(sequence, "fzf:wait")
    return proc


def make_errorformat_proc(
    sequence: list[str], jsonl_lines: list[str], returncode: int = 0
) -> Mock:
    """Create mocked errorformat subprocess with JSONL output."""
    proc: Mock = create_autospec(subprocess.Popen, instance=True)
    proc.returncode = returncode
    proc.stdin = create_autospec(io.TextIOWrapper, instance=True)

    # Support both communicate() and stdout iteration
    stdout_text = "".join(jsonl_lines)
    proc.communicate.return_value = (stdout_text, "")

    def stdout_iter() -> Iterator[str]:
        for line in jsonl_lines:
            sequence.append(f"errorformat:{line[:50]}")
            yield line

    proc.stdout = stdout_iter()
    proc.wait.return_value = returncode

    proc.__enter__.side_effect = track(sequence, "errorformat:enter", ret=proc)
    proc.__exit__.side_effect = track(sequence, "errorformat:exit", ret=False)
    return proc


def patch_popen(sequence: list[str], procs: list[Mock]) -> Any:  # noqa: ANN401
    """Patch subprocess.Popen to return procs in sequence, tracking 'popen'.

    Returns a context manager that patches subprocess.Popen.
    """
    index = 0

    def popen_factory(*args, **kwargs):  # noqa: ANN002, ANN003
        nonlocal index
        sequence.append("popen")
        proc = procs[index]
        index += 1
        return proc

    return patch("subprocess.Popen", side_effect=popen_factory)


def patch_popen_selective(
    sequence: list[str], mock_map: dict[str, Mock]
) -> Any:  # noqa: ANN401
    """Patch Popen to mock specific commands, passthrough others."""
    original_popen = subprocess.Popen

    def popen_factory(args, **kwargs):  # noqa: ANN001, ANN003
        cmd = args[0] if args else ""
        if cmd in mock_map:
            sequence.append("popen")
            return mock_map[cmd]
        return original_popen(args, **kwargs)

    return patch("subprocess.Popen", side_effect=popen_factory)


def get_command_calls(
    calls: list[tuple[list[str], dict[str, typing.Any]]], cmd: str
) -> list[list[str]]:
    """Get argument lists for command from Popen calls."""
    return [c[0] for c in calls if c[0] and c[0][0] == cmd]


def get_command_calls_from_mock(mock: Mock, cmd: str) -> list[list[str]]:
    """Extract command calls matching cmd from mock.mock_calls."""
    result = []
    for call in mock.mock_calls:
        args = call[1]
        if args and args[0] and args[0][0] == cmd:
            result.append(args[0])
    return result


def test_cli_default_launches_fzf() -> None:
    """Default command streams data through errorformat to fzf stdin."""
    sequence: list[str] = []
    cmd_proc = make_cmd_proc(sequence, "command", [])
    errorformat_jsonl = [
        '{"filename":"test.py","lnum":1,"col":0,"text":"error",'
        '"lines":["test.py:1: error"]}\n',
        '{"filename":"test.py","lnum":2,"col":0,"text":"warning",'
        '"lines":["test.py:2: warning"]}\n',
    ]
    errorformat_proc = make_errorformat_proc(sequence, errorformat_jsonl)
    fzf_proc = make_fzf_proc(sequence)

    with (
        patch_popen(
            sequence, [cmd_proc, errorformat_proc, fzf_proc]
        ) as popen_mock,
        patch("tuick.cli.MonitorThread"),
    ):
        runner.invoke(app, ["--", "flake8", "src/"])

    assert popen_mock.call_args_list[0].args[0] == ["flake8", "src/"]
    assert popen_mock.call_args_list[0].kwargs["stdout"] == subprocess.PIPE
    assert popen_mock.call_args_list[1].args[0][0] == "errorformat"
    assert popen_mock.call_args_list[1].kwargs["stdin"] == subprocess.PIPE
    assert popen_mock.call_args_list[2].args[0][0] == "fzf"
    assert popen_mock.call_args_list[2].kwargs["stdin"] == subprocess.PIPE

    assert sequence == [
        "popen",
        "command:enter",
        "popen",
        # Streaming: errorformat reads first JSONL entry
        'errorformat:{"filename":"test.py","lnum":1,"col":0,"text":"err',
        "popen",
        "fzf:enter",
        # Streaming: write first block to fzf immediately
        "write:test.py\x1f1\x1f\x1f\x1f\x1ftest.py:1: error\x00",
        # Streaming: errorformat reads second JSONL entry
        'errorformat:{"filename":"test.py","lnum":2,"col":0,"text":"war',
        # Streaming: write second block to fzf immediately
        "write:test.py\x1f2\x1f\x1f\x1f\x1ftest.py:2: warning\x00",
        "fzf:close",
        "command:wait",
        "fzf:exit",
        "command:exit",
    ]


def test_cli_no_output_no_fzf() -> None:
    """When command produces no output, fzf is not started."""
    sequence: list[str] = []

    cmd_proc = make_cmd_proc(sequence, "command", [])
    errorformat_proc = make_errorformat_proc(sequence, [])

    with (
        patch_popen(sequence, [cmd_proc, errorformat_proc]) as popen_mock,
        patch("tuick.cli.MonitorThread"),
    ):
        runner.invoke(app, ["--", "ruff", "check", "src/"])

    assert popen_mock.call_count == 2
    assert sequence == [
        "popen",
        "command:enter",
        "popen",
        "command:wait",
        "command:exit",
    ]


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

    # Mock mypy command subprocess
    mypy_proc = make_cmd_proc(
        sequence, "mypy", ["src/test.py:1: error: Test\n"], returncode=1
    )
    # Mock errorformat subprocess
    ef_jsonl = [
        '{"filename":"src/test.py","lnum":1,"col":0,'
        '"lines":["src/test.py:1: error: Test"],"text":"Test",'
        f'"type":{ord("e")},"valid":true}}\n'
    ]
    ef_proc = make_errorformat_proc(sequence, ef_jsonl)

    try:
        env = {"TUICK_PORT": str(port), "TUICK_API_KEY": api_key}

        with (
            patch_popen(sequence, [mypy_proc, ef_proc]),
            patch.dict("os.environ", env),
        ):
            result = runner.invoke(
                app, ["--reload", "-v", "--", "mypy", "src/"]
            )
        assert result.exit_code == 0
        # Block format: file\x1fline\x1fcol\x1fend_line\x1fend_col\x1ftext\0
        expected = (
            "src/test.py\x1f1\x1f\x1f\x1f\x1fsrc/test.py:1: error: Test\0"
        )
        assert result.stdout == expected
        assert "> Terminating reload command\n" in strip_ansi(result.stderr)
        expected_seq = [
            "terminate",
            "wait",
            "popen",
            "mypy:enter",
            "popen",
            "mypy:src/test.py:1: error: Test",
            'errorformat:{"filename":"src/test.py","lnum":1,"col":0,"lines"',
            "mypy:exit",
        ]
        assert sequence == expected_seq
    finally:
        # Shutdown server
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect(("127.0.0.1", port))
            sock.sendall(f"secret: {api_key}\nshutdown\n".encode())


def test_reload_binding_default_mode() -> None:
    """Default mode: reload binding excludes --top flag."""
    sequence: list[str] = []
    cmd_proc = make_cmd_proc(sequence, "mypy", ["src/a.py:1: error\n"])
    ef_jsonl = ['{"filename":"src/a.py","lnum":1}\n']
    ef_proc = make_errorformat_proc(sequence, ef_jsonl)
    fzf_proc = make_fzf_proc(sequence)
    with (
        patch_popen(sequence, [cmd_proc, ef_proc, fzf_proc]) as mock,
        patch("tuick.cli.MonitorThread"),
    ):
        runner.invoke(app, ["--", "mypy", "src/"])
    fzf_cmd = " ".join(mock.call_args.args[0])
    assert "reload(" in fzf_cmd
    assert "--top" not in fzf_cmd


def test_reload_binding_explicit_top_flag() -> None:
    """Explicit --top: reload binding includes --top flag."""
    sequence: list[str] = []
    cmd_proc = make_cmd_proc(
        sequence, "make", ["\x02a.c\x1f1\x1f\x1f\x1f\x1ferr\0\x03"]
    )
    fzf_proc = make_fzf_proc(sequence)
    with (
        patch_popen(sequence, [cmd_proc, fzf_proc]) as mock,
        patch("tuick.cli.MonitorThread"),
        patch("tuick.cli.get_errorformat_builtin_formats", return_value=set()),
    ):
        runner.invoke(app, ["--top", "--", "make"])
    fzf_cmd = " ".join(mock.call_args.args[0])
    assert "reload(" in fzf_cmd
    assert "--top" in fzf_cmd


def test_reload_binding_autodetect_excludes_top() -> None:
    """Auto-detected build system: reload binding excludes --top."""
    sequence: list[str] = []
    cmd_proc = make_cmd_proc(
        sequence, "make", ["\x02a.c\x1f1\x1f\x1f\x1f\x1ferr\0\x03"]
    )
    fzf_proc = make_fzf_proc(sequence)
    with (
        patch_popen(sequence, [cmd_proc, fzf_proc]) as mock,
        patch("tuick.cli.MonitorThread"),
        patch("tuick.cli.get_errorformat_builtin_formats", return_value=set()),
    ):
        runner.invoke(app, ["--", "make"])
    fzf_cmd = " ".join(mock.call_args.args[0])
    assert "reload(" in fzf_cmd
    assert "--top" not in fzf_cmd


def test_cli_select_plain() -> None:
    """--select option opens editor at location and prints nothing."""
    with (
        patch("tuick.cli.subprocess.run") as mock_run,
        patch.dict(os.environ, {"EDITOR": "vi"}, clear=True),
    ):
        mock_run.return_value = create_autospec(
            subprocess.CompletedProcess,
            instance=True,
        )
        mock_run.return_value.returncode = 0
        args = app, ["--select", "src/test.py", "10", "5", "", ""]
        result = runner.invoke(*args)
        assert result.exit_code == 0
        assert strip_ansi(result.stderr) == ""
        command = ["vi", "+10", "+normal! 5l", "src/test.py"]
        mock_run.assert_called_once_with(command, check=True)


def test_cli_select_verbose() -> None:
    """--verbose --select prints the command to execute."""
    with (
        patch("tuick.cli.subprocess.run") as mock_run,
        patch.dict(os.environ, {"EDITOR": "vi"}, clear=True),
    ):
        mock_run.return_value = create_autospec(
            subprocess.CompletedProcess, instance=True
        )
        mock_run.return_value.returncode = 0
        args = app, ["--verbose", "--select", "src/test.py", "10", "5", "", ""]
        result = runner.invoke(*args)
        assert result.exit_code == 0
        expected = (
            "> tuick --verbose --select src/test.py 10 5 '' ''\n"
            "  $ vi +10 '+normal! 5l' src/test.py\n"
        )
        assert strip_ansi(result.stderr) == expected
        mock_run.assert_called_once()


def test_cli_select_error() -> None:
    """--select prints a message if the editor exits with error."""
    with (
        patch("tuick.cli.subprocess.run") as mock_run,
        patch.dict(os.environ, {"EDITOR": "vi"}, clear=True),
    ):
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd="whatever"
        )
        mock_run.return_value = create_autospec(
            subprocess.CompletedProcess, instance=True
        )
        mock_run.return_value.returncode = 1
        args = app, ["--select", "src/test.py", "10", "5", "", ""]
        result = runner.invoke(*args)
        assert result.exit_code == 1
        mock_run.assert_called_once_with(ANY, check=True)
        assert strip_ansi(result.stderr) == "Error: Editor exit status: 1\n"


def test_cli_select_no_location_found() -> None:
    """--select with no location (empty file) does nothing."""
    with patch("tuick.cli.subprocess.run") as mock_run:
        result = runner.invoke(app, ["--select", "", "", "", "", ""])
        assert result.exit_code == 0
        assert strip_ansi(result.stderr) == ""
        # Verify editor was not called
        mock_run.assert_not_called()


def test_cli_select_verbose_no_location() -> None:
    """--verbose --select with no location prints a message."""
    with patch("tuick.cli.subprocess.run") as mock_run:
        result = runner.invoke(
            app, ["--verbose", "--select", "", "", "", "", ""]
        )
        assert result.exit_code == 0
        expected = dedent("""\
            > tuick --verbose --select '' '' '' '' ''
            No location in selection (informational block)
        """)
        assert strip_ansi(result.stderr) == expected
        # Verify editor was not called
        mock_run.assert_not_called()


def test_verbose_propagates_to_child_processes() -> None:
    """--verbose propagates to nested tuick via TUICK_VERBOSE env var."""
    sequence: list[str] = []
    make_lines = [
        "compiling...\n",
        "\x02src/a.py\x1f10\x1f5\x1f\x1f\x1ferror msg\0\x03",
    ]
    cmd_proc = make_cmd_proc(sequence, "make", make_lines)
    fzf_proc = make_fzf_proc(sequence)
    mock_map = {"make": cmd_proc, "fzf": fzf_proc}

    # Capture env passed to make
    captured_env: dict[str, str] = {}
    original_popen = subprocess.Popen

    def capture_and_mock(args, **kwargs):  # noqa: ANN001, ANN003
        cmd = args[0] if args else ""
        if cmd == "make":
            captured_env.update(kwargs.get("env", {}))
            sequence.append("popen")
            return mock_map[cmd]
        if cmd == "fzf":
            sequence.append("popen")
            return mock_map[cmd]
        return original_popen(args, **kwargs)  # Real for errorformat

    with (
        patch("subprocess.Popen", side_effect=capture_and_mock),
        patch("tuick.cli.MonitorThread"),
    ):
        result = runner.invoke(app, ["--verbose", "--", "make"])

    # Verify TUICK_VERBOSE=1 passed to children
    assert captured_env.get("TUICK_VERBOSE") == "1"
    # Verify verbose output shows the command
    output = strip_ansi(result.stderr)
    assert "$ make" in output


def test_tuick_verbose_env_var_enables_verbose_mode() -> None:
    """TUICK_VERBOSE=1 environment variable enables verbose output."""
    # Temporarily override clean_env fixture by explicitly setting the var
    original_clean = os.environ.copy()
    try:
        os.environ["TUICK_VERBOSE"] = "1"
        console._verbose = False  # Start with verbose off

        with (
            patch("tuick.cli.subprocess.run") as mock_run,
            patch.dict(os.environ, {"EDITOR": "vi"}, clear=False),
        ):
            mock_run.return_value = create_autospec(
                subprocess.CompletedProcess, instance=True
            )
            mock_run.return_value.returncode = 0
            result = runner.invoke(
                app, ["--select", "foo.py", "10", "0", "", ""]
            )

        # Verbose mode should be enabled from env var
        output = strip_ansi(result.stderr)
        assert "> tuick" in output
        assert "$ vi" in output
    finally:
        # Restore original env
        os.environ.clear()
        os.environ.update(original_clean)


def test_nested_verbose_output_not_duplicated() -> None:
    """Nested tuick doesn't duplicate verbose output."""
    set_verbose()
    sequence: list[str] = []
    make_lines = ["\x02src/a.py\x1f1\x1f1\x1f\x1f\x1ferror\0\x03"]
    cmd_proc = make_cmd_proc(sequence, "make", make_lines)
    fzf_proc = make_fzf_proc(sequence)

    nested_result: TestingResult | None = None

    def fzf_exit_with_nested(*args: Any) -> bool:  # noqa: ANN401
        """Simulate fzf start handler invoking nested tuick --start."""
        nonlocal nested_result
        with (
            patch.dict(os.environ, {"FZF_PORT": "12345"}),
            patch("tuick.cli._send_to_tuick_server"),
        ):
            nested_result = runner.invoke(app, ["--start"])
        sequence.append("fzf:exit")
        return False

    fzf_proc.__exit__.side_effect = fzf_exit_with_nested
    mock_map = {"make": cmd_proc, "fzf": fzf_proc}

    with (
        patch_popen_selective(sequence, mock_map),
        patch("tuick.cli.MonitorThread"),
    ):
        result = runner.invoke(app, ["--", "make"])

    # Check total count across both invocations
    assert nested_result is not None
    total_stderr = result.stderr + nested_result.stderr
    assert strip_ansi(total_stderr).count("> tuick --start") == 1


def test_cli_exclusive_options() -> None:
    """--reload and --select are mutually exclusive."""
    result = runner.invoke(
        app, ["--reload", "--select", "foo", "--", "mypy", "src/"]
    )
    assert result.exit_code != 0
    expected = (
        "Error: Options --reload, --select, --start, --message, --format,"
        " and --top are mutually exclusive\n"
    )
    assert strip_ansi(result.stderr) == expected


def test_reload_with_top_allowed() -> None:
    """--reload and --top should work together."""
    with patch("tuick.cli.reload_command") as mock_reload:
        result = runner.invoke(
            app, ["--reload", "--top", "--", "ruff", "check"]
        )
    # Should NOT fail with mutual exclusivity error
    assert result.exit_code == 0
    assert "mutually exclusive" not in strip_ansi(result.stderr)
    # Verify reload_command was called with top_mode=True
    assert mock_reload.call_count == 1
    _args, kwargs = mock_reload.call_args
    assert kwargs["top_mode"] is True


def test_reload_top_conflicts_with_select() -> None:
    """--reload --top should conflict with --select."""
    result = runner.invoke(
        app, ["--reload", "--top", "--select", "foo", "--", "make"]
    )
    assert result.exit_code != 0
    expected = (
        "Error: Options --reload, --select, --start, --message, --format,"
        " and --top are mutually exclusive"
    )
    assert expected in strip_ansi(result.stderr)


def test_reload_autodetects_list_mode() -> None:
    """Reload auto-detects list mode for ruff (non-build-system)."""
    with patch("tuick.cli.reload_command") as mock_reload:
        result = runner.invoke(app, ["--reload", "--", "ruff", "check"])
    assert result.exit_code == 0
    # ruff is NOT a build system, should use list mode (top_mode=False)
    assert mock_reload.call_count == 1
    _args, kwargs = mock_reload.call_args
    assert kwargs["top_mode"] is False


def test_reload_autodetects_build_system() -> None:
    """Reload auto-detects top-mode for just (build system)."""
    with patch("tuick.cli.reload_command") as mock_reload:
        result = runner.invoke(app, ["--reload", "--", "just", "check"])
    assert result.exit_code == 0
    # just IS a build system, should use top mode (top_mode=True)
    assert mock_reload.call_count == 1
    _args, kwargs = mock_reload.call_args
    assert kwargs["top_mode"] is True


def test_reload_explicit_top_forces_mode() -> None:
    """Reload with explicit --top forces top-mode for any tool."""
    with patch("tuick.cli.reload_command") as mock_reload:
        result = runner.invoke(
            app, ["--reload", "--top", "--", "ruff", "check"]
        )
    assert result.exit_code == 0
    # Explicit --top forces top_mode even for non-build-system tools
    assert mock_reload.call_count == 1
    _args, kwargs = mock_reload.call_args
    assert kwargs["top_mode"] is True


def test_cli_abort_after_initial_load_prints_output() -> None:
    """On fzf abort (exit 130) after initial load, print initial output."""
    sequence: list[str] = []

    # Mock mypy command subprocess
    mypy_proc = make_cmd_proc(
        sequence, "mypy", ["initial.py:1: error\n", "initial.py:2: warning\n"]
    )
    # Mock errorformat subprocess
    ef_jsonl = [
        '{"filename":"initial.py","lnum":1,"col":0,'
        '"lines":["initial.py:1: error"]}\n',
        '{"filename":"initial.py","lnum":2,"col":0,'
        '"lines":["initial.py:2: warning"]}\n',
    ]
    ef_proc = make_errorformat_proc(sequence, ef_jsonl)
    fzf_proc = make_fzf_proc(sequence, returncode=130)  # User abort

    with (
        patch_popen(sequence, [mypy_proc, ef_proc, fzf_proc]),
        patch("tuick.cli.MonitorThread"),
    ):
        result = runner.invoke(app, ["--", "mypy", "src/"])

    assert result.exit_code == 0

    # Verify initial output was printed after abort
    assert "initial.py:1: error" in result.stdout
    assert "initial.py:2: warning" in result.stdout

    # Verify mypy was waited before fzf exit
    assert sequence.index("mypy:wait") < sequence.index("fzf:exit")


def format_block(file: str, line: str, col: str, text: str) -> str:
    r"""Format block: file\x1fline\x1fcol\x1f\x1f\x1ftext\0."""
    return f"{file}\x1f{line}\x1f{col}\x1f\x1f\x1f{text}\0"


def format_blocks(blocks: list[tuple[str, str, str, str]]) -> str:
    r"""Format null-terminated blocks."""
    return "".join(format_block(*b) for b in blocks)


def test_errorformat_simple_mode() -> None:
    """Simple mode: flake8 → errorformat JSONL → fzf with field delimiters."""
    sequence: list[str] = []
    flake8_lines = [
        "src/a.py:10:5: F401 unused\n",
        "src/b.py:15:1: E302\n",
    ]
    cmd_proc = make_cmd_proc(sequence, "flake8", flake8_lines)
    ef_jsonl = [
        '{"filename":"src/a.py","lnum":10,"col":5,'
        '"lines":["src/a.py:10:5: F401 unused"]}\n',
        '{"filename":"src/b.py","lnum":15,"col":1,'
        '"lines":["src/b.py:15:1: E302"]}\n',
    ]
    ef_proc = make_errorformat_proc(sequence, ef_jsonl)
    fzf_proc = make_fzf_proc(sequence)

    with (
        patch(
            "subprocess.Popen",
            side_effect=[cmd_proc, ef_proc, fzf_proc],
        ) as mock,
        patch("tuick.cli.MonitorThread"),
    ):
        runner.invoke(app, ["--", "flake8", "src/"])

    assert mock.call_args_list[0].args[0] == ["flake8", "src/"]
    ef_args = ["errorformat", "-w=jsonl", "-name=flake8"]
    assert mock.call_args_list[1].args[0] == ef_args
    fzf_cmd = " ".join(mock.call_args_list[2].args[0])
    assert "--delimiter=\x1f" in fzf_cmd

    blocks = [
        ("src/a.py", "10", "5", "src/a.py:10:5: F401 unused"),
        ("src/b.py", "15", "1", "src/b.py:15:1: E302"),
    ]
    expected = format_blocks(blocks)
    writes = [
        s.removeprefix("write:") for s in sequence if s.startswith("write:")
    ]
    assert "".join(writes) == expected


def test_errorformat_top_mode() -> None:
    """Top mode: make with TUICK_PORT set → parse mixed stream."""
    sequence: list[str] = []
    make_lines = [
        "make: Entering 'src'\n",
        "\x02src/a.c\x1f10\x1f5\x1f\x1f\x1ferror\0\x03",
        "make: Leaving 'src'\n",
    ]
    cmd_proc = make_cmd_proc(sequence, "make", make_lines)
    fzf_proc = make_fzf_proc(sequence)

    mock_map = {"make": cmd_proc, "fzf": fzf_proc}
    with (
        patch_popen_selective(sequence, mock_map) as popen_mock,
        patch("tuick.cli.MonitorThread"),
    ):
        runner.invoke(app, ["--", "make"])

    make_calls = get_command_calls_from_mock(popen_mock, "make")
    assert len(make_calls) == 1
    # Check env from first call: call is (name, args, kwargs)
    _name, _args, kwargs = popen_mock.mock_calls[0]
    assert "TUICK_PORT" in kwargs["env"]

    expected = format_blocks(
        [
            ("", "", "", "make: Entering 'src'"),
            ("src/a.c", "10", "5", "error"),
            ("", "", "", "make: Leaving 'src'"),
        ]
    )
    writes = [
        s.removeprefix("write:") for s in sequence if s.startswith("write:")
    ]
    assert "".join(writes) == expected


def test_errorformat_format_passthrough() -> None:
    """Format mode without TUICK_PORT: passthrough to stdout."""
    sequence: list[str] = []
    mypy_lines = [MYPY_BLOCKS[0] + "\n"]
    cmd_proc = make_cmd_proc(sequence, "mypy", mypy_lines)

    def write_and_wait() -> int:
        """Simulate subprocess writing to stdout."""
        for line in mypy_lines:
            sys.stdout.write(line)
        return 0

    cmd_proc.wait.side_effect = lambda: write_and_wait()

    with (
        patch("subprocess.Popen", side_effect=[cmd_proc]) as mock,
        patch.dict("os.environ", {}, clear=False),
    ):
        result = runner.invoke(app, ["--format", "--", "mypy", "src/"])

    assert mock.call_args_list[0].kwargs.get("stdout") != subprocess.PIPE
    assert result.stdout == "".join(mypy_lines)


@pytest.fixture
def nested_tuick(
    server_with_key: ServerFixture,
) -> Iterator[ReloadSocketServer]:
    """Start server and set TUICK_PORT and TUICK_API_KEY env vars."""
    env = {
        "TUICK_PORT": str(server_with_key.port),
        "TUICK_API_KEY": server_with_key.api_key,
    }
    with patch.dict("os.environ", env):
        yield server_with_key.server


def test_errorformat_format_structured(
    nested_tuick: ReloadSocketServer,
) -> None:
    r"""Format mode with TUICK_PORT set: output \x02blocks\x03."""
    sequence: list[str] = []
    mypy_lines = [MYPY_BLOCKS[0] + "\n", MYPY_BLOCKS[1] + "\n"]
    cmd_proc = make_cmd_proc(sequence, "mypy", mypy_lines)
    ef_jsonl = [
        '{"filename":"src/jobsearch/search.py","lnum":58,'
        f'"lines":["{MYPY_BLOCKS[0]}"]'
        "}\n",
        '{"filename":"tests/test_search.py","lnum":144,'
        f'"lines":["{MYPY_BLOCKS[1]}"]'
        "}\n",
    ]
    ef_proc = make_errorformat_proc(sequence, ef_jsonl)

    with patch("subprocess.Popen", side_effect=[cmd_proc, ef_proc]) as mock:
        nested_tuick.begin_output()
        result = runner.invoke(app, ["--format", "--", "mypy", "src/"])

    assert mock.call_args_list[1].kwargs["stdout"] == subprocess.PIPE
    expected = (
        "\x02"
        + format_blocks(
            [
                ("src/jobsearch/search.py", "58", "", MYPY_BLOCKS[0]),
                ("tests/test_search.py", "144", "", MYPY_BLOCKS[1]),
            ]
        )
        + "\x03"
    )
    assert result.stdout == expected


def test_errorformat_missing_shows_error(
    nested_tuick: ReloadSocketServer,
) -> None:
    """Show clear error when errorformat not installed and --format used."""
    sequence: list[str] = []
    mypy_lines = [MYPY_BLOCKS[0] + "\n"]
    cmd_proc = make_cmd_proc(sequence, "mypy", mypy_lines)

    def popen_factory(*args, **kwargs):  # noqa: ANN002, ANN003
        sequence.append("popen")
        if args[0][0] == "errorformat":
            raise FileNotFoundError
        return cmd_proc

    with (
        patch("subprocess.Popen", side_effect=popen_factory),
    ):
        result = runner.invoke(app, ["--format", "--", "mypy", "src/"])

    assert result.exit_code != 0
    output = strip_ansi(result.stderr)
    assert "errorformat not found" in output
    assert "go install" in output


def test_format_name_and_pattern_exclusive() -> None:
    """-f and -p options are mutually exclusive."""
    args = ["-f", "mypy", "-p", "%f:%l: %m", "--", "mypy", "src/"]
    result = runner.invoke(app, args)
    assert result.exit_code != 0
    output = strip_ansi(result.stderr)
    assert "mutually exclusive" in output


def test_unsupported_tool_without_options() -> None:
    """Unsupported tool without -f or -p shows error."""
    with patch("tuick.tool_registry.detect_tool", return_value="unsupported"):
        result = runner.invoke(app, ["--", "unsupported", "src/"])
    assert result.exit_code != 0
    output = strip_ansi(result.stderr)
    assert "not supported" in output
    assert "-f/--format-name" in output or "-p/--pattern" in output


def test_custom_pattern_option() -> None:
    """Using -p with custom patterns."""
    sequence: list[str] = []
    fzf_proc = make_fzf_proc(sequence)

    with (
        patch_popen_selective(sequence, {"fzf": fzf_proc}) as popen_mock,
        patch("tuick.cli.MonitorThread"),
    ):
        args = ["-p", "%f:%l: %m", "--", "echo", "file.txt:1: error"]
        result = runner.invoke(app, args)

    assert result.exit_code == 0

    # Verify errorformat called with custom pattern
    ef_calls = get_command_calls_from_mock(popen_mock, "errorformat")
    assert ef_calls == [["errorformat", "-w=jsonl", "%f:%l: %m"]]

    # Verify output format with location properly extracted
    writes = [
        s.removeprefix("write:") for s in sequence if s.startswith("write:")
    ]
    actual = parse_blocks("".join(writes))
    expected_block = Block("file.txt", "1", content="file.txt:1: error")
    expected_format = BlockList([expected_block]).format_for_test()
    assert actual.format_for_test() == expected_format


def test_format_name_option() -> None:
    """Using -f to override autodetected format."""
    sequence: list[str] = []
    fzf_proc = make_fzf_proc(sequence)

    with (
        patch_popen_selective(sequence, {"fzf": fzf_proc}) as popen_mock,
        patch("tuick.cli.MonitorThread"),
    ):
        args = ["-f", "mypy", "--", "echo", "file.py:42: error: Incompatible"]
        result = runner.invoke(app, args)

    assert result.exit_code == 0

    # Verify errorformat uses override patterns (not -name=mypy)
    ef_calls = get_command_calls_from_mock(popen_mock, "errorformat")
    assert len(ef_calls) == 1
    assert ef_calls[0][0] == "errorformat"
    assert ef_calls[0][1] == "-w=jsonl"
    assert ef_calls[0][2].startswith("%E")  # Custom pattern

    # Verify output format with location properly extracted
    writes = [
        s.removeprefix("write:") for s in sequence if s.startswith("write:")
    ]
    actual = parse_blocks("".join(writes))
    expected_content = "file.py:42: error: Incompatible"
    expected = BlockList([Block("file.py", "42", content=expected_content)])
    assert actual.format_for_test() == expected.format_for_test()


def get_fzf_cmd(popen_mock: Mock) -> list[str]:
    """Get fzf command from popen mock, asserting it was called once."""
    fzf_calls = [
        call for call in popen_mock.call_args_list if "fzf" in call[0][0]
    ]
    assert len(fzf_calls) == 1
    cmd: list[str] = fzf_calls[0][0][0]
    return cmd


def get_option_value(cmd: list[str], option: str) -> str:
    """Get value of command-line option, asserting it exists."""
    assert option in cmd
    option_idx = cmd.index(option)
    return cmd[option_idx + 1]


def has_preview_toggle_binding(fzf_cmd: list[str]) -> bool:
    """Check if fzf command has preview toggle binding."""
    bindings = get_option_value(fzf_cmd, "--bind")
    return "toggle-preview" in bindings


def make_preview_test_procs(sequence: list[str]) -> list[Mock]:
    """Create standard process mocks for preview tests."""
    cmd_proc = make_cmd_proc(sequence, "command", ["file.py:1: error\n"])
    errorformat_jsonl = [
        '{"filename":"file.py","lnum":1,"col":0,"text":"error",'
        '"lines":["file.py:1: error"]}\n',
    ]
    errorformat_proc = make_errorformat_proc(sequence, errorformat_jsonl)
    fzf_proc = make_fzf_proc(sequence)
    return [cmd_proc, errorformat_proc, fzf_proc]


def test_preview_enabled_by_default_with_bat() -> None:
    """Preview is enabled by default when bat is installed."""
    sequence: list[str] = []

    with (
        patch_popen(sequence, make_preview_test_procs(sequence)) as popen,
        patch("tuick.cli.MonitorThread"),
        patch("shutil.which", return_value="/usr/bin/bat"),
    ):
        runner.invoke(app, ["--", "flake8", "src/"])

    fzf_cmd = get_fzf_cmd(popen)

    # Verify preview command includes bat
    preview_cmd = get_option_value(fzf_cmd, "--preview")
    assert "bat" in preview_cmd
    assert "-f" in preview_cmd
    assert "--theme=dark" in preview_cmd
    assert "{1}" in preview_cmd  # filename field
    assert "{2}" in preview_cmd  # line number field

    # Verify preview window configuration (visible by default)
    window_config = get_option_value(fzf_cmd, "--preview-window")
    assert "right" in window_config or "up" in window_config
    assert "hidden" not in window_config

    # Verify preview toggle binding exists
    assert has_preview_toggle_binding(fzf_cmd)


def test_preview_disabled_with_env_var() -> None:
    """Preview starts hidden when TUICK_PREVIEW=0, but can be toggled."""
    sequence: list[str] = []

    with (
        patch_popen(sequence, make_preview_test_procs(sequence)) as popen,
        patch("tuick.cli.MonitorThread"),
        patch("shutil.which", return_value="/usr/bin/bat"),
        patch.dict(os.environ, {"TUICK_PREVIEW": "0"}),
    ):
        runner.invoke(app, ["--", "flake8", "src/"])

    fzf_cmd = get_fzf_cmd(popen)

    # Verify preview window has "hidden" flag
    window_config = get_option_value(fzf_cmd, "--preview-window")
    assert "hidden" in window_config

    # Verify preview toggle binding exists
    assert has_preview_toggle_binding(fzf_cmd)


def test_preview_shows_error_when_bat_not_installed() -> None:
    """Preview shows error message when bat is not installed."""
    sequence: list[str] = []

    with (
        patch_popen(sequence, make_preview_test_procs(sequence)) as popen,
        patch("tuick.cli.MonitorThread"),
        patch("shutil.which", return_value=None),
    ):
        runner.invoke(app, ["--", "flake8", "src/"])

    fzf_cmd = get_fzf_cmd(popen)

    # Verify preview shows error message
    preview_cmd = get_option_value(fzf_cmd, "--preview")
    assert "Preview requires bat" in preview_cmd

    # Verify preview toggle binding exists
    assert has_preview_toggle_binding(fzf_cmd)


def test_version_option() -> None:
    """--version shows version number and exits."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"tuick {tuick.__version__}" in result.stdout
