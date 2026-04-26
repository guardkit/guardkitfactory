"""Forward-propagation contract map for FEAT-FORGE-007 Mode A.

This module defines the producer-to-consumer artefact handshake for each of
the seven non-product-owner stages. It is the declarative contract that
tells the ``ForwardContextBuilder`` (TASK-MAG7-006) which ``stage_log``
artefact_path values to thread into the next stage's ``--context`` flags.

It encodes the FEAT-FORGE-007 Group A scenarios — "The product-owner output
is supplied as input to the architect delegation" and "Architecture outputs
are supplied as context for system design" — by mirroring the seven
prerequisite rows from
:data:`forge.pipeline.stage_taxonomy.STAGE_PREREQUISITES` (TASK-MAG7-001).
By construction every approved-prerequisite produces an artefact that is
consumed by the immediate-downstream stage.

The seven contract rows, in dispatch order:

    1. ARCHITECT            ← product-owner approved charter (text)
    2. SYSTEM_ARCH          ← architect approved output (text)
    3. SYSTEM_DESIGN        ← system-arch artefact paths (path-list)
    4. FEATURE_SPEC         ← system-design feature catalogue entry (text)
    5. FEATURE_PLAN         ← feature-spec artefact path (path)
    6. AUTOBUILD            ← feature-plan artefact path (path)
    7. PULL_REQUEST_REVIEW  ← autobuild branch ref + commit summary (text)

This module imports only from :mod:`forge.pipeline.stage_taxonomy` and
nothing else from ``forge.pipeline.*``. It is side-effect free at import
time apart from a structural self-validation check that asserts every
contract key is reachable from ``PRODUCT_OWNER`` via the
``STAGE_PREREQUISITES`` chain — failing import loud if the contract drifts
out of sync with the taxonomy.

References:
    - TASK-MAG7-002 — this task brief.
    - TASK-MAG7-001 — ``StageClass`` enum and ``STAGE_PREREQUISITES`` map.
    - FEAT-FORGE-007 Group A scenarios (forward propagation).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from forge.pipeline.stage_taxonomy import STAGE_PREREQUISITES, StageClass

__all__ = [
    "ContextRecipe",
    "PROPAGATION_CONTRACT",
]


#: The three artefact kinds the ``ForwardContextBuilder`` knows how to
#: render onto a ``--context`` flag value:
#:
#: - ``text``       : inline text payload (charter, approved output, etc.).
#: - ``path``       : a single filesystem path to an artefact.
#: - ``path-list``  : a list of filesystem paths (e.g. system-arch fanout).
ArtefactKind = Literal["text", "path", "path-list"]


class ContextRecipe(BaseModel):
    """Producer-to-consumer artefact handshake for a single downstream stage.

    A :class:`ContextRecipe` describes how the
    :class:`~forge.pipeline.stage_taxonomy.StageClass` *consumer* (the
    dict key in :data:`PROPAGATION_CONTRACT`) should receive the artefact
    produced by ``producer_stage``: which artefact kind to expect and
    which CLI flag to thread it onto.

    Attributes:
        producer_stage: The upstream stage whose approved artefact is
            propagated into the consumer's context.
        artefact_kind: Shape of the artefact payload — ``"text"`` for an
            inline string, ``"path"`` for a single filesystem path, or
            ``"path-list"`` for a list of paths.
        context_flag: The CLI flag the ``ForwardContextBuilder`` should
            thread the artefact onto when invoking the consumer stage
            (e.g. ``"--context"``).
        description: Human-readable description of the producer artefact,
            e.g. ``"product-owner approved charter"``. Used in audit logs
            and error messages, not for routing.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    producer_stage: StageClass = Field(
        ..., description="Upstream stage whose artefact is propagated."
    )
    artefact_kind: ArtefactKind = Field(
        ..., description="Shape of the artefact payload."
    )
    context_flag: str = Field(
        ...,
        description="CLI flag the artefact is threaded onto (e.g. '--context').",
        min_length=1,
    )
    description: str = Field(
        ...,
        description="Human-readable description of the producer artefact.",
        min_length=1,
    )


