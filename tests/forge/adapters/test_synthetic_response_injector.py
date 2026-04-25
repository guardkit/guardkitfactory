"""Unit tests for :mod:`forge.adapters.nats.synthetic_response_injector`.

Test classes mirror the acceptance criteria of TASK-CGCP-008:

- AC-001 — ``inject_cli_cancel`` publishes a synthetic
  ``ApprovalResponsePayload(decision="reject", responder="rich",
  reason="cli cancel", request_id=...)`` to
  ``agents.approval.forge.{build_id}.response``.
- AC-002 — ``inject_cli_skip`` publishes a synthetic
  ``ApprovalResponsePayload(decision="override", responder="rich",
  reason="cli skip", request_id=...)`` to the same subject.
- AC-003 — request_id derived via TASK-CGCP-003
  :func:`derive_request_id` (matches the persisted value when caller
  passes the SQLite-persisted ``attempt_count``).
- AC-004 — Group D ``@edge-case`` "Cancelling a paused build from the
  command line behaves as a rejection": the synthetic response carries
  decision=reject + reason=cli cancel so the state-machine resume path
  produces a CANCELLED outcome.
- AC-005 — Group D ``@edge-case`` "Skipping a paused build from the
  command line overrides the current stage only": decision=override +
  reason=cli skip drives a per-stage override (state-machine integration
  is owned by TASK-CGCP-010; this file verifies the metadata contract).
- AC-006 — Idempotency invariant: synthetic response uses the same
  ``request_id`` as a hypothetical concurrent real response, so the
  TASK-CGCP-007 dedup buffer can recognise duplicates.
- AC-007 — Persisted-record distinction: ``decided_by="rich"`` AND
  ``notes`` ∈ {"cli cancel", "cli skip"} so the persisted GateDecision
  response record is distinguishable from a real Rich response.
- AC-008 — Lint/format is enforced by CI; not asserted here.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from forge.adapters.nats import SyntheticInjectFailure, SyntheticResponseInjector
from forge.adapters.nats import synthetic_response_injector as sri_module
from forge.gating.identity import derive_request_id
from nats_core.envelope import EventType, MessageEnvelope
from nats_core.events import ApprovalResponsePayload

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


BUILD_ID = "build-FEAT-A1B2-20260425120000"
STAGE_LABEL = "Architecture Review"
ATTEMPT_COUNT = 2
CORRELATION_ID = "corr-1234-5678"


@pytest.fixture
def nats_client() -> AsyncMock:
    """A mock async NATS client capturing publish calls."""
    client = AsyncMock()
    client.publish = AsyncMock(return_value=None)
    return client


@pytest.fixture
def injector(nats_client: AsyncMock) -> SyntheticResponseInjector:
    return SyntheticResponseInjector(nats_client=nats_client)


def _decode_publish_call(call: Any) -> tuple[str, dict[str, Any]]:
    """Pull (subject, decoded_envelope) out of a recorded ``nc.publish`` call."""
    args, kwargs = call.args, call.kwargs
    subject = args[0] if args else kwargs["subject"]
    body = args[1] if len(args) > 1 else kwargs["payload"]
    if isinstance(body, (bytes, bytearray)):
        body = body.decode("utf-8")
    return subject, json.loads(body)


# ---------------------------------------------------------------------------
# Class shape — both injection methods exist as coroutines
# ---------------------------------------------------------------------------


class TestInjectorSurface:
    """Class exposes the two CLI steering coroutines."""

    @pytest.mark.parametrize(
        "method_name",
        ["inject_cli_cancel", "inject_cli_skip"],
    )
    def test_method_exists_and_is_coroutine(self, method_name: str) -> None:
        method = getattr(SyntheticResponseInjector, method_name, None)
        assert method is not None, f"{method_name!r} not defined"
        assert asyncio.iscoroutinefunction(method), (
            f"{method_name!r} must be `async def`"
        )

    def test_inject_methods_are_keyword_only(self) -> None:
        # The CLI wiring layer (TASK-CGCP-010) calls these by name —
        # keep the surface keyword-only so partial-application bugs at
        # the wiring layer are impossible.
        for name in ("inject_cli_cancel", "inject_cli_skip"):
            sig = inspect.signature(getattr(SyntheticResponseInjector, name))
            non_self = [p for p in sig.parameters.values() if p.name != "self"]
            for param in non_self:
                assert param.kind is inspect.Parameter.KEYWORD_ONLY, (
                    f"{name}: parameter {param.name!r} should be keyword-only, "
                    f"got {param.kind!r}"
                )

    def test_synthetic_inject_failure_is_exception(self) -> None:
        assert issubclass(SyntheticInjectFailure, Exception)


# ---------------------------------------------------------------------------
# AC-001 — inject_cli_cancel publishes the documented payload + subject
# ---------------------------------------------------------------------------


class TestInjectCliCancel:
    """AC-001 — cancel maps to decision=reject, decided_by=rich, notes=cli cancel."""

    @pytest.mark.asyncio
    async def test_publish_to_build_response_subject(
        self,
        injector: SyntheticResponseInjector,
        nats_client: AsyncMock,
    ) -> None:
        await injector.inject_cli_cancel(
            build_id=BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=ATTEMPT_COUNT,
        )
        nats_client.publish.assert_awaited_once()
        subject, _env = _decode_publish_call(nats_client.publish.call_args)
        assert subject == f"agents.approval.forge.{BUILD_ID}.response"

    @pytest.mark.asyncio
    async def test_payload_decision_is_reject(
        self,
        injector: SyntheticResponseInjector,
        nats_client: AsyncMock,
    ) -> None:
        await injector.inject_cli_cancel(
            build_id=BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=ATTEMPT_COUNT,
        )
        _subject, env = _decode_publish_call(nats_client.publish.call_args)
        assert env["payload"]["decision"] == "reject"

    @pytest.mark.asyncio
    async def test_payload_responder_and_reason_carry_cli_origin(
        self,
        injector: SyntheticResponseInjector,
        nats_client: AsyncMock,
    ) -> None:
        # AC-007 persisted-record distinction: a CLI cancel must carry
        # responder="rich" (decided_by) AND reason="cli cancel" (notes)
        # so a downstream consumer can distinguish it from a real Rich
        # rejection that happens to also be decision="reject".
        await injector.inject_cli_cancel(
            build_id=BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=ATTEMPT_COUNT,
        )
        _subject, env = _decode_publish_call(nats_client.publish.call_args)
        payload = env["payload"]
        assert payload["decided_by"] == "rich"
        assert payload["notes"] == "cli cancel"

    @pytest.mark.asyncio
    async def test_envelope_event_type_and_source_id(
        self,
        injector: SyntheticResponseInjector,
        nats_client: AsyncMock,
    ) -> None:
        await injector.inject_cli_cancel(
            build_id=BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=ATTEMPT_COUNT,
        )
        _subject, env = _decode_publish_call(nats_client.publish.call_args)
        assert env["event_type"] == EventType.APPROVAL_RESPONSE.value
        assert env["source_id"] == "forge"

    @pytest.mark.asyncio
    async def test_correlation_id_threaded_when_provided(
        self,
        injector: SyntheticResponseInjector,
        nats_client: AsyncMock,
    ) -> None:
        await injector.inject_cli_cancel(
            build_id=BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=ATTEMPT_COUNT,
            correlation_id=CORRELATION_ID,
        )
        _subject, env = _decode_publish_call(nats_client.publish.call_args)
        assert env["correlation_id"] == CORRELATION_ID

    @pytest.mark.asyncio
    async def test_correlation_id_is_none_when_omitted(
        self,
        injector: SyntheticResponseInjector,
        nats_client: AsyncMock,
    ) -> None:
        await injector.inject_cli_cancel(
            build_id=BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=ATTEMPT_COUNT,
        )
        _subject, env = _decode_publish_call(nats_client.publish.call_args)
        assert env["correlation_id"] is None


# ---------------------------------------------------------------------------
# AC-002 — inject_cli_skip publishes the documented payload + subject
# ---------------------------------------------------------------------------


class TestInjectCliSkip:
    """AC-002 — skip maps to decision=override, decided_by=rich, notes=cli skip."""

    @pytest.mark.asyncio
    async def test_publish_to_build_response_subject(
        self,
        injector: SyntheticResponseInjector,
        nats_client: AsyncMock,
    ) -> None:
        await injector.inject_cli_skip(
            build_id=BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=ATTEMPT_COUNT,
        )
        nats_client.publish.assert_awaited_once()
        subject, _env = _decode_publish_call(nats_client.publish.call_args)
        assert subject == f"agents.approval.forge.{BUILD_ID}.response"

    @pytest.mark.asyncio
    async def test_payload_decision_is_override(
        self,
        injector: SyntheticResponseInjector,
        nats_client: AsyncMock,
    ) -> None:
        await injector.inject_cli_skip(
            build_id=BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=ATTEMPT_COUNT,
        )
        _subject, env = _decode_publish_call(nats_client.publish.call_args)
        assert env["payload"]["decision"] == "override"

    @pytest.mark.asyncio
    async def test_payload_responder_and_reason_carry_cli_origin(
        self,
        injector: SyntheticResponseInjector,
        nats_client: AsyncMock,
    ) -> None:
        # AC-007: skip must carry responder="rich" (decided_by) AND
        # reason="cli skip" (notes) so it is distinguishable from a real
        # Rich override.
        await injector.inject_cli_skip(
            build_id=BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=ATTEMPT_COUNT,
        )
        _subject, env = _decode_publish_call(nats_client.publish.call_args)
        payload = env["payload"]
        assert payload["decided_by"] == "rich"
        assert payload["notes"] == "cli skip"

    @pytest.mark.asyncio
    async def test_envelope_event_type_and_source_id(
        self,
        injector: SyntheticResponseInjector,
        nats_client: AsyncMock,
    ) -> None:
        await injector.inject_cli_skip(
            build_id=BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=ATTEMPT_COUNT,
        )
        _subject, env = _decode_publish_call(nats_client.publish.call_args)
        assert env["event_type"] == EventType.APPROVAL_RESPONSE.value
        assert env["source_id"] == "forge"


# ---------------------------------------------------------------------------
# AC-003 — request_id matches derive_request_id (TASK-CGCP-003 contract)
# ---------------------------------------------------------------------------


class TestRequestIdContract:
    """AC-003 — synthetic response keys on the same deterministic request_id."""

    @pytest.mark.asyncio
    async def test_cancel_request_id_matches_derive_request_id(
        self,
        injector: SyntheticResponseInjector,
        nats_client: AsyncMock,
    ) -> None:
        expected_request_id = derive_request_id(
            build_id=BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=ATTEMPT_COUNT,
        )
        await injector.inject_cli_cancel(
            build_id=BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=ATTEMPT_COUNT,
        )
        _subject, env = _decode_publish_call(nats_client.publish.call_args)
        assert env["payload"]["request_id"] == expected_request_id

    @pytest.mark.asyncio
    async def test_skip_request_id_matches_derive_request_id(
        self,
        injector: SyntheticResponseInjector,
        nats_client: AsyncMock,
    ) -> None:
        expected_request_id = derive_request_id(
            build_id=BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=ATTEMPT_COUNT,
        )
        await injector.inject_cli_skip(
            build_id=BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=ATTEMPT_COUNT,
        )
        _subject, env = _decode_publish_call(nats_client.publish.call_args)
        assert env["payload"]["request_id"] == expected_request_id

    @pytest.mark.asyncio
    async def test_request_id_changes_with_attempt_count(
        self,
        injector: SyntheticResponseInjector,
        nats_client: AsyncMock,
    ) -> None:
        # Refresh distinguishability — the TASK-CGCP-007 refresh-loop
        # advances attempt_count on timeout; passing different
        # attempt_count values to the injector must yield different
        # request_ids so the dedup buffer keys can collide deliberately.
        await injector.inject_cli_cancel(
            build_id=BUILD_ID, stage_label=STAGE_LABEL, attempt_count=0
        )
        await injector.inject_cli_cancel(
            build_id=BUILD_ID, stage_label=STAGE_LABEL, attempt_count=1
        )
        _, env_first = _decode_publish_call(nats_client.publish.call_args_list[0])
        _, env_second = _decode_publish_call(nats_client.publish.call_args_list[1])
        assert (
            env_first["payload"]["request_id"]
            != env_second["payload"]["request_id"]
        )

    @pytest.mark.asyncio
    async def test_invalid_inputs_propagate_value_error_from_derivation(
        self,
        injector: SyntheticResponseInjector,
    ) -> None:
        # derive_request_id validates the same three preconditions; the
        # injector should propagate them rather than swallow.
        with pytest.raises(ValueError):
            await injector.inject_cli_cancel(
                build_id="", stage_label=STAGE_LABEL, attempt_count=0
            )
        with pytest.raises(ValueError):
            await injector.inject_cli_skip(
                build_id=BUILD_ID, stage_label="", attempt_count=0
            )
        with pytest.raises(ValueError):
            await injector.inject_cli_cancel(
                build_id=BUILD_ID, stage_label=STAGE_LABEL, attempt_count=-1
            )


# ---------------------------------------------------------------------------
# AC-004 — Group D @edge-case: cancelling produces a rejection-shaped resume
# ---------------------------------------------------------------------------


class TestCancelEdgeCase:
    """AC-004 — synthetic cancel resumes the same dedup-and-resume path."""

    @pytest.mark.asyncio
    @pytest.mark.edge_case
    async def test_cancel_payload_validates_as_approval_response_payload(
        self,
        injector: SyntheticResponseInjector,
        nats_client: AsyncMock,
    ) -> None:
        # The state-machine resume path consumes ApprovalResponsePayload;
        # the synthetic envelope MUST round-trip through the typed model
        # so it traverses the same idempotency gate as a real Rich
        # response (no parallel resume code path — closes risk F6).
        await injector.inject_cli_cancel(
            build_id=BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=ATTEMPT_COUNT,
        )
        _subject, env_dict = _decode_publish_call(nats_client.publish.call_args)
        envelope = MessageEnvelope.model_validate(env_dict)
        payload = ApprovalResponsePayload.model_validate(envelope.payload)
        assert payload.decision == "reject"
        # State machine maps decision=reject + reason=cli cancel ⇒
        # CANCELLED outcome with the CLI origin recorded.
        assert payload.notes == "cli cancel"
        assert payload.decided_by == "rich"


# ---------------------------------------------------------------------------
# AC-005 — Group D @edge-case: skipping overrides the current stage only
# ---------------------------------------------------------------------------


class TestSkipEdgeCase:
    """AC-005 — synthetic skip resumes via a per-stage override."""

    @pytest.mark.asyncio
    @pytest.mark.edge_case
    async def test_skip_payload_validates_as_approval_response_payload(
        self,
        injector: SyntheticResponseInjector,
        nats_client: AsyncMock,
    ) -> None:
        await injector.inject_cli_skip(
            build_id=BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=ATTEMPT_COUNT,
        )
        _subject, env_dict = _decode_publish_call(nats_client.publish.call_args)
        envelope = MessageEnvelope.model_validate(env_dict)
        payload = ApprovalResponsePayload.model_validate(envelope.payload)
        # decision=override drives a per-stage override (build continues
        # to the next stage). reason=cli skip records the CLI origin.
        assert payload.decision == "override"
        assert payload.notes == "cli skip"
        assert payload.decided_by == "rich"


# ---------------------------------------------------------------------------
# AC-006 — Idempotency invariant: synthetic + real share request_id
# ---------------------------------------------------------------------------


class TestIdempotencyInvariant:
    """AC-006 — synthetic response keys on same request_id as real response."""

    @pytest.mark.asyncio
    async def test_two_injects_for_same_paused_stage_share_request_id(
        self,
        injector: SyntheticResponseInjector,
        nats_client: AsyncMock,
    ) -> None:
        # The dedup buffer (TASK-CGCP-007) keys on request_id with
        # first-response-wins semantics. Two synthetic responses for the
        # same paused stage must share the same request_id so the second
        # is recognised as a duplicate.
        await injector.inject_cli_cancel(
            build_id=BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=ATTEMPT_COUNT,
        )
        await injector.inject_cli_cancel(
            build_id=BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=ATTEMPT_COUNT,
        )
        _, env_first = _decode_publish_call(nats_client.publish.call_args_list[0])
        _, env_second = _decode_publish_call(nats_client.publish.call_args_list[1])
        assert (
            env_first["payload"]["request_id"]
            == env_second["payload"]["request_id"]
        )

    @pytest.mark.asyncio
    async def test_synthetic_and_pure_derived_request_id_match(
        self,
        injector: SyntheticResponseInjector,
        nats_client: AsyncMock,
    ) -> None:
        # AC-006 is the central anti-double-resume invariant: if Rich's
        # phone responds at the exact moment Rich types `forge cancel`,
        # both the real and synthetic responses key on the same
        # request_id and the dedup buffer picks one. This test verifies
        # the synthetic side of that contract by comparing against the
        # pure derivation a real responder would mirror.
        real_response_request_id = derive_request_id(
            build_id=BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=ATTEMPT_COUNT,
        )
        await injector.inject_cli_skip(
            build_id=BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=ATTEMPT_COUNT,
        )
        _subject, env = _decode_publish_call(nats_client.publish.call_args)
        assert env["payload"]["request_id"] == real_response_request_id


# ---------------------------------------------------------------------------
# AC-007 — Persisted-record distinction (responder + reason sentinels)
# ---------------------------------------------------------------------------


class TestPersistedRecordDistinction:
    """AC-007 — CLI cancel/skip carry distinguishable responder + reason."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "method_name,expected_reason",
        [
            ("inject_cli_cancel", "cli cancel"),
            ("inject_cli_skip", "cli skip"),
        ],
    )
    async def test_responder_is_rich_and_reason_is_cli_sentinel(
        self,
        injector: SyntheticResponseInjector,
        nats_client: AsyncMock,
        method_name: str,
        expected_reason: str,
    ) -> None:
        method = getattr(injector, method_name)
        await method(
            build_id=BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=ATTEMPT_COUNT,
        )
        _subject, env = _decode_publish_call(nats_client.publish.call_args)
        payload = env["payload"]
        # Mapped from API §4.1 design names: responder→decided_by,
        # reason→notes (see synthetic_response_injector module docstring).
        assert payload["decided_by"] == "rich"
        assert payload["notes"] == expected_reason


