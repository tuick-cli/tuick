"""Shared console instances for tuick."""

import os
import sys
import traceback
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import IO, TYPE_CHECKING, Any

from rich.console import Console
from rich.markup import escape

from tuick.editor import EditorCommand
from tuick.shell import quote_command_words

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


TUICK_LOG_FILE = "TUICK_LOG_FILE"


_console = Console(soft_wrap=True, stderr=True)
_verbose = False
_trace = False


def set_verbose() -> None:
    """Turn on verbose mode.

    Note: Tests use autouse fixture reset_verbose to clear between tests.
    """
    global _verbose  # noqa: PLW0603
    _verbose = True


def is_verbose() -> bool:
    """Check if verbose mode is enabled."""
    return _verbose


def print_verbose(*args: Any) -> None:  # noqa: ANN401
    """Print general verbose messages."""
    if _verbose:
        _console.print(*args, style="dim")
        _console.file.flush()


def print_trace(*args: Any) -> None:  # noqa: ANN401
    """Print trace messages (extra verbose)."""
    if _trace:
        _console.print(*args, style="dim")
        _console.file.flush()


def print_exception() -> None:
    """Print exception with traceback and local variables."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        traceback.print_exc(file=_console.file)
        return
    _console.print_exception(show_locals=True)
    _console.file.flush()


def print_entry(command: list[str]) -> None:
    """Print a process entry event, verbose mode."""
    if _verbose:
        _console.print("[bold]>", *_style_command(command))
        _console.file.flush()


def print_event(message: str) -> None:
    """Print an event message, verbose mode."""
    if _verbose:
        _console.print("[bold]>", escape(message), style="magenta")
        _console.file.flush()


def print_command(command: list[str] | EditorCommand) -> None:
    """Print a command to be executed, verbose mode."""
    if not _verbose:
        return
    if isinstance(command, EditorCommand):
        command = command.command_words()
    words = _style_command(command)
    _console.print("  [bold]$", *words, style="dim")
    _console.file.flush()


def _style_command(command: list[str]) -> Iterable[str]:
    escaped = (escape(x) for x in quote_command_words(command))
    return (
        _style_shell_word(word, first=i == 0) for i, word in enumerate(escaped)
    )


def _style_shell_word(word: str, *, first: bool) -> str:
    """Style a shell word."""
    if not word:
        return ""
    if "\n" in word:
        closing = ""
        if word[0] == word[-1] and word[0] in "'\"":
            closing = word[0]
        word = word.split("\n", 1)[0] + "[bold red]···[/]" + closing
    if first:
        return f"[bold]{word}"
    # Do not overdo it, or we will miss out on rich built-in highlighting
    return word


def print_success(*args: Any) -> None:  # noqa: ANN401
    """Print a success message."""
    if _verbose:
        _console.print(*args, style="blue")
        _console.file.flush()


def print_warning(*args: Any) -> None:  # noqa: ANN401
    """Print a warning message."""
    if _verbose:
        _console.print(*args, style="yellow")
        _console.file.flush()


def print_error(title: str | None, *args: Any) -> None:  # noqa: ANN401
    """Print an error message."""
    title = title or "Error:"
    _console.print(f"[bold]{title}", *args, style="red")
    _console.file.flush()


@contextmanager
def setup_log_file() -> Iterator[None]:
    """Configure console to use the log file specified in TUICK_LOG_FILE.

    Close the file and revert the console configuration when done.

    If TUICK_LOG_FILE is not set, we are in a top-level tuick command, create a
    log file and set TUICK_LOG_FILE so that child processes can use it, then
    copy the log file to stderr when done.
    """
    with _open_log_file() as (append_file, read_file):
        saved_file = _console.file
        _console.file = append_file
        try:
            yield
        finally:
            _console.file = saved_file
            if read_file:
                while chunk := read_file.read(64 * 1024):
                    sys.stderr.write(chunk)


@contextmanager
def _open_log_file() -> Iterator[tuple[IO[str], IO[str] | None]]:
    env_path = os.environ.get(TUICK_LOG_FILE)
    if env_path:
        # Open the log file if it is set in TUICK_LOG_FILE
        try:
            with Path(env_path).open("a") as append_file:
                yield append_file, None
        except OSError as error:
            print_error("Error opening log file:", error)
            raise SystemExit(1) from error
    else:
        # If TUICK_LOG_FILE is not set, create a temporary log file.
        with (
            NamedTemporaryFile("r", prefix="tuick-", suffix=".log") as tmpfile,
            Path(tmpfile.name).open("a") as append_file,
        ):
            os.environ[TUICK_LOG_FILE] = tmpfile.name
            yield append_file, tmpfile
