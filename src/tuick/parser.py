"""Parser for compiler and checker output.

This module provides functionality to parse and split compiler/checker output
into blocks for display in fzf.
"""

import re
import typing
from dataclasses import dataclass
from enum import Enum, auto

from tuick.errorformat import parse_with_errorformat
from tuick.errorformats import detect_tool, is_known_tool

if typing.TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


class State(Enum):
    """State machine states for block splitting."""

    START = auto()
    NORMAL = auto()
    NOTE_CONTEXT = auto()
    SUMMARY = auto()
    PYTEST_BLOCK = auto()


class LineType(Enum):
    """Types of lines in linter output."""

    BLANK = auto()
    NOTE = auto()
    LOCATION = auto()
    SUMMARY = auto()
    SEPARATOR = auto()
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


LINE_REGEX = re.compile(
    r"""^([^\s:]        # File name, with no colon, not indented
          [^:\n]*       # File name may contain spaces after first char
          :\d+          # Line number
          (?::\d+)?     # Column number
         )
         (?::\d+:\d+)?  # Line and column of end
         :[ ].+         # Message
    """,
    re.VERBOSE,
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
        |^={3,}.+?={3,}$      # === summary ===
    """,
    re.VERBOSE,
)
PYTEST_SEP_REGEX = re.compile(
    r"""^(_{3,}|_[ ](_[ ])+_)  # ___ or _ _ _ separators
    """,
    re.VERBOSE,
)

LINE_LOCATION_REGEX = re.compile(
    r"""^([^\s:]        # File name, with no colon, not indented
          [^:\n]*       # File name may contain spaces after first char
          :\d+          # Line number
          (?::\d+)?     # Column number
         )
         (?::\d+:\d+)?  # Line and column of end
         :[ ]           # Final colon and space
    """,
    re.MULTILINE + re.VERBOSE,
)
RUFF_LOCATION_REGEX = re.compile(
    r"""^[ ]*-->[ ]  # Arrow marker, preceded by number column width padding
        ([^:]+       # File name
        :\d+         # Line number
        :\d+         # Column number
        )$
    """,
    re.MULTILINE + re.VERBOSE,
)

ANSI_REGEX = re.compile(
    r"""
    \x1B                    # ESC character (0x1B, decimal 27)
    (?:                     # ECMA-48 escape sequences (two types)
        [@-Z\\-_]           # Fe sequence: ESC + single byte
                            #   @-Z: 0x40-0x5A
                            #   \:   0x5C (backslash)
                            #   ]-_: 0x5D-0x5F
                            # Examples: ESC M (reverse index)
    |                       # OR
        \[                  # CSI (Control Sequence Introducer): ESC [
        [0-?]*              # Parameter bytes (0 or more): 0x30-0x3F
                            #   0-9: digits for numeric parameters
                            #   :;<=>?: separators and private markers
                            # Examples: 31, 1;32, ?25, >
        [ -/]*              # Intermediate bytes (0 or more): 0x20-0x2F
                            # Modifies final byte meaning (rare)
        [@-~]               # Final byte (exactly 1): 0x40-0x7E
                            # Determines the command
                            # m: SGR (colors), H: cursor, J: erase, etc.
    )
    """,
    re.VERBOSE,
)


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text.

    Strips ECMA-48 escape sequences:
    - Fe sequences: ESC + single byte (ESC M, ESC 7, etc.)
    - CSI sequences: ESC [ params intermediates final
      Common: ESC[31m (red), ESC[1;32m (bold green), ESC[0m (reset)
    """
    return ANSI_REGEX.sub("", text)


def classify_line(text: str) -> LineType:
    """Classify a line by its type for block splitting."""
    if not text:
        return LineType.BLANK
    if re.match(MYPY_NOTE_REGEX, text):
        return LineType.NOTE
    if re.match(LINE_REGEX, text):
        return LineType.LOCATION
    if re.match(SUMMARY_REGEX, text):
        return LineType.SUMMARY
    if re.match(PYTEST_SEP_REGEX, text):
        return LineType.SEPARATOR
    return LineType.OTHER


def extract_location_str(text: str) -> str | None:
    """Extract location string (path:line:col) from a line.

    Returns:
        Location string like "path:line" or "path:line:col",
        or None if no match
    """
    text = strip_ansi(text)
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
        raw_text, trailing_nl = (
            line.removesuffix("\n"),
            "\n" if line.endswith("\n") else "",
        )
        text = strip_ansi(raw_text)
        line_type = classify_line(text)

        if line_type == LineType.BLANK:
            if self.pending_nl:
                yield self.pending_nl
            if self.state not in (State.SUMMARY, State.PYTEST_BLOCK):
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

        if self.pending_nl:
            yield self.pending_nl
        yield raw_text
        self.pending_nl = trailing_nl

        self._update_state(line_type, text)

    def _should_start_new_block(self, line_type: LineType, text: str) -> bool:  # noqa: PLR0911
        """Check if this line should start a new block."""
        if line_type in (LineType.NOTE, LineType.SEPARATOR):
            return True

        if line_type == LineType.SUMMARY:
            return self.state != State.SUMMARY

        if line_type == LineType.LOCATION:
            current_location = extract_location_str(text)
            assert current_location is not None
            if self.state == State.NOTE_CONTEXT:
                current_path = current_location.split(":")[0]
                return self.note_path != current_path
            if self.state == State.SUMMARY:
                return True
            if self.state == State.PYTEST_BLOCK and text.startswith("E "):
                # Looks like a location, but it's a failure message
                return False
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
            elif self.state != State.PYTEST_BLOCK:
                self.state = State.NORMAL
                self.note_path = None
            self.prev_location = current_location
        elif line_type == LineType.SEPARATOR:
            self.state = State.PYTEST_BLOCK
            self.prev_location = None
            self.note_path = None
        elif line_type == LineType.SUMMARY:
            self.state = State.SUMMARY
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


def split_blocks_errorformat(tool: str, lines: Iterable[str]) -> Iterator[str]:
    r"""Split lines into \0-separated blocks using errorformat."""
    yield from parse_with_errorformat(tool, lines)


def split_blocks_auto(
    command: list[str], lines: Iterable[str]
) -> Iterator[str]:
    r"""Split lines into \0-separated blocks, auto-selecting parser.

    Uses errorformat for known tools, regex parser otherwise.
    """
    tool = detect_tool(command)
    if is_known_tool(tool):
        yield from split_blocks_errorformat(tool, lines)
    else:
        yield from split_blocks(lines)


def get_location(selection: str) -> FileLocation:
    """Extract file location from error message selection.

    Args:
        selection: Error message text (line or block format)

    Returns:
        FileLocation with path, row, and optional column

    Raises:
        FileLocationNotFoundError: If location pattern not found
    """
    selection = strip_ansi(selection)
    match = re.search(LINE_LOCATION_REGEX, selection)
    if match is None:
        match = re.search(RUFF_LOCATION_REGEX, selection)
    if match is None:
        raise FileLocationNotFoundError(selection)

    # Parse "path:row" or "path:row:col"
    location_str = match.group(1)
    parts = location_str.split(":")
    path = parts[0]
    row = int(parts[1]) if len(parts) > 1 else None
    column = int(parts[2]) if len(parts) > 2 else None

    return FileLocation(path=path, row=row, column=column)
