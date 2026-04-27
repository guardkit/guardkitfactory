"""``forge cancel`` — thin wrapper over :class:`CliSteeringHandler` (TASK-PSM-011).

Resolves ``feature_id|build_id`` via
:meth:`SqliteLifecyclePersistence.find_active_or_recent` (Group C
"cancel of unknown" → exit non-zero) then delegates to
:meth:`CliSteeringHandler.handle_cancel` with ``responder=os.getlogin()``
(Group E audit trail). Behavioural rules live in the handler.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click

from forge.cli.runtime import build_cli_runtime


@click.command(name="cancel")
@click.argument("identifier")
@click.option(
    "--reason",
    default="cli cancel",
    show_default=True,
    help="Reason recorded on the synthetic-reject resolution.",
)
@click.option(
    "--db",
    "db_path",
    type=click.Path(path_type=Path, dir_okay=False, exists=True),
    required=True,
    help="Path to forge.db (SQLite).",
)
def cancel_cmd(identifier: str, reason: str, db_path: Path) -> None:
    """Cancel an active or recent build for ``identifier``."""
    runtime = build_cli_runtime(db_path)
    build = runtime.persistence.find_active_or_recent(identifier)
    if build is None:
        click.echo(
            f"forge cancel: no active or recent build for {identifier!r}",
            err=True,
        )
        sys.exit(2)
    outcome = runtime.cli_steering_handler.handle_cancel(
        build_id=build.build_id,
        reason=reason,
        responder=os.getlogin(),
    )
    click.echo(f"Cancelled {build.build_id}: {outcome.status.value}")
    click.echo(outcome.rationale)


__all__ = ["cancel_cmd"]
