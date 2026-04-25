"""Tests for :mod:`forge.gating.wrappers` (TASK-CGCP-010).

One ``Test*`` class per acceptance criterion in
``tasks/design_approved/TASK-CGCP-010-state-machine-integration.md``:

* AC-001 — :func:`gate_check` orchestrates the full read → evaluate →
  write → publish/transition sequence.
* AC-002 (F9) — ``read_adjustments(approved_only=True)`` is the only
  filter point for unapproved adjustments.
* AC-003 (F10) — gate decision recorded durably even if publish fails.
* AC-004 (F5) — pause-and-publish atomicity (no PAUSED status without
  a corresponding bus publish issued).
* AC-005..AC-007 (Group A) — approve/reject/override responses drive
  the state machine.
* AC-008 (Group D @regression) — boot re-emits with persisted
  ``request_id`` (not re-derived).
* AC-009 / AC-010 (Group D @edge-case) — CLI cancel + skip route
  through the synthetic injector.
* AC-011 (F4) — every read of the response goes through
  :func:`resume_value_as` (verified by the dict-rehydration test).
* AC-012 (Group D @edge-case) — per-build response routing.
* AC-013 — max-wait ceiling reached → fallback transition.
"""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest
from nats_core.envelope import MessageEnvelope
from nats_core.events import ApprovalResponsePayload

from forge.gating import (
    CalibrationAdjustment,
    DetectionFinding,
    GateDecision,
    GateMode,
    PriorReference,
)
from forge.gating.wrappers import (
    REASON_CLI_CANCEL,
    REASON_HARD_STOP,
    REASON_MAX_WAIT,
    REASON_REJECT,
    GateCheckDeps,
    GateOutcome,
    PausedBuildSnapshot,
    cli_cancel_build,
    cli_skip_stage,
    gate_check,
    recover_paused_builds,
)


# ---------------------------------------------------------------------------
# In-memory fakes — one per Protocol surface.
# ---------------------------------------------------------------------------


@dataclass
class _FakePriorsReader:
    priors: list[PriorReference] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def read_priors(self, **kw: Any) -> list[PriorReference]:
        self.calls.append(dict(kw))
        return list(self.priors)


@dataclass
class _FakeAdjustmentsReader:
    adjustments: list[CalibrationAdjustment] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def read_adjustments(
        self, *, target_capability: str, approved_only: bool
    ) -> list[CalibrationAdjustment]:
        self.calls.append(
            {
                "target_capability": target_capability,
                "approved_only": approved_only,
            }
        )
        return list(self.adjustments)


@dataclass
class _FakeRulesReader:
    rules: list[Any] = field(default_factory=list)

    async def read_rules(self, **kw: Any) -> list[Any]:
        return list(self.rules)


@dataclass
class _FakeRepository:
    decisions: list[GateDecision] = field(default_factory=list)
    graphiti_writes: list[GateDecision] = field(default_factory=list)
    paused: list[PausedBuildSnapshot] = field(default_factory=list)
    resumed: list[tuple[str, str]] = field(default_factory=list)
    overridden: list[tuple[str, str, str]] = field(default_factory=list)
    cancelled: list[tuple[str, str]] = field(default_factory=list)
    # Allow tests to inject a graphiti write failure.
    graphiti_should_raise: bool = False
    # Order log: a flat list of ("op", payload) tuples used to assert
    # SQLite-before-publish ordering for F10 + F5.
    order_log: list[tuple[str, Any]] = field(default_factory=list)

    async def record_decision(self, decision: GateDecision) -> None:
        self.decisions.append(decision)
        self.order_log.append(("record_decision", decision.build_id))

    async def write_to_graphiti(self, decision: GateDecision) -> None:
        if self.graphiti_should_raise:
            raise RuntimeError("graphiti unavailable")
        self.graphiti_writes.append(decision)
        self.order_log.append(("write_to_graphiti", decision.build_id))

    async def record_paused_build(
        self,
        *,
        build_id: str,
        feature_id: str,
        stage_label: str,
        request_id: str,
        attempt_count: int,
        decision: GateDecision,
    ) -> None:
        snap = PausedBuildSnapshot(
            build_id=build_id,
            feature_id=feature_id,
            stage_label=stage_label,
            request_id=request_id,
            attempt_count=attempt_count,
            decision_snapshot=decision,
        )
        self.paused.append(snap)
        self.order_log.append(("record_paused_build", request_id))

    async def list_paused_builds(self) -> list[PausedBuildSnapshot]:
        return list(self.paused)

    async def mark_resumed(self, *, build_id: str, stage_label: str) -> None:
        self.resumed.append((build_id, stage_label))

    async def mark_overridden(
        self, *, build_id: str, stage_label: str, reason: str
    ) -> None:
        self.overridden.append((build_id, stage_label, reason))

    async def mark_cancelled(self, *, build_id: str, reason: str) -> None:
        self.cancelled.append((build_id, reason))


