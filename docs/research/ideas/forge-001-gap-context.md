# FEAT-FORGE-001 Gap Context — what already exists, what `/feature-plan` must build

> **Purpose:** focused context for `/feature-plan FEAT-FORGE-001` so the plan does
> **not** duplicate work that 002–007 already shipped. FEAT-FORGE-001 was specced
> on a clean-slate assumption (Apr 24); it was then absorbed silently into the
> per-feature backlogs of 002–007, which built the *upstream-of-CLI* surface
> (NATS adapters, config models, stage-ordering guards, executor-layer cancel /
> skip handler) but **not** the CLI itself, the SQLite-backed build history,
> the build-lifecycle transition table, or crash recovery.
>
> Read alongside [pipeline-state-machine-and-configuration_summary.md](../../../features/pipeline-state-machine-and-configuration/pipeline-state-machine-and-configuration_summary.md)
> (the feature spec) and [DDR-003-sqlite-schema-layout-wal.md](../../design/decisions/DDR-003-sqlite-schema-layout-wal.md)
> (the SQLite schema contract).

## How to use this document

Pass it to `/feature-plan FEAT-FORGE-001` as a `--context` flag alongside the
spec summary:

```bash
guardkit feature-plan "Pipeline State Machine and Configuration" \
  --context forge/features/pipeline-state-machine-and-configuration/pipeline-state-machine-and-configuration_summary.md \
  --context forge/docs/research/ideas/forge-001-gap-context.md \
  --context forge/docs/design/contracts/API-cli.md \
  --context forge/docs/design/contracts/API-sqlite-schema.md \
  --context forge/docs/design/decisions/DDR-003-sqlite-schema-layout-wal.md
```

The plan must **reuse** the existing Protocols / executor logic listed in §2 and
**only build** the gaps in §3.

---

## §1 — TL;DR

| Layer | Status | Owning module(s) |
|---|---|---|
| Config models (`forge.yaml` schema) | ✅ shipped | [src/forge/config/models.py](../../../src/forge/config/models.py) |
| Build-lifecycle state enum | ✅ shipped | [src/forge/pipeline/supervisor.py](../../../src/forge/pipeline/supervisor.py) (`BuildState`), [src/forge/pipeline/cli_steering.py](../../../src/forge/pipeline/cli_steering.py) (`BuildLifecycle`) |
| Build-lifecycle **transition table** + invalid-transition rejection | ❌ **build** | new — `src/forge/lifecycle/state_machine.py` |
| Cancel / skip executor logic (synthetic reject, skip-veto, directive enqueue) | ✅ shipped | [src/forge/pipeline/cli_steering.py](../../../src/forge/pipeline/cli_steering.py) |
| Cancel / skip Protocol seams (`BuildSnapshotReader`, `BuildCanceller`, `BuildResumer`, `StageLogReader`, `StageSkipRecorder`, `PauseRejectResolver`, `AsyncTaskCanceller`, `AsyncTaskUpdater`) | ✅ shipped (interfaces only) | [src/forge/pipeline/cli_steering.py](../../../src/forge/pipeline/cli_steering.py) |
| **Concrete SQLite-backed implementations of those Protocols** | ❌ **build** | new — `src/forge/lifecycle/persistence.py` |
| `builds` + `stage_log` SQLite schema (DDR-003 WAL + STRICT) | ❌ **build** | new — `src/forge/lifecycle/schema.sql` + `migrations.py` |
| NATS pipeline consumer (pull, durable) | ✅ shipped | [src/forge/adapters/nats/pipeline_consumer.py](../../../src/forge/adapters/nats/pipeline_consumer.py) |
| NATS pipeline publisher (lifecycle subjects) | ✅ shipped | [src/forge/adapters/nats/pipeline_publisher.py](../../../src/forge/adapters/nats/pipeline_publisher.py) |
| Synthetic response injector (cancel→reject for paused builds) | ✅ shipped | [src/forge/adapters/nats/synthetic_response_injector.py](../../../src/forge/adapters/nats/synthetic_response_injector.py) |
| **CLI surface (`forge queue/status/history/cancel/skip`)** | ❌ **build** | new — `src/forge/cli/main.py` + per-command modules |
| **`console_scripts` entry point** | ❌ **build** | edit — [pyproject.toml](../../../pyproject.toml) |
| **Sequential-queue picker** (per-project max_concurrent=1) | ❌ **build** | new — `src/forge/lifecycle/queue.py` |
| **Crash-recovery / reconciliation pass** (rehydrate non-terminal builds on restart) | ❌ **build** | new — `src/forge/lifecycle/recovery.py` |
| **Path-traversal validation** for `feature_id` | ❌ **build** | new — `src/forge/lifecycle/identifiers.py` |
| **Watch-mode** (`forge status --watch`) | ❌ **build** | new — folded into `cli/status.py` |
| **Defaults application** (forge.yaml → new build) | ❌ **build** | folded into `cli/queue.py` + `lifecycle/persistence.py` |
| **Write-then-publish failure-mode visibility** (build row remains pending pickup if NATS publish fails) | ❌ **build** | folded into `cli/queue.py` |

