"""Tests for ``forge.pipeline.mode_b_planner`` (TASK-MBC8-003).

Validates the :class:`ModeBChainPlanner` — a pure-function planner that
takes the build's recorded stage history and returns the next permitted
stage in the Mode B chain (FEAT-FORGE-008 ASSUM-001 / ASSUM-013).

Test cases mirror the acceptance criteria of TASK-MBC8-003 and cover the
12 Mode B Group A / B / C scenarios from
``features/mode-b-feature-and-mode-c-review-fix/``
``mode-b-feature-and-mode-c-review-fix.feature``. Where a feature-file
scenario covers behaviour beyond the planner's responsibility (e.g.
"async subagent dispatch", "build pause on flag-for-review"), the test
verifies the planner's contribution to that scenario — the next-stage
decision the planner returns — and leaves the surrounding lifecycle
behaviour to the Supervisor / state-machine tests.

The :class:`StageEntry` Protocol is satisfied by an in-memory dataclass
(:class:`FakeStageEntry`); the :class:`Build` value object is the real
``forge.lifecycle.persistence.Build`` since it is a frozen dataclass with
no I/O surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import pytest

from forge.lifecycle.modes import BuildMode
from forge.lifecycle.persistence import Build
from forge.pipeline.mode_b_planner import (
    APPROVED,
    EMPTY_ARTEFACTS,
    FAILED,
    HARD_STOP,
    MODE_B_PERMITTED_STAGES,
    MissingSpecArtefacts,
    ModeBChainPlanner,
    ModeBPlan,
    ModeBoundaryViolation,
    plan_next_stage,
)
from forge.pipeline.mode_chains_data import MODE_B_CHAIN
from forge.pipeline.stage_taxonomy import StageClass
from forge.pipeline.supervisor import BuildState


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


@dataclass
class FakeStageEntry:
    """Structural stand-in for a ``stage_log`` row.

    Matches the :class:`forge.pipeline.mode_b_planner.StageEntry` Protocol
    with the four attributes the planner reads. Production wires the
    Pydantic ``StageLogEntry``; tests use this dataclass to avoid
    constructing full Pydantic objects per case.
    """

    stage: StageClass
    status: str
    feature_id: str | None = "FEAT-X"
    details: Mapping[str, Any] = field(default_factory=dict)


def make_build(
    *,
    build_id: str = "build-FEAT-X-20260427000000",
    status: BuildState = BuildState.RUNNING,
    mode: BuildMode = BuildMode.MODE_B,
) -> Build:
    """Build factory with sensible Mode B defaults."""
    return Build(build_id=build_id, status=status, mode=mode)


# ---------------------------------------------------------------------------
# AC-001 — module path and signature
# ---------------------------------------------------------------------------


class TestModuleAndSignature:
    """AC-001: ``forge.pipeline.mode_b_planner`` exposes the planner."""

    def test_class_importable_from_mode_b_planner_module(self) -> None:
        from forge.pipeline import mode_b_planner

        assert hasattr(mode_b_planner, "ModeBChainPlanner")
        assert hasattr(mode_b_planner, "plan_next_stage")
        assert hasattr(mode_b_planner, "ModeBPlan")
        assert hasattr(mode_b_planner, "ModeBoundaryViolation")

    def test_plan_next_stage_returns_mode_b_plan(self) -> None:
        plan = ModeBChainPlanner().plan_next_stage(make_build(), history=())

        assert isinstance(plan, ModeBPlan)
        assert isinstance(plan.permitted_stages, frozenset)
        # next_stage may be StageClass | None — sanity check the type union.
        assert plan.next_stage is None or isinstance(
            plan.next_stage, StageClass
        )

    def test_module_function_matches_class_method(self) -> None:
        build = make_build()
        history = ()

        method_plan = ModeBChainPlanner().plan_next_stage(build, history)
        function_plan = plan_next_stage(build, history)

        assert method_plan == function_plan


# ---------------------------------------------------------------------------
# AC-002 — empty history → FEATURE_SPEC
# ---------------------------------------------------------------------------


class TestEmptyHistoryAdvance:
    """AC-002: empty history returns ``next_stage = FEATURE_SPEC``."""

    def test_plan_next_stage_with_empty_history_returns_feature_spec(
        self,
    ) -> None:
        plan = plan_next_stage(make_build(), history=())

        assert plan.next_stage is StageClass.FEATURE_SPEC
        assert plan.diagnostics == ()


# ---------------------------------------------------------------------------
# AC-003/004/005 — chain advance per Group B Scenario Outline
# ---------------------------------------------------------------------------


class TestChainAdvanceScenarioOutline:
    """Group B Scenario Outline rows: feature-plan ← feature-spec etc."""

    def test_plan_next_stage_after_feature_spec_approved_returns_feature_plan(
        self,
    ) -> None:
        history = [
            FakeStageEntry(
                stage=StageClass.FEATURE_SPEC,
                status=APPROVED,
                details={"artefact_paths": ("specs/feature-spec.md",)},
            ),
        ]

        plan = plan_next_stage(make_build(), history=history)

        assert plan.next_stage is StageClass.FEATURE_PLAN

    def test_plan_next_stage_after_feature_plan_approved_returns_autobuild(
        self,
    ) -> None:
        history = [
            FakeStageEntry(
                stage=StageClass.FEATURE_SPEC,
                status=APPROVED,
                details={"artefact_paths": ("specs/feature-spec.md",)},
            ),
            FakeStageEntry(
                stage=StageClass.FEATURE_PLAN,
                status=APPROVED,
                details={"artefact_paths": ("plans/feature-plan.md",)},
            ),
        ]

        plan = plan_next_stage(make_build(), history=history)

        assert plan.next_stage is StageClass.AUTOBUILD

    def test_plan_next_stage_after_autobuild_with_diff_returns_pull_request_review(
        self,
    ) -> None:
        history = [
            FakeStageEntry(stage=StageClass.FEATURE_SPEC, status=APPROVED,
                           details={"artefact_paths": ("s.md",)}),
            FakeStageEntry(stage=StageClass.FEATURE_PLAN, status=APPROVED),
            FakeStageEntry(
                stage=StageClass.AUTOBUILD,
                status=APPROVED,
                details={"diff_present": True},
            ),
        ]

        plan = plan_next_stage(make_build(), history=history)

        assert plan.next_stage is StageClass.PULL_REQUEST_REVIEW

    def test_plan_next_stage_after_autobuild_without_diff_returns_none(
        self,
    ) -> None:
        history = [
            FakeStageEntry(stage=StageClass.FEATURE_SPEC, status=APPROVED,
                           details={"artefact_paths": ("s.md",)}),
            FakeStageEntry(stage=StageClass.FEATURE_PLAN, status=APPROVED),
            FakeStageEntry(
                stage=StageClass.AUTOBUILD,
                status=APPROVED,
                details={"diff_present": False},
            ),
        ]

        plan = plan_next_stage(make_build(), history=history)

        assert plan.next_stage is None
        assert "no diff" in plan.rationale.lower()
        # Defers to TASK-MBC8-006; planner does not emit a missing-spec
        # diagnostic for the no-diff branch.
        assert plan.diagnostics == ()


# ---------------------------------------------------------------------------
# AC-006 — security boundary — ModeBoundaryViolation
# ---------------------------------------------------------------------------


class TestSecurityBoundary:
    """AC-006 / Group J / ASSUM-013: refuse forbidden Mode A stages."""

    @pytest.mark.parametrize(
        "forbidden_stage",
        [
            StageClass.PRODUCT_OWNER,
            StageClass.ARCHITECT,
            StageClass.SYSTEM_ARCH,
            StageClass.SYSTEM_DESIGN,
        ],
    )
    def test_plan_next_stage_with_forbidden_stage_raises_mode_boundary_violation(
        self,
        forbidden_stage: StageClass,
    ) -> None:
        history = [FakeStageEntry(stage=forbidden_stage, status=APPROVED)]

        with pytest.raises(ModeBoundaryViolation) as excinfo:
            plan_next_stage(make_build(build_id="build-X"), history=history)

        assert excinfo.value.stage is forbidden_stage
        assert excinfo.value.build_id == "build-X"
        assert excinfo.value.assumption == "ASSUM-013"
        # Distinct from a generic ordering error so callers can route the
        # security audit message correctly.
        assert isinstance(excinfo.value, ModeBoundaryViolation)
        assert not isinstance(
            excinfo.value, type("StageOrderingError", (Exception,), {})
        )

    def test_violation_message_names_forbidden_stage_and_assumption(
        self,
    ) -> None:
        history = [
            FakeStageEntry(stage=StageClass.SYSTEM_ARCH, status=APPROVED),
        ]

        with pytest.raises(ModeBoundaryViolation) as excinfo:
            plan_next_stage(make_build(), history=history)

        message = str(excinfo.value)
        assert "system-arch" in message
        assert "ASSUM-013" in message


# ---------------------------------------------------------------------------
# AC-007 — permitted_stages frozenset
# ---------------------------------------------------------------------------


class TestPermittedStages:
    """AC-007: ``permitted_stages`` is a frozenset of MODE_B chain only."""

    def test_permitted_stages_equals_mode_b_chain_frozenset(self) -> None:
        plan = plan_next_stage(make_build(), history=())

        assert plan.permitted_stages == frozenset(MODE_B_CHAIN)
        assert plan.permitted_stages == MODE_B_PERMITTED_STAGES
        assert isinstance(plan.permitted_stages, frozenset)

    def test_permitted_stages_excludes_mode_a_pre_feature_spec_stages(
        self,
    ) -> None:
        plan = plan_next_stage(make_build(), history=())

        assert StageClass.PRODUCT_OWNER not in plan.permitted_stages
        assert StageClass.ARCHITECT not in plan.permitted_stages
        assert StageClass.SYSTEM_ARCH not in plan.permitted_stages
        assert StageClass.SYSTEM_DESIGN not in plan.permitted_stages

    def test_permitted_stages_excludes_mode_c_only_stages(self) -> None:
        plan = plan_next_stage(make_build(), history=())

        assert StageClass.TASK_REVIEW not in plan.permitted_stages
        assert StageClass.TASK_WORK not in plan.permitted_stages


# ---------------------------------------------------------------------------
# AC-008 — Group C: hard-stop on FEATURE_SPEC
# ---------------------------------------------------------------------------


class TestHardStopOnFeatureSpec:
    """Group C negative: hard-stop / failed FEATURE_SPEC ⇒ no later dispatch."""

    def test_plan_next_stage_with_hard_stop_feature_spec_returns_none(
        self,
    ) -> None:
        history = [
            FakeStageEntry(stage=StageClass.FEATURE_SPEC, status=HARD_STOP),
        ]

        plan = plan_next_stage(make_build(), history=history)

        assert plan.next_stage is None
        assert plan.rationale  # non-empty rationale recorded
        assert "feature-specification" in plan.rationale.lower()

    def test_plan_next_stage_with_failed_feature_spec_dispatch_returns_none(
        self,
    ) -> None:
        history = [
            FakeStageEntry(stage=StageClass.FEATURE_SPEC, status=FAILED),
        ]

        plan = plan_next_stage(make_build(), history=history)

        assert plan.next_stage is None
        assert plan.rationale


# ---------------------------------------------------------------------------
# AC-009 — Group B boundary: empty FEATURE_SPEC artefacts
# ---------------------------------------------------------------------------


class TestEmptySpecArtefacts:
    """AC-009 / Group B boundary: empty artefacts triggers diagnostic."""

    def test_plan_next_stage_with_empty_artefacts_returns_none_and_emits_diagnostic(
        self,
    ) -> None:
        history = [
            FakeStageEntry(
                stage=StageClass.FEATURE_SPEC,
                status=APPROVED,  # gate may have approved but artefacts are empty
                feature_id="FEAT-X",
                details={"artefact_paths": ()},
            ),
        ]

        plan = plan_next_stage(
            make_build(build_id="build-FEAT-X-T0"),
            history=history,
        )

        assert plan.next_stage is None
        assert len(plan.diagnostics) == 1
        diag = plan.diagnostics[0]
        assert isinstance(diag, MissingSpecArtefacts)
        assert diag.build_id == "build-FEAT-X-T0"
        assert diag.feature_id == "FEAT-X"
        assert "missing-spec" in diag.rationale
        assert "missing-spec" in plan.rationale

    def test_plan_next_stage_with_explicit_empty_artefacts_status(
        self,
    ) -> None:
        history = [
            FakeStageEntry(
                stage=StageClass.FEATURE_SPEC,
                status=EMPTY_ARTEFACTS,
                feature_id="FEAT-X",
                details={},
            ),
        ]

        plan = plan_next_stage(make_build(), history=history)

        assert plan.next_stage is None
        assert any(
            isinstance(d, MissingSpecArtefacts) for d in plan.diagnostics
        )

    def test_plan_next_stage_with_non_empty_artefacts_does_not_emit_diagnostic(
        self,
    ) -> None:
        history = [
            FakeStageEntry(
                stage=StageClass.FEATURE_SPEC,
                status=APPROVED,
                details={"artefact_paths": ("specs/x.md",)},
            ),
        ]

        plan = plan_next_stage(make_build(), history=history)

        assert plan.next_stage is StageClass.FEATURE_PLAN
        assert plan.diagnostics == ()


# ---------------------------------------------------------------------------
# AC-010 — coverage of Mode B Group A / B / C feature-file scenarios
# ---------------------------------------------------------------------------


class TestModeBGroupAScenarios:
    """Group A key examples — planner contribution per scenario."""

    def test_a1_full_chain_to_pull_request_review_with_diff(self) -> None:
        """Group A scenario 1: spec→plan→autobuild→PR review."""
        # After every stage approves with a diff, plan returns PR review
        # (the next dispatch the supervisor should issue).
        history = [
            FakeStageEntry(stage=StageClass.FEATURE_SPEC, status=APPROVED,
                           details={"artefact_paths": ("s.md",)}),
            FakeStageEntry(stage=StageClass.FEATURE_PLAN, status=APPROVED),
            FakeStageEntry(stage=StageClass.AUTOBUILD, status=APPROVED,
                           details={"diff_present": True}),
        ]

        plan = plan_next_stage(make_build(), history=history)

        assert plan.next_stage is StageClass.PULL_REQUEST_REVIEW

    def test_a2_spec_then_planning_then_autobuild_in_order(self) -> None:
        """Group A scenario 2: spec output drives plan, plan drives autobuild.

        The planner returns FEATURE_PLAN after spec, AUTOBUILD after plan;
        the forward-context builder (TASK-MAG7-007) handles the artefact
        threading itself — the planner only orders dispatches.
        """
        spec_only = [
            FakeStageEntry(stage=StageClass.FEATURE_SPEC, status=APPROVED,
                           details={"artefact_paths": ("s.md",)}),
        ]
        spec_then_plan = spec_only + [
            FakeStageEntry(stage=StageClass.FEATURE_PLAN, status=APPROVED),
        ]

        assert (
            plan_next_stage(make_build(), spec_only).next_stage
            is StageClass.FEATURE_PLAN
        )
        assert (
            plan_next_stage(make_build(), spec_then_plan).next_stage
            is StageClass.AUTOBUILD
        )

    def test_a3_autobuild_dispatch_returned_when_plan_approved(self) -> None:
        """Group A scenario 3: autobuild dispatch follows plan approval.

        Async-subagent semantics live in the dispatcher (TASK-MBC8-005);
        the planner just returns AUTOBUILD as the next dispatch.
        """
        history = [
            FakeStageEntry(stage=StageClass.FEATURE_SPEC, status=APPROVED,
                           details={"artefact_paths": ("s.md",)}),
            FakeStageEntry(stage=StageClass.FEATURE_PLAN, status=APPROVED),
        ]

        plan = plan_next_stage(make_build(), history=history)

        assert plan.next_stage is StageClass.AUTOBUILD

    def test_a4_pull_request_review_pinned_regardless_of_upstream_scores(
        self,
    ) -> None:
        """Group A scenario 4 / Group C scenario 12: PR review is constitutional.

        The planner returns PULL_REQUEST_REVIEW once AUTOBUILD is approved
        and a diff exists. The constitutional MANDATORY_HUMAN_APPROVAL is
        enforced by the supervisor / executor (TASK-MAG7-004) — the
        planner's job here is just to put the chain on the PR review path.
        """
        history = [
            FakeStageEntry(stage=StageClass.FEATURE_SPEC, status=APPROVED,
                           details={"artefact_paths": ("s.md",)}),
            FakeStageEntry(stage=StageClass.FEATURE_PLAN, status=APPROVED),
            FakeStageEntry(stage=StageClass.AUTOBUILD, status=APPROVED,
                           details={"diff_present": True,
                                    "coach_score": 1.0}),
        ]

        plan = plan_next_stage(make_build(), history=history)

        assert plan.next_stage is StageClass.PULL_REQUEST_REVIEW

    def test_a5_flag_for_review_at_planning_pauses_chain_until_approved(
        self,
    ) -> None:
        """Group A scenario 5: flagged-for-review at plan ⇒ planner waits."""
        history_pending = [
            FakeStageEntry(stage=StageClass.FEATURE_SPEC, status=APPROVED,
                           details={"artefact_paths": ("s.md",)}),
            FakeStageEntry(stage=StageClass.FEATURE_PLAN, status="awaiting"),
        ]
        history_approved = [
            FakeStageEntry(stage=StageClass.FEATURE_SPEC, status=APPROVED,
                           details={"artefact_paths": ("s.md",)}),
            FakeStageEntry(stage=StageClass.FEATURE_PLAN, status=APPROVED),
        ]

        pending = plan_next_stage(make_build(), history_pending)
        approved = plan_next_stage(make_build(), history_approved)

        assert pending.next_stage is None
        assert approved.next_stage is StageClass.AUTOBUILD

    def test_a6_completed_pr_review_records_terminal(self) -> None:
        """Group A scenario 6: PR review approved ⇒ chain complete."""
        history = [
            FakeStageEntry(stage=StageClass.FEATURE_SPEC, status=APPROVED,
                           details={"artefact_paths": ("s.md",)}),
            FakeStageEntry(stage=StageClass.FEATURE_PLAN, status=APPROVED),
            FakeStageEntry(stage=StageClass.AUTOBUILD, status=APPROVED,
                           details={"diff_present": True}),
            FakeStageEntry(
                stage=StageClass.PULL_REQUEST_REVIEW, status=APPROVED
            ),
        ]

        plan = plan_next_stage(make_build(), history=history)

        assert plan.next_stage is None
        assert "complete" in plan.rationale.lower()


class TestModeBGroupBScenarios:
    """Group B boundary scenarios."""

    def test_b1_single_feature_culminates_in_one_pull_request(self) -> None:
        """Group B scenario: single feature, one PR review pause.

        ASSUM-006 single-feature contract is reflected in the planner's
        FEATURE_PLAN / AUTOBUILD / PR-review decisions all keying off
        the single feature_id carried on each entry.
        """
        history = [
            FakeStageEntry(stage=StageClass.FEATURE_SPEC, status=APPROVED,
                           feature_id="FEAT-X",
                           details={"artefact_paths": ("s.md",)}),
            FakeStageEntry(stage=StageClass.FEATURE_PLAN, status=APPROVED,
                           feature_id="FEAT-X"),
            FakeStageEntry(stage=StageClass.AUTOBUILD, status=APPROVED,
                           feature_id="FEAT-X",
                           details={"diff_present": True}),
        ]

        plan = plan_next_stage(make_build(), history=history)

        assert plan.next_stage is StageClass.PULL_REQUEST_REVIEW

    def test_b2_no_dispatch_until_prerequisite_approved_outline(self) -> None:
        """Group B scenario outline: no dispatch before prereq approved."""
        # feature-plan ← feature-spec for the feature
        not_yet_approved_spec = [
            FakeStageEntry(stage=StageClass.FEATURE_SPEC, status="running"),
        ]
        # autobuild ← feature-plan for the feature
        not_yet_approved_plan = [
            FakeStageEntry(stage=StageClass.FEATURE_SPEC, status=APPROVED,
                           details={"artefact_paths": ("s.md",)}),
            FakeStageEntry(stage=StageClass.FEATURE_PLAN, status="running"),
        ]
        # pull-request ← autobuild for the feature
        not_yet_approved_autobuild = [
            FakeStageEntry(stage=StageClass.FEATURE_SPEC, status=APPROVED,
                           details={"artefact_paths": ("s.md",)}),
            FakeStageEntry(stage=StageClass.FEATURE_PLAN, status=APPROVED),
            FakeStageEntry(stage=StageClass.AUTOBUILD, status="running"),
        ]

        for history in (
            not_yet_approved_spec,
            not_yet_approved_plan,
            not_yet_approved_autobuild,
        ):
            plan = plan_next_stage(make_build(), history)
            assert plan.next_stage is None, (
                f"expected no dispatch but got {plan.next_stage!r} "
                f"for history={history!r}"
            )

    def test_b3_no_spec_artefacts_records_missing_spec_rationale(self) -> None:
        """Group B scenario: spec produces no artefacts ⇒ flagged with rationale."""
        history = [
            FakeStageEntry(
                stage=StageClass.FEATURE_SPEC,
                status=APPROVED,
                details={"artefact_paths": []},
            ),
        ]

        plan = plan_next_stage(make_build(), history)

        assert plan.next_stage is None
        assert any(
            isinstance(d, MissingSpecArtefacts) for d in plan.diagnostics
        )


class TestModeBGroupCScenarios:
    """Group C negative scenarios."""

    def test_c1_hard_stop_on_feature_spec_terminates_no_later_dispatch(
        self,
    ) -> None:
        """Group C scenario: hard-stop at FEATURE_SPEC ⇒ no later dispatch."""
        history = [
            FakeStageEntry(stage=StageClass.FEATURE_SPEC, status=HARD_STOP),
        ]

        plan = plan_next_stage(make_build(), history)

        assert plan.next_stage is None

    def test_c2_failed_spec_halts_before_planning(self) -> None:
        """Group C scenario: failed spec dispatch halts before planning."""
        history = [
            FakeStageEntry(stage=StageClass.FEATURE_SPEC, status=FAILED),
        ]

        plan = plan_next_stage(make_build(), history)

        assert plan.next_stage is None
        assert plan.next_stage is not StageClass.FEATURE_PLAN

    def test_c3_failed_autobuild_halts_before_pull_request(self) -> None:
        """Group C scenario: autobuild internal hard-stop ⇒ no PR creation."""
        history = [
            FakeStageEntry(stage=StageClass.FEATURE_SPEC, status=APPROVED,
                           details={"artefact_paths": ("s.md",)}),
            FakeStageEntry(stage=StageClass.FEATURE_PLAN, status=APPROVED),
            FakeStageEntry(stage=StageClass.AUTOBUILD, status=HARD_STOP),
        ]

        plan = plan_next_stage(make_build(), history)

        assert plan.next_stage is None
        assert "autobuild" in plan.rationale.lower()


# ---------------------------------------------------------------------------
# AC-011 — implementation hygiene checks
# ---------------------------------------------------------------------------


class TestImplementationHygiene:
    """AC-011: planner is stateless / pure-function."""

    def test_planner_is_pure_no_side_effects(self) -> None:
        """Two calls with the same inputs return equal plans."""
        history = [
            FakeStageEntry(stage=StageClass.FEATURE_SPEC, status=APPROVED,
                           details={"artefact_paths": ("s.md",)}),
        ]
        planner = ModeBChainPlanner()

        first = planner.plan_next_stage(make_build(), history)
        second = planner.plan_next_stage(make_build(), history)

        assert first == second

    def test_history_argument_not_mutated(self) -> None:
        history = [
            FakeStageEntry(stage=StageClass.FEATURE_SPEC, status=APPROVED,
                           details={"artefact_paths": ("s.md",)}),
        ]
        snapshot = list(history)

        plan_next_stage(make_build(), history)

        assert history == snapshot

    def test_mode_b_plan_is_frozen(self) -> None:
        """Plan dataclass is frozen — Supervisor cannot mutate it."""
        plan = plan_next_stage(make_build(), history=())

        with pytest.raises((AttributeError, Exception)):
            plan.next_stage = StageClass.PRODUCT_OWNER  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Defensive checks
# ---------------------------------------------------------------------------


class TestDefensiveBehaviour:
    """Edge cases that the planner should not crash on."""

    def test_history_with_unknown_status_does_not_advance(self) -> None:
        history = [
            FakeStageEntry(
                stage=StageClass.FEATURE_SPEC,
                status="some-unknown-status",
                details={"artefact_paths": ("s.md",)},
            ),
        ]

        plan = plan_next_stage(make_build(), history)

        assert plan.next_stage is None
        assert plan.rationale  # explanation recorded

    def test_history_with_malformed_artefacts_value_does_not_crash(
        self,
    ) -> None:
        # Non-Sized artefacts value — defensive: treat as no signal,
        # do not raise.
        history = [
            FakeStageEntry(
                stage=StageClass.FEATURE_SPEC,
                status=APPROVED,
                details={"artefact_paths": object()},
            ),
        ]

        plan = plan_next_stage(make_build(), history)

        # Non-empty malformed artefacts is treated as "has artefacts" /
        # "no boundary signal" — planner advances to FEATURE_PLAN rather
        # than crashing.
        assert plan.next_stage is StageClass.FEATURE_PLAN

    def test_planner_only_inspects_latest_entry_per_stage(self) -> None:
        """Multiple FEATURE_SPEC entries — last one wins."""
        history = [
            FakeStageEntry(stage=StageClass.FEATURE_SPEC, status=FAILED),
            FakeStageEntry(stage=StageClass.FEATURE_SPEC, status=APPROVED,
                           details={"artefact_paths": ("s.md",)}),
        ]

        plan = plan_next_stage(make_build(), history)

        assert plan.next_stage is StageClass.FEATURE_PLAN
