---
id: TASK-F009-001
title: Add forge serve skeleton, ServeConfig, and shared SubscriptionState
task_type: scaffolding
status: completed
priority: high
created: 2026-04-30T00:00:00Z
updated: 2026-04-30T00:00:00Z
parent_review: TASK-REV-F009
feature_id: FEAT-FORGE-009
wave: 1
implementation_mode: direct
complexity: 3
dependencies: []
tags: [forge-serve, scaffolding, cli, feat-forge-009]
test_results:
  status: completed
  coverage: null
  last_run: null
---

# Task: Add `forge serve` skeleton, `ServeConfig`, and shared `SubscriptionState`

## Description

Lay the scaffolding for the new `forge serve` long-lived daemon subcommand.
This is the producer of Integration Contracts B (`HEALTHZ_PORT = 8080`) and
C (`JETSTREAM_DURABLE_NAME = "forge-serve"`) for the rest of the wave. No
daemon body, no HTTP server — only the boundary surface that Wave-2 tasks
will fill in.

Files created/edited:
- NEW `src/forge/cli/serve.py` — Click `serve_cmd` group; imports proxies
  from `_serve_daemon` and `_serve_healthz`; runs them via `asyncio.gather`
- NEW `src/forge/cli/_serve_state.py` — `SubscriptionState` dataclass with
  `live: bool` (and a thread/asyncio-safe setter) — shared between daemon
  (writer) and healthz (reader)
- NEW `src/forge/cli/_serve_daemon.py` — stub `async def run_daemon(config,
  state)` that returns immediately; T3 fills the body
- NEW `src/forge/cli/_serve_healthz.py` — stub `async def run_healthz_server(
  config, state)` that returns immediately; T4 fills the body
- NEW `src/forge/cli/_serve_config.py` — `ServeConfig` Pydantic model with
  the public constants `DEFAULT_HEALTHZ_PORT = 8080` and
  `DEFAULT_DURABLE_NAME = "forge-serve"` (Contracts B and C)
- EDIT `src/forge/cli/main.py` — register `_serve.serve_cmd` alongside the
  existing 5 subcommands (lines 80–93)

The four boundary files exist so Wave-2 tasks T3, T4, T5 can edit only
their own file with no collisions on `serve.py`.

## Acceptance Criteria

- [ ] `forge serve --help` runs and shows the `serve` subcommand with a
      one-line description
- [ ] `forge --help` lists `serve` alongside `queue`, `status`, `history`,
      `cancel`, `skip` (ASSUM-008, A2 scenario)
- [ ] `from forge.cli.serve import DEFAULT_HEALTHZ_PORT` returns `8080`
      (Contract B producer)
- [ ] `from forge.cli.serve import DEFAULT_DURABLE_NAME` returns
      `"forge-serve"` (Contract C producer)
- [ ] `ServeConfig` is a Pydantic v2 model with fields `nats_url: str =
      "nats://127.0.0.1:4222"`, `healthz_port: int = 8080`, `durable_name:
      str = "forge-serve"`, `log_level: str = "info"`; env-var overrides
      via `FORGE_NATS_URL`, `FORGE_HEALTHZ_PORT`, `FORGE_LOG_LEVEL`
- [ ] `SubscriptionState` exposes `live: bool` defaulted to `False` and is
      safe to mutate from one task and read from another (`asyncio.Lock`
      or atomic-read pattern)
- [ ] `serve_cmd` runs both `run_daemon` and `run_healthz_server` via
      `asyncio.gather` — when both stubs return immediately, the command
      exits 0 (this is the scaffold's "smoke test")
- [ ] Unit test in `tests/forge/test_cli_serve_skeleton.py` asserts the
      contract constants and the registration in `main.py`

## Test Requirements

- [ ] Contract producer test: `DEFAULT_HEALTHZ_PORT == 8080` and
      `DEFAULT_DURABLE_NAME == "forge-serve"` are both module-level
      constants importable as `forge.cli.serve.DEFAULT_*`
- [ ] CLI registration test: `forge --help` output contains the literal
      string `serve`
- [ ] Pydantic model test: `ServeConfig()` instantiates with defaults;
      env-var overrides work via `model_validate({}, context=...)` or
      explicit `os.environ` patching

## Implementation Notes

This is a scaffolding task. CoachValidator skips architectural review for
`task_type: scaffolding`. Keep the daemon and healthz stubs as no-op
coroutines — Wave-2 tasks own the implementations.

The boundary-file split exists *specifically* so T3 and T4 can run in
parallel in Wave 2 without colliding on `serve.py`. Do not consolidate
back into a single file later.