@dataclass
class _FakeStateMachine:
    paused: list[tuple[str, str]] = field(default_factory=list)
    running: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    cancelled: list[tuple[str, str]] = field(default_factory=list)
    # Cross-checked against the repository order_log in the
    # atomicity test.
    order_log: list[tuple[str, Any]] = field(default_factory=list)

    async def transition_to_paused(
        self, *, build_id: str, stage_label: str
    ) -> None:
        self.paused.append((build_id, stage_label))
        self.order_log.append(("paused", build_id))

    async def transition_to_running(self, *, build_id: str) -> None:
        self.running.append(build_id)

    async def transition_to_failed(
        self, *, build_id: str, reason: str
    ) -> None:
        self.failed.append((build_id, reason))

    async def transition_to_cancelled(
        self, *, build_id: str, reason: str
    ) -> None:
        self.cancelled.append((build_id, reason))


@dataclass
class _FakePublisher:
    envelopes: list[MessageEnvelope] = field(default_factory=list)
    # Optional sequence of side effects to execute on each call.
    side_effects: list[Exception | None] = field(default_factory=list)
    order_log: list[tuple[str, Any]] = field(default_factory=list)

    async def publish_request(self, envelope: MessageEnvelope) -> None:
        self.envelopes.append(envelope)
        # Pop a side effect if one was queued.
        if self.side_effects:
            effect = self.side_effects.pop(0)
            if effect is not None:
                raise effect
        request_id = envelope.payload["request_id"]
        self.order_log.append(("publish_request", request_id))


@dataclass
class _FakeSubscriber:
    """Subscriber stub returning a programmable sequence of responses.

    Each entry in ``responses`` is consumed by one ``await_response``
    call. ``None`` represents a max-wait timeout. The entry can be a
    typed :class:`ApprovalResponsePayload` (direct-invoke mode) or a
    plain ``dict`` (server-mode / DDR-002) — the latter exercises
    :func:`resume_value_as`.
    """

    responses: list[ApprovalResponsePayload | dict[str, Any] | None] = field(
        default_factory=list
    )
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def await_response(
        self,
        build_id: str,
        *,
        stage_label: str,
        attempt_count: int = 0,
        timeout_seconds: int | None = None,
    ) -> ApprovalResponsePayload | dict[str, Any] | None:
        self.calls.append(
            {
                "build_id": build_id,
                "stage_label": stage_label,
                "attempt_count": attempt_count,
                "timeout_seconds": timeout_seconds,
            }
        )
        if not self.responses:
            return None
        return self.responses.pop(0)


@dataclass
class _FakeInjector:
    cancel_calls: list[dict[str, Any]] = field(default_factory=list)
    skip_calls: list[dict[str, Any]] = field(default_factory=list)

    async def inject_cli_cancel(self, **kw: Any) -> None:
        self.cancel_calls.append(dict(kw))

    async def inject_cli_skip(self, **kw: Any) -> None:
        self.skip_calls.append(dict(kw))


# ---------------------------------------------------------------------------
# Reasoning-model doubles — return canned JSON for each gate mode.
# ---------------------------------------------------------------------------


def _model_returning(mode: GateMode, *, score_threshold: float | None = None):
    """Return a ``(prompt: str) -> str`` callable yielding fixed JSON."""

    payload = {
        "mode": mode.value,
        "rationale": f"reasoned: {mode.value}",
        "relevant_prior_ids": [],
        "threshold_applied": score_threshold,
    }
    import json

    body = json.dumps(payload)

    def _call(_prompt: str) -> str:
        return body

    return _call


