# C4 Level 3 — Agent Runtime (Component Diagram)

> **Generated:** 2026-04-23 via `/system-design`
> **Container:** `Agent Runtime` (from [container.md](../../architecture/container.md))
> **Components inside:** 9 (7 modules + supervisor state + subgraph reference)
> **Status:** Awaiting Rich's approval (C4 L3 review gate)

---

## Purpose

The Agent Runtime is Forge's DeepAgents shell — the reasoning loop, the tool layer, and the two sub-agents (`build_plan_composer` sync, `autobuild_runner` async). This diagram decomposes it into its internal components and shows how they cooperate at runtime.

Why this container warrants an L3 (ADR-ARCH-031 threshold): 7+ internal modules plus the AsyncSubAgent separate-graph pattern creates enough structural complexity that a single L2 node obscures more than it reveals.

---

## Diagram

```mermaid
C4Component
    title Component diagram for Agent Runtime (Forge DeepAgents shell)

    Container_Boundary(runtime, "Agent Runtime") {
        Component(agent, "forge.agent", "Python / DeepAgents 0.5.3", "create_deep_agent(...) wiring. Exports the CompiledStateGraph as `graph`. Entry point in langgraph.json.")
        Component(prompts, "forge.prompts", "Python / string templates", "System prompt templates with {date}, {domain_prompt}, {available_capabilities}, {calibration_priors}, {project_context} placeholders. Assembled at build start.")
        Component(subagents_mod, "forge.subagents", "Python", "SubAgent + AsyncSubAgent spec factories. Two pre-declared: build_plan_composer (sync) + autobuild_runner (async).")
        Component(tools_dispatch, "dispatch_by_capability", "Python / @tool(parse_docstring)", "Single generic dispatch tool. Resolves via forge.discovery, publishes to NATS agents.command.*, waits on correlation-keyed reply subject.")
        Component(tools_approval, "approval + notification tools", "Python / @tool", "request_approval (interrupt() + NATS) and emit_notification (jarvis.notification.*).")
        Component(tools_graphiti, "graphiti_tools", "Python / @tool", "record_override, write_gate_decision, read_override_history, write_session_outcome.")
        Component(tools_guardkit, "guardkit_* tools (11)", "Python / @tool over execute", "One wrapper per GuardKit subcommand with context-manifest resolution.")
        Component(tools_history, "history_tools", "Python / @tool over SQLite", "record_build_transition, record_stage.")
        Component(async_middleware, "AsyncSubAgentMiddleware", "DeepAgents 0.5.3 preview", "Exposes 5 supervisor tools: start/check/update/cancel/list_async_task. Maintains async_tasks state channel.")
    }

    Container_Boundary(subagents_boundary, "Subagents") {
        Component(bpc, "build_plan_composer", "LangGraph SubAgent (sync)", "Composes waves+tasks from feature-spec + retrieved priors. Supervisor blocks on output — gates the next reasoning step.")
        Component(abr, "autobuild_runner", "LangGraph graph (AsyncSubAgent, ASGI co-deployed)", "Executes waves via /task-work + /task-review + /task-complete. Long-running (30-90+ min). Internal interrupt() pauses independently of supervisor.")
    }

    ContainerDb_Ext(state_channel, "async_tasks state channel", "LangGraph channel", "AutobuildState entries per running async subagent (DDR-006 schema).")

    Container_Ext(discovery, "Discovery + Learning + Calibration", "Python", "forge.discovery, .learning, .calibration")
    Container_Ext(nats_adapter, "NATS Adapter", "forge.adapters.nats", "JetStream + core + KV")
    Container_Ext(sqlite_adapter, "SQLite Adapter", "forge.adapters.sqlite", "~/.forge/forge.db WAL")
    Container_Ext(graphiti_adapter, "Graphiti Adapter", "forge.adapters.graphiti", "forge_pipeline_history + forge_calibration_history")
    Container_Ext(subprocess_adapter, "Subprocess Adapter", "forge.adapters.guardkit / git / execute", "/usr/local/bin/guardkit + git + gh")
    Container_Ext(langgraph_adapter, "LangGraph Adapter", "forge.adapters.langgraph", "resume_value_as helper (DDR-002)")
    Container_Ext(llm, "LLM Provider", "Gemini 3.1 Pro / Gemini 2.5 Flash", "Reasoning + implementation models")

    Rel(agent, prompts, "assemble system prompt at build start")
    Rel(agent, subagents_mod, "register sub-agent specs")
    Rel(agent, tools_dispatch, "tool surface")
    Rel(agent, tools_approval, "tool surface")
    Rel(agent, tools_graphiti, "tool surface")
    Rel(agent, tools_guardkit, "tool surface")
    Rel(agent, tools_history, "tool surface")
    Rel(agent, async_middleware, "wraps for supervisor")
    Rel(async_middleware, state_channel, "read/write async_tasks entries")
    Rel(async_middleware, abr, "start/check/update/cancel via ASGI")
    Rel(subagents_mod, bpc, "factory produces spec")
    Rel(subagents_mod, abr, "factory produces spec")

    Rel(prompts, discovery, "query live fleet capabilities for {available_capabilities}")
    Rel(prompts, graphiti_adapter, "query priors for {calibration_priors} + {project_context}")

    Rel(tools_dispatch, discovery, "resolve(tool_name, intent_pattern)")
    Rel(tools_dispatch, nats_adapter, "publish agents.command.*; subscribe reply")
    Rel(tools_approval, nats_adapter, "publish ApprovalRequestPayload")
    Rel(tools_approval, sqlite_adapter, "mark_paused + transition on resume")
    Rel(tools_approval, langgraph_adapter, "resume_value_as(ApprovalResponsePayload, raw)")
    Rel(tools_graphiti, graphiti_adapter, "write gate/override/session entities")
    Rel(tools_guardkit, subprocess_adapter, "run guardkit subcommand with --nats + --context")
    Rel(tools_history, sqlite_adapter, "write builds + stage_log rows")

    Rel(bpc, tools_guardkit, "invokes /feature-spec + /feature-plan")
    Rel(bpc, tools_graphiti, "read_override_history for priors")
    Rel(bpc, tools_dispatch, "may call architect-agent for feasibility")

    Rel(abr, tools_guardkit, "invokes /task-work + /task-review + /task-complete")
    Rel(abr, tools_history, "record_stage per task")
    Rel(abr, tools_approval, "internal gate interrupts")
    Rel(abr, tools_graphiti, "record_override + write_gate_decision")

    Rel(agent, llm, "reasoning invocations", "HTTPS")
    Rel(bpc, llm, "reasoning invocations", "HTTPS")
    Rel(abr, llm, "implementation invocations", "HTTPS")
```

