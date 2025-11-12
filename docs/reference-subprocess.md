# Python 3.14 subprocess Module Reference

Complete, token-efficient API reference for the subprocess module.

## Overview

The subprocess module enables spawning new processes, managing their I/O, and obtaining return codes. Replaces older modules like `os.system()` and `os.spawn*`.

## Core Functions

### `run(args, **kwargs) -> CompletedProcess`

Execute command and wait for completion.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `args` | str/seq | required | Command and arguments |
| `stdin` | int/file/None | None | Child stdin |
| `stdout` | int/file/None | None | Child stdout |
| `stderr` | int/file/None | None | Child stderr |
| `input` | bytes/str | None | Data to send to stdin (requires stdin=PIPE) |
| `capture_output` | bool | False | Capture stdout+stderr (equiv: stdout=PIPE, stderr=PIPE) |
| `shell` | bool | False | Execute through shell |
| `cwd` | str/Path | None | Working directory |
| `timeout` | float | None | Timeout in seconds (raises TimeoutExpired) |
| `check` | bool | False | Raise CalledProcessError on non-zero exit |
| `encoding` | str | None | Text mode with encoding |
| `errors` | str | None | Error handling mode |
| `text` | bool | False | Alias for encoding='utf-8' |
| `env` | dict | None | Environment variables (replaces parent's entirely) |

**Returns**: `CompletedProcess` with args, returncode, stdout, stderr

**Raises**: `TimeoutExpired`, `CalledProcessError` (if check=True)

**Note**: Simplest interface; use for most tasks.

---

### `call(args, **kwargs) -> int`

Execute command, return exit code.

**Deprecated**: Use `run()` instead.

**Returns**: returncode (int)

---

### `check_call(args, **kwargs) -> int`

Execute command, return exit code or raise on failure.

**Returns**: 0 on success

**Raises**: `CalledProcessError` on non-zero exit

**Deprecated**: Use `run(check=True)` instead.

---

### `check_output(args, **kwargs) -> bytes/str`

Execute command, return captured stdout.

**Parameters**:
| Parameter | Type | Default |
|-----------|------|---------|
| `stderr` | int/file/None | None |
| `shell` | bool | False |
| `cwd` | str/Path | None |
| `encoding` | str | None |
| `errors` | str | None |
| `text` | bool | False |
| `timeout` | float | None |
| `env` | dict | None |

**Returns**: stdout (bytes or str, depending on encoding)

**Raises**: `CalledProcessError` on non-zero exit

**Note**: Automatically sets stdout=PIPE and check=True.

---

### `getstatusoutput(cmd) -> (int, str)`

Execute shell command (via shell=True).

**Returns**: (exit_code, output)

**Platform**: POSIX only

---

### `getoutput(cmd) -> str`

Execute shell command, return output.

**Platform**: POSIX only

---

## Classes

### `CompletedProcess`

Result of `run()`.

**Attributes**:
| Attribute | Type | Description |
|-----------|------|-------------|
| `args` | list/str | Command arguments |
| `returncode` | int | Exit status (0=success, negative=signal on POSIX) |
| `stdout` | bytes/str/None | Captured stdout (None if not captured) |
| `stderr` | bytes/str/None | Captured stderr (None if not captured) |

**Methods**:
- `check_returncode()` → None. Raises `CalledProcessError` if returncode != 0.

---

### `Popen`

Low-level process interface. Use for long-running processes or fine-grained control.

#### Constructor

```python
Popen(args, bufsize=-1, executable=None, stdin=None, stdout=None,
      stderr=None, preexec_fn=None, close_fds=True, shell=False,
      cwd=None, env=None, universal_newlines=None, startupinfo=None,
      creationflags=0, restore_signals=True, start_new_session=False,
      pass_fds=(), *, group=None, extra_groups=None, user=None,
      umask=-1, encoding=None, errors=None, text=None, pipesize=-1,
      process_group=None)
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `args` | str/seq | required | Command and arguments |
| `bufsize` | int | -1 | Buffering: 0=unbuffered, 1=line (text only), -1=default |
| `executable` | str | None | Program to execute (rarely needed) |
| `stdin` | None/PIPE/DEVNULL/int/file | None | Child stdin |
| `stdout` | None/PIPE/DEVNULL/int/file | None | Child stdout |
| `stderr` | None/PIPE/DEVNULL/int/file/STDOUT | None | Child stderr |
| `preexec_fn` | callable | None | Call before child exec (POSIX only) |
| `close_fds` | bool | True | Close unneeded FDs (True on Python 3) |
| `shell` | bool | False | Execute through shell |
| `cwd` | str/Path | None | Working directory |
| `env` | dict | None | Environment variables (replaces parent) |
| `universal_newlines` | bool | None | Alias for text (backwards compat) |
| `startupinfo` | STARTUPINFO | None | Process startup info (Windows only) |
| `creationflags` | int | 0 | Process creation flags (Windows only) |
| `restore_signals` | bool | True | Restore signal handlers (POSIX only) |
| `start_new_session` | bool | False | Start new session (POSIX only) |
| `pass_fds` | tuple | () | FDs to keep open (POSIX only) |
| `group` | int | None | Group ID for child (POSIX only) |
| `extra_groups` | list | None | Supplemental group IDs (POSIX only) |
| `user` | int | None | User ID for child (POSIX only) |
| `umask` | int | -1 | Umask for child (POSIX only) |
| `encoding` | str | None | Text mode encoding |
| `errors` | str | None | Error handling for text mode |
| `text` | bool | False | Open streams in text mode |
| `pipesize` | int | -1 | Pipe buffer size |
| `process_group` | int | None | Process group ID |

#### Attributes

| Attribute | Type | Description |
|-----------|-------|-------------|
| `pid` | int | Child process ID |
| `returncode` | int/None | Exit code (None until termination) |
| `stdin` | file/None | Pipe object (if stdin=PIPE) |
| `stdout` | file/None | Pipe object (if stdout=PIPE) |
| `stderr` | file/None | Pipe object (if stderr=PIPE) |

#### Methods

**`poll() -> int/None`**
- Check if child terminated
- Sets and returns returncode, or None if running

**`wait(timeout=None) -> int`**
- Block until child terminates
- Returns returncode
- Raises `TimeoutExpired` if timeout exceeded
- **Warning**: Deadlock if PIPE used without reading output

**`communicate(input=None, timeout=None) -> (bytes/str, bytes/str)`**
- Send data to stdin, read stdout/stderr until EOF
- Returns (stdout_data, stderr_data)
- Waits for process termination
- **Recommended**: Use instead of direct pipe operations (avoids deadlock)
- Raises `TimeoutExpired` if timeout exceeded
- Kills process if timeout occurs

**`send_signal(signum)`**
- Send signal to child process
- Windows: SIGTERM → terminate()

**`terminate()`**
- Stop child gracefully
- POSIX: SIGTERM
- Windows: TerminateProcess()

**`kill()`**
- Force immediate termination
- POSIX: SIGKILL
- Windows: TerminateProcess() (same as terminate)

---

## Special Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `PIPE` | -1 | Create pipe to/from child |
| `DEVNULL` | int | Discard data (maps to os.devnull) |
| `STDOUT` | -2 | Redirect stderr to stdout |

**Usage**:
```python
run(['cmd'], stdout=PIPE)           # Capture stdout
run(['cmd'], stderr=DEVNULL)        # Discard stderr
run(['cmd'], stderr=STDOUT)         # Merge stderr into stdout
```

---

## Exceptions

All inherit from `SubprocessError`.

### `TimeoutExpired`

Raised when timeout expires during process execution.

**Attributes**:
| Attribute | Type | Description |
|-----------|------|-------------|
| `cmd` | str/list | Command that timed out |
| `timeout` | float | Timeout value (seconds) |
| `output` | bytes/str/None | Data captured before timeout |
| `stdout` | bytes/str/None | Stdout data |
| `stderr` | bytes/str/None | Stderr data |

**Methods**:
- `kill()` → Kill process and wait for termination

---

### `CalledProcessError`

Raised when process exits with non-zero status (check=True or check_call/check_output).

**Attributes**:
| Attribute | Type | Description |
|-----------|------|-------------|
| `returncode` | int | Exit code |
| `cmd` | str/list | Command executed |
| `output` | bytes/str/None | Stdout (if captured) |
| `stdout` | bytes/str/None | Stdout data |
| `stderr` | bytes/str/None | Stderr data |

---

### `SubprocessError`

Base exception class for subprocess module.

---

## Parameter Details

### `stdin`, `stdout`, `stderr`

Accept: `None`, `PIPE`, `DEVNULL`, file descriptor (int), file object

| Value | Behavior |
|-------|----------|
| `None` | Inherit from parent |
| `PIPE` | Create new pipe |
| `DEVNULL` | Discard data |
| `int` | Use existing FD |
| file object | Use file's FD |

---

### `shell`

When `True`:
- Command executed through shell (sh on POSIX, cmd.exe on Windows)
- Enables shell features (pipes, globbing, variable expansion)
- String args: passed to shell directly
- Sequence args: joined with spaces

**Security**: Avoid with untrusted input; use sequences instead of strings

---

### `env`

Environment variables dict. If provided:
- **Replaces entire parent environment** (not merged)
- To preserve parent vars: `{**os.environ, 'NEW_VAR': 'value'}`

---

### `cwd`

Change working directory before execution. Relative paths resolved relative to old cwd.

---

### `encoding`, `errors`, `text`

| Parameter | Effect |
|-----------|--------|
| `text=True` | Opens stdin/stdout/stderr in text mode (UTF-8) |
| `encoding='utf-8'` | Text mode with specified encoding |
| `errors='strict'` | Error handling: strict, replace, ignore, etc. |

---

### `timeout`

Specified in seconds (float). When exceeded:
- `run()`, `call()`: Raises `TimeoutExpired` after killing process
- `wait()`, `communicate()`: Raises `TimeoutExpired`

**Note**: Process is killed after timeout; call `.kill()` on exception if needed

---

### Platform-Specific Parameters

**POSIX only:**
- `preexec_fn`: Called in child before exec (risk of deadlock with threads)
- `restore_signals`: Restore signal handlers from SIG_DFL
- `start_new_session`: Start new session/process group
- `pass_fds`: File descriptors to keep open (tuple of ints)
- `group`: Group ID (mutually exclusive with process_group)
- `extra_groups`: Supplemental group IDs
- `user`: User ID
- `umask`: Process umask (-1 = inherit from parent)
- `process_group`: Process group ID

**Windows only:**
- `startupinfo`: STARTUPINFO object for process creation
- `creationflags`: Process creation flags (e.g., CREATE_NEW_CONSOLE)

---

## Common Patterns

### Capture output
```python
result = run(['cmd'], capture_output=True, text=True)
stdout, stderr = result.stdout, result.stderr
```

### Check for errors
```python
result = run(['cmd'], check=True)  # Raises CalledProcessError on failure
```

### Set timeout
```python
try:
    result = run(['cmd'], timeout=5)
except TimeoutExpired:
    # Handle timeout
    pass
```

### Pipe input
```python
result = run(['cat'], input='data', text=True, capture_output=True)
```

### Merge stderr to stdout
```python
result = run(['cmd'], stdout=PIPE, stderr=STDOUT, text=True)
```

### Discard output
```python
run(['cmd'], stdout=DEVNULL, stderr=DEVNULL)
```

### Long-running process with streaming
```python
with Popen(['cmd'], stdout=PIPE, text=True) as proc:
    for line in proc.stdout:
        process(line)
    proc.wait()
```

### Avoid deadlock with pipes
```python
proc = Popen(['cmd'], stdin=PIPE, stdout=PIPE, stderr=PIPE, text=True)
stdout, stderr = proc.communicate(input='data', timeout=5)
```

---

## Security Considerations

1. **Avoid `shell=True` with untrusted input**: Enables shell injection
2. **Use sequences for args**: `['ls', '-la']` not `'ls -la'`
3. **Quote shell arguments**: Use `shlex.quote()` if shell=True necessary
4. **Validate/escape user input**: Before passing to subprocess
5. **Never pass raw user input as shell=True**

---

## Deadlock Prevention

**Never do this**:
```python
proc = Popen(['cmd'], stdout=PIPE, stderr=PIPE)
output = proc.stdout.read()  # Deadlock if stderr fills pipe buffer
```

**Do this instead**:
```python
output, errors = proc.communicate()
```

Or use `run()` which handles it automatically.

---

## Process Termination Behavior

| Method | Signal | Effect | Windows |
|--------|--------|--------|---------|
| `terminate()` | SIGTERM | Graceful | TerminateProcess |
| `kill()` | SIGKILL | Forceful | TerminateProcess |
| `wait()` + timeout | none | Timeout after kill | same |

---

## Return Code Meanings

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1-255 | Error (application-defined) |
| -N (POSIX) | Killed by signal N |

**Windows**: Use negative signal number mapping (e.g., -9 for SIGKILL equivalent)

---

## File Descriptor Management

- `close_fds=True` (default in Python 3): Closes FDs >= 3 in child
- `pass_fds=(fd1, fd2,...)`: Keep specified FDs open (POSIX only)
- File object use: Automatically duplicated to child

---

## Text vs Binary Mode

| Setting | stdout/stderr | Behavior |
|---------|---------------|----------|
| `text=False` (default) | bytes | Raw binary data |
| `text=True` | str | Decoded using system default or specified encoding |
| `encoding='utf-8'` | str | Decoded with UTF-8 |
| `universal_newlines=True` | str | Alias for text (deprecated) |

---

## Buffering Modes

| bufsize | Behavior |
|---------|----------|
| -1 (default) | Fully buffered |
| 0 | Unbuffered (read/write are system calls) |
| 1 | Line buffered (text mode only) |
| > 1 | Buffer of specified size |

---

## Signal Handling (POSIX)

- `restore_signals=True` (default): Reset signal handlers from SIG_DFL
- Set to `False` to inherit parent's signal handlers
- `preexec_fn`: Called after fork, before exec; can set custom handlers

---

## Context Manager Support

Popen supports context manager protocol (Python 3.2+):

```python
with Popen(['cmd'], stdout=PIPE) as proc:
    output = proc.communicate()
```

Automatically closes pipes and calls `wait()` on exit.

---

## Subprocess Creation Overhead

- Process creation itself **cannot be interrupted** on many platforms
- Timeout applies after creation, not during creation
- Use `timeout` for expected long operations, not for creation latency

---

## Platform Differences

**Behavior varies:**
- Signal handling (Windows has limited signals)
- Process groups and sessions (POSIX vs Windows)
- Shell defaults (sh vs cmd.exe)
- Return code semantics

Always test on target platform.

---

## Version Notes

- Python 3.14: Latest; includes all features listed
- `capture_output` added in 3.7
- `text` parameter added in 3.7 (alias for universal_newlines)
- `timeout` added in 3.3
- `encoding`/`errors` added in 3.6
- Context manager support added in 3.2