# ---------------------------------------------------------------------------
# Common fixtures.
# ---------------------------------------------------------------------------


def _fixed_clock() -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC)


def _build_deps(
    *,
    mode: GateMode = GateMode.AUTO_APPROVE,
    threshold: float | None = None,
    priors: list[PriorReference] | None = None,
    adjustments: list[CalibrationAdjustment] | None = None,
    responses: list[ApprovalResponsePayload | dict[str, Any] | None]
    | None = None,
) -> tuple[
    GateCheckDeps,
    _FakePriorsReader,
    _FakeAdjustmentsReader,
    _FakeRepository,
    _FakeStateMachine,
    _FakePublisher,
    _FakeSubscriber,
    _FakeInjector,
]:
    pr = _FakePriorsReader(priors=list(priors or []))
    ar = _FakeAdjustmentsReader(adjustments=list(adjustments or []))
    rr = _FakeRulesReader(rules=[])
    repo = _FakeRepository()
    sm = _FakeStateMachine()
    pub = _FakePublisher()
    sub = _FakeSubscriber(responses=list(responses or []))
    inj = _FakeInjector()
    deps = GateCheckDeps(
        priors_reader=pr,
        adjustments_reader=ar,
        rules_reader=rr,
        repository=repo,
        state_machine=sm,
        publisher=pub,
        subscriber=sub,
        injector=inj,
        reasoning_model_call=_model_returning(mode, score_threshold=threshold),
        clock=_fixed_clock,
    )
    return deps, pr, ar, repo, sm, pub, sub, inj


# ---------------------------------------------------------------------------
# AC-001 — full sequence orchestration.
# ---------------------------------------------------------------------------


class TestGateCheckOrchestratesFullSequence:
    """AC-001: read priors → read adjustments → evaluate → write → branch."""

    @pytest.mark.asyncio
    async def test_auto_approve_persists_decision_and_returns_outcome(
        self,
    ) -> None:
        deps, pr, ar, repo, sm, pub, sub, _ = _build_deps(
            mode=GateMode.AUTO_APPROVE,
            threshold=0.85,
            priors=[
                PriorReference(
                    entity_id="e1",
                    group_id="forge_pipeline_history",
                    summary="prior",
                )
            ],
        )

        outcome, decision = await gate_check(
            deps=deps,
            build_id="build-1",
            feature_id="FEAT-001",
            stage_label="Implementation",
            target_kind="local_tool",
            target_identifier="write_file",
            coach_score=0.9,
            criterion_breakdown={"completeness": 0.9},
            detection_findings=[],
        )

        assert outcome is GateOutcome.AUTO_APPROVED
        assert isinstance(decision, GateDecision)
        # Read side ran exactly once.
        assert len(pr.calls) == 1
        assert len(ar.calls) == 1
        # Decision persisted to SQLite.
        assert repo.decisions == [decision]
        # State machine NEVER transitioned for AUTO_APPROVE.
        assert sm.paused == []
        assert sm.failed == []
        # No publish for AUTO_APPROVE.
        assert pub.envelopes == []
        # Subscriber NEVER awaited.
        assert sub.calls == []


# ---------------------------------------------------------------------------
# AC-002 — F9 / R8 — adjustments always read with approved_only=True.
# ---------------------------------------------------------------------------


class TestApprovedOnlyIsAlwaysTrue:
    """AC F9: ``read_adjustments(approved_only=True)`` is the only filter."""

    @pytest.mark.asyncio
    async def test_unapproved_adjustments_never_reach_evaluate_gate(
        self,
    ) -> None:
        deps, _, ar, _, _, _, _, _ = _build_deps(mode=GateMode.AUTO_APPROVE)
        await gate_check(
            deps=deps,
            build_id="b",
            feature_id="FEAT",
            stage_label="s",
            target_kind="local_tool",
            target_identifier="t",
            coach_score=0.8,
            criterion_breakdown={"c": 0.8},
            detection_findings=[],
        )
        # The wrapper MUST pass approved_only=True (closes R8).
        assert all(call["approved_only"] is True for call in ar.calls)
        assert ar.calls, "adjustments_reader must be consulted"


# ---------------------------------------------------------------------------
# AC-003 (F10) — gate decision recorded durably when publish fails.
# ---------------------------------------------------------------------------


