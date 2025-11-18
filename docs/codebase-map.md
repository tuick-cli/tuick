# Tuick Codebase Map

**Purpose**: Token-efficient reference for understanding tuick architecture and locating code for modifications.

**Last Updated**: 2025-11-18

## Project Overview

Tuick is a command-line tool that runs build commands, parses their output for errors, and presents them in fzf for interactive selection. When a user selects an error, tuick opens the file at the error location in their editor.

**Key workflow**: `tuick command` → run command → parse output → group into blocks → feed to fzf → user selects → open editor at location

## Directory Structure

```
tuick/
├── src/tuick/          # Main source code
│   ├── cli.py          # Entry point, command routing, modes
│   ├── errorformat.py  # Errorformat subprocess wrapper, JSONL parsing
│   ├── tool_registry.py # Tool detection, errorformat patterns
│   ├── ansi.py         # ANSI code stripping
│   ├── console.py      # Logging, output formatting
│   ├── fzf.py          # fzf process management
│   ├── reload_socket.py # TCP coordination server
│   ├── monitor.py      # Filesystem watcher (watchexec)
│   ├── editor.py       # Editor command building, file locations
│   └── shell.py        # Shell quoting utilities
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

### fzf.py (120 lines)
**Purpose**: Launch and configure fzf process

**Key Functions**:
- `open_fzf_process(callbacks, user_interface, tuick_server_info, fzf_api_key)`
  - Spawns fzf with `--read0` (null-separated input)
  - Configures bindings: ctrl-r (reload), enter (select), / and ctrl-/ (preview)
  - Uses `--bind` for dynamic command injection
- `_check_bat_installed()` - Check if bat is available
- `_get_preview_command()` - Generate bat command or error message
- `_get_preview_window_config()` - Configure preview visibility

**fzf Configuration**:
- `--ansi` - Preserve ANSI colors
- `--read0` - Read null-separated records
- `--tac` - Reverse order (latest first)
- `--no-sort` - Preserve input order
- `--bind` - Dynamic key bindings
- `--preview` - Bat command for syntax-highlighted code preview
- `--preview-window` - Preview layout (hidden if TUICK_PREVIEW=0)

**Preview Feature**:
- Uses bat to show syntax-highlighted file at error location
- Enabled by default, hidden with TUICK_PREVIEW=0
- Toggle with / or ctrl-/
- Shows error message if bat not installed

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
**Purpose**: File location data structures and editor-specific command generation

**Data Structures**:
- `FileLocation` - Dataclass with path, row, column (used by CLI and editor modules)
- `FileLocationNotFoundError` - Exception for invalid location selections

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

### errorformat.py (178 lines)
**Purpose**: Errorformat subprocess wrapper, JSONL parsing, block formatting

**Key Functions**:
- `run_errorformat(tool, input_lines) -> Iterator[ErrorformatEntry]`
  - Runs errorformat subprocess with tool-specific patterns
  - Parses JSONL output into ErrorformatEntry objects

- `parse_with_errorformat(tool, lines) -> Iterator[str]`
  - Parse tool output preserving ANSI codes
  - Maps stripped lines to original colored lines
  - Yields null-terminated blocks

- `split_at_markers(lines) -> Iterator[tuple[bool, str]]`
  - Split stream at `\x02` and `\x03` markers
  - Used by top mode for two-layer parsing

- `wrap_blocks_with_markers(blocks) -> Iterator[str]`
  - Wrap blocks with `\x02` and `\x03` markers
  - Used by format mode for nested output

**Data Structures**:
- `ErrorformatEntry`: filename, lnum, col, end_lnum, end_col, lines, text, type, valid

### tool_registry.py (49 lines)
**Purpose**: Tool detection and errorformat pattern registry

**Registries**:
- `BUILTIN_TOOLS`: Tools with errorformat built-in support (flake8)
- `CUSTOM_PATTERNS`: Custom patterns for tools without built-in support
- `OVERRIDE_PATTERNS`: Override inadequate built-in patterns (mypy)
- `BUILD_SYSTEMS`: Build orchestrators (make, just, cmake, ninja)

**Key Functions**:
- `detect_tool(command) -> str`: Extract tool name from command
- `is_known_tool(tool) -> bool`: Check errorformat support
- `is_build_system(tool) -> bool`: Check if tool is build orchestrator

### ansi.py
**Purpose**: ANSI escape code handling

**Key Functions**:
- `strip_ansi(text) -> str`: Remove ANSI codes for parsing

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

### Errorformat Integration (Implemented)

**errorformat.py** - Errorformat subprocess wrapper:
- `run_errorformat()`: Run errorformat subprocess, yield parsed entries
- `parse_with_errorformat()`: Parse tool output, preserve ANSI codes
- `format_block_from_entry()`: Format errorformat entry as tuick block
- `split_at_markers()`: Split lines at `\x02` and `\x03` markers for top mode
- `wrap_blocks_with_markers()`: Wrap blocks with markers for format mode

**tool_registry.py** - Tool detection and patterns:
- `BUILTIN_TOOLS`: Tools with errorformat built-in patterns (flake8)
- `CUSTOM_PATTERNS`: Custom patterns for unsupported tools
- `OVERRIDE_PATTERNS`: Override patterns for inadequate built-ins (mypy)
- `BUILD_SYSTEMS`: Build system detection (make, just, cmake, ninja)
- `detect_tool()`: Extract tool name from command
- `is_known_tool()`: Check if tool has errorformat support
- `is_build_system()`: Check if tool is a build system

**cli.py** - Mode routing:
- Default mode (no flags): Auto-detect tool, route to list_command or top mode
- `--format`: format_command() - parse and output structured blocks
- `--top`: top_command() - orchestrator with two-layer parsing
- TUICK_PORT environment: nested mode behavior in default path

**Three modes**:
1. **List mode** (default for checkers): Run tool → parse → fzf
2. **Top mode** (default for build systems): Two-layer parsing with nested blocks
3. **Format mode** (`--format` or TUICK_PORT set): Parse and output blocks

**Block format**: `file\x1fline\x1fcol\x1fend-line\x1fend-col\x1fcontent\0`
**fzf config**: `--delimiter=\x1f --with-nth=6`

### Current Parsing Logic

**Location**: `errorformat.py` - all parsing now uses errorformat

**Algorithm**:
1. Strip ANSI codes while maintaining line mapping
2. Run errorformat subprocess with tool-specific patterns
3. Parse JSONL output into ErrorformatEntry objects
4. Apply tool-specific grouping (mypy, pytest, ruff)
5. Restore ANSI codes in output
6. Format as structured blocks

**Tool-specific patterns** (tool_registry.py):
- BUILTIN_TOOLS: Tools with errorformat built-in support
- CUSTOM_PATTERNS: Custom patterns for unsupported tools
- OVERRIDE_PATTERNS: Improved patterns for inadequate built-ins

### Output Format

**Current**: Structured blocks with delimiters
- Block format: `file\x1fline\x1fcol\x1fend-line\x1fend-col\x1fcontent\0`
- Blocks separated by null byte (`\0`) for fzf `--read0`
- fzf config: `--delimiter=\x1f --with-nth=6` to display only content

## Testing Infrastructure

**Location**: `tests/` directory

**Key Test Files**:
- `test_cli.py` - CLI integration tests
- `test_errorformat.py` - Errorformat parsing and block formatting tests
- `test_editor.py` - Editor command generation tests
- `test_reload_socket.py` - Coordination server tests
- `test_monitor.py` - Filesystem watcher tests
- `test_data.py` - Shared test data constants

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

### Adding New Tool Error Format

**Location**: `tool_registry.py` and `errorformat.py`

**Steps**:
1. Check if errorformat has built-in support: `errorformat -list`
2. If yes, add to BUILTIN_TOOLS in `tool_registry.py`
3. If no, add custom pattern to CUSTOM_PATTERNS
4. If built-in pattern is inadequate, add override to OVERRIDE_PATTERNS
5. Test with real tool output using `fmt_ef.py` helper script
6. Add tool-specific grouping logic to `errorformat.py` if needed (e.g., mypy, pytest)
7. Add tests in `test_errorformat.py` with actual tool output

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
