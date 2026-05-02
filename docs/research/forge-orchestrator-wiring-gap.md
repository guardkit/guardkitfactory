# Forge Orchestrator Wiring Gap — Findings

**Date**: 2026-05-02
**Author**: Investigation conducted while attempting TASK-FORGE-FRR-001
**Status**: Findings — feeds `/feature-spec` + `/feature-plan` for the next feature
**Provenance**: Surfaced by jarvis FEAT-JARVIS-INTERNAL-001 first-real-run on
GB10 2026-05-01 (`correlation_id a58ec9a7-27c6-485a-beac-e18675639a10`)

---

## Executive summary

**`forge serve` ships in production. The pipeline orchestrator it is
supposed to host does not.**

The complete pipeline state machine — `Supervisor`, the three dispatchers
(`SpecialistDispatcher`, `SubprocessDispatcher`, `AutobuildDispatcher`),
`PipelineConsumerDeps`, `PipelineLifecycleEmitter`, `ForwardContextBuilder`,
the `autobuild_runner` AsyncSubAgent — exists in `src/forge/pipeline/`
and `src/forge/adapters/nats/` as fully-Pydantic-validated, well-unit-tested
components with clean Protocol surfaces. But **none of them are
constructed in production**. Repository-wide:

```
$ grep -rn "Supervisor("                  src/forge/  # zero matches
$ grep -rn "PipelineConsumerDeps("        src/forge/  # zero matches
$ grep -rn "PipelineLifecycleEmitter("    src/forge/  # zero matches
$ grep -rn "ForwardContextBuilder("       src/forge/  # only one docstring example
$ find  src/forge -name "*runner*"                    # zero matches (no autobuild_runner subagent)
$ grep -rn "dispatch_autobuild_async("    src/forge/  # only the function definition itself
```

The components exist as **un-instantiated capability**. FEAT-FORGE-009
deliberately shipped the daemon process (`forge serve` + healthz +
JetStream durable consumer attach) and deferred the orchestrator wiring
into a single line in `_default_dispatch`'s docstring:

> The actual orchestrator wiring is owned by the existing
> `forge.adapters.nats.pipeline_consumer` machinery; `forge serve` is
> the new daemon process that hosts that machinery.

That sentence is structurally true and operationally misleading. The
"existing pipeline_consumer machinery" is itself unwired in production
— it has no caller anywhere in `src/forge/`. F009's deferral is much
larger than "wire `dispatch_payload`": it's the entire orchestration
tail of FEAT-FORGE-007 (Mode A greenfield) plus the per-build NATS
consumer wiring from TASK-NFI-007 plus the `PipelineLifecycleEmitter`
wiring from FEAT-FORGE-002.

