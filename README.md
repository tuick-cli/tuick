# Tuick, the Text-based User Interface for Compilers and checKers

Interactive error browser for command-line tools, powered by [`fzf`] and [`errorformat`].

## Features

- **Errorformat parsing**: Parse output from any tool with errorformat patterns
- **Multi-line error grouping**: Complex errors displayed as cohesive blocks
- **Fuzzy search**: Filter errors with fzf's powerful search
- **Editor integration**: Jump directly to error locations in your editor
- **Manual reload**: Press `r` in fzf to re-run the command
- **Auto-reload**: Automatic refresh on file changes using [`watchexec`]
- **Build system support**: Parse mixed output from make, just, etc.
- **Theme detection**: Automatic dark/light theme detection for fzf and bat

## Quick Start

```bash
tuick mypy .        # Parse and browse mypy errors
tuick ruff check    # Parse and browse ruff errors
```

Press `r` to reload manually, `Enter` to open in editor, `Ctrl-C` to exit.
Auto-reload triggers when files change (respects .gitignore and VCS ignore files).

## Usage Modes

### List Mode (Default)

Default mode when a compiler or checker is detected. Runs the command, parses output, and launches fzf:

```bash
tuick mypy .        # Auto-detect mypy
tuick ruff check    # Auto-detect ruff
tuick flake8        # Auto-detect flake8
tuick pytest        # Auto-detect pytest
```

### Top Mode

Parse output from build systems that orchestrate multiple tools:

```bash
tuick make          # Auto-detect make as build system
tuick just check    # Auto-detect just as build system
tuick --top script  # Explicit top mode for unrecognized commands
```

Build systems (make, just, cmake, ninja) are auto-detected and use top mode automatically.

Top mode sets `TUICK_PORT` environment variable so nested tuick commands output structured blocks.

### Format Mode

Explicitly parse tool output and output structured blocks:

```bash
tuick --format mypy .    # Always parse and output blocks
```

Typically called from build systems in top mode:

```makefile
# In Makefile:
check:
    tuick --format mypy .
    tuick --format ruff check
```

If `TUICK_PORT` is not set, streams tool output unchanged (passthrough mode).

## Command-Line Options

### Top-Level Options

- `-f`, `--format-name NAME` - Override autodetected errorformat name
- `-p`, `--pattern PATTERN` - Custom errorformat pattern(s), can be specified multiple times
- `--top` - Force top mode (override build system detection)
- `-v`, `--verbose` - Show verbose output
- `--theme THEME` - Color theme: `dark`, `light`, `bw`, `auto` (default: `auto`)

**Note**: `-f/--format-name` and `-p/--pattern` are mutually exclusive.

### Internal Options

These options are for internal use by tuick when communicating between processes:

- `--reload` - Run command and output blocks (called by fzf binding)
- `--select` - Open editor at error location (called by fzf binding)
- `--message TEXT` - Log a message (used for event logging)
- `--start` - Notify fzf port to parent process
- `--format` - Format mode: parse and output structured blocks

## Auto-Reload on File Changes

Tuick automatically monitors the filesystem and reloads on changes using [`watchexec`]:

- Monitors current directory recursively
- Honors .gitignore and other VCS ignore files by default
- Debounces rapid changes
- No configuration needed

## Theme Detection and Configuration

Tuick supports automatic theme detection for fzf and bat preview:

### Theme Priority Order

1. `--theme` CLI option (if not `auto`)
2. `CLI_THEME` environment variable
3. `NO_COLOR` environment variable (disables colors)
4. Automatic detection via:
   - OSC 11 terminal query (most accurate)
   - `COLORFGBG` environment variable
   - Default to `dark`

### Theme Options

- `dark` - Dark theme (dark background)
- `light` - Light theme (light background)
- `bw` - Black and white (no colors)
- `auto` - Automatic detection (default)

### Environment Variables

- `CLI_THEME` - Force theme: `dark`, `light`, or `bw`
- `NO_COLOR` - If set and non-empty, disables colors
- `COLORFGBG` - Terminal foreground/background colors
- `BAT_THEME` - Bat theme for syntax highlighting (preserved if set)
- `TUICK_PREVIEW` - Set to `0` to start with preview window hidden

## Editor Integration

Tuick opens files at error locations in your editor. Editor is selected in this order:

1. `TUICK_EDITOR` - Tuick-specific editor
2. `EDITOR` - Standard editor variable
3. `VISUAL` - Alternative editor variable

### Custom Editor Templates

For editors not automatically recognized, use these environment variables:

- `TUICK_EDITOR_LINE_COLUMN` - Template for line and column: `{editor} {file}:{line}:{col}`
- `TUICK_EDITOR_LINE` - Template for line only: `{editor} {file}:{line}`

Examples:

```bash
export TUICK_EDITOR="code"
export TUICK_EDITOR_LINE_COLUMN="{editor} -g {file}:{line}:{col}"
```

## Environment Variables (Internal)

These variables are set by tuick for communication with commands:

- `TUICK_PORT` - Port number for tuick coordination server
- `TUICK_API_KEY` - Authentication key for tuick server
- `TUICK_LOG_FILE` - Path to shared log file for all tuick processes
- `FORCE_COLOR` - Set to `1` for build commands when theme is not black-and-white

## Dependencies

**Required**:
- [`fzf`] - Interactive fuzzy finder
- [`errorformat`] - Error output parser (from reviewdog project)
- [`watchexec`] - Filesystem watcher for auto-reload

**Optional**:
- [`bat`] - Syntax-highlighted preview in fzf (highly recommended)

Install:

```bash
# macOS (via Homebrew)
brew install fzf watchexec bat

# errorformat (requires Go)
go install github.com/reviewdog/errorformat/cmd/errorformat@latest
```

## Supported Tools

Tuick supports all tools with [errorformat built-in patterns]. Run `errorformat -list` to see available formats:

```
ansible-lint, bandit, black, brakeman, buf, cargo-check, clippy, dotenv-linter,
dotnet, erb-lint, eslint, eslint-compact, fasterer, flake8, go-consistent,
golangci-lint, golint, gosec, govet, haml-lint, hlint, isort, luacheck,
misspell, msbuild, mypy, pep8, phpstan, protolint, psalm, puppet-lint,
pydocstyle, reek, remark-lint, rubocop, sbt, sbt-scalastyle, scalac, scalastyle,
slim-lint, sorbet, standardjs, standardrb, staticcheck, stylelint, tsc, tslint,
typos, yamllint
```

Additionally, tuick provides enhanced patterns for:

- **mypy** - Enhanced multi-line patterns with column support
- **ruff** - Enhanced patterns for both concise and full formats
- **pytest** - Custom multi-line patterns for test failures

Build systems (stub support - groups output into info blocks):
- **make**, **just**, **cmake**, **ninja**

Additional tools can be added by:
- Extending `tool_registry.py` for custom patterns
- Providing custom patterns via `-p/--pattern` option
- Using `-f/--format-name` to reference any errorformat built-in format

## Recommended: dmypy

Use [`dmypy`] for fast incremental type checking:

```bash
tuick dmypy run .
```

[`dmypy`] runs mypy as a daemon for fast incremental checks.

[`fzf`]: https://junegunn.github.io/fzf/
[`errorformat`]: https://github.com/reviewdog/errorformat
[errorformat built-in patterns]: https://github.com/reviewdog/errorformat
[`watchexec`]: https://github.com/watchexec/watchexec
[`dmypy`]: https://mypy.readthedocs.io/en/stable/mypy_daemon.html
[`bat`]: https://github.com/sharkdp/bat
