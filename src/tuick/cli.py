"""Tuick command line interface.

Tuick is a wrapper for compilers and checkers that integrates with fzf and your
text editor to provide fluid, keyboard-friendly, access to code error
locations.
"""

import contextlib
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import typing
from io import StringIO
from pathlib import Path
from subprocess import PIPE, STDOUT

import typer

import tuick.console
from tuick.console import (
    print_command,
    print_entry,
    print_error,
    print_event,
    print_verbose,
    print_warning,
    set_verbose,
)
from tuick.editor import (
    FileLocation,
    UnsupportedEditorError,
    get_editor_command,
    get_editor_from_env,
)
from tuick.errorformat import (
    CustomPatterns,
    ErrorformatNotFoundError,
    FormatConfig,
    FormatName,
    get_errorformat_builtin_formats,
    parse_with_errorformat,
    split_at_markers,
    wrap_blocks_with_markers,
)
from tuick.fzf import FzfUserInterface, open_fzf_process
from tuick.monitor import MonitorThread
from tuick.reload_socket import ReloadSocketServer
from tuick.shell import quote_command
from tuick.tool_registry import detect_tool, is_build_system, is_known_tool

app = typer.Typer()


# ruff: noqa: FBT001 FBT003 Typer API uses boolean arguments for flags
# ruff: noqa: B008 function-call-in-default-argument
# ruff: noqa: TRY301 Error handling refactoring in TODO.md


class ProcessTerminatedError(Exception):
    """Raised when a command process is terminated before completing."""


def _create_format_config(
    command: list[str], format_name: str, pattern: list[str] | None
) -> FormatConfig:
    """Create FormatConfig from CLI options, with validation.

    Args:
        command: Command to run
        format_name: User-provided format name (or empty string)
        pattern: User-provided patterns (or None)

    Returns:
        FormatConfig object

    Raises:
        typer.Exit: If options are invalid or tool is unsupported
    """
    # Validate mutual exclusivity
    if format_name and pattern:
        print_error(
            None,
            "Options -f/--format-name and -p/--pattern are mutually exclusive",
        )
        raise typer.Exit(1)

    # Use custom patterns if provided
    if pattern:
        return CustomPatterns(patterns=pattern)

    # Use provided format name or autodetect
    tool = format_name if format_name else detect_tool(command)

    # Build systems accepted (stub: groups all output into info blocks)
    if is_build_system(tool):
        return FormatName(format_name=tool)

    # Validate tool is supported
    if (
        not is_known_tool(tool)
        and tool not in get_errorformat_builtin_formats()
    ):
        if format_name:
            msg = (
                f"Format '{tool}' not supported. "
                "Use -p/--pattern for custom patterns."
            )
        else:
            msg = (
                f"Tool '{tool}' not supported. "
                "Use -f/--format-name or -p/--pattern."
            )
        print_error(None, msg)
        raise typer.Exit(1)

    return FormatName(format_name=tool)


@app.command()
def main(  # noqa: PLR0913, C901, PLR0912
    command: list[str] = typer.Argument(default_factory=list),
    reload: bool = typer.Option(
        False, "--reload", help="Internal: run command and output blocks"
    ),
    select: bool = typer.Option(
        False, "--select", help="Internal: open editor at error location"
    ),
    start: bool = typer.Option(
        False, "--start", help="Internal: notify fzf port to parent process"
    ),
    message: str = typer.Option(
        "", "--message", help="Internal: log a message"
    ),
    format: bool = typer.Option(  # noqa: A002
        False,
        "--format",
        help="Format mode: parse and output structured blocks",
    ),
    top: bool = typer.Option(
        False, "--top", help="Top mode: orchestrate nested tuick commands"
    ),
    verbose: bool = typer.Option(
        False, "-v", "--verbose", help="Show verbose output"
    ),
    format_name: str = typer.Option(
        "",
        "-f",
        "--format-name",
        help="Override autodetected errorformat name",
    ),
    pattern: list[str] | None = typer.Option(
        None,
        "-p",
        "--pattern",
        help="Custom errorformat pattern(s)",
    ),
) -> None:
    """Tuick: Text User Interface for Compilers and checkers."""
    with tuick.console.setup_log_file():
        if verbose:
            set_verbose()
        print_entry([Path(sys.argv[0]).name, *sys.argv[1:]])

        exclusive_options = sum(
            [reload, bool(select), start, bool(message), format, top]
        )
        if exclusive_options > 1:
            message = (
                "Options --reload, --select, --start, --message, --format,"
                " and --top are mutually exclusive"
            )
            print_error(None, message)
            raise typer.Exit(1)

        if not exclusive_options and not command:
            print_error(None, "No command specified")

        if reload:
            config = _create_format_config(command, format_name, pattern)
            reload_command(command, config)
        elif select:
            select_command(command)
        elif start:
            start_command()
        elif message:
            message_command(message)
        elif format:
            config = _create_format_config(command, format_name, pattern)
            format_command(command, config)
        elif top:
            config = _create_format_config(command, format_name, pattern)
            top_command(command, config, verbose=verbose)
        else:
            config = _create_format_config(command, format_name, pattern)
            # Check if we're being called from a top-mode orchestrator
            tuick_port = os.environ.get("TUICK_PORT")
            if tuick_port:
                # Output structured blocks (nested behavior)
                try:
                    cmd_proc = _create_command_process(command)
                    with cmd_proc:
                        assert cmd_proc.stdout is not None
                        blocks = parse_with_errorformat(
                            config, cmd_proc.stdout
                        )
                        for chunk in wrap_blocks_with_markers(blocks):
                            _write_block_and_maybe_flush(sys.stdout, chunk)
                except ErrorformatNotFoundError as error:
                    print_error(None, str(error))
                    raise typer.Exit(1) from error
            else:
                # Auto-detect build systems and use top mode
                match config:
                    case FormatName(format_name):
                        if is_build_system(format_name):
                            list_command(
                                command, config, verbose=verbose, top_mode=True
                            )
                        else:
                            list_command(command, config, verbose=verbose)
                    case CustomPatterns():
                        list_command(command, config, verbose=verbose)


