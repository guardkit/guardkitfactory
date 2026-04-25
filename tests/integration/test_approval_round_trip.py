"""End-to-end approval round-trip across the in-memory NATS double.

Group A ``@key-example @smoke`` for FEAT-FORGE-004 / TASK-CGCP-011.
Covers every documented terminal path through :func:`forge.gating.gate_check`:

* ``AUTO_APPROVE`` — no pause, no publish, build continues.
* ``FLAG_FOR_REVIEW`` → pause → ``approve`` → resume.
* ``HARD_STOP`` — state machine transitions to FAILED, no pause/publish.
* ``FLAG_FOR_REVIEW`` → pause → ``override`` → continue with stage marked overridden.
* ``FLAG_FOR_REVIEW`` → pause → ``reject`` → cancel.

Each round-trip uses the real :class:`ApprovalPublisher` and
:class:`ApprovalSubscriber` against the in-memory NATS double provided
by ``conftest.py`` so the publisher subject resolution, the subscriber
subject resolution, the dedup gate, and the wrapper's branch logic are
all exercised together.
"""

from __future__ import annotations

import asyncio

import pytest

from forge.gating.identity import derive_request_id
from forge.gating.models import GateMode
from forge.gating.wrappers import GateOutcome, gate_check

from .conftest import (
    BUILD_ID,
    FEATURE_ID,
    STAGE_LABEL,
    InMemoryNats,
    build_gate_check_deps,
)


# ---------------------------------------------------------------------------
# Helper — wait for the subscriber to register, then deliver a response
# ---------------------------------------------------------------------------


