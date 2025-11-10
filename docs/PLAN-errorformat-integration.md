# Feature Plan: Reviewdog/Errorformat Integration

**Created**: 2025-11-09
**Updated**: 2025-11-10
**Status**: Approved - Ready for Implementation

## Goal

Add errorformat-based parsing with three modes:
- **Default**: `tuick ruff check` → auto-detect → parse → fzf (simple case)
- **Top**: `tuick make` → parse mixed stream → fzf (build system orchestrator)
- **Nested**: `tuick --format ruff check` → structured blocks output

## Three Modes

### Mode 1: Default (Simple Mode)

```bash
tuick ruff check              # Auto-detect tool, parse, launch fzf
tuick mypy .                  # No flags needed for common case
```

**Behavior**:
- If `TUICK_NESTED=1`: output structured blocks (behave as nested)
- If not: detect tool → parse → launch fzf

**Use case**: Direct invocation (95% of usage)

### Mode 2: Top/Orchestrator (`--top` or auto-detect)

```bash
tuick make                    # Auto-detect 'make' as build system
tuick just check              # Auto-detect 'just' as build system
tuick --top -f make custom    # Explicit format for unrecognized command
```

**Behavior**:
- Set `TUICK_NESTED=1` environment variable
- Run build command
- Parse mixed stream (two-layer):
  1. Split at `\x02` and `\x03` markers
  2. Parse build-system blocks with detected/explicit format
- Feed all to fzf

**Use case**: Build system that calls `tuick --format` for all subcommands

**Critical requirement**: Build system MUST use `tuick --format` for all subcommands (compilers, checkers, etc.). Otherwise top mode would incorrectly parse compiler output with build-system syntax.

**Two-layer parsing**:
- **Between `\x02...\x03`**: nested tuick blocks (pass through as-is)
- **Outside markers**: build-system output only (parse with build-system format)

**Build-system blocks contain ONLY**:
- Build-system errors (make syntax errors, just errors)
- Build-system messages (entering directory, target info)
- NOT compiler/checker output (handled by nested tuick)

### Mode 3: Nested (`--format`)

```bash
# In justfile/Makefile called by orchestrator:
check:
    tuick --format ruff check
    tuick --format mypy .
    tuick --format gcc compile.c
```

**Behavior**:
- If `TUICK_NESTED=1`: parse and output structured blocks with markers
- If not: streaming passthrough (no parsing, no fzf)

**Use case**: Called from build system, safe fallback

**Motivation**: Combined with top mode provides:
- `make` alone: non-interactive
- `tuick make`: interactive with all errors parsed

## Control Flow

### Simple Mode (Default)

```
User: tuick ruff check
  → detect tool: ruff
  → run command: subprocess
  → parse output: errorformat
  → fzf with blocks
  → select → open editor
```

### Top/Orchestrator Mode

```
User: tuick make
  → detect 'make' as build system
  → set TUICK_NESTED=1
  → run: make
      → make output: "make: Entering directory 'src'"
      → make calls: tuick --format gcc compile.c
          → output: \x02gcc-error1\0gcc-error2\x03
      → make output: "make: Leaving directory 'src'"
      → make calls: tuick --format ruff check
          → output: \x02ruff-error1\x03
  → stream: "make: Entering...\n\x02gcc-error1\0gcc-error2\x03\nmake: Leaving...\n\x02ruff-error1\x03"
  → two-layer parsing:
      1. Split at markers:
         - "make: Entering...\n" → build-system block
         - gcc-error1\0gcc-error2 (from \x02...\x03, pass through)
         - "make: Leaving...\n" → build-system block
         - ruff-error1 (from \x02...\x03, pass through)
      2. Parse build-system blocks with 'make' format:
         - "make: Entering..." → informational block
         - "make: Leaving..." → informational block
  → feed to fzf: entering-info\0gcc-error1\0gcc-error2\0leaving-info\0ruff-error1
```

### Nested Mode (--format)

```
Build system: tuick --format gcc compile.c
  → check TUICK_NESTED
      → if set: parse and output blocks with markers
      → if not: streaming passthrough
```

## Components

### Default Mode: `tuick COMMAND`

**Processing**:
1. Check `TUICK_NESTED` env var
   - If set: run as nested mode (output blocks)
   - If not: continue to simple mode
2. Detect tool from command
3. Run command subprocess
4. Parse output with errorformat
5. Launch fzf with blocks
6. Handle selection → open editor

### Top/Orchestrator Mode: `tuick --top COMMAND` or auto-detect

**Processing**:
1. Detect build system from command OR use explicit `--top`
2. Set `TUICK_NESTED=1`
3. Run build command subprocess
4. Parse mixed stream (two-layer):
   - **Layer 1**: Split at `\x02` and `\x03` markers
     - Between markers: pass through as-is (already formatted)
     - Outside markers: build-system output
   - **Layer 2**: Parse build-system blocks
     - Detect format from command (make, just, etc.)
     - Or explicit: `--top -f <format>`
     - Parse build-system errors and messages
5. Launch fzf with all blocks
6. Handle selection → open editor

