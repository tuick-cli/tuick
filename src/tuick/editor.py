"""Editor detection and command building."""

import os
import shlex
import typing
from pathlib import Path
from urllib.parse import quote

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from tuick.parser import FileLocation


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

    def get_command(self, location: FileLocation) -> Sequence[str]:
        """Build command for opening file at location."""
        raise NotImplementedError

    @classmethod
    def get_editor_class(cls, editor_name: str) -> type[BaseEditor]:
        """Get editor class for editor name."""
        editor_class = cls._registry.get(editor_name)
        if editor_class is None:
            raise UnsupportedEditorError(editor_name)
        return editor_class


class IdeaEditor(BaseEditor):
    """IntelliJ IDEA editor."""

    command_names = ("idea",)

    def get_command(self, location: FileLocation) -> Sequence[str]:
        """Build IDEA URL scheme command."""
        abs_path = Path(location.path).resolve(strict=True)
        quoted_path = quote(str(abs_path), safe="")
        url = f"idea://open?file={quoted_path}&line={location.row}"
        if location.column is not None:
            url += f"&column={location.column}"
        return ["open", url]


class PyCharmEditor(BaseEditor):
    """PyCharm editor."""

    command_names = ("charm", "pycharm")

    def get_command(self, location: FileLocation) -> Sequence[str]:
        """Build PyCharm URL scheme command."""
        abs_path = Path(location.path).resolve(strict=True)
        quoted_path = quote(str(abs_path), safe="")
        url = f"pycharm://open?file={quoted_path}&line={location.row}"
        if location.column is not None:
            url += f"&column={location.column}"
        return ["open", url]


class VSCodeEditor(BaseEditor):
    """VSCode editor."""

    command_names = ("code",)

    def get_command(self, location: FileLocation) -> Sequence[str]:
        """Build VSCode command, using URL scheme unless --wait present."""
        if "--wait" in self.editor_args:
            dest = f"{location.path}:{location.row}"
            if location.column is not None:
                dest += f":{location.column}"
            return ["code", *self.editor_args, "--goto", dest]

        abs_path = Path(location.path).resolve(strict=True)
        url = f"vscode://file/{abs_path}:{location.row}"
        if location.column is not None:
            url += f":{location.column}"
        return ["open", url]


class VSCodeOSSEditor(BaseEditor):
    """VSCode OSS editor."""

    command_names = ("code-oss",)

    def get_command(self, location: FileLocation) -> Sequence[str]:
        """Build VSCode OSS command, using URL scheme unless --wait present."""
        if "--wait" in self.editor_args:
            dest = f"{location.path}:{location.row}"
            if location.column is not None:
                dest += f":{location.column}"
            return ["code-oss", *self.editor_args, "--goto", dest]

        abs_path = Path(location.path).resolve(strict=True)
        url = f"code-oss://file/{abs_path}:{location.row}"
        if location.column is not None:
            url += f":{location.column}"
        return ["open", url]


class VimEditor(BaseEditor):
    """Vim-like editors."""

    command_names = ("vim", "nvim", "vi")

    def get_command(self, location: FileLocation) -> Sequence[str]:
        """Build vim command."""
        cmd = [self.editor_path, *self.editor_args, f"+{location.row}"]
        if location.column is not None:
            cmd.append(f"+normal! {location.column}l")
        cmd.append(location.path)
        return cmd


class EmacsEditor(BaseEditor):
    """Emacs-like editors."""

    command_names = ("emacs", "emacsclient", "gedit")

    def get_command(self, location: FileLocation) -> Sequence[str]:
        """Build emacs command."""
        if location.column is not None:
            pos = f"+{location.row}:{location.column}"
        else:
            pos = f"+{location.row}"
        return [self.editor_path, *self.editor_args, pos, location.path]


