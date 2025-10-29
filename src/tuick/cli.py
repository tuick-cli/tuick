"""Tuick command line interface.

Tuick is a wrapper for compilers and checkers that integrates with fzf and your
text editor to provide fluid, keyboard-friendly, access to code error
locations.
"""

import contextlib
import os
import shlex
import subprocess
import sys
import tempfile
import typing
from pathlib import Path

if typing.TYPE_CHECKING:
    from collections.abc import Iterable

import typer
from rich.console import Console

from tuick.editor import (
    UnsupportedEditorError,
    get_editor_command,
    get_editor_from_env,
)
from tuick.monitor import MonitorThread
from tuick.parser import FileLocationNotFoundError, get_location, split_blocks

app = typer.Typer()

console = Console()
err_console = Console(stderr=True)


# ruff: noqa: S607 start-process-with-partial-path
# ruff: noqa: FBT001 FBT003 Typer API uses boolean arguments for flags
# ruff: noqa: B008 function-call-in-default-argument

# TODO: use watchexec to detect changes, and trigger fzf reload through socket

# TODO: exit when command output is empty. We cannot do that within fzf,
# because it has no event for empty input, just for zero matches.
# We need a socket connection


def quote_command(words: Iterable[str]) -> str:
    """Shell quote words and join in a single command string."""
    return " ".join(shlex.quote(x) for x in words)


@app.command()
def main(
    command: list[str] = typer.Argument(None),
    reload: bool = typer.Option(
        False, "--reload", help="Run command and output blocks"
    ),
    select: str = typer.Option(
        "", "--select", help="Open editor at error location"
    ),
    verbose: bool = typer.Option(
        False, "-v", "--verbose", help="Show verbose output"
    ),
) -> None:
    """Tuick: Text User Interface for Compilers and checKers."""
    if reload and select:
        err_console.print(
            "[bold red]Error:[/] "
            "[red]--reload and --select are mutually exclusive"
        )
        raise typer.Exit(1)

    if command is None:
        command = []

    if reload:
        reload_command(command)
    elif select:
        select_command(select, verbose=verbose)
    else:
        list_command(command)


def list_command(command: list[str]) -> None:
    """List errors from running COMMAND."""
    myself = sys.argv[0]
    reload_cmd = quote_command([myself, "--reload", "--", *command])
    select_cmd = quote_command([myself, "--select"])
    env = os.environ.copy()
    env["FZF_DEFAULT_COMMAND"] = reload_cmd

    with contextlib.ExitStack() as stack:
        tmpdir = stack.enter_context(tempfile.TemporaryDirectory())
        socket_path = Path(tmpdir) / "fzf.sock"

        monitor = MonitorThread(socket_path, reload_cmd)
        monitor.start()
        stack.callback(monitor.stop)

        result = subprocess.run(
            [
                "fzf",
                f"--listen={socket_path}",
                "--read0",
                "--ansi",
                "--no-sort",
                "--reverse",
                "--disabled",
                "--color=dark",
                "--highlight-line",
                "--wrap",
                "--no-input",
                "--bind",
                ",".join(
                    [
                        f"enter,right:execute({select_cmd} {{}})",
                        f"r:reload({reload_cmd})",
                        "q:abort",
                        "space:down",
                        "backspace:up",
                        "zero:abort",
                    ]
                ),
            ],
            env=env,
            text=True,
            check=False,
        )
        if result.returncode not in [0, 130]:
            # 130 means fzf was aborted with ctrl-C or ESC
            sys.exit(result.returncode)


def reload_command(command: list[str]) -> None:
    """Run COMMAND with FORCE_COLOR=1 and split output into blocks."""
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
            for chunk in split_blocks(process.stdout):
                sys.stdout.write(chunk)


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
    editor_command.print_to(console)
    try:
        editor_command.run()
    except subprocess.CalledProcessError as e:
        err_console.print(
            f"[bold red]Error running editor (exit {e.returncode})"
        )
        raise typer.Exit(1) from e


if __name__ == "__main__":
    app()
