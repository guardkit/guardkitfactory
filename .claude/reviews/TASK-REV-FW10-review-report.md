# TASK-REV-FW10: Decision-Mode Review Report
## FEAT-FORGE-010 — Wire the production pipeline orchestrator into `forge serve`

**Mode:** decision
**Depth:** standard (Context A: focus = task_decomposition_and_risk; tradeoff = quality)
**Reviewer:** /feature-plan orchestrator (decision-mode analysis)
**Completed:** 2026-05-02
**Score:** 86 / 100 (recommended for implementation; architectural choices already settled)

---

## 1. Executive Summary

FEAT-FORGE-010 closes the structural gap between `forge serve`'s shipped
daemon process (FEAT-FORGE-009) and the un-instantiated orchestrator
chain (`Supervisor`, `PipelineConsumerDeps`, `PipelineLifecycleEmitter`,
`PipelinePublisher`, `ForwardContextBuilder`, plus the net-new
`autobuild_runner` AsyncSubAgent). The architecture is unusually settled
for a feature plan: DDR-007 chose Option A (thread the lifecycle emitter
through the dispatcher's context payload, co-located with DDR-006's
`_update_state` boundary), all 18 assumptions are confirmed, and the
seam-refactor design from the superseded TASK-FORGE-FRR-001 is reusable
verbatim. The dominant residual risk is **production composition order
under crash recovery** — both `reconcile_on_boot` routines must run
before the consumer fetches its first message, otherwise an in-flight
build's redelivered envelope will be processed against an unreconciled
durable-history view. The task plan therefore foregrounds the seam
refactor + paired `reconcile_on_boot` wiring as Wave 1, lands the
five net-new orchestrator components in parallel as Wave 2, composes
them at the `_serve_deps` factory in Wave 3, and proves the lifecycle
envelope sequence end-to-end in Wave 4.

**Recommended approach: single end-to-end implementation following
DDR-007 — no carve-outs.** Pause/resume publish stays in scope; the
synthetic dispatch-stage envelope from FRR-001 is dropped per ASSUM-004;
the autobuild_runner subagent + its four collaborators land as five
parallel tasks in one wave per the user's Context A choice.

---

## 2. Scope Assessment

**In-scope for FEAT-FORGE-010 (per the gap doc and confirmed assumptions):**
- Construct `Supervisor`, `PipelineConsumerDeps`, `PipelineLifecycleEmitter`,
  `PipelinePublisher`, `ForwardContextBuilder` once per daemon process,
  bound to the daemon's single shared NATS connection (ASSUM-002, ASSUM-011).
- Implement the `autobuild_runner` AsyncSubAgent module
  (`src/forge/subagents/autobuild_runner.py`, currently absent from the
  repo) with the DDR-006 `_update_state` helper extended per DDR-007 to
  call the matching `emit_*` method at the same boundary.
- Register `autobuild_runner` as a separate graph in `langgraph.json`
  under ASGI co-deployment (ADR-ARCH-031, ASSUM-003).
- Wire DeepAgents `AsyncSubAgentMiddleware` (start/check/update/cancel/list)
  into the supervisor's reasoning loop.
- Refactor `_serve_daemon._process_message`'s `DispatchFn` from
  `(bytes) -> None` to `(_MsgLike) -> None`; remove the post-dispatch
  ack from the success path (deferred to the state machine via
  `pipeline_consumer.handle_message`'s `ack_callback`); set
  `max_ack_pending=1` on the durable's `ConsumerConfig` (ASSUM-005,
  ASSUM-006, ASSUM-007).
- Wire **both** `reconcile_on_boot` routines (`pipeline_consumer.reconcile_on_boot`
  + `forge.lifecycle.recovery.reconcile_on_boot`) into `_run_serve` —
  before the consumer's first fetch (ASSUM-009).
- Per-stage `emit_stage_complete` from inside `autobuild_runner`'s
  `_update_state` boundary, with `target_kind="subagent"` and
  `target_identifier=task_id` for autobuild-internal transitions
  (ASSUM-018).