**Auto-detection**: Recognize build systems (just, make, npm run, gradle, etc.)

**Format detection/specification**:
- Auto: detect from command name
- Explicit: `-f <name>` or `-e <pattern>`

### Nested Mode: `tuick --format COMMAND`

**Processing**:
1. Check `TUICK_NESTED` env var
   - If not set: passthrough (stream command output unchanged)
   - If set: continue
2. Detect tool from command
3. Run command subprocess
4. Parse output with errorformat
5. Output structured blocks:
   - Start marker: `\x02`
   - Blocks: `file\x1fline\x1fcol\x1fend-line\x1fend-col\x1fcontent\0`
   - End marker: `\x03`
   - **NO trailing `\0` after last block** (before `\x03`)

**Output format**: `\x02block1\0block2\0blockN\x03`

**Note**: `\0` is block separator, not terminator

**Options**:
- `-f auto` (default): detect from command
- `-f <name>`: explicit format name
- `-e <pattern>`: custom errorformat pattern

### Block Format

```
file\x1fline\x1fcol\x1fend-line\x1fend-col\x1fcontent\0
```

**Fields**:
1-5: Location (empty for informational blocks)
6: Original text with ANSI codes (multiple lines joined with \n)

**fzf config**: `--delimiter=\x1f --with-nth=6`

### Block Boundaries

How does errorformat indicate block structure?
- Multi-line patterns: `%A` (start), `%C` (continuation), `%Z` (end)
- Does errorformat output metadata about line types?
- Or infer from location changes?

Research required.

## Tool Detection

```python
ERRORFORMAT_MAP = {
    "ruff": "%f:%l:%c: %m",
    "mypy": "%f:%l:%c: %t%*[^:]: %m",
    "flake8": "%f:%l:%c: %m",
    "pylint": "%f:%l: %m",
    "pytest": "%f:%l: %m",
}

def detect_tool(cmd: list[str]) -> str:
    # ["ruff", "check"] → "ruff"
    # ["python", "-m", "pytest"] → "pytest"
```

## Sequential Commits (TDD)

### 1. Write xfail integration tests
- Test 1: Simple mode (`tuick ruff check`)
- Test 2: Top-format mode (`tuick make` with nested `tuick --format`)
- Test 3: Format passthrough (`tuick --format` without `TUICK_NESTED`)
- Mark as xfail, commit as failing tests

### 2. Add --format and --top to CLI
- Route to format_command() and top_command()
- Options: -f, -e
- Environment variable: TUICK_NESTED

### 3. Tool detection (for all modes)
- `errorformats.py`: ERRORFORMAT_MAP, detect_tool()
- Support both build systems and checkers
- Tests: detection logic for various tools

### 4. Errorformat wrapper
- `errorformat.py`: subprocess, parse output
- Strip ANSI → errorformat → extract locations
- Research: block boundary detection
- Tests: location extraction

### 5. Block assembly with markers
- `blocks.py`: buffer, boundaries, format
- Add marker support (`\x02`, `\x03`)
- Field format: `file\x1fline\x1fcol\x1fend-line\x1fend-col\x1fcontent\0`
- Tests: block formation, marker handling

### 6. Implement format_command (nested mode)
- Check TUICK_NESTED env var
- Passthrough if not set
- Parse and output with markers if set
- Remove xfail from Test 3

### 7. Implement top_command (orchestrator mode)
- Set TUICK_NESTED=1
- Two-layer parsing: split markers, parse build-system blocks
- Auto-detect build systems
- Remove xfail from Test 2

### 8. Update default command for TUICK_NESTED
- Check env var in main flow
- Output blocks if set, launch fzf if not
- Remove xfail from Test 1

### 9. Update fzf integration for delimiters
- Configure fzf with `--delimiter=\x1f --with-nth=6`
- Update select binding to pass fields

### 10. Update select_command
- Receive location fields from fzf
- Build FileLocation from fields

### 11. Update reload_command
- Ensure mode and format propagation
- Tests: reload preserves mode/format

### 12. Documentation
- README: three modes, usage examples
- codebase-map.md: architecture updates
- errorformat-guide.md: format patterns
- Update TODO.md

## Open Questions

- How does errorformat handle multi-line blocks?
- Does errorformat expose line type metadata?
- Does errorformat strip ANSI codes?
- How to detect block boundaries from errorformat output?

## Success Criteria

- [ ] Build tool can call `tuick --format checker`
- [ ] Blocks output correctly formatted
- [ ] fzf shows only content field
- [ ] Select extracts location from fields
- [ ] Reload works through build tool
- [ ] Tests pass: `just agent`

## Appendix A: Errorformat Research Findings

### Output Formats

From reviewdog/errorformat research:

**errorformat CLI** outputs in these modes:
- Default: prints matched errors line by line
- Format: `file:line:col: message` (or custom format)
- Does NOT provide structured output (no JSON, no delimiters)

**Key limitations**:
- No built-in block grouping
- No line type metadata in output
- ANSI handling: unknown, requires testing

### Multi-line Block Detection