---

## What to look for

- **`forge.agent` is the hub** — expected; it's the entry point that wires everything.
- **No direct module-to-module I/O** — every adapter call goes through a `@tool`, and every adapter is crossed via one explicit arrow.
- **Two distinct subagent patterns** — sync `build_plan_composer` sits inside the same graph; async `autobuild_runner` is its own graph linked via the `async_tasks` state channel (ADR-ARCH-031).
- **ApprovalRequestPayload path is wide but explicit** — `tools_approval` talks to NATS (publish), SQLite (mark paused), and LangGraph (rehydrate resume). Three collaborators for a single tool, all justified by the round-trip contract.
- **Tool-layer breadth** — 5 tool-module clusters. Could compress further but each group has a distinct semantic home (dispatch vs approval vs graphiti vs guardkit vs history).

Node count: 16 / 30 threshold.

---

## Module mapping

| Diagram component | Source module(s) |
|---|---|
| `forge.agent` | `src/forge/agent.py` |
| `forge.prompts` | `src/forge/prompts/__init__.py` + per-role templates |
| `forge.subagents` | `src/forge/subagents/__init__.py` (spec factories) |
| `dispatch_by_capability` | `src/forge/tools/dispatch.py` |
| `approval + notification tools` | `src/forge/tools/approval.py`, `notification.py` |
| `graphiti_tools` | `src/forge/tools/graphiti.py` |
| `guardkit_* tools` | `src/forge/tools/guardkit/*.py` (11 files) |
| `history_tools` | `src/forge/tools/history.py` |
| `AsyncSubAgentMiddleware` | DeepAgents `deepagents.middleware.async_subagent` |
| `build_plan_composer` | `src/forge/subagents/build_plan_composer.py` |
| `autobuild_runner` | `src/forge/subagents/autobuild_runner.py` (separate graph entry) |

---

## Related

- C4 L2: [container.md](../../architecture/container.md)
- ADRs: ADR-ARCH-001, ADR-ARCH-002, ADR-ARCH-020, ADR-ARCH-031
- Adjacent L3: [domain-core.md](domain-core.md)
- Subagent contract: [API-subagents.md](../contracts/API-subagents.md)
- Async state contract: [DDR-006](../decisions/DDR-006-async-subagent-state-channel-contract.md)