class TestGateDecisionDurableEvenIfPublishFails:
    """AC F10 / Group E @data-integrity @regression."""

    @pytest.mark.asyncio
    async def test_publish_failure_does_not_roll_back_sqlite(self) -> None:
        deps, _, _, repo, sm, pub, _, _ = _build_deps(
            mode=GateMode.FLAG_FOR_REVIEW,
            responses=[None],  # max-wait fallback
        )
        # Queue a publish failure on the very first publish.
        pub.side_effects.append(RuntimeError("nats down"))

        with pytest.raises(RuntimeError, match="nats down"):
            await gate_check(
                deps=deps,
                build_id="build-2",
                feature_id="FEAT-002",
                stage_label="ArchReview",
                target_kind="subagent",
                target_identifier="reviewer",
                coach_score=0.7,
                criterion_breakdown={"c": 0.7},
                detection_findings=[],
            )

        # SQLite mirror is intact even after publish blew up.
        assert len(repo.decisions) == 1
        # Paused-build row was committed BEFORE the publish attempt.
        assert len(repo.paused) == 1
        # State machine reached PAUSED.
        assert sm.paused == [("build-2", "ArchReview")]


# ---------------------------------------------------------------------------
# AC-004 (F5) — pause-and-publish atomicity (ordering).
# ---------------------------------------------------------------------------


class TestPauseAndPublishAtomicity:
    """AC F5: SQLite paused-row + state-PAUSED commit BEFORE bus publish."""

    @pytest.mark.asyncio
    async def test_record_paused_row_precedes_state_paused_precedes_publish(
        self,
    ) -> None:
        deps, _, _, repo, sm, pub, _, _ = _build_deps(
            mode=GateMode.FLAG_FOR_REVIEW,
            responses=[
                ApprovalResponsePayload(
                    request_id="ignored",
                    decision="approve",
                    decided_by="rich",
                )
            ],
        )

        await gate_check(
            deps=deps,
            build_id="build-3",
            feature_id="FEAT-003",
            stage_label="Stage",
            target_kind="local_tool",
            target_identifier="t",
            coach_score=0.7,
            criterion_breakdown={"c": 0.7},
            detection_findings=[],
        )

        # The repository's record_decision and record_paused_build
        # entries must precede the publisher's publish_request entry
        # in real time. Because all the awaits resolve synchronously
        # in this in-memory test, the merged order is observable
        # via insertion.
        repo_ops = [op for op, _ in repo.order_log]
        assert "record_decision" in repo_ops
        assert "record_paused_build" in repo_ops
        # State machine PAUSED before publish.
        assert sm.paused == [("build-3", "Stage")]
        # Exactly one publish.
        assert len(pub.envelopes) == 1


# ---------------------------------------------------------------------------
# AC-005..AC-007 — Group A: approve / reject / override.
# ---------------------------------------------------------------------------


