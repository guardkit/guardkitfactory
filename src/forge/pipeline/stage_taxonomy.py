"""Canonical Mode A stage taxonomy for FEAT-FORGE-007.

This module is the single source of truth for the eight Mode A stage classes
and the prerequisite map that encodes the seven prerequisite rows from the
FEAT-FORGE-007 Group B Scenario Outline ("A downstream stage is not
dispatched before its prerequisite has reached the approved state").

Per FEAT-FORGE-007 ASSUM-001 (Mode A greenfield assumptions), the eight
stage classes that drive Mode A are, in dispatch order:

    product-owner → architect → /system-arch → /system-design →
    /feature-spec → /feature-plan → autobuild → pull-request review

The final ``PULL_REQUEST_REVIEW`` stage is constitutional per
ADR-ARCH-026 (constitutional-rules-belt-and-braces): every Mode A run
must terminate at a human-reviewable pull request, regardless of how
many features are in flight.

This module is intentionally free of imports from any other
``forge.pipeline`` submodule so it can be imported from every downstream
guard, dispatcher, and context builder in Waves 2–4 without forming an
import cycle (see TASK-MAG7-001 implementation notes).

References:
    - FEAT-FORGE-007 ASSUM-001 — eight-stage taxonomy assumption.
    - ADR-ARCH-026 — constitutional rules (belt-and-braces); the
      ``PULL_REQUEST_REVIEW`` stage is the constitutional gate that
      terminates every Mode A run.
    - ``features/mode-a-greenfield-end-to-end/``
      ``mode-a-greenfield-end-to-end.feature`` — Background and Group B
      Scenario Outline rows that this taxonomy mirrors verbatim.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "StageClass",
    "STAGE_PREREQUISITES",
    "CONSTITUTIONAL_STAGES",
    "PER_FEATURE_STAGES",
]


class StageClass(StrEnum):
    """The eight Mode A stage classes, in dispatch order.

    Member order matches the FEAT-FORGE-007 ASSUM-001 dispatch order
    and the ``mode-a-greenfield-end-to-end.feature`` Background. Do
    **not** reorder — downstream guards rely on iteration order to
    reason about wave membership and pipeline progress.

    String values mirror the dash-separated names that appear in the
    Group B Scenario Outline ("architect ← product-owner",
    "system-arch ← architect", …) so callers can round-trip between the
    enum and the feature file without a translation table.
    """

    PRODUCT_OWNER = "product-owner"
    ARCHITECT = "architect"
    SYSTEM_ARCH = "system-arch"
    SYSTEM_DESIGN = "system-design"
    FEATURE_SPEC = "feature-spec"
    FEATURE_PLAN = "feature-plan"
    AUTOBUILD = "autobuild"
    PULL_REQUEST_REVIEW = "pull-request-review"


#: Stage prerequisite map.
#:
#: Encodes the seven prerequisite rows from the FEAT-FORGE-007 Group B
#: Scenario Outline. Each key is a stage; the value lists the stages
#: that must have reached the approved state before the key stage may
#: be dispatched.
#:
#: Rows (verbatim from Group B Scenario Outline):
#:
#:     1. architect           ← product-owner
#:     2. system-arch         ← architect
#:     3. system-design       ← system-arch
#:     4. feature-spec        ← system-design
#:     5. feature-plan        ← feature-spec        (per feature)
#:     6. autobuild           ← feature-plan        (per feature)
#:     7. pull-request-review ← autobuild           (for every feature)
#:
#: ``PRODUCT_OWNER`` is the entry stage and has no prerequisites; it is
#: deliberately omitted from this map so callers can use ``in
#: STAGE_PREREQUISITES`` as a "has prerequisites?" predicate.
STAGE_PREREQUISITES: dict[StageClass, list[StageClass]] = {
    StageClass.ARCHITECT: [StageClass.PRODUCT_OWNER],
    StageClass.SYSTEM_ARCH: [StageClass.ARCHITECT],
    StageClass.SYSTEM_DESIGN: [StageClass.SYSTEM_ARCH],
    StageClass.FEATURE_SPEC: [StageClass.SYSTEM_DESIGN],
    StageClass.FEATURE_PLAN: [StageClass.FEATURE_SPEC],
    StageClass.AUTOBUILD: [StageClass.FEATURE_PLAN],
    StageClass.PULL_REQUEST_REVIEW: [StageClass.AUTOBUILD],
}


#: Constitutional stages — gates that every Mode A run must pass.
#:
#: Per ADR-ARCH-026, the pull-request review stage is the
#: constitutional terminator: a Mode A run is not "complete" until a
#: human-reviewable pull request has been opened for every feature.
#: ``constitutional`` here means the stage is a non-skippable rule of
#: the pipeline, not that it is governed by a separate constitution
#: document.
CONSTITUTIONAL_STAGES: frozenset[StageClass] = frozenset(
    {StageClass.PULL_REQUEST_REVIEW}
)


#: Per-feature stages — stages that fan out across all in-flight features.
#:
#: The first four stages (product-owner through system-design) run once
#: per Mode A pipeline; the remaining four fan out across every feature
#: in scope. ``PULL_REQUEST_REVIEW`` is per-feature even though it is
#: also constitutional — Group B row 7 ("pull-request ← autobuild for
#: every feature") makes this explicit.
PER_FEATURE_STAGES: frozenset[StageClass] = frozenset(
    {
        StageClass.FEATURE_SPEC,
        StageClass.FEATURE_PLAN,
        StageClass.AUTOBUILD,
        StageClass.PULL_REQUEST_REVIEW,
    }
)
