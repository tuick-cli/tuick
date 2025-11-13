# Tuick Task List

- **Group errorformat entries by location**: errorformat splits multi-line
  blocks into separate entries (mypy note lines, continuation lines). Add
  post-processing in parse_with_errorformat() to group entries by location.
  Attach note: lines (no line number) to next error at same file. See
  test_parse_with_errorformat_mypy[fancy/very_fancy] xfail tests.

- **Port existing parser patterns to errorformat**: parser.py contains regex
  patterns for ruff, pytest, mypy notes, etc. Port these to errorformat
  patterns in tool_registry.py (BUILTIN_TOOLS or CUSTOM_PATTERNS).

- **Errorformat line matching**: Current implementation uses dict mapping from
  stripped lines to original ANSI lines. This fails if duplicate stripped lines
  exist. Implement proper matching algorithm that handles:
  - Errorformat may drop invalid lines (but never adds lines)
  - Match ASCII output lines to original ANSI input lines sequentially
  - Simple forward-scan algorithm sufficient (no full diff needed)

- REF[med]: Refactor main() to reduce complexity (C901, PLR0912: 17 > 12).
  Extract routing logic or use pattern matching.

- REF[med]: Refactor list_command() to reduce complexity (C901: 11 > 10).
  Extract setup/teardown or use helper functions.

- Configurable editor commands

- QA[high]:Test editors with CLI integration. (Already tested code, surf,
  cursor, idea, pycharm, micro)

- QA[med]: Test editors with URL integration, on Mac/Linux/Windows.

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

- UX[high]: Add allow_interspersed_args=False to command, so we do not need to
  use -- most of the time.

- UX[low]: Use execute-silent for select_command in client editors.

- FEAT[high]: Integrate with bat for preview. Possible approaches:
  1. `tuick --preview bat` as a wrapper to bat
  2. Hidden data (--with-nth) or invisible delimiters (so the path and line
     number are in fixed fields)

- FEAT[low]: Optimize output handling: use binary files for saved output instead
  of text files, use TextIOWrapper when printing to console. This avoids
  redundant decode-encode operations when streaming output through sockets and
  files.

- FEAT[low]: Enable filtering.
  - That (probably) implies removing the "zero:abort" binding.
  - If a reload (manual or automatic) command produces no output, kill fzf
  - For the case of a manual reload, that requires IPC between the reload
    command and the top command, probably through a unix socket.
