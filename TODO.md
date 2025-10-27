# Tuick Task List

- Write a failing test for line-based communication through a unix socket, with
  commands run by fzf. Parent process listen, subprocesses write, parent must
  receive message, fail if message was not received after subcommand completed.
  Do not use subprocesses, test through typer to keep test fast.
- Write failing test (patching subprocess) for FZF_PORT setup and HTTP
  communication using a local http server, verifying that the appropriate
  reload command is sent when a file is created. Green, create unix socket in
  temporary dir and set FZF_PORT before subprocessing fzf, send reload command
  when filesystem monitor detects a change.
- Add support for other editors. Steal code from [open-in-editor]
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

[open-in-editor]: https://raw.githubusercontent.com/dandavison/open-in-editor/refs/heads/master/open-in-editor
