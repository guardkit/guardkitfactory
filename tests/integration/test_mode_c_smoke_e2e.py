"""End-to-end smoke test for FEAT-FORGE-008 Mode C pipeline (TASK-MBC8-011).

Drives Mode C builds through the three terminal shapes and asserts the
stage-history, attribution, lineage, failure-isolation, hard-stop, and
cycle-termination invariants documented in TASK-MBC8-011.

Terminal shapes covered (per the AC):

1. **Empty initial review** — ``/task-review`` returns zero fix tasks; no
   ``/task-work`` is dispatched; the build reaches the ``complete``
   terminal state with the ``clean-review`` rationale; no PR URL.
   (FEAT-FORGE-008 ASSUM-007 / Group B scenario.)
2. **N fix tasks → no commits** — three fix tasks are dispatched and
   approved; the worktree commit count is zero; the build reaches the
   ``complete`` terminal state with the ``clean-review`` rationale; no
   PR URL. (FEAT-FORGE-008 ASSUM-017 / Group N scenario.)
3. **N fix tasks → commits** — three fix tasks are dispatched and
   approved; the worktree carries one or more commits; the build pauses
   at ``pull-request-review`` with ``MANDATORY_HUMAN_APPROVAL`` (Mode C's
   constitutional gate, ASSUM-005 / Group A key-example).

Stage-history invariants asserted (TASK-MBC8-011 AC):

* ``/task-review`` precedes every ``/task-work`` it produced (Group G
  ordering invariant).
* Each ``/task-work`` references **exactly one** fix-task identifier
  (Group B "every dispatched task-work should reference exactly one
  fix task identifier").
* Per-fix-task artefact paths attribute only to the producing fix
  task (Group G "no artefact path attributed to more than one fix
  task").
* Each ``/task-work`` carries ``originating_review_entry_id`` pointing
  to the ``/task-review`` that emitted its fix-task identifier
  (Group L lineage).

Plus three behavioural assertions:

* **Failure isolation** (ASSUM-008): one fix task's ``/task-work``
  returns failed; sibling fix tasks still get dispatched; the failure
  is recorded against itself, not against the cycle.
* **Hard-stop**: ``/task-review`` returns a hard-stop result; no
  ``/task-work`` is dispatched; the build reaches the ``failed``
  terminal state (Group C).
* **Cycle termination** (ASSUM-010): after N fix tasks complete, a
  follow-up ``/task-review`` returns no further fix tasks; no further
  ``/task-work`` is dispatched; the cycle terminates with the
  appropriate clean or PR terminal.

Harness shape
-------------

The :func:`mode_c_smoke_pipeline` fixture wires the production
:class:`forge.pipeline.supervisor.Supervisor` against in-memory fakes
that satisfy every Protocol the supervisor depends on. Real substrate
adapters (FEAT-FORGE-001 SQLite, FEAT-FORGE-005 git probe) are mocked
at their Protocol boundaries; only the FEAT-FORGE-008 net-new code (the
Mode C planner, terminal handler, and supervisor wiring from
TASK-MBC8-008) runs for real.

The harness owns:

* :class:`FakeModeCStageLog` — composite in-memory backing for the Mode
  C history reader, ordering reader, and turn recorder. Tracks
  ``stage_log`` rows with ``entry_id`` / ``originating_review_entry_id``
  for the lineage assertion.
* :class:`PlannedSubprocessDispatcher` — returns canned outcomes per
  scripted scenario (review with N fix tasks, work with optional
  failure injection). Records artefact paths per fix task so the
  attribution invariant is checkable.
* :class:`FakePRReviewGate` — submission is the build's terminal pause
  with ``MANDATORY_HUMAN_APPROVAL`` gate mode.
* :class:`FakeCommitProbe` — returns an injectable commit count so the
  no-commits / commits-present split is deterministic without a real
  worktree.

Driver
------

:meth:`ModeCSmokePipeline.drive_until_terminal` runs ``next_turn``
iteratively, absorbing each dispatcher's outcome into the history
between turns:

* ``/task-review`` + ``status=approved`` → append a review row carrying
  the canned fix-task list, then continue.
* ``/task-work`` + ``status=approved|failed`` → append a work row
  attributed to the fix-task ref, then continue.
* PR-review submission → annotate the row with ``gate_mode`` +
  ``pull_request_url`` and stop — the build is paused at PR review.
* ``TERMINAL`` outcome → stop — the build has reached a clean / failed
  terminal.

References
----------

* FEAT-FORGE-008 ``features/mode-b-feature-and-mode-c-review-fix``
  Group A / B / C / G / L / N scenarios.
* TASK-MBC8-004 — :class:`forge.pipeline.mode_c_planner.ModeCCyclePlanner`.
* TASK-MBC8-007 — :func:`forge.pipeline.terminal_handlers.mode_c.evaluate_terminal`.
* TASK-MBC8-008 — :meth:`forge.pipeline.supervisor.Supervisor.next_turn`
  Mode C wiring.
* TASK-MBC8-011 — this task brief.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

import pytest

from forge.lifecycle.modes import BuildMode
from forge.pipeline import FakeClock
from forge.pipeline.constitutional_guard import ConstitutionalGuard
from forge.pipeline.mode_c_planner import (
    FixTaskRef,
    ModeCCyclePlanner,
    StageEntry as ModeCStageEntry,
)
from forge.pipeline.per_feature_sequencer import PerFeatureLoopSequencer
from forge.pipeline.stage_ordering_guard import StageOrderingGuard
from forge.pipeline.stage_taxonomy import StageClass
from forge.pipeline.supervisor import (
    BuildState,
    Supervisor,
    TurnOutcome,
    TurnReport,
)
from forge.pipeline.terminal_handlers.mode_c import (
    CommitProbeResult,
    build_task_work_attribution,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


SMOKE_BUILD_ID: str = "build-MBC8-20260427120000"

#: ``MANDATORY_HUMAN_APPROVAL`` is the canonical gate-mode literal Mode C
#: emits when the constitutional PR-review gate is triggered. Recorded on
#: the chronology row by the harness so the AC assertion ("PR URL +
#: mandatory_human gate mode") is local to the chronology log rather
#: than to the gate's internal payload shape.
MANDATORY_HUMAN_APPROVAL: str = "MANDATORY_HUMAN_APPROVAL"


# ---------------------------------------------------------------------------
# Scripted dispatch outcomes — one canned outcome per dispatcher call
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReviewOutcome:
    """Canned ``/task-review`` outcome.

    Attributes:
        fix_tasks: The fix-task identifiers the review emits (empty
            tuple → clean review).
        status: ``"approved"`` (the only status that allows downstream
            dispatch) or ``"failed"`` / ``"rejected"`` for the
            review-failure branch.
        hard_stop: Whether the review hard-stops the build. Drives the
            terminal handler's FAILED path independently of ``status``.
    """

    fix_tasks: tuple[str, ...] = ()
    status: str = "approved"
    hard_stop: bool = False


@dataclass(frozen=True, slots=True)
class WorkOutcome:
    """Canned ``/task-work`` outcome.

    Attributes:
        status: ``"approved"`` (success) or ``"failed"`` (ASSUM-008
            failure-isolation path).
        artefact_paths: Per-dispatch artefact paths the harness will
            attribute to the dispatched fix task.
    """

    status: str = "approved"
    artefact_paths: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# In-memory stage_log — composite history + ordering + turn recorder
# ---------------------------------------------------------------------------


@dataclass
class StageLogRow:
    """One persisted ``stage_log`` row in the harness.

    Mirrors the production row shape that matters for the AC: the
    ``entry_id`` is the audit anchor referenced from later rows;
    ``details`` carries ``fix_task_id`` / ``originating_review_entry_id``
    / ``artefact_paths`` for ``/task-work`` rows.
    """

    entry_id: str
    stage_class: StageClass
    status: str
    fix_tasks: tuple[str, ...] = ()
    fix_task_id: str | None = None
    hard_stop: bool = False
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class FakeModeCStageLog:
    """Composite stage_log — history + ordering + turn-recorder surfaces.

    The supervisor consults this object through three Protocols. Tests
    mutate ``rows`` and ``commits`` directly between turns to mimic the
    real adapters writing back after a successful dispatch.
    """

    rows: list[StageLogRow] = field(default_factory=list)
    commits_by_build: dict[str, bool] = field(default_factory=dict)
    chronology: list[dict[str, Any]] = field(default_factory=list)
    approved_marks: set[tuple[str, StageClass, str | None]] = field(default_factory=set)
    catalogues: dict[str, list[str]] = field(default_factory=dict)
    _next_entry_seq: int = 0

    # ------------------------------------------------------------------
    # Mode C history reader Protocol
    # ------------------------------------------------------------------

    def get_mode_c_history(self, build_id: str) -> Sequence[ModeCStageEntry]:
        del build_id  # single-build harness; rows are scoped to one build
        return [
            ModeCStageEntry(
                stage_class=row.stage_class,
                status=row.status,
                fix_tasks=row.fix_tasks,
                fix_task_id=row.fix_task_id,
                hard_stop=row.hard_stop,
            )
            for row in self.rows
        ]

    def has_commits(self, build_id: str) -> bool:
        return self.commits_by_build.get(build_id, False)

    # ------------------------------------------------------------------
    # Stage-ordering reader Protocol
    # ------------------------------------------------------------------

    def is_approved(
        self,
        build_id: str,
        stage: StageClass,
        feature_id: str | None = None,
    ) -> bool:
        return (build_id, stage, feature_id) in self.approved_marks

    def feature_catalogue(self, build_id: str) -> list[str]:
        return list(self.catalogues.get(build_id, []))

    # ------------------------------------------------------------------
    # Turn-recorder Protocol
    # ------------------------------------------------------------------

    def record_turn(
        self,
        *,
        build_id: str,
        outcome: TurnOutcome,
        permitted_stages: frozenset[StageClass],
        chosen_stage: StageClass | None,
        chosen_feature_id: str | None,
        rationale: str,
        gate_verdict: str | None,
    ) -> None:
        self.chronology.append(
            {
                "build_id": build_id,
                "outcome": outcome,
                "permitted_stages": frozenset(permitted_stages),
                "chosen_stage": chosen_stage,
                "chosen_feature_id": chosen_feature_id,
                "rationale": rationale,
                "gate_verdict": gate_verdict,
                # Smoke-test annotations populated by the driver after
                # absorbing the dispatcher outcome.
                "gate_mode": None,
                "pull_request_url": None,
            }
        )

    # ------------------------------------------------------------------
    # Driver-side mutators
    # ------------------------------------------------------------------

    def _allocate_entry_id(self, prefix: str) -> str:
        self._next_entry_seq += 1
        return f"{prefix}-{self._next_entry_seq:03d}"

    def append_review(
        self,
        *,
        build_id: str,
        outcome: ReviewOutcome,
    ) -> StageLogRow:
        row = StageLogRow(
            entry_id=self._allocate_entry_id("review"),
            stage_class=StageClass.TASK_REVIEW,
            status=outcome.status,
            fix_tasks=outcome.fix_tasks,
            hard_stop=outcome.hard_stop,
        )
        self.rows.append(row)
        if outcome.status == "approved" and not outcome.hard_stop:
            self.approved_marks.add((build_id, StageClass.TASK_REVIEW, None))
        return row

    def append_work(
        self,
        *,
        build_id: str,
        fix_task: FixTaskRef,
        outcome: WorkOutcome,
        originating_review_entry_id: str,
    ) -> StageLogRow:
        details = build_task_work_attribution(
            fix_task_id=fix_task.fix_task_id,
            originating_review_entry_id=originating_review_entry_id,
            artefact_paths=outcome.artefact_paths,
        )
        row = StageLogRow(
            entry_id=self._allocate_entry_id("work"),
            stage_class=StageClass.TASK_WORK,
            status=outcome.status,
            fix_task_id=fix_task.fix_task_id,
            details=details,
        )
        self.rows.append(row)
        # Mark the work approved so the supervisor's belt-and-braces
        # ordering check unlocks the next planner pick on the next
        # iteration. ASSUM-008: a *failed* work row also unblocks the
        # next fix task — the planner checks terminal status, not
        # success.
        if outcome.status in ("approved", "failed"):
            self.approved_marks.add((build_id, StageClass.TASK_WORK, None))
        return row

    @property
    def review_rows(self) -> list[StageLogRow]:
        return [r for r in self.rows if r.stage_class is StageClass.TASK_REVIEW]

    @property
    def work_rows(self) -> list[StageLogRow]:
        return [r for r in self.rows if r.stage_class is StageClass.TASK_WORK]


# ---------------------------------------------------------------------------
# State-machine reader (always RUNNING in the harness)
# ---------------------------------------------------------------------------


@dataclass
class FakeStateReader:
    states: dict[str, BuildState] = field(default_factory=dict)

    def get_build_state(self, build_id: str) -> BuildState:
        return self.states.get(build_id, BuildState.RUNNING)


@dataclass
class FakeAsyncTaskReader:
    """Empty ``async_tasks`` channel — Mode C never schedules an autobuild."""

    states_by_build: dict[str, list[Any]] = field(default_factory=dict)

    def list_autobuild_states(self, build_id: str) -> Iterable[Any]:
        return list(self.states_by_build.get(build_id, []))


@dataclass
class FakeBuildModeReader:
    """Mode reader pinned to MODE_C for every build the smoke drives."""

    modes: dict[str, BuildMode] = field(default_factory=dict)

    def get_build_mode(self, build_id: str) -> BuildMode:
        return self.modes.get(build_id, BuildMode.MODE_C)


# ---------------------------------------------------------------------------
# Reasoning model — Mode C does not consult it but the supervisor still
# requires the field; this stub satisfies the Protocol.
# ---------------------------------------------------------------------------


@dataclass
class _UnusedReasoningModel:
    """Stub reasoning model — Mode C goes through the cycle planner."""

    def choose_dispatch(
        self,
        *,
        build_id: str,
        build_state: BuildState,
        permitted_stages: frozenset[StageClass],
        stage_hints: Mapping[StageClass, str],
        feature_catalogue: tuple[str, ...],
    ) -> None:
        # Mode C never reaches the reasoning model — it is gated out at
        # ``next_turn`` step 1a. Returning None is the safe default.
        return None


# ---------------------------------------------------------------------------
# Subprocess dispatcher — scripted per stage class with optional injection
# ---------------------------------------------------------------------------


@dataclass
class PlannedSubprocessDispatcher:
    """Dispatcher that returns scripted outcomes for review / work calls.

    The dispatcher pops the next outcome from the queue matching the
    requested stage. Each call also records the fix-task ref (when
    ``stage == TASK_WORK``) so tests can assert the canary AC: every
    ``/task-work`` references exactly one fix-task identifier.
    """

    review_outcomes: list[ReviewOutcome] = field(default_factory=list)
    work_outcomes_by_fix_task: dict[str, WorkOutcome] = field(default_factory=dict)
    default_work_outcome: WorkOutcome = field(
        default_factory=lambda: WorkOutcome(status="approved")
    )
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def __call__(
        self,
        *,
        stage: StageClass,
        build_id: str,
        feature_id: str | None,
        rationale: str,
        fix_task: FixTaskRef | None = None,
        forward_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        call = {
            "stage": stage,
            "build_id": build_id,
            "feature_id": feature_id,
            "rationale": rationale,
            "fix_task": fix_task,
            "forward_context": dict(forward_context) if forward_context else None,
        }
        self.calls.append(call)
        if stage is StageClass.TASK_REVIEW:
            if not self.review_outcomes:
                raise AssertionError(
                    "PlannedSubprocessDispatcher: ran out of scripted "
                    "review outcomes — the planner asked for another "
                    "/task-review beyond what the test scripted"
                )
            review = self.review_outcomes.pop(0)
            return {
                "stage": stage,
                "status": review.status,
                "fix_tasks": list(review.fix_tasks),
                "hard_stop": review.hard_stop,
                "rationale": rationale,
            }
        if stage is StageClass.TASK_WORK:
            if fix_task is None:
                raise AssertionError(
                    "PlannedSubprocessDispatcher: TASK_WORK called "
                    "without a fix_task ref — supervisor wiring is "
                    "broken (Group B canary)"
                )
            outcome = self.work_outcomes_by_fix_task.get(
                fix_task.fix_task_id, self.default_work_outcome
            )
            return {
                "stage": stage,
                "status": outcome.status,
                "fix_task_id": fix_task.fix_task_id,
                "artefact_paths": list(outcome.artefact_paths),
                "rationale": rationale,
            }
        raise AssertionError(
            f"PlannedSubprocessDispatcher: unexpected stage={stage!r}; "
            "Mode C only dispatches TASK_REVIEW / TASK_WORK"
        )


# ---------------------------------------------------------------------------
# PR-review gate stub — submission is the terminal pause
# ---------------------------------------------------------------------------


@dataclass
class FakePRReviewGate:
    """PR-review gate stub returning a ``mandatory_human`` decision.

    Mode C calls ``submit_decision`` with ``auto_approve=False`` so the
    constitutional guard's ``veto_auto_approve`` is implicitly honoured
    — the gate's response carries the ``MANDATORY_HUMAN_APPROVAL`` mode
    flag and a synthetic PR URL recorded on the chronology.
    """

    submissions: list[dict[str, Any]] = field(default_factory=list)
    pr_url_template: str = "https://github.com/example/forge/pull/{number}"
    _next_pr_number: int = 700

    def submit_decision(
        self,
        *,
        build_id: str,
        feature_id: str,
        auto_approve: bool,
        rationale: str,
    ) -> dict[str, Any]:
        self._next_pr_number += 1
        pr_url = self.pr_url_template.format(number=self._next_pr_number)
        record = {
            "build_id": build_id,
            "feature_id": feature_id,
            "auto_approve": auto_approve,
            "rationale": rationale,
            "gate_mode": MANDATORY_HUMAN_APPROVAL,
            "pull_request_url": pr_url,
        }
        self.submissions.append(record)
        return record


# ---------------------------------------------------------------------------
# Commit probe — deterministic count
# ---------------------------------------------------------------------------


@dataclass
class FakeCommitProbe:
    """Async commit probe returning a deterministic count.

    Mirrors the production probe's contract (FEAT-FORGE-005 worktree
    allowlist) without ever shelling out. Tests mutate ``count`` between
    fixture setup and ``drive_until_terminal`` to script the
    no-commits / commits-present split.
    """

    count: int = 0
    failed: bool = False
    error: str | None = None
    calls: list[Any] = field(default_factory=list)

    async def __call__(self, build: Any) -> CommitProbeResult:
        self.calls.append(build)
        return CommitProbeResult(count=self.count, failed=self.failed, error=self.error)


# ---------------------------------------------------------------------------
# Subprocess-dispatcher → stage_log absorption helper
# ---------------------------------------------------------------------------


@dataclass
class ModeCSmokePipeline:
    """Composite in-memory harness for the Mode C smoke E2E suite.

    Owns every fake collaborator the supervisor consumes plus a small
    driver loop (:meth:`drive_until_terminal`) that runs supervisor
    turns until the build either reaches a TERMINAL outcome or pauses
    at PR review. All collaborators are exposed as attributes so tests
    can assert against call records, chronology rows, and PR URLs
    without re-resolving fixture handles.
    """

    supervisor: Supervisor
    stage_log: FakeModeCStageLog
    state_machine: FakeStateReader
    mode_reader: FakeBuildModeReader
    subprocess_dispatcher: PlannedSubprocessDispatcher
    pr_review_gate: FakePRReviewGate
    commit_probe: FakeCommitProbe
    clock: FakeClock
    captured_fix_tasks: list[dict[str, Any]] = field(default_factory=list)

    # Cap on supervisor turns. Each cycle iteration is one /task-review
    # plus N /task-work dispatches plus one terminal evaluation; 32
    # leaves ample headroom for the 3-fix-task scenarios while still
    # surfacing a runaway loop loud and early.
    MAX_TURNS: int = 32

    async def drive_until_terminal(
        self, *, build_id: str = SMOKE_BUILD_ID
    ) -> TurnReport:
        """Run ``next_turn`` until terminal / PR-review pause.

        Each turn:

        * Calls :meth:`Supervisor.next_turn` for ``build_id``.
        * Absorbs the dispatcher result into :attr:`stage_log` so the
          next planner tick sees the row.
        * Stops on TERMINAL or on the PR-review dispatch.

        Args:
            build_id: Build identifier to drive.

        Returns:
            The final :class:`TurnReport`.

        Raises:
            RuntimeError: ``MAX_TURNS`` exceeded without a terminal —
                surfaces a runaway loop rather than silently truncating
                the chronology.
        """
        last_report: TurnReport | None = None
        for _ in range(self.MAX_TURNS):
            report = await self.supervisor.next_turn(build_id)
            last_report = report
            self._absorb(build_id=build_id, report=report)
            if self._is_paused_or_terminal(report):
                return report
        raise RuntimeError(
            f"smoke harness exceeded MAX_TURNS={self.MAX_TURNS} without "
            f"reaching a paused / terminal state; "
            f"chronology={len(self.stage_log.chronology)} rows; "
            f"last_outcome={last_report.outcome.value if last_report else None!r}"
        )

    # ------------------------------------------------------------------
    # Internals — absorb dispatcher outcome between turns
    # ------------------------------------------------------------------

    def _absorb(self, *, build_id: str, report: TurnReport) -> None:
        if report.outcome is not TurnOutcome.DISPATCHED:
            return
        stage = report.chosen_stage
        if stage is None:
            return

        if stage is StageClass.TASK_REVIEW:
            self._absorb_review(build_id=build_id, report=report)
            return
        if stage is StageClass.TASK_WORK:
            self._absorb_work(build_id=build_id, report=report)
            return
        if stage is StageClass.PULL_REQUEST_REVIEW:
            self._absorb_pr_terminal(report)
            return

    def _absorb_review(self, *, build_id: str, report: TurnReport) -> None:
        result = report.dispatch_result
        if not isinstance(result, dict):
            return
        outcome = ReviewOutcome(
            fix_tasks=tuple(result.get("fix_tasks", ())),
            status=str(result.get("status", "approved")),
            hard_stop=bool(result.get("hard_stop", False)),
        )
        self.stage_log.append_review(build_id=build_id, outcome=outcome)

    def _absorb_work(self, *, build_id: str, report: TurnReport) -> None:
        result = report.dispatch_result
        if not isinstance(result, dict):
            return
        fix_task_id = result.get("fix_task_id")
        if not isinstance(fix_task_id, str):
            return
        # Locate the originating review row by the planner's
        # ``review_history_index`` lineage (Group L). The review at the
        # planner's scoped index *is* the most recent review row in the
        # harness — the planner is stateless and tracks the most recent
        # review on every call.
        review_rows = self.stage_log.review_rows
        if not review_rows:
            raise AssertionError(
                "harness invariant violated: TASK_WORK dispatched "
                "without a recorded /task-review row preceding it"
            )
        originating = review_rows[-1]
        # Resolve the fix-task ref the planner emitted by reading the
        # captured fix-task on this dispatcher call. Falls back to the
        # last captured ref when the call sequencing is in doubt.
        last_call = self.subprocess_dispatcher.calls[-1]
        ref = last_call.get("fix_task")
        if ref is None or not isinstance(ref, FixTaskRef):
            raise AssertionError(
                "harness invariant violated: TASK_WORK dispatch carried "
                "no FixTaskRef (Group B canary)"
            )
        outcome = WorkOutcome(
            status=str(result.get("status", "approved")),
            artefact_paths=tuple(result.get("artefact_paths", ())),
        )
        self.stage_log.append_work(
            build_id=build_id,
            fix_task=ref,
            outcome=outcome,
            originating_review_entry_id=originating.entry_id,
        )

    def _absorb_pr_terminal(self, report: TurnReport) -> None:
        if not self.pr_review_gate.submissions:
            return
        latest_submission = self.pr_review_gate.submissions[-1]
        if not self.stage_log.chronology:
            return
        row = self.stage_log.chronology[-1]
        row["gate_mode"] = latest_submission["gate_mode"]
        row["pull_request_url"] = latest_submission["pull_request_url"]

    @staticmethod
    def _is_paused_or_terminal(report: TurnReport) -> bool:
        if report.outcome is TurnOutcome.TERMINAL:
            return True
        if report.outcome is TurnOutcome.DISPATCHED:
            return report.chosen_stage is StageClass.PULL_REQUEST_REVIEW
        # NO_OP / WAITING / refused outcomes are not terminal but they
        # also do not advance the cycle; stop so the test surfaces the
        # stuck state rather than spinning to MAX_TURNS.
        return report.outcome in (
            TurnOutcome.WAITING,
            TurnOutcome.NO_OP,
            TurnOutcome.REFUSED_OUT_OF_BAND,
            TurnOutcome.REFUSED_CONSTITUTIONAL,
        )


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


def _build_pipeline(
    *,
    review_outcomes: Sequence[ReviewOutcome],
    work_outcomes_by_fix_task: Mapping[str, WorkOutcome] | None = None,
    commit_count: int = 0,
    build_id: str = SMOKE_BUILD_ID,
) -> ModeCSmokePipeline:
    """Construct a Mode C smoke harness with scripted outcomes."""
    stage_log = FakeModeCStageLog()
    state_reader = FakeStateReader()
    mode_reader = FakeBuildModeReader(modes={build_id: BuildMode.MODE_C})
    async_task_reader = FakeAsyncTaskReader()
    reasoning_model = _UnusedReasoningModel()
    subprocess_dispatcher = PlannedSubprocessDispatcher(
        review_outcomes=list(review_outcomes),
        work_outcomes_by_fix_task=dict(work_outcomes_by_fix_task or {}),
    )
    pr_review_gate = FakePRReviewGate()
    commit_probe = FakeCommitProbe(count=commit_count)
    captured_fix_tasks: list[dict[str, Any]] = []

    def fix_task_context_builder(
        stage: StageClass, build_id_arg: str, fix_task: FixTaskRef
    ) -> Mapping[str, Any]:
        captured_fix_tasks.append(
            {
                "stage": stage,
                "build_id": build_id_arg,
                "fix_task": fix_task,
            }
        )
        return {"--fix-task": fix_task.fix_task_id}

    supervisor = Supervisor(
        ordering_guard=StageOrderingGuard(),
        per_feature_sequencer=PerFeatureLoopSequencer(),
        constitutional_guard=ConstitutionalGuard(),
        state_reader=state_reader,
        ordering_stage_log_reader=stage_log,
        per_feature_stage_log_reader=stage_log,
        async_task_reader=async_task_reader,
        reasoning_model=reasoning_model,
        turn_recorder=stage_log,
        specialist_dispatcher=_unused_specialist_dispatcher,
        subprocess_dispatcher=subprocess_dispatcher,
        autobuild_dispatcher=_unused_autobuild_dispatcher,
        pr_review_gate=pr_review_gate,
        build_mode_reader=mode_reader,
        mode_c_planner=ModeCCyclePlanner(),
        mode_c_history_reader=stage_log,
        mode_c_commit_probe=commit_probe,
        fix_task_context_builder=fix_task_context_builder,
    )

    return ModeCSmokePipeline(
        supervisor=supervisor,
        stage_log=stage_log,
        state_machine=state_reader,
        mode_reader=mode_reader,
        subprocess_dispatcher=subprocess_dispatcher,
        pr_review_gate=pr_review_gate,
        commit_probe=commit_probe,
        clock=FakeClock(),
        captured_fix_tasks=captured_fix_tasks,
    )


async def _unused_specialist_dispatcher(**kwargs: Any) -> Any:
    raise AssertionError(
        f"specialist dispatcher must NOT fire in Mode C; got kwargs={kwargs!r}"
    )


def _unused_autobuild_dispatcher(**kwargs: Any) -> Any:
    raise AssertionError(
        f"autobuild dispatcher must NOT fire in Mode C; got kwargs={kwargs!r}"
    )


# ---------------------------------------------------------------------------
# AC: Module exists at tests/integration/test_mode_c_smoke_e2e.py
# ---------------------------------------------------------------------------


class TestModuleExists:
    """AC: Test module exists at the canonical AC path."""

    def test_module_path_matches_acceptance_criterion(self) -> None:
        assert __name__.endswith("test_mode_c_smoke_e2e")


# ---------------------------------------------------------------------------
# AC: Empty initial review → clean-review terminal, no /task-work
# ---------------------------------------------------------------------------


class TestEmptyInitialReviewTerminal:
    """ASSUM-007 / Group B — initial empty review terminates without dispatch."""

    @pytest.mark.asyncio
    async def test_empty_review_reaches_clean_review_terminal(self) -> None:
        pipeline = _build_pipeline(
            review_outcomes=[ReviewOutcome(fix_tasks=())],
            commit_count=0,
        )

        report = await pipeline.drive_until_terminal()

        assert report.outcome is TurnOutcome.TERMINAL, (
            f"expected TERMINAL outcome for empty initial review; "
            f"got {report.outcome.value!r}"
        )
        assert (
            "clean-review" in report.rationale
        ), "terminal rationale must reference the clean-review outcome"

    @pytest.mark.asyncio
    async def test_empty_review_does_not_dispatch_task_work(self) -> None:
        pipeline = _build_pipeline(
            review_outcomes=[ReviewOutcome(fix_tasks=())],
            commit_count=0,
        )

        await pipeline.drive_until_terminal()

        # Exactly one /task-review dispatch — no /task-work.
        review_calls = [
            c
            for c in pipeline.subprocess_dispatcher.calls
            if c["stage"] is StageClass.TASK_REVIEW
        ]
        work_calls = [
            c
            for c in pipeline.subprocess_dispatcher.calls
            if c["stage"] is StageClass.TASK_WORK
        ]
        assert len(review_calls) == 1
        assert work_calls == []

    @pytest.mark.asyncio
    async def test_empty_review_records_no_pr_url(self) -> None:
        pipeline = _build_pipeline(
            review_outcomes=[ReviewOutcome(fix_tasks=())],
            commit_count=0,
        )

        await pipeline.drive_until_terminal()

        assert (
            pipeline.pr_review_gate.submissions == []
        ), "PR-review gate must not be invoked on the empty-review path"
        # Every chronology row's pull_request_url must be None.
        pr_urls = [
            row["pull_request_url"]
            for row in pipeline.stage_log.chronology
            if row["pull_request_url"] is not None
        ]
        assert pr_urls == []


# ---------------------------------------------------------------------------
# AC: N fix tasks → no commits → clean-review terminal, no PR
# ---------------------------------------------------------------------------


class TestFixTasksNoCommitsTerminal:
    """ASSUM-017 / Group N — N fix tasks complete with zero commits."""

    @pytest.mark.asyncio
    async def test_three_fix_tasks_no_commits_reaches_clean_review_terminal(
        self,
    ) -> None:
        # First review emits 3 fix tasks; follow-up review is clean.
        pipeline = _build_pipeline(
            review_outcomes=[
                ReviewOutcome(fix_tasks=("FIX-1", "FIX-2", "FIX-3")),
                ReviewOutcome(fix_tasks=()),
            ],
            commit_count=0,
        )

        report = await pipeline.drive_until_terminal()

        assert report.outcome is TurnOutcome.TERMINAL
        # All three fix tasks were dispatched and approved.
        work_calls = [
            c
            for c in pipeline.subprocess_dispatcher.calls
            if c["stage"] is StageClass.TASK_WORK
        ]
        assert len(work_calls) == 3
        assert sorted(c["fix_task"].fix_task_id for c in work_calls) == [
            "FIX-1",
            "FIX-2",
            "FIX-3",
        ]
        assert "clean-review" in report.rationale.lower(), (
            f"terminal rationale must reference clean-review; "
            f"got {report.rationale!r}"
        )

    @pytest.mark.asyncio
    async def test_three_fix_tasks_no_commits_records_no_pr_url(self) -> None:
        pipeline = _build_pipeline(
            review_outcomes=[
                ReviewOutcome(fix_tasks=("FIX-1", "FIX-2", "FIX-3")),
                ReviewOutcome(fix_tasks=()),
            ],
            commit_count=0,
        )

        await pipeline.drive_until_terminal()

        # No PR-creation attempt — the constitutional gate has nothing to
        # fire on (ASSUM-017).
        assert pipeline.pr_review_gate.submissions == []


# ---------------------------------------------------------------------------
# AC: N fix tasks → commits → PR-awaiting-review terminal at constitutional
# gate
# ---------------------------------------------------------------------------


class TestFixTasksWithCommitsReachesPRReview:
    """ASSUM-005 / Group A key-example — N fix tasks + commits → PR review."""

    @pytest.mark.asyncio
    async def test_three_fix_tasks_with_commits_pauses_at_pull_request_review(
        self,
    ) -> None:
        pipeline = _build_pipeline(
            review_outcomes=[
                ReviewOutcome(fix_tasks=("FIX-1", "FIX-2", "FIX-3")),
                ReviewOutcome(fix_tasks=()),
            ],
            commit_count=2,
        )

        report = await pipeline.drive_until_terminal()

        assert report.outcome is TurnOutcome.DISPATCHED
        assert report.chosen_stage is StageClass.PULL_REQUEST_REVIEW
        assert len(pipeline.pr_review_gate.submissions) == 1

    @pytest.mark.asyncio
    async def test_pr_review_carries_mandatory_human_gate_mode_and_url(
        self,
    ) -> None:
        pipeline = _build_pipeline(
            review_outcomes=[
                ReviewOutcome(fix_tasks=("FIX-1", "FIX-2", "FIX-3")),
                ReviewOutcome(fix_tasks=()),
            ],
            commit_count=4,
        )

        await pipeline.drive_until_terminal()

        # Exactly one PR submission with auto_approve=False — Mode C
        # never auto-approves the constitutional gate.
        submission = pipeline.pr_review_gate.submissions[0]
        assert submission["auto_approve"] is False
        assert submission["gate_mode"] == MANDATORY_HUMAN_APPROVAL
        assert submission["pull_request_url"].startswith(
            "https://github.com/example/forge/pull/"
        )

        # PR URL is recorded on the chronology row for the PR-review
        # dispatch — matches the FEAT-FORGE-007 smoke contract.
        pr_rows = [
            row
            for row in pipeline.stage_log.chronology
            if row["chosen_stage"] is StageClass.PULL_REQUEST_REVIEW
        ]
        assert len(pr_rows) == 1
        assert pr_rows[0]["gate_mode"] == MANDATORY_HUMAN_APPROVAL
        assert pr_rows[0]["pull_request_url"]


# ---------------------------------------------------------------------------
# AC: Stage-history shape — ordering, single fix-task ref, attribution,
# lineage
# ---------------------------------------------------------------------------


class TestStageHistoryShape:
    """Stage-history invariants that hold across all three terminals."""

    @pytest.mark.asyncio
    async def test_task_review_precedes_every_task_work_it_produced(
        self,
    ) -> None:
        # Group G ordering: each /task-work appears AFTER the
        # /task-review whose fix-task list it dispatched against.
        pipeline = _build_pipeline(
            review_outcomes=[
                ReviewOutcome(fix_tasks=("FIX-A", "FIX-B")),
                ReviewOutcome(fix_tasks=()),
            ],
            commit_count=0,
        )

        await pipeline.drive_until_terminal()

        rows = pipeline.stage_log.rows
        # The first row must be a /task-review; every subsequent
        # /task-work must have a /task-review row at a smaller index.
        assert rows[0].stage_class is StageClass.TASK_REVIEW
        last_review_idx_seen: int | None = None
        for idx, row in enumerate(rows):
            if row.stage_class is StageClass.TASK_REVIEW:
                last_review_idx_seen = idx
                continue
            if row.stage_class is StageClass.TASK_WORK:
                assert last_review_idx_seen is not None, (
                    f"row {idx} TASK_WORK appeared before any TASK_REVIEW: "
                    f"chronology={rows!r}"
                )
                assert last_review_idx_seen < idx

    @pytest.mark.asyncio
    async def test_each_task_work_references_exactly_one_fix_task_id(
        self,
    ) -> None:
        # Group B "every dispatched task-work should reference exactly
        # one fix task identifier".
        pipeline = _build_pipeline(
            review_outcomes=[
                ReviewOutcome(fix_tasks=("FIX-1", "FIX-2", "FIX-3")),
                ReviewOutcome(fix_tasks=()),
            ],
            commit_count=0,
        )

        await pipeline.drive_until_terminal()

        for work in pipeline.stage_log.work_rows:
            assert (
                work.fix_task_id is not None
            ), f"TASK_WORK row {work!r} carries no fix_task_id"
            assert (
                work.details.get("fix_task_id") == work.fix_task_id
            ), "details.fix_task_id must mirror the row-level fix_task_id"

    @pytest.mark.asyncio
    async def test_artefact_paths_attribute_only_to_producing_fix_task(
        self,
    ) -> None:
        # Group G "no artefact path attributed to more than one fix task".
        pipeline = _build_pipeline(
            review_outcomes=[
                ReviewOutcome(fix_tasks=("FIX-1", "FIX-2", "FIX-3")),
                ReviewOutcome(fix_tasks=()),
            ],
            work_outcomes_by_fix_task={
                "FIX-1": WorkOutcome(
                    status="approved",
                    artefact_paths=("src/a.py", "tests/a_test.py"),
                ),
                "FIX-2": WorkOutcome(
                    status="approved",
                    artefact_paths=("src/b.py",),
                ),
                "FIX-3": WorkOutcome(
                    status="approved",
                    artefact_paths=("docs/c.md",),
                ),
            },
            commit_count=0,
        )

        await pipeline.drive_until_terminal()

        seen_paths: dict[str, str] = {}
        for work in pipeline.stage_log.work_rows:
            for path in work.details.get("artefact_paths", []):
                prior_owner = seen_paths.get(path)
                assert prior_owner is None or prior_owner == work.fix_task_id, (
                    f"artefact path {path!r} attributed to both "
                    f"{prior_owner!r} and {work.fix_task_id!r}"
                )
                seen_paths[path] = work.fix_task_id  # type: ignore[assignment]
        # Sanity-check that artefact attribution actually carried at
        # least one path per fix task — guards against the test silently
        # passing on an empty list.
        attributed_per_fix_task = {
            work.fix_task_id: list(work.details.get("artefact_paths", []))
            for work in pipeline.stage_log.work_rows
        }
        assert attributed_per_fix_task["FIX-1"] == [
            "src/a.py",
            "tests/a_test.py",
        ]
        assert attributed_per_fix_task["FIX-2"] == ["src/b.py"]
        assert attributed_per_fix_task["FIX-3"] == ["docs/c.md"]

    @pytest.mark.asyncio
    async def test_each_task_work_carries_originating_review_entry_id(
        self,
    ) -> None:
        # Group L lineage: every /task-work points back to the
        # /task-review entry_id that emitted its fix-task identifier.
        pipeline = _build_pipeline(
            review_outcomes=[
                ReviewOutcome(fix_tasks=("FIX-1", "FIX-2")),
                ReviewOutcome(fix_tasks=()),
            ],
            commit_count=0,
        )

        await pipeline.drive_until_terminal()

        review_rows = pipeline.stage_log.review_rows
        # The first review is the originator for every dispatched fix
        # task; the follow-up review (if any) emits no fix tasks in
        # this scenario.
        originating_id = review_rows[0].entry_id
        for work in pipeline.stage_log.work_rows:
            assert work.details.get("originating_review_entry_id") == originating_id, (
                f"TASK_WORK {work.fix_task_id!r} lineage missing or stale: "
                f"got {work.details.get('originating_review_entry_id')!r}, "
                f"expected {originating_id!r}"
            )


# ---------------------------------------------------------------------------
# AC: Failure-isolation (ASSUM-008) — sibling fix tasks dispatched after
# one fails
# ---------------------------------------------------------------------------


class TestFailureIsolation:
    """ASSUM-008 — failed /task-work does not auto-cancel sibling fix tasks."""

    @pytest.mark.asyncio
    async def test_failed_work_does_not_block_sibling_dispatch(self) -> None:
        pipeline = _build_pipeline(
            review_outcomes=[
                ReviewOutcome(fix_tasks=("FIX-A", "FIX-B", "FIX-C")),
                ReviewOutcome(fix_tasks=()),
            ],
            work_outcomes_by_fix_task={
                "FIX-A": WorkOutcome(status="approved"),
                "FIX-B": WorkOutcome(status="failed"),
                "FIX-C": WorkOutcome(status="approved"),
            },
            commit_count=0,
        )

        report = await pipeline.drive_until_terminal()

        # All three fix tasks were dispatched even though FIX-B failed.
        dispatched_ids = [
            c["fix_task"].fix_task_id
            for c in pipeline.subprocess_dispatcher.calls
            if c["stage"] is StageClass.TASK_WORK
        ]
        assert sorted(dispatched_ids) == ["FIX-A", "FIX-B", "FIX-C"]

        # Failure recorded against the offending fix task only.
        statuses_by_id = {
            row.fix_task_id: row.status for row in pipeline.stage_log.work_rows
        }
        assert statuses_by_id == {
            "FIX-A": "approved",
            "FIX-B": "failed",
            "FIX-C": "approved",
        }
        # The cycle still terminates cleanly (mixed failures do not
        # poison the cycle — the follow-up review decides).
        assert report.outcome is TurnOutcome.TERMINAL


# ---------------------------------------------------------------------------
# AC: Hard-stop — /task-review hard-stops the build, no /task-work
# ---------------------------------------------------------------------------


class TestHardStopReview:
    """Group C — /task-review hard-stop terminates the build with FAILED."""

    @pytest.mark.asyncio
    async def test_hard_stop_review_reaches_failed_terminal(self) -> None:
        pipeline = _build_pipeline(
            review_outcomes=[
                ReviewOutcome(fix_tasks=(), status="failed", hard_stop=True),
            ],
            commit_count=0,
        )

        report = await pipeline.drive_until_terminal()

        assert report.outcome is TurnOutcome.TERMINAL
        # Terminal rationale flags the FAILED outcome on a hard-stopped
        # review.
        rationale = report.rationale.lower()
        assert "failed" in rationale or "hard-stop" in rationale, (
            f"hard-stop terminal must surface FAILED rationale; "
            f"got {report.rationale!r}"
        )

    @pytest.mark.asyncio
    async def test_hard_stop_review_does_not_dispatch_any_task_work(
        self,
    ) -> None:
        pipeline = _build_pipeline(
            review_outcomes=[
                ReviewOutcome(fix_tasks=(), status="failed", hard_stop=True),
            ],
            commit_count=0,
        )

        await pipeline.drive_until_terminal()

        work_calls = [
            c
            for c in pipeline.subprocess_dispatcher.calls
            if c["stage"] is StageClass.TASK_WORK
        ]
        assert work_calls == []
        assert pipeline.pr_review_gate.submissions == []


# ---------------------------------------------------------------------------
# AC: Cycle termination (ASSUM-010) — clean follow-up after N fix tasks
# ---------------------------------------------------------------------------


class TestCycleTermination:
    """ASSUM-010 — no numeric cap; reviewer-driven cycle termination."""

    @pytest.mark.asyncio
    async def test_followup_clean_review_terminates_after_fix_tasks_complete(
        self,
    ) -> None:
        # First review: 2 fix tasks; second review: clean (no fix tasks).
        # No commits → clean-review terminal (ASSUM-017).
        pipeline = _build_pipeline(
            review_outcomes=[
                ReviewOutcome(fix_tasks=("FIX-X", "FIX-Y")),
                ReviewOutcome(fix_tasks=()),
            ],
            commit_count=0,
        )

        report = await pipeline.drive_until_terminal()

        # Exactly two reviews dispatched (initial + follow-up).
        review_calls = [
            c
            for c in pipeline.subprocess_dispatcher.calls
            if c["stage"] is StageClass.TASK_REVIEW
        ]
        assert len(review_calls) == 2
        # No further /task-work after the follow-up review (it returned
        # an empty fix-task list).
        review_rows = pipeline.stage_log.review_rows
        assert len(review_rows) == 2
        followup_idx = pipeline.stage_log.rows.index(review_rows[-1])
        assert followup_idx == len(pipeline.stage_log.rows) - 1, (
            "follow-up /task-review must be the last recorded row "
            "when the cycle terminates with no commits"
        )
        assert report.outcome is TurnOutcome.TERMINAL


# ---------------------------------------------------------------------------
# AC: Tests run in under 60 seconds with stubbed dispatchers
# ---------------------------------------------------------------------------


class TestPerformanceBudget:
    """AC: the smoke suite completes in under 60 seconds."""

    @pytest.mark.asyncio
    async def test_three_terminal_paths_complete_under_one_second(self) -> None:
        # All three terminal paths together; each individually well
        # under the 60s budget. The harness uses zero real I/O — every
        # dispatcher is in-memory — so this is a regression canary
        # against future wiring that accidentally introduces sleeps or
        # real subprocess spawns.
        import time

        start = time.monotonic()

        empty = _build_pipeline(
            review_outcomes=[ReviewOutcome(fix_tasks=())],
            commit_count=0,
        )
        await empty.drive_until_terminal()

        no_commits = _build_pipeline(
            review_outcomes=[
                ReviewOutcome(fix_tasks=("F-1", "F-2", "F-3")),
                ReviewOutcome(fix_tasks=()),
            ],
            commit_count=0,
        )
        await no_commits.drive_until_terminal()

        with_commits = _build_pipeline(
            review_outcomes=[
                ReviewOutcome(fix_tasks=("F-1", "F-2", "F-3")),
                ReviewOutcome(fix_tasks=()),
            ],
            commit_count=2,
        )
        await with_commits.drive_until_terminal()

        elapsed = time.monotonic() - start
        # 1 second is a tight bound that still gives orders of magnitude
        # of headroom against the 60-second AC budget.
        assert elapsed < 1.0, (
            f"smoke suite exceeded 1-second budget: {elapsed:.2f}s — "
            "regression canary for accidentally-introduced sleeps or "
            "real subprocess spawns"
        )
