"""``forge serve`` — long-lived daemon subcommand (TASK-F009-001 + TASK-FW10-001).

This module is the public entry-point for the ``forge serve`` subcommand
introduced by FEAT-FORGE-009. It runs the JetStream consumer daemon and
the healthz HTTP readiness probe concurrently via ``asyncio.wait`` with
``FIRST_COMPLETED`` semantics — first task to return cancels the other,
so a daemon failure stops reporting healthy and a healthz failure stops
consuming.

TASK-FW10-001 wiring (Wave 1, foundation)
-----------------------------------------

1. ``_run_serve`` opens **one** NATS client via the daemon's
   :data:`forge.cli._serve_daemon.nats_connect` seam (ASSUM-011). The
   single client is shared with all downstream constructors — the
   dispatcher, the deps factory, the publisher, and the daemon's first
   attach — so the daemon's startup path contains exactly one
   ``nats.connect(...)`` call.
2. Both ``reconcile_on_boot`` routines run synchronously **before** the
   durable consumer is attached:

   - :func:`forge.lifecycle.recovery.reconcile_on_boot` reconciles
     non-terminal SQLite rows (PREPARING / RUNNING / PAUSED / FINALISING).
   - :func:`forge.adapters.nats.pipeline_consumer.reconcile_on_boot`
     drains JetStream redeliveries against the SQLite truth.

   Both are exposed as module-level rebindable seams
   (:data:`recovery_reconcile_on_boot`, :data:`consumer_reconcile_on_boot`)
   so this task can wire the boot order without dragging in the full
   production deps graph (which is owned by later tasks). Tests rebind
   these to assert the ordering invariant.
3. After both routines complete, ``state.chain_ready`` flips True. The
   healthz endpoint reads this flag and returns 503 / ``chain_not_ready``
   until then (TASK-FW10-001 ASSUM-012; AC for healthz row 1).
4. The daemon and healthz coroutines are then started; the daemon
   receives the shared client via :func:`run_daemon`'s ``client``
   keyword, so it does **not** call ``nats.connect(...)`` on its first
   attach.

Re-exports
----------

The two integration-contract constants live in
:mod:`forge.cli._serve_config` but are also re-exported here so callers
can use the canonical import path documented in the acceptance
criteria::

    from forge.cli.serve import DEFAULT_HEALTHZ_PORT  # 8080
    from forge.cli.serve import DEFAULT_DURABLE_NAME  # "forge-serve"
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any, Awaitable, Callable

import click

from forge.cli import _serve_daemon
from forge.cli._serve_config import (
    DEFAULT_DURABLE_NAME,
    DEFAULT_HEALTHZ_PORT,
    ServeConfig,
)
from forge.cli._serve_daemon import run_daemon
from forge.cli._serve_healthz import run_healthz_server
from forge.cli._serve_state import SubscriptionState

logger = logging.getLogger(__name__)

# stdlib ``logging`` format chosen for daemon-grep readability across
# replicas: ISO-8601 timestamp, level, logger name, message. If the
# project ever moves to structlog/JSON, ``_configure_logging`` is the
# single swap point — keep that in mind before scattering more
# ``basicConfig`` calls.
_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOG_DATEFMT = "%Y-%m-%dT%H:%M:%S"


# ---------------------------------------------------------------------------
# Reconcile-on-boot seams (TASK-FW10-001)
# ---------------------------------------------------------------------------


ReconcileFn = Callable[[Any], Awaitable[None]]
"""``async (client: nats_client) -> None`` — boot-time reconciliation seam.

