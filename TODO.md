# Tuick Task List

- Rewrite split_blocks to generator for incremental output.
- Make all tests currently expected fail pass.
- Make select command not fail if no url is found, just be no-op.
- Make select command function with all formats tested with split_blocks.
- Write failing test for iterator that yields whenever a filesystem change
  happen. Use a thread to make a change, and timeout of 0.1s. Test monitoring
  for creating file, modifying file, deleting file. Add watchdog
  to requirements, integrate to detect changes under the current directory
- Write failing test for ignoring creation of a file matching a .gitignore. Add
  pathspec dependency and integrate to respect gitignore.
- Write test to ensure that the monitor is not just yielding without blocking,
  use appropriate synchronization to make it work reliably without any sleep.
  Validate test by inserting a bug in the monitor code.
- Write a failing test for line-based communication through a unix socket, with
  commands run by fzf. Parent process listen, subprocesses write, parent must
  receive message, fail if message was not received after subcommand completed.
  Do not use subprocesses, test through typer to keep test fast.
- Write failing test (patching subprocess) for FZF_PORT setup and HTTP
  communication using a local http server, verifying that the appropriate
  reload command is sent when a file is created. Green, create unix socket in
  temporary dir and set FZF_PORT before subprocessing fzf, send reload command
  when filesystem monitor detects a change.
- Add support for other editors. Steal code from
  https://raw.githubusercontent.com/dandavison/open-in-editor/refs/heads/master/open-in-editor
  and ../edit_command_buffer.fish.
- For Idea, Pycharm, code, use "open URL" subprocess, because it's faster.
  - idea://open?file={absolute-path}&line={line-number}
  - pycharm://open?file={absolute-path}&line={line-number}
  - vscode://file/{absolute-path}:{line-number}
- Enable filtering again.
- Improve filtering by adding ASCII control characters in the stream and using
  them as fzf delimiter, so the search only applies to the file name and
  message
  - Test insertion of controls chars in various error formats
