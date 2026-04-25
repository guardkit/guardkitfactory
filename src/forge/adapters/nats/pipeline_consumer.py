"""Inbound build-queue subscription for the Forge pipeline.

This module owns Forge's JetStream pull consumer for ``pipeline.build-queued.>``
described in ``docs/design/contracts/API-nats-pipeline-events.md §2``.

Responsibilities (per TASK-NFI-007):

- Build the durable pull-consumer :class:`~nats.js.api.ConsumerConfig` exactly as
  specified in API contract §2.2 (``durable="forge-consumer"``,
  ``max_ack_pending=1``, ``ack_wait=1h``, ``deliver_policy=ALL``,
  ``ack_policy=EXPLICIT``, ``max_deliver=-1``).
- Validate every incoming :class:`~nats_core.events.BuildQueuedPayload` and
  reject malformed payloads, unrecognised originators, and ``feature_yaml_path``
  values outside the configured filesystem allowlist by acking the JetStream
  message and publishing ``pipeline.build-failed.{feature_id}``.
- Detect already-terminal duplicates against an injected SQLite read helper and
  skip them idempotently (ack + no new build).
- For accepted builds, hand control to the state machine entrypoint together
  with an ``ack_callback`` closure bound to the JetStream ``Msg.ack`` method —
  the callback is invoked **only on terminal transitions**, leaving the
  message unacked across non-terminal states (PAUSED, RUNNING, etc.) so the
  position in the queue is preserved across restarts (ADR-SP-013).

The module is intentionally I/O-thin: real dependencies (state-machine entry
point, SQLite duplicate read, build-failed publisher) are injected through
:class:`PipelineConsumerDeps`. Tests substitute simple async callables; the
production wiring binds them to the concrete adapters in
``forge.adapters.nats`` / ``forge.adapters.sqlite`` / ``forge.pipeline``.

ADR / contract anchors:

- API contract: ``docs/design/contracts/API-nats-pipeline-events.md``
- Sequential-build constraint: ADR-ARCH-014 (``max_ack_pending=1``)
- Terminal-only ack semantics: ADR-SP-013
- Crash recovery (out of scope here, owned by TASK-NFI-009)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol, runtime_checkable

from nats.aio.msg import Msg
from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy
from nats.js.client import JetStreamContext
from nats_core.envelope import MessageEnvelope
from nats_core.events import BuildFailedPayload, BuildQueuedPayload
from pydantic import ValidationError

from forge.config.models import ForgeConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants pinned to the API contract (API-nats-pipeline-events.md §2)
# ---------------------------------------------------------------------------

#: NATS JetStream stream name carrying both the inbound build queue and the
#: outbound lifecycle events (configured by ``nats-infrastructure``).
STREAM_NAME: str = "PIPELINE"

#: Durable consumer name. Survives Forge restart so unacked messages are
#: redelivered after a crash.
DURABLE_NAME: str = "forge-consumer"

#: Subject pattern subscribed to by the pull consumer. The trailing ``>`` is
#: a NATS wildcard matching every ``feature_id``.
BUILD_QUEUE_SUBJECT: str = "pipeline.build-queued.>"

#: ``ack_wait`` as a float number of seconds. The contract phrases it as
#: ``timedelta(hours=1)``; nats-py's :class:`ConsumerConfig` takes seconds.
ACK_WAIT_SECONDS: float = float(60 * 60)

#: Subject prefix for the build-failed publish. The full subject is
#: ``pipeline.build-failed.{feature_id}`` per API contract §3.1.
BUILD_FAILED_SUBJECT_PREFIX: str = "pipeline.build-failed"

#: ``source_id`` used on every envelope Forge publishes.
FORGE_SOURCE_ID: str = "forge"

#: Sentinel used in build-failed payloads when we never got far enough to
#: parse a real ``feature_id`` (e.g. malformed payload).
UNKNOWN_FEATURE_ID: str = "unknown"


# ---------------------------------------------------------------------------
# Failure reasons — these strings are part of the contract surface and are
# asserted verbatim by tests.
# ---------------------------------------------------------------------------

REASON_MALFORMED_PAYLOAD: str = "malformed BuildQueuedPayload"
REASON_PATH_OUTSIDE_ALLOWLIST: str = "path outside allowlist"
REASON_ORIGINATOR_NOT_RECOGNISED: str = "originator not recognised"


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

AckCallback = Callable[[], Awaitable[None]]
"""Closure handed to the state machine. Calling it acks the JetStream message."""

IsDuplicateTerminal = Callable[[str, str], Awaitable[bool]]
"""``async (feature_id, correlation_id) -> bool`` — True if the build already
terminated (``COMPLETE | FAILED | CANCELLED | SKIPPED``) and the consumer
should ack-and-skip."""

DispatchBuild = Callable[[BuildQueuedPayload, AckCallback], Awaitable[None]]
"""``async (payload, ack_callback) -> None`` — pipeline state-machine entry."""

PublishBuildFailed = Callable[[BuildFailedPayload, str], Awaitable[None]]
"""``async (failure_payload, feature_id) -> None`` — the wrapper publishes to
``pipeline.build-failed.{feature_id}``. Owns envelope construction."""


@runtime_checkable
class _MsgLike(Protocol):
    """Minimal slice of :class:`nats.aio.msg.Msg` we depend on.

    Declared so tests can use lightweight ``unittest.mock.AsyncMock`` doubles
    without having to monkey-patch the full nats-py msg class.
    """

    data: bytes

    async def ack(self) -> None:  # pragma: no cover - protocol stub
        ...


# ---------------------------------------------------------------------------
# Dependency container
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PipelineConsumerDeps:
    """Injected collaborators of the message-processing pipeline.

    Keeping these on a frozen dataclass means the consumer can be unit-tested
    with simple async callables and re-wired in production without touching
    the validation logic itself.
    """

    forge_config: ForgeConfig
    is_duplicate_terminal: IsDuplicateTerminal
    dispatch_build: DispatchBuild
    publish_build_failed: PublishBuildFailed


# ---------------------------------------------------------------------------
# Consumer config + subscription wiring
# ---------------------------------------------------------------------------


def build_consumer_config() -> ConsumerConfig:
    """Return the durable pull-consumer config exactly as pinned by §2.2.

    Notes:
        ``filter_subject`` is set to the same subject as ``pull_subscribe``'s
        ``subject`` argument. nats-py is happy with redundancy here and the
        contract spec lists it explicitly, so we mirror it.
    """

    return ConsumerConfig(
        durable_name=DURABLE_NAME,
        deliver_policy=DeliverPolicy.ALL,
        ack_policy=AckPolicy.EXPLICIT,
        ack_wait=ACK_WAIT_SECONDS,
        max_deliver=-1,
        max_ack_pending=1,
        filter_subject=BUILD_QUEUE_SUBJECT,
    )


async def start_pipeline_consumer(
    js: JetStreamContext,
) -> JetStreamContext.PullSubscription:
    """Bind the durable pull subscription on ``js`` and return it.

    The caller is expected to drive the subscription with ``fetch()`` in a
    long-running task and dispatch each message into :func:`handle_message`.
    Decoupling the bind from the dispatch loop keeps the function trivially
    testable and lets crash-recovery (TASK-NFI-009) reuse the same factory.
    """

    return await js.pull_subscribe(
        subject=BUILD_QUEUE_SUBJECT,
        durable=DURABLE_NAME,
        stream=STREAM_NAME,
        config=build_consumer_config(),
    )


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _path_inside_allowlist(candidate: str, allowlist: list[Path]) -> bool:
    """Return True iff ``candidate`` resolves inside one of ``allowlist``.

    Uses :meth:`pathlib.Path.resolve` to collapse ``..`` traversal **before**
    the :meth:`pathlib.Path.is_relative_to` check (AC-010). Each allowlisted
    path is also resolved so that a symlink in the allowlist root does not
    silently widen the authorised footprint at the cost of a divergence
    between the on-disk and resolved roots.

    ``candidate`` does not need to exist on disk — :meth:`Path.resolve` is
    purely lexical for paths that have not been ``mkdir``'d.
    """

    try:
        target = Path(candidate).resolve()
    except (OSError, ValueError):
        # OSError can come from Windows-style invalid paths on POSIX; both
        # are simply "not in the allowlist" from our POV.
        return False

    for allowed in allowlist:
        try:
            allowed_resolved = allowed.resolve()
        except (OSError, ValueError):
            continue
        if target.is_relative_to(allowed_resolved):
            return True
    return False


def _failure_payload(
    *,
    feature_id: str,
    build_id: str,
    reason: str,
) -> BuildFailedPayload:
    """Construct the :class:`BuildFailedPayload` for a rejection.

    Rejected-on-receive failures are not recoverable: the originating adapter
    must reissue the build with corrected inputs. We therefore set
    ``recoverable=False`` for every reason this module produces.
    """

    return BuildFailedPayload(
        feature_id=feature_id,
        build_id=build_id,
        failure_reason=reason,
        recoverable=False,
        failed_task_id=None,
    )


# ---------------------------------------------------------------------------
# Core message handler
# ---------------------------------------------------------------------------


async def handle_message(msg: _MsgLike, deps: PipelineConsumerDeps) -> None:
    """Validate one JetStream message and route it to the state machine.

    Outcomes (mutually exclusive — exactly one fires per call):

    1. *Malformed envelope or payload* → ``msg.ack()`` and publish
       ``build-failed`` with reason :data:`REASON_MALFORMED_PAYLOAD`.
       The state machine is **never** invoked.
    2. *Unrecognised ``originating_adapter``* → ack + ``build-failed`` with
       :data:`REASON_ORIGINATOR_NOT_RECOGNISED`.
    3. *``feature_yaml_path`` outside allowlist* → ack + ``build-failed``
       with :data:`REASON_PATH_OUTSIDE_ALLOWLIST`. ``..`` traversal is
       rejected because :func:`_path_inside_allowlist` calls
       :meth:`Path.resolve` before :meth:`Path.is_relative_to`.
    4. *Duplicate already-terminal build* → ack + idempotent skip. No build
       is started, no event is published.
    5. *Accepted build* → :meth:`PipelineConsumerDeps.dispatch_build` is
       awaited with an ``ack_callback`` bound to ``msg.ack``. The message
       remains unacked until the state machine invokes the callback at the
       terminal transition.

    The function never raises on bad input — every validation failure is
    captured and translated into outcome (1)–(3). It still propagates
    ``asyncio.CancelledError`` (the calling fetch loop owns shutdown
    semantics, per the task brief).
    """

    # --- 1. Parse envelope + payload -------------------------------------
    try:
        envelope = MessageEnvelope.model_validate_json(msg.data)
    except (ValidationError, ValueError) as exc:
        logger.warning(
            "pipeline_consumer: could not parse MessageEnvelope (%s); "
            "acking and publishing build-failed",
            exc,
        )
        await msg.ack()
        await deps.publish_build_failed(
            _failure_payload(
                feature_id=UNKNOWN_FEATURE_ID,
                build_id=UNKNOWN_FEATURE_ID,
                reason=REASON_MALFORMED_PAYLOAD,
            ),
            UNKNOWN_FEATURE_ID,
        )
        return

    try:
        payload = BuildQueuedPayload.model_validate(envelope.payload)
    except ValidationError as exc:
        # We have a parseable envelope, so use whatever identifying info it
        # carries. ``correlation_id`` is informational only — it does not
        # widen the failure surface.
        feature_id = _safe_envelope_feature(envelope) or UNKNOWN_FEATURE_ID
        logger.warning(
            "pipeline_consumer: BuildQueuedPayload validation failed for "
            "feature_id=%s (%s); acking and publishing build-failed",
            feature_id,
            exc,
        )
        await msg.ack()
        await deps.publish_build_failed(
            _failure_payload(
                feature_id=feature_id,
                build_id=feature_id,
                reason=REASON_MALFORMED_PAYLOAD,
            ),
            feature_id,
        )
        return

    # --- 2. Originator allowlist -----------------------------------------
    approved = deps.forge_config.pipeline.approved_originators
    originator = payload.originating_adapter
    if originator is None or originator not in approved:
        logger.warning(
            "pipeline_consumer: originating_adapter=%r not in approved list "
            "for feature_id=%s; rejecting",
            payload.originating_adapter,
            payload.feature_id,
        )
        await msg.ack()
        await deps.publish_build_failed(
            _failure_payload(
                feature_id=payload.feature_id,
                build_id=payload.feature_id,
                reason=REASON_ORIGINATOR_NOT_RECOGNISED,
            ),
            payload.feature_id,
        )
        return

    # --- 3. Path allowlist -----------------------------------------------
    allowlist = deps.forge_config.permissions.filesystem.allowlist
    if not _path_inside_allowlist(payload.feature_yaml_path, allowlist):
        logger.warning(
            "pipeline_consumer: feature_yaml_path=%r outside allowlist for "
            "feature_id=%s; rejecting",
            payload.feature_yaml_path,
            payload.feature_id,
        )
        await msg.ack()
        await deps.publish_build_failed(
            _failure_payload(
                feature_id=payload.feature_id,
                build_id=payload.feature_id,
                reason=REASON_PATH_OUTSIDE_ALLOWLIST,
            ),
            payload.feature_id,
        )
        return

    # --- 4. Duplicate detection (idempotent skip) ------------------------
    if await deps.is_duplicate_terminal(payload.feature_id, payload.correlation_id):
        logger.info(
            "pipeline_consumer: duplicate already-terminal build "
            "feature_id=%s correlation_id=%s; ack + skip",
            payload.feature_id,
            payload.correlation_id,
        )
        await msg.ack()
        return

    # --- 5. Accepted build — dispatch with deferred ack ------------------
    ack_callback = _build_ack_callback(msg)
    logger.info(
        "pipeline_consumer: dispatching build feature_id=%s correlation_id=%s "
        "originating_adapter=%s",
        payload.feature_id,
        payload.correlation_id,
        payload.originating_adapter,
    )
    await deps.dispatch_build(payload, ack_callback)


def _build_ack_callback(msg: _MsgLike) -> AckCallback:
    """Return an idempotent ack closure bound to ``msg.ack``.

    The state machine may invoke the callback more than once across a long
    build (e.g. once on terminal transition, again on retry-from-scratch
    crash recovery). JetStream tolerates double-ack but we prefer to log
    the second call as a warning and short-circuit, which makes the
    "ack called exactly once" acceptance criterion verifiable from tests.
    """

    state: dict[str, bool] = {"acked": False}

    async def _ack() -> None:
        if state["acked"]:
            logger.debug(
                "pipeline_consumer: ack_callback invoked twice; ignoring "
                "second call (idempotent)"
            )
            return
        state["acked"] = True
        await msg.ack()

    return _ack


def _safe_envelope_feature(envelope: MessageEnvelope) -> str | None:
    """Best-effort extraction of ``feature_id`` from an unvalidated envelope.

    The envelope ``payload`` is a free-form ``dict[str, Any]`` until we
    round-trip it through :class:`BuildQueuedPayload`. If validation failed
    we still want to publish a useful build-failed event keyed on whichever
    id the producer included; this helper returns it without raising.
    """

    raw: Any = envelope.payload
    if isinstance(raw, dict):
        candidate = raw.get("feature_id")
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


__all__ = [
    "ACK_WAIT_SECONDS",
    "BUILD_FAILED_SUBJECT_PREFIX",
    "BUILD_QUEUE_SUBJECT",
    "DURABLE_NAME",
    "FORGE_SOURCE_ID",
    "PipelineConsumerDeps",
    "REASON_MALFORMED_PAYLOAD",
    "REASON_ORIGINATOR_NOT_RECOGNISED",
    "REASON_PATH_OUTSIDE_ALLOWLIST",
    "STREAM_NAME",
    "UNKNOWN_FEATURE_ID",
    "build_consumer_config",
    "handle_message",
    "start_pipeline_consumer",
]
