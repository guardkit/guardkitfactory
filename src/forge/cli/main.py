"""Click entry point for the ``forge`` CLI (TASK-PSM-008 / TASK-PSM-011).

This module exposes the top-level Click group :func:`main` and a small
helper :func:`build_cli_runtime` that the cancel/skip wrappers
(TASK-PSM-011) use to obtain wired-up persistence + CLI steering handler
instances without importing the seven SQLite Protocol implementations
themselves.

Subcommands are registered onto :func:`main` at module-import time. The
``forge queue`` / ``forge status`` commands are added by their owning
tasks (TASK-PSM-008 / TASK-PSM-009) — this module currently registers:

* ``forge history`` (TASK-PSM-010 — read-path bypass to SQLite)
* ``forge cancel`` (TASK-PSM-011 — thin wrapper over CliSteeringHandler)
* ``forge skip`` (TASK-PSM-011 — thin wrapper over CliSteeringHandler)

The ``--db`` option mirrors the option already exposed by
``forge.cli.history`` so operators have one consistent way to point the
CLI at a forge.db. ``--config`` is accepted for forward compatibility
with TASK-PSM-008's ForgeConfig loader; the cancel/skip wrappers do not
require it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import click

from forge.adapters.sqlite.connect import connect_writer
from forge.lifecycle.persistence import (
    AsyncTaskCanceller,
    AsyncTaskUpdater,
    SqliteBuildCanceller,
    SqliteBuildResumer,
    SqliteBuildSnapshotReader,
    SqliteLifecyclePersistence,
    SqlitePauseRejectResolver,
    SqliteStageSkipRecorder,
)
from forge.pipeline.cli_steering import CliSteeringHandler


# ---------------------------------------------------------------------------
# CLI runtime — the dependency-injection seam consumed by the wrappers
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CliRuntime:
    """Bundle of wired-up dependencies the cancel/skip wrappers consume.

    Attributes:
        persistence: The lifecycle facade used by the wrappers to
            resolve ``feature_id → build_id`` via
            :meth:`SqliteLifecyclePersistence.find_active_or_recent`.
        cli_steering_handler: The executor-layer handler that owns the
            cancel/skip behavioural rules. The wrappers delegate to
            :meth:`CliSteeringHandler.handle_cancel` /
            :meth:`CliSteeringHandler.handle_skip`.
    """

    persistence: SqliteLifecyclePersistence
    cli_steering_handler: CliSteeringHandler


def _noop_async_call(*_args: object, **_kwargs: object) -> None:
    """No-op pass-through for the AsyncTask{Canceller,Updater} seams.

    ``forge`` is a short-lived CLI process — it does not hold a live
    LangGraph runtime, so ``cancel_async_task`` / ``update_async_task``
    cannot reach an in-flight autobuild from inside the CLI. The
    SQLite-backed snapshot reader does not surface
    :attr:`BuildLifecycle.AUTOBUILD_RUNNING` on its own (see
    :class:`SqliteBuildSnapshotReader` docstring), so this no-op is
    only ever reached when a future composite reader is wired in. We
    fail open rather than failing closed to keep the wrapper thin.
    """
    return None


def _noop_synthetic_injector(_payload: object) -> None:
    """No-op synthetic-injector for :class:`SqlitePauseRejectResolver`.

    The production path wires
    :class:`forge.adapters.nats.synthetic_response_injector.SyntheticResponseInjector`,
    which republishes the synthetic reject onto the approval bus. From
    a short-lived CLI invocation there is no live NATS publisher; the
    SQLite resolution row is still written by the resolver, which is
    the audit-trail invariant the Group D / Group E scenarios depend
    on. Tests inject explicit fakes via :func:`build_cli_runtime`'s
    ``synthetic_injector`` override.
    """
    return None


def build_cli_runtime(
    db_path: Path,
    *,
    synthetic_injector: Callable[[object], object] | None = None,
    async_task_canceller: Callable[[str], object] | None = None,
    async_task_updater: Callable[..., object] | None = None,
) -> CliRuntime:
    """Wire :class:`CliRuntime` against a real SQLite database.

    The seven Protocol implementations the
    :class:`CliSteeringHandler` is composed against are constructed
    here so the cancel/skip wrappers stay under the 60-line ceiling
    declared by TASK-PSM-011 AC-007. The async-task / synthetic-
    injector seams default to no-ops because the SQLite-only CLI can
    never observe a live autobuild — see :func:`_noop_async_call` and
    :func:`_noop_synthetic_injector`.

    Args:
        db_path: Path to ``forge.db``. Must already exist; the writer
            connection is opened against it.
        synthetic_injector: Optional override for the synthetic-reject
            injector. Tests use this to capture the synthetic payload
            without standing up a NATS publisher.
        async_task_canceller: Optional override for the
            ``cancel_async_task`` seam.
        async_task_updater: Optional override for the
            ``update_async_task`` seam.

    Returns:
        A populated :class:`CliRuntime`.
    """
    connection = connect_writer(db_path)
    persistence = SqliteLifecyclePersistence(
        connection=connection,
        db_path=db_path,
    )
    handler = CliSteeringHandler(
        snapshot_reader=SqliteBuildSnapshotReader(persistence),
        pause_reject_resolver=SqlitePauseRejectResolver(
            persistence,
            synthetic_injector=synthetic_injector or _noop_synthetic_injector,
        ),
        async_task_canceller=AsyncTaskCanceller(
            async_task_canceller or _noop_async_call
        ),
        async_task_updater=AsyncTaskUpdater(
            async_task_updater or _noop_async_call
        ),
        build_canceller=SqliteBuildCanceller(persistence),
        skip_recorder=SqliteStageSkipRecorder(persistence),
        build_resumer=SqliteBuildResumer(persistence),
    )
    return CliRuntime(persistence=persistence, cli_steering_handler=handler)


# ---------------------------------------------------------------------------
# Click group
# ---------------------------------------------------------------------------


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


# Subcommand registration — kept at the bottom so each subcommand can
# import :func:`main` if it needs to (none currently do).
from forge.cli import cancel as _cancel  # noqa: E402  (intentional cyclic-aware import)
from forge.cli import history as _history  # noqa: E402
from forge.cli import skip as _skip  # noqa: E402

main.add_command(_history.history_cmd)
main.add_command(_cancel.cancel_cmd)
main.add_command(_skip.skip_cmd)


__all__ = ["CliRuntime", "build_cli_runtime", "main"]
