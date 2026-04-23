# DDR-003 — SQLite schema layout + WAL + STRICT tables

## Status

Accepted

- **Date:** 2026-04-23
- **Session:** `/system-design`, design-pass 1
- **Related:** ADR-ARCH-009 (omit LangGraph checkpointer), ADR-ARCH-013 (CLI read bypasses NATS), ADR-SP-013

---

## Context

Forge uses SQLite as the authoritative build-history store. Concurrency is asymmetric:

- Single writer — the agent runtime — inside a single process.
- Multiple readers — every `forge status` / `forge history` invocation from the CLI, potentially concurrent with the writer.

The schema has two core tables (`builds`, `stage_log`) plus a small `history_snapshots` table for calibration ingestion bookkeeping. Options for durability + concurrency:

- **Default rollback journal + synchronous=FULL** — strongest durability, but readers block during writes.
- **WAL + synchronous=NORMAL** — readers never block; writes fsync at checkpoint boundaries; crash-safe with modern OS fsync semantics.
- **WAL + synchronous=FULL** — unnecessary cost for Forge's workload (sequential builds, ~100 stage writes/build).

SQLite 3.37+ supports `STRICT` tables that enforce typed columns; important because Forge serialises Pydantic models in and expects types on the way back out.

## Decision

- **`PRAGMA journal_mode = WAL`** + **`PRAGMA synchronous = NORMAL`** set on every connection open.
- **`PRAGMA foreign_keys = ON`** + **`PRAGMA busy_timeout = 5000`**.
- All tables declared `STRICT`.
- Single persistent write connection held by the agent runtime, serialised by an asyncio lock. Readers open new connections in `mode=ro` on every CLI invocation.
- Schema versioned via `schema_version` table; migrations are additive and run at boot before any domain writes.

Schema DDL, write API, and read API captured in [API-sqlite-schema.md](../contracts/API-sqlite-schema.md).

## Rationale

- **WAL is industry-standard for this exact workload** — single writer, many short-lived readers. Readers see a consistent snapshot from the last commit; writes append to the WAL file without blocking readers.
- **`synchronous = NORMAL` is safe with WAL** — durability loss bound to the most recent uncommitted transaction on power loss; this is acceptable because SQLite is not the only durability layer — JetStream holds the unacked message for redelivery.
- **STRICT tables catch serialisation bugs early** — Forge writes Pydantic-validated payloads but the conversion to SQLite storage is where type drift typically appears. STRICT rejects it at write time.
- **Single persistent write connection** avoids connection-pool overhead for a process that writes on the order of 100 rows per build. The asyncio lock makes the serialisation explicit rather than relying on SQLite's busy-timeout dance.
- **Readers open short-lived `mode=ro` connections** — consistent with ADR-ARCH-013; the CLI is short-lived, no connection to manage.

## Alternatives considered

- **Default rollback journal** — rejected; blocks readers during writes, inconsistent with sub-200ms `forge status` target.
- **PostgreSQL / DuckDB** — rejected; SQLite is sufficient, requires no separate server, runs in-container with zero ops.
- **STRICT off** — rejected; the cost of silent type drift at the storage boundary outweighs the minor schema-authoring constraint.
- **Separate write connection per transaction** — rejected; connection setup is non-trivial for SQLite with WAL + pragmas; a held connection is simpler.

## Consequences

- **+** `forge status` and `forge history` remain fast and non-blocking throughout a build.
- **+** Crash safety is bounded and well-understood; reconciliation at boot uses the unacked-message path to rebuild state.
- **+** STRICT tables surface Pydantic-model drift as explicit errors.
- **−** Requires SQLite ≥ 3.37 for STRICT; the GB10 Docker base image already provides this.
- **−** WAL creates additional files (`-wal`, `-shm`) alongside `forge.db`; backup scripts include them.

## Related components

- SQLite Adapter (`forge.adapters.sqlite`)
- CLI Read path (`forge.cli`)
- Build lifecycle data model — [DM-build-lifecycle.md](../models/DM-build-lifecycle.md)
