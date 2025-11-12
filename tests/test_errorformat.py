"""Tests for errorformat integration."""

from tuick.errorformat import parse_with_errorformat


def test_parse_with_errorformat_mypy() -> None:
    """Integration test: parse mypy output with errorformat."""
    # Real mypy output from test_parser.py test data
    mypy_output = [
        "src/jobsearch/search.py:58: error: Returning Any from function...\n",
        "src/jobsearch/cadremploi_scraper.py:43:35: error: Missing type "
        'parameters for "dict"  [type-arg]\n',
        "    def extract_json_ld(html: str) -> dict | None:\n",
        "                                      ^\n",
        "tests/test_search.py:144: error: Non-overlapping equality check...\n",
        "Found 8 errors in 6 files (checked 20 source files)\n",
    ]

    result = "".join(parse_with_errorformat("mypy", iter(mypy_output)))

    # Block 1: file:line (no column)
    # Block 2: file:line:col with 2 continuation lines (multi-line)
    # Block 3: file:line (no column)
    # Block 4: informational message (no location, valid=true via %G)
    expected = (
        "src/jobsearch/search.py\x1f58\x1f\x1f\x1f\x1f"
        "src/jobsearch/search.py:58: error: Returning Any from "
        "function...\0"
        "src/jobsearch/cadremploi_scraper.py\x1f43\x1f35\x1f\x1f\x1f"
        "src/jobsearch/cadremploi_scraper.py:43:35: error: Missing type "
        'parameters for "dict"  [type-arg]\n'
        "    def extract_json_ld(html: str) -> dict | None:\n"
        "                                      ^\0"
        "tests/test_search.py\x1f144\x1f\x1f\x1f\x1f"
        "tests/test_search.py:144: error: Non-overlapping equality "
        "check...\0"
        "\x1f\x1f\x1f\x1f\x1f"
        "Found 8 errors in 6 files (checked 20 source files)\0"
    )
    assert result == expected


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
