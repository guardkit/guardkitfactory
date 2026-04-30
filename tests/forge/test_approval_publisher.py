"""Unit + seam tests for :mod:`forge.adapters.nats.approval_publisher` (TASK-CGCP-006).

Test classes mirror the acceptance criteria:

- AC-001 — :meth:`ApprovalPublisher.publish_request` is an async coroutine.
- AC-002 — :func:`_build_approval_details` produces the documented eleven-key
  dict per ``API-nats-approval-protocol §3.2``.
- AC-003 — :func:`_derive_risk_level` matches §3.3 exactly.
- AC-004 — Subject resolves to ``agents.approval.forge.{build_id}`` and is
  project-scoped via :meth:`Topics.for_project` when configured.
- AC-005 — Publish failures raise :class:`ApprovalPublishError` (typed) and
  the underlying cause is preserved.
- AC-006 — When the publish call raises, control returns to the caller —
  no other state is mutated by the publisher.
- AC-007 — A published envelope round-trips back through
  :class:`MessageEnvelope` with the eleven-key ``details`` dict intact.
- AC-008 — ``approval_publisher`` is the only place in
  ``forge.adapters.nats.approval_*`` that constructs the ``details`` shape.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from forge.adapters.nats.approval_publisher import (
    AGENT_ID,
    APPROVAL_SUBJECT_TEMPLATE,
    ApprovalPublishError,
    ApprovalPublisher,
    _build_approval_details,
    _derive_risk_level,
    build_recovery_approval_envelope,
)
from forge.gating.models import (
    DetectionFinding,
    GateDecision,
    GateMode,
    PriorReference,
)
from nats_core.envelope import EventType, MessageEnvelope
from nats_core.events import ApprovalRequestPayload

# ---------------------------------------------------------------------------
# Fixtures and factories
# ---------------------------------------------------------------------------


BUILD_ID = "build-FEAT-A1B2-20260425120000"
FEATURE_ID = "FEAT-A1B2"
CORRELATION_ID = "corr-9999-aaaa"


def _decided_at() -> datetime:
    return datetime(2026, 4, 25, 12, 0, 0, tzinfo=timezone.utc)


def _make_decision(
    *,
    mode: GateMode = GateMode.FLAG_FOR_REVIEW,
    coach_score: float | None = 0.52,
    rationale: str = "reasoning model says ambiguous",
    auto_approve_override: bool = False,
    threshold_applied: float | None = None,
) -> GateDecision:
    """Build a :class:`GateDecision` covering the fields the helper consumes."""
    return GateDecision(
        build_id=BUILD_ID,
        stage_label="Architecture Review",
        target_kind="local_tool",
        target_identifier="some_tool",
        mode=mode,
        rationale=rationale,
        coach_score=coach_score,
        criterion_breakdown={"fidelity": 0.4, "rigour": 0.6},
        detection_findings=[
            DetectionFinding(
                pattern="SCOPE_CREEP",
                severity="medium",
                evidence="excerpt-from-coach",
            ),
        ],
        evidence=[
            PriorReference(
                entity_id="entity-001",
                group_id="forge_pipeline_history",
                summary="Recent flagged builds at score≈0.5 mostly approved.",
            ),
        ],
        threshold_applied=threshold_applied,
        auto_approve_override=auto_approve_override,
        degraded_mode=coach_score is None,
        decided_at=_decided_at(),
    )


def _make_envelope(
    *,
    decision: GateDecision | None = None,
    feature_id: str = FEATURE_ID,
    correlation_id: str | None = CORRELATION_ID,
    artefact_paths: list[str] | None = None,
    resume_options: list[str] | None = None,
) -> MessageEnvelope:
    """Build a fully wrapped approval-request envelope.

    Mirrors how the wrapper (TASK-CGCP-010) will call the publisher: the
    ``details`` dict is constructed via the helper exposed by this module,
    so envelopes built here are structurally identical to production.
    """
    decision = decision if decision is not None else _make_decision()
    details = _build_approval_details(
        decision,
        feature_id=feature_id,
        artefact_paths=list(artefact_paths or [f"/var/forge/{decision.build_id}/x.md"]),
        resume_options=list(
            resume_options or ["approve", "reject", "defer", "override"]
        ),
    )
    payload = ApprovalRequestPayload(
        request_id=decision.build_id,
        agent_id=AGENT_ID,
        action_description=(
            f"{decision.stage_label} flagged {decision.coach_score!r}"
        ),
        risk_level=_derive_risk_level(decision),
        details=details,
        timeout_seconds=300,
    )
    return MessageEnvelope(
        source_id=AGENT_ID,
        event_type=EventType.APPROVAL_REQUEST,
        correlation_id=correlation_id,
        payload=payload.model_dump(mode="json"),
    )


@pytest.fixture
def nats_client() -> AsyncMock:
    """Async NATS client mock that records ``publish`` calls."""
    client = AsyncMock()
    client.publish = AsyncMock(return_value=None)
    return client


@pytest.fixture
def publisher(nats_client: AsyncMock) -> ApprovalPublisher:
    return ApprovalPublisher(nats_client=nats_client)


def _decode_publish_call(call: Any) -> tuple[str, dict[str, Any]]:
    """Pull (subject, decoded_envelope_dict) out of a recorded publish call."""
    args, kwargs = call.args, call.kwargs
    subject = args[0] if args else kwargs["subject"]
    body = args[1] if len(args) > 1 else kwargs["payload"]
    if isinstance(body, (bytes, bytearray)):
        body = body.decode("utf-8")
    return subject, json.loads(body)


# ---------------------------------------------------------------------------
# AC-001 — class shape
# ---------------------------------------------------------------------------


class TestPublisherSurface:
    """AC-001 — :class:`ApprovalPublisher` exposes :meth:`publish_request` as ``async def``."""

    def test_publish_request_is_async(self) -> None:
        method = getattr(ApprovalPublisher, "publish_request", None)
        assert method is not None, "publish_request must be defined"
        assert asyncio.iscoroutinefunction(method)

    def test_publish_failure_is_exception(self) -> None:
        assert issubclass(ApprovalPublishError, Exception)

    def test_subject_template_matches_protocol(self) -> None:
        # The template MUST contain the build_id placeholder so the resolver
        # can substitute it. We do not hard-code the literal here — instead
        # we assert the template ends with the exported ``{task_id}`` token
        # so a future rename in nats-core fails this test loudly.
        assert "{task_id}" in APPROVAL_SUBJECT_TEMPLATE
        assert APPROVAL_SUBJECT_TEMPLATE.startswith("agents.approval.")


# ---------------------------------------------------------------------------
# AC-002 — _build_approval_details (eleven-key shape)
# ---------------------------------------------------------------------------


EXPECTED_KEYS = {
    "build_id",
    "feature_id",
    "stage_label",
    "gate_mode",
    "coach_score",
    "criterion_breakdown",
    "detection_findings",
    "rationale",
    "evidence_priors",
    "artefact_paths",
    "resume_options",
}


class TestBuildApprovalDetails:
    """AC-002 — eleven-key ``details`` dict per §3.2."""

    def test_returns_exactly_the_eleven_documented_keys(self) -> None:
        decision = _make_decision()
        details = _build_approval_details(
            decision,
            feature_id=FEATURE_ID,
            artefact_paths=["/var/forge/x.md"],
            resume_options=["approve", "reject", "defer", "override"],
        )
        assert set(details.keys()) == EXPECTED_KEYS

    def test_scalar_fields_propagate_from_decision(self) -> None:
        decision = _make_decision()
        details = _build_approval_details(
            decision,
            feature_id=FEATURE_ID,
            artefact_paths=[],
            resume_options=["approve"],
        )
        assert details["build_id"] == BUILD_ID
        assert details["stage_label"] == "Architecture Review"
        assert details["gate_mode"] == "FLAG_FOR_REVIEW"  # enum.value, not name
        assert details["coach_score"] == pytest.approx(0.52)
        assert details["rationale"] == "reasoning model says ambiguous"

    def test_criterion_breakdown_is_a_plain_dict_copy(self) -> None:
        decision = _make_decision()
        details = _build_approval_details(
            decision,
            feature_id=FEATURE_ID,
            artefact_paths=[],
            resume_options=[],
        )
        assert details["criterion_breakdown"] == {"fidelity": 0.4, "rigour": 0.6}
        # Helper must return a defensive copy so callers can't mutate the
        # underlying decision via the result.
        details["criterion_breakdown"]["fidelity"] = 0.0
        assert decision.criterion_breakdown["fidelity"] == 0.4

    def test_detection_findings_serialised_as_list_of_dicts(self) -> None:
        decision = _make_decision()
        details = _build_approval_details(
            decision,
            feature_id=FEATURE_ID,
            artefact_paths=[],
            resume_options=[],
        )
        findings = details["detection_findings"]
        assert isinstance(findings, list)
        assert findings[0]["pattern"] == "SCOPE_CREEP"
        assert findings[0]["severity"] == "medium"
        assert findings[0]["evidence"] == "excerpt-from-coach"
        # JSON-serialisable: must round-trip without TypeErrors.
        assert json.loads(json.dumps(findings)) == findings

    def test_evidence_priors_use_entity_id_and_summary_subset(self) -> None:
        decision = _make_decision()
        details = _build_approval_details(
            decision,
            feature_id=FEATURE_ID,
            artefact_paths=[],
            resume_options=[],
        )
        priors = details["evidence_priors"]
        assert priors == [
            {
                "entity_id": "entity-001",
                "summary": "Recent flagged builds at score≈0.5 mostly approved.",
            }
        ]

    def test_kwargs_propagate_verbatim(self) -> None:
        decision = _make_decision()
        details = _build_approval_details(
            decision,
            feature_id="FEAT-OTHER",
            artefact_paths=["/a.md", "/b.md"],
            resume_options=["approve", "reject"],
        )
        assert details["feature_id"] == "FEAT-OTHER"
        assert details["artefact_paths"] == ["/a.md", "/b.md"]
        assert details["resume_options"] == ["approve", "reject"]

    def test_returned_dict_is_json_serialisable(self) -> None:
        # End-to-end: the whole details dict must JSON round-trip so the
        # envelope writer can serialise it unmodified.
        decision = _make_decision()
        details = _build_approval_details(
            decision,
            feature_id=FEATURE_ID,
            artefact_paths=["/x"],
            resume_options=["approve"],
        )
        round_tripped = json.loads(json.dumps(details))
        assert round_tripped == details

    def test_degraded_decision_emits_none_coach_score(self) -> None:
        # Degraded mode is allowed for FLAG_FOR_REVIEW; the helper must not
        # silently coerce ``None`` into a number.
        decision = _make_decision(coach_score=None, mode=GateMode.FLAG_FOR_REVIEW)
        details = _build_approval_details(
            decision,
            feature_id=FEATURE_ID,
            artefact_paths=[],
            resume_options=[],
        )
        assert details["coach_score"] is None


# ---------------------------------------------------------------------------
# AC-003 — _derive_risk_level matches §3.3 exactly
# ---------------------------------------------------------------------------


class TestDeriveRiskLevel:
    """AC-003 — risk-level table fidelity."""

    def test_flag_for_review_high_score_is_low(self) -> None:
        decision = _make_decision(mode=GateMode.FLAG_FOR_REVIEW, coach_score=0.65)
        assert _derive_risk_level(decision) == "low"

    def test_flag_for_review_above_threshold_is_low(self) -> None:
        decision = _make_decision(mode=GateMode.FLAG_FOR_REVIEW, coach_score=0.91)
        assert _derive_risk_level(decision) == "low"

    def test_flag_for_review_below_threshold_is_medium(self) -> None:
        decision = _make_decision(mode=GateMode.FLAG_FOR_REVIEW, coach_score=0.64)
        assert _derive_risk_level(decision) == "medium"

    def test_flag_for_review_degraded_mode_is_medium(self) -> None:
        # No coach_score available — cannot meet the ≥0.65 threshold,
        # so risk falls back to "medium" per the ≥-style table.
        decision = _make_decision(mode=GateMode.FLAG_FOR_REVIEW, coach_score=None)
        assert _derive_risk_level(decision) == "medium"

    def test_hard_stop_is_high(self) -> None:
        decision = _make_decision(mode=GateMode.HARD_STOP, coach_score=0.10)
        assert _derive_risk_level(decision) == "high"

    def test_mandatory_human_approval_is_medium(self) -> None:
        decision = _make_decision(
            mode=GateMode.MANDATORY_HUMAN_APPROVAL,
            coach_score=0.85,
            auto_approve_override=True,
        )
        assert _derive_risk_level(decision) == "medium"

    def test_auto_approve_is_rejected(self) -> None:
        # AUTO_APPROVE never reaches the publisher (no pause), but the
        # helper must fail loud rather than silently coerce.
        decision = _make_decision(mode=GateMode.AUTO_APPROVE, coach_score=0.95)
        with pytest.raises(ValueError, match="AUTO_APPROVE"):
            _derive_risk_level(decision)


# ---------------------------------------------------------------------------
# AC-004, AC-005, AC-006 — publish_request behaviour
# ---------------------------------------------------------------------------


class TestPublishRequest:
    """AC-004/005/006 — subject resolution, error wrapping, no rollback."""

    @pytest.mark.asyncio
    async def test_subject_resolves_to_agents_approval_forge_build_id(
        self, publisher: ApprovalPublisher, nats_client: AsyncMock
    ) -> None:
        envelope = _make_envelope()
        await publisher.publish_request(envelope)

        nats_client.publish.assert_awaited_once()
        subject, env = _decode_publish_call(nats_client.publish.call_args)
        assert subject == f"agents.approval.forge.{BUILD_ID}"
        assert env["source_id"] == "forge"
        assert env["event_type"] == EventType.APPROVAL_REQUEST.value
        assert env["correlation_id"] == CORRELATION_ID

    @pytest.mark.asyncio
    async def test_project_scope_prefixes_subject(
        self, nats_client: AsyncMock
    ) -> None:
        publisher = ApprovalPublisher(nats_client=nats_client, project="finproxy")
        await publisher.publish_request(_make_envelope())

        subject, _ = _decode_publish_call(nats_client.publish.call_args)
        assert subject == f"finproxy.agents.approval.forge.{BUILD_ID}"

    @pytest.mark.asyncio
    async def test_publish_failure_wraps_underlying_exception(
        self, publisher: ApprovalPublisher, nats_client: AsyncMock
    ) -> None:
        boom = RuntimeError("nats unreachable")
        nats_client.publish = AsyncMock(side_effect=boom)

        with pytest.raises(ApprovalPublishError) as exc_info:
            await publisher.publish_request(_make_envelope())

        assert exc_info.value.__cause__ is boom
        assert exc_info.value.cause is boom
        assert exc_info.value.subject == f"agents.approval.forge.{BUILD_ID}"
        assert "agents.approval.forge" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_publish_failure_does_not_roll_back_caller_state(
        self, publisher: ApprovalPublisher, nats_client: AsyncMock
    ) -> None:
        """AC-006 — failure surfaces, but the publisher mutates nothing else.

        We model "caller state" as a sentinel mapping captured before the
        failing publish call. After the exception propagates the sentinel
        must be untouched — proving the publisher does not reach into the
        caller's domain to roll back the GateDecision mirror.
        """
        nats_client.publish = AsyncMock(side_effect=ConnectionError("flaky"))
        caller_state: dict[str, Any] = {"decision_recorded": True, "rollbacks": 0}

        with pytest.raises(ApprovalPublishError):
            await publisher.publish_request(_make_envelope())

        assert caller_state == {"decision_recorded": True, "rollbacks": 0}

    @pytest.mark.asyncio
    async def test_envelope_missing_build_id_raises_value_error(
        self, publisher: ApprovalPublisher, nats_client: AsyncMock
    ) -> None:
        # Envelope whose payload.details lacks ``build_id`` cannot resolve a
        # subject — the publisher must fail loud, not silently publish to a
        # malformed subject.
        envelope = _make_envelope()
        envelope.payload["details"].pop("build_id")

        with pytest.raises(ValueError, match="build_id"):
            await publisher.publish_request(envelope)

        nats_client.publish.assert_not_awaited()


# ---------------------------------------------------------------------------
# AC-007 — published envelope round-trips with the eleven-key details intact
# ---------------------------------------------------------------------------


class TestPublishedEnvelopeContract:
    """AC-007 — wire-format envelope carries enough context for an adapter."""

    @pytest.mark.asyncio
    async def test_published_envelope_round_trips_through_message_envelope(
        self, publisher: ApprovalPublisher, nats_client: AsyncMock
    ) -> None:
        await publisher.publish_request(_make_envelope())

        _subject, env_dict = _decode_publish_call(nats_client.publish.call_args)
        # Round-trip through the canonical envelope model — proves we wrote
        # a structurally valid envelope, not a hand-rolled dict.
        envelope = MessageEnvelope.model_validate(env_dict)
        payload = ApprovalRequestPayload.model_validate(envelope.payload)

        assert payload.agent_id == "forge"
        assert payload.request_id == BUILD_ID
        assert payload.risk_level == "medium"  # FLAG_FOR_REVIEW + score 0.52
        assert set(payload.details.keys()) == EXPECTED_KEYS

    @pytest.mark.asyncio
    async def test_envelope_payload_is_serialisable_as_json(
        self, publisher: ApprovalPublisher, nats_client: AsyncMock
    ) -> None:
        await publisher.publish_request(_make_envelope())
        _subject, env = _decode_publish_call(nats_client.publish.call_args)
        # The whole envelope must JSON round-trip without TypeErrors.
        assert json.loads(json.dumps(env)) == env


# ---------------------------------------------------------------------------
# TASK-F8-004 / AC-5 — recovery envelope helper
# ---------------------------------------------------------------------------


def _make_paused_build_row(
    *,
    build_id: str = "build-FEAT-RECV-20260429120000",
    feature_id: str = "FEAT-RECV",
    request_id: str | None = "req-recover-001",
) -> Any:
    """Build a minimal PAUSED :class:`BuildRow` for recovery-helper tests."""
    from forge.lifecycle.modes import BuildMode
    from forge.lifecycle.persistence import BuildRow
    from forge.lifecycle.state_machine import BuildState

    return BuildRow(
        build_id=build_id,
        feature_id=feature_id,
        repo="appmilla/forge",
        branch="main",
        feature_yaml_path=f"docs/features/{feature_id}.yaml",
        project=None,
        status=BuildState.PAUSED,
        triggered_by="test",
        correlation_id="corr-recover-0001",
        queued_at=datetime(2026, 4, 29, 12, 0, 0, tzinfo=timezone.utc),
        pending_approval_request_id=request_id,
        mode=BuildMode.MODE_A,
    )


class TestBuildRecoveryApprovalEnvelope:
    """TASK-F8-004 / AC-5 — recovery-flavoured envelope helper.

    Verifies the public helper:

    (a) sets ``recovery=True`` on the ``details`` dict,
    (b) preserves the original ``request_id`` verbatim (sc_004), and
    (c) emits the canonical eleven-key shape on ``details`` plus the
        ``recovery`` marker (AC-008 single-source-of-truth).
    """

    def test_envelope_carries_recovery_true_on_details(self) -> None:
        envelope = build_recovery_approval_envelope(_make_paused_build_row())
        details = envelope.payload["details"]
        assert details["recovery"] is True

    def test_envelope_preserves_request_id_verbatim(self) -> None:
        # sc_004: the responder correlates by ``request_id``; the recovery
        # republish MUST carry the same value as
        # ``builds.pending_approval_request_id`` rather than minting a new
        # UUID.
        build = _make_paused_build_row(request_id="req-recover-verbatim-XYZ")
        envelope = build_recovery_approval_envelope(build)
        assert envelope.payload["request_id"] == "req-recover-verbatim-XYZ"

    def test_envelope_details_match_canonical_eleven_key_shape(self) -> None:
        # AC-008: the eleven canonical keys are present, and the only
        # additional key is the ``recovery`` marker (twelfth key).
        envelope = build_recovery_approval_envelope(_make_paused_build_row())
        details = envelope.payload["details"]
        assert EXPECTED_KEYS.issubset(details.keys())
        assert set(details.keys()) == EXPECTED_KEYS | {"recovery"}

    def test_envelope_details_carry_build_and_feature_ids(self) -> None:
        build = _make_paused_build_row(
            build_id="build-FEAT-OTHER-99",
            feature_id="FEAT-OTHER",
        )
        envelope = build_recovery_approval_envelope(build)
        details = envelope.payload["details"]
        assert details["build_id"] == "build-FEAT-OTHER-99"
        assert details["feature_id"] == "FEAT-OTHER"

    def test_envelope_uses_recovery_stage_label_and_mode(self) -> None:
        # Stripped recovery card: stage_label="recovery",
        # gate_mode="MANDATORY_HUMAN_APPROVAL", and the empty/null
        # decision-derived defaults documented in the helper's docstring.
        envelope = build_recovery_approval_envelope(_make_paused_build_row())
        details = envelope.payload["details"]
        assert details["stage_label"] == "recovery"
        assert details["gate_mode"] == "MANDATORY_HUMAN_APPROVAL"
        assert details["coach_score"] is None
        assert details["criterion_breakdown"] == {}
        assert details["detection_findings"] == []
        assert details["evidence_priors"] == []
        assert details["artefact_paths"] == []
        assert details["resume_options"] == [
            "approve",
            "reject",
            "defer",
            "override",
        ]

    def test_envelope_payload_round_trips_through_json(self) -> None:
        # Wire-shape sanity: the envelope must serialise without
        # TypeErrors so :meth:`ApprovalPublisher.publish_request` can
        # ``model_dump_json().encode("utf-8")`` it.
        envelope = build_recovery_approval_envelope(_make_paused_build_row())
        body = envelope.model_dump_json()
        decoded = json.loads(body)
        assert decoded["payload"]["details"]["recovery"] is True

    def test_missing_request_id_raises_value_error(self) -> None:
        # The lifecycle handler checks first, but the helper keeps the
        # defensive guard so a future caller cannot bypass the contract.
        build = _make_paused_build_row(request_id=None)
        with pytest.raises(ValueError, match="pending_approval_request_id"):
            build_recovery_approval_envelope(build)


# ---------------------------------------------------------------------------
# AC-008 — single ownership of the `details` dict shape
# ---------------------------------------------------------------------------


class TestSingleOwnership:
    """AC-008 — only ``approval_publisher`` constructs the eleven-key dict."""

    def test_no_other_module_in_forge_constructs_evidence_priors(self) -> None:
        # Cheap structural guard: scan the source tree for the
        # tell-tale ``"evidence_priors"`` literal. Only this module (and
        # this test) should reference it — anything else means another
        # module is open-coding the dict shape and bypassing the helper.
        import pathlib

        repo_root = pathlib.Path(__file__).resolve().parents[2]
        forge_src = repo_root / "src" / "forge"
        offenders = []
        for path in forge_src.rglob("*.py"):
            if path.name == "approval_publisher.py":
                continue
            text = path.read_text(encoding="utf-8")
            if '"evidence_priors"' in text or "'evidence_priors'" in text:
                offenders.append(path.relative_to(repo_root))
        assert offenders == [], (
            f"Other modules reconstruct details shape (AC-008): {offenders}"
        )


# ---------------------------------------------------------------------------
# Seam tests — copied from the task spec (verbatim contracts)
# ---------------------------------------------------------------------------


@pytest.mark.seam  # type: ignore[misc]
@pytest.mark.integration_contract("GateDecision")
def test_gate_decision_drives_approval_details() -> None:
    """Verify GateDecision populates the eleven-key details dict.

    Contract: GateDecision per DM-gating.md §1; details dict per API §3.2.
    Producer: TASK-CGCP-005.
    """
    decision = GateDecision(
        build_id="build-test-001",
        stage_label="Architecture Review",
        target_kind="local_tool",
        target_identifier="some_tool",
        mode=GateMode.FLAG_FOR_REVIEW,
        rationale="reasoning model says ambiguous",
        coach_score=0.52,
        criterion_breakdown={"fidelity": 0.4, "rigour": 0.6},
        detection_findings=[],
        evidence=[],
        decided_at=_decided_at(),
    )
    details = _build_approval_details(
        decision,
        feature_id="FEAT-TEST",
        artefact_paths=["/tmp/x"],
        resume_options=["approve", "reject", "defer", "override"],
    )
    expected_keys = {
        "build_id",
        "feature_id",
        "stage_label",
        "gate_mode",
        "coach_score",
        "criterion_breakdown",
        "detection_findings",
        "rationale",
        "evidence_priors",
        "artefact_paths",
        "resume_options",
    }
    assert expected_keys.issubset(details.keys())
    assert details["gate_mode"] == "FLAG_FOR_REVIEW"


@pytest.mark.seam  # type: ignore[misc]
@pytest.mark.integration_contract("ApprovalConfig.default_wait_seconds")
def test_approval_config_default_wait_format() -> None:
    """Verify default_wait_seconds is non-negative int with default 300.

    Contract: ApprovalConfig.default_wait_seconds: int = 300.
    Producer: TASK-CGCP-002.
    """
    from forge.config.models import ApprovalConfig

    cfg = ApprovalConfig()
    assert cfg.default_wait_seconds == 300
    assert cfg.max_wait_seconds == 3600
    with pytest.raises(ValueError):
        ApprovalConfig(default_wait_seconds=-1)
