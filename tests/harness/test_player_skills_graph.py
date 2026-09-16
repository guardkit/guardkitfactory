"""Real native Deep Agents graph checks for the Player experiment seam."""

from __future__ import annotations

import asyncio
import json
import shutil
import socket
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from guardkit.orchestrator.harness import (
    AssistantMessageEvent,
    ResultMessageEvent,
    ToolResultEvent,
)
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from guardkitfactory.harness.backend_config import build_autobuild_backend
from guardkitfactory.harness.langgraph_harness import (
    LangGraphHarness,
    LangGraphHarnessError,
)
from guardkitfactory.harness.player_experiment import parse_player_experiment

_BUNDLE = Path(__file__).resolve().parents[2] / "examples" / "coding-skills-bundle"
_PYTHON = Path(sys.executable)
_CORRECTION = "NATIVE_GRAPH_CORRECTION_STAGE1_20260916"


@pytest.fixture(autouse=True)
def _deny_real_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    attempts: list[str] = []

    def deny(*args: Any, **kwargs: Any) -> Any:
        attempts.append(repr(args))
        raise AssertionError("real network connection denied by Player graph test")

    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    yield attempts
    assert not attempts


def _scaffold(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    bundle = repo / "examples" / "coding-skills-bundle"
    shutil.copytree(_BUNDLE, bundle)
    shutil.copy2(bundle / "AGENTS.md", repo / "AGENTS.md")
    (repo / "skills").symlink_to(
        "examples/coding-skills-bundle/skills",
        target_is_directory=True,
    )
    (repo / ".agents").mkdir()
    (repo / ".agents" / "skills").symlink_to("../skills", target_is_directory=True)
    (repo / "valid.py").write_text(
        "def add(left: int, right: int) -> int:\n    return left + right\n"
    )
    (repo / "invalid.py").write_text("def broken(:\n    pass\n")
    (repo / "product_tests").mkdir()
    (repo / ".venv").symlink_to(_PYTHON.parent.parent, target_is_directory=True)
    return repo


def _child_network_guard(repo: Path) -> Path:
    guard = repo / ".network-guard"
    guard.mkdir(exist_ok=True)
    (guard / "sitecustomize.py").write_text(
        "import socket\n"
        "def deny(*args, **kwargs):\n"
        "    raise RuntimeError('real network connection denied in helper child')\n"
        "socket.create_connection = deny\n"
        "socket.socket.connect = deny\n"
        "socket.socket.connect_ex = deny\n"
    )
    return guard


def _backend(repo: Path) -> Any:
    backend = build_autobuild_backend(repo)
    guard = _child_network_guard(repo)
    backend.default._env["PATH"] = f"{_PYTHON.parent}:/usr/bin:/bin"
    backend.default._env["PYTHONPATH"] = str(guard)
    backend.default._env["LANGSMITH_TRACING"] = "false"
    backend.default._env["LANGCHAIN_TRACING_V2"] = "false"
    backend.default._env["FLEET_MEMORY_ENABLED"] = "false"
    backend.default._env["DEEPAGENTS_CODE_OFFLINE"] = "1"
    backend.default._env["PYTHONDONTWRITEBYTECODE"] = "1"
    return backend


class FakeExchange:
    def __init__(
        self,
        calls: list[tuple[str, dict[str, object]]],
        *,
        final_text: str = "native Player completed",
        finish_reason: str = "stop",
    ) -> None:
        self.calls = calls
        self.final_text = final_text
        self.finish_reason = finish_reason
        self.requests: list[dict[str, object]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        index = len(self.requests)
        messages = body.get("messages", [])
        system = "\n".join(
            str(message.get("content", ""))
            for message in messages
            if message.get("role") in {"system", "developer"}
        )
        offered = [tool["function"]["name"] for tool in body.get("tools", [])]
        self.requests.append(
            {
                "path": request.url.path,
                "model": body.get("model"),
                "system": system,
                "offered": offered,
            }
        )
        assert request.url.host == "fake.test"
        assert request.url.path == "/v1/chat/completions"
        assert body["model"] == "qwen36-workhorse"
        assert body.get("stream") is False

        if index < len(self.calls):
            name, arguments = self.calls[index]
            assert name in offered
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": f"call-{index}",
                        "type": "function",
                        "function": {
                            "name": name,
                            "arguments": json.dumps(arguments),
                        },
                    }
                ],
            }
            finish_reason = "tool_calls"
        else:
            message = {"role": "assistant", "content": self.final_text}
            finish_reason = self.finish_reason
        return httpx.Response(
            200,
            json={
                "id": f"chatcmpl-{index}",
                "object": "chat.completion",
                "created": 1,
                "model": body["model"],
                "choices": [
                    {
                        "index": 0,
                        "message": message,
                        "finish_reason": finish_reason,
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 10,
                    "total_tokens": 110,
                },
            },
        )


def _model(
    exchange: FakeExchange,
) -> tuple[ChatOpenAI, httpx.Client, httpx.AsyncClient]:
    transport = httpx.MockTransport(exchange)
    sync_client = httpx.Client(transport=transport)
    async_client = httpx.AsyncClient(transport=transport)
    model = ChatOpenAI(
        model="qwen36-workhorse",
        base_url="http://fake.test/v1",
        api_key="synthetic-test",
        use_responses_api=False,
        temperature=0,
        max_tokens=8192,
        profile={"max_input_tokens": 131072},
        http_client=sync_client,
        http_async_client=async_client,
        max_retries=0,
        disable_streaming=True,
        http_socket_options=(),
    )
    return model, sync_client, async_client


async def _collect(
    harness: LangGraphHarness,
    repo: Path,
    prompt: str = "Complete the checked change.",
) -> list[Any]:
    return [
        event
        async for event in harness.invoke(
            prompt=prompt,
            role="player",
            tools=[],
            cwd=repo,
            timeout_seconds=60,
        )
    ]


def _close_clients(sync_client: httpx.Client, async_client: httpx.AsyncClient) -> None:
    asyncio.run(async_client.aclose())
    sync_client.close()


def test_real_native_graph_uses_skills_memory_helpers_and_product_repair(
    tmp_path: Path,
) -> None:
    repo = _scaffold(tmp_path)
    correction = f"# Coding instructions\n\n- {_CORRECTION}"
    calls = [
        (
            "read_file",
            {"file_path": str(repo / "skills/planning/SKILL.md"), "limit": 1000},
        ),
        (
            "read_file",
            {"file_path": str(repo / "skills/code-review/SKILL.md"), "limit": 1000},
        ),
        (
            "execute",
            {
                "command": (
                    "python skills/code-review/lint_check.py --root . "
                    "invalid.py valid.py"
                )
            },
        ),
        (
            "execute",
            {
                "command": (
                    "python skills/code-review/lint_check.py --root . valid.py"
                )
            },
        ),
        ("read_file", {"file_path": str(repo / "AGENTS.md"), "limit": 1000}),
        (
            "edit_file",
            {
                "file_path": str(repo / "AGENTS.md"),
                "old_string": "# Coding instructions",
                "new_string": correction,
            },
        ),
        (
            "write_file",
            {
                "file_path": str(repo / "calculator.py"),
                "content": "def multiply(left: int, right: int) -> int:\n    return left + right\n",
            },
        ),
        (
            "write_file",
            {
                "file_path": str(repo / "product_tests/test_calculator.py"),
                "content": (
                    "from calculator import multiply\n\n"
                    "def test_multiply():\n"
                    "    assert multiply(3, 4) == 12\n"
                ),
            },
        ),
        (
            "execute",
            {"command": ".venv/bin/python -m pytest -q product_tests/test_calculator.py"},
        ),
        (
            "edit_file",
            {
                "file_path": str(repo / "calculator.py"),
                "old_string": "return left + right",
                "new_string": "return left * right",
            },
        ),
        (
            "execute",
            {"command": ".venv/bin/python -m pytest -q product_tests/test_calculator.py"},
        ),
    ]
    exchange = FakeExchange(calls)
    model, sync_client, async_client = _model(exchange)
    pings: list[int] = []
    config = parse_player_experiment(
        '{"engine":"native","skills":["skills"],"memory":["AGENTS.md"]}',
        cwd=repo,
    )
    harness = LangGraphHarness(
        model,
        backend=_backend(repo),
        on_model_activity=lambda: pings.append(1),
        player_experiment=config,
    )

    try:
        events = asyncio.run(
            _collect(
                harness,
                repo,
                "Read both selected skills, run their helper on bad and good files, "
                "save the correction, then write, test, and repair multiply.",
            )
        )
    finally:
        _close_clients(sync_client, async_client)

    first_system = str(exchange.requests[0]["system"])
    assert "planning" in first_system and "code-review" in first_system
    assert "# Coding instructions" in first_system
    assert _CORRECTION not in first_system
    assert _CORRECTION in (repo / "AGENTS.md").read_text()
    assert (repo / "calculator.py").read_text().endswith("return left * right\n")
    assert pings

    tool_results = [
        str(event.content) for event in events if isinstance(event, ToolResultEvent)
    ]
    assert any("ERROR invalid.py:1" in result for result in tool_results), tool_results
    assert any("CHECKED valid.py" in result for result in tool_results)
    assert any("1 failed" in result for result in tool_results)
    assert any("1 passed" in result for result in tool_results)

    assistant = next(event for event in events if isinstance(event, AssistantMessageEvent))
    terminal = next(event for event in events if isinstance(event, ResultMessageEvent))
    assert assistant.text == "native Player completed"
    assert terminal.stop_reason == "stop"
    assert terminal.usage == dict(terminal.raw.usage_metadata)
    assert terminal.usage["input_tokens"] == 100
    assert terminal.usage["output_tokens"] == 10
    assert terminal.usage["total_tokens"] == 110
    assert isinstance(terminal.raw, AIMessage)
    assert terminal.raw is assistant.raw["messages"][-1]

    reconstructed_exchange = FakeExchange([])
    reconstructed_model, reconstructed_sync, reconstructed_async = _model(
        reconstructed_exchange
    )
    reconstructed = LangGraphHarness(
        reconstructed_model,
        backend=_backend(repo),
        player_experiment=parse_player_experiment(
            '{"engine":"native","skills":["skills"],"memory":["AGENTS.md"]}',
            cwd=repo,
        ),
    )
    try:
        asyncio.run(_collect(reconstructed, repo, "Read the current instructions."))
    finally:
        _close_clients(reconstructed_sync, reconstructed_async)
    assert _CORRECTION in str(reconstructed_exchange.requests[0]["system"])

    fresh_repo = _scaffold(tmp_path, "fresh")
    fresh_exchange = FakeExchange([])
    fresh_model, fresh_sync, fresh_async = _model(fresh_exchange)
    fresh = LangGraphHarness(
        fresh_model,
        backend=_backend(fresh_repo),
        player_experiment=parse_player_experiment(
            '{"engine":"native","skills":["skills"],"memory":["AGENTS.md"]}',
            cwd=fresh_repo,
        ),
    )
    try:
        asyncio.run(_collect(fresh, fresh_repo, "Read the clean instructions."))
    finally:
        _close_clients(fresh_sync, fresh_async)
    assert _CORRECTION not in str(fresh_exchange.requests[0]["system"])


@pytest.mark.parametrize(
    ("final_text", "finish_reason", "match"),
    [
        ("", "stop", "empty terminal assistant"),
        ("partial answer", "length", "finish_reason='length'"),
    ],
)
def test_real_graph_rejects_false_terminal_success(
    tmp_path: Path,
    final_text: str,
    finish_reason: str,
    match: str,
) -> None:
    repo = _scaffold(tmp_path)
    exchange = FakeExchange(
        [("read_file", {"file_path": str(repo / "AGENTS.md"), "limit": 1000})],
        final_text=final_text,
        finish_reason=finish_reason,
    )
    model, sync_client, async_client = _model(exchange)
    harness = LangGraphHarness(
        model,
        backend=_backend(repo),
        player_experiment=parse_player_experiment(
            '{"engine":"native","memory":["AGENTS.md"]}',
            cwd=repo,
        ),
    )
    seen: list[Any] = []

    async def run() -> None:
        async for event in harness.invoke(
            "Read the instructions.", "player", [], repo, timeout_seconds=30
        ):
            seen.append(event)

    try:
        with pytest.raises(LangGraphHarnessError, match=match) as caught:
            asyncio.run(run())
    finally:
        _close_clients(sync_client, async_client)
    assert not any(isinstance(event, ResultMessageEvent) for event in seen)
    assert seen == []
    assert isinstance(caught.value.raw_result, dict)
    terminal = caught.value.raw_result["messages"][-1]
    assert isinstance(terminal, AIMessage)
    assert terminal.content == final_text


def test_enabled_graph_does_not_fall_back_to_non_ai_message(tmp_path: Path) -> None:
    repo = _scaffold(tmp_path)
    harness = LangGraphHarness(
        object(),
        backend=_backend(repo),
        player_experiment=parse_player_experiment('{"engine":"native"}', cwd=repo),
    )
    raw_result = {
        "messages": [
            {"role": "user", "content": "earlier user text"},
            {"role": "assistant", "content": "dict fallback text"},
        ]
    }
    with pytest.raises(LangGraphHarnessError, match="no terminal AIMessage") as caught:
        harness._experiment_terminal_message(raw_result)
    assert caught.value.raw_result is raw_result


def test_invocation_revalidates_source_and_backend_worktree(tmp_path: Path) -> None:
    repo = _scaffold(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    config = parse_player_experiment(
        '{"engine":"native","memory":["AGENTS.md"]}',
        cwd=repo,
    )
    (repo / "AGENTS.md").unlink()
    missing = LangGraphHarness(
        object(),
        backend=_backend(repo),
        player_experiment=config,
    )
    with pytest.raises(LangGraphHarnessError, match="does not exist"):
        asyncio.run(_collect(missing, repo))

    repo = _scaffold(tmp_path, "restored")
    config = parse_player_experiment('{"engine":"native"}', cwd=repo)
    wrong_backend = LangGraphHarness(
        object(),
        backend=_backend(other),
        player_experiment=config,
    )
    with pytest.raises(LangGraphHarnessError, match="backend/worktree mismatch"):
        asyncio.run(_collect(wrong_backend, repo))

    conflicting = _backend(other)
    conflicting.artifacts_root = str(repo)
    split_backend = LangGraphHarness(
        object(),
        backend=conflicting,
        player_experiment=config,
    )
    with pytest.raises(LangGraphHarnessError, match="conflicting backend roots"):
        asyncio.run(_collect(split_backend, repo))


def test_dcode_request_is_lazy_and_never_falls_back(tmp_path: Path) -> None:
    repo = _scaffold(tmp_path)
    profile = tmp_path / "profile"
    profile.mkdir()
    config = parse_player_experiment(
        json.dumps({"engine": "dcode", "dcode_home": str(profile)}),
        cwd=repo,
    )
    harness = LangGraphHarness(
        object(),
        backend=_backend(repo),
        player_experiment=config,
    )
    real_import = __import__

    def import_trap(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("deepagents_code"):
            raise AssertionError("dcode was imported eagerly")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=import_trap):
        with pytest.raises(LangGraphHarnessError, match="not implemented.*no fallback"):
            asyncio.run(_collect(harness, repo))


class _BlockingAsyncTransport(httpx.AsyncBaseTransport):
    def __init__(self, started: asyncio.Event) -> None:
        self.started = started

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.started.set()
        await asyncio.Future()
        raise AssertionError("unreachable")


def test_real_graph_callback_and_cancellation_propagate(tmp_path: Path) -> None:
    repo = _scaffold(tmp_path)

    async def scenario() -> tuple[bool, list[int]]:
        started = asyncio.Event()
        sync_client = httpx.Client(
            transport=httpx.MockTransport(
                lambda request: (_ for _ in ()).throw(
                    AssertionError("async graph used sync HTTP client")
                )
            )
        )
        async_client = httpx.AsyncClient(transport=_BlockingAsyncTransport(started))
        model = ChatOpenAI(
            model="qwen36-workhorse",
            base_url="http://fake.test/v1",
            api_key="synthetic-test",
            use_responses_api=False,
            http_client=sync_client,
            http_async_client=async_client,
            max_retries=0,
            disable_streaming=True,
            http_socket_options=(),
        )
        pings: list[int] = []
        harness = LangGraphHarness(
            model,
            backend=_backend(repo),
            on_model_activity=lambda: pings.append(1),
            player_experiment=parse_player_experiment(
                '{"engine":"native"}',
                cwd=repo,
            ),
        )
        consumer = asyncio.create_task(_collect(harness, repo))
        await asyncio.wait_for(started.wait(), timeout=10)
        await harness.cancel()
        cancelled = False
        try:
            await consumer
        except asyncio.CancelledError:
            cancelled = True
        await async_client.aclose()
        sync_client.close()
        return cancelled, pings

    cancelled, pings = asyncio.run(scenario())
    assert cancelled
    assert pings
