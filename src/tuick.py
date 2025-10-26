#!/usr/bin/env python3
"""Tuick, the Text User Interface for Compilers and checKers.

Tuick is a wrapper for compilers and checkers that integrates with fzf and your
text editor to provide fluid, keyboard-friendly, access to code error
locations.
"""

import os
import re
import shlex
import subprocess
import sys
import typing

if typing.TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

import typer
from rich.console import Console

app = typer.Typer()

err_console = Console(stderr=True)

# ruff: noqa: S607 start-process-with-partial-path
# Typer API uses boolean arguments, positional values, and function calls
# in defaults
# ruff: noqa: FBT001 boolean-type-hint-positional-argument
# ruff: noqa: FBT003 boolean-positional-value-in-call
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
        select_command(select)
    else:
        list_command(command)


def list_command(command: list[str]) -> None:
    """List errors from running COMMAND."""
    myself = sys.argv[0]
    reload_cmd = quote_command([myself, "--reload", "--", *command])
    select_cmd = quote_command([myself, "--select"])
    env = os.environ.copy()
    env["FZF_DEFAULT_COMMAND"] = reload_cmd
    result = subprocess.run(
        [
            "fzf",
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


def split_blocks(lines: Iterable[str]) -> Iterator[str]:
    r"""Split lines into NULL-separated blocks.

    Args:
        lines: Iterable of lines with line endings preserved

    Yields:
        Chunks of the \0-separated stream
    """
    first_block = True
    pending_nl = ""
    for line in lines:
        text, trailing_nl = (
            line.removesuffix("\n"),
            "\n" if line.endswith("\n") else "",
        )
        if not text:
            # Blank line
            yield "\n\0"
            first_block = False
            pending_nl = ""
            continue
        if re.match(LINE_REGEX, text):
            if not first_block:
                yield "\0"
            first_block = False
            trailing_nl = ""
        yield pending_nl
        yield text
        pending_nl = trailing_nl
    yield pending_nl


LINE_REGEX = re.compile(
    r"""^([^:]+         # File name
          :\d+          # Line number
          (?::\d+)?     # Column number
         )
         (?::\d+:\d+)?  # Line and column of end
         :[ ].+         # Message
    """,
    re.VERBOSE,
)
RUFF_REGEX = re.compile(
    r"""^[ ]*-->[ ]  # Arrow marker, preceded by number column width padding
        ([^:]+       # File name
        :\d+         # Line number
        :\d+         # Column number
        )$
    """,
    re.VERBOSE,
)


def select_command(selection: str) -> None:
    """Display the selected error in the text editor."""
    regex = RUFF_REGEX if "\n" in selection else LINE_REGEX
    match = re.search(regex, selection)
    if match is None:
        pattern = {LINE_REGEX: "line", RUFF_REGEX: "ruff"}[regex]
        err_console.print("[bold red]Line pattern not found:", pattern)
        err_console.print("[bold]Input:", repr(selection))
        raise typer.Exit(1)
    destination = match.group(1)
    editor_command = ["code", "--goto", destination]
    result = subprocess.run(
        editor_command, check=False, capture_output=True, text=True
    )
    if result.returncode or result.stderr:
        err_console.print(
            "[bold red]Error running editor:",
            " ".join(shlex.quote(x) for x in editor_command),
        )
        if result.stderr:
            err_console.print(result.stderr)


if __name__ == "__main__":
    app()
