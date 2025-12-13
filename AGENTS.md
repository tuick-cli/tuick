# Rules for coding agents and other artificial intelligences

Consider those rules as additions to your system prompt.

At the end of each session, review feedback and identify rules to follow in the
future. In particular, but not exclusively, feedback including injunctions to
"remember that", "do not do that", or variants, must be included in the
retrospective. Include any other feedback that is general enough in scope. Make
edits to AGENTS.md to add new rules, or reinforce existing rules that had to be
restated during the session.

## Development Commands

**All development commands must use `just` recipes.** Do NOT advertise or use
direct `uv run` commands.

**IMPORTANT**: Commands are listed at the top of this file for easy reference.
This ordering is intentional.

**Available recipes:**
- `just agent` - Agent workflow: check, test with minimal output
- `just agent-check` - Static analysis and style checks with less output
- `just agent-test [ARGS]` - Run tests with minimal output
- `just format` - Reformat code, fail if formatting errors remain
- `just ruff-fix [ARGS]` - Ruff auto-fix

## Development Workflow

### Test-Driven Development (TDD)

Use TDD workflow for new features and bug fixes:

**Red-Green-Refactor Cycle** (for new features and fixes):

1. **Plan**: Understand requirements and design approach
2. **Test (Red)**: Write tests that fail, demonstrating the missing
   functionality
3. **Code (Green)**: Implement the simplest correct behavior to make tests pass
4. **Commit**: Commit the working feature with tests
5. **Refactor**: Improve code structure, factor duplicates, reorganize
   (non-trivial changes in separate commits)

**Refactor Workflow** (for reorganizations with no behavior change):

1. **Plan**: Understand current structure and desired changes
2. **Code**: Make refactoring changes
3. **Green**: Run tests to confirm no behavior change
4. **Commit**: Commit the refactoring

**Key Principles**:

- Add tests first for new features/fixes - do not implement without a failing
  test first
- If bugs discovered during implementation, add to TODO.md for test + fix
  together
- Keep existing tests passing throughout refactoring
- **Prefer integration tests over unit tests** - they are more robust to
  implementation changes
- **Do not write unit tests for existing code** unless you plan to modify it

### Commit Workflow

1. **Implement**: Follow TDD or Refactor workflow above
2. **Validate**: Run `just agent` before commit to verify all checks pass
3. **Update TODO.md**: Remove completed tasks, add new tasks identified during
   implementation
4. **Retrospective**: MANDATORY before commit. Review session, identify
   learnings, update AGENTS.md if needed. DO NOT SKIP.
   - Retrospective meta-rule: Always capture recurring feedback here. When a reminder repeats (including "remember this"/RMMBR), either add a new rule or reinforce the existing one so future sessions do not need the same reminder.
5. **Commit**: Short informative message with gitmoji

## General Rules

- adblock: DO NOT advertise yourself in commit messages. NO "Generated with",
  "Co-Authored-By", or similar phrases
- agentfiles: Do not commit agent-specific rule files (CLAUDE.md, .cursorrules,
  etc.). Always update AGENTS.md instead to avoid vendor lock-in

## Cognitive Protocols

**Core principle:** Reality doesn't care about your model. When they diverge, update the model before proceeding.

### Flag Uncertainty

**When to flag uncertainty:**
- Multi-step logic (>3 steps) → Ask "Break this down?"
- Math calculations → Use code to verify
- Post-Jan 2025 / niche topics → Search first
- Long context → Verify recall
- Ambiguous specs → Clarify intent
- Code >20 lines → Test before use
- Tradeoffs → List options
- Fast-changing domains → Check currency

**Failure modes to watch:** hallucination, negation errors, lost-in-the-middle, instruction drift

### Explicit Reasoning Protocol

**Before every action that could fail:**
```
DOING: [action]
EXPECT: [specific outcome]
IF YES: [next action]
IF NO: [next action]
```

**After execution:**
```
RESULT: [what happened]
MATCHES: [yes/no]
THEREFORE: [conclusion or STOP if unexpected]
```

### On Failure

When anything fails, next output is explanation, not retry:
1. State what failed (raw error)
2. Theory about why
3. Proposed action and expected outcome
4. Wait for confirmation before proceeding