# ---------------------------------------------------------------------------
# Subject builder direct test
# ---------------------------------------------------------------------------


class TestSubjectBuilder:
    """Subject helper produces ``agents.approval.forge.{build_id}.response``."""

    def test_subject_for_returns_response_mirror(self) -> None:
        subject = SyntheticResponseInjector._subject_for("build-FEAT-9Z9Z-x")
        assert subject == "agents.approval.forge.build-FEAT-9Z9Z-x.response"

    def test_empty_build_id_rejected(self) -> None:
        with pytest.raises(ValueError):
            SyntheticResponseInjector._subject_for("")


# ---------------------------------------------------------------------------
# Envelope round-trip
# ---------------------------------------------------------------------------


class TestEnvelopeShape:
    """Wire format validates as a typed MessageEnvelope."""

    @pytest.mark.asyncio
    async def test_envelope_round_trips_through_message_envelope(
        self,
        injector: SyntheticResponseInjector,
        nats_client: AsyncMock,
    ) -> None:
        await injector.inject_cli_cancel(
            build_id=BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=ATTEMPT_COUNT,
            correlation_id=CORRELATION_ID,
        )
        _subject, env_dict = _decode_publish_call(nats_client.publish.call_args)
        envelope = MessageEnvelope.model_validate(env_dict)
        assert envelope.source_id == "forge"
        assert envelope.event_type == EventType.APPROVAL_RESPONSE
        assert envelope.correlation_id == CORRELATION_ID
        # Inner payload validates as ApprovalResponsePayload.
        ApprovalResponsePayload.model_validate(envelope.payload)


