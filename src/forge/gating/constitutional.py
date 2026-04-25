"""Constitutional override branch for ``forge.gating.evaluate_gate`` (TASK-CGCP-004).

This module implements the **executor-layer half** of the
ADR-ARCH-026 belt-and-braces rule: pull-request review and pull-request
creation are *always* gated on human approval, regardless of Coach
overall scores, detection findings, retrieved priors, or calibration
adjustments.

The complementary prompt-layer rule (``SAFETY_CONSTITUTION``) lives in
the orchestrator's prompt module and is **out of scope** for this
module. The two layers are deliberately redundant: disabling either one
in isolation must still produce ``MANDATORY_HUMAN_APPROVAL`` (Group E
``@security @regression`` two-layer regression test).

Domain purity (DM-gating §1, ADR-ARCH-019): imports nothing from
``nats_core``, ``nats-py``, ``langgraph``, or ``forge.adapters.*``.

References:

* DM-gating §1 — :class:`GateDecision`, :class:`GateMode`
* DM-gating §6 — invariants enforced by :class:`GateDecision`'s validator
* ADR-ARCH-026 — belt-and-braces constitutional rule
* TASK-CGCP-004 — this branch's specification
"""

from __future__ import annotations

from datetime import UTC, datetime

from .models import GateDecision, GateMode, GateTargetKind

# ---------------------------------------------------------------------------
# Module-level constants (TASK-CGCP-004 AC-001, implementation note 1)
# ---------------------------------------------------------------------------

#: Target identifiers that trigger the executor-layer constitutional
#: override. Defined as a module-level :class:`frozenset` (and **not**
#: inlined inside the function body) so tests, callers, and future
#: ADRs can reference the canonical set rather than reproducing it.
CONSTITUTIONAL_OVERRIDE_TARGETS: frozenset[str] = frozenset(
    {"review_pr", "create_pr_after_review"},
)

#: Rationale string written onto every constitutional-override
#: :class:`GateDecision`. Pinned at module level so the regression suite
#: can assert the exact wording of the rule citation
#: (``ADR-ARCH-026``).
CONSTITUTIONAL_OVERRIDE_RATIONALE: str = (
    "Constitutional override: pull-request review/creation always "
    "requires human approval (ADR-ARCH-026)"
)

#: Sentinel ``build_id`` used when the helper is invoked without an
#: explicit pipeline build identifier. Pydantic enforces
#: ``min_length=1`` on :attr:`GateDecision.build_id`, so an empty string
#: would fail validation; this sentinel makes the placeholder visible
#: in logs and Graphiti exports rather than silent.
_DEFAULT_OVERRIDE_BUILD_ID: str = "<constitutional-override>"

#: Stage label used when the helper is invoked without an explicit
#: stage label (e.g. in direct unit tests).
_DEFAULT_OVERRIDE_STAGE_LABEL: str = "constitutional_override"


# ---------------------------------------------------------------------------
# Override branch
# ---------------------------------------------------------------------------


def _check_constitutional_override(
    target_identifier: str,
    *,
    target_kind: GateTargetKind = "local_tool",
    stage_label: str = _DEFAULT_OVERRIDE_STAGE_LABEL,
    build_id: str = _DEFAULT_OVERRIDE_BUILD_ID,
    decided_at: datetime | None = None,
) -> GateDecision | None:
    """Return the executor-layer constitutional override decision, if any.

    The matching set :data:`CONSTITUTIONAL_OVERRIDE_TARGETS` lists the
    ``target_identifier`` values that *unconditionally* require human
    approval per ADR-ARCH-026. For any other identifier this function
    returns ``None`` so :func:`forge.gating.evaluate_gate` can fall
    through to the reasoning-model branch (TASK-CGCP-005).

    The decision returned for a matching identifier has::

        mode                  = GateMode.MANDATORY_HUMAN_APPROVAL
        auto_approve_override = True
        threshold_applied     = None
        rationale             = CONSTITUTIONAL_OVERRIDE_RATIONALE
        coach_score           = None
        degraded_mode         = True

    These six fields are the ones the regression suite (Group A,
    Group C, Group E ``@security @regression``) pins. The remaining
    executor-context fields (``build_id``, ``stage_label``,
    ``target_kind``, ``decided_at``) are taken from keyword arguments so
    the orchestrator can stamp them with values from the live pipeline;
    sensible defaults are provided for direct unit tests of this helper.

    Note that ``coach_score`` is intentionally ``None`` — the override
    short-circuits before the Coach is consulted (AC-003), so any value
    here would imply a contract that does not exist. ``degraded_mode``
    follows from DM-gating §6 invariant 2: when ``coach_score is None``,
    ``mode`` must be one of ``{FLAG_FOR_REVIEW, HARD_STOP,
    MANDATORY_HUMAN_APPROVAL}`` — the override satisfies that by
    construction.

    Args:
        target_identifier: Identifier of the gated target — the **only**
            input that determines whether the override fires.
        target_kind: Kind of gated target. Defaults to ``"local_tool"``.
        stage_label: Pipeline stage label that produced the decision.
            Defaults to a sentinel that makes direct unit-test calls
            distinguishable from real pipeline calls.
        build_id: Pipeline build identifier. The orchestrator should
            pass its real build id; the default is a visible sentinel.
        decided_at: UTC timestamp of the decision; defaults to *now*
            (UTC) when omitted.

    Returns:
        A fully-formed :class:`GateDecision` if ``target_identifier`` is
        in :data:`CONSTITUTIONAL_OVERRIDE_TARGETS`; ``None`` otherwise.
    """
    if target_identifier not in CONSTITUTIONAL_OVERRIDE_TARGETS:
        return None

    return GateDecision(
        build_id=build_id,
        stage_label=stage_label,
        target_kind=target_kind,
        target_identifier=target_identifier,
        mode=GateMode.MANDATORY_HUMAN_APPROVAL,
        rationale=CONSTITUTIONAL_OVERRIDE_RATIONALE,
        coach_score=None,
        criterion_breakdown={},
        detection_findings=[],
        evidence=[],
        threshold_applied=None,
        auto_approve_override=True,
        degraded_mode=True,
        decided_at=decided_at if decided_at is not None else datetime.now(UTC),
    )


__all__ = [
    "CONSTITUTIONAL_OVERRIDE_RATIONALE",
    "CONSTITUTIONAL_OVERRIDE_TARGETS",
    "_check_constitutional_override",
]
