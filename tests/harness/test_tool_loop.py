"""The shared tool limit (``harness/tool_loop.py``) ends tool use with an answer.

Moved from specialist-agent's ``tests/test_tool_loop_guard.py`` with the
middleware (the build reviewer design of 29 October 2026). These tests drive a
real ``langchain.agents.create_agent`` graph (its real ToolNode) with only this
middleware and a scripted fake chat model. No test calls a live endpoint. The
specialist-agent tests that need its own tools and failure cap stay there.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, ClassVar

import pytest
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from guardkitfactory.harness.tool_loop import (
    MAX_IDENTICAL_CALLS_PER_RUN,
    MAX_TOOL_FAILURES_PER_RUN,
    MAX_TOOL_TURNS_PER_RUN,
    ToolLoopGuardMiddleware,
    ToolUseEnded,
    stop_reason,
    written_out,
)


class _Recorder(GenericFakeChatModel):
    """Replays scripted replies; records the tools and messages of each call."""

    offered: ClassVar[list[list[str]]] = []
    sent: ClassVar[list[list[BaseMessage]]] = []

    def bind_tools(self, tools: Any, **kwargs: Any):  # type: ignore[override]
        type(self).offered.append(
            sorted(getattr(t, "name", None) or t.get("name") for t in tools)
        )
        return self

    def bind(self, **kwargs: Any):  # type: ignore[override]
        type(self).offered.append([])
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # type: ignore[override]
        type(self).sent.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


@tool
def lookup(query: str) -> str:
    """Look something up."""
    return f"facts about {query}"


@tool
def other(query: str) -> str:
    """Another tool."""
    return f"other {query}"


def _agent(
    script: list[AIMessage],
    tools: list[Any],
    deadline: float | None = None,
    *,
    limits: bool = True,
) -> Any:
    _Recorder.offered = []
    _Recorder.sent = []
    return create_agent(
        _Recorder(messages=iter(script)),
        tools=tools,
        system_prompt="a prompt",
        middleware=[ToolLoopGuardMiddleware(deadline=deadline, limits=limits)],
    )


def _call(name: str, args: dict[str, Any], call_id: str, text: str = "") -> AIMessage:
    return AIMessage(content=text, tool_calls=[{"name": name, "args": args, "id": call_id}])


def _tool_messages(result: dict[str, Any]) -> list[ToolMessage]:
    return [m for m in result["messages"] if isinstance(m, ToolMessage)]


def _go(agent: Any) -> dict[str, Any]:
    return asyncio.run(agent.ainvoke({"messages": [{"role": "user", "content": "review it"}]}))


class TestIdenticalCalls:
    def test_two_identical_calls_run_as_before(self) -> None:
        script = [
            _call("lookup", {"query": "x"}, "c0"),
            _call("lookup", {"query": "x"}, "c1"),
            AIMessage("done"),
        ]
        result = _go(_agent(script, [lookup, other]))
        assert [m.status for m in _tool_messages(result)] == ["success", "success"]
        assert result["messages"][-1].content == "done"
        assert all(o == ["lookup", "other"] for o in _Recorder.offered)

    def test_a_third_identical_call_is_not_run_and_tool_use_ends(self) -> None:
        script = [
            _call("lookup", {"query": "x"}, f"c{i}")
            for i in range(MAX_IDENTICAL_CALLS_PER_RUN + 1)
        ]
        script.append(AIMessage("the answer"))
        result = _go(_agent(script, [lookup, other]))
        msgs = _tool_messages(result)
        assert [m.status for m in msgs[:-1]] == ["success"] * MAX_IDENTICAL_CALLS_PER_RUN
        assert msgs[-1].status == "error"
        assert "already called with exactly these arguments" in msgs[-1].content
        assert _Recorder.offered[-1] == []
        assert result["messages"][-1].content == "the answer"

    def test_an_alternating_cycle_is_caught_too(self) -> None:
        """A, B, A, B, ... with A identical every time and B different every
        time; nothing is ever consecutive."""
        script: list[AIMessage] = []
        for i in range(MAX_IDENTICAL_CALLS_PER_RUN + 1):
            script.append(_call("lookup", {"query": "same"}, f"a{i}"))
            script.append(_call("other", {"query": f"growing {i}"}, f"b{i}"))
        script.pop()  # the cycle is cut where the guard ends it
        script.append(AIMessage("answer"))
        result = _go(_agent(script, [lookup, other]))
        assert result["messages"][-1].content == "answer"
        assert _Recorder.offered[-1] == []
        runs = [m for m in _tool_messages(result) if m.name == "lookup"]
        assert [m.status for m in runs] == ["success"] * MAX_IDENTICAL_CALLS_PER_RUN + [
            "error"
        ]

    def test_different_arguments_are_not_identical(self) -> None:
        script = [_call("lookup", {"query": f"q{i}"}, f"c{i}") for i in range(5)]
        script.append(AIMessage("done"))
        result = _go(_agent(script, [lookup]))
        assert all(m.status == "success" for m in _tool_messages(result))
        assert all(o == ["lookup"] for o in _Recorder.offered)


class TestToolTurns:
    def test_tool_use_ends_after_the_turn_limit(self) -> None:
        script = [
            _call("lookup", {"query": f"q{i}"}, f"c{i}") for i in range(MAX_TOOL_TURNS_PER_RUN)
        ]
        script.append(AIMessage("answer from what I have"))
        result = _go(_agent(script, [lookup]))
        assert len(_tool_messages(result)) == MAX_TOOL_TURNS_PER_RUN
        assert _Recorder.offered[:MAX_TOOL_TURNS_PER_RUN] == [["lookup"]] * MAX_TOOL_TURNS_PER_RUN
        assert _Recorder.offered[MAX_TOOL_TURNS_PER_RUN] == []
        assert result["messages"][-1].content == "answer from what I have"

    def test_one_turn_below_the_limit_keeps_its_tools(self) -> None:
        script = [
            _call("lookup", {"query": f"q{i}"}, f"c{i}")
            for i in range(MAX_TOOL_TURNS_PER_RUN - 1)
        ]
        script.append(AIMessage("done"))
        _go(_agent(script, [lookup]))
        assert all(o == ["lookup"] for o in _Recorder.offered)

    def test_the_limit_is_forty_turns(self) -> None:
        assert MAX_TOOL_TURNS_PER_RUN == 40
        assert MAX_IDENTICAL_CALLS_PER_RUN == 2


class TestDeadline:
    """A pass that runs short of time answers from what it has read (31 October
    2026: in reviewer experiment 1 the code-reading step ran out of time in 14 of
    19 reviews and everything it had found was thrown away)."""

    def test_a_passed_deadline_ends_tool_use_with_an_answer(self) -> None:
        script = [AIMessage("answer from what I have")]
        result = _go(_agent(script, [lookup], deadline=time.monotonic() - 1))
        assert _Recorder.offered == [[]]
        assert _tool_messages(result) == []
        assert result["messages"][-1].content == "answer from what I have"

    def test_tools_are_kept_before_the_deadline(self) -> None:
        script = [_call("lookup", {"query": "x"}, "c0"), AIMessage("done")]
        result = _go(_agent(script, [lookup], deadline=time.monotonic() + 3600))
        assert [m.status for m in _tool_messages(result)] == ["success"]
        assert all(o == ["lookup"] for o in _Recorder.offered)

    def test_the_deadline_is_checked_at_each_step(self) -> None:
        @tool
        def slow(query: str) -> str:
            """Takes longer than the time left."""
            time.sleep(0.5)
            return f"slow facts about {query}"

        script = [_call("slow", {"query": "x"}, "c0"), AIMessage("answer")]
        result = _go(_agent(script, [slow], deadline=time.monotonic() + 0.25))
        assert [m.status for m in _tool_messages(result)] == ["success"]
        assert _Recorder.offered == [["slow"], []]
        assert result["messages"][-1].content == "answer"


class TestTimeCutOffOnly:
    """15 November 2026: ``limits=False`` (the review pass with write tools,
    GuardKit's end review) keeps the time cut-off and nothing else."""

    def test_the_turn_limit_does_not_apply(self) -> None:
        turns = MAX_TOOL_TURNS_PER_RUN + 5
        script = [_call("lookup", {"query": f"q{i}"}, f"c{i}") for i in range(turns)]
        script.append(AIMessage("done"))
        result = _go(_agent(script, [lookup], deadline=time.monotonic() + 3600, limits=False))
        assert [m.status for m in _tool_messages(result)] == ["success"] * turns
        assert _Recorder.offered == [["lookup"]] * (turns + 1)
        assert result["messages"][-1].content == "done"

    def test_identical_calls_are_all_run(self) -> None:
        repeats = MAX_IDENTICAL_CALLS_PER_RUN + 3
        script = [_call("lookup", {"query": "x"}, f"c{i}") for i in range(repeats)]
        script.append(AIMessage("done"))
        result = _go(_agent(script, [lookup], limits=False))
        assert [m.status for m in _tool_messages(result)] == ["success"] * repeats
        assert all(o == ["lookup"] for o in _Recorder.offered)

    def test_the_deadline_still_ends_tool_use_with_an_answer(self) -> None:
        script = [AIMessage("answer from what I have")]
        result = _go(_agent(script, [lookup], deadline=time.monotonic() - 1, limits=False))
        assert _Recorder.offered == [[]]
        assert _tool_messages(result) == []
        assert result["messages"][-1].content == "answer from what I have"

    def test_the_deadline_is_checked_at_each_step(self) -> None:
        @tool
        def slow(query: str) -> str:
            """Takes longer than the time left."""
            time.sleep(0.5)
            return f"slow facts about {query}"

        script = [_call("slow", {"query": "x"}, "c0"), AIMessage("answer")]
        result = _go(_agent(script, [slow], deadline=time.monotonic() + 0.25, limits=False))
        assert [m.status for m in _tool_messages(result)] == ["success"]
        assert _Recorder.offered == [["slow"], []]
        assert result["messages"][-1].content == "answer"

    def test_limits_are_on_unless_turned_off(self) -> None:
        assert ToolLoopGuardMiddleware().limits is True
        assert ToolLoopGuardMiddleware(deadline=1.0).limits is True


class TestEveryToolFailing:
    def test_tool_use_ends_when_every_offered_tool_has_failed(self) -> None:
        failed = [
            message
            for i in range(MAX_TOOL_FAILURES_PER_RUN)
            for message in (
                _call("lookup", {"query": f"q{i}"}, f"c{i}"),
                ToolMessage("down", tool_call_id=f"c{i}", name="lookup", status="error"),
            )
        ]
        state = {"messages": [HumanMessage("go"), *failed]}
        reason = stop_reason(state, [lookup])
        assert reason is not None and "failed" in reason
        assert stop_reason(state, [lookup, other]) is None


class TestTheFinalCall:
    def _ending_script(self, final: AIMessage) -> list[AIMessage]:
        script = [
            _call("lookup", {"query": "x"}, f"c{i}")
            for i in range(MAX_IDENTICAL_CALLS_PER_RUN + 1)
        ]
        script.append(final)
        return script

    def test_no_text_and_another_tool_call_fails_with_a_plain_reason(self) -> None:
        agent = _agent(self._ending_script(_call("lookup", {"query": "y"}, "late")), [lookup])
        with pytest.raises(ToolUseEnded, match="asked for a tool again"):
            _go(agent)

    def test_an_empty_reply_fails_with_a_plain_reason(self) -> None:
        agent = _agent(self._ending_script(AIMessage("")), [lookup])
        with pytest.raises(ToolUseEnded, match="wrote no answer"):
            _go(agent)

    def test_text_with_a_tool_call_keeps_the_text_and_drops_the_call(self) -> None:
        agent = _agent(
            self._ending_script(_call("lookup", {"query": "y"}, "late", "the findings")),
            [lookup],
        )
        last = _go(agent)["messages"][-1]
        assert last.content == "the findings"
        assert last.tool_calls == []

    def test_history_is_written_out_and_alternates(self) -> None:
        _go(_agent(self._ending_script(AIMessage("the findings")), [lookup]))
        final = _Recorder.sent[-1]
        assert not any(isinstance(m, ToolMessage) for m in final)
        assert not any(getattr(m, "tool_calls", None) for m in final)
        kinds = [type(m) for m in final if not m.type == "system"]
        assert all(a is not b for a, b in zip(kinds, kinds[1:], strict=False))
        joined = "\n".join(str(m.content) for m in final)
        assert "(I asked for the tool lookup with" in joined
        assert "Result of the tool lookup:" in joined
        assert isinstance(final[-1], HumanMessage)
        assert "Tool use has ended for this answer" in final[-1].content

    def test_the_real_history_is_kept(self) -> None:
        result = _go(_agent(self._ending_script(AIMessage("the findings")), [lookup]))
        assert any(isinstance(m, ToolMessage) for m in result["messages"])


class TestWrittenOut:
    def test_parallel_results_merge_into_one_user_turn(self) -> None:
        messages = [
            HumanMessage("go"),
            AIMessage(
                "",
                tool_calls=[
                    {"name": "a", "args": {}, "id": "1"},
                    {"name": "b", "args": {"q": 1}, "id": "2"},
                ],
            ),
            ToolMessage("ra", tool_call_id="1", name="a"),
            ToolMessage("rb", tool_call_id="2", name="b"),
        ]
        out = written_out(messages, "note")
        assert [type(m) for m in out] == [HumanMessage, AIMessage, HumanMessage]
        assert "ra" in out[-1].content and "rb" in out[-1].content
        assert out[-1].content.endswith("note")
