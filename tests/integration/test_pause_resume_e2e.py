"""End-to-end pause/resume publish round-trip — TASK-FW10-010 (Group D).

Validates the lifecycle:

    autobuild_runner._update_state(awaiting_approval)
        → publish ``pipeline.build-paused.<feature_id>``
    daemon restart (simulated by re-instantiating the adapter +
    re-emitting from a rehydrated paused snapshot)
        → re-publish ``pipeline.build-paused.<feature_id>`` with the
          SAME correlation_id
    approval response arrives via the subscriber
        → publish ``pipeline.build-resumed.<feature_id>`` BEFORE the
          orchestrator advances
    second approval response (concurrent or duplicate)
        → no-op (FEAT-FORGE-004 first-wins)

This is the integration counterpart to
``tests/forge/test_pause_resume_publish.py`` — it exercises both call
sites in one continuous flow against the real publisher.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest

from forge.adapters.nats import PipelinePublisher
from forge.adapters.nats.approval_subscriber import (
    ApprovalSubscriber,
    ApprovalSubscriberDeps,
)
from forge.config.models import ApprovalConfig, PipelineConfig
from forge.pipeline import BuildContext, PipelineLifecycleEmitter
from forge.subagents.autobuild_runner import (
    AutobuildState,
    LifecycleEmitterAdapter,
    _update_state,
)
from nats_core.envelope import EventType, MessageEnvelope
from nats_core.events import ApprovalResponsePayload

FEATURE_ID = "FEAT-PAUSE-RESUME"
BUILD_ID = "build-FEAT-PAUSE-RESUME-20260502120000"
CORRELATION_ID = "corr-pause-resume"


async def _drain_loop_tasks() -> None:
    """Yield control until all currently-pending tasks complete.

    The :class:`LifecycleEmitterAdapter` schedules emit coroutines via
    :meth:`asyncio.AbstractEventLoop.create_task` when a running loop is
    present (the integration scenario). Tests must yield enough times to
    let the chained awaits inside ``_safe_publish → publish_method →
    _publish_envelope`` reach the wire-level publish before assertions
    fire. Five iterations covers the deepest await chain produced today.
    """
    for _ in range(8):
        await asyncio.sleep(0)


@dataclass
class _CapturingNats:
    published: list[tuple[str, bytes]] = field(default_factory=list)

    async def publish(self, subject: str, body: bytes) -> None:
        self.published.append((subject, body))


class _FakeSubscribeClient:
    async def subscribe(self, topic: str, callback: Any) -> Any:  # noqa: ARG002
        class _Sub:
            async def unsubscribe(self) -> None:
                return None

        return _Sub()


def _make_state(**overrides: Any) -> AutobuildState:
    base: dict[str, Any] = {
        "task_id": "task-001",
        "build_id": BUILD_ID,
        "feature_id": FEATURE_ID,
        "lifecycle": "running_wave",
        "correlation_id": CORRELATION_ID,
    }
    base.update(overrides)
    return AutobuildState(**base)


def _make_ctx() -> BuildContext:
    return BuildContext(
        feature_id=FEATURE_ID,
        build_id=BUILD_ID,
        correlation_id=CORRELATION_ID,
        wave_total=3,
    )


def _build_emitter() -> tuple[PipelineLifecycleEmitter, _CapturingNats]:
    nc = _CapturingNats()
    publisher = PipelinePublisher(nc)
    emitter = PipelineLifecycleEmitter(
        publisher, PipelineConfig(progress_interval_seconds=60)
    )
    return emitter, nc


def _approval_response_envelope(
    *,
    request_id: str,
    decision: str = "approve",
    decided_by: str = "rich",
    correlation_id: str = CORRELATION_ID,
) -> MessageEnvelope:
    payload = ApprovalResponsePayload(
        request_id=request_id,
        decision=decision,  # type: ignore[arg-type]
        decided_by=decided_by,
        notes=None,
    )
    return MessageEnvelope(
        source_id="rich",
        event_type=EventType.APPROVAL_RESPONSE,
        correlation_id=correlation_id,
        payload=payload.model_dump(mode="json"),
    )


# ---------------------------------------------------------------------------
# Group D end-to-end scenario
# ---------------------------------------------------------------------------


class TestPauseResumeRoundTrip:
    """The full pause → restart → resume flow against real publishers."""

    @pytest.mark.asyncio
    async def test_pause_restart_resume_round_trip(self) -> None:
        """Pause → re-emit on restart → resume on first approval."""
        emitter, nc = _build_emitter()
        ctx = _make_ctx()

        # ----- Phase 1: initial pause -----
        adapter = LifecycleEmitterAdapter(emitter, ctx)
        state = _make_state(lifecycle="running_wave")
        state = _update_state(
            state,
            lifecycle="awaiting_approval",
            emitter=adapter,
            waiting_for="approval:Implementation Review",
        )
        await _drain_loop_tasks()

        paused_publishes_phase1 = [
            (s, b) for s, b in nc.published if "build-paused" in s
        ]
        assert len(paused_publishes_phase1) == 1
        assert paused_publishes_phase1[0][0] == (
            f"pipeline.build-paused.{FEATURE_ID}"
        )
        env1 = MessageEnvelope.model_validate_json(
            paused_publishes_phase1[0][1].decode("utf-8")
        )
        assert env1.correlation_id == CORRELATION_ID

        # ----- Phase 2: simulated daemon restart -----
        # A new adapter instance with the SAME emitter mimics what the
        # boot-time recovery hook does after rehydrating the paused
        # snapshot. The correlation_id and feature_id are reused
        # verbatim — re-emission must NOT mint a fresh correlation
        # (Group D scenario; ADR-ARCH-021).
        post_restart_adapter = LifecycleEmitterAdapter(emitter, ctx)
        # The rehydrated state is still awaiting_approval; calling
        # _update_state with the same lifecycle re-fires the pause
        # publish (re-emit from the recovery hook).
        rehydrated = _make_state(
            lifecycle="awaiting_approval",
            waiting_for="approval:Implementation Review",
        )
        _update_state(
            rehydrated,
            lifecycle="awaiting_approval",
            emitter=post_restart_adapter,
            waiting_for="approval:Implementation Review",
        )
        await _drain_loop_tasks()

        paused_publishes_total = [
            (s, b) for s, b in nc.published if "build-paused" in s
        ]
        assert len(paused_publishes_total) == 2, (
            "Group D: paused build SURVIVES restart and re-emits "
            f"build-paused with the same correlation. Got {paused_publishes_total}"
        )
        env2 = MessageEnvelope.model_validate_json(
            paused_publishes_total[1][1].decode("utf-8")
        )
        assert env2.correlation_id == CORRELATION_ID, (
            "ADR-ARCH-021: re-emit MUST reuse the original correlation_id"
        )

        # ----- Phase 3: approval response arrives -----
        deps = ApprovalSubscriberDeps(
            nats_client=_FakeSubscribeClient(),
            config=ApprovalConfig(
                default_wait_seconds=60, max_wait_seconds=60
            ),
        )
        sub = ApprovalSubscriber(deps)
        # Register publish ctx as await_response would.
        sub._resume_publish_ctx[BUILD_ID] = (  # type: ignore[attr-defined]
            emitter,
            ctx,
            CORRELATION_ID,
            "implementation",
        )
        queue: asyncio.Queue = asyncio.Queue()
        sub._queues[BUILD_ID] = queue  # type: ignore[attr-defined]

        await sub._on_envelope(  # type: ignore[attr-defined]
            build_id=BUILD_ID,
            envelope=_approval_response_envelope(request_id="req-1"),
        )

        resumed_publishes = [
            s for s, _ in nc.published if "build-resumed" in s
        ]
        assert resumed_publishes == [
            f"pipeline.build-resumed.{FEATURE_ID}"
        ], f"Expected one build-resumed, got {resumed_publishes}"

        # ----- Phase 4: second approval is dropped -----
        await sub._on_envelope(  # type: ignore[attr-defined]
            build_id=BUILD_ID,
            envelope=_approval_response_envelope(request_id="req-1"),
        )

        resumed_after_second = [
            s for s, _ in nc.published if "build-resumed" in s
        ]
        assert len(resumed_after_second) == 1, (
            "FEAT-FORGE-004 first-wins: a second matching response "
            "MUST NOT publish a second build-resumed envelope."
        )

    @pytest.mark.asyncio
    async def test_only_first_approval_advances_orchestrator(self) -> None:
        """Two concurrent valid responses → exactly one queue entry, one publish."""
        emitter, nc = _build_emitter()
        ctx = _make_ctx()

        deps = ApprovalSubscriberDeps(
            nats_client=_FakeSubscribeClient(),
            config=ApprovalConfig(
                default_wait_seconds=60, max_wait_seconds=60
            ),
        )
        sub = ApprovalSubscriber(deps)
        sub._resume_publish_ctx[BUILD_ID] = (  # type: ignore[attr-defined]
            emitter,
            ctx,
            CORRELATION_ID,
            "implementation",
        )
        queue: asyncio.Queue = asyncio.Queue()
        sub._queues[BUILD_ID] = queue  # type: ignore[attr-defined]

        # Two concurrent envelopes with the same request_id.
        env = _approval_response_envelope(request_id="req-1")
        await asyncio.gather(
            sub._on_envelope(  # type: ignore[attr-defined]
                build_id=BUILD_ID, envelope=env
            ),
            sub._on_envelope(  # type: ignore[attr-defined]
                build_id=BUILD_ID, envelope=env
            ),
        )

        resumed = [s for s, _ in nc.published if "build-resumed" in s]
        assert len(resumed) == 1
        assert queue.qsize() == 1
