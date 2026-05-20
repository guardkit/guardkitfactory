"""ReqnrollPlugin (stub) — placeholder for the .NET BDD oracle.

Per TASK-HMIG-007 AC-009, this stub is registered so the loader can
iterate it safely. Its :meth:`discover` returns ``None`` for every stack
(no .NET match) and :meth:`contract_tests` returns an empty list (no
contracts to enforce on a no-op plugin). The concrete implementation —
``dotnet test --filter Category=task_<TASK_ID>`` with TRX parsing per
parent review §6.4 — lands in a follow-on task when a .NET project that
actually needs it exists.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from guardkitfactory.bdd.loader import register
from guardkitfactory.bdd.plugin import (
    BDDPlugin,
    BDDRunResult,
    ContractTestResult,
    Scenario,
    StackProfile,
)


@register
class ReqnrollPlugin(BDDPlugin):
    """.NET / xUnit + Reqnroll plugin (stub, not yet implemented)."""

    name = "reqnroll"

    @classmethod
    def discover(
        cls, stack: StackProfile, worktree: Path,
    ) -> Optional["ReqnrollPlugin"]:
        return None

    def preflight(self, task_id: str, worktree: Path) -> bool:
        raise NotImplementedError(
            "ReqnrollPlugin is a stub. Concrete implementation lands in a "
            "follow-on task per TASK-HMIG-007 AC-009."
        )

    def run(
        self,
        scenarios: list[Scenario],
        task_id: str,
        worktree: Path,
        *,
        timeout_seconds: int = 600,
    ) -> BDDRunResult:
        raise NotImplementedError(
            "ReqnrollPlugin is a stub. Concrete implementation lands in a "
            "follow-on task per TASK-HMIG-007 AC-009."
        )

    def contract_tests(self) -> list[ContractTestResult]:
        return []


__all__ = ["ReqnrollPlugin"]
