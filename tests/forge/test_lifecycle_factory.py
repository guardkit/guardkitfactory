"""Unit tests for TASK-FW10-006 — ``build_publisher_and_emitter``.

The factory is the production-side wiring for
:class:`forge.adapters.nats.PipelinePublisher` and
:class:`forge.pipeline.PipelineLifecycleEmitter`. Test classes mirror the
acceptance criteria in the task brief:

- AC-001 — ``build_publisher_and_emitter(client)`` returns a
  ``(PipelinePublisher, PipelineLifecycleEmitter)`` tuple bound to the
  supplied client. Asserted by reading the publisher's ``_nc`` attribute
  and the emitter's ``_publisher`` attribute (private, but stable: this
  is the seam the tests own).
- AC-002 — no second ``nats.connect`` call is opened. We import the
  ``forge.cli._serve_deps_lifecycle`` module after stubbing
  ``forge.adapters.nats.pipeline_publisher``'s lazy ``nats`` import path
  with a sentinel that explodes on access — if the factory tried to dial
  a second connection it would surface here.
- AC-003 — ``emitter.on_transition`` dispatches to the correct
  ``emit_*`` method for every lifecycle literal in DDR-006. Parametrised
  over the six declared transitions in
  :data:`forge.pipeline.TRANSITION_TO_EMITTER`.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.adapters.nats import PipelinePublisher
from forge.cli._serve_deps_lifecycle import build_publisher_and_emitter
from forge.config.models import PipelineConfig
from forge.pipeline import (
    BuildContext,
    PipelineLifecycleEmitter,
    State,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


FEATURE_ID = "FEAT-FACT"
BUILD_ID = "build-FEAT-FACT-20260502120000"
CORRELATION_ID = "corr-from-build-queued"
WAVE_TOTAL = 3
ISO_TS = "2026-05-02T12:00:00+00:00"


@pytest.fixture
def fake_client() -> MagicMock:
    """Stand-in for an already-connected ``nats.aio.client.Client``.

    The publisher only ever calls ``await client.publish(subject, body)``;
    we expose ``publish`` as an :class:`AsyncMock` so the publisher's
    awaitable contract is honoured. Any other attribute access also
    returns a :class:`MagicMock` — that is fine because the factory must
    not touch anything beyond the publish surface.
    """
    client = MagicMock(name="shared_nats_client")
    client.publish = AsyncMock(return_value=None)
    return client


@pytest.fixture
def ctx() -> BuildContext:
    return BuildContext(
        feature_id=FEATURE_ID,
        build_id=BUILD_ID,
        correlation_id=CORRELATION_ID,
        wave_total=WAVE_TOTAL,
    )


def _paused_kwargs() -> dict[str, Any]:
    return dict(
        stage_label="implementation",
        gate_mode="FLAG_FOR_REVIEW",
        coach_score=0.7,
        rationale="needs human eyes",
        approval_subject="approval.flag.X",
        paused_at=ISO_TS,
    )


def _resumed_kwargs() -> dict[str, Any]:
    return dict(
        stage_label="implementation",
        decision="APPROVE",
        responder="reviewer@forge",
        resumed_at=ISO_TS,
    )


def _complete_kwargs() -> dict[str, Any]:
    return dict(
        repo="example/repo",
        branch="feat/X",
        tasks_completed=4,
        tasks_failed=0,
        tasks_total=4,
        pr_url="https://example.com/pr/1",
        duration_seconds=900,
        summary="all green",
    )


def _failed_kwargs() -> dict[str, Any]:
    return dict(
        failure_reason="autobuild halted",
        recoverable=False,
        failed_task_id="TASK-X-001",
    )


def _cancelled_kwargs() -> dict[str, Any]:
    return dict(
        reason="operator cancel",
        cancelled_by="operator@forge",
        cancelled_at=ISO_TS,
    )


# ---------------------------------------------------------------------------
# AC-001 — factory returns the right tuple bound to the supplied client
# ---------------------------------------------------------------------------


class TestFactoryReturnsBoundPair:
    """Both objects share the supplied client — no rebinding, no copies."""

    def test_returns_publisher_and_emitter_types(self, fake_client: MagicMock) -> None:
        publisher, emitter = build_publisher_and_emitter(fake_client)
        assert isinstance(publisher, PipelinePublisher)
        assert isinstance(emitter, PipelineLifecycleEmitter)

    def test_publisher_is_bound_to_supplied_client(
        self, fake_client: MagicMock
    ) -> None:
        publisher, _ = build_publisher_and_emitter(fake_client)
        # The publisher stores the client on its ``_nc`` slot. Asserting
        # identity (``is``) — not equality — is the load-bearing check
        # for ASSUM-011: the daemon's single client must reach the
        # publisher unwrapped.
        assert publisher._nc is fake_client

    def test_emitter_is_bound_to_returned_publisher(
        self, fake_client: MagicMock
    ) -> None:
        publisher, emitter = build_publisher_and_emitter(fake_client)
        # ``_publisher`` is the private slot on PipelineLifecycleEmitter.
        # The factory's contract is that the **same** publisher instance
        # is wired into the emitter — passing emit_* through to the same
        # underlying NATS write path the publisher tuple exposes.
        assert emitter._publisher is publisher

    def test_emitter_uses_supplied_pipeline_config(
        self, fake_client: MagicMock
    ) -> None:
        cfg = PipelineConfig(progress_interval_seconds=42)
        _, emitter = build_publisher_and_emitter(fake_client, config=cfg)
        assert emitter._config is cfg
        assert emitter._config.progress_interval_seconds == 42

    def test_emitter_defaults_to_default_pipeline_config(
        self, fake_client: MagicMock
    ) -> None:
        _, emitter = build_publisher_and_emitter(fake_client)
        # Default ASSUM-005 cadence — a regression here means the factory
        # silently dropped the operator's ability to override the
        # heartbeat interval.
        assert emitter._config.progress_interval_seconds == (
            PipelineConfig().progress_interval_seconds
        )

    def test_none_client_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="client"):
            build_publisher_and_emitter(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# AC-002 — no second NATS connection is opened
# ---------------------------------------------------------------------------


class TestFactoryDoesNotOpenSecondConnection:
    """The factory MUST NOT dial NATS — it accepts a pre-opened client."""

    def test_no_call_to_nats_connect(self, fake_client: MagicMock) -> None:
        # ``nats.connect`` is the only public API for opening a NATS
        # client. Patch the symbol on the (lazy) ``nats`` module's
        # canonical import path; if the factory ever reaches it, the
        # mock's ``called`` flag flips. The fact that ``nats`` may not
        # be importable on every CI host is irrelevant — we patch the
        # *module attribute* via ``sys.modules`` so the import only
        # resolves to our sentinel.
        import sys
        import types

        fake_nats = types.ModuleType("nats")
        fake_nats.connect = AsyncMock(  # type: ignore[attr-defined]
            side_effect=AssertionError(
                "build_publisher_and_emitter must not call nats.connect — "
                "ASSUM-011 says the daemon owns the single client"
            )
        )
        with patch.dict(sys.modules, {"nats": fake_nats}):
            publisher, emitter = build_publisher_and_emitter(fake_client)

        # Connect was not called — the AssertionError side-effect would
        # have surfaced if it had been. Belt and braces: assert directly.
        fake_nats.connect.assert_not_called()  # type: ignore[attr-defined]

        # And the returned pair is still bound to the original client.
        assert publisher._nc is fake_client
        assert emitter._publisher is publisher

    def test_publisher_publish_uses_supplied_client(
        self, fake_client: MagicMock, ctx: BuildContext
    ) -> None:
        """Sanity check: emit_* on the returned emitter routes writes
        through the **supplied** client, not a phantom second one."""
        # Run a single emit_started end-to-end through emit -> publish ->
        # client.publish. Wave through asyncio.run because the test
        # class itself is sync.
        import asyncio

        publisher, emitter = build_publisher_and_emitter(fake_client)

        async def run() -> None:
            await emitter.emit_started(ctx)

        asyncio.run(run())
        # Exactly one wire-level publish. Subject and body shape are
        # owned by PipelinePublisher's own tests; here we only assert
        # that the call landed on **this** client.
        assert fake_client.publish.await_count == 1
        (subject, body), _ = fake_client.publish.call_args
        assert subject.startswith("pipeline.build-started.")
        assert isinstance(body, bytes)


# ---------------------------------------------------------------------------
# AC-003 — emitter.on_transition dispatches per lifecycle literal
# ---------------------------------------------------------------------------


class TestOnTransitionDispatchMatrix:
    """One assertion per declared (from_state, to_state) → emit_* row.

    Mirrors :data:`forge.pipeline.TRANSITION_TO_EMITTER`. Wildcard rows
    (``None`` on either side) are exercised with a representative
    concrete state — the emitter's own unit tests cover the wildcard
    semantics in full; here we only verify the factory-built emitter
    routes correctly.
    """

    # Apply asyncio marker class-scoped so each method below stays a
    # plain ``async def`` without the decorator on every line. Sync
    # tests in the rest of this file are unaffected.
    pytestmark = pytest.mark.asyncio

    async def test_preparing_to_running_dispatches_emit_started(
        self, fake_client: MagicMock, ctx: BuildContext
    ) -> None:
        _, emitter = build_publisher_and_emitter(fake_client)
        emitter.emit_started = AsyncMock()  # type: ignore[method-assign]
        await emitter.on_transition(State.PREPARING, State.RUNNING, ctx)
        emitter.emit_started.assert_awaited_once_with(ctx)

    async def test_running_to_paused_dispatches_emit_paused(
        self, fake_client: MagicMock, ctx: BuildContext
    ) -> None:
        _, emitter = build_publisher_and_emitter(fake_client)
        emitter.emit_paused = AsyncMock()  # type: ignore[method-assign]
        kwargs = _paused_kwargs()
        await emitter.on_transition(State.RUNNING, State.PAUSED, ctx, **kwargs)
        emitter.emit_paused.assert_awaited_once_with(ctx, **kwargs)

    async def test_paused_to_running_dispatches_emit_resumed(
        self, fake_client: MagicMock, ctx: BuildContext
    ) -> None:
        _, emitter = build_publisher_and_emitter(fake_client)
        emitter.emit_resumed = AsyncMock()  # type: ignore[method-assign]
        kwargs = _resumed_kwargs()
        await emitter.on_transition(State.PAUSED, State.RUNNING, ctx, **kwargs)
        emitter.emit_resumed.assert_awaited_once_with(ctx, **kwargs)

    async def test_finalising_to_complete_dispatches_emit_complete(
        self, fake_client: MagicMock, ctx: BuildContext
    ) -> None:
        _, emitter = build_publisher_and_emitter(fake_client)
        emitter.emit_complete = AsyncMock()  # type: ignore[method-assign]
        kwargs = _complete_kwargs()
        await emitter.on_transition(State.FINALISING, State.COMPLETE, ctx, **kwargs)
        emitter.emit_complete.assert_awaited_once_with(ctx, **kwargs)

    async def test_running_to_failed_dispatches_emit_failed(
        self, fake_client: MagicMock, ctx: BuildContext
    ) -> None:
        # Wildcard from_state — RUNNING is the representative concrete
        # source state for FAILED (a build that breaks while in flight).
        _, emitter = build_publisher_and_emitter(fake_client)
        emitter.emit_failed = AsyncMock()  # type: ignore[method-assign]
        kwargs = _failed_kwargs()
        await emitter.on_transition(State.RUNNING, State.FAILED, ctx, **kwargs)
        emitter.emit_failed.assert_awaited_once_with(ctx, **kwargs)

    async def test_running_to_cancelled_dispatches_emit_cancelled(
        self, fake_client: MagicMock, ctx: BuildContext
    ) -> None:
        # Wildcard from_state — RUNNING covers the operator-cancel path.
        _, emitter = build_publisher_and_emitter(fake_client)
        emitter.emit_cancelled = AsyncMock()  # type: ignore[method-assign]
        kwargs = _cancelled_kwargs()
        await emitter.on_transition(State.RUNNING, State.CANCELLED, ctx, **kwargs)
        emitter.emit_cancelled.assert_awaited_once_with(ctx, **kwargs)

    async def test_paused_to_cancelled_dispatches_emit_cancelled(
        self, fake_client: MagicMock, ctx: BuildContext
    ) -> None:
        # Second wildcard exercise — cancelling while PAUSED also
        # routes to emit_cancelled (the table's wildcard rule must
        # match any from_state).
        _, emitter = build_publisher_and_emitter(fake_client)
        emitter.emit_cancelled = AsyncMock()  # type: ignore[method-assign]
        kwargs = _cancelled_kwargs()
        await emitter.on_transition(State.PAUSED, State.CANCELLED, ctx, **kwargs)
        emitter.emit_cancelled.assert_awaited_once_with(ctx, **kwargs)


# ---------------------------------------------------------------------------
# pytest-asyncio mode
# ---------------------------------------------------------------------------


# Module-level marker is intentionally NOT used here — it would apply
# the ``asyncio`` mark to every sync test class in the file (factory
# return-value asserts, ``None``-client guard) and pytest-asyncio
# would emit a warning per sync test. The class-level
# ``pytestmark = pytest.mark.asyncio`` on
# :class:`TestOnTransitionDispatchMatrix` covers the async path
# exclusively.
