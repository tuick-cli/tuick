# fzf Reference

Complete reference for fzf command-line fuzzy finder.

## Overview

fzf is an interactive filter for command-line lists, implementing fuzzy matching to rapidly locate patterns even with omitted characters. Typically piped data through stdin and outputs selected items to stdout.

## Invocation & Basic Usage

```bash
command | fzf [options]
fzf < input_file
```

## Search Modes & Options

| Option | Description |
|--------|-------------|
| `-x, --extended` | Extended-search mode (default): fuzzy, exact, anchored, negation patterns |
| `-e, --exact` | Exact-match mode only |
| `-i, --ignore-case` | Case-insensitive matching |
| `--smart-case` | Case-insensitive unless query contains uppercase |
| `--scheme=[default\|path\|history]` | Scoring algorithm variant |
| `--algo=[v2\|v1]` | v2: optimal scoring; v1: faster |

## Input/Output

| Option | Description |
|--------|-------------|
| `--read0` | Read NUL-delimited input (instead of newlines) |
| `--print0` | Output NUL-delimited results |
| `--ansi` | Process and preserve ANSI color codes in input |
| `-f, --filter=STR` | Non-interactive filter mode (output matching lines) |
| `-q, --query=STR` | Set initial query string |
| `--print-query` | Include query as first line of output |

## Field Operations

Use field operations to extract and manipulate specific columns/fields within lines.

### Delimiter & Field References

| Option | Description |
|--------|-------------|
| `-d, --delimiter=STR` | Define field delimiter (plain string preferred over regex for speed) |
| `-n, --nth=FIELDS` | Limit search scope to specified fields only |
| `--with-nth=FIELDS` | Transform display to show only specified fields (original line still output) |
| `--accept-nth=FIELDS` | Output specified fields instead of full line |

### Field Syntax

Field expressions follow these patterns:

| Syntax | Meaning |
|--------|---------|
| `1` | First field |
| `-1` | Last field |
| `3..5` | Fields 3 through 5 inclusive |
| `2..` | Field 2 to end |
| `..` | All fields |
| `1,3,5` | Specific fields (comma-separated) |

Examples:
```bash
# Search only field 3, display full line
echo -e "a:b:c\nd:e:f" | fzf --delimiter : --nth 3

# Show only fields 2 and 3, search all fields
echo -e "a:b:c\nd:e:f" | fzf --delimiter : --with-nth 2,3

# Output only first and third fields
echo -e "a:b:c:d\ne:f:g:h" | fzf --delimiter : --accept-nth 1,3
```

## Selection Options

| Option | Description |
|--------|-------------|
| `-m, --multi[=MAX]` | Enable multi-select (optionally limit count) |
| `-1, --select-1` | Auto-select if exactly one match |
| `-0, --exit-0` | Exit cleanly if no matches (exit 0 instead of 1) |
| `--cycle` | Enable circular scrolling |
| `--track` | Track selections when results update |

## Display & Layout

### Window Positioning

| Option | Description |
|--------|-------------|
| `--height=[~]HEIGHT[%]` | Window height (absolute or percentage; `~` for no upper bound) |
| `--layout=[default\|reverse\|reverse-list]` | Prompt position: default (bottom), reverse (top), reverse-list (top, list reversed) |
| `--border[=STYLE]` | Add border: rounded, sharp, bold, double, block, horizontal, vertical |
| `--margin=TOP,RIGHT,BOTTOM,LEFT` | Spacing around finder window |
| `--padding=TOP,RIGHT,BOTTOM,LEFT` | Internal padding |
| `--scroll-off=N` | Keep N lines visible during scrolling |

### Styling

| Option | Description |
|--------|-------------|
| `--color=SCHEME[,...]` | Color configuration (base16, solarized, dracula, etc.) |
| `--ansi` | Process ANSI color codes in input |

Color syntax:
```
--color=base16
--color=fg:200,bg:237,fg+:229,bg+:235,hl:38,hl+:208
```

Attributes: `bold`, `underline`, `reverse`, `dim`, `italic`, `blink`

### Preview Window

| Option | Description |
|--------|-------------|
| `--preview=CMD` | Display preview using command (supports placeholders) |
| `--preview-window=[SIDE,]SIZE[%][,OPTS]` | Position and size preview: side (right/left/up/down), size (absolute/percentage) |
| `-–preview-window=follow` | Auto-scroll preview (for log tailing) |

