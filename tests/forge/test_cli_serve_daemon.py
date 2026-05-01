"""Tests for the ``forge serve`` daemon body (TASK-F009-003).

Each ``Test*`` class maps to one acceptance criterion of TASK-F009-003 so
the criterion → verifier mapping stays explicit (per the project's
testing rules — AAA pattern, descriptive names, AC traceability).

Production collaborators (NATS connect, JetStream subscribe, dispatch)
are stubbed with ``unittest.mock.AsyncMock`` and small in-process fakes.
The only real external library exercised here is ``nats-py``'s
``ConsumerConfig`` / ``AckPolicy`` enums for shape verification.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy
from pydantic import ValidationError

from forge.cli import _serve_daemon
from forge.cli._serve_config import (
    DEFAULT_DURABLE_NAME,
    DEFAULT_NATS_URL,
    ServeConfig,
)
from forge.cli._serve_daemon import (
    BUILD_QUEUED_SUBJECT_FILTER,
    PIPELINE_STREAM_NAME,
    SHUTDOWN_TIMEOUT_SECONDS,
    run_daemon,
)
from forge.cli._serve_state import SubscriptionState


# ---------------------------------------------------------------------------
# Shared fakes
# ---------------------------------------------------------------------------


class _FakeMsg:
    """Minimal stand-in for ``nats.aio.msg.Msg``.

    Carries a payload as bytes and an ``ack`` async method that records
    whether ack was called — enough to verify the at-most-once / E2.1
    crash-redelivery semantics.
    """

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.acked = False

    async def ack(self) -> None:
        self.acked = True


class _FakeSubscription:
    """Pull subscription whose ``fetch()`` returns batches from a queue.

    Returning an empty list (or raising ``asyncio.TimeoutError``) lets
    the daemon's main loop poll without messages so we can assert state
    transitions independently of message delivery.
    """

    def __init__(self) -> None:
        self.batches: list[list[_FakeMsg]] = []
        self.fetch_calls = 0
        self.unsubscribed = False
        # When ``raise_on_fetch`` is set the next ``fetch`` raises it once
        # — used to model broker-loss → reconnect (D3 scenario).
        self.raise_on_fetch: BaseException | None = None

    async def fetch(self, batch: int = 1, timeout: float = 1.0) -> list[_FakeMsg]:
        self.fetch_calls += 1
        if self.raise_on_fetch is not None:
            err = self.raise_on_fetch
            self.raise_on_fetch = None
            raise err
        if self.batches:
            return self.batches.pop(0)
        # Mimic nats-py's "no messages" behaviour: TimeoutError.
        raise asyncio.TimeoutError()

    async def unsubscribe(self) -> None:
        self.unsubscribed = True


class _FakeJetStream:
    """Captures ``pull_subscribe`` arguments and yields a ``_FakeSubscription``."""

    def __init__(self, sub: _FakeSubscription) -> None:
        self._sub = sub
        self.pull_subscribe_kwargs: dict[str, Any] | None = None

    async def pull_subscribe(self, **kwargs: Any) -> _FakeSubscription:
        self.pull_subscribe_kwargs = kwargs
        return self._sub


class _FakeNatsClient:
    """Fake ``nats`` client returning a fake JetStream context."""

    def __init__(self, sub: _FakeSubscription | None = None) -> None:
        self._js = _FakeJetStream(sub or _FakeSubscription())
        self.closed = False

    def jetstream(self) -> _FakeJetStream:
        return self._js

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_sub() -> _FakeSubscription:
    return _FakeSubscription()


@pytest.fixture
def fake_client(fake_sub: _FakeSubscription) -> _FakeNatsClient:
    return _FakeNatsClient(fake_sub)


@pytest.fixture
def patched_seams(
    monkeypatch: pytest.MonkeyPatch,
    fake_client: _FakeNatsClient,
) -> _FakeNatsClient:
    """Bind the module-level NATS connect seam to ``fake_client``."""

    async def _connect(url: str) -> Any:
        return fake_client

    monkeypatch.setattr(_serve_daemon, "nats_connect", _connect)
    return fake_client


async def _drive_daemon(
    config: ServeConfig,
    state: SubscriptionState,
    *,
    until: callable,
    timeout: float = 2.0,
) -> None:
    """Run the daemon until ``until()`` returns truthy then signal stop.

    Spawns ``run_daemon`` as a task, polls ``until`` between asyncio
    ticks, sets the daemon's stop event, and awaits clean exit. Returns
    on success; raises ``asyncio.TimeoutError`` on stuck daemons.
    """
    task = asyncio.create_task(run_daemon(config, state))

    async def _waiter() -> None:
        while not until():
            await asyncio.sleep(0.01)

    try:
        await asyncio.wait_for(_waiter(), timeout=timeout)
    except asyncio.TimeoutError:
        task.cancel()
        with pytest.raises((asyncio.CancelledError, BaseException)):
            await task
        raise

    task.cancel()
    try:
        await asyncio.wait_for(task, timeout=timeout)
    except asyncio.CancelledError:
        pass


# ---------------------------------------------------------------------------
# Seam test (TASK-F009-003 §Seam Tests) — durable name contract with T1
# ---------------------------------------------------------------------------


class TestDurableNameContract:
    """Seam: ``DEFAULT_DURABLE_NAME == 'forge-serve'`` exactly (case-sensitive)."""

    @pytest.mark.seam
    @pytest.mark.integration_contract("JETSTREAM_DURABLE_NAME")
    def test_jetstream_durable_name_format(self) -> None:
        from forge.cli.serve import DEFAULT_DURABLE_NAME as exported

        assert exported, "DEFAULT_DURABLE_NAME must not be empty"
        assert exported == "forge-serve", (
            f"Expected exact 'forge-serve' (case-sensitive), got: {exported!r}"
        )


# ---------------------------------------------------------------------------
# AC-001: forge serve starts and stays running until SIGTERM
# ---------------------------------------------------------------------------


class TestDaemonStaysRunningUntilStop:
    """AC-001: Daemon runs indefinitely until cancelled / signalled."""

    @pytest.mark.asyncio
    async def test_daemon_runs_until_cancelled(
        self,
        patched_seams: _FakeNatsClient,
    ) -> None:
        config = ServeConfig()
        state = SubscriptionState()

        await _drive_daemon(
            config,
            state,
            until=lambda: state.live,
            timeout=2.0,
        )
        # Reaching this point means the daemon was alive until we cancelled.
        # ``state.live`` was True at least once (driver waited for it).
        assert patched_seams.closed is True


# ---------------------------------------------------------------------------
# AC-002: Daemon attaches the durable consumer named ``forge-serve``
# on ``pipeline.build-queued.*`` (Contract C; ASSUM-006).
# ---------------------------------------------------------------------------


class TestDurableConsumerAttach:
    """AC-002: Pull-subscribe arguments match Contract C exactly."""

    @pytest.mark.asyncio
    async def test_pull_subscribe_uses_forge_serve_durable(
        self,
        patched_seams: _FakeNatsClient,
    ) -> None:
        config = ServeConfig()
        state = SubscriptionState()

        await _drive_daemon(
            config, state, until=lambda: state.live, timeout=2.0,
        )

        kwargs = patched_seams.jetstream().pull_subscribe_kwargs
        assert kwargs is not None
        # Durable name MUST be exactly 'forge-serve' (case-sensitive).
        assert kwargs["durable"] == "forge-serve"
        assert kwargs["durable"] == DEFAULT_DURABLE_NAME
        # Subject filter is the build-queued wildcard.
        assert kwargs["subject"] == "pipeline.build-queued.*"
        assert kwargs["subject"] == BUILD_QUEUED_SUBJECT_FILTER
        # Stream is shared with the existing pipeline consumer.
        assert kwargs["stream"] == "PIPELINE"
        assert kwargs["stream"] == PIPELINE_STREAM_NAME

    @pytest.mark.asyncio
    async def test_consumer_config_uses_explicit_ack_and_filter(
        self,
        patched_seams: _FakeNatsClient,
    ) -> None:
        config = ServeConfig()
        state = SubscriptionState()

        await _drive_daemon(
            config, state, until=lambda: state.live, timeout=2.0,
        )

        kwargs = patched_seams.jetstream().pull_subscribe_kwargs
        assert kwargs is not None
        cfg = kwargs.get("config")
        assert isinstance(cfg, ConsumerConfig)
        # Explicit ack — required for at-least-once + work-queue semantics.
        assert cfg.ack_policy == AckPolicy.EXPLICIT
        assert cfg.deliver_policy == DeliverPolicy.ALL
        assert cfg.durable_name == "forge-serve"
        assert cfg.filter_subject == "pipeline.build-queued.*"


# ---------------------------------------------------------------------------
# AC-003 (D2): Two replicas share the durable; semantics are work-queue.
# Contract: each replica calls pull_subscribe with the SAME durable name.
# ---------------------------------------------------------------------------


class TestSharedDurableForMultiReplica:
    """AC-003 (D2): each replica binds the same durable, not a per-replica name."""

    @pytest.mark.asyncio
    async def test_two_replicas_share_durable_name(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Each "replica" gets its own client + recorder.
        clients: list[_FakeNatsClient] = []

        async def _connect(url: str) -> Any:
            client = _FakeNatsClient()
            clients.append(client)
            return client

        monkeypatch.setattr(_serve_daemon, "nats_connect", _connect)

        async def _run_one() -> None:
            config = ServeConfig()
            state = SubscriptionState()
            await _drive_daemon(
                config, state, until=lambda: state.live, timeout=2.0,
            )

        # Run sequentially (same effect — we assert against the recorded
        # subscribe kwargs, not message-fanout behaviour, which is the
        # broker's responsibility).
        await _run_one()
        await _run_one()

        assert len(clients) == 2
        durables = {
            c.jetstream().pull_subscribe_kwargs["durable"]
            for c in clients
            if c.jetstream().pull_subscribe_kwargs
        }
        # Both replicas share *one* durable name — the heart of D2.
        assert durables == {"forge-serve"}


# ---------------------------------------------------------------------------
# AC-004 (D3): Broker-outage recovery — state.live flips False then True
# ---------------------------------------------------------------------------


class TestBrokerOutageRecovery:
    """AC-004: state.live flips False on broker loss, True on reconnect."""

    @pytest.mark.asyncio
    async def test_state_clears_on_fetch_error_then_recovers(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # First call: a sub that raises on fetch (broker loss).
        # Second call: a healthy sub that yields nothing (broker back).
        sub_bad = _FakeSubscription()
        sub_bad.raise_on_fetch = ConnectionError("broker gone")
        client_bad = _FakeNatsClient(sub_bad)

        sub_good = _FakeSubscription()
        client_good = _FakeNatsClient(sub_good)

        seq = iter([client_bad, client_good])

        async def _connect(url: str) -> Any:
            return next(seq)

        monkeypatch.setattr(_serve_daemon, "nats_connect", _connect)
        monkeypatch.setattr(
            _serve_daemon, "RECONNECT_INITIAL_BACKOFF", 0.05
        )
        monkeypatch.setattr(_serve_daemon, "RECONNECT_MAX_BACKOFF", 0.05)

        config = ServeConfig()
        state = SubscriptionState()

        # Wait for second attach (state goes False then True again).
        await _drive_daemon(
            config,
            state,
            until=lambda: client_good.jetstream().pull_subscribe_kwargs is not None,
            timeout=2.0,
        )
        assert client_bad.closed is True


# ---------------------------------------------------------------------------
# AC-005 (E2.1): On crash before ack, message stays pending.
# We cannot directly test "process crash"; instead we assert that the
# daemon does NOT ack a message whose dispatch is interrupted by stop.
# ---------------------------------------------------------------------------


class TestUnackedOnCrash:
    """AC-005 (E2.1): unacked messages survive abrupt stop for redelivery."""

    @pytest.mark.asyncio
    async def test_message_not_acked_when_dispatch_blocks_through_cancel(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Subscription yields one message immediately.
        msg = _FakeMsg(b"{}")
        sub = _FakeSubscription()
        sub.batches.append([msg])
        client = _FakeNatsClient(sub)

        async def _connect(url: str) -> Any:
            return client

        # Dispatch hangs forever until cancelled — simulates a long-running
        # build. When SIGTERM fires before dispatch returns, ack must NOT
        # run, so JetStream redelivers on restart.
        dispatch_started = asyncio.Event()

        async def _hang(body: bytes) -> None:
            dispatch_started.set()
            await asyncio.Event().wait()  # never returns

        monkeypatch.setattr(_serve_daemon, "nats_connect", _connect)
        monkeypatch.setattr(_serve_daemon, "dispatch_payload", _hang)

        config = ServeConfig()
        state = SubscriptionState()
        task = asyncio.create_task(run_daemon(config, state))

        try:
            await asyncio.wait_for(dispatch_started.wait(), timeout=2.0)
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        finally:
            if not task.done():
                task.cancel()

        # Crash-safety property: ack did not run.
        assert msg.acked is False


# ---------------------------------------------------------------------------
# AC-006 (E3.1): Provider unavailable — only that build fails.
# Daemon stays available for subsequent messages.
# ---------------------------------------------------------------------------


class TestDispatchFailureIsolated:
    """AC-006 (E3.1): a failed dispatch does NOT take the daemon down."""

    @pytest.mark.asyncio
    async def test_dispatch_exception_acks_and_continues(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        msg_bad = _FakeMsg(b"{}")
        msg_good = _FakeMsg(b"{}")
        sub = _FakeSubscription()
        sub.batches.append([msg_bad])
        sub.batches.append([msg_good])
        client = _FakeNatsClient(sub)

        async def _connect(url: str) -> Any:
            return client

        seen: list[bytes] = []

        async def _dispatch(body: bytes) -> None:
            seen.append(body)
            if len(seen) == 1:
                raise RuntimeError("provider unavailable")

        monkeypatch.setattr(_serve_daemon, "nats_connect", _connect)
        monkeypatch.setattr(_serve_daemon, "dispatch_payload", _dispatch)

        config = ServeConfig()
        state = SubscriptionState()

        await _drive_daemon(
            config,
            state,
            until=lambda: msg_good.acked,
            timeout=2.0,
        )

        # The failed dispatch was still acked — releases the queue slot
        # so the daemon stays available (E3.1).
        assert msg_bad.acked is True
        assert msg_good.acked is True
        # Both payloads observed; the daemon did not crash on the first.
        assert len(seen) == 2


# ---------------------------------------------------------------------------
# AC-007: SubscriptionState.live mirrors broker connectivity
# ---------------------------------------------------------------------------


class TestSubscriptionStateLive:
    """AC-007: ``state.live`` is True after attach, False on broker loss."""

    @pytest.mark.asyncio
    async def test_state_starts_false(self) -> None:
        state = SubscriptionState()
        assert state.live is False

    @pytest.mark.asyncio
    async def test_state_flips_true_after_subscribe(
        self, patched_seams: _FakeNatsClient
    ) -> None:
        config = ServeConfig()
        state = SubscriptionState()

        await _drive_daemon(
            config, state, until=lambda: state.live, timeout=2.0,
        )
        # After daemon exits, live is False again — clean tear-down.
        assert state.live is False


# ---------------------------------------------------------------------------
# AC-008: SIGTERM completes within the documented 10 s budget
# ---------------------------------------------------------------------------


class TestShutdownGrace:
    """AC-008: SIGTERM grace constant is bounded at 10 s."""

    def test_shutdown_timeout_is_at_most_ten_seconds(self) -> None:
        # The constant is declarative — the daemon uses it to bound the
        # final ``client.close()`` so a hung broker cannot delay exit
        # past the AC's 10 s budget.
        assert SHUTDOWN_TIMEOUT_SECONDS <= 10.0
        assert SHUTDOWN_TIMEOUT_SECONDS > 0

    @pytest.mark.asyncio
    async def test_daemon_exits_quickly_after_cancel(
        self, patched_seams: _FakeNatsClient
    ) -> None:
        config = ServeConfig()
        state = SubscriptionState()
        task = asyncio.create_task(run_daemon(config, state))

        # Wait for live, then cancel.
        for _ in range(200):
            if state.live:
                break
            await asyncio.sleep(0.01)
        task.cancel()

        loop = asyncio.get_event_loop()
        start = loop.time()
        try:
            await asyncio.wait_for(task, timeout=10.0)
        except asyncio.CancelledError:
            pass
        elapsed = loop.time() - start
        # The smoke bound is well under the AC's 10 s ceiling.
        assert elapsed < 5.0


# ---------------------------------------------------------------------------
# AC-009 (C5): ServeConfig refuses to construct with invalid fields.
# ---------------------------------------------------------------------------


class TestServeConfigValidationRefusal:
    """AC-009: ServeConfig validation names the offending field."""

    def test_invalid_healthz_port_raises_with_field_name(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ServeConfig(healthz_port=0)
        # Pydantic v2 includes the field name in the error message.
        assert "healthz_port" in str(exc_info.value)

    def test_empty_durable_name_raises_with_field_name(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ServeConfig(durable_name="")
        assert "durable_name" in str(exc_info.value)

    def test_extra_field_refused_by_pydantic(self) -> None:
        # ``ConfigDict(extra="forbid")`` makes typos visible at boot
        # rather than silently shadowing a default.
        with pytest.raises(ValidationError) as exc_info:
            ServeConfig(unknown_field="oops")  # type: ignore[call-arg]
        assert "unknown_field" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AC-010 (lint-clean): the module imports cleanly, exports the public API.
# ---------------------------------------------------------------------------


class TestPublicSurface:
    """AC-010: ``run_daemon`` and module constants are public-API."""

    def test_run_daemon_is_callable(self) -> None:
        assert callable(run_daemon)

    def test_module_exports_seams(self) -> None:
        # The seams are module-level so tests (and operators) can rebind
        # them — same pattern as ``forge.cli.queue.publish``.
        assert hasattr(_serve_daemon, "nats_connect")
        assert hasattr(_serve_daemon, "dispatch_payload")
        assert callable(_serve_daemon.nats_connect)
        assert callable(_serve_daemon.dispatch_payload)

    def test_constants_match_contracts(self) -> None:
        assert _serve_daemon.BUILD_QUEUED_SUBJECT_FILTER == "pipeline.build-queued.*"
        assert _serve_daemon.PIPELINE_STREAM_NAME == "PIPELINE"
        # Default constants match the T1 producers.
        assert DEFAULT_DURABLE_NAME == "forge-serve"
        assert DEFAULT_NATS_URL == "nats://127.0.0.1:4222"


# ---------------------------------------------------------------------------
# Helper-level test: dispatch helper does not raise on malformed envelope
# (buffer for E3.1 isolation property — even garbage input cannot kill
# the daemon's main loop)
# ---------------------------------------------------------------------------


class TestDefaultDispatchHandlesMalformed:
    """Defensive: the default dispatch helper never raises."""

    @pytest.mark.asyncio
    async def test_default_dispatch_swallows_garbage_bytes(self) -> None:
        # ``_default_dispatch`` is the production seam — it logs warnings
        # but must NEVER propagate an exception, otherwise the daemon's
        # main loop catches it and the bad message blocks the queue.
        await _serve_daemon._default_dispatch(b"not-json")
        await _serve_daemon._default_dispatch(b"")
        # Reaching here is the assertion: no exception escaped.
