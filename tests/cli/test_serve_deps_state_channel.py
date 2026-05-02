"""Tests for ``forge.cli._serve_deps_state_channel`` (TASK-FW10-005).

Acceptance-criteria coverage map:

* AC-001: ``build_autobuild_state_initialiser(sqlite_pool)`` returns a
  Protocol-conforming object whose ``initialise_autobuild_state(...)``
  writes ``lifecycle="starting"`` per DDR-006 —
  :class:`TestFactoryReturnsProtocolImplementation` and
  :class:`TestInitialiseWritesStartingLifecycle`.
* AC-002: A read after initialise returns the row with
  ``lifecycle="starting"`` —
  :class:`TestRoundTripWriteThenRead`.
* AC-003: No transition writes happen inside the initialiser — only
  the initial-state write —
  :class:`TestNoTransitionWritesInsideInitialiser`.
* AC-004 (lint/format): handled by project ruff/format config; not a
  runtime test.

Tests run against an on-disk SQLite database created in ``tmp_path`` so
the round-trip read uses a real ``read_only_connect`` handle (per
ADR-ARCH-013) — the in-memory fallback path inside
``SqliteLifecyclePersistence._reader`` is exercised by a sibling test
that constructs the persistence facade against an in-memory connection.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator

import pytest

from forge.adapters.sqlite import connect as sqlite_connect
from forge.cli._serve_deps_state_channel import (
    ASYNC_TASKS_SCHEMA_DDL,
    AutobuildStateRow,
    build_autobuild_state_initialiser,
    ensure_async_tasks_schema,
    read_autobuild_state,
)
from forge.lifecycle import migrations
from forge.lifecycle.persistence import SqliteLifecyclePersistence
from forge.pipeline.dispatchers.autobuild_async import (
    AUTOBUILD_STARTING_LIFECYCLE,
    AutobuildStateInitialiser,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def writer_db(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """Return a writer connection against a freshly-migrated db file.

    Mirrors the fixture in ``tests/cli/test_serve_deps_stage_log.py`` so
    the round-trip test exercises the same boot path as production —
    on-disk file, full migration ledger applied, autocommit isolation
    via :func:`forge.adapters.sqlite.connect.connect_writer`.
    """
    db_path = tmp_path / "forge.db"
    cx = sqlite_connect.connect_writer(db_path)
    migrations.apply_at_boot(cx)
    yield cx
    cx.close()


@pytest.fixture()
def persistence(
    writer_db: sqlite3.Connection,
) -> SqliteLifecyclePersistence:
    """Return the persistence facade bound to the migrated writer connection."""
    return SqliteLifecyclePersistence(connection=writer_db)


@pytest.fixture()
def seeded_build_id(persistence: SqliteLifecyclePersistence) -> str:
    """Insert a minimal ``builds`` row so the initialiser has a parent.

    Although the ``async_tasks`` table currently does not declare a FK
    onto ``builds.build_id``, seeding the parent row keeps the
    round-trip test honest: a production dispatch always has a builds
    row in flight by the time the dispatcher reaches the
    state-channel write.
    """
    payload = SimpleNamespace(
        feature_id="FEAT-FW10-005",
        repo="guardkit/forge",
        branch="main",
        feature_yaml_path="features/test/test.yaml",
        max_turns=5,
        sdk_timeout_seconds=1800,
        triggered_by="cli",
        originating_adapter=None,
        originating_user="test-user",
        correlation_id="corr-FW10-005",
        parent_request_id=None,
        queued_at=datetime(2026, 5, 2, 12, 0, 0, tzinfo=UTC),
    )
    return persistence.record_pending_build(payload)


# ---------------------------------------------------------------------------
# AC-001: factory returns a Protocol-conforming object
# ---------------------------------------------------------------------------


class TestFactoryReturnsProtocolImplementation:
    """``build_autobuild_state_initialiser`` returns the Protocol shape."""

    def test_factory_returns_object_with_initialise_method(
        self,
        persistence: SqliteLifecyclePersistence,
    ) -> None:
        initialiser = build_autobuild_state_initialiser(persistence)
        assert hasattr(initialiser, "initialise_autobuild_state")
        assert callable(initialiser.initialise_autobuild_state)

    def test_factory_returns_runtime_checkable_protocol_implementation(
        self,
        persistence: SqliteLifecyclePersistence,
    ) -> None:
        """``AutobuildStateInitialiser`` is decorated ``@runtime_checkable``.

        An ``isinstance`` check is the structural conformance gate the
        dispatcher relies on at runtime. The factory's return value
        must satisfy it without any adapter shim.
        """
        initialiser = build_autobuild_state_initialiser(persistence)
        assert isinstance(initialiser, AutobuildStateInitialiser)

    def test_factory_rejects_non_persistence_pool(self) -> None:
        class NotAPersistence:
            pass

        with pytest.raises(TypeError, match="SqliteLifecyclePersistence"):
            build_autobuild_state_initialiser(NotAPersistence())  # type: ignore[arg-type]

    def test_factory_provisions_async_tasks_table(
        self,
        persistence: SqliteLifecyclePersistence,
    ) -> None:
        """Constructing the initialiser must create the table.

        DDR-006's mirror table is not in ``schema.sql`` (it's
        provisioned by this module). The factory's contract is that a
        fresh database boots into the right shape without an explicit
        migration step.
        """
        # The factory's ``__init__`` should idempotently provision the
        # schema. We confirm by asking sqlite_master directly.
        build_autobuild_state_initialiser(persistence)
        row = persistence.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='async_tasks'"
        ).fetchone()
        assert row is not None, (
            "factory must run CREATE TABLE IF NOT EXISTS for async_tasks"
        )


# ---------------------------------------------------------------------------
# AC-002 & AC-003: round-trip — write produces lifecycle="starting"
# ---------------------------------------------------------------------------


class TestInitialiseWritesStartingLifecycle:
    """The initial-state write carries ``lifecycle="starting"``."""

    def test_initialise_with_starting_lifecycle_does_not_raise(
        self,
        persistence: SqliteLifecyclePersistence,
        seeded_build_id: str,
    ) -> None:
        initialiser = build_autobuild_state_initialiser(persistence)
        initialiser.initialise_autobuild_state(
            build_id=seeded_build_id,
            feature_id="FEAT-FW10-005",
            task_id="autobuild-task-0001",
            correlation_id="corr-FW10-005",
            lifecycle=AUTOBUILD_STARTING_LIFECYCLE,
            wave_index=0,
            task_index=0,
        )

    def test_initialise_rejects_non_starting_lifecycle(
        self,
        persistence: SqliteLifecyclePersistence,
        seeded_build_id: str,
    ) -> None:
        """The dispatcher's contract is the ``"starting"`` write only.

        DDR-006 reserves transitions for ``autobuild_runner``. A caller
        passing ``"running_wave"`` (or any non-starting literal) is in
        contract violation; the initialiser must refuse rather than
        smuggle a transition through the initial-state seam.
        """
        initialiser = build_autobuild_state_initialiser(persistence)
        with pytest.raises(ValueError, match=AUTOBUILD_STARTING_LIFECYCLE):
            initialiser.initialise_autobuild_state(
                build_id=seeded_build_id,
                feature_id="FEAT-FW10-005",
                task_id="autobuild-task-0001",
                correlation_id="corr-FW10-005",
                lifecycle="running_wave",
                wave_index=0,
                task_index=0,
            )


class TestRoundTripWriteThenRead:
    """Write via the initialiser; read via the same persistence pool."""

    def test_initialise_then_read_observes_starting_row(
        self,
        persistence: SqliteLifecyclePersistence,
        seeded_build_id: str,
    ) -> None:
        """AC-002: read after initialise returns ``lifecycle="starting"``."""
        initialiser = build_autobuild_state_initialiser(persistence)
        initialiser.initialise_autobuild_state(
            build_id=seeded_build_id,
            feature_id="FEAT-FW10-005",
            task_id="autobuild-task-0001",
            correlation_id="corr-FW10-005",
            lifecycle=AUTOBUILD_STARTING_LIFECYCLE,
            wave_index=0,
            task_index=0,
        )

        row = read_autobuild_state(persistence, task_id="autobuild-task-0001")

        assert row is not None, (
            "the round-trip read must observe the recorded write on the "
            "same SQLite pool"
        )
        assert isinstance(row, AutobuildStateRow)
        assert row.task_id == "autobuild-task-0001"
        assert row.build_id == seeded_build_id
        assert row.feature_id == "FEAT-FW10-005"
        assert row.correlation_id == "corr-FW10-005"
        # The load-bearing assertion: the dispatcher's contribution is
        # ``"starting"`` and ``"starting"`` only (DDR-006 +
        # IMPLEMENTATION-GUIDE.md §4 contract).
        assert row.lifecycle == AUTOBUILD_STARTING_LIFECYCLE
        assert row.wave_index == 0
        assert row.task_index == 0

    def test_read_before_initialise_returns_none(
        self,
        persistence: SqliteLifecyclePersistence,
    ) -> None:
        """A read for an unknown ``task_id`` returns ``None``.

        This is the legitimate response for "not yet dispatched" and
        keeps the reader from raising ``OperationalError`` on a fresh
        database (the schema bootstrap inside ``read_autobuild_state``
        guarantees the table exists).
        """
        row = read_autobuild_state(persistence, task_id="autobuild-task-9999")
        assert row is None

    def test_read_uses_fresh_connection_on_disk_db(
        self,
        persistence: SqliteLifecyclePersistence,
        seeded_build_id: str,
        tmp_path: Path,
    ) -> None:
        """The read path opens a fresh ``read_only_connect`` for on-disk dbs.

        The persistence facade was built against an on-disk file (per
        ``writer_db`` fixture). A subsequent read must observe the
        write even though ``read_only_connect`` opens a new connection
        — WAL mode + the writer's COMMIT make the row visible to any
        ro reader on the same file.
        """
        initialiser = build_autobuild_state_initialiser(persistence)
        initialiser.initialise_autobuild_state(
            build_id=seeded_build_id,
            feature_id="FEAT-FW10-005",
            task_id="autobuild-task-0042",
            correlation_id="corr-FW10-005",
            lifecycle=AUTOBUILD_STARTING_LIFECYCLE,
            wave_index=0,
            task_index=0,
        )

        # Open an entirely independent ro connection — same file, fresh
        # process-side state — to assert the write is visible without
        # the persistence facade as an intermediary.
        ro = sqlite_connect.read_only_connect(persistence.db_path)
        try:
            ro.row_factory = sqlite3.Row
            row = ro.execute(
                "SELECT lifecycle FROM async_tasks WHERE task_id = ?",
                ("autobuild-task-0042",),
            ).fetchone()
        finally:
            ro.close()
        assert row is not None
        assert row["lifecycle"] == AUTOBUILD_STARTING_LIFECYCLE


# ---------------------------------------------------------------------------
# AC-003: no transition writes happen inside the initialiser
# ---------------------------------------------------------------------------


class TestNoTransitionWritesInsideInitialiser:
    """Subsequent reads continue to observe the initial value.

    DDR-006: the dispatcher writes ``lifecycle="starting"`` and exits.
    The subagent owns subsequent transitions (TASK-FW10-002). This
    class asserts the dispatcher's contribution stops at the first
    write — repeated reads after a single initialise see the same
    ``"starting"`` row, and no other lifecycle row appears for the
    same ``task_id``.
    """

    def test_only_one_row_per_task_id_after_single_initialise(
        self,
        persistence: SqliteLifecyclePersistence,
        seeded_build_id: str,
    ) -> None:
        initialiser = build_autobuild_state_initialiser(persistence)
        initialiser.initialise_autobuild_state(
            build_id=seeded_build_id,
            feature_id="FEAT-FW10-005",
            task_id="autobuild-task-0001",
            correlation_id="corr-FW10-005",
            lifecycle=AUTOBUILD_STARTING_LIFECYCLE,
            wave_index=0,
            task_index=0,
        )

        row_count = persistence.connection.execute(
            "SELECT COUNT(*) FROM async_tasks WHERE task_id = ?",
            ("autobuild-task-0001",),
        ).fetchone()[0]
        assert row_count == 1, (
            "initialiser must produce exactly one row; the subagent "
            "owns subsequent writes (DDR-006)"
        )

    def test_repeated_reads_continue_to_observe_starting(
        self,
        persistence: SqliteLifecyclePersistence,
        seeded_build_id: str,
    ) -> None:
        """Three sequential reads all see ``lifecycle="starting"``.

        This is the deferred-transition assertion from the task brief:
        subsequent reads observe the initial value until the subagent's
        first transition (which TASK-FW10-002 owns; not exercised
        here). Repeated reads exercise the read-side determinism
        without invoking any subagent.
        """
        initialiser = build_autobuild_state_initialiser(persistence)
        initialiser.initialise_autobuild_state(
            build_id=seeded_build_id,
            feature_id="FEAT-FW10-005",
            task_id="autobuild-task-0001",
            correlation_id="corr-FW10-005",
            lifecycle=AUTOBUILD_STARTING_LIFECYCLE,
            wave_index=0,
            task_index=0,
        )

        for _ in range(3):
            row = read_autobuild_state(persistence, task_id="autobuild-task-0001")
            assert row is not None
            assert row.lifecycle == AUTOBUILD_STARTING_LIFECYCLE

    def test_initialiser_object_exposes_only_protocol_method(
        self,
        persistence: SqliteLifecyclePersistence,
    ) -> None:
        """No ``transition`` / ``advance`` / ``update`` method exists.

        DDR-006 forbids the dispatcher from progressing the lifecycle.
        The initialiser's public surface must therefore be exactly the
        ``initialise_autobuild_state`` method — any extra hook is a
        contract leak.
        """
        initialiser = build_autobuild_state_initialiser(persistence)
        public_methods = {
            name
            for name in dir(initialiser)
            if not name.startswith("_") and callable(getattr(initialiser, name))
        }
        assert public_methods == {"initialise_autobuild_state"}, (
            "initialiser must expose only the Protocol method; subsequent "
            f"transitions are owned by autobuild_runner. Got {public_methods!r}"
        )


# ---------------------------------------------------------------------------
# Argument validation — fail-fast guards
# ---------------------------------------------------------------------------


class TestInitialiseValidation:
    """Fail-fast guards on the initialiser's keyword arguments."""

    @pytest.fixture()
    def initialiser(
        self,
        persistence: SqliteLifecyclePersistence,
    ) -> AutobuildStateInitialiser:
        return build_autobuild_state_initialiser(persistence)

    def test_empty_build_id_raises_value_error(
        self,
        initialiser: AutobuildStateInitialiser,
    ) -> None:
        with pytest.raises(ValueError, match="build_id"):
            initialiser.initialise_autobuild_state(
                build_id="",
                feature_id="FEAT-X",
                task_id="t-1",
                correlation_id="c-1",
                lifecycle=AUTOBUILD_STARTING_LIFECYCLE,
                wave_index=0,
                task_index=0,
            )

    def test_empty_feature_id_raises_value_error(
        self,
        initialiser: AutobuildStateInitialiser,
        seeded_build_id: str,
    ) -> None:
        with pytest.raises(ValueError, match="feature_id"):
            initialiser.initialise_autobuild_state(
                build_id=seeded_build_id,
                feature_id="",
                task_id="t-1",
                correlation_id="c-1",
                lifecycle=AUTOBUILD_STARTING_LIFECYCLE,
                wave_index=0,
                task_index=0,
            )

    def test_empty_task_id_raises_value_error(
        self,
        initialiser: AutobuildStateInitialiser,
        seeded_build_id: str,
    ) -> None:
        with pytest.raises(ValueError, match="task_id"):
            initialiser.initialise_autobuild_state(
                build_id=seeded_build_id,
                feature_id="FEAT-X",
                task_id="",
                correlation_id="c-1",
                lifecycle=AUTOBUILD_STARTING_LIFECYCLE,
                wave_index=0,
                task_index=0,
            )

    def test_empty_correlation_id_raises_value_error(
        self,
        initialiser: AutobuildStateInitialiser,
        seeded_build_id: str,
    ) -> None:
        with pytest.raises(ValueError, match="correlation_id"):
            initialiser.initialise_autobuild_state(
                build_id=seeded_build_id,
                feature_id="FEAT-X",
                task_id="t-1",
                correlation_id="",
                lifecycle=AUTOBUILD_STARTING_LIFECYCLE,
                wave_index=0,
                task_index=0,
            )


