"""Per-build response routing — Group D ``@edge-case``.

The contract under test: two paused builds running concurrently must
receive responses **only** on their own mirror subjects. A response
published on build A's mirror must not resume build B (and vice versa).
The protocol enforces this via per-build subjects:
``agents.approval.forge.{build_id}.response``. The subscriber
:meth:`ApprovalSubscriber.await_response` opens its subscription on the
mirror subject for its specific ``build_id``; the in-memory NATS double
respects the subject keying so cross-build delivery is impossible.

This integration test runs two real subscribers concurrently against
the in-memory bus and asserts that delivering a response on subject A
resolves the wait on A — not on B.
"""

from __future__ import annotations

import asyncio

import pytest

from forge.adapters.nats.approval_subscriber import (
    APPROVAL_SUBJECT_PREFIX,
    ApprovalSubscriber,
    ApprovalSubscriberDeps,
)
from forge.config.models import ApprovalConfig
from forge.gating.identity import derive_request_id

from .conftest import (
    BUILD_ID,
    OTHER_BUILD_ID,
    STAGE_LABEL,
    FakeMonotonicClock,
    InMemoryNats,
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPerBuildRoutingIsolatesResponses:
    """A response on subject A never resolves a wait on subject B."""

    @pytest.mark.asyncio
    async def test_response_on_build_a_does_not_resolve_wait_on_build_b(
        self,
    ) -> None:
        nats = InMemoryNats()
        clock = FakeMonotonicClock()
        # Two independent subscriber instances — one per build.
        deps_a = ApprovalSubscriberDeps(
            nats_client=nats,
            config=ApprovalConfig(default_wait_seconds=1, max_wait_seconds=2),
            publish_refresh=None,
            clock=clock,
        )
        deps_b = ApprovalSubscriberDeps(
            nats_client=nats,
            config=ApprovalConfig(default_wait_seconds=1, max_wait_seconds=2),
            publish_refresh=None,
            clock=clock,
        )
        sub_a = ApprovalSubscriber(deps_a)
        sub_b = ApprovalSubscriber(deps_b)

        rid_a = derive_request_id(
            build_id=BUILD_ID, stage_label=STAGE_LABEL, attempt_count=0
        )
        rid_b = derive_request_id(
            build_id=OTHER_BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=0,
        )

        wait_a = asyncio.create_task(
            sub_a.await_response(BUILD_ID, stage_label=STAGE_LABEL)
        )
        wait_b = asyncio.create_task(
            sub_b.await_response(OTHER_BUILD_ID, stage_label=STAGE_LABEL)
        )

        # Yield until both subscriptions are registered.
        sub_a_subject = f"{APPROVAL_SUBJECT_PREFIX}.{BUILD_ID}.response"
        sub_b_subject = f"{APPROVAL_SUBJECT_PREFIX}.{OTHER_BUILD_ID}.response"
        for _ in range(50):
            if (
                nats.subscribers.get(sub_a_subject)
                and nats.subscribers.get(sub_b_subject)
            ):
                break
            await asyncio.sleep(0)

        # Deliver only on build A's subject.
        await nats.deliver_response(
            build_id=BUILD_ID, request_id=rid_a, decision="approve"
        )

        result_a = await asyncio.wait_for(wait_a, timeout=1.0)
        assert result_a is not None
        assert result_a.request_id == rid_a

        # Build B's wait is still pending because no response landed
        # on its subject.
        assert not wait_b.done(), (
            "build B's wait resolved despite the response landing on "
            "build A's subject — per-build routing violated"
        )
        # Cancel + drain to satisfy the test runner. We deliberately
        # cancel rather than deliver a real response — the assertion
        # is that delivery to A did NOT resolve B.
        wait_b.cancel()
        with pytest.raises(asyncio.CancelledError):
            await wait_b

    @pytest.mark.asyncio
    async def test_two_responses_each_resolve_only_their_own_wait(
        self,
    ) -> None:
        # Bidirectional confirmation: deliver to BOTH subjects and
        # observe each wait resolves with its own request_id.
        nats = InMemoryNats()
        clock = FakeMonotonicClock()
        deps_a = ApprovalSubscriberDeps(
            nats_client=nats,
            config=ApprovalConfig(default_wait_seconds=1, max_wait_seconds=2),
            publish_refresh=None,
            clock=clock,
        )
        deps_b = ApprovalSubscriberDeps(
            nats_client=nats,
            config=ApprovalConfig(default_wait_seconds=1, max_wait_seconds=2),
            publish_refresh=None,
            clock=clock,
        )
        sub_a = ApprovalSubscriber(deps_a)
        sub_b = ApprovalSubscriber(deps_b)

        rid_a = derive_request_id(
            build_id=BUILD_ID, stage_label=STAGE_LABEL, attempt_count=0
        )
        rid_b = derive_request_id(
            build_id=OTHER_BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=0,
        )

        wait_a = asyncio.create_task(
            sub_a.await_response(BUILD_ID, stage_label=STAGE_LABEL)
        )
        wait_b = asyncio.create_task(
            sub_b.await_response(OTHER_BUILD_ID, stage_label=STAGE_LABEL)
        )
        # Wait until both subscriptions exist.
        for _ in range(50):
            if (
                nats.subscribers.get(
                    f"{APPROVAL_SUBJECT_PREFIX}.{BUILD_ID}.response"
                )
                and nats.subscribers.get(
                    f"{APPROVAL_SUBJECT_PREFIX}.{OTHER_BUILD_ID}.response"
                )
            ):
                break
            await asyncio.sleep(0)

        await nats.deliver_response(
            build_id=BUILD_ID, request_id=rid_a, decision="approve"
        )
        await nats.deliver_response(
            build_id=OTHER_BUILD_ID, request_id=rid_b, decision="reject"
        )

        result_a = await asyncio.wait_for(wait_a, timeout=1.0)
        result_b = await asyncio.wait_for(wait_b, timeout=1.0)

        assert result_a is not None
        assert result_b is not None
        assert result_a.request_id == rid_a
        assert result_a.decision == "approve"
        assert result_b.request_id == rid_b
        assert result_b.decision == "reject"
