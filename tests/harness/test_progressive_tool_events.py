"""Progressive native tool evidence from the live LangChain callback path."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from langchain_core.messages import ToolMessage

from guardkitfactory.harness.langgraph_harness import (
    LangGraphHarness,
    NativeToolEvent,
    NativeToolEvidenceError,
    _ModelActivityCallbackHandler,
)


def test_callback_emits_correlated_structured_tool_boundaries() -> None:
    events: list[NativeToolEvent] = []
    handler = _ModelActivityCallbackHandler(None, events.append)
    run_id = uuid4()
    parent_id = uuid4()
    error_id = uuid4()

    handler.on_tool_start(
        {"name": "generic_reader"},
        "fallback",
        run_id=run_id,
        parent_run_id=parent_id,
        inputs={"path": "skills/naïve/SKILL.md", "lines": [1, 2]},
    )
    handler.on_tool_end(
        ToolMessage(
            content="café ✓",
            tool_call_id="tool-call-1",
            artifact={"rows": [{"count": 64}]},
        ),
        run_id=run_id,
        parent_run_id=parent_id,
    )
    handler.on_tool_start(
        {"name": "generic_execute"},
        "run failing check",
        run_id=error_id,
        parent_run_id=parent_id,
    )
    handler.on_tool_error(
        ValueError("bad ünicode"),
        run_id=error_id,
        parent_run_id=parent_id,
    )

    assert [event.phase for event in events] == ["start", "end", "start", "error"]
    assert {event.run_id for event in events} == {str(run_id), str(error_id)}
    assert {event.parent_run_id for event in events} == {str(parent_id)}
    assert events[0].tool_name == "generic_reader"
    assert events[0].payload == {
        "path": "skills/naïve/SKILL.md",
        "lines": [1, 2],
    }
    assert events[1].tool_name == "generic_reader"
    assert events[2].tool_name == "generic_execute"
    assert events[3].tool_name == "generic_execute"
    assert events[1].payload["content"] == "café ✓"
    assert events[1].payload["artifact"] == {"rows": [{"count": 64}]}
    assert events[3].payload == {
        "type": "ValueError",
        "message": "bad ünicode",
    }


def test_enabled_sink_failure_is_not_silently_suppressed() -> None:
    def fail(_event: NativeToolEvent) -> None:
        raise OSError("disk unavailable")

    handler = _ModelActivityCallbackHandler(None, fail)

    with pytest.raises(NativeToolEvidenceError, match="could not be recorded"):
        handler.on_tool_start(
            {"name": "reader"},
            "payload",
            run_id=uuid4(),
        )


def test_tool_start_is_persistable_before_inflight_cancellation() -> None:
    events: list[NativeToolEvent] = []
    harness = LangGraphHarness(
        model="ignored",
        on_native_tool_event=events.append,
    )
    started = asyncio.Event()

    async def hanging_ainvoke(_input: dict, *, config: dict) -> dict:
        handler = config["callbacks"][0]
        handler.on_tool_start(
            {"name": "generic_reader"},
            '{"path":"guide.md"}',
            run_id=uuid4(),
        )
        started.set()
        await asyncio.sleep(3600)
        return {"messages": []}

    fake_agent = MagicMock(name="hanging_deep_agent")
    fake_agent.ainvoke = hanging_ainvoke

    async def scenario() -> None:
        with patch(
            "guardkitfactory.harness.langgraph_harness.create_deep_agent",
            return_value=fake_agent,
        ):
            stream = harness.invoke(
                prompt="inspect project guidance",
                role="coach",
                tools=[],
                cwd=Path.cwd(),
                timeout_seconds=30,
            )

            async def consume() -> None:
                async for _ in stream:
                    pass

            consumer = asyncio.create_task(consume())
            await started.wait()
            assert len(events) == 1
            await harness.cancel()
            with suppress(asyncio.CancelledError):
                await consumer

    asyncio.run(scenario())

    assert events[0].phase == "start"
    assert events[0].tool_name == "generic_reader"
    assert events[0].payload == '{"path":"guide.md"}'
    assert harness._ainvoke_task is None
