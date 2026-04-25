"""Reasoning-model assembly and post-condition checks for ``evaluate_gate``.

This module is the **reasoning-branch implementation** of the Confidence-Gated
Checkpoint Protocol (FEAT-FORGE-004 / TASK-CGCP-005), per
``docs/design/models/DM-gating.md`` §3 and ADR-ARCH-019.

Per ADR-ARCH-019 there are **no static thresholds** — thresholds emerge from
priors via a reasoning-model invocation that is parameterised into
:func:`forge.gating.evaluate_gate` so the function remains pure (no I/O, no
global state, deterministic in tests).

Design highlights:

* :class:`ReasoningModelCall` — a :class:`typing.Protocol` for the
  dependency-injected reasoning-model callable (``(prompt: str) -> str``).
  Production binds the orchestrator's reasoning model; tests bind a small
  deterministic double that returns hard-coded JSON.
* :func:`_assemble_reasoning_prompt` — builds a deterministic prompt from
  the gate inputs. Identical inputs produce identical prompts (snapshot
  stable), which makes the reasoning-branch logic testable with golden
  fixtures.
* :func:`_parse_model_response` — parses the structured response into a
  private :class:`ParsedDecision` Pydantic model and raises
  :class:`ReasoningResponseError` on malformed responses.
* :func:`_enforce_post_conditions` — enforces the §6 invariants that are
  best checked **after** the reasoning model has produced a decision:

  - **Degraded-mode** invariant: if ``coach_score is None`` the decision
    must not be ``AUTO_APPROVE`` (closes risk **R3** — silent coercion
    is forbidden, so the function raises rather than rewriting the mode).
  - **Critical-finding escalation**: a :class:`DetectionFinding` with
    ``severity="critical"`` cannot result in ``AUTO_APPROVE`` (Group C
    ``@negative``).

Domain purity (DM-gating §1, ADR-ARCH-019):

* Imports are restricted to the standard library, ``pydantic``, and the
  sibling :mod:`forge.gating.models` module.
* No imports from ``nats_core``, ``nats-py``, ``langgraph``, or
  ``forge.adapters.*``.
"""

from __future__ import annotations

import json
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from forge.gating.models import (
    CalibrationAdjustment,
    DetectionFinding,
    GateMode,
    PriorReference,
)

__all__ = [
    "ParsedDecision",
    "PostConditionError",
    "ReasoningModelCall",
    "ReasoningResponseError",
]


# ---------------------------------------------------------------------------
# Protocol — dependency-injected reasoning model
# ---------------------------------------------------------------------------


@runtime_checkable
class ReasoningModelCall(Protocol):
    """Callable signature for the reasoning-model dependency injected into
    :func:`forge.gating.evaluate_gate`.

    The callable receives the assembled prompt and must return the model's
    raw response as a string. The string is expected to be JSON matching
    the :class:`ParsedDecision` schema; structural validation is performed
    by :func:`_parse_model_response`.

    The protocol is :func:`typing.runtime_checkable` so production wiring
    can ``isinstance(...)`` -test bound implementations without requiring a
    nominal subclass; this keeps the test double contract minimal.
    """

    def __call__(self, prompt: str) -> str:  # pragma: no cover — Protocol
        ...


# ---------------------------------------------------------------------------
# Structured-response model (private to this module)
# ---------------------------------------------------------------------------


class ParsedDecision(BaseModel):
    """Structured shape the reasoning model is required to produce.

    The model returns a JSON object with these fields; anything else is
    rejected by :func:`_parse_model_response`. ``extra="forbid"`` so a
    drifting model that adds undeclared fields fails loudly rather than
    silently dropping data.
    """

    model_config = ConfigDict(extra="forbid")

    mode: GateMode = Field(
        description="GateMode the reasoning model selected for this decision.",
    )
    rationale: str = Field(
        min_length=1,
        description="Reasoning model's explanation for the chosen mode.",
    )
    threshold_applied: float | None = Field(
        default=None,
        description=(
            "Threshold the reasoning model derived from priors, if any. "
            "``None`` when no static threshold applied (DM-gating §3 — no "
            "static thresholds in the function itself)."
        ),
    )
    relevant_prior_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Subset of supplied prior ``entity_id`` values that the "
            "reasoning model judged relevant. Used to populate "
            "``GateDecision.evidence``."
        ),
    )


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ReasoningResponseError(ValueError):
    """Raised when the reasoning model's response cannot be parsed.

    The error wraps the underlying cause (``json.JSONDecodeError`` or
    :class:`pydantic.ValidationError`) and includes a human-readable
    message naming what failed.
    """