class CallbackCommands:
    """Utility class for generating CLI callback commands."""

    def __init__(
        self,
        command: list[str],
        config: FormatConfig,
        *,
        verbose: bool,
        explicit_top: bool = False,
    ) -> None:
        """Initialize callback commands."""
        # Shorten the command name if it is the same as the default
        myself = sys.argv[0]
        default: str | None = shutil.which(Path(myself).name)
        if default and Path(default).resolve() == Path(myself).resolve():
            myself = Path(myself).name

        # Build format options
        format_opts: list[str] = []
        match config:
            case CustomPatterns(patterns):
                for pattern in patterns:
                    format_opts.extend(["-p", pattern])
            case FormatName(format_name):
                format_opts = ["-f", format_name]

        verbose_flag = ["-v"] if verbose else []
        top_flag = ["--top"] if explicit_top else []
        reload_opts = [*verbose_flag, *top_flag, "--reload", *format_opts]
        reload_words = [myself, *reload_opts, "--", *command]
        self.reload_command = quote_command(reload_words)

        # Used only by fzf
        self.start_command = quote_command([myself, *verbose_flag, "--start"])
        self.select_prefix = quote_command([myself, *verbose_flag, "--select"])
        self.message_prefix = quote_command([myself, "--message"])


def list_command(  # noqa: C901
    command: list[str],
    config: FormatConfig,
    *,
    verbose: bool = False,
    top_mode: bool = False,
    explicit_top: bool = False,
) -> None:
    """List errors from running COMMAND.

    Args:
        command: Command to run
        config: Format configuration
        verbose: Enable verbose output
        top_mode: If True, use two-layer parsing for build systems
        explicit_top: If True, include --top flag in reload binding
    """
    callbacks = CallbackCommands(
        command, config, verbose=verbose, explicit_top=explicit_top
    )
    user_interface = FzfUserInterface(command)

    with contextlib.ExitStack() as stack:
        # Create tuick reload coordination server
        reload_server = ReloadSocketServer()
        reload_server.start()

        server_info = reload_server.get_server_info()
        print_verbose("TUICK_PORT:", server_info.port)
        print_verbose("TUICK_API_KEY:", server_info.api_key)

        monitor = MonitorThread(
            callbacks.reload_command,
            user_interface.running_header,
            reload_server,
            verbose=verbose,
        )
        print_verbose("FZF_API_KEY:", monitor.fzf_api_key)
        monitor.start()
        stack.callback(monitor.stop)

        # Run command, save raw output to temp file, and stream blocks to fzf
        temp_file = stack.enter_context(
            tempfile.TemporaryFile(mode="w+", encoding="utf-8")
        )

        cmd_proc = _create_command_process(
            command, (server_info.port, server_info.api_key)
        )
        stack.enter_context(cmd_proc)
        reload_server.cmd_proc = cmd_proc

        assert cmd_proc.stdout is not None
        stdout = cmd_proc.stdout

        # Wrapper to save raw output while feeding to split_blocks
        def raw_and_split() -> typing.Iterator[str]:
            for line in stdout:
                temp_file.write(line)
                yield line

        if top_mode:
            chunks = _parse_top_mode(config, raw_and_split())
        else:
            chunks = parse_with_errorformat(config, raw_and_split())

        try:
            # Read first chunk to check if there's any output
            first_chunk = next(chunks)
        except StopIteration:
            # No output, don't start fzf
            _wait_command(cmd_proc)
            temp_file.close()
            return

        with open_fzf_process(
            callbacks,
            user_interface,
            reload_server.get_server_info(),
            monitor.fzf_api_key,
        ) as fzf_proc:
            assert fzf_proc.stdin is not None

            # Write first chunk to fzf stdin
            _write_block_and_maybe_flush(fzf_proc.stdin, first_chunk)

            # Continue writing blocks to fzf stdin
            for chunk in chunks:
                _write_block_and_maybe_flush(fzf_proc.stdin, chunk)

            fzf_proc.stdin.close()

            # Wait for command process before fzf exits
            _wait_command(cmd_proc)

        reload_server.commit_saved_output_file(temp_file)

        if fzf_proc.returncode == 130:
            # User abort - print saved output if available
            output_file = reload_server.get_saved_output_file()
            if output_file:
                chunk_size = 8192
                while True:
                    chunk = output_file.read(chunk_size)
                    if not chunk:
                        break
                    sys.stdout.write(chunk)
        elif fzf_proc.returncode not in (0, 1):
            # 0 normal exit, 1 no match
            sys.exit(1)


