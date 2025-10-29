# Tuick Task List

- Stop using FZF_DEFAULT_COMMAND and only start fzf if there is output to
  display. Feed null-separated data to fzf stdin.

- Open a unix socket in the top process, set env TUICK_SOCKET, so reload
  process (--reload) can connect. Simple line based protocol. Currently only
  message is "reload", to notify that a reload was initiated either by the user
  or through the fzf socket. Wait for "go" response indicates that, if the
  input process was still live, it has been killed and waited.

  - First test and implement server side
  - Then implement client side. Test as integration test by mocking subprocess,
    going through Typer test wrapper, and checking the sequence:
    proc.terminate, proc.wait, reply sent.

- Test editors with CLI integration.

- Test editors with URL integration, on Mac/Linux/Windows.

- Enable filtering.
  - That (probably) implies removing the "zero:abort" binding.
  - If a reload (manual or automatic) command produces no output, kill fzf
  - For the case of a manual reload, that requires IPC between the reload
    command and the top command, probably through a unix socket.

- Maybe integrate with bat for preview. Possible approaches:
  1. `tuick --preview bat` as a wrapper to bat
  2. Hidden data (--with-nth) or invisible delimiters (so the path and line
     number are in fixed fields)
