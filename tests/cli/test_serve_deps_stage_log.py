"""Tests for ``forge.cli._serve_deps_stage_log`` (TASK-FW10-004).

Acceptance-criteria coverage map:

* AC-001: ``build_stage_log_recorder(sqlite_pool)`` returns a
  ``StageLogRecorder`` Protocol implementation —
  :class:`TestFactoryReturnsProtocolImplementation`.
* AC-002: A round-trip test (write then read on the same pool) observes
  the recorded transition —
  :class:`TestRoundTripWriteThenRead`.
* AC-003 (lint/format): handled by project ruff/format config; not a
  runtime test.

Tests run against an in-memory SQLite database — no mocking of the
storage layer. The persistence facade is constructed with a real
writer connection produced by
:func:`forge.adapters.sqlite.connect.connect_writer` after migrations
have been applied via :func:`forge.lifecycle.migrations.apply_at_boot`,
so the read-after-write assertion exercises the full stage_log table
machinery.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from forge.adapters.sqlite import connect as sqlite_connect
from forge.cli._serve_deps_stage_log import (
    AUTOBUILD_LIFECYCLE_STATE_KEY,
    AUTOBUILD_LIFECYCLE_STATE_VALUE,
    AUTOBUILD_RUNNING_STATUS,
    AUTOBUILD_TARGET_KIND,
    build_stage_log_recorder,
)
from forge.lifecycle import migrations
from forge.lifecycle.persistence import (
    SqliteLifecyclePersistence,
    StageLogEntry,
)
from forge.pipeline.dispatchers.autobuild_async import StageLogRecorder
from forge.pipeline.stage_taxonomy import StageClass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def writer_db(tmp_path: Path) -> sqlite3.Connection:
    """Return a writer connection against a freshly-migrated db file.

    Mirrors the fixture in ``tests/forge/test_lifecycle_persistence.py``
    so the round-trip test exercises the same boot path as production.
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
    """Insert a minimal ``builds`` row so the FK from ``stage_log`` resolves.

    ``stage_log.build_id`` carries a foreign key onto ``builds.build_id``
    (DDR-003 / TASK-PSM-002). Inserting the parent row keeps the
    round-trip test honest: the same row a production dispatch would
    reference is present, so the write exercises the same code path.
    """
    from types import SimpleNamespace

    payload = SimpleNamespace(
        feature_id="FEAT-FW10-004",
        repo="guardkit/forge",
        branch="main",
        feature_yaml_path="features/test/test.yaml",
        max_turns=5,
        sdk_timeout_seconds=1800,
        # ``triggered_by`` is constrained by a CHECK constraint to the
        # canonical adapter set; ``cli`` is the conventional choice for
        # tests that don't care about provenance.
        triggered_by="cli",
        originating_adapter=None,
        originating_user="test-user",
        correlation_id="corr-FW10-004",
        parent_request_id=None,
        queued_at=datetime(2026, 5, 2, 12, 0, 0, tzinfo=UTC),
    )
    return persistence.record_pending_build(payload)


# ---------------------------------------------------------------------------
# AC-001: factory returns a Protocol implementation
# ---------------------------------------------------------------------------


class TestFactoryReturnsProtocolImplementation:
    """``build_stage_log_recorder`` returns a ``StageLogRecorder``."""

    def test_factory_returns_object_with_record_running_method(
        self,
        persistence: SqliteLifecyclePersistence,
    ) -> None:
        recorder = build_stage_log_recorder(persistence)
        assert hasattr(recorder, "record_running")
        assert callable(recorder.record_running)

    def test_factory_returns_runtime_checkable_protocol_implementation(
        self,
        persistence: SqliteLifecyclePersistence,
    ) -> None:
        recorder = build_stage_log_recorder(persistence)
        # ``StageLogRecorder`` is decorated with ``@runtime_checkable``
        # in :mod:`forge.pipeline.dispatchers.autobuild_async`, so an
        # ``isinstance`` check confirms the structural conformance the
        # dispatcher relies on at runtime.
        assert isinstance(recorder, StageLogRecorder)

    def test_factory_rejects_pool_without_record_stage(self) -> None:
        class NoRecordStage:
            pass

        with pytest.raises(TypeError, match="record_stage"):
            build_stage_log_recorder(NoRecordStage())


# ---------------------------------------------------------------------------
# AC-002: round-trip — write then read observes the recorded transition
# ---------------------------------------------------------------------------


