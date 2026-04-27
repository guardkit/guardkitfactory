# Review Report — TASK-REV-3EEE

## Executive Summary

**Feature**: FEAT-FORGE-001 — Pipeline State Machine and Configuration
**Mode**: Decision (standard depth)
**Scope**: All areas (full sweep), quality trade-off priority
**Specific concerns**: state-mutation exclusivity, write-then-publish failure path, identifier validation depth, PAUSED-recovery `request_id` idempotency
**Outcome**: **Option 1 — Dedicated `src/forge/lifecycle/` package + `src/forge/cli/` package, reusing 002–007 surface unchanged** recommended.
**Estimated effort**: ~55–60 focused hours with 2-wide parallelism, 13 subtasks across 5 waves.
**Aggregate complexity**: 8/10.

The feature is exceptionally well-grounded. The spec (34 BDD scenarios, 5
confirmed assumptions, 0 deferred items) and the gap-context document
(`docs/research/ideas/forge-001-gap-context.md`) together pin nearly every
design boundary: the SQLite DDL is fixed by `API-sqlite-schema.md` and DDR-003;
the CLI shape is fixed by `API-cli.md`; the cancel/skip executor logic and
Protocol seams already ship in `pipeline/cli_steering.py` from FEAT-FORGE-007;
the eight NATS lifecycle subjects and synthetic-response injector already ship
in `adapters/nats/` from FEAT-FORGE-002. The decision is therefore primarily
about **module layout, the state-machine sole-writer rule, the
write-then-publish ordering at the CLI boundary, the depth of identifier
validation, and the PAUSED-recovery request_id contract**.

The four user-supplied specific concerns each map cleanly to a single named
module under `src/forge/lifecycle/` and constitute the highest-priority
correctness invariants for the feature. None requires redesign of existing
contracts; all are enforceable with thin, testable code.

## Review Details

- **Task**: TASK-REV-3EEE — Plan: Pipeline State Machine and Configuration
- **Mode**: `decision`
- **Depth**: `standard`
- **Clarification**: Context A captured — Focus=All, Tradeoff=Quality, Concerns=[state mutation exclusivity, write-then-publish, identifier depth, paused recovery idempotency]
- **Reviewer**: orchestrator with gap-context analysis (no external agents invoked — gap-context, API-cli, API-sqlite-schema, and DDR-003 were authoritative)
- **Knowledge graph**: queried — 8 items returned. Most useful: confirmation that pipeline-state NATS KV bucket detail was deferred to forge repo (out of FEAT-FORGE-001 scope), Forge is JetStream-native (recovery rides on JetStream redelivery), and the `agents.result.{agent_id}` singular convention is adopted across forge repo docs.

## Context Used

- **Gap-context document** (`docs/research/ideas/forge-001-gap-context.md`): primary basis for the reuse-vs-build classification in F1 and the proposed module layout in §4.
- **API-sqlite-schema.md** (DDL, write/read API, recovery semantics table): primary basis for F2 (state mutation exclusivity), F4 (PAUSED recovery), and F8 (STRICT type drift risk).
- **API-cli.md** (Click CLI contract, exit codes, write-before-publish ordering): primary basis for F3 (write-then-publish) and F6 (CLI module boundary).
- **DDR-003** (WAL + STRICT decision): primary basis for F7 (concurrency model) and the connection-helper sub-task in Wave 1.
- **Graphiti** — `pipeline-state KV bucket DEFERRED_TO forge repo`: validated that FEAT-FORGE-001 does NOT need to design the pipeline-state KV adapter (separate concern, owned elsewhere).
- **Graphiti** — `Forge IS_JETSTREAM_NATIVE — runtime state in messaging resident`: validated that crash recovery's "NACK + redeliver" path leans on JetStream durability, not on a separate persistence layer.
- **Past-failure pattern** (PEX-019 "regenerate from scratch" misfire): cautionary — recovery's "retry-from-scratch" policy on RUNNING crash must be carefully scoped to the build, not to the entire pipeline state, to avoid the same misapplication.

## Findings

### F1 — Gap is precisely scoped; there is no genuine architectural decision to make

