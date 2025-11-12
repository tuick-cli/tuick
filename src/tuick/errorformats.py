"""Errorformat tool detection."""

from pathlib import Path


class UnknownToolError(KeyError):
    """Tool not found in errorformat registry."""


# Tools using errorformat built-in patterns (-name=tool)
BUILTIN_TOOLS: set[str] = {"flake8"}

# Custom errorformat patterns for tools without built-in support
CUSTOM_PATTERNS: dict[str, list[str]] = {}

# Override patterns for tools with inadequate built-in patterns
# mypy - built-in doesn't handle --show-column-numbers or multi-line blocks
OVERRIDE_PATTERNS: dict[str, list[str]] = {
    "mypy": [
        "%E%f:%l:%c: %m",  # file:line:col: msg (start multi-line error)
        "%E%f:%l: %m",  # file:line: msg (start multi-line error)
        "%+C    %.%#",  # continuation: 4 spaces + anything
        "%G%.%#",  # general/informational lines (preserved)
    ],
}

# All known tools with errorformat support
KNOWN_TOOLS: set[str] = (
    BUILTIN_TOOLS | set(CUSTOM_PATTERNS) | set(OVERRIDE_PATTERNS)
)


def detect_tool(command: list[str]) -> str:
    """Extract tool name from command, stripping path prefix if present."""
    return Path(command[0]).name


def is_known_tool(tool: str) -> bool:
    """Check if tool has errorformat support."""
    return tool in KNOWN_TOOLS