class PostConditionError(RuntimeError):
    """Raised when the reasoning model's decision violates a §6 invariant.

    This is a **programmer error** signal — per AC, the function does not
    silently coerce a bad decision (closes risk **R3**); it raises so the
    caller sees the contract violation.
    """


# ---------------------------------------------------------------------------
# Prompt assembly (deterministic for fixed inputs)
# ---------------------------------------------------------------------------


_PROMPT_INSTRUCTIONS = (
    "You are the confidence-gated checkpoint reasoning evaluator for the "
    "Forge pipeline (FEAT-FORGE-004 / DM-gating §3).\n"
    "\n"
    "Decide a GateMode for the supplied inputs and respond with a single "
    "JSON object matching this schema:\n"
    "{\n"
    '  "mode": "AUTO_APPROVE | FLAG_FOR_REVIEW | HARD_STOP | '
    'MANDATORY_HUMAN_APPROVAL",\n'
    '  "rationale": "<short explanation referencing the inputs>",\n'
    '  "threshold_applied": <float in [0.0, 1.0] | null>,\n'
    '  "relevant_prior_ids": ["<entity_id>", ...]\n'
    "}\n"
    "\n"
    "Rules (DM-gating §3, §6):\n"
    "- No static thresholds — any threshold MUST be derived from the "
    "supplied priors and adjustments.\n"
    "- A DetectionFinding with severity=='critical' MUST NOT result in "
    "AUTO_APPROVE.\n"
    "- If coach_score is null, MUST choose one of FLAG_FOR_REVIEW, "
    "HARD_STOP, or MANDATORY_HUMAN_APPROVAL.\n"
    "- Only approved CalibrationAdjustments (approved_by_rich==True) "
    "should influence the decision.\n"
    "- Output the JSON object alone — no prose, no Markdown fencing.\n"
)


