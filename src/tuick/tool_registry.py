"""Errorformat tool detection."""

from pathlib import Path


class UnknownToolError(KeyError):
    """Tool not found in errorformat registry."""


# Tools using errorformat built-in patterns (-name=tool)
BUILTIN_TOOLS: set[str] = {"flake8"}

# Build system stub: groups all output into informative blocks
stub_build_format = ["%C%m", "%A%m"]

# Custom errorformat patterns for tools without built-in support
CUSTOM_PATTERNS: dict[str, list[str]] = {
    "make": stub_build_format,
    "just": stub_build_format,
    "cmake": stub_build_format,
    "ninja": stub_build_format,
    "pytest": [
        "%E%f:%l: %m",  # tests/test_search.py:133: ValueError
        "%E%f:%l: ",  # 'tests/test_search.py:142: '
        "%G=%#%m%#=%#",  # ===== FAILURES =====
        "%G_%#%m%#_%#",  # _____ test_name _____
        "%C%s%m",  # continuation (indented or traceback)
    ],
    "ruff": [
        # Concise format: src/file.py:8:1: I001 Message
        "%E%f:%l:%c: %m",
        # Full format: error code + message starts multiline block
        r"%E%[A-Z]\+%[0-9]\+ %.%#",
        # Full format: location line upgrades block with file:line:col
        "%C %#--> %f:%l:%c",
        # Full format: code snippet lines (line number | code)
        r"%C %#%[0-9]%# \+|%.%#",
        # Full format: optional help message after snippet
        "%Chelp: %.%#",
        # Full format: blank line ends block
        "%Z",
        # Success summary
        "%GAll checks passed!",
        # Failure summary, fixes summary on following line
        r"%AFound %[0-9]\+ error%.%#",
        "%CNo fixes available %.%#",
        r"%C[*] %[0-9]\+ fixable %.%#",
        "%+C%.%#",
    ],
}

# Override patterns for tools with inadequate built-in patterns
# mypy - built-in doesn't handle --show-column-numbers or multi-line blocks
OVERRIDE_PATTERNS: dict[str, list[str]] = {
    "mypy": [
        # file:line:col:end_line:end_col: type: msg
        "%E%f:%l:%c:%e:%k: %t%*[a-z]: %m",
        "%E%f:%l:%c: %t%*[a-z]: %m",  # file:line:col: type: msg
        "%E%f:%l: %t%*[a-z]: %m",  # file:line: type: msg
        "%I%f: %t%*[a-z]: %m",  # file: type: msg (note, no line number)
        "%GFound %.%# error%.%# in %.%# file%.%#",  # error summary
        "%GSuccess: no issues found%.%#",  # success summary
        "%C%.%#",  # continuation (indented and wrapped)
    ],
}

# All known tools with errorformat support
KNOWN_TOOLS: set[str] = (
    BUILTIN_TOOLS | set(CUSTOM_PATTERNS) | set(OVERRIDE_PATTERNS)
)

# Build systems that orchestrate nested tuick commands
BUILD_SYSTEMS: set[str] = {"make", "just", "cmake", "ninja"}

# Command aliases: commands that should use another tool's errorformat
COMMAND_ALIASES: dict[str, str] = {
    "dmypy": "mypy",
    "gmake": "make",
}


def detect_tool(command: list[str]) -> str:
    """Extract tool name, stripping path prefix and resolving aliases."""
    tool = Path(command[0]).name
    return COMMAND_ALIASES.get(tool, tool)


def is_known_tool(tool: str) -> bool:
    """Check if tool has errorformat support."""
    return tool in KNOWN_TOOLS


def is_build_system(tool: str) -> bool:
    """Check if tool is a known build system."""
    return tool in BUILD_SYSTEMS