**Net new code surface:** one new package — `src/forge/lifecycle/` (persistence,
schema, state machine, queue, recovery, identifiers) — plus the `src/forge/cli/`
package and a small pyproject edit. Everything else wires to existing modules.

---

## §2 — What `/feature-plan` MUST reuse (do not duplicate)

### 2.1 Config layer — `src/forge/config/`

`ForgeConfig` and its sub-models (`PipelineConfig`, `ApprovalConfig`,
`FleetConfig`, `PermissionsConfig`, `FilesystemPermissions`) already exist as
Pydantic v2 models at [src/forge/config/models.py](../../../src/forge/config/models.py).
The `ForgeConfig` root model is the parsed shape of `forge.yaml`.

**What's missing here, but must be added inside the existing module (not a new
config package):**
- A `load_config(path: Path) -> ForgeConfig` helper that reads YAML + validates
  via Pydantic. (The class exists; the loader does not.)
- An additional sub-model for `forge.yaml.queue` (turn-budget defaults, history
  default-limit `50`, allowlisted repository paths) — see spec scenarios under
  Group A "Configuration loading" and Group C "path allowlist".

`/feature-plan` should produce **edit** tasks against `forge/config/models.py`,
not a parallel `forge/lifecycle/config.py`.

### 2.2 Pipeline executor layer — `src/forge/pipeline/cli_steering.py`

`CliSteeringHandler` already implements:
- Cancel-during-pause → synthetic reject (FEAT-FORGE-004 ASSUM-005, AC-002)
- Cancel-during-autobuild → `cancel_async_task` + terminal CANCELLED (AC-002)
- Skip-on-non-constitutional-stage → stage logged SKIPPED, resume next (AC-003 / AC-006)
- Skip-on-constitutional-stage → vetoed via `ConstitutionalGuard.veto_skip` (AC-007)
- Mid-flight directive → enqueued onto `AutobuildState.pending_directives` (AC-004)

The Protocol seams (`BuildSnapshotReader`, `PauseRejectResolver`,
`AsyncTaskCanceller`, `AsyncTaskUpdater`, `BuildCanceller`, `StageSkipRecorder`,
`BuildResumer`) are defined in the same module and explicitly waiting for
FEAT-FORGE-001's concrete implementations.

**`/feature-plan` MUST NOT** redesign the cancel/skip semantics. It must only
produce a concrete `LifecyclePersistence` / `SqliteBuildSnapshotReader` /
`SqliteBuildCanceller` / etc. classes that satisfy these Protocols, and a thin
CLI wrapper that calls `CliSteeringHandler.handle_cancel()` /
`.handle_skip()` / `.handle_directive()`.

### 2.3 Pipeline supervisor — `src/forge/pipeline/supervisor.py`

`Supervisor` owns the **per-turn reasoning loop within a running build**.
`BuildState` enum is here, used by the supervisor to refuse work after a
terminal state (`TerminalStateError`).

**What's NOT here:** the build-lifecycle transition graph (queued→pending_pickup
→preparing→running→finalising→complete|failed|cancelled|skipped), the rules for
which transitions are valid, and the rejection of out-of-table jumps. Those
belong in the new `src/forge/lifecycle/state_machine.py` and must be the **sole
caller** of any persistence write that mutates `builds.state`.

