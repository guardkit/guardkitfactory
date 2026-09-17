"""Shared Player test helpers and required dcode dispatch checks."""

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
from langchain_openai import ChatOpenAI

from guardkitfactory.harness.backend_config import build_autobuild_backend
from guardkitfactory.harness.langgraph_harness import (
    LangGraphHarness,
    LangGraphHarnessError,
)
from guardkitfactory.harness.player_config import build_player_config

_BUNDLE = Path(__file__).resolve().parents[2] / "examples" / "coding-skills-bundle"
_PYTHON = Path(sys.executable)


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


def _player_config(repo: Path, profile: Path | None = None) -> Any:
    selected_profile = profile or (repo.parent / "dcode-profile")
    selected_profile.mkdir(exist_ok=True)
    return build_player_config(
        cwd=repo,
        dcode_home=selected_profile,
        skills=["skills"],
        memory=["AGENTS.md"],
        repository_instructions=["AGENTS.md"],
    )


def test_player_requires_config_and_never_uses_native_graph(tmp_path: Path) -> None:
    repo = _scaffold(tmp_path)
    harness = LangGraphHarness(object(), backend=_backend(repo))

    with patch("guardkitfactory.harness.langgraph_harness.create_deep_agent") as native:
        with pytest.raises(
            LangGraphHarnessError, match="native Player implementation has been retired"
        ):
            harness._create_agent(role="player", cwd=repo, resolved_model=object())
        native.assert_not_called()


def test_coach_retains_shared_deep_agents_graph(tmp_path: Path) -> None:
    repo = _scaffold(tmp_path)
    harness = LangGraphHarness(object(), backend=_backend(repo))
    sentinel = object()

    with patch(
        "guardkitfactory.harness.langgraph_harness.create_deep_agent",
        return_value=sentinel,
    ) as create:
        assert harness._create_agent(role="coach", cwd=repo, resolved_model=object()) is sentinel
    assert "Review the implementation independently" in create.call_args.kwargs["system_prompt"]


def test_player_revalidates_sources_and_backend_worktree(tmp_path: Path) -> None:
    repo = _scaffold(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    selected = _player_config(repo)
    (repo / "AGENTS.md").unlink()
    missing = LangGraphHarness(object(), backend=_backend(repo), player_config=selected)
    with pytest.raises(LangGraphHarnessError, match="does not exist"):
        asyncio.run(_collect(missing, repo))

    restored = _scaffold(tmp_path, "restored")
    selected = _player_config(restored, tmp_path / "restored-profile")
    wrong_backend = LangGraphHarness(
        object(), backend=_backend(other), player_config=selected
    )
    with pytest.raises(LangGraphHarnessError, match="backend/worktree mismatch"):
        asyncio.run(_collect(wrong_backend, restored))


def test_required_dcode_dependency_failure_has_no_native_fallback(tmp_path: Path) -> None:
    repo = _scaffold(tmp_path)
    selected = _player_config(repo)
    harness = LangGraphHarness(object(), backend=_backend(repo), player_config=selected)

    from guardkitfactory.harness import dcode_harness

    with (
        patch.object(dcode_harness.importlib.util, "find_spec", return_value=None),
        patch("guardkitfactory.harness.langgraph_harness.create_deep_agent") as native,
        pytest.raises(LangGraphHarnessError, match="required dependency.*no fallback"),
    ):
        asyncio.run(_collect(harness, repo))
    native.assert_not_called()
