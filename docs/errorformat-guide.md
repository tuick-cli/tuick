# Errorformat Integration Guide

## Overview

Tuick uses [errorformat](https://github.com/reviewdog/errorformat) to parse tool output into structured error blocks. This guide explains how errorformat integration works and how to add support for new tools.

## How Errorformat Works

Errorformat uses Vim's errorformat patterns to parse compiler and checker output:

1. Tool runs and produces output (possibly with ANSI color codes)
2. Tuick strips ANSI codes and feeds output to errorformat subprocess
3. Errorformat parses output using tool-specific patterns
4. Errorformat outputs JSONL - one JSON object per error message (potentially multi-line)
5. Tuick restores ANSI codes and formats blocks for fzf

## Block Format

Tuick uses a structured block format for fzf:

```
file\x1fline\x1fcol\x1fend-line\x1fend-col\x1fcontent\0
```

Fields (separated by `\x1f` unit separator):
1. **file**: File path
2. **line**: Line number (empty for informational blocks)
3. **col**: Column number (empty if not available)
4. **end-line**: End line number (currently unused)
5. **end-col**: End column number (currently unused)
6. **content**: Original multi-line text with ANSI codes preserved

Blocks are terminated with `\0` (null byte) for fzf's `--read0` option.

fzf is configured with `--delimiter=\x1f --with-nth=6` to display only the content field.

## Errorformat JSONL Output

Each error message produces one JSONL object:

```json
{
  "filename": "file.py",
  "lnum": 10,
  "col": 5,
  "text": "error message",
  "type": "E",
  "valid": true,
  "lines": [
    "file.py:10:5: error message",
    "    continuation line",
    "    another line"
  ]
}
```

The `lines` array contains all lines belonging to this error message (potentially multi-line).

## Tool Registry

Tools are registered in `src/tuick/tool_registry.py`:

### BUILTIN_TOOLS

Tools with errorformat built-in patterns:

```python
BUILTIN_TOOLS: set[str] = {"flake8"}
```

Uses errorformat's `-name=tool` option.

### OVERRIDE_PATTERNS

Override inadequate built-in patterns:

```python
OVERRIDE_PATTERNS: dict[str, list[str]] = {
    "mypy": [
        "%E%f:%l:%c: %m",  # file:line:col: msg (start multi-line error)
        "%E%f:%l: %m",     # file:line: msg (start multi-line error)
        "%+C    %.%#",     # continuation: 4 spaces + anything
        "%G%.%#",          # general/informational lines (preserved)
    ],
}
```

Example: mypy's built-in pattern doesn't handle `--show-column-numbers` or multi-line blocks properly.

### CUSTOM_PATTERNS

Custom patterns for tools without built-in support:

```python
CUSTOM_PATTERNS: dict[str, list[str]] = {
    "newtool": [
        "%f:%l:%c: %m",  # Basic pattern
    ],
}
```

### BUILD_SYSTEMS

Build systems that orchestrate multiple tools:

```python
BUILD_SYSTEMS: set[str] = {"make", "just", "cmake", "ninja"}
```

These automatically use top mode with two-layer parsing.

## Adding Tool Support

### Step 1: Test with errorformat

First, test if the tool works with errorformat's built-in patterns:

```bash
# List available built-in patterns
errorformat -list

# Test with built-in pattern
your_tool | errorformat -w=jsonl -name=your_tool
```

### Step 2: Add to Registry

If built-in works:

```python
# In tool_registry.py
BUILTIN_TOOLS: set[str] = {"flake8", "your_tool"}
```

If built-in doesn't exist or is inadequate, add custom pattern:

```python
CUSTOM_PATTERNS: dict[str, list[str]] = {
    "your_tool": [
        "%f:%l:%c: %m",  # Your pattern here
    ],
}
```

Or override built-in:

```python
OVERRIDE_PATTERNS: dict[str, list[str]] = {
    "your_tool": [
        # Better patterns here
    ],
}
```

### Step 3: Add Tests

Add integration test in `tests/test_errorformat.py`:

```python
def test_your_tool_format():
    """Test your_tool errorformat pattern."""
    tool_output = """
    file.py:10:5: error message
    """

    blocks = list(parse_with_errorformat("your_tool", tool_output.splitlines(keepends=True)))

    assert len(blocks) == 1
    assert "file.py\x1f10\x1f5\x1f\x1f\x1ffile.py:10:5: error message\0" in blocks[0]
```

Use real tool output (run the tool to capture actual output).

## Errorformat Pattern Syntax

Quick reference for errorformat patterns:

- `%f` - File name
- `%l` - Line number
- `%c` - Column number
- `%m` - Error message
- `%t` - Error type (single character: E, W, etc.)
- `%n` - Error number
- `%s` - Search pattern

**Multi-line patterns**:
- `%E` - Start of multi-line error message
- `%C` - Continuation of multi-line message
- `%Z` - End of multi-line message
- `%A` - Start of multi-line message (all lines included)
- `%G` - General message (always matched, doesn't end block)
- `%+C` - Continuation including next line(s)

**Pattern matching**:
- `%.%#` - Match anything (like `.*` in regex)
- `%*[...]` - Match and ignore character class
- `%-` - Ignore this match

See [errorformat documentation](https://github.com/reviewdog/errorformat#vim-errorformat) for complete syntax.

## Common Patterns

### Simple one-line errors

```
file:line:col: message
```

Pattern:
```python
"%f:%l:%c: %m"
```

### No column number

```
file:line: message
```

Pattern:
```python
"%f:%l: %m"
```

### Multi-line errors with indentation

```
file:line:col: message
    continuation line
    another continuation
```

Pattern:
```python
[
    "%E%f:%l:%c: %m",  # Start of error
    "%+C    %.%#",      # Continuation (4 spaces + anything)
]
```

Errorformat will output one JSONL object with all lines in the `lines` array.

### Ruff-style arrows

```
file:line:col: message
  --> file:line:col
```

Pattern:
```python
[
    "%f:%l:%c: %m",
    "%+C  --> %.%#",
]
```

### Pytest-style sections

```
================================= FAILURES =================================
_______________________________ test_foo ___________________________________
file:line: AssertionError
```

Pattern (complex - requires state machine, not pure errorformat):
```python
# Best handled by custom parsing in parser.py
```

## Limitations

### Duplicate Lines

Current implementation uses dict mapping from stripped lines to original ANSI lines. This fails if duplicate stripped lines exist.

Workaround: Sequential matching algorithm (TODO in TODO.md).

### Complex State Machines

Some formats (pytest sections, Make output) require complex state machines beyond errorformat's capabilities. These may need custom parsing in parser.py.

### Line Grouping

Errorformat may split related errors at the same location into separate entries (e.g., mypy note lines). These need grouping (TODO in TODO.md).

## Debugging

### Verbose Mode

Run with `-v` to see detailed output:

```bash
tuick -v mypy .
```

### Manual Testing

Test errorformat directly:

```bash
# Run your tool
your_tool > output.txt 2>&1

# Test with errorformat
cat output.txt | errorformat -w=jsonl -name=your_tool

# Or with custom pattern
cat output.txt | errorformat -w=jsonl -f '%f:%l:%c: %m'
```

### Check Tool Detection

```bash
# See what tool is detected
tuick -v your_tool args
# Look for "Detected tool: ..." in output
```

## Future Improvements

See TODO.md for planned improvements:

- Errorformat line matching algorithm for duplicate lines
- Group errorformat entries by location for multi-line blocks
- Port existing parser.py patterns to errorformat
- Custom pattern command-line options (`-f`, `-e`)