### 2.4 NATS adapters — `src/forge/adapters/nats/`

Already shipped:
- `pipeline_consumer.py` — durable pull consumer on `pipeline.build-queued.>`
- `pipeline_publisher.py` — eight outbound lifecycle subjects (build-started, build-paused, build-resumed, build-cancelled, build-completed, build-failed, stage-completed, queue-acknowledged)
- `synthetic_response_injector.py` — cancel→reject injection for paused builds
- `approval_publisher.py` / `approval_subscriber.py` — pause/resume protocol

**`/feature-plan` MUST NOT** add new adapters. The `forge queue` CLI publishes
through `pipeline_publisher`; reconciliation reads from `pipeline_consumer`.

### 2.5 Pipeline package wiring — `src/forge/pipeline/`

`stage_taxonomy.py` (StageClass enum + CONSTITUTIONAL_STAGES set),
`stage_ordering_guard.py` (per-stage prerequisite map within a single build),
`forward_propagation.py` / `forward_context_builder.py` (stage→stage context
threading), `constitutional_guard.py` (PR-review skip-veto), and the
`dispatchers/` (subprocess, specialist, autobuild_async) are all in flight from
002–007 and **must not** be touched by FEAT-FORGE-001.

---

## §3 — What `/feature-plan` MUST build (per-scenario gap)

Every row below is a build task or task cluster. "Reuse" cells reference the
modules from §2; "Build" cells point at the new module under
`src/forge/lifecycle/` or `src/forge/cli/`.

### Group A — Key Examples (6)

| Scenario | Coverage | Build (FEAT-FORGE-001) | Reuse |
|---|---|---|---|
| Queueing creates pending pickup | ❌ | `cli/queue.py` (argv, allowlist check, identifier validation, defaults application, write-then-publish, exit codes) + `lifecycle/persistence.py` (`record_pending_build`) | `config.models.ForgeConfig`, `adapters.nats.pipeline_publisher` |
| Lifecycle to completion | partial | `lifecycle/state_machine.py` transition table (preparing→running→finalising→complete) + `lifecycle/persistence.py` writes that *only* the state machine may invoke | `pipeline.supervisor.BuildState`, existing dispatch pipeline |
| `forge status` shows non-terminal + recent | ❌ | `cli/status.py` + `lifecycle/persistence.py.read_status()` (no NATS dependency — pure SQLite read) | none |
| `forge history --feature` lists prior attempts | ❌ | `cli/history.py` + `lifecycle/persistence.py.read_history(feature_id, limit)` | none |
| Defaults applied; CLI override wins | ❌ | `cli/queue.py` argv parsing → merges with `ForgeConfig` defaults; persisted onto build row | `config.models` |
| Status responsive while writer active (WAL) | ❌ | DDR-003 SQLite WAL configuration in `lifecycle/schema.sql` + `connect()` helper that opens reader connections in deferred mode | DDR-003 |

### Group B — Boundary Conditions (6)

| Scenario | Coverage | Build | Reuse |
|---|---|---|---|
| Turn budget ≥ 1 accepted | ❌ | Pydantic validator on the new `QueueConfig` sub-model in `config/models.py` | `config.models` |
| Turn budget ≤ 0 rejected | ❌ | same validator, rejection branch | same |
| `forge history --limit N` capped | ❌ | `cli/history.py` argument parsing + `persistence.read_history(limit=...)` SQL clamp | none |
| `forge history` default = 50 | ❌ | default in `cli/history.py` argparse | none |
| Duplicate `(feature_id, correlation_id)` refused | ❌ | UNIQUE INDEX in `schema.sql` on `(feature_id, correlation_id)` + `cli/queue.py` translates IntegrityError → exit code | DDR-003 |
| Full status view caps stage detail at 5 | ❌ | `cli/status.py --full` clamps stage tail to 5 (configurable later) | none |

### Group C — Negative Cases (7)

