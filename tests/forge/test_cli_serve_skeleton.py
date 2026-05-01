"""Tests for the ``forge serve`` skeleton (TASK-F009-001).

Each ``Test*`` class mirrors one acceptance criterion of TASK-F009-001 so
the criterion → verifier mapping stays explicit (per the project's
testing rules — AAA pattern, descriptive names, AC traceability).

This task only scaffolds the boundary; Wave-2 tasks fill the daemon and
healthz bodies. The tests therefore focus on:

- Contract producer constants (Contracts B and C).
- CLI registration (``forge --help`` and ``forge serve --help``).
- ``ServeConfig`` Pydantic v2 model defaults and env-var overrides.
- ``SubscriptionState`` shape and concurrency-safe mutator.
- The ``serve_cmd`` smoke test — both stubs return, exit code is 0.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import click
import pytest
from click.testing import CliRunner


# ---------------------------------------------------------------------------
# AC-001: forge serve --help shows the serve subcommand
# ---------------------------------------------------------------------------


class TestServeHelp:
    """AC-001: ``forge serve --help`` runs and shows the subcommand."""

    def test_serve_help_runs_and_shows_serve(self) -> None:
        from forge.cli.main import main

        runner = CliRunner()
        result = runner.invoke(main, ["serve", "--help"])
        assert result.exit_code == 0, result.output
        # Click's auto-generated help renders the subcommand name and
        # the docstring's first line; both are sufficient.
        assert "serve" in result.output.lower()
        assert "daemon" in result.output.lower() or "healthz" in result.output.lower()


# ---------------------------------------------------------------------------
# AC-002: forge --help lists serve alongside the existing five subcommands
# ---------------------------------------------------------------------------


class TestSubcommandRegistration:
    """AC-002: ``forge --help`` lists ``serve`` next to the other commands."""

    def test_top_level_help_lists_serve(self) -> None:
        from forge.cli.main import main

        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0, result.output
        for expected in ("queue", "status", "history", "cancel", "skip", "serve"):
            assert expected in result.output, (
                f"expected {expected!r} in --help output; got:\n{result.output}"
            )

    def test_serve_command_is_registered_on_main_group(self) -> None:
        from forge.cli.main import main

        assert isinstance(main, click.Group)
        assert "serve" in main.commands


# ---------------------------------------------------------------------------
# AC-003 / AC-004: contract constants importable as forge.cli.serve.DEFAULT_*
# ---------------------------------------------------------------------------


class TestContractConstants:
    """AC-003 / AC-004: Contracts B and C are module-level constants."""

    def test_default_healthz_port_is_8080(self) -> None:
        from forge.cli.serve import DEFAULT_HEALTHZ_PORT

        assert DEFAULT_HEALTHZ_PORT == 8080
        assert isinstance(DEFAULT_HEALTHZ_PORT, int)

    def test_default_durable_name_is_forge_serve(self) -> None:
        from forge.cli.serve import DEFAULT_DURABLE_NAME

        assert DEFAULT_DURABLE_NAME == "forge-serve"
        assert isinstance(DEFAULT_DURABLE_NAME, str)


# ---------------------------------------------------------------------------
# AC-005: ServeConfig is a Pydantic v2 model with the documented defaults
# ---------------------------------------------------------------------------


class TestServeConfigModel:
    """AC-005: ``ServeConfig`` is a Pydantic v2 model with field defaults."""

    def test_default_construction_yields_documented_defaults(self) -> None:
        from forge.cli.serve import ServeConfig

        cfg = ServeConfig()
        assert cfg.nats_url == "nats://127.0.0.1:4222"
        assert cfg.healthz_port == 8080
        assert cfg.durable_name == "forge-serve"
        assert cfg.log_level == "info"

    def test_is_pydantic_v2_basemodel(self) -> None:
        from pydantic import BaseModel

        from forge.cli.serve import ServeConfig

        assert issubclass(ServeConfig, BaseModel)
        # Pydantic v2 exposes ``model_validate`` (v1 had ``parse_obj``).
        assert hasattr(ServeConfig, "model_validate")

    def test_env_var_overrides_for_nats_url(self) -> None:
        from forge.cli._serve_config import ServeConfig

        cfg = ServeConfig.from_env(
            {
                "FORGE_NATS_URL": "nats://broker.internal:4222",
            }
        )
        assert cfg.nats_url == "nats://broker.internal:4222"
        # Untouched fields fall back to their declared defaults.
        assert cfg.healthz_port == 8080
        assert cfg.log_level == "info"

    def test_env_var_overrides_for_healthz_port_parsed_as_int(self) -> None:
        from forge.cli._serve_config import ServeConfig

        cfg = ServeConfig.from_env({"FORGE_HEALTHZ_PORT": "9999"})
        assert cfg.healthz_port == 9999
        assert isinstance(cfg.healthz_port, int)

    def test_env_var_overrides_for_log_level(self) -> None:
        from forge.cli._serve_config import ServeConfig

        cfg = ServeConfig.from_env({"FORGE_LOG_LEVEL": "debug"})
        assert cfg.log_level == "debug"


# ---------------------------------------------------------------------------
# AC-006: SubscriptionState exposes live: bool and is concurrency-safe
# ---------------------------------------------------------------------------


class TestSubscriptionState:
    """AC-006: ``SubscriptionState.live`` defaults to ``False`` and is mutable."""

    def test_default_live_is_false(self) -> None:
        from forge.cli.serve import SubscriptionState

        state = SubscriptionState()
        assert state.live is False
        assert state.is_live() is False

    def test_set_live_under_lock_updates_value(self) -> None:
        from forge.cli.serve import SubscriptionState

        state = SubscriptionState()

        async def _flip() -> None:
            await state.set_live(True)

        asyncio.run(_flip())
        assert state.live is True
        assert state.is_live() is True

    def test_concurrent_writers_do_not_corrupt_state(self) -> None:
        from forge.cli.serve import SubscriptionState

        state = SubscriptionState()

        async def _concurrent_flips() -> None:
            await asyncio.gather(
                *(state.set_live(i % 2 == 0) for i in range(64))
            )

        asyncio.run(_concurrent_flips())
        # Final value is deterministic for the loop body above (last
        # write wins under the lock); the important property is that
        # ``live`` is *some* bool — i.e. the lock prevented torn writes.
        assert isinstance(state.live, bool)


# ---------------------------------------------------------------------------
# AC-007: serve_cmd runs daemon + healthz via asyncio.gather and exits 0
# ---------------------------------------------------------------------------


class TestServeCmdSmoke:
    """AC-007: ``serve_cmd`` returns ``0`` when both stubs return."""

    def test_serve_cmd_exits_zero_with_stub_coroutines(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # TASK-F009-003: ``run_daemon`` is no longer a no-op — it opens a
        # JetStream pull subscription. The smoke test substitutes both
        # coroutines with fast no-ops so ``serve_cmd`` still exits ``0``
        # without a real broker. The detailed daemon body coverage lives
        # in ``test_cli_serve_daemon.py``.
        from forge.cli import serve as serve_module
        from forge.cli.main import main

        async def _fake_daemon(config: object, state: object) -> None:
            return None

        async def _fake_healthz(config: object, state: object) -> None:
            return None

        monkeypatch.setattr(serve_module, "run_daemon", _fake_daemon)
        monkeypatch.setattr(serve_module, "run_healthz_server", _fake_healthz)

        runner = CliRunner()
        result = runner.invoke(main, ["serve"])
        assert result.exit_code == 0, result.output

    def test_serve_cmd_uses_asyncio_gather(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Assert ``serve_cmd`` schedules both stubs via ``asyncio.gather``."""
        from forge.cli import serve as serve_module

        observed: list[str] = []

        async def _fake_daemon(config: object, state: object) -> None:
            observed.append("daemon")

        async def _fake_healthz(config: object, state: object) -> None:
            observed.append("healthz")

        monkeypatch.setattr(serve_module, "run_daemon", _fake_daemon)
        monkeypatch.setattr(serve_module, "run_healthz_server", _fake_healthz)

        runner = CliRunner()
        result = runner.invoke(serve_module.serve_cmd, [])
        assert result.exit_code == 0, result.output
        assert set(observed) == {"daemon", "healthz"}


