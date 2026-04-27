"""SQLite connection helpers (TASK-PSM-002 / DDR-003).

Two helpers, deliberately minimal and stable — every consumer in the
feature reuses them:

- :func:`connect_writer` opens the persistent agent-runtime write
  connection. Single per-process, held for the lifetime of the
  runtime; serialised externally by an asyncio lock.
- :func:`read_only_connect` opens a short-lived reader on a
  ``mode=ro`` URI filename for CLI invocations.

Both helpers apply the four mandatory pragmas declared in DDR-003 on
every open:

- ``journal_mode = WAL`` — readers never block writers.
- ``synchronous = NORMAL`` — durability is bounded by the most recent
  uncommitted transaction; JetStream redelivery covers the rest.
- ``foreign_keys = ON`` — STRICT tables already validate types but the
  ``stage_log → builds`` foreign key only fires when this is on.
- ``busy_timeout = 5000`` — five-second hold for the rare CLI/agent
  contention window.

The helpers raise :class:`SQLiteConnectError` when a path is rejected
before any pragmas can run; we'd rather surface a clear domain-shaped
error at the boundary than a raw ``sqlite3.OperationalError`` half-way
through pragma application.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Final


# DDR-003 §Decision — busy timeout in milliseconds. Five seconds covers
# the worst-case CLI burst against a writer mid-transaction; anything
# longer and the CLI feels frozen.
DEFAULT_BUSY_TIMEOUT_MS: Final[int] = 5_000


class SQLiteConnectError(RuntimeError):
    """Raised when a connection helper cannot open the database.

    This is a domain-shaped error so callers can catch it without
    importing :mod:`sqlite3`. The originating ``sqlite3`` exception is
    preserved as ``__cause__`` for diagnostics.
    """


def _apply_pragmas(
    connection: sqlite3.Connection,
    *,
    read_only: bool,
) -> None:
    """Apply the four DDR-003 pragmas to ``connection``.

    On a read-only connection, ``journal_mode`` is still queried (so
    the connection observes the WAL mode the writer set) but no other
    side effect is required. ``synchronous`` and ``foreign_keys`` are
    applied because pragma scope is per-connection — the writer's
    settings do not propagate to readers — and they cost nothing on
    reads.
    """
    if read_only:
        # Reading the pragma without setting it; SQLite refuses the
        # mutating form on a mode=ro connection.
        connection.execute("PRAGMA journal_mode;")
    else:
        connection.execute("PRAGMA journal_mode = WAL;")

    connection.execute("PRAGMA synchronous = NORMAL;")
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute(f"PRAGMA busy_timeout = {DEFAULT_BUSY_TIMEOUT_MS};")


def connect_writer(db_path: Path) -> sqlite3.Connection:
    """Open the persistent write connection.

    Parameters
    ----------
    db_path:
        Filesystem path to ``forge.db``. The parent directory must
        already exist; the helper does not auto-create it because the
        caller (the agent runtime bootstrap) is the right place to
        decide whether a missing ``~/.forge/`` directory is an error.

    Returns
    -------
    sqlite3.Connection
        A writable connection with the four DDR-003 pragmas applied.

    Raises
    ------
    SQLiteConnectError
        When the path cannot be opened (e.g. parent directory missing,
        permission denied).
    """
    if not isinstance(db_path, Path):
        # Defensive — every adapter in this package types ``Path`` and
        # the AC requires it, but downstream callers occasionally hand
        # us strings during early bring-up.
        db_path = Path(db_path)

    parent = db_path.parent
    if not parent.exists():
        raise SQLiteConnectError(
            f"parent directory does not exist for {db_path!s}: {parent!s}"
        )

    try:
        connection = sqlite3.connect(
            str(db_path),
            isolation_level=None,  # autocommit; transactions managed via ``with cx``
            check_same_thread=False,
            timeout=DEFAULT_BUSY_TIMEOUT_MS / 1000,
        )
    except sqlite3.Error as exc:
        raise SQLiteConnectError(
            f"failed to open writer connection at {db_path!s}: {exc}"
        ) from exc

    try:
        _apply_pragmas(connection, read_only=False)
    except sqlite3.Error as exc:
        connection.close()
        raise SQLiteConnectError(
            f"failed to apply pragmas on writer connection: {exc}"
        ) from exc

    return connection


def read_only_connect(db_path: Path) -> sqlite3.Connection:
    """Open a short-lived read-only connection.

    Uses the ``file:<path>?mode=ro`` URI form so SQLite refuses any
    write attempt at the engine level — this is the safety net behind
    ADR-ARCH-013 (CLI never writes).

    Parameters
    ----------
    db_path:
        Filesystem path to ``forge.db``. The file must already exist;
        opening a non-existent DB in ``mode=ro`` raises immediately.

    Returns
    -------
    sqlite3.Connection
        A read-only connection with the DDR-003 pragmas applied.

    Raises
    ------
    SQLiteConnectError
        When the path cannot be opened (e.g. file missing, permission
        denied).
    """
    if not isinstance(db_path, Path):
        db_path = Path(db_path)

    if not db_path.exists():
        raise SQLiteConnectError(
            f"cannot open read-only connection — database not found: {db_path!s}"
        )

    uri = f"file:{db_path}?mode=ro"
    try:
        connection = sqlite3.connect(
            uri,
            uri=True,
            isolation_level=None,
            check_same_thread=False,
            timeout=DEFAULT_BUSY_TIMEOUT_MS / 1000,
        )
    except sqlite3.Error as exc:
        raise SQLiteConnectError(
            f"failed to open read-only connection at {db_path!s}: {exc}"
        ) from exc

    try:
        _apply_pragmas(connection, read_only=True)
    except sqlite3.Error as exc:
        connection.close()
        raise SQLiteConnectError(
            f"failed to apply pragmas on read-only connection: {exc}"
        ) from exc

    return connection


__all__ = [
    "DEFAULT_BUSY_TIMEOUT_MS",
    "SQLiteConnectError",
    "connect_writer",
    "read_only_connect",
]
