"""Editor detection and command building."""

import os
import platform
import subprocess
import typing
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

if typing.TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass
class FileLocation:
    """File location with optional row and column."""

    path: str
    row: int | None = None
    column: int | None = None


class FileLocationNotFoundError(ValueError):
    """Error when location pattern not found in selection."""

    def __init__(self, selection: str) -> None:
        """Initialize with the selection text."""
        self.selection = selection
        super().__init__(f"Location pattern not found in: {selection!r}")

    def __rich__(self) -> str:
        """Rich formatted error message."""
        return (
            f"[bold red]Error:[/] Location pattern not found\n"
            f"[bold]Input:[/] {self.selection!r}"
        )


class EditorCommand:
    """Abstract base class for editor commands."""

    def run(self) -> None:
        """Execute the command, may raise subprocess.CalledProcessError."""
        raise NotImplementedError

    def command_words(self) -> list[str]:
        """Return the command as a list of words."""
        raise NotImplementedError


@dataclass
class BaseEditorURL(EditorCommand):
    """Editor command using URL scheme."""

    url: str

    def command_words(self) -> list[str]:
        """Return the command as a list of words."""
        raise NotImplementedError

    def run(self) -> None:
        """Execute the command."""
        subprocess.run(self.command_words(), check=True)


class DarwinEditorUrl(BaseEditorURL):
    """Editor command using URL scheme via 'open' command on Darwin."""

    def command_words(self) -> list[str]:
        """Return the command as a list of words."""
        return ["open", self.url]


class WindowsEditorUrl(BaseEditorURL):
    """Editor command using URL scheme via os.startfile on Windows."""

    def run(self) -> None:
        """Execute the os.startfile command."""
        os.startfile(self.url)  # type: ignore[attr-defined]  # noqa: S606

    def command_words(self) -> list[str]:
        """Return the command as a list of words."""
        return ["start", self.url]


class LinuxEditorUrl(BaseEditorURL):
    """Editor command using URL scheme via 'xdg-open' on Linux."""

    def command_words(self) -> list[str]:
        """Return the command as a list of words."""
        return ["xdg-open", self.url]


def _setup_editor_url() -> type[BaseEditorURL]:
    if platform.system() == "Darwin":
        return DarwinEditorUrl
    if platform.system() == "Windows":
        return WindowsEditorUrl
    return LinuxEditorUrl


EditorURL = _setup_editor_url()


@dataclass
class EditorSubprocess(EditorCommand):
    """Editor command using direct subprocess execution."""

    args: Sequence[str]

    def run(self) -> None:
        """Execute the command."""
        subprocess.run(self.args, check=True)

    def command_words(self) -> list[str]:
        """Return the command as a list of words."""
        return list(self.args)


class UnsupportedEditorError(ValueError):
    """Error when editor is not supported."""

    def __init__(self, editor_name: str) -> None:
        """Initialize with the editor name."""
        self.editor_name = editor_name
        super().__init__(f"Unsupported editor: {editor_name}")


class BaseEditor:
    """Base class for editor command builders."""

    command_names: typing.ClassVar[Sequence[str]] = ()
    _registry: typing.ClassVar[dict[str, type[BaseEditor]]] = {}

    def __init_subclass__(cls) -> None:
        """Register editor class for all its command names."""
        for name in cls.command_names:
            BaseEditor._registry[name] = cls

    def __init__(self, editor_path: str, editor_args: Sequence[str]) -> None:
        """Initialize editor with path and arguments."""
        self.editor_path = editor_path
        self.editor_args = editor_args

    def get_command(self, location: FileLocation) -> EditorCommand:
        """Build command for opening file at location."""
        raise NotImplementedError

    @classmethod
    def get_editor_class(cls, editor_name: str) -> type[BaseEditor]:
        """Get editor class for editor name."""
        editor_class = cls._registry.get(editor_name)
        if editor_class is None:
            raise UnsupportedEditorError(editor_name)
        return editor_class


