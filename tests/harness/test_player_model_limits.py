"""Bounded Player limits: strict refusal and actual A/B/C HTTP parity."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import socket
import sys
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from guardkit.orchestrator.harness import ResultMessageEvent
from langchain_openai import ChatOpenAI

from guardkitfactory.harness import model_config
from guardkitfactory.harness.langgraph_harness import LangGraphHarness, LangGraphHarnessError
from guardkitfactory.harness.player_experiment import parse_player_experiment

from .test_player_skills_graph import _backend, _collect, _scaffold

LIMITS = {"model": "openai:workhorse", "context_tokens": 131072, "output_tokens": 8192}
ENV = "GUARDKIT_PLAYER_MODEL_LIMITS"


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.delenv(ENV, raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:4000/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test")

    def deny(*args, **kwargs):
        raise AssertionError("real network forbidden")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "create_connection", deny)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "null",
        "[]",
        "true",
        "{}",
        '{"model":"openai:workhorse"}',
        json.dumps({**LIMITS, "unknown": 1}),
        json.dumps({**LIMITS, "model": "openai:other"}),
        '{"model":"openai:other",' + json.dumps(LIMITS)[1:],
        *[
            json.dumps({**LIMITS, key: value})
            for key in ("context_tokens", "output_tokens")
            for value in (True, False, 0, -1, 131072.0, 8192.0, "8192", None)
        ],
    ],
)
def test_invalid_carrier_refuses_before_construction(monkeypatch, raw):
    monkeypatch.setenv(ENV, raw)
    with patch.object(model_config, "_resolve_model_for_transport") as construct:
        with pytest.raises(LangGraphHarnessError, match="explicit Player model limits refused"):
            LangGraphHarness("openai:workhorse")._resolve_model_for_invoke("player")
    construct.assert_not_called()


@pytest.mark.parametrize(
    "model", [None, object(), "workhorse", "anthropic:workhorse", "openai:", "openai:a b"]
)
def test_unsupported_models_cannot_fall_back(monkeypatch, model):
    monkeypatch.setenv(
        ENV, json.dumps({**LIMITS, "model": model if isinstance(model, str) else LIMITS["model"]})
    )
    with patch.object(model_config, "_resolve_model_for_transport") as construct:
        with pytest.raises(LangGraphHarnessError):
            LangGraphHarness(model)._resolve_model_for_invoke("player")
    construct.assert_not_called()


def test_prebuilt_refused(monkeypatch):
    monkeypatch.setenv(ENV, json.dumps(LIMITS))
    model = ChatOpenAI(
        model="workhorse", base_url="http://localhost:4000/v1", use_responses_api=False
    )
    with pytest.raises(LangGraphHarnessError):
        LangGraphHarness(model)._resolve_model_for_invoke("player")


@pytest.mark.parametrize(
    "endpoint",
    [
        "",
        "localhost:4000/v1",
        "ftp://localhost/v1",
        "https://api.openai.com/v1",
        "https://openrouter.ai/v1",
        "https://api.deepseek.com/v1",
        "https://user:pass@localhost/v1",
        "http://localhost/v1?q=x",
        "http://localhost/v1#x",
        "http://localhost/v1?",
        "http://localhost/v1#",
        "http://localhost:bad/v1",
        "http://localhost:99999/v1",
        " http://localhost/v1",
        "http://local\nhost/v1",
    ],
)
def test_endpoint_refusal_ignores_frontier_escape(monkeypatch, endpoint):
    monkeypatch.setenv(ENV, json.dumps(LIMITS))
    monkeypatch.setenv("OPENAI_BASE_URL", endpoint)
    monkeypatch.setenv("GUARDKIT_ALLOW_FRONTIER", "1")
    with patch.object(model_config, "_resolve_model_for_transport") as construct:
        with pytest.raises(LangGraphHarnessError):
            LangGraphHarness("openai:workhorse")._resolve_model_for_invoke("player")
    construct.assert_not_called()


@pytest.mark.parametrize("role", ["coach", "specialist", None])
def test_malformed_other_roles_follow_accepted_path(monkeypatch, role):
    monkeypatch.setenv(ENV, "not-json")
    sentinel = object()
    with patch(
        "guardkitfactory.harness.langgraph_harness.resolve_autobuild_model", return_value=sentinel
    ) as resolve:
        assert LangGraphHarness("openai:workhorse")._resolve_model_for_invoke(role) is sentinel
    resolve.assert_called_once_with("openai:workhorse", role=role)


def test_absent_carrier_retains_baseline():
    with patch(
        "guardkitfactory.harness.langgraph_harness.resolve_autobuild_model", return_value="baseline"
    ) as resolve:
        assert (
            LangGraphHarness("openai:workhorse")._resolve_model_for_invoke("player") == "baseline"
        )
    resolve.assert_called_once_with("openai:workhorse", role="player")
    assert "workhorse" not in model_config.MODEL_CONTEXT_WINDOWS


@pytest.mark.parametrize(
    "changes",
    [
        {"model_name": "other"},
        {"openai_api_base": "http://other/v1"},
        {"use_responses_api": True},
        {"profile": {"max_input_tokens": 64000}},
        {"profile": {"max_output_tokens": 1234}},
        {"max_tokens": 1234},
        {"extra_body": {"max_completion_tokens": 1234}},
    ],
)
def test_resolved_conflicts_refuse(monkeypatch, changes):
    monkeypatch.setenv(ENV, json.dumps(LIMITS))
    model = ChatOpenAI(
        model="workhorse", base_url="http://localhost:4000/v1", use_responses_api=False
    )
    for key, value in changes.items():
        setattr(model, key, value)
    with patch.object(model_config, "_resolve_model_for_transport", return_value=model):
        with pytest.raises(LangGraphHarnessError):
            LangGraphHarness("openai:workhorse")._resolve_model_for_invoke("player")


def test_profile_preserved_and_assignment_failure_refuses(monkeypatch):
    monkeypatch.setenv(ENV, json.dumps(LIMITS))
    model = ChatOpenAI(
        model="workhorse",
        base_url="http://localhost:4000/v1",
        use_responses_api=False,
        profile={"tool_calling": True},
    )
    with patch.object(model_config, "_resolve_model_for_transport", return_value=model):
        result = LangGraphHarness("openai:workhorse")._resolve_model_for_invoke("player")
        assert result.profile == {"tool_calling": True, "max_input_tokens": 131072}
        assert result.max_tokens == 8192
        original = ChatOpenAI.__setattr__

        def fail(self, name, value):
            if name == "max_tokens":
                raise ValueError("immutable")
            original(self, name, value)

        with patch.object(ChatOpenAI, "__setattr__", fail):
            with pytest.raises(LangGraphHarnessError, match="assignment failed"):
                LangGraphHarness("openai:workhorse")._resolve_model_for_invoke("player")


@pytest.mark.parametrize("arm", ["A", "B", "C"])
def test_actual_graph_main_subagent_compaction_parity(monkeypatch, tmp_path: Path, arm: str):
    if arm == "C" and (
        sys.version_info < (3, 12) or importlib.util.find_spec("deepagents_code") is None
    ):
        pytest.skip("dcode requires optional Python 3.12+ environment")
    from deepagents import create_deep_agent
    from deepagents.middleware.summarization import SummarizationMiddleware

    from .test_dcode_harness import response as wire_response

    monkeypatch.setenv(ENV, json.dumps(LIMITS))
    repo = _scaffold(tmp_path)
    (repo / "long.txt").write_text("HISTORY_SENTINEL " * 2500)
    config = (
        None
        if arm == "A"
        else parse_player_experiment(
            json.dumps(
                {
                    "engine": "dcode" if arm == "C" else "native",
                    "skills": ["skills"],
                    "memory": ["AGENTS.md"],
                    **({"dcode_home": os.environ["DEEPAGENTS_HOME"]} if arm == "C" else {}),
                }
            ),
            cwd=repo,
        )
    )
    requests, models, clients, summaries = [], [], [], []
    main_calls = 0
    tool_requests = 0

    def response(body, **kwargs):
        kwargs.setdefault("index", len(requests))
        return wire_response(body, **kwargs)

    def exchange(request):
        nonlocal main_calls, tool_requests
        body = json.loads(request.content)
        requests.append(body)
        assert request.url == "http://localhost:4000/v1/chat/completions"
        if not body.get("tools"):
            summaries.append(body)
            return response(body, text="SUMMARY_SENTINEL retained", index=len(requests))
        tool_requests += 1
        if tool_requests == 1:
            return response(
                body,
                call=(
                    "task",
                    {"subagent_type": "general-purpose", "description": "NESTED_SENTINEL"},
                ),
            )
        if tool_requests == 2:
            return response(body, text="NESTED_SENTINEL completed")
        main_calls += 1
        if main_calls <= 9:
            return response(
                body,
                call=("read_file", {"file_path": str(repo / "long.txt"), "limit": 1000}),
                tokens=65000,
            )
        if main_calls == 10 and arm == "C":
            return response(body, call=("compact_conversation", {}), tokens=65000)
        return response(body, text="Player complete")

    transport = httpx.MockTransport(exchange)

    def sync_builder(*args, **kwargs):
        client = httpx.Client(transport=transport)
        clients.append(client)
        return client

    def async_builder(*args, **kwargs):
        client = httpx.AsyncClient(transport=transport)
        clients.append(client)
        return client

    def native_graph(**kwargs):
        models.append(kwargs["model"])
        kwargs["middleware"].append(
            SummarizationMiddleware(
                model=kwargs["model"],
                backend=kwargs["backend"],
                trigger=("messages", 10),
                keep=("messages", 2),
            )
        )
        return create_deep_agent(**kwargs)

    harness = LangGraphHarness(
        "openai:workhorse", backend=_backend(repo), player_experiment=config, recursion_limit=200
    )
    if arm != "C":
        history = []
        for index in range(12):
            history.extend(
                [
                    {"role": "user", "content": f"prior user {index} " + "x" * 80},
                    {"role": "assistant", "content": f"prior answer {index} " + "y" * 80},
                ]
            )
        history.append({"role": "user", "content": "Delegate NESTED_SENTINEL then read history"})
        monkeypatch.setattr(harness, "_build_input", lambda _: {"messages": history})
    with (
        patch(
            "langchain_openai.chat_models._client_utils._build_sync_httpx_client",
            side_effect=sync_builder,
        ),
        patch(
            "langchain_openai.chat_models._client_utils._build_async_httpx_client",
            side_effect=async_builder,
        ),
        patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent", side_effect=native_graph
        ),
    ):
        if arm == "C":
            from deepagents_code.agent import create_cli_agent

            def dcode_graph(*args, **kwargs):
                models.append(kwargs["model"])
                assert kwargs["cli_max_retries"] == 0
                return create_cli_agent(*args, **kwargs)

            with patch("deepagents_code.agent.create_cli_agent", side_effect=dcode_graph):
                events = asyncio.run(_collect(harness, repo))
        else:
            events = asyncio.run(_collect(harness, repo))
    assert any(isinstance(e, ResultMessageEvent) for e in events)
    assert summaries and len(requests) > 4
    assert "NESTED_SENTINEL" in str([body for body in requests if body.get("tools")][1]["messages"])
    assert any("SUMMARY_SENTINEL" in str(body["messages"]) for body in requests)
    for body in requests:
        assert body["model"] == "workhorse" and body["max_completion_tokens"] == 8192
        assert not {"temperature", "top_p", "reasoning_effort", "extra_body"}.intersection(body)
    assert models[0].profile["max_input_tokens"] == 131072
    assert models[0].root_async_client.max_retries == 2
    if arm == "C":
        assert models[0]._deepagents_model_retries == 0
    assert len(clients) == 2 and all(client.is_closed for client in clients)
    assert harness._ainvoke_task is None
    evidence = os.environ.get("DCODE_TEST_EVIDENCE")
    if evidence:
        directory = Path(evidence)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"limits-parity-{arm}.json").write_text(
            json.dumps(
                {
                    "requests": requests,
                    "profile": models[0].profile,
                    "provider_retries": 2,
                    "owned_clients_closed": True,
                },
                indent=2,
            )
        )


@pytest.mark.parametrize("engine", ["native", "dcode"])
@pytest.mark.parametrize("outcome", ["provider_error", "cancel", "empty_terminal"])
def test_enabled_carrier_failure_and_cancellation_cleanup(monkeypatch, tmp_path, engine, outcome):
    if engine == "dcode" and (
        sys.version_info < (3, 12) or importlib.util.find_spec("deepagents_code") is None
    ):
        pytest.skip("dcode requires optional Python 3.12+ environment")
    from .test_dcode_harness import response

    monkeypatch.setenv(ENV, json.dumps(LIMITS))
    repo = _scaffold(tmp_path)
    selected = parse_player_experiment(
        json.dumps(
            {
                "engine": engine,
                "skills": ["skills"],
                "memory": ["AGENTS.md"],
                **({"dcode_home": os.environ["DEEPAGENTS_HOME"]} if engine == "dcode" else {}),
            }
        ),
        cwd=repo,
    )
    clients, requests = [], []

    async def run():
        entered = asyncio.Event()
        settled = asyncio.Event()

        async def exchange(request):
            body = json.loads(request.content)
            requests.append(body)
            assert body["model"] == "workhorse" and body["max_completion_tokens"] == 8192
            if outcome == "provider_error":
                return httpx.Response(
                    400,
                    json={
                        "error": {"message": "synthetic failure", "type": "invalid_request_error"}
                    },
                )
            if outcome == "empty_terminal":
                return response(body, text="")
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                settled.set()

        transport = httpx.MockTransport(exchange)

        def sync_builder(*args, **kwargs):
            client = httpx.Client(transport=transport)
            clients.append(client)
            return client

        def async_builder(*args, **kwargs):
            client = httpx.AsyncClient(transport=transport)
            clients.append(client)
            return client

        harness = LangGraphHarness(
            "openai:workhorse", backend=_backend(repo), player_experiment=selected
        )
        with (
            patch(
                "langchain_openai.chat_models._client_utils._build_sync_httpx_client",
                side_effect=sync_builder,
            ),
            patch(
                "langchain_openai.chat_models._client_utils._build_async_httpx_client",
                side_effect=async_builder,
            ),
        ):
            task = asyncio.create_task(_collect(harness, repo))
            if outcome == "cancel":
                await asyncio.wait_for(entered.wait(), 5)
                assert not any(client.is_closed for client in clients)
                await harness.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                assert settled.is_set()
            else:
                with pytest.raises(LangGraphHarnessError):
                    await task
        assert harness._ainvoke_task is None
        assert len(requests) == 1
        assert len(clients) == 2 and all(client.is_closed for client in clients)

    asyncio.run(run())


def test_silent_limit_assignment_is_refused(monkeypatch):
    monkeypatch.setenv(ENV, json.dumps(LIMITS))
    model = ChatOpenAI(
        model="workhorse", base_url="http://localhost:4000/v1", use_responses_api=False
    )
    original = ChatOpenAI.__setattr__

    def ignore(self, name, value):
        if name != "max_tokens":
            original(self, name, value)

    with (
        patch.object(model_config, "_resolve_model_for_transport", return_value=model),
        patch.object(ChatOpenAI, "__setattr__", ignore),
    ):
        with pytest.raises(LangGraphHarnessError, match="not retained"):
            LangGraphHarness("openai:workhorse")._resolve_model_for_invoke("player")
