"""Integration tests for the SQLite substrate (TASK-PSM-002).

Covers:

- ``forge.lifecycle.schema`` (the ``schema.sql`` file shipped as a
  package resource).
- ``forge.lifecycle.migrations.apply_at_boot`` — idempotent boot-time
  migration runner that creates tables and seeds the
  ``schema_version`` table.
- ``forge.adapters.sqlite.connect.connect_writer`` and
  ``read_only_connect`` — connection helpers that apply the four
  mandatory pragmas from DDR-003 (``journal_mode = WAL``,
  ``synchronous = NORMAL``, ``foreign_keys = ON``,
  ``busy_timeout = 5000``).

The tests follow the AAA pattern (Arrange / Act / Assert) and exercise
the adapter against real SQLite files in ``tmp_path`` — the sub-millisecond
SQLite file engine makes "integration" tests cheap enough that mocking
adds nothing.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from forge.adapters.sqlite import connect as sqlite_connect
from forge.lifecycle import migrations


# ---------------------------------------------------------------------------
# schema.sql shape
# ---------------------------------------------------------------------------


def _read_schema_sql() -> str:
    """Return the bundled ``schema.sql`` text via importlib.resources.

    Mirrors the way ``migrations.apply_at_boot`` is documented to load
    the file — keeps the test contract close to production loading.
    """
    from importlib.resources import files

    return (files("forge.lifecycle") / "schema.sql").read_text(encoding="utf-8")


def test_schema_defines_strict_builds_table_with_pending_approval_column() -> None:
    """`builds` must be STRICT and carry the F4 recovery column."""
    sql = _read_schema_sql()

    assert "CREATE TABLE IF NOT EXISTS builds" in sql
    # STRICT marker for the builds table
    assert "STRICT" in sql
    # F4 recovery column required by the task description
    assert "pending_approval_request_id TEXT" in sql


def test_schema_defines_stage_log_with_indices() -> None:
    """`stage_log` plus the two §2.2 indices must be present."""
    sql = _read_schema_sql()

    assert "CREATE TABLE IF NOT EXISTS stage_log" in sql
    assert "idx_stage_log_build" in sql
    assert "idx_stage_log_gated" in sql


def test_schema_defines_schema_version_with_seed_row() -> None:
    """`schema_version` table is created and seeded idempotently."""
    sql = _read_schema_sql()

    assert "CREATE TABLE IF NOT EXISTS schema_version" in sql
    assert "INSERT OR IGNORE INTO schema_version" in sql


def test_schema_declares_unique_feature_correlation_index() -> None:
    """UNIQUE INDEX on (feature_id, correlation_id) per AC."""
    sql = _read_schema_sql()

    assert "uq_builds_feature_correlation" in sql
    assert "UNIQUE INDEX" in sql


# ---------------------------------------------------------------------------
# migrations.apply_at_boot
# ---------------------------------------------------------------------------


def test_apply_at_boot_creates_tables_and_seeds_schema_version(
    tmp_path: Path,
) -> None:
    """Fresh DB → tables exist and schema_version row 1 is seeded."""
    db_path = tmp_path / "forge.db"
    cx = sqlite_connect.connect_writer(db_path)
    try:
        migrations.apply_at_boot(cx)

        tables = {
            row[0]
            for row in cx.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            )
        }
        assert {"builds", "stage_log", "schema_version"}.issubset(tables)

        version_row = cx.execute(
            "SELECT version FROM schema_version ORDER BY version;"
        ).fetchone()
        assert version_row == (1,)
    finally:
        cx.close()


def test_apply_at_boot_is_idempotent(tmp_path: Path) -> None:
    """Running migrations twice must be a no-op (AC explicit)."""
    db_path = tmp_path / "forge.db"
    cx = sqlite_connect.connect_writer(db_path)
    try:
        migrations.apply_at_boot(cx)
        migrations.apply_at_boot(cx)

        rows = cx.execute(
            "SELECT version FROM schema_version ORDER BY version;"
        ).fetchall()
        assert rows == [(1,)], "second apply must not duplicate the seed row"
    finally:
        cx.close()


# ---------------------------------------------------------------------------
# Connection helpers — DDR-003 pragmas
# ---------------------------------------------------------------------------


def _read_pragma(cx: sqlite3.Connection, pragma: str) -> object:
    """Read back a pragma value (single-column round-trip)."""
    row = cx.execute(f"PRAGMA {pragma};").fetchone()
    return None if row is None else row[0]


def test_connect_writer_applies_four_mandatory_pragmas(tmp_path: Path) -> None:
    """`connect_writer` must apply DDR-003 pragmas on open."""
    db_path = tmp_path / "forge.db"
    cx = sqlite_connect.connect_writer(db_path)
    try:
        # Triggering a write commits the WAL pragma.
        migrations.apply_at_boot(cx)

        assert _read_pragma(cx, "journal_mode") == "wal"
        assert _read_pragma(cx, "synchronous") == 1  # NORMAL
        assert _read_pragma(cx, "foreign_keys") == 1
        assert _read_pragma(cx, "busy_timeout") == 5000
    finally:
        cx.close()


def test_read_only_connect_uses_mode_ro_uri_and_rejects_writes(
    tmp_path: Path,
) -> None:
    """`read_only_connect` must open with mode=ro and refuse writes."""
    db_path = tmp_path / "forge.db"
    writer = sqlite_connect.connect_writer(db_path)
    try:
        migrations.apply_at_boot(writer)
        writer.execute(
            """
            INSERT INTO builds (
                build_id, feature_id, repo, branch, feature_yaml_path,
                status, triggered_by, correlation_id, queued_at
            ) VALUES (
                'build-feat-1', 'feat-1', 'repo', 'main',
                'features/feat-1/feat-1.yaml',
                'QUEUED', 'cli', 'corr-1', '2026-04-27T00:00:00Z'
            );
            """
        )
        writer.commit()
    finally:
        writer.close()

    reader = sqlite_connect.read_only_connect(db_path)
    try:
        # Reads are fine
        row = reader.execute("SELECT build_id FROM builds;").fetchone()
        assert row == ("build-feat-1",)

        # Writes must raise — the DB is open in mode=ro
        with pytest.raises(sqlite3.OperationalError):
            reader.execute(
                "UPDATE builds SET status='RUNNING' WHERE build_id='build-feat-1';"
            )
    finally:
        reader.close()


# ---------------------------------------------------------------------------
# Integration ACs
# ---------------------------------------------------------------------------


def test_apply_migrations_then_journal_mode_is_wal(tmp_path: Path) -> None:
    """Open fresh DB, run migrations, observe WAL + version=1."""
    db_path = tmp_path / "forge.db"
    cx = sqlite_connect.connect_writer(db_path)
    try:
        migrations.apply_at_boot(cx)

        assert _read_pragma(cx, "journal_mode") == "wal"
        version = cx.execute("SELECT version FROM schema_version;").fetchone()
        assert version == (1,)
    finally:
        cx.close()


def test_strict_table_rejects_non_integer_max_turns(tmp_path: Path) -> None:
    """STRICT enforcement: text in an INTEGER column must raise."""
    db_path = tmp_path / "forge.db"
    cx = sqlite_connect.connect_writer(db_path)
    try:
        migrations.apply_at_boot(cx)

        with pytest.raises(sqlite3.IntegrityError):
            cx.execute(
                """
                INSERT INTO builds (
                    build_id, feature_id, repo, branch, feature_yaml_path,
                    status, triggered_by, correlation_id, queued_at,
                    max_turns
                ) VALUES (
                    'build-feat-2', 'feat-2', 'repo', 'main',
                    'features/feat-2/feat-2.yaml',
                    'QUEUED', 'cli', 'corr-2', '2026-04-27T00:00:00Z',
                    'not-an-int'
                );
                """
            )
    finally:
        cx.close()


def test_wal_sidecar_files_appear_after_first_write(tmp_path: Path) -> None:
    """After a committed write the -wal and -shm files must exist.

    The check runs *while the connection is still open* — SQLite's
    default close-time checkpoint can collapse the WAL frames back
    into the main DB and unlink the sidecar files, which would mask
    the contract this test exists to verify. The DDR-003 requirement
    is that WAL is engaged during the lifetime of the writer, not
    that the files persist after shutdown.
    """
    db_path = tmp_path / "forge.db"
    cx = sqlite_connect.connect_writer(db_path)
    try:
        migrations.apply_at_boot(cx)
        cx.execute(
            """
            INSERT INTO builds (
                build_id, feature_id, repo, branch, feature_yaml_path,
                status, triggered_by, correlation_id, queued_at
            ) VALUES (
                'build-feat-3', 'feat-3', 'repo', 'main',
                'features/feat-3/feat-3.yaml',
                'QUEUED', 'cli', 'corr-3', '2026-04-27T00:00:00Z'
            );
            """
        )
        cx.commit()

        assert db_path.exists()
        assert db_path.with_name(db_path.name + "-wal").exists()
        assert db_path.with_name(db_path.name + "-shm").exists()
    finally:
        cx.close()


# ---------------------------------------------------------------------------
# Foreign key + unique index round-trip
# ---------------------------------------------------------------------------


def test_unique_feature_correlation_index_rejects_duplicates(
    tmp_path: Path,
) -> None:
    """The UNIQUE INDEX on (feature_id, correlation_id) is enforced."""
    db_path = tmp_path / "forge.db"
    cx = sqlite_connect.connect_writer(db_path)
    try:
        migrations.apply_at_boot(cx)
        cx.execute(
            """
            INSERT INTO builds (
                build_id, feature_id, repo, branch, feature_yaml_path,
                status, triggered_by, correlation_id, queued_at
            ) VALUES (
                'build-A', 'feat-x', 'repo', 'main',
                'features/feat-x/feat-x.yaml',
                'QUEUED', 'cli', 'corr-x', '2026-04-27T00:00:00Z'
            );
            """
        )
        cx.commit()

        with pytest.raises(sqlite3.IntegrityError):
            cx.execute(
                """
                INSERT INTO builds (
                    build_id, feature_id, repo, branch, feature_yaml_path,
                    status, triggered_by, correlation_id, queued_at
                ) VALUES (
                    'build-B', 'feat-x', 'repo', 'main',
                    'features/feat-x/feat-x.yaml',
                    'QUEUED', 'cli', 'corr-x', '2026-04-27T00:00:00Z'
                );
                """
            )
    finally:
        cx.close()
