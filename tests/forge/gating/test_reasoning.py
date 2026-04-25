"""Tests for ``forge.gating.reasoning`` and the reasoning branch of
``forge.gating.evaluate_gate`` (TASK-CGCP-005).

Each test class maps to one or more acceptance criteria in
``tasks/design_approved/TASK-CGCP-005-reasoning-model-assembly.md``:

* :class:`TestReasoningModelCallProtocol`     — AC: ``ReasoningModelCall`` Protocol
* :class:`TestEvaluateGatePurity`             — AC: pure function (no I/O imports, clock injection)
* :class:`TestAssembleReasoningPrompt`        — AC: deterministic prompt for fixed inputs
* :class:`TestParseModelResponse`             — AC: validates structured response
* :class:`TestDegradedModePostCondition`      — AC: coach_score=None ⇒ non-AUTO_APPROVE
* :class:`TestCriterionRangeInvariant`        — AC: criterion in [0,1] / Group B @negative
* :class:`TestCriticalFindingEscalation`      — AC: critical severity ⇒ no AUTO_APPROVE (Group C @negative)
* :class:`TestGroupAScenarios`                — AC: Group A scenarios via test double
* :class:`TestGateDecisionShape`              — AC: GateDecision carries rationale, evidence, findings, decided_at

The reasoning-model double is a tiny ``(prompt: str) -> str`` callable that
returns hard-coded JSON for each scenario, satisfying the implementation
note "a single fixture file is sufficient".
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from forge.gating import (
    DetectionFinding,
    GateDecision,
    GateMode,
    PriorReference,
    PostConditionError,
    ReasoningModelCall,
    ReasoningResponseError,
    evaluate_gate,
)
from forge.gating.reasoning import (
    ParsedDecision,
    _assemble_reasoning_prompt,
    _enforce_post_conditions,
    _parse_model_response,
)


# ---------------------------------------------------------------------------
# Helpers — deterministic test doubles
# ---------------------------------------------------------------------------


def _frozen_clock() -> datetime:
    """Deterministic clock used for ``decided_at`` in tests."""
    return datetime(2026, 4, 25, 12, 0, 0, tzinfo=UTC)


def _scripted_call(response_payload: dict[str, Any] | str) -> ReasoningModelCall:
    """Return a reasoning-model double that emits ``response_payload``.

    Accepts either a JSON-serialisable dict (which is dumped via
    ``json.dumps``) or a literal string (so malformed-response tests can
    inject non-JSON or schema-violating strings directly).
    """
    if isinstance(response_payload, str):
        canned = response_payload
    else:
        canned = json.dumps(response_payload)

    def _call(prompt: str) -> str:
        # The prompt argument is exercised by the prompt-assembly test
        # class; here we only care about the response.
        assert isinstance(prompt, str) and prompt, "double saw empty prompt"
        return canned

    return _call


def _gate_kwargs(**overrides: Any) -> dict[str, Any]:
    """Build a minimal-but-valid kwargs dict for :func:`evaluate_gate`."""
    base: dict[str, Any] = {
        "build_id": "build-2026-04-25-001",
        "target_kind": "fleet_capability",
        "target_identifier": "review_specification",
        "stage_label": "review",
        "coach_score": 0.92,
        "criterion_breakdown": {"completeness": 0.95, "correctness": 0.9},
        "detection_findings": [],
        "retrieved_priors": [
            PriorReference(
                entity_id="prior-A",
                group_id="forge_pipeline_history",
                summary="Previous review_specification builds auto-approved at 0.9+.",
                relevance_score=0.8,
            ),
        ],
        "calibration_adjustments": [],
        "constitutional_rules": [],
        "reasoning_model_call": _scripted_call(
            {
                "mode": "AUTO_APPROVE",
                "rationale": "Score 0.92 above prior-derived threshold.",
                "threshold_applied": 0.85,
                "relevant_prior_ids": ["prior-A"],
            },
        ),
        "clock": _frozen_clock,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# AC: ReasoningModelCall Protocol
# ---------------------------------------------------------------------------


class TestReasoningModelCallProtocol:
    """AC: a ``ReasoningModelCall`` Protocol exists and accepts callables."""

    def test_lambda_satisfies_protocol(self) -> None:
        call: ReasoningModelCall = lambda prompt: "{}"  # noqa: E731
        # Runtime-checkable Protocol — isinstance is meaningful.
        assert isinstance(call, ReasoningModelCall)

    def test_callable_class_satisfies_protocol(self) -> None:
        class _Double:
            def __call__(self, prompt: str) -> str:
                return "{}"

        assert isinstance(_Double(), ReasoningModelCall)


# ---------------------------------------------------------------------------
# AC: pure function — no banned imports, clock is injectable
# ---------------------------------------------------------------------------


class TestEvaluateGatePurity:
    """AC: ``evaluate_gate`` is pure — no I/O, deterministic in tests."""

    def test_evaluate_gate_uses_injected_clock(self) -> None:
        called_at = datetime(2030, 1, 1, 0, 0, 0, tzinfo=UTC)

        def _clock() -> datetime:
            return called_at

        decision = evaluate_gate(**_gate_kwargs(clock=_clock))
        assert decision.decided_at == called_at

    def test_reasoning_module_does_not_import_forbidden_packages(self) -> None:
        # Domain-purity guard at the source level — mirrors the
        # ``test_models.py::TestModulePurity`` AST check but local to this
        # module so it fails with TASK-CGCP-005 in the message.
        import ast
        from pathlib import Path

        module_path = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "forge"
            / "gating"
            / "reasoning.py"
        )
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        forbidden = ("nats_core", "nats", "langgraph", "forge.adapters")

        seen: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                seen.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module is not None:
                    seen.append(node.module)

        for imported in seen:
            for bad in forbidden:
                assert not imported.startswith(bad), (
                    f"TASK-CGCP-005: forge.gating.reasoning imports {imported!r}"
                )


# ---------------------------------------------------------------------------
# AC: deterministic prompt assembly (snapshot-stable)
# ---------------------------------------------------------------------------


class TestAssembleReasoningPrompt:
    """AC: ``_assemble_reasoning_prompt`` is deterministic for fixed inputs."""

    def test_identical_inputs_produce_identical_prompts(self) -> None:
        kwargs = {
            "target_kind": "fleet_capability",
            "target_identifier": "review_specification",
            "stage_label": "review",
            "coach_score": 0.91,
            "criterion_breakdown": {
                "correctness": 0.9,
                "completeness": 0.92,
            },
            "detection_findings": [
                DetectionFinding(
                    pattern="UNGROUNDED",
                    severity="low",
                    evidence="Section 2.3 lacks citation.",
                ),
            ],
            "retrieved_priors": [
                PriorReference(
                    entity_id="prior-1",
                    group_id="forge_pipeline_history",
                    summary="Older builds at 0.91 auto-approved.",
                    relevance_score=0.7,
                ),
            ],
            "calibration_adjustments": [],
        }
        prompt_a = _assemble_reasoning_prompt(**kwargs)  # type: ignore[arg-type]
        prompt_b = _assemble_reasoning_prompt(**kwargs)  # type: ignore[arg-type]
        assert prompt_a == prompt_b

    def test_criterion_breakdown_keys_are_sorted_for_stability(self) -> None:
        # Insertion order should not influence the prompt.
        prompt_a = _assemble_reasoning_prompt(
            target_kind="fleet_capability",
            target_identifier="x",
            stage_label="s",
            coach_score=0.5,
            criterion_breakdown={"b": 0.1, "a": 0.2},
            detection_findings=[],
            retrieved_priors=[],
            calibration_adjustments=[],
        )
        prompt_b = _assemble_reasoning_prompt(
            target_kind="fleet_capability",
            target_identifier="x",
            stage_label="s",
            coach_score=0.5,
            criterion_breakdown={"a": 0.2, "b": 0.1},
            detection_findings=[],
            retrieved_priors=[],
            calibration_adjustments=[],
        )
        assert prompt_a == prompt_b

    def test_prompt_advertises_critical_severity_rule(self) -> None:
        prompt = _assemble_reasoning_prompt(
            target_kind="fleet_capability",
            target_identifier="x",
            stage_label="s",
            coach_score=0.5,
            criterion_breakdown={},
            detection_findings=[],
            retrieved_priors=[],
            calibration_adjustments=[],
        )
        assert "critical" in prompt
        assert "AUTO_APPROVE" in prompt


# ---------------------------------------------------------------------------
# AC: parse_model_response validates against Pydantic and reports clearly
# ---------------------------------------------------------------------------


class TestParseModelResponse:
    """AC: ``_parse_model_response`` validates the structured response."""

    def test_valid_response_returns_parsed_decision(self) -> None:
        raw = json.dumps(
            {
                "mode": "AUTO_APPROVE",
                "rationale": "Score above derived threshold.",
                "threshold_applied": 0.85,
                "relevant_prior_ids": ["prior-A"],
            },
        )
        parsed = _parse_model_response(raw)
        assert isinstance(parsed, ParsedDecision)
        assert parsed.mode is GateMode.AUTO_APPROVE

    def test_empty_response_raises_clear_error(self) -> None:
        with pytest.raises(ReasoningResponseError) as exc:
            _parse_model_response("   \n  ")
        assert "empty" in str(exc.value).lower()

    def test_non_json_response_raises_clear_error(self) -> None:
        with pytest.raises(ReasoningResponseError) as exc:
            _parse_model_response("not really json {")
        assert "JSON" in str(exc.value)

    def test_array_response_is_rejected_with_clear_error(self) -> None:
        with pytest.raises(ReasoningResponseError) as exc:
            _parse_model_response("[1, 2, 3]")
        assert "JSON object" in str(exc.value)

    def test_missing_required_field_raises_clear_error(self) -> None:
        # No ``rationale`` — Pydantic should reject.
        raw = json.dumps({"mode": "AUTO_APPROVE"})
        with pytest.raises(ReasoningResponseError) as exc:
            _parse_model_response(raw)
        assert "schema validation" in str(exc.value)

    def test_invalid_mode_value_raises_clear_error(self) -> None:
        raw = json.dumps({"mode": "MAYBE", "rationale": "x"})
        with pytest.raises(ReasoningResponseError):
            _parse_model_response(raw)

    def test_extra_fields_are_rejected(self) -> None:
        # extra="forbid" so a drifting model that adds undeclared keys
        # fails loud rather than silently dropping data.
        raw = json.dumps(
            {
                "mode": "AUTO_APPROVE",
                "rationale": "x",
                "uninvited": True,
            },
        )
        with pytest.raises(ReasoningResponseError):
            _parse_model_response(raw)


# ---------------------------------------------------------------------------
# AC: degraded-mode post-condition (DM-gating §6, R3)
# ---------------------------------------------------------------------------


class TestDegradedModePostCondition:
    """AC: ``coach_score is None`` ⇒ mode in
    ``{FLAG_FOR_REVIEW, HARD_STOP, MANDATORY_HUMAN_APPROVAL}``;
    violation raises a programmer error (do NOT silently coerce).
    """

    def test_helper_raises_when_degraded_mode_returns_auto_approve(self) -> None:
        parsed = ParsedDecision(
            mode=GateMode.AUTO_APPROVE,
            rationale="oops",
        )
        with pytest.raises(PostConditionError) as exc:
            _enforce_post_conditions(
                parsed=parsed,
                coach_score=None,
                detection_findings=[],
            )
        assert "Degraded-mode" in str(exc.value)
        assert "R3" in str(exc.value)

    @pytest.mark.parametrize(
        "mode",
        [
            GateMode.FLAG_FOR_REVIEW,
            GateMode.HARD_STOP,
            GateMode.MANDATORY_HUMAN_APPROVAL,
        ],
    )
    def test_helper_accepts_allowed_modes_in_degraded_mode(
        self, mode: GateMode
    ) -> None:
        parsed = ParsedDecision(mode=mode, rationale="ok")
        # Should not raise.
        _enforce_post_conditions(
            parsed=parsed,
            coach_score=None,
            detection_findings=[],
        )

    def test_evaluate_gate_raises_when_double_returns_auto_approve_in_degraded_mode(
        self,
    ) -> None:
        bad_double = _scripted_call(
            {
                "mode": "AUTO_APPROVE",
                "rationale": "Should never have been allowed.",
            },
        )
        with pytest.raises(PostConditionError):
            evaluate_gate(
                **_gate_kwargs(
                    coach_score=None,
                    criterion_breakdown={},
                    reasoning_model_call=bad_double,
                ),
            )


# ---------------------------------------------------------------------------
# AC: criterion-range invariant (Group B @negative)
# ---------------------------------------------------------------------------


class TestCriterionRangeInvariant:
    """AC: criterion scores in ``[0.0, 1.0]`` accepted; out-of-range
    refused with a validation error and **no decision is recorded**.
    """

    @pytest.mark.parametrize("value", [0.0, 0.25, 0.5, 0.99, 1.0])
    def test_in_range_values_are_accepted(self, value: float) -> None:
        decision = evaluate_gate(
            **_gate_kwargs(criterion_breakdown={"completeness": value}),
        )
        assert decision.criterion_breakdown["completeness"] == value

    @pytest.mark.parametrize("bad_value", [-0.01, 1.01, 1.5, -1.0])
    def test_out_of_range_values_are_refused(self, bad_value: float) -> None:
        # Track whether the reasoning model was even consulted.
        invoked: list[str] = []

        def _call(prompt: str) -> str:
            invoked.append(prompt)
            return json.dumps({"mode": "AUTO_APPROVE", "rationale": "x"})

        with pytest.raises(ValueError) as exc:
            evaluate_gate(
                **_gate_kwargs(
                    criterion_breakdown={"completeness": bad_value},
                    reasoning_model_call=_call,
                ),
            )
        assert "criterion_breakdown" in str(exc.value)
        # No decision is recorded — the model was never called.
        assert invoked == []


# ---------------------------------------------------------------------------
# AC: critical-finding escalation (Group C @negative)
# ---------------------------------------------------------------------------


class TestCriticalFindingEscalation:
    """AC: a ``DetectionFinding`` with severity='critical' cannot result
    in ``AUTO_APPROVE``.
    """

    def test_helper_raises_when_critical_finding_with_auto_approve(self) -> None:
        finding = DetectionFinding(
            pattern="PHANTOM",
            severity="critical",
            evidence="Claim X has no grounding anywhere.",
        )
        parsed = ParsedDecision(
            mode=GateMode.AUTO_APPROVE,
            rationale="model ignored severity",
        )
        with pytest.raises(PostConditionError) as exc:
            _enforce_post_conditions(
                parsed=parsed,
                coach_score=0.95,
                detection_findings=[finding],
            )
        assert "critical" in str(exc.value).lower()
        assert "AUTO_APPROVE" in str(exc.value)

    def test_helper_accepts_critical_finding_with_flag_for_review(self) -> None:
        finding = DetectionFinding(
            pattern="PHANTOM",
            severity="critical",
            evidence="Claim X has no grounding.",
        )
        parsed = ParsedDecision(
            mode=GateMode.FLAG_FOR_REVIEW,
            rationale="critical finding requires human review",
        )
        _enforce_post_conditions(
            parsed=parsed,
            coach_score=0.95,
            detection_findings=[finding],
        )

    def test_evaluate_gate_raises_when_double_auto_approves_with_critical(
        self,
    ) -> None:
        finding = DetectionFinding(
            pattern="PHANTOM",
            severity="critical",
            evidence="Phantom citation in build_plan.md:42.",
        )
        bad_double = _scripted_call(
            {"mode": "AUTO_APPROVE", "rationale": "ignored critical"},
        )
        with pytest.raises(PostConditionError):
            evaluate_gate(
                **_gate_kwargs(
                    detection_findings=[finding],
                    reasoning_model_call=bad_double,
                ),
            )


# ---------------------------------------------------------------------------
# AC: Group A scenarios pass via the deterministic test double
# ---------------------------------------------------------------------------


class TestGroupAScenarios:
    """Group A — the canonical happy/ambiguous/negative paths."""

    def test_auto_approve_happy_path(self) -> None:
        double = _scripted_call(
            {
                "mode": "AUTO_APPROVE",
                "rationale": (
                    "Score 0.94 above prior-derived threshold 0.85; "
                    "no negative findings."
                ),
                "threshold_applied": 0.85,
                "relevant_prior_ids": ["prior-A"],
            },
        )
        decision = evaluate_gate(
            **_gate_kwargs(coach_score=0.94, reasoning_model_call=double),
        )
        assert decision.mode is GateMode.AUTO_APPROVE
        assert decision.threshold_applied == 0.85
        assert decision.degraded_mode is False
        assert decision.evidence and decision.evidence[0].entity_id == "prior-A"

    def test_ambiguous_evidence_flag_for_review(self) -> None:
        double = _scripted_call(
            {
                "mode": "FLAG_FOR_REVIEW",
                "rationale": (
                    "Mixed priors: 0.82 falls between accept/reject thresholds."
                ),
                "threshold_applied": 0.85,
                "relevant_prior_ids": ["prior-A"],
            },
        )
        decision = evaluate_gate(
            **_gate_kwargs(coach_score=0.82, reasoning_model_call=double),
        )
        assert decision.mode is GateMode.FLAG_FOR_REVIEW
        assert "Mixed priors" in decision.rationale

    def test_strongly_negative_hard_stop(self) -> None:
        finding = DetectionFinding(
            pattern="SCOPE_CREEP",
            severity="high",
            evidence="Implementation diverges from acceptance criteria.",
        )
        double = _scripted_call(
            {
                "mode": "HARD_STOP",
                "rationale": "Score 0.41 with high-severity SCOPE_CREEP finding.",
                "threshold_applied": 0.7,
                "relevant_prior_ids": [],
            },
        )
        decision = evaluate_gate(
            **_gate_kwargs(
                coach_score=0.41,
                detection_findings=[finding],
                reasoning_model_call=double,
            ),
        )
        assert decision.mode is GateMode.HARD_STOP
        assert decision.detection_findings == [finding]


# ---------------------------------------------------------------------------
# AC: GateDecision carries rationale, evidence, findings, decided_at
# ---------------------------------------------------------------------------


class TestGateDecisionShape:
    """AC: every gate decision records its rationale, priors, findings,
    and ``decided_at`` (Group A "every gate decision records its rationale,
    priors, and findings").
    """

    def test_decision_records_rationale_and_priors_and_findings(self) -> None:
        finding = DetectionFinding(
            pattern="UNGROUNDED",
            severity="medium",
            evidence="Section 2.4 unsupported.",
        )
        prior = PriorReference(
            entity_id="prior-X",
            group_id="forge_pipeline_history",
            summary="Recent build with similar finding flagged for review.",
            relevance_score=0.6,
        )
        double = _scripted_call(
            {
                "mode": "FLAG_FOR_REVIEW",
                "rationale": (
                    "UNGROUNDED finding in Section 2.4 mirrors a flagged "
                    "prior (prior-X)."
                ),
                "threshold_applied": 0.8,
                "relevant_prior_ids": ["prior-X"],
            },
        )
        decision = evaluate_gate(
            **_gate_kwargs(
                detection_findings=[finding],
                retrieved_priors=[prior],
                reasoning_model_call=double,
            ),
        )

        assert isinstance(decision, GateDecision)
        assert decision.rationale.startswith("UNGROUNDED finding")
        assert decision.detection_findings == [finding]
        assert decision.evidence == [prior]
        assert decision.decided_at == _frozen_clock()

    def test_decision_falls_back_to_full_priors_when_model_omits_relevance(
        self,
    ) -> None:
        prior_a = PriorReference(
            entity_id="prior-A",
            group_id="forge_pipeline_history",
            summary="A",
        )
        prior_b = PriorReference(
            entity_id="prior-B",
            group_id="forge_calibration_history",
            summary="B",
        )
        double = _scripted_call(
            {
                "mode": "AUTO_APPROVE",
                "rationale": "Strong evidence across all priors.",
                "threshold_applied": 0.7,
                "relevant_prior_ids": [],  # model declined to filter
            },
        )
        decision = evaluate_gate(
            **_gate_kwargs(
                retrieved_priors=[prior_a, prior_b],
                reasoning_model_call=double,
            ),
        )
        # Empty filter ⇒ all priors retained as evidence.
        assert decision.evidence == [prior_a, prior_b]

    def test_degraded_mode_flag_is_set_when_coach_score_is_none(self) -> None:
        double = _scripted_call(
            {
                "mode": "FLAG_FOR_REVIEW",
                "rationale": "No coach score — degraded path.",
                "threshold_applied": None,
                "relevant_prior_ids": [],
            },
        )
        decision = evaluate_gate(
            **_gate_kwargs(
                coach_score=None,
                criterion_breakdown={},
                reasoning_model_call=double,
            ),
        )
        assert decision.degraded_mode is True
        assert decision.coach_score is None
        assert decision.mode is GateMode.FLAG_FOR_REVIEW