This gap was first surfaced by the jarvis runbook's Phase 7 close
criterion ("between-prompt notifications render in the chat REPL,
showing stage-complete events for FEAT-43DE") — which could not be met
because nothing on the forge side publishes anything back. TASK-FORGE-FRR-001
was filed to "wire `dispatch_payload`", scoped against the assumption
that one wire was missing. The Phase 2.8 design checkpoint of FRR-001
discovered the deferral is structural and FRR-001-as-scoped is
infeasible without large-scale stub-building.

This document surfaces the gap so the next step can be a **real
feature**, scoped honestly, planned through `/feature-spec` and
`/feature-plan` against the existing architecture rather than another
follow-up task that papers over the same deferral with a placeholder.

---

## What's wired vs what isn't

### Wired in production today (FEAT-FORGE-009)

```
forge serve (CLI)
  └── _run_serve()  — opens NATS, runs daemon + healthz concurrently
        ├── run_daemon()
        │     ├── _attach_consumer  — JetStream durable "forge-serve"
        │     │                       on pipeline.build-queued.*
        │     │                       (NO max_ack_pending=1 today)
        │     ├── _consume_forever  — pull-loop, fetch one msg at a time
        │     └── _process_message
        │           ├── dispatch_payload(msg.data)  ◄─── seam, points at
        │           │                                   _default_dispatch
        │           │                                   which logs + returns
        │           │                                   (RECEIPT-ONLY STUB)
        │           └── msg.ack()    — fires unconditionally on success+failure
        └── run_healthz_server  — :8088 readiness probe
```

The daemon validates structurally that JetStream is reachable, attaches
a durable consumer, dequeues messages, acks them, and exits cleanly on
SIGTERM. **Nothing else happens.**

### Built but unwired in production

```
┌─────────────────────────────────────────────────────────────────────┐
│  forge.pipeline.supervisor.Supervisor                               │
│    fields: ordering_guard, per_feature_sequencer, constitutional_   │
│    guard, state_reader, ordering_stage_log_reader, per_feature_     │
│    stage_log_reader, async_task_reader, reasoning_model,            │
│    turn_recorder, specialist_dispatcher, subprocess_dispatcher,     │
│    autobuild_dispatcher, pr_review_gate, stage_hints                │
│                                                                     │
│    ⚠ NEVER CONSTRUCTED IN src/forge/                               │
└─────────────────────────────────────────────────────────────────────┘
        │
        ├── autobuild_dispatcher: AutobuildDispatcher
        │     ⚠ wraps dispatch_autobuild_async(...) — never wired
        │     │
        │     ├── forward_context_builder: ForwardContextBuilder
        │     │     ⚠ NEVER CONSTRUCTED IN src/forge/
        │     │
        │     ├── async_task_starter: AsyncTaskStarter
        │     │     ⚠ DeepAgents start_async_task middleware tool
        │     │     ⚠ never wired into a forge.cli entry point
        │     │
        │     ├── stage_log_recorder: StageLogRecorder
        │     │     ⚠ Protocol; SQLite implementation exists in
        │     │     forge.lifecycle.persistence but no production
        │     │     factory composes them
        │     │
        │     ├── state_channel: AutobuildStateInitialiser
        │     │     ⚠ Protocol; same situation
        │     │
        │     └── (then dispatches to AUTOBUILD_RUNNER_NAME = "autobuild_runner")
        │           ⚠ no module matches *runner* anywhere in src/forge/
        │           ⚠ the AsyncSubAgent itself doesn't exist
        │
        ├── specialist_dispatcher: SpecialistDispatcher
        │     ⚠ wraps dispatch_specialist_stage — same situation
        │
        └── subprocess_dispatcher: SubprocessDispatcher
              ⚠ wraps dispatch_subprocess_stage — same situation

┌─────────────────────────────────────────────────────────────────────┐
│  forge.adapters.nats.pipeline_consumer.PipelineConsumerDeps         │
│    fields: forge_config, is_duplicate_terminal, dispatch_build,     │
│    publish_build_failed                                             │
│                                                                     │
│    ⚠ NEVER CONSTRUCTED IN src/forge/ (only in tests)               │
│    ⚠ handle_message() never called outside tests                   │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  forge.pipeline.PipelineLifecycleEmitter                            │
│    methods: emit_build_started, emit_build_progress,                │
│    emit_stage_complete, emit_build_paused, emit_build_resumed,      │
│    emit_build_complete, emit_build_failed, emit_build_cancelled,    │
│    on_transition (generic dispatcher)                               │
│                                                                     │
│    ⚠ NEVER CONSTRUCTED IN src/forge/ (only in tests)               │
│    ⚠ no per-stage publish ever fires in production                 │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  forge.adapters.nats.pipeline_publisher.PipelinePublisher           │
│    methods: publish_build_started, publish_build_progress,          │
│    publish_stage_complete, publish_build_paused, ...                │
│                                                                     │
│    ⚠ Class itself is fine but nothing constructs it for the         │
│      daemon's NATS client                                           │
└─────────────────────────────────────────────────────────────────────┘
```

### What FEAT-FORGE-009 actually shipped

A daemon **process container**. The hexagonal-architecture port surface
of the orchestrator (`forge serve` reaches NATS, holds a durable, has a
healthz socket, exits on SIGTERM) but none of the **adapters** that
plug into the port (the actual orchestrator and its dispatchers).

This is consistent with `IMPLEMENTATION-GUIDE.md` for the
forge-production-image feature, which scoped F009 explicitly to
"daemon process + healthz + JetStream attach" and explicitly noted
the orchestrator wiring as out of scope. The deferred work was never
filed as a follow-up feature — only as the single FRR-001 task that
incorrectly assumed it was a one-wire fix.

---

## Why this is a feature, not a follow-up task

The FRR-001 plan estimated 3-4 days for "wire dispatch_payload + the
PipelineConsumerDeps factory". That estimate assumed:

- `dispatch_autobuild_async`'s collaborators were constructible
- `PipelineLifecycleEmitter` had per-stage callers somewhere
- `Supervisor` had a production constructor we could re-use

None of those are true. To honestly satisfy FRR-001's literal AC ("at
least one `pipeline.stage-complete.<feature_id>` envelope is published
back to JetStream with the same `correlation_id`") **without
synthetic stubs**, the actual scope is:

| Component | Scope of work |
|---|---|
| `autobuild_runner` AsyncSubAgent | **Net-new**: implement the DeepAgents subagent that runs an autobuild end-to-end. Currently doesn't exist in the codebase. |
| `start_async_task` middleware integration | **Net-new**: wire DeepAgents `AsyncSubAgentMiddleware` into a forge entry point. |
| `ForwardContextBuilder` production factory | **Net-new**: construct against SQLite reader + worktree allowlist. |
| `StageLogRecorder` production binding | Wire `forge.lifecycle.persistence` SQLite writer behind the Protocol. |
| `AutobuildStateInitialiser` production binding | Same — SQLite `async_tasks` channel writer. |
| `PipelineLifecycleEmitter` construction | Wire against `PipelinePublisher` (which itself needs construction against the daemon's NATS client). |
| `PipelineLifecycleEmitter` per-stage callers | **Net-new**: instrument the autobuild_runner subagent (and the supervisor's stage transitions) to call `emit_stage_complete` at the right boundaries. |
| `Supervisor` production construction | Compose 12+ injected deps. Must reuse the daemon's NATS client (no second connection). |
| `PipelineConsumerDeps.dispatch_build` wiring | The thin closure that wraps Supervisor's autobuild path so `pipeline_consumer.handle_message` can dispatch into it. |
| `_serve_daemon` seam refactor | Change `DispatchFn` from `(bytes) -> None` to `(_MsgLike) -> None`; add `max_ack_pending=1`; remove post-dispatch ack from `_process_message`. (This was FRR-001's first piece — reusable in the new feature.) |
| Crash-recovery integration | `pipeline_consumer.reconcile_on_boot` and `forge.lifecycle.recovery.reconcile_on_boot` (two functions, same name, different responsibilities) need a single boot-time call site somewhere in `_run_serve` — neither has one today. |
| BDD scenarios + integration tests | The Mode A feature (FEAT-FORGE-007) already specifies the orchestrator's behaviour; this feature must verify those scenarios against the wired-in-production stack. |

This is **multi-week work**, not a 3-day task. It needs feature-level
scoping, requirements decomposition, and a proper task plan.

---

## Constraints carried from existing architecture

This feature must honour the following pre-existing decisions:

| Anchor | Constraint |
|---|---|
| **ADR-ARCH-014** (single consumer, max_ack_pending=1) | Sequential builds; one outstanding-ack slot per durable. Multi-replica is achieved by JetStream handing the one slot to whichever replica fetched it; replicas idle when the slot is taken. |
| **ADR-ARCH-031** (AsyncSubAgents for long-running work) | Autobuild runs as a DeepAgents `AsyncSubAgent` via `start_async_task`. The supervisor's reasoning loop stays responsive while autobuild executes in the background. |
| **ADR-SP-013** (referenced in ADR-ARCH-021 and assumptions.yaml; standalone file not present in `docs/architecture/decisions/` — naming may have shifted) | Terminal-only ack: `pipeline_consumer.handle_message` hands an `ack_callback` to the state machine; the message remains unacked across non-terminal states (PAUSED, RUNNING, etc.). Crash-recovery is retry-from-scratch with SQLite as authoritative truth, the JetStream stream as a derived projection. |
| **ADR-ARCH-021** (PAUSED via LangGraph interrupt) | Pause/resume via the approval protocol (FEAT-FORGE-004); paused builds re-emit lifecycle on boot (`reconcile_on_boot`). |
| **ADR-ARCH-027** (no horizontal scaling) | Single-process daemon assumption. Multi-replica is for failover, not parallelism. |
| **ADR-ARCH-008** (forge produces own history) | SQLite is the durable source of truth; NATS is a derived projection that subscribers can re-read. Publish failures must not corrupt SQLite state. |
| **API contract** `docs/design/contracts/API-nats-pipeline-events.md` | The eight `pipeline.{event}.{feature_id}` subjects are the public contract. The emitter's responsibility is to publish them in order with correct payload shapes; subscribers' contract is to thread on `correlation_id`. |
| **DDR-006** (`AutobuildState` lifecycle Pydantic) | The `lifecycle` field's `Literal` values are the canonical state-channel transitions: `starting → planning_waves → running_wave → awaiting_approval → completed/failed/cancelled`. The autobuild_runner subagent owns these writes; the dispatcher writes only `"starting"`. |
| **FEAT-FORGE-007 / Mode A spec** | The end-to-end orchestrator behaviour is already specified in Gherkin in `features/mode-a-greenfield-end-to-end/`. This feature must satisfy those scenarios in production, not just in unit tests with mocked dispatchers. |

---

## What FRR-001 should become

Three plausible disposals for the existing FRR-001 + FRR-001b task pair:

**(1) Subsume into the new feature.** Both task files become reference
material; their ACs become acceptance criteria of the new feature
(possibly as separate sub-tasks). The new feature carries the
correlation_id back to the original GB10 run.

**(2) Close FRR-001 + FRR-001b as `superseded-by-feature`.** Move them
to `tasks/completed/` with a frontmatter note that they're closed
because the work was re-scoped at a higher level. The new feature
references them as historical context.

**(3) Keep FRR-001 in backlog, scoped down.** Strip FRR-001 to just
the `_serve_daemon` seam refactor (changing `DispatchFn` from `(bytes)`
to `(_MsgLike)`, adding `max_ack_pending=1`, removing the post-dispatch
ack). That's an honest 0.5-day refactor that the new feature can
build on. Cancel FRR-001b entirely (the per-stage publishing is
intrinsic to the new feature).

Recommendation: **(1)** if the new feature can carry the correlation_id
through; **(2)** otherwise. **(3)** is technically clean but produces
two artifacts moving in lock-step which is bookkeeping noise.

---

## Proposed feature scope (to feed `/feature-spec`)

**Working title**: "Wire the production pipeline orchestrator into
`forge serve`" (slug: `forge-serve-orchestrator-wiring` or similar —
final naming is for `/feature-spec` to settle).

**One-line scope statement**: `forge serve` consumes a
`pipeline.build-queued.<feature_id>` envelope, dispatches the autobuild
end-to-end through the existing Mode A orchestrator chain
(supervisor + dispatchers + autobuild_runner subagent), publishes the
full lifecycle event sequence (`build-started`, `stage-complete×N`,
`build-complete` or `build-failed`) back to JetStream with the same
`correlation_id`, and survives crash + restart with no lost or
duplicated builds.

**What's in scope**:

- Construct `Supervisor`, `PipelineConsumerDeps`, `PipelineLifecycleEmitter`,
  `PipelinePublisher`, `ForwardContextBuilder` in production.
- Implement the `autobuild_runner` AsyncSubAgent.
- Wire DeepAgents `AsyncSubAgentMiddleware` into `_run_serve`.
- Refactor `_serve_daemon._process_message` per the FRR-001 design
  (seam contract change to `(_MsgLike) -> None`, deferred-ack to the
  state machine, `max_ack_pending=1` on the durable).
- Wire `reconcile_on_boot` (both flavours) into the daemon startup.
- Per-stage `emit_stage_complete` calls inside the autobuild_runner.
- E2E tests: jarvis chat REPL → forge serve → real autobuild runs →
  full lifecycle envelope sequence visible at the chat REPL, threaded
  by `correlation_id`.

**What's out of scope**:

- Net-new orchestration semantics. The behaviour spec already exists
  in FEAT-FORGE-007; this feature wires that spec into production.
- Mode B / Mode C orchestration (separate features:
  `mode-b-feature-and-mode-c-review-fix`).
- Jarvis-side `forge_subscriber` workqueue attach fix (separate
  jarvis-side task).
- Adding new lifecycle envelope types (the eight in
  `API-nats-pipeline-events.md §3` are the catalogue).
- Approval / pause-resume integration (FEAT-FORGE-004 territory; if
  it's a one-line addition, include; otherwise track separately).

---

## Empirical evidence chain

1. **2026-05-01, GB10**: FEAT-JARVIS-INTERNAL-001 first-real-run.
   `correlation_id a58ec9a7-27c6-485a-beac-e18675639a10`. Phase 7
   close criterion fails: nothing renders in the chat REPL between
   prompts.

2. **`docker logs forge-prod | wc -l → 0`** (separately fixed by
   TASK-FORGE-FRR-002, `b1da833`, 2026-05-01: `serve_cmd` now calls
   `logging.basicConfig`).

3. **Consumer state inspection**: `nats consumer info PIPELINE
   forge-serve -j` → `delivered=1, acked=1, num_pending=0,
   num_redelivered=0`. The daemon dequeued and acked, but published
   nothing back.

4. **TASK-FORGE-FRR-001 filed** with the assumption "wire
   dispatch_payload to the existing pipeline_consumer machinery".

5. **2026-05-02, FRR-001 Phase 2.8 design checkpoint**: investigation
   surfaces that `pipeline_consumer.PipelineConsumerDeps` is itself
   never wired in production, the autobuild dispatcher's four
   collaborators have no production constructors, the `Supervisor`
   class has zero production callers, and the `autobuild_runner`
   subagent doesn't exist as a module anywhere. Plan re-scoped to
   include the production wiring of `PipelineConsumerDeps`; estimate
   inflates from 1-2 days to 3-4 days.

6. **2026-05-02, FRR-001 implementation phase, file #1 mid-edit**:
   investigation goes one level deeper. The autobuild dispatcher's
   collaborators not being constructible isn't the floor — the
   `Supervisor` itself isn't, the entire FEAT-FORGE-007 Mode A
   orchestration chain that it's supposed to drive isn't, and the
   `autobuild_runner` AsyncSubAgent doesn't exist. The honest scope
   is multi-week, feature-level work. **FRR-001 stops; this document
   is written; `/feature-spec` + `/feature-plan` is the next step.**

---

## References

### Primary architectural anchors

- `docs/architecture/ARCHITECTURE.md` — system overview
- `docs/architecture/container.md` — container-level diagram and process boundaries
- `docs/architecture/domain-model.md` — domain entities and their relationships
- `docs/architecture/system-context.md` — external context
- `docs/architecture/assumptions.yaml` — the ASSUM-* registry referenced throughout
- `docs/research/forge-pipeline-architecture.md` — the existing pipeline architecture writeup
- `docs/research/pipeline-orchestrator-motivation.md` — original motivation
- `docs/research/pipeline-orchestrator-consolidated-build-plan.md` — consolidated build plan
- `docs/research/forge-build-plan-alignment-review.md` — alignment review

### ADRs that constrain the design

- `docs/architecture/decisions/ADR-ARCH-014-single-consumer-max-ack-pending.md`
- `docs/architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md`
- `docs/architecture/decisions/ADR-ARCH-021-paused-via-langgraph-interrupt.md`
- `docs/architecture/decisions/ADR-ARCH-027-no-horizontal-scaling.md`
- `docs/architecture/decisions/ADR-ARCH-008-forge-produces-own-history.md`
- `docs/architecture/decisions/ADR-ARCH-001-hexagonal-inside-deepagents.md`
- `docs/architecture/decisions/ADR-ARCH-020-adopt-deepagents-builtins.md`
- ADR-SP-013 — referenced widely (terminal-only ack, retry-from-scratch
  crash recovery) but the standalone file doesn't appear in
  `docs/architecture/decisions/`. May be in a different ADR series or
  the reference may be stale; needs reconciliation during /feature-spec.

### Data-model decision records

- `docs/design/decisions/DDR-006-async-subagent-state-channel-contract.md`
  — `AutobuildState` lifecycle literals
- `docs/design/decisions/DDR-001-reply-subject-correlation.md`
  — correlation-id threading rules
- `docs/design/decisions/DDR-003-sqlite-schema-layout-wal.md`
  — SQLite schema constraints
- `docs/design/models/DM-build-lifecycle.md`
  — build state machine
- `docs/design/models/DM-gating.md`
  — gating model the orchestrator must respect

### Integration contracts

- `docs/design/contracts/API-nats-pipeline-events.md` — **the bus shape this feature must conform to**
- `docs/design/contracts/API-sqlite-schema.md` — SQLite schema contract
- `docs/design/contracts/API-subagents.md` — subagent contract
- `docs/design/contracts/API-nats-approval-protocol.md` — approval protocol (for the pause/resume integration question)

### Existing feature specs (the orchestrator behaviour is already spec'd here)

- `features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature` — **the canonical orchestrator behaviour spec**
- `features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end_summary.md`
- `features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end_assumptions.yaml`
- `features/forge-production-image/forge-production-image.feature` — what F009 actually shipped (the daemon process)
- `features/pipeline-state-machine-and-configuration/pipeline-state-machine-and-configuration.feature`
- `features/specialist-agent-delegation/specialist-agent-delegation.feature`
- `features/infrastructure-coordination/infrastructure-coordination.feature` (related: the inbound build-queue contract)
- `features/nats-fleet-integration/nats-fleet-integration.feature`

### Source files holding the unwired components (de-facto Protocol contracts)

- `src/forge/pipeline/supervisor.py` — `Supervisor` (the unwired root)
- `src/forge/pipeline/dispatchers/autobuild_async.py` — `dispatch_autobuild_async` and its four Protocols
- `src/forge/pipeline/__init__.py` — `PipelineLifecycleEmitter` (the unwired emitter)
- `src/forge/pipeline/forward_context_builder.py` — `ForwardContextBuilder`
- `src/forge/pipeline/per_feature_sequencer.py`
- `src/forge/pipeline/cli_steering.py` — cancel/skip/directive surface
- `src/forge/pipeline/stage_taxonomy.py` — `StageClass` enum (the `stage_label` source)
- `src/forge/adapters/nats/pipeline_consumer.py` — `PipelineConsumerDeps`, `handle_message`, `reconcile_on_boot`
- `src/forge/adapters/nats/pipeline_publisher.py` — `PipelinePublisher`
- `src/forge/cli/_serve_daemon.py` — the daemon body (FRR-001's seam refactor target)
- `src/forge/cli/serve.py` — `_run_serve` (where construction happens)
- `src/forge/cli/_serve_config.py` — `ServeConfig` (env-driven configuration surface)
- `src/forge/lifecycle/persistence.py` — SQLite writers (likely sources for `StageLogRecorder` and `AutobuildStateInitialiser`)
- `src/forge/lifecycle/recovery.py` — the second `reconcile_on_boot` (lifecycle-side, distinct from `pipeline_consumer.reconcile_on_boot`)
- `src/forge/config/models.py` — `ForgeConfig`, `PipelineConfig`, `DEFAULT_APPROVED_ORIGINATORS`

### Test files (executable specifications of the dispatcher contracts)

- `tests/forge/test_supervisor.py` — Supervisor behavioural tests
- `tests/forge/test_supervisor_mode_dispatch.py` — mode-aware dispatch
- `tests/forge/test_dispatch_autobuild_async.py` — the autobuild dispatcher Protocol contracts
- `tests/forge/test_pipeline_consumer.py` — `handle_message` contract
- `tests/forge/test_pipeline_lifecycle.py` — `PipelineLifecycleEmitter` contract
- `tests/forge/test_per_feature_sequencer.py` — per-feature sequencer
- `tests/forge/test_contract_and_seam.py` — `PipelineConsumerDeps` shape
- `tests/integration/test_mode_a_crash_recovery.py` — crash-recovery integration
- `tests/integration/test_mode_b_smoke_e2e.py` — e2e smoke
- `tests/integration/test_mode_b_c_crash_recovery.py` — crash recovery for mode B/C
- `tests/cli/test_serve_*.py` — daemon-process tests (F009 surface)

### Tasks that ground this work historically

- `tasks/completed/forge-production-image/IMPLEMENTATION-GUIDE.md` — F009 implementation guide (explicitly defers orchestrator wiring)
- `tasks/completed/forge-production-image/README.md`
- `tasks/completed/forge-production-image/TASK-F009-003-implement-forge-serve-daemon.md` — the daemon body task (where `_default_dispatch` was first introduced as a stub)
- `tasks/in_progress/TASK-FORGE-FRR-001-wire-dispatch-payload-to-real-orchestrator.md` — the symptom that surfaced this
- `tasks/backlog/feat-jarvis-internal-001-followups/TASK-FORGE-FRR-001b-publish-pipeline-lifecycle-from-autobuild-orchestrator.md` — the per-stage publishing intent
- `docs/state/TASK-FORGE-FRR-001/implementation_plan.md` — the planning artifact produced during the FRR-001 design phase (captures the seam-refactor design + the 3-day estimate that turned out to be wrong)

### External evidence

- `/home/richardwoollcott/Projects/appmilla_github/jarvis/docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md` — RESULTS file from the GB10 first-real-run
- `/home/richardwoollcott/Projects/appmilla_github/jarvis/docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md` — the runbook itself

---

## What this document is not

- **Not a design.** It identifies the gap and lists the constraints. The
  design choices (where the emitter is constructed, how the
  `autobuild_runner` subagent is structured, how `start_async_task`
  middleware is wired) are for `/feature-spec` and `/feature-plan` to
  settle.
- **Not a task list.** No file changes are proposed here. The task
  decomposition is for `/feature-plan` to produce.
- **Not a recommendation that the existing code is wrong.** The
  components are well-built and well-tested. The gap is *only* in
  production composition. This is a wire-it-together feature, not a
  refactor.
