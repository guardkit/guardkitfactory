"""Tests for ``forge.lifecycle.queue`` (TASK-PSM-006).

Acceptance-criteria coverage map:

* AC-001: ``next_build_to_pick(project)`` returns ``None`` if any build
  for the project is in {PREPARING, RUNNING, PAUSED, FINALISING} —
  :class:`TestNextBuildBlockedByActiveBuild`.
* AC-002: ``next_build_to_pick(project)`` returns the oldest-by-
  ``queued_at`` QUEUED build when nothing else is in flight —
  :class:`TestNextBuildReturnsOldestQueued`.
* AC-003: Picker query uses ``BEGIN IMMEDIATE`` —
  :class:`TestPickerUsesBeginImmediate`.
* AC-004: ``is_project_busy(project=None)`` handles fleet-wide NULL
  scope via ``IS NULL`` — :class:`TestIsProjectBusyNullScope`.
* AC-005: PREPARING + QUEUED for project X → None —
  :meth:`TestNextBuildBlockedByActiveBuild.test_preparing_blocks_pick`.
* AC-006: COMPLETE + QUEUED for project X → returns the QUEUED build —
  :meth:`TestNextBuildReturnsOldestQueued.test_terminal_does_not_block`.
* AC-007: RUNNING for X + QUEUED for Y → returns Y —
  :meth:`TestNextBuildReturnsOldestQueued.test_other_project_does_not_block`.
* AC-008: two QUEUED for X with different ``queued_at`` → returns the
  older one —
  :meth:`TestNextBuildReturnsOldestQueued.test_returns_oldest_when_two_queued`.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from forge.adapters.sqlite import connect as sqlite_connect
from forge.lifecycle import migrations
from forge.lifecycle.persistence import SqliteLifecyclePersistence
from forge.lifecycle.queue import (
    BLOCKING_STATES,
    SqliteSequentialQueuePicker,
    is_project_busy,
    next_build_to_pick,
)
from forge.lifecycle.state_machine import BuildState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def writer_db(tmp_path: Path) -> sqlite3.Connection:
    """Return a writer connection against a freshly-migrated db file."""
    db_path = tmp_path / "forge.db"
    cx = sqlite_connect.connect_writer(db_path)
    migrations.apply_at_boot(cx)
    yield cx
    cx.close()


@pytest.fixture()
def persistence(writer_db: sqlite3.Connection) -> SqliteLifecyclePersistence:
    """Return a persistence facade bound to the migrated writer connection."""
    return SqliteLifecyclePersistence(connection=writer_db)


@pytest.fixture()
def picker(
    persistence: SqliteLifecyclePersistence,
) -> SqliteSequentialQueuePicker:
    """Return a queue picker bound to the persistence facade."""
    return SqliteSequentialQueuePicker(persistence)


def _seed_build(
    cx: sqlite3.Connection,
    *,
    build_id: str,
    feature_id: str,
    project: str | None,
    status: BuildState,
    queued_at: datetime,
    correlation_id: str | None = None,
) -> None:
    """Insert a builds row directly with arbitrary status / project.

    We bypass :meth:`SqliteLifecyclePersistence.record_pending_build`
    because that helper hard-codes ``status='QUEUED'`` and never sets
    ``project``. Tests need full control of both fields.
    """
    if correlation_id is None:
        correlation_id = f"corr-{build_id}"
    cx.execute(
        """
        INSERT INTO builds (
            build_id, feature_id, repo, branch, feature_yaml_path,
            project, status, triggered_by, correlation_id, queued_at,
            max_turns, sdk_timeout_seconds
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'cli', ?, ?, 5, 1800)
        """,
        (
            build_id,
            feature_id,
            "guardkit/forge",
            "main",
            f"features/{feature_id}/{feature_id}.yaml",
            project,
            status.value,
            correlation_id,
            queued_at.isoformat(),
        ),
    )


# Base instant — every seeded queued_at is anchored off this so tests
# describe relative ordering without cluttering arrange blocks.
BASE = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# AC-005: PREPARING/RUNNING/PAUSED/FINALISING block pick
# ---------------------------------------------------------------------------


class TestNextBuildBlockedByActiveBuild:
    """If any blocking-state build exists for the project, picker returns None."""

    @pytest.mark.parametrize(
        "blocking_state",
        [
            BuildState.PREPARING,
            BuildState.RUNNING,
            BuildState.PAUSED,
            BuildState.FINALISING,
        ],
    )
    def test_preparing_blocks_pick(
        self,
        writer_db: sqlite3.Connection,
        picker: SqliteSequentialQueuePicker,
        blocking_state: BuildState,
    ) -> None:
        # Arrange: seed one blocking-state build + one QUEUED for project X.
        _seed_build(
            writer_db,
            build_id="build-blocking",
            feature_id="FEAT-X-001",
            project="X",
            status=blocking_state,
            queued_at=BASE,
        )
        _seed_build(
            writer_db,
            build_id="build-queued",
            feature_id="FEAT-X-002",
            project="X",
            status=BuildState.QUEUED,
            queued_at=BASE + timedelta(seconds=5),
        )

        # Act
        result = picker.next_build_to_pick("X")

        # Assert
        assert result is None
        assert picker.is_project_busy("X") is True

    def test_blocking_states_constant_matches_expected_set(self) -> None:
        # Defensive: if someone broadens BLOCKING_STATES later, the
        # behaviour above is the source of truth — this assertion locks
        # the membership.
        assert BLOCKING_STATES == frozenset(
            {
                BuildState.PREPARING,
                BuildState.RUNNING,
                BuildState.PAUSED,
                BuildState.FINALISING,
            }
        )


# ---------------------------------------------------------------------------
# AC-006 / AC-007 / AC-008: oldest QUEUED is returned, terminal/other-project ignored
# ---------------------------------------------------------------------------


class TestNextBuildReturnsOldestQueued:
    """Picker returns the oldest QUEUED build when nothing else blocks."""

    def test_terminal_does_not_block(
        self,
        writer_db: sqlite3.Connection,
        picker: SqliteSequentialQueuePicker,
    ) -> None:
        # Arrange: COMPLETE + QUEUED for project X.
        _seed_build(
            writer_db,
            build_id="build-complete",
            feature_id="FEAT-X-001",
            project="X",
            status=BuildState.COMPLETE,
            queued_at=BASE,
        )
        _seed_build(
            writer_db,
            build_id="build-queued",
            feature_id="FEAT-X-002",
            project="X",
            status=BuildState.QUEUED,
            queued_at=BASE + timedelta(seconds=5),
        )

        # Act
        result = picker.next_build_to_pick("X")

        # Assert
        assert result is not None
        assert result.build_id == "build-queued"
        assert result.status is BuildState.QUEUED

    def test_other_project_does_not_block(
        self,
        writer_db: sqlite3.Connection,
        picker: SqliteSequentialQueuePicker,
    ) -> None:
        # Arrange: RUNNING for project X + QUEUED for project Y.
        _seed_build(
            writer_db,
            build_id="build-running-x",
            feature_id="FEAT-X-001",
            project="X",
            status=BuildState.RUNNING,
            queued_at=BASE,
        )
        _seed_build(
            writer_db,
            build_id="build-queued-y",
            feature_id="FEAT-Y-001",
            project="Y",
            status=BuildState.QUEUED,
            queued_at=BASE + timedelta(seconds=10),
        )

        # Act
        result_y = picker.next_build_to_pick("Y")
        result_x = picker.next_build_to_pick("X")

        # Assert
        assert result_y is not None
        assert result_y.build_id == "build-queued-y"
        # Project X is still busy because the RUNNING build dominates.
        assert result_x is None
        assert picker.is_project_busy("X") is True
        assert picker.is_project_busy("Y") is False

    def test_returns_oldest_when_two_queued(
        self,
        writer_db: sqlite3.Connection,
        picker: SqliteSequentialQueuePicker,
    ) -> None:
        # Arrange: two QUEUED for project X with different queued_at.
        older_at = BASE
        newer_at = BASE + timedelta(seconds=30)
        _seed_build(
            writer_db,
            build_id="build-older",
            feature_id="FEAT-X-001",
            project="X",
            status=BuildState.QUEUED,
            queued_at=older_at,
        )
        _seed_build(
            writer_db,
            build_id="build-newer",
            feature_id="FEAT-X-002",
            project="X",
            status=BuildState.QUEUED,
            queued_at=newer_at,
        )

        # Act
        result = picker.next_build_to_pick("X")

        # Assert
        assert result is not None
        assert result.build_id == "build-older"
        assert result.queued_at == older_at

    def test_no_queued_returns_none(
        self,
        picker: SqliteSequentialQueuePicker,
    ) -> None:
        # Empty database: nothing to pick.
        assert picker.next_build_to_pick("X") is None
        assert picker.is_project_busy("X") is False


# ---------------------------------------------------------------------------
# AC-003: BEGIN IMMEDIATE used by picker query
# ---------------------------------------------------------------------------


class TestPickerUsesBeginImmediate:
    """The picker query must run inside a ``BEGIN IMMEDIATE`` transaction."""

    def test_source_contains_begin_immediate(self) -> None:
        # Static-analysis check on the module source — verifiable in
        # source per the Coach validation hint.
        from forge.lifecycle import queue as queue_module

        source = Path(queue_module.__file__).read_text(encoding="utf-8")
        assert re.search(r"BEGIN\s+IMMEDIATE", source, re.IGNORECASE), (
            "queue.py must use BEGIN IMMEDIATE for the picker query "
            "(TASK-PSM-006 AC-003 / Group F)"
        )

    def test_begin_immediate_executed_at_runtime(
        self,
        writer_db: sqlite3.Connection,
        picker: SqliteSequentialQueuePicker,
    ) -> None:
        # Arrange: seed a QUEUED build, then instrument the connection
        # via ``set_trace_callback`` to capture every statement the
        # picker issues. This is the documented sqlite3 hook and works
        # around the read-only ``Connection.execute`` attribute.
        _seed_build(
            writer_db,
            build_id="build-q",
            feature_id="FEAT-X-001",
            project="X",
            status=BuildState.QUEUED,
            queued_at=BASE,
        )

        observed: list[str] = []
        writer_db.set_trace_callback(observed.append)
        try:
            # Act
            picker.next_build_to_pick("X")
        finally:
            writer_db.set_trace_callback(None)

        # Assert: at least one statement contains BEGIN IMMEDIATE.
        assert any(
            re.search(r"BEGIN\s+IMMEDIATE", s, re.IGNORECASE) for s in observed
        ), f"expected BEGIN IMMEDIATE in executed SQL; got {observed!r}"
        # And a matching COMMIT was issued so the connection is left
        # in autocommit state.
        assert any(
            s.strip().upper().startswith("COMMIT") for s in observed
        ), f"expected COMMIT after picker; got {observed!r}"


# ---------------------------------------------------------------------------
# AC-004: fleet-wide NULL scope handled correctly
# ---------------------------------------------------------------------------


class TestIsProjectBusyNullScope:
    """``project=None`` compares against NULL via IS NULL, not = NULL."""

    def test_null_scope_busy_when_null_project_running(
        self,
        writer_db: sqlite3.Connection,
        picker: SqliteSequentialQueuePicker,
    ) -> None:
        # Arrange: a RUNNING build with NULL project.
        _seed_build(
            writer_db,
            build_id="build-null-running",
            feature_id="FEAT-NULL-001",
            project=None,
            status=BuildState.RUNNING,
            queued_at=BASE,
        )

        # Act + Assert
        assert picker.is_project_busy(None) is True
        # Named projects are unaffected.
        assert picker.is_project_busy("X") is False

    def test_null_scope_not_busy_when_only_named_projects_running(
        self,
        writer_db: sqlite3.Connection,
        picker: SqliteSequentialQueuePicker,
    ) -> None:
        # Arrange: RUNNING build for project "X". The NULL scope is
        # **not** the same scope as "X" — IS NULL must not match "X".
        _seed_build(
            writer_db,
            build_id="build-x-running",
            feature_id="FEAT-X-001",
            project="X",
            status=BuildState.RUNNING,
            queued_at=BASE,
        )

        # Act + Assert
        assert picker.is_project_busy(None) is False
        assert picker.is_project_busy("X") is True

    def test_null_scope_picks_only_null_queued(
        self,
        writer_db: sqlite3.Connection,
        picker: SqliteSequentialQueuePicker,
    ) -> None:
        # Arrange: QUEUED for project "X" + QUEUED with NULL project.
        # Picking the NULL scope must return only the NULL row.
        _seed_build(
            writer_db,
            build_id="build-x-queued",
            feature_id="FEAT-X-001",
            project="X",
            status=BuildState.QUEUED,
            queued_at=BASE,
        )
        _seed_build(
            writer_db,
            build_id="build-null-queued",
            feature_id="FEAT-NULL-001",
            project=None,
            status=BuildState.QUEUED,
            queued_at=BASE + timedelta(seconds=5),
        )

        # Act
        result = picker.next_build_to_pick(None)

        # Assert
        assert result is not None
        assert result.build_id == "build-null-queued"
        assert result.project is None

    def test_query_uses_is_null_predicate_in_source(self) -> None:
        # Static-analysis: the module must contain ``IS NULL`` for the
        # NULL-scope branches.
        from forge.lifecycle import queue as queue_module

        source = Path(queue_module.__file__).read_text(encoding="utf-8")
        assert re.search(r"\bIS NULL\b", source), (
            "queue.py must use ``IS NULL`` for fleet-wide scope "
            "(TASK-PSM-006 AC-004)"
        )
        # Defensive: we should NOT accidentally compare against NULL
        # using ``= NULL`` (always evaluates to NULL in SQLite).
        assert not re.search(r"=\s*NULL\b", source, re.IGNORECASE), (
            "queue.py must not use ``= NULL`` — SQLite NULL semantics "
            "require ``IS NULL``"
        )


# ---------------------------------------------------------------------------
# Module-level convenience wrappers
# ---------------------------------------------------------------------------


class TestModuleLevelWrappers:
    """``next_build_to_pick`` and ``is_project_busy`` work at module scope."""

    def test_next_build_to_pick_module_function(
        self,
        writer_db: sqlite3.Connection,
        persistence: SqliteLifecyclePersistence,
    ) -> None:
        _seed_build(
            writer_db,
            build_id="build-q",
            feature_id="FEAT-X-001",
            project="X",
            status=BuildState.QUEUED,
            queued_at=BASE,
        )
        result = next_build_to_pick(persistence, "X")
        assert result is not None
        assert result.build_id == "build-q"

    def test_is_project_busy_module_function(
        self,
        writer_db: sqlite3.Connection,
        persistence: SqliteLifecyclePersistence,
    ) -> None:
        _seed_build(
            writer_db,
            build_id="build-running",
            feature_id="FEAT-X-001",
            project="X",
            status=BuildState.RUNNING,
            queued_at=BASE,
        )
        assert is_project_busy(persistence, "X") is True
        assert is_project_busy(persistence, None) is False
