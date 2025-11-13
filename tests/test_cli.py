"""Tests for the CLI module."""

import functools
import io
import socket
import subprocess
import sys
from io import StringIO
from textwrap import dedent
from typing import TYPE_CHECKING, Any
from unittest.mock import ANY, Mock, create_autospec, patch

import pytest
import typer.testing

from tuick.cli import app
from tuick.reload_socket import ReloadSocketServer

from .test_parser import MYPY_BLOCKS

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

    return patch("tuick.cli.subprocess.Popen", side_effect=popen_factory)


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

    # Mock mypy command subprocess
    mypy_proc = make_cmd_proc(
        sequence, "mypy", ["src/test.py:1: error: Test\n"], returncode=1
    )
    # Mock errorformat subprocess
    ef_jsonl = [
        '{"filename":"src/test.py","lnum":1,"col":0,'
        '"lines":["src/test.py:1: error: Test"],"text":"Test",'
        '"type":"E","valid":true}\n'
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
        assert "> Terminating reload command\n" in console_out.getvalue()
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


def test_reload_binding_default_mode(console_out: ConsoleFixture) -> None:
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


def test_reload_binding_explicit_top_flag(
    console_out: ConsoleFixture,
) -> None:
    """Explicit --top: reload binding includes --top flag."""
    sequence: list[str] = []
    cmd_proc = make_cmd_proc(
        sequence, "make", ["\x02a.c\x1f1\x1f\x1f\x1f\x1ferr\0\x03"]
    )
    fzf_proc = make_fzf_proc(sequence)
    with (
        patch_popen(sequence, [cmd_proc, fzf_proc]) as mock,
        patch("tuick.cli.MonitorThread"),
    ):
        runner.invoke(app, ["--top", "--", "make"])
    fzf_cmd = " ".join(mock.call_args.args[0])
    assert "reload(" in fzf_cmd
    assert "--top" in fzf_cmd


def test_reload_binding_autodetect_excludes_top(
    console_out: ConsoleFixture,
) -> None:
    """Auto-detected build system: reload binding excludes --top."""
    sequence: list[str] = []
    cmd_proc = make_cmd_proc(
        sequence, "make", ["\x02a.c\x1f1\x1f\x1f\x1f\x1ferr\0\x03"]
    )
    fzf_proc = make_fzf_proc(sequence)
    with (
        patch_popen(sequence, [cmd_proc, fzf_proc]) as mock,
        patch("tuick.cli.MonitorThread"),
    ):
        runner.invoke(app, ["--", "make"])
    fzf_cmd = " ".join(mock.call_args.args[0])
    assert "reload(" in fzf_cmd
    assert "--top" not in fzf_cmd


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
        args = app, ["--select", "src/test.py", "10", "5", "", ""]
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
        assert console_out.getvalue() == expected
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
        args = app, ["--select", "src/test.py", "10", "5", "", ""]
        result = runner.invoke(*args)
        assert result.exit_code == 1
        mock_run.assert_called_once_with(ANY, check=True)
        assert console_out.getvalue() == "Error: Editor exit status: 1\n"


def test_cli_select_no_location_found(console_out: ConsoleFixture) -> None:
    """--select with no location (empty file) does nothing."""
    with patch("tuick.cli.subprocess.run") as mock_run:
        result = runner.invoke(app, ["--select", "", "", "", "", ""])
        assert result.exit_code == 0
        assert console_out.getvalue() == ""
        # Verify editor was not called
        mock_run.assert_not_called()


def test_cli_select_verbose_no_location(console_out: ConsoleFixture) -> None:
    """--verbose --select with no location prints a message."""
    with patch("tuick.cli.subprocess.run") as mock_run:
        result = runner.invoke(
            app, ["--verbose", "--select", "", "", "", "", ""]
        )
        assert result.exit_code == 0
        assert console_out.getvalue() == dedent("""\
            > tuick --verbose --select '' '' '' '' ''
            No location in selection (informational block)
        """)
        # Verify editor was not called
        mock_run.assert_not_called()


def test_cli_exclusive_options(console_out: ConsoleFixture) -> None:
    """--reload and --select are mutually exclusive."""
    result = runner.invoke(
        app, ["--reload", "--select", "foo", "--", "mypy", "src/"]
    )
    assert result.exit_code != 0
    expected = (
        "Error: Options --reload, --select, --start, --message, --format,"
        " and --top are mutually exclusive\n"
    )
    assert console_out.getvalue() == expected


def test_cli_abort_after_initial_load_prints_output(
    console_out: ConsoleFixture,
) -> None:
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
            "tuick.cli.subprocess.Popen",
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

    with (
        patch(
            "tuick.cli.subprocess.Popen",
            side_effect=[cmd_proc, fzf_proc],
        ) as mock,
        patch("tuick.cli.MonitorThread"),
    ):
        runner.invoke(app, ["--", "make"])

    assert "TUICK_PORT" in mock.call_args_list[0].kwargs["env"]

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
    """Format mode without TUICK_NESTED: passthrough to stdout."""
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
        patch("tuick.cli.subprocess.Popen", side_effect=[cmd_proc]) as mock,
        patch.dict("os.environ", {}, clear=False),
    ):
        result = runner.invoke(app, ["--format", "--", "mypy", "src/"])

    assert mock.call_args_list[0].kwargs.get("stdout") != subprocess.PIPE
    assert result.stdout == "".join(mypy_lines)


def test_errorformat_format_structured() -> None:
    r"""Format mode with TUICK_NESTED=1: output \x02blocks\x03."""
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

    with (
        patch(
            "tuick.cli.subprocess.Popen", side_effect=[cmd_proc, ef_proc]
        ) as mock,
        patch.dict("os.environ", {"TUICK_NESTED": "1"}),
    ):
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
    console_out: ConsoleFixture,
) -> None:
    """Show clear error when errorformat not installed and --format used."""
    sequence: list[str] = []
    mypy_lines = [MYPY_BLOCKS[0] + "\n"]
    cmd_proc = make_cmd_proc(sequence, "mypy", mypy_lines)

    with (
        patch_popen(sequence, [cmd_proc]),
        patch("tuick.errorformat.shutil.which", return_value=None),
        patch.dict("os.environ", {"TUICK_NESTED": "1"}),
    ):
        result = runner.invoke(app, ["--format", "--", "mypy", "src/"])

    assert result.exit_code != 0
    output = console_out.getvalue()
    assert "errorformat not found" in output
    assert "go install" in output
