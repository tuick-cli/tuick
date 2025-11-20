"""Tests for errorformat tool detection."""

from tuick.tool_registry import detect_tool, is_build_system, is_known_tool


def test_detect_tool() -> None:
    """detect_tool() extracts tool name, stripping path prefix."""
    assert detect_tool(["ruff", "check"]) == "ruff"
    assert detect_tool(["/usr/bin/ruff", "check"]) == "ruff"
    assert detect_tool(["./venv/bin/mypy", "."]) == "mypy"
    assert detect_tool(["dmypy", "run"]) == "mypy"


def test_is_known_tool() -> None:
    """is_known_tool() returns True for known tools."""
    assert is_known_tool("ruff")
    assert is_known_tool("mypy")


def test_not_is_known_tool() -> None:
    """is_known_tool() returns False for unknown tools."""
    assert not is_known_tool("nonexistent")


def test_is_build_system() -> None:
    """is_build_system() returns True for known build systems."""
    assert is_build_system("make")
    assert is_build_system("just")
    assert is_build_system("cmake")
    assert is_build_system("ninja")
    assert is_build_system(detect_tool(["gmake"]))


def test_not_is_build_system() -> None:
    """is_build_system() returns False for non-build-systems."""
    assert not is_build_system("ruff")
    assert not is_build_system("mypy")
    assert not is_build_system("nonexistent")
