"""CucumberJSPlugin (stub) — placeholder for the TypeScript / JS BDD oracle.

Per TASK-HMIG-007 AC-009, this stub is registered so the loader can
iterate it safely. Its :meth:`discover` returns ``None`` for every stack
(no TS/JS match) and :meth:`contract_tests` returns an empty list. The
concrete implementation — ``npx cucumber-js --tags @task_<TASK_ID>`` with
Cucumber JSON parsing per parent review §6.5 — lands in a follow-on task
when a TS project that actually needs it exists.
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
class CucumberJSPlugin(BDDPlugin):
    """TypeScript / Cucumber.js plugin (stub, not yet implemented)."""

    name = "cucumber-js"

    @classmethod
    def discover(
        cls, stack: StackProfile, worktree: Path,
    ) -> Optional["CucumberJSPlugin"]:
        return None

    def preflight(self, task_id: str, worktree: Path) -> bool:
        raise NotImplementedError(
            "CucumberJSPlugin is a stub. Concrete implementation lands in a "
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
            "CucumberJSPlugin is a stub. Concrete implementation lands in a "
            "follow-on task per TASK-HMIG-007 AC-009."
        )

    def contract_tests(self) -> list[ContractTestResult]:
        return []


__all__ = ["CucumberJSPlugin"]