Environment variables available to preview command:
- `FZF_PREVIEW_LINES`: Height of preview pane
- `FZF_PREVIEW_COLUMNS`: Width of preview pane

## Field References & Placeholders

Use placeholders in `--preview`, `--bind` execute actions, and similar contexts.

| Placeholder | Meaning |
|-------------|---------|
| `{}` | Current line (automatically single-quoted) |
| `{+}` | All selected items (multi-select) |
| `{*}` | All matched items in current result |
| `{n}` | Zero-based line index of current item |
| `{q}` | Current query string |
| `{q:N}` | Nth query string from split |
| `{1}` | First field (using delimiter, automatically quoted) |
| `{2}` | Second field (automatically quoted) |
| `{-1}` | Last field (automatically quoted) |
| `{3..5}` | Fields 3-5 joined by space (automatically quoted) |
| `{1..}` | All fields (1 to end, automatically quoted) |
| `{..}` | All fields (automatically quoted) |

### Placeholder Quoting Behavior

**Automatic Single-Quoting**: By default, fzf automatically wraps all placeholder expansions in single quotes. This makes it safe to use placeholders in shell commands without manual escaping, even when field values contain spaces or special characters.

Examples of how placeholders are substituted:

```bash
# Placeholder: {}
# If selected line is: "hello world"
# fzf executes: echo 'hello world'
--bind 'enter:execute(echo {})'

# Placeholder: {1} {2}
# If input is "field1:field2" with --delimiter :
# fzf executes: echo 'field1' 'field2'
--bind 'enter:execute(echo {1} {2})' --delimiter :

# Placeholder: {}
# If line contains special chars: "test & file.txt"
# fzf executes: echo 'test & file.txt'
# The single quotes prevent shell interpretation of &
--bind 'enter:execute(echo {})'
```

**Raw Flag (Disable Quoting)**: Use the raw flag (`r`) to get unquoted placeholder values. This is useful when the placeholder content should be directly interpreted by the shell (use with caution, as it can lead to injection vulnerabilities).

```bash
# {r} - raw/unquoted current line
{r}

# {r1}, {r2} - raw/unquoted field references
{r1}
{r2}
```

Example with raw flag:
```bash
# Dangerous: if field contains shell metacharacters
--bind 'enter:execute(echo {r1})'  # NOT recommended for untrusted input

# This would expand "test & file" without quotes,
# potentially executing "&" as a shell operator
```

**Whitespace Preservation**: By default, leading and trailing whitespace is stripped from field references. Use the `s` flag to preserve whitespace.

```bash
# {s1}, {s2} - field reference with leading/trailing whitespace preserved
{s1}
{s2}
```

Example with whitespace preservation:
```bash
# Input: "  padded field  :  another  " with --delimiter :
# {1} expands to: 'padded field'  (whitespace trimmed)
# {s1} expands to: '  padded field  '  (whitespace preserved, then quoted)
--bind 'enter:execute(echo {s1})'
```

Examples:
```bash
# Preview with current line (safely quoted)
fzf --preview 'cat {}'

# Open file at line number
git grep --line-number . | fzf --delimiter : --preview 'cat {1}:{2}'

# Execute with field extraction (fields automatically quoted)
fzf --delimiter , --bind 'enter:execute(echo {1} {2})'

# Multi-select: all selected items, automatically quoted
fzf -m --bind 'enter:execute(process {+})'

# Pass to command that needs raw output (less safe, use with caution)
fzf --bind 'enter:execute(eval {r})'  # NOT recommended
```

## Key Bindings & Actions

### Binding Syntax

```bash
--bind=KEY_SEQUENCE:ACTION
--bind=EVENT:ACTION
```

Multiple bindings:
```bash
--bind='enter:accept,esc:abort' --bind='ctrl-a:select-all'
```

### Standard Keys

