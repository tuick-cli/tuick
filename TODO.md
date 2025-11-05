# Tuick Task List

- On abort, print the output of the last load command.
  - Reload command writes raw output to the top process, through the socket,
    require new socket command "save-output".
  - save-output command follow by sequence of one line containing decimal
    length, then that many bytes of binary output, then a line containing
    "end".
  - Server starts a thread to read from the socket and write to a temporary
    file, can be unnamed temporary file. If connection is closed before "end",
    close temp file. If connection reaches end, commit temp file.
  - On fzf process termination, if status is 130, print the content of the
    tempfile.

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
