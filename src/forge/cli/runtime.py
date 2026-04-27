"""CLI runtime wiring for the cancel/skip wrappers (TASK-PSM-011).

Splits :class:`CliRuntime` and :func:`build_cli_runtime` out of
:mod:`forge.cli.main` so the cancel/skip subcommand modules can import
the runtime helper without a circular import (``main`` imports
``cancel`` / ``skip`` to register them on the Click group).

The runtime owns no behavioural rules — it only constructs the SQLite
adapters that satisfy the seven Protocols
:class:`~forge.pipeline.cli_steering.CliSteeringHandler` is composed
against. Async-task / synthetic-injector seams default to no-ops
because a short-lived CLI process cannot reach a live LangGraph
runtime; tests inject explicit fakes via the kwargs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

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


@dataclass(frozen=True, slots=True)
class CliRuntime:
    """Bundle of wired-up dependencies the cancel/skip wrappers consume.

    Attributes:
        persistence: The lifecycle facade used to resolve
            ``identifier → build_id`` via
            :meth:`SqliteLifecyclePersistence.find_active_or_recent`.
        cli_steering_handler: The executor-layer handler that owns the
            cancel/skip behavioural rules.
    """

    persistence: SqliteLifecyclePersistence
    cli_steering_handler: CliSteeringHandler


def _noop_async_call(*_args: object, **_kwargs: object) -> None:
    """No-op pass-through for the AsyncTask{Canceller,Updater} seams."""
    return None


def _noop_synthetic_injector(_payload: object) -> None:
    """No-op synthetic-injector for :class:`SqlitePauseRejectResolver`."""
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
    declared by TASK-PSM-011 AC-007.

    Args:
        db_path: Path to ``forge.db``. Must already exist.
        synthetic_injector: Optional override for the synthetic-reject
            injector (tests use this to capture the synthetic payload).
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
        async_task_updater=AsyncTaskUpdater(async_task_updater or _noop_async_call),
        build_canceller=SqliteBuildCanceller(persistence),
        skip_recorder=SqliteStageSkipRecorder(persistence),
        build_resumer=SqliteBuildResumer(persistence),
    )
    return CliRuntime(persistence=persistence, cli_steering_handler=handler)


__all__ = ["CliRuntime", "build_cli_runtime"]