def _assemble_reasoning_prompt(
    *,
    target_kind: str,
    target_identifier: str,
    stage_label: str,
    coach_score: float | None,
    criterion_breakdown: dict[str, float],
    detection_findings: list[DetectionFinding],
    retrieved_priors: list[PriorReference],
    calibration_adjustments: list[CalibrationAdjustment],
) -> str:
    """Build a deterministic reasoning-model prompt.

    The prompt embeds the gate inputs as a canonical (sorted-keys) JSON
    payload so identical inputs always produce byte-identical prompts.
    This makes snapshot tests stable and makes prompt-regression bugs
    visible in diff review.

    Args:
        target_kind: Kind of gated target (``local_tool`` |
            ``fleet_capability`` | ``subagent``).
        target_identifier: Identifier of the gated target.
        stage_label: Pipeline stage label producing the decision.
        coach_score: Specialist-agent Coach overall score, or ``None``
            when unavailable (degraded mode).
        criterion_breakdown: Per-criterion Coach scores in ``[0, 1]``.
        detection_findings: Coach pattern findings.
        retrieved_priors: Graphiti priors retrieved by the tool layer.
        calibration_adjustments: Approved bias entities (only entries
            with ``approved_by_rich=True`` are surfaced to the model;
            unapproved adjustments are filtered out).

    Returns:
        The full prompt string (instructions + canonical input JSON).
    """
    payload: dict[str, object] = {
        "target_kind": target_kind,
        "target_identifier": target_identifier,
        "stage_label": stage_label,
        "coach_score": coach_score,
        "criterion_breakdown": dict(sorted(criterion_breakdown.items())),
        "detection_findings": [
            {
                "pattern": finding.pattern,
                "severity": finding.severity,
                "evidence": finding.evidence,
                "criterion": finding.criterion,
            }
            for finding in detection_findings
        ],
        "retrieved_priors": [
            {
                "entity_id": prior.entity_id,
                "group_id": prior.group_id,
                "summary": prior.summary,
                "relevance_score": prior.relevance_score,
            }
            for prior in retrieved_priors
        ],
        "calibration_adjustments": [
            {
                "adjustment_id": adj.adjustment_id,
                "target_capability": adj.target_capability,
                "project_scope": adj.project_scope,
                "observed_pattern": adj.observed_pattern,
                "proposed_bias": adj.proposed_bias,
            }
            for adj in calibration_adjustments
            if adj.approved_by_rich
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, indent=2, default=str)
    return f"{_PROMPT_INSTRUCTIONS}\nINPUTS:\n{canonical}\n"


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def _parse_model_response(raw_response: str) -> ParsedDecision:
    """Parse and validate the reasoning model's structured response.

    The reasoning model is contracted to return a JSON object matching the
    :class:`ParsedDecision` schema. Anything else is a contract violation
    and raises :class:`ReasoningResponseError`.

    Args:
        raw_response: Raw string returned by the reasoning model.

    Returns:
        A validated :class:`ParsedDecision`.

    Raises:
        ReasoningResponseError: If the response is empty, not valid JSON,
            not a JSON object, or fails ``ParsedDecision`` validation.
    """
    if raw_response is None or not raw_response.strip():
        raise ReasoningResponseError(
            "Reasoning model returned an empty or whitespace-only response.",
        )

    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise ReasoningResponseError(
            f"Reasoning model response is not valid JSON: {exc.msg} "
            f"(line {exc.lineno}, column {exc.colno}).",
        ) from exc

    if not isinstance(payload, dict):
        raise ReasoningResponseError(
            "Reasoning model response must be a JSON object; "
            f"got top-level type {type(payload).__name__!r}.",
        )

    try:
        return ParsedDecision.model_validate(payload)
    except ValidationError as exc:
        raise ReasoningResponseError(
            f"Reasoning model response failed schema validation: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Post-condition enforcement (DM-gating §6)
# ---------------------------------------------------------------------------


_DEGRADED_MODE_ALLOWED: frozenset[GateMode] = frozenset(
    {
        GateMode.FLAG_FOR_REVIEW,
        GateMode.HARD_STOP,
        GateMode.MANDATORY_HUMAN_APPROVAL,
    },
)


def _enforce_post_conditions(
    *,
    parsed: ParsedDecision,
    coach_score: float | None,
    detection_findings: list[DetectionFinding],
) -> None:
    """Enforce DM-gating §6 invariants on a parsed reasoning-model decision.

    Two invariants are checked here (the third — criterion-range — is
    enforced **before** the reasoning call by validating the input
    ``criterion_breakdown``):

    1. **Degraded mode** (R3 closure): if ``coach_score is None`` the
       reasoning model MUST choose one of ``FLAG_FOR_REVIEW``,
       ``HARD_STOP``, or ``MANDATORY_HUMAN_APPROVAL``. If it returns
       ``AUTO_APPROVE`` we **raise** rather than silently coerce — the
       coercion path is the exact bug this invariant is designed to
       prevent.
    2. **Critical-finding escalation** (Group C ``@negative``): if any
       supplied :class:`DetectionFinding` has ``severity="critical"`` the
       reasoning model MUST NOT return ``AUTO_APPROVE``. Coercion is
       again forbidden.

    Args:
        parsed: The validated reasoning-model decision.
        coach_score: Coach overall score input to ``evaluate_gate``.
        detection_findings: Detection findings input to ``evaluate_gate``.

    Raises:
        PostConditionError: If any invariant is violated.
    """
    if coach_score is None and parsed.mode not in _DEGRADED_MODE_ALLOWED:
        raise PostConditionError(
            "Degraded-mode post-condition violated (DM-gating §6): "
            "coach_score is None requires mode in "
            "{FLAG_FOR_REVIEW, HARD_STOP, MANDATORY_HUMAN_APPROVAL}; "
            f"reasoning model produced mode={parsed.mode.value!r}. "
            "Refusing to silently coerce (closes risk R3).",
        )

    if (
        any(finding.severity == "critical" for finding in detection_findings)
        and parsed.mode is GateMode.AUTO_APPROVE
    ):
        raise PostConditionError(
            "Critical-finding escalation violated (Group C @negative): "
            "a DetectionFinding with severity='critical' cannot result in "
            "mode=AUTO_APPROVE; reasoning model produced "
            f"mode={parsed.mode.value!r}.",
        )
