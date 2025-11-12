"""ANSI escape code utilities."""

import re

# ANSI escape code regex pattern
ANSI_REGEX = re.compile(
    r"""
    \x1b  # ESC
    (?:
        [@-Z\\-_]  # Fe sequences: ESC + single byte (ESC M, ESC 7, etc.)
        |
        \[         # CSI sequences: ESC [ params intermediates final
        [0-?]*     # Parameter bytes (optional)
        [ -/]*     # Intermediate bytes (optional)
        [@-~]      # Final byte
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