`enter`, `esc`, `tab`, `alt+enter`, `ctrl+a`, `ctrl+c`, `ctrl+d`, `ctrl+e`, `ctrl+f`, `ctrl+g`, `ctrl+h`, `ctrl+k`, `ctrl+l`, `ctrl+n`, `ctrl+p`, `ctrl+q`, `ctrl+r`, `ctrl+s`, `ctrl+t`, `ctrl+u`, `ctrl+v`, `ctrl+w`, `ctrl+x`, `ctrl+y`, `ctrl+z`

Function keys: `f1` through `f12`

### Selection Actions

| Action | Description |
|--------|-------------|
| `accept` | Accept current selection and exit |
| `abort` | Cancel without selection |
| `toggle` | Toggle selection of current item |
| `select` | Select current item |
| `deselect` | Deselect current item |
| `select-all` | Select all items |
| `deselect-all` | Deselect all |
| `clear-multi` | Clear multi-select (keep current) |
| `clear-selection` | Clear current selection |

### Navigation Actions

| Action | Description |
|--------|-------------|
| `first` | Move to first item |
| `last` | Move to last item |
| `up` | Move up one item |
| `down` | Move down one item |
| `page-up` | Move up one page |
| `page-down` | Move down one page |
| `pos(N)` | Move to Nth position |

### Text Manipulation

| Action | Description |
|--------|-------------|
| `kill-line` | Delete line from cursor to end |
| `kill-word` | Delete word under cursor |
| `unix-line-discard` | Delete entire line |
| `backward-char` | Move cursor left |
| `forward-char` | Move cursor right |
| `backward-word` | Move cursor one word left |
| `forward-word` | Move cursor one word right |
| `beginning-of-line` | Move cursor to line start |
| `end-of-line` | Move cursor to line end |

### Query & Display

| Action | Description |
|--------|-------------|
| `change-query(STR)` | Replace query with string |
| `change-prompt(STR)` | Change prompt text |
| `change-preview(CMD)` | Change preview command |
| `change-preview-window(OPTS)` | Modify preview window |
| `transform(STR)` | Chain multiple actions conditionally |
| `show-header` / `hide-header` | Toggle header display |
| `show-preview` / `hide-preview` | Toggle preview |

### Command Execution

| Action | Description |
|--------|-------------|
| `execute(CMD)` | Run command, return to fzf (supports {placeholders}, automatically quoted) |
| `execute-silent(CMD)` | Run command silently, return to fzf (automatically quoted placeholders) |
| `become(CMD)` | Replace fzf process with command (handles edge cases better than subshell, automatically quoted) |
| `reload(CMD)` | Refresh list with command output (automatically quoted placeholders) |

**Quoting in Execute Actions**: All placeholder substitutions in execute actions are automatically single-quoted, making them safe from shell injection. You do not need to manually quote placeholders.

```bash
# Placeholder {} automatically quoted to protect spaces and special chars
--bind='ctrl+c:execute-silent(echo {} | pbcopy)'

# If selection is "file name.txt", fzf executes:
# echo 'file name.txt' | pbcopy

# Multiple field placeholders, each automatically quoted
--bind='enter:execute(process {1} {2})'

# If fields are "field1" and "field2", fzf executes:
# process 'field1' 'field2'
```

Examples:
```bash
# Copy to clipboard and continue (selection safely quoted)
--bind='ctrl+c:execute-silent(echo {} | pbcopy)'

# Open file in editor, become replaces fzf (path safely quoted)
--bind='enter:become(vim {})'

# Reload list with filter
--bind='ctrl+r:reload(command)'

# Complex: fields with spaces are protected by automatic quoting
echo -e "path with spaces:123\nother file:456" | \
  fzf --delimiter : --bind='enter:execute(cat {1})'
  # Executes: cat 'path with spaces'
  # Executes: cat 'other file'
```

### Dynamic Behavior

| Action | Description |
|--------|-------------|
| `enable-search` / `disable-search` | Toggle search capability |
| `search(STR)` | Trigger search with query string |
| `print-query` | Output current query and exit |
| `jump-label` | EasyMotion-style navigation |

### Advanced

| Action | Description |
|--------|-------------|
| `unbind(KEY)` | Remove binding for key |
| `rebind(KEY)` | Restore default binding |
| `listen(PROTOCOL:PORT)` | Enable external API control |
| `transform-query(STR)` | Modify query and refresh |

### Events

Trigger actions on lifecycle events:

