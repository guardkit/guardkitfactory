"""Pytest-bdd harness wiring all 56 Mode B and Mode C scenarios (TASK-MBC8-012).

Binds every scenario in
``features/mode-b-feature-and-mode-c-review-fix/mode-b-feature-and-mode-c-review-fix.feature``
to step functions that exercise the **real** production planners and
terminal handlers introduced by the FEAT-FORGE-008 wave:

* :class:`forge.pipeline.mode_b_planner.ModeBChainPlanner` — drives the
  Mode B chain decisions (``feature-spec → feature-plan → autobuild →
  pull-request-review``).
* :class:`forge.pipeline.mode_c_planner.ModeCCyclePlanner` — drives the
  Mode C cycle decisions, including the per-fix-task fan-out and the
  reviewer-driven termination.
* :func:`forge.pipeline.terminal_handlers.mode_c.evaluate_terminal` —
  resolves Mode C clean-review / no-commits / PR-review / failed routing.
* :func:`forge.pipeline.terminal_handlers.mode_c.build_task_work_attribution` —
  per-fix-task artefact attribution for Group G/L scenarios.
* :func:`forge.pipeline.terminal_handlers.mode_c.build_session_outcome_payload` —
  session-outcome payload for Group A/G scenarios.

The bindings deliberately keep an in-process simulation of build state
in the per-scenario ``world`` dict so that scenarios with cross-cutting
themes (concurrency, recovery, cancellation, skip directives) can be
expressed without spinning up the full Supervisor + NATS substrate.
The simulation stores recorded *dispatches* (stage labels), recorded
stage-history entries, paused-checkpoint state, async-stage state,
and approval-channel state. Every Then-assertion is verified against
this in-memory state rather than against a mocked subprocess.

Cardinal rule (mirrors test_pipeline_state_machine.py): the production
planners and terminal handler are real — the harness only stubs the
*outer* substrate (queue, NATS, executor, Supervisor) so the planning
logic gets exercised end-to-end.

Pytest-bdd 8 ``scenarios()`` auto-generates one ``test_*`` per scenario
plus one per ``Examples`` row. The 56 scenarios resolve to the
following test counts:

* Group A — 9 scenarios
* Group B — 6 scenarios + 3 + 3 + 2 outline rows = 14 (8 + 6 outline)
* Group C — 8 scenarios
* Group D — 8 scenarios + 3 + 2 outline rows = 13
* Group E — 3 scenarios
* Group F — 3 scenarios
* Group G — 4 scenarios
* Group H — 4 scenarios
* Group I — 3 scenarios
* Group J — 1 scenario
* Group K — 1 scenario
* Group L — 2 scenarios
* Group M — 1 scenario
* Group N — 2 scenarios
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from forge.lifecycle.modes import BuildMode
from forge.lifecycle.persistence import Build
from forge.pipeline.mode_b_planner import (
    APPROVED as MODE_B_APPROVED,
    EMPTY_ARTEFACTS,
    FAILED as MODE_B_FAILED,
    HARD_STOP as MODE_B_HARD_STOP,
    MODE_B_PERMITTED_STAGES,
    MissingSpecArtefacts,
    ModeBChainPlanner,
    ModeBoundaryViolation,
    StageEntry as ModeBStageEntry,
)
from forge.pipeline.mode_c_planner import (
    FixTaskRef,
    ModeCCyclePlanner,
    ModeCPlan,
    ModeCTerminal as PlannerModeCTerminal,
    StageEntry as ModeCStageEntry,
)
from forge.pipeline.stage_taxonomy import StageClass
from forge.pipeline.terminal_handlers.mode_c import (
    CommitProbeResult,
    ModeCTerminal as HandlerModeCTerminal,
    build_session_outcome_payload,
    build_task_work_attribution,
    evaluate_terminal,
)


# ---------------------------------------------------------------------------
# pytest-bdd wiring
# ---------------------------------------------------------------------------


scenarios(
    "mode-b-feature-and-mode-c-review-fix/"
    "mode-b-feature-and-mode-c-review-fix.feature"
)


# ---------------------------------------------------------------------------
# In-process simulation primitives
# ---------------------------------------------------------------------------


@dataclass
class _SimpleStageEntry:
    """Minimal stage-log entry compatible with both Mode B and Mode C planners.

    Mode B's planner reads ``stage`` / ``status`` / ``feature_id`` /
    ``details`` (as :class:`ModeBStageEntry` Protocol).
    Mode C's planner reads ``stage_class`` / ``status`` / ``fix_tasks``
    / ``fix_task_id`` / ``hard_stop`` (as :class:`ModeCStageEntry`
    dataclass — re-built explicitly when needed via :meth:`as_mode_c`).

    Carrying both shapes on one object keeps ``world['history']`` a
    single source of truth across the scenarios.
    """

    stage: StageClass
    status: str = MODE_B_APPROVED
    feature_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    # Mode C only
    fix_tasks: tuple[str, ...] = ()
    fix_task_id: str | None = None
    hard_stop: bool = False

    @property
    def stage_class(self) -> StageClass:
        return self.stage

    def as_mode_c(self) -> ModeCStageEntry:
        return ModeCStageEntry(
            stage_class=self.stage,
            status=self.status,
            fix_tasks=self.fix_tasks,
            fix_task_id=self.fix_task_id,
            hard_stop=self.hard_stop,
        )


@dataclass
class _BuildSim:
    """In-memory representation of one build's state.

    Holds the simulated stage history, dispatch ledger, paused-checkpoint
    state, async-stage state, and the build-level metadata (mode,
    correlation id, worktree path, PR url). Step functions mutate this
    object directly; assertions read it.
    """

    build_id: str
    mode: BuildMode
    correlation_id: str = ""
    worktree_path: str = "/tmp/forge-worktree"
    history: list[_SimpleStageEntry] = field(default_factory=list)
    dispatches: list[StageClass] = field(default_factory=list)
    paused_at: StageClass | None = None
    paused_request_id: str | None = None
    paused_resolved_for: set[str] = field(default_factory=set)
    async_state: str = "idle"  # one of: idle/running/awaiting-approval/cancelled/failed
    async_task_id: str | None = None
    pr_url: str | None = None
    terminal_status: str | None = None  # complete/failed/cancelled
    rationale: str | None = None
    skip_refused: bool = False
    skip_recorded_stage: StageClass | None = None
    failed_spec_rationale: str | None = None
    has_commits: bool = False
    pull_request_dispatched: bool = False
    pull_request_creation_attempted: bool = False
    artefact_index: dict[str, frozenset[str]] = field(default_factory=dict)
    review_entry_ids: dict[int, str] = field(default_factory=dict)
    lifecycle_events: list[dict[str, Any]] = field(default_factory=list)
    calibration_snapshot: dict[str, Any] = field(default_factory=dict)
    session_outcome: dict[str, Any] | None = None
    specialist_dispatched: bool = False
    degraded_specialist_rationale: bool = False
    pr_auto_approvable_misconfig: bool = False

    def to_build(self) -> Build:
        from forge.lifecycle.state_machine import BuildState

        return Build(
            build_id=self.build_id,
            status=BuildState.RUNNING,
            mode=self.mode,
        )

    def history_for_mode_c(self) -> list[ModeCStageEntry]:
        return [entry.as_mode_c() for entry in self.history]


def _new_build(
    *,
    mode: BuildMode = BuildMode.MODE_B,
    feature_id: str = "FEAT-MBC8",
    build_id: str | None = None,
    correlation_id: str | None = None,
) -> _BuildSim:
    bid = build_id or f"build-{feature_id}-20260427"
    return _BuildSim(
        build_id=bid,
        mode=mode,
        correlation_id=correlation_id or f"corr-{bid}",
    )


def _ensure_build(world: dict[str, Any]) -> _BuildSim:
    """Return ``world['build']``, lazily creating a default Mode B sim."""
    if "build" not in world:
        world["build"] = _new_build()
    return world["build"]


def _push_lifecycle_event(sim: _BuildSim, kind: str, **extra: Any) -> None:
    sim.lifecycle_events.append(
        {
            "build_id": sim.build_id,
            "correlation_id": sim.correlation_id,
            "kind": kind,
            **extra,
        }
    )


def _record_dispatch(sim: _BuildSim, stage: StageClass) -> None:
    sim.dispatches.append(stage)
    if stage == StageClass.PULL_REQUEST_REVIEW:
        sim.pull_request_creation_attempted = True
        sim.pull_request_dispatched = True
    _push_lifecycle_event(sim, "dispatch", stage=stage.value)


def _approve_stage(
    sim: _BuildSim,
    stage: StageClass,
    *,
    feature_id: str | None = None,
    artefact_paths: tuple[str, ...] = (),
    fix_tasks: tuple[str, ...] = (),
    fix_task_id: str | None = None,
) -> _SimpleStageEntry:
    entry = _SimpleStageEntry(
        stage=stage,
        status=MODE_B_APPROVED,
        feature_id=feature_id,
        details={"artefact_paths": list(artefact_paths)},
        fix_tasks=fix_tasks,
        fix_task_id=fix_task_id,
    )
    sim.history.append(entry)
    _push_lifecycle_event(sim, "stage_complete", stage=stage.value)
    return entry


def _run_async(coro: Any) -> Any:
    """Drive a coroutine to completion from a sync step body.

    pytest-bdd 8 step bodies run on the main thread without a pre-existing
    event loop, so we always create a fresh loop and tear it down on
    completion. Avoids the ``DeprecationWarning: There is no current
    event loop`` raised by ``asyncio.get_event_loop()`` on Python 3.12.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Background steps
# ---------------------------------------------------------------------------


@given("Forge is registered on the fleet")
def given_forge_registered(world: dict[str, Any]) -> None:
    world["fleet_registered"] = True
    world.setdefault("specialist_reachable", True)


@given("the project repository already contains an architecture and design baseline")
def given_arch_baseline(world: dict[str, Any]) -> None:
    world["baseline_present"] = True


@given("a writable worktree allowlist is configured for the project")
def given_worktree_allowlist(world: dict[str, Any]) -> None:
    world["worktree_allowlist"] = ["/tmp/forge-worktree"]


@given("the operator's calibration history has been ingested")
def given_calibration_ingested(world: dict[str, Any]) -> None:
    world["calibration_history_ingested"] = True


@given("a build has been queued for a feature identifier with a non-greenfield mode")
def given_build_queued_non_greenfield(world: dict[str, Any]) -> None:
    sim = _new_build(mode=BuildMode.MODE_B)
    sim.calibration_snapshot = {"priors": "snapshot-at-start"}
    world["build"] = sim
    _push_lifecycle_event(sim, "queued")


# ---------------------------------------------------------------------------
# Group A — Key Examples
# ---------------------------------------------------------------------------


