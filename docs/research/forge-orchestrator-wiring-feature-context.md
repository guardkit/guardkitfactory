# `--context` Evaluation for `/feature-spec` + `/feature-plan`

**Companion to**: `docs/research/forge-orchestrator-wiring-gap.md`
**Purpose**: Identify which existing documents to inject into
`/feature-spec` and `/feature-plan` via `--context` arguments so the
generated spec and plan are anchored in the existing architecture
rather than re-inventing it.

---

## Principles applied

1. **Spec inputs differ from plan inputs.** `/feature-spec` produces
   Gherkin scenarios from intent + constraints. `/feature-plan`
   produces a task decomposition from a spec + implementation context.
   Their `--context` sets overlap but are not identical.

2. **Heaviest weight goes to the documents that already contain the
   contract or behaviour.** `API-nats-pipeline-events.md` and
   `mode-a-greenfield-end-to-end.feature` are not background reading
   — they are the ground truth this feature wires into production. A
   spec that drifts from them is a bug.

3. **Source files matter when they hold un-instantiated Protocols.**
   The `Supervisor` dataclass and the `dispatch_autobuild_async`
   Protocols are de-facto specifications of what production
   construction must conform to. They go to `/feature-plan`, not
   `/feature-spec` (the Gherkin layer should describe behaviour, not
   class shapes).

4. **Tests are the executable spec of the dispatcher contracts.**
   Where Protocols leave room for interpretation, the tests pin them.
   Particularly relevant for the `AutobuildState` lifecycle
   transitions and the deferred-ack contract on `handle_message`.

5. **The findings doc is the bridge.** Both commands should receive
   `forge-orchestrator-wiring-gap.md` first — it carries the problem
   statement, the empirical chain, the constraints catalogue, and the
   proposed scope envelope.

---

## `/feature-spec --context=…`

The spec command needs **behavioural ground truth + constraints + a
problem statement**. It does not need source code.

### Tier 1 — must include (the spec will not be correct without these)

| Path | Why |
|---|---|
| `docs/research/forge-orchestrator-wiring-gap.md` | The findings doc — problem statement, scope envelope, what's wired vs not, evidence chain. The whole reason this feature exists. |
| `docs/design/contracts/API-nats-pipeline-events.md` | The eight `pipeline.{event}.{feature_id}` subjects + payload shapes are the public bus contract. The spec must describe scenarios where these envelopes are emitted in the right order with the right `correlation_id` threading. |
| `features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature` | **The orchestrator behaviour is already spec'd here for FEAT-FORGE-007.** This feature's job is to wire that behaviour into production. The new spec should not re-describe Mode A — it should describe the *production composition* scenarios that connect the Mode A spec to the daemon process. |
| `features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end_summary.md` | Quick orientation to the Mode A scope so the new spec stays at the integration layer. |
| `features/forge-production-image/forge-production-image.feature` | What FEAT-FORGE-009 actually shipped — the daemon process container. The new spec extends this scope into orchestration, so it must not contradict the daemon-process scenarios already specified. |

### Tier 2 — should include (constrains the spec's solution space)

| Path | Why |
|---|---|
| `docs/architecture/decisions/ADR-ARCH-014-single-consumer-max-ack-pending.md` | Sequential-build constraint — `max_ack_pending=1` on the durable. A spec scenario that asserts concurrent builds would violate this. |
| `docs/architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md` | The autobuild-as-AsyncSubAgent pattern. The spec should reference "the autobuild runs as an async subagent" without re-deciding it. |
| `docs/architecture/decisions/ADR-ARCH-021-paused-via-langgraph-interrupt.md` | The pause/resume + crash-recovery contract. References ADR-SP-013 (terminal-only ack) which is itself referenced widely but not present as a standalone file — the spec should observe the contract regardless. |
| `docs/architecture/decisions/ADR-ARCH-008-forge-produces-own-history.md` | SQLite is authoritative; NATS is a derived projection. Drives the "publish failure does not corrupt build state" scenarios. |
| `docs/architecture/decisions/ADR-ARCH-027-no-horizontal-scaling.md` | Single-process daemon assumption. Multi-replica is failover-only. Constrains the multi-replica work-queue scenarios. |
| `docs/design/decisions/DDR-006-async-subagent-state-channel-contract.md` | `AutobuildState.lifecycle` literals — `starting → planning_waves → running_wave → awaiting_approval → completed/failed/cancelled`. The spec's stage-transition scenarios reference these. |
| `docs/design/decisions/DDR-001-reply-subject-correlation.md` | Correlation-id threading rules — pin the round-trip scenarios. |
| `docs/architecture/assumptions.yaml` | The ASSUM-* registry. The spec should add to it (or reference it) rather than invent new assumptions. |

