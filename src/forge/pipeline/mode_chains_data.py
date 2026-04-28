"""Declarative chain and prerequisite data for Mode B and Mode C.

This module is pure declarative data — no runtime behaviour, no I/O, and
no imports from sibling ``forge.pipeline.*`` submodules other than
:mod:`forge.pipeline.stage_taxonomy` (the canonical :class:`StageClass`
enum). It exists so the Wave 2 planners (``ModeBPlanner``,
``ModeCCyclePlanner``) can be pure functions over the data here.

The constitutional ``PULL_REQUEST_REVIEW`` stage is **shared across all
three modes** (FEAT-FORGE-008 ASSUM-011). Per ADR-ARCH-026 the
constitutional rule is mode-agnostic and is enforced once on the
existing ``ConstitutionalGuard`` from TASK-MAG7-004, not duplicated per
mode.

Mode-specific notes:

- **Mode B** (FEAT-FORGE-008 ASSUM-001) is a strict suffix of the Mode A
  chain starting at ``/feature-spec``. It explicitly skips
  ``product-owner``, ``architect``, ``/system-arch`` and
  ``/system-design`` — those four stages are listed in
  :data:`MODE_B_FORBIDDEN_STAGES`. ASSUM-013 (mode-aware planning
  refuses upstream Mode A stages) and ASSUM-014 (Mode B does not
  dispatch to specialists) are direct consequences.

- **Mode C** (FEAT-FORGE-008 ASSUM-004) is a cyclic chain
  ``/task-review → /task-work → pull-request-review``. The chain shape
  is intentionally length-3, *not* length-2: the per-fix-task fan-out of
  ``/task-work`` is the responsibility of the cycle controller in
  TASK-MBC8-004, not encoded in the chain shape itself. The terminal
  ``pull-request-review`` is conditional — see ASSUM-005 (a Mode C
  build that produces commits ends with PR review) and ASSUM-017 (a
  Mode C build that produces no commits ends in a clean-review terminal
  outcome). Mode C operates on existing artefacts; it forbids every
  Mode A pre-feature-spec stage as well as ``feature-spec``,
  ``feature-plan`` and ``autobuild``.

References:
    - FEAT-FORGE-008 ASSUM-001 — Mode B chain
      (``feature-spec → feature-plan → autobuild → pull-request-review``).
    - FEAT-FORGE-008 ASSUM-004 — Mode C chain
      (``task-review → task-work × N → optional pull-request-review``).
    - FEAT-FORGE-008 ASSUM-013 — mode-aware planning refuses upstream
      Mode A stages even when a context manifest references them.
    - FEAT-FORGE-008 ASSUM-014 — Mode B does not dispatch to product-
      owner or architect specialists.
    - ADR-ARCH-026 — constitutional ``pull-request-review`` rule is
      mode-agnostic; ``CONSTITUTIONAL_STAGES`` is not duplicated per
      mode.
"""

from __future__ import annotations

from typing import Mapping

from forge.lifecycle.modes import BuildMode
from forge.pipeline.stage_taxonomy import StageClass

__all__ = [
    "MODE_A_CHAIN",
    "MODE_B_CHAIN",
    "MODE_C_CHAIN",
    "MODE_B_FORBIDDEN_STAGES",
    "MODE_C_FORBIDDEN_STAGES",
    "CHAIN_BY_MODE",
    "MODE_B_PREREQUISITES",
    "MODE_C_PREREQUISITES",
]


#: Mode A chain — the canonical eight-stage greenfield sequence.
#:
#: Re-exported here so :data:`CHAIN_BY_MODE` is a complete map covering
#: every :class:`BuildMode` value. Mode A semantics live in
#: :mod:`forge.pipeline.stage_taxonomy`; this tuple only mirrors the
#: dispatch order so callers can branch by mode without a separate
#: lookup.
MODE_A_CHAIN: tuple[StageClass, ...] = (
    StageClass.PRODUCT_OWNER,
    StageClass.ARCHITECT,
    StageClass.SYSTEM_ARCH,
    StageClass.SYSTEM_DESIGN,
    StageClass.FEATURE_SPEC,
    StageClass.FEATURE_PLAN,
    StageClass.AUTOBUILD,
    StageClass.PULL_REQUEST_REVIEW,
)


#: Mode B chain (FEAT-FORGE-008 ASSUM-001).
#:
#: Strict suffix of :data:`MODE_A_CHAIN` starting at ``feature-spec``.
#: The four pre-feature-spec stages are intentionally excluded — see
#: :data:`MODE_B_FORBIDDEN_STAGES`. Order matters: Wave 2's
#: ``ModeBPlanner`` iterates this tuple to dispatch.
MODE_B_CHAIN: tuple[StageClass, ...] = (
    StageClass.FEATURE_SPEC,
    StageClass.FEATURE_PLAN,
    StageClass.AUTOBUILD,
    StageClass.PULL_REQUEST_REVIEW,
)