- `emit_build_paused` at the `lifecycle="awaiting_approval"` transition
  inside `_update_state`; `emit_build_resumed` in the existing
  `forge.adapters.nats.approval_subscriber` resume path (DDR-007 keeps
  pause/resume in scope; ASSUM-010).
- Healthz endpoint extension: healthy iff NATS subscription is live
  AND the orchestrator chain is fully constructed (ASSUM-012).
- Validation surface for malformed payload, duplicate detection
  (SQLite unique index on `(feature_id, correlation_id)`), and
  worktree-allowlist gating (ASSUM-013, ASSUM-014, ASSUM-015).
- E2E integration test: build-queued envelope → terminal envelope, all
  envelopes correlation-id threaded.

**Strictly upstream (do not re-implement):**
- FEAT-FORGE-001 owns the SQLite state machine, `stage_log` schema,
  state transitions, durable history, and crash-recovery (retry-from-scratch).
  This feature **reads** from that store; it must not change schema or
  add transitions.
- FEAT-FORGE-002 owns `PipelinePublisher`, the eight pipeline-event
  subjects, the approval channel surface, and correlation-id threading
  rules. This feature **constructs** the publisher in production; it
  must not modify the class itself or add subjects.
- FEAT-FORGE-004 owns the pause/resume protocol semantics
  (`ApprovalResponsePayload`, idempotent first-wins, correlation-keyed
  reply subjects per DDR-001). This feature wires the publish-back
  path; it must not modify approval semantics.
- FEAT-FORGE-007 owns the Mode A orchestration semantics (stage chain,
  gating policy, per-feature loop, constitutional pull-request review).
  This feature **verifies** those semantics in production; it must not
  re-spec them.
- FEAT-FORGE-009 owns the daemon process, healthz endpoint, JetStream
  durable attach, and SIGTERM handling. This feature **changes** the
  `_process_message` seam contract, switches `max_ack_pending` from
  default to 1, adds the paired `reconcile_on_boot` calls, and replaces
  the receipt-only `_default_dispatch` with the real orchestrator
  dispatch.

**Explicitly out of scope:**
- Net-new lifecycle envelope types beyond the eight in
  `API-nats-pipeline-events.md §3`.
- Mode B / Mode C orchestration (separate features).
- Jarvis-side `forge_subscriber` workqueue attach fix.
- HTTP transport for the `autobuild_runner` AsyncSubAgent (ASGI is the
  default per ADR-ARCH-031; HTTP is its own future ADR per
  DDR-007 §Forward compatibility).
- Renaming dormant `forge-consumer` durable constant (separate cleanup).

---

## 3. Architectural Decisions (already settled, not re-opened)

| Decision | Source | Outcome |
|---|---|---|
| Lifecycle emitter wiring path | DDR-007 | **Option A** — thread emitter through dispatcher context; call from `_update_state` co-located with the state-channel write. |
| Pause/resume publish in scope of this feature | DDR-007 §Decision; ASSUM-010 | **In scope.** Single one-line addition at each call site. Carve-out only if implementation discovers a structural blocker (instructed split-out path documented). |
| Stage-complete from inside subagent envelope shape | DDR-007 §Decision; ASSUM-018 | `target_kind="subagent"`, `target_identifier=task_id`. Supervisor's emit calls (for stages dispatched outside the subagent) use existing taxonomy unchanged. |
| Synthetic dispatch-stage envelope | ASSUM-004; FRR-001 SUPERSEDED | **Dropped.** Only real stage transitions emit `stage-complete`. |
| Seam refactor of `_serve_daemon._process_message` | TASK-FORGE-FRR-001 implementation_plan.md | **Reused verbatim.** `(bytes) -> None` → `(_MsgLike) -> None`; ack moves to `pipeline_consumer.handle_message`'s deferred `ack_callback`; remove post-dispatch ack on success. |
| `max_ack_pending=1` on `forge-serve` durable | ADR-ARCH-014; ASSUM-005 | Set in `_attach_consumer`'s `ConsumerConfig`. Operational note: existing consumer must be deleted before deploying (`nats consumer rm PIPELINE forge-serve`). |
| Single shared NATS connection | ASSUM-011; FRR-001 implementation_plan.md | One connection opened in `_run_serve`; passed to both consumer and publisher. Refactor `run_daemon` to accept an injected client. |
| autobuild_runner transport | ADR-ARCH-031; ASSUM-003 | ASGI co-deployment via DeepAgents `AsyncSubAgent`. Subagent is a reachable Python object — non-serialisable context payload is OK. |
| Recovery authority | ADR-ARCH-008; DDR-006; ASSUM-017 | SQLite history is authoritative. `async_tasks` channel is advisory. Both `reconcile_on_boot` routines run at startup. |
| Approval reply subject correlation | DDR-001; ASSUM-016 | Correlation-keyed reply subjects; mismatched correlation_id is dropped. |

