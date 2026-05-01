"""``forge serve`` daemon body — JetStream durable consumer (TASK-F009-003).

This module owns the long-running side of ``forge serve``. It connects to
NATS, attaches to the **shared** JetStream durable consumer named
:data:`forge.cli._serve_config.DEFAULT_DURABLE_NAME` ("forge-serve") on
subject ``pipeline.build-queued.*``, pulls payloads, and hands them to
the orchestrator. The receipt path (subscribe + ack) is the contract this
task delivers — the actual build dispatch is owned downstream.

Behaviour summary (see TASK-F009-003 acceptance criteria):

* ``run_daemon`` returns only on cancellation / signal — otherwise loops
  forever (AC: starts and stays running until SIGTERM).
* The pull subscription uses ``durable=DEFAULT_DURABLE_NAME`` exactly,
  on the shared :data:`PIPELINE_STREAM_NAME` stream, with explicit ack
  policy. Two replicas binding the same durable get JetStream's
  work-queue semantics (each message is delivered to one replica) —
  the heart of the D2 multi-replica AC and ASSUM-006.
* :class:`SubscriptionState.live` flips to ``True`` only after the
  pull subscription is bound; it flips to ``False`` on broker loss
  and again at clean shutdown.
* Broker-outage recovery is JetStream-defaults only (ASSUM-007): we
  reconnect with bounded backoff and re-attach the same durable. We do
  not implement a forge-side replay window.
* SIGTERM / SIGINT are wired via :func:`asyncio.AbstractEventLoop.add_signal_handler`
  when available; the daemon also exits cleanly on
  :class:`asyncio.CancelledError`. The teardown ``client.close()`` is
  bounded by :data:`SHUTDOWN_TIMEOUT_SECONDS` so a hung broker cannot
  delay exit past the 10 s AC.
* Unacked messages stay pending on the consumer for redelivery (E2.1):
  the daemon only acks **after** the dispatch coroutine returns, and
  it stops fetching new messages as soon as the stop event fires.
* A failed dispatch acks the message (releases the queue slot) and the
  daemon continues with the next payload — only the failed build is
  lost, the daemon stays available (E3.1).

Module-level seams (rebindable by tests):

- :data:`nats_connect` — ``async (servers: str) -> client``.
- :data:`dispatch_payload` — ``async (body: bytes) -> None``.

Tests monkey-patch these to drive the daemon without a real broker.
Production keeps the defaults wired to ``nats-py`` and a structured
logger that other agents can subscribe to via the existing
``forge.adapters.nats.pipeline_consumer`` machinery.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any, Awaitable, Callable, Protocol, runtime_checkable

from forge.cli._serve_config import ServeConfig
from forge.cli._serve_state import SubscriptionState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants pinned to the integration contract
# ---------------------------------------------------------------------------

#: Subject filter for the durable consumer. The trailing ``*`` matches a
#: single ``feature_id`` token — same shape as the producer-side queue
#: subject in :mod:`forge.cli.queue`.
BUILD_QUEUED_SUBJECT_FILTER: str = "pipeline.build-queued.*"

#: Stream name shared with the existing pipeline consumer. Configured
#: by ``nats-infrastructure``; carries both the inbound build queue and
#: the outbound lifecycle events.
PIPELINE_STREAM_NAME: str = "PIPELINE"

#: How many messages to fetch per pull. Kept at 1 to mirror the
#: sequential-build constraint (ADR-ARCH-014) — a fanned-out batch would
#: defeat the work-queue semantics that make D2 safe.
PULL_BATCH_SIZE: int = 1

#: Timeout (seconds) for one ``fetch`` call. Short so the loop returns
#: control to the stop-event check between message arrivals.
PULL_TIMEOUT_SECONDS: float = 1.0

#: Initial reconnect backoff after a broker error.
RECONNECT_INITIAL_BACKOFF: float = 1.0

#: Cap on the exponential reconnect backoff.
RECONNECT_MAX_BACKOFF: float = 30.0

#: Hard ceiling on the final ``client.close()`` await. Keeps the SIGTERM
#: budget under the documented 10 s AC even if the broker is hung.
SHUTDOWN_TIMEOUT_SECONDS: float = 5.0


# ---------------------------------------------------------------------------
# Type surface
# ---------------------------------------------------------------------------


@runtime_checkable
class _MsgLike(Protocol):
    """Minimal slice of :class:`nats.aio.msg.Msg` used by the loop."""

    data: bytes

    async def ack(self) -> None:  # pragma: no cover - protocol stub
        ...


NatsConnectFn = Callable[[str], Awaitable[Any]]
"""``async (servers: str) -> client`` — lazy NATS connect seam."""

DispatchFn = Callable[[bytes], Awaitable[None]]
"""``async (body: bytes) -> None`` — orchestrator dispatch seam."""


# ---------------------------------------------------------------------------
# Default seam implementations (production)
# ---------------------------------------------------------------------------


async def _default_nats_connect(servers: str) -> Any:
    """Production NATS connect — opens a fresh client.

    The ``nats`` import is lazy so importing this module does not pull
    the network stack into ``forge --help``.

    Args:
        servers: NATS URL (defaults to ``nats://127.0.0.1:4222``).

    Returns:
        A connected ``nats.NATS`` client.

    Raises:
        RuntimeError: When ``nats-py`` is not installed.
    """
    try:
        import nats  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - covered via the seam
        raise RuntimeError(
            "nats client not installed — `pip install nats-py`"
        ) from exc
    return await nats.connect(servers=servers)


async def _default_dispatch(body: bytes) -> None:
    """Receipt-side dispatch — log the envelope and return.

    The actual orchestrator wiring is owned by the existing
    :mod:`forge.adapters.nats.pipeline_consumer` machinery; ``forge serve``
    is the new daemon process that hosts that machinery. For the receipt
    AC we only need to prove the message was pulled and acked.

    The function MUST NOT raise — a failure here would propagate into
    the consume loop and ``handle_message``'s outer ``except`` would
    treat the build as failed (E3.1 isolation). Logging at WARNING for
    malformed input keeps observability without breaking that property.
    """
    try:
        from nats_core.envelope import MessageEnvelope

        envelope = MessageEnvelope.model_validate_json(body)
    except Exception as exc:  # noqa: BLE001 — log + drop, never raise
        logger.warning(
            "forge-serve: dropping unparseable envelope (%s)", exc
        )
        return

    feature_id: str | None = None
    raw_payload = envelope.payload if isinstance(envelope.payload, dict) else {}
    candidate = raw_payload.get("feature_id")
    if isinstance(candidate, str) and candidate:
        feature_id = candidate

    logger.info(
        "forge-serve: received build-queued envelope feature_id=%s "
        "correlation_id=%s",
        feature_id,
        envelope.correlation_id,
    )


# Module-level rebindable seams. Tests substitute these with AsyncMock
# fakes; production keeps the defaults.
nats_connect: NatsConnectFn = _default_nats_connect
dispatch_payload: DispatchFn = _default_dispatch


# ---------------------------------------------------------------------------
# Subscription wiring
# ---------------------------------------------------------------------------


async def _attach_consumer(client: Any, durable_name: str) -> Any:
    """Bind the shared durable pull subscription on ``client``.

    Imports :mod:`nats.js.api` lazily so this module's import surface
    stays small. The :class:`~nats.js.api.ConsumerConfig` mirrors the
    one used by :mod:`forge.adapters.nats.pipeline_consumer` for explicit
    ack semantics; the differences are scoped to durable name and the
    subject filter (``forge serve`` does not gate on
    ``max_ack_pending=1`` because the new daemon supports multi-replica
    work-queue distribution by design).
    """
    from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy

    js = client.jetstream()
    config = ConsumerConfig(
        durable_name=durable_name,
        deliver_policy=DeliverPolicy.ALL,
        ack_policy=AckPolicy.EXPLICIT,
        filter_subject=BUILD_QUEUED_SUBJECT_FILTER,
    )
    return await js.pull_subscribe(
        subject=BUILD_QUEUED_SUBJECT_FILTER,
        durable=durable_name,
        stream=PIPELINE_STREAM_NAME,
        config=config,
    )


# ---------------------------------------------------------------------------
# Inner loops
# ---------------------------------------------------------------------------


async def _process_message(msg: _MsgLike) -> None:
    """Dispatch then ack — see :func:`run_daemon` for AC mapping.

    Failures inside :data:`dispatch_payload` are caught and logged so
    one bad build cannot take the daemon down (AC E3.1). The ack still
    runs after a failed dispatch — leaving the message un-acked would
    block the durable's queue slot until ``ack_wait`` expires, which
    contradicts the "daemon remains available" property.

    Cancellation propagates without acking (E2.1: a crash mid-build
    leaves the message pending for redelivery).
    """
    try:
        await dispatch_payload(msg.data)
    except asyncio.CancelledError:
        # Crash-safety: do NOT ack. JetStream redelivers after ack_wait.
        raise
    except Exception as exc:  # noqa: BLE001 — E3.1 isolation
        logger.warning(
            "forge-serve: dispatch failed (%s); acking to release queue slot",
            exc,
        )
    await msg.ack()


async def _consume_forever(
    sub: Any,
    state: SubscriptionState,
    stop_event: asyncio.Event,
) -> None:
    """Pull loop — fetches one message at a time until ``stop_event``.

    A bare ``asyncio.TimeoutError`` from ``fetch`` is the no-message
    signal and is silently absorbed. Any other exception (broker loss,
    network blip) propagates to the caller, which marks the state
    not-live and triggers reconnect.
    """
    while not stop_event.is_set():
        try:
            msgs = await sub.fetch(
                PULL_BATCH_SIZE, timeout=PULL_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            # No messages this tick — yield to let stop_event flip.
            await asyncio.sleep(0)
            continue
        for msg in msgs:
            if stop_event.is_set():
                # Leave un-acked messages for redelivery (E2.1).
                return
            await _process_message(msg)


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    """Wire SIGTERM / SIGINT to flip ``stop_event``.

    Falls back silently when the running loop does not support
    ``add_signal_handler`` (Windows ProactorEventLoop, non-main-thread
    test runners). On those platforms we still react to
    :class:`asyncio.CancelledError` — :func:`run_daemon` treats both
    cancellation paths as "stop now".
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop yet — caller will register handlers later.
        return

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except (NotImplementedError, RuntimeError, ValueError):
            logger.debug(
                "forge-serve: cannot install handler for %s "
                "(not in main thread or unsupported loop)",
                sig.name,
            )


# ---------------------------------------------------------------------------
# Top-level daemon coroutine
# ---------------------------------------------------------------------------


async def run_daemon(config: ServeConfig, state: SubscriptionState) -> None:
    """Run the JetStream durable consumer until SIGTERM / cancellation.

    The control flow:

    1. Install signal handlers (best-effort — see
       :func:`_install_signal_handlers`).
    2. Outer loop: connect, attach consumer, run the inner pull loop
       until either the stop event fires or a broker error escapes.
    3. On broker error: mark state not-live, sleep with bounded backoff,
       retry. Repeats until ``stop_event`` is set.
    4. On clean exit: mark state not-live, unsubscribe, close client.

    Args:
        config: Daemon configuration (NATS URL, durable name, …).
        state: Shared readiness flag — flipped True once the durable
            is bound and False on broker loss / shutdown.
    """
    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)

    backoff = RECONNECT_INITIAL_BACKOFF
    try:
        while not stop_event.is_set():
            client: Any = None
            sub: Any = None
            try:
                client = await nats_connect(config.nats_url)
                sub = await _attach_consumer(client, config.durable_name)
                await state.set_live(True)
                # Successful attach resets the backoff so the next outage
                # starts from RECONNECT_INITIAL_BACKOFF rather than the
                # capped ceiling.
                backoff = RECONNECT_INITIAL_BACKOFF
                try:
                    await _consume_forever(sub, state, stop_event)
                finally:
                    await state.set_live(False)
            except asyncio.CancelledError:
                stop_event.set()
                await state.set_live(False)
                raise
            except Exception as exc:  # noqa: BLE001 — D3 reconnect path
                logger.warning(
                    "forge-serve: broker error (%s); reconnecting in %.1fs",
                    exc,
                    backoff,
                )
                await state.set_live(False)
                # Wake early if a SIGTERM arrives during the backoff sleep.
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=backoff)
                except asyncio.TimeoutError:
                    pass
                backoff = min(backoff * 2, RECONNECT_MAX_BACKOFF)
            finally:
                # Best-effort tear-down — broker may already be gone.
                if sub is not None:
                    try:
                        await sub.unsubscribe()
                    except Exception as exc:  # noqa: BLE001
                        logger.debug(
                            "forge-serve: unsubscribe error (%s)", exc
                        )
                if client is not None:
                    try:
                        await asyncio.wait_for(
                            client.close(),
                            timeout=SHUTDOWN_TIMEOUT_SECONDS,
                        )
                    except (asyncio.TimeoutError, Exception) as exc:  # noqa: BLE001
                        logger.debug(
                            "forge-serve: client.close error (%s)", exc
                        )
    finally:
        await state.set_live(False)


__all__ = [
    "BUILD_QUEUED_SUBJECT_FILTER",
    "PIPELINE_STREAM_NAME",
    "PULL_BATCH_SIZE",
    "PULL_TIMEOUT_SECONDS",
    "RECONNECT_INITIAL_BACKOFF",
    "RECONNECT_MAX_BACKOFF",
    "SHUTDOWN_TIMEOUT_SECONDS",
    "dispatch_payload",
    "nats_connect",
    "run_daemon",
]