#: Forward-propagation contract — one entry per non-product-owner stage.
#:
#: Each key is the *consumer* stage; the value's
#: :attr:`ContextRecipe.producer_stage` is the immediate prerequisite
#: from :data:`forge.pipeline.stage_taxonomy.STAGE_PREREQUISITES`. This
#: relationship is asserted at import time by
#: :func:`_validate_propagation_contract`.
#:
#: ``PRODUCT_OWNER`` is intentionally absent — it is the entry stage and
#: has no forward-propagated artefact ancestor.
PROPAGATION_CONTRACT: dict[StageClass, ContextRecipe] = {
    StageClass.ARCHITECT: ContextRecipe(
        producer_stage=StageClass.PRODUCT_OWNER,
        artefact_kind="text",
        context_flag="--context",
        description="product-owner approved charter",
    ),
    StageClass.SYSTEM_ARCH: ContextRecipe(
        producer_stage=StageClass.ARCHITECT,
        artefact_kind="text",
        context_flag="--context",
        description="architect approved output",
    ),
    StageClass.SYSTEM_DESIGN: ContextRecipe(
        producer_stage=StageClass.SYSTEM_ARCH,
        artefact_kind="path-list",
        context_flag="--context",
        description="system-arch artefact paths",
    ),
    StageClass.FEATURE_SPEC: ContextRecipe(
        producer_stage=StageClass.SYSTEM_DESIGN,
        artefact_kind="text",
        context_flag="--context",
        description="system-design feature catalogue entry",
    ),
    StageClass.FEATURE_PLAN: ContextRecipe(
        producer_stage=StageClass.FEATURE_SPEC,
        artefact_kind="path",
        context_flag="--context",
        description="feature-spec artefact path",
    ),
    StageClass.AUTOBUILD: ContextRecipe(
        producer_stage=StageClass.FEATURE_PLAN,
        artefact_kind="path",
        context_flag="--context",
        description="feature-plan artefact path",
    ),
    StageClass.PULL_REQUEST_REVIEW: ContextRecipe(
        producer_stage=StageClass.AUTOBUILD,
        artefact_kind="text",
        context_flag="--context",
        description="autobuild branch ref + commit summary",
    ),
}


def _validate_propagation_contract(
    contract: dict[StageClass, ContextRecipe],
    prerequisites: dict[StageClass, list[StageClass]],
) -> None:
    """Assert every contract key is reachable from ``PRODUCT_OWNER``.

    Two structural invariants are enforced at import:

    1. Every consumer stage in ``contract`` has its
       :attr:`ContextRecipe.producer_stage` listed as a prerequisite in
       :data:`forge.pipeline.stage_taxonomy.STAGE_PREREQUISITES`. This
       prevents the contract from drifting out of sync with the taxonomy.

    2. Every consumer stage is reachable from
       :attr:`StageClass.PRODUCT_OWNER` by walking the prerequisite chain
       backwards. This catches orphaned rows that would never receive a
       forward-propagated artefact at runtime.

    Args:
        contract: The propagation contract to validate (dependency-injected
            so tests can exercise the validator with synthetic maps).
        prerequisites: The stage prerequisite map (dependency-injected
            for the same reason).

    Raises:
        ValueError: If any contract row violates the invariants above.
    """
    for consumer, recipe in contract.items():
        prereqs = prerequisites.get(consumer)
        if prereqs is None:
            raise ValueError(
                f"PROPAGATION_CONTRACT key {consumer!r} has no entry in "
                "STAGE_PREREQUISITES — contract has drifted from the "
                "stage taxonomy."
            )
        if recipe.producer_stage not in prereqs:
            raise ValueError(
                f"PROPAGATION_CONTRACT[{consumer!r}].producer_stage = "
                f"{recipe.producer_stage!r} is not listed in "
                f"STAGE_PREREQUISITES[{consumer!r}] = {prereqs!r}."
            )

    # Reachability: walk every consumer back to PRODUCT_OWNER via prereqs.
    for consumer in contract:
        seen: set[StageClass] = set()
        cursor: StageClass = consumer
        while cursor != StageClass.PRODUCT_OWNER:
            if cursor in seen:
                raise ValueError(
                    f"Cycle detected while walking prerequisites from "
                    f"{consumer!r}: revisited {cursor!r}."
                )
            seen.add(cursor)
            upstream = prerequisites.get(cursor)
            if not upstream:
                raise ValueError(
                    f"PROPAGATION_CONTRACT key {consumer!r} is not "
                    f"reachable from PRODUCT_OWNER — chain terminated "
                    f"at {cursor!r} with no prerequisites."
                )
            # Mode A's prerequisite chain is single-parent per stage; pick
            # the first entry. The validator does not need to fan out.
            cursor = upstream[0]


# Self-validation at import — fail loud if the contract drifts.
_validate_propagation_contract(PROPAGATION_CONTRACT, STAGE_PREREQUISITES)