#: Mode C chain (FEAT-FORGE-008 ASSUM-004).
#:
#: Cyclic chain ``task-review → task-work → pull-request-review``. The
#: tuple is length-3 by design:
#:
#: * ``TASK_REVIEW`` runs once per cycle. A clean follow-up
#:   ``/task-review`` (no fix tasks) terminates the cycle —
#:   ASSUM-007, ASSUM-010.
#: * ``TASK_WORK`` repeats once per fix task identified by the most
#:   recent ``/task-review``. The per-fix-task fan-out is enforced by
#:   the cycle controller in TASK-MBC8-004; this tuple records the
#:   stage class once.
#: * ``PULL_REQUEST_REVIEW`` is conditional on commits — see ASSUM-005
#:   (PR review when fixes change the branch) and ASSUM-017 (no PR
#:   when no commits were produced). The constitutional rule still
#:   applies if it fires (ASSUM-011).
MODE_C_CHAIN: tuple[StageClass, ...] = (
    StageClass.TASK_REVIEW,
    StageClass.TASK_WORK,
    StageClass.PULL_REQUEST_REVIEW,
)


#: Mode B forbidden stages (FEAT-FORGE-008 ASSUM-013, ASSUM-014).
#:
#: Mode B starts at ``/feature-spec``; the four pre-feature-spec Mode A
#: stages must never be dispatched in Mode B even if a context manifest
#: references them (ASSUM-013). ASSUM-014 follows directly: Mode B
#: never delegates to product-owner or architect specialists.
MODE_B_FORBIDDEN_STAGES: frozenset[StageClass] = frozenset(
    {
        StageClass.PRODUCT_OWNER,
        StageClass.ARCHITECT,
        StageClass.SYSTEM_ARCH,
        StageClass.SYSTEM_DESIGN,
    }
)


#: Mode C forbidden stages (FEAT-FORGE-008 ASSUM-004 boundary).
#:
#: Mode C operates on **existing** artefacts produced by a prior
#: Mode A or Mode B build, so every stage class that *creates* those
#: artefacts is forbidden:
#:
#: * The four Mode A pre-feature-spec stages (``product-owner``,
#:   ``architect``, ``/system-arch``, ``/system-design``).
#: * ``/feature-spec``, ``/feature-plan`` and ``autobuild`` — these
#:   build the artefacts Mode C is reviewing and fixing; re-running
#:   them in Mode C would short-circuit the review-fix cycle.
#:
#: ``PULL_REQUEST_REVIEW`` is **not** forbidden — Mode C may culminate
#: in a PR when commits are pushed (ASSUM-005, ASSUM-011).
MODE_C_FORBIDDEN_STAGES: frozenset[StageClass] = frozenset(
    {
        StageClass.PRODUCT_OWNER,
        StageClass.ARCHITECT,
        StageClass.SYSTEM_ARCH,
        StageClass.SYSTEM_DESIGN,
        StageClass.FEATURE_SPEC,
        StageClass.FEATURE_PLAN,
        StageClass.AUTOBUILD,
    }
)


#: Mapping from :class:`BuildMode` to the dispatch chain for that mode.
#:
#: Every member of :class:`BuildMode` is a key — exhaustiveness is
#: validated in the test suite (``test_chain_by_mode_covers_every_build_mode``).
#: The Mode A chain stays the existing eight-stage chain so no Mode A
#: caller needs to change to consume this map.
CHAIN_BY_MODE: Mapping[BuildMode, tuple[StageClass, ...]] = {
    BuildMode.MODE_A: MODE_A_CHAIN,
    BuildMode.MODE_B: MODE_B_CHAIN,
    BuildMode.MODE_C: MODE_C_CHAIN,
}


#: Mode B prerequisite map (subset of :data:`STAGE_PREREQUISITES`).
#:
#: Same shape as the Mode A prerequisite map but only over Mode B's
#: four stages. ``FEATURE_SPEC`` is the Mode B entry stage and is
#: deliberately omitted as a key (mirrors the Mode A convention where
#: ``PRODUCT_OWNER`` is omitted because it has no prerequisites).
#:
#: Rows:
#:
#:     1. feature-plan        ← feature-spec
#:     2. autobuild           ← feature-plan
#:     3. pull-request-review ← autobuild
MODE_B_PREREQUISITES: dict[StageClass, list[StageClass]] = {
    StageClass.FEATURE_PLAN: [StageClass.FEATURE_SPEC],
    StageClass.AUTOBUILD: [StageClass.FEATURE_PLAN],
    StageClass.PULL_REQUEST_REVIEW: [StageClass.AUTOBUILD],
}


#: Mode C prerequisite map.
#:
#: Same shape as :data:`MODE_B_PREREQUISITES` and the Mode A
#: prerequisite map, but for Mode C's three stage classes.
#: ``TASK_REVIEW`` is the Mode C entry stage and is deliberately
#: omitted as a key (it has no prerequisites — the build plan starts
#: with a review pass).
#:
#: Rows:
#:
#:     1. task-work           ← task-review
#:     2. pull-request-review ← task-work
#:
#: The per-fix-task fan-out of ``task-work`` is enforced by the cycle
#: controller in TASK-MBC8-004; this map records the prerequisite
#: relationship once at the stage-class level.
MODE_C_PREREQUISITES: dict[StageClass, list[StageClass]] = {
    StageClass.TASK_WORK: [StageClass.TASK_REVIEW],
    StageClass.PULL_REQUEST_REVIEW: [StageClass.TASK_WORK],
}
