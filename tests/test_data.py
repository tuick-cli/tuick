"""Shared test data for parser and errorformat tests."""

MYPY_BLOCKS = [
    "src/jobsearch/search.py:58: error: Returning Any from function...",
    "tests/test_search.py:144: error: Non-overlapping equality check...",
]

# uv run --no-sync mypy --show-column-numbers --pretty --show-error-context
#
# --pretty turns on soft word wrap, and location marker. That makes messages
# multi-line. Error blocks start with a message with at least a line number.
#
# --show-error-context adds a leading note. A "note" message without line
# number is context, it indicates the start of a block.
MYPY_FANCY_BLOCKS = [
    """\
src/jobsearch/cadremploi_scraper.py: note: In function "extract_json_ld":
src/jobsearch/cadremploi_scraper.py:43:35: error: Missing type parameters fo...
"dict"  [type-arg]
    def extract_json_ld(html: str) -> dict | None:
                                      ^\
""",
    """\
src/jobsearch/cadremploi_scraper.py: note: In function "parse_job_posting":
src/jobsearch/cadremploi_scraper.py:65:32: error: Missing type parameters fo...
"dict"  [type-arg]
    def parse_job_posting(json_ld: dict, url: str) -> dict:
                                   ^""",
]

# uv run --no-sync mypy --show-absolute-path
MYPY_ABSOLUTE_BLOCKS = [
    "/path/to/src/jobsearch/cadremploi_scraper.py:43: error: Missing type ...",
    "/path/to/src/jobsearch/cadremploi_scraper.py:65: error: Missing type ...",
    "/path/to/tests/test_ollama_extraction.py:80: error: Missing type para...",
]

# mypy --pretty --show-error-context --show-error-code-links
# --show-column-numbers
#
# --show-error-code-links adds a "note" message with the same location as the
# previous error after the location marker. Multiple messages with the same
# location must be grouped.
MYPY_VERY_FANCY_BLOCKS = [
    """\
src/jobsearch/search.py: note: In function "select_one_text":
src/jobsearch/search.py:58:5:58:29: error: Returning Any from function decla...
        return inner.text.strip()
        ^~~~~~~~~~~~~~~~~~~~~~~~~
src/jobsearch/search.py:58:5:58:29: note: See https://mypy.rtfd.io/en/stabl...\
""",
    """\
tests/test_tui_checker.py:5: error: Unused "type: ignore" comment  [unused-i...
    from tui_checker import split_blocks  # type: ignore[import-untyped]
    ^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\
""",
    """\
tests/test_search.py: note: In function "test_extract_search_card_no_salary":
tests/test_search.py:142:12:142:23: error: Non-overlapping equality check (l...
"SearchCard", right operand type: "dict[Never, Never]")  [comparison-overlap]
        assert result == {}
               ^~~~~~~~~~~~
tests/test_search.py:142:12:142:23: note: See https://mypy.rtfd.io/en/stabl...\
""",
    """\
Found 8 errors in 6 files (checked 20 source files)""",
]

RUFF_FULL_BLOCKS = [
    '''\
I001 [*] Import block is un-sorted or un-formatted
  --> src/jobsearch/search_cli.py:8:1
   |
 6 |   """
 7 |
 8 | / from __future__ import annotations
28 | | from .types import JobEntry, ProcessedJob
   | |_________________________________________^
29 |
30 |   DATA_DIR = Path("data")
   |
help: Organize imports
''',
    '''\
C901 `run_urls_file_workflow` is too complex (11 > 10)
  --> src/jobsearch/search_cli.py:51:5
   |
51 | def run_urls_file_workflow(...) -> None:
   |     ^^^^^^^^^^^^^^^^^^^^^^
52 |     """Scrape job pages from a file of URLs and postprocess."""
   |
''',
    """\
D100 Missing docstring in public module
--> src/tui_checker.py:1:1
""",
    """\
PT015 Assertion always fails, replace with `pytest.fail()`
   --> tests/test_search.py:134:5
    |
132 |     }
133 |     raise ValueError
134 |     assert False
    |     ^^^^^^^^^^^^
    |
""",
    """\
Found 12 errors.
[*] 3 fixable with the `--fix` option (...).""",
]

RUFF_CONCISE_BLOCKS = [
    "src/jobsearch/search_cli.py:8:1: I001 [*] Import block is un-sorted o...",
    "src/jobsearch/search_cli.py:51:5: C901 `run_urls_file_workflow` is to...",
    "src/tui_checker.py:1:1: D100 Missing docstring in public module",
    """\
Found 12 errors.
[*] 3 fixable with the `--fix` option (4 hidden fixes can be enabled wit...""",
]

