"""Bounded Player limits: strict refusal and required dcode HTTP parity."""

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
from guardkitfactory.harness.player_config import build_player_config

from .test_player_skills_graph import _backend, _collect, _scaffold

LIMITS = {"model": "openai:workhorse", "context_tokens": 131072, "output_tokens": 8192}
THINKING_OFF_LIMITS = {**LIMITS, "enable_thinking": False}
ENV = "GUARDKIT_PLAYER_MODEL_LIMITS"


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.delenv(ENV, raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:4000/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test")
    monkeypatch.setenv("DEEPAGENTS_CODE_OFFLINE", "1")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")

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
        json.dumps({**THINKING_OFF_LIMITS, "model": "openai:other"}),
        (
            '{"model":"openai:workhorse","context_tokens":131072,'
            '"output_tokens":8192,"enable_thinking":false,"enable_thinking":false}'
        ),
        *[
            json.dumps({**LIMITS, "enable_thinking": value})
            for value in (True, None, 0, 1, "false", [], {})
        ],
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


@pytest.mark.parametrize("raw", [json.dumps(THINKING_OFF_LIMITS), "not-json"])
@pytest.mark.parametrize("route", ["coach", "specialist", "synthesis"])
def test_actual_nonplayer_requests_ignore_carrier(monkeypatch, tmp_path, raw, route):
    from .test_dcode_harness import response

    monkeypatch.setenv(ENV, raw)
    monkeypatch.delenv("GUARDKIT_COACH_SYNTHESIS_DISABLE_THINKING", raising=False)
    repo = _scaffold(tmp_path)
    requests, clients = [], []

    def exchange(request):
        body = json.loads(request.content)
        requests.append(body)
        return response(body, text=f"{route} complete")

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
        "openai:coach" if route == "synthesis" else "openai:gemma4:31b",
        backend=_backend(repo),
    )

    async def collect():
        if route == "synthesis":
            return [
                event
                async for event in harness.invoke_synthesis(
                    "Return the verdict.",
                    "coach",
                    grammar='root ::= "ok"',
                    cwd=repo,
                    timeout_seconds=20,
                )
            ]
        return [
            event
            async for event in harness.invoke(
                "Complete the task.",
                route,
                [],
                repo,
                timeout_seconds=20,
            )
        ]

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
        events = asyncio.run(collect())

    assert any(isinstance(event, ResultMessageEvent) for event in events)
    assert len(requests) == 1
    body = requests[0]
    assert "chat_template_kwargs" not in body
    assert not {"reasoning", "reasoning_effort", "reasoning_budget"}.intersection(body)
    if route == "synthesis":
        assert body["model"] == "coach"
        assert body["temperature"] == 0
        assert body["max_completion_tokens"] == 16384
        assert body["grammar"] == 'root ::= "ok"'
        assert "tools" not in body
    elif route == "coach":
        assert body["model"] == "gemma4:31b"
        assert body["max_completion_tokens"] == 16384
        assert "tools" in body
    else:
        assert body["model"] == "gemma4:31b"
        assert "max_completion_tokens" not in body
        assert "tools" in body
    assert len(clients) == 2 and all(client.is_closed for client in clients)



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


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("model_kwargs", {"reasoning": {"effort": "none"}}),
        ("model_kwargs", {"reasoning_effort": "none"}),
        ("model_kwargs", {"reasoning_budget": 0}),
        ("model_kwargs", {"chat_template": "custom"}),
        ("model_kwargs", {"enable_thinking": False}),
        ("model_kwargs", {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}),
        ("model_kwargs", {"chat_template_kwargs": {"enable_thinking": False}}),
        ("extra_body", {"enable_thinking": False}),
        ("extra_body", []),
        ("extra_body", ""),
        ("extra_body", {"enable_reasoning": False}),
        ("extra_body", {"reasoning": {"effort": "none"}}),
        ("extra_body", {"reasoning_effort": "none"}),
        ("extra_body", {"reasoning_budget": 0}),
        ("extra_body", {"template": "custom"}),
        ("extra_body", {"chat_template_kwargs": []}),
        ("extra_body", {"chat_template_kwargs": {"enable_thinking": True}}),
        ("extra_body", {"chat_template_kwargs": {"enable_thinking": 0}}),
        ("extra_body", {"chat_template_kwargs": {"thinking": False}}),
        ("extra_body", {"chat_template_kwargs": {"enable_reasoning": False}}),
    ],
)
def test_thinking_control_conflicts_refuse(monkeypatch, attribute, value):
    monkeypatch.setenv(ENV, json.dumps(THINKING_OFF_LIMITS))
    model = ChatOpenAI(
        model="workhorse", base_url="http://localhost:4000/v1", use_responses_api=False
    )
    setattr(model, attribute, value)
    with patch.object(model_config, "_resolve_model_for_transport", return_value=model):
        with pytest.raises(LangGraphHarnessError):
            LangGraphHarness("openai:workhorse")._resolve_model_for_invoke("player")