---

## 4. Findings

### F1 — Composition order under crash recovery (HIGH risk)

The two `reconcile_on_boot` routines (one in `pipeline_consumer.py`,
one in `forge.lifecycle.recovery`) **must run before the consumer's
first fetch**. If the consumer fetches a redelivered message before
the durable history has been reconciled, the build will be processed
against a stale view (e.g., a build that crashed while paused will
re-emit `build-started` instead of `build-paused`, breaking the audit
sequence). Wave 1 must wire both routines synchronously before the
consumer attaches.

**Mitigation:** Sequence in `_run_serve`:
1. Open NATS client.
2. Open SQLite pool.
3. Run `forge.lifecycle.recovery.reconcile_on_boot(sqlite_pool)`.
4. Run `pipeline_consumer.reconcile_on_boot(client, sqlite_pool, publisher)`.
5. Construct supervisor + deps factory.
6. Attach durable consumer (`_attach_consumer`).
7. Start healthz + daemon loops.

### F2 — `_update_state` is the single transition site for both DDR-006 and DDR-007 (DESIGN)

DDR-007 explicitly co-locates the emitter call with the state-channel
write at `_update_state`. The implementation must not have two
divergent transition sites. The autobuild_runner module's
`_update_state` is the single canonical site; every lifecycle
transition writes the channel **and** emits in the same function.
Tests must assert this co-location (a state-channel write without an
emit, or vice versa, is a bug).

### F3 — DeepAgents 0.5.3 AsyncSubAgent context payload contract (verify during implementation)

DDR-007 §Consequences flags this as a verification step. The subagent's
context payload now carries a non-serialisable Python object (the
`PipelineLifecycleEmitter`). ASGI co-deployment per ADR-ARCH-031 is
the explicit transport choice precisely so in-process objects can be
passed — but the contract should be confirmed during the autobuild_runner
implementation task before downstream tasks depend on the shape.

**Mitigation:** Task TASK-FW10-002 (autobuild_runner subagent module)
includes an explicit acceptance criterion that a smoke test instantiates
the subagent with a real `PipelineLifecycleEmitter` in its context and
calls one transition. If 0.5.3 rejects the non-serialisable context,
the recovery path is the thin RPC-shaped emitter from DDR-007 §Forward
compatibility (one-line constructor swap at `_serve_deps`).

### F4 — Five Protocol-impl bindings have ambiguous owning module (DESIGN)

The four collaborators on `dispatch_autobuild_async`
(`forward_context_builder`, `async_task_starter`, `stage_log_recorder`,
`state_channel`) plus the `is_duplicate_terminal` reader and
`publish_build_failed` binder for `PipelineConsumerDeps` need
production constructors. They could live in a single `_serve_deps.py`
factory or in separate modules. **Single-module per Context A's
preference for "five separate tasks in one wave"** — but to avoid
file-merge conflicts when five tasks are running in parallel, each
binding gets its own private module (`_serve_deps_*.py`) and they're
composed in `_serve_deps.py` in Wave 3.

### F5 — `PipelinePublisher` already exists and is testable; its production constructor is the only missing piece (LOW risk)

The class itself is fine. The factory just needs `client` (the daemon's
NATS client). One line at `_serve_deps`. This is a low-risk component
to land in Wave 2.

### F6 — Healthz extension is a small but real surface (MEDIUM)

