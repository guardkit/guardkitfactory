"""Production binding for ``AutobuildStateInitialiser`` (TASK-FW10-005).

This module is the third of the four production wirings the Wave 2
collaborator set requires for ``dispatch_autobuild_async`` (per
IMPLEMENTATION-GUIDE.md §4 and the FEAT-FORGE-010 task graph). It wires
the dispatcher's ``state_channel`` Protocol surface to a SQLite-backed
``async_tasks`` writer mirrored on the same ``sqlite_pool`` the rest of
``forge serve`` shares.

Design invariants
-----------------

1. *DDR-006 contract* — the dispatcher writes **only** ``lifecycle="starting"``
   for every dispatch (per
   :data:`forge.pipeline.dispatchers.autobuild_async.AUTOBUILD_STARTING_LIFECYCLE`).
   Subsequent transitions (``planning_waves`` ↦ ``running_wave`` ↦ …)
   are owned by ``autobuild_runner`` (TASK-FW10-002), not by this
   initialiser. The factory does not expose any "transition" method —
   the Protocol surface is a single :meth:`initialise_autobuild_state`
   call.

2. *Single-pool composition* — the initialiser wraps the same
   :class:`forge.lifecycle.persistence.SqliteLifecyclePersistence` facade
   the ``stage_log`` recorder (TASK-FW10-004) and ``builds`` writer use,
   so all three production bindings serialise their writes against one
   connection. This avoids the WAL-conflict / busy-timeout window that
   would arise if every binding opened its own writer.

3. *Idempotent schema* — the ``async_tasks`` table is provisioned via
   ``CREATE TABLE IF NOT EXISTS`` on every initialiser construction.
   The DDR-006 LangGraph state channel is the live source for the
   reasoning loop; this SQLite mirror exists for crash-recovery
   durability (per IMPLEMENTATION-GUIDE.md §2 storage diagram, the
   ``async_tasks`` table is the "advisory state channel" companion to
   the authoritative ``stage_log``).

4. *Upsert on ``task_id``* — re-dispatch of the same ``task_id``
   overwrites the row rather than failing. The ``dispatch_autobuild_async``
   contract is itself upsert-shaped (record stage_log twice on the
   happy path); the initialiser preserves the same posture so a retry
   that re-mints the same ``task_id`` does not crash mid-dispatch.

References:
    - TASK-FW10-005 — this task.
    - DDR-006 — ``AutobuildState`` Pydantic model + lifecycle literals.
    - TASK-FW10-001 — boot sequence that constructs the shared pool.
    - TASK-FW10-007 — composes this factory into ``PipelineConsumerDeps``.
    - :mod:`forge.lifecycle.persistence` — sibling SQLite writer.
    - :mod:`forge.pipeline.dispatchers.autobuild_async` — Protocol surface
      and the dispatcher that calls :meth:`initialise_autobuild_state`.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from forge.lifecycle.persistence import SqliteLifecyclePersistence
from forge.pipeline.dispatchers.autobuild_async import (
    AUTOBUILD_STARTING_LIFECYCLE,
    AutobuildStateInitialiser,
)

__all__ = [
    "ASYNC_TASKS_SCHEMA_DDL",
    "AutobuildStateRow",
    "build_autobuild_state_initialiser",
    "ensure_async_tasks_schema",
    "read_autobuild_state",
]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema (additive, idempotent)
# ---------------------------------------------------------------------------

#: DDL for the ``async_tasks`` SQLite mirror. Mirrors the DDR-006
#: ``AutobuildState`` Pydantic model's load-bearing fields. The full
#: model carries more fields (Coach scores, ``waiting_for``,
#: ``pending_directives``) which the subagent writes on later
#: transitions; the dispatcher only needs the identity columns +
#: ``lifecycle`` + the wave/task indices to seed the row.
#:
#: ``CREATE TABLE IF NOT EXISTS`` is idempotent — every initialiser
#: construction runs it so a fresh database boots into the correct
#: schema without an explicit migration step.
ASYNC_TASKS_SCHEMA_DDL: Final[str] = """
CREATE TABLE IF NOT EXISTS async_tasks (
    task_id TEXT PRIMARY KEY,
    build_id TEXT NOT NULL,
    feature_id TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    lifecycle TEXT NOT NULL,
    wave_index INTEGER NOT NULL,
    task_index INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    last_activity_at TEXT NOT NULL
) STRICT
""".strip()


# ---------------------------------------------------------------------------
# Read-side projection (used by the round-trip test)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AutobuildStateRow:
    """Read-side projection of one ``async_tasks`` row.

    Frozen dataclass so callers can compare rows by value across the
    write/read boundary in tests. Mirrors the columns written by
    :class:`_SqliteAutobuildStateInitialiser` one-for-one.

    Attributes:
        task_id: Identifier minted by ``start_async_task``. Primary key.
        build_id: Build the autobuild belongs to.
        feature_id: Feature the autobuild belongs to.
        correlation_id: Originating correlation ID, threaded onto the
            ``stage_log`` row and the launched task's context payload.
        lifecycle: DDR-006 lifecycle literal. The dispatcher always
            writes :data:`AUTOBUILD_STARTING_LIFECYCLE`.
        wave_index: Initial wave index (always ``0`` on dispatch).
        task_index: Initial task index (always ``0`` on dispatch).
        started_at: UTC timestamp the row was first written.
        last_activity_at: UTC timestamp of the most recent write
            (initialiser writes both columns to the same value).
    """

    task_id: str
    build_id: str
    feature_id: str
    correlation_id: str
    lifecycle: str
    wave_index: int
    task_index: int
    started_at: datetime
    last_activity_at: datetime


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------


def ensure_async_tasks_schema(connection: sqlite3.Connection) -> None:
    """Create the ``async_tasks`` table if it does not already exist.

    Idempotent — the underlying DDL uses ``CREATE TABLE IF NOT EXISTS``
    so repeated calls are a no-op. Exposed at module scope so the
    test-side reader can guarantee the table exists before issuing a
    ``SELECT`` (otherwise a fresh in-memory database would raise
    ``OperationalError: no such table``).

    Args:
        connection: A SQLite connection. The DDL is applied via
            ``connection.execute`` directly, relying on the autocommit
            isolation level used by
            :func:`forge.adapters.sqlite.connect.connect_writer`.

    Raises:
        sqlite3.Error: If the DDL cannot be applied (e.g. read-only
            connection). The error is left to propagate so the caller
            sees the underlying SQLite diagnostic.
    """
    connection.execute(ASYNC_TASKS_SCHEMA_DDL)


# ---------------------------------------------------------------------------
# Production initialiser (Protocol implementation)
# ---------------------------------------------------------------------------


class _SqliteAutobuildStateInitialiser:
    """Production :class:`AutobuildStateInitialiser` backed by SQLite.

    Wraps the shared :class:`SqliteLifecyclePersistence` writer connection
    and exposes the single-method Protocol surface
    :meth:`initialise_autobuild_state` the dispatcher calls.

    The initialiser refuses any non-``"starting"`` lifecycle write so a
    misconfigured caller cannot smuggle a transition through the
    initial-state seam — DDR-006 reserves transitions for
    ``autobuild_runner``. This is intentionally stricter than the
    Protocol signature suggests; the dispatcher always passes
    :data:`AUTOBUILD_STARTING_LIFECYCLE` so the strictness has no false
    positives in production.
    """

    def __init__(self, persistence: SqliteLifecyclePersistence) -> None:
        if not isinstance(persistence, SqliteLifecyclePersistence):
            raise TypeError(
                "build_autobuild_state_initialiser: sqlite_pool must be a "
                "SqliteLifecyclePersistence; got "
                f"{type(persistence).__name__}"
            )
        self._persistence = persistence
        # Idempotent — the DDL ships ``IF NOT EXISTS``. Production calls
        # this once per boot; tests that re-instantiate the factory
        # against the same in-memory pool benefit from the second call
        # being a no-op.
        ensure_async_tasks_schema(self._persistence.connection)

    def initialise_autobuild_state(
        self,
        build_id: str,
        feature_id: str,
        task_id: str,
        correlation_id: str,
        lifecycle: str,
        wave_index: int,
        task_index: int,
    ) -> None:
        """Write the initial ``AutobuildState`` row for the launched task.

        Implements the
        :class:`forge.pipeline.dispatchers.autobuild_async.AutobuildStateInitialiser`
        Protocol verbatim. All identifier arguments are validated up
        front so a malformed dispatch cannot persist a row keyed on
        ``""`` (which would alias every subsequent dispatch on the
        primary key).

        The whole INSERT runs inside a ``BEGIN IMMEDIATE`` block to
        match the persistence layer's concurrency posture (see
        :class:`SqliteLifecyclePersistence` doc-comment): we hold the
        writer lock for exactly the duration of the INSERT, so a
        concurrent CLI read against a read-only connection sees either
        the pre- or post-write state, never a torn row.

        Args:
            build_id: Build the autobuild belongs to. Non-empty.
            feature_id: Feature the autobuild belongs to. Non-empty.
            task_id: Identifier returned by ``start_async_task``.
                Non-empty (the dispatcher already validates this; the
                second guard here is defence-in-depth).
            correlation_id: Originating correlation ID. Non-empty.
            lifecycle: Lifecycle string. Must equal
                :data:`AUTOBUILD_STARTING_LIFECYCLE` — DDR-006 reserves
                transitions for ``autobuild_runner``.
            wave_index: Initial wave index (always ``0`` on dispatch).
            task_index: Initial task index (always ``0`` on dispatch).

        Raises:
            ValueError: If any identifier argument is empty or
                ``lifecycle`` is not :data:`AUTOBUILD_STARTING_LIFECYCLE`.
            sqlite3.Error: If the underlying INSERT cannot complete.
                The transaction is rolled back so the row is not
                partially written.
        """
        if not build_id:
            raise ValueError("initialise_autobuild_state: build_id must be non-empty")
        if not feature_id:
            raise ValueError("initialise_autobuild_state: feature_id must be non-empty")
        if not task_id:
            raise ValueError("initialise_autobuild_state: task_id must be non-empty")
        if not correlation_id:
            raise ValueError(
                "initialise_autobuild_state: correlation_id must be non-empty"
            )
        if lifecycle != AUTOBUILD_STARTING_LIFECYCLE:
            # DDR-006 + IMPLEMENTATION-GUIDE.md §4: the dispatcher's
            # contribution is the ``"starting"`` write only. Any other
            # lifecycle value here would be a contract violation by
            # the caller — refuse rather than persist.
            raise ValueError(
                "initialise_autobuild_state: lifecycle must be "
                f"{AUTOBUILD_STARTING_LIFECYCLE!r} (the dispatcher only "
                "writes the initial entry; transitions are owned by "
                f"autobuild_runner). Got {lifecycle!r}."
            )

        cx = self._persistence.connection
        now_iso = datetime.now(UTC).isoformat()

        try:
            cx.execute("BEGIN IMMEDIATE;")
            cx.execute(
                """
                INSERT INTO async_tasks (
                    task_id, build_id, feature_id, correlation_id,
                    lifecycle, wave_index, task_index,
                    started_at, last_activity_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    build_id = excluded.build_id,
                    feature_id = excluded.feature_id,
                    correlation_id = excluded.correlation_id,
                    lifecycle = excluded.lifecycle,
                    wave_index = excluded.wave_index,
                    task_index = excluded.task_index,
                    last_activity_at = excluded.last_activity_at
                """,
                (
                    task_id,
                    build_id,
                    feature_id,
                    correlation_id,
                    lifecycle,
                    int(wave_index),
                    int(task_index),
                    now_iso,
                    now_iso,
                ),
            )
            cx.execute("COMMIT;")
        except sqlite3.Error:
            # Roll back so the row is not partially visible. We keep
            # the original SQLite exception in the chain — callers can
            # introspect ``__cause__`` to see the underlying diagnostic.
            try:
                cx.execute("ROLLBACK;")
            except sqlite3.Error:  # pragma: no cover - rollback failure is rare
                pass
            raise

        logger.debug(
            "_SqliteAutobuildStateInitialiser: wrote async_tasks row "
            "task_id=%s build_id=%s feature_id=%s lifecycle=%s "
            "wave_index=%d task_index=%d",
            task_id,
            build_id,
            feature_id,
            lifecycle,
            int(wave_index),
            int(task_index),
        )


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------


def build_autobuild_state_initialiser(
    sqlite_pool: SqliteLifecyclePersistence,
) -> AutobuildStateInitialiser:
    """Construct the production ``AutobuildStateInitialiser``.

    Composes the
    :class:`forge.pipeline.dispatchers.autobuild_async.AutobuildStateInitialiser`
    Protocol implementation that
    ``forge.cli._serve_deps.build_pipeline_consumer_deps`` (TASK-FW10-007)
    threads into the dispatch closure.

    The factory keeps the wiring narrow on purpose — the only
    collaborator is the shared SQLite pool. Anything richer (clock
    injection for ``started_at``, custom lifecycle literals, etc.) is
    deliberately out of scope: DDR-006 owns the schema and the
    dispatcher always writes ``"starting"``.

    Args:
        sqlite_pool: The shared
            :class:`forge.lifecycle.persistence.SqliteLifecyclePersistence`
            facade owned by ``forge serve``. Must already have its
            schema initialised by ``forge.lifecycle.migrations.apply_at_boot``;
            this factory only adds the ``async_tasks`` table on top.

    Returns:
        An :class:`AutobuildStateInitialiser` Protocol implementation
        ready to be passed as the ``state_channel`` keyword argument to
        :func:`forge.pipeline.dispatchers.autobuild_async.dispatch_autobuild_async`.

    Raises:
        TypeError: If ``sqlite_pool`` is not a
            :class:`SqliteLifecyclePersistence`. We refuse duck-typed
            inputs at the boundary so a misuse surfaces here rather
            than as a confusing AttributeError on the first dispatch.
    """
    initialiser = _SqliteAutobuildStateInitialiser(sqlite_pool)
    logger.info(
        "build_autobuild_state_initialiser: composed SQLite-backed "
        "AutobuildStateInitialiser against pool db_path=%s",
        sqlite_pool.db_path,
    )
    return initialiser


# ---------------------------------------------------------------------------
# Read helper (test-side observation)
# ---------------------------------------------------------------------------


def read_autobuild_state(
    sqlite_pool: SqliteLifecyclePersistence,
    *,
    task_id: str,
) -> AutobuildStateRow | None:
    """Return the current ``async_tasks`` row for ``task_id``.

    Used by the round-trip test to assert that the initialiser's write
    is observable by a reader on the same pool. Production callers
    that need the live state read it through the LangGraph
    ``check_async_task`` middleware tool (per DDR-006); this helper is
    the SQLite-mirror read path that operates without a LangGraph
    runtime.

    The helper opens a fresh read connection via
    :meth:`SqliteLifecyclePersistence._reader` so the read does not
    contend with the writer's lock (per ADR-ARCH-013). For in-memory
    test databases the reader transparently falls back to the writer
    connection because in-memory SQLite is per-connection.

    Args:
        sqlite_pool: The shared persistence facade. Must be the same
            pool the initialiser was built against — reads on a
            different pool would observe an unrelated database.
        task_id: The task identifier to look up. Non-empty.

    Returns:
        The :class:`AutobuildStateRow` if the row exists, else
        ``None``. ``None`` is the legitimate response for a
        ``task_id`` that has not yet been initialised — callers should
        treat it as "not yet dispatched".

    Raises:
        ValueError: If ``task_id`` is empty.
    """
    if not task_id:
        raise ValueError("read_autobuild_state: task_id must be non-empty")

    # Defensive — make sure the table exists before we SELECT against
    # it. The initialiser already provisions the schema, but the test
    # may call this helper before any write (to assert ``None`` return)
    # and we want that to behave deterministically rather than raising
    # ``OperationalError: no such table``.
    ensure_async_tasks_schema(sqlite_pool.connection)

    with sqlite_pool._reader() as cx:
        cx.row_factory = sqlite3.Row
        row = cx.execute(
            """
            SELECT task_id, build_id, feature_id, correlation_id,
                   lifecycle, wave_index, task_index,
                   started_at, last_activity_at
              FROM async_tasks
             WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()

    if row is None:
        return None

    return AutobuildStateRow(
        task_id=row["task_id"],
        build_id=row["build_id"],
        feature_id=row["feature_id"],
        correlation_id=row["correlation_id"],
        lifecycle=row["lifecycle"],
        wave_index=int(row["wave_index"]),
        task_index=int(row["task_index"]),
        started_at=datetime.fromisoformat(row["started_at"]),
        last_activity_at=datetime.fromisoformat(row["last_activity_at"]),
    )
