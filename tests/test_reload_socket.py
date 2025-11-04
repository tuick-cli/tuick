"""Tests for cross-platform reload socket IPC."""

from io import StringIO
import socket
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from tuick.reload_socket import ReloadSocketServer

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass
class ServerFixture:
    """Test fixture data for server with API key."""

    server: ReloadSocketServer
    api_key: str
    port: int

    def send(self, message: str) -> str:
        """Send authenticated message to server and return response."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect(("127.0.0.1", self.port))
            sock.sendall(f"secret: {self.api_key}\n{message}\n".encode())
            return sock.recv(1024).decode().strip()


@pytest.fixture
def server_with_key() -> Iterator[ServerFixture]:
    """Create server with API key and return fixture."""
    server = ReloadSocketServer()
    api_key = server.get_server_info().api_key
    server.start()
    fixture = ServerFixture(server, api_key, server.server_address[1])

    yield fixture

    fixture.send("shutdown")


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
) -> None:
    """Server stores fzf_port and responds ok."""
    response = server_with_key.send("fzf_port: 12345")

    assert response == "ok"
    assert server_with_key.server.fzf_port == 12345


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
    console_out: StringIO,
) -> None:
    """Server terminates and waits for cmd_proc on reload."""
    # Setup mock process that is still running
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
