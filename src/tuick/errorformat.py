"""Errorformat integration for parsing tool output."""

import json
import re
import shutil
import subprocess
import threading
import typing
from dataclasses import dataclass, replace

from tuick.ansi import strip_ansi
from tuick.tool_registry import (
    BUILTIN_TOOLS,
    CUSTOM_PATTERNS,
    OVERRIDE_PATTERNS,
)

if typing.TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


class ErrorformatNotFoundError(Exception):
    """Errorformat CLI not found."""

    def __init__(self) -> None:  # noqa: D107
        super().__init__(
            "errorformat not found. Install with:\n"
            "  go install github.com/reviewdog/errorformat/cmd/"
            "errorformat@latest"
        )


@dataclass
class ErrorformatEntry:
    """Parsed entry from errorformat JSONL output."""

    filename: str
    lnum: int | None
    col: int | None
    end_lnum: int | None
    end_col: int | None
    lines: list[str]
    text: str
    type: str
    valid: bool


def run_errorformat(  # noqa: C901
    tool: str, input_lines: Iterable[str]
) -> Iterator[ErrorformatEntry]:
    """Run errorformat subprocess, yield parsed entries.

    Args:
        tool: Tool name (mypy, etc.)
        input_lines: Tool output lines (with ANSI codes)

    Yields:
        ErrorformatEntry objects

    Raises:
        ErrorformatNotFoundError: If errorformat not in PATH
        subprocess.CalledProcessError: If errorformat fails
    """
    if shutil.which("errorformat") is None:
        raise ErrorformatNotFoundError

    # Build errorformat command based on tool configuration
    cmd = ["errorformat", "-w=jsonl"]
    if tool in OVERRIDE_PATTERNS:
        cmd.extend(OVERRIDE_PATTERNS[tool])
    elif tool in CUSTOM_PATTERNS:
        cmd.extend(CUSTOM_PATTERNS[tool])
    elif tool in BUILTIN_TOOLS:
        cmd.append(f"-name={tool}")
    else:
        msg = f"Unknown tool: {tool} (is_known_tool() should be checked first)"
        raise AssertionError(msg)
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Stream input to errorformat stdin in background thread
    def write_input() -> None:
        assert proc.stdin is not None
        try:
            for line in input_lines:
                proc.stdin.write(line)
            proc.stdin.close()
        except BrokenPipeError:
            pass

    writer = threading.Thread(target=write_input, daemon=True)
    writer.start()

    # Stream output from errorformat stdout
    assert proc.stdout is not None
    for line in proc.stdout:
        if not line.strip():
            continue
        data = json.loads(line)
        yield ErrorformatEntry(
            filename=data.get("filename", ""),
            lnum=data.get("lnum") or None,
            col=data.get("col") or None,
            end_lnum=data.get("end_lnum") or None,
            end_col=data.get("end_col") or None,
            lines=data.get("lines", []),
            text=data.get("text", ""),
            type=data.get("type", ""),
            valid=data.get("valid", False),
        )

    writer.join()
    proc.wait()

    if proc.returncode != 0:
        stderr = proc.stderr.read() if proc.stderr else ""
        raise subprocess.CalledProcessError(
            proc.returncode, cmd, stderr=stderr
        )


def group_entries_by_location(  # noqa: C901, PLR0912
    entries: Iterable[ErrorformatEntry],
) -> Iterator[ErrorformatEntry]:
    """Group errorformat entries by location.

    Notes (entries without line numbers) are merged with following errors from
    the same file. Entries with the same (filename, lnum, col) are grouped
    together.
    """
    pending_note: ErrorformatEntry | None = None
    pending_block: ErrorformatEntry | None = None

    for entry in entries:
        if not entry.lnum:
            # Context note entry - buffer or replace
            if pending_note and pending_note.filename != entry.filename:
                # Different file - keep only the new note.
                # That should not happen, being defensive.
                yield pending_note
                pending_note = entry
            elif pending_note:
                # Same file - merge
                pending_note = replace(
                    pending_note, lines=pending_note.lines + entry.lines
                )
            else:
                pending_note = entry
        else:
            # Location entry
            if pending_note:
                if pending_note.filename != entry.filename:
                    # Pending note does not match file, flush
                    yield pending_note
                else:
                    # Pending note with matching file, swallow
                    entry = replace(  # noqa: PLW2901
                        entry, lines=pending_note.lines + entry.lines
                    )
                pending_note = None

            loc = (entry.filename, entry.lnum, entry.col)
            pending_loc = (
                (pending_block.filename, pending_block.lnum, pending_block.col)
                if pending_block
                else None
            )

            if pending_loc == loc:
                # Same location - merge
                assert pending_block is not None
                pending_block = replace(
                    pending_block, lines=pending_block.lines + entry.lines
                )
            else:
                # New location - flush pending block
                if pending_block:
                    yield pending_block
                # Start new block, attach note if same file
                if pending_note and pending_note.filename == entry.filename:
                    pending_block = replace(
                        entry, lines=pending_note.lines + entry.lines
                    )
                    pending_note = None
                else:
                    pending_block = entry

    # Flush remaining
    if pending_block:
        yield pending_block
    if pending_note:
        yield pending_note


