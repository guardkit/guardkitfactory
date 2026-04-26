"""Supervisor reasoning-loop dispatch turn (TASK-MAG7-010, FEAT-FORGE-007).

This module owns the **reasoning-loop turn function** the FEAT-FORGE-007
supervisor runs once per build per outer-loop iteration. Each call to
:meth:`Supervisor.next_turn`:

1. Reads the build's current state from the FEAT-FORGE-001 state machine
   (via the injected :class:`StateMachineReader` Protocol).
2. Asks :class:`~forge.pipeline.stage_ordering_guard.StageOrderingGuard`
   for the set of dispatchable stages (TASK-MAG7-003 belt-and-braces).
3. Presents the permitted set + per-stage forward-propagation hints
   (TASK-MAG7-002) to the reasoning model and parses the chosen
   dispatch.
4. Re-checks the model's choice against the permitted set — refuses with
   a structured warning if the model hallucinates an out-of-band stage.
5. Applies the per-feature autobuild sequencer
   (:class:`~forge.pipeline.per_feature_sequencer.PerFeatureLoopSequencer`,
   TASK-MAG7-005) for ``AUTOBUILD`` choices.
6. Applies the constitutional guard
   (:class:`~forge.pipeline.constitutional_guard.ConstitutionalGuard`,
   TASK-MAG7-004) for ``PULL_REQUEST_REVIEW`` gate decisions.
7. Routes the (verified) dispatch to the correct dispatcher:

   ============================  ====================================
   Stage class                   Dispatcher
   ============================  ====================================
   ``PRODUCT_OWNER``             specialist (TASK-MAG7-007)
   ``ARCHITECT``                 specialist (TASK-MAG7-007)
   ``SYSTEM_ARCH``               subprocess  (TASK-MAG7-008)
   ``SYSTEM_DESIGN``             subprocess  (TASK-MAG7-008)
   ``FEATURE_SPEC``              subprocess  (TASK-MAG7-008)
   ``FEATURE_PLAN``              subprocess  (TASK-MAG7-008)
   ``AUTOBUILD``                 autobuild_async (TASK-MAG7-009)
   ``PULL_REQUEST_REVIEW``       gate decision (FEAT-FORGE-004)
   ============================  ====================================

8. Records the per-turn outcome (decision + rationale) in ``stage_log``
   via the injected :class:`StageLogTurnRecorder` Protocol.

The supervisor itself owns **no mutable state** keyed on ``build_id`` —
every dependency is injected, every method takes ``build_id`` explicitly,
and the same instance is safe to call from concurrent ``next_turn``
invocations on different builds (FEAT-FORGE-007 Group F @concurrency).

I/O-thinness is a hard requirement (TASK-MAG7-010 implementation notes):
this module never opens a SQLite connection, never spawns a process,
never reads NATS — it composes the guards and dispatchers from Waves 2
and 3 and lets *them* do the I/O behind their respective Protocols.

References
----------

- TASK-MAG7-010 — this task brief.
- TASK-MAG7-001 — :mod:`forge.pipeline.stage_taxonomy`.
- TASK-MAG7-002 — forward-propagation hints (consumed via
  :class:`~forge.pipeline.forward_propagation.ForwardPropagation` if
  available; this module accepts the hints as plain strings so the
  taxonomy/propagation modules stay decoupled from the supervisor).
- TASK-MAG7-003 — :class:`StageOrderingGuard`.
- TASK-MAG7-004 — :class:`ConstitutionalGuard`.
- TASK-MAG7-005 — :class:`PerFeatureLoopSequencer`.
- TASK-MAG7-007 — :func:`dispatch_specialist_stage`.
- TASK-MAG7-008 — :func:`dispatch_subprocess_stage`.
- TASK-MAG7-009 — :func:`dispatch_autobuild_async`.
- ADR-ARCH-026 — Constitutional rules (belt-and-braces).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Awaitable, Callable, Mapping, Protocol, runtime_checkable

from forge.pipeline.constitutional_guard import (
    AutoApproveDecision,
    AutoApproveVerdict,
    ConstitutionalGuard,
)
from forge.pipeline.per_feature_sequencer import (
    AsyncTaskReader as PerFeatureAsyncTaskReader,
)
from forge.pipeline.per_feature_sequencer import PerFeatureLoopSequencer
from forge.pipeline.per_feature_sequencer import (
    StageLogReader as PerFeatureStageLogReader,
)
from forge.pipeline.stage_ordering_guard import (
    StageLogReader as OrderingStageLogReader,
)
from forge.pipeline.stage_ordering_guard import StageOrderingGuard
from forge.pipeline.stage_taxonomy import PER_FEATURE_STAGES, StageClass

logger = logging.getLogger(__name__)


__all__ = [
    "BuildState",
    "DispatchChoice",
    "PRReviewGate",
    "ReasoningModelPort",
    "StageLogTurnRecorder",
    "StateMachineReader",
    "Supervisor",
    "TerminalStateError",
    "TurnOutcome",
    "TurnReport",
]


# ---------------------------------------------------------------------------
# Outcome enum + report dataclass — supervisor's structured return shape
# ---------------------------------------------------------------------------


class TurnOutcome(StrEnum):
    """Closed set of outcomes :meth:`Supervisor.next_turn` can yield.

    The outcome tells the supervisor's *outer* loop what to do next and
    is recorded verbatim on the per-turn ``stage_log`` row so the audit
    trail captures why a turn ended where it did.

    Members:
        DISPATCHED: A dispatch was issued to one of the four dispatchers.
            ``TurnReport.dispatch_result`` carries the dispatcher's
            structured outcome.
        WAITING: No dispatchable stages and the build is in a non-terminal
            state (e.g. waiting on an approval response). The outer loop
            should pause until an external event resumes the build.
        WAITING_PRIOR_AUTOBUILD: An ``AUTOBUILD`` was permitted by the
            stage-ordering guard, but the per-feature sequencer refused
            because a sibling feature's autobuild is still in flight.
        REFUSED_OUT_OF_BAND: The reasoning model picked a stage outside
            the permitted set. The supervisor refused to act and recorded
            a structured warning. The outer loop should retry the turn.
        REFUSED_CONSTITUTIONAL: A ``PULL_REQUEST_REVIEW`` auto-approve
            was attempted and the constitutional guard refused. The PR
            stays gated for mandatory human approval.
        TERMINAL: The build is in a terminal state (COMPLETE / FAILED /
            CANCELLED). The supervisor will not produce further turns.
        NO_OP: The reasoning model declined to choose any stage (returned
            ``None``). This is distinct from ``WAITING``: the model
            actively reasoned about an empty action.
    """

    DISPATCHED = "dispatched"
    WAITING = "waiting"
    WAITING_PRIOR_AUTOBUILD = "waiting_prior_autobuild"
    REFUSED_OUT_OF_BAND = "refused_out_of_band"
    REFUSED_CONSTITUTIONAL = "refused_constitutional"
    TERMINAL = "terminal"
    NO_OP = "no_op"


class BuildState(StrEnum):
    """Coarse state-machine states the supervisor reasons about.

    Mirrors the FEAT-FORGE-001 ``Build.state`` literal; only the four
    states the supervisor needs to *branch on* are enumerated. Anything
    else is treated as "running" by default — the supervisor never
    decides terminal-vs-not on its own; it asks the state machine.
    """

    PREPARING = "PREPARING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FINALISING = "FINALISING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        """Return ``True`` for terminal states (COMPLETE / FAILED / CANCELLED)."""
        return self in (
            BuildState.COMPLETE,
            BuildState.FAILED,
            BuildState.CANCELLED,
        )


@dataclass(frozen=True, slots=True)
class DispatchChoice:
    """Structured dispatch choice returned by the reasoning model.

    The reasoning model is asked to pick one entry from the permitted
    set; this dataclass is the parsed shape the supervisor consumes. A
    ``None`` choice (no dispatch) is represented by the model returning
    ``None`` from :meth:`ReasoningModelPort.choose_dispatch`, not by
    constructing a sentinel :class:`DispatchChoice`.

    Attributes:
        stage: The stage class the model selected.
        feature_id: Per-feature scope. Required for stages in
            :data:`PER_FEATURE_STAGES` other than ``PULL_REQUEST_REVIEW``.
        rationale: Free-form rationale string the model emits alongside
            its choice. Recorded verbatim on the per-turn ``stage_log``
            row so the audit trail captures *why* the model chose this
            dispatch.
        auto_approve: For ``PULL_REQUEST_REVIEW`` only — set to ``True``
            when the model wants to attempt an auto-approve. The
            constitutional guard veto runs on this flag (AC: PR-review
            constitutional veto).
    """

    stage: StageClass
    feature_id: str | None = None
    rationale: str = ""
    auto_approve: bool = False


@dataclass(frozen=True, slots=True)
class TurnReport:
    """Structured return shape of :meth:`Supervisor.next_turn`.

    Threaded back to the outer loop and recorded verbatim on the
    per-turn ``stage_log`` row. The :attr:`outcome` field is the primary
    discriminator; the remaining fields carry context for the outer loop
    and the audit trail.

    Attributes:
        outcome: The :class:`TurnOutcome` enum member.
        build_id: Build identifier the turn was for.
        permitted_stages: Snapshot of the dispatchable set returned by
            :class:`StageOrderingGuard`. Stored as a frozen set so the
            audit trail can compare against the model's choice.
        chosen_stage: The stage the reasoning model picked (or ``None``
            if no dispatch attempted).
        chosen_feature_id: Feature scope of the choice, or ``None``.
        rationale: Combined rationale: model's reasoning plus any
            supervisor-side append (e.g. constitutional refusal).
        dispatch_result: Whatever the dispatcher returned. The
            supervisor does not interpret this — the gating layer does.
        gate_decision: For ``PULL_REQUEST_REVIEW`` turns, the
            :class:`AutoApproveDecision` returned by the constitutional
            guard. ``None`` for every other outcome.
    """

    outcome: TurnOutcome
    build_id: str
    permitted_stages: frozenset[StageClass] = frozenset()
    chosen_stage: StageClass | None = None
    chosen_feature_id: str | None = None
    rationale: str = ""
    dispatch_result: Any | None = None
    gate_decision: AutoApproveDecision | None = None


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class TerminalStateError(RuntimeError):
    """Raised by callers that try to invoke ``next_turn`` after a terminal state.

    The supervisor itself does **not** raise this — terminal builds yield
    :attr:`TurnOutcome.TERMINAL` so the outer loop can clean up gracefully.
    The exception type is exported so tests and diagnostic tooling can
    assert on it, and so future callers that want a hard-fail signal can
    opt in by inspecting the ``outcome``.
    """


# ---------------------------------------------------------------------------
# Injected Protocols — supervisor's only I/O surface
# ---------------------------------------------------------------------------


@runtime_checkable
class StateMachineReader(Protocol):
    """Read-side Protocol over the FEAT-FORGE-001 build state machine.

    The supervisor only needs the current coarse state of the build —
    "is this build still running, or has it terminated?". The full state
    machine surface (transitions, history, etc.) lives in
    FEAT-FORGE-001; this Protocol is the read-only seam the supervisor
    consults once per turn.
    """

    def get_build_state(
        self, build_id: str
    ) -> BuildState:  # pragma: no cover - protocol stub
        """Return the current :class:`BuildState` for ``build_id``."""
        ...


@runtime_checkable
class ReasoningModelPort(Protocol):
    """Protocol over the supervisor's reasoning model.

    Production wires a LangChain ``ChatModel`` adapter; tests inject an
    in-memory fake that returns a deterministic :class:`DispatchChoice`.
    The Protocol is intentionally narrow — exactly one call per turn,
    receiving the build state, the permitted set, and a per-stage hints
    mapping (forward-propagation hints from TASK-MAG7-002).
    """

    def choose_dispatch(
        self,
        *,
        build_id: str,
        build_state: BuildState,
        permitted_stages: frozenset[StageClass],
        stage_hints: Mapping[StageClass, str],
        feature_catalogue: tuple[str, ...],
    ) -> DispatchChoice | None:  # pragma: no cover - protocol stub
        """Return the dispatch the model wants to issue, or ``None`` for no-op.

        Args:
            build_id: Build identifier.
            build_state: Current coarse state-machine state.
            permitted_stages: Set returned by
                :meth:`StageOrderingGuard.next_dispatchable`. The model
                is asked to pick one entry; anything outside this set
                will be refused at the executor layer.
            stage_hints: Mapping of stage class to a free-form hint
                string (forward-propagation context, prior reasoning,
                etc.). Empty mapping is fine — the supervisor never
                depends on a specific hint shape.
            feature_catalogue: Feature IDs in the build's catalogue.
                Required for the model to choose a per-feature stage.
        """
        ...


@runtime_checkable
class StageLogTurnRecorder(Protocol):
    """Recorder over the FEAT-FORGE-001 ``stage_log`` for per-turn rows.

    Distinct from the dispatcher-side stage-log writers (which record
    *dispatch* outcomes); this Protocol records the **per-turn** decision
    — outcome, rationale, the permitted set, the chosen stage, and any
    gate verdict. Production wires the SQLite adapter; tests use an
    in-memory fake.
    """

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
    ) -> None:  # pragma: no cover - protocol stub
        """Persist a per-turn audit row.

        Args:
            build_id: Build identifier.
            outcome: The :class:`TurnOutcome` discriminator.
            permitted_stages: Snapshot of the dispatchable set.
            chosen_stage: Stage class the model picked (or ``None``).
            chosen_feature_id: Feature scope (or ``None``).
            rationale: Combined rationale string. May include the model's
                free-form text plus supervisor-side appendices (e.g.
                "constitutional refusal: ...").
            gate_verdict: Optional verdict string for PR-review turns
                (e.g. ``"refused"`` / ``"allowed"``). ``None`` for
                non-gate turns.
        """
        ...


@runtime_checkable
class PRReviewGate(Protocol):
    """Protocol over the FEAT-FORGE-004 pull-request-review gate.

    The supervisor only needs the "submit a gate decision" side — the
    constitutional veto is applied *before* this method is called, so
    by the time we reach :meth:`submit_decision` the auto-approve flag
    has been sanitised against ADR-ARCH-026.
    """

    def submit_decision(
        self,
        *,
        build_id: str,
        feature_id: str,
        auto_approve: bool,
        rationale: str,
    ) -> Any:  # pragma: no cover - protocol stub
        """Submit the PR-review gate decision and return the gate's record."""
        ...