class KakouneEditor(BaseEditor):
    """Kakoune editor."""

    command_names = ("kak",)

    def get_command(self, location: FileLocation) -> Sequence[str]:
        """Build kakoune command."""
        if location.column is not None:
            pos = f"+{location.row}:{location.column}"
        else:
            pos = f"+{location.row}"
        return [self.editor_path, *self.editor_args, pos, location.path]


class NanoEditor(BaseEditor):
    """Nano editor."""

    command_names = ("nano",)

    def get_command(self, location: FileLocation) -> Sequence[str]:
        """Build nano command."""
        if location.column is not None:
            pos = f"+{location.row},{location.column}"
        else:
            pos = f"+{location.row}"
        return [self.editor_path, *self.editor_args, pos, location.path]


class JoeEditor(BaseEditor):
    """Joe and ee editors."""

    command_names = ("joe", "ee")

    def get_command(self, location: FileLocation) -> Sequence[str]:
        """Build joe/ee command."""
        return [
            self.editor_path,
            *self.editor_args,
            f"+{location.row}",
            location.path,
        ]


class SublimeEditor(BaseEditor):
    """Sublime Text editor."""

    command_names = ("subl",)

    def get_command(self, location: FileLocation) -> Sequence[str]:
        """Build sublime text command."""
        dest = f"{location.path}:{location.row}"
        if location.column is not None:
            dest += f":{location.column}"
        return [self.editor_path, *self.editor_args, dest, "--wait"]


class MicroEditor(BaseEditor):
    """Micro editor."""

    command_names = ("micro",)

    def get_command(self, location: FileLocation) -> Sequence[str]:
        """Build micro command."""
        if location.column is not None:
            pos = f"+{location.row}:{location.column}"
        else:
            pos = f"+{location.row}"
        return [self.editor_path, *self.editor_args, location.path, pos]


class HelixEditor(BaseEditor):
    """Helix editor."""

    command_names = ("helix", "hx")

    def get_command(self, location: FileLocation) -> Sequence[str]:
        """Build helix command."""
        dest = f"{location.path}:{location.row}"
        if location.column is not None:
            dest += f":{location.column}"
        return [self.editor_path, *self.editor_args, dest]


class ZedEditor(BaseEditor):
    """Zed editor."""

    command_names = ("zed",)

    def get_command(self, location: FileLocation) -> Sequence[str]:
        """Build zed command."""
        dest = f"{location.path}:{location.row}"
        if location.column is not None:
            dest += f":{location.column}"
        return [self.editor_path, *self.editor_args, dest]


class OEditor(BaseEditor):
    """O editor."""

    command_names = ("o",)

    def get_command(self, location: FileLocation) -> Sequence[str]:
        """Build o editor command."""
        cmd = [
            self.editor_path,
            *self.editor_args,
            location.path,
            f"+{location.row}",
        ]
        if location.column is not None:
            cmd.append(f"+{location.column}")
        return cmd


def get_editor_from_env() -> str | None:
    """Get editor command from EDITOR or VISUAL environment variable.

    Returns:
        Editor command with arguments, or None if neither variable is set
    """
    return os.environ.get("EDITOR") or os.environ.get("VISUAL")


def get_editor_command(editor: str, location: FileLocation) -> Sequence[str]:
    """Build editor command from editor string and file location.

    Args:
        editor: Editor command, possibly with arguments
        location: File location with row and optional column

    Returns:
        Command list ready for subprocess execution

    Raises:
        UnsupportedEditorError: If editor is not supported
    """
    # Parse editor command to extract base name and arguments
    # First separate directory path from command to handle paths with spaces
    path_head, command_and_args = os.path.split(editor)

    # Split command and arguments
    parts = shlex.split(command_and_args)
    editor_name = parts[0]
    editor_args = parts[1:]
    editor_path = os.path.join(path_head, editor_name)  # noqa: PTH118

    # Lookup editor class in registry
    editor_class = BaseEditor.get_editor_class(editor_name)

    # Create editor instance and build command
    editor_instance = editor_class(editor_path, editor_args)
    return editor_instance.get_command(location)
