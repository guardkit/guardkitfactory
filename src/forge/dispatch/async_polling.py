"""Async-mode polling coordinator for the Forge dispatch layer (TASK-SAD-008).

Some specialist capabilities are long-running: their first reply carries a
``run_identifier`` rather than a final result, and Forge polls the
capability's *status tool* until the final outcome arrives. The status
tool is itself a regular dispatch — so the polling path **reuses the
orchestrator** rather than implementing a parallel code path. Every
poll therefore traverses the same five steps the orchestrator enforces
on any other dispatch:

1. Resolve against a stable cache snapshot.
2. Persist the resolution row (write-before-send).
3. Bind the reply subscription (subscribe-before-publish).
4. Publish the dispatch command.
5. Wait + parse into a :data:`DispatchOutcome`.

Convergence contract
--------------------

The sync-reply path and the async-mode path **converge at the
:data:`DispatchOutcome` level**: both produce the same outcome shape,
so the reasoning loop sees one contract regardless of whether the
specialist replied synchronously or via async-mode polling. This
module's :class:`AsyncPollingCoordinator` is the bridge.

Implements scenario D.async-mode-polling.

Design notes
------------

* ``poll_interval_seconds`` is **constant** by design — no adaptive
  backoff. The spec is silent on poll cadence and the simplest
  behaviour is the least-surprising one. A future requirement that
  demands backoff can extend the coordinator without breaking the
  sealed-by-default semantics today.
* The hard 900-second ceiling (ASSUM-003) is the **same** cut-off the
  per-attempt :class:`~forge.dispatch.timeout.TimeoutCoordinator`
  enforces. Polling cannot extend the dispatch beyond this ceiling.
* Cumulative elapsed time is measured via the injected
  :class:`~forge.discovery.protocol.Clock`, so tests freeze or advance
  time deterministically without relying on real ``asyncio.sleep``
  pacing.
* Every outcome returned to the caller carries the **caller's**
  ``resolution_id`` (the AsyncPending the reasoning loop dispatched
  against). Each polling dispatch creates its own persistence row
  with its own resolution_id; re-stamping at the boundary keeps the
  reasoning-loop contract simple — one logical dispatch in, one
  outcome out, all sharing one resolution_id.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Protocol

from forge.discovery.protocol import Clock
from forge.dispatch.models import (
    AsyncPending,
    DispatchError,
    DispatchOutcome,
)
from forge.dispatch.persistence import DispatchParameter

if TYPE_CHECKING:  # pragma: no cover - import only for static type checking
    # The concrete DispatchOrchestrator lives in
    # ``forge.dispatch.orchestrator`` (TASK-SAD-006). It is imported only
    # for type checking so the polling coordinator can be exercised
    # against any object that satisfies :class:`_OrchestratorLike`.
    from forge.dispatch.orchestrator import DispatchOrchestrator  # noqa: F401


logger = logging.getLogger(__name__)


# ASSUM-003 — hard ceiling matching the per-attempt timeout coordinator.
DEFAULT_MAX_TOTAL_SECONDS: float = 900.0

# Default poll cadence — see "Design notes" above for why this is
# constant rather than adaptive.
DEFAULT_POLL_INTERVAL_SECONDS: float = 5.0

# Sentinel error explanation surfaced when polling exceeds the ceiling.
# Pinned as a module-level constant so callers (tests, downstream
# matchers) do not depend on a string literal that could drift.
CEILING_EXCEEDED_EXPLANATION: str = "async_polling_ceiling_exceeded"

# Parameter name used to thread the run_identifier into each status-tool
# dispatch. Kept as a constant so the contract is greppable from the
# reasoning-loop side and from specialist implementations alike.
_RUN_IDENTIFIER_PARAM: str = "run_identifier"


class _OrchestratorLike(Protocol):
    """Structural surface of the orchestrator the coordinator depends on.

    Only the keyword-arg form of :meth:`DispatchOrchestrator.dispatch`
    is exercised. Declaring the dependency structurally lets the test
    suite drop a recording stub in without inheriting from the
    production class — and keeps the coordinator decoupled from any
    transport-specific construction concerns.
    """

    async def dispatch(
        self,
        *,
        capability: str,
        parameters: list[DispatchParameter],
        attempt_no: int = ...,
        retry_of: str | None = ...,
        intent_pattern: str | None = ...,
        build_id: str = ...,
        stage_label: str = ...,
    ) -> DispatchOutcome:
        ...


def _restamp_outcome(
    outcome: DispatchOutcome,
    *,
    resolution_id: str,
    attempt_no: int,
) -> DispatchOutcome:
    """Return a copy of ``outcome`` with the converge-caller's identity.

    Every polling dispatch creates a brand-new persistence row carrying
    its own ``resolution_id``. Re-stamping at the boundary preserves
    the reasoning loop's view: one logical dispatch in, one outcome
    out, all sharing the *original* AsyncPending's resolution_id.

    The discriminated-union members all derive from
    :class:`pydantic.BaseModel`, so :meth:`model_copy` produces a new
    validated instance without mutating the input. The discriminator
    field (``kind``) is preserved by the copy.
    """

    return outcome.model_copy(
        update={"resolution_id": resolution_id, "attempt_no": attempt_no},
    )


class AsyncPollingCoordinator:
    """Convert :class:`AsyncPending` → :class:`SyncResult` /
    :class:`DispatchError` by polling the specialist's status tool.

    Each poll is a regular dispatch via the orchestrator, so the full
    subscribe-before-publish / write-before-send / exactly-once
    pipeline is exercised on every iteration. The status tool's reply
    is parsed by the existing reply parser (TASK-SAD-005), and the
    coordinator converts the resulting :data:`DispatchOutcome` back
    into a single boundary outcome for the reasoning loop.

    Args:
        orchestrator: The :class:`DispatchOrchestrator` (or any object
            satisfying :class:`_OrchestratorLike`) used to dispatch
            each status-tool poll.
        clock: Time provider — the cumulative-time check that enforces
            the ASSUM-003 ceiling reads from this clock so tests can
            advance time deterministically.
        poll_interval_seconds: Constant pause between polls (no
            adaptive backoff). ``0.0`` is permitted so tests can run
            without real-time delay.
        max_total_seconds: Hard ceiling on cumulative polling time
            (defaults to the ASSUM-003 900s value). Strictly positive.

    Raises:
        ValueError: ``poll_interval_seconds`` is negative or
            ``max_total_seconds`` is not strictly positive.
    """

    def __init__(
        self,
        orchestrator: _OrchestratorLike,
        clock: Clock,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        max_total_seconds: float = DEFAULT_MAX_TOTAL_SECONDS,
    ) -> None:
        if poll_interval_seconds < 0:
            raise ValueError(
                "poll_interval_seconds must be >= 0, got "
                f"{poll_interval_seconds!r}",
            )
        if max_total_seconds <= 0:
            raise ValueError(
                "max_total_seconds must be strictly positive, got "
                f"{max_total_seconds!r}",
            )
        self._orchestrator = orchestrator
        self._clock = clock
        self._poll_interval_seconds = float(poll_interval_seconds)
        self._max_total_seconds = float(max_total_seconds)

    @property
    def poll_interval_seconds(self) -> float:
        """Constant pause between polls (no adaptive backoff)."""
        return self._poll_interval_seconds

    @property
    def max_total_seconds(self) -> float:
        """Hard ceiling on cumulative polling time (ASSUM-003)."""
        return self._max_total_seconds

    async def converge(
        self,
        pending: AsyncPending,
        *,
        status_capability: str = "status",
    ) -> DispatchOutcome:
        """Poll the status tool until a final outcome arrives.

        Each poll dispatches the capability named ``status_capability``
        (default ``"status"``) via the injected orchestrator, threading
        the latest ``run_identifier`` as a dispatch parameter. The
        resulting :data:`DispatchOutcome` is interpreted as follows:

        * :class:`AsyncPending` — keep polling, updating the cached
          ``run_identifier`` to the freshest value the specialist
          returned (some specialists rotate the handle across polls).
        * :class:`SyncResult`, :class:`DispatchError`, or
          :class:`Degraded` — final outcome; re-stamp with the
          original ``resolution_id`` and return.

        If cumulative elapsed time (read via the injected
        :class:`Clock`) reaches ``max_total_seconds`` before a final
        outcome arrives, the coordinator emits
        :class:`DispatchError` carrying
        :data:`CEILING_EXCEEDED_EXPLANATION` (``"async_polling_ceiling_exceeded"``)
        as ``error_explanation``.

        Args:
            pending: The :class:`AsyncPending` returned by the initial
                dispatch. Its ``run_identifier`` is the first handle
                threaded into the status tool, and its
                ``resolution_id`` / ``attempt_no`` identify the boundary
                outcome the reasoning loop is awaiting.
            status_capability: The status tool's capability name. The
                default ``"status"`` matches the per-specialist
                convention; pass an override for specialists that use
                a different name.

        Returns:
            A :data:`DispatchOutcome` linked to the original
            ``pending.resolution_id`` and ``pending.attempt_no``.

        Notes:
            * Polling never bypasses the orchestrator — every poll is
              a full dispatch attempt, which means
              subscribe-before-publish, write-before-send, and the
              per-attempt timeout coordinator are all in play for each
              individual poll.
            * The poll interval is constant by design (see module
              docstring). ``poll_interval_seconds=0.0`` is supported
              for tests; production callers should use a meaningful
              cadence.
        """

        if not isinstance(pending, AsyncPending):
            raise TypeError(
                "pending must be AsyncPending, got "
                f"{type(pending).__name__}",
            )

        started_at = self._clock.now()
        latest_pending: AsyncPending = pending

        while True:
            # Cumulative-time check FIRST so a stale-by-construction
            # caller (clock already past the ceiling) cannot smuggle
            # in an extra dispatch before the ceiling fires.
            elapsed_seconds = (
                self._clock.now() - started_at
            ).total_seconds()
            if elapsed_seconds >= self._max_total_seconds:
                logger.info(
                    "async_polling.ceiling_exceeded "
                    "resolution_id=%s elapsed_seconds=%.3f max_seconds=%.3f",
                    pending.resolution_id,
                    elapsed_seconds,
                    self._max_total_seconds,
                )
                return DispatchError(
                    resolution_id=pending.resolution_id,
                    attempt_no=pending.attempt_no,
                    error_explanation=CEILING_EXCEEDED_EXPLANATION,
                )

            # Constant pause between polls. ``asyncio.sleep(0)``
            # yields control back to the event loop without a real
            # delay so deterministic tests stay fast.
            await asyncio.sleep(self._poll_interval_seconds)

            # Each poll is a regular dispatch — preserves all
            # invariants. The status tool reply is parsed by the
            # standard reply parser inside the orchestrator.
            outcome: DispatchOutcome = await self._orchestrator.dispatch(
                capability=status_capability,
                parameters=[
                    DispatchParameter(
                        name=_RUN_IDENTIFIER_PARAM,
                        value=latest_pending.run_identifier,
                    ),
                ],
            )

            if isinstance(outcome, AsyncPending):
                # Specialist still working — keep polling, but update
                # the cached run_identifier in case the specialist
                # rotated it.
                logger.debug(
                    "async_polling.still_pending "
                    "resolution_id=%s run_identifier=%s",
                    pending.resolution_id,
                    outcome.run_identifier,
                )
                latest_pending = outcome
                continue

            # Terminal outcome (SyncResult / DispatchError / Degraded).
            # Re-stamp with the converge-caller's identity so the
            # reasoning loop sees a consistent resolution_id.
            logger.info(
                "async_polling.converged "
                "resolution_id=%s outcome_kind=%s elapsed_seconds=%.3f",
                pending.resolution_id,
                getattr(outcome, "kind", "<unknown>"),
                elapsed_seconds,
            )
            return _restamp_outcome(
                outcome,
                resolution_id=pending.resolution_id,
                attempt_no=pending.attempt_no,
            )


__all__ = [
    "CEILING_EXCEEDED_EXPLANATION",
    "DEFAULT_MAX_TOTAL_SECONDS",
    "DEFAULT_POLL_INTERVAL_SECONDS",
    "AsyncPollingCoordinator",
]