def format_block_from_entry(entry: ErrorformatEntry) -> str:
    r"""Format errorformat entry as tuick block.

    Block format: file\x1fline\x1fcol\x1fend-line\x1fend-col\x1ftext\0
    """
    text = "\n".join(entry.lines)
    line_str = str(entry.lnum) if entry.lnum is not None else ""
    col_str = str(entry.col) if entry.col is not None else ""
    end_line_str = str(entry.end_lnum) if entry.end_lnum is not None else ""
    end_col_str = str(entry.end_col) if entry.end_col is not None else ""
    return (
        f"{entry.filename}\x1f{line_str}\x1f{col_str}\x1f"
        f"{end_line_str}\x1f{end_col_str}\x1f{text}\0"
    )


def group_pytest_entries(  # noqa: C901, PLR0912
    entries: Iterable[ErrorformatEntry],
) -> Iterator[ErrorformatEntry]:
    """Group pytest errorformat entries into multi-line blocks.

    Pytest blocks are info blocks (no location) delimited by headings:
    - === headings === start new info block OR continue current info block
    - ___ headings ___ start new test failure blocks
    - _ _ _ delimiters start new traceback frame blocks

    All pytest blocks have empty location fields.

    Yields:
        Grouped entries without location fields
    """
    pending: ErrorformatEntry | None = None
    pending_is_eq_block = False

    for entry in entries:
        assert len(entry.lines) == 1
        line = entry.lines[0] if entry.lines else ""
        # Match headings: at least 3 = or _ at start and end
        is_eq_heading = (
            len(line) >= 6 and line[:3] == "===" and line[-3:] == "==="
        )
        is_underscore_heading = (
            len(line) >= 6 and line[:3] == "___" and line[-3:] == "___"
        )
        # Match _ _ _ delimiter at start of line
        is_delimiter = line.startswith("_ _ _")

        # Determine if we should start a new block
        if is_eq_heading:
            # === continues === blocks, starts new block otherwise
            if pending and pending_is_eq_block:
                # Current is === block - append
                pending = replace(pending, lines=pending.lines + entry.lines)
            else:
                # Start new === block
                if pending:
                    yield pending
                pending = entry
                pending_is_eq_block = True
        elif is_underscore_heading or is_delimiter:
            # ___ and _ _ _ always start new blocks
            if pending:
                yield pending
            pending = entry
            pending_is_eq_block = False
        # Error line - handle based on context
        elif entry.lnum:
            # Error line with location
            if pending and pending_is_eq_block:
                # Pending is prolog block, start a new  block
                yield pending
                pending = entry
                pending_is_eq_block = False
            elif pending and not pending.filename:
                # Pending is info - upgrade with location (keep it)
                pending = replace(entry, lines=pending.lines + entry.lines)
            elif pending:
                # Pending has location - start new block (keep location)
                yield pending
                pending = entry
                pending_is_eq_block = False
            else:
                # No pending - start new block (keep location)
                pending = entry
                pending_is_eq_block = False
        elif pending:
            # Regular continuation - append
            pending = replace(pending, lines=pending.lines + entry.lines)
        else:
            pending = entry
            pending_is_eq_block = False

    if pending:
        yield pending


def parse_with_errorformat(tool: str, lines: Iterable[str]) -> Iterator[str]:
    """Parse tool output with errorformat, yield block chunks.

    Args:
        tool: Tool name matching errorformat -name option
        lines: Tool output lines (may contain ANSI codes)

    Yields:
        Null-terminated block chunks (with ANSI codes preserved)
    """
    # Build mapping from stripped lines to original (with ANSI) while streaming
    stripped_to_original: dict[str, str] = {}

    def strip_and_track(lines: Iterable[str]) -> Iterator[str]:
        """Strip ANSI codes and track mapping while streaming."""
        for line in lines:
            stripped = strip_ansi(line)
            stripped_to_original[stripped.rstrip("\n")] = line.rstrip("\n")
            yield stripped

    # Parse with errorformat using stripped lines
    entries = run_errorformat(tool, strip_and_track(lines))

    # Group entries by location (merges notes with errors)
    if tool == "mypy":
        entries = group_entries_by_location(entries)
    elif tool == "pytest":
        entries = group_pytest_entries(entries)

    for entry in entries:
        # Restore original colored lines from mapping
        entry.lines = [
            stripped_to_original.get(line, line) for line in entry.lines
        ]
        yield format_block_from_entry(entry)


def split_at_markers(lines: Iterable[str]) -> Iterator[tuple[bool, str]]:
    r"""Split lines at \x02 and \x03 markers.

    Yields:
        (is_nested, content) tuples where is_nested indicates if content
        came from between markers (True) or outside markers (False).
    """
    text = "".join(lines)
    parts = re.split(r"(\x02|\x03)", text)
    in_nested = False

    for part in parts:
        if part == "\x02":
            in_nested = True
        elif part == "\x03":
            in_nested = False
        elif part:  # Non-empty content
            yield (in_nested, part)


def wrap_blocks_with_markers(blocks: Iterable[str]) -> Iterator[str]:
    r"""Wrap blocks with \x02 and \x03 markers."""
    yield "\x02"
    yield from blocks
    yield "\x03"
