"""Tests for ``forge.cli.status`` (TASK-PSM-009).

Acceptance-criteria coverage map:

* AC-001: ``forge status`` (no args) shows active builds + 5 most recent
  terminal — :class:`TestDefaultView`.
* AC-002: ``forge status FEAT-XXX`` filters to that feature only —
  :class:`TestFeatureFilter`.
* AC-003: ``forge status --watch`` polls every 2s, re-renders, exits on
  terminal — :class:`TestWatchMode`.
* AC-004: ``forge status --full`` includes the last 5 stage_log entries
  per build — :class:`TestFullView`.
* AC-005: ``forge status --json`` emits a JSON array; each row matches
  :class:`BuildStatusView` — :class:`TestJsonOutput`.
* AC-006: ``cli/status.py`` imports zero modules from
  ``forge.adapters.nats.*`` — :class:`TestNoNatsImports`.
* AC-007: BDD scenario, NATS unreachable + ``forge status`` succeeds —
  :class:`TestNatsUnreachable`.
* AC-008: status query during active write returns within reasonable
  bound — :class:`TestStatusResponsiveWhileWriterActive`.

The CLI surface is exercised via Click's :class:`CliRunner` against a
real in-memory-on-disk SQLite database created by the lifecycle
migrations module — no mocking of the storage layer.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from click.testing import CliRunner

from forge.adapters.sqlite import connect as sqlite_connect
from forge.cli.status import (
    _FULL_STAGE_LIMIT,
    _RECENT_TERMINAL_LIMIT,
    _WATCH_INTERVAL_SECS,
    _all_terminal,
    _read_status_views,
    status_cmd,
)
from forge.lifecycle import migrations
from forge.lifecycle.persistence import (
    ACTIVE_STATES,
    BuildStatusView,
    SqliteLifecyclePersistence,
    StageLogEntry,
)
from forge.lifecycle.state_machine import BuildState
from forge.lifecycle.state_machine import transition as compose_transition
from forge.lifecycle.persistence import Build


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_payload(
    *,
    feature_id: str,
    correlation_id: str,
    queued_at: datetime,
) -> SimpleNamespace:
    """Construct a duck-typed BuildQueuedPayload."""
    return SimpleNamespace(
        feature_id=feature_id,
        repo="appmilla/forge",
        branch="main",
        feature_yaml_path=f"features/{feature_id}/feature.yaml",
        max_turns=5,
        sdk_timeout_seconds=1800,
        triggered_by="cli",
        originating_adapter="terminal",
        originating_user="rich",
        correlation_id=correlation_id,
        parent_request_id=None,
        queued_at=queued_at,
        requested_at=queued_at,
    )


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """Create a freshly-migrated db file and return its path."""
    path = tmp_path / "forge.db"
    cx = sqlite_connect.connect_writer(path)
    migrations.apply_at_boot(cx)
    cx.close()
    return path


@pytest.fixture()
def writer(db_path: Path) -> sqlite3.Connection:
    """Re-open the writer connection for seeding test data."""
    cx = sqlite_connect.connect_writer(db_path)
    yield cx
    cx.close()


@pytest.fixture()
def persistence(
    writer: sqlite3.Connection, db_path: Path
) -> SqliteLifecyclePersistence:
    """Return a persistence facade bound to the writer + db_path."""
    return SqliteLifecyclePersistence(connection=writer, db_path=db_path)


def _seed_build(
    persistence: SqliteLifecyclePersistence,
    *,
    feature_id: str,
    correlation_id: str,
    target_state: BuildState,
    queued_at: datetime,
) -> str:
    """Seed a build and drive it to ``target_state`` via the state machine."""
    payload = _make_payload(
        feature_id=feature_id,
        correlation_id=correlation_id,
        queued_at=queued_at,
    )
    build_id = persistence.record_pending_build(payload)
    state_path = {
        BuildState.QUEUED: [],
        BuildState.PREPARING: [BuildState.PREPARING],
        BuildState.RUNNING: [BuildState.PREPARING, BuildState.RUNNING],
        BuildState.PAUSED: [
            BuildState.PREPARING,
            BuildState.RUNNING,
            BuildState.PAUSED,
        ],
        BuildState.FINALISING: [
            BuildState.PREPARING,
            BuildState.RUNNING,
            BuildState.FINALISING,
        ],
        BuildState.COMPLETE: [
            BuildState.PREPARING,
            BuildState.RUNNING,
            BuildState.FINALISING,
            BuildState.COMPLETE,
        ],
        BuildState.FAILED: [
            BuildState.PREPARING,
            BuildState.RUNNING,
            BuildState.FINALISING,
            BuildState.FAILED,
        ],
        BuildState.CANCELLED: [BuildState.CANCELLED],
        BuildState.SKIPPED: [
            BuildState.PREPARING,
            BuildState.RUNNING,
            BuildState.SKIPPED,
        ],
    }
    current = BuildState.QUEUED
    for next_state in state_path[target_state]:
        kwargs: dict[str, Any] = {}
        if next_state in (
            BuildState.COMPLETE,
            BuildState.FAILED,
            BuildState.CANCELLED,
            BuildState.SKIPPED,
        ):
            kwargs["completed_at"] = queued_at + timedelta(minutes=5)
        if next_state is BuildState.PAUSED:
            kwargs["pending_approval_request_id"] = "req-001"
        t = compose_transition(
            Build(build_id=build_id, status=current),
            next_state,
            **kwargs,
        )
        persistence.apply_transition(t)
        current = next_state
    return build_id


def _seed_stage_log(
    persistence: SqliteLifecyclePersistence,
    *,
    build_id: str,
    count: int,
    base_time: datetime,
) -> None:
    """Seed ``count`` stage_log rows for a build."""
    for i in range(count):
        started = base_time + timedelta(minutes=i)
        completed = started + timedelta(seconds=30)
        persistence.record_stage(
            StageLogEntry(
                build_id=build_id,
                stage_label=f"stage-{i:02d}",
                target_kind="local_tool",
                target_identifier=f"tool-{i}",
                status="PASSED",
                gate_mode=None,
                started_at=started,
                completed_at=completed,
                duration_secs=30.0,
                details={"index": i},
            )
        )


# ---------------------------------------------------------------------------
# AC-006: import discipline (static-analysis check)
# ---------------------------------------------------------------------------


class TestNoNatsImports:
    """``cli/status.py`` MUST NOT import any module from
    ``forge.adapters.nats.*``."""

    def test_no_nats_imports_in_source(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        src_path = repo_root / "src" / "forge" / "cli" / "status.py"
        text = src_path.read_text(encoding="utf-8")
        # Any import (top-level or function-local) of forge.adapters.nats.*
        # is a direct violation of review F6 / Group H.
        assert not re.search(
            r"\bfrom\s+forge\.adapters\.nats\b", text
        ), "forge.cli.status must not import forge.adapters.nats.*"
        assert not re.search(
            r"\bimport\s+forge\.adapters\.nats\b", text
        ), "forge.cli.status must not import forge.adapters.nats.*"

    def test_no_nats_in_module_imports_at_runtime(self) -> None:
        import forge.cli.status as status_mod

        seen = set(getattr(status_mod, "__dict__", {}).keys())
        for name in seen:
            value = getattr(status_mod, name, None)
            module_name = getattr(value, "__module__", "") or ""
            assert not module_name.startswith("forge.adapters.nats"), (
                f"forge.cli.status pulled in nats module via {name}: "
                f"{module_name}"
            )


# ---------------------------------------------------------------------------
# AC-001: default view — active + 5 recent terminal
# ---------------------------------------------------------------------------


class TestDefaultView:
    """Default ``forge status`` shows active builds + 5 recent terminal."""

    def test_default_view_includes_active_and_terminal(
        self,
        persistence: SqliteLifecyclePersistence,
        db_path: Path,
    ) -> None:
        base = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
        # 2 active
        _seed_build(
            persistence,
            feature_id="FEAT-A",
            correlation_id="corr-A",
            target_state=BuildState.RUNNING,
            queued_at=base,
        )
        _seed_build(
            persistence,
            feature_id="FEAT-B",
            correlation_id="corr-B",
            target_state=BuildState.QUEUED,
            queued_at=base + timedelta(minutes=1),
        )
        # 7 terminal — only the most-recent 5 should be returned.
        for i in range(7):
            _seed_build(
                persistence,
                feature_id=f"FEAT-T{i}",
                correlation_id=f"corr-T{i}",
                target_state=BuildState.COMPLETE,
                queued_at=base - timedelta(hours=i + 1),
            )

        views = _read_status_views(db_path, feature_id=None)
        assert len(views) == 2 + _RECENT_TERMINAL_LIMIT
        # Sorted newest-first.
        assert views == sorted(
            views, key=lambda v: v.queued_at, reverse=True
        )

    def test_default_view_renders_table(
        self,
        persistence: SqliteLifecyclePersistence,
        db_path: Path,
    ) -> None:
        base = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
        _seed_build(
            persistence,
            feature_id="FEAT-RENDER",
            correlation_id="corr-R",
            target_state=BuildState.RUNNING,
            queued_at=base,
        )
        runner = CliRunner()
        result = runner.invoke(status_cmd, ["--db-path", str(db_path)])
        assert result.exit_code == 0, result.output
        assert "FEAT-RENDER" in result.output
        assert "RUNNING" in result.output


# ---------------------------------------------------------------------------
# AC-002: feature filter
# ---------------------------------------------------------------------------


class TestFeatureFilter:
    """Positional ``feature_id`` filters to that feature, all builds."""

    def test_feature_filter_returns_only_matching(
        self,
        persistence: SqliteLifecyclePersistence,
        db_path: Path,
    ) -> None:
        base = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
        _seed_build(
            persistence,
            feature_id="FEAT-X",
            correlation_id="corr-X1",
            target_state=BuildState.RUNNING,
            queued_at=base,
        )
        _seed_build(
            persistence,
            feature_id="FEAT-X",
            correlation_id="corr-X2",
            target_state=BuildState.COMPLETE,
            queued_at=base - timedelta(hours=1),
        )
        _seed_build(
            persistence,
            feature_id="FEAT-Y",
            correlation_id="corr-Y1",
            target_state=BuildState.RUNNING,
            queued_at=base,
        )
        views = _read_status_views(db_path, feature_id="FEAT-X")
        assert len(views) == 2
        assert all(v.feature_id == "FEAT-X" for v in views)
        assert views[0].queued_at >= views[1].queued_at

    def test_feature_filter_via_cli(
        self,
        persistence: SqliteLifecyclePersistence,
        db_path: Path,
    ) -> None:
        base = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
        _seed_build(
            persistence,
            feature_id="FEAT-Q",
            correlation_id="corr-Q",
            target_state=BuildState.RUNNING,
            queued_at=base,
        )
        _seed_build(
            persistence,
            feature_id="FEAT-Z",
            correlation_id="corr-Z",
            target_state=BuildState.RUNNING,
            queued_at=base,
        )
        runner = CliRunner()
        result = runner.invoke(
            status_cmd, ["FEAT-Q", "--db-path", str(db_path)]
        )
        assert result.exit_code == 0, result.output
        assert "FEAT-Q" in result.output
        assert "FEAT-Z" not in result.output


# ---------------------------------------------------------------------------
# AC-005: --json output
# ---------------------------------------------------------------------------


class TestJsonOutput:
    """``--json`` emits a JSON array; rows match ``BuildStatusView``."""

    def test_json_output_is_array_of_status_views(
        self,
        persistence: SqliteLifecyclePersistence,
        db_path: Path,
    ) -> None:
        base = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
        _seed_build(
            persistence,
            feature_id="FEAT-J",
            correlation_id="corr-J",
            target_state=BuildState.RUNNING,
            queued_at=base,
        )
        runner = CliRunner()
        result = runner.invoke(
            status_cmd, ["--json", "--db-path", str(db_path)]
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert isinstance(payload, list)
        assert len(payload) == 1
        # Each row must round-trip through BuildStatusView.
        for row in payload:
            view = BuildStatusView.model_validate(row)
            assert view.feature_id == "FEAT-J"
            assert view.status is BuildState.RUNNING

    def test_json_empty_db_returns_empty_array(
        self,
        db_path: Path,
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            status_cmd, ["--json", "--db-path", str(db_path)]
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload == []


# ---------------------------------------------------------------------------
# AC-004: --full clamps stage tail to 5
# ---------------------------------------------------------------------------


class TestFullView:
    """``--full`` includes the last 5 stage_log entries per build."""

    def test_full_view_caps_stage_detail_at_five(
        self,
        persistence: SqliteLifecyclePersistence,
        db_path: Path,
    ) -> None:
        base = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
        build_id = _seed_build(
            persistence,
            feature_id="FEAT-F",
            correlation_id="corr-F",
            target_state=BuildState.RUNNING,
            queued_at=base,
        )
        # 8 stages — only the last 5 must appear.
        _seed_stage_log(
            persistence, build_id=build_id, count=8, base_time=base
        )

        runner = CliRunner()
        result = runner.invoke(
            status_cmd,
            ["--json", "--full", "--db-path", str(db_path)],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert len(payload) == 1
        stages = payload[0].get("stages")
        assert stages is not None, "--full --json must include 'stages' key"
        assert len(stages) == _FULL_STAGE_LIMIT
        # Should be the LAST 5 stages (indices 3..7).
        labels = [s["stage_label"] for s in stages]
        assert labels == [
            f"stage-{i:02d}" for i in range(8 - _FULL_STAGE_LIMIT, 8)
        ]

    def test_full_view_with_fewer_than_five_stages(
        self,
        persistence: SqliteLifecyclePersistence,
        db_path: Path,
    ) -> None:
        base = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
        build_id = _seed_build(
            persistence,
            feature_id="FEAT-F2",
            correlation_id="corr-F2",
            target_state=BuildState.RUNNING,
            queued_at=base,
        )
        _seed_stage_log(
            persistence, build_id=build_id, count=2, base_time=base
        )

        runner = CliRunner()
        result = runner.invoke(
            status_cmd,
            ["--json", "--full", "--db-path", str(db_path)],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        stages = payload[0]["stages"]
        assert len(stages) == 2


# ---------------------------------------------------------------------------
# AC-003: --watch mode
# ---------------------------------------------------------------------------


class TestWatchMode:
    """``--watch`` polls every 2s, re-renders, exits when all terminal."""

    def test_watch_interval_is_two_seconds(self) -> None:
        # AC: per ``API-cli.md §4.2`` the watch loop polls every 2s.
        assert _WATCH_INTERVAL_SECS == 2.0

    def test_all_terminal_helper_with_only_terminal_states(
        self,
    ) -> None:
        base = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
        views = [
            BuildStatusView(
                build_id="b1",
                feature_id="FEAT-A",
                status=BuildState.COMPLETE,
                queued_at=base,
                completed_at=base + timedelta(minutes=5),
            ),
            BuildStatusView(
                build_id="b2",
                feature_id="FEAT-B",
                status=BuildState.FAILED,
                queued_at=base,
                completed_at=base + timedelta(minutes=5),
            ),
        ]
        assert _all_terminal(views) is True

    def test_all_terminal_helper_with_active_state(self) -> None:
        base = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
        views = [
            BuildStatusView(
                build_id="b1",
                feature_id="FEAT-A",
                status=BuildState.RUNNING,
                queued_at=base,
            ),
        ]
        assert _all_terminal(views) is False

    def test_all_terminal_helper_empty_list(self) -> None:
        # An empty list must be considered terminal so the watch loop
        # exits cleanly when the queue drains.
        assert _all_terminal([]) is True

    def test_watch_mode_exits_when_only_terminal(
        self,
        persistence: SqliteLifecyclePersistence,
        db_path: Path,
    ) -> None:
        base = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
        _seed_build(
            persistence,
            feature_id="FEAT-W",
            correlation_id="corr-W",
            target_state=BuildState.COMPLETE,
            queued_at=base,
        )
        runner = CliRunner()
        result = runner.invoke(
            status_cmd,
            ["--watch", "--db-path", str(db_path)],
        )
        # Must not hang — terminal-only state means immediate exit.
        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# AC-007: NATS unreachable + status succeeds
# ---------------------------------------------------------------------------


class TestNatsUnreachable:
    """Status command works without the messaging layer (Group H)."""

    def test_status_works_without_nats_module_imported(
        self,
        persistence: SqliteLifecyclePersistence,
        db_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Simulate "NATS unreachable" by ensuring no nats module is even
        # loaded into sys.modules at import time.
        import sys

        # Block any future attempt to import forge.adapters.nats.*.
        class _ForbiddenFinder:
            def find_module(self, name: str, path: Any = None) -> Any:
                if name.startswith("forge.adapters.nats"):
                    raise ImportError(
                        f"NATS adapters are unreachable: {name}"
                    )
                return None

        monkeypatch.setattr(sys, "meta_path", [_ForbiddenFinder()] + sys.meta_path)

        base = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
        _seed_build(
            persistence,
            feature_id="FEAT-NATS-DOWN",
            correlation_id="corr-N",
            target_state=BuildState.RUNNING,
            queued_at=base,
        )
        # Re-import status module — must succeed without NATS.
        # Force a clean re-read of the module.
        sys.modules.pop("forge.cli.status", None)
        import forge.cli.status as reimport

        runner = CliRunner()
        result = runner.invoke(
            reimport.status_cmd, ["--db-path", str(db_path)]
        )
        assert result.exit_code == 0, result.output
        assert "FEAT-NATS-DOWN" in result.output


# ---------------------------------------------------------------------------
# AC-008: status responsive while writer active
# ---------------------------------------------------------------------------


class TestStatusResponsiveWhileWriterActive:
    """A status query while a writer is mid-transaction returns promptly."""

    def test_read_status_returns_within_reasonable_bound(
        self,
        persistence: SqliteLifecyclePersistence,
        db_path: Path,
    ) -> None:
        import time

        base = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
        _seed_build(
            persistence,
            feature_id="FEAT-CONC",
            correlation_id="corr-C",
            target_state=BuildState.RUNNING,
            queued_at=base,
        )

        # Writer holds a BEGIN IMMEDIATE transaction; reader must still
        # complete because we open a fresh ``mode=ro`` URI handle and
        # WAL mode on the writer permits concurrent readers (DDR-003).
        writer_cx = persistence.connection
        writer_cx.execute("BEGIN IMMEDIATE;")
        try:
            start = time.monotonic()
            views = _read_status_views(db_path, feature_id=None)
            elapsed = time.monotonic() - start
        finally:
            writer_cx.execute("ROLLBACK;")

        assert len(views) == 1
        # Reasonable bound — well under the 5s busy-timeout default.
        assert elapsed < 2.0, (
            f"read_status took {elapsed:.2f}s while writer active; "
            "exceeded reasonable bound"
        )


# ---------------------------------------------------------------------------
# Helper: status_cmd is a Click command
# ---------------------------------------------------------------------------


class TestStatusCommandShape:
    """``status_cmd`` is a Click command exposing the four flags."""

    def test_status_cmd_is_click_command(self) -> None:
        import click

        assert isinstance(status_cmd, click.Command)
        assert status_cmd.name == "status"

    def test_help_lists_all_flags(self) -> None:
        runner = CliRunner()
        result = runner.invoke(status_cmd, ["--help"])
        assert result.exit_code == 0
        for flag in ("--watch", "--full", "--json"):
            assert flag in result.output, (
                f"--help output missing {flag}: {result.output!r}"
            )
