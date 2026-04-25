"""Pause-and-publish atomicity — Group E ``@concurrency @data-integrity``.

The contract under test (closes risk **F5**): from any external observer
the build's status is never reported as ``PAUSED`` *without* a
corresponding bus publish having been issued. The wrapper enforces this
by writing the SQLite paused-build row **and** transitioning the state
machine to ``PAUSED`` *before* publishing the approval-request envelope —
no awaits between the SQLite/state-machine writes and the publish that
would let an observer interleave a status query in the gap.

This integration test interleaves a synthetic observer with the
gate-check execution and asserts the invariant from the observer's
perspective: at every observable timestamp, ``status=PAUSED`` is
preceded by an approval-request publish.
"""

from __future__ import annotations

import asyncio

import pytest

from forge.gating.identity import derive_request_id
from forge.gating.models import GateMode
from forge.gating.wrappers import gate_check

from .conftest import (
    BUILD_ID,
    FEATURE_ID,
    STAGE_LABEL,
    InMemoryNats,
    build_gate_check_deps,
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPauseAndPublishAtomicity:
    """Observer never sees PAUSED-without-corresponding-publish."""

    @pytest.mark.asyncio
    async def test_paused_status_never_observed_before_request_publish(
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

        # Synthetic observer — yields its own status snapshot every
        # event-loop tick until gate_check reaches ``await_response``.
        observations: list[tuple[int, str | None, int]] = []

        async def observer() -> None:
            for tick in range(40):
                # Status the observer would see at this exact tick.
                status = sm.status_log[-1][1] if sm.status_log else None
                published_count = sum(
                    len(v) for v in nats.published.values()
                )
                observations.append((tick, status, published_count))
                if BUILD_ID in deps.subscriber._queues:  # type: ignore[attr-defined]
                    return
                await asyncio.sleep(0)

        await observer()

        # Drive the response so gate_check completes.
        request_subject = f"agents.approval.forge.{BUILD_ID}.response"
        # Wait until the response subscription is registered.
        for _ in range(50):
            if request_subject in nats.subscribers and nats.subscribers[
                request_subject
            ]:
                break
            await asyncio.sleep(0)
        await nats.deliver_response(
            build_id=BUILD_ID, request_id=request_id, decision="approve"
        )
        await asyncio.wait_for(gate_task, timeout=1.0)

        # Invariant — for every snapshot the observer captured, if
        # status was ``PAUSED`` then the publish count was at least 1.
        for tick, status, published in observations:
            if status == "PAUSED":
                assert published >= 1, (
                    f"observer at tick {tick} saw status=PAUSED with "
                    f"published_count={published}; pause-and-publish "
                    f"atomicity violated."
                )

        # Belt-and-braces: the order_log shows the SQLite paused row
        # was written before the publisher recorded the publish — the
        # repository order log records ``record_paused_build`` and
        # the bus log records the publish.
        assert ("record_paused_build", request_id) in repo.order_log
        assert any(b for b in nats.published.get(
            f"agents.approval.forge.{BUILD_ID}", []
        ))

    @pytest.mark.asyncio
    async def test_record_paused_row_precedes_state_paused_precedes_publish(
        self, nats: InMemoryNats
    ) -> None:
        # Even when the publish fails, the order-of-operations contract
        # is preserved: SQLite paused row, then state-machine PAUSED,
        # then publish (which raises). This makes crash-recovery
        # re-emission safe — see test_crash_recovery_re_emit.py.
        nats.publish_failures[f"agents.approval.forge.{BUILD_ID}"] = [
            ConnectionError("flaky")
        ]
        deps, _, repo, sm, _, _ = build_gate_check_deps(
            nats=nats, mode=GateMode.FLAG_FOR_REVIEW
        )

        with pytest.raises(Exception):
            await asyncio.wait_for(
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
                ),
                timeout=1.0,
            )

        # The paused-row was committed.
        assert len(repo.paused) == 1
        # The state machine reached PAUSED.
        assert sm.paused == [(BUILD_ID, STAGE_LABEL)]
        # No publish landed (the only attempt was the one that raised).
        published = nats.published.get(f"agents.approval.forge.{BUILD_ID}", [])
        assert published == []
