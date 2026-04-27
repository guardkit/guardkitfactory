"""``forge queue`` — write-then-publish enqueue command (TASK-PSM-008).

Behavioural contract (``API-cli.md §3.3``)
------------------------------------------

The ``forge queue`` command implements the **write-then-publish**
discipline (concern ``sc_002`` from TASK-REV-3EEE). The flow is, in order:

1. **Validate ``feature_id``** through
   :func:`forge.lifecycle.identifiers.validate_feature_id` (concern
   ``sc_003``). On :class:`InvalidIdentifierError` we exit ``4`` *before*
   any SQLite write or NATS publish runs — no side effects.
2. **Allowlist check** — refuse with exit ``2`` when ``--repo`` is not in
   ``ForgeConfig.queue.repo_allowlist`` (Group C "path-allowlist
   refused"). An empty allowlist (the schema default) means "no
   restriction" per :class:`forge.config.models.QueueConfig`.
3. **Merge defaults** — CLI flags override ``ForgeConfig.queue.default_*``.
4. **Build the wire payload** —
   :class:`nats_core.events.BuildQueuedPayload` with
   ``triggered_by="cli"`` and ``originating_user`` resolved from
   :func:`os.getlogin` (with a tolerant fallback for unattended
   environments where ``getlogin()`` raises :class:`OSError`).
5. **Active in-flight check** — short-circuit with exit ``3`` when
   :meth:`SqliteLifecyclePersistence.exists_active_build` returns
   ``True`` (Group C "active in-flight duplicate").
6. **Write the SQLite row first** via
   :meth:`SqliteLifecyclePersistence.record_pending_build`. A
   :class:`DuplicateBuildError` raised by the unique
   ``(feature_id, correlation_id)`` index translates to exit ``3``
   (Group B "duplicate refused").
7. **Then publish** the
   :class:`nats_core.envelope.MessageEnvelope` to subject
   ``pipeline.build-queued.{feature_id}``. The publisher seam is
   :func:`publish` — production wires it to a real NATS connection;
   tests monkey-patch it.
8. **On publish failure** — *do not* roll back the SQLite row. Print a
   diagnostic on stderr that mentions both ``"publish failed"`` and the
   ``"messaging-layer"`` cause (Group H), then exit ``1``. Pipeline
   truth lives in SQLite; the JetStream stream is a derived projection
   and the on-boot reconciler (TASK-PSM-007) redrives any orphaned
   rows.

Test seams
----------

Two module-level callables make the side-effect-bearing steps mockable
without a NATS broker or a real ``forge.db`` file:

- :func:`make_persistence` — returns a
  :class:`SqliteLifecyclePersistence` (or any duck-typed equivalent).
- :func:`publish` — synchronous wrapper around the async NATS publish.

Both seams default to production-correct implementations; they are *not*
stubs. The :class:`PublishError` raised by the default publisher is the
single error-shape the queue command translates into exit code ``1``.
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import click

from forge.config.models import ForgeConfig
from forge.lifecycle.identifiers import (
    InvalidIdentifierError,
    validate_feature_id,
)
from forge.lifecycle.persistence import (
    DuplicateBuildError,
    SqliteLifecyclePersistence,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exit-code constants — see ``API-cli.md §3.3``
# ---------------------------------------------------------------------------

#: Successful enqueue.
EXIT_OK = 0
#: Generic CLI error / messaging-layer publish failure (Group G + Group H).
EXIT_PUBLISH_FAILED = 1
#: Configuration / authorization refusal — repo not in allowlist (Group C).
EXIT_PATH_REFUSED = 2
#: Duplicate refused — either ``(feature_id, correlation_id)`` collision
#: (Group B) or an active in-flight build for the feature (Group C).
EXIT_DUPLICATE = 3
#: Identifier validation failed — traversal/null-byte/disallowed-char
#: (concern ``sc_003`` / Group A). NEW exit code added by TASK-PSM-008.
EXIT_INVALID_IDENTIFIER = 4

#: Default location of the SQLite substrate when ``$FORGE_DB_PATH`` is
#: unset. Honours the convention used by every other Forge subsystem.
DEFAULT_DB_PATH = Path("~/.forge/forge.db")

#: NATS subject family for build-queued events
#: (``API-nats-pipeline-events.md §3``).
BUILD_QUEUED_SUBJECT_PREFIX = "pipeline.build-queued"

#: Source-id stamped onto every envelope this CLI emits. Distinct from
#: the ``"forge"`` value used by the agent-runtime publisher so
#: subscribers can tell CLI-originated builds from runtime-originated
#: ones.
SOURCE_ID = "forge-cli"


__all__ = [
    "BUILD_QUEUED_SUBJECT_PREFIX",
    "DEFAULT_DB_PATH",
    "EXIT_DUPLICATE",
    "EXIT_INVALID_IDENTIFIER",
    "EXIT_OK",
    "EXIT_PATH_REFUSED",
    "EXIT_PUBLISH_FAILED",
    "PublishError",
    "SOURCE_ID",
    "make_persistence",
    "publish",
    "queue_cmd",
]


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------


class PublishError(RuntimeError):
    """Raised by :func:`publish` when the NATS write fails.

    Distinct from
    :class:`forge.adapters.nats.pipeline_publisher.PublishFailure` so the
    CLI does not need to import the NATS adapter to catch the error —
    this seam translates any underlying failure into a domain shape so
    the import-discipline rule (``cli/`` modules must not pull
    ``forge.adapters.nats.*`` at the top level) holds.
    """


# ---------------------------------------------------------------------------
# Persistence-protocol shape (duck type)
# ---------------------------------------------------------------------------


class _PersistenceLike(Protocol):
    """Subset of :class:`SqliteLifecyclePersistence` used by ``forge queue``.

    The real :class:`SqliteLifecyclePersistence` satisfies this Protocol
    structurally — declaring it explicitly here lets tests substitute
    a minimal stand-in without inheriting from the full facade.
    """

    def exists_active_build(self, feature_id: str) -> bool: ...

    def record_pending_build(self, payload: Any) -> str: ...


# ---------------------------------------------------------------------------
# Module-level seams (mockable in tests)
# ---------------------------------------------------------------------------


def make_persistence(config: ForgeConfig) -> _PersistenceLike:
    """Construct the production :class:`SqliteLifecyclePersistence`.

    The CLI is short-lived (per ``API-cli.md``), so we open a fresh
    writer connection on each invocation and never hand it back to the
    caller. The connection is intentionally not closed here — Python's
    GC drops it on process exit, and SQLite's per-connection WAL state
    is flushed on every ``COMMIT`` issued by the persistence layer.

    The DB path is resolved from ``$FORGE_DB_PATH`` (operator override)
    or falls back to :data:`DEFAULT_DB_PATH`. Parent directories are
    created on demand so a fresh checkout can run ``forge queue`` without
    manual setup.
    """
    # Imports are local so importing :mod:`forge.cli.queue` does not
    # eagerly pull in the SQLite adapter or the migration runner — keeps
    # ``forge --help`` fast and helps the import-discipline check.
    from forge.adapters.sqlite.connect import connect_writer
    from forge.lifecycle.migrations import apply_at_boot

    raw_path = os.environ.get("FORGE_DB_PATH")
    db_path = (
        Path(raw_path).expanduser() if raw_path else DEFAULT_DB_PATH.expanduser()
    )
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = connect_writer(db_path)
    apply_at_boot(connection)

    # ``config`` is forward-passed only — current persistence reads no
    # config fields. Keeping the parameter lets future tasks (e.g.
    # WAL-mode tuning) plumb new fields without breaking the seam.
    _ = config
    return SqliteLifecyclePersistence(connection=connection, db_path=db_path)


def publish(subject: str, body: bytes) -> None:
    """Publish ``body`` to NATS subject ``subject`` synchronously.

    The CLI is sync; the underlying NATS client (``nats-py``) is async.
    We bridge by spinning up a single-shot :func:`asyncio.run` that opens
    a connection, publishes the body, flushes, and closes — fire-and-
    forget semantics matching the rest of the pipeline (LES1 parity
    rule: PubAck is informational, not proof of delivery).

    Args:
        subject: Canonical NATS subject
            (``pipeline.build-queued.{feature_id}``).
        body: Pre-serialised envelope bytes.

    Raises:
        PublishError: When the NATS connect/publish/flush fails for any
            reason. The originating exception is preserved as
            ``__cause__``.
    """
    import asyncio  # local — keeps top-level import surface small

    servers = os.environ.get("FORGE_NATS_URL", "nats://127.0.0.1:4222")

    async def _publish_once() -> None:
        try:
            import nats  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - covered via seam
            raise PublishError(
                "nats client not installed — `pip install nats-py`"
            ) from exc

        client = await nats.connect(servers=servers)
        try:
            await client.publish(subject, body)
            await client.flush()
        finally:
            await client.close()

    try:
        asyncio.run(_publish_once())
    except PublishError:
        raise
    except Exception as exc:  # noqa: BLE001 — re-raised as a domain error
        raise PublishError(f"publish to {subject!r} failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_originating_user() -> str | None:
    """Best-effort lookup of the operator's login name.

    :func:`os.getlogin` raises :class:`OSError` on detached terminals
    (containers, CI, ``nohup`` jobs). We fall back to ``$USER``/``$LOGNAME``
    and finally to ``None`` — :class:`BuildQueuedPayload` allows a
    missing originating user.
    """
    try:
        return os.getlogin()
    except OSError:
        return os.environ.get("USER") or os.environ.get("LOGNAME") or None


def _path_in_allowlist(repo: Path, allowlist: list[Path]) -> bool:
    """Return ``True`` when ``repo`` matches an entry in ``allowlist``.

    Comparison is done against the *resolved* absolute path so a
    relative ``--repo`` is matched against canonical allowlist entries.

    A bare/empty ``allowlist`` (the schema default — see
    :class:`forge.config.models.QueueConfig`) means "no restriction" per
    the model docstring; in that case every repo passes.
    """
    if not allowlist:
        return True
    repo_resolved = Path(repo).expanduser().resolve()
    for entry in allowlist:
        try:
            entry_resolved = Path(entry).expanduser().resolve()
        except (OSError, RuntimeError):
            # Defensive — pathological symlink loops should not crash
            # the CLI. Skip the bad entry; the operator can re-run after
            # cleaning up ``forge.yaml``.
            logger.warning(
                "repo_allowlist entry %r could not be resolved", entry
            )
            continue
        if repo_resolved == entry_resolved:
            return True
        # Allow nested checkouts — a queue against
        # ``/work/repos/foo/sub`` passes when ``/work/repos/foo`` is
        # allowlisted.
        try:
            repo_resolved.relative_to(entry_resolved)
        except ValueError:
            continue
        return True
    return False


def _envelope_bytes(payload: Any, correlation_id: str) -> bytes:
    """Wrap ``payload`` in :class:`MessageEnvelope` and serialise to bytes.

    The lazy :mod:`nats_core.envelope` import keeps the envelope module
    off the top-level import path of :mod:`forge.cli.queue` — important
    for the CLI startup-cost budget.
    """
    from nats_core.envelope import EventType, MessageEnvelope

    envelope = MessageEnvelope(
        source_id=SOURCE_ID,
        event_type=EventType.BUILD_QUEUED,
        correlation_id=correlation_id,
        payload=payload.model_dump(mode="json"),
    )
    return envelope.model_dump_json().encode("utf-8")


def _require_forge_config(config: Any) -> ForgeConfig:
    """Coerce ``ctx.obj`` into a :class:`ForgeConfig` or fail with a clear error.

    The top-level group (:func:`forge.cli.main.main`) populates
    ``ctx.obj`` with a parsed :class:`ForgeConfig` when ``--config`` is
    supplied (or when ``./forge.yaml`` exists). For ``forge queue``
    specifically a config is mandatory — the queue subcommand needs the
    repo allowlist and the queue defaults — so we surface a
    :class:`click.UsageError` if it is missing.
    """
    if isinstance(config, ForgeConfig):
        return config
    raise click.UsageError(
        "forge queue requires a forge.yaml — pass --config <path> or run "
        "from a directory containing forge.yaml"
    )


# ---------------------------------------------------------------------------
# Click command
# ---------------------------------------------------------------------------


@click.command(name="queue")
@click.argument("feature_id")
@click.option(
    "--repo",
    required=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=True),
    help="Filesystem path to the local checkout. Must match repo_allowlist.",
)
@click.option(
    "--branch",
    default="main",
    show_default=True,
    help="Branch the build should target.",
)
@click.option(
    "--feature-yaml",
    "feature_yaml",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the feature YAML spec consumed by GuardKit.",
)
@click.option(
    "--max-turns",
    type=int,
    default=None,
    help="Per-build Player-Coach turn budget. Overrides queue.default_max_turns.",
)
@click.option(
    "--timeout",
    "sdk_timeout_seconds",
    type=int,
    default=None,
    help=(
        "GuardKit autobuild SDK timeout in seconds. Overrides "
        "queue.default_sdk_timeout_seconds."
    ),
)
@click.option(
    "--correlation-id",
    "correlation_id",
    default=None,
    help=(
        "Stable identifier for tracing the build across stages. "
        "Auto-generated (uuid4) when omitted."
    ),
)
@click.pass_obj
def queue_cmd(
    config_obj: Any,
    feature_id: str,
    repo: str,
    branch: str,
    feature_yaml: str,
    max_turns: int | None,
    sdk_timeout_seconds: int | None,
    correlation_id: str | None,
) -> None:
    """Enqueue a build for ``feature_id`` (write-then-publish).

    See module docstring for the full step-by-step contract.
    """
    config = _require_forge_config(config_obj)

    # 1. Validate feature_id BEFORE any side effect (AC-003 / sc_003).
    try:
        feature_id = validate_feature_id(feature_id)
    except InvalidIdentifierError as exc:
        click.echo(
            f"Invalid feature_id ({exc.reason}): {exc.value!r}",
            err=True,
        )
        sys.exit(EXIT_INVALID_IDENTIFIER)

    # 2. Allowlist check (AC-004 / Group C "path-allowlist refused").
    repo_path = Path(repo)
    if not _path_in_allowlist(repo_path, config.queue.repo_allowlist):
        click.echo(
            f"Repository {repo!r} is not in queue.repo_allowlist; "
            "refusing to enqueue (Group C path-allowlist refused).",
            err=True,
        )
        sys.exit(EXIT_PATH_REFUSED)

    # 3. Merge defaults (AC-005).
    effective_max_turns = (
        max_turns if max_turns is not None else config.queue.default_max_turns
    )
    effective_timeout = (
        sdk_timeout_seconds
        if sdk_timeout_seconds is not None
        else config.queue.default_sdk_timeout_seconds
    )
    effective_correlation_id = correlation_id or str(uuid.uuid4())

    # 4. Build the wire payload. ``nats_core.events`` is imported lazily
    #    so this module's import surface stays small.
    from nats_core.events import BuildQueuedPayload

    now = datetime.now(UTC)
    payload = BuildQueuedPayload(
        feature_id=feature_id,
        repo=str(repo_path),
        branch=branch,
        feature_yaml_path=str(Path(feature_yaml)),
        max_turns=effective_max_turns,
        sdk_timeout_seconds=effective_timeout,
        triggered_by="cli",
        originating_user=_resolve_originating_user(),
        correlation_id=effective_correlation_id,
        requested_at=now,
        queued_at=now,
    )

    # 5. Construct the persistence facade (production: SQLite; tests:
    #    monkey-patched fake).
    persistence = make_persistence(config)

    # 6. Active in-flight check (Group C "active duplicate").
    if persistence.exists_active_build(feature_id):
        click.echo(
            f"duplicate build refused: an active build for {feature_id} "
            "is already in flight (Group C).",
            err=True,
        )
        sys.exit(EXIT_DUPLICATE)

    # 7. Write SQLite row FIRST (AC-006 / sc_002 ordering).
    try:
        persistence.record_pending_build(payload)
    except DuplicateBuildError as exc:
        click.echo(
            f"duplicate build refused: {exc} (Group B).",
            err=True,
        )
        sys.exit(EXIT_DUPLICATE)

    # 8. THEN publish to NATS (AC-006 second half).
    subject = f"{BUILD_QUEUED_SUBJECT_PREFIX}.{feature_id}"
    body = _envelope_bytes(payload, effective_correlation_id)
    try:
        publish(subject, body)
    except PublishError as exc:
        # 9. AC-007: do NOT roll back the SQLite row; surface a clear
        #    diagnostic on stderr identifying the messaging-layer cause
        #    (Group H "messaging unreachable") and exit 1.
        click.echo(
            f"Queued {feature_id} (build pending) but pipeline NOT NOTIFIED — "
            f"publish failed (messaging-layer): {exc}",
            err=True,
        )
        sys.exit(EXIT_PUBLISH_FAILED)

    # 10. Happy path — print operator-facing confirmation and exit 0.
    click.echo(
        f"Queued {feature_id} (build pending) "
        f"correlation_id={effective_correlation_id}"
    )
    sys.exit(EXIT_OK)
