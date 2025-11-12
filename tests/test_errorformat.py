"""Tests for errorformat integration."""

import pytest

from tuick.errorformat import parse_with_errorformat

from .test_parser import (
    MYPY_ABSOLUTE_BLOCKS,
    MYPY_BLOCKS,
    MYPY_FANCY_BLOCKS,
    MYPY_VERY_FANCY_BLOCKS,
)


@pytest.mark.parametrize(
    "blocks",
    [
        pytest.param(MYPY_BLOCKS, id="simple"),
        pytest.param(
            MYPY_FANCY_BLOCKS,
            id="fancy",
            marks=pytest.mark.xfail(reason="needs block grouping by location"),
        ),
        pytest.param(MYPY_ABSOLUTE_BLOCKS, id="absolute"),
        pytest.param(
            MYPY_VERY_FANCY_BLOCKS[:-1],
            id="very_fancy",
            marks=pytest.mark.xfail(reason="needs block grouping by location"),
        ),
    ],
)
def test_parse_with_errorformat_mypy(blocks: list[str]) -> None:
    """Integration test: parse mypy output produces one block per location."""
    input_text = "\n".join((*blocks, ""))
    input_lines = input_text.splitlines(keepends=True)
    result = list(parse_with_errorformat("mypy", input_lines))

    # Should produce one block per input block (same count)
    assert len(result) == len(blocks)

    # Each result block should contain all lines from input block
    for i, block in enumerate(blocks):
        # Extract content field (after 5 \x1f delimiters)
        content = result[i].split("\x1f")[5].rstrip("\0")
        # Content should match original block
        assert content == block.rstrip("\n") or content in block


def test_parse_with_errorformat_flake8() -> None:
    """Integration test: parse flake8 output with built-in pattern."""
    # Real flake8 output from running on test file
    flake8_output = [
        "test_flake8.py:1:1: F401 'os' imported but unused\n",
        "test_flake8.py:2:1: F401 'sys' imported but unused\n",
        "test_flake8.py:5:80: E501 line too long (93 > 79 characters)\n",
    ]

    result = "".join(parse_with_errorformat("flake8", iter(flake8_output)))

    # Each error is a single-line block with file:line:col location
    expected = (
        "test_flake8.py\x1f1\x1f1\x1f\x1f\x1f"
        "test_flake8.py:1:1: F401 'os' imported but unused\0"
        "test_flake8.py\x1f2\x1f1\x1f\x1f\x1f"
        "test_flake8.py:2:1: F401 'sys' imported but unused\0"
        "test_flake8.py\x1f5\x1f80\x1f\x1f\x1f"
        "test_flake8.py:5:80: E501 line too long (93 > 79 characters)\0"
    )
    assert result == expected


def test_parse_with_errorformat_flake8_with_ansi() -> None:
    """Integration test: flake8 with ANSI codes (requires stripping)."""
    # Real flake8 --color=always output
    flake8_colored = [
        "\x1b[1mtest_flake8.py\x1b[m\x1b[36m:\x1b[m1\x1b[36m:\x1b[m1"
        "\x1b[36m:\x1b[m \x1b[1m\x1b[31mF401\x1b[m 'os' imported "
        "but unused\n",
        "\x1b[1mtest_flake8.py\x1b[m\x1b[36m:\x1b[m2\x1b[36m:\x1b[m1"
        "\x1b[36m:\x1b[m \x1b[1m\x1b[31mF401\x1b[m 'sys' imported "
        "but unused\n",
    ]

    result = "".join(parse_with_errorformat("flake8", iter(flake8_colored)))

    # ANSI codes preserved in output, but location still parsed
    expected = (
        "test_flake8.py\x1f1\x1f1\x1f\x1f\x1f"
        "\x1b[1mtest_flake8.py\x1b[m\x1b[36m:\x1b[m1\x1b[36m:\x1b[m1"
        "\x1b[36m:\x1b[m \x1b[1m\x1b[31mF401\x1b[m 'os' imported but unused\0"
        "test_flake8.py\x1f2\x1f1\x1f\x1f\x1f"
        "\x1b[1mtest_flake8.py\x1b[m\x1b[36m:\x1b[m2\x1b[36m:\x1b[m1"
        "\x1b[36m:\x1b[m \x1b[1m\x1b[31mF401\x1b[m 'sys' imported but unused\0"
    )
    assert result == expected
