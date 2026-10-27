"""Required dcode integration through the real graph and fake provider HTTP."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from guardkit.orchestrator.harness import AssistantMessageEvent, ResultMessageEvent, ToolResultEvent
from langchain_core.messages import AIMessage

from guardkitfactory.harness.langgraph_harness import LangGraphHarness, LangGraphHarnessError
from guardkitfactory.harness.player_config import build_player_config

from .test_player_skills_graph import (
    FakeExchange,
    _backend,
    _close_clients,
    _collect,
    _model,
    _scaffold,
)

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 12) or importlib.util.find_spec("deepagents_code") is None,
    reason="dcode graph acceptance requires Python 3.12+ and the required dependency",
)


@pytest.fixture(autouse=True)
def isolate(monkeypatch: pytest.MonkeyPatch) -> None:
    def deny(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("real network is forbidden")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://fake.test/v1")
    monkeypatch.setenv("DEEPAGENTS_CODE_OFFLINE", "1")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    profile = os.environ.get("DEEPAGENTS_HOME")
    assert profile and Path(profile).is_absolute(), "launch with a unique DEEPAGENTS_HOME"


def config(repo: Path) -> Any:
    return build_player_config(
        cwd=repo,
        dcode_home=os.environ["DEEPAGENTS_HOME"],
        skills=["skills"],
        memory=["AGENTS.md"],
        repository_instructions=["AGENTS.md"],
        declared_commands=[("test", "./qa/run-suite.sh --exact")],
        protected_paths=["product_tests"],
    )


_DECLARED_DOCUMENT = "skills/planning/references/project-conventions.md"


def declare_document(repo: Path) -> Path:
    """Write the supporting document a skill body tells the Player to read."""

    folder = (repo / "skills" / "planning" / "references").resolve()
    folder.mkdir(parents=True, exist_ok=True)
    document = folder / "project-conventions.md"
    document.write_text(
        "# Project conventions\n"
        "State the delivered surface (route, command or screen) in the plan.\n"
    )
    return document


def config_with_documents(repo: Path, documents: list[str] | None = None) -> Any:
    """The same Player inputs, plus project-declared mandatory documents."""

    return build_player_config(
        cwd=repo,
        dcode_home=os.environ["DEEPAGENTS_HOME"],
        skills=["skills"],
        memory=["AGENTS.md"],
        repository_instructions=["AGENTS.md"],
        declared_commands=[("test", "./qa/run-suite.sh --exact")],
        protected_paths=["product_tests"],
        required_documents=[_DECLARED_DOCUMENT] if documents is None else documents,
    )


def read_call(path: Path) -> tuple[str, dict[str, object]]:
    return ("read_file", {"file_path": str(path), "limit": 1000})


def selected_skill_calls(repo: Path) -> list[tuple[str, dict[str, object]]]:
    root = (repo / "skills").resolve()
    return [
        ("read_file", {"file_path": str(root / "planning/SKILL.md"), "limit": 1000}),
        ("read_file", {"file_path": str(root / "code-review/SKILL.md"), "limit": 1000}),
    ]


class Exchange(FakeExchange):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.bodies: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.bodies.append(json.loads(request.content))
        return super().__call__(request)


def evidence(name: str, value: Any) -> None:
    directory = os.environ.get("DCODE_TEST_EVIDENCE")
    if directory:
        path = Path(directory)
        path.mkdir(exist_ok=True, parents=True)
        (path / f"{name}.json").write_text(json.dumps(value, indent=2, default=str))


def test_real_graph_skills_helper_repair_and_metadata(tmp_path: Path) -> None:
    repo = _scaffold(tmp_path)
    acceptance = repo / "product_tests" / "test_product.py"
    acceptance.write_text(
        "from calculator import multiply\ndef test_product():\n    assert multiply(3, 4) == 12\n"
    )
    digest = hashlib.sha256(acceptance.read_bytes()).hexdigest()
    exchange = Exchange(
        [
            *selected_skill_calls(repo),
            ("read_file", {"file_path": str(repo / "AGENTS.md")}),
            (
                "execute",
                {"command": "python skills/code-review/lint_check.py --root . invalid.py valid.py"},
            ),
            ("execute", {"command": "python skills/code-review/lint_check.py --root . valid.py"}),
            (
                "write_file",
                {
                    "file_path": str(repo / "calculator.py"),
                    "content": "def multiply(a, b):\n    return a + b\n",
                },
            ),
            ("execute", {"command": ".venv/bin/python -m pytest -q product_tests/test_product.py"}),
            (
                "edit_file",
                {
                    "file_path": str(repo / "calculator.py"),
                    "old_string": "return a + b",
                    "new_string": "return a * b",
                },
            ),
            ("execute", {"command": ".venv/bin/python -m pytest -q product_tests/test_product.py"}),
        ],
        final_text="dcode repaired the product",
    )
    model, sync, async_ = _model(exchange)
    activity = []
    harness = LangGraphHarness(
        model,
        backend=_backend(repo),
        player_config=config(repo),
        on_model_activity=lambda: activity.append(1),
    )
    from deepagents_code.agent import create_cli_agent

    supplied: list[dict[str, Any]] = []

    def observe(*args: Any, **kwargs: Any) -> Any:
        supplied.append(kwargs)
        return create_cli_agent(*args, **kwargs)

    try:
        with patch("deepagents_code.agent.create_cli_agent", side_effect=observe):
            graph = harness._create_agent(role="player", cwd=repo, resolved_model=model)
        assert graph.guardkit_dcode_evidence["model"]["alias"] == "qwen36-workhorse"
        assert graph.guardkit_dcode_backend.default.default is harness.backend
        events = asyncio.run(_collect(harness, repo))
    finally:
        _close_clients(sync, async_)
    results = [str(e.content) for e in events if isinstance(e, ToolResultEvent)]
    assert any("ERROR invalid.py:1" in item for item in results)
    assert any("CHECKED valid.py" in item for item in results)
    assert any("1 failed" in item for item in results)
    assert any("1 passed" in item for item in results)
    assert hashlib.sha256(acceptance.read_bytes()).hexdigest() == digest
    assert "return a * b" in (repo / "calculator.py").read_text()
    terminal = next(e for e in events if isinstance(e, ResultMessageEvent))
    assistant = next(e for e in events if isinstance(e, AssistantMessageEvent))
    assert terminal.session_id is None and harness.supports_resume is False
    assert terminal.stop_reason == "stop" and terminal.usage["total_tokens"] == 110
    assert isinstance(terminal.raw, AIMessage) and terminal.raw is assistant.raw["messages"][-1]
    assert assistant.text == "dcode repaired the product" and activity
    assert supplied[0]["cwd"] == repo.resolve()
    assert supplied[0]["project_context"].user_cwd == repo.resolve()
    assert supplied[0]["project_context"].project_root == repo.resolve()
    assert "planning" in exchange.requests[0]["system"]
    assert "# Coding instructions" in exchange.requests[0]["system"]
    supplied_messages = str(exchange.bodies[0]["messages"])
    assert "Factory-supplied project context" in supplied_messages
    assert "./qa/run-suite.sh --exact" in supplied_messages
    assert "product_tests" in supplied_messages
    assert "Complete the checked change." in supplied_messages
    assert "Documents to read first" in supplied_messages
    assert "[selected skill]" in supplied_messages
    assert "[project-declared document]" not in supplied_messages
    assert "compact_conversation" in exchange.requests[0]["offered"]
    assert all(
        b["model"] == "qwen36-workhorse"
        and b["temperature"] == 0
        and b["max_completion_tokens"] == 8192
        for b in exchange.bodies
    )
    evidence(
        "repair",
        {
            "inventory": graph.guardkit_dcode_evidence,
            "requests": exchange.bodies,
            "results": results,
            "activity": len(activity),
            "acceptance_sha256": digest,
        },
    )


def test_protected_file_is_readable_but_refused_for_writes_in_a_full_turn(
    tmp_path: Path,
) -> None:
    """A full Player turn over a declared-protected file whose content was set up
    beforehand.

    The test writes the file's bytes itself; it does not run any approval or
    amendment path (that belongs to Forge's tests). It shows that the Player
    can read the file and write elsewhere, that its write and edit of the
    protected file are refused with the new wording, and that the sync and
    async backend paths refuse too, leaving the bytes unchanged.
    """

    from guardkitfactory.harness.backend_config import build_autobuild_backend

    repo = _scaffold(tmp_path)
    stack = repo / "docs" / "product" / "stack.md"
    stack.parent.mkdir(parents=True)
    original = "# Stack\n\n- dependency-a 2.0\n- dependency-b 1.4\n"
    stack.write_text(original)

    selected = build_player_config(
        cwd=repo,
        dcode_home=os.environ["DEEPAGENTS_HOME"],
        skills=["skills"],
        memory=["AGENTS.md"],
        repository_instructions=["AGENTS.md"],
        protected_paths=["docs/product/stack.md"],
    )
    backend = build_autobuild_backend(repo, protected_paths=["docs/product/stack.md"])
    notes = repo / "docs" / "product" / "notes.md"
    exchange = Exchange(
        [
            *selected_skill_calls(repo),
            ("read_file", {"file_path": str(stack), "limit": 100}),
            ("write_file", {"file_path": str(notes), "content": "builder notes\n"}),
            ("write_file", {"file_path": str(stack), "content": "# Stack\n"}),
            (
                "edit_file",
                {
                    "file_path": str(stack),
                    "old_string": "dependency-a 2.0",
                    "new_string": "dependency-a 1.0",
                },
            ),
        ],
        final_text="the stack document needs another change; it is protected",
    )
    model, sync, async_ = _model(exchange)
    harness = LangGraphHarness(model, backend=backend, player_config=selected)
    try:
        events = asyncio.run(_collect(harness, repo))
    finally:
        _close_clients(sync, async_)

    assert any(isinstance(event, ResultMessageEvent) for event in events)
    [read] = tool_results(exchange, "call-2")
    assert "dependency-b 1.4" in read
    assert notes.read_text() == "builder notes\n"
    protected = "This file is protected. Do not retry or work around it."
    [refused_write] = tool_results(exchange, "call-4")
    [refused_edit] = tool_results(exchange, "call-5")
    assert protected in refused_write and protected in refused_edit
    assert stack.read_text() == original

    assert protected in backend.write(str(stack), "x\n").error
    assert protected in backend.edit(str(stack), "2.0", "1.0").error
    assert protected in asyncio.run(backend.awrite(str(stack), "x\n")).error
    assert protected in asyncio.run(backend.aedit(str(stack), "2.0", "1.0")).error
    assert stack.read_text() == original


def test_a_new_file_in_a_protected_folder_is_written_in_a_full_turn(
    tmp_path: Path,
) -> None:
    """26 October 2026 (step 2; re-run feature 5, census GKF-109 and GKF-072).

    The plan needed a new design-decision record in a protected folder. In a
    full Player turn the new record is written and then edited, the existing
    record in the same folder is still refused, and a declared protected path
    that does not exist yet is skipped instead of refusing the Player. The
    sync and async backend routes agree.
    """

    from guardkitfactory.harness.backend_config import build_autobuild_backend

    repo = _scaffold(tmp_path)
    decisions = repo / "docs" / "design" / "decisions"
    decisions.mkdir(parents=True)
    existing = decisions / "DDR-001-existing.md"
    existing.write_text("# DDR-001\n\nDecided.\n")
    declared = ["docs/design/decisions", "docs/design/not-yet"]

    selected = build_player_config(
        cwd=repo,
        dcode_home=os.environ["DEEPAGENTS_HOME"],
        skills=["skills"],
        memory=["AGENTS.md"],
        repository_instructions=["AGENTS.md"],
        protected_paths=declared,
    )
    assert selected.protected_paths == (decisions.resolve(),)
    backend = build_autobuild_backend(repo, protected_paths=declared)
    record = decisions / "DDR-111-validation-errors.md"
    exchange = Exchange(
        [
            *selected_skill_calls(repo),
            ("write_file", {"file_path": str(record), "content": "# DDR-111\n\nDraft.\n"}),
            (
                "edit_file",
                {"file_path": str(record), "old_string": "Draft.", "new_string": "Accepted."},
            ),
            ("write_file", {"file_path": str(existing), "content": "# replaced\n"}),
        ],
        final_text="the design-decision record is written",
    )
    model, sync, async_ = _model(exchange)
    harness = LangGraphHarness(model, backend=backend, player_config=selected)
    try:
        events = asyncio.run(_collect(harness, repo))
    finally:
        _close_clients(sync, async_)

    assert any(isinstance(event, ResultMessageEvent) for event in events)
    assert record.read_text() == "# DDR-111\n\nAccepted.\n"
    protected = "This file is protected. Do not retry or work around it."
    [refused] = tool_results(exchange, "call-4")
    assert protected in refused
    assert existing.read_text() == "# DDR-001\n\nDecided.\n"

    other = decisions / "DDR-112-async.md"
    assert asyncio.run(backend.awrite(str(other), "# DDR-112\n")).error is None
    assert protected in asyncio.run(backend.aedit(str(existing), "Decided", "x")).error
    assert protected in backend.edit(str(existing), "Decided", "x").error
    assert other.read_text() == "# DDR-112\n"


_REFUSAL = "Read these required documents in full before running commands: "


def tool_results(exchange: Exchange, call_id: str) -> list[str]:
    """The tool results the model was sent for one call id, in order."""

    return [
        str(message.get("content", ""))
        for body in exchange.bodies
        for message in body.get("messages", [])
        if message.get("role") == "tool" and message.get("tool_call_id") == call_id
    ][:1]


def test_selected_skill_complete_read_normalizes_crlf(tmp_path: Path) -> None:
    repo = _scaffold(tmp_path)
    planning = (repo / "skills/planning/SKILL.md").resolve()
    planning.write_bytes(planning.read_bytes().replace(b"\n", b"\r\n"))
    exchange = Exchange(selected_skill_calls(repo), final_text="CRLF skill consumed")
    model, sync, async_ = _model(exchange)
    harness = LangGraphHarness(model, backend=_backend(repo), player_config=config(repo))
    try:
        events = asyncio.run(_collect(harness, repo))
        assert any(isinstance(event, ResultMessageEvent) for event in events)
    finally:
        _close_clients(sync, async_)


@pytest.mark.parametrize("text,finish", [("", "stop"), ("", "length"), ("partial", "length")])
def test_an_empty_or_cut_off_final_answer_ends_the_turn_as_usual(
    tmp_path: Path, text: str, finish: str
) -> None:
    # The edits are what matter; the turn ends whatever the answer says.
    repo = _scaffold(tmp_path)
    exchange = Exchange(
        [("read_file", {"file_path": str(repo / "AGENTS.md")})],
        final_text=text,
        finish_reason=finish,
    )
    model, sync, async_ = _model(exchange)
    harness = LangGraphHarness(model, backend=_backend(repo), player_config=config(repo))
    received = []

    async def run() -> None:
        async for event in harness.invoke(
            "read then answer", "player", [], repo, timeout_seconds=60
        ):
            received.append(event)

    try:
        asyncio.run(run())
        [result] = [event for event in received if isinstance(event, ResultMessageEvent)]
        assert result.stop_reason == finish
        assert harness._ainvoke_task is None
    finally:
        _close_clients(sync, async_)


_ADVICE_KINDS = (
    "source_removed",
    "extra_skill",
    "duplicate",
    "escape",
    "extra_memory",
    "changed",
)


@pytest.mark.parametrize(
    "kind",
    [
        # Refused: the wrong folder, a backend naming none, the local model.
        # (Custom subagents: test_a_valid_custom_subagent_naming_a_hosted_model_cannot_run.)
        "sibling",
        "opaque",
        "endpoint",
        "unresolved",
        # The Player starts with what is there.
        *_ADVICE_KINDS,
    ],
)
def test_refusals_before_model_activity_and_what_starts(tmp_path: Path, kind: str) -> None:
    repo = _scaffold(tmp_path)
    selected = config(repo)
    exchange = Exchange([])
    model, sync, async_ = _model(exchange)
    backend = _backend(repo)
    if kind == "sibling":
        sibling = tmp_path / "sibling"
        sibling.mkdir()
        backend = _backend(sibling)
    elif kind == "opaque":
        backend = SimpleNamespace(artifacts_root=repo)
    elif kind == "source_removed":
        (repo / "AGENTS.md").unlink()
    elif kind == "endpoint":
        model.openai_api_base = "http://other.test/v1"
    elif kind == "unresolved":
        model = "unknown:model"
    elif kind == "extra_skill":
        extra = repo / ".claude/skills/unselected"
        extra.mkdir(parents=True)
        (extra / "SKILL.md").write_text("---\nname: unselected\n---\n")
    elif kind == "duplicate":
        (repo / ".deepagents").mkdir()
        (repo / ".deepagents/skills").symlink_to("../skills")
    elif kind == "escape":
        (repo / "skills/escape").symlink_to(tmp_path)
    elif kind == "extra_memory":
        (repo / ".deepagents").mkdir()
        (repo / ".deepagents/AGENTS.md").write_text("extra")
    harness = LangGraphHarness(model, backend=backend, player_config=selected)
    try:
        if kind == "changed":
            from deepagents_code.agent import create_cli_agent

            def changing(*args: Any, **kwargs: Any) -> Any:
                result = create_cli_agent(*args, **kwargs)
                (repo / "skills/planning/SKILL.md").write_text(
                    "---\nname: planning\ndescription: valid changed skill\n---\nchanged"
                )
                return result

            with patch("deepagents_code.agent.create_cli_agent", side_effect=changing):
                events = asyncio.run(_collect(harness, repo))
            assert any(isinstance(event, ResultMessageEvent) for event in events)
            assert exchange.requests
            return
        if kind in _ADVICE_KINDS:
            events = asyncio.run(_collect(harness, repo))
            assert any(isinstance(event, ResultMessageEvent) for event in events)
            assert exchange.requests
            return
        with pytest.raises(LangGraphHarnessError):
            asyncio.run(_collect(harness, repo))
        assert not exchange.requests
    finally:
        _close_clients(sync, async_)


def test_a_valid_custom_subagent_naming_a_hosted_model_cannot_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Step 2 review R1 (27 October 2026): a frontier model on the build path
    # is a safety fence. dcode resolves a custom subagent's declared model
    # itself, so the launch stops before dcode builds the agent at all.
    from deepagents_code.subagents import list_subagents

    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-the-test")
    repo = _scaffold(tmp_path)
    definition = repo / ".deepagents/agents/researcher/AGENTS.md"
    definition.parent.mkdir(parents=True)
    definition.write_text(
        "---\nname: researcher\ndescription: Researches things\n"
        "model: anthropic:claude-sonnet-4-6\n---\nResearch.\n"
    )
    [declared] = list_subagents(project_agents_dir=repo / ".deepagents/agents")
    assert declared["model"] == "anthropic:claude-sonnet-4-6"
    exchange = Exchange([])
    model, sync, async_ = _model(exchange)
    harness = LangGraphHarness(model, backend=_backend(repo), player_config=config(repo))
    try:
        with patch("deepagents_code.agent.create_cli_agent") as build:
            with pytest.raises(LangGraphHarnessError, match="custom subagents"):
                asyncio.run(_collect(harness, repo))
        build.assert_not_called()
        assert not exchange.requests
    finally:
        _close_clients(sync, async_)


def response(
    body: dict[str, Any],
    *,
    call: tuple[str, dict[str, Any]] | None = None,
    text: str = "completed",
    tokens: int = 100,
    index: int = 0,
) -> httpx.Response:
    message: dict[str, Any] = {"role": "assistant", "content": text}
    if call:
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": f"step-{index}",
                    "type": "function",
                    "function": {"name": call[0], "arguments": json.dumps(call[1])},
                }
            ],
        }
    return httpx.Response(
        200,
        json={
            "id": f"chat-{index}",
            "object": "chat.completion",
            "created": 1,
            "model": body["model"],
            "choices": [
                {"index": 0, "message": message, "finish_reason": "tool_calls" if call else "stop"}
            ],
            "usage": {
                "prompt_tokens": tokens,
                "completion_tokens": 10,
                "total_tokens": tokens + 10,
            },
        },
    )


class ArtifactExchange:
    def __init__(self, repo: Path) -> None:
        self.repo = repo
        self.bodies: list[dict[str, Any]] = []
        self.index = 0
        self.summary_count = 0
        self.references: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.bodies.append(body)
        assert request.url.path == "/v1/chat/completions"
        assert body["model"] == "qwen36-workhorse"
        if not body.get("tools"):
            self.summary_count += 1
            return response(
                body, text="SUMMARY_SENTINEL preserve artifact tests", index=len(self.bodies)
            )
        index = self.index
        self.index += 1
        skill_calls = selected_skill_calls(self.repo)
        if index < len(skill_calls):
            call = skill_calls[index]
        elif index == 2:
            call = ("execute", {"command": "python -c \"print('LARGE_SENTINEL ' * 10000)\""})
        elif index == 3:
            rendered = "\n".join(str(m.get("content", "")) for m in body["messages"])
            alias = re.search(r"/large_tool_results/[a-zA-Z0-9_.-]+", rendered)[0]
            self.references.append(alias)
            call = ("read_file", {"file_path": alias, "limit": 5})
        elif index < 11:
            call = ("read_file", {"file_path": str(self.repo / "long.txt"), "limit": 1000})
        elif index == 11:
            call = ("compact_conversation", {})
        elif index == 12:
            rendered = "\n".join(str(m.get("content", "")) for m in body["messages"])
            alias = re.search(r"/conversation_history/[a-zA-Z0-9_./-]+", rendered)[0].rstrip(".")
            self.references.append(alias)
            call = ("read_file", {"file_path": alias, "limit": 5})
        elif index == 13:
            call = (
                "write_file",
                {"file_path": str(self.repo.parent / "outside.txt"), "content": "BLOCK_ME"},
            )
        else:
            return response(body, text="artifacts round-tripped", index=index)
        return response(body, call=call, tokens=65000 if index >= 8 else 100, index=index)


def test_real_graph_forced_compaction_and_large_result_round_trip(tmp_path: Path) -> None:
    repo = _scaffold(tmp_path)
    (repo / "long.txt").write_text("HISTORY_SENTINEL " * 2500)
    immutable = repo / "acceptance.txt"
    immutable.write_text("IMMUTABLE_ACCEPTANCE")
    # A real git checkout, so the artifacts take the production route: the
    # private folder in the worktree's own git directory (14 October 2026).
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    exchange = ArtifactExchange(repo)
    model, sync, async_ = _model(exchange)
    activity = []
    backend = _backend(repo)
    private = Path(backend.artifacts_root)
    assert private == (repo / ".git" / "guardkit-scratch" / "model-artifacts").resolve()
    harness = LangGraphHarness(
        model,
        backend=backend,
        player_config=config(repo),
        on_model_activity=lambda: activity.append(1),
        recursion_limit=200,
    )
    try:
        events = asyncio.run(_collect(harness, repo))
    finally:
        _close_clients(sync, async_)
    assert exchange.summary_count >= 1
    assert len(exchange.references) == 2
    assert not (repo.parent / "outside.txt").exists()
    assert immutable.read_text() == "IMMUTABLE_ACCEPTANCE"
    results = [str(e.content) for e in events if isinstance(e, ToolResultEvent)]
    assert any("LARGE_SENTINEL" in value for value in results)
    assert any("outside" in value.lower() or "not permitted" in value.lower() for value in results)
    assert any(
        "HISTORY_SENTINEL" in p.read_text()
        for p in (private / "conversation_history").rglob("*")
        if p.is_file()
    )
    assert any("SUMMARY_SENTINEL" in str(b["messages"]) for b in exchange.bodies)
    # Both aliases came from model-visible references and were sent through the
    # real read_file tool, whose replies must not be missing-path errors.
    assert not any("does not exist" in value or "File not found" in value for value in results)
    artifacts = {}
    for name in ("conversation_history", "large_tool_results"):
        files = [p for p in (private / name).rglob("*") if p.is_file()]
        assert files
        artifacts[name] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        assert all(p.resolve().is_relative_to(private / name) for p in files)
        # Nothing of the model's own lands in the worktree, where a
        # checkpoint commit would take it.
        assert not (repo / name).exists()
        assert ((private / name).stat().st_mode & 0o777) == 0o700
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=repo, check=True, capture_output=True, text=True,
    ).stdout
    assert "conversation_history" not in status and "large_tool_results" not in status
    assert activity
    assert all(
        b["max_completion_tokens"] == 8192 and b["temperature"] == 0 for b in exchange.bodies
    )
    evidence(
        "artifacts",
        {
            "requests": exchange.bodies,
            "files": artifacts,
            "references": exchange.references,
            "results": results,
            "summaries": exchange.summary_count,
        },
    )


def test_real_inherited_subagent_uses_same_model(tmp_path: Path) -> None:
    repo = _scaffold(tmp_path)
    bodies = []

    def exchange(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies.append(body)
        index = len(bodies)
        if index <= 2:
            return response(body, call=selected_skill_calls(repo)[index - 1], index=index)
        if index == 3:
            return response(
                body,
                call=(
                    "task",
                    {
                        "subagent_type": "general-purpose",
                        "description": "Read AGENTS.md and report NESTED_SENTINEL",
                    },
                ),
                index=index,
            )
        if index == 4:
            return response(
                body, call=("read_file", {"file_path": str(repo / "AGENTS.md")}), index=index
            )
        return response(body, text="NESTED_SENTINEL complete", index=index)

    model, sync, async_ = _model(exchange)
    activity = []
    harness = LangGraphHarness(
        model,
        backend=_backend(repo),
        player_config=config(repo),
        on_model_activity=lambda: activity.append(1),
    )
    try:
        events = asyncio.run(_collect(harness, repo))
    finally:
        _close_clients(sync, async_)
    assert len(bodies) == 6 and activity
    assert all(
        b["model"] == "qwen36-workhorse"
        and b["temperature"] == 0
        and b["max_completion_tokens"] == 8192
        for b in bodies
    )
    assert any(
        "NESTED_SENTINEL" in str(e.content) for e in events if isinstance(e, ToolResultEvent)
    )
    evidence("subagent", {"requests": bodies, "activity": len(activity)})


@pytest.mark.parametrize("phase", ["main", "nested", "compaction"])
@pytest.mark.parametrize("method", ["cancel", "timeout"])
def test_nested_cancellation_settles(tmp_path: Path, phase: str, method: str) -> None:
    repo = _scaffold(tmp_path)
    (repo / "long.txt").write_text("HISTORY_SENTINEL " * 2500)
    bodies = []
    activity = []

    async def run() -> None:
        started = asyncio.Event()
        cancelled = asyncio.Event()
        compaction_tool_calls = 0

        class Blocking(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                nonlocal compaction_tool_calls
                body = json.loads(request.content)
                bodies.append(body)
                index = len(bodies)
                if phase == "nested" and index == 1:
                    return response(
                        body,
                        call=(
                            "task",
                            {"subagent_type": "general-purpose", "description": "NESTED_CANCEL"},
                        ),
                        index=index,
                    )
                if phase == "compaction" and body.get("tools"):
                    compaction_tool_calls += 1
                    if compaction_tool_calls <= 2:
                        call = selected_skill_calls(repo)[compaction_tool_calls - 1]
                    elif compaction_tool_calls < 10:
                        call = (
                            "read_file",
                            {"file_path": str(repo / "long.txt"), "limit": 1000},
                        )
                    else:
                        call = ("compact_conversation", {})
                    return response(
                        body,
                        call=call,
                        tokens=65000 if compaction_tool_calls >= 9 else 100,
                        index=index,
                    )
                started.set()
                try:
                    await asyncio.Future()
                except asyncio.CancelledError:
                    cancelled.set()
                    raise

        model, sync, unused = _model(Exchange([]))
        await unused.aclose()
        client = httpx.AsyncClient(transport=Blocking())
        # Rebuild so both the LangChain model and provider use the blocking client.
        from langchain_openai import ChatOpenAI

        model = ChatOpenAI(
            model="qwen36-workhorse",
            base_url="http://fake.test/v1",
            api_key="synthetic",
            use_responses_api=False,
            temperature=0,
            max_tokens=8192,
            profile={"max_input_tokens": 131072},
            http_client=sync,
            http_async_client=client,
            max_retries=0,
            disable_streaming=True,
            http_socket_options=(),
        )
        harness = LangGraphHarness(
            model,
            backend=_backend(repo),
            player_config=config(repo),
            on_model_activity=lambda: activity.append(1),
            recursion_limit=200,
        )
        received = []
        generator = harness.invoke("cancel this test", "player", [], repo, timeout_seconds=60)

        async def consume() -> None:
            async for event in generator:
                received.append(event)

        task = asyncio.create_task(consume())
        try:
            await asyncio.wait_for(started.wait(), 10)
            if method == "cancel":
                await harness.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                with pytest.raises(TimeoutError):
                    await asyncio.wait_for(task, 0.01)
            await generator.aclose()
            assert cancelled.is_set() and not received and harness._ainvoke_task is None
            assert activity
            pending = [
                t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()
            ]
            assert not pending
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await generator.aclose()
            await client.aclose()
            sync.close()

    asyncio.run(run())
    evidence(
        f"cancel-{phase}-{method}",
        {"requests": bodies, "activity": len(activity), "pending": 0, "success_events": 0},
    )


def test_aclose_does_not_deliver_success(tmp_path: Path) -> None:
    repo = _scaffold(tmp_path)
    exchange = Exchange(
        [*selected_skill_calls(repo), ("read_file", {"file_path": str(repo / "AGENTS.md")})]
    )
    model, sync, async_ = _model(exchange)
    harness = LangGraphHarness(model, backend=_backend(repo), player_config=config(repo))

    async def run() -> None:
        generator = harness.invoke("read", "player", [], repo, timeout_seconds=60)
        first = await anext(generator)
        assert not isinstance(first, ResultMessageEvent)
        await generator.aclose()
        assert harness._ainvoke_task is None
        assert not [
            t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()
        ]

    try:
        asyncio.run(run())
    finally:
        _close_clients(sync, async_)


def test_provider_error_has_no_dcode_retry_or_success(tmp_path: Path) -> None:
    repo = _scaffold(tmp_path)
    requests = []

    def reject(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(
            400,
            json={"error": {"message": "provider test rejection", "type": "invalid_request_error"}},
        )

    model, sync, async_ = _model(reject)
    harness = LangGraphHarness(model, backend=_backend(repo), player_config=config(repo))
    try:
        with pytest.raises(LangGraphHarnessError, match="provider test rejection"):
            asyncio.run(_collect(harness, repo))
        assert len(requests) == 1 and harness._ainvoke_task is None
    finally:
        _close_clients(sync, async_)


@pytest.mark.parametrize("provider_retries", [0, 2])
def test_compaction_error_has_only_provider_retry_budget(
    tmp_path: Path, provider_retries: int
) -> None:
    repo = _scaffold(tmp_path)
    (repo / "long.txt").write_text("HISTORY_SENTINEL " * 2500)
    main_count = 0
    summary_requests = []

    def exchange(request: httpx.Request) -> httpx.Response:
        nonlocal main_count
        body = json.loads(request.content)
        if not body.get("tools"):
            summary_requests.append(body)
            return httpx.Response(
                429,
                headers={"retry-after-ms": "1"},
                json={"error": {"message": "SUMMARY_RATE_LIMIT", "type": "rate_limit_error"}},
            )
        main_count += 1
        if main_count <= 2:
            return response(
                body,
                call=selected_skill_calls(repo)[main_count - 1],
                index=main_count,
            )
        if main_count < 10:
            return response(
                body,
                call=("read_file", {"file_path": str(repo / "long.txt"), "limit": 1000}),
                tokens=65000 if main_count == 7 else 100,
                index=main_count,
            )
        if main_count == 10:
            return response(body, call=("compact_conversation", {}), tokens=65000, index=main_count)
        return response(
            body, text="Compaction failed; preserved the conversation", index=main_count
        )

    from langchain_openai import ChatOpenAI

    transport = httpx.MockTransport(exchange)
    sync = httpx.Client(transport=transport)
    async_ = httpx.AsyncClient(transport=transport)
    model = ChatOpenAI(
        model="qwen36-workhorse",
        base_url="http://fake.test/v1",
        api_key="synthetic",
        use_responses_api=False,
        temperature=0,
        max_tokens=8192,
        profile={"max_input_tokens": 131072},
        http_client=sync,
        http_async_client=async_,
        max_retries=provider_retries,
        disable_streaming=True,
        http_socket_options=(),
    )
    harness = LangGraphHarness(
        model, backend=_backend(repo), player_config=config(repo), recursion_limit=200
    )
    try:
        from deepagents_code.agent import create_cli_agent

        supplied = []

        def observe(*args: Any, **kwargs: Any) -> Any:
            supplied.append(kwargs["model"])
            return create_cli_agent(*args, **kwargs)

        with patch("deepagents_code.agent.create_cli_agent", side_effect=observe):
            events = asyncio.run(_collect(harness, repo))
        assert len(summary_requests) == provider_retries + 1
        clone = supplied[0]
        assert (
            clone is not model and clone.http_client is sync and clone.http_async_client is async_
        )
        assert (
            clone.root_client is model.root_client
            and clone.root_async_client is model.root_async_client
        )
        assert clone.max_retries == model.max_retries == provider_retries
        assert not hasattr(model, "_deepagents_model_retries")
        assert any(
            "Compaction failed" in str(e.content) for e in events if isinstance(e, ToolResultEvent)
        )
        assert harness._ainvoke_task is None and not sync.is_closed and not async_.is_closed
        assert all(
            b["model"] == "qwen36-workhorse"
            and b["max_completion_tokens"] == 8192
            and b["temperature"] == 0
            for b in summary_requests
        )
        evidence(
            f"summary-error-retries-{provider_retries}",
            {
                "summary_requests": summary_requests,
                "attempts": len(summary_requests),
                "provider_retries": provider_retries,
                "dcode_retries": 0,
                "caller_clients_retained": True,
            },
        )
    finally:
        _close_clients(sync, async_)


def test_profile_controls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _scaffold(tmp_path)
    selected = config(repo)
    exchange = Exchange([])
    model, sync, async_ = _model(exchange)
    harness = LangGraphHarness(model, backend=_backend(repo), player_config=selected)
    try:
        with monkeypatch.context() as scoped:
            scoped.setenv("DEEPAGENTS_HOME", str(tmp_path))
            with pytest.raises(LangGraphHarnessError, match="does not match"):
                asyncio.run(_collect(harness, repo))
        from deepagents_code._paths import PATHS

        with patch(
            "deepagents_code._paths.PATHS", SimpleNamespace(profile=SimpleNamespace(root=tmp_path))
        ):
            with pytest.raises(LangGraphHarnessError, match="already-imported"):
                asyncio.run(_collect(harness, repo))
        assert PATHS.profile.root == selected.dcode_home
        assert not exchange.requests
    finally:
        _close_clients(sync, async_)


def test_dcode_without_selected_skills_or_instructions(tmp_path: Path) -> None:
    repo = tmp_path / "empty-task"
    repo.mkdir()
    selected = build_player_config(
        cwd=repo,
        dcode_home=os.environ["DEEPAGENTS_HOME"],
    )
    exchange = Exchange([])
    model, sync, async_ = _model(exchange)
    harness = LangGraphHarness(model, backend=_backend(repo), player_config=selected)
    try:
        events = asyncio.run(_collect(harness, repo))
        assert any(isinstance(event, ResultMessageEvent) for event in events)
        assert "# Coding instructions" not in exchange.requests[0]["system"]
        assert "<available_skills>" not in exchange.requests[0]["system"]
    finally:
        _close_clients(sync, async_)


@pytest.mark.parametrize(
    "setting", ["offline", "tracing", "home_mismatch", "already_imported", "endpoint_mismatch"]
)
def test_process_wide_launch_refusals_are_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, setting: str
) -> None:
    """Refusals fixed for the whole process repeat every turn, so they are typed too."""
    from guardkitfactory.harness import PlayerLaunchRefused
    from guardkitfactory.harness.dcode_harness import _validate_launch, create_dcode_player

    repo = tmp_path / "task"
    repo.mkdir()
    selected = build_player_config(cwd=repo, dcode_home=os.environ["DEEPAGENTS_HOME"])
    exchange = Exchange([])
    model, sync, async_ = _model(exchange)
    try:
        with pytest.raises(PlayerLaunchRefused) as refused:
            if setting == "offline":
                monkeypatch.delenv("DEEPAGENTS_CODE_OFFLINE")
                _validate_launch(selected)
            elif setting == "tracing":
                monkeypatch.setenv("LANGSMITH_TRACING", "true")
                _validate_launch(selected)
            elif setting == "home_mismatch":
                monkeypatch.setenv("DEEPAGENTS_HOME", str(tmp_path))
                _validate_launch(selected)
            elif setting == "endpoint_mismatch":
                monkeypatch.setenv("OPENAI_BASE_URL", "http://other.test/v1")
                create_dcode_player(
                    model=model,
                    backend=_backend(repo),
                    cwd=repo,
                    config=selected,
                    recursion_limit=None,
                )
            else:
                with patch(
                    "deepagents_code._paths.PATHS",
                    SimpleNamespace(profile=SimpleNamespace(root=tmp_path)),
                ):
                    create_dcode_player(
                        model=model,
                        backend=_backend(repo),
                        cwd=repo,
                        config=selected,
                        recursion_limit=None,
                    )
        error = refused.value
        assert error.failure_kind == "agent_launch_refused"
        assert error.profile == str(selected.dcode_home)
        assert not exchange.requests
    finally:
        _close_clients(sync, async_)


def test_resolved_comparison_defaults_across_main_subagent_compaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The local model is built from its alias; the client needs a key to
    # exist (the GitHub workflow sets none).
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test")
    repo = _scaffold(tmp_path)
    (repo / "long.txt").write_text("HISTORY_SENTINEL " * 2500)
    artifact = ArtifactExchange(repo)
    requests = []
    supplied = []
    clients = []

    def exchange(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        if len(requests) <= 2:
            return response(
                body,
                call=selected_skill_calls(repo)[len(requests) - 1],
                index=898 + len(requests),
            )
        if len(requests) == 3:
            return response(
                body,
                call=(
                    "task",
                    {"subagent_type": "general-purpose", "description": "DEFAULT_NESTED_SENTINEL"},
                ),
                index=900,
            )
        if len(requests) == 4:
            return response(body, text="DEFAULT_NESTED_SENTINEL complete", index=901)
        return artifact(request)

    transport = httpx.MockTransport(exchange)

    def sync_builder(*args: Any, **kwargs: Any) -> httpx.Client:
        client = httpx.Client(transport=transport)
        clients.append(client)
        return client

    def async_builder(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        client = httpx.AsyncClient(transport=transport)
        clients.append(client)
        return client

    from deepagents_code.agent import create_cli_agent

    def observe(*args: Any, **kwargs: Any) -> Any:
        supplied.append(kwargs["model"])
        return create_cli_agent(*args, **kwargs)

    harness = LangGraphHarness(
        "openai:qwen36-workhorse",
        backend=_backend(repo),
        player_config=config(repo),
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
        patch("deepagents_code.agent.create_cli_agent", side_effect=observe),
    ):
        events = asyncio.run(_collect(harness, repo))
    assert any(isinstance(e, ResultMessageEvent) for e in events)
    assert artifact.summary_count >= 1
    assert all(
        b["model"] == "qwen36-workhorse" and b["max_completion_tokens"] == 8192 for b in requests
    )
    assert all(
        "temperature" not in b
        and "top_p" not in b
        and "reasoning_effort" not in b
        and "extra_body" not in b
        for b in requests
    )
    assert supplied[0].profile["max_input_tokens"] == 131072
    assert supplied[0].root_async_client.max_retries == 2
    assert supplied[0]._deepagents_model_retries == 0
    assert len(clients) == 2 and all(c.is_closed for c in clients)
    assert harness._ainvoke_task is None
    evidence(
        "comparison-defaults",
        {
            "requests": requests,
            "profile": supplied[0].profile,
            "provider_retries": 2,
            "dcode_retries": 0,
            "owned_clients_closed": True,
        },
    )


def test_player_replays_its_thinking_on_main_helper_and_compaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Coding speed fix A: every Player request hands back the earlier thinking.

    The fake server attaches unique thinking to every reply. Each later request
    must carry that thinking on the matching assistant message, on the main
    loop, inside the inherited helper agent, and after compaction. The
    construction inventory must say the replay is on.
    """
    from guardkitfactory.harness.reasoning_replay import ReasoningReplayChatOpenAI

    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test")
    repo = _scaffold(tmp_path)
    (repo / "long.txt").write_text("HISTORY_SENTINEL " * 2500)
    artifact = ArtifactExchange(repo)
    requests: list[dict[str, Any]] = []
    thinking: dict[str, str] = {}
    supplied: list[Any] = []
    graphs: list[Any] = []

    def scripted(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        n = len(requests)
        if n <= 2:
            return response(body, call=selected_skill_calls(repo)[n - 1], index=n)
        if n == 3:
            return response(
                body,
                call=(
                    "task",
                    {"subagent_type": "general-purpose", "description": "REPLAY_NESTED_SENTINEL"},
                ),
                index=n,
            )
        if n == 4:
            return response(
                body, call=("read_file", {"file_path": str(repo / "AGENTS.md")}), index=n
            )
        if n == 5:
            return response(body, text="REPLAY_NESTED_SENTINEL complete", index=n)
        return artifact(request)

    def exchange(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        n = len(requests)
        reply = scripted(request)
        payload = json.loads(reply.content)
        message = payload["choices"][0]["message"]
        message["reasoning_content"] = f"THINKING-{n}"
        for call in message.get("tool_calls") or []:
            # Unique ids pair each assistant message with the thinking sent on it.
            call["id"] = f"call-{n}"
            thinking[call["id"]] = message["reasoning_content"]
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(exchange)
    clients: list[Any] = []

    def sync_builder(*args: Any, **kwargs: Any) -> httpx.Client:
        clients.append(httpx.Client(transport=transport))
        return clients[-1]

    def async_builder(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        clients.append(httpx.AsyncClient(transport=transport))
        return clients[-1]

    from deepagents_code.agent import create_cli_agent

    def observe(*args: Any, **kwargs: Any) -> Any:
        supplied.append(kwargs["model"])
        built = create_cli_agent(*args, **kwargs)
        graphs.append(built[0])
        return built

    harness = LangGraphHarness(
        "openai:qwen36-workhorse",
        backend=_backend(repo),
        player_config=config(repo),
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
        patch("deepagents_code.agent.create_cli_agent", side_effect=observe),
    ):
        events = asyncio.run(_collect(harness, repo))
    assert any(isinstance(e, ResultMessageEvent) for e in events)
    assert artifact.summary_count >= 1
    assert isinstance(supplied[0], ReasoningReplayChatOpenAI)
    assert graphs[0].guardkit_dcode_evidence["model"]["reasoning_replay"] is True

    # The inherited helper continues the main conversation after a user turn
    # naming its task; its own steps follow that turn. The compaction request
    # itself sends the history as one plain-text user message (no assistant
    # entries), so compaction is checked on the main requests that follow it.
    checked = {"main": 0, "helper": 0, "after_compaction": 0}
    for body in requests:
        phase = "after_compaction" if "SUMMARY_SENTINEL" in json.dumps(body) else "main"
        for message in body["messages"]:
            if message["role"] == "user" and "REPLAY_NESTED_SENTINEL" in str(message["content"]):
                phase = "helper"
            if message["role"] != "assistant":
                assert "reasoning_content" not in message
                continue
            if not message.get("tool_calls"):
                continue
            call_id = message["tool_calls"][0]["id"]
            assert message.get("reasoning_content") == thinking[call_id], (phase, call_id)
            checked[phase] += 1
    assert all(count > 0 for count in checked.values()), checked
    evidence("reasoning-replay", {"checked": checked, "requests": len(requests)})


def test_inventory_reports_no_replay_for_a_plain_model(monkeypatch: pytest.MonkeyPatch) -> None:
    from langchain_openai import ChatOpenAI

    from guardkitfactory.harness.dcode_harness import _validate_model
    from guardkitfactory.harness.reasoning_replay import ReasoningReplayChatOpenAI

    for cls, expected in ((ChatOpenAI, False), (ReasoningReplayChatOpenAI, True)):
        model = cls(
            model="qwen36-workhorse",
            base_url="http://fake.test/v1",
            api_key="synthetic-test",
            use_responses_api=False,
        )
        settings = _validate_model(model, SimpleNamespace(dcode_home=None))
        assert settings["reasoning_replay"] is expected


# --- Project-declared supporting documents (Lane A) -------------------------


def test_declared_documents_join_the_required_reads(tmp_path: Path) -> None:
    """The declared document is named to the Player after the skill bodies."""

    repo = _scaffold(tmp_path)
    document = declare_document(repo)
    exchange = Exchange(
        [*selected_skill_calls(repo), read_call(document)],
        final_text="declared documents consumed",
    )
    model, sync, async_ = _model(exchange)
    harness = LangGraphHarness(
        model, backend=_backend(repo), player_config=config_with_documents(repo)
    )
    try:
        events = asyncio.run(_collect(harness, repo))
        assert any(isinstance(event, ResultMessageEvent) for event in events)
        from guardkitfactory.harness.dcode_harness import required_skill_reads

        required = required_skill_reads(config_with_documents(repo))
        assert [item["kind"] for item in required] == ["skill", "skill", "declared_document"]
        assert required[-1]["relative_path"].endswith("references/project-conventions.md")
        supplied = str(exchange.bodies[0]["messages"])
        assert "Documents to read first" in supplied
        assert "[project-declared document]" in supplied
        assert "project-conventions.md" in supplied
    finally:
        _close_clients(sync, async_)


def test_skill_only_declaration_is_unchanged(tmp_path: Path) -> None:
    """Positive control: no declaration means exactly the previous required set."""

    from guardkitfactory.harness.dcode_harness import required_skill_reads

    repo = _scaffold(tmp_path)
    declare_document(repo)
    selected = config(repo)

    assert selected.required_documents == ()
    required = required_skill_reads(selected)
    assert [item["kind"] for item in required] == ["skill", "skill"]
    assert [Path(item["path"]).name for item in required] == ["SKILL.md", "SKILL.md"]
