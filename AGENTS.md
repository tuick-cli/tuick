# AI Agent and Development Rules

## Development Workflow

1. **Select task**: Do first item of TODO.md
2. **Implement**: Follow TDD (Test Driven Development) or Refactor approach, see
   below
3. **Validate**: Run `just agent` before commit
4. **Update TODO.md**: Remove completed tasks, add new tasks identified during
   implementation
5. **Retrospective**: MANDATORY before commit. Review session, identify
   learnings, update AGENTS.md if needed. DO NOT SKIP.
6. **Commit**: Short informative message with gitmoji

## General Rules

- adblock: DO NOT advertise yourself in commit messages. NO "Generated with",
  "Co-Authored-By", or similar phrases
- agentfiles: Do not commit agent-specific rule files (CLAUDE.md, .cursorrules,
  etc.). Always update AGENTS.md instead to avoid vendor lock-in

## Design and Planning

### Architecture

- datafirst: Design data structures first: names, attributes, types, docstrings.
  Code design flows from data structure design
- Deslop (condense/simplify) generated code: remove unnecessary comments, blank
  lines, redundancy
- Make code concise while retaining functionality and readability
- Avoid trivial data structures: if map values are computable or identical to
  keys, use simpler structure (set instead of dict with identity mapping)
- Reuse code with shared intent: check existing patterns in codebase before
  implementing utilities. Use established idioms (Path.name vs os.path.basename)
- Reuse existing infrastructure: before adding new environment variables or IPC
  mechanisms, check if existing ones can serve the purpose. Reduces complexity
  and maintenance burden.

### Planning

- Keep plans concise: under 200 lines, outline level
- Document unknowns as open questions for research
- Do not make assumptions about implementation details
- Expect iterative refinement through conversation
- Validate understanding: Before finalizing plans or making changes, reformulate
  your understanding back to the user for confirmation. Present concrete examples
  of the proposed behavior.
- Use appendices for supporting information
- Create/update codebase map early for session continuity
- In plan mode: no file writes until plan approved
- Read documentation thoroughly: understand actual tool behavior before
  implementing integrations, don't rely on assumptions
- Be precise about data formats: distinguish between terminators vs separators
  (null-terminated means `\0` after each item; null-separated means `\0` between
  items). Document format specs accurately.

### Interface Design

- Present usage examples before implementation details when designing interfaces
- Show concrete examples of how users will interact with the system
- Validate that common cases are simple and require minimal configuration

## Code Style and Quality

### General

- Avoid confusing names: module/file names must be clearly distinct. Don't use
  names differing by one character (errorformat.py vs errorformats.py). Use
  descriptive, distinct names (tool_registry.py vs errorformat.py).
- Validate input once when entering system, handle errors explicitly
- Include docstrings for functions/modules
- Limit lines to 79 columns
- Write only necessary code for required use cases
- Do not write speculative and boilerplate code
- Factor duplicated logic: extract helper functions when same logic appears
  twice, even for small chunks (5-6 lines). Reduces maintenance burden and
  ensures consistency
- All other things being equal, prefer code that takes fewer lines
- Consider intermediate variables where they make code more compact. For
  command-line options/flags, extract meaningful intermediate lists like
  `reload_opts`, `verbose_flag` that represent cohesive option sets
- Do not write trivial docstrings, except for important public objects
- Helper function docstrings must not exceed implementation length. One-line
  docstrings for simple helpers. Detailed Args/Returns only for public APIs.
- Preserve compact notation for function signatures: keep on one line when
  possible. For function calls with long arguments, use intermediate variables
  to prevent wrapping and reduce vertical space waste.
- Docstring first line must be concise, details go in body or comments
- Implementation details belong in comments, not docstrings
- Complexity suppressions: complexity errors (C901, PLR0912, PLR0915) can be
  suppressed with noqa if a refactoring task is added to TODO.md
- Streaming: Never buffer entire input in memory when processing iterables.
  Process line-by-line, yield results incrementally. Use generator functions,
  not list() calls that force materialization. MUST maintain streaming:
  consume one item, process, yield result, repeat.
