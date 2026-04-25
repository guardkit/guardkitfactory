"""Unrecognised-responder anomaly path — Group E ``@security``.

Contract under test: a response from a non-expected approver does NOT
resume the paused build. The subscriber's responder allowlist
(:attr:`ApprovalSubscriberDeps.expected_approver`) is consulted on
every inbound envelope, and a non-match is logged as an anomaly and
silently dropped — the dedup buffer is **not** poisoned because the
allowlist check runs before dedup recording.

Defence against an attacker impersonating Rich's responder identity:
even if the attacker echoes back the right ``request_id``, the
unrecognised ``decided_by`` keeps the build paused. A subsequent real
Rich response arrives with the right responder identity and is the
one that actually resumes the build.
"""

from __future__ import annotations

import asyncio
import logging

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
    RICH,
    STAGE_LABEL,
    FakeMonotonicClock,
    InMemoryNats,
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUnrecognisedResponderDoesNotResumeBuild:
    """Non-allowlisted responder → log + drop, build stays paused."""

    @pytest.mark.asyncio
    async def test_unrecognised_responder_keeps_build_paused(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        nats = InMemoryNats()
        clock = FakeMonotonicClock()
        deps = ApprovalSubscriberDeps(
            nats_client=nats,
            config=ApprovalConfig(default_wait_seconds=1, max_wait_seconds=1),
            publish_refresh=None,
            expected_approver=RICH,  # only Rich may resume
            clock=clock,
        )
        subscriber = ApprovalSubscriber(deps)

        rid = derive_request_id(
            build_id=BUILD_ID, stage_label=STAGE_LABEL, attempt_count=0
        )

        wait_task = asyncio.create_task(
            subscriber.await_response(BUILD_ID, stage_label=STAGE_LABEL)
        )
        # Wait for the subscription to register.
        subject = f"{APPROVAL_SUBJECT_PREFIX}.{BUILD_ID}.response"
        for _ in range(50):
            if nats.subscribers.get(subject):
                break
            await asyncio.sleep(0)

        with caplog.at_level(logging.WARNING):
            await nats.deliver_response(
                build_id=BUILD_ID,
                request_id=rid,
                decision="approve",
                decided_by="not-rich",  # unrecognised responder
            )

        # The build is NOT resumed — wait_task remains pending until
        # the wait ceiling fires below.
        assert not wait_task.done(), (
            "wait resolved despite non-allowlisted responder — anomaly "
            "path failed to short-circuit"
        )

        # Anomaly was logged.
        assert any(
            "unrecognised responder" in record.message.lower()
            for record in caplog.records
        ), "anomaly was not surfaced through the warning log"

        # Dedup buffer was NOT poisoned — request_id is still
        # available for a subsequent legitimate Rich response.
        assert rid not in subscriber._dedup

        # Now drive a legitimate Rich response — the real responder
        # resumes the build.
        await nats.deliver_response(
            build_id=BUILD_ID,
            request_id=rid,
            decision="approve",
            decided_by=RICH,
        )
        result = await asyncio.wait_for(wait_task, timeout=1.0)
        assert result is not None
        assert result.decision == "approve"
        assert result.decided_by == RICH
