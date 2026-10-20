"""Open a file from a project's worktree only when it is a regular file.

The checkers read files that a model wrote. A named pipe (``mkfifo``) among
them makes a plain ``open()`` wait forever for a writer, and a device such as
``/dev/zero`` (reached through a link) never ends. Either one hangs the
Coach turn. So every checker read goes through :func:`open_regular`:

- the entry is looked up first (following links, as ``open()`` does) and only
  a regular file goes on;
- it is then opened non-blocking, so a pipe swapped in between the look-up and
  the open cannot block, and the type is checked again on the open file;
- anything else (a pipe, a socket, a device, a folder) is skipped and never
  opened for reading.

A link to a regular file is followed and read, exactly as before.

Each skipped entry is logged at DEBUG. A checker that reads many files runs
inside :func:`skipped_entries_summary`, which writes one INFO line for the
whole call (how many entries were skipped and the first few of them), so a
worktree holding thousands of sockets does not flood the run log. A read made
outside such a call logs its one skipped entry at INFO.
"""

from __future__ import annotations

import functools
import io
import logging
import os
import stat
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import BinaryIO, TypeVar

logger = logging.getLogger(__name__)

_EXAMPLES = 3

#: The skipped entries of the checker call in progress (path -> kind), or
#: ``None`` outside any such call.
_skipped: ContextVar[dict[str, str] | None] = ContextVar(
    "guardkitfactory_skipped_entries", default=None
)

_F = TypeVar("_F", bound=Callable[..., object])


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
    name = os.fspath(path)
    found = _skipped.get()
    if found is None:
        logger.info(
            "Skipped %s: it is a %s, not a regular file, so it was not read.", name, kind
        )
        return
    logger.debug("Skipped %s: it is a %s, not a regular file, so it was not read.", name, kind)
    found.setdefault(name, kind)


@contextmanager
def skipped_entries_summary(what: str) -> Iterator[None]:
    """Collect the entries skipped during one checker call and log them as
    one INFO line at the end. Inside another such call it adds to that one,
    so a checker calling other checkers still writes a single line."""
    if _skipped.get() is not None:
        yield
        return
    found: dict[str, str] = {}
    token = _skipped.set(found)
    try:
        yield
    finally:
        _skipped.reset(token)
        if found:
            examples = "; ".join(
                f"{name} ({kind})" for name, kind in list(found.items())[:_EXAMPLES]
            )
            more = len(found) - _EXAMPLES
            if len(found) == 1:
                counted = "1 entry that is not a regular file, so it was"
            else:
                counted = f"{len(found)} entries that are not regular files, so they were"
            logger.info(
                "%s skipped %s not read: %s%s.",
                what,
                counted,
                examples,
                f"; and {more} more" if more > 0 else "",
            )


def summarise_skipped_entries(what: str) -> Callable[[_F], _F]:
    """Decorator form of :func:`skipped_entries_summary`."""

    def wrap(func: _F) -> _F:
        @functools.wraps(func)
        def inner(*args: object, **kwargs: object) -> object:
            with skipped_entries_summary(what):
                return func(*args, **kwargs)

        return inner  # type: ignore[return-value]

    return wrap


def open_regular(path: str | os.PathLike[str]) -> BinaryIO | None:
    """Open ``path`` for binary reading if it is a regular file.

    Returns ``None`` (after a log note, see the module notes) for any other
    kind of entry. Never blocks. Raises ``OSError`` when the entry is missing
    or cannot be read, as ``open()`` would.
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
