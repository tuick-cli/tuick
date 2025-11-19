"""Cross-platform IPC for reload coordination via TCP sockets."""

import queue
import secrets
import socketserver
import string
import tempfile
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    import io

from tuick.console import print_event, print_exception, print_verbose

if TYPE_CHECKING:
    import subprocess


def generate_api_key() -> str:
    """Generate a random 16-character base62 API key.

    16 chars of base62 provides ~95 bits of entropy, sufficient for preventing
    attackers from hijacking IPC connections.
    """
    chars = string.digits + string.ascii_letters
    return "".join(secrets.choice(chars) for _ in range(16))


class ReloadRequestHandler(socketserver.StreamRequestHandler):
    """Handler for reload coordination messages."""

    def handle(self) -> None:  # noqa: C901, PLR0912, PLR0915
        """Process single client connection with authentication."""
        server = cast("ReloadSocketServer", self.server)

        # Read authentication line
        auth_line = self.rfile.readline().decode().strip()
        if not auth_line.startswith("secret: "):
            self.wfile.write(b"error: invalid auth format\n")
            return

        client_key = auth_line.removeprefix("secret: ")
        if client_key != server.api_key:
            self.wfile.write(b"error: invalid api key\n")
            return

        # Read command line
        command_line = self.rfile.readline().decode().strip()

        if command_line.startswith("fzf_port: "):
            # Store fzf port for MonitorThread to use
            port_str = command_line.removeprefix("fzf_port: ")
            try:
                server.fzf_port = int(port_str)
                server.fzf_port_ready.set()
                self.wfile.write(b"ok\n")
            except ValueError:
                self.wfile.write(b"error: invalid port\n")
            else:
                print_verbose("FZF_PORT:", port_str)

        elif command_line == "reload":
            # Terminate cmd_proc if still running
            if server.cmd_proc is not None:
                proc = server.cmd_proc
                if proc.poll() is None:  # Still running
                    print_event("Terminating reload command")
                    proc.terminate()
                    proc.wait()

            # Signal go to proceed with reload
            self.wfile.write(b"go\n")

        elif command_line == "save-output":
            # Receive output via streaming protocol and save to temp file
            # File ownership transferred to server on commit, not closed here
            temp_file = tempfile.TemporaryFile(  # noqa: SIM115
                mode="w+", encoding="utf-8"
            )

            while True:
                # Read length line or 'end' marker
                line = self.rfile.readline().decode().strip()

                if not line:
                    # Connection closed before 'end', discard temp file
                    temp_file.close()
                    return

                if line == "end":
                    server.commit_saved_output_file(temp_file)
                    self.wfile.write(b"ok\n")
                    break

                # Parse length and read that many bytes
                try:
                    length = int(line)
                except ValueError:
                    # Invalid format, discard temp file
                    temp_file.close()
                    self.wfile.write(b"error: invalid length\n")
                    return

                # Read exactly 'length' bytes
                data = self.rfile.read(length)
                if len(data) != length:
                    # Short read - connection closed, discard temp file
                    temp_file.close()
                    return

                temp_file.write(data.decode("utf-8"))

        elif command_line == "shutdown":
            # For test teardown only
            server.should_shutdown = True
            self.wfile.write(b"ok\n")

        else:
            self.wfile.write(b"error: unknown command\n")


class ReloadSocketServer(socketserver.TCPServer):
    """TCP server for reload coordination with authentication."""

    allow_reuse_address = True

    def __init__(self) -> None:
        """Initialize server on dynamic localhost port."""
        super().__init__(("127.0.0.1", 0), ReloadRequestHandler)
        self.api_key = generate_api_key()
        self.cmd_proc: subprocess.Popen[str] | None = None
        self.fzf_port: int | None = None
        self.fzf_port_ready = threading.Event()
        self.should_shutdown = False
        self._thread: threading.Thread | None = None
        self.saved_output_file: io.TextIOWrapper | None = None
        self._output_file_lock = threading.Lock()
        self.termination_queue: queue.Queue[bool] = queue.Queue()

    def serve_until_shutdown(self) -> None:
        """Handle requests in loop until shutdown message received."""
        while not self.should_shutdown:
            self.handle_request()

    def start(self) -> None:
        """Start server in daemon thread."""
        self._thread = threading.Thread(
            target=self.serve_until_shutdown, daemon=True
        )
        self._thread.start()

    def get_server_info(self) -> TuickServerInfo:
        """Get information needed to connect to the tuick server."""
        return TuickServerInfo(
            port=self.server_address[1],
            api_key=self.api_key,
        )

    def commit_saved_output_file(self, file: io.TextIOWrapper) -> None:
        """Atomically commit saved output file, closing previous if exists."""
        file.seek(0)
        with self._output_file_lock:
            if self.saved_output_file is not None:
                self.saved_output_file.close()
            self.saved_output_file = file

    def get_saved_output_file(self) -> io.TextIOWrapper | None:
        """Get saved output file handle at position 0, ready for reading."""
        with self._output_file_lock:
            return self.saved_output_file

    def handle_error(
        self,
        _request: Any,  # noqa: ANN401
        _client_address: tuple[str, int],
    ) -> None:
        """Handle error by printing exception with traceback."""
        print_exception()


@dataclass
class TuickServerInfo:
    """Information needed to connect to the tuick server."""

    port: int
    api_key: str
