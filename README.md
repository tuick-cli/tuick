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

## Auto-reload on File Changes

Tuick automatically monitors the filesystem and reloads on changes using [`watchexec`]:

- Monitors current directory recursively
- Honors .gitignore and other VCS ignore files by default
- Debounces rapid changes
- No configuration needed

## Dependencies

**Required**:
- [`fzf`] - Interactive fuzzy finder
- [`errorformat`] - Error output parser (from reviewdog project)
- [`watchexec`] - Filesystem watcher for auto-reload

Install:

```bash
# fzf
brew install fzf

# errorformat
go install github.com/reviewdog/errorformat/cmd/errorformat@latest

# watchexec
brew install watchexec
```

## Supported Tools

Currently supported tools with errorformat patterns:
- **mypy**: Type checker (custom multi-line error patterns)
- **flake8**: Python linter (built-in errorformat pattern)

Additional tools can be added by extending `tool_registry.py`.

## Recommended: dmypy

Use [`dmypy`] for fast incremental type checking:

```bash
tuick dmypy run .
```

[`dmypy`] runs mypy as a daemon for fast incremental checks.

[`fzf`]: https://junegunn.github.io/fzf/
[`errorformat`]: https://github.com/reviewdog/errorformat
[`watchexec`]: https://github.com/watchexec/watchexec
[`dmypy`]: https://mypy.readthedocs.io/en/stable/mypy_daemon.html
