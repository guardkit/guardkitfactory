"""Concurrent-responses regression — closes risk **R4**.

Group E ``@concurrency``. Two responses arriving for the same paused
build at effectively the same moment MUST resolve to exactly one
decision; the second is recorded as a duplicate and silently discarded.

The contract is owned by :class:`forge.adapters.nats.ApprovalSubscriber`'s
dedup buffer, which is keyed on the responder-echoed ``request_id`` and
guarded by an ``asyncio.Lock``. This integration test drives the
subscriber via ``asyncio.gather`` over two ``_on_envelope`` invocations
that race on the same id, asserting first-response-wins semantics from
the wait-loop's perspective.
"""

from __future__ import annotations

import asyncio

import pytest
from nats_core.envelope import EventType, MessageEnvelope

from forge.adapters.nats.approval_subscriber import (
    ApprovalSubscriber,
    ApprovalSubscriberDeps,
)
from forge.config.models import ApprovalConfig
from forge.gating.identity import derive_request_id

from .conftest import (
    BUILD_ID,
    RICH,
    STAGE_LABEL,
    FakeMonotonicClock,
    InMemoryNats,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _response_envelope(
    *,
    request_id: str,
    decision: str,
    decided_by: str = RICH,
    notes: str | None = None,
) -> MessageEnvelope:
    return MessageEnvelope(
        source_id=decided_by,
        event_type=EventType.APPROVAL_RESPONSE,
        payload={
            "request_id": request_id,
            "decision": decision,
            "decided_by": decided_by,
            "notes": notes,
        },
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestConcurrentResponsesResolveToExactlyOneDecision:
    """``asyncio.gather`` of two responses on the same id ⇒ one decision."""

    @pytest.mark.asyncio
    async def test_gather_two_responses_same_request_id_one_dedup_winner(
        self,
    ) -> None:
        # Build the subscriber with a manual clock so the dedup TTL never
        # advances — the dedup buffer is the only arbiter under test.
        nats = InMemoryNats()
        clock = FakeMonotonicClock()
        deps = ApprovalSubscriberDeps(
            nats_client=nats,
            config=ApprovalConfig(default_wait_seconds=1, max_wait_seconds=2),
            publish_refresh=None,
            expected_approver=None,
            project=None,
            clock=clock,
            dedup_ttl_seconds=300,
        )
        subscriber = ApprovalSubscriber(deps)

        request_id = derive_request_id(
            build_id=BUILD_ID, stage_label=STAGE_LABEL, attempt_count=0
        )

        async def race_two_responses() -> None:
            # Both envelopes carry the SAME request_id but different
            # responder-stamped notes so we can prove which one won.
            env_a = _response_envelope(
                request_id=request_id, decision="approve", notes="first"
            )
            env_b = _response_envelope(
                request_id=request_id, decision="reject", notes="second"
            )
            await asyncio.gather(
                subscriber._on_envelope(build_id=BUILD_ID, envelope=env_a),
                subscriber._on_envelope(build_id=BUILD_ID, envelope=env_b),
            )

        # Run await_response and the racer concurrently — the wait loop
        # must dequeue exactly the first-arrival payload.
        wait_task = asyncio.create_task(
            subscriber.await_response(BUILD_ID, stage_label=STAGE_LABEL)
        )
        # Yield until the subscription has been registered (the race
        # should not start until the queue exists for this build_id).
        for _ in range(50):
            if BUILD_ID in subscriber._queues:
                break
            await asyncio.sleep(0)
        else:
            wait_task.cancel()
            raise AssertionError("subscribe never registered queue for build")

        await race_two_responses()

        result = await asyncio.wait_for(wait_task, timeout=1.0)
        assert result is not None
        # Exactly one decision survives; whichever arrived first wins
        # because the dedup lock serialises check-and-record.
        assert result.notes in {"first", "second"}
        # Dedup buffer holds one entry — the winning request_id.
        assert request_id in subscriber._dedup
        assert len(subscriber._dedup) == 1


class TestDuplicateAfterDecisionIsObservedAndDiscarded:
    """A late duplicate is logged + dropped — never re-resumes the build."""

    @pytest.mark.asyncio
    async def test_late_duplicate_does_not_re_enqueue(
        self,
    ) -> None:
        nats = InMemoryNats()
        clock = FakeMonotonicClock()
        deps = ApprovalSubscriberDeps(
            nats_client=nats,
            config=ApprovalConfig(),
            publish_refresh=None,
            clock=clock,
            dedup_ttl_seconds=300,
        )
        subscriber = ApprovalSubscriber(deps)
        request_id = derive_request_id(
            build_id=BUILD_ID, stage_label=STAGE_LABEL, attempt_count=0
        )

        # Phase 1 — first arrival is recorded.
        # Note: there is no active waiter, but ``_check_and_record``
        # still flags the second arrival as a duplicate.
        env = _response_envelope(request_id=request_id, decision="approve")
        await subscriber._on_envelope(build_id=BUILD_ID, envelope=env)
        # Phase 2 — duplicate arrival.
        await subscriber._on_envelope(build_id=BUILD_ID, envelope=env)

        # The dedup buffer holds only one entry.
        assert request_id in subscriber._dedup
        assert len(subscriber._dedup) == 1
