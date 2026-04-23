# API Contract — Subagents

> **Type:** DeepAgents sub-agent specs (TypedDict factories)
> **Framework:** DeepAgents 0.5.3 — `SubAgent` (sync `task()`) and `AsyncSubAgent` (preview, ASGI)
> **Related ADRs:** [ADR-ARCH-002](../../architecture/decisions/ADR-ARCH-002-two-model-separation.md), [ADR-ARCH-020](../../architecture/decisions/ADR-ARCH-020-adopt-deepagents-builtins.md), [ADR-ARCH-031](../../architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md)

---

## 1. Purpose

Forge pre-declares exactly **two** sub-agents; everything else is spawned via the DeepAgents built-in `task()` tool on demand (ADR-ARCH-020). The two pre-declared specs live in `forge.subagents`:

- `build_plan_composer` — **sync `SubAgent`**. Bounded, gates the next decision.
- `autobuild_runner` — **async `AsyncSubAgent`**. Long-running (30–90+ min), launched via `start_async_task`.

This contract specifies their TypedDict factory shapes, the models assigned to each, and the state-channel contract for the async runner.

---

## 2. `build_plan_composer` — Sync SubAgent

### 2.1 Factory

```python
# forge.subagents.build_plan_composer
from deepagents import SubAgent
from forge.prompts import BUILD_PLAN_COMPOSER_PROMPT

def build_plan_composer_spec(domain_prompt: str) -> SubAgent:
    return SubAgent(
        name="build_plan_composer",
        description=(
            "Compose a gated build plan from the current feature-spec and retrieved priors. "
            "Input: feature_id, feature_yaml_path, capability snapshot. "
            "Output: {waves: [{tasks: [...]}], risks: [...], priors_referenced: [...]}. "
            "Supervisor blocks on this — output gates the next reasoning step (ADR-ARCH-007)."
        ),
        system_prompt=BUILD_PLAN_COMPOSER_PROMPT.format(domain_prompt=domain_prompt),
        model="google_genai:gemini-3.1-pro",            # reasoning model
        tools=[
            "read_file", "write_file", "ls", "grep",    # DeepAgents built-ins
            "write_todos",
            "guardkit_feature_spec",
            "guardkit_feature_plan",
            "read_override_history",
            "dispatch_by_capability",                    # May call architect-agent for feasibility
        ],
    )
```

### 2.2 Invocation contract

```python
# Invoked via DeepAgents built-in task() — sync, supervisor blocks until return
result_json = await task(
    subagent_name="build_plan_composer",
    task_description=f"Compose build plan for {feature_id}",
    context={...},
)
# Return value is a JSON string; reasoning model parses and decides next step.
```

**Gate.** Per ADR-ARCH-007, the output is always gated — the reasoning model evaluates the build plan score against retrieved priors and either auto-approves, flags for review, or hard-stops before `autobuild_runner` is dispatched.

---

## 3. `autobuild_runner` — Async SubAgent

### 3.1 Separate graph

Per ADR-ARCH-031, `autobuild_runner` is its own LangGraph graph registered in `langgraph.json`:

```json
{
  "graphs": {
    "forge":             "./src/forge/agent.py:graph",
    "autobuild_runner":  "./src/forge/subagents/autobuild_runner.py:graph"
  }
}
```

Both graphs run in the same process under `langgraph dev` (ASGI transport, co-deployed — ADR-ARCH-031 "Transport choice"). Zero network latency; no separate auth.

### 3.2 Factory

