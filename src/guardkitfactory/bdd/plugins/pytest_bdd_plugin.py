"""PytestBDDPlugin: Python / pytest BDD oracle (parent review §6.3).

Subprocesses pytest with a per-task marker filter and parses the resulting
JUnit XML into :class:`BDDRunResult`. The six C1-C6 contract tests at the
bottom of this module are unit tests of the *interpretation* the plugin
performs on runner output — counters, timeout structure, command argv,
sanitisation — i.e. exactly the §5 failure-pattern hazards the parent
review identified. End-to-end runner integration is exercised downstream
when the plugin is actually invoked by AutoBuild.

The plugin's :func:`discover` probes for ``pytest-bdd`` importability in
the worktree's venv (per the §6.3 example) so a Python project missing the
dep is reported as "no oracle available" rather than crashing at run time.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional
from unittest.mock import patch
from xml.etree import ElementTree as ET

from guardkitfactory.bdd.loader import register
from guardkitfactory.bdd.plugin import (
    BDDPlugin,
    BDDRunResult,
    ContractTestResult,
    Scenario,
    StackProfile,
)


def _sanitise_task_id(task_id: str) -> str:
    """Sanitise task ID per ``bdd-per-task-glue.md``.

    Strip leading ``@``, replace ``:`` with ``_``, replace ``-`` with ``_``.
    """
    return task_id.lstrip("@").replace(":", "_").replace("-", "_")


def _sanitise_slug(slug: str) -> str:
    """Sanitise feature slug per ``bdd-per-task-glue.md`` (hyphens → underscores)."""
    return slug.replace("-", "_")


def _per_task_glue_name(slug: str, task_id: str) -> str:
    """Compute per-task glue filename: ``test_<slug>__<TASK_ID>.py``."""
    return f"test_{_sanitise_slug(slug)}__{_sanitise_task_id(task_id)}.py"


def _marker_for_task(task_id: str) -> str:
    """Compute the pytest marker the per-task filter applies."""
    return f"task_{_sanitise_task_id(task_id)}"


@register
class PytestBDDPlugin(BDDPlugin):
    """BDD oracle for Python projects using ``pytest`` + ``pytest-bdd``."""

    name = "pytest-bdd"

    # ----- Lifecycle ---------------------------------------------------

    @classmethod
    def discover(
        cls,
        stack: StackProfile,
        worktree: Path,
    ) -> Optional["PytestBDDPlugin"]:
        if stack.language != "python":
            return None
        if stack.test_framework != "pytest":
            return None
        venv_python = stack.extras.get("venv_python", sys.executable)
        try:
            subprocess.run(
                [venv_python, "-c", "import pytest_bdd"],
                check=True,
                capture_output=True,
                cwd=worktree,
                timeout=10,
            )
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
        ):
            return None
        return cls()

    #: Name of the env var the canonical conftest honours per
    #: ``.claude/rules/bdd-per-task-glue.md``.
    BDD_TASK_ID_ENV = "GUARDKIT_BDD_TASK_ID"

    def preflight(self, task_id: str, worktree: Path) -> bool:
        """Verify the per-task glue contract + env-var honour (AC-006).

        Checks, in order:

          1. Sanitisation shape — task_id sanitises to a non-empty,
             identifier-shaped marker name.
          2. Worktree exists.
          3. ``features/`` directory exists in the worktree.
          4. **Per-task glue file exists on disk**: at least one file
             matching ``features/**/test_*__<SANITISED_TASK_ID>.py`` per
             the naming contract in ``bdd-per-task-glue.md``. A missing
             glue file means the active task has no scenarios bound, and
             a blind ``-m task_<ID>`` run would silently deselect
             everything (Pattern 2 / absence-of-failure-is-not-success).
          5. **``GUARDKIT_BDD_TASK_ID`` env-var honour**: at least one
             ``features/**/conftest.py`` references the env var. The
             canonical conftest at ``installer/core/templates/common/
             features/conftest.py.template`` in the sibling guardkit
             repo honours this; preflight verifies the project has
             adopted it.

        Returns ``False`` if any check fails so the orchestrator can
        surface "BDD oracle not configured for this task" as Coach
        feedback rather than retrying a guaranteed-zero run.
        """
        sanitised = _sanitise_task_id(task_id)
        if not sanitised:
            return False
        marker = _marker_for_task(task_id)
        if not marker.replace("_", "").isalnum():
            return False
        if not worktree.exists():
            return False

        features_root = worktree / "features"
        if not features_root.is_dir():
            return False

        # Check (4): per-task glue file is present on disk
        glue_pattern = f"test_*__{sanitised}.py"
        glue_matches = list(features_root.rglob(glue_pattern))
        if not glue_matches:
            return False

        # Check (5): some conftest under features/ references the env var
        conftest_files = list(features_root.rglob("conftest.py"))
        try:
            referenced = any(
                self.BDD_TASK_ID_ENV in p.read_text(encoding="utf-8")
                for p in conftest_files
            )
        except OSError:
            return False
        if not referenced:
            return False

        return True

    def run(
        self,
        scenarios: list[Scenario],
        task_id: str,
        worktree: Path,
        *,
        timeout_seconds: int = 600,
    ) -> BDDRunResult:
        """Subprocess pytest with ``-m task_<TASK_ID>`` and parse the JUnit XML.

        On :class:`subprocess.TimeoutExpired`, returns a structured result
        with ``errors=["timeout"]`` (Contract C5) — does NOT raise.
        """
        marker = _marker_for_task(task_id)
        junit_path = (
            worktree / ".guardkit" / "autobuild" / task_id / f"bdd_{task_id}.xml"
        )
        junit_path.parent.mkdir(parents=True, exist_ok=True)

        env = {**os.environ, "GUARDKIT_BDD_TASK_ID": task_id}
        venv_python = env.get("GUARDKIT_BDD_VENV_PYTHON", sys.executable)

        # Note: feature path is "features/" (directory glob), NOT specific
        # .feature filenames — this is Contract C4 (identity-bounded
        # resolution: pytest re-discovers from features/ even if the
        # orchestrator renames a .feature file mid-task; the run is not
        # invalidated by path-string equality misses).
        cmd = [
            venv_python,
            "-m",
            "pytest",
            "features/",
            "-m",
            marker,
            f"--junitxml={junit_path}",
            "-p",
            "no:cacheprovider",
            "--no-header",
        ]

        try:
            proc = subprocess.run(
                cmd,
                cwd=worktree,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return BDDRunResult(
                scenarios_attempted=0,
                scenarios_passed=0,
                scenarios_failed=0,
                scenarios_skipped=0,
                scenarios_errored=0,
                duration_seconds=float(timeout_seconds),
                raw_report_path=None,
                errors=["timeout"],
            )

        return self._parse_junit(junit_path, proc)

    # ----- JUnit XML parsing -------------------------------------------

    @staticmethod
    def _parse_junit(
        junit_path: Path,
        proc: subprocess.CompletedProcess[str],
    ) -> BDDRunResult:
        """Parse a JUnit XML file into a :class:`BDDRunResult`.

        Fail-safe semantics:
          - JUnit missing → ``scenarios_errored=1`` + diagnostic stderr
            capture (Contract C6: no silent zero on runner crash).
          - JUnit unparseable → same.
          - JUnit produced cleanly → faithful counter extraction.
        """
        if not junit_path.exists():
            stderr_tail = (proc.stderr or "")[-1000:]
            return BDDRunResult(
                scenarios_attempted=0,
                scenarios_passed=0,
                scenarios_failed=0,
                scenarios_skipped=0,
                scenarios_errored=1,
                duration_seconds=0.0,
                raw_report_path=None,
                errors=[
                    f"no junit produced; pytest exit={proc.returncode}; "
                    f"stderr={stderr_tail}"
                ],
            )

        try:
            tree = ET.parse(junit_path)
        except ET.ParseError as exc:
            return BDDRunResult(
                scenarios_attempted=0,
                scenarios_passed=0,
                scenarios_failed=0,
                scenarios_skipped=0,
                scenarios_errored=1,
                duration_seconds=0.0,
                raw_report_path=junit_path,
                errors=[f"junit parse error: {exc}"],
            )

        root = tree.getroot()
        # JUnit may be rooted at <testsuites> wrapping <testsuite>, or
        # directly at <testsuite>. pytest emits the former by default.
        if root.tag == "testsuites":
            suite = root.find("testsuite")
            attrib = suite.attrib if suite is not None else {}
        else:
            attrib = root.attrib

        attempted = int(attrib.get("tests", "0"))
        failures = int(attrib.get("failures", "0"))
        errors = int(attrib.get("errors", "0"))
        skipped = int(attrib.get("skipped", "0"))
        duration = float(attrib.get("time", "0"))
        passed = max(attempted - failures - errors - skipped, 0)

        return BDDRunResult(
            scenarios_attempted=attempted,
            scenarios_passed=passed,
            scenarios_failed=failures,
            scenarios_skipped=skipped,
            scenarios_errored=errors,
            duration_seconds=duration,
            raw_report_path=junit_path,
        )

    # ----- Contract tests (C1-C6) --------------------------------------

    def contract_tests(self) -> list[ContractTestResult]:
        """Self-test against the six §5 failure-pattern guards.

        Implementation strategy: each contract test exercises the plugin's
        *interpretation* of runner output (parsing, command construction,
        timeout handling) using synthetic fixtures (constructed JUnit XML,
        mocked subprocess). This keeps registration sub-second and the
        contracts deterministic — end-to-end pytest-bdd integration is
        exercised when the plugin is actually invoked by AutoBuild.
        """
        return [
            self._contract_c1_zero_cardinality(),
            self._contract_c2_per_task_glue_sanitisation(),
            self._contract_c3_parallel_disjoint_markers(),
            self._contract_c4_identity_bounded_resolution(),
            self._contract_c5_timeout_structured(),
            self._contract_c6_collection_error_surfaced(),
        ]

    def _contract_c1_zero_cardinality(self) -> ContractTestResult:
        """C1: JUnit reporting ``tests=0`` is treated as zero-cardinality, not green."""
        with tempfile.TemporaryDirectory() as tmpdir:
            junit_path = Path(tmpdir) / "junit.xml"
            junit_path.write_text(
                '<?xml version="1.0" encoding="utf-8"?>\n'
                '<testsuites>\n'
                '  <testsuite name="pytest" tests="0" failures="0"'
                ' errors="0" skipped="0" time="0.01"/>\n'
                '</testsuites>\n'
            )
            fake_proc = subprocess.CompletedProcess(
                args=[], returncode=5, stdout="", stderr=""
            )
            result = self._parse_junit(junit_path, fake_proc)

        if not result.is_zero_cardinality:
            return ContractTestResult(
                "C1", False,
                f"zero-cardinality JUnit interpreted as non-zero "
                f"(scenarios_attempted={result.scenarios_attempted})",
            )
        if result.errors:
            return ContractTestResult(
                "C1", False,
                f"zero-cardinality should not synthesise errors when JUnit "
                f"reports a clean zero; got errors={result.errors}",
            )
        return ContractTestResult(
            "C1", True,
            "is_zero_cardinality=True, errors=[], no false-green path",
        )

    def _contract_c2_per_task_glue_sanitisation(self) -> ContractTestResult:
        """C2: sanitisation + per-task glue naming match ``bdd-per-task-glue.md``."""
        cases = [
            ("TASK-FG-002", "TASK_FG_002"),
            ("@TASK:FOO-bar", "TASK_FOO_bar"),
            ("TASK-HMIG-007", "TASK_HMIG_007"),
            ("TASK_already_sanitised", "TASK_already_sanitised"),
        ]
        for raw, expected in cases:
            got = _sanitise_task_id(raw)
            if got != expected:
                return ContractTestResult(
                    "C2", False,
                    f"_sanitise_task_id({raw!r}) → {got!r}, expected {expected!r}",
                )

        slug_cases = [
            ("fleet-gateway-common", "fleet_gateway_common"),
            ("simple", "simple"),
            ("multi-hyphen-slug-name", "multi_hyphen_slug_name"),
        ]
        for raw, expected in slug_cases:
            got = _sanitise_slug(raw)
            if got != expected:
                return ContractTestResult(
                    "C2", False,
                    f"_sanitise_slug({raw!r}) → {got!r}, expected {expected!r}",
                )

        # End-to-end glue filename
        glue = _per_task_glue_name("fleet-gateway-common", "TASK-FG-002")
        expected_glue = "test_fleet_gateway_common__TASK_FG_002.py"
        if glue != expected_glue:
            return ContractTestResult(
                "C2", False,
                f"_per_task_glue_name → {glue!r}, expected {expected_glue!r}",
            )

        # Marker derives consistently
        marker = _marker_for_task("TASK-FG-002")
        if marker != "task_TASK_FG_002":
            return ContractTestResult(
                "C2", False,
                f"_marker_for_task → {marker!r}, expected 'task_TASK_FG_002'",
            )

        return ContractTestResult(
            "C2", True,
            "task_id + slug sanitisation match bdd-per-task-glue.md "
            f"({len(cases)} task_id cases, {len(slug_cases)} slug cases)",
        )

    def _contract_c3_parallel_disjoint_markers(self) -> ContractTestResult:
        """C3: parallel tasks produce disjoint marker filters → disjoint scenario sets.

        Verifies the *mechanism* by which disjointness is guaranteed: each
        task_id yields a unique pytest marker, and ``run()`` passes that
        marker to pytest via ``-m``. Two tasks sharing a feature file will
        therefore select non-overlapping scenarios.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            worktree = Path(tmpdir)
            captured: list[list[str]] = []

            def _capture(cmd, **kwargs):
                captured.append(list(cmd))
                return subprocess.CompletedProcess(
                    args=cmd, returncode=5, stdout="", stderr=""
                )

            with patch("subprocess.run", side_effect=_capture):
                self.run([], "TASK-C3-A", worktree, timeout_seconds=5)
                self.run([], "TASK-C3-B", worktree, timeout_seconds=5)

        if len(captured) != 2:
            return ContractTestResult(
                "C3", False,
                f"expected 2 subprocess invocations, captured {len(captured)}",
            )

        def _marker_from_argv(argv: list[str]) -> str | None:
            # The argv contains two ``-m`` flags: one for ``python -m pytest``
            # (Python module invocation) and one for ``pytest -m <marker>``
            # (the per-task filter). The second occurrence is the one we
            # care about — use the last index.
            try:
                last_idx = len(argv) - 1 - argv[::-1].index("-m")
                return argv[last_idx + 1]
            except (ValueError, IndexError):
                return None

        marker_a = _marker_from_argv(captured[0])
        marker_b = _marker_from_argv(captured[1])
        if marker_a is None or marker_b is None:
            return ContractTestResult(
                "C3", False,
                f"pytest invocation missing -m marker; argv_a={captured[0]}, "
                f"argv_b={captured[1]}",
            )
        if marker_a == marker_b:
            return ContractTestResult(
                "C3", False,
                f"two task_ids collapsed to same marker {marker_a!r} — "
                "parallel runs would share scenarios",
            )
        if marker_a != "task_TASK_C3_A" or marker_b != "task_TASK_C3_B":
            return ContractTestResult(
                "C3", False,
                f"marker construction wrong: got ({marker_a!r}, {marker_b!r}), "
                "expected ('task_TASK_C3_A', 'task_TASK_C3_B')",
            )
        return ContractTestResult(
            "C3", True,
            f"two task_ids yield disjoint markers ({marker_a} ≠ {marker_b})",
        )

    def _contract_c4_identity_bounded_resolution(self) -> ContractTestResult:
        """C4: scenario-file rename mid-task is survivable (identity-bounded).

        The plugin invokes pytest against the ``features/`` directory, not
        against specific scenario file paths. Pytest re-discovers .feature
        files in the dir on every run, so an orchestrator-induced rename
        between turns does not invalidate the run by path-string mismatch
        (`.claude/rules/path-string-mismatch-is-not-dishonesty.md`).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            worktree = Path(tmpdir)
            captured: list[list[str]] = []

            def _capture(cmd, **kwargs):
                captured.append(list(cmd))
                return subprocess.CompletedProcess(
                    args=cmd, returncode=5, stdout="", stderr=""
                )

            with patch("subprocess.run", side_effect=_capture):
                self.run(
                    [
                        Scenario(
                            feature_path=worktree / "features" / "renamed_v1.feature",
                            name="ScenarioA",
                            tags=("@task_TASK_C4",),
                            task_id="TASK-C4",
                        )
                    ],
                    "TASK-C4",
                    worktree,
                    timeout_seconds=5,
                )

        if len(captured) != 1:
            return ContractTestResult(
                "C4", False,
                f"expected 1 subprocess invocation, captured {len(captured)}",
            )
        argv = captured[0]
        if "features/" not in argv:
            return ContractTestResult(
                "C4", False,
                "pytest invocation does not target the features/ directory; "
                f"argv={argv}. Specific .feature path-string targeting "
                "would make the plugin brittle to mid-run renames "
                "(path-string-mismatch-is-not-dishonesty.md)",
            )
        # Make sure no specific .feature filename leaked into argv (i.e.
        # the plugin really is using directory-level discovery).
        leaks = [a for a in argv if a.endswith(".feature")]
        if leaks:
            return ContractTestResult(
                "C4", False,
                f"specific .feature paths leaked into pytest argv: {leaks}",
            )
        return ContractTestResult(
            "C4", True,
            "run() targets features/ directory; specific .feature path-strings "
            "do not enter argv, so renames mid-run are survivable",
        )

    def _contract_c5_timeout_structured(self) -> ContractTestResult:
        """C5: ``subprocess.TimeoutExpired`` → structured result, no exception leak."""
        with tempfile.TemporaryDirectory() as tmpdir:
            worktree = Path(tmpdir)

            def _timeout(cmd, **kwargs):
                raise subprocess.TimeoutExpired(cmd=cmd, timeout=2)

            try:
                with patch("subprocess.run", side_effect=_timeout):
                    result = self.run(
                        [], "TASK-C5", worktree, timeout_seconds=2,
                    )
            except subprocess.TimeoutExpired:
                return ContractTestResult(
                    "C5", False,
                    "TimeoutExpired leaked from run() — should be caught and "
                    "surfaced via BDDRunResult.errors=['timeout']",
                )
            except Exception as exc:  # noqa: BLE001
                return ContractTestResult(
                    "C5", False,
                    f"unexpected exception leaked from run(): {type(exc).__name__}: {exc}",
                )

        if result.errors != ["timeout"]:
            return ContractTestResult(
                "C5", False,
                f"expected errors=['timeout'], got errors={result.errors}",
            )
        if result.scenarios_attempted != 0:
            return ContractTestResult(
                "C5", False,
                f"timeout should report 0 attempted, got "
                f"{result.scenarios_attempted}",
            )
        return ContractTestResult(
            "C5", True,
            "TimeoutExpired → BDDRunResult(errors=['timeout']), no exception leak",
        )

    def _contract_c6_collection_error_surfaced(self) -> ContractTestResult:
        """C6: collection error / undefined step → ``scenarios_errored > 0``.

        Two sub-cases the plugin must handle:
          (a) JUnit XML reports ``errors > 0`` cleanly.
          (b) JUnit XML is missing entirely (pytest crashed pre-XML emit).
        Both MUST result in ``scenarios_errored > 0`` — never silent zero.
        """
        # Sub-case (a): JUnit with errors > 0
        with tempfile.TemporaryDirectory() as tmpdir:
            junit_path = Path(tmpdir) / "junit.xml"
            junit_path.write_text(
                '<?xml version="1.0" encoding="utf-8"?>\n'
                '<testsuites>\n'
                '  <testsuite name="pytest" tests="1" failures="0"'
                ' errors="1" skipped="0" time="0.01"/>\n'
                '</testsuites>\n'
            )
            fake_proc = subprocess.CompletedProcess(
                args=[], returncode=2, stdout="", stderr="undefined step"
            )
            result_a = self._parse_junit(junit_path, fake_proc)

        if result_a.scenarios_errored <= 0:
            return ContractTestResult(
                "C6", False,
                f"JUnit errors=1 not surfaced; got "
                f"scenarios_errored={result_a.scenarios_errored}",
            )

        # Sub-case (b): JUnit missing → fallback to errored=1
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_junit = Path(tmpdir) / "never_emitted.xml"
            fake_proc = subprocess.CompletedProcess(
                args=[], returncode=4, stdout="", stderr="collection failed"
            )
            result_b = self._parse_junit(missing_junit, fake_proc)

        if result_b.scenarios_errored <= 0:
            return ContractTestResult(
                "C6", False,
                "missing JUnit XML not surfaced as errored; got "
                f"scenarios_errored={result_b.scenarios_errored}. "
                "Silent zero on runner crash is the absence-of-failure-"
                "is-not-success hazard.",
            )
        if not result_b.errors:
            return ContractTestResult(
                "C6", False,
                "missing JUnit XML lacks diagnostic in BDDRunResult.errors",
            )
        return ContractTestResult(
            "C6", True,
            f"collection error surfaced both ways: JUnit errors=1 → "
            f"scenarios_errored={result_a.scenarios_errored}; missing JUnit "
            f"→ scenarios_errored={result_b.scenarios_errored}",
        )


__all__ = [
    "PytestBDDPlugin",
    "_marker_for_task",
    "_per_task_glue_name",
    "_sanitise_slug",
    "_sanitise_task_id",
]
