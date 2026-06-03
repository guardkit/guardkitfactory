"""Explicit C1-C6 contract tests for PytestBDDPlugin (TASK-HMIG-007 AC-011).

Mirrors the in-class :meth:`PytestBDDPlugin.contract_tests` aggregation so
the same guards surface as granular pytest tests rather than a single
opaque registration failure. Each test exercises the plugin's
*interpretation* of runner output (counters, command argv, sanitisation,
timeout handling) — the §5 failure-pattern hazards the parent review
identified.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from guardkitfactory.bdd.plugin import BDDRunResult, Scenario
from guardkitfactory.bdd.plugins.pytest_bdd_plugin import (
    PytestBDDPlugin,
    _marker_for_task,
    _per_task_glue_name,
    _sanitise_slug,
    _sanitise_task_id,
)


@pytest.fixture()
def plugin() -> PytestBDDPlugin:
    return PytestBDDPlugin()


@pytest.fixture()
def junit_writer(tmp_path: Path):
    """Helper that writes a JUnit XML file with the given counters."""

    def _writer(
        *,
        tests: int = 0,
        failures: int = 0,
        errors: int = 0,
        skipped: int = 0,
        time: float = 0.0,
        wrap_testsuites: bool = True,
    ) -> Path:
        suite = (
            f'<testsuite name="pytest" tests="{tests}" failures="{failures}" '
            f'errors="{errors}" skipped="{skipped}" time="{time}"/>'
        )
        body = (
            f"<testsuites>\n  {suite}\n</testsuites>" if wrap_testsuites else suite
        )
        junit = tmp_path / "junit.xml"
        junit.write_text(f'<?xml version="1.0" encoding="utf-8"?>\n{body}\n')
        return junit

    return _writer


def _fake_proc(returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout="", stderr=stderr
    )


# ---------------------------------------------------------------------------
# C1: zero-cardinality JUnit → is_zero_cardinality=True, not green
# ---------------------------------------------------------------------------


class TestC1ZeroCardinality:
    """Pattern 2 + Pattern 4: absence-of-failure-is-not-success."""

    def test_clean_zero_is_zero_cardinality(self, plugin, junit_writer) -> None:
        junit = junit_writer(tests=0, failures=0, errors=0, skipped=0)
        result = plugin._parse_junit(junit, _fake_proc(returncode=5))
        assert result.is_zero_cardinality is True
        assert result.scenarios_attempted == 0

    def test_clean_zero_carries_no_synthetic_error(
        self, plugin, junit_writer
    ) -> None:
        """A clean zero JUnit is honestly zero — don't fabricate errors."""
        junit = junit_writer(tests=0)
        result = plugin._parse_junit(junit, _fake_proc(returncode=5))
        assert result.errors == []

    def test_aggregate_contract_passes(self, plugin) -> None:
        results = {r.contract_name: r for r in plugin.contract_tests()}
        assert results["C1"].passed, results["C1"].detail


# ---------------------------------------------------------------------------
# C2: per-task glue naming + sanitisation rules
# ---------------------------------------------------------------------------


