"""``forge serve`` — long-lived daemon subcommand (TASK-F009-001 scaffold).

This module is the public entry-point for the new ``forge serve``
subcommand introduced by FEAT-FORGE-009. It runs the JetStream consumer
daemon and the healthz HTTP readiness probe concurrently via
:func:`asyncio.gather`.

The current task (T1) lays only the **boundary surface** — the actual
daemon body lives in :mod:`forge.cli._serve_daemon` (filled by
TASK-F009-003) and the HTTP server lives in
:mod:`forge.cli._serve_healthz` (filled by TASK-F009-004). Both
coroutines are stubs that return immediately, so invoking ``forge
serve`` exits ``0`` — the scaffold's smoke test.

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

import click

from forge.cli._serve_config import (
    DEFAULT_DURABLE_NAME,
    DEFAULT_HEALTHZ_PORT,
    ServeConfig,
)
from forge.cli._serve_daemon import run_daemon
from forge.cli._serve_healthz import run_healthz_server
from forge.cli._serve_state import SubscriptionState

# stdlib ``logging`` format chosen for daemon-grep readability across
# replicas: ISO-8601 timestamp, level, logger name, message. If the
# project ever moves to structlog/JSON, ``_configure_logging`` is the
# single swap point — keep that in mind before scattering more
# ``basicConfig`` calls.
_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOG_DATEFMT = "%Y-%m-%dT%H:%M:%S"


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


async def _run_serve(config: ServeConfig, state: SubscriptionState) -> None:
    """Run the daemon and the healthz server concurrently.

    Wrapped in a private coroutine so the Click command body stays
    synchronous (Click does not natively support async callbacks).

    Wave-2 wiring (TASK-F009-004): once both bodies are real coroutines
    they each block forever, so the original ``asyncio.gather`` would
    only return on cancellation. This implementation upgrades the
    join-pattern to "first-to-complete cancels the other" — which is
    also the production-correct behaviour for a Kubernetes pod: if the
    JetStream consumer dies, the readiness probe must stop reporting
    healthy (kubelet will then restart the pod), and conversely if the
    healthz socket is lost we should not silently keep consuming
    messages.

    The pre-Wave-2 stub case (both coroutines returning immediately) is
    preserved: ``FIRST_COMPLETED`` fires on the first stub return, the
    other stub's task is cancelled (no-op for an already-completed
    coroutine), and the function exits with ``return_value`` 0 — which
    is what TASK-F009-001 ``AC-007`` smoke-tests for.
    """
    daemon_task: asyncio.Task[None] = asyncio.create_task(
        run_daemon(config, state), name="forge-serve-daemon"
    )
    healthz_task: asyncio.Task[None] = asyncio.create_task(
        run_healthz_server(config, state), name="forge-serve-healthz"
    )
    done, pending = await asyncio.wait(
        {daemon_task, healthz_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
    # Drain cancellations so the AppRunner.cleanup() finally-block in
    # run_healthz_server actually runs before we return.
    await asyncio.gather(*pending, return_exceptions=True)
    # Surface any non-cancellation exceptions raised by the winner.
    for task in done:
        if task.cancelled():
            continue
        exc = task.exception()
        if exc is not None:
            raise exc


@click.command(name="serve")
def serve_cmd() -> None:
    """Run the long-lived forge daemon (JetStream consumer + healthz)."""
    config = ServeConfig.from_env()
    # Attach the stderr handler BEFORE _run_serve schedules the daemon
    # / healthz coroutines, so their first ``logger.info`` lines (the
    # consumer-attach log and the healthz-listening log) reach
    # ``docker logs`` and ``journalctl`` instead of the silent root
    # logger. TASK-FORGE-FRR-002.
    _configure_logging(config.log_level)
    state = SubscriptionState()
    asyncio.run(_run_serve(config, state))


__all__ = [
    "DEFAULT_DURABLE_NAME",
    "DEFAULT_HEALTHZ_PORT",
    "ServeConfig",
    "SubscriptionState",
    "run_daemon",
    "run_healthz_server",
    "serve_cmd",
]
