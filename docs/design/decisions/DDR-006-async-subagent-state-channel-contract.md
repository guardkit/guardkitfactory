# DDR-006 — Async subagent state-channel contract (`async_tasks`)

## Status

Accepted

- **Date:** 2026-04-23
- **Session:** `/system-design`, design-pass 1
- **Related:** ADR-ARCH-031, ADR-ARCH-021, ADR-SP-013

---

## Context

ADR-ARCH-031 commits `autobuild_runner` to DeepAgents `AsyncSubAgent` — launched via `start_async_task`, supervised via five middleware-provided tools (`start_async_task`, `check_async_task`, `update_async_task`, `cancel_async_task`, `list_async_tasks`). The middleware maintains an `async_tasks` state channel that survives context compaction and is readable from the supervisor reasoning loop.

What the middleware does **not** specify is the **content** of each task's state entry. That's a Forge-level decision: what fields does `autobuild_runner` write into its state so that `forge status` and `forge history` can render meaningful live progress — and so that `forge.adapters.sqlite.reconcile_on_boot()` can make sense of a crash that happened mid-autobuild?

The refresh doc §"Forge history narrative" shows the intended UX (wave-level progress with task counts and Coach scores) but doesn't lock the schema.

## Decision

Each `async_tasks` entry is a Pydantic `AutobuildState` model, serialised to the state channel as `dict` (LangGraph channel requirement). Shape:

```python
class AutobuildState(BaseModel):
    # Identity
    task_id: str                                            # Assigned by start_async_task
    build_id: str
    feature_id: str

    # Progress
    lifecycle: Literal[
        "starting",
        "planning_waves",
        "running_wave",
        "awaiting_approval",
        "pushing_pr",
        "completed",
        "cancelled",
        "failed",
    ]
    wave_index: int = 0
    wave_total: int = 0
    task_index: int = 0
    task_total: int = 0
    current_task_label: str | None = None                   # Reasoning-model-chosen
    tasks_completed: int = 0
    tasks_failed: int = 0

    # Quality
    last_coach_score: float | None = None
    aggregate_coach_score: float | None = None              # Weighted average across completed tasks

    # Approval coupling
    waiting_for: str | None = None                          # e.g. "approval:Architecture Review"

    # Steering
    pending_directives: list[str] = []                      # Injected by supervisor via update_async_task

    # Timing
    started_at: datetime
    last_activity_at: datetime
    estimated_completion_at: datetime | None = None         # Computed from tasks remaining + per-task avg
```

**Write cadence:**

- On every lifecycle transition (entry and exit of each lifecycle state).
- On every task completion (wave/task index bumps, tasks_completed++, coach score updated).
- On every `interrupt()` fire (lifecycle → `awaiting_approval`, waiting_for set).
- On every supervisor-injected directive (append to pending_directives).
- Otherwise at most every 30s (avoid excess state-channel churn).

**Read patterns:**

- `forge status` (CLI) calls `list_async_tasks` → filters for the active build → renders lifecycle + wave/task indices + ETA.
- `forge history --feature X` does **not** read the live state channel; it reads the terminal state mirrored into `stage_log.details_json["subagent_trace"]` after completion.
- Supervisor reasoning model uses `check_async_task(task_id)` when deciding whether to continue waiting or proceed with another parallel concern.

**Crash-recovery linkage:** On Forge restart, `forge.adapters.sqlite.reconcile_on_boot()` reads `async_tasks` state channel (LangGraph persists it across checkpoints) alongside SQLite. If SQLite shows `RUNNING` and the state channel still has an `AutobuildState` with lifecycle != terminal, the reasoning model decides: retry-from-scratch (anchor §5 default) or inspect the trace to see if autobuild actually finished silently. The retry-from-scratch policy holds as the **default**; the state-channel data is advisory for reasoning.

**`waiting_for` ↔ ADR-ARCH-021 linkage:** When the async subgraph fires `interrupt()`, it sets `lifecycle="awaiting_approval"` + `waiting_for="approval:{stage_label}"` **before** calling interrupt. On resume (via NATS ApprovalResponsePayload), `autobuild_runner` clears `waiting_for` and returns to `running_wave`. This gives the supervisor observability into the pause without coupling it to the NATS approval subscription.

## Rationale

- **Explicit shape** — without a locked schema, two versions of `autobuild_runner` (current + future) risk writing divergent state that `forge status` can't render.
- **Enables ETA estimation** — storing `aggregate_coach_score` + `tasks_completed` / `task_total` lets `forge status` render meaningful progress, not just "still running".
- **Decouples supervisor observability from NATS** — `waiting_for` is readable via `check_async_task` without the supervisor subscribing to approval topics.
- **Defence in depth with SQLite** — authoritative lifecycle state still lives in SQLite; the state channel adds richness but the fault path is well-defined.

## Alternatives considered

- **Free-form `dict[str, Any]` state entries** — rejected; creates drift risk and forces renderer to tolerate unknown shapes.
- **Full `StageLogEntry` stream in the state channel** — rejected; doubles the write volume and SQLite already owns this.
- **State-channel as primary durability (drop SQLite mirror)** — rejected; LangGraph's async state channel is not a durability contract equivalent to SQLite + JetStream.

## Consequences

- **+** `forge status` can render wave-level progress, ETA, and pause reason — the refresh-doc UX becomes realisable.
- **+** Supervisor observability into pauses is schema-driven, not string-matching.
- **+** Crash-recovery has an extra advisory channel without compromising the authoritative SQLite + JetStream path.
- **−** Shape is now a versioned contract — changing field names requires a migration path. Mitigated by Pydantic's `extra="ignore"` default + additive-only evolution.
- **−** Every `autobuild_runner` write path has an obligation to update `AutobuildState` consistently; drift = degraded UX. Mitigated by a single helper `forge.subagents.autobuild_runner._update_state(...)` that centralises writes.

## Related components

- Subagent (`forge.subagents.autobuild_runner`)
- Agent Runtime (supervisor, via DeepAgents `AsyncSubAgentMiddleware`)
- CLI (`forge status`)
- Data model — [DM-build-lifecycle.md §4](../models/DM-build-lifecycle.md#4-relationships)
- API contract — [API-subagents.md §3.3](../contracts/API-subagents.md#33-supervisor-interaction)