class TestC2PerTaskGlueSanitisation:
    """Mirrors `.claude/rules/bdd-per-task-glue.md` sanitisation contract."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("TASK-FG-002", "TASK_FG_002"),
            ("@TASK:FOO-bar", "TASK_FOO_bar"),
            ("TASK-HMIG-007", "TASK_HMIG_007"),
            ("TASK_already_sanitised", "TASK_already_sanitised"),
        ],
    )
    def test_task_id_sanitisation(self, raw: str, expected: str) -> None:
        assert _sanitise_task_id(raw) == expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("fleet-gateway-common", "fleet_gateway_common"),
            ("simple", "simple"),
            ("multi-hyphen-slug-name", "multi_hyphen_slug_name"),
        ],
    )
    def test_slug_sanitisation(self, raw: str, expected: str) -> None:
        assert _sanitise_slug(raw) == expected

    def test_per_task_glue_filename(self) -> None:
        assert (
            _per_task_glue_name("fleet-gateway-common", "TASK-FG-002")
            == "test_fleet_gateway_common__TASK_FG_002.py"
        )

    def test_marker_is_derived_consistently(self) -> None:
        assert _marker_for_task("TASK-FG-002") == "task_TASK_FG_002"
        assert _marker_for_task("@TASK:FOO-bar") == "task_TASK_FOO_bar"

    def test_aggregate_contract_passes(self, plugin) -> None:
        results = {r.contract_name: r for r in plugin.contract_tests()}
        assert results["C2"].passed, results["C2"].detail


# ---------------------------------------------------------------------------
# C3: parallel tasks against the same feature produce disjoint scenario sets
# ---------------------------------------------------------------------------


class TestC3ParallelDisjointMarkers:
    """Verifies the disjointness mechanism (the per-task marker filter)."""

    def test_two_task_ids_produce_distinct_markers(
        self, plugin, tmp_path: Path
    ) -> None:
        captured: list[list[str]] = []

        def _capture(cmd, **kwargs):
            captured.append(list(cmd))
            return subprocess.CompletedProcess(
                args=cmd, returncode=5, stdout="", stderr=""
            )

        with patch("subprocess.run", side_effect=_capture):
            plugin.run([], "TASK-C3-A", tmp_path, timeout_seconds=5)
            plugin.run([], "TASK-C3-B", tmp_path, timeout_seconds=5)

        assert len(captured) == 2
        # Find the *last* -m in each argv (first -m is `python -m pytest`).
        def _marker(argv: list[str]) -> str:
            last_m = len(argv) - 1 - argv[::-1].index("-m")
            return argv[last_m + 1]

        marker_a = _marker(captured[0])
        marker_b = _marker(captured[1])

        assert marker_a == "task_TASK_C3_A"
        assert marker_b == "task_TASK_C3_B"
        assert marker_a != marker_b, (
            "two task_ids must not collapse to the same marker — parallel "
            "runs would share scenarios"
        )

    def test_aggregate_contract_passes(self, plugin) -> None:
        results = {r.contract_name: r for r in plugin.contract_tests()}
        assert results["C3"].passed, results["C3"].detail


# ---------------------------------------------------------------------------
# C4: identity-bounded resolution (no specific .feature paths in argv)
# ---------------------------------------------------------------------------


class TestC4IdentityBoundedResolution:
    """Mirrors `.claude/rules/path-string-mismatch-is-not-dishonesty.md`."""

    def test_run_targets_features_directory_not_specific_paths(
        self, plugin, tmp_path: Path
    ) -> None:
        captured: list[list[str]] = []

        def _capture(cmd, **kwargs):
            captured.append(list(cmd))
            return subprocess.CompletedProcess(
                args=cmd, returncode=5, stdout="", stderr=""
            )

        with patch("subprocess.run", side_effect=_capture):
            plugin.run(
                [
                    Scenario(
                        feature_path=tmp_path / "features" / "renamed_v1.feature",
                        name="ScenarioA",
                        tags=("@task_TASK_C4",),
                        task_id="TASK-C4",
                    )
                ],
                "TASK-C4",
                tmp_path,
                timeout_seconds=5,
            )

        assert len(captured) == 1
        argv = captured[0]
        assert "features/" in argv, (
            "pytest must target the features/ directory so renames are "
            "survivable (path-string-mismatch-is-not-dishonesty.md)"
        )
        leaks = [a for a in argv if a.endswith(".feature")]
        assert not leaks, (
            f"specific .feature paths leaked into argv: {leaks}"
        )

    def test_aggregate_contract_passes(self, plugin) -> None:
        results = {r.contract_name: r for r in plugin.contract_tests()}
        assert results["C4"].passed, results["C4"].detail


# ---------------------------------------------------------------------------
# C5: timeout → structured BDDRunResult.errors=["timeout"], no exception leak
# ---------------------------------------------------------------------------


class TestC5TimeoutStructured:
    """Pattern 5: task-work-timeout-and-resume-fragility."""

    def test_timeout_returns_structured_result(
        self, plugin, tmp_path: Path
    ) -> None:
        def _timeout(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=2)

        with patch("subprocess.run", side_effect=_timeout):
            result = plugin.run(
                [], "TASK-C5", tmp_path, timeout_seconds=2,
            )

        assert isinstance(result, BDDRunResult)
        assert result.errors == ["timeout"]
        assert result.scenarios_attempted == 0
        assert result.duration_seconds == 2.0

    def test_timeout_does_not_leak_exception(
        self, plugin, tmp_path: Path
    ) -> None:
        def _timeout(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=1)

        with patch("subprocess.run", side_effect=_timeout):
            # Must not raise — this is the contract.
            plugin.run([], "TASK-C5", tmp_path, timeout_seconds=1)

    def test_aggregate_contract_passes(self, plugin) -> None:
        results = {r.contract_name: r for r in plugin.contract_tests()}
        assert results["C5"].passed, results["C5"].detail


# ---------------------------------------------------------------------------
# C6: collection error / undefined step → scenarios_errored > 0
# ---------------------------------------------------------------------------


class TestC6CollectionErrorSurfaced:
    """Pattern 2 + absence-of-failure-is-not-success.md."""

    def test_junit_errors_attribute_surfaces_as_scenarios_errored(
        self, plugin, junit_writer
    ) -> None:
        junit = junit_writer(tests=1, errors=1)
        result = plugin._parse_junit(junit, _fake_proc(returncode=2))
        assert result.scenarios_errored == 1, (
            "JUnit errors attribute must not be silently dropped"
        )
        assert not result.is_zero_cardinality

    def test_missing_junit_falls_back_to_errored(
        self, plugin, tmp_path: Path
    ) -> None:
        missing = tmp_path / "never_emitted.xml"
        proc = _fake_proc(returncode=4, stderr="collection failed")
        result = plugin._parse_junit(missing, proc)
        assert result.scenarios_errored >= 1, (
            "missing JUnit XML must surface as errored, not silent zero"
        )
        assert result.errors, "missing JUnit must record a diagnostic"

    def test_aggregate_contract_passes(self, plugin) -> None:
        results = {r.contract_name: r for r in plugin.contract_tests()}
        assert results["C6"].passed, results["C6"].detail


# ---------------------------------------------------------------------------
# Run-level smoke tests outside the C1-C6 cases
# ---------------------------------------------------------------------------


class TestPreflightShape:
    """Sanitisation-shape and worktree-existence checks."""

    def test_preflight_rejects_empty_after_sanitisation(
        self, plugin, tmp_path: Path
    ) -> None:
        assert plugin.preflight("@", tmp_path) is False

    def test_preflight_rejects_missing_worktree(self, plugin) -> None:
        assert plugin.preflight("TASK-X", Path("/nonexistent/path/never")) is False

    def test_preflight_rejects_missing_features_dir(
        self, plugin, tmp_path: Path
    ) -> None:
        # tmp_path exists but has no features/ subdir
        assert plugin.preflight("TASK-X", tmp_path) is False


class TestPreflightAC006:
    """AC-006: per-task glue file existence + GUARDKIT_BDD_TASK_ID env-var honour.

    Refinement of the original implementation that only verified
    sanitisation shape. Per the /task-refine feedback, preflight MUST
    detect when the project has not adopted the per-task glue convention
    or has not honoured the env-var contract, so the orchestrator can
    surface that as feedback rather than running a blind zero-cardinality
    pytest invocation.
    """

    @pytest.fixture()
    def worktree_with_glue_and_conftest(self, tmp_path: Path) -> Path:
        features = tmp_path / "features"
        features.mkdir()
        (features / "conftest.py").write_text(
            "import os\n"
            "_BDD_TASK_ID_ENV = 'GUARDKIT_BDD_TASK_ID'\n"
            "_active_task = os.environ.get(_BDD_TASK_ID_ENV)\n"
        )
        (features / "test_login__TASK_AUTH_001.py").write_text(
            "# per-task glue stub for TASK-AUTH-001\n"
        )
        return tmp_path

    def test_preflight_accepts_when_glue_and_conftest_present(
        self, plugin, worktree_with_glue_and_conftest: Path
    ) -> None:
        assert plugin.preflight(
            "TASK-AUTH-001", worktree_with_glue_and_conftest
        ) is True

    def test_preflight_accepts_with_sanitised_task_id(
        self, plugin, worktree_with_glue_and_conftest: Path
    ) -> None:
        """Sanitisation TASK-AUTH-001 → TASK_AUTH_001 must match the
        glue file ``test_login__TASK_AUTH_001.py`` on disk."""
        assert plugin.preflight(
            "@TASK:AUTH-001", worktree_with_glue_and_conftest
        ) is True

    def test_preflight_rejects_when_glue_for_other_task(
        self, plugin, worktree_with_glue_and_conftest: Path
    ) -> None:
        # Worktree has glue for TASK-AUTH-001 only; another task has none.
        assert plugin.preflight(
            "TASK-OTHER-002", worktree_with_glue_and_conftest
        ) is False

    def test_preflight_rejects_when_conftest_lacks_env_var(
        self, plugin, tmp_path: Path
    ) -> None:
        features = tmp_path / "features"
        features.mkdir()
        (features / "conftest.py").write_text("# nothing here\n")
        (features / "test_x__TASK_Y.py").write_text("# glue\n")
        assert plugin.preflight("TASK-Y", tmp_path) is False

    def test_preflight_rejects_when_no_conftest_at_all(
        self, plugin, tmp_path: Path
    ) -> None:
        features = tmp_path / "features"
        features.mkdir()
        (features / "test_x__TASK_Y.py").write_text("# glue\n")
        # No conftest.py at all — env-var honour cannot be confirmed
        assert plugin.preflight("TASK-Y", tmp_path) is False

    def test_preflight_finds_glue_in_nested_features_subdir(
        self, plugin, tmp_path: Path
    ) -> None:
        features = tmp_path / "features"
        (features / "subdir").mkdir(parents=True)
        (features / "conftest.py").write_text(
            "import os\n"
            "_BDD_TASK_ID_ENV = 'GUARDKIT_BDD_TASK_ID'\n"
        )
        (features / "subdir" / "test_nested__TASK_NESTED.py").write_text("# glue\n")
        assert plugin.preflight("TASK-NESTED", tmp_path) is True


class TestRunSetsEnvAndPath:
    """Sanity-check that run() places JUnit under .guardkit/autobuild/<id>/."""

    def test_junit_path_layout(self, plugin, tmp_path: Path) -> None:
        captured: list[list[str]] = []

        def _capture(cmd, **kwargs):
            captured.append(list(cmd))
            return subprocess.CompletedProcess(
                args=cmd, returncode=5, stdout="", stderr=""
            )

        with patch("subprocess.run", side_effect=_capture):
            plugin.run([], "TASK-X1", tmp_path, timeout_seconds=5)

        expected = tmp_path / ".guardkit" / "autobuild" / "TASK-X1" / "bdd_TASK-X1.xml"
        assert expected.parent.is_dir()
        junit_args = [a for a in captured[0] if a.startswith("--junitxml=")]
        assert junit_args == [f"--junitxml={expected}"]


class TestRunPropagatesEnvVar:
    """run() MUST pass GUARDKIT_BDD_TASK_ID through to the pytest subprocess.

    Tests the env-var contract at the run() level by capturing the
    ``env=`` kwarg on a mocked ``subprocess.run`` invocation.
    """

    def test_run_sets_guardkit_bdd_task_id_to_active_task(
        self, plugin, tmp_path: Path
    ) -> None:
        captured: list[dict] = []

        def _capture(cmd, **kwargs):
            captured.append(dict(kwargs.get("env") or {}))
            return subprocess.CompletedProcess(
                args=cmd, returncode=5, stdout="", stderr=""
            )

        with patch("subprocess.run", side_effect=_capture):
            plugin.run([], "TASK-ENV-001", tmp_path, timeout_seconds=5)

        assert len(captured) == 1
        assert captured[0].get("GUARDKIT_BDD_TASK_ID") == "TASK-ENV-001", (
            "run() must propagate GUARDKIT_BDD_TASK_ID to the subprocess env "
            "so the canonical conftest can scope the active task "
            "(bdd-per-task-glue.md)"
        )

    def test_run_preserves_existing_environ_entries(
        self, plugin, tmp_path: Path
    ) -> None:
        """The env var injection MUST not strip the rest of os.environ — the
        subprocess needs PATH, HOME, etc. to run pytest at all."""
        captured: list[dict] = []

        def _capture(cmd, **kwargs):
            captured.append(dict(kwargs.get("env") or {}))
            return subprocess.CompletedProcess(
                args=cmd, returncode=5, stdout="", stderr=""
            )

        with patch("subprocess.run", side_effect=_capture):
            plugin.run([], "TASK-ENV-002", tmp_path, timeout_seconds=5)

        # PATH is the canonical "must be there" entry
        assert captured[0].get("PATH"), (
            "run() must merge GUARDKIT_BDD_TASK_ID onto os.environ, not "
            "replace it — subprocess needs PATH to locate python"
        )


# End-to-end C3/C4 exercises live in
# ``tests/bdd/test_pytest_bdd_plugin_end_to_end.py`` (TASK-HMIG-007F).
# They are ``@pytest.mark.slow`` so the default fast suite is unaffected;
# CI runs them with ``pytest -m slow tests/bdd/``.
