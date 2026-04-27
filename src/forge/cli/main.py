"""Click entry point for the ``forge`` CLI (TASK-PSM-008 / TASK-PSM-011).

This module exposes the top-level Click group :func:`main` and registers
every subcommand currently shipped:

* ``forge history`` (TASK-PSM-010 — read-path bypass to SQLite)
* ``forge cancel`` (TASK-PSM-011 — thin wrapper over CliSteeringHandler)
* ``forge skip`` (TASK-PSM-011 — thin wrapper over CliSteeringHandler)

The CLI runtime helpers (:class:`CliRuntime` and :func:`build_cli_runtime`)
live in :mod:`forge.cli.runtime` so subcommand modules can import them
without a circular import.
"""

from __future__ import annotations

from pathlib import Path

import click

from forge.cli import cancel as _cancel
from forge.cli import history as _history
from forge.cli import skip as _skip
from forge.cli.runtime import CliRuntime, build_cli_runtime


@click.group(name="forge")
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to forge.yaml. Defaults to the canonical project file.",
)
@click.pass_context
def main(ctx: click.Context, config_path: Path | None) -> None:
    """Forge — pipeline orchestrator and checkpoint manager CLI."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path


main.add_command(_history.history_cmd)
main.add_command(_cancel.cancel_cmd)
main.add_command(_skip.skip_cmd)


__all__ = ["CliRuntime", "build_cli_runtime", "main"]
