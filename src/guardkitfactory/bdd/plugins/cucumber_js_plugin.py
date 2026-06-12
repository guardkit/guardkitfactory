"""CucumberJSPlugin — TypeScript / JavaScript Cucumber.js BDD oracle.

Registers with the loader so the Coach evidence path routes JS/TS projects
to ``cucumber-js`` when a ``package.json`` with a cucumber dependency and
the ``npx`` CLI are present.
"""

from __future__ import annotations

import json
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
class CucumberJSPlugin(BDDPlugin):
    """TypeScript / Cucumber.js plugin."""

    name = "cucumber-js"

    @classmethod
    def discover(
        cls, stack: StackProfile, worktree: Path,
    ) -> Optional["CucumberJSPlugin"]:
        if stack.language not in ("javascript", "typescript"):
            return None
        # Check for package.json with cucumber dependency
        package_json = Path(worktree) / "package.json"
        if not package_json.exists():
            return None
        try:
            with open(package_json) as f:
                pkg = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        if not any("cucumber" in dep for dep in deps):
            return None
        # Check for npx / cucumber-js CLI availability
        try:
            subprocess.run(
                ["npx", "cucumber-js", "--version"],
                check=True,
                capture_output=True,
                timeout=10,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return None
        return cls()

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
