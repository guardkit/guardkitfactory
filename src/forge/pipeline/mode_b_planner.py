"""Mode B chain planner (TASK-MBC8-003, FEAT-FORGE-008).

This module defines :class:`ModeBChainPlanner` — a pure-function planner
that takes the build's recorded stage history and returns the next
permitted stage in the Mode B chain. The planner is the security boundary
in FEAT-FORGE-008 Group J (ASSUM-013): even if a context manifest
references ``/system-arch`` or ``/system-design``, no Mode B build
dispatches them. This guard fires at the planning layer and is the only
secure layer — executor-side guards run later and cannot put stages back
into the chain.

Single-feature contract
-----------------------

The planner is the Mode B counterpart to MAG7's
:class:`~forge.pipeline.per_feature_sequencer.PerFeatureLoopSequencer`
(TASK-MAG7-005) and reuses its single-feature-only contract
(FEAT-FORGE-008 ASSUM-006): a Mode B build operates on exactly one
feature and culminates in exactly one ``PULL_REQUEST_REVIEW`` pause.

Pure-function shape
-------------------

The planner is stateless. Every call takes ``(build, history)`` and
returns a :class:`ModeBPlan`. Persisted state lives in the
:class:`~forge.lifecycle.persistence.Build` value object and the
``stage_log`` rows already; the planner does not own any I/O surface
and does no mutation.

Boundary diagnostic vs. ordering error
--------------------------------------

The :class:`ModeBoundaryViolation` exception is intentionally distinct
from a generic ``StageOrderingError`` — callers (the Supervisor in
TASK-MBC8-008) surface a security audit message rather than a generic
ordering error when the violation fires.

The :class:`MissingSpecArtefacts` diagnostic is also intentionally
distinct from a status-based termination: an empty-artefacts FEATURE_SPEC
result needs a ``flag-for-review`` outcome with a missing-spec rationale,
not a hard-stop terminal state.

References
----------

- TASK-MBC8-003 — this implementation.
- FEAT-FORGE-008 ASSUM-001 — Mode B chain
  (``feature-spec → feature-plan → autobuild → pull-request-review``).
- FEAT-FORGE-008 ASSUM-006 — single-feature-only contract.
- FEAT-FORGE-008 ASSUM-013 — mode-aware planning refuses upstream Mode A
  stages even when a context manifest references them.
- FEAT-FORGE-008 ASSUM-014 — Mode B does not dispatch to product-owner /
  architect specialists.
- TASK-MBC8-006 — no-diff terminal handler. This planner returns
  ``None`` for the no-diff branch so the terminal handler can decide
  between PR creation and a no-op terminal outcome.
- TASK-MBC8-008 — Supervisor integration (consumes
  :attr:`ModeBPlan.permitted_stages` to scope its dispatch switch).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from forge.lifecycle.persistence import Build
from forge.pipeline.mode_chains_data import (
    MODE_B_CHAIN,
    MODE_B_FORBIDDEN_STAGES,
)
from forge.pipeline.stage_taxonomy import StageClass

__all__ = [
    "APPROVED",
    "EMPTY_ARTEFACTS",
    "FAILED",
    "HARD_STOP",
    "MODE_B_PERMITTED_STAGES",
    "MissingSpecArtefacts",
    "ModeBChainPlanner",
    "ModeBPlan",
    "ModeBoundaryViolation",
    "StageEntry",
    "plan_next_stage",
]


# ---------------------------------------------------------------------------
# Permitted stages — frozen subset of MODE_B_CHAIN
# ---------------------------------------------------------------------------


#: Stages permitted by the Mode B chain.
#:
#: Equals ``frozenset(MODE_B_CHAIN)`` — the Mode B suffix of the Mode A chain
#: starting at ``FEATURE_SPEC``. Returned verbatim as
#: :attr:`ModeBPlan.permitted_stages` so :meth:`Supervisor.next_turn` (in
#: TASK-MBC8-008) can scope its dispatch switch without re-deriving the
#: subset.
MODE_B_PERMITTED_STAGES: frozenset[StageClass] = frozenset(MODE_B_CHAIN)


# ---------------------------------------------------------------------------
# Stage-entry status literals
# ---------------------------------------------------------------------------


#: Gate decision indicating the stage's coach output cleared the gate.
APPROVED = "approved"

#: Gate decision indicating a hard-stop fired against the stage. Terminates
#: the build; subsequent stages are not dispatched (Group C negative case).
HARD_STOP = "hard_stop"

#: Status indicating the stage's dispatch failed (subprocess returned a
#: non-zero exit code, or the dispatch raised). Terminates the chain.
FAILED = "failed"

#: Boundary marker for a FEATURE_SPEC stage that ran but produced no
#: artefact paths. The planner emits a :class:`MissingSpecArtefacts`
#: diagnostic regardless of how this is signalled (empty
#: ``details["artefact_paths"]`` works equivalently).
EMPTY_ARTEFACTS = "empty_artefacts"


# ---------------------------------------------------------------------------
# StageEntry — minimal Protocol over a stage_log row
# ---------------------------------------------------------------------------


@runtime_checkable
class StageEntry(Protocol):
    """Minimal stage-log entry shape consumed by the planner.

    Production wires the FEAT-FORGE-001 stage_log rows (or a
    :class:`~forge.lifecycle.persistence.StageLogEntry` projection); tests
    inject simple dataclasses or :class:`types.SimpleNamespace` instances
    with the same four attributes.

    The Protocol is deliberately narrow — no timestamps, no coach scores,
    no gate metadata. The planner only needs to know which stage class
    ran, what the gate decided, which feature the entry is scoped to, and
    a small details bag for the two boundary checks (empty FEATURE_SPEC
    artefacts and AUTOBUILD diff presence).

    Attributes:
        stage: The :class:`StageClass` this entry records. The planner
            iterates the history once to find entries by stage class — it
            does not consult labels or string representations.
        status: Gate / dispatch outcome for the stage. The planner
            recognises :data:`APPROVED`, :data:`HARD_STOP`, :data:`FAILED`
            and :data:`EMPTY_ARTEFACTS`; any other value is treated as
            "still in flight, do not advance".
        feature_id: The feature this entry is scoped to. Per-feature Mode
            B stages (``FEATURE_SPEC``, ``FEATURE_PLAN``, ``AUTOBUILD``,
            ``PULL_REQUEST_REVIEW``) carry the feature id; entries
            outside the per-feature set are tolerated with ``None``.
        details: Arbitrary metadata bag. Two keys are read:

            - ``"artefact_paths"`` — sequence of strings; an empty
              sequence on a FEATURE_SPEC entry triggers
              :class:`MissingSpecArtefacts`.
            - ``"diff_present"`` — boolean; ``True`` on an approved
              AUTOBUILD entry advances to ``PULL_REQUEST_REVIEW``,
              ``False`` returns ``next_stage = None`` for the
              TASK-MBC8-006 terminal handler.
    """

    stage: StageClass
    status: str
    feature_id: str | None
    details: Mapping[str, Any]


# ---------------------------------------------------------------------------
# Domain exceptions and diagnostics
# ---------------------------------------------------------------------------


class ModeBoundaryViolation(Exception):
    """Raised when a Mode B planner is asked to dispatch a forbidden stage.

    Mode B's chain is fixed by FEAT-FORGE-008 ASSUM-001 / ASSUM-013. The
    four pre-feature-spec Mode A stages (``PRODUCT_OWNER``, ``ARCHITECT``,
    ``SYSTEM_ARCH``, ``SYSTEM_DESIGN``) are explicitly forbidden via
    :data:`~forge.pipeline.mode_chains_data.MODE_B_FORBIDDEN_STAGES`.

    This exception is intentionally distinct from a generic
    ``StageOrderingError`` so callers can surface a security audit message
    rather than a generic ordering error.

    Attributes:
        stage: The forbidden stage that triggered the violation.
        build_id: The build whose history (or manifest) referenced the
            forbidden stage.
        assumption: The FEAT-FORGE-008 assumption identifier this
            violation maps to. Always ``"ASSUM-013"``.
    """

    assumption: str = "ASSUM-013"

    def __init__(
        self,
        stage: StageClass,
        *,
        build_id: str | None = None,
    ) -> None:
        message = (
            f"Mode B planner refuses to dispatch forbidden Mode A stage "
            f"{stage.value!r} (build_id={build_id!r}). "
            f"See FEAT-FORGE-008 ASSUM-013 (mode-aware planning refuses "
            f"upstream Mode A stages)."
        )
        super().__init__(message)
        self.stage = stage
        self.build_id = build_id


@dataclass(frozen=True, slots=True)
class MissingSpecArtefacts:
    """Diagnostic emitted when the Mode B FEATURE_SPEC entry has no artefacts.

    The Mode B Group B boundary scenario "A Mode B feature-specification
    stage that produces no spec artefacts cannot enter feature planning"
    requires the build to be flagged for review with the missing-spec
    rationale recorded. The Supervisor reads this diagnostic off the
    returned :class:`ModeBPlan` and records the flag-for-review.

    Attributes:
        build_id: The build whose history triggered the diagnostic.
        feature_id: The feature whose FEATURE_SPEC produced no artefacts;
            may be ``None`` if the stage entry did not carry a
            ``feature_id`` (defensive against malformed history rows).
        rationale: Human-readable explanation written verbatim into the
            ``stage_log`` row.
    """

    build_id: str
    feature_id: str | None
    rationale: str = (
        "missing-spec: feature-specification produced no artefact paths"
    )


@dataclass(frozen=True, slots=True)
class ModeBPlan:
    """Decision returned by :meth:`ModeBChainPlanner.plan_next_stage`.

    The plan is consumed by the Supervisor's reasoning loop. The
    ``permitted_stages`` set is what scopes the dispatch switch in
    TASK-MBC8-008; ``next_stage`` is the actual decision.

    Attributes:
        permitted_stages: Frozen subset of :class:`StageClass` enumerating
            the stages a Mode B build is allowed to dispatch. Always
            equals :data:`MODE_B_PERMITTED_STAGES` — exposed on the plan
            for caller introspection without forcing a separate import.
        next_stage: The stage to dispatch next, or ``None`` when the build
            should not advance. ``None`` is returned when:

            * ``FEATURE_SPEC`` was hard-stopped or failed — Group C
              negative case.
            * ``FEATURE_SPEC`` produced empty artefacts — Group B
              boundary; ``diagnostics`` carries a
              :class:`MissingSpecArtefacts` entry.
            * ``AUTOBUILD`` is approved but reported no diff — delegated
              to TASK-MBC8-006's no-diff terminal handler.
            * Any in-flight stage has not yet been approved — the build
              is awaiting a gate decision.
            * The chain is complete (``PULL_REQUEST_REVIEW`` approved).
        rationale: Human-readable explanation. Non-empty whenever
            ``next_stage`` is ``None`` so the Supervisor can record it on
            the build's stage history.
        diagnostics: Tuple of diagnostics this decision emitted. Empty
            for happy-path advancements; carries
            :class:`MissingSpecArtefacts` for the empty-artefacts case.
    """

    permitted_stages: frozenset[StageClass]
    next_stage: StageClass | None
    rationale: str = ""
    diagnostics: tuple[MissingSpecArtefacts, ...] = ()


# ---------------------------------------------------------------------------
# The planner
# ---------------------------------------------------------------------------


class ModeBChainPlanner:
    """Pure-function planner for the Mode B chain.

    Stateless — every call takes ``(build, history)`` and returns a
    :class:`ModeBPlan`. The same instance can be reused across builds and
    threads without ownership ambiguity.

    The decision tree, in order of evaluation:

    1. **Boundary check** — every entry's ``stage`` is matched against
       :data:`~forge.pipeline.mode_chains_data.MODE_B_FORBIDDEN_STAGES`;
       a forbidden stage raises :class:`ModeBoundaryViolation` (ASSUM-013).
    2. **Empty history** → ``next_stage = FEATURE_SPEC`` (chain entry).
    3. **FEATURE_SPEC terminal** — ``HARD_STOP`` / ``FAILED`` returns
       ``next_stage = None`` with a Group C rationale.
    4. **Empty FEATURE_SPEC artefacts** → ``next_stage = None`` plus a
       :class:`MissingSpecArtefacts` diagnostic (Group B boundary).
    5. **FEATURE_SPEC awaiting approval** → ``next_stage = None``,
       rationale records the wait.
    6. **FEATURE_SPEC approved** → ``next_stage = FEATURE_PLAN`` if the
       plan stage has not yet started, else recurse against
       ``FEATURE_PLAN`` status.
    7. **FEATURE_PLAN approved** → ``next_stage = AUTOBUILD`` if the
       autobuild stage has not yet started, else recurse.
    8. **AUTOBUILD approved with non-empty diff** →
       ``next_stage = PULL_REQUEST_REVIEW``.
    9. **AUTOBUILD approved with no diff** → ``next_stage = None``,
       deferring to TASK-MBC8-006's terminal handler.
    10. **PULL_REQUEST_REVIEW approved** → chain complete, ``None``.

    Example:
        >>> from forge.lifecycle.persistence import Build
        >>> from forge.lifecycle.modes import BuildMode
        >>> from forge.pipeline.supervisor import BuildState
        >>> build = Build(
        ...     build_id="build-FEAT-X-20260427",
        ...     status=BuildState.RUNNING,
        ...     mode=BuildMode.MODE_B,
        ... )
        >>> planner = ModeBChainPlanner()
        >>> plan = planner.plan_next_stage(build, history=())
        >>> plan.next_stage is StageClass.FEATURE_SPEC
        True
    """

    def plan_next_stage(
        self,
        build: Build,
        history: Sequence[StageEntry],
    ) -> ModeBPlan:
        """Return the next permitted Mode B stage for ``(build, history)``.

        See class docstring for the full decision tree. The method itself
        is short and dispatches against ``history``-derived "latest entry
        per stage class" snapshots so the order of entries within a
        history sequence does not matter — only the latest entry per
        stage is consulted.

        Args:
            build: The build value object. Only :attr:`Build.build_id` is
                read; ``status`` and ``mode`` are accepted for parity with
                callers that already hold a ``Build`` and not consulted by
                the planner itself (mode is implicit by virtue of calling
                the Mode B planner).
            history: Recorded stage history for the build. May be empty.
                Iteration order is preserved when picking the "latest"
                entry per stage class — callers should pass entries in
                chronological order.

        Returns:
            A :class:`ModeBPlan` carrying ``permitted_stages``, the chosen
            ``next_stage`` (or ``None``), a rationale, and any diagnostics.

        Raises:
            ModeBoundaryViolation: If any entry in ``history`` references
                a stage in
                :data:`~forge.pipeline.mode_chains_data.MODE_B_FORBIDDEN_STAGES`.
                The exception message names the forbidden stage and
                references ASSUM-013.
        """
        self._enforce_boundary(build.build_id, history)

        spec_entry = self._latest_for_stage(history, StageClass.FEATURE_SPEC)
        plan_entry = self._latest_for_stage(history, StageClass.FEATURE_PLAN)
        autobuild_entry = self._latest_for_stage(history, StageClass.AUTOBUILD)
        pr_entry = self._latest_for_stage(
            history, StageClass.PULL_REQUEST_REVIEW
        )

        # Empty history → start at FEATURE_SPEC (AC: empty history → FEATURE_SPEC).
        if spec_entry is None:
            return self._advance(StageClass.FEATURE_SPEC)

        # Group C negative cases — hard-stop / failed FEATURE_SPEC dispatch.
        if spec_entry.status in (HARD_STOP, FAILED):
            return self._halt(
                rationale=(
                    f"Mode B halted at feature-specification "
                    f"(status={spec_entry.status!r}); no later stage dispatched."
                ),
            )

        # Group B boundary — FEATURE_SPEC ran but produced no artefacts.
        if self._has_empty_artefacts(spec_entry):
            diagnostic = MissingSpecArtefacts(
                build_id=build.build_id,
                feature_id=spec_entry.feature_id,
            )
            return ModeBPlan(
                permitted_stages=MODE_B_PERMITTED_STAGES,
                next_stage=None,
                rationale=diagnostic.rationale,
                diagnostics=(diagnostic,),
            )

        # FEATURE_SPEC still in flight (e.g. flagged for review, awaiting
        # approval). Do not advance.
        if spec_entry.status != APPROVED:
            return self._wait(StageClass.FEATURE_SPEC, spec_entry.status)

        # FEATURE_SPEC approved → advance to FEATURE_PLAN if not yet started.
        if plan_entry is None:
            return self._advance(StageClass.FEATURE_PLAN)

        # FEATURE_PLAN terminal failure paths mirror FEATURE_SPEC handling.
        if plan_entry.status in (HARD_STOP, FAILED):
            return self._halt(
                rationale=(
                    f"Mode B halted at feature-planning "
                    f"(status={plan_entry.status!r}); no autobuild dispatched."
                ),
            )
        if plan_entry.status != APPROVED:
            return self._wait(StageClass.FEATURE_PLAN, plan_entry.status)

        # FEATURE_PLAN approved → advance to AUTOBUILD if not yet started.
        if autobuild_entry is None:
            return self._advance(StageClass.AUTOBUILD)

        if autobuild_entry.status in (HARD_STOP, FAILED):
            return self._halt(
                rationale=(
                    f"Mode B halted at autobuild "
                    f"(status={autobuild_entry.status!r}); no pull-request "
                    f"dispatched."
                ),
            )
        if autobuild_entry.status != APPROVED:
            return self._wait(StageClass.AUTOBUILD, autobuild_entry.status)

        # AUTOBUILD approved → branch on diff presence.
        diff_present = bool(
            autobuild_entry.details.get("diff_present", False)
        )

        # PULL_REQUEST_REVIEW already recorded — either complete or paused.
        if pr_entry is not None:
            if pr_entry.status == APPROVED:
                return self._halt(
                    rationale=(
                        "Mode B chain complete: pull-request review approved."
                    ),
                )
            if pr_entry.status in (HARD_STOP, FAILED):
                return self._halt(
                    rationale=(
                        f"Mode B halted at pull-request review "
                        f"(status={pr_entry.status!r})."
                    ),
                )
            return self._wait(
                StageClass.PULL_REQUEST_REVIEW, pr_entry.status
            )

        # No PR entry yet — diff presence decides the next move.
        if diff_present:
            return self._advance(StageClass.PULL_REQUEST_REVIEW)

        return self._halt(
            rationale=(
                "autobuild produced no diff against the working branch; "
                "deferring terminal decision to TASK-MBC8-006 no-diff handler."
            ),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _enforce_boundary(
        build_id: str,
        history: Sequence[StageEntry],
    ) -> None:
        """Raise :class:`ModeBoundaryViolation` on any forbidden stage entry.

        Walks the history once. The first forbidden stage observed wins —
        the violation is structural (no Mode B build should ever record a
        Mode A pre-feature-spec stage), so we do not bother accumulating.
        """
        for entry in history:
            if entry.stage in MODE_B_FORBIDDEN_STAGES:
                raise ModeBoundaryViolation(
                    entry.stage, build_id=build_id
                )

    @staticmethod
    def _latest_for_stage(
        history: Sequence[StageEntry],
        stage: StageClass,
    ) -> StageEntry | None:
        """Return the last entry whose ``stage`` matches, or ``None``.

        Linear scan keeps the planner free of any list/dict allocations
        beyond the loop variables themselves; for the Mode B chain (four
        stages, single feature) the input sequence is short enough that
        this beats building intermediate dictionaries.
        """
        latest: StageEntry | None = None
        for entry in history:
            if entry.stage is stage:
                latest = entry
        return latest

    @staticmethod
    def _has_empty_artefacts(entry: StageEntry) -> bool:
        """Detect an empty-artefacts Group B boundary case for FEATURE_SPEC.

        Two equivalent signals are accepted:

        - ``entry.status == EMPTY_ARTEFACTS`` — explicit boundary marker.
        - ``entry.details["artefact_paths"]`` is an empty container —
          the gate may have written the spec row with status approved
          but the producer emitted nothing.

        The check is safe against missing keys and non-sized values: a
        ``details`` dict with no ``artefact_paths`` key is treated as
        "no signal", not as "empty"; an ``artefact_paths`` value that is
        not :class:`Sized` is also treated as "no signal" so a malformed
        history row does not silently halt the build.
        """
        if entry.status == EMPTY_ARTEFACTS:
            return True
        artefacts = entry.details.get("artefact_paths")
        if artefacts is None:
            return False
        try:
            return len(artefacts) == 0
        except TypeError:
            # Non-sized value (e.g. None passed through) — treat as no signal.
            return False

    @staticmethod
    def _advance(stage: StageClass) -> ModeBPlan:
        """Build a happy-path advancement plan."""
        return ModeBPlan(
            permitted_stages=MODE_B_PERMITTED_STAGES,
            next_stage=stage,
        )

    @staticmethod
    def _halt(rationale: str) -> ModeBPlan:
        """Build a terminate / no-advance plan with a rationale."""
        return ModeBPlan(
            permitted_stages=MODE_B_PERMITTED_STAGES,
            next_stage=None,
            rationale=rationale,
        )

    @classmethod
    def _wait(cls, stage: StageClass, status: str) -> ModeBPlan:
        """Build a "stage not yet approved, do not advance" plan."""
        return cls._halt(
            rationale=(
                f"awaiting approval at {stage.value!r} (status={status!r})"
            ),
        )


# ---------------------------------------------------------------------------
# Functional shortcut
# ---------------------------------------------------------------------------


def plan_next_stage(
    build: Build,
    history: Sequence[StageEntry],
) -> ModeBPlan:
    """Functional shortcut over :meth:`ModeBChainPlanner.plan_next_stage`.

    Provided so callers that hold no planner instance can call the
    planner with a single import. Equivalent to:

    >>> ModeBChainPlanner().plan_next_stage(build, history)

    Args:
        build: The build value object.
        history: Recorded stage history.

    Returns:
        The :class:`ModeBPlan` produced by the planner.

    Raises:
        ModeBoundaryViolation: Propagated from the planner unchanged.
    """
    return ModeBChainPlanner().plan_next_stage(build, history)
