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
import threading
import typing
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
)
from tuick.editor import (
    UnsupportedEditorError,
    get_editor_command,
    get_editor_from_env,
)
from tuick.fzf import FzfUserInterface, open_fzf_process
from tuick.monitor import MonitorThread
from tuick.parser import FileLocationNotFoundError, get_location, split_blocks
from tuick.reload_socket import ReloadSocketServer
from tuick.shell import quote_command

app = typer.Typer()


# ruff: noqa: FBT001 FBT003 Typer API uses boolean arguments for flags
# ruff: noqa: B008 function-call-in-default-argument


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
    verbose: bool = typer.Option(
        False, "-v", "--verbose", help="Show verbose output"
    ),
) -> None:
    """Tuick: Text User Interface for Compilers and checkers."""
    with tuick.console.setup_log_file():
        if verbose:
            base_cmd = Path(sys.argv[0]).name
            print_entry([base_cmd, *sys.argv[1:]])

        exclusive_options = sum([reload, bool(select), start, bool(message)])
        if exclusive_options > 1:
            message = (
                "Options --reload, --select, --start, and --message are"
                " mutually exclusive"
            )
            print_error(None, message)
            raise typer.Exit(1)

        if not exclusive_options and not command:
            print_error(None, "No command specified")

        if reload:
            reload_command(command, verbose=verbose)
        elif select:
            select_command(select, verbose=verbose)
        elif start:
            start_command()
        elif message:
            message_command(message)
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

        if verbose:
            server_info = reload_server.get_server_info()
            print_verbose("TUICK_PORT:", server_info.port)
            print_verbose("TUICK_API_KEY:", server_info.api_key)

        monitor = MonitorThread(
            callbacks.reload_command,
            user_interface.running_header,
            reload_server,
            verbose=verbose,
        )
        if verbose:
            print_verbose("FZF_API_KEY:", monitor.fzf_api_key)
        monitor.start()
        stack.callback(monitor.stop)

        # Run command and stream to fzf stdin
        env = os.environ.copy()
        env["FORCE_COLOR"] = "1"
        if verbose:
            print_command(command)
        cmd_proc = subprocess.Popen(
            command, stdout=PIPE, stderr=STDOUT, text=True, env=env
        )
        stack.enter_context(cmd_proc)
        reload_server.cmd_proc = cmd_proc

        assert cmd_proc.stdout is not None
        chunks = split_blocks(cmd_proc.stdout)

        def wait_initial_command() -> None:
            cmd_proc.wait()
            if verbose:
                args = "  Initial command exit:", cmd_proc.returncode
                print_verbose(*args)

        try:
            # Read first chunk to check if there's any output
            first_chunk = next(chunks)
        except StopIteration:
            # No output, don't start fzf
            wait_initial_command()
            return

        threading.Thread(target=wait_initial_command, daemon=True).start()

        with open_fzf_process(
            callbacks,
            user_interface,
            reload_server.get_server_info(),
            monitor.fzf_api_key,
            verbose=verbose,
        ) as fzf_proc:
            assert fzf_proc.stdin is not None

            # Write blocks to fzf stdin
            fzf_proc.stdin.write(first_chunk)
            fzf_proc.stdin.flush()
            for chunk in chunks:
                fzf_proc.stdin.write(chunk)
                # Current split_blocks implementation sometimes yields single
                # chars, like nulls and newlines. No need to flush those
                # because there is nothing to display
                if len(chunk) > 1:
                    fzf_proc.stdin.flush()
            fzf_proc.stdin.close()

        if fzf_proc.returncode not in (0, 1, 130):
            # 0 normal exit, 1 no match, 130 user abort
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


def _run_command_and_stream_blocks(
    command: list[str], output: typing.TextIO, *, verbose: bool = False
) -> None:
    """Run COMMAND with FORCE_COLOR=1 and stream null-separated blocks."""
    env = os.environ.copy()
    env["FORCE_COLOR"] = "1"
    if verbose:
        print_command(command)
    with subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    ) as process:
        assert process.stdout
        for block in split_blocks(process.stdout):
            output.write(block)
            if len(block) > 1:
                # split_blocks sometimes yields single chars, like nulls and
                # newlines. Do not flush those, there is nothing to display
                output.flush()
    if verbose:
        print_verbose("  Reload command exit:", process.returncode)


def start_command() -> None:
    """Notify parent process of fzf port."""
    fzf_port = os.environ.get("FZF_PORT")
    if not fzf_port:
        print_error(None, "Missing environment variable: FZF_PORT")
        raise typer.Exit(1)
    _send_to_tuick_server(f"fzf_port: {fzf_port}", "ok")


def reload_command(command: list[str], *, verbose: bool = False) -> None:
    """Notify parent, wait for go, then run command and output blocks."""
    try:
        _send_to_tuick_server("reload", "go")
        _run_command_and_stream_blocks(command, sys.stdout, verbose=verbose)
    except Exception as error:
        print_error("Reload error:", error)
        raise


def select_command(selection: str, *, verbose: bool = False) -> None:
    """Display the selected error in the text editor."""
    try:
        location = get_location(selection)
    except FileLocationNotFoundError:
        if verbose:
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
    if verbose:
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


if __name__ == "__main__":
    app()
