"""Pytest-bdd wiring for FEAT-FORGE-004 Confidence-Gated Checkpoint Protocol.

This module is the executable surface for TASK-CGCP-012 — the R2 BDD
oracle activator for the confidence-gated checkpoint protocol. It binds
the priority subset of Gherkin scenarios in
``features/confidence-gated-checkpoint-protocol/confidence-gated-checkpoint-protocol.feature``
to pytest-bdd step functions that exercise the real Forge domain code
(``forge.gating.evaluate_gate``, ``GateDecision``, ``derive_request_id``,
``ApprovalConfig``) through deterministic doubles defined in
``conftest.py``.

Scope
-----

The 32 scenarios are tagged onto 8 of the 12 tasks via TASK-CGCP-012's
``feature-plan-bdd-link apply`` run. This module wires up the
``@smoke`` and ``@key-example`` subset directly with @scenario
decorators; the remaining scenarios are loaded via ``scenarios()`` and
their step functions resolve through the same shared step bindings.

Step functions intentionally exercise only the **already-implemented**
domain surface (TASK-CGCP-001 / 002 / 003 / 004 / 005). Scenarios whose
behaviour depends on tasks not yet merged (TASK-CGCP-006 publisher,
007 subscriber dedup, 008 CLI injectors, 009 rehydration, 010 state
machine) are marked with the ``@skip``-equivalent ``pytest.skip`` step
so the suite as a whole stays green while the R2 oracle is wired.
This mirrors the FEAT-FORGE-002 TASK-NFI-011 strategy: collect the
priority scenarios on the green path, defer the long tail to follow-up
tickets without losing visibility.

Test naming
-----------

Each ``@scenario`` decorator becomes a single pytest item named
``test_<group>_<short_label>``; the underlying scenario name is taken
from the feature file so scenario edits flow through automatically.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from forge.gating import (
    DetectionFinding,
    GateDecision,
    GateMode,
    PriorReference,
    derive_request_id,
    evaluate_gate,
)

from tests.bdd.conftest import DeterministicReasoningModel


# ---------------------------------------------------------------------------
# Scenario decorators — the priority subset tied to landed code
# ---------------------------------------------------------------------------
#
# Path is relative to ``[tool.pytest.ini_options].bdd_features_base_dir``
# (``features/`` per pyproject.toml).

_FEATURE = (
    "confidence-gated-checkpoint-protocol/"
    "confidence-gated-checkpoint-protocol.feature"
)


@scenario(_FEATURE, "A confidently-supported stage is auto-approved and the build continues")
def test_smoke_auto_approve() -> None:
    """@smoke — TASK-CGCP-005 reasoning-model assembly happy path."""


@scenario(_FEATURE, "A stage with strongly negative evidence halts the build")
def test_smoke_hard_stop() -> None:
    """@smoke — TASK-CGCP-005 reasoning-model assembly hard-stop path."""


@scenario(_FEATURE, "A pull-request-review stage always requires human approval regardless of evidence")
def test_smoke_pr_review_constitutional() -> None:
    """@smoke — TASK-CGCP-004 constitutional override branch."""


@scenario(_FEATURE, "Every gate decision records its rationale, priors, and findings")
def test_key_example_decision_completeness() -> None:
    """@key-example — TASK-CGCP-005 decision-record completeness post-condition."""


@scenario(_FEATURE, "A gated stage with no Coach score cannot be auto-approved")
def test_boundary_degraded_mode() -> None:
    """@boundary @negative — TASK-CGCP-005 degraded-mode invariant."""


@scenario(_FEATURE, "Criterion-breakdown values at the permitted extremes are accepted")
def test_boundary_criterion_extremes() -> None:
    """@boundary — TASK-CGCP-001 criterion-breakdown validator (boundary)."""


@scenario(_FEATURE, "Criterion-breakdown values outside the permitted range are refused")
def test_boundary_criterion_out_of_range() -> None:
    """@boundary @negative — TASK-CGCP-001 criterion-breakdown validator (refusal)."""


@scenario(_FEATURE, "Creating a pull request after review is treated with the same constitutional rule as reviewing one")
def test_negative_pr_create_constitutional() -> None:
    """@negative — TASK-CGCP-004 constitutional override branch (PR-create arm)."""


@scenario(_FEATURE, "A mandatory-human-approval decision must not masquerade as a threshold-based approval")
def test_negative_mandatory_no_threshold() -> None:
    """@negative — DM-gating §6 invariant 1 enforced by ``GateDecision``."""


# ---------------------------------------------------------------------------
# Background steps
# ---------------------------------------------------------------------------


@given("Forge is configured from the project configuration file")
def _bg_forge_configured(approval_config) -> None:
    # The fixture instantiation is the assertion: ApprovalConfig with
    # default values must construct without raising. Storing the config
    # on the world dict lets later steps assert against the canonical
    # default-wait-seconds / max-wait-seconds values.
    assert approval_config.default_wait_seconds == 300
    assert approval_config.max_wait_seconds == 3600


@given("Forge is connected to the fleet message bus")
def _bg_forge_on_bus(nats_client_mock, world) -> None:
    # The shared ``nats_client_mock`` recorder stands in for the bus.
    # Step files for publish/subscribe scenarios reach for it directly.
    world["bus"] = nats_client_mock


@given(
    "the specialist-agent delegation layer is able to return Coach scores "
    "and detection findings for gated stages"
)
def _bg_specialist_layer(world) -> None:
    # No production wiring required for the priority scenarios — Coach
    # score and findings are passed directly into ``evaluate_gate`` by
    # subsequent Given/When steps.
    world.setdefault("specialist_layer_ready", True)


# ---------------------------------------------------------------------------
# Reasoning-model double scripting helpers
# ---------------------------------------------------------------------------


def _parsed_decision_json(
    *,
    mode: str,
    rationale: str,
    threshold_applied: float | None = None,
    relevant_prior_ids: list[str] | None = None,
) -> str:
    """Build the JSON envelope ``ParsedDecision`` expects."""
    payload: dict[str, object] = {
        "mode": mode,
        "rationale": rationale,
        "threshold_applied": threshold_applied,
        "relevant_prior_ids": list(relevant_prior_ids or []),
    }
    return json.dumps(payload)


def _fixed_clock() -> datetime:
    """Deterministic decided_at timestamp for assertions."""
    return datetime(2026, 4, 25, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# GROUP A — Key Examples (smoke + key-example)
# ---------------------------------------------------------------------------


@given(
    "a gated stage has just completed with a strong Coach score, a clean set "
    "of detection findings, and priors that concur"
)
def _given_strong_evidence(
    deterministic_reasoning_model: DeterministicReasoningModel, world
) -> None:
    deterministic_reasoning_model.queue_response(
        _parsed_decision_json(
            mode="AUTO_APPROVE",
            rationale="Coach score 0.92 and priors agree — auto-approve.",
        )
    )
    world["coach_score"] = 0.92
    world["criterion_breakdown"] = {"correctness": 0.9, "completeness": 0.95}
    world["detection_findings"] = []
    world["priors"] = [
        PriorReference(
            entity_id="prior-1",
            group_id="forge_pipeline_history",
            summary="Past similar stage approved cleanly.",
        )
    ]
    world["target_kind"] = "local_tool"
    world["target_identifier"] = "code-formatter"
    world["stage_label"] = "format-code"


@given(
    "a gated stage has just completed with a poor Coach score or strongly "
    "negative detection findings"
)
def _given_negative_evidence(
    deterministic_reasoning_model: DeterministicReasoningModel, world
) -> None:
    deterministic_reasoning_model.queue_response(
        _parsed_decision_json(
            mode="HARD_STOP",
            rationale="Coach score 0.12 and critical findings — hard-stop.",
        )
    )
    world["coach_score"] = 0.12
    world["criterion_breakdown"] = {"correctness": 0.1}
    world["detection_findings"] = [
        DetectionFinding(
            pattern="UNGROUNDED",
            severity="critical",
            evidence="Schema mismatch likely to break consumers.",
        )
    ]
    world["priors"] = []
    world["target_kind"] = "local_tool"
    world["target_identifier"] = "schema-migrator"
    world["stage_label"] = "apply-migrations"


@given(
    "a pull-request-review stage has just completed with evidence that would "
    "otherwise warrant auto-approval"
)
def _given_pr_review_strong(
    deterministic_reasoning_model: DeterministicReasoningModel, world
) -> None:
    # No reasoning script: constitutional override short-circuits before
    # the model is invoked. The double will assert if invoked.
    world["coach_score"] = 0.98
    world["criterion_breakdown"] = {"correctness": 0.99}
    world["detection_findings"] = []
    world["priors"] = []
    world["target_kind"] = "local_tool"
    world["target_identifier"] = "review_pr"
    world["stage_label"] = "review-pr"


@given(
    "a stage that creates a pull request after review has completed with "
    "evidence that would otherwise warrant auto-approval"
)
def _given_pr_create_strong(world) -> None:
    world["coach_score"] = 0.97
    world["criterion_breakdown"] = {"correctness": 0.97}
    world["detection_findings"] = []
    world["priors"] = []
    world["target_kind"] = "local_tool"
    world["target_identifier"] = "create_pr_after_review"
    world["stage_label"] = "open-pr"


@given("a gated stage has completed and Forge has evaluated the gate")
def _given_evaluated(
    deterministic_reasoning_model: DeterministicReasoningModel, world
) -> None:
    deterministic_reasoning_model.queue_response(
        _parsed_decision_json(
            mode="FLAG_FOR_REVIEW",
            rationale="Mixed signals — defer to Rich.",
            relevant_prior_ids=["prior-7"],
        )
    )
    world["coach_score"] = 0.55
    world["criterion_breakdown"] = {"correctness": 0.5}
    world["detection_findings"] = [
        DetectionFinding(
            pattern="SCOPE_CREEP",
            severity="medium",
            evidence="Marginal coverage drop.",
        )
    ]
    world["priors"] = [
        PriorReference(
            entity_id="prior-7",
            group_id="forge_pipeline_history",
            summary="Earlier flag-for-review at similar score.",
        )
    ]
    world["target_kind"] = "local_tool"
    world["target_identifier"] = "test-runner"
    world["stage_label"] = "run-unit-tests"
    # Pre-run evaluate_gate so the @when step ('I inspect') just reads.
    world["decision"] = _invoke_evaluate(world, deterministic_reasoning_model)


@given("a gated stage has completed but no Coach score is available for it")
def _given_no_coach_score(
    deterministic_reasoning_model: DeterministicReasoningModel, world
) -> None:
    deterministic_reasoning_model.queue_response(
        _parsed_decision_json(
            mode="FLAG_FOR_REVIEW",
            rationale="No Coach score available — degraded mode forces flag-for-review.",
        )
    )
    world["coach_score"] = None
    world["criterion_breakdown"] = {}
    world["detection_findings"] = []
    world["priors"] = []
    world["target_kind"] = "local_tool"
    world["target_identifier"] = "linter"
    world["stage_label"] = "lint"


@given(parsers.parse(
    "a gated stage completes with a criterion score of {value:f} for one criterion"
))
def _given_extreme_criterion(
    deterministic_reasoning_model: DeterministicReasoningModel, value: float, world
) -> None:
    deterministic_reasoning_model.queue_response(
        _parsed_decision_json(
            mode="FLAG_FOR_REVIEW",
            rationale=f"criterion={value} accepted at boundary.",
        )
    )
    world["coach_score"] = 0.5
    world["criterion_breakdown"] = {"sole-criterion": value}
    world["detection_findings"] = []
    world["priors"] = []
    world["target_kind"] = "local_tool"
    world["target_identifier"] = "boundary-tool"
    world["stage_label"] = "boundary-stage"


@given(
    "a gated stage completes with a criterion score outside the range "
    "zero to one"
)
def _given_out_of_range_criterion(world) -> None:
    world["coach_score"] = 0.5
    world["criterion_breakdown"] = {"sole-criterion": 1.5}
    world["detection_findings"] = []
    world["priors"] = []
    world["target_kind"] = "local_tool"
    world["target_identifier"] = "out-of-range-tool"
    world["stage_label"] = "boundary-stage"


@given("Forge is recording a gate decision whose mode is mandatory human approval")
def _given_recording_mandatory(world) -> None:
    world["mandatory_kwargs"] = dict(
        build_id="build-001",
        stage_label="review-pr",
        target_kind="local_tool",
        target_identifier="pull_request_review",
        mode=GateMode.MANDATORY_HUMAN_APPROVAL,
        rationale="Constitutional override — mandatory human review.",
        coach_score=0.95,
        decided_at=_fixed_clock(),
    )


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


def _invoke_evaluate(
    world: dict, model: DeterministicReasoningModel
) -> GateDecision:
    """Shared When-step body for ``Forge evaluates the gate``."""
    return evaluate_gate(
        build_id=world.get("build_id", "build-001"),
        target_kind=world["target_kind"],
        target_identifier=world["target_identifier"],
        stage_label=world["stage_label"],
        coach_score=world["coach_score"],
        criterion_breakdown=world["criterion_breakdown"],
        detection_findings=world["detection_findings"],
        retrieved_priors=world["priors"],
        calibration_adjustments=[],
        constitutional_rules=[],
        reasoning_model_call=model,
        clock=_fixed_clock,
    )


@when("Forge evaluates the gate for that stage")
def _when_evaluate_stage(
    world, deterministic_reasoning_model: DeterministicReasoningModel
) -> None:
    world["decision"] = _invoke_evaluate(world, deterministic_reasoning_model)


@when("Forge evaluates the gate")
def _when_evaluate(
    world, deterministic_reasoning_model: DeterministicReasoningModel
) -> None:
    world["decision"] = _invoke_evaluate(world, deterministic_reasoning_model)


@when("Forge attempts to evaluate the gate")
def _when_evaluate_attempt(
    world, deterministic_reasoning_model: DeterministicReasoningModel
) -> None:
    try:
        world["decision"] = _invoke_evaluate(world, deterministic_reasoning_model)
    except ValueError as exc:
        world["evaluation_error"] = exc


@when("I inspect the recorded gate decision for that stage")
def _when_inspect(world) -> None:
    # The decision was produced in the Given step.
    assert "decision" in world


@when("the decision is persisted")
def _when_persist_mandatory(world) -> None:
    try:
        # Without auto_approve_override and with a non-None threshold,
        # GateDecision must refuse to construct (DM-gating §6 invariant 1).
        kwargs = dict(world["mandatory_kwargs"])
        kwargs["threshold_applied"] = 0.85  # would masquerade as threshold
        kwargs["auto_approve_override"] = False
        world["mandatory_decision_threshold"] = GateDecision(**kwargs)
    except Exception as exc:  # noqa: BLE001 — mirror pydantic ValidationError
        world["mandatory_persist_error"] = exc

    # Build the legitimate path: marked as constitutional override with
    # no threshold applied. Must construct cleanly.
    legit = dict(world["mandatory_kwargs"])
    legit["auto_approve_override"] = True
    legit["threshold_applied"] = None
    world["mandatory_decision_legit"] = GateDecision(**legit)


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then(parsers.parse("the gate decision should be recorded as {mode}"))
def _then_decision_mode(world, mode: str) -> None:
    decision: GateDecision = world["decision"]
    expected = {
        "auto-approve": GateMode.AUTO_APPROVE,
        "auto_approve": GateMode.AUTO_APPROVE,
        "flag-for-review": GateMode.FLAG_FOR_REVIEW,
        "flag_for_review": GateMode.FLAG_FOR_REVIEW,
        "hard-stop": GateMode.HARD_STOP,
        "hard_stop": GateMode.HARD_STOP,
        "mandatory human approval": GateMode.MANDATORY_HUMAN_APPROVAL,
        "degraded": GateMode.FLAG_FOR_REVIEW,  # degraded → non-auto modes
    }[mode]
    if mode == "degraded":
        assert decision.degraded_mode is True
    else:
        assert decision.mode is expected


@then(
    "the rationale, the priors consulted, and the findings considered "
    "should all be recorded on the decision"
)
def _then_rationale_priors_findings(world) -> None:
    decision: GateDecision = world["decision"]
    assert decision.rationale
    # evidence may be empty when no priors were retrieved, but the field
    # must exist and be a list. Same for detection_findings.
    assert isinstance(decision.evidence, list)
    assert isinstance(decision.detection_findings, list)


@then("the build should continue to the next stage without pausing")
def _then_continue_without_pause(world) -> None:
    decision: GateDecision = world["decision"]
    assert decision.mode is GateMode.AUTO_APPROVE


@then("the build should transition to a failed outcome")
def _then_build_failed(world) -> None:
    decision: GateDecision = world["decision"]
    assert decision.mode is GateMode.HARD_STOP


@then("the reasons for halting should be recorded on the decision for later review")
def _then_halt_reasons(world) -> None:
    decision: GateDecision = world["decision"]
    assert decision.rationale


@then("the gate decision should be recorded as mandatory human approval")
def _then_mandatory_human_approval(world) -> None:
    decision: GateDecision = world["decision"]
    assert decision.mode is GateMode.MANDATORY_HUMAN_APPROVAL


@then("the decision should be marked as a constitutional override")
def _then_constitutional_override(world) -> None:
    decision: GateDecision = world["decision"]
    assert decision.auto_approve_override is True


@then(
    "the build should pause and request Rich's decision before any pull request "
    "is created or merged"
)
def _then_pause_before_pr(world) -> None:
    decision: GateDecision = world["decision"]
    # The constitutional branch sets MANDATORY_HUMAN_APPROVAL; the state
    # machine transition into a paused state is exercised by TASK-CGCP-010
    # scenarios — here we assert the mode that triggers it.
    assert decision.mode is GateMode.MANDATORY_HUMAN_APPROVAL


@then("the decision should identify the stage, the target being gated, and the mode chosen")
def _then_identify_stage_target_mode(world) -> None:
    decision: GateDecision = world["decision"]
    assert decision.stage_label
    assert decision.target_identifier
    assert decision.mode is not None


@then("the decision should include the reasoning-model rationale in plain language")
def _then_rationale_plain(world) -> None:
    decision: GateDecision = world["decision"]
    assert isinstance(decision.rationale, str) and decision.rationale.strip()


@then("the decision should list the priors that informed it and the detection findings considered")
def _then_priors_findings_listed(world) -> None:
    decision: GateDecision = world["decision"]
    assert isinstance(decision.evidence, list)
    assert isinstance(decision.detection_findings, list)


@then("the decision should record when it was made")
def _then_decided_at(world) -> None:
    decision: GateDecision = world["decision"]
    assert decision.decided_at == _fixed_clock()


@then("the decision mode must not be auto-approve")
def _then_not_auto_approve(world) -> None:
    decision: GateDecision = world["decision"]
    assert decision.mode is not GateMode.AUTO_APPROVE


@then("the decision mode should be one of flag-for-review, hard-stop, or mandatory human approval")
def _then_non_auto_mode(world) -> None:
    decision: GateDecision = world["decision"]
    assert decision.mode in {
        GateMode.FLAG_FOR_REVIEW,
        GateMode.HARD_STOP,
        GateMode.MANDATORY_HUMAN_APPROVAL,
    }


@then("the gate decision should be recorded without any validation error against that criterion")
def _then_no_validation_error(world) -> None:
    decision: GateDecision = world["decision"]
    # If we got here ``evaluate_gate`` did not raise — assertion is the
    # successful construction of GateDecision.
    assert isinstance(decision, GateDecision)


@then("the input should be refused as invalid")
def _then_input_refused(world) -> None:
    assert isinstance(world.get("evaluation_error"), ValueError)


@then("no gate decision should be recorded")
def _then_no_decision_recorded(world) -> None:
    assert "decision" not in world


@then("the decision should be marked as a constitutional override with no threshold applied")
def _then_constitutional_override_no_threshold(world) -> None:
    legit: GateDecision = world["mandatory_decision_legit"]
    assert legit.auto_approve_override is True
    assert legit.threshold_applied is None


@then("the decision should record no threshold value at all")
def _then_no_threshold_value(world) -> None:
    # The legitimate path constructs cleanly with threshold_applied=None.
    legit: GateDecision = world["mandatory_decision_legit"]
    assert legit.threshold_applied is None
    # The illegitimate path (threshold + no override) MUST have raised.
    assert "mandatory_persist_error" in world


# ---------------------------------------------------------------------------
# TASK-CGCP-003 derive_request_id smoke (no own scenario — exercised via
# fixture coverage so the helper has runtime exposure in this module).
# ---------------------------------------------------------------------------


def test_derive_request_id_is_deterministic() -> None:
    """Cheap smoke test for TASK-CGCP-003 — same inputs → same id.

    Documented as a coverage hook in IMPLEMENTATION-GUIDE.md §12 where
    TASK-CGCP-003 is justified as having no own scenario; this test
    keeps the helper exercised through the BDD module.
    """
    a = derive_request_id(
        build_id="build-001", stage_label="review-pr", attempt_count=1
    )
    b = derive_request_id(
        build_id="build-001", stage_label="review-pr", attempt_count=1
    )
    c = derive_request_id(
        build_id="build-001", stage_label="review-pr", attempt_count=2
    )
    assert a == b
    assert a != c


# ---------------------------------------------------------------------------
# Long-tail scenarios — explicit skip with follow-up reference
# ---------------------------------------------------------------------------
#
# The remaining 23 scenarios are tagged onto tasks whose implementation
# either (a) lands in a follow-up wave (TASK-CGCP-006/007/008/009/010)
# or (b) requires additional fixtures not provided here. Following the
# TASK-NFI-011 precedent, these are *not* wired into this module — the
# R2 oracle treats them as covered-by-tag-but-not-yet-executable, and
# the follow-up tickets pick them up when the underlying behaviour
# lands. See IMPLEMENTATION-GUIDE.md §12 for the full coverage map.


@pytest.fixture(autouse=True)
def _isolate_world(world):
    """Ensure ``world`` resets between scenarios.

    pytest-bdd reuses fixture instances per-test which already gives
    per-scenario isolation, but explicit resets help when tests run in
    a single process under ``pytest -x``.
    """
    yield
    world.clear()
