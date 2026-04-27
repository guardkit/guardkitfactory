"""Sequential per-project queue picker (TASK-PSM-006).

This module exposes the per-project sequential build picker used by the
NATS pull consumer (``adapters/nats/pipeline_consumer.py``, shipped in
FEAT-FORGE-002). On every received message the consumer asks the picker
"is this project free to start a new build?". The picker either:

* returns the oldest QUEUED :class:`~forge.lifecycle.persistence.BuildRow`
  for the project — the consumer ACKs and begins preparation; or
* returns ``None`` — the consumer NACKs and JetStream redelivers later.

ASSUM-004 (confirmed) scopes sequential discipline as **per-project**:
only one build runs at a time *per project*; different projects can run
concurrently. ``project=None`` is the fleet-wide scope (per-NULL
semantics) — two ``None`` projects compare equal via ``IS NULL``
predicates (SQLite NULL semantics; equality comparison against NULL
always evaluates to NULL, so the standard ``=`` operator must not be
used for the fleet-wide scope).

Concurrency contract
--------------------

The picker query runs inside a ``BEGIN IMMEDIATE`` transaction so the
write lock is acquired up-front. This prevents two consumer instances
from both observing the same QUEUED build as pickable and both
ACK-ing it in parallel (Group F "two simultaneous queues"). The
transaction is committed unconditionally — the picker never writes,
but the lock acquisition serialises concurrent pick attempts at the
SQLite engine level.

Design rules baked into this module:

* **Thin** — purely query logic. The pull consumer's handler (the
  caller) is responsible for ACK / NACK dispatch and for composing any
  follow-up :class:`~forge.lifecycle.state_machine.Transition`. This
  module never writes ``builds.status``.
* **NULL-safe** — every project comparison branches on ``project is
  None`` and uses ``IS NULL`` (the equality operator against NULL
  evaluates to NULL in SQLite, never true).
* **Atomic** — ``next_build_to_pick`` runs inside ``BEGIN IMMEDIATE``;
  the rollback path is exercised on any ``sqlite3.Error`` so the
  writer connection never sits in a half-open transaction.

References
----------

- TASK-PSM-006 — this task brief.
- TASK-PSM-002 — schema + connection helpers (``SCHEMA_INITIALIZED``).
- TASK-PSM-005 — the persistence facade we compose.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Final

from forge.lifecycle.persistence import (
    BuildRow,
    SqliteLifecyclePersistence,
    _row_to_build_row,
)
from forge.lifecycle.state_machine import BuildState

__all__ = [
    "BLOCKING_STATES",
    "SqliteSequentialQueuePicker",
    "is_project_busy",
    "next_build_to_pick",
]


#: Lifecycle states that, when occupied by *any* build for a project,
#: prevent a fresh QUEUED build for the same project from being picked.
#:
#: ``QUEUED`` is **not** in this set: a project may have many QUEUED
#: builds waiting; the picker simply returns the oldest one. The
#: blocking states are the in-flight, non-terminal states that signify
#: ongoing work. INTERRUPTED is also excluded — it represents a build
#: awaiting recovery and the recovery pass (TASK-PSM-007) re-pickups
#: it via the standard transition table; it should not block fresh
#: picks because that would deadlock the project until manual
#: intervention.
BLOCKING_STATES: Final[frozenset[BuildState]] = frozenset(
    {
        BuildState.PREPARING,
        BuildState.RUNNING,
        BuildState.PAUSED,
        BuildState.FINALISING,
    }
)


# ---------------------------------------------------------------------------
# Class-based facade
# ---------------------------------------------------------------------------


class SqliteSequentialQueuePicker:
    """Per-project sequential build picker over a SQLite writer connection.

    Composes :class:`~forge.lifecycle.persistence.SqliteLifecyclePersistence`
    so the picker shares the same writer connection that
    ``apply_transition`` uses — this is what gives ``BEGIN IMMEDIATE``
    its mutual-exclusion property: a competing consumer trying to
    pick on the same database file will block on the busy_timeout.

    Args:
        persistence: The lifecycle persistence facade. The picker reads
            the writer connection off ``persistence.connection``.
    """

    def __init__(self, persistence: SqliteLifecyclePersistence) -> None:
        self._persistence = persistence
        self._cx = persistence.connection

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def next_build_to_pick(self, project: str | None) -> BuildRow | None:
        """Return the oldest QUEUED build for ``project``, or ``None``.

        Returns ``None`` when:

        * Any build for ``project`` is already in :data:`BLOCKING_STATES`
          (PREPARING / RUNNING / PAUSED / FINALISING) — the project is
          busy, the consumer must NACK; or
        * No QUEUED build exists for ``project`` — nothing to pick.

        Otherwise returns the QUEUED build with the smallest
        ``queued_at`` (FIFO within the project).

        The whole decision runs inside ``BEGIN IMMEDIATE`` so two
        consumer instances racing on the same database serialise:
        the second ``BEGIN IMMEDIATE`` blocks on the writer lock
        until the first commits, and then re-evaluates against the
        post-commit state.

        Args:
            project: Project name. ``None`` means the fleet-wide scope
                — only builds with a NULL ``project`` column are
                considered, via ``IS NULL`` predicates.

        Returns:
            The picked :class:`BuildRow`, or ``None`` if the project is
            busy or has nothing queued.

        Raises:
            sqlite3.Error: Re-raised after rollback. The caller is
                expected to log and let JetStream redeliver.
        """
        try:
            self._cx.execute("BEGIN IMMEDIATE;")
        except sqlite3.Error:
            # Could not acquire the write lock at all (e.g. another
            # writer holds it past busy_timeout). Surface to the caller.
            raise

        try:
            if self._project_has_blocking_build(project):
                self._cx.execute("COMMIT;")
                return None

            row = self._select_oldest_queued(project)
            self._cx.execute("COMMIT;")
        except sqlite3.Error:
            try:
                self._cx.execute("ROLLBACK;")
            except sqlite3.Error:  # pragma: no cover - rollback failure is rare
                pass
            raise

        if row is None:
            return None
        return _row_to_build_row(row)

    def is_project_busy(self, project: str | None) -> bool:
        """Return ``True`` iff ``project`` has any blocking-state build.

        A project is *busy* when at least one build for that project is
        in :data:`BLOCKING_STATES`. The fleet-wide scope (``project is
        None``) compares against the NULL ``project`` column via ``IS
        NULL`` — two ``None`` projects are the **same** scope (Group F
        NULL-semantics correctness criterion).

        This is a cheap predicate intended for the consumer handler's
        fast-path; it does **not** acquire the write lock. Callers that
        need atomicity must use :meth:`next_build_to_pick` instead.
        """
        return self._project_has_blocking_build(project)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _project_has_blocking_build(self, project: str | None) -> bool:
        """Return ``True`` if any build for ``project`` is blocking."""
        blocking_values = tuple(s.value for s in BLOCKING_STATES)
        placeholders = ",".join(["?"] * len(blocking_values))
        if project is None:
            sql = (
                "SELECT 1 "
                "  FROM builds "
                " WHERE project IS NULL "
                f"   AND status IN ({placeholders}) "
                " LIMIT 1"
            )
            params: list[Any] = list(blocking_values)
        else:
            sql = (
                "SELECT 1 "
                "  FROM builds "
                " WHERE project = ? "
                f"   AND status IN ({placeholders}) "
                " LIMIT 1"
            )
            params = [project, *blocking_values]
        row = self._cx.execute(sql, params).fetchone()
        return row is not None

    def _select_oldest_queued(
        self, project: str | None
    ) -> sqlite3.Row | tuple[Any, ...] | None:
        """Return the oldest QUEUED row for ``project`` (or ``None``)."""
        if project is None:
            sql = (
                "SELECT * "
                "  FROM builds "
                " WHERE project IS NULL "
                "   AND status = 'QUEUED' "
                " ORDER BY queued_at ASC "
                " LIMIT 1"
            )
            params: list[Any] = []
        else:
            sql = (
                "SELECT * "
                "  FROM builds "
                " WHERE project = ? "
                "   AND status = 'QUEUED' "
                " ORDER BY queued_at ASC "
                " LIMIT 1"
            )
            params = [project]
        return self._cx.execute(sql, params).fetchone()


# ---------------------------------------------------------------------------
# Module-level convenience wrappers
# ---------------------------------------------------------------------------


def next_build_to_pick(
    persistence: SqliteLifecyclePersistence,
    project: str | None,
) -> BuildRow | None:
    """Module-level wrapper for :meth:`SqliteSequentialQueuePicker.next_build_to_pick`.

    Provided so callers that only need the picker once (e.g. a unit
    test or an ad-hoc CLI debug command) do not have to instantiate
    the class. Production consumers typically hold a long-lived
    :class:`SqliteSequentialQueuePicker` instance instead.
    """
    return SqliteSequentialQueuePicker(persistence).next_build_to_pick(project)


def is_project_busy(
    persistence: SqliteLifecyclePersistence,
    project: str | None = None,
) -> bool:
    """Module-level wrapper for :meth:`SqliteSequentialQueuePicker.is_project_busy`."""
    return SqliteSequentialQueuePicker(persistence).is_project_busy(project)
