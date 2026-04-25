"""Unit tests for ``forge.gating.constitutional`` (TASK-CGCP-004).

Each test class maps to one or more acceptance criteria in
``tasks/design_approved/TASK-CGCP-004-constitutional-override-branch.md``:

* ``TestCheckConstitutionalOverrideMatching``        — AC-001 / AC-008
* ``TestConstitutionalOverrideDecisionFields``       — AC-002 / AC-007
* ``TestEvaluateGateConstitutionalFirst``            — AC-003 / AC-004 / AC-005
* ``TestTwoLayerRegression``                         — AC-006 (Group E)
* ``TestModulePurity``                               — AC-009

AC-010 (lint/format) is enforced by the project's lint pipeline and is
not unit-testable from here.
"""

from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from forge.gating import (
    DetectionFinding,
    GateDecision,
    GateMode,
    PriorReference,
    evaluate_gate,
)
from forge.gating.constitutional import (
    CONSTITUTIONAL_OVERRIDE_RATIONALE,
    CONSTITUTIONAL_OVERRIDE_TARGETS,
    _check_constitutional_override,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decided_at() -> datetime:
    return datetime(2026, 4, 25, 12, 0, 0, tzinfo=UTC)


def _explode_if_called(prompt: str) -> str:  # pragma: no cover - guard only
    """Reasoning-model double that fails the test if it is ever invoked.

    AC-003 demands that the constitutional override branch returns
    immediately without consulting the reasoning model. A test that
    calls :func:`evaluate_gate` with a constitutional ``target_identifier``
    passes this double as ``reasoning_model_call``; if the override
    branch is missing or wired incorrectly, the reasoning model would
    be called and this guard would fail loudly.
    """
    raise AssertionError(
        f"Reasoning model was invoked for a constitutional-override "
        f"target. Prompt fragment: {prompt[:120]!r}",
    )


def _evaluate_gate_kwargs(**overrides: Any) -> dict[str, Any]:
    """Build the minimal-but-valid set of kwargs for :func:`evaluate_gate`.

    Sensible defaults for the inputs that the constitutional branch
    must *ignore* — coach_score, detection_findings, retrieved_priors,
    calibration_adjustments. Tests override only the slots they care
    about.
    """
    base: dict[str, Any] = {
        "build_id": "build-cgcp-004",
        "target_kind": "local_tool",
        "target_identifier": "review_pr",
        "stage_label": "review",
        "coach_score": None,
        "criterion_breakdown": {},
        "detection_findings": [],
        "retrieved_priors": [],
        "calibration_adjustments": [],
        "constitutional_rules": [],
        "reasoning_model_call": _explode_if_called,
        "clock": _decided_at,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# AC-001 / AC-008 — matching set
# ---------------------------------------------------------------------------


class TestCheckConstitutionalOverrideMatching:
    """AC-001 / AC-008: matching set & non-matching identifiers."""

    def test_constitutional_targets_constant_is_module_level_frozenset(self) -> None:
        # Implementation note 1 of TASK-CGCP-004: "matching set ... is a
        # module-level constant — not inlined".
        assert isinstance(CONSTITUTIONAL_OVERRIDE_TARGETS, frozenset)
        assert CONSTITUTIONAL_OVERRIDE_TARGETS == frozenset(
            {"review_pr", "create_pr_after_review"},
        )

    @pytest.mark.parametrize(
        "target_identifier",
        ["review_pr", "create_pr_after_review"],
    )
    def test_matching_identifier_returns_gate_decision(
        self,
        target_identifier: str,
    ) -> None:
        decision = _check_constitutional_override(target_identifier)
        assert isinstance(decision, GateDecision)
        assert decision.target_identifier == target_identifier

    @pytest.mark.parametrize(
        "target_identifier",
        [
            "review_specification",
            "review_design",
            "review_build_plan",
            "execute_subagent",
            "search_graphiti",
        ],
    )
    def test_non_matching_identifier_returns_none(
        self,
        target_identifier: str,
    ) -> None:
        # AC-008: at least three non-matching identifiers — five here for
        # belt-and-braces coverage of the realistic capability surface.
        assert _check_constitutional_override(target_identifier) is None

    def test_empty_string_is_non_matching(self) -> None:
        # Edge case — empty target is not in the set.
        assert _check_constitutional_override("") is None


# ---------------------------------------------------------------------------
# AC-002 / AC-007 — decision-field invariants
# ---------------------------------------------------------------------------


class TestConstitutionalOverrideDecisionFields:
    """AC-002 / AC-007: returned decision has the canonical fields."""

    @pytest.mark.parametrize(
        "target_identifier",
        ["review_pr", "create_pr_after_review"],
    )
    def test_decision_has_mandatory_human_approval_mode(
        self,
        target_identifier: str,
    ) -> None:
        decision = _check_constitutional_override(target_identifier)
        assert decision is not None
        assert decision.mode is GateMode.MANDATORY_HUMAN_APPROVAL

    @pytest.mark.parametrize(
        "target_identifier",
        ["review_pr", "create_pr_after_review"],
    )
    def test_decision_has_auto_approve_override_true(
        self,
        target_identifier: str,
    ) -> None:
        decision = _check_constitutional_override(target_identifier)
        assert decision is not None
        assert decision.auto_approve_override is True

    @pytest.mark.parametrize(
        "target_identifier",
        ["review_pr", "create_pr_after_review"],
    )
    def test_decision_has_threshold_applied_none(
        self,
        target_identifier: str,
    ) -> None:
        # AC-007 invariant: a mandatory-human-approval decision must
        # never masquerade as a threshold-based approval. Both
        # ``threshold_applied is None`` and ``auto_approve_override is
        # True`` are required to defend against masquerade.
        decision = _check_constitutional_override(target_identifier)
        assert decision is not None
        assert decision.threshold_applied is None

    def test_decision_rationale_names_constitutional_rule(self) -> None:
        decision = _check_constitutional_override("review_pr")
        assert decision is not None
        assert "ADR-ARCH-026" in decision.rationale
        assert decision.rationale == CONSTITUTIONAL_OVERRIDE_RATIONALE

    def test_decision_coach_score_is_none(self) -> None:
        # Override short-circuits before the Coach is consulted, so
        # ``coach_score`` MUST be None (no reliance on Coach output).
        decision = _check_constitutional_override("review_pr")
        assert decision is not None
        assert decision.coach_score is None

    def test_negative_invariant_holds_for_both_targets(self) -> None:
        # AC-007 (Group C @negative): for *every* matching target, the
        # decision must satisfy ``auto_approve_override=True AND
        # threshold_applied is None`` simultaneously.
        for target in CONSTITUTIONAL_OVERRIDE_TARGETS:
            decision = _check_constitutional_override(target)
            assert decision is not None, target
            assert decision.auto_approve_override is True, target
            assert decision.threshold_applied is None, target


# ---------------------------------------------------------------------------
# AC-003 / AC-004 / AC-005 — wiring into evaluate_gate
# ---------------------------------------------------------------------------


class TestEvaluateGateConstitutionalFirst:
    """AC-003 / AC-004 / AC-005: evaluate_gate consults override first."""

    def test_evaluate_gate_first_statement_is_constitutional_override(self) -> None:
        # AC-003: the override branch must run before any other behavioral
        # check. Walk the function's AST and find the first executable
        # node whose call site references ``_check_constitutional_override``;
        # assert it occurs before any other Call node.
        source = inspect.getsource(evaluate_gate)
        tree = ast.parse(source)
        function_node = tree.body[0]
        assert isinstance(function_node, ast.FunctionDef)

        # Skip over the docstring expression if present.
        statements = list(function_node.body)
        if (
            statements
            and isinstance(statements[0], ast.Expr)
            and isinstance(statements[0].value, ast.Constant)
            and isinstance(statements[0].value.value, str)
        ):
            statements = statements[1:]

        # First behavioral construct must reference the override helper.
        # The override is preceded only by its own lazy-import statement.
        # Scan top-level statements for the first Call/Assign that touches
        # ``_check_constitutional_override``; assert no other behavioral
        # Call (e.g. ``_validate_criterion_breakdown``,
        # ``_assemble_reasoning_prompt``, ``reasoning_model_call``)
        # appears earlier.
        first_override_index: int | None = None
        first_other_behavioral_index: int | None = None
        forbidden_first = {
            "_validate_criterion_breakdown",
            "_assemble_reasoning_prompt",
            "reasoning_model_call",
            "_parse_model_response",
            "_enforce_post_conditions",
        }
        for index, stmt in enumerate(statements):
            for node in ast.walk(stmt):
                if (
                    isinstance(node, ast.Name)
                    and node.id == "_check_constitutional_override"
                ):
                    if first_override_index is None:
                        first_override_index = index
                if isinstance(node, ast.Name) and node.id in forbidden_first:
                    if first_other_behavioral_index is None:
                        first_other_behavioral_index = index
        assert first_override_index is not None, (
            "evaluate_gate does not reference _check_constitutional_override"
        )
        if first_other_behavioral_index is not None:
            assert first_override_index < first_other_behavioral_index, (
                "evaluate_gate consults a non-constitutional helper before "
                "the override branch — AC-003 violation."
            )

    def test_evaluate_gate_review_pr_returns_constitutional_decision(self) -> None:
        # AC-004 — Group A: pull-request-review stage always requires
        # human approval regardless of evidence (high coach_score, empty
        # findings, concurring priors).
        concurring_prior = PriorReference(
            entity_id="prior-001",
            group_id="forge_pipeline_history",
            summary="Past PR reviews have all auto-approved cleanly.",
            relevance_score=0.95,
        )
        decision = evaluate_gate(
            **_evaluate_gate_kwargs(
                target_identifier="review_pr",
                coach_score=0.95,
                criterion_breakdown={"completeness": 0.95, "correctness": 0.95},
                detection_findings=[],
                retrieved_priors=[concurring_prior],
            ),
        )
        assert decision.mode is GateMode.MANDATORY_HUMAN_APPROVAL
        assert decision.auto_approve_override is True
        assert decision.threshold_applied is None
        # Crucial: coach_score is NOT carried through — the override
        # short-circuits before the Coach is consulted, and AC-003
        # forbids consulting it.
        assert decision.coach_score is None
        # The orchestrator-supplied build_id MUST be stamped on the
        # returned decision (no placeholder leakage).
        assert decision.build_id == "build-cgcp-004"
        assert decision.target_identifier == "review_pr"
        assert decision.stage_label == "review"

    def test_evaluate_gate_create_pr_after_review_returns_constitutional_decision(
        self,
    ) -> None:
        # AC-005 — Group C: creating a pull request after review is
        # treated with the same constitutional rule.
        decision = evaluate_gate(
            **_evaluate_gate_kwargs(
                target_identifier="create_pr_after_review",
                coach_score=0.99,  # would auto-approve absent the override
                criterion_breakdown={"completeness": 1.0, "correctness": 1.0},
            ),
        )
        assert decision.mode is GateMode.MANDATORY_HUMAN_APPROVAL
        assert decision.target_identifier == "create_pr_after_review"
        assert decision.auto_approve_override is True
        assert decision.threshold_applied is None

    def test_evaluate_gate_does_not_consult_reasoning_model_for_override(
        self,
    ) -> None:
        # AC-003: returns immediately without consulting coach_score,
        # detection_findings, retrieved_priors, or calibration_adjustments.
        # We enforce this by passing a reasoning-model double that raises
        # if invoked. If the override branch returns first, the model is
        # never called and the test passes.
        decision = evaluate_gate(
            **_evaluate_gate_kwargs(
                target_identifier="review_pr",
                detection_findings=[
                    DetectionFinding(
                        pattern="PHANTOM",
                        severity="critical",
                        evidence="Hallucinated dependency in review.",
                    ),
                ],
            ),
        )
        # If we got here, the reasoning model was *not* invoked.
        assert decision.mode is GateMode.MANDATORY_HUMAN_APPROVAL


# ---------------------------------------------------------------------------
# AC-006 — Group E two-layer regression (@security @regression)
# ---------------------------------------------------------------------------


class TestTwoLayerRegression:
    """AC-006: executor branch alone is sufficient for MANDATORY_HUMAN_APPROVAL.

    The complementary prompt-layer ``SAFETY_CONSTITUTION`` block lives
    in the orchestrator's prompt module and is *out of scope* here. We
    simulate "the prompt-layer rule has been removed" by *bypassing*
    any prompt-layer logic — the test calls :func:`evaluate_gate`
    directly with ``constitutional_rules=[]`` (no prompt-layer rules
    given to the model) and verifies the executor branch alone returns
    ``MANDATORY_HUMAN_APPROVAL``.
    """

    @pytest.mark.parametrize(
        "target_identifier",
        ["review_pr", "create_pr_after_review"],
    )
    def test_executor_branch_alone_produces_mandatory_human_approval(
        self,
        target_identifier: str,
    ) -> None:
        # Prompt layer disabled in test harness: constitutional_rules=[]
        # AND the reasoning_model_call raises if invoked. The override
        # branch is the *only* enforcement remaining.
        decision = evaluate_gate(
            **_evaluate_gate_kwargs(
                target_identifier=target_identifier,
                constitutional_rules=[],
                # High score that would auto-approve in the absence of
                # the override; if the executor branch fails, this test
                # would surface as MANDATORY → AUTO_APPROVE drift.
                coach_score=0.99,
                criterion_breakdown={"completeness": 1.0, "correctness": 1.0},
            ),
        )
        assert decision.mode is GateMode.MANDATORY_HUMAN_APPROVAL
        assert decision.auto_approve_override is True
        assert decision.threshold_applied is None

    def test_regression_signal_is_visible_when_executor_layer_disabled(
        self,
    ) -> None:
        # The complementary regression: if the *executor* layer were
        # disabled in isolation, the prompt layer would have to catch
        # the failure. We can't disable the executor branch in a unit
        # test (it's the function under test), but we can pin the
        # property the regression suite relies on: the constitutional
        # decision short-circuits the rest of the pipeline. If a future
        # refactor moves the override branch later, this assertion will
        # surface the drift.
        #
        # Walk the function's AST body (not the source string — that
        # would also match docstring text) and confirm the override
        # helper is referenced strictly before any reasoning helper.
        function_node = ast.parse(inspect.getsource(evaluate_gate)).body[0]
        assert isinstance(function_node, ast.FunctionDef)
        body = list(function_node.body)
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body = body[1:]  # strip docstring

        def _first_reference(name: str) -> int | None:
            for index, stmt in enumerate(body):
                for sub_node in ast.walk(stmt):
                    if isinstance(sub_node, ast.Name) and sub_node.id == name:
                        return index
            return None

        override_index = _first_reference("_check_constitutional_override")
        reasoning_index = _first_reference("_assemble_reasoning_prompt")
        assert override_index is not None, (
            "evaluate_gate body never references _check_constitutional_override."
        )
        if reasoning_index is not None:
            assert override_index < reasoning_index, (
                "Executor-layer override no longer precedes reasoning "
                "assembly — AC-006 two-layer regression."
            )


# ---------------------------------------------------------------------------
# AC-009 — module purity
# ---------------------------------------------------------------------------


_GATING_PKG = Path(__file__).resolve().parents[3] / "src" / "forge" / "gating"
_FORBIDDEN_ROOTS = ("nats_core", "nats", "langgraph", "forge.adapters")


def _iter_imports(source_path: Path) -> list[str]:
    """Return the full import-paths declared in ``source_path``."""
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                names.append(node.module)
    return names


class TestModulePurity:
    """AC-009: forge.gating.constitutional imports nothing forbidden."""

    def test_constitutional_imports_are_clean(self) -> None:
        constitutional_path = _GATING_PKG / "constitutional.py"
        for imported in _iter_imports(constitutional_path):
            for forbidden in _FORBIDDEN_ROOTS:
                assert not imported.startswith(forbidden), (
                    "forge.gating.constitutional imports forbidden module: "
                    f"{imported!r}"
                )
