"""Common test fixtures."""

import socket
from dataclasses import dataclass, field
from io import StringIO
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from rich.console import Console

import tuick.console
from tuick.reload_socket import ReloadSocketServer

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass
class ConsoleFixture:
    """Console output fixture that tracks whether output was checked.

    Usage patterns:
    1. Verify specific output: assert console_out.getvalue() == "expected"
    2. No output expected: don't call getvalue(), fixture verifies empty
    3. Ignore output: call console_out.ignore_output()

    NEVER call getvalue() without asserting its value - this defeats the
    safety check for unexpected output.
    """

    _output: StringIO
    _checked: bool = field(default=False, init=False)

    def getvalue(self) -> str:
        """Get console output, marking it as checked."""
        self._checked = True
        return self._output.getvalue()

    def ignore_output(self) -> None:
        """Mark output as intentionally ignored."""
        self._checked = True

    def assert_no_unexpected_output(self) -> None:
        """Assert no unexpected output if not already checked."""
        if not self._checked:
            output = self._output.getvalue()
            assert output == "", "Unexpected console output"


@pytest.fixture
def console_out() -> Iterator[ConsoleFixture]:
    """Patch console with test console using StringIO (no colors)."""
    tuick.console._verbose = False
    output = StringIO()
    test_console = Console(file=output, force_terminal=False)
    fixture = ConsoleFixture(output)

    with patch("tuick.console._console", test_console):
        yield fixture

    fixture.assert_no_unexpected_output()


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
def server_with_key(console_out: ConsoleFixture) -> Iterator[ServerFixture]:
    """Create server with API key and return fixture."""
    _ = console_out  # Ensure console is patched
    server = ReloadSocketServer()
    api_key = server.get_server_info().api_key
    server.start()
    fixture = ServerFixture(server, api_key, server.server_address[1])

    yield fixture

    fixture.send("shutdown")
