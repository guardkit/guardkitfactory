"""``forge history`` command — read-path bypass to SQLite (TASK-PSM-010).

Implements ``forge history [--feature FEAT-XXX] [--limit N] [--since DATE]
[--format table|json|md]`` per ``API-cli.md §5``.

**Import discipline**: this module MUST NOT import from
``forge.adapters.nats.*``. The CLI read path is a SQLite-only bypass per
ADR-ARCH-013. Any NATS coupling here would defeat the bypass and break the
"forge history works without a running Forge process" property.

The command surface and behaviour:

* ``forge history`` (no args) — last N builds where N is taken from
  ``ForgeConfig.queue.default_history_limit`` (default 50).
* ``--feature FEAT-XXX`` — filter to one feature; every matching build's
  ``stage_log`` is expanded in the markdown / json output.
* ``--limit N`` — clamp results to N. The persistence layer caps this at
  ``MAX_HISTORY_LIMIT`` (1000) to prevent unbounded queries.
* ``--since 2026-04-20`` — filter to builds whose ``queued_at >= date``
  (interpreted as midnight UTC).
* ``--format table|json|md`` — table is the default human view, ``md``
  emits the structure shown in ``API-cli.md §5.3``, ``json`` emits a
  machine-readable JSON array suitable for piping.

The command is exposed both as a Click command (``history_cmd``) and as a
plain ``run_history`` callable so unit tests can drive the rendering path
without invoking the Click runner. Both paths share the same rendering
helpers, so the contract between them is the rendered string.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import click

from forge.adapters.sqlite import read_only_connect
from forge.config.models import ForgeConfig, QueueConfig
from forge.lifecycle.persistence import (
    BuildRow,
    SqliteLifecyclePersistence,
    StageLogEntry,
)


# ---------------------------------------------------------------------------
# Public types and constants
# ---------------------------------------------------------------------------


#: Allowed values for ``--format``. Kept explicit so Click can build a
#: ``click.Choice`` and the json-format renderer can compare against the same
#: source of truth as the table renderer.
SUPPORTED_FORMATS: tuple[str, ...] = ("table", "json", "md")


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------


def parse_since(raw: str) -> datetime:
    """Parse a ``--since`` argument into a timezone-aware UTC datetime.

    The CLI accepts a bare ISO date (``2026-04-20``) for ergonomics. We
    promote it to ``2026-04-20T00:00:00+00:00`` so SQLite ISO-8601 string
    comparisons against ``builds.queued_at`` (also stored UTC ISO-8601)
    work without timezone surprises.

    A full ISO-8601 datetime is also accepted; if it is naive, UTC is
    assumed.
    """
    if not raw:
        raise click.BadParameter("--since must be a non-empty ISO date")
    candidate = raw.strip()
    # Bare-date ergonomic form per the task implementation notes.
    if "T" not in candidate and " " not in candidate:
        candidate = f"{candidate}T00:00:00+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise click.BadParameter(
            f"--since: invalid ISO date {raw!r}: {exc}"
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


# ---------------------------------------------------------------------------
# Filtering / fetching
# ---------------------------------------------------------------------------


def _filter_since(rows: Iterable[BuildRow], since: datetime | None) -> list[BuildRow]:
    """Return only rows whose ``queued_at >= since`` (no-op when ``since`` is None).

    Filtering happens in Python so the persistence layer's read API stays
    minimal — ``read_history(limit, feature_id)`` does not need to grow a
    third filter column. The list is materialised here.
    """
    if since is None:
        return list(rows)
    return [row for row in rows if row.queued_at >= since]


def fetch_history(
    persistence: SqliteLifecyclePersistence,
    *,
    limit: int,
    feature_id: str | None,
    since: datetime | None,
    include_stages: bool,
) -> list[tuple[BuildRow, list[StageLogEntry]]]:
    """Return ``(BuildRow, stage_log)`` pairs ordered newest-first.

    ``include_stages`` controls whether per-build ``stage_log`` is read.
    The table renderer never needs stages; the markdown / json renderers
    need them when ``--feature`` is supplied or when the user asked for
    ``--format md`` (stage list is part of §5.3's structure).

    The returned list preserves ``queued_at DESC`` ordering from
    :meth:`SqliteLifecyclePersistence.read_history`.
    """
    rows = persistence.read_history(limit=limit, feature_id=feature_id)
    rows = _filter_since(rows, since)
    if not include_stages:
        return [(row, []) for row in rows]
    return [(row, persistence.read_stages(row.build_id)) for row in rows]


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def _format_dt(value: datetime | None) -> str:
    """Render a UTC datetime as ``YYYY-MM-DD HH:MM:SS UTC`` or ``-`` when None."""
    if value is None:
        return "-"
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def _duration(start: datetime | None, end: datetime | None) -> str:
    """Render the elapsed time as ``Xh YYm`` or ``-`` if endpoints are missing."""
    if start is None or end is None:
        return "-"
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    delta = end - start
    total_seconds = max(int(delta.total_seconds()), 0)
    hours, rem = divmod(total_seconds, 3600)
    minutes, _ = divmod(rem, 60)
    return f"{hours}h {minutes:02d}m"


def render_table(pairs: list[tuple[BuildRow, list[StageLogEntry]]]) -> str:
    """Render rows as a fixed-column ASCII table (default ``--format``).

    Stage entries are ignored — the table view is intentionally narrow.
    """
    if not pairs:
        return "No builds found.\n"

    header = f"{'BUILD':<48} {'FEATURE':<14} {'STATUS':<11} {'QUEUED':<22}"
    lines = [header, "-" * len(header)]
    for row, _stages in pairs:
        lines.append(
            f"{row.build_id:<48} {row.feature_id:<14} "
            f"{row.status.value:<11} {_format_dt(row.queued_at):<22}"
        )
    return "\n".join(lines) + "\n"


def render_json(pairs: list[tuple[BuildRow, list[StageLogEntry]]]) -> str:
    """Render rows as a JSON array suitable for piping into tooling.

    Each element has the BuildRow fields plus a ``stage_log`` array (empty
    when stages were not requested). Datetimes are emitted as ISO-8601
    strings so the output round-trips through ``json.loads`` unchanged.
    """
    payload: list[dict[str, Any]] = []
    for row, stages in pairs:
        record = row.model_dump(mode="json")
        record["stage_log"] = [stage.model_dump(mode="json") for stage in stages]
        payload.append(record)
    return json.dumps(payload, indent=2, default=str) + "\n"


def render_markdown(
    pairs: list[tuple[BuildRow, list[StageLogEntry]]],
    *,
    feature_id: str | None,
) -> str:
    """Render rows as the markdown structure shown in ``API-cli.md §5.3``.

    Per build:
      * ``## <build_id> — <STATUS> (Xh YYm)``
      * ``Started:``/``Finished:`` lines
      * Optional ``PR:`` line
      * ``### Stages`` followed by ``- HH:MM:SS — <stage> <STATUS> [score=…]``
    """
    title = f"# Forge history — {feature_id}" if feature_id else "# Forge history"
    sections: list[str] = [title, ""]

    if not pairs:
        sections.append("_No builds found._")
        return "\n".join(sections) + "\n"

    for row, stages in pairs:
        duration = _duration(row.started_at, row.completed_at)
        heading = f"## {row.build_id} — {row.status.value} ({duration})"
        sections.append(heading)
        sections.append(f"Started: {_format_dt(row.started_at)}")
        sections.append(f"Finished: {_format_dt(row.completed_at)}")
        if row.pr_url:
            sections.append(f"PR: {row.pr_url}")
        sections.append("")
        sections.append("### Stages")
        if not stages:
            sections.append("- _no stages recorded_")
        else:
            for stage in stages:
                ts = stage.started_at
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                ts_str = ts.astimezone(UTC).strftime("%H:%M:%S")
                score = (
                    f"  score={stage.coach_score:.2f}"
                    if stage.coach_score is not None
                    else ""
                )
                sections.append(
                    f"- {ts_str} — {stage.stage_label:<32} {stage.status}{score}"
                )
        sections.append("")
    return "\n".join(sections) + "\n"


# ---------------------------------------------------------------------------
# Top-level entrypoint (used by the Click command and unit tests)
# ---------------------------------------------------------------------------


def _resolve_default_limit(config: ForgeConfig | QueueConfig | None) -> int:
    """Return the default limit drawn from config (per AC — never hardcoded).

    The CLI accepts either a full :class:`ForgeConfig` (the production
    case) or a bare :class:`QueueConfig` (test-friendly). When ``None`` is
    passed the loader has not run yet — fall back to the QueueConfig
    default which is itself the canonical 50.
    """
    if config is None:
        return QueueConfig().default_history_limit
    if isinstance(config, QueueConfig):
        return config.default_history_limit
    return config.queue.default_history_limit


def run_history(
    *,
    db_path: Path,
    config: ForgeConfig | QueueConfig | None,
    feature_id: str | None,
    limit: int | None,
    since: str | None,
    output_format: str,
) -> str:
    """Execute the history command and return the rendered string.

    This is the seam unit tests drive directly, bypassing Click. It opens
    a read-only SQLite connection against ``db_path``, fetches the
    history, and renders it in the requested format.
    """
    if output_format not in SUPPORTED_FORMATS:
        raise click.BadParameter(
            f"--format must be one of {SUPPORTED_FORMATS}; got {output_format!r}"
        )

    effective_limit = (
        limit if limit is not None else _resolve_default_limit(config)
    )
    if effective_limit < 1:
        raise click.BadParameter("--limit must be a positive integer")

    parsed_since = parse_since(since) if since else None

    connection = read_only_connect(db_path)
    try:
        connection.row_factory = sqlite3.Row
        persistence = SqliteLifecyclePersistence(
            connection=connection,
            db_path=db_path,
        )
        include_stages = output_format != "table"
        pairs = fetch_history(
            persistence,
            limit=effective_limit,
            feature_id=feature_id,
            since=parsed_since,
            include_stages=include_stages,
        )
    finally:
        connection.close()

    if output_format == "table":
        return render_table(pairs)
    if output_format == "json":
        return render_json(pairs)
    return render_markdown(pairs, feature_id=feature_id)


# ---------------------------------------------------------------------------
# Click command
# ---------------------------------------------------------------------------


@click.command(name="history")
@click.option(
    "--feature",
    "feature_id",
    type=str,
    default=None,
    help="Filter to a single feature_id (e.g. FEAT-A1B2).",
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help=(
        "Maximum rows to return. Defaults to "
        "ForgeConfig.queue.default_history_limit (50)."
    ),
)
@click.option(
    "--since",
    type=str,
    default=None,
    help="Filter to builds with queued_at >= ISO date (e.g. 2026-04-20).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(SUPPORTED_FORMATS, case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--db",
    "db_path",
    type=click.Path(path_type=Path, dir_okay=False, exists=True),
    required=True,
    help="Path to forge.db (SQLite).",
)
@click.pass_context
def history_cmd(
    ctx: click.Context,
    feature_id: str | None,
    limit: int | None,
    since: str | None,
    output_format: str,
    db_path: Path,
) -> None:
    """Show build + stage history (read-path bypass to SQLite).

    See ``docs/design/contracts/API-cli.md §5`` for the canonical spec.
    """
    config = ctx.obj if isinstance(ctx.obj, (ForgeConfig, QueueConfig)) else None
    rendered = run_history(
        db_path=db_path,
        config=config,
        feature_id=feature_id,
        limit=limit,
        since=since,
        output_format=output_format.lower(),
    )
    click.echo(rendered, nl=False)


__all__ = [
    "SUPPORTED_FORMATS",
    "fetch_history",
    "history_cmd",
    "parse_since",
    "render_json",
    "render_markdown",
    "render_table",
    "run_history",
]