PYTEST_AUTO_BLOCKS = [
    """\
============================= test session starts =============================
platform darwin -- Python 3.13.3, pytest-8.4.2, pluggy-1.6.0
...
tests/test_wait_for_load.py ..                                           [100%]

=================================== FAILURES ==============================""",
    """\
___________________________ test_extract_search_card __________________________

    def test_extract_search_card():
        ...
>       raise ValueError
E       ValueError

tests/test_search.py:133: ValueError\
""",
    """\
______________________ test_extract_search_card_no_salary _____________________

    def test_extract_search_card_no_salary():
        ...
>       result = extract_search_card(card)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^

tests/test_search.py:142: """,
    """\
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
src/jobsearch/search.py:92: in extract_search_card
    contract_type = select_first_text(card, "h3 + div > div:nth-child(2) p")
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^""",
    """\
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

tag = <div class="job-posting-card">
...
selector = 'h3 + div > div:nth-child(2) p'

    def select_first_text(tag: Tag, selector: str) -> str:
        ...
        if not tags:
>           raise SelectorNotFoundError(selector)
E           jobsearch.search.SelectorNotFoundError: Not found: h3 + div > di...

src/jobsearch/search.py:68: SelectorNotFoundError""",
    """\
=========================== short test summary info ===========================
FAILED tests/test_search.py::test_extract_search_card - ValueError
FAILED tests/test_search.py::test_extract_search_card_no_salary - jobsearch....
========================= 2 failed, 32 passed in 4.97s ====================""",
]

# Pytest --tb=long output is a subset of auto, no need to test separately

PYTEST_SHORT_BLOCKS = [
    """\
============================= test session starts =============================
platform darwin -- Python 3.13.3, pytest-8.4.2, pluggy-1.6.0
...
tests/test_wait_for_load.py ..                                           [100%]

=================================== FAILURES ==============================""",
    """\
___________________________ test_extract_search_card __________________________
tests/test_search.py:133: in test_extract_search_card
    raise ValueError
E   ValueError""",
    """\
______________________ test_extract_search_card_no_salary _____________________
tests/test_search.py:142: in test_extract_search_card_no_salary
    result = extract_search_card(card)
             ^^^^^^^^^^^^^^^^^^^^^^^^^""",
    """\
src/jobsearch/search.py:92: in extract_search_card
    contract_type = select_first_text(card, "h3 + div > div:nth-child(2) p")
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^""",
    """\
src/jobsearch/search.py:68: in select_first_text
    raise SelectorNotFoundError(selector)
E   jobsearch.search.SelectorNotFoundError: Not found: h3 + div > div:nth-c""",
    """\
=========================== short test summary info ===========================
FAILED tests/test_search.py::test_extract_search_card - ValueError
FAILED tests/test_search.py::test_extract_search_card_no_salary - jobsearch....
========================= 2 failed, 32 passed in 4.99s ====================""",
]

PYTEST_LINE_BLOCKS = [
    """\
============================= test session starts =============================
platform darwin -- Python 3.13.3, pytest-8.4.2, pluggy-1.6.0
...
tests/test_wait_for_load.py ..                                           [100%]

=================================== FAILURES ==============================""",
    "/Users/david/code/jobsearch/tests/test_search.py:133: ValueError",
    "/Users/david/code/jobsearch/src/jobsearch/search.py:68: jobsearch.sea...",
    """\
=========================== short test summary info ===========================
FAILED tests/test_search.py::test_extract_search_card - ValueError
FAILED tests/test_search.py::test_extract_search_card_no_salary - jobsearch....
========================= 2 failed, 32 passed in 4.93s ====================""",
]

# Interesting edge case, the assert report contains something that looks like a
# location, and the line starts with a non-whitespace, so naively matching for
# lines that look like locations succeeds but should not. In addition, the text
# may contain ANSI escape codes.
PYTEST_TRICKY_BLOCKS = [
    "============================ FAILURES =============================",
    """\
\x1b[31m\x1b[1m_______________ test_cli_reload_option _______________\x1b[0m
\x1b[1m\x1b[31mtests/test_cli.py\x1b[0m:142: in test_cli_reload_option
    \x1b[0m\x1b[94massert\x1b[39;49;00m result.stdout == \
\x1b[33m"\x1b[39;49;00m\x1b[33msrc/test.py:1: error: Test\
\x1b[39;49;00m\x1b[33m"\x1b[39;49;00m\x1b[90m\x1b[39;49;00m
\x1b[1m\x1b[31mE   AssertionError: assert equals failed\x1b[0m
\x1b[1m\x1b[31mE     \x1b[m\x1b[1;31m''\x1b[m                            \
\x1b[1;32m'src/test.py:1: error: Test'\x1b[m\x1b[0m""",
    "\x1b[31m\x1b[1m___________ test_cli_select_verbose ____________\x1b[0m",
]