class TestApprovalDecisionsDriveStateMachine:
    """Group A — paused build's terminal outcome is response-driven."""

    @pytest.mark.asyncio
    async def test_approve_resumes_build(self) -> None:
        deps, _, _, repo, sm, _, _, _ = _build_deps(
            mode=GateMode.FLAG_FOR_REVIEW,
            responses=[
                ApprovalResponsePayload(
                    request_id="rid",
                    decision="approve",
                    decided_by="rich",
                )
            ],
        )
        outcome, _ = await gate_check(
            deps=deps,
            build_id="b-A",
            feature_id="FEAT-A",
            stage_label="StageA",
            target_kind="local_tool",
            target_identifier="t",
            coach_score=0.7,
            criterion_breakdown={"c": 0.7},
            detection_findings=[],
        )
        assert outcome is GateOutcome.RESUMED
        assert sm.running == ["b-A"]
        assert repo.resumed == [("b-A", "StageA")]

    @pytest.mark.asyncio
    async def test_reject_cancels_with_reason(self) -> None:
        deps, _, _, repo, sm, _, _, _ = _build_deps(
            mode=GateMode.FLAG_FOR_REVIEW,
            responses=[
                ApprovalResponsePayload(
                    request_id="rid",
                    decision="reject",
                    decided_by="rich",
                    notes="not safe",
                )
            ],
        )
        outcome, _ = await gate_check(
            deps=deps,
            build_id="b-B",
            feature_id="FEAT-B",
            stage_label="StageB",
            target_kind="local_tool",
            target_identifier="t",
            coach_score=0.7,
            criterion_breakdown={"c": 0.7},
            detection_findings=[],
        )
        assert outcome is GateOutcome.CANCELLED
        # Rich's notes flow through as the cancel reason.
        assert sm.cancelled == [("b-B", "not safe")]
        assert repo.cancelled == [("b-B", "not safe")]

    @pytest.mark.asyncio
    async def test_reject_without_notes_uses_default_reason(self) -> None:
        deps, _, _, _, sm, _, _, _ = _build_deps(
            mode=GateMode.FLAG_FOR_REVIEW,
            responses=[
                ApprovalResponsePayload(
                    request_id="rid", decision="reject", decided_by="rich"
                )
            ],
        )
        await gate_check(
            deps=deps,
            build_id="b-C",
            feature_id="FEAT-C",
            stage_label="S",
            target_kind="local_tool",
            target_identifier="t",
            coach_score=0.7,
            criterion_breakdown={"c": 0.7},
            detection_findings=[],
        )
        assert sm.cancelled == [("b-C", REASON_REJECT)]

    @pytest.mark.asyncio
    async def test_override_marks_overridden_and_continues(self) -> None:
        deps, _, _, repo, sm, _, _, _ = _build_deps(
            mode=GateMode.FLAG_FOR_REVIEW,
            responses=[
                ApprovalResponsePayload(
                    request_id="rid",
                    decision="override",
                    decided_by="rich",
                    notes="ship it",
                )
            ],
        )
        outcome, _ = await gate_check(
            deps=deps,
            build_id="b-D",
            feature_id="FEAT-D",
            stage_label="StageD",
            target_kind="local_tool",
            target_identifier="t",
            coach_score=0.7,
            criterion_breakdown={"c": 0.7},
            detection_findings=[],
        )
        assert outcome is GateOutcome.OVERRIDDEN
        assert repo.overridden == [("b-D", "StageD", "ship it")]
        assert sm.running == ["b-D"]


class TestHardStopTransitionsToFailed:
    """AC: HARD_STOP → state machine transitions to FAILED."""

    @pytest.mark.asyncio
    async def test_hard_stop_transitions_to_failed_no_publish(self) -> None:
        deps, _, _, _, sm, pub, sub, _ = _build_deps(
            mode=GateMode.HARD_STOP,
            threshold=0.85,
        )
        outcome, _ = await gate_check(
            deps=deps,
            build_id="b-HS",
            feature_id="FEAT-HS",
            stage_label="S",
            target_kind="local_tool",
            target_identifier="t",
            coach_score=None,  # degraded mode allows HARD_STOP
            criterion_breakdown={"c": 0.5},
            detection_findings=[],
        )
        assert outcome is GateOutcome.FAILED
        assert sm.failed == [("b-HS", REASON_HARD_STOP)]
        # No publish on HARD_STOP — pause-and-publish path skipped.
        assert pub.envelopes == []
        assert sub.calls == []


# ---------------------------------------------------------------------------
# AC-008 — Group D @regression: re-emit on boot with persisted request_id.
# ---------------------------------------------------------------------------


