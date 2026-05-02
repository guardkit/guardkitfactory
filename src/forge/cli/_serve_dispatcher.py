"""Composed dispatcher closure for the ``forge serve`` daemon (TASK-FW10-007).

This module is the seam between :mod:`forge.cli._serve_daemon`'s
``DispatchFn`` contract (``async (msg: _MsgLike) -> None``) and
:func:`forge.adapters.nats.pipeline_consumer.handle_message` — the
state machine that owns terminal-only ack and the malformed-payload
ack-and-publish flow.

The closure is intentionally **thin**: it forwards the JetStream
message together with the production
:class:`~forge.adapters.nats.pipeline_consumer.PipelineConsumerDeps`
container straight into ``handle_message``. The dispatcher itself
**never** calls ``msg.ack()``:

- on the **success** path the state machine acks via the
  ``ack_callback`` closure ``handle_message`` builds for accepted
  builds (terminal-only ack — ADR-SP-013);
- on the **rejection / malformed** path ``handle_message`` itself
  acks-and-publishes ``build-failed`` before returning;
- on the **duplicate-terminal** path ``handle_message`` acks-and-skips.

Keeping the dispatcher dumb means there is exactly one ack site in the
production code path: the state machine. Splitting the ack between two
modules is the classic source of double-ack / no-ack bugs that
TASK-FW10-001 AC-002 was carved out to prevent.

Why we import the module instead of the function
-------------------------------------------------

The seam test in TASK-FW10-007 (and the production E2E test in
TASK-FW10-011) monkey-patches ``handle_message`` on the
``forge.adapters.nats.pipeline_consumer`` module to drive the
dispatcher without a real consumer state machine::

    import forge.adapters.nats.pipeline_consumer as pc
    pc.handle_message = fake_handle

If this module did ``from ... import handle_message`` at import time,
the local binding would already point at the original function and the
monkey-patch would not take effect. We therefore hold a module-level
reference and call ``pipeline_consumer.handle_message(...)`` so the
attribute lookup happens at call time.
"""

from __future__ import annotations

import logging

from forge.adapters.nats import pipeline_consumer
from forge.adapters.nats.pipeline_consumer import PipelineConsumerDeps, _MsgLike
from forge.cli._serve_daemon import DispatchFn

logger = logging.getLogger(__name__)


__all__ = ["make_handle_message_dispatcher"]


def make_handle_message_dispatcher(deps: PipelineConsumerDeps) -> DispatchFn:
    """Return a :data:`DispatchFn` closure bound to ``deps``.

    The returned closure satisfies the
    :data:`forge.cli._serve_daemon.DispatchFn` type alias
    (``async (msg: _MsgLike) -> None``). It delegates straight into
    :func:`forge.adapters.nats.pipeline_consumer.handle_message`,
    which owns:

    * the ``BuildQueuedPayload`` validation flow (malformed → ack +
      publish ``build-failed``);
    * the originator and filesystem-allowlist checks (rejected →
      ack + publish ``build-failed``);
    * the duplicate-terminal idempotent skip (ack + no dispatch);
    * the accepted-build dispatch with a deferred ``ack_callback``
      bound to ``msg.ack`` (terminal-only ack — ADR-SP-013).

    The dispatcher itself does **not** call ``msg.ack()``. Doing so
    would either:

    1. ack twice on the rejection path (handle_message already acks),
       which JetStream tolerates but masks the contract bug; or
    2. ack on the success path before terminal completion, which
       defeats the "ack only on terminal state" property that lets
       the lifecycle pipeline survive a mid-build crash without
       losing the build.

    Args:
        deps: The composed
            :class:`~forge.adapters.nats.pipeline_consumer.PipelineConsumerDeps`
            for this daemon. Built by
            :func:`forge.cli._serve_deps.build_pipeline_consumer_deps`
            against the daemon's shared NATS client, ``ForgeConfig``,
            and SQLite pool.

    Returns:
        An ``async def dispatch(msg: _MsgLike) -> None`` closure that
        :mod:`forge.cli._serve_daemon` rebinds onto its
        :data:`~forge.cli._serve_daemon.dispatch_payload` seam, replacing
        the receipt-only ``_default_dispatch`` stub.

    Example:
        >>> deps = build_pipeline_consumer_deps(client, config, pool)
        >>> dispatcher = make_handle_message_dispatcher(deps)
        >>> # rebind onto the daemon's dispatch seam
        >>> _serve_daemon.dispatch_payload = dispatcher
    """

    async def dispatch(msg: _MsgLike) -> None:
        """Forward ``msg`` and the bound ``deps`` to ``handle_message``.

        The body is one line on purpose. Putting any logic here
        (logging, retry, ack-on-failure) duplicates behaviour that
        already lives in either ``handle_message`` (rejection /
        duplicate / dispatch flow) or ``_serve_daemon._process_message``
        (E3.1 isolation: ack-on-exception). Keeping this closure dumb
        makes the seam test in TASK-FW10-007 a one-shot assertion:
        "dispatcher delegated; dispatcher did not ack".
        """
        # ``pipeline_consumer.handle_message`` is intentionally looked up
        # via the module attribute rather than imported as a name so the
        # seam test in TASK-FW10-007 can monkey-patch the module's
        # ``handle_message`` and observe a single delegated call.
        await pipeline_consumer.handle_message(msg, deps)

    return dispatch
