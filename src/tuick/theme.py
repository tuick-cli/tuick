"""Theme detection and configuration for tuick."""

import fcntl
import os
import select
import termios
import tty
from enum import StrEnum, auto

# Known COLORFGBG values from https://github.com/rocky/shell-term-background/
LIGHT_COLORFGBG_VALUES = ("0;15", "0;default;15")
DARK_COLORFGBG_VALUES = ("15;0", "15;default;0")


class ColorTheme(StrEnum):
    """Color theme for fzf and bat."""

    DARK = auto()
    LIGHT = auto()
    BW = auto()


class ColorThemeAuto(StrEnum):
    """Auto theme option."""

    AUTO = auto()


type ColorThemeOption = ColorTheme | ColorThemeAuto
type DetectedTheme = ColorTheme | None


def detect_theme(cli_option: ColorThemeOption) -> ColorTheme:
    """Detect color theme based on priority order.

    Priority:
    1. CLI option if not "auto"
    2. CLI_THEME environment variable
    3. NO_COLOR environment variable (if defined and not empty)
    4. Autodetect via OSC 11, then COLORFGBG, default to DARK
    """
    if cli_option != ColorThemeAuto.AUTO:
        return ColorTheme(cli_option.value)

    if cli_theme := os.getenv("CLI_THEME"):
        try:
            return ColorTheme(cli_theme.lower())
        except ValueError:
            pass

    no_color = os.getenv("NO_COLOR")
    if no_color is not None and no_color != "":
        return ColorTheme.BW

    # Type error: returning wrong type
    return _detect_via_osc11()


def _autodetect_theme() -> ColorTheme:
    """Autodetect theme using OSC 11, then COLORFGBG, default to DARK."""
    if theme := _detect_via_osc11():
        return theme

    if theme := _detect_via_colorfgbg():
        return theme

    return ColorTheme.DARK


def _detect_via_osc11() -> DetectedTheme:
    """Query terminal background color using OSC 11 escape sequence."""
    try:
        tty_fd = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
    except (FileNotFoundError, PermissionError, OSError):
        return None

    try:
        os.write(tty_fd, b"\033]11;?\007")

        old_settings = termios.tcgetattr(tty_fd)
        old_flags = fcntl.fcntl(tty_fd, fcntl.F_GETFL)
        try:
            tty.setraw(tty_fd)
            fcntl.fcntl(tty_fd, fcntl.F_SETFL, old_flags | os.O_NONBLOCK)

            # Wait for response with 100ms timeout. OSC 11 responses are short
            # (~30-40 bytes) and terminals send them atomically, so a single
            # select() is sufficient. If terminal doesn't support OSC 11, this
            # times out cleanly without entering the read path.
            ready, _, _ = select.select([tty_fd], [], [], 0.1)
            if not ready:
                return None

            response = os.read(tty_fd, 100).decode()
        finally:
            fcntl.fcntl(tty_fd, fcntl.F_SETFL, old_flags)
            termios.tcsetattr(tty_fd, termios.TCSADRAIN, old_settings)
    finally:
        os.close(tty_fd)

    if "rgb:" not in response:
        return None

    try:
        rgb_part = response.split("rgb:")[1].split("\007")[0].split("\033")[0]
        r, g, b = rgb_part.split("/")
        r_val = int(r[:2], 16)
        g_val = int(g[:2], 16)
        b_val = int(b[:2], 16)
    except (IndexError, ValueError):
        return None

    brightness = 0.2126 * r_val + 0.7152 * g_val + 0.0722 * b_val

    return ColorTheme.LIGHT if brightness > 128 else ColorTheme.DARK


def _detect_via_colorfgbg() -> DetectedTheme:
    """Detect theme via COLORFGBG environment variable."""
    colorfgbg = os.getenv("COLORFGBG")
    if not colorfgbg:
        return None

    if colorfgbg in LIGHT_COLORFGBG_VALUES:
        return ColorTheme.LIGHT
    if colorfgbg in DARK_COLORFGBG_VALUES:
        return ColorTheme.DARK

    return None
