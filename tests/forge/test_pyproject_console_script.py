"""Tests for TASK-PSM-012 — ``[project.scripts]`` console-script entry.

These tests verify the acceptance criteria for the ``pyproject.toml``
``console_scripts`` wiring that exposes the ``forge`` binary on
``$PATH`` after ``pip install -e .``:

* AC-001 — ``[project.scripts]`` declares ``forge = "forge.cli.main:main"``.
* AC-003 — ``forge --help`` exits 0 and lists all five subcommands.
* AC-004 — every subcommand's ``--help`` exits 0.
* AC-005 — ``forge status`` against an empty SQLite DB returns exit 0
  with an empty rendered table and never opens a NATS connection.
* AC-006 — neither ``setup.py`` nor ``setup.cfg`` exist (this remains a
  pure ``pyproject.toml`` project per project convention).

The pip-install side of AC-002 is covered indirectly: importing the
dotted-path target named in ``[project.scripts]`` *is* the operation
``pip install -e .`` performs at console-script invocation time. If the
target imports cleanly and is a ``click.Group`` then the install-time
shim will resolve to a working callable.

The "tests follow AAA pattern with descriptive names" project rule is
applied throughout — every test name encodes the input, the action and
the expected outcome.
"""

from __future__ import annotations

import sqlite3
import sys
import tomllib
from pathlib import Path
from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner

from forge.lifecycle.migrations import apply_at_boot

# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

#: Repo root resolved from this test file. The pyproject.toml under test
#: lives two levels above ``tests/forge/``.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PYPROJECT = _REPO_ROOT / "pyproject.toml"

#: All five subcommands the CLI is contractually required to register.
#: The order matches the task description ("queue, status, history,
#: cancel, skip"). Click's ``commands`` mapping is unordered, but the
#: rendered ``--help`` lists them alphabetically — tests only check
#: presence.
_EXPECTED_SUBCOMMANDS: tuple[str, ...] = (
    "queue",
    "status",
    "history",
    "cancel",
    "skip",
)


# ---------------------------------------------------------------------------
# AC-001: pyproject.toml [project.scripts] entry
# ---------------------------------------------------------------------------


class TestPyprojectScriptsEntry:
    """AC-001: ``[project.scripts]`` declares the ``forge`` console script."""

    def test_pyproject_declares_forge_console_script(self) -> None:
        # Arrange.
        pyproject_text = _PYPROJECT.read_bytes()

        # Act.
        data = tomllib.loads(pyproject_text.decode("utf-8"))
        scripts = data.get("project", {}).get("scripts", {})

        # Assert.
        assert (
            "forge" in scripts
        ), "[project.scripts] must declare a ``forge`` entry per TASK-PSM-012"
        assert scripts["forge"] == "forge.cli.main:main", (
            f"console-script must point at forge.cli.main:main; "
            f"got {scripts['forge']!r}"
        )

    def test_console_script_target_resolves_to_a_click_group(self) -> None:
        # Arrange / Act — emulate what the pip-installed shim does:
        # parse the dotted path and import it.
        import importlib

        module = importlib.import_module("forge.cli.main")
        target = getattr(module, "main")

        # Assert — a callable Click group is what the shim invokes.
        assert isinstance(target, click.Group)


# ---------------------------------------------------------------------------
# AC-003: forge --help exits 0 and lists all five subcommands
# ---------------------------------------------------------------------------


class TestTopLevelHelpListsAllSubcommands:
    """AC-003: ``forge --help`` exits 0 and lists every subcommand."""

    def test_forge_help_exits_zero_and_mentions_every_subcommand(self) -> None:
        # Arrange.
        from forge.cli.main import main

        runner = CliRunner()

        # Act.
        result = runner.invoke(main, ["--help"])

        # Assert.
        assert result.exit_code == 0, result.output
        for subcommand in _EXPECTED_SUBCOMMANDS:
            assert (
                subcommand in result.output
            ), f"forge --help must list ``{subcommand}``; got:\n{result.output}"

    def test_main_group_registers_all_five_subcommands(self) -> None:
        # Arrange / Act.
        from forge.cli.main import main

        # Assert — every required name resolves to a Click command.
        for name in _EXPECTED_SUBCOMMANDS:
            assert name in main.commands, (
                f"main group must register ``{name}``; "
                f"registered={sorted(main.commands)!r}"
            )


# ---------------------------------------------------------------------------
# AC-004: every subcommand's --help exits 0
# ---------------------------------------------------------------------------


