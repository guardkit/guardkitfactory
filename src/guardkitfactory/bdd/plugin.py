"""BDDPlugin interface + supporting dataclasses (TASK-HMIG-007 / parent review §6.1).

Decouples "the BDD oracle" from any single test runner. Coach consumes only
:class:`BDDRunResult`; the per-stack plugins (PytestBDDPlugin, ReqnrollPlugin,
CucumberJSPlugin) know how to invoke the underlying runner and parse its
output back into this shared contract.

The six contracts on :meth:`BDDPlugin.contract_tests` are the
:doc:`§5 failure-pattern guards <.../reviews/TASK-REV-HMIG-review-report>`
lifted into the type system — see :mod:`guardkitfactory.bdd.loader` for the
registration gate that enforces them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional


def run_project_command(args: Any, **kwargs: Any) -> Any:
    """GuardKit's ``process_group.run_project_command`` (13 October 2026).

    The same arguments, results and exceptions as ``subprocess.run``, but the
    command runs in a process group of its own, so a timeout ends everything
    it started (a pytest worker, a server), not only its first process.
    Imported when called: GuardKit imports this package while it loads.
    """
    from guardkit.orchestrator.process_group import (
        run_project_command as _run_in_group,
    )

    return _run_in_group(args, **kwargs)


def project_command_env(
    worktree: Path, additions: Optional[Mapping[str, str]] = None
) -> dict[str, str]:
    """The environment a plugin's project command runs with (13 October 2026).

    Built from nothing by GuardKit's ``project_command_env``
    (design ``factory-project-commands-without-factory-credentials``): the
    project's interpreter, its ``npx`` copy or its ``global.json``-chosen
    ``dotnet`` never see the factory's credentials. The ``launch:`` block is
    read from the main checkout the worktree was cut from.

    GuardKit is required at run time (``harness/langgraph_harness.py`` already
    imports it); an ``ImportError`` is raised rather than falling back to this
    process's environment. Raises GuardKit's ``LaunchEnvironmentError`` (an
    ``OSError``) when the environment cannot be built.
    """
    from guardkit.orchestrator.launch_declaration import (
        load_launch_declaration,
        main_checkout_root,
    )
    from guardkit.orchestrator.project_command_env import (
        project_command_environment,
    )

    folder = Path(worktree)
    return project_command_environment(
        folder,
        load_launch_declaration(main_checkout_root(folder)),
        additions=dict(additions or {}),
    )


@dataclass(frozen=True)
class StackProfile:
    """What the stack detector returns and what plugin :meth:`discover` matches against."""

    language: str
    test_framework: str
    package_manager: str
    project_root: Path
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Scenario:
    """One BDD scenario, plugin-agnostic."""

    feature_path: Path
    name: str
    tags: tuple[str, ...]
    task_id: Optional[str] = None


@dataclass
class BDDRunResult:
    """The plugin's output contract. Coach reads only this.

    The :attr:`is_zero_cardinality` property is the
    *absence-of-failure-is-not-success* precondition
    (`.claude/rules/absence-of-failure-is-not-success.md` in the sibling
    guardkit repo). Downstream consumers MUST treat zero attempts as
    "no oracle ran" rather than "no failures observed".
    """

    scenarios_attempted: int
    scenarios_passed: int
    scenarios_failed: int
    scenarios_skipped: int
    scenarios_errored: int
    duration_seconds: float
    raw_report_path: Optional[Path]
    discoveries: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_zero_cardinality(self) -> bool:
        return self.scenarios_attempted == 0


@dataclass(frozen=True)
class ContractTestResult:
    """One C1-C6 contract test outcome."""

    contract_name: str
    passed: bool
    detail: str


class BDDPlugin(ABC):
    """Technology-agnostic BDD oracle interface.

    Lifecycle:
      1. :meth:`discover` — return plugin instance or ``None`` for this stack.
      2. :meth:`preflight` — sanity-check the per-task glue convention.
      3. :meth:`run` — execute the scenarios; return :class:`BDDRunResult`.
      4. :meth:`contract_tests` — self-validate against the §5 failure-pattern
         guards. The loader refuses to register any plugin with a failing
         contract.
    """

    #: Stable identifier surfaced in logs and the Coach evidence bundle.
    name: str = ""

    @classmethod
    @abstractmethod
    def discover(
        cls,
        stack: StackProfile,
        worktree: Path,
    ) -> Optional["BDDPlugin"]:
        """Return a plugin instance iff this plugin matches the stack.

        Match rules:
          - python + pytest      → PytestBDDPlugin
          - csharp + dotnet-test → ReqnrollPlugin
          - typescript + vitest  → CucumberJSPlugin
        """

    @abstractmethod
    def preflight(self, task_id: str, worktree: Path) -> bool:
        """Sanity-check the runner config before invoking the oracle.

        Verifies:
          - The per-task glue file naming + sanitisation rules (Pattern 2).
          - The task_id is honourable by the runner's filtering mechanism.
        Returns ``False`` if any check fails; the orchestrator surfaces
        the failure as Coach feedback rather than retrying blindly.
        """

    @abstractmethod
    def run(
        self,
        scenarios: list[Scenario],
        task_id: str,
        worktree: Path,
        *,
        timeout_seconds: int = 600,
    ) -> BDDRunResult:
        """Execute scenarios. Return a fully-populated :class:`BDDRunResult`.

        Contract obligations:
          - MUST NOT silently approve zero-cardinality runs — return
            ``scenarios_attempted=0`` honestly (Coach gates on the
            ``is_zero_cardinality`` property).
          - MUST capture timeouts as ``errors=["timeout"]`` (Contract C5)
            rather than raising.
          - MUST surface collection errors / undefined steps via
            ``scenarios_errored > 0`` (Contract C6) rather than reporting
            a silent zero.
        """

    @abstractmethod
    def contract_tests(self) -> list[ContractTestResult]:
        """Self-test the plugin against the failure-pattern guards (§5).

        Every implementation MUST honour all six contracts before the
        loader will register it:

          C1: zero-cardinality → ``is_zero_cardinality=True``, not green
          C2: per-task glue naming follows the sanitisation rule
              (`bdd-per-task-glue.md`).
          C3: parallel tasks against the same feature produce disjoint
              scenario sets (typically via the per-task filter mechanism).
          C4: identity-bounded resolution survives mid-run scenario file
              renames (no path-string false-red — see
              `path-string-mismatch-is-not-dishonesty.md`).
          C5: timeout produces a structured :class:`BDDRunResult` with
              ``errors=["timeout"]`` rather than an exception leak.
          C6: undefined step / collection error → ``scenarios_errored > 0``,
              not silent zero.
        """


__all__ = [
    "BDDPlugin",
    "BDDRunResult",
    "ContractTestResult",
    "Scenario",
    "StackProfile",
]
