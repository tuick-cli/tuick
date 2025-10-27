# Tuick Task List

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
