"""Reasoning-model-driven retry coordinator for the Forge dispatch layer.

This module is intentionally policy-free. There is **no fixed
max-retry** count at this layer (ASSUM-005): the reasoning loop owns
retry policy — when to retry, what additional context to attach, and
when to stop. The :class:`RetryCoordinator` only executes one retry
decision correctly:

1. Generate a **fresh correlation key**. The orchestrator's own
   :class:`~forge.dispatch.correlation.CorrelationRegistry` issues a
   distinct key on every ``dispatch()`` invocation; this layer does
   NOT reuse the prior attempt's key.
2. **Append additional context** to the dispatch parameters without
   mutating the original list — list concatenation produces a new
   list object the orchestrator owns.
3. Persist a **sibling resolution record** linked via
   ``retry_of=<prev_resolution_id>``. The original record is **not**
   overwritten — both rows exist after a retry, so the retry chain is
   recoverable from persistence alone.
4. **Increment** ``attempt_no`` from the previous outcome's counter.

Implements scenario A.retry-with-additional-context (TASK-SAD-007).

Why no max-retry counter here
-----------------------------

A counter at this layer would silently disagree with the reasoning
loop. The reasoning loop has visibility on retry budget, additional
context, and whether the same failure is recurring — none of which
this coordinator can observe. A coordinator-side max-retry would
therefore either short-circuit a legitimately long retry chain or rate
limit the loop in a way the loop cannot see. Both modes are wrong.
**Do not add a max-retry counter, exponential backoff, jitter, or rate
limit to this module.** If you find yourself wanting one, that signal
belongs in the reasoning loop's policy.

Edge case: ``Degraded`` retries
-------------------------------

If the reasoning loop calls retry on a :class:`~forge.dispatch.models.Degraded`
outcome, the orchestrator will re-resolve the capability against a
fresh discovery snapshot and may produce a different ``Degraded`` —
e.g., a new specialist may have joined since the prior attempt. This
is the correct behaviour per ``D.cache-freshness-on-join``; do not
short-circuit by inspecting the previous outcome's kind here.
"""

from __future__ import annotations

import logging

from forge.dispatch.models import DispatchOutcome
from forge.dispatch.orchestrator import DispatchOrchestrator
from forge.dispatch.persistence import DispatchParameter

logger = logging.getLogger(__name__)


class RetryCoordinator:
    """Reasoning-model-driven retry. No fixed max-retry at this layer.

    Each retry creates a sibling
    :class:`~forge.discovery.models.CapabilityResolution` record linked
    via ``retry_of=<prev_resolution_id>``. The reasoning loop chooses
    whether to invoke retry and what additional context to attach;
    this coordinator only forwards the right arguments into the
    orchestrator's normal dispatch path.

    Args:
        orchestrator: The :class:`DispatchOrchestrator` whose
            ``dispatch()`` performs the underlying attempt. The
            orchestrator owns correlation-key generation, persistence
            (write-before-send), bind, publish, wait, and parse — this
            coordinator only computes the three retry-specific
            arguments (next ``attempt_no``, ``retry_of`` linkage, and
            the merged parameters list).
    """

    def __init__(self, orchestrator: DispatchOrchestrator) -> None:
        if not isinstance(orchestrator, DispatchOrchestrator):
            # Guard at the boundary — duck-typed orchestrators silently
            # bypass the write-before-send invariant the real one
            # enforces, so we refuse them here rather than discover the
            # leak at retry time.
            raise TypeError(
                "orchestrator must be DispatchOrchestrator, got "
                f"{type(orchestrator).__name__}"
            )
        self._orchestrator = orchestrator

    async def retry_with_context(
        self,
        *,
        previous_outcome: DispatchOutcome,
        capability: str,
        original_parameters: list[DispatchParameter],
        additional_context: list[DispatchParameter],
    ) -> DispatchOutcome:
        """Re-dispatch with a fresh correlation and additional context.

        Args:
            previous_outcome: Outcome of the prior dispatch attempt.
                Supplies ``resolution_id`` (used as ``retry_of``) and
                ``attempt_no`` (the basis for the new attempt's
                counter). Any concrete :data:`DispatchOutcome` variant
                is accepted — ``Degraded`` retries deliberately re-run
                the resolve step, see module docstring.
            capability: Tool name to dispatch against, forwarded
                verbatim to :meth:`DispatchOrchestrator.dispatch`.
            original_parameters: The previous attempt's parameters.
                Must be passed through unchanged — this list is
                **not** mutated; the new parameters list is built via
                concatenation.
            additional_context: Extra parameters the reasoning loop
                wants the retry attempt to carry. Appended after the
                original parameters so an audit shows the prior call's
                parameters first, then the additional context that
                provoked the retry.

        Returns:
            The :data:`DispatchOutcome` produced by the orchestrator's
            normal dispatch path. The outcome's ``attempt_no`` is one
            greater than ``previous_outcome.attempt_no`` and the new
            persisted resolution row carries
            ``retry_of=previous_outcome.resolution_id``.

        Raises:
            Exception: any error raised by the orchestrator's dispatch
                propagates unchanged. We do not swallow errors here —
                the reasoning loop needs to see real failures so it
                can decide whether to retry again.
        """
        next_attempt_no = previous_outcome.attempt_no + 1
        retry_of_id = previous_outcome.resolution_id
        # List concatenation, NOT in-place extend. The original list
        # passed by the caller is never mutated; a fresh list object
        # is handed to the orchestrator every time. This is the only
        # parameter-side mutation guarantee that lets the reasoning
        # loop reuse ``original_parameters`` across multiple retry
        # attempts safely.
        merged_parameters = original_parameters + additional_context

        logger.info(
            "retry.dispatch capability=%s retry_of=%s next_attempt_no=%d "
            "extra_params=%d",
            capability,
            retry_of_id,
            next_attempt_no,
            len(additional_context),
        )

        return await self._orchestrator.dispatch(
            capability=capability,
            parameters=merged_parameters,
            attempt_no=next_attempt_no,
            retry_of=retry_of_id,
        )


__all__ = ["RetryCoordinator"]