| Scenario | Coverage | Build | Reuse |
|---|---|---|---|
| Path outside allowlist refused | ❌ | `cli/queue.py` allowlist check against `PermissionsConfig.repo_allowlist` (extend `FilesystemPermissions` if needed) — fail before write, before publish | `config.models.PermissionsConfig` |
| Active in-flight duplicate refused | ❌ | `persistence.exists_active_build(feature_id) -> bool` queried by `cli/queue.py` before write | none |
| Skip on non-paused refused | ✅ executor logic exists | `cli/skip.py` thin wrapper → `CliSteeringHandler.handle_skip()` (handler already returns `SkipStatus.REFUSED` for non-paused) | `pipeline.cli_steering.CliSteeringHandler` |
| Cancel of unknown feature → not-found | ❌ | `persistence.find_active_or_recent(feature_id)` returns None → `cli/cancel.py` exits non-zero | none |
| Invalid feature description → preparing→failed | ❌ | preparation entry-point validates description; on ValidationError, state machine `transition(build, BuildState.FAILED, reason=...)` | `lifecycle/state_machine.py` |
| Hard-stop gate during running → running→failed | partial | gate evaluator already exists (FEAT-FORGE-004); state_machine must accept the running→failed transition with completion_time set | `gating/`, new state machine |
| Invalid lifecycle jump refused | ❌ | `lifecycle/state_machine.py.transition()` validates against the table; raises `InvalidTransitionError`; persistence write only after validation | new |

### Group D — Edge Cases (9)

| Scenario | Coverage | Build | Reuse |
|---|---|---|---|
| Crash during preparing → interrupted, redeliver | ❌ | `lifecycle/recovery.py.reconcile()` runs on startup: scan SQLite for non-terminal builds, mark INTERRUPTED, NACK any in-flight delivery so JetStream redelivers | `adapters.nats.pipeline_consumer` |
| Crash during running → interrupted, restart from preparing | ❌ | same recovery path; build re-enters lifecycle at PENDING_PICKUP and the next pull picks it up | same |
| Crash during finalising → interrupted with PR warning | ❌ | recovery emits warning record (PR may exist), operator reconciles via `forge history --reconcile` | new CLI flag |
| Paused-build crash → re-issue approval | ❌ | recovery detects PAUSED, re-publishes pending approval request via `approval_publisher` | `adapters.nats.approval_publisher` |
| Terminal-after-crash = no-op | ❌ | recovery filters terminal states; ACKs any pending delivery | same |
| Cancel paused → synthetic reject → cancelled | ✅ executor logic exists | `cli/cancel.py` thin wrapper → `CliSteeringHandler.handle_cancel()` (handler returns `CancelStatus.RESOLVED_AS_REJECT` for paused) | `pipeline.cli_steering`, `adapters.nats.synthetic_response_injector` |
| Skip flagged-stage → stage SKIPPED, resume running | ✅ executor logic exists | `cli/skip.py` wrapper → `CliSteeringHandler.handle_skip()` | `pipeline.cli_steering` |
| Sequential queue per-project | ❌ | `lifecycle/queue.py.next_build_to_pick(project)` returns None if any non-terminal build for that project exists; pull-consumer handler delegates to it | `adapters.nats.pipeline_consumer` |
| Watch mode refreshes | ❌ | `cli/status.py --watch` polls `persistence.read_status()` at 1Hz; exits on terminal | `lifecycle/persistence.py` |

### Group E — Security (2)

