"""ReqnrollPlugin — .NET / Reqnroll BDD oracle.

Registers with the loader so the Coach evidence path routes .NET projects
to ``dotnet test`` with Reqnroll TRX output.  Its :meth:`discover` checks
that the stack language is ``dotnet`` or ``csharp`` and that a .sln or
.csproj file plus the ``dotnet`` CLI are present.
"""

from __future__ import annotations

import subprocess
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
    """.NET / xUnit + Reqnroll plugin."""

    name = "reqnroll"

    @classmethod
    def discover(
        cls, stack: StackProfile, worktree: Path,
    ) -> Optional["ReqnrollPlugin"]:
        if stack.language not in ("dotnet", "csharp"):
            return None
        project_root = Path(worktree)
        # Check for .sln or .csproj files
        if not any(project_root.glob("*.sln")) and not any(project_root.glob("*.csproj")):
            return None
        # Check for dotnet CLI availability
        try:
            subprocess.run(
                ["dotnet", "--version"],
                check=True,
                capture_output=True,
                timeout=10,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return None
        return cls()

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
