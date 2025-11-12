"""Errorformat tool detection."""

from pathlib import Path


class UnknownToolError(KeyError):
    """Tool not found in errorformat registry."""


# Known tools that have errorformat definitions
# Add tools here as errorformat support is implemented
KNOWN_TOOLS: set[str] = {"mypy"}


def detect_tool(command: list[str]) -> str:
    """Extract tool name from command, stripping path prefix if present."""
    return Path(command[0]).name


def is_known_tool(tool: str) -> bool:
    """Check if tool has errorformat support."""
    return tool in KNOWN_TOOLS
