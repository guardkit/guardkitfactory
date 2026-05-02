"""Tests for ``forge.cli._serve_dispatcher`` (TASK-FW10-007).

Acceptance-criteria coverage map:

* AC: ``make_handle_message_dispatcher(deps)`` returns a closure
  conforming to ``(_MsgLike) -> Awaitable[None]`` —
  :class:`TestDispatcherClosureSignature`.
* AC: The closure delegates to ``pipeline_consumer.handle_message(msg, deps)``
  and does NOT call ``msg.ack()`` —
  :class:`TestDispatcherDelegatesWithoutAck`.
* AC (seam test from task brief): ack lifecycle is owned by the state
  machine, not by the dispatcher closure —
  :class:`TestDispatcherDoesNotAckSeam`.
* AC: malformed-payload delegation — the dispatcher does not short-
  circuit on a bad envelope; ``handle_message`` is still invoked and
  it owns the ack + ``build-failed`` flow —
  :class:`TestMalformedDelegation`.

Tests use the ``forge.adapters.nats.pipeline_consumer`` module's
``handle_message`` attribute as the monkey-patch target — this is the
exact attribute the production dispatcher looks up at call time so the
seam test pattern matches the production code path.
"""

from __future__ import annotations

import inspect
from typing import Any
from unittest.mock import AsyncMock

import pytest

from forge.adapters.nats import pipeline_consumer
from forge.cli._serve_dispatcher import make_handle_message_dispatcher


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _FakeMsg:
    """Minimal :data:`_MsgLike` double with a counted ``ack`` coroutine."""

    def __init__(self, data: bytes = b'{"feature_id":"FEAT-X","correlation_id":"c"}') -> None:
        self.data = data
        self.ack_calls = 0

    async def ack(self) -> None:
        self.ack_calls += 1


@pytest.fixture()
def restore_handle_message():
    """Restore ``pipeline_consumer.handle_message`` after a monkey-patch.

    The seam test pattern monkey-patches the module-level attribute
    directly (rather than using ``monkeypatch.setattr`` on the function
    object) because the production dispatcher looks up the attribute on
    the module at call time — that lookup MUST observe the patch.
    """
    original = pipeline_consumer.handle_message
    yield
    pipeline_consumer.handle_message = original


# ---------------------------------------------------------------------------
# AC: closure signature
# ---------------------------------------------------------------------------


class TestDispatcherClosureSignature:
    """``make_handle_message_dispatcher`` returns a ``DispatchFn`` closure."""

    def test_factory_returns_async_callable(self) -> None:
        dispatcher = make_handle_message_dispatcher(deps=object())

        assert callable(dispatcher), "factory must return a callable"
        assert inspect.iscoroutinefunction(dispatcher), (
            "dispatcher must be an async coroutine function "
            "(matches DispatchFn = Callable[[_MsgLike], Awaitable[None]])"
        )

    def test_factory_closure_accepts_msg_argument(self) -> None:
        dispatcher = make_handle_message_dispatcher(deps=object())
        sig = inspect.signature(dispatcher)
        params = list(sig.parameters.values())

        assert len(params) == 1, (
            f"dispatcher must accept exactly one positional argument (the msg); "
            f"got {len(params)}"
        )


# ---------------------------------------------------------------------------
# AC: delegates without acking
# ---------------------------------------------------------------------------


class TestDispatcherDelegatesWithoutAck:
    """Dispatcher delegates to ``handle_message(msg, deps)`` and never acks."""

    @pytest.mark.asyncio
    async def test_delegates_to_handle_message_with_msg_and_deps(
        self, restore_handle_message: None
    ) -> None:
        captured: list[tuple[Any, Any]] = []

        async def fake_handle(msg: Any, deps: Any) -> None:
            captured.append((msg, deps))

        pipeline_consumer.handle_message = fake_handle  # type: ignore[assignment]

        sentinel_deps = object()
        msg = _FakeMsg()

        dispatcher = make_handle_message_dispatcher(sentinel_deps)
        await dispatcher(msg)

        assert len(captured) == 1, (
            "dispatcher must delegate to handle_message exactly once"
        )
        observed_msg, observed_deps = captured[0]
        assert observed_msg is msg, (
            "dispatcher must forward the same msg instance to handle_message"
        )
        assert observed_deps is sentinel_deps, (
            "dispatcher must forward the bound deps instance to handle_message"
        )

    @pytest.mark.asyncio
    async def test_dispatcher_does_not_call_msg_ack(
        self, restore_handle_message: None
    ) -> None:
        # Ack lifecycle is owned by handle_message via ack_callback;
        # the dispatcher must never call msg.ack() itself (TASK-FW10-001
        # AC-002 + ADR-SP-013).
        async def fake_handle(msg: Any, deps: Any) -> None:
            return None

        pipeline_consumer.handle_message = fake_handle  # type: ignore[assignment]

        msg = _FakeMsg()
        dispatcher = make_handle_message_dispatcher(deps=object())
        await dispatcher(msg)

        assert msg.ack_calls == 0, (
            "dispatcher must not call msg.ack(); ack is deferred to the "
            "state machine via ack_callback"
        )


# ---------------------------------------------------------------------------
# AC (seam test): mirror the test in TASK-FW10-007 brief
# ---------------------------------------------------------------------------


class TestDispatcherDoesNotAckSeam:
    """Reproduces the load-bearing seam test from the task brief verbatim."""

    @pytest.mark.asyncio
    async def test_dispatcher_closure_does_not_ack(
        self, restore_handle_message: None
    ) -> None:
        ack_calls = 0
        handle_calls: list[tuple[Any, Any]] = []

        class FakeMsg:
            data = b'{"feature_id":"F","correlation_id":"c"}'

            async def ack(self) -> None:
                nonlocal ack_calls
                ack_calls += 1

        async def fake_handle(msg: Any, deps: Any) -> None:
            handle_calls.append((msg, deps))

        fake_deps = object()
        pipeline_consumer.handle_message = fake_handle  # type: ignore[assignment]

        dispatcher = make_handle_message_dispatcher(fake_deps)
        await dispatcher(FakeMsg())

        assert handle_calls, "dispatcher must delegate to handle_message"
        assert ack_calls == 0, (
            "dispatcher must not ack — ack is deferred to the state machine"
        )


# ---------------------------------------------------------------------------
# AC: malformed-payload delegation (no short-circuit)
# ---------------------------------------------------------------------------


class TestMalformedDelegation:
    """A malformed payload still delegates; handle_message owns ack + publish."""

    @pytest.mark.asyncio
    async def test_malformed_payload_still_delegates_to_handle_message(
        self, restore_handle_message: None
    ) -> None:
        # The dispatcher does NOT validate the payload itself; it
        # forwards every msg straight to handle_message, which owns the
        # malformed-envelope ack + build-failed publish flow. This test
        # asserts the dispatcher does not short-circuit on bad bytes.
        delegated = AsyncMock()
        pipeline_consumer.handle_message = delegated  # type: ignore[assignment]

        msg = _FakeMsg(data=b"not-a-valid-envelope")
        dispatcher = make_handle_message_dispatcher(deps=object())
        await dispatcher(msg)

        delegated.assert_awaited_once_with(msg, dispatcher.__closure__[0].cell_contents)  # type: ignore[union-attr]
        assert msg.ack_calls == 0, (
            "dispatcher must not pre-empt handle_message's ack — that is the "
            "state machine's responsibility, even on malformed payloads"
        )
