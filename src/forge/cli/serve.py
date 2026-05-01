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

import click

from forge.cli._serve_config import (
    DEFAULT_DURABLE_NAME,
    DEFAULT_HEALTHZ_PORT,
    ServeConfig,
)
from forge.cli._serve_daemon import run_daemon
from forge.cli._serve_healthz import run_healthz_server
from forge.cli._serve_state import SubscriptionState


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
