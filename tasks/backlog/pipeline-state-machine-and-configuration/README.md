# FEAT-FORGE-001 — Pipeline State Machine and Configuration

> **Generated**: 2026-04-27 by `/feature-plan` from review TASK-REV-3EEE
> **Status**: planned (13 tasks pending)
> **Aggregate complexity**: 8/10
> **Estimated effort**: 35–40 hours with 2-wide parallelism per wave

## Problem Statement

Forge needs a durable build lifecycle from queue to terminal — including
the state machine transitions, SQLite-backed history, crash recovery,
sequential-queue discipline, and the user-facing CLI surface
(`forge queue`, `forge status`, `forge history`, `forge cancel`,
`forge skip`).

This is the foundation of Forge's operator-facing surface and the source
of truth for "what is the pipeline doing right now?". Sibling features
002–007 already ship the *upstream-of-CLI* surface (NATS adapters, config
models, stage-ordering guards, executor-layer cancel/skip handler) but
deliberately did not build the lifecycle layer or the CLI itself —
FEAT-FORGE-001 closes the gap.

## Solution Approach

**Option 1** from the review (recommended, accepted): build a dedicated
`src/forge/lifecycle/` package and `src/forge/cli/` package, reusing the
002–007 surface unchanged. The lifecycle package is the *across-build*
concern (state machine, history, queue, recovery), distinct from the
existing `src/forge/pipeline/` which is the *within-build* concern
(supervisor, stage ordering, dispatchers).

```
src/forge/
├── cli/                    ← NEW
│   ├── main.py             # Click entry point
│   ├── queue.py            # forge queue
│   ├── status.py           # forge status
│   ├── history.py          # forge history
│   ├── cancel.py           # forge cancel
│   └── skip.py             # forge skip
├── lifecycle/              ← NEW
│   ├── schema.sql          # DDR-003 SQLite DDL
│   ├── migrations.py
│   ├── persistence.py      # concrete cli_steering Protocol implementations
│   ├── state_machine.py    # transition table + InvalidTransitionError
│   ├── queue.py            # sequential per-project picker
│   ├── recovery.py         # crash reconciliation
│   └── identifiers.py      # path-traversal validation
└── pipeline/               ← UNCHANGED (002-007 territory)
```

Plus `pyproject.toml` `[project.scripts]` entry for the `forge` binary.
Plus a small extension to `forge/config/models.py` (a `QueueConfig`
sub-model + `load_config()` helper).

## Key Architectural Invariants

Four user-supplied review concerns are first-class invariants enforced
structurally:

- **sc_001** — `state_machine.py` is the SOLE caller of writes that
  mutate `builds.state`
- **sc_002** — write-then-publish: SQLite row survives NATS publish
  failure (exit code 1; row remains for reconciliation)
- **sc_003** — identifier validation rejects URL-encoded `%2F` / `%2E%2E`
  variants and null bytes (decode-then-allowlist)
- **sc_004** — PAUSED-recovery preserves the original `request_id`
  (additive schema column `pending_approval_request_id`)

See [IMPLEMENTATION-GUIDE.md](./IMPLEMENTATION-GUIDE.md) §
Architectural Invariants for the enforcement table.

## Subtask Summary

5 waves, 13 tasks. See [IMPLEMENTATION-GUIDE.md](./IMPLEMENTATION-GUIDE.md)
for the full dependency graph.

### Wave 1 — Foundation (3 parallel)

- [TASK-PSM-001](./TASK-PSM-001-identifiers-and-traversal-validation.md) —
  Identifiers + path-traversal validation
- [TASK-PSM-002](./TASK-PSM-002-sqlite-schema-and-migrations.md) —
  SQLite schema + migrations + connection helpers
- [TASK-PSM-003](./TASK-PSM-003-config-extension-queue-and-loader.md) —
  Config extension (QueueConfig + load_config)

### Wave 2 — State Machine + Persistence (2 parallel)

- [TASK-PSM-004](./TASK-PSM-004-state-machine-transition-table.md) —
  State machine — transition table and invariants
- [TASK-PSM-005](./TASK-PSM-005-persistence-protocol-implementations.md) —
  Persistence — concrete cli_steering Protocol implementations

### Wave 3 — Queue + Recovery (2 parallel)

- [TASK-PSM-006](./TASK-PSM-006-sequential-queue-picker.md) — Sequential
  per-project queue picker
- [TASK-PSM-007](./TASK-PSM-007-crash-recovery-reconciliation.md) —
  Crash-recovery reconciliation across all non-terminal states

### Wave 4 — CLI Surface (4 parallel)

- [TASK-PSM-008](./TASK-PSM-008-cli-scaffold-and-forge-queue.md) — CLI
  scaffold + `forge queue`
- [TASK-PSM-009](./TASK-PSM-009-forge-status-command.md) —
  `forge status` (default, --watch, --full, --json)
- [TASK-PSM-010](./TASK-PSM-010-forge-history-command.md) —
  `forge history` (--feature, --limit, --since, --format)
- [TASK-PSM-011](./TASK-PSM-011-forge-cancel-and-skip-wrappers.md) —
  `forge cancel` + `forge skip` thin wrappers

### Wave 5 — Integration

- [TASK-PSM-012](./TASK-PSM-012-pyproject-console-scripts-entry.md) —
  `pyproject.toml` `console_scripts` entry
- [TASK-PSM-013](./TASK-PSM-013-bdd-harness-all-34-scenarios.md) — BDD
  harness wiring all 34 scenarios

## BDD Scenario Coverage

All 34 scenarios from
[`pipeline-state-machine-and-configuration.feature`](../../../features/pipeline-state-machine-and-configuration/pipeline-state-machine-and-configuration.feature)
across 8 groups (Key Examples, Boundary Conditions, Negative Cases, Edge
Cases, Security, Concurrency, Data Integrity, Integration Boundaries) are
mapped to subtasks. The mapping table is in the
[review report](../../../.claude/reviews/TASK-REV-3EEE-review-report.md)
finding F12.

`/feature-plan` Step 11 will tag each scenario in the `.feature` file
with `@task:TASK-PSM-NNN` so the BDD oracle (R2) wires the right
scenarios to the right tasks during autobuild.

## Reference Documents

- [Feature spec summary](../../../features/pipeline-state-machine-and-configuration/pipeline-state-machine-and-configuration_summary.md)
- [Feature .feature file (34 scenarios)](../../../features/pipeline-state-machine-and-configuration/pipeline-state-machine-and-configuration.feature)
- [Assumptions manifest](../../../features/pipeline-state-machine-and-configuration/pipeline-state-machine-and-configuration_assumptions.yaml)
- [Gap-context document](../../../docs/research/ideas/forge-001-gap-context.md)
- [API-cli.md](../../../docs/design/contracts/API-cli.md)
- [API-sqlite-schema.md](../../../docs/design/contracts/API-sqlite-schema.md)
- [DDR-003 SQLite schema layout + WAL](../../../docs/design/decisions/DDR-003-sqlite-schema-layout-wal.md)
- [Review report](../../../.claude/reviews/TASK-REV-3EEE-review-report.md)

## Execution

```bash
# Recommended — autobuild end-to-end
guardkit autobuild feature FEAT-FORGE-001

# Or run individual tasks
/task-work TASK-PSM-001
/task-work TASK-PSM-002
# ... etc.
```
