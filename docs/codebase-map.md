# Tuick Codebase Map

**Purpose**: Token-efficient reference for understanding tuick architecture and locating code for modifications.

**Last Updated**: 2025-11-11

## Project Overview

Tuick is a command-line tool that runs build commands, parses their output for errors, and presents them in fzf for interactive selection. When a user selects an error, tuick opens the file at the error location in their editor.

**Key workflow**: `tuick command` → run command → parse output → group into blocks → feed to fzf → user selects → open editor at location

## Directory Structure

```
tuick/
├── src/tuick/          # Main source code
│   ├── cli.py          # Entry point, command routing
│   ├── parser.py       # Error parsing, block splitting
│   ├── console.py      # Logging, output formatting
│   ├── fzf.py          # fzf process management
│   ├── reload_socket.py # TCP coordination server
│   ├── monitor.py      # Filesystem watcher
│   └── editor.py       # Editor command building
├── tests/              # Test suite
├── docs/               # Documentation
│   └── codebase-map.md # This file
└── justfile            # Build commands

```

## Core Modules

### cli.py (378 lines)
**Purpose**: Main entry point, CLI routing, four operational modes

**Key Functions**:
- `main()` - Entry point, validates options
- `list_command()` - **Primary mode**: run command → parse → fzf
- `reload_command()` - **Reload mode**: re-run command → stream to fzf
- `select_command()` - **Editor mode**: parse selection → open editor
- `start_command()` - **Init mode**: notify fzf of port

**CLI Options**:
- `--list` (default) - Primary mode
- `--reload` - Reload mode (called by fzf binding)
- `--select` - Editor selection mode (called by fzf binding)
- `--start` - Initialization mode
- `--verbose` - Enable debug logging
- `--watch` - Auto-reload on file changes

**Key Classes**:
- `CallbackCommands` - Generates command strings for fzf bindings
  - Methods: `start()`, `reload()`, `select()`, `load()`

**Data Flow in list_command()** (lines 147-213):
```
1. ReloadSocketServer.start() - Launch coordination server
2. MonitorThread.start() - Launch filesystem watcher (if --watch)
3. _create_command_process() - Spawn subprocess
4. _process_raw_and_split() - Parse output into blocks
5. open_fzf_process() - Launch fzf with blocks
```

### parser.py (329 lines)
**Purpose**: Parse tool output, extract locations, group multi-line errors into blocks

**Data Structures**:
```python
@dataclass
class FileLocation:
    path: str
    row: int
    column: int | None

class State(Enum):
    START = auto()
    NORMAL = auto()
    NOTE_CONTEXT = auto()
    SUMMARY = auto()
    PYTEST_BLOCK = auto()

class LineType(Enum):
    BLANK = auto()
    LOCATION = auto()
    MYPY_NOTE = auto()
    SUMMARY = auto()
    PYTEST_SEP = auto()
    RUFF_LOCATION = auto()
    NORMAL = auto()
```

**Regex Patterns** (lines 62-91):
- `LINE_REGEX` - Standard format: `file:line:col: message`
- `MYPY_NOTE_REGEX` - Mypy notes: `file:line: note:`
- `SUMMARY_REGEX` - Summary lines (PASSED, FAILED, etc.)
- `PYTEST_SEP_REGEX` - Pytest separators (`====`, `----`, `____`)
- `RUFF_LOCATION_REGEX` - Ruff format: `--> file:line:col`
- `ANSI_REGEX` - Strip ANSI color codes

**Key Functions**:
- `classify_line(line: str) -> LineType` (lines 116-138)
  - Determines what type of line this is

- `extract_location_str(line: str) -> str | None` (lines 141-152)
  - Extracts "file:line:col" string from line

- `strip_ansi(text: str) -> str` (lines 155-158)
  - Removes ANSI color codes

- `split_blocks(lines: Iterable[str]) -> Iterator[str]` (lines 289-301)
  - **Main entry point** - splits lines into null-separated blocks
  - Uses BlockSplitter state machine

- `get_location(text: str) -> FileLocation` (lines 303-329)
  - Extracts location from user-selected block
  - Called by select_command()

**BlockSplitter State Machine** (lines 161-286):
- Maintains state while processing lines
- Groups related lines into blocks
- Emits null-separated blocks

**Block Boundary Logic** (lines 216-247):
- New location → new block
- State transitions → new block
- Blank lines → new block (except in summary/pytest)
- Pytest separators → new block

### fzf.py (94 lines)
**Purpose**: Launch and configure fzf process

**Key Function**:
- `open_fzf_process(blocks: Iterable[str], bindings: dict, initial_port: int | None) -> None`
  - Spawns fzf with `--read0` (null-separated input)
  - Configures bindings: ctrl-r (reload), enter (select), ctrl-l (load)
  - Uses `--bind` for dynamic command injection

**fzf Configuration**:
- `--ansi` - Preserve ANSI colors
- `--read0` - Read null-separated records
- `--tac` - Reverse order (latest first)
- `--no-sort` - Preserve input order
- `--bind` - Dynamic key bindings

