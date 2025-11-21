"""Tests for cross-platform reload socket IPC."""

import socket
import subprocess
from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import Mock

from tuick.console import set_verbose

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .conftest import ConsoleFixture, ServerFixture


def test_server_rejects_invalid_auth_format(
    server_with_key: ServerFixture,
) -> None:
    """Server rejects connection without proper auth format."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(("127.0.0.1", server_with_key.port))
        sock.sendall(b"invalid\nreload\n")
        response = sock.recv(1024).decode().strip()

    assert response == "error: invalid auth format"


def test_server_rejects_invalid_api_key(
    server_with_key: ServerFixture,
) -> None:
    """Server rejects connection with wrong API key."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(("127.0.0.1", server_with_key.port))
        sock.sendall(b"secret: wrongkey123\nreload\n")
        response = sock.recv(1024).decode().strip()

    assert response == "error: invalid api key"


def test_server_accepts_valid_fzf_port_message(
    server_with_key: ServerFixture,
    console_out: ConsoleFixture,
) -> None:
    """Server stores fzf_port and responds ok."""
    set_verbose()
    response = server_with_key.send("fzf_port: 12345")

    assert response == "ok"
    assert server_with_key.server.fzf_port == 12345
    assert console_out.getvalue() == "FZF_PORT: 12345\n"


def test_server_rejects_invalid_fzf_port(
    server_with_key: ServerFixture,
) -> None:
    """Server rejects non-numeric fzf_port."""
    response = server_with_key.send("fzf_port: notanumber")

    assert response == "error: invalid port"
    assert server_with_key.server.fzf_port is None


def test_server_responds_go_to_reload_message(
    server_with_key: ServerFixture,
) -> None:
    """Server responds go to reload message."""
    response = server_with_key.send("reload")

    assert response == "go"


def test_server_terminates_running_cmd_proc(
    server_with_key: ServerFixture,
    console_out: ConsoleFixture,
) -> None:
    """Server terminates and waits for cmd_proc on reload."""
    # Setup mock process that is still running
    set_verbose()
    mock_proc = Mock(spec=subprocess.Popen)
    mock_proc.poll.return_value = None  # Still running
    server_with_key.server.cmd_proc = mock_proc

    response = server_with_key.send("reload")

    assert response == "go"
    mock_proc.terminate.assert_called_once()
    mock_proc.wait.assert_called_once()

    assert console_out.getvalue() == "> Terminating reload command\n"


def test_server_handles_already_exited_cmd_proc(
    server_with_key: ServerFixture,
) -> None:
    """Server handles cmd_proc that already exited."""
    # Setup mock process that already exited
    mock_proc = Mock(spec=subprocess.Popen)
    mock_proc.poll.return_value = 0  # Already exited
    server_with_key.server.cmd_proc = mock_proc

    response = server_with_key.send("reload")

    assert response == "go"
    mock_proc.terminate.assert_not_called()
    mock_proc.wait.assert_not_called()


def test_server_rejects_unknown_command(
    server_with_key: ServerFixture,
) -> None:
    """Server rejects unknown commands."""
    response = server_with_key.send("unknown_cmd")

    assert response == "error: unknown command"


@contextmanager
def _connect_to_tuick_server(server: ServerFixture) -> Iterator[socket.socket]:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(("127.0.0.1", server.port))
        sock.sendall(f"secret: {server.api_key}\n".encode())
        yield sock


def test_server_save_output_protocol(
    server_with_key: ServerFixture,
) -> None:
    """Server receives save-output and stores in temp file.

    Uses streaming protocol with length+data pairs.
    """
    with _connect_to_tuick_server(server_with_key) as sock:
        sock.sendall(b"begin-output\n")
        assert sock.recv(1024) == b"ok\n"

    # Send save-output command with streaming protocol
    with _connect_to_tuick_server(server_with_key) as sock:
        sock.sendall(b"save-output\n")

        # Send first chunk: length + data
        data1 = b"line1: error\n"
        sock.sendall(f"{len(data1)}\n".encode())
        sock.sendall(data1)

        # Send second chunk: length + data
        data2 = b"line2: warning\n"
        sock.sendall(f"{len(data2)}\n".encode())
        sock.sendall(data2)

        # Send end marker
        sock.sendall(b"end\n")
        assert sock.recv(1024) == b"ok\n"

    with _connect_to_tuick_server(server_with_key) as sock:
        sock.sendall(b"end-output\n")
        assert sock.recv(1024) == b"ok\n"

    # Verify saved output can be retrieved
    output_file = server_with_key.server.get_saved_output_file()
    assert output_file is not None
    content = output_file.read()
    assert content == "line1: error\nline2: warning\n"


def test_server_save_output_empty(
    server_with_key: ServerFixture,
) -> None:
    """Server handles empty output.

    save-output followed immediately by end.
    """
    with _connect_to_tuick_server(server_with_key) as sock:
        sock.sendall(b"begin-output\n")
        assert sock.recv(1024) == b"ok\n"

    with _connect_to_tuick_server(server_with_key) as sock:
        sock.sendall(b"save-output\n")
        # Send end marker immediately (no data chunks)
        sock.sendall(b"end\n")
        assert sock.recv(1024) == b"ok\n"

    with _connect_to_tuick_server(server_with_key) as sock:
        sock.sendall(b"end-output\n")
        assert sock.recv(1024) == b"ok\n"

    # Verify empty output is saved
    output_file = server_with_key.server.get_saved_output_file()
    assert output_file is not None
    content = output_file.read()
    assert content == ""


def test_server_save_output_connection_closed_before_end(
    server_with_key: ServerFixture,
) -> None:
    """Server discards output if connection closes before 'end' marker."""
    # Send save-output but close connection before sending 'end'
    with _connect_to_tuick_server(server_with_key) as sock:
        sock.sendall(b"begin-output\n")
        assert sock.recv(1024) == b"ok\n"

    with _connect_to_tuick_server(server_with_key) as sock:
        sock.sendall(b"save-output\n")

        # Send some data
        data1 = b"incomplete data\n"
        sock.sendall(f"{len(data1)}\n".encode())
        sock.sendall(data1)
        # Connection closes without 'end'

    # Verify no output is saved (temp file discarded)
    output_file = server_with_key.server.get_saved_output_file()
    assert output_file is None
