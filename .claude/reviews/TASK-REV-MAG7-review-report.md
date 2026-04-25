# Review Report: TASK-REV-MAG7 — Plan Mode A Greenfield End-to-End

**Feature**: FEAT-FORGE-007 — Mode A Greenfield End-to-End
**Mode**: Decision
**Depth**: Standard
**Generated**: 2026-04-25
**Reviewer**: /task-review (decision mode)

---

## Executive Summary

FEAT-FORGE-007 is the **capstone composition feature** for Forge. It introduces no
new transitions, transports, or gate modes — every primitive it relies on is
already specified in FEAT-FORGE-001 through FEAT-FORGE-006. The work is therefore
*purely orchestration*: ordering the eight stage classes correctly, threading
each stage's approved output forward into the next stage's dispatch context,
launching autobuild as an `AsyncSubAgent` so the supervisor stays responsive, and
ensuring that the constitutional pull-request rule and the crash-recovery
contract remain honoured.

The recommended approach is **Option 1: Reasoning-loop-driven dispatch with a
deterministic ordering guard**. A small `StageOrderingGuard` deterministic
validator enforces the seven-prerequisite invariant (Group B Scenario Outline);
the LangGraph supervisor's reasoning model decides *when* to dispatch the next
permitted stage, given recorded history and the live state channel. This
preserves the LangGraph supervisor pattern already used elsewhere in Forge while
making the constitutional invariants impossible to bypass through prompt drift.

The plan decomposes into **14 tasks across 5 waves**, with the longest critical
path bounded by the wave dependency graph rather than by serial enumeration.
Estimated total effort: ~12–16 hours of focused implementation, dominated by the
end-to-end concurrency and crash-recovery integration tests in Wave 5.

---

## Review Scope (Context A captured at /feature-plan)

- **Focus**: All — full sweep across architecture, technical, performance, security
- **Trade-off priority**: Balanced
- **Specific concerns**: None pre-flagged — surfaced organically below

---

## Knowledge Graph Context Used

- **Mode A entity** (`forge__project_decisions`): confirms eight stage chain
  driven via GuardKit slash commands, history files as calibration data
- **`autobuild_runner` HAS_STATE_CHANNEL `async_tasks`** — DeepAgents AsyncSubAgent
  with `check_async_task` / `update_async_task` middleware tools
- **ADR-ARCH-026** (Constitutional Rules enforced at two layers): system prompt
  GUARDRAILS section + executor assertions in `pr_finaliser`
- **DDR-006** (Async subagent state-channel contract): `AutobuildState` Pydantic
  shape with `lifecycle`, `wave_index`, `task_index`, `waiting_for`, `pending_directives`
- **ADR-ARCH-031** (Async subagents for long-running work) — autobuild_runner
  launched via `start_async_task`
- **Existing code** (`src/forge/pipeline.py`): `PipelineLifecycleEmitter` already
  threads correlation_id, publishes paused-then-interrupt ordering, swallows
  `PublishFailure` after SQLite commit (Group D / Group G already covered at the
  emitter level)

---

## Substrate Inventory — What Already Exists

| Substrate | Owned by | Status |
|-----------|----------|--------|
| Build state machine (queued/preparing/running/paused/terminal) | FEAT-FORGE-001 | Specified |
| SQLite history (`stage_log`, `build_state`) — authoritative | FEAT-FORGE-001 | Specified |
| Crash recovery — retry-from-scratch | FEAT-FORGE-001 | Specified |
| CLI steering (`forge cancel`, `forge skip`) | FEAT-FORGE-001/004 | Specified |
| Pipeline event publish (started/progress/stage-complete/paused/resumed/complete) | FEAT-FORGE-002 | **Implemented** (`PipelineLifecycleEmitter`) |
| Build queue subscription (terminal-ack, dedupe, allowlist refusal) | FEAT-FORGE-002 | Specified |
| Discovery cache (30s TTL) + degraded-mode fallback | FEAT-FORGE-002 | Specified |
| Specialist dispatch (capability resolution, retry-with-context) | FEAT-FORGE-003 | Specified |
| Confidence-gated checkpoint protocol (4 modes) | FEAT-FORGE-004 | Specified |
| Build-keyed approval channel + first-wins idempotency | FEAT-FORGE-004 | Specified |
| Belt-and-braces PR-review enforcement | FEAT-FORGE-004 | Specified (executor + prompt) |
| GuardKit subprocess engine (`/system-arch`, `/system-design`, `/feature-spec`, `/feature-plan`, autobuild) | FEAT-FORGE-005 | Specified |
| Worktree allowlist confinement | FEAT-FORGE-005 | Specified |
| Long-term memory seeding + priors retrieval | FEAT-FORGE-006 | Specified |
| Calibration priors (snapshot at build start) | FEAT-FORGE-006 | Specified |
| `git`/`gh` PR creation adapter | FEAT-FORGE-006 | Specified |

