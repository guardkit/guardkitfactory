"""Two-layer constitutional regression — closes risk **R1**.

Group E ``@security @regression`` — the highest-stakes test in the
feature. The contract under verification is ADR-ARCH-026: pull-request
review and pull-request creation always demand human approval,
regardless of any other input.

The protocol uses two redundant layers:

1. **Prompt layer** — the orchestrator's ``SAFETY_CONSTITUTION`` system
   prompt instructs the reasoning model to return
   ``MANDATORY_HUMAN_APPROVAL`` for the protected target identifiers.
2. **Executor layer** — :func:`forge.gating.constitutional._check_constitutional_override`
   short-circuits :func:`forge.gating.evaluate_gate` for the same set of
   targets *before* the reasoning model is consulted.

This regression suite proves that **disabling either layer alone** still
produces ``MANDATORY_HUMAN_APPROVAL``. Two scenarios:

* **Layer 1 disabled, Layer 2 active** — model is wired to return a
  permissive ``AUTO_APPROVE`` (simulating a model that ignores the
  removed safety constitution); assert the executor branch overrides
  to ``MANDATORY_HUMAN_APPROVAL`` regardless.
* **Layer 1 active, Layer 2 disabled** — the executor branch is patched
  to return ``None`` (simulating a removed override); a model that
  obeys the safety constitution returns ``MANDATORY_HUMAN_APPROVAL``
  and the wrapper consumes it as-is.

Together the two scenarios prove that the project's safety baseline is
preserved even if a single defect breaks one layer.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from forge.gating.constitutional import (
    CONSTITUTIONAL_OVERRIDE_RATIONALE,
    CONSTITUTIONAL_OVERRIDE_TARGETS,
)
from forge.gating.models import GateDecision, GateMode, evaluate_gate


# ---------------------------------------------------------------------------
# Local doubles — none of the wrapper-level adapters are needed: this is a
# pure-domain regression test running through ``evaluate_gate``.
# ---------------------------------------------------------------------------


def _permissive_model(_prompt: str) -> str:
    """Reasoning model that always says ``AUTO_APPROVE``.

    Simulates a model whose prompt-layer ``SAFETY_CONSTITUTION`` was
    stripped — left to its own devices the model would happily auto-
    approve every gated stage.
    """
    return json.dumps(
        {
            "mode": GateMode.AUTO_APPROVE.value,
            "rationale": "no safety prompt — model is unconstrained",
            "relevant_prior_ids": [],
            "threshold_applied": 0.5,
        }
    )


def _safety_obedient_model(_prompt: str) -> str:
    """Reasoning model that obeys the prompt-layer ``SAFETY_CONSTITUTION``.

    Returns ``MANDATORY_HUMAN_APPROVAL`` for the protected targets the
    constitution names. Used in the "executor branch disabled" scenario
    to prove the prompt layer alone still produces the safe outcome.
    """
    return json.dumps(
        {
            "mode": GateMode.MANDATORY_HUMAN_APPROVAL.value,
            "rationale": "obeyed SAFETY_CONSTITUTION",
            "relevant_prior_ids": [],
            "threshold_applied": None,
        }
    )


def _common_kwargs(target: str) -> dict[str, Any]:
    return {
        "build_id": "build-CG44-2026-04-25T120000",
        "target_kind": "local_tool",
        "target_identifier": target,
        "stage_label": "ImplementationReview",
        "coach_score": 0.95,
        "criterion_breakdown": {"completeness": 0.95},
        "detection_findings": [],
        "retrieved_priors": [],
        "calibration_adjustments": [],
        "constitutional_rules": [],
    }


# ---------------------------------------------------------------------------
# Scenario 1 — Prompt layer disabled, executor branch active.
# ---------------------------------------------------------------------------


class TestExecutorBranchAloneIsSufficient:
    """SAFETY_CONSTITUTION removed → executor branch still wins."""

    @pytest.mark.parametrize(
        "target",
        sorted(CONSTITUTIONAL_OVERRIDE_TARGETS),
    )
    def test_protected_target_yields_mandatory_human_approval_even_with_permissive_model(
        self, target: str
    ) -> None:
        decision: GateDecision = evaluate_gate(
            **_common_kwargs(target),
            reasoning_model_call=_permissive_model,
        )
        # Executor branch fired before the model was consulted.
        assert decision.mode is GateMode.MANDATORY_HUMAN_APPROVAL, (
            f"target {target!r} did not produce MANDATORY_HUMAN_APPROVAL "
            f"with the executor branch active; got mode={decision.mode}"
        )
        # Hallmarks of the override branch (constitutional.py):
        assert decision.auto_approve_override is True
        assert decision.threshold_applied is None
        assert decision.coach_score is None  # short-circuit before Coach
        assert decision.degraded_mode is True  # invariant 2 satisfaction
        assert decision.rationale == CONSTITUTIONAL_OVERRIDE_RATIONALE

    def test_unprotected_target_falls_through_to_model(self) -> None:
        # Negative control: a target NOT in the override set must let the
        # model's permissive verdict through, otherwise the executor
        # branch is matching too widely.
        decision = evaluate_gate(
            **_common_kwargs("write_file"),
            reasoning_model_call=_permissive_model,
        )
        assert decision.mode is GateMode.AUTO_APPROVE
        assert decision.auto_approve_override is False


# ---------------------------------------------------------------------------
# Scenario 2 — Prompt layer active, executor branch disabled.
# ---------------------------------------------------------------------------


class TestPromptLayerAloneIsSufficient:
    """Executor branch removed → prompt layer still wins."""

    @pytest.mark.parametrize(
        "target",
        sorted(CONSTITUTIONAL_OVERRIDE_TARGETS),
    )
    def test_protected_target_yields_mandatory_human_approval_when_executor_bypassed(
        self, target: str
    ) -> None:
        # Patch the executor branch to return ``None`` so it never fires.
        # The patch target is the *source* module — ``evaluate_gate``
        # imports the helper lazily via
        # ``from forge.gating.constitutional import _check_constitutional_override``
        # so the per-call lookup picks up the patched object.
        with patch(
            "forge.gating.constitutional._check_constitutional_override",
            return_value=None,
        ):
            decision = evaluate_gate(
                **_common_kwargs(target),
                reasoning_model_call=_safety_obedient_model,
            )
        # Prompt layer carried the safety baseline alone.
        assert decision.mode is GateMode.MANDATORY_HUMAN_APPROVAL
        # The wrapper consumed the model's verdict so ``auto_approve_override``
        # is False — this is the *prompt-layer*-driven path, not the
        # executor short-circuit.
        assert decision.auto_approve_override is False
        # The model-driven path includes the Coach score, unlike the
        # executor short-circuit which strips it.
        assert decision.coach_score == 0.95