def test_thinking_setting_preserves_unrelated_extra_body_with_copy_isolation(monkeypatch):
    monkeypatch.setenv(ENV, json.dumps(THINKING_OFF_LIMITS))
    model = ChatOpenAI(
        model="workhorse",
        base_url="http://localhost:4000/v1",
        use_responses_api=False,
        extra_body={
            "metadata": {"fixture": "preserved"},
            "chat_template_kwargs": {"add_generation_prompt": True},
        },
    )
    original_extra_body = model.extra_body
    original_template_kwargs = original_extra_body["chat_template_kwargs"]
    with patch.object(model_config, "_resolve_model_for_transport", return_value=model):
        result = LangGraphHarness("openai:workhorse")._resolve_model_for_invoke("player")
    assert result.extra_body == {
        "metadata": {"fixture": "preserved"},
        "chat_template_kwargs": {
            "add_generation_prompt": True,
            "enable_thinking": False,
        },
    }
    assert result.extra_body is not original_extra_body
    assert result.extra_body["chat_template_kwargs"] is not original_template_kwargs
    assert original_template_kwargs == {"add_generation_prompt": True}


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


@pytest.mark.parametrize(
    ("mode", "message"),
    [
        ("raise", "assignment failed"),
        ("ignore", "not retained"),
        ("zero", "not retained"),
        ("zero_float", "not retained"),
        ("mutate_true", "not retained"),
        ("mutate_delete", "not retained"),
    ],
)
def test_thinking_assignment_failure_is_refused(monkeypatch, mode, message):
    monkeypatch.setenv(ENV, json.dumps(THINKING_OFF_LIMITS))
    model = ChatOpenAI(
        model="workhorse", base_url="http://localhost:4000/v1", use_responses_api=False
    )
    original = ChatOpenAI.__setattr__

    def intercept(self, name, value):
        if name == "extra_body":
            if mode == "raise":
                raise ValueError("immutable")
            if mode == "ignore":
                return
            if mode in {"zero", "zero_float"}:
                value = {
                    **value,
                    "chat_template_kwargs": dict(value["chat_template_kwargs"]),
                }
                value["chat_template_kwargs"]["enable_thinking"] = (
                    0 if mode == "zero" else 0.0
                )
            elif mode == "mutate_true":
                value["chat_template_kwargs"]["enable_thinking"] = True
            else:
                del value["chat_template_kwargs"]["enable_thinking"]
        original(self, name, value)

    with (
        patch.object(model_config, "_resolve_model_for_transport", return_value=model),
        patch.object(ChatOpenAI, "__setattr__", intercept),
    ):
        with pytest.raises(LangGraphHarnessError, match=message):
            LangGraphHarness("openai:workhorse")._resolve_model_for_invoke("player")



