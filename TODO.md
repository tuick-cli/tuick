# Tuick Task List

- BUG[med]: Create custom Popen subclass with thread-safe wait(): add lock
  around wait() method since it can be called from main thread (normal
  completion) or reload server thread (termination).

- BUG[med]: Fix race condition in reload server: catch ProcessLookupError from
  .terminate() to handle process that already completed. The proc.poll() check
  before proc.terminate() is insufficient.

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

- FEAT[low]: Optimize output handling: use binary files for saved output
  instead of text files, use TextIOWrapper when printing to console. This
  avoids redundant decode-encode operations when streaming output through
  sockets and files.

- FEAT[low]: Enable filtering.
  - That (probably) implies removing the "zero:abort" binding.
  - If a reload (manual or automatic) command produces no output, kill fzf
  - For the case of a manual reload, that requires IPC between the reload
    command and the top command, probably through a unix socket.