class TestEverySubcommandHelpExitsZero:
    """AC-004: each ``forge <sub> --help`` invocation exits 0."""

    @pytest.mark.parametrize("subcommand", _EXPECTED_SUBCOMMANDS)
    def test_subcommand_help_exits_zero(self, subcommand: str) -> None:
        # Arrange.
        from forge.cli.main import main

        runner = CliRunner()

        # Act.
        result = runner.invoke(main, [subcommand, "--help"])

        # Assert.
        assert result.exit_code == 0, (
            f"forge {subcommand} --help must exit 0; got exit "
            f"{result.exit_code} with output:\n{result.output}"
        )
        # Click renders ``Usage: forge <sub>`` in its help banner; this
        # is a cheap sanity check that the help text actually rendered
        # rather than failing silently with a zero exit code.
        assert "Usage:" in result.output


# ---------------------------------------------------------------------------
# AC-005: forge status against an empty DB returns an empty table, no NATS
# ---------------------------------------------------------------------------


class TestStatusSmokeAgainstEmptyDb:
    """AC-005: ``forge status`` against an empty SQLite DB renders empty.

    The smoke test must:

    * exit 0,
    * render the table header (no rows),
    * never attempt a NATS connection — the read-side CLI is required
      to be NATS-free per TASK-PSM-009 / TASK-PSM-010 import discipline.
    """

    @pytest.fixture
    def empty_forge_db(self, tmp_path: Path) -> Path:
        """Initialise a fresh schema-applied SQLite DB with zero rows."""
        db_path = tmp_path / "forge.db"
        connection = sqlite3.connect(db_path)
        try:
            apply_at_boot(connection)
        finally:
            connection.close()
        return db_path

    def test_status_against_empty_db_exits_zero_with_header_only(
        self, empty_forge_db: Path
    ) -> None:
        # Arrange.
        from forge.cli.main import main

        runner = CliRunner()

        # Act.
        result = runner.invoke(main, ["status", "--db-path", str(empty_forge_db)])

        # Assert.
        assert result.exit_code == 0, result.output
        # The rendered table header must appear; no data rows are
        # asserted on (an empty DB cannot produce them).
        assert "BUILD" in result.output.upper()
        assert "STATUS" in result.output.upper()

    def test_status_smoke_does_not_attempt_a_nats_connection(
        self, empty_forge_db: Path
    ) -> None:
        # Arrange — patch the NATS publisher used by ``forge queue`` so a
        # call attempt would explode loudly. ``forge status`` must not
        # touch this seam at all.
        from forge.cli import queue as cli_queue
        from forge.cli.main import main

        runner = CliRunner()

        def _trip_wire(*_args: object, **_kwargs: object) -> None:
            raise AssertionError(
                "forge status must NOT publish to NATS — read path is "
                "SQLite-only per TASK-PSM-009 / API-cli.md §4."
            )

        with patch.object(cli_queue, "publish", _trip_wire):
            # Act.
            result = runner.invoke(main, ["status", "--db-path", str(empty_forge_db)])

        # Assert.
        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# AC-006: project still uses pyproject.toml only (no setup.py / setup.cfg)
# ---------------------------------------------------------------------------


class TestPyprojectOnlyBuildSystem:
    """AC-006: project remains pyproject.toml-only."""

    def test_no_legacy_setup_py(self) -> None:
        # Arrange / Act.
        legacy_setup_py = _REPO_ROOT / "setup.py"
        # Assert.
        assert not legacy_setup_py.exists(), (
            "TASK-PSM-012 requires the project remains pyproject.toml-only; "
            f"unexpected setup.py at {legacy_setup_py}"
        )

    def test_no_legacy_setup_cfg(self) -> None:
        # Arrange / Act.
        legacy_setup_cfg = _REPO_ROOT / "setup.cfg"
        # Assert.
        assert not legacy_setup_cfg.exists(), (
            "TASK-PSM-012 requires the project remains pyproject.toml-only; "
            f"unexpected setup.cfg at {legacy_setup_cfg}"
        )


# ---------------------------------------------------------------------------
# AC-002 surrogate: dotted-path is importable (what pip's shim ultimately does)
# ---------------------------------------------------------------------------


class TestEntryPointTargetIsImportable:
    """AC-002 surrogate: the dotted-path the ``pip install`` shim points at
    imports cleanly with no side effects.

    A full ``pip install -e .`` requires a clean virtualenv and is out of
    scope for the pytest collection. We verify the *equivalent invariant*
    — that the dotted path the shim would invoke is resolvable and
    callable — which is precisely what the shim does at runtime.
    """

    def test_main_module_imports_without_raising(self) -> None:
        # Arrange — ensure no cached module, then import fresh.
        sys.modules.pop("forge.cli.main", None)
        # Act.
        import importlib

        module = importlib.import_module("forge.cli.main")
        # Assert.
        assert callable(module.main)
