"""SQLite adapter package — connection helpers + writer/reader APIs.

The two helpers re-exported here are the canonical entrypoints for
every consumer of the durable build-history store. Keeping them
importable from the package root means callers don't need to know
where individual modules live.

- :func:`connect_writer` — persistent agent-runtime write connection
  with the four DDR-003 pragmas pre-applied.
- :func:`read_only_connect` — short-lived ``mode=ro`` reader for the
  CLI bypass path (ADR-ARCH-013).
"""

from forge.adapters.sqlite.connect import (
    DEFAULT_BUSY_TIMEOUT_MS,
    connect_writer,
    read_only_connect,
)

__all__ = [
    "DEFAULT_BUSY_TIMEOUT_MS",
    "connect_writer",
    "read_only_connect",
]