# ---------------------------------------------------------------------------
# Schema bootstrap helper
# ---------------------------------------------------------------------------


class TestEnsureAsyncTasksSchema:
    """``ensure_async_tasks_schema`` is idempotent."""

    def test_ddl_constant_creates_async_tasks_table(self) -> None:
        """Smoke: applying the DDL constant alone provisions the table."""
        cx = sqlite3.connect(":memory:")
        try:
            cx.execute(ASYNC_TASKS_SCHEMA_DDL)
            row = cx.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='async_tasks'"
            ).fetchone()
            assert row is not None
            assert row[0] == "async_tasks"
        finally:
            cx.close()

    def test_ensure_schema_is_idempotent(
        self, persistence: SqliteLifecyclePersistence
    ) -> None:
        """Repeated calls do not raise — ``IF NOT EXISTS`` covers the re-run."""
        ensure_async_tasks_schema(persistence.connection)
        ensure_async_tasks_schema(persistence.connection)
        ensure_async_tasks_schema(persistence.connection)


# ---------------------------------------------------------------------------
# Read helper validation
# ---------------------------------------------------------------------------


class TestReadAutobuildStateValidation:
    def test_empty_task_id_raises_value_error(
        self, persistence: SqliteLifecyclePersistence
    ) -> None:
        with pytest.raises(ValueError, match="task_id"):
            read_autobuild_state(persistence, task_id="")