| Event | When |
|-------|------|
| `start` | fzf starts |
| `load` | Input finished loading |
| `change` | Query changes |
| `focus` | Selection changes |
| `result` | Selection accepted |
| `one` | Exactly one match exists |
| `zero` | No matches |

Example:
```bash
--bind='start:change-query(test)' --bind='zero:abort'
```

## Selection Output

By default, fzf outputs selected items (one per line). Control output with:

| Option | Description |
|--------|-------------|
| `--print-query` | Include original query as first line |
| `--print0` | NUL-separate output (for multi-select with newlines in items) |
| `--accept-nth=FIELDS` | Output specific fields instead of full line |

Multi-select output: one selected item per line by default, or NUL-separated with `--print0`.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Normal exit (selection made) |
| 1 | No match found |
| 2 | Error occurred |
| 126 | Permission denied (become action) |
| 127 | Invalid shell command (become action) |
| 130 | Interrupted (Ctrl-C or Esc) |

## Environment Variables

### Input Configuration

| Variable | Purpose |
|----------|---------|
| `FZF_DEFAULT_COMMAND` | Command to generate default input |
| `FZF_DEFAULT_OPTS` | Default fzf options |
| `FZF_DEFAULT_OPTS_FILE` | File containing default options |

### Runtime Export (available to preview/execute commands)

| Variable | Content |
|----------|---------|
| `FZF_QUERY` | Current search query |
| `FZF_POS` | Current position (1-indexed) |
| `FZF_LINES` | Height of fzf window |
| `FZF_COLUMNS` | Width of fzf window |
| `FZF_TOTAL_COUNT` | Total input items |
| `FZF_MATCH_COUNT` | Items matching current query |
| `FZF_SELECT_COUNT` | Number of selected items |
| `FZF_PREVIEW_LINES` | Height of preview pane |
| `FZF_PREVIEW_COLUMNS` | Width of preview pane |
| `FZF_PORT` | Port number (when using --listen) |

## Extended Search Syntax

Extended search (default) supports multiple patterns and operators:

| Pattern | Behavior |
|---------|----------|
| `word` | Fuzzy match "word" |
| `^prefix` | Match line starting with "prefix" |
| `suffix$` | Match line ending with "suffix" |
| `'exact` | Exact substring match (quotes required) |
| `!exclude` | Negation: exclude matching lines |
| `pattern1 \| pattern2` | OR: match either pattern |
| `wild ^music .mp3$` | Multiple patterns (all must match) |

Disable with `-e/--exact` for exact-match mode only.

## Common Usage Patterns

### File Selection

```bash
# Select file interactively
find . -type f | fzf

# Preview file content
find . -type f | fzf --preview 'head -20 {}'

# Open selected file in editor
vim $(find . -type f | fzf)
```

### Command Output Filtering

```bash
# Select process
ps aux | fzf --header-lines=1

# Select line from log
tail -f logfile | fzf --layout=reverse

# Filter grep results
grep -r "pattern" . | fzf --delimiter : --nth 1,3 --preview 'cat {1}'
```

### Git Integration

```bash
# Select branch
git branch | fzf --preview 'git log --oneline {}'

# Select commit
git log --oneline | fzf --preview 'git show {1}'

# Select file
git diff --name-only | fzf --preview 'git diff -- {}'
```

### Multi-Select Workflows

```bash
# Select multiple files
find . -type f | fzf -m --preview 'file {}'

# Multiple selection with field extraction
csv_data | fzf -m --delimiter , --preview 'echo {2}:{3}'
```

### Dynamic Reloading

```bash
# Live search with updated results
fzf --bind='ctrl-r:reload(command_that_generates_list)'

# Reload on query pattern
--bind='start:change-query(initial)' --bind='load:reload(run_command)'
```

### Preview Window

```bash
# Side-by-side layout
--preview-window=right:40% --preview='cat {}'

# Follow mode (log tailing)
--preview-window=follow --preview='tail -f {}'

# Positioned preview
--preview-window=up:50% --preview='cat {}'
```

## References

- Official repository: https://github.com/junegunn/fzf
- Manual page: `man fzf`
- README: https://github.com/junegunn/fzf/blob/master/README.md
- Advanced: https://github.com/junegunn/fzf/blob/master/ADVANCED.md
