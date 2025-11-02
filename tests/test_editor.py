"""Tests for the editor module."""

import os
import subprocess
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from tuick.editor import (
    EditorSubprocess,
    EditorURL,
    get_editor_command,
    get_editor_from_env,
)
from tuick.parser import FileLocation


def _mock_resolve(self: Path, *, strict: bool = False) -> Path:
    """Mock Path.resolve to add prefix for relative paths."""
    assert strict is True, "Path.resolve must be called with strict=True"
    if self.is_absolute():
        return self
    return Path("/project") / self


def test_get_editor_from_env_editor() -> None:
    """Get editor command from EDITOR, preserving arguments."""
    with patch.dict(os.environ, {"EDITOR": "vim -p"}, clear=True):
        assert get_editor_from_env() == "vim -p"


def test_get_editor_from_env_visual() -> None:
    """Fall back to VISUAL when EDITOR not set."""
    with patch.dict(os.environ, {"VISUAL": "nvim"}, clear=True):
        assert get_editor_from_env() == "nvim"


def test_get_editor_from_env_editor_precedence() -> None:
    """EDITOR takes precedence over VISUAL."""
    with patch.dict(
        os.environ, {"EDITOR": "vim", "VISUAL": "nvim"}, clear=True
    ):
        assert get_editor_from_env() == "vim"


def test_get_editor_from_env_none() -> None:
    """Return None when neither EDITOR nor VISUAL set."""
    with patch.dict(os.environ, {}, clear=True):
        assert get_editor_from_env() is None


