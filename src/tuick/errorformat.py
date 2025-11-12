"""Errorformat integration for parsing tool output."""

import json
import shutil
import subprocess
import typing
from dataclasses import dataclass

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


def run_errorformat(
    tool: str, input_lines: Iterable[str]
) -> Iterator[ErrorformatEntry]:
    """Run errorformat subprocess, yield parsed entries.

    Args:
        tool: Tool name (mypy, etc.) matching errorformat -name option
        input_lines: Tool output lines (with ANSI codes)

    Yields:
        ErrorformatEntry objects

    Raises:
        ErrorformatNotFoundError: If errorformat not in PATH
        subprocess.CalledProcessError: If errorformat fails
    """
    if shutil.which("errorformat") is None:
        raise ErrorformatNotFoundError

    cmd = ["errorformat", "-w=jsonl", f"-name={tool}"]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    input_text = "".join(input_lines)
    stdout, stderr = proc.communicate(input_text)

    if proc.returncode != 0:
        raise subprocess.CalledProcessError(
            proc.returncode, cmd, stderr=stderr
        )

    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
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
        except json.JSONDecodeError:
            continue


def format_block_from_entry(entry: ErrorformatEntry) -> str:
    r"""Format errorformat entry as tuick block.

    Block format: file\x1fline\x1fcol\x1fend-line\x1fend-col\x1ftext\0
    """
    text = "\n".join(entry.lines)
    line_str = str(entry.lnum) if entry.lnum is not None else ""
    col_str = str(entry.col) if entry.col is not None else ""
    return f"{entry.filename}\x1f{line_str}\x1f{col_str}\x1f\x1f\x1f{text}\0"


def parse_with_errorformat(tool: str, lines: Iterable[str]) -> Iterator[str]:
    """Parse tool output with errorformat, yield block chunks.

    Args:
        tool: Tool name matching errorformat -name option
        lines: Tool output lines

    Yields:
        Null-terminated block chunks
    """
    for entry in run_errorformat(tool, lines):
        yield format_block_from_entry(entry)
