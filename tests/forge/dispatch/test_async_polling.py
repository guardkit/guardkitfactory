"""Tests for ``forge.dispatch.async_polling`` (TASK-SAD-008).

Acceptance criteria coverage map:

* AC-001: ``src/forge/dispatch/async_polling.py`` defines
  :class:`AsyncPollingCoordinator` with ``converge()`` — see
  :class:`TestSurface`.
* AC-002: Each poll dispatches via the orchestrator and does NOT
  bypass any invariant — see
  :class:`TestPollDispatchesViaOrchestrator`.
* AC-003: Polling honours the hard 900s ceiling (ASSUM-003) and
  cumulative time is tracked via the injected :class:`Clock` — see
  :class:`TestCeilingTrackedViaClock`.
* AC-004 (D.async-mode-polling): initial ``AsyncPending`` →
  status-tool reply with ``coach_score`` → :class:`SyncResult`. The
  two are linked via the same ``resolution_id`` — see
  :class:`TestConvergeFromPending`.
* AC-005: status tool keeps replying ``AsyncPending`` →
  :class:`DispatchError` with
  ``error_explanation="async_polling_ceiling_exceeded"`` — see
  :class:`TestRepeatedPendingHitsCeiling`.
* AC-006: status tool replies with an error → polling stops and the
  :class:`DispatchError` propagates (specialist explanation
  preserved) — see :class:`TestStatusToolError`.
* AC-007: lint/format checks (verified outside this module).

The orchestrator dependency is exercised through an in-memory stub
that records every ``dispatch()`` call. The stub never imports a
transport — that's what makes the orchestrator-level invariants the
single source of truth for "did we route through the pipeline?".
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

import pytest

from forge.dispatch.async_polling import (
    CEILING_EXCEEDED_EXPLANATION,
    DEFAULT_MAX_TOTAL_SECONDS,
    AsyncPollingCoordinator,
)
from forge.dispatch.models import (
    AsyncPending,
    Degraded,
    DispatchError,
    DispatchOutcome,
    SyncResult,
)
from forge.dispatch.persistence import DispatchParameter


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class FakeClock:
    """Deterministic UTC :class:`Clock` mirroring the orchestrator-test fake."""

    def __init__(self, start: Optional[datetime] = None) -> None:
        self._now = start or datetime(2026, 4, 25, 12, 0, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now = self._now + timedelta(seconds=seconds)


class StubOrchestrator:
    """In-memory orchestrator stub that scripts dispatch outcomes.

    Records every ``dispatch()`` call so AC-002 can assert that the
    coordinator actually went through ``orchestrator.dispatch`` (and
    therefore through subscribe-before-publish, write-before-send,
    etc.) rather than calling some side-channel.

    Optionally advances an injected :class:`FakeClock` per call so
    ceiling-driven tests can simulate cumulative elapsed time without
    real ``asyncio.sleep`` delays.
    """

    def __init__(
        self,
        outcomes: list[DispatchOutcome],
        *,
        clock: Optional[FakeClock] = None,
        clock_advance_per_call: float = 0.0,
    ) -> None:
        self._outcomes: list[DispatchOutcome] = list(outcomes)
        self._clock = clock
        self._clock_advance_per_call = clock_advance_per_call
        self.calls: list[dict[str, Any]] = []

    async def dispatch(
        self,
        *,
        capability: str,
        parameters: list[DispatchParameter],
        attempt_no: int = 1,
        retry_of: Optional[str] = None,
        intent_pattern: Optional[str] = None,
        build_id: str = "unknown",
        stage_label: str = "unknown",
    ) -> DispatchOutcome:
        self.calls.append(
            {
                "capability": capability,
                "parameters": list(parameters),
                "attempt_no": attempt_no,
                "retry_of": retry_of,
                "intent_pattern": intent_pattern,
                "build_id": build_id,
                "stage_label": stage_label,
            }
        )
        if self._clock is not None and self._clock_advance_per_call:
            self._clock.advance(self._clock_advance_per_call)
        if not self._outcomes:
            raise AssertionError(
                "StubOrchestrator received an unexpected dispatch call — "
                "the coordinator polled more times than the test scripted",
            )
        return self._outcomes.pop(0)


# ---------------------------------------------------------------------------
# AC-001 — module surface
# ---------------------------------------------------------------------------


class TestSurface:
    """AC-001 — module exports the coordinator + ``converge()`` is a coroutine."""

    def test_module_defines_async_polling_coordinator(self) -> None:
        from forge.dispatch import async_polling as module

        assert hasattr(module, "AsyncPollingCoordinator")
        assert hasattr(module, "CEILING_EXCEEDED_EXPLANATION")
        assert hasattr(module, "DEFAULT_MAX_TOTAL_SECONDS")

    def test_default_max_total_seconds_matches_assum_003(self) -> None:
        # ASSUM-003 hard ceiling — must be 900s by default so the
        # polling path honours the same cut-off as sync dispatch.
        assert DEFAULT_MAX_TOTAL_SECONDS == 900.0

    def test_converge_method_is_coroutine(self) -> None:
        assert inspect.iscoroutinefunction(AsyncPollingCoordinator.converge)

    def test_constructor_rejects_non_positive_max_total_seconds(self) -> None:
        with pytest.raises(ValueError):
            AsyncPollingCoordinator(
                orchestrator=StubOrchestrator(outcomes=[]),
                clock=FakeClock(),
                poll_interval_seconds=1.0,
                max_total_seconds=0.0,
            )

    def test_constructor_rejects_negative_poll_interval(self) -> None:
        with pytest.raises(ValueError):
            AsyncPollingCoordinator(
                orchestrator=StubOrchestrator(outcomes=[]),
                clock=FakeClock(),
                poll_interval_seconds=-1.0,
                max_total_seconds=900.0,
            )


# ---------------------------------------------------------------------------
# AC-004 — happy path: AsyncPending → SyncResult, linked resolution_id
# ---------------------------------------------------------------------------


class TestConvergeFromPending:
    """AC-004 — D.async-mode-polling key example."""

    @pytest.mark.asyncio
    async def test_async_pending_then_sync_result_links_via_resolution_id(
        self,
    ) -> None:
        pending = AsyncPending(
            resolution_id="resolution-original",
            attempt_no=2,
            run_identifier="remote-run-42",
        )
        # Status-tool dispatch creates its own persistence row with a
        # different resolution_id; the coordinator must re-stamp the
        # boundary outcome so the reasoning loop sees one logical
        # resolution_id end-to-end.
        status_outcome = SyncResult(
            resolution_id="resolution-status-poll",
            attempt_no=1,
            coach_score=0.92,
            criterion_breakdown={"quality": 0.9},
            detection_findings=["clean"],
        )
        stub = StubOrchestrator(outcomes=[status_outcome])
        coordinator = AsyncPollingCoordinator(
            orchestrator=stub,
            clock=FakeClock(),
            poll_interval_seconds=0.0,
            max_total_seconds=10.0,
        )

        outcome = await coordinator.converge(pending)

        assert isinstance(outcome, SyncResult)
        # AC-004: the two are linked via the same resolution_id.
        assert outcome.resolution_id == pending.resolution_id
        assert outcome.attempt_no == pending.attempt_no
        # Coach fields propagate verbatim from the status-tool reply.
        assert outcome.coach_score == 0.92
        assert outcome.criterion_breakdown == {"quality": 0.9}
        assert outcome.detection_findings == ["clean"]


# ---------------------------------------------------------------------------
# AC-002 — every poll routes through the orchestrator
# ---------------------------------------------------------------------------


class TestPollDispatchesViaOrchestrator:
    """AC-002 — polling must reuse ``orchestrator.dispatch``."""

    @pytest.mark.asyncio
    async def test_each_poll_dispatches_status_capability_with_run_identifier(
        self,
    ) -> None:
        pending = AsyncPending(
            resolution_id="resolution-original",
            attempt_no=1,
            run_identifier="remote-run-99",
        )
        status_outcome = SyncResult(
            resolution_id="resolution-status",
            attempt_no=1,
            coach_score=0.5,
        )
        stub = StubOrchestrator(outcomes=[status_outcome])
        coordinator = AsyncPollingCoordinator(
            orchestrator=stub,
            clock=FakeClock(),
            poll_interval_seconds=0.0,
            max_total_seconds=10.0,
        )

        await coordinator.converge(pending)

        assert len(stub.calls) == 1
        call = stub.calls[0]
        # AC-002: capability is the status tool name (default "status")
        assert call["capability"] == "status"
        # The run_identifier is threaded into the dispatch parameters
        # so the status tool can correlate against the remote run.
        names = [param.name for param in call["parameters"]]
        values = {param.name: param.value for param in call["parameters"]}
        assert "run_identifier" in names
        assert values["run_identifier"] == "remote-run-99"

    @pytest.mark.asyncio
    async def test_status_capability_is_overridable(self) -> None:
        pending = AsyncPending(
            resolution_id="resolution-original",
            attempt_no=1,
            run_identifier="remote-run-99",
        )
        status_outcome = SyncResult(
            resolution_id="resolution-status",
            attempt_no=1,
            coach_score=0.4,
        )
        stub = StubOrchestrator(outcomes=[status_outcome])
        coordinator = AsyncPollingCoordinator(
            orchestrator=stub,
            clock=FakeClock(),
            poll_interval_seconds=0.0,
            max_total_seconds=10.0,
        )

        await coordinator.converge(pending, status_capability="run_status")

        assert stub.calls[0]["capability"] == "run_status"

    @pytest.mark.asyncio
    async def test_subsequent_pending_uses_latest_run_identifier(self) -> None:
        """Each poll passes the freshest run_identifier, not the original.

        Some specialists rotate the run identifier across polls. The
        coordinator forwards the latest pending's identifier so the
        status tool always sees the canonical handle.
        """
        pending = AsyncPending(
            resolution_id="resolution-original",
            attempt_no=1,
            run_identifier="remote-run-1",
        )
        rotated_pending = AsyncPending(
            resolution_id="resolution-status-1",
            attempt_no=1,
            run_identifier="remote-run-2",
        )
        final = SyncResult(
            resolution_id="resolution-status-2",
            attempt_no=1,
            coach_score=0.7,
        )
        stub = StubOrchestrator(outcomes=[rotated_pending, final])
        coordinator = AsyncPollingCoordinator(
            orchestrator=stub,
            clock=FakeClock(),
            poll_interval_seconds=0.0,
            max_total_seconds=10.0,
        )

        outcome = await coordinator.converge(pending)

        assert isinstance(outcome, SyncResult)
        assert outcome.resolution_id == pending.resolution_id
        assert len(stub.calls) == 2
        # First poll uses the original run_identifier.
        first_params = {p.name: p.value for p in stub.calls[0]["parameters"]}
        assert first_params["run_identifier"] == "remote-run-1"
        # Second poll uses the rotated identifier from the first reply.
        second_params = {p.name: p.value for p in stub.calls[1]["parameters"]}
        assert second_params["run_identifier"] == "remote-run-2"


# ---------------------------------------------------------------------------
# AC-005 — repeated pending hits the ceiling
# ---------------------------------------------------------------------------


class TestRepeatedPendingHitsCeiling:
    """AC-005 — repeated AsyncPending → DispatchError(ceiling_exceeded)."""

    @pytest.mark.asyncio
    async def test_repeated_pending_yields_async_polling_ceiling_exceeded(
        self,
    ) -> None:
        pending = AsyncPending(
            resolution_id="resolution-original",
            attempt_no=1,
            run_identifier="remote-run-42",
        )
        # Status tool always says "still pending". We script enough
        # outcomes that the test would explode if the ceiling check
        # ever broke.
        rotating_pending = [
            AsyncPending(
                resolution_id=f"resolution-status-{i}",
                attempt_no=1,
                run_identifier="remote-run-42",
            )
            for i in range(50)
        ]
        clock = FakeClock()
        # Each dispatch call advances the clock by 100s. Ceiling = 250s,
        # so after the third dispatch (clock=300s) the next ceiling
        # check fires.
        stub = StubOrchestrator(
            outcomes=rotating_pending,
            clock=clock,
            clock_advance_per_call=100.0,
        )
        coordinator = AsyncPollingCoordinator(
            orchestrator=stub,
            clock=clock,
            poll_interval_seconds=0.0,
            max_total_seconds=250.0,
        )

        outcome = await coordinator.converge(pending)

        assert isinstance(outcome, DispatchError)
        assert outcome.error_explanation == CEILING_EXCEEDED_EXPLANATION
        assert outcome.error_explanation == "async_polling_ceiling_exceeded"
        # AC-004 linkage: error carries the original resolution_id.
        assert outcome.resolution_id == pending.resolution_id
        assert outcome.attempt_no == pending.attempt_no
        # Polling stopped — not all 50 scripted pendings were consumed.
        assert len(stub.calls) < 50


# ---------------------------------------------------------------------------
# AC-006 — status-tool error stops polling
# ---------------------------------------------------------------------------


class TestStatusToolError:
    """AC-006 — status-tool error → DispatchError emitted, polling stops."""

    @pytest.mark.asyncio
    async def test_status_tool_error_stops_polling_after_one_call(self) -> None:
        pending = AsyncPending(
            resolution_id="resolution-original",
            attempt_no=3,
            run_identifier="remote-run-42",
        )
        status_error = DispatchError(
            resolution_id="resolution-status",
            attempt_no=1,
            error_explanation="specialist failed: invalid run_identifier",
        )
        # Script extra outcomes: any consumed call beyond the first
        # would prove polling did NOT stop on the error.
        stub = StubOrchestrator(outcomes=[status_error, status_error])
        coordinator = AsyncPollingCoordinator(
            orchestrator=stub,
            clock=FakeClock(),
            poll_interval_seconds=0.0,
            max_total_seconds=10.0,
        )

        outcome = await coordinator.converge(pending)

        assert isinstance(outcome, DispatchError)
        # Specialist's error explanation is preserved verbatim — the
        # coordinator does not paper over a real failure with a
        # ceiling-style summary.
        assert outcome.error_explanation == (
            "specialist failed: invalid run_identifier"
        )
        # Re-stamped to the converge-caller's resolution_id (AC-004).
        assert outcome.resolution_id == pending.resolution_id
        assert outcome.attempt_no == pending.attempt_no
        # Polling stopped after the first error.
        assert len(stub.calls) == 1


# ---------------------------------------------------------------------------
# AC-003 — Clock drives the ceiling check
# ---------------------------------------------------------------------------


class TestCeilingTrackedViaClock:
    """AC-003 — cumulative time is tracked via the injected Clock."""

    @pytest.mark.asyncio
    async def test_ceiling_does_not_fire_when_clock_does_not_advance(
        self,
    ) -> None:
        """If the Clock never advances, the cumulative-time check
        never trips — proving the ceiling depends on the *injected*
        clock, not on real wall-clock time.
        """
        pending = AsyncPending(
            resolution_id="resolution-original",
            attempt_no=1,
            run_identifier="remote-run-42",
        )
        # Final result arrives on the third poll; if the ceiling were
        # tied to wall-clock time the test machine could spuriously
        # trip it. Frozen Clock proves the ceiling is Clock-driven.
        outcomes: list[DispatchOutcome] = [
            AsyncPending(
                resolution_id="resolution-status-1",
                attempt_no=1,
                run_identifier="remote-run-42",
            ),
            AsyncPending(
                resolution_id="resolution-status-2",
                attempt_no=1,
                run_identifier="remote-run-42",
            ),
            SyncResult(
                resolution_id="resolution-status-3",
                attempt_no=1,
                coach_score=0.8,
            ),
        ]
        frozen_clock = FakeClock()
        stub = StubOrchestrator(
            outcomes=outcomes,
            clock=frozen_clock,
            clock_advance_per_call=0.0,  # Clock NEVER advances.
        )
        coordinator = AsyncPollingCoordinator(
            orchestrator=stub,
            clock=frozen_clock,
            poll_interval_seconds=0.0,
            max_total_seconds=0.001,  # Tiny ceiling — would trip on real time.
        )

        outcome = await coordinator.converge(pending)

        assert isinstance(outcome, SyncResult)
        assert outcome.resolution_id == pending.resolution_id
        assert len(stub.calls) == 3

    @pytest.mark.asyncio
    async def test_ceiling_fires_at_expected_clock_elapsed_time(self) -> None:
        """The ceiling is keyed against the Clock's cumulative delta,
        not the count of polls — advance by exactly the ceiling and
        the next iteration's pre-dispatch check fires.
        """
        pending = AsyncPending(
            resolution_id="resolution-original",
            attempt_no=1,
            run_identifier="remote-run-42",
        )
        rotating_pending = [
            AsyncPending(
                resolution_id=f"resolution-status-{i}",
                attempt_no=1,
                run_identifier="remote-run-42",
            )
            for i in range(20)
        ]
        clock = FakeClock()
        # Advance by exactly the ceiling each call. After the first
        # dispatch the elapsed delta equals max_total_seconds, so the
        # next pre-dispatch check fires.
        stub = StubOrchestrator(
            outcomes=rotating_pending,
            clock=clock,
            clock_advance_per_call=900.0,
        )
        coordinator = AsyncPollingCoordinator(
            orchestrator=stub,
            clock=clock,
            poll_interval_seconds=0.0,
            max_total_seconds=900.0,
        )

        outcome = await coordinator.converge(pending)

        assert isinstance(outcome, DispatchError)
        assert outcome.error_explanation == CEILING_EXCEEDED_EXPLANATION
        # Exactly one dispatch happened: it consumed the full budget,
        # then the next iteration's check fired before re-dispatching.
        assert len(stub.calls) == 1


# ---------------------------------------------------------------------------
# Outcome-passthrough edge cases (Degraded)
# ---------------------------------------------------------------------------


class TestDegradedOutcomePassthrough:
    """Degraded status replies surface to the reasoning loop unchanged.

    Degraded means the *status* capability could not be resolved on
    this fleet — a useful signal that the reasoning loop should see
    rather than have papered over by the polling layer.
    """

    @pytest.mark.asyncio
    async def test_degraded_status_outcome_is_returned_with_restamped_resolution_id(
        self,
    ) -> None:
        pending = AsyncPending(
            resolution_id="resolution-original",
            attempt_no=1,
            run_identifier="remote-run-42",
        )
        degraded = Degraded(
            resolution_id="resolution-status",
            attempt_no=1,
            reason="no_specialist_resolvable",
        )
        stub = StubOrchestrator(outcomes=[degraded])
        coordinator = AsyncPollingCoordinator(
            orchestrator=stub,
            clock=FakeClock(),
            poll_interval_seconds=0.0,
            max_total_seconds=10.0,
        )

        outcome = await coordinator.converge(pending)

        assert isinstance(outcome, Degraded)
        assert outcome.resolution_id == pending.resolution_id
        assert outcome.reason == "no_specialist_resolvable"
        assert len(stub.calls) == 1
