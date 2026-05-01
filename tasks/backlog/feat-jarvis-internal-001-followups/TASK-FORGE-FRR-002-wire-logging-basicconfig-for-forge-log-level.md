---
id: TASK-FORGE-FRR-002
title: Wire `logging.basicConfig` in `forge serve` so `FORGE_LOG_LEVEL` actually produces visible logs
status: backlog
created: 2026-05-01T00:00:00Z
updated: 2026-05-01T00:00:00Z
priority: high
task_type: fix
tags:
  - forge-serve
  - logging
  - observability
  - feat-forge-009-followup
  - first-real-run-followup
  - quick-fix
complexity: 2
estimated_minutes: 60
estimated_effort: "30-60 minutes (config + 1-2 unit tests)"
parent_feature: FEAT-FORGE-009
correlation_id: a58ec9a7-27c6-485a-beac-e18675639a10
discovered_on:
  date: 2026-05-01
  machine: GB10 (promaxgb10-41b1)
  context: "co-resident first walkthrough of jarvis FEAT-JARVIS-INTERNAL-001 runbook"
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Wire `logging.basicConfig` in `forge serve` so `FORGE_LOG_LEVEL` actually produces visible logs

## Description

`forge serve` (FEAT-FORGE-009) parses `FORGE_LOG_LEVEL` from the
environment into `ServeConfig.log_level` (defaulting to `"info"`),
**but never actually configures Python's logging system**. As a
result, every `logger.info(...)`, `logger.warning(...)`, and
`logger.error(...)` call in `_serve_daemon.py` and `_default_dispatch`
goes nowhere — Python's root logger has no handler attached, so the
default WARNING-or-higher records get silently dropped at INFO level
and below, and even WARNING records emit only the
`logging.lastResort` stream (which is fine for ad-hoc scripts but
clobbers any structured output a daemon would want).

### Why this matters (empirical evidence — 2026-05-01 GB10 run)

During the jarvis FEAT-JARVIS-INTERNAL-001 first-real-run on 2026-05-01
on GB10 (correlation_id
`a58ec9a7-27c6-485a-beac-e18675639a10`), `docker logs forge-prod` was
**completely empty** even after the daemon had attached its durable
consumer, opened the healthz socket on `:8088`, and consumed +
acked one `pipeline.build-queued.FEAT-43DE` message. Verified
empirically: `docker logs forge-prod | wc -l` → `0` after the
end-to-end test completed. The per-receipt `logger.info` line that
`_default_dispatch` already emits (with the parsed `feature_id` and
`correlation_id`) was nowhere to be seen — not because the code
didn't run (consumer state proved it did: `delivered=1, acked=1`),
but because there was no handler configured to deliver the log
record to stderr.

This makes operator triage of `forge serve` purely guess-and-check:
the only signals available are the consumer-state JSON
(`nats consumer info ...`) and the healthz endpoint. For a daemon
process this is unacceptable.

The runbook explicitly calls this out — "The `-e FORGE_LOG_LEVEL=info`
flag has no observable effect" — and recommends "add a forge follow-up
to wire `logging.basicConfig(level=config.log_level)` in `serve.py` so
`FORGE_LOG_LEVEL` actually does something". This task is that
follow-up.

## Source code references

- **Where logging is parsed but never applied**:
  [`src/forge/cli/_serve_config.py`](../../../src/forge/cli/_serve_config.py)
  (`ServeConfig.log_level` parsed from `FORGE_LOG_LEVEL`).
- **Where the basicConfig call should go**:
  [`src/forge/cli/serve.py:43-94`](../../../src/forge/cli/serve.py)
  (`_run_serve` — top of the function, before any task is created), or
  alternatively [`serve_cmd`](../../../src/forge/cli/serve.py) right
  after `ServeConfig.from_env()`.
- **Loggers that currently emit nothing observable**:
  - `forge.cli._serve_daemon.logger` — emits the per-receipt info
    line, broker-error warnings, dispatch-failure warnings, signal-
    handler debug lines.
  - `forge.cli._serve_healthz.logger` (presumed — confirm during
    impl) — emits the healthz-socket-listening line.

## Goal

At the top of `_run_serve` (or wherever the serve subcommand
initialises its runtime, before any coroutine that emits logs is
created), call

```python
logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format="<sane forge format — see Implementation Notes>",
    stream=sys.stderr,
)
```

so that the daemon's existing `logger.info/warning/error` calls reach
the container's stderr (and therefore `docker logs forge-prod`,
`journalctl -u forge`, etc.).

## Acceptance Criteria

- [ ] **At `FORGE_LOG_LEVEL=info`**: `docker logs forge-prod`
  immediately after `docker run` shows:
  - the durable-consumer-attach log line (currently exists in
    `_serve_daemon.run_daemon` as a `state.set_live(True)` adjacent
    log, or wherever the attach logs — confirm during impl), AND
  - the healthz-listening log line emitted by
    `forge.cli._serve_healthz` when the AppRunner binds the port.

  Both currently exist in source as `logger.info(...)` calls but are
  silenced today.
- [ ] **At `FORGE_LOG_LEVEL=debug`**: in addition to the above, the
  consume-loop's debug lines (signal-handler installation
  fall-throughs at `_serve_daemon.py:303-308`, sub.unsubscribe error
  paths at `:377-379`, client.close error paths at `:387-389`)
  appear when their conditions trigger.
- [ ] **Per-receipt log line is visible**: publishing a single
  `pipeline.build-queued.FEAT-XXXX` message produces — in
  `docker logs forge-prod` — the `_default_dispatch` info line
  including the parsed `feature_id` and `correlation_id`. (This is
  the line at `_serve_daemon.py:175-180` that today emits to a
  silent root logger.)
