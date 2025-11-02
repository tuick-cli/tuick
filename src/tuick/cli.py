"""Tuick command line interface.

Tuick is a wrapper for compilers and checkers that integrates with fzf and your
text editor to provide fluid, keyboard-friendly, access to code error
locations.
"""

import contextlib
import os
import re
import socket
import subprocess
import sys
import typing

if typing.TYPE_CHECKING:
    from collections.abc import Iterable

import typer

from tuick.console import console, err_console
from tuick.editor import (
    UnsupportedEditorError,
    get_editor_command,
    get_editor_from_env,
)
from tuick.monitor import MonitorThread
from tuick.parser import FileLocationNotFoundError, get_location, split_blocks
from tuick.reload_socket import ReloadSocketServer, generate_api_key

app = typer.Typer()


# ruff: noqa: FBT001 FBT003 Typer API uses boolean arguments for flags
# ruff: noqa: B008 function-call-in-default-argument

# TODO: use watchexec to detect changes, and trigger fzf reload through socket

# TODO: exit when command output is empty. We cannot do that within fzf,
# because it has no event for empty input, just for zero matches.
# We need a socket connection


def quote_command(words: Iterable[str]) -> str:
    """Shell quote words and join in a single command string."""
    result: list[str] = []
    first = True
    for word in words:
        result.append(_quote_word(word, first))
        first = False
    return " ".join(result)


def _quote_word(word: str, first: bool) -> str:
    if not _needs_quoting(word, first=first):
        return word
    if "'" not in word:
        # That covers the empty case too
        return f"'{word}'"
    for char in '\\"$`':
        word = word.replace(char, "\\" + char)
    return f'"{word}"'


def _needs_quoting(word: str, first: bool) -> bool:
    if not word:
        return True
    if not re.match(r"^[a-zA-Z0-9._/\-:,@%+~=]+$", word):
        return True
    return (first and "=" in word[1:]) or word[0] == "~"


@app.command()
def main(
    command: list[str] = typer.Argument(None),
    reload: bool = typer.Option(
        False, "--reload", help="Run command and output blocks"
    ),
    select: str = typer.Option(
        "", "--select", help="Open editor at error location"
    ),
    start: bool = typer.Option(
        False, "--start", help="Notify fzf port to parent process"
    ),
    verbose: bool = typer.Option(
        False, "-v", "--verbose", help="Show verbose output"
    ),
) -> None:
    """Tuick: Text User Interface for Compilers and checKers."""
    exclusive_options = sum([reload, bool(select), start])
    if exclusive_options > 1:
        err_console.print(
            "[bold red]Error:[/] "
            "[red]--reload, --select, and --start are mutually exclusive"
        )
        raise typer.Exit(1)

    if command is None:
        command = []

    if reload:
        reload_command(command)
    elif select:
        select_command(select, verbose=verbose)
    elif start:
        start_command()
    else:
        list_command(command, verbose=verbose)