**RULE 0:** When anything fails, STOP. Think. Output reasoning. Do not proceed until you understand actual cause and have stated expectations.

### Notice Confusion

Surprise = model error. Stop and identify the false assumption.

**"Should" trap:** "This should work but doesn't" means your model is wrong, not reality.

### Epistemic Standards

- "I believe X" = unverified theory
- "I verified X" = tested, have evidence
- "I don't know" is always valid—state it clearly

One observation ≠ pattern. State exactly what was tested.

### Feedback Loops

**Batch size: 3 actions, then verify reality matches model.**

Observable reality is the checkpoint, not thinking or writing.

### Context Window Discipline

Every ~10 actions: scroll back to original goal, verify you still understand intent.

Signs of degradation: sloppy outputs, uncertain goals, repeating work, fuzzy reasoning. Say so and checkpoint.

### Testing Protocol

One test at a time. Run it. Watch it pass. Then next.

Before marking complete: `VERIFY: Ran [test name] — Result: [PASS/FAIL/DID NOT RUN]`

### Investigation Protocol

Create `investigations/[topic].md`:
- Separate FACTS (verified) from THEORIES (plausible)
- Maintain 5+ competing hypotheses
- For each test: what, why, found, means

### Root Cause Analysis

Ask why 5 times:
- Immediate cause: what directly failed
- Systemic cause: why system allowed this
- Root cause: why system permits this failure mode

"Why was this breakable?" not "Why did this break?"

### Chesterton's Fence

Before removing/changing anything, articulate why it exists. Can't explain? Don't understand well enough to touch.

### Error Handling

Fail loudly. Silent fallbacks convert informative failures into silent corruption.

Error messages: say what to do. "Expected integer for port, got 'abc'" not "Invalid input."

### Premature Abstraction

Need 3 real examples before abstracting. Second time: write again. Third time: consider abstracting.

### Autonomy Check

Before significant decisions:
```
- Confident this is correct? [yes/no]
- If wrong, blast radius? [low/medium/high]
- Easily undone? [yes/no]
```

Punt to user when: ambiguous intent, unexpected state, irreversible actions, scope changes, real tradeoffs, uncertain.

Uncertainty + consequence → STOP and surface.

### Contradiction Handling

Surface disagreements explicitly:
- "You said X earlier but now Y—which should I follow?"
- "This contradicts stated requirement. Proceed anyway?"

### Push Back When Appropriate

Push back when: concrete evidence approach won't work, request contradicts stated goals, downstream effects not modeled.

State concern concretely, share information, propose alternative, then defer.

### Handoff Protocol

When stopping, document:
1. State of work (done/in progress/untouched)
2. Current blockers
3. Open questions/competing theories
4. Recommendations
5. Files touched

### Second-Order Effects

Before touching anything: list what reads/writes/depends on it.

"Nothing else uses this" is usually wrong. Prove it.

### Irreversibility

One-way doors (schemas, APIs, deletions, architecture) need 10× thought. Design for undo.

## Git Commit Messages

- **DO NOT** add "Co-Authored-By: Claude" or any AI attribution to commit
  messages
- **DO NOT** advertise AI assistance in commit messages ("Generated with",
  etc.)