@pytest.mark.parametrize("thinking_off", [False, True], ids=["legacy", "thinking-off"])
def test_actual_dcode_graph_main_subagent_compaction_limits(
    monkeypatch, tmp_path: Path, thinking_off: bool
):
    if sys.version_info < (3, 12) or importlib.util.find_spec("deepagents_code") is None:
        pytest.skip("dcode requires Python 3.12+ and the required dependency")
    from deepagents_code.agent import create_cli_agent

    from .test_dcode_harness import response as wire_response, selected_skill_calls

    monkeypatch.setenv(ENV, json.dumps(THINKING_OFF_LIMITS if thinking_off else LIMITS))
    repo = _scaffold(tmp_path)
    (repo / "long.txt").write_text("HISTORY_SENTINEL " * 2500)
    selected = build_player_config(
        cwd=repo,
        dcode_home=os.environ["DEEPAGENTS_HOME"],
        skills=["skills"],
        memory=["AGENTS.md"],
        repository_instructions=["AGENTS.md"],
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
        if tool_requests <= 2:
            return response(
                body,
                call=selected_skill_calls(repo)[tool_requests - 1],
            )
        if tool_requests == 3:
            return response(
                body,
                call=(
                    "task",
                    {"subagent_type": "general-purpose", "description": "NESTED_SENTINEL"},
                ),
            )
        if tool_requests == 4:
            return response(body, text="NESTED_SENTINEL completed")
        main_calls += 1
        if main_calls <= 9:
            return response(
                body,
                call=("read_file", {"file_path": str(repo / "long.txt"), "limit": 1000}),
                tokens=65000,
            )
        if main_calls == 10:
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

    def dcode_graph(*args, **kwargs):
        models.append(kwargs["model"])
        assert kwargs["cli_max_retries"] == 0
        return create_cli_agent(*args, **kwargs)

    harness = LangGraphHarness(
        "openai:workhorse",
        backend=_backend(repo),
        player_config=selected,
        recursion_limit=200,
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
        patch("deepagents_code.agent.create_cli_agent", side_effect=dcode_graph),
    ):
        events = asyncio.run(_collect(harness, repo))
    assert any(isinstance(e, ResultMessageEvent) for e in events)
    assert summaries and len(requests) > 4
    assert any(
        "NESTED_SENTINEL" in str(body["messages"])
        for body in requests
        if body.get("tools")
    )
    assert any("SUMMARY_SENTINEL" in str(body["messages"]) for body in requests)
    for body in requests:
        assert body["model"] == "workhorse" and body["max_completion_tokens"] == 8192
        assert not {
            "temperature", "top_p", "reasoning", "reasoning_effort", "extra_body"
        }.intersection(body)
        if thinking_off:
            assert body["chat_template_kwargs"] == {"enable_thinking": False}
        else:
            assert "chat_template_kwargs" not in body
    assert models[0].profile["max_input_tokens"] == 131072
    assert models[0].root_async_client.max_retries == 2
    assert models[0]._deepagents_model_retries == 0
    assert len(clients) == 2 and all(client.is_closed for client in clients)
    assert harness._ainvoke_task is None


@pytest.mark.parametrize("outcome", ["provider_error", "cancel", "empty_terminal"])
def test_dcode_failure_and_cancellation_cleanup(monkeypatch, tmp_path, outcome):
    if sys.version_info < (3, 12) or importlib.util.find_spec("deepagents_code") is None:
        pytest.skip("dcode requires Python 3.12+ and the required dependency")
    from .test_dcode_harness import response

    monkeypatch.setenv(ENV, json.dumps(THINKING_OFF_LIMITS))
    repo = _scaffold(tmp_path)
    selected = build_player_config(
        cwd=repo,
        dcode_home=os.environ["DEEPAGENTS_HOME"],
        skills=["skills"],
        memory=["AGENTS.md"],
        repository_instructions=["AGENTS.md"],
    )
    clients, requests = [], []

    async def run():
        entered = asyncio.Event()
        settled = asyncio.Event()

        async def exchange(request):
            body = json.loads(request.content)
            requests.append(body)
            assert body["model"] == "workhorse" and body["max_completion_tokens"] == 8192
            assert body["chat_template_kwargs"] == {"enable_thinking": False}
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
            "openai:workhorse", backend=_backend(repo), player_config=selected
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