@pytest.mark.parametrize(
    ("editor", "location", "expected"),
    [
        # IntelliJ IDEA - URL scheme when no --wait
        (
            "idea",
            FileLocation(path="src/test.py", row=10, column=5),
            [
                "open",
                "idea://open?file=%2Fproject%2Fsrc%2Ftest.py&line=10&column=5",
            ],
        ),
        (
            "idea",
            FileLocation(path="src/test.py", row=10),
            ["open", "idea://open?file=%2Fproject%2Fsrc%2Ftest.py&line=10"],
        ),
        (
            "/Applications/IntelliJ IDEA.app/Contents/MacOS/idea",
            FileLocation(path="src/test.py", row=10, column=5),
            [
                "open",
                "idea://open?file=%2Fproject%2Fsrc%2Ftest.py&line=10&column=5",
            ],
        ),
        # IntelliJ IDEA - CLI when --wait
        (
            "idea --wait",
            FileLocation(path="src/test.py", row=10, column=5),
            ["idea", "--wait", "--line", "10", "--column", "5", "src/test.py"],
        ),
        (
            "idea --wait",
            FileLocation(path="src/test.py", row=10),
            ["idea", "--wait", "--line", "10", "src/test.py"],
        ),
        # PyCharm - URL scheme
        (
            "charm",
            FileLocation(path="src/test.py", row=10, column=5),
            [
                "open",
                "pycharm://open?file=%2Fproject%2Fsrc%2Ftest.py&line=10&column=5",
            ],
        ),
        (
            "pycharm",
            FileLocation(path="src/test.py", row=10),
            ["open", "pycharm://open?file=%2Fproject%2Fsrc%2Ftest.py&line=10"],
        ),
        # VSCode - URL scheme when no --wait
        (
            "code",
            FileLocation(path="src/test.py", row=10, column=5),
            ["open", "vscode://file//project/src/test.py:10:5"],
        ),
        (
            "code",
            FileLocation(path="src/test.py", row=10),
            ["open", "vscode://file//project/src/test.py:10"],
        ),
        # VSCode - traditional command when --wait present
        (
            "code --wait",
            FileLocation(path="src/test.py", row=10, column=5),
            ["code", "--wait", "--goto", "src/test.py:10:5"],
        ),
        (
            "code --wait",
            FileLocation(path="src/test.py", row=10),
            ["code", "--wait", "--goto", "src/test.py:10"],
        ),
        # VSCode OSS - URL scheme when no --wait
        (
            "code-oss",
            FileLocation(path="src/test.py", row=10, column=5),
            ["open", "code-oss://file//project/src/test.py:10:5"],
        ),
        # VSCode OSS - traditional command when --wait present
        (
            "code-oss --wait",
            FileLocation(path="src/test.py", row=10, column=5),
            ["code-oss", "--wait", "--goto", "src/test.py:10:5"],
        ),
        # Windsurf - Like VSCode
        (
            "surf",
            FileLocation(path="src/test.py", row=10, column=5),
            ["open", "windsurf://file//project/src/test.py:10:5"],
        ),
        (
            "surf --wait",
            FileLocation(path="src/test.py", row=10, column=5),
            ["surf", "--wait", "--goto", "src/test.py:10:5"],
        ),
        # Cursor - Like VSCode
        (
            "cursor",
            FileLocation(path="src/test.py", row=10, column=5),
            ["open", "cursor://file//project/src/test.py:10:5"],
        ),
        (
            "cursor --wait",
            FileLocation(path="src/test.py", row=10, column=5),
            ["cursor", "--wait", "--goto", "src/test.py:10:5"],
        ),
        # Vim variants
        (
            "vim",
            FileLocation(path="src/test.py", row=10),
            ["vim", "+10", "src/test.py"],
        ),
        (
            "vim",
            FileLocation(path="src/test.py", row=10, column=5),
            ["vim", "+10", "+normal! 5l", "src/test.py"],
        ),
        (
            "vim -p",
            FileLocation(path="src/test.py", row=10, column=5),
            ["vim", "-p", "+10", "+normal! 5l", "src/test.py"],
        ),
        (
            "/usr/local/bin/vim",
            FileLocation(path="src/test.py", row=10, column=5),
            ["/usr/local/bin/vim", "+10", "+normal! 5l", "src/test.py"],
        ),
        (
            "nvim",
            FileLocation(path="src/test.py", row=10, column=5),
            ["nvim", "+10", "+normal! 5l", "src/test.py"],
        ),
        (
            "nvim --noplugin",
            FileLocation(path="src/test.py", row=10),
            ["nvim", "--noplugin", "+10", "src/test.py"],
        ),
        (
            "vi",
            FileLocation(path="src/test.py", row=10),
            ["vi", "+10", "src/test.py"],
        ),
        (
            "vi",
            FileLocation(path="src/test.py", row=10, column=5),
            ["vi", "+10", "+normal! 5l", "src/test.py"],
        ),
        # Emacs variants - +line:col file
        (
            "emacs",
            FileLocation(path="src/test.py", row=10, column=5),
            ["emacs", "+10:5", "src/test.py"],
        ),
        (
            "emacs",
            FileLocation(path="src/test.py", row=10),
            ["emacs", "+10", "src/test.py"],
        ),
        (
            "emacsclient",
            FileLocation(path="src/test.py", row=10, column=5),
            ["emacsclient", "+10:5", "src/test.py"],
        ),
        (
            "gedit",
            FileLocation(path="src/test.py", row=10, column=5),
            ["gedit", "+10:5", "src/test.py"],
        ),
        # Kakoune - file:line:col with -e hook
        (
            "kak",
            FileLocation(path="src/test.py", row=10, column=5),
            ["kak", "+10:5", "src/test.py"],
        ),
        (
            "kak",
            FileLocation(path="src/test.py", row=10),
            ["kak", "+10", "src/test.py"],
        ),
        # Nano - +line,col file
        (
            "nano",
            FileLocation(path="src/test.py", row=10, column=5),
            ["nano", "+10,5", "src/test.py"],
        ),
        (
            "nano",
            FileLocation(path="src/test.py", row=10),
            ["nano", "+10", "src/test.py"],
        ),
        # Joe and ee - +line file
        (
            "joe",
            FileLocation(path="src/test.py", row=10, column=5),
            ["joe", "+10", "src/test.py"],
        ),
        (
            "joe",
            FileLocation(path="src/test.py", row=10),
            ["joe", "+10", "src/test.py"],
        ),
        (
            "ee",
            FileLocation(path="src/test.py", row=10, column=5),
            ["ee", "+10", "src/test.py"],
        ),
        # Sublime Text - file:line:col
        (
            "subl",
            FileLocation(path="src/test.py", row=10, column=5),
            ["subl", "src/test.py:10:5"],
        ),
        (
            "subl",
            FileLocation(path="src/test.py", row=10),
            ["subl", "src/test.py:10"],
        ),
        # Micro - file +line:col
        (
            "micro",
            FileLocation(path="src/test.py", row=10, column=5),
            ["micro", "src/test.py", "+10:5"],
        ),
        (
            "micro",
            FileLocation(path="src/test.py", row=10),
            ["micro", "src/test.py", "+10"],
        ),
        # Helix - file:line:col
        (
            "helix",
            FileLocation(path="src/test.py", row=10, column=5),
            ["helix", "src/test.py:10:5"],
        ),
        (
            "helix",
            FileLocation(path="src/test.py", row=10),
            ["helix", "src/test.py:10"],
        ),
        (
            "hx",
            FileLocation(path="src/test.py", row=10, column=5),
            ["hx", "src/test.py:10:5"],
        ),
        # Zed - file:line:col
        (
            "zed",
            FileLocation(path="src/test.py", row=10, column=5),
            ["zed", "src/test.py:10:5"],
        ),
        (
            "zed",
            FileLocation(path="src/test.py", row=10),
            ["zed", "src/test.py:10"],
        ),
        # O editor - path +line +column
        (
            "o",
            FileLocation(path="src/test.py", row=10, column=5),
            ["o", "src/test.py", "+10", "+5"],
        ),
        (
            "o",
            FileLocation(path="src/test.py", row=10),
            ["o", "src/test.py", "+10"],
        ),
    ],
)
def test_get_editor_command(
    editor: str, location: FileLocation, expected: list[str]
) -> None:
    """Build editor command from editor string and location."""
    with patch.object(
        Path, "resolve", autospec=True, side_effect=_mock_resolve
    ):
        cmd = get_editor_command(editor, location)
        if isinstance(cmd, EditorURL):
            assert ["open", cmd.url] == expected
        elif isinstance(cmd, EditorSubprocess):
            assert list(cmd.args) == expected