**Net new in FEAT-FORGE-007**: the supervisor's reasoning loop wiring + the
stage-ordering guard + the per-stage forward-propagation context-builder.

---

## Technical Options Analysis

### Option 1: Reasoning-Loop-Driven Dispatch with Ordering Guard ⭐ Recommended

**Pattern**: LangGraph supervisor's reasoning model selects the next stage to
dispatch on each turn; a deterministic `StageOrderingGuard` (Pydantic validator
+ pure function) refuses any dispatch whose prerequisites are not all
recorded-as-approved in SQLite. The guard also encodes the constitutional
PR-review rule (refuses skip, refuses auto-approve at executor layer).

**Complexity**: 7/10
**Effort**: 12–16 hours
**Pros**:
- Aligns with the existing DeepAgents supervisor topology (`create_orchestrator`,
  reasoning model + implementation model)
- Guard is a pure function over `stage_log` rows — trivially unit-testable, no
  async, no flakiness
- Reasoning loop stays small: it asks "what's next?" and the guard answers
  "you can dispatch X, Y, but not Z" — the LLM picks one
- Supervisor responsiveness during autobuild is automatic: the reasoning loop
  is not blocked because `autobuild_runner` is an `AsyncSubAgent` (DDR-006)
- Constitutional invariants are enforced at executor layer (the guard)
  *independently* of prompt content — ADR-ARCH-026 belt-and-braces holds
- All 47 scenarios map cleanly onto guard predicates + reasoning-loop choices

**Cons**:
- Reasoning model still needs a clear system-prompt section enumerating the
  eight stages and their inputs (forward-propagation hints) — prompt + guard
  must agree on the stage taxonomy
- Per-feature inner-loop sequencing (ASSUM-006) requires a guard predicate that
  sees "is any autobuild for this build still non-terminal?" — slightly subtle
  but well-bounded

**Dependencies**: Substrate features 1–6 must be at parity with their specs
(none need extension).

---

### Option 2: State-Machine-Driven Dispatch (Deterministic FSM)

**Pattern**: A pure FSM with explicit transitions for all eight stages drives
dispatch sequentially; the reasoning model is reduced to a "should I retry,
escalate, or proceed" oracle at gate decisions.

**Complexity**: 5/10 (simpler control flow)
**Effort**: 8–12 hours
**Pros**:
- Fully deterministic dispatch order — easier to reason about
- No reasoning-model variance affects sequencing
- Easier crash-recovery: the FSM resumes at "the next state SQLite says is
  pending"

**Cons**:
- **Misaligns with the established Forge topology.** Forge already uses a
  reasoning-loop supervisor (`create_orchestrator` + DeepAgents). A second FSM
  duplicates state.