def list_command(command: list[str], *, verbose: bool = False) -> None:
    """List errors from running COMMAND."""
    myself = sys.argv[0]
    verbose_flag = ["-v"] if verbose else []
    reload_cmd = quote_command(
        [myself, "--reload", *verbose_flag, "--", *command]
    )
    select_cmd = quote_command([myself, "--select", *verbose_flag])
    start_cmd = quote_command([myself, "--start"])
    header = quote_command(command)

    with contextlib.ExitStack() as stack:
        # Create tuick reload coordination server
        tuick_api_key = generate_api_key()
        reload_server = ReloadSocketServer(tuick_api_key)
        reload_server.start()
        tuick_port = reload_server.server_address[1]

        # Generate fzf API key for monitor thread
        fzf_api_key = generate_api_key()

        monitor = MonitorThread(
            reload_cmd,
            reload_server,
            fzf_api_key,
            verbose=verbose,
        )
        monitor.start()
        stack.callback(monitor.stop)

        # Run command and stream to fzf stdin
        env = os.environ.copy()
        env["FORCE_COLOR"] = "1"
        env["TUICK_PORT"] = str(tuick_port)
        env["TUICK_API_KEY"] = tuick_api_key
        env["FZF_API_KEY"] = fzf_api_key

        with subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        ) as cmd_proc:
            reload_server.cmd_proc = cmd_proc
            # Read first chunk to check if there's any output
            assert cmd_proc.stdout is not None
            chunks = split_blocks(cmd_proc.stdout)
            first_chunk = None
            try:
                first_chunk = next(chunks)
            except StopIteration:
                # No output, don't start fzf
                return

            # Have output, start fzf
            fzf_cmd = [
                "fzf",
                "--listen",
                "--read0",
                "--ansi",
                "--no-sort",
                "--reverse",
                "--disabled",
                "--color=dark",
                "--highlight-line",
                "--wrap",
                "--no-input",
                "--header-border",
                "--track",
                "--bind",
                ",".join(
                    [
                        f"start:change-header({header} ⏳ Running...)"
                        f"+execute-silent({start_cmd})",
                        f"load:change-header({header})",
                        f"enter,right:execute({select_cmd} {{}})",
                        f"r:change-header({header} ⏳ Running...)"
                        f"+reload({reload_cmd})",
                        "q:abort",
                        "space:down",
                        "backspace:up",
                        "zero:abort",
                    ]
                ),
            ]

            if verbose:
                console.print(f"[dim]$ {quote_command(fzf_cmd)}[/]")

            with subprocess.Popen(
                fzf_cmd, stdin=subprocess.PIPE, text=True, env=env
            ) as fzf_proc:
                if fzf_proc.stdin is None:
                    return

                # Write first chunk
                fzf_proc.stdin.write(first_chunk)

                # Stream remaining chunks
                for chunk in chunks:
                    fzf_proc.stdin.write(chunk)

                fzf_proc.stdin.close()

            if verbose:
                if fzf_proc.returncode == 0:
                    console.print("[dim]fzf exited normally (0)[/]")
                elif fzf_proc.returncode == 130:
                    console.print("[dim]fzf aborted by user (130)[/]")
                else:
                    console.print(
                        f"[yellow]fzf exited with "
                        f"status {fzf_proc.returncode}[/]"
                    )

            if fzf_proc.returncode not in [0, 130, None]:
                # 130 means fzf was aborted with ctrl-C or ESC
                sys.exit(fzf_proc.returncode)


def _send_to_tuick_server(message: str, expected_response: str) -> None:
    """Send authenticated message to tuick server and verify response."""
    tuick_port = os.environ.get("TUICK_PORT")
    tuick_api_key = os.environ.get("TUICK_API_KEY")

    if not tuick_port or not tuick_api_key:
        err_console.print(
            "[bold red]Error:[/] Missing environment variables: "
            "TUICK_PORT or TUICK_API_KEY"
        )
        raise typer.Exit(1)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(("127.0.0.1", int(tuick_port)))
        sock.sendall(f"secret: {tuick_api_key}\n{message}\n".encode())
        response = sock.recv(1024).decode().strip()

    if response != expected_response:
        err_console.print(f"[bold red]Error:[/] Server response: {response}")
        raise typer.Exit(1)


def _run_command_and_stream_blocks(
    command: list[str], output: typing.TextIO
) -> None:
    """Run COMMAND with FORCE_COLOR=1 and stream null-separated blocks."""
    env = os.environ.copy()
    env["FORCE_COLOR"] = "1"
    with subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    ) as process:
        if process.stdout:
            output.writelines(split_blocks(process.stdout))


def start_command() -> None:
    """Notify parent process of fzf port."""
    fzf_port = os.environ.get("FZF_PORT")

    if not fzf_port:
        err_console.print(
            "[bold red]Error:[/] Missing environment variable: FZF_PORT"
        )
        raise typer.Exit(1)

    _send_to_tuick_server(f"fzf_port: {fzf_port}", "ok")


def reload_command(command: list[str]) -> None:
    """Notify parent, wait for go, then run command and output blocks."""
    _send_to_tuick_server("reload", "go")
    _run_command_and_stream_blocks(command, sys.stdout)


def select_command(selection: str, *, verbose: bool = False) -> None:
    """Display the selected error in the text editor."""
    try:
        location = get_location(selection)
    except FileLocationNotFoundError:
        console.print("[yellow]No location found")
        if verbose:
            console.print(repr(selection))
        return

    # Get editor from environment
    editor = get_editor_from_env()
    if editor is None:
        err_console.print(
            "[bold red]Error:[/] No editor configured. "
            "Set EDITOR or VISUAL environment variable."
        )
        raise typer.Exit(1)

    # Build editor command
    try:
        editor_command = get_editor_command(editor, location)
    except UnsupportedEditorError as e:
        err_console.print(f"[bold red]Error:[/] {e}")
        raise typer.Exit(1) from e

    # Display and execute command
    if verbose:
        console.print(editor_command)
    try:
        editor_command.run()
    except subprocess.CalledProcessError as e:
        err_console.print(
            f"[bold red]Error running editor (exit {e.returncode})"
        )
        raise typer.Exit(1) from e


if __name__ == "__main__":
    app()