ASSUM-012 extends FEAT-FORGE-009's healthz contract: healthy iff NATS
subscription is live AND the orchestrator chain is fully constructed.
This means healthz must read a "chain ready" flag set after Wave 1's
construction completes. The Scenario Outline in Group E specifies
three states: not-yet-constructed → unhealthy; fully-constructed +
consumer-attached → healthy; constructed but NATS dropped → unhealthy.
This needs a small bool flag in `_serve_state` (or similar) and a
read in `_serve_healthz`.

### F7 — End-to-end test must run without actually invoking real autobuild (DESIGN)

The E2E test asserts the lifecycle envelope sequence. It should mock
`AutobuildDispatcher` at the boundary so the test doesn't actually
run an autobuild (which would take real time and require a real
worktree). The supervisor's reasoning model can be stubbed too —
this is a wiring test, not a Mode A behaviour test (Mode A behaviour
is FEAT-FORGE-007's territory).

---

## 5. Task Decomposition (recommended)

Per Context A: five separate tasks for the autobuild_runner subagent
+ its four collaborators, in one wave; standard testing depth with
seam tests at boundaries.

### Wave 1 — Seam refactor + recovery wiring (foundation)

**TASK-FW10-001** — Refactor `_serve_daemon` seam to `(_MsgLike) -> None`,
set `max_ack_pending=1`, defer ack to state machine, wire paired
`reconcile_on_boot` calls into `_run_serve`. (complexity 6)

**Files modified:**
- `src/forge/cli/_serve_daemon.py` — DispatchFn signature change,
  remove post-dispatch ack, add max_ack_pending=1.
- `src/forge/cli/serve.py` — `_run_serve` opens NATS once; runs both
  reconcile routines before consumer attach; passes client downstream.
- `src/forge/cli/_serve_state.py` — adds `chain_ready` flag for healthz.
- `src/forge/cli/_serve_healthz.py` — extends healthy gate to chain_ready.
- `tests/cli/test_serve_daemon.py` (existing) — migrate seam tests.
- `tests/cli/test_serve_*.py` — add chain_ready healthz tests.

**Why solo wave:** every later task depends on the new seam contract
and the single shared NATS client. Parallelising would create
merge conflicts on `serve.py`.

### Wave 2 — Five net-new components (parallel)

**TASK-FW10-002** — Implement `autobuild_runner` AsyncSubAgent module
with DDR-006 `_update_state` extended per DDR-007. (complexity 8)
- Creates: `src/forge/subagents/__init__.py`,
  `src/forge/subagents/autobuild_runner.py`.
- Registers in `langgraph.json` as a second graph entry.
- Implements `_update_state(state, *, lifecycle, emitter, ...)` with
  state-channel write + `emitter.on_transition(new_state)` co-located.
- Emits `target_kind="subagent"`, `target_identifier=task_id` for
  autobuild-internal transitions (ASSUM-018).
- Smoke test: instantiate with real `PipelineLifecycleEmitter`,
  exercise one transition, verify both writes happen (F2 + F3).

**TASK-FW10-003** — `ForwardContextBuilder` production factory
(`build_forward_context_builder` in `src/forge/cli/_serve_deps_forward_context.py`).
(complexity 4)
- Wires SQLite reader (`forge.lifecycle.persistence`) + worktree
  allowlist (`forge_config.allowed_worktree_paths`).
- Unit tests: factory returns a builder that round-trips against a
  fixture SQLite DB.

**TASK-FW10-004** — `StageLogRecorder` production binding
(`build_stage_log_recorder` in `src/forge/cli/_serve_deps_stage_log.py`).
(complexity 3)
- Wires `forge.lifecycle.persistence`'s SQLite writer behind the
  Protocol.
- Unit tests: writer records a transition that the reader observes.

**TASK-FW10-005** — `AutobuildStateInitialiser` production binding
(`build_autobuild_state_initialiser` in
`src/forge/cli/_serve_deps_state_channel.py`). (complexity 4)
- Wires `forge.lifecycle.persistence`'s `async_tasks` channel writer.
- Unit tests: initial-state write + subsequent reads via the channel.

**TASK-FW10-006** — `PipelinePublisher` + `PipelineLifecycleEmitter`
production constructors (`build_publisher_and_emitter` in
`src/forge/cli/_serve_deps_lifecycle.py`). (complexity 3)
- Both bound to the daemon's single shared client.
- Emitter's `on_transition(new_state)` dispatches to the eight
  `emit_*` methods based on `lifecycle` literal.
- Unit tests: emitter dispatch matrix (one test per lifecycle literal).

**Why one wave:** each task creates its own module; no merge
conflicts. All depend on Wave 1's `(_MsgLike) -> None` seam being
in place. None depend on each other.

### Wave 3 — Composition (`_serve_deps` factory + supervisor wiring)

**TASK-FW10-007** — Compose Wave 2 modules into the production
`PipelineConsumerDeps` factory and the dispatcher closure.
(complexity 6)
- Creates: `src/forge/cli/_serve_deps.py` —
  `build_pipeline_consumer_deps(client, forge_config, sqlite_pool)`.
- Creates: `src/forge/cli/_serve_dispatcher.py` —
  `make_handle_message_dispatcher(deps)` returning an
  `async def dispatch(msg: _MsgLike) -> None` closure that calls
  `pipeline_consumer.handle_message(msg, deps)`.
- Wires the dispatcher into `_serve_daemon.dispatch_payload` from
  `_run_serve` so the receipt-only `_default_dispatch` is no longer
  reachable.
- `Supervisor` constructed against the composed deps + reasoning model.

**TASK-FW10-008** — Wire `AsyncSubAgentMiddleware` into the supervisor's
reasoning loop. (complexity 5)
- Adds the middleware's start/check/update/cancel/list tools to the
  supervisor's tool list.
- Threads the `PipelineLifecycleEmitter` into `dispatch_autobuild_async`'s
  context payload per DDR-007.
- Verifies the supervisor stays responsive while autobuild is in
  flight (Group A scenario "supervisor stays responsive").

### Wave 4 — Validation, gating, and end-to-end proof

**TASK-FW10-009** — Validation surface (malformed payload, duplicate
detection, worktree allowlist) emitting `build-failed` and acking.
(complexity 4)
- Implements ASSUM-013, ASSUM-014, ASSUM-015 paths on the
  `pipeline_consumer.handle_message` boundary.
- Unit tests for each validation rejection path.

**TASK-FW10-010** — Pause/resume publish round-trip. (complexity 3)
- `emit_build_paused` at the `lifecycle="awaiting_approval"` transition
  in `_update_state`.
- `emit_build_resumed` in `forge.adapters.nats.approval_subscriber`'s
  resume path.
- Integration test: pause → restart → re-emit pause + approval-request →
  resume on approval.

**TASK-FW10-011** — End-to-end lifecycle integration test
(build-queued → terminal envelope, all eight subjects covered).
(complexity 6)
- New test file: `tests/integration/test_forge_serve_orchestrator_e2e.py`.
- Spins up forge serve against an embedded NATS + a temporary SQLite.
- Mocks `AutobuildDispatcher` at the boundary (F7).
- Asserts: build-started precedes any stage-complete; every stage-complete
  carries the inbound correlation_id; terminal envelope appears exactly
  once; `target_kind="subagent"` for autobuild-internal stages.

---

## 6. Wave Plan (parallel groups)

```
Wave 1: [TASK-FW10-001]                                              (1 task,  serial)
Wave 2: [TASK-FW10-002, FW10-003, FW10-004, FW10-005, FW10-006]      (5 tasks, parallel)
Wave 3: [TASK-FW10-007, TASK-FW10-008]                               (2 tasks, parallel)
Wave 4: [TASK-FW10-009, TASK-FW10-010, TASK-FW10-011]                (3 tasks, parallel)
```

**Total tasks:** 11.
**Aggregate complexity:** 52 / 110.
**Estimated duration (parallel):** ~12–15 working hours; serial ~25 hours.

---

## 7. Cross-task Integration Contracts (§4 candidates)

Several Wave 2 → Wave 3 → Wave 4 boundaries pass typed Python objects
between tasks. The most load-bearing are:

| Producer | Consumer | Artifact | Format constraint |
|---|---|---|---|
| TASK-FW10-002 (autobuild_runner) | TASK-FW10-008 (supervisor wiring) | `AUTOBUILD_RUNNER_GRAPH` (langgraph entry name) | Constant string `"autobuild_runner"` registered in `langgraph.json`; supervisor references it via `AUTOBUILD_RUNNER_NAME`. |
| TASK-FW10-006 (publisher + emitter) | TASK-FW10-002 (autobuild_runner) | `PipelineLifecycleEmitter` instance | Threaded into `dispatch_autobuild_async` context payload per DDR-007. Subagent calls `emitter.on_transition(new_state)` from `_update_state`. |
| TASK-FW10-003/004/005/006 (Wave 2 factories) | TASK-FW10-007 (deps composer) | Four Protocol implementations + `PipelinePublisher` + `PipelineLifecycleEmitter` | Each factory returns a Protocol-conforming object; `_serve_deps.build_pipeline_consumer_deps` composes them into `PipelineConsumerDeps`. |
| TASK-FW10-001 (seam refactor) | TASK-FW10-007 (dispatcher wiring) | New `DispatchFn` type alias `Callable[[_MsgLike], Awaitable[None]]` | `_serve_dispatcher.make_handle_message_dispatcher` returns this signature; `_run_serve` rebinds `_serve_daemon.dispatch_payload` to it. |
| TASK-FW10-006 (emitter) | TASK-FW10-010 (pause/resume) | `emit_build_paused` / `emit_build_resumed` methods | Already on the emitter class; no new shape. Pause/resume is a call-site addition only. |

These will be made explicit in IMPLEMENTATION-GUIDE.md §4: Integration
Contracts.

---

## 8. Recommendations

1. **Adopt the 4-wave plan above.** Wave 1 lands the foundation; Wave 2
   parallelises the five net-new components; Wave 3 composes; Wave 4
   validates end-to-end.
2. **Verify the DeepAgents 0.5.3 AsyncSubAgent context contract early
   (TASK-FW10-002).** If non-serialisable context payload is rejected,
   pivot to DDR-007's HTTP-shaped emitter wrapper before further tasks
   depend on the in-process shape.
3. **Wire both `reconcile_on_boot` routines synchronously before the
   consumer's first fetch (TASK-FW10-001).** Failing to do so reopens
   F1 and breaks crash-recovery scenarios in Group D.
4. **Keep the `_update_state` boundary as the single canonical
   transition site (TASK-FW10-002).** Test for co-located write + emit.
5. **Drop the synthetic dispatch-stage envelope from FRR-001
   completely.** Per ASSUM-004; carried via Group A scenario "no
   synthetic stub" assertion in TASK-FW10-011.
6. **Land each Wave 2 binding in its own private module
   (`_serve_deps_*.py`)** to avoid five tasks colliding on `_serve_deps.py`.
7. **Mock `AutobuildDispatcher` at the boundary in the E2E test
   (TASK-FW10-011).** This is a wiring test, not a Mode A test.
8. **Operational note: existing `forge-serve` durable must be
   `nats consumer rm`-ed before deploying the new image** (the
   `max_ack_pending=1` change is not editable on a live consumer).
   Capture in TASK-FW10-001's deployment notes.
9. **Pause/resume publish stays in scope (Context A: in_scope_per_DDR_007).**
   If TASK-FW10-010 discovers a structural blocker (e.g., the approval
   subscriber needs reshaping), file a carve-out at that point — but
   the default position is to keep it in scope.
10. **Standard testing depth with seam tests (Context A).** Each Wave 2
    binding has its own unit tests; cross-task contracts in §4 each
    get a seam test stub in the consumer task; one E2E integration
    test covers the full lifecycle (TASK-FW10-011).
11. **Lint compliance is an acceptance criterion of every implementation
    task** (per /feature-plan policy).

---

## 9. Decision Checkpoint

**Recommended approach:** Land the full 11-task, 4-wave plan against
DDR-007 / Option A. No carve-outs.

**Rationale:** The architecture is settled. The risks (F1, F3) are
addressable in-task with explicit mitigations. The scope split that
would otherwise be tempting (pause/resume to a follow-up) is
explicitly closed by DDR-007 §Decision and §Do-not-reopen.

The decision options follow.
