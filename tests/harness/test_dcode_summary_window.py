"""What the dcode Player's model sees after a conversation summary (19 October 2026).

Live build FEAT-D31F logged, on every model request after its first summary,
``Discarding malformed `_summarization_event` (cutoff_index=316, messages=9)``.
These tests drive the real dcode graph (deepagents-code 0.1.69 on deepagents
0.7.14, exactly the pair upstream pins) through fake provider HTTP, force one
summary with the ``compact_conversation`` tool, and record every request body.

They pin two facts:

* where dcode's summariser sits relative to its goal-state middleware in the
  stack the SDK actually assembles, and
* what the model receives after the summary: the summary plus the recent tail,
  never the early history again.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Any

import httpx
import pytest

from guardkitfactory.harness.langgraph_harness import LangGraphHarness

from .test_dcode_harness import config, isolate, pytestmark, response, selected_skill_calls
from .test_player_skills_graph import _backend, _close_clients, _collect, _model, _scaffold

__all__ = ["isolate", "pytestmark"]

_EARLY = 10
_LATE = 4
_DISCARD = "Discarding malformed `_summarization_event`"


class SummaryExchange:
    """Fake provider: skill reads, early reads, one compaction, late reads."""

    def __init__(self, repo: Path) -> None:
        self.repo = repo
        self.bodies: list[dict[str, Any]] = []
        self.agent_bodies: list[dict[str, Any]] = []
        self.summaries = 0
        self.index = 0
        skills = selected_skill_calls(repo)
        early = [
            ("read_file", {"file_path": str(repo / f"early_{i}.txt"), "limit": 1000})
            for i in range(_EARLY)
        ]
        late = [
            ("read_file", {"file_path": str(repo / f"late_{i}.txt"), "limit": 1000})
            for i in range(_LATE)
        ]
        self.calls = [*skills, *early, ("compact_conversation", {}), *late]
        self.compact_index = len(skills) + len(early)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.bodies.append(body)
        if not body.get("tools"):
            self.summaries += 1
            return response(body, text="SUMMARY_SENTINEL early files were read", index=999)
        self.agent_bodies.append(body)
        index = self.index
        self.index += 1
        if index >= len(self.calls):
            return response(body, text="done", index=index)
        # Large reported usage once the early reads have landed, so the compact
        # tool finds something to summarise (as in the artifact round-trip test).
        tokens = 65000 if index >= self.compact_index - 2 else 100
        return response(body, call=self.calls[index], tokens=tokens, index=index)


def _rendered(body: dict[str, Any]) -> str:
    return "\n".join(str(message.get("content", "")) for message in body["messages"])


def _run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture):
    import deepagents.graph as sdk_graph

    stacks: list[list[str]] = []
    real_create_agent = sdk_graph.create_agent

    def recording_create_agent(*args: Any, **kwargs: Any) -> Any:
        stacks.append([m.name for m in kwargs.get("middleware", ())])
        return real_create_agent(*args, **kwargs)

    monkeypatch.setattr(sdk_graph, "create_agent", recording_create_agent)

    from deepagents_code.goal_tools import GoalToolsMiddleware

    seen: list[tuple[int, int | None]] = []
    real_notice = GoalToolsMiddleware._request_with_goal_notice

    def recording_notice(request: Any) -> Any:
        event = request.state.get("_summarization_event")
        seen.append((len(request.messages), event["cutoff_index"] if event else None))
        return real_notice(request)

    monkeypatch.setattr(
        GoalToolsMiddleware, "_request_with_goal_notice", staticmethod(recording_notice)
    )

    repo = _scaffold(tmp_path)
    for i in range(_EARLY):
        (repo / f"early_{i}.txt").write_text(f"EARLY_{i}_SENTINEL line\n" * 1000)
    for i in range(_LATE):
        (repo / f"late_{i}.txt").write_text(f"LATE_{i}_SENTINEL\n")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    exchange = SummaryExchange(repo)
    model, sync, async_ = _model(exchange)
    harness = LangGraphHarness(
        model,
        backend=_backend(repo),
        player_config=config(repo),
        recursion_limit=200,
    )
    caplog.set_level(logging.WARNING, logger="deepagents_code.goal_state_notice")
    try:
        asyncio.run(_collect(harness, repo))
    finally:
        _close_clients(sync, async_)
    main = next(stack for stack in stacks if "GoalToolsMiddleware" in stack)
    discards = [r.getMessage() for r in caplog.records if _DISCARD in r.getMessage()]
    return exchange, main, discards, seen


def test_model_sees_summary_and_tail_not_the_early_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    exchange, main, discards, seen = _run(tmp_path, monkeypatch, caplog)
    assert exchange.summaries == 1
    compact = exchange.compact_index
    before = exchange.agent_bodies[compact]
    after = exchange.agent_bodies[compact + 1 :]
    assert len(after) == _LATE + 1

    # Before the summary the model saw every early read.
    assert all(f"EARLY_{i}_SENTINEL" in _rendered(before) for i in range(_EARLY))
    assert "SUMMARY_SENTINEL" not in _rendered(before)

    # After it: the summary every time, the oldest reads never again, and a
    # window that grows only by the new turns.
    for offset, body in enumerate(after):
        text = _rendered(body)
        assert "SUMMARY_SENTINEL" in text, offset
        assert "EARLY_0_SENTINEL" not in text, offset
        assert all(f"LATE_{i}_SENTINEL" in text for i in range(offset)), offset
    sizes = [len(body["messages"]) for body in after]
    assert sizes == sorted(sizes)
    assert sizes[0] < len(before["messages"])
    assert sizes[-1] - sizes[0] == 2 * _LATE

    # The summariser sits outside (before) the goal-state middleware: dcode's
    # compaction middleware borrows the SDK summariser's name, and
    # `create_deep_agent` swaps a same-named custom middleware into the SDK's
    # own slot near the top of the stack.
    assert main.index("SummarizationMiddleware") < main.index("GoalToolsMiddleware")

    # So the goal-state middleware is handed the trimmed window (exactly what
    # the model then receives, less the system message), not the persisted
    # list its absolute cutoff counts in.
    assert len(seen) == len(exchange.agent_bodies)
    post = seen[compact + 1 :]
    cutoff = post[0][1]
    assert cutoff is not None and all(event == cutoff for _, event in post)
    assert [window + 1 for window, _ in post] == sizes
    assert all(window < cutoff for window, _ in post)
    # It therefore judges a valid cutoff out of range and logs a discard on
    # every post-summary request, as FEAT-D31F did (cutoff_index=316,
    # messages=9, 11, ...). The warning's "re-sends the full history" does not
    # happen in this ordering: the summariser has already trimmed (above).
    assert len(discards) == len(after)
    assert all(
        f"cutoff_index={cutoff}, messages={window})" in message
        for message, (window, _) in zip(discards, post, strict=True)
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "upstream deepagents-code 0.1.69: GoalToolsMiddleware is wrapped by the "
        "summariser, so it sees the trimmed window and discards a valid summary "
        "event on every request (see test above)"
    ),
)
def test_no_summary_event_is_discarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _, _, discards, _ = _run(tmp_path, monkeypatch, caplog)
    assert discards == []
