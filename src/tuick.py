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
from dataclasses import dataclass
from enum import Enum, auto

if typing.TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

import typer
from rich.console import Console

app = typer.Typer()

err_console = Console(stderr=True)


class State(Enum):
    """State machine states for block splitting."""

    START = auto()
    NORMAL = auto()
    NOTE_CONTEXT = auto()


class LineType(Enum):
    """Types of lines in linter output."""

    BLANK = auto()
    NOTE = auto()
    LOCATION = auto()
    SUMMARY = auto()
    OTHER = auto()


@dataclass
class FileLocation:
    """File location with optional row and column."""

    path: str
    row: int | None = None
    column: int | None = None


class FileLocationNotFoundError(ValueError):
    """Error when location pattern not found in selection."""

    def __init__(self, selection: str) -> None:
        """Initialize with the selection text."""
        self.selection = selection
        super().__init__(f"Location pattern not found in: {selection!r}")

    def __rich__(self) -> str:
        """Rich formatted error message."""
        return (
            f"[bold red]Error:[/] Location pattern not found\n"
            f"[bold]Input:[/] {self.selection!r}"
        )


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
    splitter = BlockSplitter()
    for line in lines:
        yield from splitter.process_line(line)


LINE_REGEX = re.compile(
    r"""^([^\s:]        # File name, with no colon, not indented
          [^:]*         # File name may contain spaces after first char
          :\d+          # Line number
          (?::\d+)?     # Column number
         )
         (?::\d+:\d+)?  # Line and column of end
         :[ ].+         # Message
    """,
    re.MULTILINE + re.VERBOSE,
)
MYPY_NOTE_REGEX = re.compile(
    r"""^[^\s:]       # File name with no colon, not indented
        [^:]*         # File name my contain spaces
        :[ ]note:[ ]  # no line number, note label
    """,
    re.VERBOSE,
)
SUMMARY_REGEX = re.compile(
    r"""^Found[ ]\d+[ ]error  # Summary line like "Found 12 errors"
    """,
    re.VERBOSE,
)
PYTEST_SEP_REGEX = re.compile(
    r"""^(={3,}|_{3,}|_[ ](_[ ])+_)  # === or ___ or _ _ _ separators
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
    re.MULTILINE + re.VERBOSE,
)


def classify_line(text: str) -> LineType:
    """Classify a line by its type for block splitting."""
    if not text:
        return LineType.BLANK
    if re.match(MYPY_NOTE_REGEX, text):
        return LineType.NOTE
    if re.match(LINE_REGEX, text):
        return LineType.LOCATION
    if re.match(SUMMARY_REGEX, text) or re.match(PYTEST_SEP_REGEX, text):
        return LineType.SUMMARY
    return LineType.OTHER


def extract_location_str(text: str) -> str | None:
    """Extract location string (path:line:col) from a line.

    Returns:
        Location string like "path:line" or "path:line:col",
        or None if no match
    """
    if match := re.match(LINE_REGEX, text):
        return match.group(1)
    return None


class BlockSplitter:
    """State machine for splitting linter output into blocks."""

    def __init__(self) -> None:
        """Initialize the block splitter."""
        self.state = State.START
        self.pending_nl = ""
        self.prev_location: str | None = None
        self.note_path: str | None = None
        self.first_block = True

    def process_line(self, line: str) -> Iterator[str]:
        """Process a line and yield output chunks."""
        text, trailing_nl = (
            line.removesuffix("\n"),
            "\n" if line.endswith("\n") else "",
        )
        line_type = classify_line(text)

        if line_type == LineType.BLANK:
            self._reset_state()
            return

        # After blank line (state=START), next line starts new block
        if self.state == State.START:
            starts_new_block = True
        else:
            starts_new_block = self._should_start_new_block(line_type, text)

        if starts_new_block:
            if not self.first_block:
                yield "\0"
            self.pending_nl = ""

        if self.first_block:
            self.first_block = False

        yield self.pending_nl
        yield text
        self.pending_nl = trailing_nl

        self._update_state(line_type, text)

    def _should_start_new_block(self, line_type: LineType, text: str) -> bool:
        """Check if this line should start a new block."""
        if line_type == LineType.NOTE:
            return True

        if line_type == LineType.SUMMARY:
            return True

        if line_type == LineType.LOCATION:
            current_location = extract_location_str(text)
            assert current_location is not None
            if self.state == State.NOTE_CONTEXT:
                current_path = current_location.split(":")[0]
                return self.note_path != current_path
            return (
                self.prev_location is not None
                and current_location != self.prev_location
            )

        return False

    def _update_state(self, line_type: LineType, text: str) -> None:
        """Update state based on processed line."""
        if line_type == LineType.NOTE:
            self.state = State.NOTE_CONTEXT
            self.note_path = text.split(":")[0]
            self.prev_location = None
        elif line_type == LineType.LOCATION:
            current_location = extract_location_str(text)
            assert current_location is not None
            if self.state == State.NOTE_CONTEXT:
                current_path = current_location.split(":")[0]
                if self.note_path != current_path:
                    self.state = State.NORMAL
                    self.note_path = None
            else:
                self.state = State.NORMAL
                self.note_path = None
            self.prev_location = current_location
        elif line_type == LineType.SUMMARY:
            self.state = State.NORMAL
            self.prev_location = None
            self.note_path = None
        elif self.state == State.START:
            self.state = State.NORMAL

    def _reset_state(self) -> None:
        """Reset state to START."""
        self.state = State.START
        self.pending_nl = ""
        self.prev_location = None
        self.note_path = None


def get_location(selection: str) -> FileLocation:
    """Extract file location from error message selection.

    Args:
        selection: Error message text (line or block format)

    Returns:
        FileLocation with path, row, and optional column

    Raises:
        FileLocationNotFoundError: If location pattern not found
    """
    regex = RUFF_REGEX if "\n" in selection else LINE_REGEX
    match = re.search(regex, selection)
    if match is None:
        raise FileLocationNotFoundError(selection)

    # Parse "path:row" or "path:row:col"
    location_str = match.group(1)
    parts = location_str.split(":")
    path = parts[0]
    row = int(parts[1]) if len(parts) > 1 else None
    column = int(parts[2]) if len(parts) > 2 else None

    return FileLocation(path=path, row=row, column=column)


def select_command(selection: str) -> None:
    """Display the selected error in the text editor."""
    try:
        location = get_location(selection)
    except FileLocationNotFoundError as e:
        err_console.print(e)
        raise typer.Exit(1) from e

    # Build destination string: "path:row" or "path:row:col"
    parts = [location.path]
    if location.row is not None:
        parts.append(str(location.row))
        if location.column is not None:
            parts.append(str(location.column))
    destination = ":".join(parts)

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