### Tier 3 — useful for completeness (clarifies the broader environment)

| Path | Why |
|---|---|
| `docs/architecture/ARCHITECTURE.md` | System overview — orients the spec to where this feature sits. |
| `docs/architecture/container.md` | Container boundaries — `forge serve` as one container, jarvis as another. |
| `docs/research/forge-pipeline-architecture.md` | Existing pipeline architecture writeup — same intent as this feature, may have prior art. |
| `docs/design/contracts/API-sqlite-schema.md` | SQLite schema contract — the `stage_log`, `async_tasks`, `builds` tables the orchestrator writes. |
| `docs/design/contracts/API-subagents.md` | Subagent contract — relevant for the `autobuild_runner` AsyncSubAgent the feature implements. |
| `docs/design/models/DM-build-lifecycle.md` | Build state machine — anchors the lifecycle scenarios. |
| `docs/design/models/DM-gating.md` | Gating model — for the constitutional-guard / PR-review-gate scenarios. |
| `tasks/in_progress/TASK-FORGE-FRR-001-wire-dispatch-payload-to-real-orchestrator.md` | The original symptom-anchored task — captures the runbook close-criterion phrasing the spec needs to satisfy. |
| `tasks/backlog/feat-jarvis-internal-001-followups/TASK-FORGE-FRR-001b-publish-pipeline-lifecycle-from-autobuild-orchestrator.md` | The per-stage publishing intent — the spec subsumes this. |
| `/home/richardwoollcott/Projects/appmilla_github/jarvis/docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md` | The empirical evidence — Phase 7 close criterion the spec must satisfy. |

### Explicitly excluded from `/feature-spec`

- **Source files (`src/forge/...`)** — these belong in `/feature-plan`. The spec should describe behaviour, not class shapes.
- **Test files (`tests/forge/...`)** — same reason. Tests document implementation contracts, not user-facing behaviour.
- **F009-internal task files (`tasks/completed/forge-production-image/TASK-F009-*.md`)** — too implementation-detail-heavy for the spec layer. Use the F009 feature file instead.
- **`docs/state/TASK-FORGE-FRR-001/implementation_plan.md`** — captures a planning artifact predicated on the wrong scope assumption. It's referenced in the findings doc as historical context; it should not directly steer the spec.

### Suggested invocation

```bash
/feature-spec "Wire the production pipeline orchestrator into forge serve" \
  --context=docs/research/forge-orchestrator-wiring-gap.md \
  --context=docs/design/contracts/API-nats-pipeline-events.md \
  --context=features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature \
  --context=features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end_summary.md \
  --context=features/forge-production-image/forge-production-image.feature \
  --context=docs/architecture/decisions/ADR-ARCH-014-single-consumer-max-ack-pending.md \
  --context=docs/architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md \
  --context=docs/architecture/decisions/ADR-ARCH-021-paused-via-langgraph-interrupt.md \
  --context=docs/architecture/decisions/ADR-ARCH-008-forge-produces-own-history.md \
  --context=docs/architecture/decisions/ADR-ARCH-027-no-horizontal-scaling.md \
  --context=docs/design/decisions/DDR-006-async-subagent-state-channel-contract.md \
  --context=docs/design/decisions/DDR-001-reply-subject-correlation.md \
  --context=docs/architecture/assumptions.yaml \
  --context=tasks/in_progress/TASK-FORGE-FRR-001-wire-dispatch-payload-to-real-orchestrator.md \
  --context=tasks/backlog/feat-jarvis-internal-001-followups/TASK-FORGE-FRR-001b-publish-pipeline-lifecycle-from-autobuild-orchestrator.md \
  --context=/home/richardwoollcott/Projects/appmilla_github/jarvis/docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md
```