The gap-context document's §1 TL;DR table classifies every layer as either ✅
shipped (config models, BuildState enum, cancel/skip executor logic, all
Protocol seams, all NATS adapters) or ❌ build (lifecycle package + CLI package
+ pyproject `console_scripts` entry). The §3 per-scenario gap table maps every
one of the 34 BDD scenarios to either an existing module (reuse) or a new
module under `src/forge/lifecycle/` or `src/forge/cli/`. **No scenario lacks a
designated owner; no scenario requires touching 002–007 territory.** The
review's job is therefore validation of the proposed boundary, not choice of
boundary.

The boundary is correct. `src/forge/lifecycle/` is the *across-build*
lifecycle (state machine, history, queue, recovery), distinct from
`src/forge/pipeline/` which is the *within-build* execution (supervisor,
stage ordering, dispatchers). This is a clean axis of separation: lifecycle
sits below pipeline in the dependency graph and never imports from it.

### F2 — State-mutation exclusivity (concern sc_001) is enforceable with a single rule

The spec (Group C "Invalid lifecycle jump refused", Group G "Terminal state ⇒
completion_time recorded") and the schema (`status TEXT NOT NULL CHECK (status
IN (...))`) together require that every status mutation goes through a
transition table with terminal-state invariants. The gap-context's proposed
`lifecycle/state_machine.py.transition()` function is the correct seam.

**Enforcement rule** (must be visible in the implementation):
> `lifecycle/persistence.py` exposes NO public method that takes a `status`
> argument. Instead, it exposes `apply_transition(transition: Transition) ->
> None` where `Transition` is the value object returned by
> `state_machine.transition()`. The state_machine module is the only producer
> of `Transition` instances. CLI commands import the state_machine, never the
> raw persistence writers.

This is testable as a property: every BDD scenario that mutates `builds.status`
must, in the implementation, route through `state_machine.transition()`. A
single static analysis test (`grep -r "UPDATE builds SET status" src/` returns
exactly the one location inside `apply_transition`) closes the loop.

### F3 — Write-then-publish failure path (concern sc_002) needs a distinct exit code and message

`API-cli.md §3.3` is explicit about ordering (write SQLite row, then publish
NATS) but silent on what the CLI does when step 5 (publish) fails. ASSUM-006
in the spec (confirmed) resolves it: the build row remains visible as pending
pickup so the operator can reconcile or re-queue. Group G scenario "A build
row is written but the pipeline publish then fails" formalises the
acceptance.

**Required CLI behaviour** (must be visible in the implementation):
> `cli/queue.py` catches `nats.errors.*` from `pipeline_publisher.publish()`
> AFTER the SQLite write has committed. On catch:
> 1. Do NOT roll back the SQLite row.
> 2. Print `Queued FEAT-XXX (build pending) but pipeline NOT NOTIFIED — publish failed: <reason>` to stderr.
> 3. Exit code 1 (NATS publish failure — distinct from exit code 0 success).
> 4. Group H scenario "Pipeline messaging unreachable" produces the same exit code 1 path.

This makes the SQLite row authoritative even when the bus is silent, and
keeps `forge status` (which is read-only against SQLite) functional and
truthful regardless of bus availability — Group H's "subsequent status queries
should still work without the messaging layer" requirement.

### F4 — PAUSED-recovery `request_id` idempotency (concern sc_004) needs explicit persistence

`API-sqlite-schema.md §6` recovery table says PAUSED recovery should "re-emit
ApprovalRequestPayload; re-fire interrupt() when graph reruns". This is silent
on whether the re-emitted request carries the original `request_id` or a fresh
one.

The spec scenario "A paused build survives a pipeline crash and re-issues its
approval request" (Group D) is also silent on this. **But the responder
correlation contract requires the same `request_id`** — otherwise an approval
response from Rich (who has been holding the original request_id from before
the crash) cannot be matched to the rehydrated PAUSED build.

**Required persistence + recovery contract** (must be visible in the
implementation):
> When `state_machine.transition(build, PAUSED, approval_request_id=...)` is
> invoked, persistence writes `request_id` into the build row (a column the
> current schema does not yet have — must be added). On crash recovery,
> `recovery.py` reads this `request_id` and passes it verbatim to
> `approval_publisher.publish(build_id, request_id=...)`. **The schema must
> grow a `pending_approval_request_id TEXT` column or the request_id must be
> embedded in `details_json` of the latest stage_log row.** The schema-column
> approach is preferred: explicit, indexable, easy to query.

This is one minor schema addition (additive, not breaking) that closes the
PAUSED-recovery idempotency gap. The migration is trivial because there are
no existing forge.db files to migrate against.

### F5 — Identifier validation depth (concern sc_003) needs decode-then-allowlist

The spec's Group E scenario "Queueing with a feature identifier that contains
path-traversal characters is refused" plus ASSUM-003 (confirmed) require
rejection of `../`, `/`, and `\` sequences. The user's specific concern asks
for decoded variants too: `%2F`, `%2E%2E`, and null bytes.

**Required validation rule** (must be visible in the implementation):
> `lifecycle/identifiers.py.validate_feature_id(s: str) -> str` performs:
> 1. **Decode pass**: `urllib.parse.unquote(s)` — this expands `%2F` → `/`,
>    `%2E%2E` → `..`, etc. Run twice to catch double-encoding.
> 2. **Null-byte rejection**: `if "\x00" in s_decoded: raise InvalidIdentifierError`.
> 3. **Allowlist match**: `re.fullmatch(r"[A-Za-z0-9_-]+", s_decoded)` — anything
>    not in the allowlist is rejected. This implicitly rejects `..`, `/`, `\`,
>    and any other special character.
> 4. **Length cap**: 64 characters (defensive; build_id ends up
>    `build-{feature_id}-{ts}` and worktree paths are bounded too).

Allowlist semantics are stronger than blocklist: any future encoding scheme
(URL-encoded, double-encoded, Unicode-normalised) that decodes to non-allowed
characters is rejected by construction. This is the only validation strategy
that's robust under decode-bypass attacks.

### F6 — CLI module boundary respects the read/write split rigidly

`API-cli.md §1` Split-IO contract is the architectural axis: read commands
(`status`, `history`) use `forge.adapters.sqlite.read_only_connect()` — no
NATS. Write commands (`queue`, `cancel`, `skip`) use NATS publish. Group H
scenario depends on this — `forge status` must work when NATS is unreachable.

**Module-level enforcement**:
> `cli/status.py` and `cli/history.py` MUST NOT import any module from
> `forge.adapters.nats.*`. A `__import_check__` test asserts this. The two
> read-path modules import only:
>   - `forge.lifecycle.persistence` (read API)
>   - `forge.config.loader`
>   - `click`, `rich.live`, `rich.table`

This makes `forge status`/`history` resilient by construction — they cannot
fail because of NATS issues because they don't know NATS exists.

### F7 — Concurrency model: SQLite WAL + IMMEDIATE for queue writes

DDR-003 fixes the WAL + `synchronous=NORMAL` decision. Group F scenarios
("Two simultaneous queues both durable, ordered" + "Concurrent reader sees
consistent snapshot") together require:

- **Two simultaneous `forge queue` invocations** must both succeed without one
  blocking the other unduly. SQLite WAL + the UNIQUE index on `(feature_id,
  correlation_id)` handles this — the second writer will retry under
  `busy_timeout=5000` and then either succeed (if different feature_id) or fail
  with `IntegrityError` (if duplicate).
- **A reader during an active write** must see the last committed snapshot,
  never a partial row. This is a WAL guarantee — no extra code needed.

**Recommendation**: open queue-write transactions as `BEGIN IMMEDIATE` to
acquire the write lock atomically; this avoids the SQLite-busy retry dance
when two processes write near-simultaneously and is the canonical pattern for
this concurrency model. Document this in `lifecycle/persistence.py.connect()`.

### F8 — Sequential per-project queue picker is a small but easily-mis-implemented module

ASSUM-004 (confirmed) scopes sequential discipline as **per-project**, not
global. The pipeline_consumer is a JetStream pull consumer on
`pipeline.build-queued.>` — its handler must call into a picker that decides
whether the next message is eligible to start, given the current SQLite
state.

**Picker contract**:
> `lifecycle/queue.py.next_build_to_pick(project: str) -> Build | None`
> returns None if any non-terminal build (`QUEUED`, `PREPARING`, `RUNNING`,
> `PAUSED`, `FINALISING`) exists for that project. Otherwise returns the
> oldest QUEUED build for that project (by `queued_at`).

The pull consumer's handler:
> 1. Receives a queued message for `project=X`.
> 2. Calls `queue.next_build_to_pick(X)`.
> 3. If returns None, NACK with delay (JetStream redelivers later).
> 4. If returns the matching build, ACK and start preparation.

**Subtle race**: two consumer instances (only one in current architecture, but
defensive) could both call the picker simultaneously. The IMMEDIATE
transaction recommendation in F7 covers this.

### F9 — Crash recovery is the largest single new module — split is justified

The recovery pass scans all non-terminal builds at startup and applies the
`API-sqlite-schema.md §6` table:
- QUEUED → no-op (JetStream redelivers)
- PREPARING → INTERRUPTED, publish `pipeline.build-failed` with `recoverable=True`, JetStream redelivers
- RUNNING → INTERRUPTED, retry-from-scratch (re-publish queue message? or rely on NACK?)
- PAUSED → re-enter PAUSED, re-publish approval request (with original `request_id` per F4)
- FINALISING → INTERRUPTED with PR-creation warning recorded
- COMPLETE/FAILED/CANCELLED/SKIPPED → ack residual JetStream message, no-op

Three distinct concerns:
- **State transition** (mark INTERRUPTED) — uses state_machine
- **Re-publication** (PAUSED only) — uses approval_publisher with preserved request_id
- **JetStream ack/nack arbitration** — talks to pipeline_consumer

Recovery is a fan-out pattern: one boot scan, multiple per-state handlers.
Single `recovery.py` module is fine; its complexity comes from the per-state
handler matrix, not from internal cohesion. A 7/10 complexity task.

### F10 — BDD scenario harness is the de-facto acceptance test suite

34 scenarios across 8 groups, with several Scenario Outlines fanning out
further (terminal-states-after-crash → 4 examples; turn-budget bounds → 4
examples; history-limit → 3 examples). pytest-bdd is the right harness; each
scenario maps 1:1 to a step-implementation file. Fixtures cover SQLite
in-memory + NATS in-process (using `nats-server` test container or an
in-process double).

Two fixture clusters:
- **SQLite fixture**: in-memory `:memory:` connection, schema applied once
  per session, rolled back per test.
- **Pipeline fixture**: stub publisher/consumer that records published
  payloads but never actually connects to NATS — sufficient for all 34
  scenarios since the test surface is "what gets published?" and "what state
  does SQLite end up in?", not "did the message round-trip through real NATS?"

This keeps the BDD harness fast and hermetic. Real NATS round-trip testing is
covered by smoke tests in 002–007 that already exist.

### F11 — `forge.yaml` schema needs minor extension; not a parallel module

The gap-context §2.1 says: extend `forge/config/models.py` in place; do NOT
add `forge.config.QueueConfig` as a parallel module. The needed extensions:

- A new `QueueConfig` Pydantic sub-model with:
  - `default_max_turns: int = Field(5, ge=1)` — minimum 1 (ASSUM-001)
  - `default_sdk_timeout_seconds: int = 1800`
  - `default_history_limit: int = 50`
  - `repo_allowlist: list[Path] = []` — paths that `forge queue --repo`
    must match against (Group C path-allowlist scenario)
- A `QueueConfig` field added to the `ForgeConfig` root model.
- A `load_config(path: Path) -> ForgeConfig` helper that reads YAML and
  validates via Pydantic.

This is a 3-complexity task. The Pydantic validator on `default_max_turns`
gives the Group B "turn budget < 1 rejected" scenario its rejection branch
for free.

### F12 — The 34-scenario coverage map has no gaps

I walked the 34 scenarios against the proposed module layout. Every scenario
maps to a named module and a single owning task. Coverage:

| Group | Scenarios | All mapped? | Owning waves |
|---|---|---|---|
| A — Key Examples | 6 | ✅ | Wave 1, 2, 4 |
| B — Boundary | 6 | ✅ | Wave 2, 4 |
| C — Negative | 7 | ✅ | Wave 1, 2, 4 |
| D — Edge Cases | 9 | ✅ | Wave 3, 4 |
| E — Security | 2 | ✅ | Wave 1, 4 |
| F — Concurrency | 2 | ✅ | Wave 2 (WAL config), Wave 1 (UNIQUE index) |
| G — Data Integrity | 2 | ✅ | Wave 2 (state machine invariant), Wave 4 (CLI failure mode) |
| H — Integration Boundaries | 1 | ✅ | Wave 4 (CLI error handling) |

No scenario lacks a task; no task lacks a scenario.

## Recommended Approach

### Option 1 — Dedicated `lifecycle/` + `cli/` packages (RECOMMENDED)

Build the proposed layout from the gap-context document verbatim:

```
src/forge/
├── cli/
│   ├── __init__.py
│   ├── main.py            # argparse/Click entry point, dispatches to subcommands
│   ├── queue.py           # forge queue (allowlist, validation, defaults, write-then-publish)
│   ├── status.py          # forge status (incl. --watch, --full, --json)
│   ├── history.py         # forge history
│   ├── cancel.py          # forge cancel  → CliSteeringHandler.handle_cancel
│   └── skip.py            # forge skip    → CliSteeringHandler.handle_skip
├── lifecycle/
│   ├── __init__.py
│   ├── schema.sql         # DDR-003 builds + stage_log + UNIQUE indices + WAL pragmas
│   ├── migrations.py      # apply schema; idempotent; schema_version table
│   ├── persistence.py     # SqliteLifecyclePersistence + concrete cli_steering Protocol implementations
│   ├── state_machine.py   # transition table + transition() guard + InvalidTransitionError
│   ├── queue.py           # next_build_to_pick(project) — sequential per-project picker
│   ├── recovery.py        # reconcile_on_boot() — per-state handler matrix
│   └── identifiers.py     # validate_feature_id, derive_build_id (with decoded-traversal rejection)
└── pipeline/              # ← UNCHANGED (002–007 territory)
    ├── cli_steering.py
    ├── supervisor.py
    └── ...