- Performance: prefer built-in functions and stdlib over manual iteration when
  performance matters. Example: use `re.split()` over char-by-char loops for
  string splitting.

### Python

- Require Python >=3.14: recursive types, no future, no quotes
- Write fully typed code with modern hints (`list[T]` not `List[T]`)
- Keep try blocks minimal to catch only intended errors
- All imports at module level, except there is a specific reason not to
- Unused parameters: Mark with leading underscore (`_param`) rather than noqa
  comments. More Pythonic and makes intent explicit.
- Don't start unittest docstrings with "Test"
- Exception chaining: Use `raise NewException from exc` when re-raising or
  transforming exceptions in except blocks. Preserves stack trace and makes
  debugging easier. Example: `except FileNotFoundError as exc: raise
  CustomError from exc`. Follow ruff B904.

### Type Hints

- TYPE_CHECKING blocks: Import types only used in annotations under
  `if typing.TYPE_CHECKING:` to avoid runtime overhead
- Use most general type that works: `Iterable` over `Iterator` when only
  iteration needed
- Missing values: Use `None` for missing/optional data, not `0` or `''`
- Context managers: Use `Self` type (from typing) for `__enter__` return
  annotation in context manager classes

### Function Design

- newfunc: Write new functions instead of adding optional parameters for
  alternate behavior paths
- If dispatch is needed, use polymorphism or explicit dispatch functions
- Example: `split_blocks_auto()` dispatches to `split_blocks()` or
  `split_blocks_errorformat()` based on tool
- Optional parameters: don't make parameters optional if they're always provided
  at call sites. Simpler to require them. Use `Optional` only for truly optional
  values.
- Separate intent from behavior: when a feature can be triggered explicitly or
  implicitly (e.g., `--top` flag vs auto-detected build system), use separate
  parameters for user intent vs implementation behavior. Example: `explicit_top`
  (preserve flag in bindings) vs `top_mode` (use top-mode parsing). Prevents
  unintended propagation when auto-detection and explicit flags must behave
  differently.

## Testing

### Test Driven Development (TDD)

- Red-green: Plan -> Test (Red) -> Code (Green) -> Commit -> Refactor
  - For: new features, fixes
  - Red: Write tests, ensure they fail
  - Green: Implement the simplest correct behavior, run tests to confirm
  - Refactor: Factorize and reorganize tests and code, non trivial changes in
    separate commits
- Refactor: Plan -> Code -> Green -> Commit
  - For: reorganizations with no behavior change, code removal
- Add tests first, period. Do not fix bugs or add features without a failing
  test first. If identified during implementation, add to TODO.md for test and
  fix together.

### Test Execution

- `just agent-test ...` to run full suite or specific tests
- `just full-diff=true agent` or `just full-diff=true agent-test` for full
  assert diffs
- Never run pytest or `just test` directly, always use `just agent-test` which
  adds flags to prevent context bloat and format errors for machine readability

### Test Quality

- testsize: Keep tests compact, fit in ~50 lines. Use helper functions to
  format expected output declaratively
- Minimize test count: combine related assertions testing the same behavior into
  one test. Separate tests should test different behaviors, not just different
  inputs. Don't write tests for trivial variations or CLI usage errors.
- Read error messages: they contain hints or directions
- Test verification: When testing parsing/transformation, verify ALL output
  fields, not just content. For location-based parsers, explicitly verify
  file, line, col, end_line, end_col extraction.
- Test formatting: Create custom formatters (like format_for_test()) that
  show differences clearly. Omit empty/default fields to reduce noise.
  Format complex fields (like multi-line content) with indentation and repr
- Real tool output: Use actual tool output for test data, not invented examples.
  Run the tool (with various flags/modes) to capture real output. Verify tool
  capabilities (e.g., check errorformat -list) before assuming support. Check
  tool registries (BUILTIN_TOOLS, CUSTOM_PATTERNS, OVERRIDE_PATTERNS) before
  writing integration tests.
- Test data reuse: NEVER duplicate test data. Extract to module-level constants
  and import them. If one test file already has the data, import from there. If
  data format is inconvenient, preprocess/transform, but do not copy-paste.
