"""Tuick module that handles the fzf command."""

import os
import shutil
import subprocess
from contextlib import contextmanager
from typing import TYPE_CHECKING

from tuick.console import is_verbose, print_command, print_error, print_success
from tuick.shell import quote_command
from tuick.theme import ColorTheme

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tuick.cli import CallbackCommands
    from tuick.reload_socket import TuickServerInfo


class FzfUserInterface:
    """Define user interface elements for fzf."""

    def __init__(self, command: list[str]) -> None:
        """Initialize fzf interface."""
        self.header = quote_command(command)
        self.running_header = f"{self.header} Running..."


def _check_bat_installed() -> bool:
    """Check if bat is installed."""
    return shutil.which("bat") is not None


def _get_preview_command(theme: ColorTheme) -> str:
    """Generate preview command for fzf."""
    if not _check_bat_installed():
        return "echo 'Preview requires bat (https://github.com/sharkdp/bat)'"

    cmd = ["bat"]

    if os.getenv("BAT_THEME"):
        cmd.append("-f")
    elif theme == ColorTheme.BW:
        pass
    else:
        cmd.extend(["-f", f"--theme={theme.value}"])

    cmd.extend(["--style=numbers,grid", "--highlight-line={2}", "{1}"])

    return " ".join(cmd)


def _get_preview_window_config() -> str:
    """Generate preview window configuration."""
    base_config = (
        "right,50%,border-line,info,"
        "<88(top),"  # Responsive, one column on narrow terminals
        "+{2}/2"  # Center preview on the error line
    )
    if os.getenv("TUICK_PREVIEW") != "0":
        return base_config
    return f"{base_config},hidden"


@contextmanager
def open_fzf_process(
    callbacks: CallbackCommands,
    user_interface: FzfUserInterface,
    tuick_server_info: TuickServerInfo,
    fzf_api_key: str,
    theme: ColorTheme,
) -> Iterator[subprocess.Popen[str]]:
    """Open and manage fzf process."""
    env = os.environ.copy()
    if theme != ColorTheme.BW:
        env["FORCE_COLOR"] = "1"
    env["TUICK_PORT"] = str(tuick_server_info.port)
    env["TUICK_API_KEY"] = tuick_server_info.api_key
    env["FZF_API_KEY"] = fzf_api_key

    # Have output, start fzf
    def binding_verbose(
        event: str, message: str, *, plus: bool = False
    ) -> list[str]:
        if not is_verbose():
            return []
        action = f"execute-silent({callbacks.message_prefix} {message})"
        return [f"{event}:{'+' if plus else ''}{action}"]

    select_action = f"{callbacks.select_prefix} {{1}} {{2}} {{3}} {{4}} {{5}}"
    fzf_bindings = [
        f"start:change-header({user_interface.running_header})",
        f"start:+execute-silent({callbacks.start_command})",
        f"load:change-header({user_interface.header})",
        *binding_verbose("load", "LOAD", plus=True),
        f"enter:execute({select_action})",
        f"r:change-header({user_interface.running_header})",
        *binding_verbose("r", "RELOAD", plus=True),
        f"r:+reload({callbacks.reload_command})",
        "q:abort",
        *binding_verbose("zero", "ZERO"),
        "zero:+accept",
        "space:down",
        "backspace:up",
        "/,ctrl-/:toggle-preview",
        "home:first",
        "end:last",
    ]
    color_opt = (
        ["--no-color"]
        if theme == ColorTheme.BW
        else [f"--color={theme.value}"]
    )
    fzf_cmd = [
        *("fzf", "--listen", "--read0", "--track"),
        *("--no-sort", "--reverse", "--header-border"),
        *("--ansi", *color_opt, "--highlight-line", "--wrap"),
        *("--delimiter=\x1f", "--with-nth=6"),
        *("--preview", _get_preview_command(theme)),
        *("--preview-window", _get_preview_window_config()),
        *("--disabled", "--no-input", "--bind"),
        ",".join(fzf_bindings),
    ]
    print_command(fzf_cmd)
    with subprocess.Popen(
        fzf_cmd, stdin=subprocess.PIPE, text=True, env=env
    ) as fzf_proc:
        yield fzf_proc
    _print_fzf_exit(fzf_proc.returncode)


def _print_fzf_exit(returncode: int) -> None:
    if returncode == 0:
        print_success("[bold]fzf:[/] normal exit (0)")
    elif returncode == 1:
        print_success("[bold]fzf:[/] no match (1)")
    elif returncode == 2:
        print_error("fzf:", "error (2)")
    elif returncode == 126:
        print_error("fzf:", "become command denied (126)")
    elif returncode == 127:
        print_error("fzf:", "become command not found (127)")
    elif returncode == 130:
        print_success("[bold]fzf:[/] aborted by user (130)")
    else:
        print_error("fzf:", "exited with status", returncode)
