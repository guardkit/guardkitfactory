"""Installed graph, scripted model: no broker or model service."""

import asyncio
import socket

import pytest
from guardkit.orchestrator.harness import AssistantMessageEvent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from guardkitfactory.harness.langgraph_harness import LangGraphHarness


@pytest.fixture(autouse=True)
def deny_external_connections(monkeypatch):
    original = socket.socket.connect
    original_ex = socket.socket.connect_ex

    def connect(sock, address):
        if sock.family != socket.AF_UNIX:
            raise AssertionError("Offline graph fixture forbids network connections")
        return original(sock, address)

    def connect_ex(sock, address):
        if sock.family != socket.AF_UNIX:
            raise AssertionError("Offline graph fixture forbids network connections")
        return original_ex(sock, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)


class Scripted(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def run_graph(tmp_path, messages, budget=14):
    state = {"tool_round_budget": budget}
    harness = LangGraphHarness(
        model=Scripted(messages=iter(messages)),
        recursion_limit=40,
        specialist_finalization=state,
    )

    async def run():
        return [
            e
            async for e in harness.invoke(
                prompt="Review the source",
                role="coach",
                tools=["Read", "Search", "Grep"],
                cwd=tmp_path,
                timeout_seconds=30,
            )
        ]

    events = asyncio.run(run())
    return state, [e.text for e in events if isinstance(e, AssistantMessageEvent)]


def calls(count, batch=1):
    return [
        AIMessage(
            content="",
            tool_calls=[
                {"name": "ls", "args": {"path": "/"}, "id": f"call-{i}-{j}"}
                for j in range(batch)
            ],
        )
        for i in range(count)
    ]


def test_actual_graph_forces_final_within_40_steps(tmp_path):
    state, text = run_graph(
        tmp_path,
        calls(14, 2)
        + [AIMessage(content="Verdict: incomplete; unseen criteria cannot tell")],
    )
    assert state["actual_tool_rounds"] == 14
    assert state["forced_finalization"] is True
    assert state["completion"] == "incomplete"
    assert text == ["Verdict: incomplete; unseen criteria cannot tell"]


def test_tool_call_after_finalization_terminates_without_execution(tmp_path):
    state, text = run_graph(tmp_path, calls(100))
    assert state["actual_tool_rounds"] == 14
    assert state["ending_reason"] == "tool request after finalization"
    assert len(text) == 1 and text[0].startswith("Verdict: incomplete")


def test_completed_negative_review_is_preserved(tmp_path):
    state, text = run_graph(
        tmp_path, [AIMessage(content="Verdict: changes needed. Criterion AC1 not met.")]
    )
    assert state["forced_finalization"] is False
    assert state["completion"] == "complete"
    assert text == ["Verdict: changes needed. Criterion AC1 not met."]


def test_normal_async_harness_completed_review_without_tools(tmp_path):
    state = {"tool_round_budget": 14}
    harness = LangGraphHarness(
        model=Scripted(messages=iter([AIMessage(content="Verdict: changes needed")])),
        recursion_limit=40,
        specialist_finalization=state,
    )

    async def run():
        return [
            event
            async for event in harness.invoke(
                prompt="Review",
                role="coach",
                tools=["Read"],
                cwd=tmp_path,
                timeout_seconds=10,
            )
        ]

    events = asyncio.run(run())
    assert [e.text for e in events if isinstance(e, AssistantMessageEvent)] == [
        "Verdict: changes needed"
    ]
    assert state["completion"] == "complete"


def test_an_empty_final_review_is_recorded_as_absent(tmp_path):
    # The reviewer's empty last answer is not filled with the prompt or an
    # earlier tool preamble: it is recorded as absent.
    state, text = run_graph(tmp_path, [AIMessage(content="")])
    assert state["forced_finalization"] is False
    assert state["completion"] == "absent"
    assert text == [""]
