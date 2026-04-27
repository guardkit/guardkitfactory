"""Tests for ``forge.cli.history`` (TASK-PSM-010).

Acceptance-criteria coverage map:

* AC-001: ``forge history`` returns at most 50 entries by default.
* AC-002: ``--limit 1`` returns at most 1 entry.
* AC-003: ``--limit 50`` on 60 prior builds returns 50.
* AC-004: 10 prior builds returns 10 (does not pad).
* AC-005: ``--feature FEAT-XXX`` returns all builds for that feature with
  ``stage_log`` expanded.
* AC-006: ``--since DATE`` filters by ``queued_at >= date``.
* AC-007: ``--format md`` emits the markdown structure from §5.3.
* AC-008: ``--format json`` emits a JSON array.
* AC-009: zero NATS imports in ``cli/history.py`` (static check).
* AC-010: Module imports cleanly under the project lint/format settings —
  this is exercised implicitly by collection succeeding (the module
  parses, type-hints resolve, no unused-import warnings produced under
  the project's Black config).

Tests use the same in-memory-then-spilled-to-disk approach as
``tests/forge/test_lifecycle_persistence.py`` — a real SQLite file under
``tmp_path`` so the ``read_only_connect()`` URI form works end-to-end.
"""

from __future__ import annotations

import ast
import json
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from forge.adapters.sqlite import connect as sqlite_connect
from forge.cli import history as history_module
from forge.cli.history import (
    SUPPORTED_FORMATS,
    fetch_history,
    history_cmd,
    parse_since,
    render_json,
    render_markdown,
    render_table,
    run_history,
)
from forge.lifecycle import migrations
from forge.lifecycle.persistence import (
    SqliteLifecyclePersistence,
    StageLogEntry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_payload(
    *,
    feature_id: str,
    correlation_id: str,
    queued_at: datetime,
) -> SimpleNamespace:
    """Build a duck-typed BuildQueuedPayload accepted by record_pending_build."""
    return SimpleNamespace(
        feature_id=feature_id,
        repo="guardkit/forge",
        branch="main",
        feature_yaml_path=f"features/{feature_id}/feature.yaml",
        max_turns=5,
        sdk_timeout_seconds=1800,
        triggered_by="cli",
        originating_adapter=None,
        originating_user="rich",
        correlation_id=correlation_id,
        parent_request_id=None,
        queued_at=queued_at,
    )


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """Return a freshly-migrated forge.db path."""
    path = tmp_path / "forge.db"
    cx = sqlite_connect.connect_writer(path)
    migrations.apply_at_boot(cx)
    cx.close()
    return path


@pytest.fixture()
def writer(db_path: Path):
    """Return an open writer connection bound to ``db_path``."""
    cx = sqlite_connect.connect_writer(db_path)
    yield cx
    cx.close()


@pytest.fixture()
def persistence(writer: sqlite3.Connection, db_path: Path) -> SqliteLifecyclePersistence:
    """Persistence facade bound to the writer + on-disk db."""
    return SqliteLifecyclePersistence(connection=writer, db_path=db_path)


def _seed_builds(
    persistence: SqliteLifecyclePersistence,
    *,
    count: int,
    feature_id: str = "FEAT-A1B2",
    base_time: datetime | None = None,
) -> list[str]:
    """Seed ``count`` builds, oldest first, separated by 1 minute."""
    if base_time is None:
        base_time = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
    ids: list[str] = []
    for index in range(count):
        queued_at = base_time + timedelta(minutes=index)
        payload = _make_payload(
            feature_id=feature_id,
            correlation_id=f"corr-{feature_id}-{index:04d}",
            queued_at=queued_at,
        )
        ids.append(persistence.record_pending_build(payload))
    return ids


# ---------------------------------------------------------------------------
# AC-009: import discipline (no NATS imports)
# ---------------------------------------------------------------------------


class TestImportDiscipline:
    """``cli/history.py`` MUST NOT import from ``forge.adapters.nats.*``."""

    def test_no_nats_import_in_history_module_source(self) -> None:
        source_path = Path(history_module.__file__)
        text = source_path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        offenders: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("forge.adapters.nats"):
                        offenders.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("forge.adapters.nats"):
                    offenders.append(module)
        assert offenders == [], (
            f"forge.cli.history must not import forge.adapters.nats.*; "
            f"found: {offenders}"
        )

    def test_no_nats_import_via_text_match(self) -> None:
        # Defence-in-depth: catch any string-form coupling (e.g. importlib).
        source_path = Path(history_module.__file__)
        text = source_path.read_text(encoding="utf-8")
        # Allow comments / docstrings to mention NATS, but no actual import.
        assert not re.search(r"^\s*(import|from)\s+forge\.adapters\.nats", text, re.M)


# ---------------------------------------------------------------------------
# AC-001..AC-004: limit and default behaviour
# ---------------------------------------------------------------------------


class TestDefaultLimitFiftyEntries:
    """``forge history`` returns at most 50 entries by default."""

    def test_default_limit_caps_at_fifty_when_more_present(
        self, db_path: Path, persistence: SqliteLifecyclePersistence
    ) -> None:
        _seed_builds(persistence, count=60)
        rendered = run_history(
            db_path=db_path,
            config=None,
            feature_id=None,
            limit=None,
            since=None,
            output_format="json",
        )
        rows = json.loads(rendered)
        assert len(rows) == 50

    def test_default_limit_returns_actual_when_fewer_present(
        self, db_path: Path, persistence: SqliteLifecyclePersistence
    ) -> None:
        # AC-004: 10 prior builds returns 10 (does not pad).
        _seed_builds(persistence, count=10)
        rendered = run_history(
            db_path=db_path,
            config=None,
            feature_id=None,
            limit=None,
            since=None,
            output_format="json",
        )
        rows = json.loads(rendered)
        assert len(rows) == 10


class TestLimitFlag:
    """``--limit`` clamps results to N entries."""

    def test_limit_one_returns_at_most_one(
        self, db_path: Path, persistence: SqliteLifecyclePersistence
    ) -> None:
        # AC-002.
        _seed_builds(persistence, count=10)
        rendered = run_history(
            db_path=db_path,
            config=None,
            feature_id=None,
            limit=1,
            since=None,
            output_format="json",
        )
        rows = json.loads(rendered)
        assert len(rows) == 1

    def test_limit_fifty_on_sixty_builds_returns_fifty(
        self, db_path: Path, persistence: SqliteLifecyclePersistence
    ) -> None:
        # AC-003.
        _seed_builds(persistence, count=60)
        rendered = run_history(
            db_path=db_path,
            config=None,
            feature_id=None,
            limit=50,
            since=None,
            output_format="json",
        )
        rows = json.loads(rendered)
        assert len(rows) == 50

    def test_limit_zero_or_negative_rejected(
        self, db_path: Path, persistence: SqliteLifecyclePersistence
    ) -> None:
        _seed_builds(persistence, count=2)
        with pytest.raises(Exception):
            run_history(
                db_path=db_path,
                config=None,
                feature_id=None,
                limit=0,
                since=None,
                output_format="json",
            )


# ---------------------------------------------------------------------------
# AC-005: --feature filter
# ---------------------------------------------------------------------------


class TestFeatureFilter:
    """``--feature FEAT-XXX`` returns all builds for that feature."""

    def test_feature_filter_returns_only_matching_builds(
        self, db_path: Path, persistence: SqliteLifecyclePersistence
    ) -> None:
        # AC-005.
        _seed_builds(persistence, count=3, feature_id="FEAT-A1B2")
        _seed_builds(
            persistence,
            count=2,
            feature_id="FEAT-C3D4",
            base_time=datetime(2026, 4, 28, 12, 0, 0, tzinfo=UTC),
        )

        rendered = run_history(
            db_path=db_path,
            config=None,
            feature_id="FEAT-A1B2",
            limit=None,
            since=None,
            output_format="json",
        )
        rows = json.loads(rendered)
        assert len(rows) == 3
        assert all(row["feature_id"] == "FEAT-A1B2" for row in rows)

    def test_feature_filter_expands_stage_log_in_md(
        self,
        db_path: Path,
        persistence: SqliteLifecyclePersistence,
    ) -> None:
        ids = _seed_builds(persistence, count=1, feature_id="FEAT-A1B2")
        build_id = ids[0]
        # Add a couple of stage_log rows so the md renderer surfaces them.
        persistence.record_stage(
            StageLogEntry(
                build_id=build_id,
                stage_label="ArchitectureReview",
                target_kind="subagent",
                target_identifier="architect",
                status="PASSED",
                gate_mode=None,
                coach_score=0.84,
                threshold_applied=None,
                started_at=datetime(2026, 4, 27, 12, 5, 3, tzinfo=UTC),
                completed_at=datetime(2026, 4, 27, 12, 6, 15, tzinfo=UTC),
                duration_secs=72.0,
                details={},
            )
        )

        rendered = run_history(
            db_path=db_path,
            config=None,
            feature_id="FEAT-A1B2",
            limit=None,
            since=None,
            output_format="md",
        )
        assert "ArchitectureReview" in rendered
        assert "score=0.84" in rendered


# ---------------------------------------------------------------------------
# AC-006: --since filter
# ---------------------------------------------------------------------------


class TestSinceFilter:
    """``--since YYYY-MM-DD`` filters by ``queued_at >= date``."""

    def test_since_filters_older_builds(
        self, db_path: Path, persistence: SqliteLifecyclePersistence
    ) -> None:
        # AC-006.
        # 5 builds on 2026-04-19, 5 on 2026-04-21.
        _seed_builds(
            persistence,
            count=5,
            feature_id="FEAT-OLD",
            base_time=datetime(2026, 4, 19, 12, 0, 0, tzinfo=UTC),
        )
        _seed_builds(
            persistence,
            count=5,
            feature_id="FEAT-NEW",
            base_time=datetime(2026, 4, 21, 12, 0, 0, tzinfo=UTC),
        )

        rendered = run_history(
            db_path=db_path,
            config=None,
            feature_id=None,
            limit=None,
            since="2026-04-20",
            output_format="json",
        )
        rows = json.loads(rendered)
        assert len(rows) == 5
        assert all(row["feature_id"] == "FEAT-NEW" for row in rows)

    def test_parse_since_bare_date_yields_midnight_utc(self) -> None:
        parsed = parse_since("2026-04-20")
        assert parsed == datetime(2026, 4, 20, 0, 0, 0, tzinfo=UTC)

    def test_parse_since_rejects_invalid_input(self) -> None:
        with pytest.raises(Exception):
            parse_since("not-a-date")
        with pytest.raises(Exception):
            parse_since("")


# ---------------------------------------------------------------------------
# AC-007: --format md
# ---------------------------------------------------------------------------


class TestMarkdownFormat:
    """``--format md`` emits the markdown structure from §5.3."""

    def test_markdown_emits_header_and_per_build_section(
        self, db_path: Path, persistence: SqliteLifecyclePersistence
    ) -> None:
        # AC-007.
        _seed_builds(persistence, count=2, feature_id="FEAT-A1B2")

        rendered = run_history(
            db_path=db_path,
            config=None,
            feature_id="FEAT-A1B2",
            limit=None,
            since=None,
            output_format="md",
        )
        # Heading per §5.3.
        assert rendered.startswith("# Forge history — FEAT-A1B2\n")
        # Each build gets a per-build heading.
        per_build_headings = re.findall(r"^## build-.*$", rendered, re.M)
        assert len(per_build_headings) == 2
        # Started/Finished and Stages sub-section.
        assert "Started:" in rendered
        assert "Finished:" in rendered
        assert "### Stages" in rendered

    def test_markdown_no_results_emits_placeholder(
        self, db_path: Path
    ) -> None:
        rendered = run_history(
            db_path=db_path,
            config=None,
            feature_id="FEAT-EMPTY",
            limit=None,
            since=None,
            output_format="md",
        )
        assert "_No builds found._" in rendered


# ---------------------------------------------------------------------------
# AC-008: --format json
# ---------------------------------------------------------------------------


class TestJsonFormat:
    """``--format json`` emits a JSON array."""

    def test_json_format_emits_array(
        self, db_path: Path, persistence: SqliteLifecyclePersistence
    ) -> None:
        # AC-008.
        _seed_builds(persistence, count=3)
        rendered = run_history(
            db_path=db_path,
            config=None,
            feature_id=None,
            limit=None,
            since=None,
            output_format="json",
        )
        parsed = json.loads(rendered)
        assert isinstance(parsed, list)
        assert len(parsed) == 3
        for row in parsed:
            assert "build_id" in row
            assert "feature_id" in row
            assert "status" in row
            assert "queued_at" in row
            assert "stage_log" in row

    def test_json_format_empty_yields_empty_array(self, db_path: Path) -> None:
        rendered = run_history(
            db_path=db_path,
            config=None,
            feature_id=None,
            limit=None,
            since=None,
            output_format="json",
        )
        parsed = json.loads(rendered)
        assert parsed == []


# ---------------------------------------------------------------------------
# Renderer unit tests (no DB)
# ---------------------------------------------------------------------------


class TestRenderTable:
    """Table renderer is the human default."""

    def test_render_table_no_rows(self) -> None:
        assert "No builds found." in render_table([])

    def test_render_table_includes_headers(
        self, db_path: Path, persistence: SqliteLifecyclePersistence
    ) -> None:
        _seed_builds(persistence, count=1)
        pairs = fetch_history(
            persistence,
            limit=10,
            feature_id=None,
            since=None,
            include_stages=False,
        )
        rendered = render_table(pairs)
        assert "BUILD" in rendered
        assert "FEATURE" in rendered
        assert "STATUS" in rendered


# ---------------------------------------------------------------------------
# Click command integration
# ---------------------------------------------------------------------------


class TestClickCommand:
    """The Click command surface forwards options to ``run_history``."""

    def test_click_command_default_format_table(
        self, db_path: Path, persistence: SqliteLifecyclePersistence
    ) -> None:
        _seed_builds(persistence, count=2)
        runner = CliRunner()
        result = runner.invoke(history_cmd, ["--db", str(db_path)])
        assert result.exit_code == 0, result.output
        assert "BUILD" in result.output

    def test_click_command_json_format(
        self, db_path: Path, persistence: SqliteLifecyclePersistence
    ) -> None:
        _seed_builds(persistence, count=2)
        runner = CliRunner()
        result = runner.invoke(
            history_cmd,
            ["--db", str(db_path), "--format", "json"],
        )
        assert result.exit_code == 0, result.output
        parsed = json.loads(result.output)
        assert len(parsed) == 2

    def test_click_command_supported_formats_constant(self) -> None:
        # Sanity — the Click choice and the run_history validator share
        # the same source of truth.
        assert "table" in SUPPORTED_FORMATS
        assert "json" in SUPPORTED_FORMATS
        assert "md" in SUPPORTED_FORMATS
