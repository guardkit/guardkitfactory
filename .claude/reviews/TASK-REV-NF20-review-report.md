# Review Report — TASK-REV-NF20

## Executive Summary

**Feature**: FEAT-FORGE-002 NATS Fleet Integration
**Mode**: Decision (standard depth)
**Scope**: All areas (full sweep), balanced trade-off priority
**Outcome**: **Option 1 — Thin Adapter Layer over nats-core** recommended.
**Estimated effort**: 16–20 focused hours, 11 subtasks across 5 waves.
**Aggregate complexity**: 7/10.

The feature is well-specified: payload schemas, consumer config, KV invalidation
rules, and timing parameters are all pinned down by the existing API contracts
(`API-nats-fleet-lifecycle.md`, `API-nats-pipeline-events.md`) and the
already-released `nats-core ≥ 0.2.0`. The decision is therefore primarily about
**Python module layout, test strategy, and sequencing against FEAT-FORGE-001**,
not about transport choice or protocol design.

## Review Details

- **Task**: TASK-REV-NF20 — Plan: NATS Fleet Integration
- **Mode**: `decision`
- **Depth**: `standard`
- **Clarification**: Context A captured — Focus=All, Tradeoff=Balanced, Concerns=none
- **Reviewer**: orchestrator with design-contract analysis (no external agents invoked — context was authoritative)

## Findings

### F1 — Transport choice is already decided

`API-nats-pipeline-events.md §2.2` pins JetStream with `max_ack_pending=1`,
`durable="forge-consumer"`, `ack_wait=1h`, `DeliverPolicy.ALL`,
`AckPolicy.EXPLICIT`, `max_deliver=-1`. `API-nats-fleet-lifecycle.md §3.1`
pins Core NATS subscriptions for `fleet.register`, `fleet.deregister`,
`fleet.heartbeat.>` and NATS KV for the `agent-registry` bucket. **No
transport decision remains open.**

### F2 — Schema ownership sits in nats-core

All eight lifecycle payloads (`BuildStartedPayload`, `BuildProgressPayload`,
`StageCompletePayload`, `BuildPausedPayload`, `BuildResumedPayload`,
`BuildCompletePayload`, `BuildFailedPayload`, `BuildCancelledPayload`) already
ship in `nats_core.events.pipeline` (post TASK-NCFA-003, 2026-04-23).
`AgentManifest`, `IntentCapability`, `ToolCapability`, `MessageEnvelope`, and
`NATSKVManifestRegistry` also ship in `nats-core`. **Forge imports; does not
redeclare** — the earlier interim carrier plan was retired. This materially
reduces the implementation surface.

### F3 — Dependency on FEAT-FORGE-001 is load-bearing

FEAT-FORGE-002 **extends** the FEAT-FORGE-001 state machine with bus publishing
and **subscribes to** the build-queue that feeds FEAT-FORGE-001's lifecycle.
The two features share the SQLite history, the `BuildStatus` enum, the
`StageLogEntry` writer, and the `(feature_id, correlation_id)` unique index
that underwrites duplicate detection. **FEAT-FORGE-002 cannot land before
FEAT-FORGE-001 ships its state machine, SQLite schema, and `forge.yaml`
loader**, otherwise fleet publishers will have no transitions to hook and
pipeline consumer will have no history to reconcile against.

### F4 — Discovery layer is pure domain; fleet watcher is the adapter

`DM-discovery.md §2` puts `forge.discovery` (cache + resolve) in Domain Core
with no NATS imports. `forge.adapters.nats.fleet_watcher` owns the
subscription and delegates cache mutations via an asyncio-locked interface.
This boundary is explicit in the design and must be preserved — the review
recommends making the interface a `Protocol` that `forge.discovery` exposes
and the watcher calls, so the domain package has zero `nats-core` imports.

### F5 — Heartbeat loop must be independent of registry reachability

Scenario "Heartbeats continue to publish even when the fleet registry is
temporarily unreachable" (Group E, `@integration`) makes this explicit.
Heartbeats publish to the FLEET subject; registry KV reads are a separate
operation. The heartbeat loop must be its own `asyncio.Task` that does NOT
await KV operations on its hot path; registry refresh is a best-effort
background concern triggered when the bus comes back.

### F6 — Publish failures must not regress SQLite history

