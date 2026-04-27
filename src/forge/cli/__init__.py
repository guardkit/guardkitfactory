"""Forge CLI package — Click commands for the read/write split.

Per ``API-cli.md`` — the CLI is intentionally small (queue, status, history,
cancel, skip). Read commands (``status``/``history``) bypass NATS entirely
and read SQLite directly via :func:`forge.adapters.sqlite.read_only_connect`.

This package follows the import discipline declared in TASK-PSM-010 — the
read modules ``forge.cli.status`` and ``forge.cli.history`` MUST NOT import
from ``forge.adapters.nats.*``. Those modules are added by TASK-PSM-009 /
TASK-PSM-010; the present scaffold (TASK-PSM-008) intentionally only ships
the ``main`` group entry point and the write-path ``queue`` subcommand.

The package is deliberately *thin*: nothing is re-exported here so that
``forge.cli.main:main`` (the entry point referenced by ``pyproject.toml``)
can be imported without dragging in optional NATS dependencies at import
time. Tests assert on this import discipline.
"""