| Scenario | Coverage | Build | Reuse |
|---|---|---|---|
| Path-traversal `../` rejected | ❌ | `lifecycle/identifiers.py.validate_feature_id(s)` — regex allowlist `[A-Za-z0-9_-]+`, no `/`, no `\`, no `..` segment; called from `cli/queue.py` *before* any write or publish | none |
| Cancelling operator recorded distinctly | ❌ | `builds.originating_user` (already in DDR-003 schema), `approval_responses.responder` set by `synthetic_response_injector` from `cli/cancel.py --as <operator>` | DDR-003, `adapters.nats.synthetic_response_injector` |

### Group F — Concurrency (2)

| Scenario | Coverage | Build | Reuse |
|---|---|---|---|
| Two simultaneous queues both durable, ordered | ❌ | UNIQUE on `build_id` (UUID), `queued_at` timestamp ordering preserved; SQLite IMMEDIATE transactions for the queue write | DDR-003 |
| Concurrent reader sees consistent snapshot | ❌ | DDR-003 WAL configuration (already specced); reader connection in deferred mode | DDR-003 |

### Group G — Data Integrity (2)

| Scenario | Coverage | Build | Reuse |
|---|---|---|---|
| Terminal state ⇒ completion_time recorded | ❌ | `state_machine.transition()` invariant: terminal transitions must set `completed_at`; tested as a property on the transition table | new state machine |
| Write succeeded but publish failed → row remains pending pickup | ❌ | `cli/queue.py` orders write→publish; on publish failure, log + exit non-zero with explicit "pipeline not notified" message; row left as-is so a re-queue or operator action can recover | `adapters.nats.pipeline_publisher` |

### Group H — Integration Boundaries (1)

| Scenario | Coverage | Build | Reuse |
|---|---|---|---|
| Pipeline messaging unreachable → clean failure | ❌ | `cli/queue.py` catches `nats.errors.*` from publisher, formats messaging-layer error; status / history continue to function (they don't touch NATS) | `adapters.nats.pipeline_publisher` |

---

## §4 — Suggested module layout

```
src/forge/
├── cli/
│   ├── __init__.py
│   ├── main.py            # argparse entry point, dispatches to subcommands
│   ├── queue.py           # forge queue
│   ├── status.py          # forge status (incl. --watch, --full)
│   ├── history.py         # forge history
│   ├── cancel.py          # forge cancel  → CliSteeringHandler.handle_cancel
│   └── skip.py            # forge skip    → CliSteeringHandler.handle_skip
├── lifecycle/
│   ├── __init__.py
│   ├── schema.sql         # DDR-003 builds + stage_log + UNIQUE indices
│   ├── migrations.py      # apply schema; idempotent
│   ├── persistence.py     # SqliteLifecyclePersistence implements all
│   │                      # FEAT-FORGE-001 Protocol seams from cli_steering
│   ├── state_machine.py   # transition table + transition() guard
│   ├── queue.py           # sequential per-project picker
│   ├── recovery.py        # startup reconciliation pass
│   └── identifiers.py     # validate_feature_id, derive_build_id
└── pipeline/              # ← UNCHANGED (002–007 territory)
```

`pyproject.toml` adds:

```toml
[project.scripts]
forge = "forge.cli.main:main"
```

---

## §5 — What `/feature-plan` MUST NOT do

- **Do not** add `forge.config.QueueConfig` as a new module — extend
  `forge/config/models.py` in place.
- **Do not** redesign cancel / skip executor semantics — they live in
  `pipeline/cli_steering.py` and are FEAT-FORGE-007 territory.
- **Do not** add new NATS subjects, payloads, or adapters. All eight lifecycle
  subjects and the synthetic-response injector exist.
- **Do not** rebuild stage-ordering guards or forward-propagation — that is
  FEAT-FORGE-007 (within-build stage progression), distinct from FEAT-FORGE-001
  (across-build lifecycle).
- **Do not** re-spec or re-scope Group D edge cases that the executor already
  handles — emit thin CLI wrappers only.

---

## §6 — Acceptance for the gap closure

The gap is closed when:

1. `forge queue / status / history / cancel / skip` work end-to-end, exercised
   by all 34 BDD scenarios in
   [pipeline-state-machine-and-configuration.feature](../../../features/pipeline-state-machine-and-configuration/pipeline-state-machine-and-configuration.feature).
2. `lifecycle/state_machine.py` rejects every out-of-table transition with
   `InvalidTransitionError`, tested as a property.
3. `lifecycle/recovery.py` reconciles every non-terminal build state on
   restart (Group D crash scenarios).
4. `forge status` returns without NATS being reachable (Group H).
5. The four LES1 parity gates from the build plan §"Specialist-agent LES1
   Parity Gates" still pass on the production image — adding the CLI must
   not break the JetStream subscription or PORT/ARFS dispatch matrices.
6. The build plan's progress log row for Step 5 / FEAT-FORGE-001 flips from
   "absorbed" to "✅ complete" with the autobuild commit recorded.
