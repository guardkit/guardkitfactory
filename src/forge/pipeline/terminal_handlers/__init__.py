"""Terminal handlers for post-stage routing decisions (TASK-MBC8-006).

This module hosts the small family of "post-stage routing shims" that
sit between a stage's gate-approval and the next dispatch step. The
single handler implemented today is the **Mode B no-diff terminal
handler** — :func:`evaluate_post_autobuild` — which decides whether a
Mode B build advances to the constitutional ``PULL_REQUEST_REVIEW``
gate, terminates as a no-op (no diff against the working branch), or
terminates as failed (the autobuild's own lifecycle reached a hard-stop
or failure terminal).

Why a routing shim, not a dispatcher
------------------------------------

ASSUM-015 (FEAT-FORGE-008): the constitutional PR-review gate has
nothing to fire on when the Mode B autobuild produces no diff. The
build must therefore terminate with a ``no-op`` outcome rather than
pause at PR review or attempt PR creation against an empty diff.

This handler is the *only* place where the no-diff vs has-diff decision
is made for Mode B. It is invoked by the Supervisor (TASK-MBC8-008)
after :class:`~forge.pipeline.mode_b_planner.ModeBChainPlanner`
returns ``next_stage = None`` for an approved AUTOBUILD entry, and
*before* any PR-creation routing happens. The actual PR creation lives
in TASK-MAG7-008's subprocess dispatcher; this handler decides whether
that dispatcher is reached at all.

Diff-result source
------------------

The handler reads the diff outcome from the AUTOBUILD ``stage_log``
row's ``details`` mapping under the key ``"changed_files_count"`` (an
integer; ``0`` means no diff). TASK-MAG7-009's autobuild result schema
records this field on the row that the autobuild runner persists to
SQLite at terminal lifecycle time. The handler does not shell out to
``git diff`` — that would re-derive a value already recorded on the
authoritative side, and would force this layer to know about repo
worktree paths it has no other reason to consult.

Defensive default: a row that is missing ``changed_files_count``
entirely (e.g. during the rollout that adds the field) is treated as
**zero** by this handler. This is the conservative choice — emitting
a NO_OP for a build that *did* produce a diff is recoverable (re-run
the autobuild, the stage_log row will then carry the field); emitting
a PR against an empty diff is not.

Three terminal routes
---------------------

- :data:`PR_REVIEW` — autobuild approved with a non-empty diff. The
  build advances to ``PULL_REQUEST_REVIEW``. The handler does not
  invoke any PR-create adapter; it merely records the routing
  decision.
- :data:`NO_OP` — autobuild approved with zero changed files. Recorded
  as a terminal ``complete`` build with rationale
  :data:`NO_DIFF_RATIONALE` (Group M scenario).
- :data:`ROUTE_FAILED` — autobuild reached a hard-stop or failed
  terminal. Recorded as terminal ``failed`` with the autobuild's
  rationale surfaced (Group C "internal hard-stop is propagated").

References
----------

- TASK-MBC8-006 — this implementation.
- ASSUM-015 — no-diff autobuild does not attempt PR creation.
- TASK-MBC8-003 — :class:`ModeBChainPlanner`. The planner returns
  ``next_stage = None`` for an approved autobuild with no diff and
  defers the terminal decision to this handler.
- TASK-MAG7-008 — subprocess PR dispatcher. Reached only when this
  handler returns :data:`PR_REVIEW` and the constitutional review
  approves.
- TASK-MAG7-009 — autobuild result schema (records
  ``changed_files_count``).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from forge.lifecycle.persistence import Build
from forge.pipeline.mode_b_planner import APPROVED, FAILED, HARD_STOP, StageEntry
from forge.pipeline.stage_taxonomy import StageClass

__all__ = [
    "NO_DIFF_RATIONALE",
    "NO_OP",
    "PR_REVIEW",
    "ROUTE_FAILED",
    "ModeBPostAutobuild",
    "evaluate_post_autobuild",
]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Route literals
# ---------------------------------------------------------------------------


#: Route advancing the build to the constitutional ``PULL_REQUEST_REVIEW``
#: gate. The handler returns this when autobuild was approved AND reported
#: a non-empty diff. The actual PR creation does not happen here — only
#: the routing decision.
PR_REVIEW: str = "PR_REVIEW"

#: Route terminating the build as a successful no-op. Returned when
#: autobuild was approved AND reported zero changed files. The recorded
#: terminal kind is ``complete`` (the build *succeeded* by virtue of
#: having nothing to commit), and no PR-creation call site is reachable.
NO_OP: str = "NO_OP"

#: Route terminating the build as failed. Returned when the autobuild's
#: own terminal lifecycle was ``hard_stop`` or ``failed``. The
#: autobuild's rationale is surfaced onto the
#: :class:`ModeBPostAutobuild` so the session-outcome record carries it.
#:
#: Named ``ROUTE_FAILED`` (rather than ``FAILED``) to avoid colliding
#: with :data:`forge.pipeline.mode_b_planner.FAILED` which is a stage-
#: status literal — the two domains live in the same module surface area
#: for some callers and clashing names would invite import-time bugs.
ROUTE_FAILED: str = "FAILED"


#: Canonical rationale string for the ``NO_OP`` terminal outcome.
#:
#: Group M scenario "no-diff autobuild does not attempt pull-request
#: creation" expects this rationale verbatim on the recorded session
#: outcome — downstream alerting and dashboards regex-match against the
#: literal, so it must stay byte-for-byte stable.
NO_DIFF_RATIONALE: str = "mode-b-autobuild-no-diff"


#: Status strings recognised by this handler as terminal autobuild
#: lifecycles. Anything else (e.g. ``"running"``,
#: ``"awaiting_approval"``) is treated as "in flight, not ready for the
#: terminal handler" and the call is rejected with :class:`ValueError`.
_TERMINAL_AUTOBUILD_STATUSES: frozenset[str] = frozenset({APPROVED, HARD_STOP, FAILED})


# ---------------------------------------------------------------------------
# Return value
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ModeBPostAutobuild:
    """Decision returned by :func:`evaluate_post_autobuild`.

    Frozen so the routing decision cannot be mutated after the
    Supervisor has logged it. Slotted to keep instances cheap; the
    Supervisor produces one of these per AUTOBUILD terminal event and
    drops them straight into the build's terminal-state record.

    Attributes:
        route: One of :data:`PR_REVIEW`, :data:`NO_OP`, or
            :data:`ROUTE_FAILED`. The Supervisor's dispatch switch keys
            off this string; mutating it after construction would
            corrupt the routing decision.
        rationale: Human-readable explanation. For :data:`NO_OP`, this
            is :data:`NO_DIFF_RATIONALE` verbatim (Group M scenario);
            for :data:`ROUTE_FAILED`, it surfaces the autobuild's own
            hard-stop rationale (Group C); for :data:`PR_REVIEW`, it
            documents the routing decision (the constitutional gate
            owns the PR verdict, so this rationale is informational).
        feature_id: The feature whose autobuild this decision is for.
            Threaded onto the session-outcome record so per-feature
            terminal events can be correlated.
        changed_files_count: The integer read off the autobuild's
            stage-log row. ``None`` for the :data:`ROUTE_FAILED`
            branch (the autobuild did not reach a clean terminal so
            the field is not authoritative).
        session_outcome_payload: Mapping of fields the Supervisor will
            drop onto the build's recorded session outcome. Always
            includes ``"outcome"`` (one of ``"complete"`` or
            ``"failed"``) and ``"rationale"``. NEVER includes
            ``"pull_request_url"`` and never includes a
            ``"pr_review_gate_decision"`` for the :data:`NO_OP` branch
            (Group M acceptance — there is no PR, so no PR url).
    """

    route: str
    rationale: str
    feature_id: str | None
    changed_files_count: int | None
    session_outcome_payload: Mapping[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _latest_autobuild_entry(
    history: Sequence[StageEntry],
) -> StageEntry | None:
    """Return the chronologically last ``AUTOBUILD`` entry in ``history``.

    Mirrors :meth:`ModeBChainPlanner._latest_for_stage` so the handler
    and the planner agree on which row is "the" autobuild row when a
    build has retried autobuild and the history has multiple entries.
    Linear scan — the Mode B chain has at most a handful of autobuild
    entries per build.
    """
    latest: StageEntry | None = None
    for entry in history:
        if entry.stage is StageClass.AUTOBUILD:
            latest = entry
    return latest


def _coerce_changed_files_count(details: Mapping[str, Any]) -> int:
    """Read ``changed_files_count`` from ``details``, defaulting to 0.

    Defensive: callers may pass dicts whose ``changed_files_count`` is
    a string (e.g. round-tripped through JSON without typing) or
    missing entirely. The handler treats malformed / missing as
    ``0`` (the conservative no-diff default — see module docstring).
    A genuinely unparseable value is logged at WARNING and folded to
    ``0`` so a malformed row never advances to PR creation.
    """
    raw = details.get("changed_files_count")
    if raw is None:
        return 0
    if isinstance(raw, bool):
        # ``bool`` is a subclass of ``int`` — guard so ``True`` does
        # not silently become ``1`` and trigger an unintended PR.
        logger.warning(
            "terminal_handlers: changed_files_count was bool %r; "
            "coercing to 0 (defensive no-diff default)",
            raw,
        )
        return 0
    if isinstance(raw, int):
        return raw if raw >= 0 else 0
    try:
        coerced = int(raw)
    except (TypeError, ValueError):
        logger.warning(
            "terminal_handlers: changed_files_count not coercible to int "
            "(value=%r); folding to 0",
            raw,
        )
        return 0
    return coerced if coerced >= 0 else 0


def _failure_rationale(entry: StageEntry) -> str:
    """Build the FAILED-route rationale, surfacing the autobuild's own.

    Group C "internal hard-stop is propagated" requires the autobuild's
    own rationale (when present in ``details``) to flow through onto
    the session-outcome record. If the autobuild did not record one,
    we fall back to a generic message naming the status — operators
    still get a non-empty rationale to triage against.
    """
    autobuild_rationale = entry.details.get("rationale")
    if isinstance(autobuild_rationale, str) and autobuild_rationale:
        return f"mode-b-autobuild-{entry.status}: {autobuild_rationale}"
    return f"mode-b-autobuild-{entry.status}"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def evaluate_post_autobuild(
    build: Build,
    history: Sequence[StageEntry],
) -> ModeBPostAutobuild:
    """Decide post-autobuild routing for a Mode B build.

    Invoked by the Supervisor (TASK-MBC8-008) immediately after the
    AUTOBUILD stage reaches a terminal lifecycle. The returned
    :class:`ModeBPostAutobuild` carries:

    * The route label (:data:`PR_REVIEW`, :data:`NO_OP`, or
      :data:`ROUTE_FAILED`) — the Supervisor's dispatch switch keys
      off this.
    * A rationale — recorded onto the build's terminal-state row.
    * ``changed_files_count`` — surfaced for auditability.
    * A ``session_outcome_payload`` — the fields the Supervisor will
      drop onto the build's recorded :class:`SessionOutcome` (per
      AC-007: NO_OP carries no ``pull_request_url`` and no PR-review
      gate decision).

    Decision tree (in evaluation order):

    1. **Locate the autobuild entry.** Walk ``history`` for the
       chronologically last :attr:`StageClass.AUTOBUILD` row. If none
       exists, raise :class:`ValueError` — the handler is post-
       autobuild and must not be invoked otherwise.
    2. **Reject in-flight statuses.** The autobuild's status must be
       one of :data:`APPROVED`, :data:`HARD_STOP`, or :data:`FAILED`.
       Anything else (e.g. ``"running"``) is a programmer error and
       raises :class:`ValueError` rather than picking an arbitrary
       route.
    3. **Branch on terminal status.**

       * :data:`HARD_STOP` / :data:`FAILED` → :data:`ROUTE_FAILED`,
         with the autobuild's rationale surfaced onto the
         ``session_outcome_payload``.
       * :data:`APPROVED` with ``changed_files_count > 0`` →
         :data:`PR_REVIEW`. The ``session_outcome_payload`` is empty
         here — the constitutional gate has not yet fired and no
         terminal record is written by this branch.
       * :data:`APPROVED` with ``changed_files_count == 0`` (or
         missing) → :data:`NO_OP`, terminal ``complete``, rationale
         :data:`NO_DIFF_RATIONALE`. Group M acceptance: payload
         carries no ``pull_request_url`` and no PR-review gate
         decision.

    Args:
        build: The build value object. Only :attr:`Build.build_id` is
            consulted (for log lines); ``status`` and ``mode`` are
            accepted for parity with other planner / handler call
            sites.
        history: Recorded stage history for the build. May be empty —
            but only as a programmer error: the handler is post-
            autobuild and an empty history means the caller invoked it
            too early. Iteration order matters — the chronologically
            last AUTOBUILD entry wins.

    Returns:
        A :class:`ModeBPostAutobuild` carrying the route, rationale,
        ``feature_id``, ``changed_files_count``, and
        ``session_outcome_payload``.

    Raises:
        ValueError: If ``history`` contains no AUTOBUILD entry, or if
            the latest AUTOBUILD entry's status is not one of the
            three terminal statuses (:data:`APPROVED`,
            :data:`HARD_STOP`, :data:`FAILED`). The handler is post-
            autobuild — failing fast surfaces the programmer bug.

    Example:
        >>> from forge.lifecycle.modes import BuildMode
        >>> from forge.lifecycle.persistence import Build
        >>> from forge.pipeline.supervisor import BuildState
        >>> build = Build(
        ...     build_id="build-FEAT-X-20260427",
        ...     status=BuildState.RUNNING,
        ...     mode=BuildMode.MODE_B,
        ... )
        >>> # An approved autobuild that touched no files → NO_OP.
        >>> evaluate_post_autobuild(build, history).route  # doctest: +SKIP
        'NO_OP'
    """
    autobuild_entry = _latest_autobuild_entry(history)
    if autobuild_entry is None:
        raise ValueError(
            "evaluate_post_autobuild: no autobuild entry in history "
            f"(build_id={build.build_id!r}); the handler is post-autobuild "
            "and must not be invoked before AUTOBUILD reaches a terminal "
            "lifecycle"
        )

    status = autobuild_entry.status
    if status not in _TERMINAL_AUTOBUILD_STATUSES:
        raise ValueError(
            "evaluate_post_autobuild: latest autobuild entry has non-terminal "
            f"status {status!r} (build_id={build.build_id!r}); expected one "
            f"of {sorted(_TERMINAL_AUTOBUILD_STATUSES)!r}"
        )

    feature_id = autobuild_entry.feature_id

    # ------------------------------------------------------------------
    # Branch 1 — hard_stop / failed → ROUTE_FAILED
    # ------------------------------------------------------------------
    if status in (HARD_STOP, FAILED):
        rationale = _failure_rationale(autobuild_entry)
        logger.info(
            "terminal_handlers: mode-b post-autobuild route=FAILED "
            "build_id=%s feature_id=%s status=%s rationale=%s",
            build.build_id,
            feature_id,
            status,
            rationale,
        )
        return ModeBPostAutobuild(
            route=ROUTE_FAILED,
            rationale=rationale,
            feature_id=feature_id,
            changed_files_count=None,
            session_outcome_payload={
                "outcome": "failed",
                "rationale": rationale,
                "autobuild_status": status,
            },
        )

    # ------------------------------------------------------------------
    # Branch 2 — APPROVED → split on changed_files_count
    # ------------------------------------------------------------------
    changed = _coerce_changed_files_count(autobuild_entry.details)

    if changed > 0:
        rationale = (
            f"mode-b-autobuild approved with {changed} changed file(s); "
            "advancing to pull-request-review"
        )
        logger.info(
            "terminal_handlers: mode-b post-autobuild route=PR_REVIEW "
            "build_id=%s feature_id=%s changed_files_count=%d",
            build.build_id,
            feature_id,
            changed,
        )
        # PR_REVIEW does not write a session outcome — the
        # constitutional gate fires next and owns that record.
        return ModeBPostAutobuild(
            route=PR_REVIEW,
            rationale=rationale,
            feature_id=feature_id,
            changed_files_count=changed,
            session_outcome_payload={},
        )

    # changed == 0 → Group M no-diff terminal
    logger.info(
        "terminal_handlers: mode-b post-autobuild route=NO_OP "
        "build_id=%s feature_id=%s rationale=%s",
        build.build_id,
        feature_id,
        NO_DIFF_RATIONALE,
    )
    return ModeBPostAutobuild(
        route=NO_OP,
        rationale=NO_DIFF_RATIONALE,
        feature_id=feature_id,
        changed_files_count=0,
        session_outcome_payload={
            "outcome": "complete",
            "rationale": NO_DIFF_RATIONALE,
            # Explicitly NO ``pull_request_url`` key (Group M
            # acceptance) — and ``pr_review_gate_decision`` is
            # ``None`` so callers that ``.get()`` it see a clean
            # absence rather than a stale value.
            "pr_review_gate_decision": None,
        },
    )