### reload_socket.py (189 lines)
**Purpose**: TCP server for coordinating reload operations

**Key Class**:
- `ReloadSocketServer` (lines 19-169)
  - Manages coordination between list and reload commands
  - Stores reference to running command process
  - Buffers raw command output for state restoration

**Attributes**:
- `cmd_proc: subprocess.Popen | None` - Running command process
- `fzf_port: int | None` - fzf listen port for reload
- `saved_output_file: Path` - Buffered raw output
- `temp_output_file: Path` - Temporary buffer during reload

**Request Types**:
- `reload` - Trigger command re-execution
- `save-output` - Stream and save command output

**Data Flow**:
```
reload_command() → send "reload" → wait for "go"
                → connect to save-output socket
                → send raw output line-by-line
                → server saves to temp file
                → server commits on completion
```

### monitor.py (159 lines)
**Purpose**: Filesystem monitoring for auto-reload

**Key Class**:
- `MonitorThread` (lines 20-139)
  - Watches filesystem for changes
  - Triggers reload via fzf port
  - Debounces rapid changes

**Monitored Events**:
- File modifications
- File creations
- File deletions

**Ignored Patterns**:
- `.git/`, `__pycache__/`, `*.pyc`
- Temporary files

### editor.py (353 lines)
**Purpose**: Generate editor-specific commands to open files at locations

**Key Function**:
- `get_editor_command(editor: str, location: FileLocation) -> list[str]`
  - Returns command to open editor at location
  - Supports: vim, neovim, emacs, vscode, sublime, etc.

**Editor Integrations**:
- CLI editors: vim, neovim, emacs, nano, micro
- GUI editors: vscode, sublime, atom, pycharm, idea
- URL-based: cursor, surf, code

**Location Formats**:
- CLI: `+line` (vim), `+line:col` (emacs)
- GUI: `-g file:line:col` (vscode)
- URL: `file://path:line:col` (some editors)

### console.py (167 lines)
**Purpose**: Logging, output formatting, stderr capture

**Key Functions**:
- `setup_log_file() -> Path`
  - Creates temp log file
  - Multiplexes stderr to file + console

- `print_error(msg: str)`
  - Styled error messages with Rich

- `print_debug(msg: str)`
  - Debug messages when verbose=True

**Global State**:
- `verbose: bool` - Debug mode flag
- `log_file_path: Path | None` - Current log file

## Data Flow Diagrams

### Primary Use Case: tuick ruff check

```
User: tuick ruff check
    ↓
main() - Parse args
    ↓
list_command()
    ├─→ ReloadSocketServer.start() - Launch coordination server
    │       ↓
    │   Listen on random port for reload requests
    │
    ├─→ MonitorThread.start() (if --watch)
    │       ↓
    │   Watch filesystem → trigger reload on changes
    │
    ├─→ _create_command_process(["ruff", "check"])
    │       ↓
    │   subprocess.Popen(["ruff", "check"])
    │       ↓
    │   Read stdout line by line
    │
    ├─→ _process_raw_and_split(proc.stdout)
    │       ↓
    │   split_blocks(lines)
    │       ├─→ BlockSplitter.process_line() for each line
    │       ├─→ classify_line() → LineType
    │       ├─→ extract_location_str() → location string
    │       ├─→ State machine determines block boundaries
    │       └─→ Yield blocks separated by '\0'
    │
    └─→ open_fzf_process(blocks, bindings)
            ↓
        fzf displays errors
            ↓
        User selects error (presses Enter)
            ↓
        fzf executes: tuick --select <selection>
            ↓
        select_command(selection)
            ↓
        get_location(selection) → FileLocation
            ↓
        get_editor_command(editor, location)
            ↓
        subprocess.run(editor_command)
            ↓
        Editor opens at location
```

### Reload Flow: User presses 'r' in fzf

**Key**: reload_command shares implementation with list_command via `split_blocks()`

```
User presses ctrl-r in fzf
    ↓
fzf executes: tuick --reload -- ruff check
    ↓
reload_command()
    ├─→ Connect to ReloadSocketServer
    │       ↓
    │   Send "reload" message
    │       ↓
    │   Wait for "go" response (server kills old process)
    │       ↓
    │   Server responds "go"
    │
    ├─→ Connect to save-output socket
    │
    ├─→ _create_command_process(["ruff", "check"])
    │       ↓
    │   subprocess.Popen(["ruff", "check"])
    │
    └─→ _process_output_and_yield_raw(proc.stdout, sys.stdout)
            ├─→ split_blocks(proc.stdout) → blocks
            │       ↓
            │   Write blocks to sys.stdout (fzf reads via --reload)
            │
            └─→ Yield raw lines for saving
                    ↓
                Send raw output to save-output socket
                    ↓
                Server commits temp output file → saved_output_file
                    ↓
                Future abort prints this output
```

**Shared parsing path**: Both list_command and reload_command call `split_blocks()`, so changes to block splitting logic (e.g., errorformat integration) automatically work for both modes.

## Key Integration Points

