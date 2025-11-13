"""Tests for errorformat integration."""

from dataclasses import dataclass, replace

import pytest

from tuick.errorformat import parse_with_errorformat, split_at_markers

from .test_parser import (
    MYPY_ABSOLUTE_BLOCKS,
    MYPY_BLOCKS,
    MYPY_FANCY_BLOCKS,
    MYPY_VERY_FANCY_BLOCKS,
    PYTEST_AUTO_BLOCKS,
    PYTEST_LINE_BLOCKS,
    PYTEST_SHORT_BLOCKS,
    PYTEST_TRICKY_BLOCKS,
    RUFF_CONCISE_BLOCKS,
    RUFF_FULL_BLOCKS,
)


@dataclass
class Block:
    """Parsed errorformat block with location and content."""

    file: str = ""
    line: str = ""
    col: str = ""
    end_line: str = ""
    end_col: str = ""
    content: str = ""

    @classmethod
    def from_block(cls, block: str) -> Block:
        """Parse a null-terminated block string."""
        parts = block.split("\x1f")
        assert len(parts) == 6, f"got {len(parts)}: {block!r}"
        return cls(*parts)

    def format_for_test(self) -> str:
        """Format block for readable pytest output."""
        parts = [f"file={self.file!r}"]
        if self.line:
            parts.append(f"line={self.line!r}")
        if self.col:
            parts.append(f"col={self.col!r}")
        if self.end_line:
            parts.append(f"end_line={self.end_line!r}")
        if self.end_col:
            parts.append(f"end_col={self.end_col!r}")
        lines = [" ".join(parts)]
        lines.extend(f"  {line!r}" for line in self.content.splitlines())
        return "\n".join(lines)


MYPY_LOCATIONS: dict[str, list[tuple[str, ...]]] = {
    "simple": [
        ("src/jobsearch/search.py", "58"),
        ("tests/test_search.py", "144"),
    ],
    "fancy": [
        ("src/jobsearch/cadremploi_scraper.py", "43", "35"),
        ("src/jobsearch/cadremploi_scraper.py", "65", "32"),
    ],
    "absolute": [
        ("/path/to/src/jobsearch/cadremploi_scraper.py", "43"),
        ("/path/to/src/jobsearch/cadremploi_scraper.py", "65"),
        ("/path/to/tests/test_ollama_extraction.py", "80"),
    ],
    "very_fancy": [
        ("src/jobsearch/search.py", "58", "5", "58", "29"),
        ("tests/test_tui_checker.py", "5"),
        ("tests/test_search.py", "142", "12", "142", "23"),
        ("",),
    ],
}


@pytest.mark.parametrize(
    "test_id",
    ["simple", "fancy", "absolute", "very_fancy"],
)
def test_parse_with_errorformat_mypy(test_id: str) -> None:
    """Integration test: parse mypy output with correct locations."""
    blocks_map = {
        "simple": MYPY_BLOCKS,
        "fancy": MYPY_FANCY_BLOCKS,
        "absolute": MYPY_ABSOLUTE_BLOCKS,
        "very_fancy": MYPY_VERY_FANCY_BLOCKS,
    }
    blocks = blocks_map[test_id]
    locations = MYPY_LOCATIONS[test_id]
    input_text = "\n".join((*blocks, ""))
    input_lines = input_text.splitlines(keepends=True)
    result = "".join(parse_with_errorformat("mypy", input_lines))

    expected = [
        replace(Block(*loc), content=blocks[i])
        for i, loc in enumerate(locations)
    ]
    parsed = [Block.from_block(b) for b in result.strip("\0").split("\0")]
    expected_fmt = "\n\n".join(b.format_for_test() for b in expected)
    parsed_fmt = "\n\n".join(b.format_for_test() for b in parsed)
    assert parsed_fmt == expected_fmt


def test_parse_with_errorformat_flake8() -> None:
    """Integration test: parse flake8 output with built-in pattern."""
    flake8_output = [
        "test_flake8.py:1:1: F401 'os' imported but unused\n",
        "test_flake8.py:2:1: F401 'sys' imported but unused\n",
        "test_flake8.py:5:80: E501 line too long (93 > 79 characters)\n",
    ]
    result = "".join(parse_with_errorformat("flake8", iter(flake8_output)))

    expected = [
        Block("test_flake8.py", "1", "1", "", "", flake8_output[0].rstrip()),
        Block("test_flake8.py", "2", "1", "", "", flake8_output[1].rstrip()),
        Block("test_flake8.py", "5", "80", "", "", flake8_output[2].rstrip()),
    ]
    parsed = [Block.from_block(b) for b in result.strip("\0").split("\0")]
    expected_fmt = "\n\n".join(b.format_for_test() for b in expected)
    parsed_fmt = "\n\n".join(b.format_for_test() for b in parsed)
    assert parsed_fmt == expected_fmt


def test_parse_with_errorformat_flake8_with_ansi() -> None:
    """Integration test: flake8 with ANSI codes (requires stripping)."""
    flake8_colored = [
        "\x1b[1mtest_flake8.py\x1b[m\x1b[36m:\x1b[m1\x1b[36m:\x1b[m1"
        "\x1b[36m:\x1b[m \x1b[1m\x1b[31mF401\x1b[m 'os' imported "
        "but unused\n",
        "\x1b[1mtest_flake8.py\x1b[m\x1b[36m:\x1b[m2\x1b[36m:\x1b[m1"
        "\x1b[36m:\x1b[m \x1b[1m\x1b[31mF401\x1b[m 'sys' imported "
        "but unused\n",
    ]
    result = "".join(parse_with_errorformat("flake8", iter(flake8_colored)))

    expected = [
        Block("test_flake8.py", "1", "1", "", "", flake8_colored[0].rstrip()),
        Block("test_flake8.py", "2", "1", "", "", flake8_colored[1].rstrip()),
    ]
    parsed = [Block.from_block(b) for b in result.strip("\0").split("\0")]
    expected_fmt = "\n\n".join(b.format_for_test() for b in expected)
    parsed_fmt = "\n\n".join(b.format_for_test() for b in parsed)
    assert parsed_fmt == expected_fmt


