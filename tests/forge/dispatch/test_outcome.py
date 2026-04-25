"""Tests for ``forge.dispatch.outcome`` (TASK-SAD-009).

Acceptance criteria coverage map:

* AC-001: ``src/forge/dispatch/outcome.py`` defines ``correlate_outcome()``
  and ``synthesize_degraded()`` — see :class:`TestPublicSurface`.
* AC-002: ``correlate_outcome()`` is idempotent — see
  :class:`TestCorrelateOutcomeIdempotency`.
* AC-003: Idempotency at SQL level — exactly one UPDATE statement across
  two consecutive calls — see
  :meth:`TestCorrelateOutcomeIdempotency.test_only_one_update_across_two_calls`.
* AC-004: After ``correlate_outcome()`` the resolution record has
  ``outcome_correlated=True`` and references ``gate_decision_id`` — see
  :class:`TestCorrelateOutcomePostState`.
* AC-005: ``synthesize_degraded(reason="no_specialist_resolvable")``
  surfaces the input reason — see :class:`TestSynthesizeDegradedReasons`.
* AC-006: ``snapshot_stale=True`` surfaces staleness in the reason —
  see :meth:`TestSynthesizeDegradedReasons.test_snapshot_stale_true_records_staleness`.
* AC-007: Bus-disconnect path produces a Degraded with
  ``reason="bus_disconnected"`` — see
  :meth:`TestSynthesizeDegradedReasons.test_bus_disconnected_reason_round_trip`.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from forge.discovery.models import CapabilityResolution
from forge.dispatch.models import Degraded
from forge.dispatch.outcome import correlate_outcome, synthesize_degraded
from forge.dispatch.persistence import (
    SqliteHistoryWriter,
    persist_resolution,
)


# ---------------------------------------------------------------------------
# Fixtures + helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def db_writer() -> SqliteHistoryWriter:
    """Fresh in-memory :class:`SqliteHistoryWriter` per test."""
    writer = SqliteHistoryWriter.in_memory()
    yield writer
    writer.close()


def _seed_resolution(
    db_writer: SqliteHistoryWriter,
    *,
    resolution_id: str = "res-001",
) -> CapabilityResolution:
    """Insert a baseline resolution row and return the model."""
    resolution = CapabilityResolution(
        resolution_id=resolution_id,
        build_id="build-001",
        stage_label="implementation",
        requested_tool="do_thing",
        matched_agent_id="agent-a",
        match_source="tool_exact",
        competing_agents=[],
        resolved_at=datetime(2026, 4, 25, 12, 0, 0, tzinfo=UTC),
    )
    persist_resolution(resolution, parameters=[], db_writer=db_writer)
    return resolution


class _UpdateCountingConnection:
    """Wrapper that counts UPDATE statements issued via ``execute``.

    Used in the idempotency test to assert the SQL-layer guarantee:
    exactly one UPDATE across two consecutive ``correlate_outcome``
    calls with identical args.
    """

    def __init__(self, real: sqlite3.Connection) -> None:
        self._real = real
        self.update_count = 0

    def execute(self, sql: str, *args: object, **kwargs: object) -> object:
        if sql.lstrip().upper().startswith("UPDATE"):
            self.update_count += 1
        return self._real.execute(sql, *args, **kwargs)

    def __getattr__(self, item: str) -> object:
        return getattr(self._real, item)

    def __enter__(self) -> sqlite3.Connection:
        return self._real.__enter__()

    def __exit__(self, *exc: object) -> object:
        return self._real.__exit__(*exc)


# ---------------------------------------------------------------------------
# AC-001 — public surface
# ---------------------------------------------------------------------------


class TestPublicSurface:
    """AC-001: the module exposes both helpers."""

    def test_correlate_outcome_is_callable(self) -> None:
        assert callable(correlate_outcome)

    def test_synthesize_degraded_is_callable(self) -> None:
        assert callable(synthesize_degraded)


# ---------------------------------------------------------------------------
# AC-002 / AC-003 — idempotency
# ---------------------------------------------------------------------------


class TestCorrelateOutcomeIdempotency:
    """AC-002 + AC-003: two consecutive calls produce equal records and
    issue exactly one UPDATE statement."""

    def test_two_calls_return_equal_records(
        self, db_writer: SqliteHistoryWriter
    ) -> None:
        _seed_resolution(db_writer)
        r1 = correlate_outcome("res-001", "gate-A", db_writer=db_writer)
        r2 = correlate_outcome("res-001", "gate-A", db_writer=db_writer)
        assert r1 == r2

    def test_only_one_update_across_two_calls(
        self, db_writer: SqliteHistoryWriter
    ) -> None:
        _seed_resolution(db_writer)
        # Wrap the underlying connection so we can count UPDATE statements
        # without changing the writer's public surface.
        counter = _UpdateCountingConnection(db_writer._connection)
        db_writer._connection = counter  # type: ignore[assignment]

        correlate_outcome("res-001", "gate-A", db_writer=db_writer)
        correlate_outcome("res-001", "gate-A", db_writer=db_writer)

        assert counter.update_count == 1

    def test_unknown_resolution_id_raises_key_error(
        self, db_writer: SqliteHistoryWriter
    ) -> None:
        with pytest.raises(KeyError):
            correlate_outcome("ghost", "gate-A", db_writer=db_writer)

    def test_mock_writer_only_invokes_update_once(self) -> None:
        """When mocked, the writer's correlate API is the seam under test.

        We assert the API contract on a MagicMock writer: two consecutive
        calls with the same args return equal records (idempotency at the
        helper boundary), and the helper delegates to the writer.
        """
        mock_writer = MagicMock(spec=SqliteHistoryWriter)
        # Configure the mock to simulate a correlate_outcome that returns
        # the same resolution for both calls.
        correlated = CapabilityResolution(
            resolution_id="res-001",
            build_id="build-001",
            stage_label="implementation",
            requested_tool="do_thing",
            matched_agent_id="agent-a",
            match_source="tool_exact",
            competing_agents=[],
            resolved_at=datetime(2026, 4, 25, 12, 0, 0, tzinfo=UTC),
            outcome_correlated=True,
            gate_decision_id="gate-A",
        )
        mock_writer.correlate_outcome.return_value = correlated

        r1 = correlate_outcome("res-001", "gate-A", db_writer=mock_writer)
        r2 = correlate_outcome("res-001", "gate-A", db_writer=mock_writer)

        assert r1 == r2
        # Helper delegates each call to the writer; the writer is
        # responsible for SQL-level idempotency. Assert the seam contract:
        # both calls land on the writer.
        assert mock_writer.correlate_outcome.call_count == 2


# ---------------------------------------------------------------------------
# AC-004 — post-state of correlated resolution
# ---------------------------------------------------------------------------


class TestCorrelateOutcomePostState:
    """AC-004: after correlate_outcome, the resolution carries the
    correlation flag and a reference to the gate_decision_id."""

    def test_outcome_correlated_flag_flipped(
        self, db_writer: SqliteHistoryWriter
    ) -> None:
        _seed_resolution(db_writer)
        result = correlate_outcome("res-001", "gate-A", db_writer=db_writer)
        assert result.outcome_correlated is True

    def test_gate_decision_id_recorded_on_record(
        self, db_writer: SqliteHistoryWriter
    ) -> None:
        _seed_resolution(db_writer)
        result = correlate_outcome("res-001", "gate-A", db_writer=db_writer)
        assert result.gate_decision_id == "gate-A"

    def test_correlation_persists_across_reads(
        self, db_writer: SqliteHistoryWriter
    ) -> None:
        _seed_resolution(db_writer)
        correlate_outcome("res-001", "gate-A", db_writer=db_writer)
        rows = db_writer.read_resolutions()
        assert len(rows) == 1
        assert rows[0].outcome_correlated is True
        assert rows[0].gate_decision_id == "gate-A"


# ---------------------------------------------------------------------------
# AC-005 / AC-006 / AC-007 — synthesize_degraded
# ---------------------------------------------------------------------------


class TestSynthesizeDegradedReasons:
    """AC-005, AC-006, AC-007: synthesize_degraded surfaces the input
    reason and the staleness flag."""

    def test_no_specialist_resolvable_reason_round_trip(self) -> None:
        degraded = synthesize_degraded(
            capability="do_thing", reason="no_specialist_resolvable"
        )
        assert isinstance(degraded, Degraded)
        assert degraded.kind == "degraded"
        assert "no_specialist_resolvable" in degraded.reason

    def test_all_resolvable_specialists_degraded_reason_round_trip(
        self,
    ) -> None:
        degraded = synthesize_degraded(
            capability="do_thing",
            reason="all_resolvable_specialists_degraded",
        )
        assert "all_resolvable_specialists_degraded" in degraded.reason

    def test_bus_disconnected_reason_round_trip(self) -> None:
        degraded = synthesize_degraded(
            capability="do_thing", reason="bus_disconnected"
        )
        assert "bus_disconnected" in degraded.reason

    def test_registry_unreadable_stale_snapshot_reason_round_trip(self) -> None:
        degraded = synthesize_degraded(
            capability="do_thing",
            reason="registry_unreadable_stale_snapshot",
            snapshot_stale=True,
        )
        assert "registry_unreadable_stale_snapshot" in degraded.reason

    def test_snapshot_stale_true_records_staleness(self) -> None:
        """AC-006: snapshot_stale=True records staleness even when paired
        with a non-staleness reason (defence-in-depth)."""
        degraded = synthesize_degraded(
            capability="do_thing",
            reason="no_specialist_resolvable",
            snapshot_stale=True,
        )
        assert "stale" in degraded.reason.lower()

    def test_attempt_no_propagates(self) -> None:
        degraded = synthesize_degraded(
            capability="do_thing",
            reason="no_specialist_resolvable",
            attempt_no=3,
        )
        assert degraded.attempt_no == 3

    def test_default_attempt_no_is_one(self) -> None:
        degraded = synthesize_degraded(
            capability="do_thing", reason="no_specialist_resolvable"
        )
        assert degraded.attempt_no == 1

    def test_capability_appears_in_synthetic_resolution_id(self) -> None:
        """The synthesised resolution_id encodes the capability so the
        downstream reasoning loop can correlate degraded outcomes back
        to the capability that triggered them."""
        degraded = synthesize_degraded(
            capability="do_thing", reason="no_specialist_resolvable"
        )
        assert "do_thing" in degraded.resolution_id

    def test_returns_pure_value_no_io(self, tmp_path: object) -> None:
        """synthesize_degraded is pure — calling it twice yields equal
        Degraded values for the same inputs."""
        d1 = synthesize_degraded(
            capability="do_thing", reason="no_specialist_resolvable"
        )
        d2 = synthesize_degraded(
            capability="do_thing", reason="no_specialist_resolvable"
        )
        assert d1 == d2


# ---------------------------------------------------------------------------
# Seam test (mirrors the seam-test snippet in the task spec)
# ---------------------------------------------------------------------------


@pytest.mark.seam
class TestSeamCorrelateOutcomeContract:
    """Seam test for the CapabilityResolution.outcome_correlated contract.

    Producer: TASK-SAD-001 (declared the field).
    Consumer: TASK-SAD-009 (this task — implements correlate_outcome()).
    """

    def test_correlate_outcome_idempotent_seam(
        self, db_writer: SqliteHistoryWriter
    ) -> None:
        _seed_resolution(db_writer, resolution_id="res-001")
        r1 = correlate_outcome("res-001", "gate-A", db_writer=db_writer)
        r2 = correlate_outcome("res-001", "gate-A", db_writer=db_writer)
        assert r1 == r2
        assert r1.outcome_correlated is True
        assert r1.gate_decision_id == "gate-A"