class JetBrainsEditor(BaseEditor):
    """IntelliJ IDEA editor."""

    command_names = ("idea",)

    def get_command(self, location: FileLocation) -> EditorCommand:
        """Build IDEA URL scheme command."""
        if "--wait" in self.editor_args:
            position_args = ["--line", str(location.row)]
            if location.column is not None:
                position_args.extend(["--column", str(location.column)])
            args = [
                self.editor_path,
                *self.editor_args,
                *position_args,
                location.path,
            ]
            return EditorSubprocess(args)

        abs_path = Path(location.path).resolve(strict=True)
        quoted_path = quote(str(abs_path), safe="")
        url = f"idea://open?file={quoted_path}&line={location.row}"
        if location.column is not None:
            url += f"&column={location.column}"
        return EditorURL(url)


class PyCharmEditor(BaseEditor):
    """PyCharm editor."""

    command_names = ("charm", "pycharm")

    def get_command(self, location: FileLocation) -> EditorCommand:
        """Build PyCharm URL scheme command."""
        abs_path = Path(location.path).resolve(strict=True)
        quoted_path = quote(str(abs_path), safe="")
        url = f"pycharm://open?file={quoted_path}&line={location.row}"
        if location.column is not None:
            url += f"&column={location.column}"
        return EditorURL(url)


class VSCodeEditor(BaseEditor):
    """VSCode editor and variants."""

    command_names = ("code", "code-oss", "surf", "cursor")

    def _url_scheme(self) -> str:
        return {
            "code": "vscode",
            "code-oss": "code-oss",
            "surf": "windsurf",
            "cursor": "cursor",
        }[Path(self.editor_path).name]

    def get_command(self, location: FileLocation) -> EditorCommand:
        """Build VSCode command, using URL scheme unless --wait present."""
        if "--wait" in self.editor_args:
            dest = f"{location.path}:{location.row}"
            if location.column is not None:
                dest += f":{location.column}"
            args = [self.editor_path, *self.editor_args, "--goto", dest]
            return EditorSubprocess(args)

        abs_path = Path(location.path).resolve()
        url = f"{self._url_scheme()}://file/{abs_path}:{location.row}"
        if location.column is not None:
            url += f":{location.column}"
        return EditorURL(url)


class VimEditor(BaseEditor):
    """Vim-like editors."""

    command_names = ("vim", "nvim", "vi")

    def get_command(self, location: FileLocation) -> EditorCommand:
        """Build vim command."""
        cmd = [self.editor_path, *self.editor_args, f"+{location.row}"]
        if location.column is not None:
            cmd.append(f"+normal! {location.column}l")
        cmd.append(location.path)
        return EditorSubprocess(cmd)


class EmacsEditor(BaseEditor):
    """Emacs-like editors."""

    command_names = ("emacs", "emacsclient", "gedit", "kak")

    def get_command(self, location: FileLocation) -> EditorCommand:
        """Build emacs command."""
        if location.column is not None:
            pos = f"+{location.row}:{location.column}"
        else:
            pos = f"+{location.row}"
        args = [self.editor_path, *self.editor_args, pos, location.path]
        return EditorSubprocess(args)


class NanoEditor(BaseEditor):
    """Nano editor."""

    command_names = ("nano",)

    def get_command(self, location: FileLocation) -> EditorCommand:
        """Build nano command."""
        if location.column is not None:
            pos = f"+{location.row},{location.column}"
        else:
            pos = f"+{location.row}"
        args = [self.editor_path, *self.editor_args, pos, location.path]
        return EditorSubprocess(args)


class JoeEditor(BaseEditor):
    """Joe and ee editors."""

    command_names = ("joe", "ee")

    def get_command(self, location: FileLocation) -> EditorCommand:
        """Build joe/ee command."""
        args = [
            self.editor_path,
            *self.editor_args,
            f"+{location.row}",
            location.path,
        ]
        return EditorSubprocess(args)


class FileColonPositionEditor(BaseEditor):
    """Editors that support the file:line[:col] syntax."""

    command_names = ("subl", "helix", "hx", "zed")

    def get_command(self, location: FileLocation) -> EditorCommand:
        """Build text editor command."""
        dest = f"{location.path}:{location.row}"
        if location.column is not None:
            dest += f":{location.column}"
        args = [self.editor_path, *self.editor_args, dest]
        return EditorSubprocess(args)


class MicroEditor(BaseEditor):
    """Micro editor."""

    command_names = ("micro",)

    def get_command(self, location: FileLocation) -> EditorCommand:
        """Build micro command."""
        if location.column is not None:
            pos = f"+{location.row}:{location.column}"
        else:
            pos = f"+{location.row}"
        args = [self.editor_path, *self.editor_args, location.path, pos]
        return EditorSubprocess(args)


