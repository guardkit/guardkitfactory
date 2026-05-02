"""Production factory for :class:`ForwardContextBuilder` (TASK-FW10-003).

This module is one of the four ``dispatch_autobuild_async`` collaborator
factories that Wave 2 of FEAT-FORGE-010 wires up. Each Wave 2 factory
lives in its own ``_serve_deps_*.py`` module so the five Wave 2 tasks
can land independently without cross-merge conflicts: composition into
the daemon's deps graph is owned by TASK-FW10-007 (the future
``_serve_deps.py``).

What this factory does
----------------------

:func:`build_forward_context_builder` accepts the two production
collaborators :class:`ForwardContextBuilder` requires:

1. ``sqlite_pool`` — a duck-typed object that satisfies the
   :class:`forge.pipeline.forward_context_builder.StageLogReader`
   Protocol (``get_approved_stage_entry`` and
   ``get_all_approved_stage_entries``). Production wires the
   FEAT-FORGE-001 SQLite stage_log adapter; tests inject an in-memory
   fake. The factory does not validate the duck type at runtime — the
   :class:`StageLogReader` Protocol is structural and the builder will
   fail loudly with ``AttributeError`` on the first call if the contract
   is unmet.

2. ``forge_config`` — the validated :class:`forge.config.models.ForgeConfig`
   loaded by ``ServeConfig.from_env()``. The factory reads
   ``forge_config.permissions.filesystem.allowlist`` (the absolute path
   roots the operator declared in ``forge.yaml``) and wraps them into a
   :class:`WorktreeAllowlist`-conforming adapter. The adapter is the
   defence-in-depth twin of the FEAT-FORGE-005 per-build allowlist —
   even if a downstream caller hands the builder a ``build_id`` whose
   per-build allowlist hasn't been wired yet, the project-wide
   allowlist still bounds every artefact path the builder threads onto
   a downstream ``--context`` flag.

The returned :class:`ForwardContextBuilder` is the production object
that ``dispatch_autobuild_async`` (and any other consumer) calls
:meth:`ForwardContextBuilder.build_for` on.

What this factory does NOT do
-----------------------------

* It does not import from ``forge.cli._serve_deps`` — composition into
  the daemon's deps graph is TASK-FW10-007's job. Keeping this factory
  decoupled from the deps composition module is what lets the five
  Wave 2 tasks merge in any order.
* It does not own the rejection-to-envelope translation. When the
  builder filters every artefact path (the "disallowed worktree path"
  rejection branch in the ACs), the caller receives an empty / partial
  forward context. Translating that into a ``build-failed`` JetStream
  envelope is delegated to TASK-FW10-009.
* It does not validate ``sqlite_pool``. The :class:`StageLogReader`
  Protocol is ``runtime_checkable`` but ``isinstance`` against a
  Protocol is best-effort (it only checks attribute names) and we
  prefer the duck-typed contract — production wires a SQLite adapter,
  tests wire an in-memory fake; both satisfy the Protocol without ever
  declaring inheritance.

References:
    - TASK-FW10-003 — this factory's brief.
    - TASK-FW10-007 — composition into the daemon's deps graph.
    - TASK-FW10-009 — build-failed envelope translation.
    - :mod:`forge.pipeline.forward_context_builder` — the class this
      factory constructs and its two Protocol seams.
    - :class:`forge.config.models.ForgeConfig` — the source of truth
      for the filesystem allowlist this factory consumes.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from forge.config.models import ForgeConfig
from forge.pipeline.forward_context_builder import (
    ForwardContextBuilder,
    StageLogReader,
    WorktreeAllowlist,
)

__all__ = [
    "ForgeConfigWorktreeAllowlist",
    "build_forward_context_builder",
]

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ForgeConfigWorktreeAllowlist:
    """:class:`WorktreeAllowlist` adapter over ``ForgeConfig.permissions.filesystem``.

    The adapter exposes the :class:`WorktreeAllowlist` Protocol surface
    expected by :class:`ForwardContextBuilder` (a single
    :meth:`is_allowed` boolean predicate). It is the defence-in-depth
    twin of the per-build FEAT-FORGE-005 allowlist: even before
    FEAT-FORGE-005 wires a per-build allowlist for ``build_id``, this
    adapter ensures every artefact path threaded onto a forward
    ``--context`` flag lies inside one of the operator-declared
    filesystem roots.

    Path containment is computed via the resolved-path / ``commonpath``
    idiom rather than by string ``startswith``: a sibling whose name
    shares a textual prefix with an allowlist root (``/work/build-1``
    vs ``/work/build-12345``) must NOT be allowed, and a textual
    ``startswith`` check would let it through. We resolve both sides
    against the filesystem (without requiring the path to exist —
    :func:`os.path.normpath` strips ``..``) and then ask
    :func:`os.path.commonpath` whether the candidate is contained.

    Attributes:
        allowed_roots: Tuple of normalised absolute path strings the
            adapter compares against. Empty tuple is a legal (and
            deliberately deny-all) configuration — useful for
            integration tests that want to exercise the rejection
            branch without changing the rest of the config.

    Notes:
        ``build_id`` is part of the Protocol signature because
        FEAT-FORGE-005's per-build allowlist needs it. This adapter
        ignores it: the FEAT-FORGE-010 wiring relies on the operator's
        project-wide ``forge.yaml`` allowlist, not a per-build one.
        The argument is preserved on the surface so a future swap to a
        per-build implementation is a drop-in replacement.
    """

    allowed_roots: tuple[str, ...]

    def is_allowed(self, build_id: str, path: str) -> bool:
        """Return ``True`` iff ``path`` is contained in one of :attr:`allowed_roots`.

        The check is symmetric: ``path == root`` is allowed, and any
        descendant ``root/sub/...`` is allowed. A path that escapes the
        root via ``..`` is normalised first and then tested again, so
        an attacker who supplies ``"/work/build-1/../../etc/passwd"``
        sees the rejection.

        ``build_id`` is currently unused (see class docstring). It is
        retained on the signature because the
        :class:`forge.pipeline.forward_context_builder.WorktreeAllowlist`
        Protocol requires it.
        """
        del build_id  # honoured by the per-build allowlist; project-wide here.

        if not path:
            # Defensive — an empty path string can never be inside a
            # non-empty root and admitting it would let a bug upstream
            # silently thread a meaningless ``--context`` value.
            return False

        try:
            candidate = os.path.normpath(os.path.abspath(path))
        except (TypeError, ValueError):
            # ``os.path.abspath`` raises ``TypeError`` for non-string
            # inputs and ``ValueError`` for embedded NULs. Either is a
            # caller bug; refuse rather than crash the builder.
            logger.warning(
                "forge.cli._serve_deps_forward_context: rejecting "
                "non-normalisable path %r",
                path,
            )
            return False

        for root in self.allowed_roots:
            try:
                common = os.path.commonpath([candidate, root])
            except ValueError:
                # Different drives on Windows, or one path is relative
                # while the other is absolute. Either way, no overlap.
                continue
            if common == root:
                return True
        return False


def _normalise_root(root: Path | str) -> str:
    """Normalise a ``forge.yaml`` allowlist entry to an absolute path string."""
    return os.path.normpath(os.path.abspath(str(root)))


def build_forward_context_builder(
    sqlite_pool: Any,
    forge_config: ForgeConfig,
) -> ForwardContextBuilder:
    """Build the production :class:`ForwardContextBuilder` for ``forge serve``.

    Wires:

    * ``sqlite_pool`` — duck-typed :class:`StageLogReader` over the
      FEAT-FORGE-001 ``stage_log`` table. Production passes the SQLite
      reader pool; tests pass an in-memory fake.
    * ``forge_config.permissions.filesystem.allowlist`` — the absolute
      path roots the operator declared in ``forge.yaml``. The factory
      wraps these in :class:`ForgeConfigWorktreeAllowlist` so the
      builder filters every artefact path through the allowlist before
      threading it onto a ``--context`` flag.

    The returned builder is fully wired and ready to call
    :meth:`ForwardContextBuilder.build_for`. The factory is
    idempotent (it allocates a fresh adapter on every call), so two
    builds in the same process can each hold their own builder
    instance without sharing state.

    Args:
        sqlite_pool: Object satisfying the
            :class:`StageLogReader` Protocol. The Protocol is
            ``runtime_checkable`` but the factory does not enforce
            ``isinstance`` — the builder is duck-typed, and the first
            call to :meth:`ForwardContextBuilder.build_for` will fail
            loudly if the contract is unmet.
        forge_config: Validated root config. The factory reads
            ``forge_config.permissions.filesystem.allowlist`` and
            normalises each entry to an absolute path string.

    Returns:
        A :class:`ForwardContextBuilder` whose
        :class:`StageLogReader` and :class:`WorktreeAllowlist`
        collaborators are bound to ``sqlite_pool`` and
        ``forge_config`` respectively.

    Raises:
        AttributeError: If ``forge_config`` lacks the expected
            ``permissions.filesystem.allowlist`` chain. The Pydantic
            schema in :mod:`forge.config.models` enforces this at
            config-load time, so reaching this branch in production
            indicates a malformed test fixture rather than an operator
            misconfiguration.
    """
    # Cast to StageLogReader for static type-checkers. The cast is a
    # documentation marker — the real contract is duck-typed.
    stage_log_reader: StageLogReader = sqlite_pool

    allowed_roots = tuple(
        _normalise_root(entry)
        for entry in forge_config.permissions.filesystem.allowlist
    )
    worktree_allowlist: WorktreeAllowlist = ForgeConfigWorktreeAllowlist(
        allowed_roots=allowed_roots,
    )

    logger.debug(
        "forge.cli._serve_deps_forward_context: bound ForwardContextBuilder "
        "with %d filesystem-allowlist root(s)",
        len(allowed_roots),
    )

    return ForwardContextBuilder(
        stage_log_reader=stage_log_reader,
        worktree_allowlist=worktree_allowlist,
    )
