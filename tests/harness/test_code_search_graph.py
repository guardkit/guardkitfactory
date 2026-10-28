"""The code search tools through the real Player and Coach graphs.

A scripted model (fake provider HTTP, no network) calls each tool; the test
reads what the model actually received back. Skipped unless the pinned
programs are installed, because the point is the real programs through the
real caller and consumer.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from guardkit.orchestrator.harness import ToolResultEvent

from guardkitfactory import code_search
from guardkitfactory.harness.code_search_tools import (
    SNAPSHOT_ONLY_TOOL_NAMES,
    TOOL_NAMES,
    code_search_tools,
)
from guardkitfactory.harness.langgraph_harness import LangGraphHarness

from .test_dcode_harness import Exchange, config, isolate, selected_skill_calls  # noqa: F401
from .test_player_skills_graph import _backend, _close_clients, _collect, _model, _scaffold

_READY, _WHY = code_search.available()
#: What a worktree binding (the Player's and the Coach's) offers.
WORKTREE_TOOL_NAMES = tuple(n for n in TOOL_NAMES if n not in SNAPSHOT_ONLY_TOOL_NAMES)
pytestmark = [
    pytest.mark.skipif(not _READY, reason=f"pinned programs not installed: {_WHY}"),
    pytest.mark.skipif(
        sys.version_info < (3, 12) or importlib.util.find_spec("deepagents_code") is None,
        reason="dcode graph acceptance requires Python 3.12+ and the required dependency",
    ),
]


def _git_init(repo: Path) -> None:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
    for args in (("init", "-q"), ("add", "-A"), ("commit", "-qm", "init")):
        subprocess.run(["git", "-C", str(repo), *args], check=True, env=env,
                       capture_output=True)


def _answers(events: list[Any]) -> list[dict[str, Any]]:
    found = []
    for event in events:
        if isinstance(event, ToolResultEvent):
            with_json = str(event.content)
            try:
                found.append(json.loads(with_json))
            except ValueError:
                continue
    return found


def test_player_graph_offers_and_runs_the_tools_on_its_worktree(tmp_path: Path) -> None:
    repo = _scaffold(tmp_path)
    _git_init(repo)
    # Written after the commit: only the worktree has it.
    (repo / "pending.py").write_text("def pending_marker():\n    return 1\n")
    exchange = Exchange(
        [
            ("code_search", {"query": "pending_marker", "mode": "literal"}),
            ("code_outline", {"path": "valid.py"}),
            ("code_pattern", {"pattern": "return $A + $B", "language": "python"}),
            *selected_skill_calls(repo),
        ],
        final_text="looked around",
    )
    model, sync, async_ = _model(exchange)
    harness = LangGraphHarness(model, backend=_backend(repo), player_config=config(repo))
    try:
        graph = harness._create_agent(role="player", cwd=repo, resolved_model=model)
        events = asyncio.run(_collect(harness, repo))
    finally:
        _close_clients(sync, async_)
    inventory = graph.guardkit_dcode_evidence
    assert set(WORKTREE_TOOL_NAMES) <= set(inventory["tools"])
    assert inventory["code_search"] == {"tools": list(WORKTREE_TOOL_NAMES), "unavailable": ""}
    assert set(WORKTREE_TOOL_NAMES) <= set(exchange.requests[0]["offered"])
    assert not set(SNAPSHOT_ONLY_TOOL_NAMES) & set(exchange.requests[0]["offered"])
    search, outline, pattern = _answers(events)[:3]
    # Run before any skill was read: the read gate lets read-only tools through.
    assert search["status"] == "ok"
    assert search["results"][0]["path"] == "pending.py"
    assert search["source"]["kind"] == "worktree"
    assert search["source"]["root"] == str(repo.resolve())
    assert search["source"]["untracked"] >= 1
    assert outline["status"] == "ok" and outline["results"][0]["name"] == "add"
    assert pattern["status"] == "ok" and pattern["results"][0]["path"] == "valid.py"


def test_coach_gather_graph_has_the_tools_and_synthesis_has_none(tmp_path: Path) -> None:
    repo = _scaffold(tmp_path)
    _git_init(repo)
    (repo / "candidate.py").write_text("def candidate_marker():\n    return 2\n")
    exchange = Exchange(
        [
            ("code_search", {"query": "candidate marker"}),
            ("code_outline", {"path": "candidate.py"}),
            ("code_pattern", {"pattern": "return $V", "language": "python",
                              "path": "candidate.py"}),
        ],
        final_text="findings: candidate_marker exists in candidate.py",
    )
    model, sync, async_ = _model(exchange)
    harness = LangGraphHarness(model, backend=_backend(repo))
    try:
        events = asyncio.run(
            _gather(harness, repo)
        )
        assert set(WORKTREE_TOOL_NAMES) <= set(exchange.requests[0]["offered"])
        search, outline, pattern = _answers(events)[:3]
        assert search["status"] == "ok"
        assert search["results"][0]["path"] == "candidate.py"
        assert outline["status"] == "ok" and outline["results"][0]["name"] == "candidate_marker"
        assert pattern["status"] == "ok" and pattern["results"][0]["path"] == "candidate.py"
        offered_before = len(exchange.requests)
        asyncio.run(_synthesis(harness, repo))
        synthesis_requests = exchange.requests[offered_before:]
        assert synthesis_requests and all(r["offered"] == [] for r in synthesis_requests)
    finally:
        _close_clients(sync, async_)


def test_the_read_only_coach_is_not_given_code_references(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The build reviewer's read-only request (Read, Search, Grep) keeps the
    shared allowlist (code_search_tools.TOOL_NAMES), but its worktree binding
    has no code_references: a builder could commit a declaration whose server
    runs its own code. It is not offered, and nothing is started, even with a
    server declared and installed."""
    servers = tmp_path / "servers"
    servers.mkdir()
    shutil.copy(Path(__file__).parent.parent / "fake_lsp_server.py", servers / "fake-lsp")
    (servers / "fake-lsp").chmod(0o755)
    monkeypatch.setattr(code_search, "LANGUAGE_SERVER_DIRS", ())
    monkeypatch.setenv(code_search.LANGUAGE_SERVER_DIR_ENV, str(servers))
    repo = _scaffold(tmp_path)
    pid_file = tmp_path / "server.pid"
    (repo / ".guardkit").mkdir()
    (repo / ".guardkit" / "config.yaml").write_text(json.dumps({"toolchain": {
        "language_servers": [{"command": ["fake-lsp"], "files": ["*.py"],
                              "env": {"FAKE_LSP_PID": str(pid_file)}}]}}))
    _git_init(repo)
    exchange = Exchange(
        [("code_search", {"query": "add", "mode": "literal"})],
        final_text="findings: add is defined in valid.py",
    )
    model, sync, async_ = _model(exchange)
    harness = LangGraphHarness(model, backend=_backend(repo))
    try:
        events = asyncio.run(_review(harness, repo))
    finally:
        _close_clients(sync, async_)
    for request in exchange.requests:
        assert set(WORKTREE_TOOL_NAMES) <= set(request["offered"])
        assert "code_references" not in request["offered"]
    (search,) = _answers(events)[:1]
    assert search["status"] == "ok"
    assert not pid_file.exists(), "a language server was started for a worktree"