Group E `@data-integrity`: a lifecycle publish failure does not roll back the
build's recorded progress. This means **the ordering is always
`write-to-SQLite → publish`, not atomic**. If publish raises, log + continue;
do not revert the state transition. This contradicts a naïve unit-of-work
pattern; callers must treat the publisher as fire-and-forget with structured
logging for later reconciliation.

### F7 — Terminal-only ack is a correctness invariant

`API-nats-pipeline-events.md §2.2` and Group E `@concurrency`: only `COMPLETE
| FAILED | CANCELLED | SKIPPED` ack. `PAUSED` holds the message unacked so the
queue position is preserved across restarts. A common mistake is acking on
`RUNNING` (because the build "started successfully") — that would cause
redelivery to be silently dropped. Contract tests must assert that ack is
called exactly once per terminal transition and never for intermediate
states.

### F8 — Redelivery idempotency must sit on the SQLite unique index

Duplicate detection uses `builds(feature_id, correlation_id)` unique index
(FEAT-FORGE-001 §5 invariant). On redelivery, the pipeline consumer first
checks SQLite; if the row exists in a terminal state, ack immediately. If
the row doesn't exist, start a fresh build. The unique index is a
**pre-condition** — the consumer cannot safely run without it. This
reinforces the FEAT-FORGE-001 sequencing requirement from F3.

### F9 — Cache consistency under racing events

`DM-discovery.md §2` states the cache is `dict[str, DiscoveryCacheEntry]`
guarded by an asyncio lock. The watcher callback runs on the NATS subscriber
task and `resolve()` runs on the dispatch-call path — both mutate/read. The
lock must be held for the whole read-modify-write of a single event
(register+upsert, deregister+delete, heartbeat+update-or-refresh). Contract
tests should exercise the racing scenario (Group E `@concurrency`) with
`asyncio.gather` of register+deregister events.

### F10 — Security scenarios require dedicated tests, not integration

Group E `@security`:
1. Manifest exclusion — runtime secrets must never be serialised. A unit
   test that `FORGE_MANIFEST.model_dump_json()` contains none of
   `{"api_key", "token", "password", "secret"}` is sufficient and cheap.
2. Originator allowlist — config-driven list, rejected originators trigger
   `publish_build_failed`. This is pure logic, no NATS transport needed.

These should not be deferred to integration tests — they are cheap, fast,
and load-bearing.

### F11 — Timing-sensitive tests risk flakiness

Heartbeat cadence (30s), cache TTL (30s), stale threshold (90s), progress
cadence (≥60s). Wall-clock sleeps are forbidden — tests must use an injected
clock (a simple `Callable[[], datetime]` or a `TimeProvider` protocol) so
boundary scenarios (`seconds_ago = 30|60|90`) are deterministic. Avoid
`freezegun` in asyncio tests where feasible — prefer manual clock injection
for lower coupling to a third-party library.

### F12 — `@tool` decorator is not in scope

The `dispatch_by_capability` generic tool is future work (ADR-ARCH-015,
governed by a separate feature). FEAT-FORGE-002 stops at discovery.resolve()
returning `(agent_id, CapabilityResolution)`. The LangChain
`@tool(parse_docstring=True)` layer will wrap it later. **Do not bundle
in.** Keeping scope tight to fleet lifecycle + pipeline bus is what keeps
the subtask count at 11 rather than 18.

## Decision Matrix

| Option | Score | Effort | Risk | Recommendation |
|---|---|---|---|---|
| **Option 1 — Thin adapter layer over nats-core** | **8.5/10** | **16–20 h** | **Low** | **✅ Recommended** |
| Option 2 — Monolithic `forge.nats` module | 5.5/10 | 8–12 h | High | ❌ Violates ADR-ARCH-017 separation; poor testability |
| Option 3 — `EventBus` protocol + in-memory test impl | 6/10 | 20–24 h | Medium | ❌ Violates ADR-ARCH-003 (no transport ABC); YAGNI — no second transport planned |

### Option 1 detail — Thin Adapter Layer (Recommended)

**Module layout**:

```
src/forge/
  config/
    loader.py                    # forge.yaml → ForgeConfig (Pydantic)
    models.py                    # FleetConfig, PipelineConfig, PermissionsConfig
  fleet/
    manifest.py                  # FORGE_MANIFEST builder (declarative)
  discovery/
    __init__.py
    cache.py                     # DiscoveryCacheEntry, asyncio-locked dict wrapper
    resolve.py                   # resolve() + tie-break; CapabilityResolution
    protocol.py                  # FleetEventSink Protocol (watcher → cache)
  adapters/
    nats/
      fleet_publisher.py         # register_on_boot, heartbeat_loop, deregister
      fleet_watcher.py           # subscribe fleet.*, delegate to FleetEventSink
      pipeline_consumer.py       # pull consumer, validation, allowlist, reconcile
      pipeline_publisher.py      # 8 lifecycle publisher methods
      clock.py                   # Clock protocol for test injection
```

