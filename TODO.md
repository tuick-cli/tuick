# Tuick Task List

- On abort, print the output of the last load command.

- Add allow_interspersed_args=False to command, so we do not need to use --
  most of the time.

- Use execute-silent for select_command in client editors.

- Find type-safe solution to avoid cast in ReloadRequestHandler.handle().

- Test editors with CLI integration. (Already tested code, surf, cursor, idea,
  pycharm, micro)

- Test editors with URL integration, on Mac/Linux/Windows.

- Fix uses of generic mocks where specs could be used.

- Enable filtering.
  - That (probably) implies removing the "zero:abort" binding.
  - If a reload (manual or automatic) command produces no output, kill fzf
  - For the case of a manual reload, that requires IPC between the reload
    command and the top command, probably through a unix socket.

- Maybe integrate with bat for preview. Possible approaches:
  1. `tuick --preview bat` as a wrapper to bat
  2. Hidden data (--with-nth) or invisible delimiters (so the path and line
     number are in fixed fields)
