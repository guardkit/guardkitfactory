"""Outcome correlation + degraded-path synthesis (TASK-SAD-009).

Two related domain helpers that close out the dispatch lifecycle:

1. :func:`correlate_outcome` — the writer referenced in
   :class:`forge.discovery.models.CapabilityResolution` docstrings.
   Stamps the resolution row with ``outcome_correlated=True`` and a
   back-reference to the downstream gate decision (FEAT-FORGE-004).
   **Idempotent** at the SQL layer so the gating layer can call it
   freely without coordinating with retries.

2. :func:`synthesize_degraded` — pure-function fallback that produces a
   :class:`forge.dispatch.models.Degraded` outcome when no specialist
   can resolve, when the bus is unreachable, or when discovery is
   running on a stale snapshot. The reasoning loop consumes the result
   as a regular "failed stage" outcome — there is no special branch
   for degraded results.

Implements scenarios A.outcome-correlation, C.unresolved-capability,
C.degraded-status-exclusion, E.bus-disconnect, and E.registry-outage.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal

from forge.dispatch.models import Degraded

if TYPE_CHECKING:  # pragma: no cover - import-cycle guard
    from forge.discovery.models import CapabilityResolution
    from forge.dispatch.persistence import SqliteHistoryWriter

logger = logging.getLogger(__name__)

# Closed enumeration of synthetic-degraded reasons. Mirrors the task
# spec's :data:`Literal` so static type-checkers reject typos at the
# call site (``E.registry-outage`` cannot be misspelt into a passing
# test).
DegradedReason = Literal[
    "no_specialist_resolvable",
    "all_resolvable_specialists_degraded",
    "bus_disconnected",
    "registry_unreadable_stale_snapshot",
]


def correlate_outcome(
    resolution_id: str,
    gate_decision_id: str,
    *,
    db_writer: SqliteHistoryWriter,
) -> CapabilityResolution:
    """Link a resolution record to its downstream gate decision.

    Idempotent: calling twice with the same arguments returns equal
    records and issues exactly one UPDATE statement at the SQL layer
    (the second call short-circuits in
    :meth:`SqliteHistoryWriter.correlate_outcome`).

    Sets ``outcome_correlated=True`` and records ``gate_decision_id`` on
    the resolution row, then returns the (possibly already-updated)
    :class:`CapabilityResolution`.

    Args:
        resolution_id: Primary key of the resolution to correlate.
            Must reference an already-persisted row.
        gate_decision_id: Identifier of the downstream gate decision
            (FEAT-FORGE-004). Persisted onto the resolution row.
        db_writer: SQLite-backed history writer that owns the
            persistence transaction. Injected so unit tests can supply
            a mock writer and assert the SQL-level idempotency
            contract.

    Returns:
        The :class:`CapabilityResolution` after correlation, with
        ``outcome_correlated=True`` and ``gate_decision_id`` populated.

    Raises:
        KeyError: If no resolution row exists for ``resolution_id``.
            We refuse to silently no-op because that would hide bugs in
            the gating layer's call site.
        ValueError: If a different ``gate_decision_id`` is already
            recorded for this resolution. Idempotency is per
            (resolution, gate) pair, not "any gate".
        TypeError: If either argument is not a non-empty string.
    """
    logger.debug(
        "correlate_outcome.start resolution_id=%s gate_decision_id=%s",
        resolution_id,
        gate_decision_id,
    )
    resolution = db_writer.correlate_outcome(resolution_id, gate_decision_id)
    logger.info(
        "correlate_outcome.complete resolution_id=%s gate_decision_id=%s "
        "outcome_correlated=%s",
        resolution.resolution_id,
        resolution.gate_decision_id,
        resolution.outcome_correlated,
    )
    return resolution


def synthesize_degraded(
    *,
    capability: str,
    reason: DegradedReason,
    snapshot_stale: bool = False,
    attempt_no: int = 1,
) -> Degraded:
    """Synthesise a :class:`Degraded` outcome for the reasoning loop.

    Pure function — no I/O, no persistence, no global state. The
    persistence side-effect happens earlier in the dispatch lifecycle
    via the orchestrator's normal :func:`persist_resolution` step
    (when there is a resolution to persist at all).

    The reasoning loop consumes :class:`Degraded` as a regular stage
    outcome. ``snapshot_stale=True`` is recorded into the ``reason``
    field so callers downstream of a stale-cache resolution can
    distinguish a "registry was unreachable" failure from a clean
    "no specialist resolvable" outcome.

    Args:
        capability: The tool / capability name that failed to resolve.
            Used to construct a synthetic ``resolution_id`` so the
            reasoning loop can correlate the degraded outcome back to
            the capability that triggered it without crossing layers.
        reason: One of the four canonical degradation reasons (see
            :data:`DegradedReason`).
        snapshot_stale: When ``True``, the reason field is decorated
            with a stale-snapshot marker. Set by the orchestrator's
            registry-outage path so the reasoning loop sees both *why*
            it degraded and *that* the underlying registry was
            unavailable.
        attempt_no: Monotonic attempt counter, starting at 1. Default
            ``1`` matches the first-attempt convention used elsewhere
            in the dispatch domain.

    Returns:
        A :class:`Degraded` whose ``reason`` carries the input reason
        (possibly decorated with a staleness marker) and whose
        ``resolution_id`` encodes ``capability`` and ``attempt_no``.
    """
    if not isinstance(capability, str) or not capability:
        raise TypeError("capability must be a non-empty str")
    if attempt_no < 1:
        raise ValueError(
            f"attempt_no must be >= 1, got {attempt_no!r}",
        )

    # Compose the reason string. We keep the raw enum value as a prefix
    # so machine consumers can substring-match without parsing — and
    # tack on the stale-snapshot marker when relevant. Two reasons
    # already imply staleness (registry_unreadable_stale_snapshot); for
    # those we keep the marker too because the reasoning loop's existing
    # "stale" detector predates this enum.
    reason_components: list[str] = [reason]
    if snapshot_stale and "stale" not in reason:
        reason_components.append("stale_snapshot")
    elif "stale" in reason:
        # Expand the inline literal into the same trailing token so the
        # reasoning loop's matcher fires uniformly.
        reason_components.append("stale_snapshot")
    composed_reason = ":".join(reason_components)

    # Synthetic resolution_id. We embed ``capability`` and
    # ``attempt_no`` so the downstream reasoning loop can correlate the
    # outcome back without needing access to a real CapabilityResolution.
    synthetic_resolution_id = f"degraded::{capability}::{attempt_no}"

    logger.info(
        "synthesize_degraded capability=%s reason=%s stale=%s attempt=%d",
        capability,
        composed_reason,
        snapshot_stale,
        attempt_no,
    )

    return Degraded(
        resolution_id=synthetic_resolution_id,
        attempt_no=attempt_no,
        reason=composed_reason,
    )


__all__ = ["DegradedReason", "correlate_outcome", "synthesize_degraded"]
