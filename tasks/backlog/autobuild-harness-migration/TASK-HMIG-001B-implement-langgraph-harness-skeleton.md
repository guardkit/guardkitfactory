---
id: TASK-HMIG-001B
title: Implement LangGraphHarness skeleton (guardkitfactory-side)
status: backlog
task_type: implementation
created: 2026-05-19T20:30:00Z
updated: 2026-05-19T20:30:00Z
priority: critical
complexity: 4
deadline: 2026-06-15
parent_review: TASK-REV-HMIG
feature_id: FEAT-HMIG
parent_feature: autobuild-harness-migration
wave: 1
parallel_group: 1B
implementation_mode: task-work
intensity: standard
effort_hours: 2
depends_on:
  - TASK-HMIG-000R   # scaffold must be in place
cross_repo:
  pairs_with: TASK-HMIG-001A   # ABC in guardkit
  notes: This implements the `HarnessAdapter` ABC defined in guardkit/orchestrator/harness/adapter.py (TASK-HMIG-001A). Wave 1 ordering, A → B, is enforced because we cannot subclass an ABC that doesn't exist yet. If TASK-HMIG-001A has not landed by start time, this task blocks.
falsifier: "Unit test in guardkitfactory: instantiate LangGraphHarness with a stub model, call invoke() with a dual-system-message input, assert it raises ValueError per assert_no_system_messages() guard (TASK-REV-R2A1). Cross-repo smoke from guardkit/.venv: `pip install -e ../guardkitfactory && python -c 'from guardkitfactory import LangGraphHarness; from guardkit.orchestrator.harness import HarnessAdapter; assert issubclass(LangGraphHarness, HarnessAdapter)'` succeeds."
tags:
  - autobuild
  - harness
  - langgraph-migration
  - cross-repo
---

# Task: Implement LangGraphHarness skeleton

## Description

Implement the LangGraph/DeepAgents-backed `HarnessAdapter` in
`guardkitfactory`. This is the implementation half of the cross-repo pair
TASK-HMIG-001A (interface in guardkit) ↔ TASK-HMIG-001B (impl in
guardkitfactory).

This task ships only the *skeleton* — the class, its `invoke()` method
wired to a `create_deep_agent()` call, and the safety guards. The backend
configuration (TASK-HMIG-002R) and the BDD plugin integration (TASK-HMIG-007)
are separate tasks that compose with this one.

## Acceptance Criteria

- [ ] AC-001: New module `src/guardkitfactory/harness/langgraph_harness.py`
      defining `LangGraphHarness(HarnessAdapter)` where `HarnessAdapter` is
      imported from `guardkit.orchestrator.harness` (cross-repo import).
- [ ] AC-002: `LangGraphHarness.__init__(self, model, *, backend=None, permissions=None)`
      stores the model + backend + permissions. Defaults: `backend=None` (uses
      DeepAgents default `StateBackend`), `permissions=None` (no extra rules).
      Real configuration comes from TASK-HMIG-002R.
- [ ] AC-003: `LangGraphHarness.invoke(prompt, role, tools, cwd, *, timeout_seconds)`
      is async. Internally calls `assert_no_system_messages()` on the input
      (lifted from `lib/factory_guards.py`), then **MUST** construct the agent via
      `create_deep_agent(model=self.model, tools=tools, backend=self.backend, permissions=self.permissions, system_prompt=<role-prompt>)` —
      i.e., the agent is a DeepAgents agent that picks up the built-in
      `ls / read_file / write_file / edit_file / glob / grep` (+ `execute` from
      `LocalShellBackend`) tool surface, `write_todos` planning, sub-agent
      delegation, and auto-summarisation **for free** through the
      backend. Then `await agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})`.

      **DO NOT** instantiate a bare `ChatOpenAI` / `init_chat_model` and
      manually bind tools via `bind_tools(...)` or build a custom LangGraph
      `StateGraph` from scratch. That regresses to the v1 D-03 plan that
      Revision 1 explicitly rejected. The `model` parameter to
      `create_deep_agent` IS where `ChatOpenAI(base_url=...)` /
      `init_chat_model(...)` lives — see Implementation Notes below.
