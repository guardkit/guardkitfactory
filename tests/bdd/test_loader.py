"""Loader registration + discovery tests (TASK-HMIG-007 AC-012).

Verifies the *contract-gated registration* guarantee: a plugin that fails
any of its contract tests is refused registration, with a
:class:`ContractTestFailure` carrying the failing contract names.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pytest

from guardkitfactory.bdd import loader as _loader
from guardkitfactory.bdd.loader import (
    ContractTestFailure,
    _registered_plugins,
    discover,
    register,
)
from guardkitfactory.bdd.plugin import (
    BDDPlugin,
    BDDRunResult,
    ContractTestResult,
    Scenario,
    StackProfile,
)
from guardkitfactory.bdd.plugins.cucumber_js_plugin import CucumberJSPlugin
from guardkitfactory.bdd.plugins.pytest_bdd_plugin import PytestBDDPlugin
from guardkitfactory.bdd.plugins.reqnroll_plugin import ReqnrollPlugin


@pytest.fixture()
def isolated_registry():
    """Snapshot and restore the global registry around a test."""
    snapshot = list(_loader._REGISTRY)
    _loader._REGISTRY.clear()
    try:
        yield
    finally:
        _loader._REGISTRY.clear()
        _loader._REGISTRY.extend(snapshot)


class _AllPassPlugin(BDDPlugin):
    name = "all-pass-test-only"

    @classmethod
    def discover(
        cls, stack: StackProfile, worktree: Path,
    ) -> Optional["_AllPassPlugin"]:
        return None

    def preflight(self, task_id: str, worktree: Path) -> bool:
        return True

    def run(
        self,
        scenarios: list[Scenario],
        task_id: str,
        worktree: Path,
        *,
        timeout_seconds: int = 600,
    ) -> BDDRunResult:
        return BDDRunResult(
            scenarios_attempted=0,
            scenarios_passed=0,
            scenarios_failed=0,
            scenarios_skipped=0,
            scenarios_errored=0,
            duration_seconds=0.0,
            raw_report_path=None,
        )

    def contract_tests(self) -> list[ContractTestResult]:
        return [
            ContractTestResult(c, True, "pass")
            for c in ("C1", "C2", "C3", "C4", "C5", "C6")
        ]


class _PartialFailPlugin(BDDPlugin):
    name = "partial-fail-test-only"

    @classmethod
    def discover(
        cls, stack: StackProfile, worktree: Path,
    ) -> Optional["_PartialFailPlugin"]:
        return None

    def preflight(self, task_id: str, worktree: Path) -> bool:
        return True

    def run(
        self,
        scenarios: list[Scenario],
        task_id: str,
        worktree: Path,
        *,
        timeout_seconds: int = 600,
    ) -> BDDRunResult:
        return BDDRunResult(
            scenarios_attempted=0,
            scenarios_passed=0,
            scenarios_failed=0,
            scenarios_skipped=0,
            scenarios_errored=0,
            duration_seconds=0.0,
            raw_report_path=None,
        )

    def contract_tests(self) -> list[ContractTestResult]:
        return [
            ContractTestResult("C1", True, "ok"),
            ContractTestResult("C3", False, "deliberately broken for test"),
            ContractTestResult("C5", False, "deliberately broken for test"),
        ]


class _MatchingPythonPlugin(BDDPlugin):
    """Used by discover() tests — matches when language=python."""

    name = "matching-python-test-only"

    @classmethod
    def discover(
        cls, stack: StackProfile, worktree: Path,
    ) -> Optional["_MatchingPythonPlugin"]:
        if stack.language == "python":
            return cls()
        return None

    def preflight(self, task_id: str, worktree: Path) -> bool:
        return True

    def run(
        self,
        scenarios: list[Scenario],
        task_id: str,
        worktree: Path,
        *,
        timeout_seconds: int = 600,
    ) -> BDDRunResult:
        return BDDRunResult(
            scenarios_attempted=0,
            scenarios_passed=0,
            scenarios_failed=0,
            scenarios_skipped=0,
            scenarios_errored=0,
            duration_seconds=0.0,
            raw_report_path=None,
        )

    def contract_tests(self) -> list[ContractTestResult]:
        return [ContractTestResult("C1", True, "ok")]


class TestRegistrationGate:
    def test_passing_plugin_is_registered(self, isolated_registry) -> None:
        register(_AllPassPlugin)
        assert _AllPassPlugin in _registered_plugins()

    def test_failing_contracts_refuse_registration(
        self, isolated_registry
    ) -> None:
        with pytest.raises(ContractTestFailure) as excinfo:
            register(_PartialFailPlugin)

        msg = str(excinfo.value)
        assert "_PartialFailPlugin" in msg
        # The failing contract names MUST surface in the error so the
        # operator can read which guard tripped.
        assert "C3" in msg
        assert "C5" in msg
        # The passing contract C1 must NOT be confused for a failure.
        assert "C1: deliberately broken" not in msg
        assert _PartialFailPlugin not in _registered_plugins()

    def test_register_is_idempotent(self, isolated_registry) -> None:
        register(_AllPassPlugin)
        register(_AllPassPlugin)
        registered = _registered_plugins()
        assert registered.count(_AllPassPlugin) == 1


class TestDiscoveryIteration:
    def test_discover_returns_first_matching_plugin(
        self, isolated_registry
    ) -> None:
        register(_MatchingPythonPlugin)
        stack = StackProfile(
            language="python",
            test_framework="pytest",
            package_manager="pip",
            project_root=Path("/tmp"),
        )
        result = discover(stack, Path("/tmp"))
        assert isinstance(result, _MatchingPythonPlugin)

    def test_discover_returns_none_when_no_match(
        self, isolated_registry
    ) -> None:
        register(_MatchingPythonPlugin)
        stack = StackProfile(
            language="rust",
            test_framework="cargo-test",
            package_manager="cargo",
            project_root=Path("/tmp"),
        )
        result = discover(stack, Path("/tmp"))
        assert result is None

    def test_stub_plugins_are_safely_iterated(
        self, isolated_registry
    ) -> None:
        """AC-009: stub plugins must not break discovery iteration."""
        register(ReqnrollPlugin)
        register(CucumberJSPlugin)
        register(_MatchingPythonPlugin)

        # Discovery iterates all three; stubs return None; matching
        # plugin returns an instance.
        stack = StackProfile(
            language="python",
            test_framework="pytest",
            package_manager="pip",
            project_root=Path("/tmp"),
        )
        result = discover(stack, Path("/tmp"))
        assert isinstance(result, _MatchingPythonPlugin)


class TestBuiltInPluginsAreRegistered:
    """Smoke test: the side-effect import wires up the three built-ins."""

    def test_pytest_bdd_plugin_is_registered(self) -> None:
        assert PytestBDDPlugin in _registered_plugins()

    def test_stub_plugins_are_registered(self) -> None:
        assert ReqnrollPlugin in _registered_plugins()
        assert CucumberJSPlugin in _registered_plugins()
