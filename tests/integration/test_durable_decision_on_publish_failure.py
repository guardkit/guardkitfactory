"""Durable-decision-on-publish-failure (closes risk **R6**).

Group E ``@data-integrity @regression``. The contract under test is:

* The :class:`forge.gating.models.GateDecision` SQLite row is committed
  **before** any bus publish.
* If the underlying NATS publish raises, the SQLite row is **not** rolled
  back — pipeline truth lives in SQLite, the bus is a derived projection.
* The publish failure surfaces as an operational signal
  (:class:`ApprovalPublishError` propagating up to the caller), not as a
  silently-swallowed exception.

This is the integration-level companion to TASK-CGCP-006 AC-006 (the
publisher's own unit test that ``ApprovalPublishError`` wraps the
underlying transport failure) and TASK-CGCP-010 AC-003 (the wrapper
unit test that the SQLite row is intact when publish fails). The seam
under test here is the join between the two — wired against the real
publisher and the in-memory NATS double.
"""

from __future__ import annotations

import asyncio

import pytest

from forge.adapters.nats.approval_publisher import ApprovalPublishError
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
# Helper — predict the canonical request subject for ``BUILD_ID``.
# ---------------------------------------------------------------------------


def _request_subject(build_id: str = BUILD_ID) -> str:
    return f"agents.approval.forge.{build_id}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDurableDecisionOnPublishFailure:
    """SQLite row is intact even when the bus publish blows up."""

    @pytest.mark.asyncio
    async def test_publish_failure_does_not_roll_back_sqlite_row(
        self, nats: InMemoryNats
    ) -> None:
        # The publisher's failure path raises :class:`ApprovalPublishError`
        # that wraps the underlying transport failure. The wrapper does
        # NOT roll back the SQLite row on failure (F10 / risk R6).
        nats.publish_failures[_request_subject()] = [
            ConnectionError("nats down")
        ]

        deps, _, repo, sm, _, _ = build_gate_check_deps(
            nats=nats, mode=GateMode.FLAG_FOR_REVIEW
        )

        with pytest.raises(ApprovalPublishError) as exc_info:
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

        # The error is a typed publisher failure, not a generic transport
        # exception — operational signal, not silent swallow (R6).
        assert exc_info.value.subject == _request_subject()
        assert isinstance(exc_info.value.cause, ConnectionError)

        # SQLite mirror is intact:
        # 1. The gate decision row was recorded (record_decision).
        assert len(repo.decisions) == 1
        # 2. The paused-build row was committed BEFORE the publish was
        #    attempted (so a crash-recovery boot can re-emit it).
        assert len(repo.paused) == 1
        assert repo.paused[0].build_id == BUILD_ID
        # 3. State machine reached PAUSED — observers see the build
        #    paused.
        assert sm.paused == [(BUILD_ID, STAGE_LABEL)]

        # And the order_log proves SQLite-before-publish:
        ops = [op for op, _ in repo.order_log]
        assert ops.index("record_decision") < ops.index("record_paused_build")

    @pytest.mark.asyncio
    async def test_publish_failure_is_propagated_not_swallowed(
        self, nats: InMemoryNats
    ) -> None:
        # The wrapper does not catch ApprovalPublishError — operators
        # see the failure and the orchestrator/bootstrap can route it
        # to the operational dashboard.
        nats.publish_failures[_request_subject()] = [
            RuntimeError("transient broker error"),
        ]
        deps, *_ = build_gate_check_deps(
            nats=nats, mode=GateMode.FLAG_FOR_REVIEW
        )
        with pytest.raises(ApprovalPublishError):
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

    @pytest.mark.asyncio
    async def test_graphiti_write_failure_does_not_roll_back_sqlite(
        self, nats: InMemoryNats
    ) -> None:
        # Adjacent invariant: a Graphiti write failure is also an
        # operational signal — never a SQLite rollback. Both Graphiti
        # and the bus are derived projections of the SQLite source of
        # truth.
        from .conftest import InMemoryRepository

        repo = InMemoryRepository(graphiti_should_raise=True)
        deps, _, _, sm, _, _ = build_gate_check_deps(
            nats=nats, mode=GateMode.AUTO_APPROVE, repo=repo
        )

        outcome, _ = await gate_check(
            deps=deps,
            build_id=BUILD_ID,
            feature_id=FEATURE_ID,
            stage_label=STAGE_LABEL,
            target_kind="local_tool",
            target_identifier="t",
            coach_score=0.95,
            criterion_breakdown={"c": 0.95},
            detection_findings=[],
        )
        # Outcome is unchanged — the wrapper logged the Graphiti error
        # and continued.
        from forge.gating.wrappers import GateOutcome

        assert outcome is GateOutcome.AUTO_APPROVED
        # SQLite decision row is present despite the Graphiti raise.
        assert len(repo.decisions) == 1
        # Graphiti write is recorded as not having succeeded.
        assert repo.graphiti_writes == []