def test_split_at_markers() -> None:
    """split_at_markers() splits nested and build-system output."""
    # Multiple marker pairs with null-terminated blocks
    input_lines = [
        "make: Entering 'src'\n",
        "\x02block1\0block2\0\x03",
        "make: Done\n",
        "\x02block3\0\x03",
    ]
    result = list(split_at_markers(input_lines))

    expected = [
        (False, "make: Entering 'src'\n"),
        (True, "block1\0block2\0"),
        (False, "make: Done\n"),
        (True, "block3\0"),
    ]
    assert result == expected


def test_split_at_markers_no_markers() -> None:
    """split_at_markers() passes through input without markers."""
    input_lines = ["line1\n", "line2\n"]
    result = list(split_at_markers(input_lines))

    assert result == [(False, "line1\nline2\n")]


PYTEST_LOCATIONS: dict[str, list[tuple[str, ...]]] = {
    "auto": [
        ("",),  # Info block: session header + FAILURES
        ("tests/test_search.py", "133"),  # test_extract_search_card error
        ("tests/test_search.py", "142"),  # test_extract_search_card_no_salary
        ("src/jobsearch/search.py", "92"),  # Traceback frame
        ("src/jobsearch/search.py", "68"),  # Traceback frame
        ("",),  # Info block: summary
    ],
    "short": [
        ("",),  # Info block: session header + FAILURES
        ("tests/test_search.py", "133"),  # test_extract_search_card error
        ("tests/test_search.py", "142"),  # test_extract_search_card_no_salary
        ("src/jobsearch/search.py", "92"),  # Traceback frame
        ("src/jobsearch/search.py", "68"),  # Traceback frame
        ("",),  # Info block: summary
    ],
    "line": [
        ("",),  # Info block: session header + FAILURES
        ("/Users/david/code/jobsearch/tests/test_search.py", "133"),
        ("/Users/david/code/jobsearch/src/jobsearch/search.py", "68"),
        ("",),  # Info block: summary
    ],
    "tricky": [
        ("",),  # Info block: FAILURES heading
        ("tests/test_cli.py", "142"),  # test_cli_reload_option with ANSI
        ("",),  # Info block: test_cli_select_verbose heading
    ],
}


@pytest.mark.parametrize(
    ("test_id", "blocks"),
    [
        ("auto", PYTEST_AUTO_BLOCKS),
        ("short", PYTEST_SHORT_BLOCKS),
        ("line", PYTEST_LINE_BLOCKS),
        ("tricky", PYTEST_TRICKY_BLOCKS),
    ],
)
def test_parse_with_errorformat_pytest(
    test_id: str, blocks: list[str]
) -> None:
    """Integration test: parse pytest output produces blocks per error."""
    locations = PYTEST_LOCATIONS[test_id]
    input_text = "\n".join((*blocks, ""))
    input_lines = input_text.splitlines(keepends=True)
    result = "".join(parse_with_errorformat("pytest", input_lines))

    expected = [
        replace(Block(*loc), content=blocks[i])
        for i, loc in enumerate(locations)
    ]
    parsed = [Block.from_block(b) for b in result.strip("\0").split("\0")]
    expected_fmt = "\n\n".join(b.format_for_test() for b in expected)
    parsed_fmt = "\n\n".join(b.format_for_test() for b in parsed)
    assert parsed_fmt == expected_fmt


RUFF_LOCATIONS: dict[str, list[tuple[str, ...]]] = {
    "full": [
        ("src/jobsearch/search_cli.py", "8", "1"),
        ("src/jobsearch/search_cli.py", "51", "5"),
        ("src/tui_checker.py", "1", "1"),
        ("tests/test_search.py", "134", "5"),
        ("",),  # Summary block
    ],
    "concise": [
        ("src/jobsearch/search_cli.py", "8", "1"),
        ("src/jobsearch/search_cli.py", "51", "5"),
        ("src/tui_checker.py", "1", "1"),
        ("",),  # Summary block
    ],
}


@pytest.mark.xfail(reason="Task 2: ruff patterns not yet implemented")
@pytest.mark.parametrize(
    ("test_id", "blocks"),
    [
        ("full", RUFF_FULL_BLOCKS),
        ("concise", RUFF_CONCISE_BLOCKS),
    ],
)
def test_parse_with_errorformat_ruff(test_id: str, blocks: list[str]) -> None:
    """Integration test: parse ruff output produces blocks per error."""
    locations = RUFF_LOCATIONS[test_id]
    input_text = "\n".join((*blocks, ""))
    input_lines = input_text.splitlines(keepends=True)
    result = "".join(parse_with_errorformat("ruff", input_lines))

    expected = [
        replace(Block(*loc), content=blocks[i])
        for i, loc in enumerate(locations)
    ]
    parsed = [Block.from_block(b) for b in result.strip("\0").split("\0")]
    expected_fmt = "\n\n".join(b.format_for_test() for b in expected)
    parsed_fmt = "\n\n".join(b.format_for_test() for b in parsed)
    assert parsed_fmt == expected_fmt
