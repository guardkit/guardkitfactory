"""Open a file from a project's worktree only when it is a regular file.

The checkers read files that a model wrote. A named pipe (``mkfifo``) among
them makes a plain ``open()`` wait forever for a writer, and a device such as
``/dev/zero`` (reached through a link) never ends. Either one hangs the
Coach turn. So every checker read goes through :func:`open_regular`:

- the entry is looked up first (following links, as ``open()`` does) and only
  a regular file goes on;
- it is then opened non-blocking, so a pipe swapped in between the look-up and
  the open cannot block, and the type is checked again on the open file;
- anything else (a pipe, a socket, a device, a folder) is skipped, with a
  plain note in the log, and never opened for reading.

A link to a regular file is followed and read, exactly as before.
"""

from __future__ import annotations

import io
import logging
import os
import stat
from typing import BinaryIO

logger = logging.getLogger(__name__)

def special_kind(mode: int) -> str:
    """``""`` for a regular file, else a plain name for the kind of entry."""
    if stat.S_ISREG(mode):
        return ""
    if stat.S_ISFIFO(mode):
        return "named pipe"
    if stat.S_ISSOCK(mode):
        return "socket"
    if stat.S_ISCHR(mode):
        return "character device"
    if stat.S_ISBLK(mode):
        return "block device"
    if stat.S_ISDIR(mode):
        return "folder"
    return "special file"


def _skip(path: str | os.PathLike[str], kind: str) -> None:
    logger.info(
        "Skipped %s: it is a %s, not a regular file, so it was not read.",
        os.fspath(path),
        kind,
    )


def open_regular(path: str | os.PathLike[str]) -> BinaryIO | None:
    """Open ``path`` for binary reading if it is a regular file.

    Returns ``None`` (after a log note) for any other kind of entry. Never
    blocks. Raises ``OSError`` when the entry is missing or cannot be read,
    as ``open()`` would.
    """
    kind = special_kind(os.stat(path).st_mode)
    if kind:
        _skip(path, kind)
        return None
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        kind = special_kind(os.fstat(fd).st_mode)
    except BaseException:
        os.close(fd)
        raise
    if kind:
        os.close(fd)
        _skip(path, kind)
        return None
    return os.fdopen(fd, "rb")


def read_regular_bytes(path: str | os.PathLike[str]) -> bytes | None:
    """The bytes of a regular file; ``None`` if it is anything else or cannot
    be read. Never blocks."""
    try:
        handle = open_regular(path)
        if handle is None:
            return None
        with handle:
            return handle.read()
    except OSError:
        return None


def read_regular_text(
    path: str | os.PathLike[str],
    *,
    encoding: str | None = None,
    errors: str | None = None,
) -> str | None:
    """The text of a regular file, decoded as ``open(path, encoding=...,
    errors=...)`` would (same default encoding and newline handling);
    ``None`` if it is anything else. Never blocks. Raises ``OSError`` and
    decoding errors as ``open()`` would, so callers keep their own handling.
    """
    handle = open_regular(path)
    if handle is None:
        return None
    with io.TextIOWrapper(handle, encoding=encoding, errors=errors) as text:
        return text.read()
