---
id: TASK-F009-004
title: Implement /healthz HTTP endpoint reporting JetStream subscription state
task_type: feature
status: backlog
priority: high
created: 2026-04-30T00:00:00Z
updated: 2026-04-30T00:00:00Z
parent_review: TASK-REV-F009
feature_id: FEAT-FORGE-009
wave: 2
implementation_mode: task-work
complexity: 5
dependencies: [TASK-F009-001]
tags: [forge-serve, healthz, http, healthcheck, feat-forge-009]
consumer_context:
  - task: TASK-F009-001
    consumes: HEALTHZ_PORT
    framework: "asyncio HTTP server (aiohttp or stdlib aiohttp.web)"
    driver: "Python asyncio"
    format_note: "Integer 8080 imported from forge.cli.serve.DEFAULT_HEALTHZ_PORT; overridable via FORGE_HEALTHZ_PORT env var. Must agree with the Dockerfile HEALTHCHECK directive (T5)."
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Implement `/healthz` HTTP endpoint reporting JetStream subscription state

## Description

Fill in the healthz HTTP server in `src/forge/cli/_serve_healthz.py`
(created empty by T1). The server:

1. Binds to TCP port 8080 (Contract B; ASSUM-005)
2. Exposes a single endpoint `GET /healthz` that returns:
   - `200 OK` (body: `{"status": "healthy"}`) when
     `SubscriptionState.live` is `True`
   - `503 Service Unavailable` (body: `{"status": "unhealthy",
     "reason": "subscription_not_live"}`) when
     `SubscriptionState.live` is `False`
3. Exposes no other paths (E1.3 scenario — no remote-access endpoints)
4. Runs concurrently with the daemon under `asyncio.gather` orchestrated
   by `serve_cmd` (T1's wiring)

This is the consumer of T1's `HEALTHZ_PORT` constant and `SubscriptionState`
shared object.

## Acceptance Criteria

- [ ] `GET /healthz` returns 200 when `SubscriptionState.live == True`
      (B5: live and ready → healthy)
- [ ] `GET /healthz` returns 503 when `SubscriptionState.live == False`
      (B5: not yet established → unhealthy; dropped without recovery →
      unhealthy)
- [ ] Server binds to port `forge.cli.serve.DEFAULT_HEALTHZ_PORT`
      (Contract B; integer 8080)
- [ ] Port is overridable via `FORGE_HEALTHZ_PORT` env var (operator-
      escape valve for R7)
- [ ] No path other than `/healthz` is served — `GET /` returns 404,
      no `/metrics` or `/debug` (E1.3 scenario)
- [ ] Server shuts down cleanly on SIGTERM (no port-leak after restart)
- [ ] All modified files pass project-configured lint/format checks
      with zero errors

## Test Requirements

- [ ] Unit test: when `SubscriptionState.live = True`, `/healthz` returns
      200; when `False`, returns 503
- [ ] Unit test: any other path returns 404 (E1.3)
- [ ] Integration test: spin the server up, hit it with `httpx`, assert
      200/503 transitions match `SubscriptionState` mutations
- [ ] Port-override test: set `FORGE_HEALTHZ_PORT=9090`, assert server
      binds to 9090

## Seam Tests

```python
"""Seam test: verify HEALTHZ_PORT contract from TASK-F009-001."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("HEALTHZ_PORT")
def test_healthz_port_format():
    """Verify HEALTHZ_PORT matches the expected format.

    Contract: Integer 8080 imported from
    forge.cli.serve.DEFAULT_HEALTHZ_PORT; overridable via
    FORGE_HEALTHZ_PORT env var. Must agree with the Dockerfile
    HEALTHCHECK directive (T5).
    Producer: TASK-F009-001
    """
    from forge.cli.serve import DEFAULT_HEALTHZ_PORT

    assert DEFAULT_HEALTHZ_PORT, "DEFAULT_HEALTHZ_PORT must not be empty"
    # Format assertion derived from §4 contract constraint:
    assert isinstance(DEFAULT_HEALTHZ_PORT, int), (
        f"Expected int, got: {type(DEFAULT_HEALTHZ_PORT).__name__}"
    )
    assert DEFAULT_HEALTHZ_PORT == 8080, (
        f"Expected 8080 (matches Dockerfile HEALTHCHECK), got: "
        f"{DEFAULT_HEALTHZ_PORT}"
    )
    assert 1 <= DEFAULT_HEALTHZ_PORT <= 65535, "port must be in TCP range"
```

## Implementation Notes

Use `aiohttp.web` (already in the LangChain ecosystem's transitive deps)
or stdlib `http.server` wrapped in an executor — keep dependency surface
small. **Do not** add a new HTTP framework dependency.

`SubscriptionState` is mutated by T3's daemon body and read here. The
shared module pattern from T1 (`_serve_state.py`) means there's no
explicit RPC between the two; both processes (or asyncio tasks) hold a
reference to the same dataclass instance, set up by `serve_cmd` and
passed into both coroutines.