Receives the shared NATS client so the routine can construct its NATS-
side dependencies (publishers, redelivery readers) against the same
connection ``_run_serve`` opened. The default implementations are
no-ops; production wiring is filled in by later FW10 tasks. Tests
rebind these to assert ordering, deps sharing, and "ran before
attach".
"""


async def _default_recovery_reconcile_on_boot(client: Any) -> None:
    """Default no-op for the SQLite-side recovery reconcile.

    Production wiring (later FW10 task) constructs the persistence,
    publisher, and approval_publisher and calls
    :func:`forge.lifecycle.recovery.reconcile_on_boot`. Until that
    lands, the seam is a logged no-op so the boot order is observable
    without forcing an empty SQLite reconciliation pass at every
    process start.
    """
    logger.debug(
        "forge-serve: recovery_reconcile_on_boot seam not bound to "
        "production wiring (default no-op)"
    )


async def _default_consumer_reconcile_on_boot(client: Any) -> None:
    """Default no-op for the JetStream-side consumer reconcile.

    Production wiring (later FW10 task) constructs the
    :class:`forge.adapters.nats.pipeline_consumer.ReconcileDeps` and
    calls :func:`forge.adapters.nats.pipeline_consumer.reconcile_on_boot`.
    The seam stays a logged no-op until then.
    """
    logger.debug(
        "forge-serve: consumer_reconcile_on_boot seam not bound to "
        "production wiring (default no-op)"
    )


#: Module-level rebindable seam: SQLite-side recovery reconcile.
recovery_reconcile_on_boot: ReconcileFn = _default_recovery_reconcile_on_boot

#: Module-level rebindable seam: JetStream-side consumer reconcile.
consumer_reconcile_on_boot: ReconcileFn = _default_consumer_reconcile_on_boot


def _configure_logging(level_name: str) -> None:
    """Attach a stderr handler honouring ``FORGE_LOG_LEVEL``.

    TASK-FORGE-FRR-002. Before this call, every ``logger.info(...)``
    inside ``_serve_daemon`` and ``_serve_healthz`` was silently
    dropped at INFO and below because the root logger had no handler
    — see the 2026-05-01 GB10 first-real-run where ``docker logs
    forge-prod`` was empty despite a successful consume + ack.

    An unrecognised value (``FORGE_LOG_LEVEL=banana``) does not crash
    the daemon: it falls back to INFO with a one-line stderr warning
    so an obvious operator typo never blocks startup.

    ``logging.basicConfig`` is invoked with ``force=False`` (the
    default), which makes re-entrant calls in the same process a
    no-op. Tests that invoke ``serve_cmd`` more than once therefore
    do not pile up duplicate handlers on the root logger.
    """
    resolved = getattr(logging, level_name.upper(), None)
    if not isinstance(resolved, int):
        sys.stderr.write(
            f"unrecognised FORGE_LOG_LEVEL={level_name!r}, defaulting to INFO\n"
        )
        resolved = logging.INFO
    logging.basicConfig(
        level=resolved,
        format=_LOG_FORMAT,
        datefmt=_LOG_DATEFMT,
        stream=sys.stderr,
    )


async def _close_client_quietly(client: Any) -> None:
    """Close a NATS client, swallowing close errors.

    The shared client lifecycle straddles three coroutines (recovery
    reconcile, consumer reconcile, run_daemon). If any of them already
    closed the client, the second close raises an ``IOError`` /
    ``InvalidStateError`` that we do not want to surface — the process
    is already shutting down.
    """
    if client is None:
        return
    try:
        await asyncio.wait_for(
            client.close(),
            timeout=_serve_daemon.SHUTDOWN_TIMEOUT_SECONDS,
        )
    except (asyncio.TimeoutError, Exception) as exc:  # noqa: BLE001
        logger.debug("forge-serve: shared client close error (%s)", exc)


async def _run_serve(config: ServeConfig, state: SubscriptionState) -> None:
    """Open one NATS client, run reconcile_on_boot, then daemon + healthz.

    TASK-FW10-001 boot order (load-bearing — see §5 of
    IMPLEMENTATION-GUIDE.md):

    1. ``nats_connect(config.nats_url)`` — exactly one connect call on
       the startup path (AC-006). All downstream collaborators share
       this client.
    2. ``recovery_reconcile_on_boot(client)`` — SQLite-side recovery
       (PREPARING / RUNNING / PAUSED / FINALISING reconciliation).
    3. ``consumer_reconcile_on_boot(client)`` — JetStream-side redelivery
       reconciliation against the SQLite truth.
    4. ``state.set_chain_ready(True)`` — healthz now reports based on the
       composite gate (live AND chain_ready).
    5. Schedule ``run_daemon(config, state, client=client)`` and
       ``run_healthz_server(config, state)``; first to complete cancels
       the other.

    The daemon receives the shared client so its **first** attach does
    not call ``nats.connect(...)`` (the AC restricts the startup path
    to one connect). Reconnects after a broker drop still open a fresh
    client through the daemon's :data:`_serve_daemon.nats_connect` seam
    — the AC scopes "no second connect" to startup, not to
    runtime-reconnect.

    Args:
        config: Validated :class:`ServeConfig`. Source of NATS URL,
            healthz port, and durable name.
        state: Shared :class:`SubscriptionState`. ``chain_ready`` is
            flipped here; ``live`` is flipped by the daemon. Both are
            read by the healthz handler.
    """
    client: Any = await _serve_daemon.nats_connect(config.nats_url)
    try:
        # Step 2 + 3 — ASSUM-009 / F1: BOTH reconciliations must run
        # before the durable consumer attaches, so a redelivered
        # envelope cannot land on an unreconciled history view.
        await recovery_reconcile_on_boot(client)
        await consumer_reconcile_on_boot(client)

        # Step 4 — chain composition complete. The daemon may still
        # be bootstrapping its pull subscription, but the lifecycle
        # chain is reconciled and ready to receive dispatches.
        await state.set_chain_ready(True)

        # Step 5 — daemon (with shared client) and healthz concurrently.
        daemon_task: asyncio.Task[None] = asyncio.create_task(
            run_daemon(config, state, client=client),
            name="forge-serve-daemon",
        )
        healthz_task: asyncio.Task[None] = asyncio.create_task(
            run_healthz_server(config, state),
            name="forge-serve-healthz",
        )
        done, pending = await asyncio.wait(
            {daemon_task, healthz_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        # Drain cancellations so the AppRunner.cleanup() finally-block
        # in run_healthz_server actually runs before we return.
        await asyncio.gather(*pending, return_exceptions=True)
        # Surface any non-cancellation exceptions raised by the winner.
        for task in done:
            if task.cancelled():
                continue
            exc = task.exception()
            if exc is not None:
                raise exc
    finally:
        # ``run_daemon`` already closes the client on its own
        # iteration's ``finally`` block. This second close is
        # defensive: if the daemon never reached the iteration finally
        # (e.g. cancelled mid-recovery_reconcile), we still release
        # the connection rather than relying on garbage collection.
        await _close_client_quietly(client)


@click.command(name="serve")
def serve_cmd() -> None:
    """Run the long-lived forge daemon (JetStream consumer + healthz)."""
    config = ServeConfig.from_env()
    # Attach the stderr handler BEFORE _run_serve schedules the daemon
    # / healthz coroutines, so their first ``logger.info`` lines reach
    # ``docker logs`` and ``journalctl`` instead of the silent root
    # logger. TASK-FORGE-FRR-002.
    _configure_logging(config.log_level)
    state = SubscriptionState()
    asyncio.run(_run_serve(config, state))


__all__ = [
    "DEFAULT_DURABLE_NAME",
    "DEFAULT_HEALTHZ_PORT",
    "ReconcileFn",
    "ServeConfig",
    "SubscriptionState",
    "consumer_reconcile_on_boot",
    "recovery_reconcile_on_boot",
    "run_daemon",
    "run_healthz_server",
    "serve_cmd",
]