def _send_to_tuick_server(message: str, expected: str) -> None:
    """Send authenticated message to tuick server and verify response."""
    tuick_port = os.environ.get("TUICK_PORT")
    tuick_api_key = os.environ.get("TUICK_API_KEY")

    if not tuick_port or not tuick_api_key:
        message = "Missing environment variable: TUICK_PORT or TUICK_API_KEY"
        print_error(None, message)
        raise typer.Exit(1)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(("127.0.0.1", int(tuick_port)))
        sock.sendall(f"secret: {tuick_api_key}\n{message}\n".encode())
        response = sock.recv(1024).decode().strip()

    if response != expected:
        print_error(None, "Server response:", response)
        raise typer.Exit(1)


def _create_command_process(
    command: list[str], server_info: tuple[int, str] | None = None
) -> subprocess.Popen[str]:
    """Create command subprocess with FORCE_COLOR and optional TUICK_PORT.

    Args:
        command: Command to execute
        server_info: Optional (port, api_key) to set TUICK_PORT/API_KEY.
            If None, inherits from os.environ (for reload/format commands).
    """
    env = os.environ.copy()
    env["FORCE_COLOR"] = "1"
    if server_info:
        port, api_key = server_info
        env["TUICK_PORT"] = str(port)
        env["TUICK_API_KEY"] = api_key
    print_command(command)
    return subprocess.Popen(
        command, stdout=PIPE, stderr=STDOUT, text=True, env=env
    )


def _process_output_and_yield_raw(
    process: subprocess.Popen[str],
    output: typing.TextIO,
    config: FormatConfig,
) -> typing.Iterator[str]:
    """Read process output, write blocks to output, yield raw output."""
    assert process.stdout
    for block in parse_with_errorformat(config, process.stdout):
        _write_block_and_maybe_flush(output, block)
        yield block
    print_verbose("  Command exit:", process.returncode)


def _buffer_chunks(
    raw_iterator: typing.Iterator[str], chunk_size: int = 8192
) -> typing.Iterator[str]:
    """Buffer raw output for efficient socket transmission."""
    accumulator = StringIO()
    for raw in raw_iterator:
        accumulator.write(raw)
        if accumulator.tell() >= chunk_size:
            chunk = accumulator.getvalue()
            accumulator = StringIO()
            yield chunk
    remaining = accumulator.getvalue()
    if remaining:
        yield remaining


def _write_block_and_maybe_flush(output: typing.IO[str], block: str) -> None:
    """Write block to output and flush if block is substantial.

    split_blocks sometimes yields single chars like nulls and newlines. No need
    to flush those because there is nothing to display yet.
    """
    output.write(block)
    if len(block) > 1:
        output.flush()


def _wait_command(process: subprocess.Popen[str]) -> None:
    """Wait for command process and optionally log exit code."""
    process.wait()
    print_verbose("  Initial command exit:", process.returncode)


def start_command() -> None:
    """Notify parent process of fzf port."""
    fzf_port = os.environ.get("FZF_PORT")
    if not fzf_port:
        print_error(None, "Missing environment variable: FZF_PORT")
        raise typer.Exit(1)
    _send_to_tuick_server(f"fzf_port: {fzf_port}", "ok")


