# ADR-ARCH-031: Async subagents for long-running work; sync `task()` for bounded delegation

- **Status:** Accepted
- **Date:** 2026-04-19
- **Session:** Amendment to `/system-arch` Category 4 (post-session refinement following fleet v3 alignment)
- **Amends:** ADR-ARCH-020 (adopt DeepAgents 0.5.3 built-ins)
- **Related:** fleet-architecture-v3-coherence-via-flywheel.md §3-4, DeepAgents 0.5.3 release notes (15 April 2026)

## Context

ADR-ARCH-020 committed Forge to the full DeepAgents 0.5.3 built-in toolset and pre-declared two subagents via sync `task()`:

- `build_plan_composer`
- `autobuild_runner`

This was before the full implications of DeepAgents 0.5.3's `AsyncSubAgent` preview feature were considered in context of Forge's actual workload profile. Review of the released docs (19 April 2026) and the fleet v3 vision surfaced an asymmetry:

- `build_plan_composer` runs briefly (seconds to a minute) and its output gates the next stage. The supervisor *should* block on it — its result directly informs the reasoning model's next decision.
- `autobuild_runner` runs for 30 minutes to several hours. Blocking the supervisor for that entire window means:
  - `forge status` cannot reflect live progress beyond "still running"
  - No mechanism for the supervisor to emit partial progress notifications
  - No way for Rich to send mid-flight instructions ("skip the remaining integration tests, just push what you have")
  - No way to cancel a wayward autobuild without killing the whole supervisor process

DeepAgents 0.5.3's `AsyncSubAgent` is the native mechanism that solves all four of those. It returns a task ID immediately, maintains a dedicated `async_tasks` state channel that survives context compaction, and exposes five supervisor-level tools: `start_async_task`, `check_async_task`, `update_async_task`, `cancel_async_task`, `list_async_tasks`.

This is not a reopening of ADR-ARCH-020 — it is a refinement of *which* built-in to use for *which* subagent.

## Decision

**Forge uses async subagents for long-running delegation and sync `task()` for bounded delegation.** Specifically:

- `build_plan_composer` — **sync `task()`.** Output gates the next reasoning step; blocking is correct.
- `autobuild_runner` — **`AsyncSubAgent`.** Launches via `start_async_task`, returns immediately. Supervisor continues the reasoning loop. `forge status` reads from `async_tasks` state channel via `list_async_tasks` for live progress.

General principle for future subagents: if the expected runtime is bounded and sub-minute and the output is needed to proceed, use sync `task()`. If the expected runtime is open-ended or multi-minute and the supervisor can meaningfully continue without the result, use `AsyncSubAgent`.

### Transport choice

`autobuild_runner` uses **ASGI transport (co-deployed)** by default. It runs as a separate LangGraph graph registered in the same `langgraph.json` as the Forge supervisor. Zero network latency, no auth configuration.

HTTP transport (remote) is reserved for the future case where autobuild needs to run on separate compute (e.g. a dedicated GB10-with-different-GPU-profile). Not v1.

### `langgraph.json` shape

```json
{
  "graphs": {
    "forge": "./src/forge/agent.py:graph",
    "autobuild_runner": "./src/forge/subagents/autobuild_runner.py:graph"
  }
}
```

### Supervisor tools exposed by `AsyncSubAgentMiddleware`

All five tools are available to the Forge supervisor's reasoning model:

| Tool | Used by Forge for |
|---|---|
| `start_async_task` | Dispatching an autobuild |
| `check_async_task` | Polling for completion when making "should I continue?" decisions |
| `update_async_task` | Mid-flight steering ("stop after current wave, don't start next") |
| `cancel_async_task` | Responding to `forge cancel FEAT-XXX` CLI command |
| `list_async_tasks` | Serving `forge status` and populating `build history` narrative |

### Interaction with ADR-ARCH-021 (`interrupt()`)

`interrupt()` continues to be the PAUSED mechanism (ADR-ARCH-021) unchanged by this amendment. When an approval gate inside `autobuild_runner` calls `interrupt()`, it halts the async subgraph, not the supervisor. The supervisor observes the paused state via `check_async_task` / `list_async_tasks`; the NATS `ApprovalResponsePayload` subscriber resumes the specific subgraph that interrupted. The external approval protocol (`ApprovalRequestPayload` published, SQLite marks PAUSED, JetStream redelivery for crash recovery) is unchanged — the `async_tasks` state channel supplements, rather than replaces, the SQLite + JetStream recovery path described in ADR-ARCH-021 and ADR-SP-013.