```python
# forge.subagents.autobuild_runner_spec
from deepagents import AsyncSubAgent
from forge.prompts import AUTOBUILD_RUNNER_PROMPT

def autobuild_runner_spec(domain_prompt: str) -> AsyncSubAgent:
    return AsyncSubAgent(
        name="autobuild_runner",
        description=(
            "Execute a build plan wave-by-wave, running /task-work per task and gating each. "
            "Long-running (30–90+ min). Launched via start_async_task. Supervisor polls "
            "check_async_task / list_async_tasks for live status. Mid-flight steering via "
            "update_async_task; cancellation via cancel_async_task. Internal approvals "
            "use interrupt() independently of the supervisor graph."
        ),
        system_prompt=AUTOBUILD_RUNNER_PROMPT.format(domain_prompt=domain_prompt),
        model="google_genai:gemini-2.5-flash",           # implementation model
        tools=[
            "read_file", "write_file", "edit_file", "ls", "glob", "grep",
            "execute",                                    # DeepAgents built-in — shells to /usr/local/bin/guardkit
            "write_todos",
            "interrupt",                                  # For gate-driven pauses inside waves
            "guardkit_task_work",
            "guardkit_task_review",
            "guardkit_task_complete",
            "guardkit_autobuild",
            "dispatch_by_capability",                     # For QA/UX/Ideation mid-build
            "record_stage",
            "emit_notification",
            "request_approval",
        ],
        transport="asgi",                                 # Co-deployed; ADR-ARCH-031
    )
```

### 3.3 Supervisor interaction

Exposed automatically by `AsyncSubAgentMiddleware`:

| Supervisor tool | Shape | Use |
|---|---|---|
| `start_async_task` | `(name, task_description, context) → task_id` | Dispatch autobuild |
| `check_async_task` | `(task_id) → {status, last_activity, async_tasks snapshot}` | Poll during long waits |
| `update_async_task` | `(task_id, directive) → ack` | Mid-flight steering |
| `cancel_async_task` | `(task_id, reason) → {cancelled: bool}` | Honour CLI cancel |
| `list_async_tasks` | `() → [{task_id, state, ...}]` | Populate `forge status` |

The `async_tasks` state channel is a first-class LangGraph channel and survives context compaction per DeepAgents 0.5.3 docs. See [DDR-006](../decisions/DDR-006-async-subagent-state-channel-contract.md) for Forge's contract over what lives in each task's state entry.

### 3.4 Interaction with `interrupt()`

When a gate inside `autobuild_runner` fires `interrupt()`:

- The **async subgraph** halts; the supervisor is **not** blocked.
- NATS `ApprovalRequestPayload` is published normally (see [API-nats-approval-protocol.md](API-nats-approval-protocol.md)).
- The NATS resume subscriber resumes the **specific subgraph** (not the supervisor) via the graph's resume API, passing the rehydrated `ApprovalResponsePayload`.
- The supervisor observes the pause via `check_async_task`/`list_async_tasks` — the task state includes `waiting_for="approval:{stage_label}"`.

---

## 4. Model Assignment Rationale

| Subagent | Model | Why |
|---|---|---|
| Supervisor (Forge graph) | `google_genai:gemini-3.1-pro` | Reasoning — makes all gate decisions, composes system prompts, decides stage ordering (ADR-ARCH-002, ADR-ARCH-010) |
| `build_plan_composer` | `google_genai:gemini-3.1-pro` | Reasoning — plan composition requires priors retrieval + risk reasoning |
| `autobuild_runner` | `google_genai:gemini-2.5-flash` | Implementation — task execution, file edits, shell ops; cheaper + faster for per-task loops |

All three are overridable via `forge.yaml.models.*` — provider-neutral via `init_chat_model("provider:model")` (ADR-ARCH-010).

---

## 5. Testing Contract

Per `pytest-agent-testing-specialist` rule:

- Unit tests patch `create_deep_agent`, `yaml.safe_load`, and the `SubAgent`/`AsyncSubAgent` factories.
- `tmp_path` fixtures stand in for `forge.yaml` and domain files.
- Async tests use `pytest-asyncio`; no real NATS/LangGraph server required.
- Integration tests against real NATS + real LangGraph server sit in `tests/integration/` and require `docker-compose up` of the GB10 stack.

---

## 6. Related

- ADRs: ADR-ARCH-031 (async-vs-sync rationale), ADR-ARCH-020 (DeepAgents built-ins)
- Tool layer: [API-tool-layer.md](API-tool-layer.md)
- Async state contract: [DDR-006-async-subagent-state-channel-contract.md](../decisions/DDR-006-async-subagent-state-channel-contract.md)
