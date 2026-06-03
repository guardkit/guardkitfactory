"""FilesystemPermission deny-rules for the AutoBuild LangGraph harness.

TASK-HMIG-002R-NOPERMS (2026-06-03) — current state
===================================================

``build_autobuild_permissions()`` currently returns ``[]``. This is a
deliberate workaround for a DeepAgents library limitation surfaced by
guardkit-side TASK-HMIG-009A AC-001D run 4: the permission middleware
does not yet support backends that provide command execution
(``SandboxBackendProtocol``). At ``deepagents==0.6.7`` the guard lives in
``deepagents.middleware.filesystem.FilesystemMiddleware.__init__`` (line
~697 in the upstream source) and raises ``NotImplementedError`` with:

  "FilesystemMiddleware does not yet support permissions with backends
  that provide command execution (SandboxBackendProtocol). Tool-level
  permissions for the execute tool are not implemented. Either remove
  permissions or use a backend without execution support."

AutoBuild needs ``execute`` (Coach runs ``pytest``, Player runs scripts),
so we cannot switch to ``FilesystemBackend``. The forced choice is
permissions OR execute — for the canary we accept losing permissions.

Upstream stance
---------------

Upstream issue https://github.com/langchain-ai/deepagents/issues/2894
("Extend ``PermissionMiddleware`` to support execute and task tool
restrictions") was **closed/declined** by maintainer ``@eyurtsev``:

  "We're not ready to add this to the SDK at the moment. You can use
  custom middleware for now to enforce execute permissions in this
  manner."

A contributor (``@NinaadRao``) had a working PR ready (29 new tests,
``ExecutePermission`` + ``TaskPermission`` dataclasses, removed the
``NotImplementedError`` guard) and the maintainer declined to merge.
"Wait for upstream" is therefore not a realistic restore path; the
follow-on `TASK-HMIG-002R-PERMS-CUSTOM-MIDDLEWARE` tracks the
custom-middleware route.

No security regression
----------------------

``LocalShellBackend(root_dir=cwd, virtual_mode=True)`` still bounds the
worktree access. The SDK harness has equivalent unrestricted access today
via ``permission_mode="acceptEdits"`` + ``cwd=worktree`` (parent review
§14.7 D-11). The deny-rules below were a strict improvement over the
status quo; their absence is parity with the SDK, not a regression.

Restoring the deny-rules
------------------------

The original deny-rule construction is preserved as a commented block at
the bottom of this module — labelled ``RESTORE WHEN ...`` — so the
restore work is mechanical. Two viable triggers:

1. Upstream reopens #2894 and lands the missing support, OR
2. ``TASK-HMIG-002R-PERMS-CUSTOM-MIDDLEWARE`` ships a guardkitfactory-
   local middleware that gates execute alongside filesystem writes.

Surfaced by: guardkit-side TASK-HMIG-009A AC-001D run 4 (2026-06-03).
See: ``../guardkit/docs/reviews/autobuild-migration/TASK-FIX-A7D3-langraph-run-4.md``
"""

from __future__ import annotations

import logging
from typing import Any

from deepagents import FilesystemPermission  # noqa: F401 — kept for restore block

logger = logging.getLogger(__name__)

__all__ = ["build_autobuild_permissions"]


def build_autobuild_permissions() -> list[Any]:
    """Return permission rules for the AutoBuild LangGraph harness.

    **TEMPORARY (TASK-HMIG-002R-NOPERMS, 2026-06-03)**: returns ``[]``.

    DeepAgents' permission middleware does not yet support backends with
    command execution (``SandboxBackendProtocol``; ``LocalShellBackend``
    qualifies). Upstream declined to add support
    (https://github.com/langchain-ai/deepagents/issues/2894). AutoBuild
    needs ``execute``, so permissions are dropped pending the in-tree
    custom-middleware port tracked by
    ``TASK-HMIG-002R-PERMS-CUSTOM-MIDDLEWARE``.

    The worktree boundary is still enforced by
    ``LocalShellBackend(root_dir=cwd, virtual_mode=True)`` — no security
    regression vs the SDK harness's current ``permission_mode="acceptEdits"``
    + ``cwd=worktree`` reality.

    Returns:
        Empty list. The original deny-rule construction is preserved as a
        commented block below — see "RESTORE WHEN ..." for activation.
    """
    logger.debug(
        "TASK-HMIG-002R-NOPERMS: returning [] — DeepAgents permission "
        "middleware does not support execute-capable backends and upstream "
        "issue #2894 was declined. See permissions.py docstring for the "
        "restore path (TASK-HMIG-002R-PERMS-CUSTOM-MIDDLEWARE)."
    )
    return []


# ---------------------------------------------------------------------------
# RESTORE WHEN either (a) DeepAgents upstream lands #2894-equivalent support,
# OR (b) TASK-HMIG-002R-PERMS-CUSTOM-MIDDLEWARE ships an in-tree middleware
# that gates execute alongside filesystem writes.
#
# To restore: delete `return []` and the logger line above, uncomment the
# block below, and re-enable the deny-rule tests in
# tests/harness/test_backend_config.py (look for the TASK-HMIG-002R-NOPERMS
# skip markers).
#
# Why these rules — see parent review TASK-REV-HMIG §3.4:
#   /**/.git/**                                  — repository integrity
#   /**/.guardkit/state_transitions.json          — kanban single source of truth
#   /**/.guardkit/autobuild/*/coach_*.json        — Coach trust boundary
#   /**/tasks/**                                  — kanban file integrity
#
# operations=["write"] covers both write_file and edit_file (deepagents
# collapses them into a single "write" operation). The /**/ prefix keeps
# the rules worktree-location-agnostic.
# ---------------------------------------------------------------------------
#
# _AUTOBUILD_DENY_WRITE_PATTERNS: list[str] = [
#     "/**/.git/**",
#     "/**/.guardkit/state_transitions.json",
#     "/**/.guardkit/autobuild/*/coach_*.json",
#     "/**/tasks/**",
# ]
#
# def build_autobuild_permissions() -> list[FilesystemPermission]:
#     return [
#         FilesystemPermission(
#             operations=["write"],
#             paths=list(_AUTOBUILD_DENY_WRITE_PATTERNS),
#             mode="deny",
#         ),
#     ]