async def _review(harness: LangGraphHarness, repo: Path) -> list[Any]:
    return [
        event
        async for event in harness.invoke(
            prompt="Review the candidate.",
            role="coach",
            tools=["Read", "Search", "Grep"],
            cwd=repo,
            timeout_seconds=60,
        )
    ]


def test_other_roles_get_no_code_search_tools(tmp_path: Path) -> None:
    from unittest.mock import patch

    repo = _scaffold(tmp_path)
    harness = LangGraphHarness(object(), backend=_backend(repo))
    with patch("guardkitfactory.harness.langgraph_harness.create_deep_agent") as create:
        harness._create_agent(role="specialist", cwd=repo, resolved_model=object())
    assert create.call_args.kwargs["tools"] == []
    with patch("guardkitfactory.harness.langgraph_harness.create_deep_agent") as create:
        harness._create_agent(role="coach", cwd=repo, resolved_model=object())
    assert [t.name for t in create.call_args.kwargs["tools"]] == list(WORKTREE_TOOL_NAMES)


def test_tools_are_bound_to_one_worktree(tmp_path: Path) -> None:
    first = _scaffold(tmp_path, "first")
    second = _scaffold(tmp_path, "second")
    (second / "only_second.py").write_text("second_marker = 1\n")
    tools, reason = code_search_tools(first)
    assert reason == ""
    search = next(t for t in tools if t.name == "code_search")
    here = json.loads(search.invoke({"query": "second_marker", "mode": "literal"}))
    assert here["status"] == "no_matches"
    escaped = json.loads(search.invoke({"query": "second_marker", "mode": "literal",
                                        "path": str(second)}))
    assert escaped["status"] == "input_error"


def test_bad_arguments_come_back_to_the_model(tmp_path: Path) -> None:
    repo = _scaffold(tmp_path)
    tools, _ = code_search_tools(repo)
    search = next(t for t in tools if t.name == "code_search")
    answer = json.loads(search.invoke({"query": "x", "mode": "fuzzy"}))
    assert answer["status"] == "input_error" and "mode" in answer["note"]


async def _gather(harness: LangGraphHarness, repo: Path) -> list[Any]:
    return [
        event
        async for event in harness.invoke(
            prompt="Gather evidence for the candidate.",
            role="coach",
            tools=["Read", "Bash", "Grep", "Glob"],
            cwd=repo,
            timeout_seconds=60,
        )
    ]


async def _synthesis(harness: LangGraphHarness, repo: Path) -> list[Any]:
    return [
        event
        async for event in harness.invoke_synthesis(
            prompt="Give the verdict.",
            role="coach",
            grammar=None,
            cwd=repo,
            timeout_seconds=60,
        )
    ]