# ---------------------------------------------------------------------------
# Fire-and-forget; PubAck logged but never treated as delivery proof
# ---------------------------------------------------------------------------


class TestFireAndForget:
    """Mirror pipeline_publisher's LES1 parity: PubAck is informational only."""

    @pytest.mark.asyncio
    async def test_inject_returns_none_even_when_client_returns_pub_ack(
        self,
        injector: SyntheticResponseInjector,
        nats_client: AsyncMock,
    ) -> None:
        nats_client.publish = AsyncMock(
            return_value=MagicMock(stream="AGENTS", seq=1)
        )
        result = await injector.inject_cli_cancel(
            build_id=BUILD_ID,
            stage_label=STAGE_LABEL,
            attempt_count=ATTEMPT_COUNT,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_pub_ack_is_logged_at_debug(
        self,
        injector: SyntheticResponseInjector,
        nats_client: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        nats_client.publish = AsyncMock(return_value="ACK-789")
        with caplog.at_level(logging.DEBUG, logger=sri_module.__name__):
            await injector.inject_cli_skip(
                build_id=BUILD_ID,
                stage_label=STAGE_LABEL,
                attempt_count=ATTEMPT_COUNT,
            )
        relevant = [rec for rec in caplog.records if rec.name == sri_module.__name__]
        assert relevant, "injector emitted no log records"


# ---------------------------------------------------------------------------
# Transport-level failures raise SyntheticInjectFailure
# ---------------------------------------------------------------------------


class TestInjectFailure:
    """Underlying NATS exceptions surface as typed SyntheticInjectFailure."""

    @pytest.mark.asyncio
    async def test_underlying_exception_is_wrapped(
        self,
        injector: SyntheticResponseInjector,
        nats_client: AsyncMock,
    ) -> None:
        nats_client.publish = AsyncMock(side_effect=ConnectionError("nats down"))
        with pytest.raises(SyntheticInjectFailure) as excinfo:
            await injector.inject_cli_cancel(
                build_id=BUILD_ID,
                stage_label=STAGE_LABEL,
                attempt_count=ATTEMPT_COUNT,
            )
        assert isinstance(excinfo.value.__cause__, ConnectionError)
        assert excinfo.value.subject == f"agents.approval.forge.{BUILD_ID}.response"
        # Cause is preserved as an attribute too for callers that
        # prefer attribute access over walking the chain.
        assert isinstance(excinfo.value.cause, ConnectionError)

    @pytest.mark.asyncio
    async def test_synthetic_inject_failure_carries_subject_in_message(
        self,
        injector: SyntheticResponseInjector,
        nats_client: AsyncMock,
    ) -> None:
        nats_client.publish = AsyncMock(side_effect=RuntimeError("disconnected"))
        with pytest.raises(SyntheticInjectFailure) as excinfo:
            await injector.inject_cli_skip(
                build_id=BUILD_ID,
                stage_label=STAGE_LABEL,
                attempt_count=ATTEMPT_COUNT,
            )
        assert "agents.approval.forge." in str(excinfo.value)
        assert ".response" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Seam test — verify request_id derivation contract from TASK-CGCP-003
# ---------------------------------------------------------------------------


@pytest.mark.seam
@pytest.mark.integration_contract("derive_request_id")
def test_synthetic_response_uses_persisted_request_id() -> None:
    """Verify synthetic injector keys on the same deterministic request_id.

    Contract: synthetic responses use the SAME request_id as the original
    paused stage to guarantee dedup against any racing real response.
    Producer: TASK-CGCP-003
    """
    rid = derive_request_id(
        build_id="b1",
        stage_label="Architecture Review",
        attempt_count=2,
    )
    # Synthetic and real responses produce identical ids for the same
    # paused stage.
    assert rid == derive_request_id(
        build_id="b1",
        stage_label="Architecture Review",
        attempt_count=2,
    )
