# Tuick Task List

- **Fix reload to use errorformat**: Update reload_command to use errorformat
  parsing directly instead of split_blocks_auto(). (PLAN.md Task 2)

- **Remove obsolete parser code and tests**: Move shared test data to
  tests/test_data.py. Remove legacy parser code (State, LineType,
  BlockSplitter, split_blocks, split_blocks_auto, get_location). Delete
  test_parser.py. Update docs. (PLAN.md Tasks 3-6)

- **Build system errorformat patterns**: Replace stub patterns (%C%m, %A%m) with
  proper patterns that parse nested tool output in top mode

- REF[low]: Refactor test_cli.py to use parse_blocks() utility where manually
  parsing block streams. Search for `split("\0")` patterns in tests.

- Configurable editor commands

- UX[high]: Add allow_interspersed_args=False to command, so we do not need to
  use -- most of the time.

- UX[low]: Use execute-silent for select_command in client editors.

- FEAT[high]: Integrate with bat for preview. Possible approaches:
  1. `tuick --preview bat` as a wrapper to bat
  2. Hidden data (--with-nth) or invisible delimiters (so the path and line
     number are in fixed fields)

- **Errorformat line matching**: Current implementation uses dict mapping from
  stripped lines to original ANSI lines. This fails if duplicate stripped lines
  exist. Implement proper matching algorithm that handles:
  - Errorformat may drop invalid lines (but never adds lines)
  - Match ASCII output lines to original ANSI input lines sequentially
  - Simple forward-scan algorithm sufficient (no full diff needed)

- REF[med]: Simplify test_errorformat.py Block construction using optional
  keyword arguments instead of tuple unpacking. Make tests more readable.

- REF[med]: Refactor run_errorformat() to reduce complexity (C901: 11 > 10).
  Extract helper functions for thread management and output streaming.

- REF[med]: Refactor group_pytest_entries() to reduce complexity (C901,
  PLR0912: 14 > 12). Extract helper functions or simplify branching logic.

- REF[med]: Refactor group_ruff_entries() to reduce complexity (C901,
  PLR0912). Extract helper functions or simplify branching logic.

- REF[med]: Refactor group_entries_by_location() to reduce complexity (C901,
  PLR0912). Extract helper functions or simplify branching logic.

- REF[med]: Refactor main() to reduce complexity (C901, PLR0912: 17 > 12).
  Extract routing logic or use pattern matching.

- REF[med]: Refactor list_command() to reduce complexity (C901: 11 > 10).
  Extract setup/teardown or use helper functions.

- REF[high]: Refactor test_cli.py to reduce verbosity: factorize subprocess
  mocking setup to make tests easier to understand and maintain.

- REF[high]: Refactor existing tests that manually create ReloadSocketServer()
  to use the server_with_key fixture from conftest.py.

- REF[high]: Refactor test_cli.py to use make_cmd_proc and make_fzf_proc
  helpers, make sequence parameter optional for tests that don't track
  sequences.

- REF[med]Refactor error handling: replace print_error + raise typer.Exit with
  custom exceptions, catch in main and print with rich. (TRY301)

- REF[med]:Fix uses of generic mocks where specs could be used.

- REF[low]Find type-safe solution to avoid cast in
  ReloadRequestHandler.handle().

- FEAT[low]: Optimize output handling: use binary files for saved output instead
  of text files, use TextIOWrapper when printing to console. This avoids
  redundant decode-encode operations when streaming output through sockets and
  files.