- [ ] **Invalid `FORGE_LOG_LEVEL` does not crash the daemon**: a
  bogus value (`FORGE_LOG_LEVEL=banana`) falls back to INFO with a
  one-line warning to stderr ("unrecognised FORGE_LOG_LEVEL=banana,
  defaulting to INFO"). The daemon must not exit non-zero on an
  obviously-recoverable misconfiguration. Use `getattr(logging,
  level.upper(), logging.INFO)` with a separate explicit check + warn,
  or a validator on `ServeConfig`.
- [ ] **Format includes timestamp + logger name + level + message**:
  recommended format
  `"%(asctime)s [%(levelname)s] %(name)s: %(message)s"` so that
  log-grep across multiple replicas stays readable. Timestamp in ISO
  8601 (i.e. `datefmt="%Y-%m-%dT%H:%M:%S"` or default
  `asctime`).
- [ ] **No double-handler regression**: calling `_run_serve` more
  than once in the same process (which `tests/cli/test_serve.py`-style
  tests sometimes do) must not attach a second handler to the root
  logger and produce duplicated lines. `logging.basicConfig` is a
  no-op on the second call by default — preserve that property.
- [ ] **Unit test** in `tests/cli/test_serve.py` (or wherever
  F009-001's serve-cmd tests live): patches
  `os.environ["FORGE_LOG_LEVEL"]`, invokes `_run_serve` with a
  short-running stubbed daemon coroutine, captures `caplog` (or
  `pytest`'s `capfd`/`capsys`), and asserts at least one `INFO`-level
  record was emitted.
- [ ] **Runbook reference stays accurate**:
  `docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md` (or the F009
  validation runbook) — wherever `-e FORGE_LOG_LEVEL=info` is
  documented — should now have an example showing what the operator
  should expect to see in `docker logs` after this task lands. Keep
  it short; one-line example output is fine.

## Out of Scope

- Switching forge to structured (JSON) logging. The current
  free-text format with stdlib `logging` is fine for now;
  structured logging is a separate (much bigger) task and would
  require a logging-config schema, JSON formatter, and probably a
  third-party dep.
- Per-module log-level overrides (e.g.
  `FORGE_LOG_LEVEL_NATS=warning`). YAGNI for the daemon's current
  scope.
- Log shipping / aggregation. The container writes to stderr; what
  the host does with stderr is the host's problem.

## Implementation Notes

- **Use `force=False`** (the default) on `logging.basicConfig`. This
  preserves the property that re-entrant calls in the same process
  are no-ops, which matters for tests that run multiple
  `_run_serve` invocations in one pytest process.
- **Place the call BEFORE creating the daemon and healthz tasks**
  in `_run_serve` — handlers must be attached before any of those
  coroutines have a chance to emit. Equivalently, put it in
  `serve_cmd` immediately after `ServeConfig.from_env()` and before
  `asyncio.run(_run_serve(config, state))` — same effect, smaller
  blast radius.
- **Format choice rationale**: stdlib `logging.basicConfig` with a
  format string is the smallest possible change. If the team later
  moves to `structlog` or JSON logging, this single call becomes
  the swap point — keep it isolated.
- **Why stderr, not stdout**: container conventions (Kubernetes,
  Docker) treat stderr as the diagnostic channel; stdout is for
  application output. `forge serve` has no application stdout —
  everything it produces is diagnostic.
- The `force=` kwarg lets a future task move handler attachment to
  test fixtures and force-reset between tests; flag this in a
  comment but don't use it now.

## References

- **RESULTS file** that surfaced this issue:
  [/home/richardwoollcott/Projects/appmilla_github/jarvis/docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md](../../../../jarvis/docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md)
- **Specific RESULTS table rows that motivate this task**:
  - Phase 7.2 (`forge logs show consume + publish-back`):
    "Container `docker logs` is empty: `forge serve` parses
    `FORGE_LOG_LEVEL` into `ServeConfig.log_level` but does not call
    `logging.basicConfig()` or attach a handler, so
    `_default_dispatch`'s `logger.info` calls go nowhere. Forge
    gap-fold."
  - Phase 2.2 (`forge serve running`): "The runbook's `-e
    NATS_URL=...` is wrong; forge reads `FORGE_NATS_URL`. … Started
    with `-e FORGE_NATS_URL=… -e FORGE_HEALTHZ_PORT=8088 -e
    FORGE_LOG_LEVEL=info`."
  - Operator-side gaps row 4 (Phase 2.2): "use `FORGE_NATS_URL` and
    add a forge follow-up to wire `logging.basicConfig(level=
    config.log_level)` in `serve.py` so `FORGE_LOG_LEVEL` actually
    does something."
  - Recommended follow-up #2: "forge: add `logging.basicConfig(
    level=config.log_level)` in `serve.py` so `FORGE_LOG_LEVEL`
    produces visible logs."
- **Forge source files**:
  - [`src/forge/cli/serve.py`](../../../src/forge/cli/serve.py) (the
    target — `_run_serve` or `serve_cmd`)
  - [`src/forge/cli/_serve_config.py`](../../../src/forge/cli/_serve_config.py)
    (where `log_level` is parsed from `FORGE_LOG_LEVEL`)
  - [`src/forge/cli/_serve_daemon.py`](../../../src/forge/cli/_serve_daemon.py)
    (the loggers that today emit nothing observable)
- **Run that surfaced this**:
  - **correlation_id**: `a58ec9a7-27c6-485a-beac-e18675639a10`
  - **Date**: 2026-05-01
  - **Machine**: GB10 (`promaxgb10-41b1`), co-resident first walkthrough

## Test Execution Log

[Automatically populated by /task-work and downstream test runs]