**Pros**:
- Preserves DDD boundaries from `domain-model.md` and `container.md`.
- Each module is independently testable via mocked `nats_client`.
- Parallelisable — four of the adapter files have no cross-dependencies beyond the config + manifest + discovery protocol.
- Tracks existing ADRs (ADR-ARCH-015/016/017/021, ADR-ARCH-014).

**Cons**:
- More files than a single-module approach; acceptable trade-off for separation of concerns.
- Requires disciplined import boundary — `forge.discovery` must not import `nats_core` (only `forge.adapters.nats.*` may).

## Recommendation

**Proceed with Option 1** under a **balanced** trade-off posture:

1. Gate FEAT-FORGE-002 on FEAT-FORGE-001 being either complete or at least
   scaffolded through its SQLite schema + state machine + config loader
   (i.e. Waves 1–2 of FEAT-FORGE-001 must be in place). Explicitly note this
   in the feature README.
2. Structure implementation as 11 subtasks across 5 waves (see §Subtask
   Breakdown below).
3. Keep `forge.discovery` pure — no NATS imports; surface a `FleetEventSink`
   Protocol for the watcher.
4. Inject a `Clock` protocol everywhere time matters — heartbeat loop,
   cache TTL, progress cadence, staleness window. No wall-clock sleeps in
   tests.
5. Contract-test the `nats_client` boundary (publisher methods called with
   correct subject + envelope shape + ack semantics) and seam-test the
   fleet_watcher → discovery handoff.
6. BDD @smoke + @key-example scenarios get dedicated pytest tests wired via
   `@task:<TASK-ID>` tags so the R2 oracle runs them per-task.

## Subtask Breakdown — 11 subtasks / 5 waves

| Wave | ID | Title | Type | Complexity | Mode | Depends on |
|---|---|---|---|---|---|---|
| 1 | TASK-NFI-001 | Extend forge.yaml config: fleet + pipeline + permissions sections | declarative | 3 | direct | — |
| 1 | TASK-NFI-002 | Define FORGE_MANIFEST constant builder | declarative | 2 | direct | — |
| 2 | TASK-NFI-003 | Implement forge.discovery domain (cache + resolve + tie-break + Clock protocol + FleetEventSink Protocol) | feature | 6 | task-work | 001, 002 |
| 3 | TASK-NFI-004 | Implement forge.adapters.nats.fleet_publisher (register / heartbeat-loop / deregister) | feature | 5 | task-work | 001, 002, 003 |
| 3 | TASK-NFI-005 | Implement forge.adapters.nats.fleet_watcher (subscribe + delegate to FleetEventSink) | feature | 5 | task-work | 003 |
| 3 | TASK-NFI-006 | Implement forge.adapters.nats.pipeline_publisher (8 lifecycle publisher methods) | feature | 5 | task-work | 001 |
| 3 | TASK-NFI-007 | Implement forge.adapters.nats.pipeline_consumer (pull consumer + validation + allowlist) | feature | 6 | task-work | 001 |
| 4 | TASK-NFI-008 | Wire state-machine transitions → pipeline_publisher (lifecycle emission points) | feature | 5 | task-work | 006 |
| 4 | TASK-NFI-009 | Implement pipeline_consumer.reconcile_on_boot (crash recovery + paused re-announce) | feature | 6 | task-work | 007, 008 |
| 5 | TASK-NFI-010 | Contract + seam tests (nats_client mock, FleetEventSink seam, terminal-ack invariant, secret-free manifest) | testing | 5 | task-work | 004, 005, 006, 007, 009 |
| 5 | TASK-NFI-011 | BDD @smoke + @key-example pytest wiring (33 scenarios → tagged tests) | testing | 4 | task-work | 004–009 |

**Parallel wave totals**:
- Wave 1 (2 tasks): ~2–3h parallel
- Wave 2 (1 task): ~4–5h
- Wave 3 (4 tasks): ~5–6h parallel — the main wave
- Wave 4 (2 tasks): ~4–5h (008 then 009)
- Wave 5 (2 tasks): ~3–4h parallel