### Crash recovery

The `async_tasks` state channel is part of LangGraph's supervisor graph state. On Forge restart, the supervisor reads the channel and knows which autobuilds were in flight. Combined with the existing JetStream + SQLite reconciliation pattern from ADR-SP-013:

- JetStream redelivers the unacknowledged `build-queued` message
- SQLite shows the build in RUNNING / FINALISING status
- `async_tasks` channel reveals whether an autobuild was in-flight, its task ID, and its last-known status
- Forge's reasoning model decides: retry from scratch (INTERRUPTED) or resume awareness of in-flight autobuild (if the task ID is still live in the async subagent's state)

The existing "retry from scratch" policy (anchor §5) holds as the default. The enhancement is that Forge has more information on restart to reason about whether the autobuild actually completed silently before the crash.

### Forge history narrative

With async subagents, `forge history --feature FEAT-XXX` now reads as:

```
FEAT-FORGE-007 build 2026-04-20T10:00:00
  10:00:01  Retrieved priors from forge_pipeline_history (14 entities)
  10:00:03  Dispatched build_plan_composer (sync)
  10:00:47  Plan received: 4 waves, 12 tasks
  10:00:48  Dispatched autobuild_runner (async, task_id=autobuild-a3f2)
  10:07:12  Checked autobuild-a3f2 — Wave 1 complete, 4/12 tasks done
  10:22:04  Checked autobuild-a3f2 — Wave 2 complete, 8/12 tasks done
  10:38:55  Checked autobuild-a3f2 — Wave 3 complete, 11/12 tasks done
  10:44:17  Checked autobuild-a3f2 — Complete, score 0.91
  10:44:18  Proceeding to PR creation stage
  ...
```

This is the "emergent stage labels" idea from ADR-ARCH-016 rendered into Rich's narrative. Labels are reasoning outputs, not a controlled vocabulary.

## Consequences

**Positive:**

- **Live progress visibility.** `forge status` and `forge history` become meaningful mid-build, not just "running" for 40 minutes.
- **Cancellation capability.** Rich can `forge cancel FEAT-XXX` mid-autobuild without killing the supervisor.
- **Mid-flight steering.** Rich can inject instructions ("skip remaining wave-3 tasks") via approval round-trip to `update_async_task`.
- **No violation of sequential builds constraint.** ADR-SP-012 and `max_ack_pending=1` still hold — only the supervisor is unblocked, not the JetStream consumer. Forge still processes one build at a time.
- **Better trace capture.** Async subagent runs are separate LangSmith traces, linked by task ID. Matches ADR-FLEET-001 trace-richness commitment.
- **No retrofit risk.** Adding async subagents to an already-deployed autobuild_runner would be much more work than starting with them.

**Negative:**

- **Preview feature dependency.** `AsyncSubAgent` is marked preview in 0.5.3; APIs may change in 0.6.x. Mitigated by DeepAgents pin `>=0.5.3, <0.6` and ongoing monitoring of release notes.
- **Slightly more moving parts.** Two graphs in `langgraph.json` instead of one. Acceptable — the separation is logical.
- **Supervisor prompt complexity.** The reasoning model needs clear guidance on when to use `check_async_task` versus waiting. Mitigated by DeepAgents' built-in prompt rules (documented in the 0.5.3 docs) and by Forge system-prompt additions.

## Do-not-reopen

- The sync-vs-async choice per subagent is set. Future subagents are classified at declaration time based on the same bounded-vs-unbounded criterion.
- ASGI transport is the default. HTTP transport requires a new ADR specifying why split deployment is needed.

## References

- fleet-architecture-v3-coherence-via-flywheel.md §3-4
- DeepAgents 0.5.3 release notes (15 April 2026)
- DeepAgents async-subagents docs (fetched 19 April 2026)
- ADR-ARCH-020 (adopt DeepAgents built-ins — amended by this ADR)
- ADR-ARCH-002 (two-model separation — orthogonal; sync/async is shape-not-model)
- ADR-ARCH-007 (build plan as gated artefact — `build_plan_composer` stays sync because its output gates the next stage)
- ADR-ARCH-008 (Forge produces its own history — autobuild command_history.md writes happen from inside the async subagent)
- ADR-ARCH-021 (PAUSED via `interrupt()` — see Interaction sub-section above)
- ADR-SP-012, ADR-SP-013 (sequential builds, JetStream + SQLite recovery)
- ADR-FLEET-001 (trace-richness)
