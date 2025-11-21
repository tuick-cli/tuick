"""ANSI escape code utilities."""

import re

# ANSI escape code regex pattern
ANSI_REGEX = re.compile(
    r"""
    \x1b              # ESC character (0x1b)
    (?:
        \[            # CSI - Control Sequence Introducer
        [0-?]*        # Parameter bytes (optional): 0-9 : ; < = > ?
        [ -/]*        # Intermediate bytes (optional): space through /
        [@-~]         # Final byte: the actual command (m, H, J, K, etc.)
        |
        \(            # SCS G0 - Select Character Set
        [B0UK]        # B=ASCII, 0=line drawing, U=null, K=user
        |
        \)            # SCS G1 - Select Character Set
        [B0UK]        # Same options as G0
        |
        [@-Z\\-_]     # Fe sequences: two-byte escapes
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
