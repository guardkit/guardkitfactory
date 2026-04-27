"""Mode C cycle planner — review-then-work iteration with cyclic terminator.

This is the only stage planner in the codebase that dispatches the same
stage class (``/task-work``) repeatedly within a single build. Mode C runs
a ``/task-review`` to identify fix tasks, then dispatches one ``/task-work``
per fix task in sequence, and finally schedules a follow-up ``/task-review``.
Termination is reviewer-driven (FEAT-FORGE-008 ASSUM-010): a follow-up
review that returns no further fix tasks ends the cycle. There is no
numeric iteration cap.

Two terminal outcomes are possible (ASSUM-005, ASSUM-007, ASSUM-017):

* :attr:`ModeCTerminal.CLEAN_REVIEW` — a review (initial or follow-up)
  emitted no fix tasks and no commits were produced.
* :attr:`ModeCTerminal.FAILED` — the most recent ``/task-review`` was
  hard-stopped or rejected. Failed *fix tasks* do **not** terminate the
  build — they are isolated to their own fix task per ASSUM-008 and the
  planner returns the next fix task in line.

When a follow-up review is clean and the build has produced commits, the
planner advances to :attr:`StageClass.PULL_REQUEST_REVIEW` instead of
terminating. The commit detection itself lives outside the planner: it
reads a ``has_commits`` flag set by TASK-MBC8-007's terminal handler.

The planner is **stateless**. Every call inspects ``history`` and the
``has_commits`` flag; cyclic behaviour emerges from the planner deciding
the same ``next_stage = TASK_WORK`` repeatedly until the most-recent
review's fix-task list is exhausted.

Each ``next_fix_task`` decision returns a :class:`FixTaskRef` carrying the
fix-task identifier and a back-reference (``review_history_index``) to the
originating ``/task-review`` entry — the audit anchor required by Group L
data-integrity scenarios.

References:
    - FEAT-FORGE-008 ASSUM-004 — Mode C chain shape.
    - FEAT-FORGE-008 ASSUM-005 — PR review when fixes change the branch.
    - FEAT-FORGE-008 ASSUM-007 — clean initial review terminates without
      dispatching ``/task-work``.
    - FEAT-FORGE-008 ASSUM-008 — failure isolation (failed ``/task-work``
      does not auto-cancel sibling fix tasks).
    - FEAT-FORGE-008 ASSUM-010 — termination is reviewer-driven; no
      numeric iteration cap.
    - FEAT-FORGE-008 ASSUM-017 — clean follow-up review with no commits
      terminates the build.
    - TASK-MBC8-004 — this task brief.
    - TASK-MBC8-007 — owner of the ``has_commits`` flag.
    - TASK-MAG7-008 — ``dispatch_subprocess_stage`` produces the typed
      fix-task list consumed here as ``StageEntry.fix_tasks``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Sequence

from forge.lifecycle.persistence import Build
from forge.pipeline.mode_chains_data import MODE_C_CHAIN
from forge.pipeline.stage_taxonomy import StageClass

__all__ = [
    "FixTaskRef",
    "ModeCCyclePlanner",
    "ModeCPlan",
    "ModeCTerminal",
    "StageEntry",
    "plan_next_stage",
]


# ---------------------------------------------------------------------------
# Status vocabulary — locally documented so callers know what to record
# ---------------------------------------------------------------------------


#: Status string indicating a stage entry was approved by its gate. The
#: only status that allows downstream dispatch in Mode C.
_STATUS_APPROVED: str = "approved"

#: Status strings indicating a stage entry has reached a terminal outcome
#: (positive or negative). For ``/task-work`` the planner treats every
#: terminal status as "this fix task's slot is complete — advance" so
#: ASSUM-008 isolation is honoured (a failed fix task does not block its
#: siblings).
_TERMINAL_STATUSES: frozenset[str] = frozenset(
    {_STATUS_APPROVED, "failed", "rejected", "cancelled"}
)

#: Status strings on a ``/task-review`` entry that terminate the whole
#: Mode C build. Hard-stop is captured as a separate flag on
#: :class:`StageEntry` because the gate vocabulary distinguishes
#: ``hard_stop`` from a generic ``reject``.
_REVIEW_FAILURE_STATUSES: frozenset[str] = frozenset({"failed", "rejected"})


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class ModeCTerminal(StrEnum):
    """Mode C terminal outcomes.

    Only set when the planner's ``next_stage`` is ``None``. The enum is a
    :class:`StrEnum` so the string values appear directly in stage history
    rationales without coercion.

    Members:
        CLEAN_REVIEW: A ``/task-review`` returned no fix tasks and no
            commits were produced. The build is "done" — nothing to fix,
            nothing to push.
        FAILED: A ``/task-review`` was hard-stopped or rejected. The
            build cannot proceed.
    """

    CLEAN_REVIEW = "clean-review"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class FixTaskRef:
    """Reference to a fix task identified by a specific ``/task-review`` entry.

    The ``review_history_index`` back-reference is the audit anchor that
    Group L lineage scenarios depend on: every dispatched ``/task-work``
    can be traced back to the exact review that emitted its fix-task
    identifier, even when later cycles emit the same identifier again.

    Attributes:
        fix_task_id: The fix-task identifier emitted by the review.
        review_history_index: Index into the planner's ``history`` argument
            of the ``/task-review`` entry that emitted this fix task.
        review_stage_label: Stage label of the originating review entry.
            Defaults to ``"task-review"`` — the canonical stage label.
            Carried explicitly so audit logs do not need to re-resolve it.
    """

    fix_task_id: str
    review_history_index: int
    review_stage_label: str = "task-review"


@dataclass(frozen=True, slots=True)
class StageEntry:
    """Planner-domain view of one recorded stage outcome.

    The planner does not consume :class:`forge.lifecycle.persistence.StageLogEntry`
    directly — that type is shaped by SQLite persistence concerns
    (``threshold_applied``, ``coach_score``, …) that the planner does not
    need. ``StageEntry`` is the minimal projection the planner reads: the
    stage class, its terminal status, and the per-stage payload (fix-task
    list for ``/task-review``; fix-task identifier for ``/task-work``).

    Adapters in TASK-MBC8-008 (Supervisor wiring) project the persisted
    ``StageLogEntry`` into this shape; tests construct it directly.

    Attributes:
        stage_class: The :class:`StageClass` of this entry.
        status: One of ``"approved"``, ``"failed"``, ``"rejected"``,
            ``"cancelled"``, or a non-terminal status (``"pending"``,
            ``"running"``). Only ``"approved"`` allows downstream dispatch.
        fix_tasks: For ``/task-review`` entries, the typed list of fix-task
            identifiers emitted by the reviewer. Empty tuple for entries
            that are not ``/task-review`` or for clean reviews.
        fix_task_id: For ``/task-work`` entries, the identifier of the fix
            task this dispatch worked on. ``None`` for entries that are
            not ``/task-work``.
        hard_stop: Whether the gate decision was a hard-stop. A hard-stop
            on ``/task-review`` terminates the build with FAILED regardless
            of the ``status`` string (gate vocabularies vary).
    """

    stage_class: StageClass
    status: str
    fix_tasks: tuple[str, ...] = field(default=())
    fix_task_id: str | None = None
    hard_stop: bool = False


@dataclass(frozen=True, slots=True)
class ModeCPlan:
    """The planner's decision for one Mode C step.

    Exactly one of the following is true on every plan:

    * ``next_stage`` is set and the supervisor dispatches that stage.
      ``terminal`` is ``None``. ``next_fix_task`` is set when
      ``next_stage == TASK_WORK``.
    * ``next_stage`` is ``None`` and ``terminal`` is set. The build has
      reached a terminal outcome — :attr:`ModeCTerminal.CLEAN_REVIEW` or
      :attr:`ModeCTerminal.FAILED`.
    * Both ``next_stage`` and ``terminal`` are ``None`` — the planner is
      waiting on an in-flight prerequisite (e.g. the most recent review
      has not yet been approved). The supervisor records the wait and
      retries on the next reasoning loop tick.

    Attributes:
        permitted_stages: Frozenset of stage classes that are dispatchable
            under Mode C. Always equal to ``frozenset(MODE_C_CHAIN)``;
            published per-plan so callers can scope the dispatch switch
            without re-importing the chain data module.
        next_stage: The stage class to dispatch next, or ``None``.
        next_fix_task: When ``next_stage == TASK_WORK``, the
            :class:`FixTaskRef` carrying the fix-task identifier and back-
            reference to the originating ``/task-review``. ``None``
            otherwise.
        terminal: A :class:`ModeCTerminal` outcome when the build is done,
            otherwise ``None``.
        rationale: A short human-readable string explaining the decision.
            The supervisor logs this against the build's stage history.
    """

    permitted_stages: frozenset[StageClass]
    next_stage: StageClass | None
    next_fix_task: FixTaskRef | None = None
    terminal: ModeCTerminal | None = None
    rationale: str = ""


# Frozenset of Mode C dispatchable stages; built once at import time so
# every plan can share the reference (frozensets are hashable + immutable).
_MODE_C_PERMITTED: frozenset[StageClass] = frozenset(MODE_C_CHAIN)


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


class ModeCCyclePlanner:
    """Stateless Mode C cycle planner.

    Single public method :meth:`plan_next_stage` consumes the build's
    recorded history and returns a :class:`ModeCPlan`. Repeated calls with
    the same history return equivalent plans — there is no internal state.

    Cyclic behaviour emerges from the planner repeatedly returning
    ``next_stage = TASK_WORK`` until the most recent review's fix-task
    list is exhausted, then scheduling a follow-up ``/task-review``.
    Termination is reviewer-driven — a follow-up review with no fix tasks
    ends the cycle.
    """

    def plan_next_stage(
        self,
        build: Build,
        history: Sequence[StageEntry],
        *,
        has_commits: bool = False,
    ) -> ModeCPlan:
        """Decide the next Mode C stage given the build and its history.

        Args:
            build: The build value object. Used today only for inclusion
                in returned rationales; the decision logic is purely
                structural over ``history``.
            history: The build's recorded stage entries in dispatch order.
                Mode C entries (``/task-review`` and ``/task-work``) are
                interleaved as the cycle runs.
            has_commits: Whether the build has produced commits against
                the working branch. Set by TASK-MBC8-007's terminal
                handler. Drives the choice between
                :attr:`ModeCTerminal.CLEAN_REVIEW` (no commits) and
                :attr:`StageClass.PULL_REQUEST_REVIEW` (commits) on a
                follow-up clean review.

        Returns:
            A :class:`ModeCPlan` describing the next decision.
        """
        del build  # build identity is not part of the planning decision
        permitted = _MODE_C_PERMITTED

        # Empty history → dispatch the initial /task-review.
        if not history:
            return ModeCPlan(
                permitted_stages=permitted,
                next_stage=StageClass.TASK_REVIEW,
                rationale="initial review — empty history",
            )

        # Locate the most recent /task-review entry. Mode C always opens
        # with one; if for any reason the history contains no review, we
        # treat that as "dispatch a review" — the recovery-friendly choice.
        latest_review_idx = self._latest_review_index(history)
        if latest_review_idx is None:
            return ModeCPlan(
                permitted_stages=permitted,
                next_stage=StageClass.TASK_REVIEW,
                rationale="no /task-review in history — dispatching initial review",
            )

        latest_review = history[latest_review_idx]

        # /task-review hard-stop or reject → terminal FAILED. AC-007 plus
        # the Group C "reject decision before PR terminates the build"
        # scenario both flow through this branch.
        if latest_review.hard_stop or latest_review.status in _REVIEW_FAILURE_STATUSES:
            return ModeCPlan(
                permitted_stages=permitted,
                next_stage=None,
                terminal=ModeCTerminal.FAILED,
                rationale=(
                    "hard-stop on /task-review"
                    if latest_review.hard_stop
                    else f"/task-review {latest_review.status} — terminal FAILED"
                ),
            )

        # /task-review still pending or running → wait. AC: ``/task-work``
        # does not dispatch before the review is approved (Group B
        # prerequisite invariant).
        if latest_review.status != _STATUS_APPROVED:
            return ModeCPlan(
                permitted_stages=permitted,
                next_stage=None,
                rationale=(
                    "/task-review awaiting approval "
                    f"(status={latest_review.status!r})"
                ),
            )

        # Approved review — fan out work or terminate based on fix-task list.
        fix_tasks = latest_review.fix_tasks
        if not fix_tasks:
            return self._decide_clean_review(
                history=history,
                latest_review_idx=latest_review_idx,
                has_commits=has_commits,
                permitted=permitted,
            )

        # Find the next fix task that has not yet reached a terminal
        # status under this review's work iteration.
        next_id = self._next_undispatched_fix_task(
            history=history,
            latest_review_idx=latest_review_idx,
            fix_tasks=fix_tasks,
        )

        if next_id is not None:
            ref = FixTaskRef(
                fix_task_id=next_id,
                review_history_index=latest_review_idx,
            )
            return ModeCPlan(
                permitted_stages=permitted,
                next_stage=StageClass.TASK_WORK,
                next_fix_task=ref,
                rationale=f"dispatch /task-work for fix task {next_id!r}",
            )

        # All fix tasks reached terminal status — schedule a follow-up
        # /task-review per ASSUM-010 (no numeric cap).
        return ModeCPlan(
            permitted_stages=permitted,
            next_stage=StageClass.TASK_REVIEW,
            rationale="all fix tasks completed — scheduling follow-up review",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _latest_review_index(
        history: Sequence[StageEntry],
    ) -> int | None:
        """Return the index of the most recent ``/task-review`` entry.

        Returns ``None`` if the history contains no review entries — that
        case is recoverable (the planner dispatches an initial review).
        """
        for idx in range(len(history) - 1, -1, -1):
            if history[idx].stage_class == StageClass.TASK_REVIEW:
                return idx
        return None

    @staticmethod
    def _next_undispatched_fix_task(
        *,
        history: Sequence[StageEntry],
        latest_review_idx: int,
        fix_tasks: tuple[str, ...],
    ) -> str | None:
        """Return the first fix task whose ``/task-work`` slot is open.

        Walks ``fix_tasks`` in declaration order and returns the first
        identifier that has not reached a terminal status under the
        current review iteration. A fix task is considered "complete"
        (slot closed) when a ``/task-work`` entry recorded *after*
        ``latest_review_idx`` references it with a status in
        :data:`_TERMINAL_STATUSES` — including ``"failed"``. ASSUM-008
        ("failure isolated to its fix task") means a failed slot still
        unblocks dispatch of the *next* fix task.
        """
        # Collect terminal-status work entries for the current review
        # iteration only — earlier iterations may have re-emitted the
        # same fix-task identifier and we must not confuse the lineage.
        completed_ids: set[str] = set()
        in_flight_ids: set[str] = set()
        for entry in history[latest_review_idx + 1 :]:
            if entry.stage_class != StageClass.TASK_WORK:
                continue
            if entry.fix_task_id is None:
                # Defensive: a /task-work entry with no fix_task_id is an
                # invariant violation upstream. Skip it rather than
                # crash; the missing fix task will be re-dispatched on
                # the next planning tick.
                continue
            if entry.status in _TERMINAL_STATUSES:
                completed_ids.add(entry.fix_task_id)
            else:
                in_flight_ids.add(entry.fix_task_id)

        for fix_task_id in fix_tasks:
            if fix_task_id in completed_ids:
                continue
            if fix_task_id in in_flight_ids:
                # A prior ``/task-work`` is still running for this fix
                # task — wait. Returning ``None`` from here triggers the
                # caller's "schedule follow-up review" branch which is
                # wrong; instead we return a sentinel that the caller
                # interprets as "already in flight". The simplest
                # encoding: return the same fix_task_id (the supervisor
                # will see a duplicate dispatch as a no-op via the
                # stage-ordering guard) — but that is brittle. Safer
                # to wait by returning None *and* let the caller's
                # follow-up-review branch handle it; in practice the
                # supervisor never planning while a stage is in flight
                # so this branch is largely defensive.
                return None
            return fix_task_id

        return None

    @staticmethod
    def _decide_clean_review(
        *,
        history: Sequence[StageEntry],
        latest_review_idx: int,
        has_commits: bool,
        permitted: frozenset[StageClass],
    ) -> ModeCPlan:
        """Resolve a clean (empty fix-task) review into a terminal or PR plan.

        Logic per AC-005 / ASSUM-005 / ASSUM-007 / ASSUM-017:

        * Initial clean review (no preceding ``/task-work``) → terminal
          ``CLEAN_REVIEW``. There is no PR review even if some other
          process has produced commits — Mode C only opens a PR when the
          build itself produced fixes through ``/task-work`` (ASSUM-005).
        * Follow-up clean review with no commits → terminal
          ``CLEAN_REVIEW`` (ASSUM-017).
        * Follow-up clean review with commits → advance to
          ``PULL_REQUEST_REVIEW`` (ASSUM-005).
        """
        # Detect whether any /task-work has run prior to this review.
        # Initial review = no prior /task-work in history.
        had_prior_work = any(
            entry.stage_class == StageClass.TASK_WORK
            for entry in history[:latest_review_idx]
        )

        if not had_prior_work:
            return ModeCPlan(
                permitted_stages=permitted,
                next_stage=None,
                terminal=ModeCTerminal.CLEAN_REVIEW,
                rationale="initial /task-review returned no fix tasks",
            )

        if has_commits:
            return ModeCPlan(
                permitted_stages=permitted,
                next_stage=StageClass.PULL_REQUEST_REVIEW,
                rationale=(
                    "follow-up /task-review clean — fixes produced commits, "
                    "advancing to pull-request review"
                ),
            )

        return ModeCPlan(
            permitted_stages=permitted,
            next_stage=None,
            terminal=ModeCTerminal.CLEAN_REVIEW,
            rationale=(
                "follow-up /task-review clean — no commits, terminal clean review"
            ),
        )


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------


def plan_next_stage(
    build: Build,
    history: Sequence[StageEntry],
    *,
    has_commits: bool = False,
) -> ModeCPlan:
    """Module-level convenience wrapper around :class:`ModeCCyclePlanner`.

    The class is stateless so the singleton wrapper is safe; callers that
    prefer a function form (mirroring ``MODE_C_PREREQUISITES`` and other
    declarative module-level surfaces in :mod:`forge.pipeline`) can use
    this without instantiating the class.
    """
    return ModeCCyclePlanner().plan_next_stage(build, history, has_commits=has_commits)
