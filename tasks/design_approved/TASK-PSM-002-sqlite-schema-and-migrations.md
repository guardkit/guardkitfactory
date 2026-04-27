---
complexity: 5
dependencies: []
estimated_minutes: 75
feature_id: FEAT-FORGE-001
id: TASK-PSM-002
implementation_mode: task-work
parent_review: TASK-REV-3EEE
status: design_approved
tags:
- lifecycle
- sqlite
- schema
- migrations
- ddr-003
task_type: scaffolding
title: SQLite schema, migrations, and connection helpers
wave: 1
---

# Task: SQLite schema, migrations, and connection helpers

## Description

Create the SQLite substrate for FEAT-FORGE-001 per
[API-sqlite-schema.md](../../../docs/design/contracts/API-sqlite-schema.md)
and [DDR-003](../../../docs/design/decisions/DDR-003-sqlite-schema-layout-wal.md):

1. `src/forge/lifecycle/schema.sql` — DDL for `builds`, `stage_log`,
   `schema_version` tables (STRICT, with all indices).
2. `src/forge/lifecycle/migrations.py` — `apply_at_boot(connection)` runs the
   schema idempotently; reads `schema_version` table; only applies missing
   migrations.
3. `src/forge/adapters/sqlite/connect.py` — two helpers:
   - `connect_writer(db_path: Path) -> sqlite3.Connection` — opens the
     persistent agent-runtime write connection with WAL pragmas applied.
   - `read_only_connect(db_path: Path) -> sqlite3.Connection` — opens a
     short-lived read-only connection for CLI invocations using `mode=ro`
     URI filename.

**Schema deviation from current API-sqlite-schema.md**: add a
`pending_approval_request_id TEXT` column on `builds` (nullable, populated
only when state=PAUSED). This is required for review finding F4 — PAUSED
crash recovery must re-issue with the original `request_id`. This is the
producer side of the `PENDING_APPROVAL_REQUEST_ID` integration contract
consumed by TASK-PSM-007.

Implements concerns **sc_004** (PAUSED-recovery idempotency) at the schema
layer.

## Acceptance Criteria

- [ ] `schema.sql` contains `CREATE TABLE IF NOT EXISTS builds (...) STRICT`
      with all columns from `API-sqlite-schema.md §2.1` PLUS the new
      `pending_approval_request_id TEXT` column
- [ ] `schema.sql` contains `CREATE TABLE IF NOT EXISTS stage_log (...) STRICT`
      with all columns and indices from `API-sqlite-schema.md §2.2`
- [ ] `schema.sql` contains `CREATE TABLE IF NOT EXISTS schema_version` with
      a seed row `INSERT OR IGNORE INTO schema_version VALUES (1, datetime('now'))`
- [ ] `schema.sql` contains the UNIQUE INDEX on `(feature_id, correlation_id)`
- [ ] `migrations.apply_at_boot(connection)` is idempotent (running twice
      is a no-op) and verifiable
- [ ] Both connection helpers apply the four mandatory pragmas (per DDR-003):
      `journal_mode = WAL`, `synchronous = NORMAL`, `foreign_keys = ON`,
      `busy_timeout = 5000`
- [ ] `read_only_connect()` opens with `mode=ro` URI
      (`sqlite3.connect(f"file:{path}?mode=ro", uri=True)`)
- [ ] Integration test: open fresh DB, apply migrations, assert
      `PRAGMA journal_mode == "wal"` and `SELECT version FROM schema_version`
      returns `1`
- [ ] Integration test: STRICT enforcement — inserting a row with a non-INTEGER
      `max_turns` raises `sqlite3.IntegrityError`
- [ ] Integration test: WAL files (`forge.db-wal`, `forge.db-shm`) are
      created alongside the main DB after first write
- [ ] All modified files pass project-configured lint/format checks with
      zero errors

## Implementation Notes

- Place `schema.sql` as a real `.sql` file (not embedded in Python) and
  load via `importlib.resources.files("forge.lifecycle") / "schema.sql"`
  so it's robust to package installation.
- `migrations.apply_at_boot` should run inside a transaction; if a
  migration fails, rollback and raise.
- The DDR-003 connection helpers are reused by EVERY consumer in this
  feature — keep the API minimal and the helper signatures stable.

## Producer of integration contracts

- **SCHEMA_INITIALIZED** — consumed by TASK-PSM-005, TASK-PSM-006,
  TASK-PSM-007. See IMPLEMENTATION-GUIDE.md §4.

## Coach Validation

- `schema.sql` and `migrations.py` exist with correct content
- `connect.py` lives under `src/forge/adapters/sqlite/`
- All four pragmas applied on every `connect_*` call (verifiable via
  `PRAGMA <name>` round-trip)
- `pending_approval_request_id` column present on `builds`
- Integration tests pass; STRICT enforcement verified