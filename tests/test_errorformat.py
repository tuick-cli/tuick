"""Tests for errorformat integration."""

import subprocess

import pytest

from tuick.errorformat import parse_with_errorformat


@pytest.mark.skipif(
    subprocess.run(
        ["which", "errorformat"], capture_output=True, check=False
    ).returncode
    != 0,
    reason="errorformat not installed",
)
@pytest.mark.xfail(reason="errorformat output format needs investigation")
def test_parse_with_errorformat_mypy() -> None:
    """Integration test: parse mypy output with errorformat."""
    mypy_output = [
        "src/test.py:10:5: error: Missing type annotation\n",
        "src/foo.py:20: note: Some note\n",
        "Consider using --strict mode\n",
    ]

    result = "".join(parse_with_errorformat("mypy", iter(mypy_output)))

    # Exact output: null-terminated blocks with unit-separator fields
    # Block 1: full location (file, line, col)
    # Block 2: partial location (file, line, no col)
    # Block 3: no location (informational message) - empty fields
    expected = (
        "src/test.py\x1f10\x1f5\x1f\x1f\x1f"
        "src/test.py:10:5: error: Missing type annotation\0"
        "src/foo.py\x1f20\x1f\x1f\x1f\x1f"
        "src/foo.py:20: note: Some note\0"
        "\x1f\x1f\x1f\x1f\x1fConsider using --strict mode\0"
    )
    assert result == expected