class TestEditorURL:
    """Tests for EditorURL class."""

    def test_displays_open_command(self) -> None:
        """Rich console displays 'open {url}'."""
        url = "vscode://file//project/src/test.py:10:5"
        cmd = EditorURL(url)
        output = StringIO()
        console = Console(file=output, force_terminal=False)
        console.print(cmd)
        assert output.getvalue() == f"open {url}\n"

    @pytest.mark.parametrize(
        ("system", "expected_command"),
        [
            ("Darwin", ["open", "test://url"]),
            ("Linux", ["xdg-open", "test://url"]),
        ],
    )
    def test_run_uses_popen_for_darwin_and_linux(
        self, system: str, expected_command: list[str]
    ) -> None:
        """Run() uses Popen with platform-specific command."""
        url = "test://url"
        cmd = EditorURL(url)
        with (
            patch("subprocess.Popen") as mock_popen,
            patch("platform.system", return_value=system),
        ):
            cmd.run()
            mock_popen.assert_called_once_with(expected_command)

    def test_run_uses_startfile_on_windows(self) -> None:
        """Run() uses os.startfile on Windows."""
        url = "test://url"
        cmd = EditorURL(url)
        mock_startfile = MagicMock()
        with (
            patch.object(os, "startfile", mock_startfile, create=True),
            patch("platform.system", return_value="Windows"),
        ):
            cmd.run()
            mock_startfile.assert_called_once_with(url)


class TestEditorSubprocess:
    """Tests for EditorSubprocess class."""

    def test_displays_formatted_command(self) -> None:
        """Rich console displays shell-quoted command args."""
        args = ["vim", "+10", "src/test.py"]
        cmd = EditorSubprocess(args)
        output = StringIO()
        console = Console(file=output, force_terminal=False)
        console.print(cmd)
        assert output.getvalue() == "vim +10 src/test.py\n"

    def test_shell_quotes_spaces(self) -> None:
        """Rich console correctly shell quotes args with spaces."""
        args = ["/usr/bin/my editor", "--arg", "file with spaces.py"]
        cmd = EditorSubprocess(args)
        output = StringIO()
        console = Console(file=output, force_terminal=False)
        console.print(cmd)
        expected = "'/usr/bin/my editor' --arg 'file with spaces.py'\n"
        assert output.getvalue() == expected

    def test_run_calls_subprocess_without_capture(self) -> None:
        """Run() calls subprocess.run without capture_output."""
        args = ["vim", "+10", "src/test.py"]
        cmd = EditorSubprocess(args)
        with patch("subprocess.run") as mock_run:
            cmd.run()
            mock_run.assert_called_once_with(args, check=True)

    def test_run_raises_on_subprocess_error(self) -> None:
        """Run() raises CalledProcessError when subprocess fails."""
        args = ["vim", "+10", "src/test.py"]
        cmd = EditorSubprocess(args)
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, args)
            with pytest.raises(subprocess.CalledProcessError):
                cmd.run()
