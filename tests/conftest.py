"""Common test fixtures."""

from io import StringIO
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from rich.console import Console

if TYPE_CHECKING:
    from collections.abc import Iterable


@pytest.fixture
def console_out() -> Iterable[StringIO]:
    """Patch console with test console using StringIO (no colors)."""
    output = StringIO()
    test_console = Console(file=output, force_terminal=False)
    with patch("tuick.console._console", test_console):
        yield output
