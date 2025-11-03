"""Tuick shell utilities."""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


def quote_command(words: Iterable[str]) -> str:
    """Shell quote words and join in a single command string."""
    return " ".join(quote_command_words(words))


def quote_command_words(words: Iterable[str]) -> Iterator[str]:
    """Shell quote words and yield each quoted word."""
    first = True
    for word in words:
        yield _quote_word(word, first)
        first = False


def _quote_word(word: str, first: bool) -> str:  # noqa: FBT001
    if not _needs_quoting(word, first=first):
        return word
    if "'" not in word:
        # That covers the empty case too
        return f"'{word}'"
    for char in '\\"$`':
        word = word.replace(char, "\\" + char)
    return f'"{word}"'


def _needs_quoting(word: str, first: bool) -> bool:  # noqa: FBT001
    if not word:
        return True

    # According to the shlex module documentation:
    # Basic safe characters: a-zA-Z0-9_
    # Additional (punctuation_chars=True): ~-./*?=
    # Unsafe word separator chars: ();<>|&

    # Weirdly, "*?" are not considered unsafe, but they must be quoted to
    # prevent globbing (file name expansion). Also, the characters ":,@%+" are
    # not special (except in association with "{}$"), but are not treated as
    # safe by shlex.

    # In the end, basic "a-zA-Z0-9_", additional "~-./=" (not * and ?), and our
    # special list ":,@%+" are safe.

    if not re.match(r"^[a-zA-Z0-9_~\-./=:,@%+]+$", word):
        return True
    return (first and "=" in word[1:]) or word[0] == "~"
