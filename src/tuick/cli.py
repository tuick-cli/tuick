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
    UnsupportedEditorError,
    get_editor_command,
    get_editor_from_env,
)
from tuick.fzf import FzfUserInterface, open_fzf_process
from tuick.monitor import MonitorThread
from tuick.parser import (
    FileLocationNotFoundError,
    get_location,
    split_blocks_auto,
)
from tuick.reload_socket import ReloadSocketServer
from tuick.shell import quote_command

app = typer.Typer()


# ruff: noqa: FBT001 FBT003 Typer API uses boolean arguments for flags
# ruff: noqa: B008 function-call-in-default-argument
# ruff: noqa: TRY301 Error handling refactoring in TODO.md


class ProcessTerminatedError(Exception):
    """Raised when a command process is terminated before completing."""


@app.command()
def main(  # noqa: PLR0913
    command: list[str] = typer.Argument(default_factory=list),
    reload: bool = typer.Option(
        False, "--reload", help="Internal: run command and output blocks"
    ),
    select: str = typer.Option(
        "", "--select", help="Internal: open editor at error location"
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
            reload_command(command)
        elif select:
            select_command(select)
        elif start:
            start_command()
        elif message:
            message_command(message)
        elif format:
            format_command(command)
        elif top:
            top_command(command)
        else:
            list_command(command, verbose=verbose)


class CallbackCommands:
    """Utility class for generating CLI callback commands."""

    def __init__(self, command: list[str], *, verbose: bool) -> None:
        """Initialize callback commands."""
        # Shorten the command name if it is the same as the default
        myself = sys.argv[0]
        default: str | None = shutil.which(Path(myself).name)
        if default and Path(default).resolve() == Path(myself).resolve():
            myself = Path(myself).name

        verbose_flag = ["-v"] if verbose else []

        # Used by MonitorThread and fzf
        reload_words = [myself, *verbose_flag, "--reload", "--", *command]
        self.reload_command = quote_command(reload_words)

        # Used only by fzf
        self.start_command = quote_command([myself, *verbose_flag, "--start"])
        self.select_prefix = quote_command([myself, *verbose_flag, "--select"])
        self.message_prefix = quote_command([myself, "--message"])


def list_command(command: list[str], *, verbose: bool = False) -> None:
    """List errors from running COMMAND."""
    callbacks = CallbackCommands(command, verbose=verbose)
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

        cmd_proc = _create_command_process(command)
        stack.enter_context(cmd_proc)
        reload_server.cmd_proc = cmd_proc

        assert cmd_proc.stdout is not None
        stdout = cmd_proc.stdout

        # Wrapper to save raw output while feeding to split_blocks
        def raw_and_split() -> typing.Iterator[str]:
            for line in stdout:
                temp_file.write(line)
                yield line

        chunks = split_blocks_auto(command, raw_and_split())

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


def _create_command_process(command: list[str]) -> subprocess.Popen[str]:
    """Create command subprocess with FORCE_COLOR=1."""
    env = os.environ.copy()
    env["FORCE_COLOR"] = "1"
    print_command(command)
    return subprocess.Popen(
        command, stdout=PIPE, stderr=STDOUT, text=True, env=env
    )


def _process_output_and_yield_raw(
    process: subprocess.Popen[str], output: typing.TextIO, command: list[str]
) -> typing.Iterator[str]:
    """Read process output, write blocks to output, yield raw output.

    Writes null-separated blocks to output (for fzf stdin or stdout). Yields
    raw output immediately as blocks are read (for saving to file).
    """
    assert process.stdout
    for block in split_blocks_auto(command, process.stdout):
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


def reload_command(command: list[str]) -> None:
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
                    process, sys.stdout, command
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


def select_command(selection: str) -> None:
    """Display the selected error in the text editor."""
    try:
        location = get_location(selection)
    except FileLocationNotFoundError:
        print_warning("No location found:", repr(selection))
        return

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


def format_command(command: list[str]) -> None:
    """Format mode: parse and output structured blocks if TUICK_NESTED=1."""
    tuick_nested = os.environ.get("TUICK_NESTED")

    if not tuick_nested:
        # Passthrough mode: just run command without capturing
        print_command(command)
        result = subprocess.run(command, check=False)
        sys.exit(result.returncode)

    # TODO: Implement structured block output with errorformat
    # This will be implemented in step 4-6 of the plan
    print_error(None, "Structured output not yet implemented")
    raise typer.Exit(1)


def top_command(_command: list[str]) -> None:
    """Top mode: orchestrate nested tuick commands with TUICK_NESTED=1."""
    # TODO: Implement two-layer parsing with errorformat
    # This will be implemented in step 7 of the plan
    print_error(None, "Top mode not yet implemented")
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