- Never guess at fixes: get proper diagnostics (tracebacks, error output) before
  fixing. If error output is unclear, add logging or error handlers first.
- Verify before fixing: When a bug is described in TODO.md or elsewhere, verify
  the problem exists before implementing a fix. Check documentation, stdlib
  source, or write a reproduction test. Don't assume the bug description is
  accurate without verification.
- Spec mocks: always use create_autospec() or patch(autospec=True), do not use
  plain Mock or MagicMock
- Do not mock the hell out of things. When testing a single unit of behavior,
  prefer integration tests over isolated unit tests. Integration tests provide
  better confidence with less maintenance. Use unit tests with mocking only
  when testing complex behavior with multiple edge cases requiring controlled
  inputs.
- Checking complex structures:
  - When comparing complex structures (lists, dicts, dataclasses) in tests
  - Do not assert comparisons to the value of individual members
  - Instead assert a single comparison for the whole structure
  - If some items must be ignored in the comparison, build a dict for the
    comparison, omitting those items.
- Fixture design: avoid implicit/magical behavior. If a fixture has side effects
  or requirements (like output checking), make them explicit through method
  calls, not automatic in teardown based on hidden state.
- xfail integration tests: For multi-mode features, write xfail integration
  tests for each configuration first, not unit tests for routing. Remove xfail
  as each mode is implemented.
- xfail for TDD of registries: when building registries that start empty and
  grow, write xfail test for first entry to be added, passing test for unknown
  entries
- xfail precision: When marking tests xfail during incremental implementation,
  reference the specific task number or feature name. Use "Task N: reason"
  format so it's clear when to remove the marker. Example:
  `@pytest.mark.xfail(reason="Task 9: fzf delimiter config not implemented")`
  not generic "feature not ready".
- Option parsing tests: When testing CLI option routing/parsing, mock the
  routed command function and verify call arguments, rather than full
  integration tests. Faster and more focused on the routing logic being tested.
- Test docstrings: Describe behavior, not command syntax. Keep command names
  lowercase (e.g., "tuick" not "Tuick"). Focus on what the test verifies.

### Test Infrastructure

- testutil: Create utilities for repeated mocking patterns, but at the right
  abstraction level
- testclarity: Test infrastructure must not obscure test intent. If mocking
  setup dominates the test, extract to utility
- testevent: Track meaningful system events in tests, not language-level
  details (e.g., process creation/termination, not `__enter__`)
- Example: `patch_popen(sequence, procs)` encapsulates both patching and proc
  sequencing
- Mock data tracking: when tracking mock calls in tests, avoid using `!r` repr
  formatting which adds extra quotes. Use `f"event:{data}"` not
  `f"event:{data!r}"` for cleaner assertions.
- ALWAYS check for existing test helpers before writing mock setup. Use
  `patch_popen()`, `make_cmd_proc()`, `make_fzf_proc()` etc. Never manually
  construct mocks that helpers already provide. Grep test files for helper
  functions if unsure what exists.
- Mock simplicity: Avoid over-abstracting mock wrappers. Use patch contexts
  directly and access `mock.mock_calls` or `mock.call_args_list` in tests.
  Create helper functions for extracting data from mock_calls if needed, but
  don't wrap the context manager itself. Example: `get_command_calls_from_mock()`
  extracts commands from mock_calls, but patch returns unwrapped context.
- Mock call structure: Each entry in `mock.mock_calls` is a tuple
  `(name, args, kwargs)`. Use tuple unpacking or indexing: `_name, args, kwargs
  = mock.mock_calls[0]`. For `call_args_list`, use `call[0]` for args tuple,
  `call[1]` for kwargs dict.
- Integration test requirements: Some dependencies (like errorformat) are hard
  requirements and should NOT be mocked in CLI integration tests. Only mock UI
  components (fzf) and use real subprocess calls for required tools. This
  validates actual integration.

### Test Synchronization