# ---------------------------------------------------------------------------
# Dispatcher callable types
# ---------------------------------------------------------------------------


# Each dispatcher is injected as a callable so the supervisor never
# imports the concrete dispatch functions directly. Tests inject in-memory
# fakes; production wires ``functools.partial`` adapters around the real
# ``dispatch_specialist_stage`` / ``dispatch_subprocess_stage`` /
# ``dispatch_autobuild_async`` callables.

#: Callable that dispatches a specialist stage. Async because the
#: production target (:func:`dispatch_specialist_stage`) is async.
SpecialistDispatcher = Callable[..., Awaitable[Any]]

#: Callable that dispatches a subprocess stage. Async — wraps
#: :func:`dispatch_subprocess_stage`.
SubprocessDispatcher = Callable[..., Awaitable[Any]]

#: Callable that dispatches an async autobuild. Sync because the
#: production target (:func:`dispatch_autobuild_async`) returns the
#: handle synchronously after launching the async task.
AutobuildDispatcher = Callable[..., Any]


# ---------------------------------------------------------------------------
# Supervisor
# ---------------------------------------------------------------------------


@dataclass
class Supervisor:
    """Reasoning-loop supervisor for the FEAT-FORGE-007 Mode A pipeline.

    The supervisor is a *composition* over the guards and dispatchers
    declared in Waves 2 and 3 of FEAT-FORGE-007. It owns no mutable
    per-build state — every dependency is injected at construction, and
    every public method takes ``build_id`` explicitly so the same
    instance is safe to use across concurrent builds.

    Attributes:
        ordering_guard: TASK-MAG7-003 stage-ordering guard.
        per_feature_sequencer: TASK-MAG7-005 per-feature sequencer.
        constitutional_guard: TASK-MAG7-004 constitutional guard.
        state_reader: FEAT-FORGE-001 state-machine reader.
        ordering_stage_log_reader: Reader for the ordering guard. Same
            ``stage_log`` table as ``per_feature_stage_log_reader``;
            different read shapes (per the two reader Protocols).
        per_feature_stage_log_reader: Reader for the per-feature
            sequencer.
        async_task_reader: Reader for the per-feature sequencer's live
            ``async_tasks`` channel.
        reasoning_model: Reasoning-model port.
        turn_recorder: Per-turn audit-row recorder.
        specialist_dispatcher: Async callable wrapping
            :func:`dispatch_specialist_stage`.
        subprocess_dispatcher: Async callable wrapping
            :func:`dispatch_subprocess_stage`.
        autobuild_dispatcher: Sync callable wrapping
            :func:`dispatch_autobuild_async`.
        pr_review_gate: FEAT-FORGE-004 gate surface.
        stage_hints: Optional per-stage forward-propagation hints
            mapping (TASK-MAG7-002). Defaults to empty.
    """

    ordering_guard: StageOrderingGuard
    per_feature_sequencer: PerFeatureLoopSequencer
    constitutional_guard: ConstitutionalGuard
    state_reader: StateMachineReader
    ordering_stage_log_reader: OrderingStageLogReader
    per_feature_stage_log_reader: PerFeatureStageLogReader
    async_task_reader: PerFeatureAsyncTaskReader
    reasoning_model: ReasoningModelPort
    turn_recorder: StageLogTurnRecorder
    specialist_dispatcher: SpecialistDispatcher
    subprocess_dispatcher: SubprocessDispatcher
    autobuild_dispatcher: AutobuildDispatcher
    pr_review_gate: PRReviewGate
    stage_hints: Mapping[StageClass, str] = field(default_factory=dict)

    # Stage groupings — pre-computed once so per-turn routing is a
    # single dict lookup rather than a chain of ``in`` checks.
    _SPECIALIST_STAGES: frozenset[StageClass] = field(
        default=frozenset({StageClass.PRODUCT_OWNER, StageClass.ARCHITECT}),
        init=False,
        repr=False,
    )
    _SUBPROCESS_STAGES: frozenset[StageClass] = field(
        default=frozenset(
            {
                StageClass.SYSTEM_ARCH,
                StageClass.SYSTEM_DESIGN,
                StageClass.FEATURE_SPEC,
                StageClass.FEATURE_PLAN,
            }
        ),
        init=False,
        repr=False,
    )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def next_turn(self, build_id: str) -> TurnReport:
        """Execute one supervisor reasoning turn for ``build_id``.

        This is the entry point exercised by the supervisor's outer
        loop. The method is async because three of the four dispatch
        targets are async; the per-feature autobuild and PR-review
        paths are sync but we keep the surface uniform.

        Sequence:

        1. Read the build state. Terminal → return ``TERMINAL``.
        2. Compute ``permitted_stages`` via the ordering guard.
           Empty + non-terminal → return ``WAITING``.
        3. Ask the reasoning model to pick one entry from the
           permitted set. ``None`` → return ``NO_OP``.
        4. Validate the choice is in the permitted set. Out-of-band
           → ``REFUSED_OUT_OF_BAND`` + structured warning log.
        5. For ``AUTOBUILD``: apply the per-feature sequencer.
           Refused → ``WAITING_PRIOR_AUTOBUILD``.
        6. For ``PULL_REQUEST_REVIEW``: apply the constitutional
           guard's ``veto_auto_approve`` to the model's auto-approve
           flag. Refused → ``REFUSED_CONSTITUTIONAL``.
        7. Route to the correct dispatcher and capture the result.
        8. Record a per-turn ``stage_log`` row regardless of outcome.

        Args:
            build_id: Build identifier the turn is for. Each
                ``next_turn`` call is independent — concurrent builds
                supply different ``build_id`` values and never share
                mutable supervisor state.

        Returns:
            :class:`TurnReport` carrying the outcome plus context.

        Raises:
            TerminalStateError: Never raised by this method; declared
                in the public surface so callers that want a hard-fail
                signal can opt in by checking ``outcome``.
        """
        # 1. State read.
        build_state = self.state_reader.get_build_state(build_id)
        if build_state.is_terminal:
            report = TurnReport(
                outcome=TurnOutcome.TERMINAL,
                build_id=build_id,
                permitted_stages=frozenset(),
                rationale=(
                    f"build {build_id} is terminal (state={build_state.value}); "
                    "supervisor will not produce further turns"
                ),
            )
            self._record_safe(report)
            return report

        # 2. Permitted set.
        permitted_stages = frozenset(
            self.ordering_guard.next_dispatchable(
                build_id, self.ordering_stage_log_reader
            )
        )
        if not permitted_stages:
            report = TurnReport(
                outcome=TurnOutcome.WAITING,
                build_id=build_id,
                permitted_stages=permitted_stages,
                rationale=(
                    "no dispatchable stages and build is non-terminal; "
                    "waiting on external resume signal (likely an approval "
                    "response — FEAT-FORGE-004)"
                ),
            )
            self._record_safe(report)
            return report

        # 3. Reasoning model choice.
        feature_catalogue = tuple(
            self.ordering_stage_log_reader.feature_catalogue(build_id)
        )
        choice = self.reasoning_model.choose_dispatch(
            build_id=build_id,
            build_state=build_state,
            permitted_stages=permitted_stages,
            stage_hints=dict(self.stage_hints),
            feature_catalogue=feature_catalogue,
        )
        if choice is None:
            report = TurnReport(
                outcome=TurnOutcome.NO_OP,
                build_id=build_id,
                permitted_stages=permitted_stages,
                rationale="reasoning model declined to choose a dispatch",
            )
            self._record_safe(report)
            return report

        # 4. Out-of-band refusal — executor layer enforcement of the
        #    permitted set. ADR-ARCH-026 belt-and-braces.
        if choice.stage not in permitted_stages:
            warning_msg = (
                "supervisor.next_turn: reasoning model picked stage "
                f"{choice.stage.value!r} which is OUTSIDE the permitted set "
                f"{sorted(s.value for s in permitted_stages)} for build_id="
                f"{build_id!r}; refusing dispatch (ADR-ARCH-026 "
                "belt-and-braces enforcement)"
            )
            logger.warning(warning_msg)
            report = TurnReport(
                outcome=TurnOutcome.REFUSED_OUT_OF_BAND,
                build_id=build_id,
                permitted_stages=permitted_stages,
                chosen_stage=choice.stage,
                chosen_feature_id=choice.feature_id,
                rationale=warning_msg,
            )
            self._record_safe(report)
            return report

        # 5. Per-feature sequencer for AUTOBUILD.
        if choice.stage is StageClass.AUTOBUILD:
            if choice.feature_id is None:
                # AUTOBUILD without feature_id is a programming error in
                # the model wiring; we refuse rather than dispatch with
                # unscoped feature_id (same stance the dispatchers take).
                refusal = (
                    "AUTOBUILD chosen without feature_id; refusing rather "
                    "than risk cross-feature dispatch attribution"
                )
                logger.warning(
                    "supervisor.next_turn: %s build_id=%s",
                    refusal,
                    build_id,
                )
                report = TurnReport(
                    outcome=TurnOutcome.REFUSED_OUT_OF_BAND,
                    build_id=build_id,
                    permitted_stages=permitted_stages,
                    chosen_stage=choice.stage,
                    chosen_feature_id=None,
                    rationale=refusal,
                )
                self._record_safe(report)
                return report

            may_dispatch = self.per_feature_sequencer.may_start_autobuild(
                build_id=build_id,
                feature_id=choice.feature_id,
                stage_log_reader=self.per_feature_stage_log_reader,
                async_task_reader=self.async_task_reader,
            )
            if not may_dispatch:
                report = TurnReport(
                    outcome=TurnOutcome.WAITING_PRIOR_AUTOBUILD,
                    build_id=build_id,
                    permitted_stages=permitted_stages,
                    chosen_stage=choice.stage,
                    chosen_feature_id=choice.feature_id,
                    rationale=(
                        "per-feature sequencer refused: a sibling feature's "
                        "autobuild is still in flight on this build "
                        "(FEAT-FORGE-007 ASSUM-006)"
                    ),
                )
                self._record_safe(report)
                return report

        # 6. Constitutional guard for PULL_REQUEST_REVIEW.
        gate_decision: AutoApproveDecision | None = None
        if choice.stage is StageClass.PULL_REQUEST_REVIEW and choice.auto_approve:
            gate_decision = self.constitutional_guard.veto_auto_approve(
                choice.stage
            )
            if gate_decision.verdict is AutoApproveVerdict.REFUSED:
                logger.warning(
                    "supervisor.next_turn: constitutional veto on auto-approve "
                    "for stage=%s build_id=%s — %s",
                    choice.stage.value,
                    build_id,
                    gate_decision.rationale,
                )
                report = TurnReport(
                    outcome=TurnOutcome.REFUSED_CONSTITUTIONAL,
                    build_id=build_id,
                    permitted_stages=permitted_stages,
                    chosen_stage=choice.stage,
                    chosen_feature_id=choice.feature_id,
                    rationale=gate_decision.rationale,
                    gate_decision=gate_decision,
                )
                self._record_safe(report)
                return report

        # 7. Route to the dispatcher.
        dispatch_result = await self._dispatch(
            build_id=build_id, choice=choice
        )

        # 8. Successful dispatch — assemble the report.
        report = TurnReport(
            outcome=TurnOutcome.DISPATCHED,
            build_id=build_id,
            permitted_stages=permitted_stages,
            chosen_stage=choice.stage,
            chosen_feature_id=choice.feature_id,
            rationale=choice.rationale or self._default_rationale(choice),
            dispatch_result=dispatch_result,
            gate_decision=gate_decision,
        )
        self._record_safe(report)
        return report

    # ------------------------------------------------------------------
    # Internal: dispatch routing
    # ------------------------------------------------------------------

    async def _dispatch(
        self,
        *,
        build_id: str,
        choice: DispatchChoice,
    ) -> Any:
        """Route ``choice`` to the correct dispatcher.

        The four routing branches mirror the AC table verbatim. Each
        branch invokes the injected dispatcher callable; the supervisor
        does not interpret the result — the gating layer
        (FEAT-FORGE-004) does. We thread ``build_id``, ``feature_id``
        (where applicable), and the model's free-form rationale so the
        downstream artefacts have the per-turn audit context.
        """
        stage = choice.stage

        if stage in self._SPECIALIST_STAGES:
            return await self.specialist_dispatcher(
                stage=stage,
                build_id=build_id,
                feature_id=choice.feature_id,
                rationale=choice.rationale,
            )

        if stage in self._SUBPROCESS_STAGES:
            # Per-feature stages must carry feature_id.
            feature_id = choice.feature_id
            if stage in PER_FEATURE_STAGES and feature_id is None:
                # Same stance the subprocess dispatcher takes: refuse
                # rather than dispatch with unscoped feature_id. We
                # surface this as a dispatch result rather than as
                # WAITING because the executor layer already permitted
                # the stage; the missing feature_id is a contract
                # violation between the model and the supervisor.
                logger.warning(
                    "supervisor._dispatch: per-feature subprocess stage %s "
                    "chosen without feature_id; refusing dispatch "
                    "(build_id=%s)",
                    stage.value,
                    build_id,
                )
                return {
                    "status": "refused",
                    "reason": (
                        f"per-feature subprocess stage {stage.value!r} "
                        "dispatched without feature_id"
                    ),
                }
            return await self.subprocess_dispatcher(
                stage=stage,
                build_id=build_id,
                feature_id=feature_id,
                rationale=choice.rationale,
            )

        if stage is StageClass.AUTOBUILD:
            # feature_id presence is already enforced upstream (step 5
            # of next_turn). The autobuild dispatcher is sync — it
            # returns the launched task's handle synchronously.
            assert choice.feature_id is not None
            return self.autobuild_dispatcher(
                build_id=build_id,
                feature_id=choice.feature_id,
                rationale=choice.rationale,
            )

        if stage is StageClass.PULL_REQUEST_REVIEW:
            # PR-review uses the FEAT-FORGE-004 gate surface, not a
            # dispatcher. Auto-approve has already been sanitised by
            # the constitutional guard; we forward whatever flag
            # survived that gate.
            return self.pr_review_gate.submit_decision(
                build_id=build_id,
                feature_id=choice.feature_id or "",
                auto_approve=choice.auto_approve,
                rationale=choice.rationale,
            )

        # Unreachable — every StageClass member is covered above.
        # We surface this as a TypeError so a future enum addition
        # without a routing branch fails loudly at runtime.
        raise TypeError(
            f"Supervisor._dispatch: no routing for stage {stage!r}; "
            "this is a bug — every StageClass needs a dispatcher branch"
        )

    # ------------------------------------------------------------------
    # Internal: rationale + recording helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _default_rationale(choice: DispatchChoice) -> str:
        """Return a stock rationale when the model omits one.

        Keeps the audit trail intelligible even if the reasoning model
        forgets to populate :attr:`DispatchChoice.rationale` — which it
        sometimes does on retry paths.
        """
        scope = (
            f" feature_id={choice.feature_id!r}"
            if choice.feature_id is not None
            else ""
        )
        return f"dispatch {choice.stage.value}{scope}"

    def _record_safe(self, report: TurnReport) -> None:
        """Persist ``report`` via :class:`StageLogTurnRecorder`; swallow errors.

        The recorder writing to SQLite must never block a turn from
        returning. We log at ``ERROR`` if the write itself raises and
        continue — the in-memory :class:`TurnReport` is the
        authoritative outcome of this method, the recorder is the
        durable side-effect.
        """
        try:
            verdict = (
                report.gate_decision.verdict.value
                if report.gate_decision is not None
                else None
            )
            self.turn_recorder.record_turn(
                build_id=report.build_id,
                outcome=report.outcome,
                permitted_stages=report.permitted_stages,
                chosen_stage=report.chosen_stage,
                chosen_feature_id=report.chosen_feature_id,
                rationale=report.rationale,
                gate_verdict=verdict,
            )
        except Exception as exc:  # noqa: BLE001 — universal error contract
            logger.error(
                "supervisor.next_turn: turn_recorder raised %s: %s; "
                "build_id=%s outcome=%s — row LOST but report still returned",
                type(exc).__name__,
                exc,
                report.build_id,
                report.outcome.value,
            )
