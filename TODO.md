# Tuick Task List

- Integration with reviewdog/errorformat. Maybe need to integrate custom regex
  for ruff and pytest.

  We are adding a dependency, you will do careful analysis on whether we use
  reviewdog or errorformat. The plan is to add a new option, for tuick command
  inside the build scripts to parse errors with a syntax chosen based on the
  build command line passed in arguments. Name of the option TBD. We want to
  group related lines to display multi-line errors for a single location as
  multi-line blocks. So reload will go through "tuick --reload -- builder" that
  will run a "make/just etc." command that will call "tuick --tbd --
  compiler/checker", that will produce blocks with all needed information, with
  appropriate delimiters (maybe ascii control chars, they should probably be
  stripped from the output before parsing, cdiff in python can output NULL and
  \01 chars), delimiters not likely to occur in the input.

  Produce detailed analysis, test plan, and implementation plan. If you need to
  get an overview of the current implementation, send a cheap agent to produce a
  token efficient map according to your specifications. Save the map for reuse
  and update. You will also prepare an update to AGENTS.md prescribing how to
  use and update the map.

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