(15 context files. If the command has a tighter context budget, drop
in this order: the FRR-001b task → the FRR-001 task → ADR-ARCH-027 →
ADR-ARCH-008 → DDR-001 → the F009 feature spec. The first five Tier 1
files plus the four highest-impact ADRs/DDRs are non-negotiable.)

---

## `/feature-plan --context=…`

The plan command needs **the spec output + implementation reality**.
It produces tasks with file-level scope, so it needs to see the source
files that hold the unwired components.

### Tier 1 — must include

| Path | Why |
|---|---|
| `features/<new-feature-slug>/<new-feature-slug>.feature` | **The output of `/feature-spec`.** The plan decomposes this into tasks. |
| `features/<new-feature-slug>/<new-feature-slug>_summary.md` | Quick orientation. |
| `features/<new-feature-slug>/<new-feature-slug>_assumptions.yaml` | Assumptions the plan must respect (or surface). |
| `docs/research/forge-orchestrator-wiring-gap.md` | The findings doc — the plan needs the same component inventory the spec was scoped against, plus the carry-forward references list. |
| `src/forge/pipeline/supervisor.py` | The `Supervisor` dataclass — the plan needs to see the 12+ injected fields to scope construction tasks correctly. |
| `src/forge/pipeline/dispatchers/autobuild_async.py` | `dispatch_autobuild_async` + its four Protocols — pins the autobuild-dispatch construction tasks. |
| `src/forge/adapters/nats/pipeline_consumer.py` | `PipelineConsumerDeps`, `handle_message`, `reconcile_on_boot`, the deferred-ack contract — pins the consumer-deps construction tasks and the daemon-side `_process_message` refactor. |
| `src/forge/adapters/nats/pipeline_publisher.py` | `PipelinePublisher` — pins the publisher construction task and the emitter-publishes-via-publisher chain. |
| `src/forge/pipeline/__init__.py` | `PipelineLifecycleEmitter` — pins the emitter construction + per-stage caller wiring tasks. |
| `src/forge/cli/_serve_daemon.py` | The seam refactor target (`DispatchFn` signature change, `max_ack_pending=1`, `_process_message` body change). |
| `src/forge/cli/serve.py` | `_run_serve` — the production composition root. |

### Tier 2 — should include

