"""Production constructors for ``PipelinePublisher`` + ``PipelineLifecycleEmitter``.

TASK-FW10-006 wave-2 module. The two collaborators are well unit-tested in
isolation but never instantiated in production until this module's
:func:`build_publisher_and_emitter` is wired into the deps factory
(TASK-FW10-007). The job here is intentionally small: bind both objects to
the **same** NATS client provided by ``forge.cli.serve._run_serve``
(ASSUM-011 — the daemon owns exactly one client and shares it with every
NATS-touching collaborator) and hand them back as a tuple.

Failure-mode contract (DDR-007 §Failure-mode contract, ADR-ARCH-008):

* The publisher logs transport-level failures at ``WARNING`` and raises
  :class:`forge.adapters.nats.PublishFailure` from
  :meth:`PipelinePublisher._publish_envelope`. The emitter's
  ``_safe_publish`` wrapper catches that exception and returns — so a
  publish failure on any ``emit_*`` method does **not** propagate to the
  state machine. The SQLite row that motivated the emission has already
  been written; the NATS stream is a derived projection, never the source
  of truth (LES1 parity rule).

Connection contract (ASSUM-011):

* This factory accepts a pre-opened ``NATSClient`` and **never** opens a
  new connection. Tests assert this by passing a sentinel object whose
  ``publish`` is a no-op and verifying that the publisher's ``_nc`` is
  the same object. There is no ``await nats.connect(...)`` reachable
  from this module.

Why ``config`` is optional:

* The strict signature in the task brief is
  ``build_publisher_and_emitter(client) -> tuple[...]``. The emitter,
  however, requires a :class:`PipelineConfig` to know its
  ``progress_interval_seconds``. We default to ``PipelineConfig()`` so the
  zero-arg call works as described, and accept an optional ``config``
  kwarg so the eventual wave-3 deps factory (TASK-FW10-007) can thread
  the orchestrator's loaded ``ForgeConfig.pipeline`` block through
  without monkey-patching the emitter post-construction.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from forge.adapters.nats import PipelinePublisher
from forge.config.models import PipelineConfig
from forge.pipeline import PipelineLifecycleEmitter

if TYPE_CHECKING:  # pragma: no cover - import-time only
    from nats.aio.client import Client as NATSClient

logger = logging.getLogger(__name__)

__all__ = ["build_publisher_and_emitter"]


def build_publisher_and_emitter(
    client: "NATSClient | Any",
    *,
    config: PipelineConfig | None = None,
) -> tuple[PipelinePublisher, PipelineLifecycleEmitter]:
    """Construct the publisher + emitter pair bound to ``client``.

    Both collaborators share the supplied NATS client (ASSUM-011). No
    second ``nats.connect`` call is reachable from this function — the
    only NATS-touching object created here is the publisher, whose
    constructor stores the client by reference and never re-dials.

    Args:
        client: Pre-opened async NATS client. Typically the value
            returned by ``await nats.connect(...)`` in
            :func:`forge.cli.serve._run_serve` and shared across the
            daemon, deps factory, dispatcher, publisher, and emitter.
        config: Optional :class:`PipelineConfig`. Defaults to
            :class:`PipelineConfig` (which carries
            ``progress_interval_seconds = 60`` per ASSUM-005). The
            wave-3 deps factory passes the orchestrator's loaded
            ``ForgeConfig.pipeline`` block here so the production
            emitter honours operator overrides.

    Returns:
        A ``(publisher, emitter)`` tuple. The publisher exposes the
        eight ``publish_*`` lifecycle methods; the emitter wraps it
        with ``emit_*`` typed-payload helpers and the
        :meth:`PipelineLifecycleEmitter.on_transition` dispatch matrix.
    """
    if client is None:
        msg = (
            "build_publisher_and_emitter: 'client' must be a connected NATS "
            "client; got None. The daemon is responsible for opening "
            "exactly one client (ASSUM-011) and passing it here — never "
            "open a second connection inside this factory."
        )
        raise ValueError(msg)

    pipeline_config = config if config is not None else PipelineConfig()

    publisher = PipelinePublisher(client)
    emitter = PipelineLifecycleEmitter(
        publisher=publisher,
        config=pipeline_config,
    )
    logger.debug(
        "build_publisher_and_emitter: bound publisher + emitter to shared "
        "client (progress_interval_seconds=%d)",
        pipeline_config.progress_interval_seconds,
    )
    return publisher, emitter
