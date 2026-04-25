"""Tests for ``forge.adapters.nats.pipeline_consumer``.

Each ``Test*`` class maps to one acceptance criterion of TASK-NFI-007 so the
mapping between criterion and verifier stays explicit. Production
collaborators (state machine entry, SQLite duplicate read, build-failed
publisher) are stubbed with ``unittest.mock.AsyncMock``; the only real
external library exercised here is ``nats-py``'s ``ConsumerConfig`` dataclass
(used for AC-001 shape verification).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy
from nats_core.envelope import EventType, MessageEnvelope
from nats_core.events import BuildFailedPayload, BuildQueuedPayload

from forge.adapters.nats.pipeline_consumer import (
    ACK_WAIT_SECONDS,
    BUILD_QUEUE_SUBJECT,
    DURABLE_NAME,
    REASON_MALFORMED_PAYLOAD,
    REASON_ORIGINATOR_NOT_RECOGNISED,
    REASON_PATH_OUTSIDE_ALLOWLIST,
    STREAM_NAME,
    PipelineConsumerDeps,
    build_consumer_config,
    handle_message,
)
from forge.config.models import (
    FilesystemPermissions,
    ForgeConfig,
    PermissionsConfig,
    PipelineConfig,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def allowlist_root(tmp_path: Path) -> Path:
    """A real, resolved directory used as the only allowlist entry."""

    root = tmp_path / "repos"
    root.mkdir()
    return root.resolve()


@pytest.fixture
def forge_config(allowlist_root: Path) -> ForgeConfig:
    """``ForgeConfig`` with the default approved-originators list and a
    single allowlisted directory rooted in ``tmp_path``."""

    return ForgeConfig(
        pipeline=PipelineConfig(),  # default approved_originators
        permissions=PermissionsConfig(
            filesystem=FilesystemPermissions(allowlist=[allowlist_root]),
        ),
    )


@pytest.fixture
def deps_factory(forge_config: ForgeConfig):
    """Build a :class:`PipelineConsumerDeps` whose collaborators are mocks.

    Returns a factory so individual tests can override the duplicate-check
    return value or capture dispatch arguments.
    """

    def _make(
        *,
        is_duplicate_terminal: bool = False,
    ) -> tuple[PipelineConsumerDeps, dict[str, AsyncMock]]:
        is_dup = AsyncMock(return_value=is_duplicate_terminal)
        dispatch = AsyncMock()
        publish_failed = AsyncMock()
        deps = PipelineConsumerDeps(
            forge_config=forge_config,
            is_duplicate_terminal=is_dup,
            dispatch_build=dispatch,
            publish_build_failed=publish_failed,
        )
        return deps, {
            "is_duplicate_terminal": is_dup,
            "dispatch_build": dispatch,
            "publish_build_failed": publish_failed,
        }

    return _make


def _envelope_bytes(payload: dict[str, Any]) -> bytes:
    """Wrap ``payload`` in a valid ``MessageEnvelope`` and serialise to JSON
    bytes ready for ``msg.data``."""

    envelope = MessageEnvelope(
        message_id="msg-test-001",
        timestamp=datetime.now(timezone.utc),
        version="1.0",
        source_id="cli-wrapper",
        event_type=EventType.BUILD_QUEUED,
        project=None,
        correlation_id="corr-001",
        payload=payload,
    )
    return envelope.model_dump_json().encode("utf-8")


def _valid_payload_dict(yaml_path: Path) -> dict[str, Any]:
    """A minimum-viable :class:`BuildQueuedPayload` dict with a path that
    resolves inside the allowlist root."""

    return {
        "feature_id": "FEAT-A1B2",
        "repo": "appmilla/example",
        "branch": "main",
        "feature_yaml_path": str(yaml_path),
        "max_turns": 5,
        "sdk_timeout_seconds": 1800,
        "wave_gating": True,
        "config_overrides": None,
        "triggered_by": "cli",
        "originating_adapter": "cli-wrapper",
        "originating_user": "rich",
        "correlation_id": "corr-001",
        "parent_request_id": None,
        "retry_count": 0,
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }


def _make_msg(data: bytes) -> AsyncMock:
    """Mock :class:`nats.aio.msg.Msg` exposing the ``.data`` byte buffer
    and an awaitable ``.ack()``."""

    msg = AsyncMock()
    msg.data = data
    msg.ack = AsyncMock()
    return msg


# ---------------------------------------------------------------------------
# AC-001: pull consumer config matches API-nats-pipeline-events.md §2.2
# ---------------------------------------------------------------------------


class TestConsumerConfig:
    """AC-001: consumer config matches the API contract verbatim."""

    def test_returns_consumer_config_instance(self) -> None:
        cfg = build_consumer_config()
        assert isinstance(cfg, ConsumerConfig)

    def test_durable_name_matches_contract(self) -> None:
        assert build_consumer_config().durable_name == "forge-consumer"
        assert DURABLE_NAME == "forge-consumer"

    def test_max_ack_pending_is_one(self) -> None:
        # ADR-ARCH-014 — sequential builds enforced at the transport.
        assert build_consumer_config().max_ack_pending == 1

    def test_ack_wait_is_one_hour(self) -> None:
        assert ACK_WAIT_SECONDS == 3600.0
        assert build_consumer_config().ack_wait == 3600.0

    def test_deliver_policy_is_all(self) -> None:
        assert build_consumer_config().deliver_policy is DeliverPolicy.ALL

    def test_ack_policy_is_explicit(self) -> None:
        assert build_consumer_config().ack_policy is AckPolicy.EXPLICIT

    def test_max_deliver_is_infinite(self) -> None:
        assert build_consumer_config().max_deliver == -1

    def test_filter_subject_matches_subscription_subject(self) -> None:
        assert build_consumer_config().filter_subject == BUILD_QUEUE_SUBJECT

    def test_subject_and_stream_constants(self) -> None:
        assert BUILD_QUEUE_SUBJECT == "pipeline.build-queued.>"
        assert STREAM_NAME == "PIPELINE"


# ---------------------------------------------------------------------------
# AC-002 + AC-009: valid payload dispatched with ack deferred until terminal
# ---------------------------------------------------------------------------


class TestValidPayloadDispatch:
    """AC-002: valid payload reaches state machine with ``ack_callback``.

    AC-009: non-terminal transitions do NOT ack. The callback is the
    state machine's only path to ``msg.ack()``.
    """

    @pytest.mark.asyncio
    async def test_valid_payload_invokes_dispatch_build(
        self, deps_factory, allowlist_root: Path
    ) -> None:
        yaml_path = allowlist_root / "feature.yaml"
        msg = _make_msg(_envelope_bytes(_valid_payload_dict(yaml_path)))
        deps, mocks = deps_factory()

        await handle_message(msg, deps)

        mocks["dispatch_build"].assert_awaited_once()
        sent_payload, ack_callback = mocks["dispatch_build"].await_args.args
        assert isinstance(sent_payload, BuildQueuedPayload)
        assert sent_payload.feature_id == "FEAT-A1B2"
        assert callable(ack_callback)

    @pytest.mark.asyncio
    async def test_ack_is_deferred_until_callback_invoked(
        self, deps_factory, allowlist_root: Path
    ) -> None:
        # AC-009: msg.ack() must NOT be called during handle_message itself
        # for a valid build — only when the state machine fires the callback.
        yaml_path = allowlist_root / "feature.yaml"
        msg = _make_msg(_envelope_bytes(_valid_payload_dict(yaml_path)))
        deps, mocks = deps_factory()

        await handle_message(msg, deps)

        msg.ack.assert_not_called()
        # Now simulate the state machine reaching a terminal state.
        _, ack_callback = mocks["dispatch_build"].await_args.args
        await ack_callback()
        msg.ack.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_failure_event_on_valid_payload(
        self, deps_factory, allowlist_root: Path
    ) -> None:
        yaml_path = allowlist_root / "feature.yaml"
        msg = _make_msg(_envelope_bytes(_valid_payload_dict(yaml_path)))
        deps, mocks = deps_factory()

        await handle_message(msg, deps)

        mocks["publish_build_failed"].assert_not_called()


# ---------------------------------------------------------------------------
# AC-008: ack is called exactly once
# ---------------------------------------------------------------------------


class TestAckCalledExactlyOnce:
    """AC-008: ack is called exactly once per message."""

    @pytest.mark.asyncio
    async def test_ack_callback_is_idempotent(
        self, deps_factory, allowlist_root: Path
    ) -> None:
        yaml_path = allowlist_root / "feature.yaml"
        msg = _make_msg(_envelope_bytes(_valid_payload_dict(yaml_path)))
        deps, mocks = deps_factory()

        await handle_message(msg, deps)
        _, ack_callback = mocks["dispatch_build"].await_args.args

        # Even if the state machine accidentally fires the callback twice,
        # the underlying msg.ack() must only run once.
        await ack_callback()
        await ack_callback()
        assert msg.ack.await_count == 1

    @pytest.mark.asyncio
    async def test_rejection_acks_once_no_dispatch(
        self, deps_factory, tmp_path: Path
    ) -> None:
        # A payload outside the allowlist should ack exactly once (here,
        # immediately) and never invoke the dispatcher.
        outside = tmp_path / "outside" / "feature.yaml"
        outside.parent.mkdir()
        msg = _make_msg(_envelope_bytes(_valid_payload_dict(outside)))
        deps, mocks = deps_factory()

        await handle_message(msg, deps)

        assert msg.ack.await_count == 1
        mocks["dispatch_build"].assert_not_called()


# ---------------------------------------------------------------------------
# AC-003: malformed payload → ack + build-failed; never reaches state machine
# ---------------------------------------------------------------------------


class TestMalformedPayload:
    """AC-003: malformed payload → ack + ``build-failed`` published."""

    @pytest.mark.asyncio
    async def test_invalid_envelope_json_acks_and_publishes_failure(
        self, deps_factory
    ) -> None:
        msg = _make_msg(b"this is not even close to valid json {{{")
        deps, mocks = deps_factory()

        await handle_message(msg, deps)

        msg.ack.assert_awaited_once()
        mocks["publish_build_failed"].assert_awaited_once()
        sent, _feature_id = mocks["publish_build_failed"].await_args.args
        assert isinstance(sent, BuildFailedPayload)
        assert sent.failure_reason == REASON_MALFORMED_PAYLOAD
        assert sent.recoverable is False
        mocks["dispatch_build"].assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_buildqueued_payload_acks_and_publishes_failure(
        self, deps_factory
    ) -> None:
        # Envelope is well-formed, but the inner payload is missing required
        # fields. We expect a malformed-payload rejection, not a crash.
        broken_payload = {"feature_id": "FEAT-OOPS"}  # missing everything else
        msg = _make_msg(_envelope_bytes(broken_payload))
        deps, mocks = deps_factory()

        await handle_message(msg, deps)

        msg.ack.assert_awaited_once()
        mocks["publish_build_failed"].assert_awaited_once()
        sent, feature_id_arg = mocks["publish_build_failed"].await_args.args
        assert sent.failure_reason == REASON_MALFORMED_PAYLOAD
        assert feature_id_arg == "FEAT-OOPS"
        mocks["dispatch_build"].assert_not_called()

    @pytest.mark.asyncio
    async def test_garbage_bytes_does_not_invoke_dispatcher(
        self, deps_factory
    ) -> None:
        msg = _make_msg(b"\x00\x01\x02not-utf8")
        deps, mocks = deps_factory()

        await handle_message(msg, deps)

        mocks["dispatch_build"].assert_not_called()


# ---------------------------------------------------------------------------
# AC-004 + AC-010: path outside allowlist → ack + build-failed; ``..`` rejected
# ---------------------------------------------------------------------------


class TestPathAllowlist:
    """AC-004: path outside allowlist → ack + ``build-failed``.

    AC-010: ``Path.resolve() + is_relative_to`` rejects ``..`` traversal.
    """

    @pytest.mark.asyncio
    async def test_path_outside_allowlist_is_rejected(
        self, deps_factory, tmp_path: Path
    ) -> None:
        outside = tmp_path / "elsewhere" / "feature.yaml"
        outside.parent.mkdir()
        msg = _make_msg(_envelope_bytes(_valid_payload_dict(outside)))
        deps, mocks = deps_factory()

        await handle_message(msg, deps)

        msg.ack.assert_awaited_once()
        mocks["publish_build_failed"].assert_awaited_once()
        sent, _feature_id = mocks["publish_build_failed"].await_args.args
        assert sent.failure_reason == REASON_PATH_OUTSIDE_ALLOWLIST
        mocks["dispatch_build"].assert_not_called()

    @pytest.mark.asyncio
    async def test_dotdot_traversal_escape_is_rejected(
        self, deps_factory, allowlist_root: Path, tmp_path: Path
    ) -> None:
        # Construct a path that *literally* sits inside the allowlist root
        # but uses ``..`` to escape — Path.resolve() must collapse the
        # traversal so is_relative_to returns False.
        traversal = (
            allowlist_root
            / ".."
            / ".."
            / tmp_path.name  # back into tmp_path itself, outside the root
            / "outside"
            / "feature.yaml"
        )
        msg = _make_msg(_envelope_bytes(_valid_payload_dict(traversal)))
        deps, mocks = deps_factory()

        await handle_message(msg, deps)

        msg.ack.assert_awaited_once()
        mocks["publish_build_failed"].assert_awaited_once()
        sent, _feature_id = mocks["publish_build_failed"].await_args.args
        assert sent.failure_reason == REASON_PATH_OUTSIDE_ALLOWLIST
        mocks["dispatch_build"].assert_not_called()

    @pytest.mark.asyncio
    async def test_path_inside_allowlist_via_dotdot_is_accepted(
        self, deps_factory, allowlist_root: Path
    ) -> None:
        # Lexical ``..`` that *resolves back into* the allowlist root must
        # be accepted — only escapes are rejected.
        nested = allowlist_root / "subdir" / ".." / "feature.yaml"
        msg = _make_msg(_envelope_bytes(_valid_payload_dict(nested)))
        deps, mocks = deps_factory()

        await handle_message(msg, deps)

        mocks["dispatch_build"].assert_awaited_once()
        mocks["publish_build_failed"].assert_not_called()


# ---------------------------------------------------------------------------
# AC-005: unrecognised originating_adapter → ack + build-failed
# ---------------------------------------------------------------------------


class TestOriginatorAllowlist:
    """AC-005: ``originating_adapter`` not in approved list → rejected."""

    @pytest.mark.asyncio
    async def test_none_originator_is_rejected(
        self, deps_factory, allowlist_root: Path
    ) -> None:
        yaml_path = allowlist_root / "feature.yaml"
        payload = _valid_payload_dict(yaml_path)
        # Bypass the Pydantic Literal so the consumer is the layer that
        # rejects it — emulates a producer publishing without populating
        # the field.
        envelope = MessageEnvelope(
            message_id="m1",
            timestamp=datetime.now(timezone.utc),
            version="1.0",
            source_id="cli-wrapper",
            event_type=EventType.BUILD_QUEUED,
            payload={**payload, "originating_adapter": None},
        )
        msg = _make_msg(envelope.model_dump_json().encode("utf-8"))
        deps, mocks = deps_factory()

        await handle_message(msg, deps)

        msg.ack.assert_awaited_once()
        mocks["publish_build_failed"].assert_awaited_once()
        sent, _feature_id = mocks["publish_build_failed"].await_args.args
        assert sent.failure_reason == REASON_ORIGINATOR_NOT_RECOGNISED
        mocks["dispatch_build"].assert_not_called()

    @pytest.mark.asyncio
    async def test_unapproved_originator_is_rejected(
        self,
        forge_config: ForgeConfig,
        allowlist_root: Path,
    ) -> None:
        # Tighten the approved list so ``cli-wrapper`` becomes invalid
        # without having to monkey-patch the Pydantic Literal.
        narrow_config = ForgeConfig(
            pipeline=PipelineConfig(approved_originators=["terminal"]),
            permissions=forge_config.permissions,
        )
        is_dup = AsyncMock(return_value=False)
        dispatch = AsyncMock()
        publish_failed = AsyncMock()
        deps = PipelineConsumerDeps(
            forge_config=narrow_config,
            is_duplicate_terminal=is_dup,
            dispatch_build=dispatch,
            publish_build_failed=publish_failed,
        )

        yaml_path = allowlist_root / "feature.yaml"
        msg = _make_msg(_envelope_bytes(_valid_payload_dict(yaml_path)))
        await handle_message(msg, deps)

        msg.ack.assert_awaited_once()
        publish_failed.assert_awaited_once()
        sent, _feature_id = publish_failed.await_args.args
        assert sent.failure_reason == REASON_ORIGINATOR_NOT_RECOGNISED
        dispatch.assert_not_called()


# ---------------------------------------------------------------------------
# AC-006 + AC-007: duplicate already-terminal build → ack + skip
# ---------------------------------------------------------------------------


class TestDuplicateDetection:
    """AC-006/AC-007: duplicates are acked and skipped without restart."""

    @pytest.mark.asyncio
    async def test_already_complete_build_is_acked_and_skipped(
        self, deps_factory, allowlist_root: Path
    ) -> None:
        yaml_path = allowlist_root / "feature.yaml"
        msg = _make_msg(_envelope_bytes(_valid_payload_dict(yaml_path)))
        deps, mocks = deps_factory(is_duplicate_terminal=True)

        await handle_message(msg, deps)

        msg.ack.assert_awaited_once()
        mocks["dispatch_build"].assert_not_called()
        mocks["publish_build_failed"].assert_not_called()

    @pytest.mark.asyncio
    async def test_already_failed_build_is_also_acked_and_skipped(
        self, deps_factory, allowlist_root: Path
    ) -> None:
        # The duplicate-check helper returns True for ANY terminal status —
        # COMPLETE, FAILED, CANCELLED, SKIPPED. We exercise the same code
        # path for FAILED to satisfy AC-007 explicitly.
        yaml_path = allowlist_root / "feature.yaml"
        msg = _make_msg(_envelope_bytes(_valid_payload_dict(yaml_path)))
        deps, mocks = deps_factory(is_duplicate_terminal=True)

        await handle_message(msg, deps)

        msg.ack.assert_awaited_once()
        mocks["dispatch_build"].assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicate_check_called_with_feature_and_correlation(
        self, deps_factory, allowlist_root: Path
    ) -> None:
        yaml_path = allowlist_root / "feature.yaml"
        msg = _make_msg(_envelope_bytes(_valid_payload_dict(yaml_path)))
        deps, mocks = deps_factory(is_duplicate_terminal=False)

        await handle_message(msg, deps)

        mocks["is_duplicate_terminal"].assert_awaited_once_with(
            "FEAT-A1B2", "corr-001"
        )


# ---------------------------------------------------------------------------
# AC-011 sanity: handle_message never raises on adversarial input
# ---------------------------------------------------------------------------


class TestRobustness:
    """The consumer is the I/O boundary — it must absorb bad input rather
    than blowing up the fetch loop. This guards the lint/format-zero-errors
    spirit of AC-011 by making sure stylistic edits never weaken the
    error-handling envelope.
    """

    @pytest.mark.asyncio
    async def test_empty_data_is_treated_as_malformed(self, deps_factory) -> None:
        msg = _make_msg(b"")
        deps, mocks = deps_factory()

        await handle_message(msg, deps)

        msg.ack.assert_awaited_once()
        mocks["publish_build_failed"].assert_awaited_once()
        sent, _feature_id = mocks["publish_build_failed"].await_args.args
        assert sent.failure_reason == REASON_MALFORMED_PAYLOAD

    @pytest.mark.asyncio
    async def test_envelope_with_non_dict_payload_is_treated_as_malformed(
        self, deps_factory
    ) -> None:
        # We can't construct this through MessageEnvelope (Pydantic enforces
        # dict[str, Any]) — but on the wire a producer might publish a
        # string payload. Hand-craft the JSON so the inner validation fails.
        wire = json.dumps(
            {
                "message_id": "m1",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "1.0",
                "source_id": "cli-wrapper",
                "event_type": "build_queued",
                "project": None,
                "correlation_id": "corr-001",
                "payload": "not-a-dict",
            }
        ).encode("utf-8")
        msg = _make_msg(wire)
        deps, mocks = deps_factory()

        await handle_message(msg, deps)

        msg.ack.assert_awaited_once()
        # Either the envelope itself rejects the non-dict payload, or the
        # inner validation does — both flow into "malformed". We just need
        # to confirm we never dispatched.
        mocks["dispatch_build"].assert_not_called()