Errorformat supports patterns for multi-line errors:
- `%A` - start of multi-line error
- `%C` - continuation line
- `%Z` - end of multi-line error
- `%+` - multi-line message continuation

**Unknown**: How these are represented in errorformat output.

**Investigation needed**:
1. Test errorformat with multi-line pattern
2. Check if output includes block markers
3. If not, implement block detection from location changes

### ANSI Code Handling

**Unknown**: Does errorformat strip ANSI codes?

**Test approach**:
1. Pipe ANSI-colored output through errorformat
2. Check if colors are stripped or preserved
3. Document behavior

If errorformat doesn't strip ANSI:
- We strip before passing to errorformat
- Keep original for output

### Alternative: Parse errorformat Pattern Definition

Instead of using errorformat as subprocess, parse the pattern ourselves:
- Convert Vim errorformat to regex
- Apply regex to lines
- Detect blocks from pattern structure

**Pros**: Full control, no subprocess overhead
**Cons**: Need to implement Vim errorformat parser

Consider if errorformat subprocess is inadequate.

## Appendix B: Block Boundary Strategies

### Strategy 1: Location Change

New block when:
- File changes
- Line number changes significantly (not +1)
- Blank line appears

**Simple but may split related errors.**

### Strategy 2: State Machine (Current Approach)

Current parser.py uses state machine with:
- `NOTE_CONTEXT` state for mypy notes
- `PYTEST_BLOCK` state for pytest sections
- `SUMMARY` state for summary lines

**Port to errorformat-based parser if needed.**

### Strategy 3: Pattern-Based

Use errorformat multi-line patterns to define boundaries:
- Pattern with `%A...%Z` defines a block
- Everything between `%A` and `%Z` is one block

**Requires errorformat to expose block structure.**

### Strategy 4: Hybrid

Combine strategies:
- Use errorformat for location extraction
- Use heuristics (location change, blank lines) for boundaries
- Use state machine for special cases (pytest, mypy notes)

**Most robust but complex.**

## Appendix C: fzf Integration Details

### Current fzf Configuration

From cli.py, current fzf call:
```python
open_fzf_process(
    blocks=blocks,
    bindings={
        "start": callback.start(),
        "load": callback.load(),
        "reload": callback.reload(),
        "select": callback.select(),
    },
    initial_port=server.port if server else None,
)
```

### Required Changes

**Add delimiter config**:
```python
fzf_args = [
    "--read0",
    "--delimiter=\x1f",
    "--with-nth=6",  # Show only content field
    # ... existing args
]
```

**Update select binding**:
```python
"--bind=enter:execute(tuick --select {1} {2} {3} {4} {5})"
```

fzf will substitute:
- `{1}` = file
- `{2}` = line
- `{3}` = col
- `{4}` = end-line
- `{5}` = end-col

### Field Extraction in select_command

```python
def select_command(
    file: str,
    line: str,
    col: str,
    end_line: str,
    end_col: str,
):
    """Handle selection from fzf."""
    if not file:
        # Informational block
        if verbose:
            print("Informational block (no location)")
        return

    location = FileLocation(
        path=file,
        row=int(line) if line else None,
        column=int(col) if col else None,
    )
    # Open editor...
```

## Appendix D: Dependencies

### Required: errorformat CLI

**Installation**:
```bash
go install github.com/reviewdog/errorformat/cmd/errorformat@latest
```

**Verify**:
```bash
errorformat --version
```

**Document in README**: errorformat is required dependency.

### Optional: reviewdog

Not needed for this implementation. We only use errorformat library.

## Appendix E: Backward Compatibility

### Migration Strategy

Keep current parser.py logic temporarily:
- Use for fallback if errorformat unavailable
- Use for testing comparison
- Remove after validation period

### Compatibility Checks

- [ ] Existing justfile commands still work
- [ ] Saved output format unchanged (raw text)
- [ ] Editor selection behavior unchanged
- [ ] Reload mechanism unchanged

## Appendix F: Testing Strategy

### Unit Tests

- Tool detection from various command formats
- Errorformat subprocess invocation
- Block assembly from parsed lines
- Field formatting with delimiters

### Integration Tests

- End-to-end: ruff check → blocks → fzf (mock fzf)
- End-to-end: mypy . → blocks
- End-to-end: pytest → blocks
- Reload: format preserved through reload
- Select: location extracted from fields

### Manual Testing

Create test files with known errors:
- `test_errors.py` with type errors, unused imports
- Run `tuick --format ruff check test_errors.py`
- Verify blocks formatted correctly
- Verify fzf displays content only
- Verify selection opens editor at correct location

## Appendix G: Performance Considerations

### Subprocess Overhead

errorformat subprocess per format command:
- Startup: ~10-50ms
- Processing: depends on output size

**Acceptable** for build tool integration (not latency-sensitive).

### Block Buffering

Must buffer lines until block complete:
- Memory usage: proportional to largest block
- Typically small (< 1KB per block)

**Monitor** if large blocks cause issues.

### Streaming Output

Emit blocks as soon as complete (don't wait for full command output).

Ensure prompt feedback for interactive use.