| Path | Why |
|---|---|
| `src/forge/pipeline/forward_context_builder.py` | `ForwardContextBuilder` — needs production construction. |
| `src/forge/pipeline/per_feature_sequencer.py` | One of the Supervisor's deps. |
| `src/forge/pipeline/cli_steering.py` | Cancel/skip/directive surface — relates to the live-build directives the orchestrator must handle. |
| `src/forge/pipeline/stage_taxonomy.py` | `StageClass` enum — the `stage_label` source for `emit_stage_complete`. |
| `src/forge/cli/_serve_config.py` | `ServeConfig` — the env-driven config surface. May need to expand to include orchestrator config (SQLite path, etc.). |
| `src/forge/lifecycle/persistence.py` | SQLite writers — likely sources for `StageLogRecorder` and `AutobuildStateInitialiser` Protocol implementations. |
| `src/forge/lifecycle/recovery.py` | The second `reconcile_on_boot` (lifecycle-side, distinct from `pipeline_consumer.reconcile_on_boot`) — both need a single startup call site. |
| `src/forge/config/models.py` | `ForgeConfig`, `PipelineConfig`, `DEFAULT_APPROVED_ORIGINATORS` — the config surface the deps factories read. |
| `tests/forge/test_supervisor.py` | Behavioural tests of the Supervisor — pin the production construction's behavioural contract. |
| `tests/forge/test_dispatch_autobuild_async.py` | Test contracts for the autobuild dispatcher — pin its production wiring. |
| `tests/forge/test_pipeline_consumer.py` | `handle_message` contract tests — pin the deferred-ack semantics. |
| `tests/forge/test_pipeline_lifecycle.py` | `PipelineLifecycleEmitter` contract tests — pin the per-stage caller wiring. |
| `tests/forge/test_contract_and_seam.py` | `PipelineConsumerDeps` shape — pin the deps factory output. |
| `tests/cli/test_serve_*.py` | Daemon-process tests — pin the `_serve_daemon` refactor against the existing F009 contract. |
| `docs/state/TASK-FORGE-FRR-001/implementation_plan.md` | The seam-refactor design (the one piece of the FRR-001 plan that's still load-bearing) lives here. The plan should re-use this design verbatim for the daemon-side task. |
| `tasks/completed/forge-production-image/IMPLEMENTATION-GUIDE.md` | F009 implementation guide — establishes the patterns this feature should follow for the daemon side. |

### Tier 3 — useful for completeness

| Path | Why |
|---|---|
| All Tier 2 + Tier 3 docs from the `/feature-spec` list above (ADRs, DDRs, contracts) | The plan can re-use the same constraint catalogue for verification of task ACs. |
| `tests/integration/test_mode_a_crash_recovery.py` | Integration tests — anchors for the e2e tasks. |
| `tests/integration/test_mode_b_smoke_e2e.py` | Same. |
| `tests/integration/test_mode_b_c_crash_recovery.py` | Same. |
| `tasks/completed/forge-production-image/TASK-F009-003-implement-forge-serve-daemon.md` | Where `_default_dispatch` was first introduced as a stub — the plan's daemon-refactor task supersedes it. |

### Explicitly excluded from `/feature-plan`

- **The runbook RESULTS file** — the spec already captures its symptoms in scenarios. The plan doesn't need it directly.
- **The pipeline-orchestrator research docs** (`pipeline-orchestrator-motivation.md`, `pipeline-orchestrator-consolidated-build-plan.md`) — useful context for the spec, too verbose for the plan.
- **The C4 SVG diagrams in `docs/research/`** — not text-readable by the planning workflow.

### Suggested invocation

```bash
/feature-plan <new-feature-slug> \
  --context=features/<new-feature-slug>/<new-feature-slug>.feature \
  --context=features/<new-feature-slug>/<new-feature-slug>_summary.md \
  --context=features/<new-feature-slug>/<new-feature-slug>_assumptions.yaml \
  --context=docs/research/forge-orchestrator-wiring-gap.md \
  --context=src/forge/pipeline/supervisor.py \
  --context=src/forge/pipeline/dispatchers/autobuild_async.py \
  --context=src/forge/adapters/nats/pipeline_consumer.py \
  --context=src/forge/adapters/nats/pipeline_publisher.py \
  --context=src/forge/pipeline/__init__.py \
  --context=src/forge/cli/_serve_daemon.py \
  --context=src/forge/cli/serve.py \
  --context=src/forge/pipeline/forward_context_builder.py \
  --context=src/forge/cli/_serve_config.py \
  --context=src/forge/lifecycle/persistence.py \
  --context=src/forge/lifecycle/recovery.py \
  --context=src/forge/config/models.py \
  --context=tests/forge/test_supervisor.py \
  --context=tests/forge/test_dispatch_autobuild_async.py \
  --context=tests/forge/test_pipeline_consumer.py \
  --context=tests/forge/test_pipeline_lifecycle.py \
  --context=tests/forge/test_contract_and_seam.py \
  --context=docs/state/TASK-FORGE-FRR-001/implementation_plan.md \
  --context=tasks/completed/forge-production-image/IMPLEMENTATION-GUIDE.md
```

(22 context files. If the command has a tighter budget, drop in this
order: `forward_context_builder.py` → `cli_steering.py` → the
integration test files → `_serve_config.py` → `recovery.py`. The
Supervisor + the four NATS-side modules + `_serve_daemon.py` +
`serve.py` + the four primary test files + the spec output + the
findings doc are non-negotiable.)

---

## What's NOT useful as `--context` for either command

A few documents that look adjacent but would mislead the workflow:

| Path | Why to skip |
|---|---|
| `tasks/completed/TASK-FORGE-FRR-002/...md` | The logging fix that just landed. Useful operationally but not architecturally relevant to the orchestrator wiring. |
| `tasks/completed/TASK-FORGE-FRR-003/...md` | Same — the build-image fix. |
| `tasks/completed/forge-production-image/TASK-F009-001-add-forge-serve-skeleton.md` through `TASK-F009-008-fold-runbook-section6-and-history.md` | Too granular. The IMPLEMENTATION-GUIDE.md captures the right level. |
| `tasks/in_progress/TASK-FORGE-FRR-001-wire-dispatch-payload-to-real-orchestrator.md` (for the plan) | The plan supersedes this; including it as plan context would create circular reference. (It's still useful for the spec layer because it captures the originating user-facing close criterion.) |
| `features/forge-production-image/forge-production-image_assumptions.yaml` | F009-internal assumptions; the new feature's own assumptions are what matter. |
| Any `tests/bdd/` files except those directly touching pipeline-state-machine surface | Too far afield. |
| `docs/runbooks/*` | Operational documentation; the new feature will have its own runbook eventually. |

---

## Open questions for `/feature-spec` to settle

These are the design decisions the spec layer needs to make. They are
listed here so they don't get re-discovered as gaps during planning.

1. **Where does the `autobuild_runner` AsyncSubAgent live in the
   codebase?** New module at `src/forge/pipeline/runners/autobuild_runner.py`?
   Inside `src/forge/pipeline/dispatchers/`? The architectural choice
   has knock-on effects for the test layout and for how `start_async_task`
   middleware finds the runner.

2. **Does the Supervisor run inside `forge serve` or alongside it?**
   The natural answer is "inside `_run_serve` next to `run_daemon` and
   `run_healthz_server`" — but the Supervisor's reasoning loop is
   long-running and may want its own `asyncio.gather` slot. Spec needs
   to describe the daemon-process composition.

3. **How does the inbound message reach the Supervisor?** Two paths:
   (a) `_serve_dispatcher` calls into `pipeline_consumer.handle_message`
   which dispatches via `PipelineConsumerDeps.dispatch_build` →
   `Supervisor.process_build`; (b) the Supervisor owns the consumer and
   the daemon just provides the NATS client. Spec should pick one.

4. **What's the ack lifecycle for the Supervisor's internal stages?**
   `pipeline_consumer.handle_message`'s `ack_callback` fires on terminal
   transition only. If the Supervisor has its own internal "stage
   accepted but not yet running" intermediate, when does ack fire?

5. **How does `PipelineLifecycleEmitter` reach the autobuild_runner
   subagent?** Through the AsyncSubAgent context payload? Through a
   module-level singleton? The choice affects testability and the
   correlation_id threading model.

6. **Does this feature subsume FEAT-FORGE-007 acceptance, or just
   wire it through?** If subsume: the feature's own e2e tests are the
   FEAT-FORGE-007 scenarios run end-to-end. If just wire-through: the
   feature has a smaller smoke-test surface and FEAT-FORGE-007 is
   implicitly verified.

---

## Open questions for `/feature-plan` to settle

These are decomposition decisions, not architectural ones. They affect
task granularity, not behaviour.

1. **One feature or two?** The autobuild_runner subagent is large
   enough to be its own feature. The Supervisor + dispatcher wiring is
   another. The two could ship sequentially. Conversely, shipping them
   as one feature avoids a "wired but un-runnable" intermediate state.

2. **Task granularity for the Supervisor's 12+ deps.** One task per
   dep? One task for "construct Supervisor + all deps"? Granularity
   trade-off between trackability and bookkeeping overhead.

3. **Test-task pairing.** Each construction task gets a paired test
   task, or test specs are co-located in the construction task? The
   F009 pattern was co-located.

4. **E2E test scope.** Single end-to-end test that exercises the full
   chain (jarvis → forge → autobuild → publish-back), or layered tests
   (one per orchestrator-internal stage transition)?
