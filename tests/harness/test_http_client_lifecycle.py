"""Persistent-socket regressions for invocation-owned factory transports.

No provider, broker or external address is reachable: the audit fence permits
only this fixture's ephemeral loopback port. Responses are fixed test data.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import AsyncExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest
from guardkit.orchestrator.harness import AssistantMessageEvent, ResultMessageEvent
from langchain_openai import ChatOpenAI
from langchain_openai._compat import httpx

from guardkitfactory.harness import http_clients
from guardkitfactory.harness import langgraph_harness as harness_module
from guardkitfactory.harness.backend_config import build_autobuild_backend
from guardkitfactory.harness.http_clients import create_chat_openai, with_invocation_clients
from guardkitfactory.harness.langgraph_harness import LangGraphHarness, LangGraphHarnessError


@pytest.fixture
def server(monkeypatch):
    state = SimpleNamespace(requests=[], delay=0.03, status=200, reply=None,
                            arrived=threading.Event(), block=None)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state.requests.append((self.path, body, self.client_address[1]))
            state.arrived.set()
            if state.block is not None:
                state.block.wait(10)
            time.sleep(state.delay)
            message = {"role": "assistant", "content": "fixture answer"}
            if state.reply is not None:
                message = state.reply(body)
            response = {
                "id": "fixture-completion", "object": "chat.completion", "created": 0,
                "model": body["model"],
                "choices": [{"index": 0, "message": message,
                             "finish_reason": "tool_calls" if "tool_calls" in message else "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
            }
            payload = json.dumps(response).encode()
            self.send_response(state.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            try:
                self.wfile.write(payload)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    enabled = True
    denied = []

    def audit(event, args):
        if not enabled:
            return
        if event == "socket.connect":
            address = args[1]
            if isinstance(address, tuple) and address[:2] != ("127.0.0.1", port):
                denied.append(str(address))
                raise AssertionError(f"non-fixture connection forbidden: {address}")
        elif event == "socket.getaddrinfo" and args[0] != "127.0.0.1":
            denied.append(str(args[:2]))
            raise AssertionError("non-fixture DNS forbidden")

    sys.addaudithook(audit)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    for name in list(os.environ):
        if "proxy" in name.lower() or name.startswith(("OPENAI_", "SANDBOX_")):
            monkeypatch.delenv(name)
    monkeypatch.setenv("OPENAI_BASE_URL", f"http://127.0.0.1:{port}/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    state.url = f"http://127.0.0.1:{port}"
    try:
        yield state
    finally:
        if state.block is not None:
            state.block.set()
        httpd.shutdown()
        httpd.server_close()
        thread.join(2)
        enabled = False
        assert not denied, denied


@pytest.fixture
def owned(monkeypatch):
    clients = []

    class TrackingStack(AsyncExitStack):
        def push_async_callback(self, callback, *args, **kwargs):
            clients.append(callback.__self__)
            return super().push_async_callback(callback, *args, **kwargs)

    monkeypatch.setattr(http_clients, "AsyncExitStack", TrackingStack)
    return clients


def invocation(harness, tmp_path, *, synthesis=False):
    if synthesis:
        return harness.invoke_synthesis("fixture prompt", "coach", grammar='root ::= "ok"',
                                        cwd=tmp_path, timeout_seconds=20)
    return harness.invoke("fixture prompt", "player", [], tmp_path, timeout_seconds=20)


async def collect(harness, tmp_path, *, synthesis=False):
    return [event async for event in invocation(harness, tmp_path, synthesis=synthesis)]


@pytest.mark.parametrize("proxy", [False, True])
def test_player_then_coach_and_repeat_across_loops(server, owned, monkeypatch, tmp_path, proxy):
    if proxy:
        monkeypatch.setenv("HTTP_PROXY", server.url)
        monkeypatch.setenv("OPENAI_BASE_URL", "http://fixture.invalid/v1")
    # Deliberately mirror GuardKit: a persistent Player loop, then asyncio.run
    # for Coach. Keep the first loop alive to reproduce the exact old failure.
    loop = asyncio.new_event_loop()
    try:
        for _ in range(2):
            loop.run_until_complete(collect(LangGraphHarness("openai:workhorse"), tmp_path))
            asyncio.run(collect(LangGraphHarness("openai:coach"), tmp_path, synthesis=True))
    finally:
        loop.close()
    assert len(server.requests) == 4  # no hidden retry
    assert len(owned) == 4 and len({id(client) for client in owned}) == 4
    assert all(client.is_closed for client in owned)
    player, coach = [r[1] for r in server.requests[:2]]
    assert player["model"] == "workhorse" and "tools" in player
    assert "temperature" not in player and "max_completion_tokens" not in player
    assert coach["model"] == "coach" and coach["temperature"] == 0
    assert coach["max_completion_tokens"] == 16384 and "tools" not in coach
    assert coach["grammar"] == 'root ::= "ok"'
    assert all(path.endswith("/v1/chat/completions") for path, _, _ in server.requests)


def test_simultaneous_worker_loops_and_same_loop(server, owned, tmp_path):
    barrier = threading.Barrier(2)

    def worker():
        barrier.wait(timeout=5)

        async def run():
            for _ in range(2):
                await collect(LangGraphHarness("openai:workhorse"), tmp_path)
                await collect(LangGraphHarness("openai:coach"), tmp_path, synthesis=True)
        asyncio.run(run())

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        for future in futures:
            future.result(timeout=20)
    assert len(server.requests) == 8
    assert len(owned) == len({id(client) for client in owned}) == 8
    assert all(client.is_closed for client in owned)


@pytest.mark.parametrize("synthesis", [False, True])
@pytest.mark.parametrize("stop", ["first", "result"])
def test_clients_closed_before_consumer_stops(server, owned, tmp_path, synthesis, stop):
    async def run():
        harness = LangGraphHarness("openai:coach" if synthesis else "openai:workhorse")
        stream = invocation(harness, tmp_path, synthesis=synthesis)
        async for event in stream:
            assert owned and all(client.is_closed for client in owned)
            assert harness._ainvoke_task is None
            if stop == "first" or isinstance(event, ResultMessageEvent):
                break
        # Still hold the suspended iterator: neither GC nor aclose caused the
        # assertion above to pass. This matches the real invoker's result break.
        await stream.aclose()
    asyncio.run(run())
    assert len(server.requests) == 1


@pytest.mark.parametrize("synthesis", [False, True])
def test_provider_error_closes_clients(server, owned, tmp_path, synthesis):
    server.status = 400
    with pytest.raises(LangGraphHarnessError):
        asyncio.run(collect(LangGraphHarness("openai:coach"), tmp_path, synthesis=synthesis))
    assert len(server.requests) == 1
    assert owned and all(client.is_closed for client in owned)


@pytest.mark.parametrize("synthesis", [False, True])
def test_model_construction_error_cannot_fallback(
    server, owned, monkeypatch, tmp_path, synthesis,
):
    def fail(**_kwargs):
        raise ValueError("owned model construction failed")

    monkeypatch.setattr("langchain_openai.ChatOpenAI", fail)
    with pytest.raises(
        (LangGraphHarnessError, ValueError), match="owned model construction failed"
    ):
        asyncio.run(collect(LangGraphHarness("openai:coach"), tmp_path, synthesis=synthesis))
    assert not server.requests
    assert owned and all(client.is_closed for client in owned)


def test_synthesis_async_client_typeerror_is_not_retried(
    server, owned, monkeypatch, tmp_path,
):
    from langchain_openai.chat_models import _client_utils as provider

    calls = []

    def fail(*_args, **_kwargs):
        calls.append(1)
        raise TypeError("async client construction failed")

    monkeypatch.setattr(provider, "_build_async_httpx_client", fail)
    with pytest.raises(TypeError, match="async client construction failed"):
        asyncio.run(collect(LangGraphHarness("openai:coach"), tmp_path, synthesis=True))
    assert len(calls) == 1
    assert not owned
    assert not server.requests


def test_synthesis_sync_client_typeerror_closes_async_client(
    server, owned, monkeypatch, tmp_path,
):
    from langchain_openai.chat_models import _client_utils as provider

    calls = []

    def fail(*_args, **_kwargs):
        calls.append(1)
        raise TypeError("sync client construction failed")

    monkeypatch.setattr(provider, "_build_sync_httpx_client", fail)
    with pytest.raises(TypeError, match="sync client construction failed"):
        asyncio.run(collect(LangGraphHarness("openai:coach"), tmp_path, synthesis=True))
    assert len(calls) == 1
    assert len(owned) == 1 and owned[0].is_closed
    assert not server.requests


def test_synthesis_model_typeerror_closes_created_clients(
    server, owned, monkeypatch, tmp_path,
):
    from langchain_openai.chat_models import _client_utils as provider

    original_sync_builder = provider._build_sync_httpx_client
    sync_clients = []
    model_calls = []

    def build_sync(*args, **kwargs):
        client = original_sync_builder(*args, **kwargs)
        sync_clients.append(client)
        return client

    def fail_model(**kwargs):
        model_calls.append(kwargs)
        raise TypeError("model construction failed")

    monkeypatch.setattr(provider, "_build_sync_httpx_client", build_sync)
    monkeypatch.setattr("langchain_openai.ChatOpenAI", fail_model)
    with pytest.raises(TypeError, match="model construction failed"):
        asyncio.run(collect(LangGraphHarness("openai:coach"), tmp_path, synthesis=True))
    assert len(model_calls) == 1
    assert model_calls[0]["use_responses_api"] is False
    assert len(owned) == 1 and owned[0].is_closed
    assert len(sync_clients) == 1 and sync_clients[0].is_closed
    assert not server.requests


def test_graph_construction_error_closes_clients(server, owned, monkeypatch, tmp_path):
    def fail(**_kwargs):
        raise ValueError("graph construction failed")

    monkeypatch.setattr(harness_module, "create_deep_agent", fail)
    with pytest.raises(LangGraphHarnessError, match="graph construction failed"):
        asyncio.run(collect(LangGraphHarness("openai:workhorse"), tmp_path))
    assert owned and all(client.is_closed for client in owned)
    assert not server.requests


@pytest.mark.parametrize("synthesis", [False, True])
def test_cancel_settles_request_before_client_close(server, owned, tmp_path, synthesis):
    server.block = threading.Event()

    async def run():
        harness = LangGraphHarness("openai:coach")
        task = asyncio.create_task(collect(harness, tmp_path, synthesis=synthesis))
        assert await asyncio.to_thread(server.arrived.wait, 5)
        assert owned and not any(client.is_closed for client in owned)
        await harness.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert harness._ainvoke_task is None
        assert all(client.is_closed for client in owned)
    asyncio.run(run())
    assert len(server.requests) == 1


@pytest.mark.parametrize("explicit", [False, True])
def test_prebuilt_identity_and_caller_clients_stay_open(server, owned, tmp_path, explicit):
    async def run():
        kwargs = {}
        client = httpx.AsyncClient(timeout=None) if explicit else None
        if explicit:
            kwargs["http_async_client"] = client
        model = ChatOpenAI(model="caller-model", temperature=.27, max_tokens=777,
                           use_responses_api=False, callbacks=[], **kwargs)
        original_client = model.root_async_client._client
        original_callbacks = model.callbacks
        harness = LangGraphHarness(model)
        try:
            assert harness._resolve_model_for_invoke("player") is model
            await collect(harness, tmp_path)
            await collect(harness, tmp_path, synthesis=True)
            assert harness.model is model and model.callbacks is original_callbacks
            assert model.root_async_client._client is original_client
            assert not original_client.is_closed
            assert not owned
            assert model.temperature == .27 and model.max_tokens == 777
        finally:
            await original_client.aclose()
            model.root_client.close()
    asyncio.run(run())
    assert len(server.requests) == 2
    assert len({r[2] for r in server.requests}) == 1


@pytest.mark.parametrize("proxy", ["none", "environment", "explicit"])
def test_provider_transport_defaults_and_proxy_route(server, owned, monkeypatch, proxy):
    if proxy != "none":
        monkeypatch.setenv("OPENAI_BASE_URL", "http://fixture.invalid/v1")
        monkeypatch.setenv("OPENAI_PROXY" if proxy == "explicit" else "HTTP_PROXY", server.url)

    reference = ChatOpenAI(model="workhorse", use_responses_api=False)
    reference_client = reference.root_async_client._client
    reference_pool = reference_client._transport_for_url(
        httpx.URL(os.environ["OPENAI_BASE_URL"])
    )._pool

    @with_invocation_clients
    async def run():
        model = create_chat_openai(model="workhorse", use_responses_api=False)
        client = model.root_async_client._client
        assert type(client).__module__.startswith(("langchain_openai", "httpx"))
        assert model.root_async_client.timeout is None
        assert client.timeout == reference_client.timeout
        pool = client._transport_for_url(httpx.URL(os.environ["OPENAI_BASE_URL"]))._pool
        for name in ("_max_connections", "_max_keepalive_connections", "_keepalive_expiry"):
            assert getattr(pool, name) == getattr(reference_pool, name)
        if proxy != "explicit":
            assert all(value is None for value in client.timeout.as_dict().values())
            assert pool._max_connections == 1000
            assert pool._max_keepalive_connections == 100
            assert pool._keepalive_expiry == 5
        yield await model.ainvoke("fixture prompt")

    async def drain():
        try:
            return [value async for value in run()]
        finally:
            await reference_client.aclose()
            reference.root_client.close()
    asyncio.run(drain())
    assert len(server.requests) == 1
    assert all(client.is_closed for client in owned)
    assert server.requests[0][0].startswith("http://fixture.invalid") == (proxy != "none")


def test_default_read_timeout_does_not_become_five_seconds(server, owned, tmp_path):
    server.delay = 5.2
    asyncio.run(collect(LangGraphHarness("openai:coach"), tmp_path, synthesis=True))
    assert len(server.requests) == 1 and all(client.is_closed for client in owned)


def test_configured_timeout_is_retained_and_closes_clients(server, owned):
    import openai

    server.delay = .25

    @with_invocation_clients
    async def run():
        model = create_chat_openai(model="coach", timeout=.05, max_retries=0,
                                  use_responses_api=False)
        assert model.root_async_client._client.timeout.read == .05
        yield await model.ainvoke("fixture prompt")

    async def drain():
        return [value async for value in run()]
    with pytest.raises(openai.APITimeoutError):
        asyncio.run(drain())
    assert len(server.requests) == 1 and all(client.is_closed for client in owned)


def test_nested_subagent_keeps_owned_client_until_parent_finishes(server, owned, tmp_path):
    def reply(body):
        assert owned and not any(client.is_closed for client in owned)
        last = body["messages"][-1]
        if last["role"] == "tool":
            return {"role": "assistant", "content": "parent finished"}
        if "child-job" in str(last["content"]):
            return {"role": "assistant", "content": "child finished"}
        return {"role": "assistant", "content": None, "tool_calls": [{
            "id": "child-call", "type": "function", "function": {
                "name": "task", "arguments": json.dumps({"description": "child-job",
                                                          "subagent_type": "general-purpose"}),
            },
        }]}

    server.reply = reply
    events = asyncio.run(collect(LangGraphHarness("openai:workhorse"), tmp_path))
    assert len(server.requests) == 3  # parent, real subagent, parent completion
    assert any(isinstance(event, AssistantMessageEvent) and event.text == "parent finished"
               for event in events)
    assert len(owned) == 1 and owned[0].is_closed
    assert len({r[2] for r in server.requests}) == 1


def test_real_compaction_uses_owned_client_through_final_request(
    server, owned, monkeypatch, tmp_path,
):
    from deepagents import create_deep_agent
    from deepagents.middleware.summarization import SummarizationMiddleware

    def create(**kwargs):
        kwargs["middleware"].append(SummarizationMiddleware(
            model=kwargs["model"], backend=kwargs["backend"],
            trigger=("messages", 10), keep=("messages", 2),
        ))
        return create_deep_agent(**kwargs)

    def reply(_body):
        assert owned and not any(client.is_closed for client in owned)
        return {"role": "assistant", "content": (
            "compact summary" if len(server.requests) == 1 else "final answer"
        )}

    server.reply = reply
    monkeypatch.setattr(harness_module, "create_deep_agent", create)
    harness = LangGraphHarness("openai:workhorse", backend=build_autobuild_backend(tmp_path))
    messages = []
    for index in range(12):
        messages.extend([{"role": "user", "content": f"user-{index} " + "x" * 80},
                         {"role": "assistant", "content": f"assistant-{index} " + "y" * 80}])
    monkeypatch.setattr(harness, "_build_input", lambda _: {"messages": messages})
    asyncio.run(collect(harness, tmp_path))
    assert len(server.requests) == 2
    assert "Context Extraction Assistant" in json.dumps(server.requests[0][1]["messages"])
    assert "compact summary" in json.dumps(server.requests[1][1]["messages"])
    assert len(owned) == 1 and owned[0].is_closed
    assert len({r[2] for r in server.requests}) == 1
    assert list((tmp_path / "conversation_history").glob("session_*.md"))


def test_cancel_during_client_cleanup_waits_for_closure(server, owned, monkeypatch, tmp_path):
    async def run():
        started = asyncio.Event()
        release = asyncio.Event()
        original_stack = http_clients.AsyncExitStack

        class SlowCloseStack(original_stack):
            async def aclose(self):
                started.set()
                await release.wait()
                await super().aclose()

        monkeypatch.setattr(http_clients, "AsyncExitStack", SlowCloseStack)
        task = asyncio.create_task(collect(LangGraphHarness("openai:coach"), tmp_path,
                                           synthesis=True))
        await asyncio.wait_for(started.wait(), 5)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        assert not task.done() and not any(client.is_closed for client in owned)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert all(client.is_closed for client in owned)
    asyncio.run(run())
    assert len(server.requests) == 1


def test_cancel_nested_subagent_settles_before_closure(server, owned, tmp_path):
    child_started = threading.Event()
    release = threading.Event()
    server.block = None

    def reply(body):
        if "child-job" in str(body["messages"][-1]["content"]):
            child_started.set()
            release.wait(5)
            return {"role": "assistant", "content": "child finished"}
        return {"role": "assistant", "content": None, "tool_calls": [{
            "id": "child-call", "type": "function", "function": {
                "name": "task", "arguments": json.dumps({"description": "child-job",
                                                          "subagent_type": "general-purpose"}),
            },
        }]}

    server.reply = reply

    async def run():
        harness = LangGraphHarness("openai:workhorse")
        task = asyncio.create_task(collect(harness, tmp_path))
        try:
            assert await asyncio.to_thread(child_started.wait, 5)
            assert not any(client.is_closed for client in owned)
            await harness.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert all(client.is_closed for client in owned)
            assert not [t for t in asyncio.all_tasks()
                        if t is not asyncio.current_task() and not t.done()]
        finally:
            release.set()
    asyncio.run(run())
    assert len(server.requests) == 2