- [ ] AC-004: Result extraction uses `_extract_last_ai_message()` lifted from
      specialist-agent `generation_loop.py:364-410`. Placed at
      `src/guardkitfactory/harness/extractors.py`.
- [ ] AC-005: The async-iterator contract from `HarnessAdapter.invoke()` is
      honoured. Yield `HarnessEvent` values mirroring the SDK's event taxonomy:
      `assistant_message`, `tool_use`, `tool_result`, `result_message`. (If the
      DeepAgents stream API exposes these natively, map; otherwise emit a
      single final `result_message` event for the skeleton — TASK-HMIG-006
      will surface any taxonomy mismatch.)
- [ ] AC-006: `session_id` property returns `None` for now (LangGraph
      checkpoint resume is out of scope for this skeleton; decision D-07
      in the parent review says JSON-on-disk checkpointing stays).
- [ ] AC-007: `supports_resume` property returns `False` for now.
- [ ] AC-008: Unit tests at `tests/harness/test_langgraph_harness.py`:
  - Happy-path: stub model + simple tools + invoke returns a final assistant message in the stream.
  - Dual-system-message: input with `{"role": "system", ...}` raises `ValueError`.
  - Unknown model: raises a clear, attributable error (not a generic langchain failure).
  - Stream is async-iterable.
- [ ] AC-009: Module docstring documents the cross-repo dependency
      (`guardkit.orchestrator.harness.HarnessAdapter`) and the rationale.
- [ ] AC-010: `src/guardkitfactory/__init__.py` exposes `LangGraphHarness`
      as a top-level symbol: `from guardkitfactory.harness import LangGraphHarness`.

## Implementation Notes

- The `tools` parameter to `invoke()` will typically be empty in production:
  AutoBuild uses DeepAgents' built-in `ls/read_file/write_file/edit_file/glob/grep/execute`
  surface delivered through the backend (configured in TASK-HMIG-002R), not
  through explicit `tools=[]` registration. The `tools` parameter exists for
  the rare case where AutoBuild wants to inject a GuardKit-specific custom tool.
- Don't try to make the LangGraph stream events bytewise identical to the SDK
  stream events. That mapping is TASK-HMIG-006's job. This task just needs
  the LangGraph-side to emit *some* coherent event stream that
  TASK-HMIG-006's adapter logic can process.
- The `model` parameter passed to `create_deep_agent()` is where
  `ChatOpenAI(base_url=<local-vllm-url>, model="qwen36-workhorse", api_key="local")`
  or `init_chat_model("openai:qwen36-workhorse", base_url=...)` lives.
  Decide which based on what's idiomatic in specialist-agent's
  `generation_loop.py` LLM-binding pattern (parent review §7.6). Either is
  fine; both ultimately produce a `BaseChatModel` that `create_deep_agent`
  consumes. The choice is stylistic, not architectural.
- The `assert_no_system_messages()` guard is the TASK-REV-R2A1 mitigation —
  do NOT skip it. The dual-system-message bug is real and well-documented.

## References

- Pair: `~/Projects/appmilla_github/guardkit/tasks/backlog/autobuild-harness-migration/TASK-HMIG-001A-define-harness-adapter-interface.md`
- Parent review §2.4 — C4 Code-level diagram
- Parent review §7.1 Wave 1 — task definitions
- Parent review §14.7 (Revision 1) — references DeepAgents v0.5+ tool surface
- specialist-agent `~/Projects/appmilla_github/specialist-agent/src/specialist_agent/orchestrator/generation_loop.py:364-410` — `_extract_last_ai_message` source

## Notes

This task does NOT yet wire the actual backend (LocalShellBackend) or
permissions — those land in TASK-HMIG-002R. After TASK-HMIG-001B lands you
have a `LangGraphHarness` that can be instantiated but won't do anything
useful with files until TASK-HMIG-002R configures the backend.