- testsync: Multithreaded tests must use proper synchronization.
  - testawake: `time.sleep()` is _strictly forbidden_ in tests.
  - fastgreen: Never block on the green path. The execution of a successful test
    must never block on a timeout.
  - testrace: Don't test race conditions by trying to trigger undefined behavior.
    Test that synchronization mechanisms work by verifying concurrent operations
    complete successfully. Use explicit synchronization (Events, Barriers) to
    control thread timing in tests.
  - The green execution path can move from one thread to another through
    blocking synchronization.
  - After teardown of a successful test, all created threads and processes must
    be joined.
  - Blocking on a timeout in test and teardown is allowed for failing tests.

### Retrospective

- Review feedback: After committing each task, review the session and summarize
  the provided feedback
- Persist feedback: Identify feedback that could be reused, produce a short
  summary to integrate into AGENTS.md. Changes could be:
  - Updates to existing rules: changes in the intent, additional details, or
    additional reinforcement
  - New rules, if no existing rule seems appropriate
- "Remember this" marker: When user says "remember this" or similar, that
  feedback MUST be added or reinforced in AGENTS.md during retrospective

## Version Control

- Commit with short informative messages
- Use gitmojis (https://gitmoji.dev) as unicode. Common ones:
  - 🚚 move/rename files or folders
  - ♻️ refactor code
  - ✨ introduce new features
  - 🐛 fix a bug
  - 📝 add or update documentation
  - ✅ add, update, or pass tests
- Do not include complete content in commit messages - summarize changes
  concisely
- `just agent` before every commit, to run all checks and tests
- Update TODO.md before commit: remove completed tasks, add new tasks identified
  during implementation

## Tooling

### Just Commands

- `just format` to format code
- `just ruff-fix` to apply automated fixes
- `just agent` to run all checks and tests
- `just agent-test` to run tests with machine-readable output
- NEVER run `ruff`, `mypy`, or `pytest` directly. ALWAYS use just commands

### Python/uv

- Use `uv run` for all commands that need the python enviroment
- Use `uv add` to install new production dependencies
- Use `uv add --dev` to install new development dependencies

### Shell/Scripting

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

## Agent Delegation

- When delegating to sub-agents (Task tool), always include @AGENTS.md in
  context so sub-agents follow project rules
- Sub-agents often ignore instructions - be explicit:
  - List forbidden commands with ❌ (e.g., `ruff check` ❌)
  - List allowed commands with ✓ (e.g., `just agent` ✓)
  - Tell agent to start with `just agent` to see current state
- Mechanical refactoring: when doing 5+ similar edits (type renames, import
  updates, signature changes), consider delegation to faster processing if your
  agent supports it

## Communication

- Be concise and conversational but professional
- Avoid business-speak, buzzwords, unfounded self-affirmations
- State facts directly even if they don't conform to requests
- Use Markdown formatting

## Documentation

### Codebase Map

- Location: `docs/codebase-map.md`
- Purpose: Token-efficient reference for understanding architecture
- Update when: major architectural changes, new modules, data flow changes
- Keep concise: focus on structure and data flow, not implementation details
- Update atomically: include map updates in feature commits, not separately

### Reference Documentation

- Create token-efficient API references for external tools/libraries used
  frequently
- Store in `docs/reference-*.md` for agent and human use
- Better than repeatedly looking up or guessing API behavior
- Format: tables, concise descriptions, common patterns
- Example: `docs/reference-subprocess.md` for Python subprocess module
- **When integrating external tools**: Create or read reference documentation
  BEFORE designing interfaces. Verify actual tool behavior (argument passing,
  quoting, field substitution, etc.) rather than assuming. Incorrect
  assumptions lead to redesign work.
- **Testing tool integrations**: Use helper scripts (like `fmt_ef.py`) to test
  patterns with actual tool output before writing integration code. Run real
  examples through different pattern combinations to verify behavior.

## Project-Specific Rules

### Tuick CLI Testing

- Selective subprocess mocking: Integration tests for CLI need to mock UI
  (fzf) but allow real tool subprocesses (errorformat, command under test).
  Use `patch_popen_selective(mock_map)` that checks command name and returns
  mock or calls real Popen. Patch both cli and errorformat modules. Track
  calls in list attribute for verification.