**Critical path**: Wave 1 → Wave 2 (discovery) → Wave 3 (publisher chain 006 → Wave 4 008) → Wave 4 (009) → Wave 5. Approx 16–20 h wall-time with good parallelisation.

## Integration Contracts (cross-task data flow)

See §4 in the generated IMPLEMENTATION-GUIDE.md. Five contracts identified:

1. **ForgeConfig.fleet** — producer 001, consumers 004, 005 (heartbeat / stale threshold)
2. **ForgeConfig.permissions.filesystem.allowlist** — producer 001, consumer 007 (path gate)
3. **FORGE_MANIFEST** — producer 002, consumer 004 (registration call)
4. **FleetEventSink Protocol** — producer 003, consumer 005 (cache upsert/delete/update)
5. **PipelinePublisher methods** — producer 006, consumer 008 (state-transition emission points)

## Risk Register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | FEAT-FORGE-001 not shipped before this feature starts | High | Gate in README; require state machine + SQLite schema + config loader present at Wave 1 start |
| R2 | Terminal-ack invariant violated (ack fires on non-terminal state) | High | Contract test asserts ack called only on COMPLETE/FAILED/CANCELLED/SKIPPED |
| R3 | Race between fleet watcher callback and resolve() corrupts cache | Medium | asyncio.Lock around dict; concurrency scenario test (Group E) |
| R4 | Heartbeat loop blocks on KV read during registry outage | Medium | Separate asyncio.Task; no KV await on heartbeat hot path; reachability scenario test |
| R5 | Publish failure rolls back SQLite history | High | Strict write-then-publish ordering; publish raises → log only, no rollback |
| R6 | Secrets leak into AgentManifest | High | Unit test scans manifest JSON for key/token/password/secret substrings |
| R7 | Timing-sensitive tests flake in CI | Medium | Inject Clock protocol everywhere; no wall-clock sleeps |
| R8 | Paused build re-announcement ordering wrong on restart | Medium | Reconcile_on_boot publishes BuildPausedPayload + ApprovalRequestPayload idempotently on correlation_id |
| R9 | Duplicate detection fails (unique index missing) | High | Pre-flight check that FEAT-FORGE-001's builds.uq_builds_feature_correlation exists before Wave 3 |
| R10 | Originator allowlist config not loaded | Medium | TASK-NFI-001 covers it; TASK-NFI-007 fails fast if config missing |

## Context Used

- `features/nats-fleet-integration/nats-fleet-integration_summary.md` — scope, assumptions, scenario counts
- `features/nats-fleet-integration/nats-fleet-integration.feature` — 33 scenarios
- `features/nats-fleet-integration/nats-fleet-integration_assumptions.yaml` — 5 confirmed assumptions
- `docs/design/contracts/API-nats-fleet-lifecycle.md` — registration, heartbeat, watch, KV contracts
- `docs/design/contracts/API-nats-pipeline-events.md` — consumer config, 8 lifecycle payloads, ack rule, crash recovery
- `docs/design/contracts/API-nats-agent-dispatch.md` — dispatch scope boundary (excluded from this feature)
- `docs/design/models/DM-discovery.md` — cache entry, resolve algorithm, invariants
- `docs/design/models/DM-build-lifecycle.md` — state machine, terminal states, invariants
- `features/pipeline-state-machine-and-configuration/pipeline-state-machine-and-configuration_summary.md` — FEAT-FORGE-001 context (upstream dependency)
- `pyproject.toml` — confirmed `nats-core >= 0.2.0` declared; no additional transport library needed
- ADRs referenced in contracts: ADR-ARCH-003 (no transport ABC), ADR-ARCH-014 (max_ack_pending=1), ADR-ARCH-015 (capability-driven dispatch), ADR-ARCH-016 (fleet-is-the-catalogue), ADR-ARCH-017 (live fleet watching), ADR-ARCH-021 (paused via langgraph interrupt)

## Decision Options

- **[A]ccept** — Approve findings. Review archived, ready to inform a later implementation cycle.
- **[R]evise** — Request deeper analysis (e.g. spike on a specific risk, exploration of alternative library, deeper test-strategy pass).
- **[I]mplement** — Create the 11-subtask feature structure under `tasks/backlog/nats-fleet-integration/`, generate the YAML feature file for AutoBuild, and run the BDD linker + nudges.
- **[C]ancel** — Discard this review.
