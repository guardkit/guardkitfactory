"""FilesystemPermission deny-rules for the AutoBuild LangGraph harness.

Why these rules (AC-003)
========================

The parent review (TASK-REV-HMIG §3.4) maps every path AutoBuild's Player
should *not* be able to mutate to a specific concern. The rules below pin
each pattern to that concern:

* ``/**/.git/**`` — repository integrity. The Player operates inside a
  worktree; mutating ``.git`` (refs, objects, hooks) breaks the
  worktree-as-isolation invariant that lets the orchestrator manage
  branches and rebases on the Player's behalf.

* ``/**/.guardkit/state_transitions.json`` — orchestrator single
  source-of-truth for kanban state transitions. The Player must never
  observe (or write) a transition the orchestrator didn't perform; the
  path-string-mismatch failure mode documented in parent review §3.4 is
  exactly this kind of dual-writer hazard.

* ``/**/.guardkit/autobuild/*/coach_*.json`` — Coach trust boundary. Coach
  verdicts are produced by the Coach role; if the Player can overwrite
  them, the adversarial-cooperation contract collapses. The orchestrator
  writes these on Coach's behalf.

* ``/**/tasks/**`` — kanban file integrity. Task state transitions are an
  orchestrator concern (see also the state-transitions rule above). The
  Player should be able to *read* task files (its prompt may reference
  them) but never modify them directly.

Why ``operations=["write"]`` covers edits too
---------------------------------------------

``FilesystemPermission`` collapses ``write_file`` and ``edit_file`` into the
single ``"write"`` operation (see ``deepagents.middleware.permissions``).
One rule with ``operations=["write"]`` is therefore enough to cover both
the "create a new file" and "modify an existing file" tools. This is the
DRY choice — four separate rules per operation would be redundant.

Why ``/**/`` prefix on every pattern
------------------------------------

``FilesystemPermission`` requires absolute paths starting with ``/`` (see
``deepagents.middleware.permissions.FilesystemPermission.__post_init__``).
The deepagents permission middleware canonicalizes the path it checks
against — so for a worktree at ``/tmp/wt-xyz`` the path the matcher sees
is the absolute ``/tmp/wt-xyz/.git/HEAD``. The ``/**/`` GLOBSTAR prefix
keeps the rules worktree-location-agnostic: they match the protected
subtrees no matter where the worktree is rooted on disk.

Reads are intentionally not denied
----------------------------------

The rules only set ``operations=["write"]``. Reads are still allowed
everywhere, because:

1. The Player legitimately needs to read task files, ``.guardkit/`` state,
   and even ``.git/`` log output during a turn.
2. The threat model (parent review §14.6/14.7) is *integrity*, not
   confidentiality — the operator already trusts the agent with the
   contents of the worktree.

If a future task requires read-side denial as well (e.g. masking secrets
under ``.git/config``), add it then rather than over-broadening now.
"""

from __future__ import annotations

from deepagents import FilesystemPermission

__all__ = ["build_autobuild_permissions"]


# Each pattern is keyed to a single concern documented in the module
# docstring above. Keep the list and the docstring in sync if you add
# or remove a pattern.
_AUTOBUILD_DENY_WRITE_PATTERNS: list[str] = [
    "/**/.git/**",
    "/**/.guardkit/state_transitions.json",
    "/**/.guardkit/autobuild/*/coach_*.json",
    "/**/tasks/**",
]


def build_autobuild_permissions() -> list[FilesystemPermission]:
    """Return the AutoBuild deny-rule list for ``LangGraphHarness`` (AC-003).

    A single ``FilesystemPermission`` collapsing all four deny patterns into
    one ``operations=["write"]`` rule. This is sufficient because:

    * ``FilesystemPermission`` evaluates rules in declaration order and the
      *first* matching rule wins, so one rule covering all four paths is
      indistinguishable from four rules covering one path each.
    * ``operations=["write"]`` covers both ``write_file`` and ``edit_file``
      (the only two DeepAgents tools that mutate filesystem state via the
      backend protocol; ``execute`` is governed by the operator-trust model
      described in :mod:`guardkitfactory.harness.backend_config`).

    Returns:
        A list with a single :class:`FilesystemPermission` ready to pass to
        :class:`guardkitfactory.harness.LangGraphHarness` (which forwards it
        as the ``permissions`` argument to ``create_deep_agent``).
    """
    return [
        FilesystemPermission(
            operations=["write"],
            paths=list(_AUTOBUILD_DENY_WRITE_PATTERNS),
            mode="deny",
        ),
    ]
