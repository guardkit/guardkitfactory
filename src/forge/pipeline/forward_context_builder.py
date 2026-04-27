"""Forward-propagation context builder for FEAT-FORGE-007 Mode A (TASK-MAG7-006).

This module defines :class:`ForwardContextBuilder`, the *only* place in the
Mode A pipeline that crosses the boundary from "the build's recorded
history" (``stage_log``) to "what gets passed to a downstream subprocess"
(``--context`` flag values on the next stage's dispatch).

It implements forward propagation per the
:data:`forge.pipeline.forward_propagation.PROPAGATION_CONTRACT` defined by
TASK-MAG7-002 and mitigates Risk R-5 ("forward-propagation context builder
leaks unapproved or stale artefacts") by centralising two read-side filters
in one auditable place:

1. *Approved-only*: a downstream stage receives context only from
   ``stage_log`` rows whose ``gate_decision == 'approved'``. In-progress
   and flagged-for-review rows are invisible to the builder by Protocol
   contract — :meth:`StageLogReader.get_approved_stage_entry` returns
   ``None`` for any row that has not reached the terminal-approved state.
2. *Worktree allowlisted*: every artefact path is checked against the
   build's :class:`WorktreeAllowlist` before it is threaded into a
   ``--context`` value. Paths that fall outside the worktree are filtered
   out individually and a structured warning is logged. This is the
   defence-in-depth twin of the FEAT-FORGE-005 allowlist that the build
   subprocess applies on its own side.

Per-feature scoping (FEAT-FORGE-007 ASSUM-001) is handled by passing
``feature_id`` through to the reader for any consumer or producer stage
in :data:`~forge.pipeline.stage_taxonomy.PER_FEATURE_STAGES`. A consumer
that is per-feature but called without a ``feature_id`` is treated as a
misuse and yields an empty context list — the same "refuse rather than
dispatch cross-feature" stance taken by
:class:`forge.pipeline.stage_ordering_guard.StageOrderingGuard`
(TASK-MAG7-003).

Architecture notes
------------------

The builder is I/O-thin: it owns no state across calls and depends only
on the two reader Protocols (:class:`StageLogReader`,
:class:`WorktreeAllowlist`) declared in this module. Production wires the
FEAT-FORGE-001 SQLite adapter for the stage_log reader and the
FEAT-FORGE-005 allowlist for the worktree gate; tests inject in-memory
fakes — the same shape TASK-MAG7-003 and TASK-MAG7-005 use.

References:
    - TASK-MAG7-006 — this task brief.
    - TASK-MAG7-001 — :mod:`forge.pipeline.stage_taxonomy`
      (``StageClass``, ``PER_FEATURE_STAGES``).
    - TASK-MAG7-002 — :mod:`forge.pipeline.forward_propagation`
      (``PROPAGATION_CONTRACT``, ``ContextRecipe``).
    - FEAT-FORGE-007 Group A scenarios — forward propagation of
      product-owner / architect outputs to the next stage's dispatch.
    - FEAT-FORGE-005 — worktree allowlist (production side).
    - FEAT-FORGE-001 — SQLite ``stage_log`` adapter (production reader).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

from forge.pipeline.forward_propagation import PROPAGATION_CONTRACT, ContextRecipe
from forge.pipeline.stage_taxonomy import PER_FEATURE_STAGES, StageClass

__all__ = [
    "ApprovedStageEntry",
    "ContextEntry",
    "ForwardContextBuilder",
    "StageLogReader",
    "WorktreeAllowlist",
]

logger = logging.getLogger(__name__)


#: The two artefact shapes a single :class:`ContextEntry` can carry.
#:
#: A producer recipe of ``"path-list"`` is expanded into one
#: :class:`ContextEntry` per path, each tagged ``"path"``; the only kinds
#: that escape :meth:`ForwardContextBuilder.build_for` are therefore
#: ``"text"`` and ``"path"``.
ContextEntryKind = Literal["text", "path"]


@dataclass(frozen=True, slots=True)
class ApprovedStageEntry:
    """The minimal stage_log row shape the builder consumes.

    Production's FEAT-FORGE-001 ``stage_log`` row carries a great deal
    more (timestamps, coach scores, gate metadata, …); this dataclass
    pins the *only* fields the builder is allowed to read so the
    :class:`StageLogReader` Protocol stays narrow.

    Attributes:
        gate_decision: Always ``"approved"`` — by Protocol contract the
            reader never returns rows in any other gate state. The field
            is preserved on the dataclass so downstream consumers (and
            tests) can introspect it without re-querying SQLite.
        artefact_paths: Filesystem paths the producer stage emitted.
            Empty tuple for ``"text"``-kind producers. Single-element
            tuple for ``"path"``. Multiple elements for ``"path-list"``.
        artefact_text: Inline text payload for ``"text"``-kind
            producers (charters, approved-output blobs, etc.). ``None``
            for path-shaped producers.
    """

    gate_decision: str
    artefact_paths: tuple[str, ...] = ()
    artefact_text: str | None = None


@dataclass(frozen=True, slots=True)
class ContextEntry:
    """A single ``--context`` flag invocation on the downstream dispatch.

    The downstream dispatcher (specialist dispatch or GuardKit
    subprocess) receives a list of these and turns each one into one
    ``--<flag> <value>`` pair on its child-process argv. Inline-text
    payloads (``kind="text"``) are passed verbatim; path payloads
    (``kind="path"``) are passed as filesystem paths the child process
    will open.

    Attributes:
        flag: CLI flag name, e.g. ``"--context"``. Sourced from
            :attr:`ContextRecipe.context_flag`.
        value: The flag value — either an inline text payload or a
            filesystem path.
        kind: Discriminator so the dispatcher knows whether ``value`` is
            inline text or a path it should resolve.
    """

    flag: str
    value: str
    kind: ContextEntryKind


@runtime_checkable
class StageLogReader(Protocol):
    """Read-side Protocol over the FEAT-FORGE-001 ``stage_log`` table.

    The builder needs exactly one query: "give me the *approved* row for
    ``(build_id, stage, feature_id)``, or ``None`` if no such row
    exists". By Protocol contract the reader filters
    ``gate_decision == 'approved'`` *internally* — the builder cannot
    accidentally widen the filter because there is no place to put a
    ``include_unapproved`` flag.

    Production wires the FEAT-FORGE-001 SQLite adapter; tests use an
    in-memory fake.
    """

    def get_approved_stage_entry(
        self,
        build_id: str,
        stage: StageClass,
        feature_id: str | None = None,
    ) -> ApprovedStageEntry | None:  # pragma: no cover - protocol stub
        """Return the approved stage_log entry, or ``None``.

        Args:
            build_id: Build the row is scoped to.
            stage: Stage class whose approved row is requested.
            feature_id: ``None`` for non-per-feature stages; the
                feature identifier for stages in
                :data:`~forge.pipeline.stage_taxonomy.PER_FEATURE_STAGES`.

        Returns:
            The :class:`ApprovedStageEntry` if a row exists with
            ``gate_decision='approved'`` for the given scope; ``None``
            otherwise (no row yet, or row exists in any non-approved
            gate state — both look the same to callers, which is the
            point).
        """
        ...


@runtime_checkable
class WorktreeAllowlist(Protocol):
    """Defence-in-depth filesystem allowlist for the build's worktree.

    Mirrors the FEAT-FORGE-005 production allowlist surface. The builder
    invokes :meth:`is_allowed` once per artefact path before threading it
    into a ``--context`` value; paths that fail the check are filtered
    out individually with a structured warning rather than raising. This
    matches the AC-004 / AC-008 contract: "Refuses to return any entry
    whose underlying artefact path falls outside the build's worktree
    allowlist".
    """

    def is_allowed(
        self, build_id: str, path: str
    ) -> bool:  # pragma: no cover - protocol stub
        """Return ``True`` iff ``path`` lies inside ``build_id``'s worktree.

        Args:
            build_id: Build whose worktree allowlist to consult.
            path: Filesystem path to gate.

        Returns:
            ``True`` iff the path is safe to thread onto a downstream
            ``--context`` flag, ``False`` otherwise (path escapes the
            worktree, or the build has no recorded worktree root).
        """
        ...


class ForwardContextBuilder:
    """Builds the ``--context`` entries for the next stage's dispatch.

    The builder is the single read-side seam between
    :data:`~forge.pipeline.forward_propagation.PROPAGATION_CONTRACT` (the
    declarative producer-to-consumer wiring) and the downstream stage's
    dispatcher (the executable subprocess invocation). All approval and
    allowlist filtering happens here, so adding a new stage is purely a
    matter of registering a :class:`ContextRecipe` row — no new
    enforcement code is required.

    Args:
        stage_log_reader: Reader over the ``stage_log`` table; only ever
            returns rows with ``gate_decision='approved'``.
        worktree_allowlist: Filesystem-path gate over the build's
            worktree. Path artefacts are filtered through it; text
            artefacts bypass it (they have no filesystem path to gate).

    Example:
        >>> builder = ForwardContextBuilder(reader, allowlist)
        >>> builder.build_for(
        ...     stage=StageClass.AUTOBUILD,
        ...     build_id="build-FEAT-X-20260426",
        ...     feature_id="FEAT-1",
        ... )
        [ContextEntry(flag='--context', value='/work/.../plan.md', kind='path')]
    """

    def __init__(
        self,
        stage_log_reader: StageLogReader,
        worktree_allowlist: WorktreeAllowlist,
    ) -> None:
        self._reader = stage_log_reader
        self._allowlist = worktree_allowlist

    def build_for(
        self,
        stage: StageClass,
        build_id: str,
        feature_id: str | None,
    ) -> list[ContextEntry]:
        """Return the ``--context`` entries to thread into ``stage``'s dispatch.

        Resolution order:

        1. Look up :data:`PROPAGATION_CONTRACT[stage]` to find the
           producer stage and the artefact recipe. Stages with no
           recipe entry (only ``PRODUCT_OWNER`` today, the entry stage)
           return an empty list — there is no upstream to propagate.
        2. Refuse early for per-feature consumers called without a
           ``feature_id`` — this is the same safe-default stance
           :class:`StageOrderingGuard` takes for misuse.
        3. Ask the :class:`StageLogReader` for the producer's approved
           row. ``None`` (no approved row yet) → empty list. This is
           how AC-007 ("in-progress prior stage → empty context") is
           enforced: the reader will not surface a non-approved row.
        4. Convert the row into one or more :class:`ContextEntry`
           values according to the recipe's ``artefact_kind``:
           ``"text"`` → one entry from ``artefact_text``;
           ``"path"`` → one entry from ``artefact_paths[0]``;
           ``"path-list"`` → one entry per element of ``artefact_paths``.
        5. For path-shaped entries, run each path through
           :meth:`WorktreeAllowlist.is_allowed`; rejects are dropped
           with a structured ``WARNING`` log line that names the path
           and the build (AC-004 / AC-008).

        Args:
            stage: Consumer stage whose dispatch is about to fire.
            build_id: Build identifier
                (``build-{feature_id}-{YYYYMMDDHHMMSS}``).
            feature_id: Feature identifier for per-feature consumers;
                ``None`` for non-per-feature consumers. Misuse
                (per-feature consumer + ``feature_id=None``) yields
                an empty list.

        Returns:
            Ordered list of :class:`ContextEntry` values. Order matches
            the producer's ``artefact_paths`` for path-list recipes so
            downstream tools can rely on stable argv ordering.
        """
        recipe = PROPAGATION_CONTRACT.get(stage)
        if recipe is None:
            # Entry stage (PRODUCT_OWNER) or any future stage without
            # a propagation row — nothing to thread.
            logger.debug(
                "forward_context_builder: no PROPAGATION_CONTRACT entry for "
                "stage=%s; returning empty context",
                stage,
            )
            return []

        # Per-feature consumer + missing feature_id is a misuse.
        if stage in PER_FEATURE_STAGES and feature_id is None:
            logger.warning(
                "forward_context_builder: per-feature stage=%s called without "
                "feature_id (build_id=%s); refusing to thread cross-feature "
                "context",
                stage,
                build_id,
            )
            return []

        producer_feature_id = (
            feature_id if recipe.producer_stage in PER_FEATURE_STAGES else None
        )
        approved = self._reader.get_approved_stage_entry(
            build_id=build_id,
            stage=recipe.producer_stage,
            feature_id=producer_feature_id,
        )
        if approved is None:
            # Producer not yet approved — AC-007 says empty context.
            logger.debug(
                "forward_context_builder: producer=%s not approved for "
                "build_id=%s feature_id=%s; returning empty context",
                recipe.producer_stage,
                build_id,
                producer_feature_id,
            )
            return []

        return self._materialise_entries(
            recipe=recipe,
            approved=approved,
            build_id=build_id,
        )

    # ------------------------------------------------------------------
    # Internal: shape the approved row into ContextEntry values
    # ------------------------------------------------------------------

    def _materialise_entries(
        self,
        recipe: ContextRecipe,
        approved: ApprovedStageEntry,
        build_id: str,
    ) -> list[ContextEntry]:
        """Convert an approved row into ``ContextEntry`` values per the recipe.

        Splits along the recipe's ``artefact_kind``:

        - ``text``: emits one entry from ``approved.artefact_text``.
          Allowlist is bypassed — text payloads have no filesystem path
          to gate. An empty / ``None`` text payload yields no entry
          (defensive: a producer that passes the gate but emits no text
          is a bug upstream, not something we should crash on).
        - ``path``: emits one entry from ``approved.artefact_paths[0]``,
          gated by the allowlist.
        - ``path-list``: emits one entry per allowed path; every path is
          checked individually.

        Rejects are filtered with a structured warning that names the
        path and the build so operators can track allowlist misses
        without spelunking through SQLite.
        """
        if recipe.artefact_kind == "text":
            return self._build_text_entries(recipe, approved)
        # Both "path" and "path-list" go through the same allowlist
        # filter — the only difference is how many paths we read.
        return self._build_path_entries(recipe, approved, build_id)

    def _build_text_entries(
        self,
        recipe: ContextRecipe,
        approved: ApprovedStageEntry,
    ) -> list[ContextEntry]:
        """Emit a single text entry from ``approved.artefact_text``."""
        text = approved.artefact_text
        if not text:
            logger.warning(
                "forward_context_builder: text-kind recipe (%s) produced "
                "no artefact_text — upstream stage approved with empty "
                "payload; returning empty context",
                recipe.description,
            )
            return []
        return [
            ContextEntry(
                flag=recipe.context_flag,
                value=text,
                kind="text",
            )
        ]

    def _build_path_entries(
        self,
        recipe: ContextRecipe,
        approved: ApprovedStageEntry,
        build_id: str,
    ) -> list[ContextEntry]:
        """Emit one path entry per allow-listed path in ``approved``."""
        if recipe.artefact_kind == "path":
            # Single-path recipe — take only the first artefact path.
            # An approved row with no paths is treated the same way as
            # a text-kind recipe with no text: defensive empty list.
            if not approved.artefact_paths:
                logger.warning(
                    "forward_context_builder: path-kind recipe (%s) "
                    "produced no artefact_paths; returning empty context",
                    recipe.description,
                )
                return []
            paths = approved.artefact_paths[:1]
        else:
            paths = approved.artefact_paths

        entries: list[ContextEntry] = []
        for path in paths:
            if not self._allowlist.is_allowed(build_id, path):
                # Structured WARNING — operators monitor this log line
                # to detect allowlist drift. Include both the path and
                # the build_id so the message is self-contained.
                logger.warning(
                    "forward_context_builder: artefact path outside "
                    "worktree allowlist; build_id=%s path=%s recipe=%s — "
                    "filtered from forward context",
                    build_id,
                    path,
                    recipe.description,
                )
                continue
            entries.append(
                ContextEntry(
                    flag=recipe.context_flag,
                    value=path,
                    kind="path",
                )
            )
        return entries


# ---------------------------------------------------------------------------
# Module-level dataclass field default factories
# ---------------------------------------------------------------------------
# (No additional state beyond the ApprovedStageEntry/ContextEntry frozen
# dataclasses defined above. Listed here for grep-ability — if a future
# refactor adds module-level mutable state, it should appear in this
# section so the audit-trail of "what does this module own?" stays
# centralised.)
_ = field  # silence unused-import; kept for future field(default_factory=...) use
