# AI Agent and Development Rules

- Do the first item of TODO.md. Remove completed tasks, add new tasks when
  identified
- Practice TDD (Test Driven Development), see below
- Update TODO.md before commit
- adblock: DO NOT advertise yourself in commit messages
- agentfiles: Do not commit agent-specific rule files (CLAUDE.md, .cursorrules,
  etc.). Always update AGENTS.md instead to avoid vendor lock-in

## Global Rules

### Version Control and Project Management

- Commit with short informative messages
- Use gitmojis (https://gitmoji.dev) as unicode
- `just agent` before every commit, to run all checks and tests
- `just format` to format code
- `just ruff-fix` to apply automated fixes

### Design and Development

- Mechanical refactoring: when doing 5+ similar edits (type renames, import
  updates, signature changes), consider delegation to faster processing if your
  agent supports it

#### Architecture

- datafirst: Design data structures first: names, attributes, types, docstrings.
  Code design flows from data structure design
- Deslop (condense/simplify) generated code: remove unnecessary comments, blank
  lines, redundancy
- Make code concise while retaining functionality and readability

#### Code Quality

- Complexity suppressions: complexity errors (C901, PLR0912, PLR0915) can be
  suppressed with noqa if a refactoring task is added to TODO.md
- Validate input once when entering system, handle errors explicitly
- Include docstrings for functions/modules
- Limit lines to 79 columns
- Write only necessary code for required use cases
- Do not write speculative and boilerplate code
- All other things being equal, prefer code that takes fewer lines
- Consider intermediate variables where they make code more compact
- Do not write trivial docstrings, except for important public objects
- Preserve compact notation for function signatures: keep on one line when
  possible. For function calls with long arguments, use intermediate variables
  to prevent wrapping and reduce vertical space waste.
- Docstring first line must be concise, details go in body or comments
- Implementation details belong in comments, not docstrings

#### Test Driven Develompent (TDD)

- Red-green: Plan -> Test (Red) -> Code (Green) -> Commit -> Refactor
  - For: new features, fixes
  - Red: Write tests, ensure thepy fail
  - Green: Implement the simplest correct behavior, run tests to confirm
  - Refactor: Factorize and reorganize tests and code, non trivial changes in
    separate commits
- Refactor: Plan -> Code -> Green -> Commit
  - For: reorganizations with no behavior change, code removal
- Add tests first, period. Do not fix bugs or add features without a failing
  test first. If identified during implementation, add to TODO.md for test and
  fix together.

#### Retrospective

- Review feedback: After committing each task, review the session and summarize
  the provided feedback
- Persist feedback: Identify feedback that could be reused, produce a short
  summary to integrate into AGENTS.md. Changes could be:
  - Updates to existing rules: changes in the intent, additional details, or
    additional reinforcement
  - New rules, if no existing rule seems appropriate

#### Testing

- `just agent-test ...` to run full suite or specific tests
- `just agent-test -vv ...` for full assert diffs
- Never run pytest or `just test` directly, always use `just agent-test` which
  adds flags to prevent context bloat and format errors for machine readability
- Read error messages: they contain hints or directions
- Never guess at fixes: get proper diagnostics (tracebacks, error output) before
  fixing. If error output is unclear, add logging or error handlers first.
- Spec mocks: always use create_autospec() or patch(autospec=True), do not use
  plain Mock or MagicMock
- Do not mock the hell out of things. When testing the happy path of a single
  behavior, prefer integration tests. Use unit tests with mocking when testing
  complex behavior with multiple inputs.
- Checking complex structures:
  - When comparing complex structures (lists, dicts, dataclasses) in tests
  - Do not assert comparisons to the value of individual members
  - Instead assert a single comparison for the whole structure
  - If some items must be ignored in the comparison, build a dict for the
    comparison, omitting those items.
- Fixture design: avoid implicit/magical behavior. If a fixture has side effects
  or requirements (like output checking), make them explicit through method
  calls, not automatic in teardown based on hidden state.
- testsync: Multithreaded tests must use proper synchronization.
  - testawake: `time.sleep()` is _strictly forbidden_ in tests.
  - fastgreen: Never block on the green path. The execution of a successful test
    must never block on a timeout.
  - The green execution path can move from one thread to another through
    blocking synchronization.
  - After teardown of a successful test, all created threads and processes must
    be joined.
  - Blocking on a timeout in test and teardown is allowed for failing tests.

### Environment and Tooling

#### Python

- Use `uv run` for all commands that need the python enviroment
- Use `uv add` to install new production dependencies
- Use `uv add --dev` to install new development dependencies
- Require Python >=3.14: recursive types, no future, no quotes
- Write fully typed code with modern hints (`list[T]` not `List[T]`)
- Keep try blocks minimal to catch only intended errors
- Don't start unittest docstrings with "Test"
- All imports at module level, except there is a specific reason not to

#### Shell/Scripting

- `#!/usr/bin/env bash -euo pipefail`
  - Use `bash` from homebrew
  - Enable bash strict mode `-euo pipefail`
    - exit on error
    - undefined variables are error
    - pipe fail if any command fails
  - Think about shell idioms involving the exit status
- Package commands (test, run, clean) using `just`
- Create parameterized commands in justfile instead of running raw commands

### File Operations

- Create scripts/temp files within working directory
- Do not modify system files

### Communication

- Be concise and conversational but professional
- Avoid business-speak, buzzwords, unfounded self-affirmations
- State facts directly even if they don't conform to requests
- Use Markdown formatting