class OEditor(BaseEditor):
    """O editor."""

    command_names = ("o",)

    def get_command(self, location: FileLocation) -> EditorCommand:
        """Build o editor command."""
        cmd = [
            self.editor_path,
            *self.editor_args,
            location.path,
            f"+{location.row}",
        ]
        if location.column is not None:
            cmd.append(f"+{location.column}")
        return EditorSubprocess(cmd)


def _expand_editor_template(template: str, **kwargs: str | int) -> list[str]:
    """Expand editor template with placeholders.

    Splits template BEFORE interpolation to handle file names with spaces.
    """
    path_head, command_and_args = os.path.split(template)
    parts = command_and_args.split()
    expanded_parts = [part.format(**kwargs) for part in parts]

    if path_head:
        editor_path = str(Path(path_head) / expanded_parts[0])
        return [editor_path, *expanded_parts[1:]]
    return expanded_parts


def _validate_templates() -> None:
    """Validate template environment variables on command start.

    Tests that templates can be formatted successfully. Catches ValueError and
    LookupError to detect invalid syntax or placeholders.
    """
    line_template = os.environ.get("TUICK_EDITOR_LINE")
    line_col_template = os.environ.get("TUICK_EDITOR_LINE_COLUMN")

    if line_template:
        try:
            _expand_editor_template(line_template, file="test.py", line=1)
        except (ValueError, LookupError) as e:
            msg = f"Invalid TUICK_EDITOR_LINE template: {e}"
            raise ValueError(msg) from e

    if line_col_template:
        try:
            _expand_editor_template(
                line_col_template, file="test.py", line=1, column=1
            )
        except (ValueError, LookupError) as e:
            msg = f"Invalid TUICK_EDITOR_LINE_COLUMN template: {e}"
            raise ValueError(msg) from e


class CustomEditor(BaseEditor):
    """Editor using custom templates from environment variables."""

    command_names = ()

    def get_command(self, location: FileLocation) -> EditorCommand:
        """Build command from template environment variables."""
        line_col_template = os.environ.get("TUICK_EDITOR_LINE_COLUMN")
        line_template = os.environ.get("TUICK_EDITOR_LINE")

        if location.column is not None and line_col_template:
            args = _expand_editor_template(
                line_col_template,
                file=location.path,
                line=location.row or 0,
                column=location.column,
            )
            return EditorSubprocess(args)

        if line_template:
            args = _expand_editor_template(
                line_template,
                file=location.path,
                line=location.row or 0,
            )
            return EditorSubprocess(args)

        msg = "CustomEditor called without templates set"
        raise AssertionError(msg)


def get_editor_from_env() -> str | None:
    """Get editor command from environment variables.

    Checks TUICK_EDITOR first, then EDITOR, then VISUAL.
    """
    return (
        os.environ.get("TUICK_EDITOR")
        or os.environ.get("EDITOR")
        or os.environ.get("VISUAL")
    )


def get_editor_command(location: FileLocation) -> EditorCommand:
    """Build editor command from environment and file location.

    Checks TUICK_EDITOR_LINE_COLUMN and TUICK_EDITOR_LINE templates first, then
    falls back to TUICK_EDITOR/EDITOR/VISUAL.
    """
    line_col_template = os.environ.get("TUICK_EDITOR_LINE_COLUMN")
    line_template = os.environ.get("TUICK_EDITOR_LINE")

    if line_col_template or line_template:
        custom_editor = CustomEditor("", [])
        return custom_editor.get_command(location)

    editor = (
        os.environ.get("TUICK_EDITOR")
        or os.environ.get("EDITOR")
        or os.environ.get("VISUAL")
    )

    if not editor:
        msg = "No editor configured in environment"
        raise ValueError(msg)

    path_head, command_and_args = os.path.split(editor)
    parts = command_and_args.split()
    editor_name = parts[0]
    editor_args = parts[1:]
    if path_head:
        editor_path = str(Path(path_head) / editor_name)
    else:
        editor_path = editor_name

    editor_class = BaseEditor.get_editor_class(editor_name)
    editor_instance = editor_class(editor_path, editor_args)
    return editor_instance.get_command(location)