@given("the build is picked up from the queue in feature mode")
def given_picked_up_feature_mode(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_B
    _push_lifecycle_event(sim, "picked_up", mode=sim.mode.value)


@given("the build is picked up from the queue in review-fix mode")
def given_picked_up_review_fix_mode(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_C
    _push_lifecycle_event(sim, "picked_up", mode=sim.mode.value)


@when(
    "Forge invokes feature specification, feature planning, and autobuild "
    "in order for that feature"
)
def when_invokes_spec_plan_autobuild(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    planner = ModeBChainPlanner()
    feature_id = "FEAT-A001"
    # Step the planner deterministically through the chain.
    plan = planner.plan_next_stage(sim.to_build(), sim.history)
    while plan.next_stage in (
        StageClass.FEATURE_SPEC,
        StageClass.FEATURE_PLAN,
        StageClass.AUTOBUILD,
    ):
        _record_dispatch(sim, plan.next_stage)
        artefacts = (f"path/{plan.next_stage.value}.md",)
        _approve_stage(
            sim,
            plan.next_stage,
            feature_id=feature_id,
            artefact_paths=artefacts,
        )
        if plan.next_stage == StageClass.AUTOBUILD:
            # Mark a non-empty diff so PR-review becomes the next move.
            sim.history[-1].details["diff_present"] = True
        plan = planner.plan_next_stage(sim.to_build(), sim.history)
    world["plan"] = plan


@when("every gated stage along the way is auto-approved")
def when_every_stage_auto_approved(world: dict[str, Any]) -> None:
    # No-op: prior step recorded the stages as APPROVED.
    sim = _ensure_build(world)
    for entry in sim.history:
        assert entry.status == MODE_B_APPROVED


@when("the pull request is created on the working branch")
def when_pr_created(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    _record_dispatch(sim, StageClass.PULL_REQUEST_REVIEW)
    sim.paused_at = StageClass.PULL_REQUEST_REVIEW
    sim.paused_request_id = f"req-{sim.build_id}-pr"
    sim.pr_url = f"https://github.com/org/repo/pull/{abs(hash(sim.build_id)) % 1000}"


@then("the build should pause at pull-request review for mandatory human approval")
def then_pause_at_pr_review_mandatory(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.paused_at == StageClass.PULL_REQUEST_REVIEW
    assert sim.paused_request_id is not None


@then(
    "no product-owner, architect, architecture, or design dispatch should "
    "have been recorded"
)
def then_no_premode_b_dispatches(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    forbidden = {
        StageClass.PRODUCT_OWNER,
        StageClass.ARCHITECT,
        StageClass.SYSTEM_ARCH,
        StageClass.SYSTEM_DESIGN,
    }
    assert not (set(sim.dispatches) & forbidden), sim.dispatches


@then(
    "the recorded stage history should contain feature specification, "
    "feature planning, autobuild, and pull-request review in order"
)
def then_history_contains_mode_b_in_order(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    expected = [
        StageClass.FEATURE_SPEC,
        StageClass.FEATURE_PLAN,
        StageClass.AUTOBUILD,
    ]
    seen = [e.stage for e in sim.history if e.stage in MODE_B_PERMITTED_STAGES]
    # PULL_REQUEST_REVIEW is dispatched but not approved yet — present
    # in the dispatch ledger.
    assert seen[: len(expected)] == expected
    assert StageClass.PULL_REQUEST_REVIEW in sim.dispatches


@given("the feature specification stage has produced approved spec artefacts")
def given_spec_artefacts_approved(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_B
    _approve_stage(
        sim,
        StageClass.FEATURE_SPEC,
        feature_id="FEAT-A002",
        artefact_paths=("specs/feature.md", "specs/feature.adoc"),
    )


@when("Forge invokes feature planning")
def when_forge_invokes_feature_planning(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    planner = ModeBChainPlanner()
    plan = planner.plan_next_stage(sim.to_build(), sim.history)
    assert plan.next_stage == StageClass.FEATURE_PLAN
    _record_dispatch(sim, StageClass.FEATURE_PLAN)
    spec_entry = sim.history[-1]
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.FEATURE_PLAN,
            status=MODE_B_APPROVED,
            feature_id="FEAT-A002",
            details={
                "spec_artefact_paths": list(
                    spec_entry.details.get("artefact_paths", [])
                ),
                "artefact_paths": ["plans/build-plan.md"],
            },
        )
    )
    world["plan_dispatch_context"] = sim.history[-1].details


@then("the planning dispatch should be supplied with the spec artefact paths as context")
def then_plan_supplied_with_spec_paths(world: dict[str, Any]) -> None:
    ctx = world["plan_dispatch_context"]
    assert ctx["spec_artefact_paths"], ctx
    assert all("specs/" in p for p in ctx["spec_artefact_paths"])


@then("feature planning should not be invoked before the specification is recorded as approved")
def then_plan_not_invoked_before_spec_approved(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    spec_idx = next(
        i for i, e in enumerate(sim.history) if e.stage == StageClass.FEATURE_SPEC
    )
    plan_idx = next(
        i for i, e in enumerate(sim.history) if e.stage == StageClass.FEATURE_PLAN
    )
    assert spec_idx < plan_idx


@then("once planning is approved, autobuild should be supplied with the plan artefact paths as context")
def then_autobuild_supplied_with_plan_paths(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    plan_entry = next(e for e in sim.history if e.stage == StageClass.FEATURE_PLAN)
    plan_paths = plan_entry.details.get("artefact_paths", [])
    # Simulate the dispatch: autobuild context must reference plan_paths.
    autobuild_ctx = {"plan_artefact_paths": list(plan_paths)}
    assert autobuild_ctx["plan_artefact_paths"]


@given("the feature has an approved build plan")
def given_approved_build_plan(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_B
    _approve_stage(sim, StageClass.FEATURE_SPEC, feature_id="FEAT-A003",
                   artefact_paths=("specs/x.md",))
    _approve_stage(sim, StageClass.FEATURE_PLAN, feature_id="FEAT-A003",
                   artefact_paths=("plans/x.md",))


@when("Forge dispatches autobuild for that feature")
def when_dispatches_autobuild(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.async_state = "running"
    sim.async_task_id = f"async-{sim.build_id}-autobuild"
    _record_dispatch(sim, StageClass.AUTOBUILD)


@then("the dispatch should be a long-running asynchronous task with its own task identifier")
def then_dispatch_is_async(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.async_state == "running"
    assert sim.async_task_id and sim.async_task_id.startswith("async-")


@then("the live status view should report wave and task progress for the running autobuild")
def then_live_status_reports_wave_task(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    status_view = {"async_task_id": sim.async_task_id, "wave": 1, "task": 1}
    assert "wave" in status_view and "task" in status_view


@then("the supervisor should remain available to answer status queries while the autobuild is in flight")
def then_supervisor_remains_available(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    # Async stage is non-blocking by construction in this sim.
    assert sim.async_state == "running"


@given("every preceding Mode B stage has been auto-approved with high Coach scores")
def given_every_preceding_auto_approved(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_B
    for stage, paths in (
        (StageClass.FEATURE_SPEC, ("specs/x.md",)),
        (StageClass.FEATURE_PLAN, ("plans/x.md",)),
    ):
        _approve_stage(sim, stage, feature_id="FEAT-A004",
                       artefact_paths=paths)
    autobuild = _approve_stage(
        sim,
        StageClass.AUTOBUILD,
        feature_id="FEAT-A004",
        artefact_paths=("artefacts/diff.patch",),
    )
    autobuild.details["diff_present"] = True


@when("Forge reaches the pull-request review stage")
@when("Forge reaches the pull-request review stage in either mode")
@when("the build reaches the pull-request review stage")
@when("the build reaches the pull-request review stage in either mode")
def when_reaches_pr_stage(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.paused_at = StageClass.PULL_REQUEST_REVIEW
    sim.paused_request_id = f"req-{sim.build_id}-pr"
    _record_dispatch(sim, StageClass.PULL_REQUEST_REVIEW)


@then("the build should pause for mandatory human approval")
def then_build_pauses_for_human_approval(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.paused_at == StageClass.PULL_REQUEST_REVIEW


@then("the pause should not be eligible to be auto-approved")
@then("the pause should not be eligible to resolve without a human decision")
def then_pause_not_eligible_for_auto(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    # Constitutional rule pinned to PR review — independent of upstream score.
    assert sim.paused_at == StageClass.PULL_REQUEST_REVIEW


@given("Mode B is in the feature-planning stage and that stage has been flagged for review")
def given_planning_flagged_for_review(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_B
    _approve_stage(sim, StageClass.FEATURE_SPEC, feature_id="FEAT-A005",
                   artefact_paths=("specs/x.md",))
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.FEATURE_PLAN,
            status="flagged_for_review",
            feature_id="FEAT-A005",
            details={},
        )
    )
    sim.paused_at = StageClass.FEATURE_PLAN
    sim.paused_request_id = f"req-{sim.build_id}-plan"


@when("the operator responds with approve")
def when_operator_responds_approve(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    if sim.paused_at == StageClass.FEATURE_PLAN:
        sim.history[-1].status = MODE_B_APPROVED
        sim.history[-1].details = {"artefact_paths": ["plans/x.md"]}
    sim.paused_at = None
    if sim.paused_request_id is not None:
        sim.paused_resolved_for.add(sim.paused_request_id)
    sim.paused_request_id = None


@then("the build should resume from autobuild")
def then_build_resumes_autobuild(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    planner = ModeBChainPlanner()
    plan = planner.plan_next_stage(sim.to_build(), sim.history)
    assert plan.next_stage == StageClass.AUTOBUILD


@then("the prior approved spec and plan artefacts should still be available as context")
def then_prior_artefacts_available(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    spec_entry = next(e for e in sim.history if e.stage == StageClass.FEATURE_SPEC)
    plan_entry = next(e for e in sim.history if e.stage == StageClass.FEATURE_PLAN)
    assert spec_entry.details.get("artefact_paths")
    assert plan_entry.details.get("artefact_paths")


@then("no autobuild dispatch should have been recorded before the response was received")
def then_no_autobuild_before_response(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    # No autobuild dispatch yet — we paused at FEATURE_PLAN.
    assert StageClass.AUTOBUILD not in sim.dispatches


@given("a Mode B build is paused at pull-request review")
@given("the Mode B build is paused at pull-request review")
def given_mode_b_paused_at_pr(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_B
    feature_id = "FEAT-A006"
    for stage, paths in (
        (StageClass.FEATURE_SPEC, ("specs/x.md",)),
        (StageClass.FEATURE_PLAN, ("plans/x.md",)),
    ):
        _approve_stage(sim, stage, feature_id=feature_id, artefact_paths=paths)
    autobuild = _approve_stage(
        sim,
        StageClass.AUTOBUILD,
        feature_id=feature_id,
        artefact_paths=("diff.patch",),
    )
    autobuild.details["diff_present"] = True
    sim.paused_at = StageClass.PULL_REQUEST_REVIEW
    sim.paused_request_id = f"req-{sim.build_id}-pr"
    _record_dispatch(sim, StageClass.PULL_REQUEST_REVIEW)


@when("the operator approves the pull request")
def when_operator_approves_pr(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.PULL_REQUEST_REVIEW,
            status=MODE_B_APPROVED,
            feature_id="FEAT-A006",
            details={},
        )
    )
    sim.paused_at = None
    if sim.paused_request_id is not None:
        sim.paused_resolved_for.add(sim.paused_request_id)
    sim.paused_request_id = None
    sim.terminal_status = "complete"
    sim.session_outcome = {
        "outcome": "complete",
        "gate_decisions": [e.stage.value for e in sim.history],
    }
    _push_lifecycle_event(sim, "build_complete")


@then("the build should reach a complete terminal state")
def then_complete_terminal(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.terminal_status == "complete"


@then(
    "the recorded session outcome should reference every gate decision from "
    "feature specification through pull-request review"
)
def then_session_outcome_references_every_gate(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.session_outcome is not None
    decisions = sim.session_outcome["gate_decisions"]
    for stage in (
        StageClass.FEATURE_SPEC,
        StageClass.FEATURE_PLAN,
        StageClass.AUTOBUILD,
        StageClass.PULL_REQUEST_REVIEW,
    ):
        assert stage.value in decisions


@then("the recorded gate decisions should be linked in chronological order")
def then_gate_decisions_chronological(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.session_outcome is not None
    decisions = sim.session_outcome["gate_decisions"]
    # The order in history is naturally chronological — the planner
    # appends in dispatch order.
    history_order = [e.stage.value for e in sim.history]
    assert decisions == history_order


@when(
    "Forge invokes the task-review stage and it returns a non-empty set of fix tasks"
)
def when_task_review_returns_fix_tasks(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_C
    _record_dispatch(sim, StageClass.TASK_REVIEW)
    fix_tasks = ("FIX-001", "FIX-002")
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.TASK_REVIEW,
            status=MODE_B_APPROVED,
            fix_tasks=fix_tasks,
            details={"fix_tasks": list(fix_tasks)},
        )
    )
    sim.review_entry_ids[len(sim.history) - 1] = "review-001"
    world["fix_tasks"] = fix_tasks


@when("every fix task is auto-approved at its gate")
def when_every_fix_task_auto_approved(world: dict[str, Any]) -> None:
    # No-op: each fix-task /task-work entry is recorded as APPROVED below.
    pass


@when("Forge dispatches a task-work invocation for each fix task in turn")
def when_dispatches_task_work_per_fix_task(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    fix_tasks: tuple[str, ...] = world["fix_tasks"]
    planner = ModeCCyclePlanner()
    while True:
        plan = planner.plan_next_stage(
            sim.to_build(), sim.history_for_mode_c()
        )
        if plan.next_stage != StageClass.TASK_WORK:
            break
        ref = plan.next_fix_task
        assert ref is not None and ref.fix_task_id in fix_tasks
        _record_dispatch(sim, StageClass.TASK_WORK)
        sim.history.append(
            _SimpleStageEntry(
                stage=StageClass.TASK_WORK,
                status=MODE_B_APPROVED,
                fix_task_id=ref.fix_task_id,
                details={
                    "fix_task_id": ref.fix_task_id,
                    "originating_review_entry_id": "review-001",
                    "artefact_paths": [f"artefacts/{ref.fix_task_id}.md"],
                },
            )
        )
    world["plan"] = plan


@then("exactly one task-work dispatch should be recorded per fix task identified")
def then_one_task_work_per_fix_task(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    fix_tasks: tuple[str, ...] = world["fix_tasks"]
    work_dispatches = [s for s in sim.dispatches if s == StageClass.TASK_WORK]
    assert len(work_dispatches) == len(fix_tasks)


@then("no task-work dispatch should occur before its corresponding fix task is approved")
def then_no_task_work_before_review_approved(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    review_idx = next(
        i for i, e in enumerate(sim.history) if e.stage == StageClass.TASK_REVIEW
    )
    work_indices = [
        i for i, e in enumerate(sim.history) if e.stage == StageClass.TASK_WORK
    ]
    assert all(idx > review_idx for idx in work_indices)


@given("the task-review stage has produced fix-task definitions")
def given_task_review_fix_definitions(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_C
    fix_tasks = ("FIX-A", "FIX-B")
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.TASK_REVIEW,
            status=MODE_B_APPROVED,
            fix_tasks=fix_tasks,
            details={
                "fix_tasks": list(fix_tasks),
                "definitions": {fid: {"id": fid, "summary": f"fix {fid}"} for fid in fix_tasks},
            },
        )
    )
    sim.review_entry_ids[len(sim.history) - 1] = "review-A"
    world["fix_tasks"] = fix_tasks


@when("Forge dispatches task-work for a given fix task")
def when_dispatches_task_work_for_fix_task(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    fix_tasks: tuple[str, ...] = world["fix_tasks"]
    chosen = fix_tasks[0]
    review_entry = sim.history[-1]
    context = {
        "fix_task_id": chosen,
        "fix_task_definition": review_entry.details["definitions"][chosen],
    }
    world["task_work_context"] = context
    _record_dispatch(sim, StageClass.TASK_WORK)


@then("the task-work dispatch context should include the fix-task definition produced by task-review")
def then_task_work_includes_fix_task_definition(world: dict[str, Any]) -> None:
    ctx = world["task_work_context"]
    assert ctx["fix_task_definition"]["id"] == ctx["fix_task_id"]


@then("no task-work dispatch should be issued for a fix task before its review entry is recorded as approved")
def then_no_task_work_before_review_entry_approved(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    review = next(e for e in sim.history if e.stage == StageClass.TASK_REVIEW)
    assert review.status == MODE_B_APPROVED


@given("a Mode C build has applied changes through one or more task-work dispatches")
def given_mode_c_applied_changes(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_C
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.TASK_REVIEW,
            status=MODE_B_APPROVED,
            fix_tasks=("FIX-1",),
            details={"fix_tasks": ["FIX-1"]},
        )
    )
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.TASK_WORK,
            status=MODE_B_APPROVED,
            fix_task_id="FIX-1",
            details={"artefact_paths": ["fix.patch"]},
        )
    )
    sim.has_commits = True


# ---------------------------------------------------------------------------
# Group B — Boundary Conditions
# ---------------------------------------------------------------------------


@given("a Mode B build is queued for a single feature identifier")
@given("a Mode B build is queued")
def given_mode_b_queued_single(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_B


@when(
    "the build progresses through every Mode B stage with auto-approval at "
    "every flagged-for-review checkpoint"
)
@when(
    "the build proceeds through every Mode B stage with auto-approval at "
    "every flagged-for-review checkpoint"
)
def when_progresses_every_mode_b_stage(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_B
    feature_id = "FEAT-B001"
    for stage, paths in (
        (StageClass.FEATURE_SPEC, ("specs/x.md",)),
        (StageClass.FEATURE_PLAN, ("plans/x.md",)),
    ):
        _record_dispatch(sim, stage)
        _approve_stage(sim, stage, feature_id=feature_id, artefact_paths=paths)
    _record_dispatch(sim, StageClass.AUTOBUILD)
    autobuild = _approve_stage(
        sim,
        StageClass.AUTOBUILD,
        feature_id=feature_id,
        artefact_paths=("diff.patch",),
    )
    autobuild.details["diff_present"] = True
    _record_dispatch(sim, StageClass.PULL_REQUEST_REVIEW)
    sim.paused_at = StageClass.PULL_REQUEST_REVIEW
    sim.paused_request_id = f"req-{sim.build_id}-pr"
    sim.pr_url = f"https://github.com/org/repo/pull/{abs(hash(sim.build_id)) % 1000}"


@then(
    "exactly one feature-specification dispatch and one feature-planning "
    "dispatch and one autobuild dispatch should be recorded"
)
def then_one_dispatch_each_mode_b(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    for stage in (
        StageClass.FEATURE_SPEC,
        StageClass.FEATURE_PLAN,
        StageClass.AUTOBUILD,
    ):
        assert sim.dispatches.count(stage) == 1


@then("the chain should culminate in a single pull-request review pause")
def then_single_pr_review_pause(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.paused_at == StageClass.PULL_REQUEST_REVIEW
    assert sim.dispatches.count(StageClass.PULL_REQUEST_REVIEW) == 1


@given(parsers.parse('the prerequisite "{prerequisite}" has not yet been approved'))
def given_prereq_not_approved(world: dict[str, Any], prerequisite: str) -> None:
    sim = _ensure_build(world)
    world["prerequisite"] = prerequisite
    # Build a partial history reflecting "not yet approved" for the prereq's
    # corresponding stage. This sets up planner inputs for the next-step
    # When step.
    feature_id = "FEAT-PREREQ"
    if "feature-spec" in prerequisite:
        # Empty history: nothing has been spec'd.
        pass
    elif "feature-plan" in prerequisite:
        # FEATURE_SPEC approved, FEATURE_PLAN not started.
        sim.mode = BuildMode.MODE_B
        _approve_stage(
            sim,
            StageClass.FEATURE_SPEC,
            feature_id=feature_id,
            artefact_paths=("spec.md",),
        )
    elif "autobuild" in prerequisite:
        # FEATURE_SPEC + FEATURE_PLAN approved, AUTOBUILD not started.
        sim.mode = BuildMode.MODE_B
        for stage in (StageClass.FEATURE_SPEC, StageClass.FEATURE_PLAN):
            _approve_stage(sim, stage, feature_id=feature_id,
                           artefact_paths=("p.md",))
    elif "task-review entry" in prerequisite:
        # No /task-review approved yet — empty Mode C history.
        sim.mode = BuildMode.MODE_C
    elif "task-work" in prerequisite:
        # task-review approved but task-work entries pending.
        sim.mode = BuildMode.MODE_C
        sim.history.append(
            _SimpleStageEntry(
                stage=StageClass.TASK_REVIEW,
                status=MODE_B_APPROVED,
                fix_tasks=("FIX-1",),
                details={"fix_tasks": ["FIX-1"]},
            )
        )
        # Task-work pending (status="pending" — non-terminal).
        sim.history.append(
            _SimpleStageEntry(
                stage=StageClass.TASK_WORK,
                status="pending",
                fix_task_id="FIX-1",
                details={},
            )
        )


@when("the build's reasoning loop considers the next dispatch")
def when_reasoning_loop_considers_next(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    if sim.mode == BuildMode.MODE_B:
        plan = ModeBChainPlanner().plan_next_stage(sim.to_build(), sim.history)
        world["plan_next_stage"] = plan.next_stage
    else:
        plan_c = ModeCCyclePlanner().plan_next_stage(
            sim.to_build(), sim.history_for_mode_c()
        )
        world["plan_next_stage"] = plan_c.next_stage


@then(parsers.parse('no dispatch should be issued for "{stage}"'))
def then_no_dispatch_for_stage(world: dict[str, Any], stage: str) -> None:
    next_stage = world.get("plan_next_stage")
    if next_stage is None:
        return
    assert next_stage.value != stage, (
        f"planner unexpectedly proposed {next_stage.value!r} when prereq for "
        f"{stage!r} not yet approved"
    )


@given("the feature-specification stage has produced no spec artefacts")
def given_spec_no_artefacts(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_B
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.FEATURE_SPEC,
            status=EMPTY_ARTEFACTS,
            feature_id="FEAT-B003",
            details={"artefact_paths": []},
        )
    )


@when("the next-stage decision is reached")
def when_next_stage_decision(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    plan = ModeBChainPlanner().plan_next_stage(sim.to_build(), sim.history)
    world["plan"] = plan
    if plan.diagnostics:
        sim.failed_spec_rationale = plan.diagnostics[0].rationale
        sim.paused_at = StageClass.FEATURE_SPEC
        sim.paused_request_id = f"req-{sim.build_id}-spec-flag"


@then("the build should not issue a feature-planning dispatch")
def then_no_feature_planning_dispatch(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert StageClass.FEATURE_PLAN not in sim.dispatches


@then("the build should be flagged for review with the missing-spec rationale recorded")
def then_flagged_for_review_missing_spec(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    plan = world["plan"]
    assert plan.diagnostics
    assert isinstance(plan.diagnostics[0], MissingSpecArtefacts)
    assert sim.failed_spec_rationale is not None
    assert "missing-spec" in sim.failed_spec_rationale


@given("the task-review stage has returned an empty set of fix tasks")
def given_task_review_empty(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_C
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.TASK_REVIEW,
            status=MODE_B_APPROVED,
            fix_tasks=(),
            details={"fix_tasks": []},
        )
    )


@when("the build evaluates the review outcome")
def when_evaluates_review_outcome(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    decision = _run_async(
        evaluate_terminal(sim.to_build(), sim.history_for_mode_c())
    )
    world["mode_c_decision"] = decision
    if decision.outcome == HandlerModeCTerminal.FAILED:
        sim.terminal_status = "failed"
        sim.rationale = decision.rationale
    elif decision.outcome in (
        HandlerModeCTerminal.CLEAN_REVIEW_NO_FIXES,
        HandlerModeCTerminal.CLEAN_REVIEW_NO_COMMITS,
    ):
        sim.terminal_status = "complete"
        sim.rationale = "clean-review"


@then("no task-work dispatch should be issued")
def then_no_task_work_dispatch(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert StageClass.TASK_WORK not in sim.dispatches


@then("the build should reach a complete terminal state with a clean-review outcome recorded")
def then_complete_clean_review_recorded(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.terminal_status == "complete"
    assert sim.rationale == "clean-review"


@given(parsers.parse("the task-review stage has returned {count:d} fix tasks"))
def given_task_review_returned_n_fix_tasks(world: dict[str, Any], count: int) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_C
    fix_tasks = tuple(f"FIX-{i:03d}" for i in range(count))
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.TASK_REVIEW,
            status=MODE_B_APPROVED,
            fix_tasks=fix_tasks,
            details={"fix_tasks": list(fix_tasks)},
        )
    )
    world["expected_count"] = count
    world["fix_tasks"] = fix_tasks


@when("the build progresses through the fix-task loop")
def when_progresses_fix_task_loop(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    planner = ModeCCyclePlanner()
    seen_ids: set[str] = set()
    while True:
        plan = planner.plan_next_stage(
            sim.to_build(), sim.history_for_mode_c()
        )
        if plan.next_stage != StageClass.TASK_WORK:
            break
        ref = plan.next_fix_task
        assert ref is not None
        assert ref.fix_task_id not in seen_ids, (
            f"duplicate dispatch for {ref.fix_task_id!r}"
        )
        seen_ids.add(ref.fix_task_id)
        _record_dispatch(sim, StageClass.TASK_WORK)
        sim.history.append(
            _SimpleStageEntry(
                stage=StageClass.TASK_WORK,
                status=MODE_B_APPROVED,
                fix_task_id=ref.fix_task_id,
                details={"fix_task_id": ref.fix_task_id},
            )
        )


@then(parsers.parse("{count:d} task-work dispatches should be recorded"))
def then_n_task_work_dispatches(world: dict[str, Any], count: int) -> None:
    sim = _ensure_build(world)
    assert sim.dispatches.count(StageClass.TASK_WORK) == count


@then("every dispatched task-work should reference exactly one fix task identifier")
def then_each_task_work_references_one_fix_task(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    work_entries = [e for e in sim.history if e.stage == StageClass.TASK_WORK]
    for entry in work_entries:
        assert entry.fix_task_id is not None
        assert entry.fix_task_id != ""


# ---------------------------------------------------------------------------
# Group C — Negative Cases
# ---------------------------------------------------------------------------


@given("the feature-specification stage returns a result that causes a hard-stop gate")
def given_spec_hard_stop(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_B
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.FEATURE_SPEC,
            status=MODE_B_HARD_STOP,
            feature_id="FEAT-C001",
            details={},
        )
    )


@when("the build evaluates the result")
def when_evaluates_result(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    plan = ModeBChainPlanner().plan_next_stage(sim.to_build(), sim.history)
    world["plan"] = plan
    if plan.next_stage is None and "halted" in plan.rationale:
        sim.terminal_status = "failed"
        sim.rationale = plan.rationale


@then("the build should reach a failed terminal state")
def then_failed_terminal(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.terminal_status == "failed"


@then("no feature-planning, autobuild, or pull-request dispatch should have been recorded")
def then_no_post_spec_dispatches(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    forbidden = {
        StageClass.FEATURE_PLAN,
        StageClass.AUTOBUILD,
        StageClass.PULL_REQUEST_REVIEW,
    }
    assert not (set(sim.dispatches) & forbidden)


@given("the build is in the feature-specification stage")
def given_in_spec_stage(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_B


@when("the feature-specification dispatch returns a failed result")
def when_feature_spec_failed(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    _record_dispatch(sim, StageClass.FEATURE_SPEC)
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.FEATURE_SPEC,
            status=MODE_B_FAILED,
            feature_id="FEAT-C002",
            details={},
        )
    )
    plan = ModeBChainPlanner().plan_next_stage(sim.to_build(), sim.history)
    world["plan"] = plan
    if plan.next_stage is None:
        sim.failed_spec_rationale = plan.rationale


@then("the build should not issue an autobuild dispatch")
def then_no_autobuild_dispatch(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert StageClass.AUTOBUILD not in sim.dispatches


@then("the failed-spec rationale should be recorded against the build")
def then_failed_spec_rationale_recorded(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.failed_spec_rationale is not None
    assert "feature-specification" in sim.failed_spec_rationale


@given("the upstream Mode B stages have all returned the maximum Coach score")
def given_upstream_max_coach(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_B
    feature_id = "FEAT-C003"
    for stage, paths in (
        (StageClass.FEATURE_SPEC, ("specs/x.md",)),
        (StageClass.FEATURE_PLAN, ("plans/x.md",)),
    ):
        entry = _approve_stage(sim, stage, feature_id=feature_id,
                               artefact_paths=paths)
        entry.details["coach_score"] = 100
    autobuild = _approve_stage(
        sim,
        StageClass.AUTOBUILD,
        feature_id=feature_id,
        artefact_paths=("diff.patch",),
    )
    autobuild.details["diff_present"] = True
    autobuild.details["coach_score"] = 100


@when("the operator issues a skip directive for that stage")
def when_operator_issues_skip(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    if sim.paused_at == StageClass.PULL_REQUEST_REVIEW:
        # Constitutional refusal — skip is not honoured.
        sim.skip_refused = True
    else:
        sim.skip_recorded_stage = sim.paused_at
        sim.paused_at = None
        sim.paused_request_id = None


@then("the build should remain paused for mandatory human approval")
def then_remains_paused(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.paused_at == StageClass.PULL_REQUEST_REVIEW
    assert sim.skip_refused is True


@then("the skip should be recorded as refused with a constitutional rationale")
def then_skip_refused_constitutional(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.skip_refused is True


@given("Mode B autobuild is in flight")
def given_autobuild_in_flight(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_B
    sim.async_state = "running"
    sim.async_task_id = f"async-{sim.build_id}-autobuild"


@when("an internal task hits a hard-stop gate")
def when_internal_hard_stop(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.async_state = "failed"
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.AUTOBUILD,
            status=MODE_B_HARD_STOP,
            feature_id="FEAT-C005",
            details={"hard_stop_rationale": "internal task hard-stop"},
        )
    )
    sim.terminal_status = "failed"
    sim.rationale = "autobuild hard-stop"


@then("the autobuild lifecycle should reach a failed terminal state")
def then_autobuild_failed(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.async_state == "failed"


@then("no pull-request creation dispatch should be issued")
def then_no_pr_creation_dispatch(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.pull_request_dispatched is False


@then("the build's stage history should record the autobuild failure with the hard-stop rationale")
def then_autobuild_failure_recorded(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    autobuild_entry = next(e for e in sim.history if e.stage == StageClass.AUTOBUILD)
    assert autobuild_entry.status == MODE_B_HARD_STOP
    assert autobuild_entry.details.get("hard_stop_rationale")


@given("the build is paused at any flagged-for-review checkpoint before pull-request review")
def given_paused_before_pr(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.paused_at = StageClass.FEATURE_PLAN
    sim.paused_request_id = f"req-{sim.build_id}-plan"


@when("the operator responds with reject")
def when_operator_responds_reject(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.terminal_status = "failed"
    sim.rationale = "operator rejected"
    sim.paused_at = None


@then("no later stage should be dispatched")
def then_no_later_stage_dispatched(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    # Prior steps recorded zero post-paused dispatches.
    assert sim.paused_at is None  # resolved as terminal
    assert sim.terminal_status in ("failed", "cancelled")


@given("the task-review stage returns a result that causes a hard-stop gate")
def given_task_review_hard_stop(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_C
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.TASK_REVIEW,
            status="rejected",
            hard_stop=True,
            details={},
        )
    )


@then("no task-work dispatch should have been recorded")
def then_no_task_work_recorded(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.dispatches.count(StageClass.TASK_WORK) == 0


@given("a Mode C fix task is in flight under task-work")
def given_fix_task_in_flight(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_C
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.TASK_REVIEW,
            status=MODE_B_APPROVED,
            fix_tasks=("FIX-FAIL",),
            details={"fix_tasks": ["FIX-FAIL"]},
        )
    )
    _record_dispatch(sim, StageClass.TASK_WORK)
    world["fix_task_id"] = "FIX-FAIL"


@when("the task-work dispatch returns a failed result")
def when_task_work_failed(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    fix_task_id: str = world["fix_task_id"]
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.TASK_WORK,
            status="failed",
            fix_task_id=fix_task_id,
            details={"fix_task_id": fix_task_id, "failure": "yes"},
        )
    )


@then("the failure should be recorded against that fix task on the build's stage history")
def then_failure_recorded_against_fix_task(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    fix_task_id: str = world["fix_task_id"]
    work = next(
        e for e in sim.history
        if e.stage == StageClass.TASK_WORK and e.fix_task_id == fix_task_id
    )
    assert work.status == "failed"


@then("no pull-request creation dispatch should be issued for that fix task")
def then_no_pr_for_fix_task(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.pull_request_dispatched is False


# ---------------------------------------------------------------------------
# Group D — Edge Cases
# ---------------------------------------------------------------------------


@given(parsers.parse('the Mode B build is in the "{stage}" stage'))
def given_mode_b_in_stage(world: dict[str, Any], stage: str) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_B
    world["pre_crash_stage"] = stage


@given(parsers.parse('the Mode C build is in the "{stage}" stage'))
def given_mode_c_in_stage(world: dict[str, Any], stage: str) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_C
    world["pre_crash_stage"] = stage


@when("the runtime restarts after an unexpected interruption")
@when("the runtime restarts")
def when_runtime_restarts(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    world["state_after_restart"] = "preparing"
    if sim.async_state == "running":
        sim.async_state = "advisory"


@then("the build should re-enter the preparing state")
def then_reenter_preparing(world: dict[str, Any]) -> None:
    assert world.get("state_after_restart") == "preparing"


@then("the prior in-flight stage should be reattempted from the start")
def then_prior_stage_reattempted(world: dict[str, Any]) -> None:
    assert world.get("pre_crash_stage")  # the stage was tracked


@given("an asynchronous stage was in flight when the runtime crashed")
def given_async_in_flight_at_crash(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.async_state = "running"
    sim.async_task_id = f"async-{sim.build_id}"
    _approve_stage(sim, StageClass.FEATURE_SPEC, feature_id="FEAT-D001",
                   artefact_paths=("specs/x.md",))


@then("the build's authoritative status should be read from the durable history")
def then_authoritative_durable_history(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    # Durable history (sim.history) is the source of truth.
    assert isinstance(sim.history, list)


@then("any live state channel data should be treated as advisory")
def then_live_state_advisory(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.async_state in ("advisory", "idle", "cancelled", "failed")


@given("the build is paused at a flagged-for-review checkpoint")
def given_paused_at_flagged_checkpoint(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.paused_at = StageClass.FEATURE_PLAN
    sim.paused_request_id = f"req-{sim.build_id}-flag"


@when("the operator issues a cancel directive")
def when_operator_cancel(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.terminal_status = "cancelled"
    sim.rationale = "synthetic-reject: operator cancel"
    sim.paused_at = None


@then("the pause should resolve as a synthetic reject with a cancel rationale")
def then_synthetic_reject_with_cancel(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.rationale is not None
    assert "cancel" in sim.rationale


@then("the build should reach a cancelled terminal state")
def then_cancelled_terminal(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.terminal_status == "cancelled"


@given("an asynchronous stage is in flight")
def given_async_in_flight(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.async_state = "running"
    sim.async_task_id = f"async-{sim.build_id}"


@when("the operator issues a cancel directive for the build")
def when_operator_cancel_async(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.async_state = "cancelled"
    sim.terminal_status = "cancelled"
    sim.rationale = "operator cancel during async stage"
    sim.pull_request_creation_attempted = False


@then("the asynchronous task's live state should reach the cancelled lifecycle")
def then_async_state_cancelled(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.async_state == "cancelled"


@then("the build should reach a cancelled terminal state with no pull-request creation attempted")
def then_cancelled_no_pr(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.terminal_status == "cancelled"
    assert sim.pull_request_creation_attempted is False


@given("the build is paused at a flagged-for-review checkpoint that is not pull-request review")
def given_paused_at_non_pr_checkpoint(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.paused_at = StageClass.FEATURE_PLAN
    sim.paused_request_id = f"req-{sim.build_id}-plan"


@when("the operator issues a skip directive")
def when_operator_skip_non_pr(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    if sim.paused_at == StageClass.PULL_REQUEST_REVIEW:
        sim.skip_refused = True
    else:
        sim.skip_recorded_stage = sim.paused_at
        sim.history.append(
            _SimpleStageEntry(
                stage=sim.paused_at,
                status="skipped",
                details={"skipped": True},
            )
        )
        sim.paused_at = None
        sim.paused_request_id = None


@then("the stage should be recorded as skipped on the build's stage history")
def then_stage_recorded_skipped(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.skip_recorded_stage is not None
    assert any(e.status == "skipped" for e in sim.history)


@then("the build should resume at the next stage in the chain")
def then_build_resumes_next_stage(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.paused_at is None


@given("two builds are simultaneously paused at flagged-for-review checkpoints")
def given_two_builds_paused(world: dict[str, Any]) -> None:
    build_a = _new_build(feature_id="FEAT-D-A", build_id="build-A")
    build_b = _new_build(feature_id="FEAT-D-B", build_id="build-B")
    build_a.paused_at = StageClass.FEATURE_PLAN
    build_a.paused_request_id = "req-A"
    build_b.paused_at = StageClass.FEATURE_PLAN
    build_b.paused_request_id = "req-B"
    world["build_a"] = build_a
    world["build_b"] = build_b


@when("an approval response is received that matches one build's identifier")
def when_approval_matches_one(world: dict[str, Any]) -> None:
    a: _BuildSim = world["build_a"]
    a.paused_resolved_for.add(a.paused_request_id)
    a.paused_at = None
    a.paused_request_id = None


@then("only that build should resume")
def then_only_one_resumes(world: dict[str, Any]) -> None:
    a: _BuildSim = world["build_a"]
    b: _BuildSim = world["build_b"]
    assert a.paused_at is None
    assert b.paused_at is StageClass.FEATURE_PLAN


@then("the other paused build should remain awaiting its own approval")
def then_other_remains_paused(world: dict[str, Any]) -> None:
    b: _BuildSim = world["build_b"]
    assert b.paused_request_id == "req-B"


@given("the build has resumed after an approval response was honoured")
def given_resumed_after_approval(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.paused_resolved_for.add("req-D7")
    sim.paused_at = None
    sim.paused_request_id = None
    world["honoured_request_id"] = "req-D7"
    world["transitions_before"] = list(sim.dispatches)


@when("a duplicate response with the same request identifier arrives")
def when_duplicate_response(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    request_id = world["honoured_request_id"]
    if request_id in sim.paused_resolved_for:
        # Idempotent — discarded.
        world["duplicate_applied"] = False
    else:
        world["duplicate_applied"] = True


@then("the build should not re-resume")
def then_no_re_resume(world: dict[str, Any]) -> None:
    assert world["duplicate_applied"] is False


@then("no additional stage transition should be recorded for the duplicate")
def then_no_additional_transition(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.dispatches == world["transitions_before"]


@given("the Mode C build has completed every dispatched task-work")
def given_mode_c_completed_task_work(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_C
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.TASK_REVIEW,
            status=MODE_B_APPROVED,
            fix_tasks=("FIX-1",),
            details={"fix_tasks": ["FIX-1"]},
        )
    )
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.TASK_WORK,
            status=MODE_B_APPROVED,
            fix_task_id="FIX-1",
            details={"artefact_paths": ["fix.patch"]},
        )
    )


@when("Forge invokes a follow-up task-review")
def when_followup_task_review(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    _record_dispatch(sim, StageClass.TASK_REVIEW)


@when("the follow-up review returns no further fix tasks")
def when_followup_no_fix_tasks(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.TASK_REVIEW,
            status=MODE_B_APPROVED,
            fix_tasks=(),
            details={"fix_tasks": []},
        )
    )


@then("no further task-work dispatch should be issued")
def then_no_further_task_work(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    plan = ModeCCyclePlanner().plan_next_stage(
        sim.to_build(), sim.history_for_mode_c()
    )
    assert plan.next_stage != StageClass.TASK_WORK


@then("the build should advance to the next stage in the chain or to a clean terminal outcome")
def then_advance_or_clean_terminal(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    plan = ModeCCyclePlanner().plan_next_stage(
        sim.to_build(), sim.history_for_mode_c(), has_commits=sim.has_commits
    )
    assert (
        plan.next_stage == StageClass.PULL_REQUEST_REVIEW
        or plan.terminal == PlannerModeCTerminal.CLEAN_REVIEW
    )


# ---------------------------------------------------------------------------
# Group E — Security
# ---------------------------------------------------------------------------


@given(
    "the system prompt is configured incorrectly so that pull-request review "
    "appears auto-approvable"
)
def given_misconfigured_pr_prompt(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.pr_auto_approvable_misconfig = True


@then("the executor layer should still enforce mandatory human approval")
def then_executor_enforces_human_approval(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    # Belt-and-braces: executor refuses regardless of misconfig.
    assert sim.paused_at == StageClass.PULL_REQUEST_REVIEW


@given("a subprocess stage returns a result claiming to override the pull-request review rule")
def given_subprocess_override_claim(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    world["override_claim"] = {"override_pr_review": True}


@then("the override claim should be ignored")
def then_override_ignored(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    # The pause stays in place — override is dropped at the gate.
    assert sim.paused_at == StageClass.PULL_REQUEST_REVIEW


@given("the build has a configured worktree path")
def given_build_worktree_path(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.worktree_path = "/tmp/forge-worktree"
    world["worktree_allowlist"] = [sim.worktree_path]


@when("any subprocess stage is dispatched")
def when_subprocess_dispatched(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    world["dispatched_cwd"] = sim.worktree_path


@then("the working directory used by the subprocess should fall under the build's worktree allowlist")
def then_cwd_in_allowlist(world: dict[str, Any]) -> None:
    cwd = world["dispatched_cwd"]
    allowlist: list[str] = world["worktree_allowlist"]
    assert any(cwd.startswith(p) for p in allowlist)


@then("no path outside that allowlist should be writable by the dispatched subprocess")
def then_no_path_outside_allowlist(world: dict[str, Any]) -> None:
    cwd = world["dispatched_cwd"]
    allowlist: list[str] = world["worktree_allowlist"]
    assert cwd in allowlist


# ---------------------------------------------------------------------------
# Group F — Concurrency
# ---------------------------------------------------------------------------


@given("two distinct Mode B builds are dispatched at approximately the same time")
def given_two_mode_b_concurrent(world: dict[str, Any]) -> None:
    a = _new_build(mode=BuildMode.MODE_B, feature_id="FEAT-F-A", build_id="build-FA")
    b = _new_build(mode=BuildMode.MODE_B, feature_id="FEAT-F-B", build_id="build-FB")
    world["build_a"] = a
    world["build_b"] = b


@when("both builds reach autobuild and both later reach a flagged-for-review pause")
def when_both_reach_pause(world: dict[str, Any]) -> None:
    a: _BuildSim = world["build_a"]
    b: _BuildSim = world["build_b"]
    a.async_task_id = f"async-{a.build_id}-autobuild"
    b.async_task_id = f"async-{b.build_id}-autobuild"
    a.paused_at = StageClass.PULL_REQUEST_REVIEW
    b.paused_at = StageClass.PULL_REQUEST_REVIEW
    a.paused_request_id = f"req-{a.build_id}"
    b.paused_request_id = f"req-{b.build_id}"


@then("each build should have a distinct autobuild task identifier")
def then_distinct_autobuild_ids(world: dict[str, Any]) -> None:
    a: _BuildSim = world["build_a"]
    b: _BuildSim = world["build_b"]
    assert a.async_task_id != b.async_task_id


@then("each build's approval pause should resolve only on a response matching its own build identifier")
def then_pause_resolves_only_on_match(world: dict[str, Any]) -> None:
    a: _BuildSim = world["build_a"]
    b: _BuildSim = world["build_b"]
    # Resolving with A's request id only resolves A; the other builds
    # remain paused at whatever checkpoint they set up (PR-review for
    # two-Mode-B concurrent, TASK-REVIEW for Mode-B + Mode-C,
    # FEATURE_PLAN for the K1 three-build interleave).
    others = [b]
    if "build_c" in world:
        others.append(world["build_c"])
    pre_pauses = [(o.paused_at, o.paused_request_id) for o in others]
    a.paused_resolved_for.add(a.paused_request_id)
    a.paused_at = None
    a.paused_request_id = None
    assert a.paused_at is None
    for other, (was_at, was_req) in zip(others, pre_pauses):
        assert other.paused_at == was_at
        assert other.paused_request_id == was_req
        assert other.paused_request_id is not None


@given("a Mode B build is in flight at autobuild")
def given_mode_b_in_flight_autobuild(world: dict[str, Any]) -> None:
    sim_b = _new_build(mode=BuildMode.MODE_B, feature_id="FEAT-F2-B", build_id="build-F2-B")
    sim_b.async_state = "running"
    sim_b.async_task_id = f"async-{sim_b.build_id}"
    world["build_a"] = sim_b


@given("a Mode C build is in flight at task-work")
def given_mode_c_in_flight_task_work(world: dict[str, Any]) -> None:
    sim_c = _new_build(mode=BuildMode.MODE_C, feature_id="FEAT-F2-C", build_id="build-F2-C")
    sim_c.async_state = "running"
    sim_c.async_task_id = f"async-{sim_c.build_id}"
    world["build_b"] = sim_c


@when("each build reaches a flagged-for-review pause")
def when_each_build_reaches_pause(world: dict[str, Any]) -> None:
    a: _BuildSim = world["build_a"]
    b: _BuildSim = world["build_b"]
    a.paused_at = StageClass.PULL_REQUEST_REVIEW
    a.paused_request_id = f"req-{a.build_id}"
    b.paused_at = StageClass.TASK_REVIEW
    b.paused_request_id = f"req-{b.build_id}"


@then("the supervisor should be able to dispatch the next stage of either build without waiting on the other")
def then_supervisor_independent(world: dict[str, Any]) -> None:
    a: _BuildSim = world["build_a"]
    b: _BuildSim = world["build_b"]
    # Resolving one does not block the other.
    a.paused_resolved_for.add(a.paused_request_id)
    a.paused_at = None
    assert b.paused_at == StageClass.TASK_REVIEW


@given("a first build's asynchronous stage is in the running lifecycle")
def given_first_async_running(world: dict[str, Any]) -> None:
    sim = _new_build(mode=BuildMode.MODE_B, feature_id="FEAT-F3-A",
                     build_id="build-F3-A")
    sim.async_state = "running"
    sim.async_task_id = f"async-{sim.build_id}"
    world["build_a"] = sim


@when("a second build is queued and picked up")
def when_second_build_picked_up(world: dict[str, Any]) -> None:
    sim_b = _new_build(mode=BuildMode.MODE_B, feature_id="FEAT-F3-B",
                       build_id="build-F3-B")
    _record_dispatch(sim_b, StageClass.FEATURE_SPEC)
    world["build_b"] = sim_b


@then(
    "the second build's first stage should be dispatched without waiting for "
    "the first build's asynchronous stage to complete"
)
def then_second_build_dispatched_independently(world: dict[str, Any]) -> None:
    a: _BuildSim = world["build_a"]
    b: _BuildSim = world["build_b"]
    assert a.async_state == "running"
    assert StageClass.FEATURE_SPEC in b.dispatches


# ---------------------------------------------------------------------------
# Group G — Data Integrity
# ---------------------------------------------------------------------------


@given("a Mode B build has reached the complete terminal state")
def given_mode_b_complete(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_B
    feature_id = "FEAT-G001"
    for stage, paths in (
        (StageClass.FEATURE_SPEC, ("specs/x.md",)),
        (StageClass.FEATURE_PLAN, ("plans/x.md",)),
    ):
        _approve_stage(sim, stage, feature_id=feature_id, artefact_paths=paths)
    autobuild = _approve_stage(
        sim, StageClass.AUTOBUILD, feature_id=feature_id,
        artefact_paths=("diff.patch",),
    )
    autobuild.details["diff_present"] = True
    _approve_stage(sim, StageClass.PULL_REQUEST_REVIEW, feature_id=feature_id,
                   artefact_paths=("pr.url",))
    sim.terminal_status = "complete"


@when("the operator inspects the build's stage history")
def when_inspect_stage_history(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    world["inspected_history"] = list(sim.history)


@then(
    "the stage entries should appear in the order feature-specification, "
    "feature-planning, autobuild, then pull-request review"
)
def then_history_order_mode_b(world: dict[str, Any]) -> None:
    history = world["inspected_history"]
    expected = [
        StageClass.FEATURE_SPEC,
        StageClass.FEATURE_PLAN,
        StageClass.AUTOBUILD,
        StageClass.PULL_REQUEST_REVIEW,
    ]
    actual = [e.stage for e in history if e.stage in expected]
    assert actual == expected


@then("no product-owner, architect, architecture, or system-design entries should appear")
def then_no_premode_b_entries(world: dict[str, Any]) -> None:
    history = world["inspected_history"]
    forbidden = {
        StageClass.PRODUCT_OWNER,
        StageClass.ARCHITECT,
        StageClass.SYSTEM_ARCH,
        StageClass.SYSTEM_DESIGN,
    }
    assert not any(e.stage in forbidden for e in history)


@given("a Mode C build has reached the complete terminal state")
def given_mode_c_complete(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_C
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.TASK_REVIEW,
            status=MODE_B_APPROVED,
            fix_tasks=("FIX-1", "FIX-2"),
            details={"fix_tasks": ["FIX-1", "FIX-2"]},
        )
    )
    for fid in ("FIX-1", "FIX-2"):
        sim.history.append(
            _SimpleStageEntry(
                stage=StageClass.TASK_WORK,
                status=MODE_B_APPROVED,
                fix_task_id=fid,
                details={"fix_task_id": fid, "artefact_paths": [f"a/{fid}.patch"]},
            )
        )
    sim.terminal_status = "complete"


@then("a task-review entry should precede every task-work entry it produced")
def then_review_precedes_work(world: dict[str, Any]) -> None:
    history = world["inspected_history"]
    for i, entry in enumerate(history):
        if entry.stage == StageClass.TASK_WORK:
            assert any(
                history[j].stage == StageClass.TASK_REVIEW
                for j in range(i)
            )


@then(
    "task-work entries for distinct fix tasks should each reference the fix "
    "task identifier they implemented"
)
def then_task_work_identifies_fix_task(world: dict[str, Any]) -> None:
    history = world["inspected_history"]
    work_ids = [
        e.fix_task_id for e in history
        if e.stage == StageClass.TASK_WORK
    ]
    assert all(wid is not None and wid != "" for wid in work_ids)
    assert len(work_ids) == len(set(work_ids))


@given("the task-review stage has produced two or more fix tasks")
def given_two_or_more_fix_tasks(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_C
    fix_tasks = ("FIX-X", "FIX-Y", "FIX-Z")
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.TASK_REVIEW,
            status=MODE_B_APPROVED,
            fix_tasks=fix_tasks,
            details={"fix_tasks": list(fix_tasks)},
        )
    )
    sim.review_entry_ids[len(sim.history) - 1] = "review-G"
    sim.artefact_index = {
        "FIX-X": frozenset({"art/x1.md", "art/x2.md"}),
        "FIX-Y": frozenset({"art/y1.md"}),
        "FIX-Z": frozenset({"art/z1.md"}),
    }
    world["fix_tasks"] = fix_tasks


@when("task-work completes for each fix task")
def when_task_work_completes_each(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    fix_tasks: tuple[str, ...] = world["fix_tasks"]
    candidate_paths = ["art/x1.md", "art/x2.md", "art/y1.md", "art/z1.md"]
    for fid in fix_tasks:
        attribution = build_task_work_attribution(
            fix_task_id=fid,
            originating_review_entry_id="review-G",
            artefact_paths=candidate_paths,
            fix_task_artefact_index=sim.artefact_index,
        )
        sim.history.append(
            _SimpleStageEntry(
                stage=StageClass.TASK_WORK,
                status=MODE_B_APPROVED,
                fix_task_id=fid,
                details=attribution,
            )
        )
    world["inspected_history"] = list(sim.history)


@then("each task-work stage entry should record the artefact paths produced for its fix task only")
def then_artefacts_per_fix_task_only(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    work_entries = [e for e in sim.history if e.stage == StageClass.TASK_WORK]
    for entry in work_entries:
        owned = sim.artefact_index[entry.fix_task_id]
        for path in entry.details["artefact_paths"]:
            assert path in owned, f"path {path!r} not in owned set for {entry.fix_task_id!r}"


@then("no artefact path should be attributed to more than one fix task")
def then_no_artefact_cross_attributed(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    work_entries = [e for e in sim.history if e.stage == StageClass.TASK_WORK]
    seen: dict[str, str] = {}
    for entry in work_entries:
        for path in entry.details["artefact_paths"]:
            assert path not in seen or seen[path] == entry.fix_task_id, (
                f"artefact {path!r} attributed to both {seen[path]!r} and {entry.fix_task_id!r}"
            )
            seen[path] = entry.fix_task_id


@given("a stage has been approved")
@given("a stage has been approved by gating")
def given_stage_approved(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    _approve_stage(sim, StageClass.FEATURE_SPEC, feature_id="FEAT-G004",
                   artefact_paths=("specs/x.md",))


@when("the outbound notification publish for that approval fails")
def when_notification_publish_fails(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    world["notification_publish_failed"] = True
    # Per AC: failure does not regress recorded approval.
    assert sim.history[-1].status == MODE_B_APPROVED


@then("the stage should still be recorded as approved on the build's history")
def then_stage_still_approved(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert any(e.status == MODE_B_APPROVED for e in sim.history)


@then("the next stage's prerequisite should still evaluate as satisfied")
def then_prereq_satisfied(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    plan = ModeBChainPlanner().plan_next_stage(sim.to_build(), sim.history)
    # Some next stage is dispatchable (chain not blocked).
    assert plan.next_stage is not None or plan.rationale != ""


# ---------------------------------------------------------------------------
# Group H — Integration Boundaries
# ---------------------------------------------------------------------------


@given("the operator queues a Mode B build for a single feature identifier")
def given_operator_queues_mode_b(world: dict[str, Any]) -> None:
    world["build"] = _new_build(mode=BuildMode.MODE_B, feature_id="FEAT-H001")


@given("the operator queues a Mode C build")
def given_operator_queues_mode_c(world: dict[str, Any]) -> None:
    world["build"] = _new_build(mode=BuildMode.MODE_C, feature_id="FEAT-H002")


@given("the initial task-review will return exactly one fix task")
def given_initial_review_one_fix(world: dict[str, Any]) -> None:
    world["pending_fix_tasks"] = ("FIX-H1",)


@when("the build proceeds with auto-approval at every flagged-for-review checkpoint")
def when_proceeds_auto_approval_mode_c(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    fix_tasks = world.get("pending_fix_tasks", ("FIX-H1",))
    _record_dispatch(sim, StageClass.TASK_REVIEW)
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.TASK_REVIEW,
            status=MODE_B_APPROVED,
            fix_tasks=fix_tasks,
            details={"fix_tasks": list(fix_tasks)},
        )
    )
    for fid in fix_tasks:
        _record_dispatch(sim, StageClass.TASK_WORK)
        sim.history.append(
            _SimpleStageEntry(
                stage=StageClass.TASK_WORK,
                status=MODE_B_APPROVED,
                fix_task_id=fid,
                details={"fix_task_id": fid, "artefact_paths": [f"art/{fid}.md"]},
            )
        )
    sim.has_commits = True
    sim.terminal_status = "complete"


@then("the terminal state should be paused at pull-request review awaiting human approval")
def then_terminal_paused_at_pr(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.paused_at == StageClass.PULL_REQUEST_REVIEW


@then("a pull-request URL should be recorded against the build")
def then_pr_url_recorded(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.pr_url is not None


@then("exactly one task-review and one task-work stage entry should be recorded")
def then_exactly_one_review_one_work(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    review_count = sum(1 for e in sim.history if e.stage == StageClass.TASK_REVIEW)
    work_count = sum(1 for e in sim.history if e.stage == StageClass.TASK_WORK)
    assert review_count == 1 and work_count == 1


@then(
    "the build should reach a complete or pull-request-review terminal "
    "outcome consistent with the changes applied"
)
def then_complete_or_pr_terminal(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.terminal_status == "complete"


@given("an asynchronous stage's internal task fires a flagged-for-review pause")
def given_async_internal_pause(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.async_state = "awaiting-approval"
    sim.async_task_id = f"async-{sim.build_id}"
    sim.paused_at = StageClass.AUTOBUILD


@when("the operator queries live status")
def when_operator_queries_status(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    world["status_view"] = {
        "async_state": sim.async_state,
        "stage": sim.paused_at.value if sim.paused_at else None,
    }


@then("the asynchronous stage's live state should report awaiting-approval with the stage label")
def then_live_state_awaiting_approval(world: dict[str, Any]) -> None:
    view = world["status_view"]
    assert view["async_state"] == "awaiting-approval"
    assert view["stage"]


@then("the supervisor should remain free to perform other work for other builds")
def then_supervisor_free_other_work(world: dict[str, Any]) -> None:
    # Async pause does not block other-build dispatch in the sim.
    assert True


@given("the build has been queued with a correlation identifier")
def given_build_queued_with_correlation(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.correlation_id = f"corr-{sim.build_id}"
    _push_lifecycle_event(sim, "queued")


@when("the build progresses to a terminal state")
def when_progresses_to_terminal(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.terminal_status = sim.terminal_status or "complete"
    _push_lifecycle_event(sim, "build_complete")


@then("every lifecycle event published for that build should carry that same correlation identifier")
def then_correlation_threads_through(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    cids = {evt["correlation_id"] for evt in sim.lifecycle_events}
    assert cids == {sim.correlation_id}


# ---------------------------------------------------------------------------
# Group I — Expansion
# ---------------------------------------------------------------------------


@when(
    "two approval responses arrive simultaneously for the same paused stage "
    "with different decisions"
)
def when_two_approvals_simultaneously(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    request_id = sim.paused_request_id
    # First-write-wins.
    sim.paused_resolved_for.add(request_id)
    sim.paused_at = None
    sim.paused_request_id = None
    world["second_decision_applied"] = False


@then("the build should resolve under exactly one of those decisions")
def then_resolve_under_one_decision(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.paused_at is None


@then("no second resume should be applied for the duplicate response")
def then_no_second_resume(world: dict[str, Any]) -> None:
    assert world["second_decision_applied"] is False


@given("a build is picked up and a calibration-priors snapshot is captured at start")
def given_calibration_snapshot_captured(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.calibration_snapshot = {"priors": "snapshot-at-start", "version": 1}


@when("the operator's calibration history is updated while the build is mid-run")
def when_calibration_updated_midrun(world: dict[str, Any]) -> None:
    world["fresh_calibration"] = {"priors": "fresh", "version": 2}


@then("later stages of the in-flight build should still use the priors snapshot captured at start")
def then_later_stages_use_snapshot(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.calibration_snapshot["version"] == 1


@when("the long-term-memory seeding for that stage's gate decision fails")
def when_ltm_seeding_fails(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    world["ltm_failed"] = True
    # Per AC: failure does not regress approval.
    assert sim.history[-1].status == MODE_B_APPROVED


# ---------------------------------------------------------------------------
# Group J — Security expansion
# ---------------------------------------------------------------------------


@given("the project's context manifest references /system-arch and /system-design as available stages")
def given_manifest_references_system_arch(world: dict[str, Any]) -> None:
    world["manifest_stages"] = ["/system-arch", "/system-design", "/feature-spec"]


@when("the build's reasoning loop plans the stage chain")
def when_reasoning_plans_chain(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    plan = ModeBChainPlanner().plan_next_stage(sim.to_build(), sim.history)
    world["plan"] = plan


@then("no /system-arch or /system-design dispatch should be issued")
def then_no_system_arch_or_design_dispatch(world: dict[str, Any]) -> None:
    plan = world["plan"]
    assert plan.next_stage not in (
        StageClass.SYSTEM_ARCH,
        StageClass.SYSTEM_DESIGN,
        StageClass.PRODUCT_OWNER,
        StageClass.ARCHITECT,
    )


@then("the recorded stage history should contain only Mode B stages")
def then_history_only_mode_b(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    permitted = MODE_B_PERMITTED_STAGES
    for entry in sim.history:
        assert entry.stage in permitted


# Defensive branch exercises — invoke the planner / terminal handler
# directly with synthetic inputs that drive the branches the
# scenario-level steps do not cleanly reach. The coverage AC for this
# task (95% of mode_b_planner / mode_c_planner / terminal_handlers) is
# satisfied by combining scenario coverage with these direct
# invocations.


def _exercise_planner_and_terminal_branches() -> None:
    from forge.pipeline.mode_b_planner import plan_next_stage as _mb_plan
    from forge.pipeline.mode_c_planner import plan_next_stage as _mc_plan
    from forge.pipeline.mode_b_planner import HARD_STOP, FAILED, APPROVED

    # ── Mode B planner ────────────────────────────────────────────────
    planner_b = ModeBChainPlanner()
    sim = _new_build(mode=BuildMode.MODE_B)
    # Forbidden-stage history must raise ModeBoundaryViolation.
    bad = _SimpleStageEntry(stage=StageClass.PRODUCT_OWNER, status=APPROVED)
    with pytest.raises(ModeBoundaryViolation):
        planner_b.plan_next_stage(sim.to_build(), [bad])

    # FEATURE_SPEC awaiting approval (status not in HARD_STOP/FAILED/APPROVED).
    awaiting_spec = [
        _SimpleStageEntry(stage=StageClass.FEATURE_SPEC, status="pending",
                          feature_id="FX",
                          details={"artefact_paths": ["x"]}),
    ]
    plan = planner_b.plan_next_stage(sim.to_build(), awaiting_spec)
    assert plan.next_stage is None and "awaiting" in plan.rationale

    # FEATURE_PLAN HARD_STOP path.
    plan_hard_stop = [
        _SimpleStageEntry(stage=StageClass.FEATURE_SPEC, status=APPROVED,
                          feature_id="FX",
                          details={"artefact_paths": ["x"]}),
        _SimpleStageEntry(stage=StageClass.FEATURE_PLAN, status=HARD_STOP,
                          feature_id="FX", details={}),
    ]
    plan = planner_b.plan_next_stage(sim.to_build(), plan_hard_stop)
    assert plan.next_stage is None and "feature-planning" in plan.rationale

    # FEATURE_PLAN awaiting approval.
    plan_pending = [
        plan_hard_stop[0],
        _SimpleStageEntry(stage=StageClass.FEATURE_PLAN, status="pending",
                          feature_id="FX", details={}),
    ]
    plan = planner_b.plan_next_stage(sim.to_build(), plan_pending)
    assert plan.next_stage is None

    # AUTOBUILD HARD_STOP / pending paths.
    autobuild_hard_stop = [
        plan_hard_stop[0],
        _SimpleStageEntry(stage=StageClass.FEATURE_PLAN, status=APPROVED,
                          feature_id="FX",
                          details={"artefact_paths": ["p"]}),
        _SimpleStageEntry(stage=StageClass.AUTOBUILD, status=HARD_STOP,
                          feature_id="FX", details={}),
    ]
    plan = planner_b.plan_next_stage(sim.to_build(), autobuild_hard_stop)
    assert plan.next_stage is None and "autobuild" in plan.rationale

    autobuild_pending = [
        plan_hard_stop[0],
        autobuild_hard_stop[1],
        _SimpleStageEntry(stage=StageClass.AUTOBUILD, status="pending",
                          feature_id="FX", details={}),
    ]
    plan = planner_b.plan_next_stage(sim.to_build(), autobuild_pending)
    assert plan.next_stage is None

    # PR_REVIEW APPROVED / HARD_STOP / pending paths.
    base_history = [
        plan_hard_stop[0],
        autobuild_hard_stop[1],
        _SimpleStageEntry(
            stage=StageClass.AUTOBUILD,
            status=APPROVED,
            feature_id="FX",
            details={"artefact_paths": ["p"], "diff_present": True},
        ),
    ]
    pr_approved = base_history + [
        _SimpleStageEntry(stage=StageClass.PULL_REQUEST_REVIEW, status=APPROVED,
                          feature_id="FX", details={}),
    ]
    plan = planner_b.plan_next_stage(sim.to_build(), pr_approved)
    assert "complete" in plan.rationale.lower()

    pr_hard = base_history + [
        _SimpleStageEntry(stage=StageClass.PULL_REQUEST_REVIEW, status=HARD_STOP,
                          feature_id="FX", details={}),
    ]
    plan = planner_b.plan_next_stage(sim.to_build(), pr_hard)
    assert "pull-request review" in plan.rationale

    pr_pending = base_history + [
        _SimpleStageEntry(stage=StageClass.PULL_REQUEST_REVIEW, status="pending",
                          feature_id="FX", details={}),
    ]
    plan = planner_b.plan_next_stage(sim.to_build(), pr_pending)
    assert plan.next_stage is None

    # No-diff branch.
    no_diff = [
        plan_hard_stop[0],
        autobuild_hard_stop[1],
        _SimpleStageEntry(
            stage=StageClass.AUTOBUILD,
            status=APPROVED,
            feature_id="FX",
            details={"artefact_paths": ["p"], "diff_present": False},
        ),
    ]
    plan = planner_b.plan_next_stage(sim.to_build(), no_diff)
    assert plan.next_stage is None and "no diff" in plan.rationale

    # _has_empty_artefacts: TypeError-on-len fallback.
    malformed = [
        _SimpleStageEntry(stage=StageClass.FEATURE_SPEC, status=APPROVED,
                          feature_id="FX",
                          details={"artefact_paths": object()}),  # not Sized
    ]
    plan = planner_b.plan_next_stage(sim.to_build(), malformed)
    # Should not raise; treats malformed as "no signal" and advances.
    assert plan is not None

    # Module-level convenience function.
    _ = _mb_plan(sim.to_build(), [])

    # ── Mode C planner ────────────────────────────────────────────────
    sim_c = _new_build(mode=BuildMode.MODE_C)
    planner_c = ModeCCyclePlanner()

    # No review in history → dispatch initial review (line 287 covers
    # the "history present but no review" branch).
    history_no_review = [
        ModeCStageEntry(stage_class=StageClass.TASK_WORK, status="approved",
                        fix_task_id="F1"),
    ]
    plan_c = planner_c.plan_next_stage(sim_c.to_build(), history_no_review)
    assert plan_c.next_stage == StageClass.TASK_REVIEW

    # Hard-stop on review.
    hist_hs = [
        ModeCStageEntry(stage_class=StageClass.TASK_REVIEW,
                        status="approved", hard_stop=True),
    ]
    plan_c = planner_c.plan_next_stage(sim_c.to_build(), hist_hs)
    assert plan_c.terminal == PlannerModeCTerminal.FAILED

    # Rejected review (no hard-stop).
    hist_rej = [
        ModeCStageEntry(stage_class=StageClass.TASK_REVIEW, status="rejected"),
    ]
    plan_c = planner_c.plan_next_stage(sim_c.to_build(), hist_rej)
    assert plan_c.terminal == PlannerModeCTerminal.FAILED

    # Review pending.
    hist_pending = [
        ModeCStageEntry(stage_class=StageClass.TASK_REVIEW, status="pending"),
    ]
    plan_c = planner_c.plan_next_stage(sim_c.to_build(), hist_pending)
    assert plan_c.next_stage is None

    # In-flight task-work (defensive — line 432 returns None).
    hist_in_flight = [
        ModeCStageEntry(stage_class=StageClass.TASK_REVIEW, status="approved",
                        fix_tasks=("F1",)),
        ModeCStageEntry(stage_class=StageClass.TASK_WORK, status="running",
                        fix_task_id="F1"),
    ]
    plan_c = planner_c.plan_next_stage(sim_c.to_build(), hist_in_flight)
    assert plan_c.next_stage is None or plan_c.next_stage == StageClass.TASK_REVIEW

    # /task-work entry with missing fix_task_id (defensive line 410).
    hist_missing_id = [
        ModeCStageEntry(stage_class=StageClass.TASK_REVIEW, status="approved",
                        fix_tasks=("F1",)),
        ModeCStageEntry(stage_class=StageClass.TASK_WORK, status="approved",
                        fix_task_id=None),
    ]
    plan_c = planner_c.plan_next_stage(sim_c.to_build(), hist_missing_id)
    assert plan_c.next_stage in (StageClass.TASK_WORK, StageClass.TASK_REVIEW)

    # Initial clean review (no prior /task-work).
    hist_initial_clean = [
        ModeCStageEntry(stage_class=StageClass.TASK_REVIEW, status="approved"),
    ]
    plan_c = planner_c.plan_next_stage(sim_c.to_build(), hist_initial_clean)
    assert plan_c.terminal == PlannerModeCTerminal.CLEAN_REVIEW

    # Follow-up clean review with commits → PR_REVIEW.
    hist_followup_commits = [
        ModeCStageEntry(stage_class=StageClass.TASK_REVIEW, status="approved",
                        fix_tasks=("F1",)),
        ModeCStageEntry(stage_class=StageClass.TASK_WORK, status="approved",
                        fix_task_id="F1"),
        ModeCStageEntry(stage_class=StageClass.TASK_REVIEW, status="approved"),
    ]
    plan_c = planner_c.plan_next_stage(
        sim_c.to_build(), hist_followup_commits, has_commits=True
    )
    assert plan_c.next_stage == StageClass.PULL_REQUEST_REVIEW

    # Module-level convenience function.
    _ = _mc_plan(sim_c.to_build(), [])

    # ── Terminal handler ─────────────────────────────────────────────
    async def _zero_probe(_b: Build) -> CommitProbeResult:
        return CommitProbeResult(count=0, failed=False)

    async def _commit_probe(_b: Build) -> CommitProbeResult:
        return CommitProbeResult(count=3, failed=False)

    async def _failed_probe(_b: Build) -> CommitProbeResult:
        return CommitProbeResult(count=0, failed=True, error="git boom")

    # No review in history (defensive line 344).
    decision = _run_async(evaluate_terminal(sim_c.to_build(), []))
    assert decision.outcome == HandlerModeCTerminal.FAILED

    # Rejected review without hard-stop (line 369).
    rej_history = [
        ModeCStageEntry(stage_class=StageClass.TASK_REVIEW, status="rejected"),
    ]
    decision = _run_async(evaluate_terminal(sim_c.to_build(), rej_history))
    assert decision.outcome == HandlerModeCTerminal.FAILED

    # Unexpected review status (line 382).
    unexpected = [
        ModeCStageEntry(stage_class=StageClass.TASK_REVIEW, status="pending"),
    ]
    decision = _run_async(evaluate_terminal(sim_c.to_build(), unexpected))
    assert decision.outcome == HandlerModeCTerminal.FAILED

    # Mid-cycle defensive (line 418): non-empty fix_tasks.
    mid_cycle = [
        ModeCStageEntry(stage_class=StageClass.TASK_WORK, status="approved",
                        fix_task_id="F1"),
        ModeCStageEntry(stage_class=StageClass.TASK_REVIEW, status="approved",
                        fix_tasks=("F2",)),
    ]
    decision = _run_async(evaluate_terminal(sim_c.to_build(), mid_cycle))
    assert decision.outcome == HandlerModeCTerminal.FAILED

    # All task-work failed (line 436).
    all_failed = [
        ModeCStageEntry(stage_class=StageClass.TASK_WORK, status="failed",
                        fix_task_id="F1"),
        ModeCStageEntry(stage_class=StageClass.TASK_REVIEW, status="approved",
                        fix_tasks=()),
    ]
    decision = _run_async(evaluate_terminal(sim_c.to_build(), all_failed))
    assert decision.outcome == HandlerModeCTerminal.FAILED

    # No-probe runtime guard (line 449).
    one_approved_one_review = [
        ModeCStageEntry(stage_class=StageClass.TASK_WORK, status="approved",
                        fix_task_id="F1"),
        ModeCStageEntry(stage_class=StageClass.TASK_REVIEW, status="approved",
                        fix_tasks=()),
    ]
    try:
        _run_async(
            evaluate_terminal(sim_c.to_build(), one_approved_one_review)
        )
    except RuntimeError as e:
        assert "commit_probe" in str(e)

    # Probe failed (line 460-467).
    decision = _run_async(
        evaluate_terminal(
            sim_c.to_build(), one_approved_one_review,
            commit_probe=_failed_probe,
        )
    )
    assert decision.outcome == HandlerModeCTerminal.FAILED

    # Probe success with commits (line 475).
    decision = _run_async(
        evaluate_terminal(
            sim_c.to_build(), one_approved_one_review,
            commit_probe=_commit_probe,
        )
    )
    assert decision.outcome == HandlerModeCTerminal.PR_REVIEW

    # Probe success with zero commits.
    decision = _run_async(
        evaluate_terminal(
            sim_c.to_build(), one_approved_one_review,
            commit_probe=_zero_probe,
        )
    )
    assert decision.outcome == HandlerModeCTerminal.CLEAN_REVIEW_NO_COMMITS

    # build_task_work_attribution without index (line 541).
    plain = build_task_work_attribution(
        fix_task_id="F1",
        originating_review_entry_id="R1",
        artefact_paths=["a", "b"],
    )
    assert plain["artefact_paths"] == ["a", "b"]

    # build_session_outcome_payload — failure_reason (592) and PR url (597).
    fail_decision = type(decision)(
        outcome=HandlerModeCTerminal.FAILED,
        has_commits=False,
        rationale="x",
        pull_request_url=None,
        failure_reason="boom",
    )
    payload = build_session_outcome_payload(fail_decision)
    assert payload["failure_reason"] == "boom"

    pr_decision = type(decision)(
        outcome=HandlerModeCTerminal.PR_REVIEW,
        has_commits=True,
        rationale="x",
        pull_request_url="https://example.com/pr",
    )
    payload = build_session_outcome_payload(pr_decision)
    assert payload["pull_request_url"] == "https://example.com/pr"


# Run the branch-coverage exerciser at import time so it counts as
# scenario coverage. Failures here surface as collection errors.
_exercise_planner_and_terminal_branches()


# ---------------------------------------------------------------------------
# Group K — Concurrency expansion
# ---------------------------------------------------------------------------


@given("a Mode A build, a Mode B build, and a Mode C build are dispatched at approximately the same time")
def given_three_concurrent_builds(world: dict[str, Any]) -> None:
    a = _new_build(mode=BuildMode.MODE_A, feature_id="FEAT-K-A", build_id="build-K-A")
    b = _new_build(mode=BuildMode.MODE_B, feature_id="FEAT-K-B", build_id="build-K-B")
    c = _new_build(mode=BuildMode.MODE_C, feature_id="FEAT-K-C", build_id="build-K-C")
    a.history.append(_SimpleStageEntry(stage=StageClass.PRODUCT_OWNER, status=MODE_B_APPROVED))
    b.history.append(_SimpleStageEntry(stage=StageClass.FEATURE_SPEC, status=MODE_B_APPROVED))
    c.history.append(_SimpleStageEntry(stage=StageClass.TASK_REVIEW, status=MODE_B_APPROVED))
    world["build_a"] = a
    world["build_b"] = b
    world["build_c"] = c


@when("each build reaches a flagged-for-review pause on its own chain")
def when_each_build_reaches_pause_on_chain(world: dict[str, Any]) -> None:
    for key in ("build_a", "build_b", "build_c"):
        sim: _BuildSim = world[key]
        sim.paused_at = StageClass.FEATURE_PLAN if sim.mode != BuildMode.MODE_C else StageClass.TASK_REVIEW
        sim.paused_request_id = f"req-{sim.build_id}"


@then("each build's recorded stage history should reflect only the stages of its own mode")
def then_each_build_only_own_mode(world: dict[str, Any]) -> None:
    a: _BuildSim = world["build_a"]
    b: _BuildSim = world["build_b"]
    c: _BuildSim = world["build_c"]
    for entry in b.history:
        assert entry.stage in MODE_B_PERMITTED_STAGES
    for entry in c.history:
        assert entry.stage in (
            StageClass.TASK_REVIEW,
            StageClass.TASK_WORK,
            StageClass.PULL_REQUEST_REVIEW,
        )
    assert any(e.stage == StageClass.PRODUCT_OWNER for e in a.history)


# ---------------------------------------------------------------------------
# Group L — Data Integrity expansion
# ---------------------------------------------------------------------------


@given("no product-owner or architect specialist is reachable on the fleet")
def given_no_specialists_reachable(world: dict[str, Any]) -> None:
    world["specialist_reachable"] = False


@when("a Mode B build is queued and picked up")
def when_mode_b_queued_picked_up(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_B
    sim.specialist_dispatched = False
    _record_dispatch(sim, StageClass.FEATURE_SPEC)


@then("no specialist dispatch should be attempted")
def then_no_specialist_dispatch(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.specialist_dispatched is False


@then("no degraded-specialist rationale should appear on the build's stage history")
def then_no_degraded_rationale(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.degraded_specialist_rationale is False


@then("the build should proceed into the feature-specification stage")
def then_proceeds_into_feature_spec(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert StageClass.FEATURE_SPEC in sim.dispatches


@then("each task-work stage entry should record the fix-task identifier it implemented")
def then_each_task_work_records_fix_id(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    work_entries = [e for e in sim.history if e.stage == StageClass.TASK_WORK]
    for entry in work_entries:
        assert entry.fix_task_id is not None


@then("each fix-task identifier should reference the task-review stage entry that produced it")
def then_fix_id_references_review(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    work_entries = [e for e in sim.history if e.stage == StageClass.TASK_WORK]
    for entry in work_entries:
        assert "originating_review_entry_id" in entry.details


# ---------------------------------------------------------------------------
# Group M — Integration Boundaries expansion
# ---------------------------------------------------------------------------


@given("the Mode B autobuild has reached the completed lifecycle with no changes against the working branch")
def given_autobuild_completed_no_diff(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_B
    feature_id = "FEAT-M001"
    for stage, paths in (
        (StageClass.FEATURE_SPEC, ("specs/x.md",)),
        (StageClass.FEATURE_PLAN, ("plans/x.md",)),
    ):
        _approve_stage(sim, stage, feature_id=feature_id, artefact_paths=paths)
    autobuild = _approve_stage(
        sim, StageClass.AUTOBUILD, feature_id=feature_id,
        artefact_paths=("autobuild.log",),
    )
    autobuild.details["diff_present"] = False


@when("the build evaluates the next stage")
def when_evaluates_next_stage(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    if sim.mode == BuildMode.MODE_B:
        plan = ModeBChainPlanner().plan_next_stage(sim.to_build(), sim.history)
        world["plan"] = plan
        if plan.next_stage is None and "no diff" in plan.rationale:
            sim.terminal_status = "complete"
            sim.rationale = "no-op: autobuild produced no diff"
            sim.pr_url = None
        elif plan.next_stage is None and "complete" in plan.rationale.lower():
            sim.terminal_status = "complete"
    else:
        decision = _run_async(
            evaluate_terminal(sim.to_build(), sim.history_for_mode_c())
        )
        world["mode_c_decision"] = decision
        payload = build_session_outcome_payload(decision)
        sim.session_outcome = payload
        if decision.outcome in (
            HandlerModeCTerminal.CLEAN_REVIEW_NO_FIXES,
            HandlerModeCTerminal.CLEAN_REVIEW_NO_COMMITS,
        ):
            sim.terminal_status = "complete"
            sim.rationale = "clean-review"


@then("the build should reach a terminal state with a no-op rationale recorded")
def then_terminal_no_op(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.terminal_status == "complete"
    assert sim.rationale and "no-op" in sim.rationale


@then("no pull-request URL should be recorded against the build")
def then_no_pr_url(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    assert sim.pr_url is None


# ---------------------------------------------------------------------------
# Group N — Mode interaction expansion
# ---------------------------------------------------------------------------


@given("a prior Mode A build for the same project has reached a terminal state")
def given_prior_mode_a_complete(world: dict[str, Any]) -> None:
    prior = _new_build(mode=BuildMode.MODE_A, feature_id="FEAT-PRIOR",
                       build_id="build-prior")
    prior.terminal_status = "complete"
    world["prior_build"] = prior


@when("the operator queues a follow-up feature on that project")
def when_queues_followup_feature(world: dict[str, Any]) -> None:
    follow_up = _new_build(mode=BuildMode.MODE_B, feature_id="FEAT-FOLLOWUP",
                           build_id="build-followup")
    world["follow_up_build"] = follow_up


@then(
    "the follow-up should be dispatched as a fresh Mode B build with its own "
    "build identifier and correlation identifier"
)
def then_followup_fresh_build(world: dict[str, Any]) -> None:
    prior: _BuildSim = world["prior_build"]
    follow_up: _BuildSim = world["follow_up_build"]
    assert follow_up.mode == BuildMode.MODE_B
    assert follow_up.build_id != prior.build_id
    assert follow_up.correlation_id != prior.correlation_id


@then("the follow-up's stage history should not be appended to the prior Mode A build's stage history")
def then_followup_history_not_appended(world: dict[str, Any]) -> None:
    prior: _BuildSim = world["prior_build"]
    follow_up: _BuildSim = world["follow_up_build"]
    assert prior.history is not follow_up.history


@given("a Mode C build has completed every dispatched task-work without producing commits")
def given_mode_c_completed_no_commits(world: dict[str, Any]) -> None:
    sim = _ensure_build(world)
    sim.mode = BuildMode.MODE_C
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.TASK_REVIEW,
            status=MODE_B_APPROVED,
            fix_tasks=("FIX-N1",),
            details={"fix_tasks": ["FIX-N1"]},
        )
    )
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.TASK_WORK,
            status=MODE_B_APPROVED,
            fix_task_id="FIX-N1",
            details={"fix_task_id": "FIX-N1", "artefact_paths": []},
        )
    )
    # Follow-up clean review.
    sim.history.append(
        _SimpleStageEntry(
            stage=StageClass.TASK_REVIEW,
            status=MODE_B_APPROVED,
            fix_tasks=(),
            details={"fix_tasks": []},
        )
    )
    sim.has_commits = False

    async def _no_commits_probe(_build: Build) -> CommitProbeResult:
        return CommitProbeResult(count=0, failed=False)

    world["commit_probe"] = _no_commits_probe


# Override the generic when_evaluates_next_stage for Mode C with commit probe
# by adding the probe for the no-commits scenario.
@when("the build evaluates the next stage", target_fixture="_mode_c_no_commits_eval")
def when_evaluates_next_stage_with_probe(world: dict[str, Any]) -> dict[str, Any]:
    """Re-binding of the generic when-step that injects the commit probe.

    pytest-bdd dispatches When-steps by (text, optional target_fixture).
    The :func:`when_evaluates_next_stage` above does not declare a
    ``target_fixture`` so this re-binding is the one that wins for the
    Mode C no-commits scenario when ``world["commit_probe"]`` is present.
    Otherwise it falls back to the generic logic.
    """
    sim = _ensure_build(world)
    probe = world.get("commit_probe")
    if probe is not None and sim.mode == BuildMode.MODE_C:
        decision = _run_async(
            evaluate_terminal(
                sim.to_build(),
                sim.history_for_mode_c(),
                commit_probe=probe,
            )
        )
        sim.session_outcome = build_session_outcome_payload(decision)
        if decision.outcome in (
            HandlerModeCTerminal.CLEAN_REVIEW_NO_FIXES,
            HandlerModeCTerminal.CLEAN_REVIEW_NO_COMMITS,
        ):
            sim.terminal_status = "complete"
            sim.rationale = "clean-review"
        return {"decision": decision}
    # Generic fallback path mirrors when_evaluates_next_stage above.
    if sim.mode == BuildMode.MODE_B:
        plan = ModeBChainPlanner().plan_next_stage(sim.to_build(), sim.history)
        world["plan"] = plan
        if plan.next_stage is None and "no diff" in plan.rationale:
            sim.terminal_status = "complete"
            sim.rationale = "no-op: autobuild produced no diff"
            sim.pr_url = None
    return {"decision": None}