def reload_command(command: list[str], config: FormatConfig) -> None:
    """Notify parent, wait for go, run command and save output."""
    try:
        _send_to_tuick_server("reload", "go")
        tuick_port = os.environ.get("TUICK_PORT")
        tuick_api_key = os.environ.get("TUICK_API_KEY")
        if not tuick_port or not tuick_api_key:
            print_error(None, "Missing TUICK_PORT or TUICK_API_KEY")
            raise typer.Exit(1)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect(("127.0.0.1", int(tuick_port)))
            sock.sendall(f"secret: {tuick_api_key}\n".encode())
            sock.sendall(b"save-output\n")

            with _create_command_process(command) as process:
                raw_output = _process_output_and_yield_raw(
                    process, sys.stdout, config
                )
                for chunk in _buffer_chunks(raw_output):
                    data_bytes = chunk.encode("utf-8")
                    sock.sendall(f"{len(data_bytes)}\n".encode())
                    sock.sendall(data_bytes)

            sock.sendall(b"end\n")
            response = sock.recv(1024).decode().strip()
            if response != "ok":
                print_error(None, "Server response:", response)
                raise typer.Exit(1)
    except Exception as error:
        print_error("Reload error:", error)
        raise


def select_command(fields: list[str]) -> None:
    """Display the selected error in the text editor.

    Args:
        fields: List of 5 fields: [file, line, col, end-line, end-col]
    """
    # Expect 5 fields from fzf: file, line, col, end-line, end-col
    if len(fields) < 5:
        print_warning("Invalid selection format:", repr(fields))
        return

    file_path, line_str, col_str = fields[0], fields[1], fields[2]

    # Empty file means no location (informational block)
    if not file_path:
        print_verbose("No location in selection (informational block)")
        return

    # Parse line and column
    try:
        line = int(line_str) if line_str else None
        col = int(col_str) if col_str else None
    except ValueError:
        print_warning("Invalid line/col format:", repr(fields))
        return

    location = FileLocation(path=file_path, row=line, column=col)

    # Get editor from environment
    editor = get_editor_from_env()
    if editor is None:
        message = "No editor configured. Set EDITOR environment variable."
        print_error(None, message)
        raise typer.Exit(1)

    # Build editor command
    try:
        editor_command = get_editor_command(editor, location)
    except UnsupportedEditorError as error:
        print_error(None, error)
        raise typer.Exit(1) from error

    # Display and execute command
    print_command(editor_command)
    try:
        editor_command.run()
    except subprocess.CalledProcessError as error:
        print_error(None, "Editor exit status:", error.returncode)
        raise typer.Exit(1) from error


def message_command(message: str) -> None:
    """Print a message to the error console."""
    if message == "RELOAD":
        print_event("Manual reload")
    elif message == "LOAD":
        print_verbose("  [cyan]Loading complete")
    elif message == "ZERO":
        print_warning("  Reload produced no output")


def format_command(command: list[str], config: FormatConfig) -> None:
    """Format mode: parse and output structured blocks if TUICK_NESTED=1."""
    tuick_nested = os.environ.get("TUICK_NESTED")

    if not tuick_nested:
        # Passthrough mode: run command without capturing output
        print_command(command)
        proc = subprocess.Popen(command)
        proc.wait()
        sys.exit(proc.returncode)

    # Nested mode: parse with errorformat and output structured blocks
    try:
        cmd_proc = _create_command_process(command)
        with cmd_proc:
            assert cmd_proc.stdout is not None
            blocks = parse_with_errorformat(config, cmd_proc.stdout)
            for chunk in wrap_blocks_with_markers(blocks):
                _write_block_and_maybe_flush(sys.stdout, chunk)
    except ErrorformatNotFoundError as error:
        print_error(None, str(error))
        raise typer.Exit(1) from error


def top_command(
    command: list[str], config: FormatConfig, *, verbose: bool = False
) -> None:
    """Top mode: orchestrate nested tuick commands with TUICK_PORT set."""
    list_command(
        command, config, verbose=verbose, top_mode=True, explicit_top=True
    )


def _parse_top_mode(
    config: FormatConfig, lines: typing.Iterable[str]
) -> typing.Iterator[str]:
    """Parse top mode output with two-layer algorithm."""
    for is_nested, content in split_at_markers(lines):
        if is_nested:
            yield content
        elif content.strip():
            yield from parse_with_errorformat(config, [content])


if __name__ == "__main__":
    app()