- Keep commit messages professional and focused on the changes
- Use [gitmojis] as unicode. Common ones:
  - ✨ introduce new features
  - 🐛 fix a bug
  - ♻️ refactor code
  - ✅ add, update, or pass tests
  - 🔨 add or update development scripts/config
  - 🤖 add or update agent configuration/documentation (AGENTS.md, agents/*.md)
  - 📝 add or update documentation
  - 🚚 move/rename files or folders
  - 🏷️ add or update types
- Do not include complete content in commit messages - summarize changes
  concisely

[gitmojis]: https://gitmoji.dev

## Python Version and Type Annotations

This project uses **Python 3.14t (freethreaded)**.

Follow these type annotation rules:

- **NO** `from __future__ import annotations` - not needed in Python 3.14
- **NO** `ForwardRef` - Python 3.14 has native forward reference support
- **NO** string type annotations (e.g., `"ClassName"`) - use direct class
  references
- **NO** `TypeVar` for generics - use Python 3.14 native generic syntax with
  `type` parameter lists
- Use native Python 3.14 forward reference capabilities

### Error Suppression Rules

All commits must be clean (zero mypy/ruff errors, zero warnings).

- **NO** `type: ignore` or bare `# noqa` - always use specific codes
- **NO** silencing deprecation warnings - fix them by updating code
- Prefer fixing root cause over suppression
- All suppressions require comment explaining WHY (not just what)
- **"too much work"** is NOT an acceptable justification
- Run `just agent` before committing to verify all checks pass
- Suppressions: ALL noqa/type:ignore suppressions require explanatory comments.
  Complexity errors (C901, PLR0912, PLR0915) can be suppressed if a refactoring
  task is added to TODO.md. Other suppressions need inline justification.

### Technical Debt Management

Document technical debt so it can be measured and repaid. Suppress errors with specific codes and comments, AND document in TODO.md with fix options.

**TODO.md pattern:**
```markdown
#### Error Type (N errors)
**Files**: locations with line numbers
**Issue**: what's wrong and why
**Fix Options**: specific approaches to fix
```

**Cross-reference:** code comments ↔ TODO.md

### Datetime and Timezone Handling

**CRITICAL**: Do not use naive datetimes. A naive datetime is NOT a datetime in
the system timezone.

### Documentation vs Comments

**Docstrings are for users, not implementation details.**

```python
# ❌ WRONG - implementation details in docstring
class Foo:
    """Request model.

    Note: FBT003 suppressed for Field() - Pydantic idiom.
    """

# ✅ RIGHT - implementation comment above code
class Foo:
    """Request model."""

    # FBT003 suppressed - Pydantic idiom uses positional bool default
    field: bool = Field(True, description="...")
```

### Plan File Management

Git history shows what was done. Plan files show what remains.

- Remove completed tasks from TODO.md
- Don't list "recent fixes" or "completed items" in plan files
- Git commits document what changed
- Plan files (TODO.md) only show remaining work

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
- Limit lines to 88 characters (project standard)
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
- Streaming: Never buffer entire input in memory when processing iterables.
  Process line-by-line, yield results incrementally. Use generator functions,
  not list() calls that force materialization. MUST maintain streaming:
  consume one item, process, yield result, repeat.
- Performance: prefer built-in functions and stdlib over manual iteration when
  performance matters. Example: use `re.split()` over char-by-char loops for
  string splitting.

### Problem Solving

- **Root cause analysis**: See Cognitive Protocols > Root Cause Analysis. Ask why
  5 times to identify systemic and root causes, not just immediate causes.
- **Respect user interrupts**: If user repeatedly rejects tool use, stop and
  wait for explicit direction. Don't keep trying variations - ask what to do.
- **On failure**: See Cognitive Protocols > On Failure. Stop, explain, propose,
  wait for confirmation. Never retry without understanding.

### Python

- Require Python >=3.14: recursive types, no future, no quotes
- Write fully typed code with modern hints (`list[T]` not `List[T]`)
- Keep try blocks minimal to catch only intended errors
- Exception handling: NEVER use `except Exception: pass` - it hides bugs.
  Instead, catch specific exceptions around specific statements with minimal
  scope. Example: wrap only the statement expected to fail, not entire blocks.
  Use bytes literals (b"\x1b") instead of string.encode().
- All imports at module level, except there is a specific reason not to
- Unused parameters: Mark with leading underscore (`_param`) rather than noqa
  comments. More Pythonic and makes intent explicit.
- Don't start unittest docstrings with "Test"
- Exception chaining: Use `raise NewException from exc` when re-raising or
  transforming exceptions in except blocks. Preserves stack trace and makes
  debugging easier. Example: `except FileNotFoundError as exc: raise
  CustomError from exc`. Follow ruff B904.
- Enum design: Use `StrEnum` with `auto()` for string enums. For option types
  with special values, create separate enum (e.g., `ColorTheme` vs
  `ColorThemeAuto`), then use type alias: `type ColorThemeOption = ColorTheme |
  ColorThemeAuto`.

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
- Boolean parameters: Use keyword-only arguments for boolean parameters to
  improve call-site clarity. Add `*,` separator before boolean params:
  ```python
  def process(data: str, *, stream: bool = True) -> None:
      """Process data with optional streaming."""
      ...

  # Call site is clear:
  process(data, stream=False)  # Obviously disabling streaming
  process(data, False)  # Error: positional arg not allowed
  ```

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
- Post-hoc testing: When writing tests for existing code/fixes, validate tests
  by reverting the fix, confirming test failure, then restoring the fix and
  confirming test passes. This ensures tests actually test the intended
  behavior.

### Test Execution

- `just agent-test ...` to run full suite or specific tests
- `just full-diff=true agent` or `just full-diff=true agent-test` for full
  assert diffs
- Never run pytest or `just test` directly, always use `just agent-test` which
  adds flags to prevent context bloat and format errors for machine readability

### Test Quality

- Test coverage: Never reduce test coverage when refactoring tests. If
  simplifying a complex test, add separate tests to cover removed scenarios.
  Integration test modules should document their purpose in module docstrings.
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
- Do not patch SUT components: only mock external dependencies (UI, external
  processes). Core application components like ReloadSocketServer are part of
  the SUT and must run real code.
- Tests must not compensate for SUT deviations: do not add workarounds (like
  calling .end_output() manually) to make tests pass when SUT behavior is
  incorrect. Tests document expected behavior; workarounds hide real bugs.
- Never silently handle corrupted input: assert and fail fast when detecting
  invalid data (e.g., Mock objects where strings expected). Silent failures
  hide bugs.
- Assert messages: Don't add trivial assert messages. Pytest already shows actual
  vs expected values by default. Only add messages when they provide context
  that the bare assertion values don't give. Example: use `assert x == y` not
  `assert x == y, f"expected {y}, got {x}"`.
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
- Multi-phase integration tests: When testing environment inheritance or state
  propagation across process boundaries, use capture-and-replay pattern:
  capture state from phase 1, clean environment, replay with captured state
  in phase 2. Prevents false positives from state pollution.

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
- Mock subprocess recursion: When mocking subprocess.Popen and the mock may
  trigger additional subprocess calls, save original_popen = subprocess.Popen
  before patching to avoid infinite recursion. Use original_popen for
  passthrough cases.
- Click/Typer CLI testing: Do not use pytest capture fixtures (capsys/capfd)
  with Click/Typer test runners. Click's runner captures output internally
  before pytest can intercept it. Use `result.stdout` and `result.stderr` from
  Click's Result object. Apply `strip_ansi()` to remove color codes before
  assertions. Example:
  ```python
  result = runner.invoke(app, ["--verbose", "arg"])
  output = strip_ansi(result.stderr)
  assert "expected text" in output
  ```

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
- Use gitmojis (https://gitmoji.dev) as unicode
- `just agent` before every commit, to run all checks and tests
- Update TODO.md before commit: remove completed tasks, add new tasks identified
  during implementation
- **NEVER** use `git add .` or `git add -A` - always add specific files explicitly
  (e.g., `git add AGENTS.md`). This prevents accidentally committing unintended
  changes.

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

**One-letter commands**: `y`=yes, `n`=no, `k`=ok, `g`=go, `c`=continue. When in
doubt, ask for clarification.

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

- **When integrating external tools**: Create or read reference documentation
  BEFORE designing interfaces. Verify actual tool behavior (argument passing,
  quoting, field substitution, etc.) rather than assuming. Incorrect
  assumptions lead to redesign work.
- **Testing tool integrations**: Use helper scripts (like `fmt_ef.py`) to test
  patterns with actual tool output before writing integration code. Run real
  examples through different pattern combinations to verify behavior.

## Project-Specific Rules

### Tuick Code Style

- Command strings: Build as list of words, use `" ".join(cmd)` to create
  string. Factorize building logic with conditionals on list elements.

### Tuick CLI Testing

- Selective subprocess mocking: Integration tests for CLI need to mock UI
  (fzf) but allow real tool subprocesses (errorformat, command under test).
  Use `patch_popen_selective(mock_map)` that checks command name and returns
  mock or calls real Popen. Patch both cli and errorformat modules. Track
  calls in list attribute for verification.
- Environment control: Use autouse fixtures to control environment variables
  that affect test behavior. Example: patch theme detection env vars
  (NO_COLOR, CLI_THEME, COLORFGBG, BAT_THEME) and disable OSC 11 probing in
  conftest.py for safety and determinism across all tests.