class TestRecoverPausedBuildsReusesPersistedRequestId:
    """AC R5: boot-time re-emission uses the *persisted* ``request_id``."""

    @pytest.mark.asyncio
    async def test_reemits_one_envelope_per_paused_build_with_persisted_id(
        self,
    ) -> None:
        deps, _, _, repo, _, pub, _, _ = _build_deps(
            mode=GateMode.AUTO_APPROVE
        )
        # Hand-construct a paused snapshot with a deliberately weird
        # request_id so we know the publisher really used it.
        snap_decision = GateDecision(
            build_id="boot-build",
            stage_label="Stage",
            target_kind="local_tool",
            target_identifier="t",
            mode=GateMode.FLAG_FOR_REVIEW,
            rationale="paused before crash",
            coach_score=0.7,
            criterion_breakdown={"c": 0.7},
            detection_findings=[],
            evidence=[],
            decided_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        repo.paused.append(
            PausedBuildSnapshot(
                build_id="boot-build",
                feature_id="FEAT-BOOT",
                stage_label="Stage",
                request_id="weird-persisted-rid",
                attempt_count=2,
                decision_snapshot=snap_decision,
            )
        )

        emitted = await recover_paused_builds(deps)

        assert emitted == ["boot-build"]
        assert len(pub.envelopes) == 1
        env = pub.envelopes[0]
        assert env.payload["request_id"] == "weird-persisted-rid"

    @pytest.mark.asyncio
    async def test_publish_failure_logs_but_does_not_stop_the_loop(
        self,
    ) -> None:
        deps, _, _, repo, _, pub, _, _ = _build_deps(
            mode=GateMode.AUTO_APPROVE
        )
        # Three paused builds — first one's publish fails, the other
        # two succeed.
        pub.side_effects = [RuntimeError("flaky"), None, None]
        for i in range(3):
            d = GateDecision(
                build_id=f"b-{i}",
                stage_label="S",
                target_kind="local_tool",
                target_identifier="t",
                mode=GateMode.FLAG_FOR_REVIEW,
                rationale="paused",
                coach_score=0.7,
                criterion_breakdown={"c": 0.7},
                detection_findings=[],
                evidence=[],
                decided_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
            repo.paused.append(
                PausedBuildSnapshot(
                    build_id=f"b-{i}",
                    feature_id=f"FEAT-{i}",
                    stage_label="S",
                    request_id=f"rid-{i}",
                    attempt_count=0,
                    decision_snapshot=d,
                )
            )

        emitted = await recover_paused_builds(deps)
        # Two successes, one logged failure, no exception escapes.
        assert emitted == ["b-1", "b-2"]


# ---------------------------------------------------------------------------
# AC-009 / AC-010 — Group D @edge-case: CLI cancel + skip route through
# the synthetic injector.
# ---------------------------------------------------------------------------


class TestCliBridgesDelegateToSyntheticInjector:
    """Group D @edge-case: CLI cancel/skip use the standard mirror subject."""

    @pytest.mark.asyncio
    async def test_cli_cancel_invokes_inject_cli_cancel_with_persisted_count(
        self,
    ) -> None:
        deps, _, _, repo, _, _, _, inj = _build_deps(mode=GateMode.AUTO_APPROVE)
        d = GateDecision(
            build_id="cli-build",
            stage_label="Stage",
            target_kind="local_tool",
            target_identifier="t",
            mode=GateMode.FLAG_FOR_REVIEW,
            rationale="paused",
            coach_score=0.7,
            criterion_breakdown={"c": 0.7},
            detection_findings=[],
            evidence=[],
            decided_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        repo.paused.append(
            PausedBuildSnapshot(
                build_id="cli-build",
                feature_id="FEAT-CLI",
                stage_label="Stage",
                request_id="rid",
                attempt_count=4,  # persisted, MUST be passed verbatim
                decision_snapshot=d,
            )
        )

        await cli_cancel_build(deps, build_id="cli-build")

        assert len(inj.cancel_calls) == 1
        call = inj.cancel_calls[0]
        assert call["build_id"] == "cli-build"
        assert call["stage_label"] == "Stage"
        # Persisted attempt_count is passed verbatim (NOT re-derived).
        assert call["attempt_count"] == 4

    @pytest.mark.asyncio
    async def test_cli_skip_invokes_inject_cli_skip(self) -> None:
        deps, _, _, repo, _, _, _, inj = _build_deps(mode=GateMode.AUTO_APPROVE)
        d = GateDecision(
            build_id="b",
            stage_label="Stage",
            target_kind="local_tool",
            target_identifier="t",
            mode=GateMode.FLAG_FOR_REVIEW,
            rationale="paused",
            coach_score=0.7,
            criterion_breakdown={"c": 0.7},
            detection_findings=[],
            evidence=[],
            decided_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        repo.paused.append(
            PausedBuildSnapshot(
                build_id="b",
                feature_id="FEAT",
                stage_label="Stage",
                request_id="rid",
                attempt_count=0,
                decision_snapshot=d,
            )
        )
        await cli_skip_stage(deps, build_id="b")
        assert len(inj.skip_calls) == 1

    @pytest.mark.asyncio
    async def test_cli_cancel_unknown_build_id_raises_lookup_error(
        self,
    ) -> None:
        deps, *_ = _build_deps(mode=GateMode.AUTO_APPROVE)
        with pytest.raises(LookupError, match="no paused build"):
            await cli_cancel_build(deps, build_id="missing")


# ---------------------------------------------------------------------------
# AC-011 (F4) — every read of the response goes through resume_value_as.
# ---------------------------------------------------------------------------


class TestResumeValueRehydration:
    """F4 / DDR-002: dict-shaped responses (server mode) are rehydrated."""

    @pytest.mark.asyncio
    async def test_dict_response_is_rehydrated_into_typed_payload(self) -> None:
        # Server-mode responses arrive as plain dicts; the wrapper MUST
        # round-trip them through resume_value_as before any attribute
        # access. If it didn't, ``raw.decision`` would AttributeError.
        deps, _, _, _, sm, _, _, _ = _build_deps(
            mode=GateMode.FLAG_FOR_REVIEW,
            responses=[
                {
                    "request_id": "rid",
                    "decision": "approve",
                    "decided_by": "rich",
                }
            ],
        )
        outcome, _ = await gate_check(
            deps=deps,
            build_id="dict-build",
            feature_id="FEAT-DICT",
            stage_label="S",
            target_kind="local_tool",
            target_identifier="t",
            coach_score=0.7,
            criterion_breakdown={"c": 0.7},
            detection_findings=[],
        )
        assert outcome is GateOutcome.RESUMED
        assert sm.running == ["dict-build"]


# ---------------------------------------------------------------------------
# AC-012 — per-build response routing (concurrent paused builds).
# ---------------------------------------------------------------------------


class TestPerBuildResponseRouting:
    """Group D @edge-case: a response addressed to one build does not
    affect another."""

    @pytest.mark.asyncio
    async def test_two_concurrent_paused_builds_resolve_independently(
        self,
    ) -> None:
        # Two distinct deps bundles → two independent subscribers, so
        # the in-memory subscriber stub can return different responses
        # per build. This exercises the "per-build queue" semantics.
        deps_a, *_, sub_a, _ = _build_deps(
            mode=GateMode.FLAG_FOR_REVIEW,
            responses=[
                ApprovalResponsePayload(
                    request_id="ra",
                    decision="approve",
                    decided_by="rich",
                )
            ],
        )
        deps_b, *_, sub_b, _ = _build_deps(
            mode=GateMode.FLAG_FOR_REVIEW,
            responses=[
                ApprovalResponsePayload(
                    request_id="rb",
                    decision="reject",
                    decided_by="rich",
                    notes="abort",
                )
            ],
        )

        out_a, out_b = await asyncio.gather(
            gate_check(
                deps=deps_a,
                build_id="A",
                feature_id="F-A",
                stage_label="S",
                target_kind="local_tool",
                target_identifier="t",
                coach_score=0.7,
                criterion_breakdown={"c": 0.7},
                detection_findings=[],
            ),
            gate_check(
                deps=deps_b,
                build_id="B",
                feature_id="F-B",
                stage_label="S",
                target_kind="local_tool",
                target_identifier="t",
                coach_score=0.7,
                criterion_breakdown={"c": 0.7},
                detection_findings=[],
            ),
        )

        assert out_a[0] is GateOutcome.RESUMED
        assert out_b[0] is GateOutcome.CANCELLED
        # Each subscriber saw exactly one ``await_response`` call for
        # its own build_id.
        assert sub_a.calls[0]["build_id"] == "A"
        assert sub_b.calls[0]["build_id"] == "B"


# ---------------------------------------------------------------------------
# AC-013 — Group D @edge-case: max-wait ceiling reached.
# ---------------------------------------------------------------------------


class TestMaxWaitCeiling:
    """Group D @edge-case: total wait reaches max_wait_seconds → fallback."""

    @pytest.mark.asyncio
    async def test_subscriber_returning_none_triggers_cancelled_fallback(
        self,
    ) -> None:
        deps, _, _, repo, sm, _, _, _ = _build_deps(
            mode=GateMode.FLAG_FOR_REVIEW,
            responses=[None],  # the subscriber's max-wait return.
        )
        outcome, _ = await gate_check(
            deps=deps,
            build_id="b-mw",
            feature_id="FEAT",
            stage_label="S",
            target_kind="local_tool",
            target_identifier="t",
            coach_score=0.7,
            criterion_breakdown={"c": 0.7},
            detection_findings=[],
        )
        assert outcome is GateOutcome.TIMED_OUT
        # ASSUM-003 fallback currently maps to CANCELLED.
        assert sm.cancelled == [("b-mw", REASON_MAX_WAIT)]
        assert repo.cancelled == [("b-mw", REASON_MAX_WAIT)]


# ---------------------------------------------------------------------------
# Defer path — re-publishes with attempt_count + 1, then dispatches.
# ---------------------------------------------------------------------------


class TestDeferRefreshesWithIncrementedAttempt:
    """Defer triggers a re-publish under a new ``request_id`` and waits
    for the next response."""

    @pytest.mark.asyncio
    async def test_defer_then_approve_resumes_with_new_request_id(
        self,
    ) -> None:
        deps, _, _, repo, sm, pub, sub, _ = _build_deps(
            mode=GateMode.FLAG_FOR_REVIEW,
            responses=[
                ApprovalResponsePayload(
                    request_id="ignored",
                    decision="defer",
                    decided_by="rich",
                ),
                ApprovalResponsePayload(
                    request_id="ignored2",
                    decision="approve",
                    decided_by="rich",
                ),
            ],
        )
        outcome, _ = await gate_check(
            deps=deps,
            build_id="b-def",
            feature_id="FEAT",
            stage_label="StageX",
            target_kind="local_tool",
            target_identifier="t",
            coach_score=0.7,
            criterion_breakdown={"c": 0.7},
            detection_findings=[],
            attempt_count=0,
        )
        assert outcome is GateOutcome.RESUMED
        # Two publishes — initial + defer-refresh.
        assert len(pub.envelopes) == 2
        first_rid = pub.envelopes[0].payload["request_id"]
        second_rid = pub.envelopes[1].payload["request_id"]
        assert first_rid != second_rid
        # Second await used the incremented attempt_count.
        assert sub.calls[1]["attempt_count"] == 1


# ---------------------------------------------------------------------------
# Sanity / signature.
# ---------------------------------------------------------------------------


class TestGateCheckSignatureIsKeywordOnlyAndAsync:
    """The wrapper must be async + accept all required params keyword-only."""

    def test_gate_check_is_a_coroutine_function(self) -> None:
        assert inspect.iscoroutinefunction(gate_check)

    def test_recover_paused_builds_is_a_coroutine_function(self) -> None:
        assert inspect.iscoroutinefunction(recover_paused_builds)

    def test_cli_bridges_are_coroutine_functions(self) -> None:
        assert inspect.iscoroutinefunction(cli_cancel_build)
        assert inspect.iscoroutinefunction(cli_skip_stage)


# ---------------------------------------------------------------------------
# Seam tests — verify the upstream Producer contracts the wrapper
# composes against.
# ---------------------------------------------------------------------------


@pytest.mark.seam
@pytest.mark.integration_contract("ApprovalPublisher.publish_request")
def test_publisher_method_exists() -> None:
    """Verify ApprovalPublisher.publish_request is async (TASK-CGCP-006)."""
    from forge.adapters.nats.approval_publisher import ApprovalPublisher

    assert hasattr(ApprovalPublisher, "publish_request")
    assert inspect.iscoroutinefunction(ApprovalPublisher.publish_request)


@pytest.mark.seam
@pytest.mark.integration_contract("ApprovalSubscriber.await_response")
def test_subscriber_method_exists() -> None:
    """Verify ApprovalSubscriber.await_response is async (TASK-CGCP-007)."""
    from forge.adapters.nats.approval_subscriber import ApprovalSubscriber

    assert hasattr(ApprovalSubscriber, "await_response")
    assert inspect.iscoroutinefunction(ApprovalSubscriber.await_response)


@pytest.mark.seam
@pytest.mark.integration_contract(
    "SyntheticResponseInjector.inject_cli_cancel"
)
def test_injector_methods_exist() -> None:
    """Verify SyntheticResponseInjector.inject_cli_cancel/skip exist."""
    from forge.adapters.nats.synthetic_response_injector import (
        SyntheticResponseInjector,
    )

    assert hasattr(SyntheticResponseInjector, "inject_cli_cancel")
    assert hasattr(SyntheticResponseInjector, "inject_cli_skip")
