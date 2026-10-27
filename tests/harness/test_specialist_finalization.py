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


@pytest.mark.parametrize(
    "scenario,completion",
    [
        ("forced", "incomplete"),
        ("positive", "complete"),
        ("negative", "complete"),
        ("empty", "absent"),
        ("timeout", "absent"),
        ("cancel", "absent"),
    ],
)
def test_normal_specialist_selector_graph_injection_and_coach_advisory(
    tmp_path, monkeypatch, scenario, completion
):
    import json

    from guardkit.orchestrator.agent_invoker import AgentInvoker
    from guardkit.orchestrator.paths import TaskArtifactPaths
    from guardkit.orchestrator.quality_gates.coach_validator import CoachValidator
    from guardkit.orchestrator.specialist_invocations import (
        SpecialistInvocationResult,
        invoke_code_reviewer,
    )

    prose = {
        "positive": "Verdict: approve. AC-001 met.",
        "negative": "Verdict: changes needed. AC-001 not met.",
        "empty": "",
    }

    import threading

    cancellation = threading.Event()

    class Slow(Scripted):
        async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
            if scenario == "cancel":
                cancellation.set()
            await asyncio.sleep(30)
            return await super()._agenerate(
                messages, stop=stop, run_manager=run_manager, **kwargs
            )

    messages = (
        calls(20)
        if scenario == "forced"
        else [AIMessage(content=prose.get(scenario, ""))]
    )
    model = (Slow if scenario in ("timeout", "cancel") else Scripted)(
        messages=iter(messages)
    )
    monkeypatch.setenv("GUARDKIT_HARNESS", "langgraph")
    monkeypatch.setattr(
        LangGraphHarness, "_resolve_model_for_invoke", lambda self, role=None: model
    )
    task = "TASK-REVIEW"
    folder = tmp_path / ".guardkit/autobuild" / task
    folder.mkdir(parents=True)
    (tmp_path / "source").write_text("scope evidence")
    (folder / "specialist_results.json").write_text(
        json.dumps({"phase_4": {"status": "passed", "tests_run": 1, "tests_failed": 0}})
    )
    invoker = AgentInvoker(worktree_path=tmp_path, model_name="gemma4:26b")
    monkeypatch.setattr(invoker, "_kill_child_claude_processes", lambda: None)
    result = asyncio.run(
        invoke_code_reviewer(
            tmp_path,
            task,
            SpecialistInvocationResult(
                "test-orchestrator", "4", "passed", 0.0, None, None
            ),
            (0.05 if scenario == "timeout" else 30),
            invoker,
            turn=1,
            acceptance_criteria=["AC-001: behavior"],
            reported_files=["source"],
            cancellation_event=cancellation if scenario == "cancel" else None,
        )
    )
    assert result.status == (
        "failed" if scenario in ("empty", "timeout", "cancel") else "passed"
    ), result.error
    block = json.loads((folder / "specialist_results.json").read_text())
    assert block["phase_4"]["tests_run"] == 1
    assert block["phase_5"]["review_record"]["forced_finalization"] is (
        scenario == "forced"
    )
    assert block["phase_5"]["review_record"]["actual_tool_rounds"] == (
        14 if scenario == "forced" else 0
    )
    assert block["phase_5"]["review_record"]["completion"] == completion
    assert block["phase_5"]["review_record"]["step_cap"] == 40
    invoker._write_direct_mode_results(
        task, {"files_modified": [], "files_created": []}
    )
    invoker._inject_specialist_records_into_task_work_results(task)
    data = json.loads(
        TaskArtifactPaths.task_work_results_path(task, tmp_path).read_text()
    )
    advisories = CoachValidator(
        str(tmp_path)
    )._compute_code_reviewer_model_report_advisories(data)
    if scenario in ("empty", "timeout", "cancel"):
        assert advisories == []
        absent = CoachValidator(str(tmp_path))._compute_specialist_failure_advisories(
            data
        )
        assert absent and absent[0]["severity"] == "should_fix"
        assert all(a["severity"] != "must_fix" for a in absent)
    else:
        assert len(advisories) == 1
        assert advisories[0]["details"]["review_completion"] == completion
        assert advisories[0]["details"]["verified"] is False
