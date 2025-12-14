# Tuick Task List

- BUG[med] Errorformat line matching: Current implementation uses dict mapping
  from stripped lines to original ANSI lines. This fails if duplicate stripped
  lines exist. Implement proper matching algorithm that handles:
  - Errorformat may drop invalid lines (but never adds lines)
  - Match ASCII output lines to original ANSI input lines sequentially
  - Simple forward-scan algorithm sufficient (no full diff needed)

- FEAT[med] Build system errorformat patterns: Replace stub patterns (%C%m,
  %A%m) with proper patterns that parse nested tool output in top mode, build
  system errors that point to build system files must be linked to the location.

- REF[med]: Refactor test_cli.py to use parse_blocks() utility where manually
  parsing block streams. Search for `split("\0")` patterns in tests.

- REF[med]: Simplify test_errorformat.py Block construction using optional
  keyword arguments instead of tuple unpacking. Make tests more readable.

- REF[med]: Refactor run_errorformat() to reduce complexity (C901: 11 > 10).
  Extract helper functions for thread management and output streaming.

- REF[med]: Refactor group_pytest_entries() to reduce complexity (C901, PLR0912:
  14 > 12). Extract helper functions or simplify branching logic.

- REF[med]: Refactor group_ruff_entries() to reduce complexity (C901, PLR0912).
  Extract helper functions or simplify branching logic.

- REF[med]: Refactor group_entries_by_location() to reduce complexity (C901,
  PLR0912). Extract helper functions or simplify branching logic.

- REF[med]: Refactor main() to reduce complexity (C901, PLR0912: 17 > 12).
  Extract routing logic or use pattern matching.

- REF[med]: Refactor list_command() to reduce complexity (C901, PLR0913,
  PLR0915). Extract setup/teardown or use helper functions. Theme parameter
  added, increasing argument count.

- REF[high]: Refactor test_cli.py to reduce verbosity: factorize subprocess
  mocking setup to make tests easier to understand and maintain.

- REF[high]: Refactor existing tests that manually create ReloadSocketServer()
  to use the server_with_key fixture from conftest.py.

- REF[high]: Refactor test_cli.py to use make_cmd_proc and make_fzf_proc
  helpers, make sequence parameter optional for tests that don't track
  sequences.

- REF[med]Refactor error handling: replace print_error + raise typer.Exit with
  custom exceptions, catch in main and print with rich.

- REF[med]:Fix uses of generic mocks where specs could be used.

- UX[low]: Use execute-silent for select_command in client editors.

- FEAT[low]: Optimize output handling: use binary files for saved output instead
  of text files, use TextIOWrapper when printing to console. This avoids
  redundant decode-encode operations when streaming output through sockets and
  files.
