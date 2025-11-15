# Plan: Remove Legacy Parser Code

## ✅ Task 1: Add -f/--format-name and -p/--pattern CLI options (COMPLETED)

### Completed implementation:
1. Added CLI options to `main()` in cli.py:
   - `-f/--format-name` (str): Override autodetected format
   - `-p/--pattern` (list[str]): Custom errorformat patterns (mutually exclusive with -f)
   - Passed to: `list`, `reload`, `format`, `top` commands

2. Created FormatConfig sum type:
   - `FormatName(format_name: str)` for named formats
   - `CustomPatterns(patterns: list[str])` for custom patterns
   - `_create_format_config()` validates and creates config

3. Format validation:
   - Checks BUILTIN_TOOLS, CUSTOM_PATTERNS, OVERRIDE_PATTERNS
   - Queries errorformat builtin formats (cached)
   - Accepts build systems (stub patterns: %C%m, %A%m)

4. Updated errorformat.py:
   - `parse_with_errorformat()` accepts FormatConfig parameter
   - Pattern matching selects patterns vs -name= flag

5. Pass options through fzf bindings:
   - `CallbackCommands` builds format_opts from config
   - Included in manual reload and auto-reload bindings

**COMMITTED** b45bd47: ✨ Add -f/--format-name and -p/--pattern CLI options

## Task 2: Update reload_command to use errorformat parsing

### Current state:
- `reload_command()` calls `_process_output_and_yield_raw()` (cli.py:405)
- `_process_output_and_yield_raw()` calls `split_blocks_auto()` (cli.py:341)
- `split_blocks_auto()` dispatches to errorformat OR legacy parser

### Changes:
- Replace `split_blocks_auto()` call with direct errorformat parsing
- Use new -f/-p options if provided
- Remove legacy fallback path

## Task 3: Remove legacy parser code from parser.py

### Code to remove:
- `State` enum (lines 20-27)
- `LineType` enum (lines 30-38)
- `classify_line()` function (line 118)
- `extract_location_str()` function (line 133)
- `BlockSplitter` class (lines 146-255)
- `split_blocks()` function (line 257)
- `split_blocks_errorformat()` function (line 271) - moved to errorformat.py
- `split_blocks_auto()` function (line 276)
- `get_location()` function (line 290)
- All regex patterns:
  - `LINE_REGEX`, `MYPY_NOTE_REGEX`, `SUMMARY_REGEX`
  - `PYTEST_SEP_REGEX`, `LINE_LOCATION_REGEX`, `RUFF_LOCATION_REGEX`

### Code to keep:
- `FileLocation` dataclass (used by cli.py, editor.py)
- `FileLocationNotFoundError` exception (may still be used)
- Consider renaming parser.py → location.py for clarity

**COMMIT AFTER TASK 3** with: ✨ Add format override options, remove legacy parser

---

## Task 4: Move shared test data to separate module

### Create tests/test_data.py with:
- `MYPY_BLOCKS`, `MYPY_FANCY_BLOCKS`, `MYPY_ABSOLUTE_BLOCKS`, `MYPY_VERY_FANCY_BLOCKS`
- `RUFF_FULL_BLOCKS`, `RUFF_CONCISE_BLOCKS`
- `PYTEST_AUTO_BLOCKS`, `PYTEST_SHORT_BLOCKS`, `PYTEST_LINE_BLOCKS`, `PYTEST_TRICKY_BLOCKS`

### Update imports:
- test_errorformat.py: import from test_data instead of test_parser
- Future tests can also import from test_data

## Task 5: Remove obsolete tests from test_parser.py

### Tests to remove (all 7 functions):
1. `test_split_blocks_mypy` - ported to test_errorformat
2. `test_split_blocks_ruff` - ported to test_errorformat
3. `test_split_blocks_pytest` - ported to test_errorformat
4. `test_get_location` - obsolete (errorformat encodes location in fields)
5. `test_classify_line_with_ansi` - internal testing of removed function
6. `test_extract_location_str_with_ansi` - internal testing of removed function
7. `test_get_location_with_ansi` - obsolete (errorformat handles this)

### Delete test_parser.py entirely after moving test data

## Task 6: Update documentation

### docs/codebase-map.md:
- Remove parser.py references to BlockSplitter, split_blocks
- Update parser.py description if keeping it (just FileLocation)
- Or remove parser.py section if renaming to location.py

### Update TODO.md:
- Remove "Port existing parser patterns to errorformat" (completed)
- Add any new refactoring tasks identified

## Execution Order:

1. Add -f/-p options (Task 1) and remove fallback to legacy parser
2. **COMMIT** ✨ Add format override options
3. Update reload to use errorformat (Task 2)
4. **COMMIT** 🐛 Fix reload to use errorformat
5. Move shared test data (Task 4)
6. Remove legacy parser code (Task 3)
7. Remove obsolete tests (Task 5)
8. Update documentation (Task 6)
9. **COMMIT** ⚰️ Remove obsolete parser code and tests

## Notes:

- Complete execution won't fit in one session
- Plan broken into two commits for incremental progress
- Run `just agent` before each commit