### Where to Add Errorformat Parsing

**Primary**: `parser.py` - `split_blocks()` function (line 289)
- Currently uses regex + state machine
- **Future**: Call reviewdog subprocess, parse structured output
- Keep existing logic as fallback

**Secondary**: `cli.py` - `list_command()` and `reload_command()`
- Both call `split_blocks()` through shared implementation
- `list_command()`: calls `split_blocks()` directly on command output (line 183)
- `reload_command()`: calls `_process_output_and_yield_raw()` which calls `split_blocks()` (line 334)
- Pass format configuration to split_blocks()
- Add `--format` and `--top` option propagation through callbacks

**Shared implementation**: Both modes use split_blocks() for parsing, so errorformat integration in split_blocks() automatically works for both list and reload modes.

### Current Parsing Logic

**Location**: `parser.py` lines 161-286 (BlockSplitter class)

**Algorithm**:
1. For each line:
   - Strip ANSI codes for parsing (but preserve for display)
   - Classify line type
   - Extract location if present
   - Determine if new block should start
   - Update state machine
   - Buffer lines until block boundary
   - Emit block with null separator

**State Transitions**:
- `START` → `NORMAL` (on first line)
- `NORMAL` → `NOTE_CONTEXT` (on mypy note)
- `NOTE_CONTEXT` → `NORMAL` (on blank or new location)
- `NORMAL` → `SUMMARY` (on summary line)
- `SUMMARY` → `START` (on blank)
- `NORMAL` → `PYTEST_BLOCK` (on pytest separator)
- `PYTEST_BLOCK` → `START` (on blank)

### Output Format

**Current**: Null-separated blocks (`\0`)
- Compatible with fzf `--read0`
- Each block is multiple lines joined with newlines
- Blocks separated by null byte

**Future**: Structured format with delimiters
- Use `\x1F` (unit separator) for internal fields
- Format: `location\x1Fmessage\x1Fmetadata`
- Still separate blocks with `\0` for fzf

## Testing Infrastructure

**Location**: `tests/` directory

**Key Test Files**:
- `test_cli.py` - CLI integration tests
- `test_parser.py` - Parser and block splitting tests
- `test_editor.py` - Editor command generation tests
- `test_reload_socket.py` - Coordination server tests
- `test_monitor.py` - Filesystem watcher tests

**Test Fixtures** (`conftest.py`):
- `server_with_key` - ReloadSocketServer instance
- `tmp_path` - Temporary directory (pytest built-in)

**Test Execution**:
- `just agent-test` - Run all tests with machine-readable output
- `just agent-test -vv tests/test_foo.py` - Verbose output for specific test

## Configuration and Build

**justfile** - Command definitions
- `just format` - Format code with ruff
- `just ruff-fix` - Apply automated fixes
- `just agent` - Run all checks and tests (pre-commit)
- `just agent-test` - Run tests with appropriate flags

**pyproject.toml** - Project configuration
- Dependencies
- Tool settings (ruff, mypy, pytest)
- Entry points

## Future Modifications Guide

### Adding New Error Format Support

1. **Define format in registry** (new: `errorformats.py`)
   ```python
   ERRORFORMAT_REGISTRY["newtool"] = "%f:%l:%c: %m"
   ```

2. **Add tool detection** (`errorformats.py`)
   ```python
   # In detect_tool_from_command()
   if command.startswith("newtool"):
       return "newtool"
   ```

3. **Test with real output**
   ```python
   # tests/test_errorformats.py
   def test_newtool_format():
       assert get_errorformat("newtool") == expected
   ```

### Modifying Block Splitting Logic

**Location**: `parser.py` lines 161-286

**Current approach**: State machine with regex patterns

**To modify**:
1. Add new `LineType` enum value if needed
2. Add regex pattern at module level (lines 62-91)
3. Update `classify_line()` to recognize new pattern
4. Update `_should_start_new_block()` for boundary logic
5. Add state transition in `_update_state()` if needed
6. Add tests in `test_parser.py`

### Adding New CLI Option

**Location**: `cli.py` lines 56-73 (main function)

**Steps**:
1. Add option parameter to `main()` function signature
2. Update option validation
3. Pass option through to relevant command functions
4. Update `CallbackCommands` to include option in bindings
5. Add tests in `test_cli.py`

### Adding New Editor Support

**Location**: `editor.py`

**Steps**:
1. Add editor name to detection logic
2. Add command template in `get_editor_command()`
3. Handle special cases (URL vs CLI, line format, etc.)
4. Add test case in `test_editor.py`

## Maintenance Notes

**Update this map when**:
- Major architectural changes
- New modules added
- Data flow changes
- Integration points change
- After completing errorformat integration

**Map update process** (from AGENTS.md):
1. Read current map
2. Make minimal, precise updates
3. Keep token-efficient (focus on structure, not implementation)
4. Update "Last Updated" date
5. Commit with other changes in feature

**Keep map concise**:
- Focus on structure and data flow
- Omit implementation details (except key algorithms)
- Use code snippets sparingly
- Emphasize integration points and modification guides
