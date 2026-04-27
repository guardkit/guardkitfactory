"""Executor-layer ``ConstitutionalGuard`` for FEAT-FORGE-007 (TASK-MAG7-004).

This module is the **executor-layer half** of the ADR-ARCH-026
belt-and-braces rule for FEAT-FORGE-007 Mode A: pull-request review (and
any other constitutional stage declared in
:data:`forge.pipeline.stage_taxonomy.CONSTITUTIONAL_STAGES`) must always
resolve under mandatory human approval. The complementary prompt-layer
half lives in the supervisor's ``GUARDRAILS`` system-prompt section
(out of scope for this module — wired in FEAT-FORGE-004).

Loss of either layer is a constitutional regression. The Group E
``@security @regression`` test deliberately misconfigures the prompt
and asserts that this guard still refuses — that is the canary for the
belt-and-braces invariant.

The guard is a **pure function**: no I/O, no async, no network. It is
parametrised on the constitutional-stages set so the same code path is
exercised by Group E negative-control tests that pass an empty set.

References:

* ADR-ARCH-026 — Constitutional Rules at Two Layers (belt-and-braces).
* FEAT-FORGE-007 Group C (auto-approve refused, skip refused).
* FEAT-FORGE-007 Group E (security: misconfigured prompt; specialist
  override claim).
* TASK-MAG7-001 — :class:`StageClass` and
  :data:`CONSTITUTIONAL_STAGES`.
* FEAT-FORGE-004 ASSUM-004 — constitutional override target identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from forge.pipeline.stage_taxonomy import CONSTITUTIONAL_STAGES, StageClass

__all__ = [
    "AutoApproveDecision",
    "AutoApproveVerdict",
    "ConstitutionalGuard",
    "SkipDecision",
    "SkipVerdict",
]


# ---------------------------------------------------------------------------
# Verdict enums — the closed alphabets the two decision-returning vetoes
# can yield. ``StrEnum`` so values round-trip through JSON / stage-log
# serialisation without a translation table.
# ---------------------------------------------------------------------------


class AutoApproveVerdict(StrEnum):
    """Verdicts returned by :meth:`ConstitutionalGuard.veto_auto_approve`.

    * ``REFUSED``  — stage is constitutional; auto-approve forbidden.
    * ``ALLOWED`` — stage is not constitutional; auto-approve permitted
      at this layer (other gates upstream may still refuse).
    """

    REFUSED = "refused"
    ALLOWED = "allowed"


class SkipVerdict(StrEnum):
    """Verdicts returned by :meth:`ConstitutionalGuard.veto_skip`.

    * ``REFUSED_CONSTITUTIONAL`` — stage is constitutional; cannot be
      skipped (AC-003).
    * ``ALLOWED`` — stage is not constitutional; skipping is permitted
      at this layer.
    """

    REFUSED_CONSTITUTIONAL = "refused_constitutional"
    ALLOWED = "allowed"


# ---------------------------------------------------------------------------
# Decision records — the structured return shapes carrying the verdict
# alongside a rationale string suitable for ``stage_log.gate_rationale``
# (AC-005). Frozen dataclasses give us value-equality (so idempotency
# tests can compare two decisions directly) without dragging in
# pydantic — the guard module is intentionally dependency-light.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AutoApproveDecision:
    """Decision returned by :meth:`ConstitutionalGuard.veto_auto_approve`.

    Attributes:
        stage: The stage the decision was made about.
        verdict: ``REFUSED`` for constitutional stages, ``ALLOWED``
            otherwise.
        rationale: Structured string suitable for recording in
            ``stage_log.gate_rationale``. Cites ADR-ARCH-026 when the
            verdict is ``REFUSED``.
    """

    stage: StageClass
    verdict: AutoApproveVerdict
    rationale: str

    @property
    def is_refused(self) -> bool:
        """``True`` iff the verdict is ``REFUSED``."""
        return self.verdict is AutoApproveVerdict.REFUSED


@dataclass(frozen=True, slots=True)
class SkipDecision:
    """Decision returned by :meth:`ConstitutionalGuard.veto_skip`.

    Attributes:
        stage: The stage the decision was made about.
        verdict: ``REFUSED_CONSTITUTIONAL`` for constitutional stages,
            ``ALLOWED`` otherwise.
        rationale: Structured string suitable for recording in
            ``stage_log.gate_rationale``. Cites ADR-ARCH-026 when the
            verdict is ``REFUSED_CONSTITUTIONAL``.
    """

    stage: StageClass
    verdict: SkipVerdict
    rationale: str

    @property
    def is_refused(self) -> bool:
        """``True`` iff the verdict is ``REFUSED_CONSTITUTIONAL``."""
        return self.verdict is SkipVerdict.REFUSED_CONSTITUTIONAL


# ---------------------------------------------------------------------------
# Rationale templates — module-level constants so callers and the
# regression suite can reference the canonical wording rather than
# reproducing it. Each cites ADR-ARCH-026 explicitly per AC-005.
# ---------------------------------------------------------------------------


_AUTO_APPROVE_REFUSED_RATIONALE = (
    "ADR-ARCH-026 belt-and-braces: stage {stage!s} is constitutional; "
    "auto-approve REFUSED at executor layer regardless of upstream "
    "Coach score."
)

_AUTO_APPROVE_ALLOWED_RATIONALE = (
    "Stage {stage!s} is not in CONSTITUTIONAL_STAGES; auto-approve "
    "permitted at the constitutional executor layer (other gates may "
    "still refuse)."
)

_SKIP_REFUSED_RATIONALE = (
    "ADR-ARCH-026 belt-and-braces: stage {stage!s} is constitutional "
    "and cannot be skipped; skip directive REFUSED_CONSTITUTIONAL at "
    "executor layer."
)

_SKIP_ALLOWED_RATIONALE = (
    "Stage {stage!s} is not in CONSTITUTIONAL_STAGES; skip permitted at "
    "the constitutional executor layer (other gates may still refuse)."
)


# ---------------------------------------------------------------------------
# Guard
# ---------------------------------------------------------------------------


class ConstitutionalGuard:
    """Executor-layer guard enforcing the ADR-ARCH-026 belt-and-braces rule.

    The guard exposes three pure synchronous methods that an
    orchestrator or dispatcher consults *before* dispatching, skipping,
    or auto-approving a constitutional stage. Each method is independent
    of upstream Coach score, prompt-layer rules, and any specialist
    override claim — refusal is keyed off the stage alone (AC-002 ..
    AC-004).

    The constitutional-stages set is dependency-injected so tests can
    exercise the negative path (an empty set) without monkey-patching
    module-level state. Production callers use the default which
    sources :data:`forge.pipeline.stage_taxonomy.CONSTITUTIONAL_STAGES`
    (TASK-MAG7-001).

    Attributes:
        constitutional_stages: The frozen set of stages the guard
            treats as constitutional. Defaults to
            :data:`forge.pipeline.stage_taxonomy.CONSTITUTIONAL_STAGES`.
    """

    __slots__ = ("constitutional_stages",)

    def __init__(
        self,
        constitutional_stages: frozenset[StageClass] = CONSTITUTIONAL_STAGES,
    ) -> None:
        # Defensive copy via ``frozenset()`` so callers passing a
        # mutable set cannot mutate the guard's view after construction.
        # The attribute is publicly readable but not writable (slots).
        self.constitutional_stages: frozenset[StageClass] = frozenset(
            constitutional_stages
        )

    # ------------------------------------------------------------------
    # AC-002 / AC-005 — auto-approve veto
    # ------------------------------------------------------------------

    def veto_auto_approve(self, stage: StageClass) -> AutoApproveDecision:
        """Return the auto-approve decision for ``stage``.

        Constitutional stages return :attr:`AutoApproveVerdict.REFUSED`
        regardless of upstream Coach score (AC-002). Non-constitutional
        stages return :attr:`AutoApproveVerdict.ALLOWED` so other
        executor-layer gates can take their turn.

        Args:
            stage: The stage being considered for auto-approval.

        Returns:
            An :class:`AutoApproveDecision` carrying the verdict, the
            stage, and a structured rationale string suitable for
            recording in ``stage_log.gate_rationale`` (AC-005).
        """
        if stage in self.constitutional_stages:
            return AutoApproveDecision(
                stage=stage,
                verdict=AutoApproveVerdict.REFUSED,
                rationale=_AUTO_APPROVE_REFUSED_RATIONALE.format(stage=stage),
            )
        return AutoApproveDecision(
            stage=stage,
            verdict=AutoApproveVerdict.ALLOWED,
            rationale=_AUTO_APPROVE_ALLOWED_RATIONALE.format(stage=stage),
        )

    # ------------------------------------------------------------------
    # AC-003 / AC-005 — skip veto
    # ------------------------------------------------------------------

    def veto_skip(self, stage: StageClass) -> SkipDecision:
        """Return the skip decision for ``stage``.

        Constitutional stages return
        :attr:`SkipVerdict.REFUSED_CONSTITUTIONAL` (AC-003).
        Non-constitutional stages return :attr:`SkipVerdict.ALLOWED`.

        Args:
            stage: The stage being considered for skipping.

        Returns:
            A :class:`SkipDecision` carrying the verdict, the stage,
            and a structured rationale string (AC-005).
        """
        if stage in self.constitutional_stages:
            return SkipDecision(
                stage=stage,
                verdict=SkipVerdict.REFUSED_CONSTITUTIONAL,
                rationale=_SKIP_REFUSED_RATIONALE.format(stage=stage),
            )
        return SkipDecision(
            stage=stage,
            verdict=SkipVerdict.ALLOWED,
            rationale=_SKIP_ALLOWED_RATIONALE.format(stage=stage),
        )

    # ------------------------------------------------------------------
    # AC-004 — specialist-override-claim veto
    # ------------------------------------------------------------------

    def veto_override_claim(
        self,
        stage: StageClass,
        claim: Mapping[str, Any],
    ) -> bool:
        """Return ``True`` (ignore-the-claim) when ``stage`` is constitutional.

        The ``claim`` argument is accepted for caller ergonomics and
        future audit-logging hooks but is **deliberately ignored** by
        the veto logic — AC-004 demands that the verdict depend only on
        the stage. A specialist-override claim cannot be smuggled
        through this method by being especially loud or by asserting
        higher authority.

        Args:
            stage: The stage the claim was made against.
            claim: The specialist's override claim payload. Ignored by
                the veto logic. Accepted as
                :class:`~typing.Mapping` for caller flexibility.

        Returns:
            ``True`` if ``stage`` is constitutional (and the claim must
            therefore be ignored); ``False`` otherwise.
        """
        # ``claim`` is intentionally unused — referenced here so static
        # analysis does not flag the parameter as dead. The Group E
        # security regression confirms that varying the claim payload
        # cannot change the verdict.
        del claim
        return stage in self.constitutional_stages