async def _drive_response(
    nats: InMemoryNats,
    *,
    build_id: str,
    request_id: str,
    decision: str,
    notes: str | None = None,
    timeout: float = 1.0,
) -> None:
    """Yield until the subscriber callback is live, then deliver the response.

    The wrapper's pause path is: publish-request → await_response. The
    subscription is registered *inside* ``await_response`` so the test
    driver must wait for it before publishing on the mirror subject —
    otherwise the response lands with no callback and silently drops.
    """
    subject = f"agents.approval.forge.{build_id}.response"
    deadline = asyncio.get_event_loop().time() + timeout
    while not nats.subscribers.get(subject):
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(
                f"Subscriber for {subject!r} never registered within "
                f"{timeout}s — gate_check is stuck before await_response"
            )
        await asyncio.sleep(0)
    await nats.deliver_response(
        build_id=build_id,
        request_id=request_id,
        decision=decision,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# AC-001 — auto-approve happy path
# ---------------------------------------------------------------------------


class TestAutoApproveRoundTrip:
    """Group A smoke: AUTO_APPROVE bypasses the bus entirely."""

    @pytest.mark.asyncio
    async def test_auto_approve_records_decision_does_not_publish_or_pause(
        self, nats: InMemoryNats
    ) -> None:
        deps, _, repo, sm, _, _ = build_gate_check_deps(
            nats=nats, mode=GateMode.AUTO_APPROVE, threshold=0.85
        )

        outcome, decision = await gate_check(
            deps=deps,
            build_id=BUILD_ID,
            feature_id=FEATURE_ID,
            stage_label=STAGE_LABEL,
            target_kind="local_tool",
            target_identifier="write_file",
            coach_score=0.92,
            criterion_breakdown={"completeness": 0.9},
            detection_findings=[],
        )

        assert outcome is GateOutcome.AUTO_APPROVED
        assert decision.mode is GateMode.AUTO_APPROVE
        # Decision was persisted (SQLite is the source of truth).
        assert repo.decisions == [decision]
        # No transitions, no publish, no subscription.
        assert sm.paused == sm.failed == sm.cancelled == []
        assert sm.running == []
        assert nats.published == {}
        assert nats.subscribers == {}


# ---------------------------------------------------------------------------
# Pause-approve-resume — the core happy path the AC headlines
# ---------------------------------------------------------------------------


class TestFlagForReviewApproveRoundTrip:
    """Group A smoke: pause → approve → resume drives RUNNING transition."""

    @pytest.mark.asyncio
    async def test_pause_then_approve_resumes_build_to_running(
        self, nats: InMemoryNats
    ) -> None:
        deps, _, repo, sm, _, _ = build_gate_check_deps(
            nats=nats, mode=GateMode.FLAG_FOR_REVIEW
        )
        request_id = derive_request_id(
            build_id=BUILD_ID, stage_label=STAGE_LABEL, attempt_count=0
        )

        gate_task = asyncio.create_task(
            gate_check(
                deps=deps,
                build_id=BUILD_ID,
                feature_id=FEATURE_ID,
                stage_label=STAGE_LABEL,
                target_kind="local_tool",
                target_identifier="t",
                coach_score=0.7,
                criterion_breakdown={"c": 0.7},
                detection_findings=[],
            )
        )
        await _drive_response(
            nats,
            build_id=BUILD_ID,
            request_id=request_id,
            decision="approve",
        )
        outcome, _ = await asyncio.wait_for(gate_task, timeout=1.0)

        assert outcome is GateOutcome.RESUMED
        # Approval-request envelope landed on the canonical subject.
        request_subject = f"agents.approval.forge.{BUILD_ID}"
        assert request_subject in nats.published
        assert len(nats.published[request_subject]) == 1
        # State machine: PAUSED → RUNNING
        assert sm.paused == [(BUILD_ID, STAGE_LABEL)]
        assert sm.running == [BUILD_ID]
        assert repo.resumed == [(BUILD_ID, STAGE_LABEL)]


# ---------------------------------------------------------------------------
# Hard stop — never publishes
# ---------------------------------------------------------------------------


class TestHardStopRoundTrip:
    """Group A: HARD_STOP transitions to FAILED with no bus traffic."""

    @pytest.mark.asyncio
    async def test_hard_stop_transitions_to_failed_no_bus_traffic(
        self, nats: InMemoryNats
    ) -> None:
        deps, _, _, sm, _, _ = build_gate_check_deps(
            nats=nats, mode=GateMode.HARD_STOP, threshold=0.85
        )

        outcome, _ = await gate_check(
            deps=deps,
            build_id=BUILD_ID,
            feature_id=FEATURE_ID,
            stage_label=STAGE_LABEL,
            target_kind="local_tool",
            target_identifier="t",
            coach_score=None,  # degraded mode allows HARD_STOP
            criterion_breakdown={"c": 0.5},
            detection_findings=[],
        )

        assert outcome is GateOutcome.FAILED
        assert sm.failed and sm.failed[0][0] == BUILD_ID
        # No publish — HARD_STOP skips the pause-and-publish path.
        assert nats.published == {}
        assert nats.subscribers == {}


# ---------------------------------------------------------------------------
# Override — stage marked overridden, build continues
# ---------------------------------------------------------------------------


class TestOverrideRoundTrip:
    """Group A: pause → override → state-machine RUNNING + repo.overridden."""

    @pytest.mark.asyncio
    async def test_override_marks_stage_overridden_and_resumes(
        self, nats: InMemoryNats
    ) -> None:
        deps, _, repo, sm, _, _ = build_gate_check_deps(
            nats=nats, mode=GateMode.FLAG_FOR_REVIEW
        )
        request_id = derive_request_id(
            build_id=BUILD_ID, stage_label=STAGE_LABEL, attempt_count=0
        )

        gate_task = asyncio.create_task(
            gate_check(
                deps=deps,
                build_id=BUILD_ID,
                feature_id=FEATURE_ID,
                stage_label=STAGE_LABEL,
                target_kind="local_tool",
                target_identifier="t",
                coach_score=0.7,
                criterion_breakdown={"c": 0.7},
                detection_findings=[],
            )
        )
        await _drive_response(
            nats,
            build_id=BUILD_ID,
            request_id=request_id,
            decision="override",
            notes="ship it",
        )
        outcome, _ = await asyncio.wait_for(gate_task, timeout=1.0)

        assert outcome is GateOutcome.OVERRIDDEN
        assert repo.overridden == [(BUILD_ID, STAGE_LABEL, "ship it")]
        # Override path also moves the state machine back to RUNNING.
        assert sm.running == [BUILD_ID]


# ---------------------------------------------------------------------------
# Reject — paused build is cancelled
# ---------------------------------------------------------------------------


class TestRejectRoundTrip:
    """Group A: pause → reject → state-machine CANCELLED."""

    @pytest.mark.asyncio
    async def test_reject_cancels_build_with_responder_notes(
        self, nats: InMemoryNats
    ) -> None:
        deps, _, repo, sm, _, _ = build_gate_check_deps(
            nats=nats, mode=GateMode.FLAG_FOR_REVIEW
        )
        request_id = derive_request_id(
            build_id=BUILD_ID, stage_label=STAGE_LABEL, attempt_count=0
        )

        gate_task = asyncio.create_task(
            gate_check(
                deps=deps,
                build_id=BUILD_ID,
                feature_id=FEATURE_ID,
                stage_label=STAGE_LABEL,
                target_kind="local_tool",
                target_identifier="t",
                coach_score=0.7,
                criterion_breakdown={"c": 0.7},
                detection_findings=[],
            )
        )
        await _drive_response(
            nats,
            build_id=BUILD_ID,
            request_id=request_id,
            decision="reject",
            notes="not safe",
        )
        outcome, _ = await asyncio.wait_for(gate_task, timeout=1.0)

        assert outcome is GateOutcome.CANCELLED
        assert sm.cancelled == [(BUILD_ID, "not safe")]
        assert repo.cancelled == [(BUILD_ID, "not safe")]