- Removes the supervisor's ability to make holistic mid-flight decisions
  (e.g. "the architect returned a degraded result — should we retry with
  additional context?" — that's a reasoning question, not an FSM transition)
- Group D edge cases (mid-flight steering, idempotent duplicate, asynchronous
  pause observability) become awkward to wire because the FSM must own all
  of them; with Option 1 they live naturally on the supervisor
- Doesn't compose well with FEAT-FORGE-003's reasoning-model-driven retry

---

### Option 3: Hybrid (Static FSM Guard + Reasoning Loop for Choice)

**Pattern**: Pre-compute the eight-stage DAG as a static graph; the reasoning
loop traverses it but each transition is a guarded edge.

**Complexity**: 6/10
**Effort**: 10–14 hours
**Pros**:
- Combines the determinism of Option 2 with the flexibility of Option 1
- The DAG is human-readable and serves as documentation

**Cons**:
- The DAG is **already** the seven prerequisite rows in the Group B Scenario
  Outline — encoding it as a graph object is over-engineering
- Adds a new abstraction (`StageDAG`) with no runtime payoff over Option 1's
  pure-function guard
- Per-feature loop fan-out is awkward — a single static DAG doesn't naturally
  express N parallel feature-specs collapsing into N sequential autobuilds
- Risk of drift between the DAG-as-data and the seven-prerequisite Scenario
  Outline (two sources of truth)

---

## Recommended Approach — Option 1 in Detail

```
┌─────────────────────────────────────────────────────────────────┐
│                  Forge Supervisor (LangGraph)                    │
│                                                                  │
│  ┌────────────────┐   asks   ┌────────────────────────┐         │
│  │ Reasoning loop │──────────>│ StageOrderingGuard      │         │
│  │ (gemini-3.1)   │<──────────│ (pure fn over SQLite)   │         │
│  └────────────────┘  permits  └────────────────────────┘         │
│         │                                                        │
│         │ dispatches                                             │
│         ▼                                                        │
│  ┌──────────────────────────────────────────────────┐           │
│  │  Stage dispatchers (one per stage class)          │           │
│  │   - product_owner, architect (FEAT-FORGE-003)     │           │
│  │   - system_arch, system_design (FEAT-FORGE-005)   │           │
│  │   - feature_spec, feature_plan (FEAT-FORGE-005)   │           │
│  │   - autobuild  (AsyncSubAgent, FEAT-FORGE-005)    │           │
│  │   - pull_request_review (constitutional)          │           │
│  └──────────────────────────────────────────────────┘           │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────────────────────────────────────┐           │
│  │  Forward-Propagation Context Builder              │           │
│  │  (per stage: read prior stage's artefact paths    │           │
│  │   from stage_log, assemble --context flags)       │           │
│  └──────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼ (writes durable history)
  ┌──────────────────────────┐
  │  SQLite stage_log        │ ← authoritative source on recovery
  │  (FEAT-FORGE-001)        │
  └──────────────────────────┘
```

**Stage taxonomy** (pinned by ASSUM-001, all eight stage classes):

| # | Stage | Constitutional? | Implementation owner | Dispatch shape |
|---|-------|----------------|---------------------|----------------|
| 1 | `product_owner` | No | FEAT-FORGE-003 | Capability dispatch (sync via `await`) |
| 2 | `architect` | No | FEAT-FORGE-003 | Capability dispatch (sync via `await`) |
| 3 | `system_arch` | No | FEAT-FORGE-005 | Subprocess (sync) |
| 4 | `system_design` | No | FEAT-FORGE-005 | Subprocess (sync) |
| 5 | `feature_spec` (×N) | No | FEAT-FORGE-005 | Subprocess (sync), per-feature |
| 6 | `feature_plan` (×N) | No | FEAT-FORGE-005 | Subprocess (sync), per-feature |
| 7 | `autobuild` (×N) | No | FEAT-FORGE-005 + DDR-006 | **AsyncSubAgent** (`start_async_task`) |
| 8 | `pull_request_review` (×N) | **Yes** (mandatory human) | FEAT-FORGE-004/006 | Gate + executor assertion |

**Forward-propagation contract** (per stage transition):

| Producer | Consumer | Artefact threaded |
|----------|----------|-------------------|
| product-owner | architect | approved charter (text) |
| architect | system-arch | architect approved output |
| system-arch | system-design | architecture artefact paths |
| system-design | feature-spec (×N) | feature catalogue entry per N |
| feature-spec | feature-plan | feature spec artefact path for that feature |
| feature-plan | autobuild | approved build plan path for that feature |
| autobuild | pull-request | branch ref + commit summary |

---

## Subtask Breakdown — 14 Tasks Across 5 Waves

### Wave 1 — Foundations (parallel)

| ID | Task | task_type | Complexity | Effort |
|----|------|-----------|-----------:|-------:|
| TASK-MAG7-001 | Define `StageClass` enum + `StagePrerequisite` table (eight stages, seven prerequisite rows from Group B Scenario Outline) | declarative | 2 | 30m |
| TASK-MAG7-002 | Define `ForwardPropagationContract` map (producer → consumer artefact handshake, seven rows) | declarative | 2 | 30m |

### Wave 2 — Core Guards (depends on Wave 1)

| ID | Task | task_type | Complexity | Effort |
|----|------|-----------|-----------:|-------:|
| TASK-MAG7-003 | Implement `StageOrderingGuard.next_dispatchable(build_id)` — pure fn over `stage_log` rows; covers Group B prerequisite Scenario Outline | feature | 5 | 90m |
| TASK-MAG7-004 | Implement `ConstitutionalGuard.veto_if_pr_review(stage, mode)` — executor-layer refusal of auto-approve and skip on PR-review (Groups C/E) | feature | 4 | 60m |
| TASK-MAG7-005 | Implement `PerFeatureLoopSequencer.may_start_autobuild(build_id, feature_id)` — refuses second autobuild while first is non-terminal (Group D ASSUM-006) | feature | 4 | 60m |

### Wave 3 — Stage Dispatchers + Context Builder (depends on Wave 2)

| ID | Task | task_type | Complexity | Effort |
|----|------|-----------|-----------:|-------:|
| TASK-MAG7-006 | Implement `ForwardContextBuilder.build_for(stage, build_id)` — assembles `--context` flags from prior stage artefact paths in `stage_log` | feature | 5 | 90m |
| TASK-MAG7-007 | Wire `dispatch_specialist_stage` (product-owner, architect) — composes FEAT-FORGE-003 capability dispatch with `ForwardContextBuilder` | feature | 4 | 75m |
| TASK-MAG7-008 | Wire `dispatch_subprocess_stage` (system-arch, system-design, feature-spec, feature-plan) — composes FEAT-FORGE-005 subprocess engine with `ForwardContextBuilder`, threads correlation_id | feature | 5 | 90m |
| TASK-MAG7-009 | Wire `dispatch_autobuild_async` — uses `start_async_task` from DDR-006, returns task_id; registers on supervisor `async_tasks` channel | feature | 6 | 120m |

### Wave 4 — Supervisor Reasoning Loop (depends on Wave 3)

| ID | Task | task_type | Complexity | Effort |
|----|------|-----------|-----------:|-------:|
| TASK-MAG7-010 | Wire `Supervisor.next_turn(build_id)` — reads guard, calls reasoning model with permitted dispatches, executes chosen dispatch; covers Group A key examples + Group F concurrency | feature | 7 | 150m |
| TASK-MAG7-011 | Wire CLI steering injection (`forge cancel` → synthetic reject, `forge skip` → synthetic override; PR-review skip refusal); covers Group D edge cases | feature | 5 | 90m |

### Wave 5 — Integration Tests + Smoke (depends on Wave 4)

| ID | Task | task_type | Complexity | Effort |
|----|------|-----------|-----------:|-------:|
| TASK-MAG7-012 | Smoke test — minimal one-line greenfield brief drives single-feature run to PR-awaiting-review (Group H @smoke @integration) | testing | 5 | 90m |
| TASK-MAG7-013 | Crash-recovery integration tests — Group D Scenario Outline (seven stage classes), durable history vs advisory state channel | testing | 6 | 120m |
| TASK-MAG7-014 | Concurrency + multi-feature integration tests — Group F (two concurrent builds), Group H multi-feature, ASSUM-006 sequencing, Group I expansion (correlation threading, calibration snapshot, first-wins) | testing | 7 | 150m |

**Total estimate**: 14 tasks, ~12–16 hours focused implementation.

---

## Risk Register

| ID | Risk | Severity | Likelihood | Mitigation |
|----|------|----------|-----------|------------|
| R-1 | Reasoning model dispatches a stage out of order despite guard refusal | **High** | Low | Guard returns *only the permitted set*; supervisor refuses to act on a non-permitted choice; integration test asserts on Scenario Outline of seven prerequisites |
| R-2 | `AsyncSubAgent` crash mid-autobuild leaves SQLite "running" but state-channel "completed" or vice versa | **High** | Medium | DDR-006 + ASSUM-004 already specify SQLite as authoritative on recovery. Wave 5 crash-recovery tests cover all seven non-terminal stages |
| R-3 | Per-feature loop dispatches second autobuild before first reaches terminal lifecycle | **Medium** | Medium | `PerFeatureLoopSequencer` (TASK-MAG7-005); explicit @edge-case test in Group D |
| R-4 | Constitutional belt-and-braces drift — prompt allows auto-approve at PR-review while executor still refuses | Medium | Low (addressed) | ADR-ARCH-026 wired both layers; `ConstitutionalGuard.veto_if_pr_review` is the executor side. Group E security scenarios test the executor with a deliberately-misconfigured prompt |
| R-5 | Forward-propagation context builder leaks unapproved or stale artefacts | **High** | Low | `ForwardContextBuilder` reads only stage entries with `gate_decision='approved'` from `stage_log`; @data-integrity tests assert on artefact-path attribution |
| R-6 | Concurrent builds collide on supervisor reasoning loop or approval channel | Medium | Low | FEAT-FORGE-002 uses build-keyed channels; FEAT-FORGE-004 is build-keyed approval; Group F concurrency test asserts isolation |
| R-7 | First-wins idempotency violated — duplicate approval response causes second resume | Medium | Low (addressed) | FEAT-FORGE-004 ASSUM-006 already specifies; Group D + Group I @concurrency tests |
| R-8 | Calibration-priors snapshot drift mid-build | Low | Medium | Snapshot at `build_picked_up`; pass via dependency injection; Group I @data-integrity test |
| R-9 | Notification publish failure silently regresses approval | Low | Low (addressed) | Existing `PipelineLifecycleEmitter` swallows `PublishFailure` after SQLite commit; Group G + Group I @data-integrity tests cover |
| R-10 | Worktree confinement bypass during subprocess stage | High | Low (inherited) | FEAT-FORGE-005 owns DeepAgents permissions; Group E @security test re-asserts at composition layer |

---

## Integration Contracts (cross-task)

### Contract: stage_taxonomy
- **Producer task**: TASK-MAG7-001
- **Consumer tasks**: TASK-MAG7-003, TASK-MAG7-005, TASK-MAG7-007, TASK-MAG7-008
- **Artefact**: Python module `forge.pipeline.stage_taxonomy` exporting `StageClass` enum + `STAGE_PREREQUISITES: dict[StageClass, list[StageClass]]`
- **Format constraint**: enum members ordered exactly as in ASSUM-001; dict matches the seven Scenario-Outline prerequisite rows verbatim
- **Validation**: Coach asserts `len(STAGE_PREREQUISITES) == 7` and key set equals `{architect, system_arch, system_design, feature_spec, feature_plan, autobuild, pull_request_review}`

### Contract: forward_propagation_map
- **Producer task**: TASK-MAG7-002
- **Consumer task**: TASK-MAG7-006
- **Artefact**: Python module `forge.pipeline.forward_propagation` exporting `PROPAGATION_CONTRACT: dict[StageClass, ContextRecipe]`
- **Format constraint**: every non-product-owner stage class has exactly one entry; recipe references `stage_log` artefact_path columns by name
- **Validation**: Coach asserts every key in `PROPAGATION_CONTRACT` is reachable from `product_owner` via `STAGE_PREREQUISITES`

### Contract: autobuild_async_task_id
- **Producer task**: TASK-MAG7-009
- **Consumer task**: TASK-MAG7-010 (supervisor) + TASK-MAG7-011 (CLI steering)
- **Artefact**: `task_id: str` returned from `start_async_task`, registered on `async_tasks` state channel
- **Format constraint**: matches DDR-006 `AutobuildState.task_id` shape; per-feature unique within a build
- **Validation**: Coach asserts `dispatch_autobuild_async` returns the same `task_id` that `list_async_tasks` later reports

---

## Test Strategy

**Unit (Waves 1–4)**:
- Pure-function tests on `StageOrderingGuard` (covers Group B Scenario Outline directly)
- Pure-function tests on `ConstitutionalGuard` (covers Group C @negative + Group E @security)
- Pure-function tests on `PerFeatureLoopSequencer`
- Mocked-substrate tests on each dispatcher (Wave 3) — substrate features mocked via FEAT-FORGE-003/005 contract surfaces

**Integration (Wave 5)**:
- Smoke: Group H @smoke @integration — end-to-end with real subprocess invocation against fixture GuardKit responses
- Crash recovery: Group D Scenario Outline — `pytest.fixture` that kills the supervisor at each of seven stages, asserts retry-from-scratch
- Concurrency: Group F + Group I @concurrency — two builds, asserts channel isolation, first-wins
- Multi-feature: Group H — three-feature catalogue, asserts one autobuild + one PR-review per feature, ASSUM-006 sequencing
- Constitutional: Group E @security @regression — deliberately misconfigured prompt, asserts executor still refuses

**Determinism**: All async tests use `FakeClock` (already used by existing
`PipelineLifecycleEmitter` per `src/forge/pipeline.py`); approval round-trips
use a stub `ApprovalChannel` driven by the test thread.

---

## Disconnection Audit

This is the read/write path map for FEAT-FORGE-007's net-new code:

```
Writes:                           Storage:                    Reads:
─────────                         ────────                    ──────
Stage dispatchers ───approved───> stage_log (SQLite)  ───────> StageOrderingGuard.next_dispatchable
                                                      ──────-> ForwardContextBuilder.build_for
                                                      ──────-> CLI forge history

Supervisor turn  ───decided────-> reasoning_history          ──> CLI forge status (advisory)
                                  (LangGraph state ch.)

dispatch_autobuild_async ──tid──> async_tasks (state ch.) ──-> Supervisor.next_turn (advisory)
                                                          ───-> CLI forge status (advisory)
                                                          ───-> CLI cancel/steering

ConstitutionalGuard ───veto────-> (in-memory return value)  ──> Supervisor.next_turn (gate)
                                                          ───-> approval response handler (gate)
```

**No disconnected paths.** Every write path has a corresponding read path
within FEAT-FORGE-007 or one of its consumers (CLI status, history, cancel
handler, approval handler).

---

## Decision

✅ **Recommended**: Option 1 — Reasoning-Loop-Driven Dispatch with Ordering Guard

The recommendation aligns with:
- The existing Forge supervisor topology (`create_orchestrator`, two-model)
- ADR-ARCH-026 belt-and-braces (executor + prompt) for constitutional rules
- DDR-006 async-subagent contract (already a load-bearing decision)
- The FEAT-FORGE-001..006 substrate without requiring any extension

Net-new code is small (~14 tasks, ~12–16 hours), well-bounded, and dominated by
pure functions over SQLite history rows. The only async surface is
`dispatch_autobuild_async`, which is a thin wrapper over the already-specified
`start_async_task` middleware.

---

## Decision Checkpoint

Review complete. Found 3 technical approaches with **Option 1 recommended**.

What would you like to do?

- **[A]ccept** — Approve recommendation, save review for reference, do not create implementation tasks
- **[R]evise** — Request deeper analysis on a specific concern (concurrency, constitutional, async-subagent stability, etc.)
- **[I]mplement** — Create the 14-task feature structure across 5 waves, ready for `/feature-build`
- **[C]ancel** — Discard this plan