class TestRoundTripWriteThenRead:
    """Write via the recorder; read via the same persistence facade."""

    def test_record_running_then_read_observes_row(
        self,
        persistence: SqliteLifecyclePersistence,
        seeded_build_id: str,
    ) -> None:
        recorder = build_stage_log_recorder(persistence)

        recorder.record_running(
            build_id=seeded_build_id,
            feature_id="FEAT-FW10-004",
            stage=StageClass.AUTOBUILD,
            details_json={
                "subagent": "autobuild_runner",
                "correlation_id": "corr-FW10-004",
                "task_id": None,
            },
        )

        entries = persistence.read_stages(seeded_build_id)
        assert len(entries) == 1, (
            "the round-trip read must observe the recorded write on the "
            "same SQLite pool"
        )
        entry = entries[0]
        assert entry.build_id == seeded_build_id
        assert entry.stage_label == StageClass.AUTOBUILD.value
        assert entry.target_kind == AUTOBUILD_TARGET_KIND
        assert entry.target_identifier == "FEAT-FW10-004"
        # The schema-valid ``status`` is "PASSED" (the dispatch action
        # passed); the actual ``state="running"`` marker lives on
        # ``details_json[AUTOBUILD_LIFECYCLE_STATE_KEY]``.
        assert entry.status == AUTOBUILD_RUNNING_STATUS
        assert (
            entry.details[AUTOBUILD_LIFECYCLE_STATE_KEY]
            == AUTOBUILD_LIFECYCLE_STATE_VALUE
        )
        # The recorder must echo feature_id into details so a reader
        # filtering on ``details_json`` can identify the feature
        # without a separate column.
        assert entry.details["feature_id"] == "FEAT-FW10-004"
        # Original details payload must round-trip verbatim.
        assert entry.details["correlation_id"] == "corr-FW10-004"
        assert entry.details["subagent"] == "autobuild_runner"
        assert entry.details["task_id"] is None
        assert isinstance(entry, StageLogEntry)

    def test_two_writes_produce_two_rows(
        self,
        persistence: SqliteLifecyclePersistence,
        seeded_build_id: str,
    ) -> None:
        """The dispatcher calls ``record_running`` twice on the happy path.

        Both writes must be observable on subsequent reads — see
        TASK-FW10-004 §Why ("durable evidence that a dispatch was
        attempted" + post-dispatch row with ``task_id`` threaded).
        """
        recorder = build_stage_log_recorder(persistence)

        recorder.record_running(
            build_id=seeded_build_id,
            feature_id="FEAT-FW10-004",
            stage=StageClass.AUTOBUILD,
            details_json={
                "subagent": "autobuild_runner",
                "correlation_id": "corr-FW10-004",
                "task_id": None,
            },
        )
        recorder.record_running(
            build_id=seeded_build_id,
            feature_id="FEAT-FW10-004",
            stage=StageClass.AUTOBUILD,
            details_json={
                "subagent": "autobuild_runner",
                "correlation_id": "corr-FW10-004",
                "task_id": "autobuild-task-001",
            },
        )

        entries = persistence.read_stages(seeded_build_id)
        assert len(entries) == 2
        # Pre-dispatch row carries task_id=None; post-dispatch row carries
        # the assigned task_id. Order on read is chronological
        # (started_at ASC, id ASC) so the second row is the post-dispatch
        # write. We assert "the assigned task_id is observable on at least
        # one row" because the deterministic clock fixture would be
        # needed to guarantee distinct started_at timestamps in the same
        # millisecond — round-trip visibility is the load-bearing
        # property here.
        observed_task_ids = {entry.details["task_id"] for entry in entries}
        assert observed_task_ids == {None, "autobuild-task-001"}

    def test_recorder_does_not_mutate_caller_details(
        self,
        persistence: SqliteLifecyclePersistence,
        seeded_build_id: str,
    ) -> None:
        """The dispatcher reuses one details dict — the recorder must copy."""
        recorder = build_stage_log_recorder(persistence)
        details = {"correlation_id": "corr-FW10-004", "task_id": None}
        details_snapshot = dict(details)

        recorder.record_running(
            build_id=seeded_build_id,
            feature_id="FEAT-FW10-004",
            stage=StageClass.AUTOBUILD,
            details_json=details,
        )

        assert details == details_snapshot, (
            "recorder must not mutate the caller's details mapping; the "
            "dispatcher reuses a single dict across pre/post-dispatch "
            "calls and a feature_id leak would alias subsequent calls"
        )


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------


class TestRecordRunningValidation:
    """Fail-fast guards on the recorder's positional arguments."""

    def test_empty_build_id_raises_value_error(
        self,
        persistence: SqliteLifecyclePersistence,
    ) -> None:
        recorder = build_stage_log_recorder(persistence)
        with pytest.raises(ValueError, match="build_id"):
            recorder.record_running(
                build_id="",
                feature_id="FEAT-X",
                stage=StageClass.AUTOBUILD,
                details_json={},
            )

    def test_empty_feature_id_raises_value_error(
        self,
        persistence: SqliteLifecyclePersistence,
        seeded_build_id: str,
    ) -> None:
        recorder = build_stage_log_recorder(persistence)
        with pytest.raises(ValueError, match="feature_id"):
            recorder.record_running(
                build_id=seeded_build_id,
                feature_id="",
                stage=StageClass.AUTOBUILD,
                details_json={},
            )

    def test_non_stageclass_stage_raises_type_error(
        self,
        persistence: SqliteLifecyclePersistence,
        seeded_build_id: str,
    ) -> None:
        recorder = build_stage_log_recorder(persistence)
        with pytest.raises(TypeError, match="StageClass"):
            recorder.record_running(
                build_id=seeded_build_id,
                feature_id="FEAT-X",
                stage="autobuild",  # type: ignore[arg-type]
                details_json={},
            )