```

Plus `pyproject.toml` adds:
```toml
[project.scripts]
forge = "forge.cli.main:main"
```

Plus `forge/config/models.py` extends in place with a `QueueConfig` sub-model
and a `load_config()` helper.

**Pros**:
- Clean separation: lifecycle is *across-build*, pipeline is *within-build*
- Every module has a single responsibility and a single owning subtask
- Protocol seams from `cli_steering.py` are honoured (concrete implementations live in `persistence.py`)
- State-mutation exclusivity rule is enforceable structurally (only `state_machine.py` produces `Transition`)
- Read/write split is enforceable structurally (no NATS imports in `cli/status.py`/`history.py`)
- Sequential per-project queue picker has a natural home in lifecycle
- Aligns with DDR-003 connection-helper pattern

**Cons**:
- 13+ new files (mitigated by tight scope per file — none > 200 LOC expected)
- Requires careful coordination of state_machine being sole writer (mitigated by the static-analysis test in F2)

### Option 2 — Fold lifecycle modules into existing packages

Put `state_machine` into `pipeline/`, `persistence` into `adapters/sqlite/`,
`recovery` into `adapters/nats/`, etc.

**Pros**: Fewer new packages; co-locates persistence with adapters

**Cons**:
- Pollutes `pipeline/` which is explicitly "002–007 territory" per gap-context §5
- Loses the "across-build lifecycle" architectural axis — state machine becomes invisible inside pipeline/
- Persistence ends up half in adapters/sqlite (low-level connection management) and half elsewhere (Protocol implementations) — split awkwardly
- Recovery would need to import from both `pipeline/` and `adapters/nats/` — backward dependency
- **Rejected by gap-context §5**: explicit "do not redesign cancel/skip executor semantics; do not touch pipeline/"

### Option 3 — Single mega-module `forge.lifecycle`

All modules collapsed into one file.

**Pros**: Simpler imports

**Cons**:
- Untestable in isolation — state_machine tests would touch persistence
- Violates SRP — one module spanning seven distinct concerns
- Recovery's per-state handler matrix becomes unreadable inline
- File length > 1000 LOC; review and edit unfriendly

### Decision: Option 1

Option 1 is the only choice that:
1. Honours the gap-context §5 do-not-touch constraints
2. Enforces state-mutation exclusivity structurally
3. Enforces the read/write split structurally
4. Maps 1:1 to the 34 BDD scenarios via the §3 per-scenario gap table
5. Keeps each module testable in isolation

## Subtask Breakdown (13 tasks across 5 waves)

### Wave 1 — Foundation (3 tasks, parallel)

| ID | Title | Complexity | Estimated min |
|---|---|---|---|
| TASK-PSM-001 | Identifiers + path-traversal validation (`lifecycle/identifiers.py`) | 3 | 45 |
| TASK-PSM-002 | SQLite schema + migrations + connection helpers (`lifecycle/schema.sql`, `migrations.py`, `adapters/sqlite/connect.py`) | 5 | 75 |
| TASK-PSM-003 | Config extension — `QueueConfig` + `load_config()` (`config/models.py`, `config/loader.py`) | 3 | 45 |

### Wave 2 — State Machine + Persistence (2 tasks, parallel)

| ID | Title | Complexity | Estimated min | Depends on |
|---|---|---|---|---|
| TASK-PSM-004 | State machine — transition table, invariants, `InvalidTransitionError` (`lifecycle/state_machine.py`) | 6 | 90 | TASK-PSM-002 |
| TASK-PSM-005 | Persistence — concrete cli_steering Protocol implementations + write API (`lifecycle/persistence.py`) | 7 | 105 | TASK-PSM-002, TASK-PSM-004 |

### Wave 3 — Queue + Recovery (2 tasks, parallel)

| ID | Title | Complexity | Estimated min | Depends on |
|---|---|---|---|---|
| TASK-PSM-006 | Sequential per-project queue picker (`lifecycle/queue.py`) | 4 | 60 | TASK-PSM-005 |
| TASK-PSM-007 | Crash-recovery reconciliation across all non-terminal states (`lifecycle/recovery.py`) | 7 | 105 | TASK-PSM-004, TASK-PSM-005 |

### Wave 4 — CLI Surface (4 tasks, parallel)

| ID | Title | Complexity | Estimated min | Depends on |
|---|---|---|---|---|
| TASK-PSM-008 | CLI scaffold + `forge queue` (allowlist, identifier validation, defaults merge, write-then-publish, exit codes) | 6 | 90 | TASK-PSM-001, TASK-PSM-003, TASK-PSM-005 |
| TASK-PSM-009 | `forge status` (default view, `--watch`, `--full`, `--json`) | 5 | 75 | TASK-PSM-005 |
| TASK-PSM-010 | `forge history` (`--feature`, `--limit`, `--since`, `--format`) | 4 | 60 | TASK-PSM-005 |
| TASK-PSM-011 | `forge cancel` + `forge skip` thin wrappers (calling `CliSteeringHandler`) | 3 | 45 | TASK-PSM-005 |

### Wave 5 — Integration (2 tasks, parallel)

| ID | Title | Complexity | Estimated min | Depends on |
|---|---|---|---|---|
| TASK-PSM-012 | `[project.scripts]` entry + smoke-test `forge --help` (`pyproject.toml`) | 2 | 30 | TASK-PSM-008, TASK-PSM-009, TASK-PSM-010, TASK-PSM-011 |
| TASK-PSM-013 | BDD harness wiring all 34 scenarios via pytest-bdd | 5 | 75 | All Wave 1–4 |

**Aggregate complexity**: 8/10 (backbone, multi-package, cross-cutting concerns)
**Total estimated**: ~900 minutes ≈ 15 hours of pure coding (excluding test debugging, integration adjustment, code review)
**Realistic effort with quality gates**: ~55–60 hours single-developer linear; ~35–40 hours with 2-wide parallelism per wave

## Risk Register

| ID | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | State-mutation exclusivity violated — a CLI command writes `builds.status` directly, bypassing state_machine | **HIGH** | `persistence.py` exposes only `apply_transition(Transition)`; CLI commands import `state_machine`, never raw writers. Static-analysis test: `grep -r "UPDATE builds SET status" src/` returns exactly one location inside `apply_transition` |
| R2 | Write-then-publish race — NATS publish times out after SQLite write succeeded | **HIGH** | CLI catches `nats.errors.*` AFTER commit; row remains QUEUED; exits 1 with distinct messaging-layer error. Group G + Group H BDD scenarios formalise this |
| R3 | PAUSED-recovery duplicates `request_id` — recovery generates fresh request_id when re-publishing | **HIGH** | Persist `pending_approval_request_id` on the build row at pause time; recovery reuses it verbatim. Schema-column addition is additive (no existing data to migrate) |
| R4 | Path-traversal bypass via decoded variants — validation only checks raw `../` | **HIGH** | Decode-then-allowlist: `urllib.parse.unquote()` (twice for double-encoding) → null-byte rejection → `re.fullmatch(r"[A-Za-z0-9_-]+", s)` |
| R5 | Crash during INTERRUPTED transition — SQLite write fails mid-recovery | **MEDIUM** | Recovery is idempotent; a re-run scans non-terminal states again. Each per-state handler is pure (state in → state out) so retry is safe |
| R6 | Sequential-queue picker race — two consumer handlers grab the same project's next build | **MEDIUM** | `BEGIN IMMEDIATE` transaction on the picker query; UNIQUE INDEX on `(feature_id, correlation_id)` catches double-write. Currently single consumer instance, but defensive |
| R7 | Watch-mode polling overload — `--watch` at 1Hz hammers SQLite | **MEDIUM** | Default poll cadence 2s per CLI contract; exit immediately on terminal state; `read_only_connect()` is per-poll, no persistent reader connection |
| R8 | Schema migration during running build — migration runs while agent has open write connection | **MEDIUM** | Migrations run BEFORE agent runtime starts, on import of `lifecycle.migrations.apply_at_boot()`; explicit `schema_version` check; additive only |
| R9 | STRICT type drift — Pydantic field type drifts from SQLite STRICT column | **LOW** | Integration test serialises every payload type and round-trips through SQLite; STRICT will reject explicitly. DDR-003 anticipates this |
| R10 | SQLite WAL files lost during backup — backup script ignores `-wal`/`-shm` | **LOW** | Documented in DDR-003 consequences; ops/backup.md owns this concern; out of FEAT-FORGE-001 scope |

## Integration Contracts (Cross-Task Data Dependencies)

These contracts will appear in the IMPLEMENTATION-GUIDE.md `§4: Integration
Contracts` section and will drive `consumer_context` blocks on the consuming
tasks plus seam-test stubs.

### Contract: SCHEMA_INITIALIZED

- **Producer task**: TASK-PSM-002
- **Consumer task(s)**: TASK-PSM-005, TASK-PSM-006, TASK-PSM-007
- **Artifact type**: SQLite schema + `schema_version` row + connection helpers with WAL/STRICT pragmas applied
- **Format constraint**: `PRAGMA journal_mode = WAL`, `PRAGMA synchronous = NORMAL`, `PRAGMA foreign_keys = ON`, `PRAGMA busy_timeout = 5000` MUST be applied on every connection open. STRICT tables. `schema_version=1` row seeded.
- **Validation method**: `migrations.apply_at_boot()` is idempotent and verifiable; integration test opens a fresh DB, applies migrations, asserts `PRAGMA journal_mode == "wal"` and `schema_version == 1`

### Contract: STATE_TRANSITION_API

- **Producer task**: TASK-PSM-004
- **Consumer task(s)**: TASK-PSM-005, TASK-PSM-007, TASK-PSM-008, TASK-PSM-011
- **Artifact type**: Python module `lifecycle.state_machine` exporting `transition(build, to_state, **fields) -> Transition` and `InvalidTransitionError`
- **Format constraint**: `Transition` is a Pydantic value object carrying `(build_id, from_state, to_state, completed_at?, error?, pr_url?)`. Terminal transitions MUST set `completed_at`. Out-of-table transitions MUST raise `InvalidTransitionError`.
- **Validation method**: Coach asserts `state_machine.transition()` is the only producer of `Transition` instances; `persistence.apply_transition()` accepts only `Transition`, never raw kwargs

### Contract: PERSISTENCE_PROTOCOLS

- **Producer task**: TASK-PSM-005
- **Consumer task(s)**: TASK-PSM-008, TASK-PSM-009, TASK-PSM-010, TASK-PSM-011
- **Artifact type**: Python classes implementing the Protocols defined in `pipeline/cli_steering.py` — `BuildSnapshotReader`, `BuildCanceller`, `BuildResumer`, `StageLogReader`, `StageSkipRecorder`, `PauseRejectResolver`, `AsyncTaskCanceller`, `AsyncTaskUpdater`
- **Format constraint**: All concrete classes live in `lifecycle/persistence.py` as `SqliteBuildSnapshotReader`, `SqliteBuildCanceller`, etc. Each implements `runtime_checkable` Protocol from cli_steering. CLI commands receive instances via dependency injection, not direct construction.
- **Validation method**: `isinstance(impl, BuildSnapshotReader)` returns True for every Sqlite* class; pytest fixture wires concrete impls into `CliSteeringHandler` and exercises Group D edge-case scenarios

### Contract: CONFIG_LOADER

- **Producer task**: TASK-PSM-003
- **Consumer task(s)**: TASK-PSM-008, TASK-PSM-009, TASK-PSM-010, TASK-PSM-011
- **Artifact type**: `forge.config.loader.load_config(path: Path) -> ForgeConfig` returning a Pydantic model with `QueueConfig` sub-tree
- **Format constraint**: `ForgeConfig.queue.default_max_turns: int >= 1`; `ForgeConfig.queue.default_history_limit: int = 50`; `ForgeConfig.queue.repo_allowlist: list[Path]`. Pydantic validation happens at load time.
- **Validation method**: Boundary test loads a fixture YAML, asserts the parsed model matches expectations; another boundary test loads a malformed YAML and asserts a clear error message

### Contract: IDENTIFIER_VALIDATION

- **Producer task**: TASK-PSM-001
- **Consumer task(s)**: TASK-PSM-008
- **Artifact type**: `forge.lifecycle.identifiers.validate_feature_id(s: str) -> str` (returns the validated string, raises `InvalidIdentifierError` on rejection)
- **Format constraint**: After URL-decode (twice), the string MUST match `r"[A-Za-z0-9_-]+"`, MUST NOT contain `\x00`, and MUST be 1–64 characters long
- **Validation method**: Property test: every input from a curated list of attack vectors (`../`, `%2F`, `%252F`, `\x00FEAT`, `..%2F`, etc.) raises `InvalidIdentifierError`; every input from a curated list of valid identifiers passes through unchanged

### Contract: PENDING_APPROVAL_REQUEST_ID

- **Producer task**: TASK-PSM-005 (writes on PAUSED transition)
- **Consumer task(s)**: TASK-PSM-007 (reads during recovery)
- **Artifact type**: SQLite column `builds.pending_approval_request_id TEXT` (nullable; populated only when state == PAUSED)
- **Format constraint**: UUID string matching the original `ApprovalRequestPayload.request_id`. NULL when state is not PAUSED. CLEARED on resume.
- **Validation method**: Group D PAUSED-recovery scenario: pause a build, snapshot its `request_id`, simulate crash, run `recovery.reconcile_on_boot()`, assert the published approval request carries the same `request_id`

## BDD Scenario Coverage Assessment

All 34 scenarios from the feature spec map to subtasks. The mapping table is in
F12 above. Two scenarios warrant flagging:

- **Group D "Crash during finalising"** is the highest-stakes recovery
  scenario because the PR may already exist on GitHub. Recovery emits an
  INTERRUPTED record with a warning that `pr_url` (if recorded before the
  crash) requires manual reconciliation. The CLI flag `forge history
  --reconcile` was mentioned in the gap-context but is best deferred to a
  later feature — the warning record itself is sufficient for FEAT-FORGE-001.
- **Group F "Concurrent reader sees consistent snapshot"** is a WAL
  property; it requires no application-level code, only correct PRAGMA
  configuration. The test should specifically cover writes-during-reads to
  validate the snapshot guarantee.

## Decision Checkpoint

Review complete for: **Plan: Pipeline State Machine and Configuration**

Decision options:

  - **[A]ccept** — Approve findings only; review artefact saved as
    `tasks/in_review/TASK-REV-3EEE-plan-pipeline-state-machine-and-configuration.md`. Use later via `/feature-plan TASK-REV-3EEE`.
  - **[R]evise** — Re-run with deeper analysis on a specific area (e.g. recovery, persistence Protocol surface).
  - **[I]mplement** — Create the feature implementation structure: 13 subtasks under `tasks/backlog/pipeline-state-machine-and-configuration/`, IMPLEMENTATION-GUIDE with mandatory diagrams, FEAT-FORGE-001 YAML, and BDD scenario linking.
  - **[C]ancel** — Discard review; move to cancelled state.

Recommended: **[I]mplement** — the spec, gap-context, contracts, and DDR are
self-consistent; the design has no open questions; the 13-task breakdown maps
1:1 to the 34 BDD scenarios; the four user concerns each have a single
testable enforcement rule.
