---
complexity: 5
consumer_context:
- consumes: CONFIG_LOADER
  driver: YAML + Pydantic
  format_note: ForgeConfig.queue.default_history_limit drives the recent-terminal-builds
    count for the default view
  framework: Pydantic v2
  task: TASK-PSM-003
- consumes: PERSISTENCE_PROTOCOLS
  driver: dependency injection via constructor
  format_note: read_status() returns active builds + last 5 terminal; read_stages(build_id)
    for --full; both use read_only_connect() (mode=ro URI)
  framework: Python typing.Protocol (runtime_checkable)
  task: TASK-PSM-005
dependencies:
- TASK-PSM-005
estimated_minutes: 75
feature_id: FEAT-FORGE-001
id: TASK-PSM-009
implementation_mode: task-work
parent_review: TASK-REV-3EEE
status: design_approved
tags:
- cli
- forge-status
- click
- watch-mode
- read-path
task_type: feature
title: '`forge status` command (default, --watch, --full, --json)'
wave: 4
---

# Task: `forge status` command (default, --watch, --full, --json)

## Description

Create `src/forge/cli/status.py` per [`API-cli.md §4`](../../../docs/design/contracts/API-cli.md).

Behaviour:

- **Default view**: active builds (`QUEUED`, `PREPARING`, `RUNNING`,
  `PAUSED`, `FINALISING`) + the last 5 terminal ones, sorted newest-first.
- **`<feature_id>`** positional: filter to that feature, all builds most
  recent first.
- **`--watch`**: poll `read_status()` every 2 seconds (per `API-cli.md §4.2`),
  re-render via `rich.live`. Exit when all visible builds are terminal.
- **`--full`**: include `stage_log` entries per build (last 5 stages by
  default, per Group B "Full status view caps stage detail at 5").
- **`--json`**: emit JSON array suitable for piping.

**Critical constraint** (review F6): this module MUST NOT import any
module from `forge.adapters.nats.*`. The read path is SQLite-only — it
must work even when the NATS bus is unreachable (Group H scenario
"subsequent status queries should still work without the messaging layer").

## Acceptance Criteria

- [ ] `forge status` (no args) shows active builds + 5 most recent
      terminal, formatted with `rich.table`
- [ ] `forge status FEAT-XXX` filters to that feature only
- [ ] `forge status --watch` polls every 2s, re-renders, exits on terminal
- [ ] `forge status --full` includes the last 5 stage_log entries per
      build (Group B "Full status view caps stage detail at 5")
- [ ] `forge status --json` emits a JSON array; each row matches the
      `BuildStatusView` Pydantic shape from
      `forge.lifecycle.persistence`
- [ ] **Import check** (Coach must verify): `cli/status.py` imports zero
      modules from `forge.adapters.nats.*` — verifiable via static
      analysis: `grep -r "from forge.adapters.nats" src/forge/cli/status.py`
      returns no matches
- [ ] BDD scenario: NATS unreachable + `forge status` succeeds (Group H)
- [ ] BDD scenario: status query during active write returns within
      reasonable bound (Group A "Status responsive while writer active")
- [ ] All modified files pass project-configured lint/format checks with
      zero errors

## Implementation Notes

- Use `rich.live.Live` for `--watch` mode; refresh cadence 2s per CLI
  contract.
- Reader connection is per-poll (short-lived). DDR-003 says "Read
  connections: per-CLI-invocation" — do not hold a long-lived reader.
- Active autobuild progress (per `API-cli.md §4.4` — "Wave 2/4, 8/12
  tasks done") is OUT OF SCOPE for this feature; it requires the
  `async_tasks` state channel which is FEAT-FORGE-007 territory. Stub
  the `STAGE` cell with the current stage_label only; document the gap
  in Implementation Notes.

## Coach Validation

- `cli/status.py` exists, exports `status_cmd` (Click command)
- No NATS imports (static-analysis check)
- `--watch` uses `rich.live.Live`
- `--full` clamps stage tail to 5
- `--json` output schema validated against `BuildStatusView`
- Lint/format pass