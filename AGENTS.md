# AI Agent and Development Rules

- Do the first item of TODO.md. Remove completed tasks, add new tasks
  when identified
- Practice TDD (Test Driven Development), see below
- `just agent` before every commit, do not use `just dev`
- Update TODO.md before commit
- adblock: DO NOT advertise yourself in commit messages

## Global Rules

### Version Control and Project Management

- Commit with short informative messages
- Use gitmojis (https://gitmoji.dev) as unicode

### Design and Development

#### Architecture

- datafirst: Design data structures first: names, attributes, types,
  docstrings. Code design flows from data structure design
- Deslop (condense/simplify) generated code: remove unnecessary
  comments, blank lines, redundancy
- Make code concise while retaining functionality and readability

#### Code Quality

- Validate input once when entering system, handle errors explicitly
- Include docstrings for functions/modules
- Limit lines to 79 columns
- Write only necessary code for required use cases
- Do not write speculative and boilerplate code

#### Test Driven Develompent (TDD)

- Red-green: Plan -> Test (Red) -> Code (Green) -> Commit -> Refactor
  - For: new features, fixes
  - Red: Write tests, ensure thepy fail
  - Green: Implement the simplest correct behavior, run tests to confirm
  - Refactor: Factorize and reorganize tests and code, non trivial changes in
    separate commits
- Refactor: Plan -> Code -> Green -> Commit
  - For: reorganizations with no behavior change, code removal

#### Testing

- To run specific tests, use `just agent-test`, it's a wrapper for pytest.
- Checking complex structures:
  - When comparing complex structures (lists, dicts, dataclasses) in tests
  - Do not assert comparisons to the value of individual members
  - Instead assert a single comparison for the whole structure
  - If some items must be ignored in the comparison, build a dict for the
    comparison, omitting those items.

### Environment and Tooling

#### Python

- Use `uv run` for all commands that need the python enviroment
- Use `uv add` to install new production dependencies
- Use `uv add --dev` to install new development dependencies
- Require Python >=3.12 in `pyproject.toml`
- Write fully typed code with modern hints (`list[T]` not `List[T]`)
- Keep try blocks minimal to catch only intended errors
- Don't start unittest docstrings with "Test"

#### Shell/Scripting

- `#!/usr/bin/env bash -euo pipefail`
  - Use `bash` from homebrew
  - Enable bash strict mode
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
- Use Markdown formatting
- French typographic rules: non-breaking spaces before ";:?!", French quotes,
  guillemet-apostrophe