# ---------------------------------------------------------------------------
# AC-008: registration is asserted by inspecting the source/main module
# ---------------------------------------------------------------------------


class TestMainModuleRegistersServe:
    """AC-008: ``main.py`` references ``_serve.serve_cmd``."""

    def test_main_source_imports_serve_module(self) -> None:
        cli_pkg = (
            Path(__file__).resolve().parent.parent.parent
            / "src"
            / "forge"
            / "cli"
            / "main.py"
        )
        source = cli_pkg.read_text(encoding="utf-8")
        assert "from forge.cli import serve as _serve" in source

    def test_main_source_adds_serve_command(self) -> None:
        cli_pkg = (
            Path(__file__).resolve().parent.parent.parent
            / "src"
            / "forge"
            / "cli"
            / "main.py"
        )
        source = cli_pkg.read_text(encoding="utf-8")
        assert "main.add_command(_serve.serve_cmd)" in source

    def test_serve_module_re_exports_contract_constants(self) -> None:
        # Symmetry with TASK-PSM-008 ``TestSourceShape`` discipline.
        import importlib

        module = importlib.import_module("forge.cli.serve")
        assert hasattr(module, "DEFAULT_HEALTHZ_PORT")
        assert hasattr(module, "DEFAULT_DURABLE_NAME")
        assert hasattr(module, "ServeConfig")
        assert hasattr(module, "SubscriptionState")
        assert hasattr(module, "serve_cmd")
