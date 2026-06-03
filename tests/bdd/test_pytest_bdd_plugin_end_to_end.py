"""End-to-end exercises for PytestBDDPlugin (TASK-HMIG-007F AC-005 / AC-007).

Mechanism vs property:

* The argv-inspection unit tests in ``test_pytest_bdd_plugin_contracts.py``
  verify the *mechanism* (what we send to pytest) — they run sub-second
  and are part of the default fast suite.
* The tests in this module verify the *property* (what we get back from
  pytest) by spawning a real ``python -m pytest features/ -m task_<ID>
  --junitxml=...`` subprocess against a synthetic worktree.

Both layers matter — the argv-inspection layer would still pass if
pytest-bdd's marker filter or directory-glob discovery were broken,
because nothing actually invokes the runner. These end-to-end tests are
the truth guard for the C3 (parallel-disjoint) and C4 (rename-survives)
contracts.

The tests are marked ``@pytest.mark.slow`` so the default fast suite is
unaffected (``pytest`` skips them via ``addopts = "-m 'not slow'"`` in
``pyproject.toml``). CI runs them explicitly with
``pytest -m slow tests/bdd/``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from guardkitfactory.bdd.plugins.pytest_bdd_plugin import PytestBDDPlugin


@pytest.fixture()
def plugin() -> PytestBDDPlugin:
    return PytestBDDPlugin()


# ---------------------------------------------------------------------------
# C3 — parallel disjoint scenarios (end-to-end)
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestC3DisjointScenarios:
    """C3 property: same .feature file, two task_ids → disjoint scenario sets.

    AC-005: writes ``features/parallel.feature`` with two task-tagged
    scenarios + a ``features/conftest.py`` that honours
    ``GUARDKIT_BDD_TASK_ID`` + two per-task glue files. Invokes
    ``PytestBDDPlugin.run`` twice (once per task_id) via a real
    subprocess; asserts each run reports ``scenarios_attempted == 1`` and
    the two scenario sets are disjoint.

    A run that picks up both scenarios would indicate the pytest marker
    filter is not enforcing per-task isolation, which would re-open the
    parent review's §5 Pattern 3 hazard
    ("coach-gate-short-circuit-cascades when parallel tasks share
    features").
    """

    @pytest.fixture()
    def parallel_worktree(self, tmp_path: Path) -> Path:
        features = tmp_path / "features"
        features.mkdir()
        # Conftest honours GUARDKIT_BDD_TASK_ID per bdd-per-task-glue.md.
        (features / "conftest.py").write_text(
            "import os\n"
            "_BDD_TASK_ID_ENV = 'GUARDKIT_BDD_TASK_ID'\n"
            "_active_task = os.environ.get(_BDD_TASK_ID_ENV)\n"
        )
        # One feature file, two task-tagged scenarios.
        (features / "parallel.feature").write_text(
            "Feature: Parallel-task verification\n"
            "\n"
            "  @task_TASK_C3_A\n"
            "  Scenario: scenario for task A\n"
            "    Given a step for A\n"
            "\n"
            "  @task_TASK_C3_B\n"
            "  Scenario: scenario for task B\n"
            "    Given a step for B\n"
        )
        # Per-task glue file A: binds only "scenario for task A".
        (features / "test_parallel__TASK_C3_A.py").write_text(
            "from pytest_bdd import scenario, given\n"
            "\n"
            "\n"
            "@scenario('parallel.feature', 'scenario for task A')\n"
            "def test_a_scenario():\n"
            "    pass\n"
            "\n"
            "\n"
            "@given('a step for A')\n"
            "def _step_a():\n"
            "    pass\n"
        )
        # Per-task glue file B: binds only "scenario for task B".
        (features / "test_parallel__TASK_C3_B.py").write_text(
            "from pytest_bdd import scenario, given\n"
            "\n"
            "\n"
            "@scenario('parallel.feature', 'scenario for task B')\n"
            "def test_b_scenario():\n"
            "    pass\n"
            "\n"
            "\n"
            "@given('a step for B')\n"
            "def _step_b():\n"
            "    pass\n"
        )
        return tmp_path

    def test_parallel_runs_pick_disjoint_scenarios(
        self, plugin: PytestBDDPlugin, parallel_worktree: Path
    ) -> None:
        result_a = plugin.run(
            [], "TASK-C3-A", parallel_worktree, timeout_seconds=60,
        )
        result_b = plugin.run(
            [], "TASK-C3-B", parallel_worktree, timeout_seconds=60,
        )

        assert result_a.scenarios_attempted == 1, (
            f"Task A should attempt exactly 1 scenario; got attempted="
            f"{result_a.scenarios_attempted}, passed={result_a.scenarios_passed}, "
            f"failed={result_a.scenarios_failed}, "
            f"errored={result_a.scenarios_errored}, errors={result_a.errors}"
        )
        assert result_a.scenarios_passed == 1, (
            f"Task A scenario should pass; got passed={result_a.scenarios_passed}, "
            f"failed={result_a.scenarios_failed}, "
            f"errored={result_a.scenarios_errored}"
        )

        assert result_b.scenarios_attempted == 1, (
            f"Task B should attempt exactly 1 scenario; got attempted="
            f"{result_b.scenarios_attempted}, errors={result_b.errors}"
        )
        assert result_b.scenarios_passed == 1, (
            f"Task B scenario should pass; got passed={result_b.scenarios_passed}, "
            f"failed={result_b.scenarios_failed}, "
            f"errored={result_b.scenarios_errored}"
        )

        # Disjointness: total attempted across both runs = 2 (1 each), not
        # 4 (2 each). 4 would mean the marker filter failed to isolate.
        total = result_a.scenarios_attempted + result_b.scenarios_attempted
        assert total == 2, (
            f"Disjoint-sets violated: parallel runs attempted {total} "
            "scenarios in total (expected 2 — one per task). A run that "
            "picks up both scenarios indicates the marker filter is not "
            "enforcing per-task isolation."
        )


# ---------------------------------------------------------------------------
# C4 — identity-bounded resolution survives rename (end-to-end)
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestC4SurvivesRename:
    """C4 property: mid-task ``.feature`` rename does not invalidate the run.

    AC-007: writes ``features/original.feature`` with one task-tagged
    scenario; runs the plugin once; renames the file to
    ``features/renamed.feature`` (plain filesystem move, not git);
    runs the plugin again. Both runs must report
    ``scenarios_attempted >= 1`` and ``scenarios_errored == 0`` — the
    second run re-discovers the (now-renamed) feature via the
    ``features/`` directory glob, not via a remembered file path.

    Failure here re-opens the
    ``.claude/rules/path-string-mismatch-is-not-dishonesty.md`` hazard.
    """

    def test_rename_does_not_invalidate_subsequent_run(
        self, plugin: PytestBDDPlugin, tmp_path: Path
    ) -> None:
        features = tmp_path / "features"
        features.mkdir()
        # Conftest honours GUARDKIT_BDD_TASK_ID per bdd-per-task-glue.md.
        (features / "conftest.py").write_text(
            "import os\n"
            "_BDD_TASK_ID_ENV = 'GUARDKIT_BDD_TASK_ID'\n"
            "_active_task = os.environ.get(_BDD_TASK_ID_ENV)\n"
        )
        original = features / "original.feature"
        original.write_text(
            "Feature: Initial feature for C4 rename test\n"
            "\n"
            "  @task_TASK_C4_RENAME\n"
            "  Scenario: the scenario\n"
            "    Given a step\n"
        )
        # Glue uses directory-glob via scenarios('./') so the run is
        # robust to mid-task file renames (identity-bounded resolution).
        (features / "test_original__TASK_C4_RENAME.py").write_text(
            "from pytest_bdd import scenarios, given\n"
            "\n"
            "scenarios('./')\n"
            "\n"
            "\n"
            "@given('a step')\n"
            "def _step():\n"
            "    pass\n"
        )

        # First invocation: feature at original.feature.
        result_before = plugin.run(
            [], "TASK-C4-RENAME", tmp_path, timeout_seconds=60,
        )
        assert result_before.scenarios_attempted >= 1, (
            f"Before rename: expected >=1 scenario, got attempted="
            f"{result_before.scenarios_attempted}, errored="
            f"{result_before.scenarios_errored}, errors={result_before.errors}"
        )
        assert result_before.scenarios_errored == 0, (
            f"Before rename: expected zero errored scenarios; got errored="
            f"{result_before.scenarios_errored}, errors={result_before.errors}"
        )
        assert result_before.scenarios_passed >= 1, (
            f"Before rename: expected scenario to pass; got passed="
            f"{result_before.scenarios_passed}, "
            f"failed={result_before.scenarios_failed}"
        )

        # Orchestrator-induced rename mid-task (simulates the
        # path-string-mismatch-is-not-dishonesty scenario). Plain
        # filesystem move keeps the test hermetic — no git side-effects.
        renamed = features / "renamed.feature"
        original.rename(renamed)
        assert not original.exists()
        assert renamed.exists()

        # Second invocation: scenarios('./') re-discovers from features/.
        result_after = plugin.run(
            [], "TASK-C4-RENAME", tmp_path, timeout_seconds=60,
        )
        assert result_after.scenarios_attempted >= 1, (
            "Identity-bounded resolution failed: after the .feature file "
            "was renamed, pytest-bdd should re-discover via the features/ "
            "directory glob and still attempt the task's scenario. "
            f"Got attempted={result_after.scenarios_attempted}, errored="
            f"{result_after.scenarios_errored}, errors={result_after.errors}"
        )
        assert result_after.scenarios_errored == 0, (
            "Identity-bounded resolution failed: after rename, the run "
            f"reported errored scenarios. Got errored="
            f"{result_after.scenarios_errored}, errors={result_after.errors}"
        )
        assert result_after.scenarios_passed >= 1, (
            "Identity-bounded resolution failed: after rename, the scenario "
            f"should still pass. Got passed={result_after.scenarios_passed}, "
            f"failed={result_after.scenarios_failed}, "
            f"errored={result_after.scenarios_errored}"
        )
