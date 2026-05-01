---
complexity: 7
consumer_context:
- consumes: JETSTREAM_DURABLE_NAME
  driver: nats-core (sibling editable install)
  format_note: String 'forge-serve' exactly — case-sensitive; durable name typo silently
    creates a second consumer (the ASSUM-006 failure mode)
  framework: nats-core JetStream client (forge.fleet's existing nats-core wrapper)
  task: TASK-F009-001
created: 2026-04-30 00:00:00+00:00
dependencies:
- TASK-F009-001
feature_id: FEAT-FORGE-009
id: TASK-F009-003
implementation_mode: task-work
parent_review: TASK-REV-F009
priority: high
status: completed
tags:
- forge-serve
- daemon
- jetstream
- durable-consumer
- feat-forge-009
task_type: feature
test_results:
  coverage: null
  last_run: null
  status: completed
title: Implement forge serve daemon body with JetStream durable consumer
updated: 2026-04-30 00:00:00+00:00
wave: 2
---

# Task: Implement `forge serve` daemon body with JetStream durable consumer

## Description

Fill in the daemon body in `src/forge/cli/_serve_daemon.py` (created
empty by T1). The daemon:

1. Connects to NATS via the `ServeConfig.nats_url` default
   (`nats://127.0.0.1:4222`) — ASSUM-001
2. Creates / attaches to the JetStream **shared durable consumer**
   `forge-serve` (Contract C) on subject pattern
   `pipeline.build-queued.*` — work-queue semantics so multiple replicas
   can run safely (ASSUM-006)
3. Pulls payloads, dispatches them to the existing forge orchestrator
   (the receipt is the test target — actual build dispatch is the
   orchestrator's job)
4. Sets `SubscriptionState.live = True` once the durable is attached;
   clears it on broker loss
5. Recovers on broker outage via JetStream's standard durable redelivery
   (ASSUM-007) — no custom forge-side window
6. Handles SIGTERM by acking in-flight payloads, closing the
   subscription cleanly, and exiting within 10 s

This is the producer of the `pipeline.build-queued` receipt path that
the CMDW gate verifies.

## Acceptance Criteria

- [ ] `forge serve` starts and stays running indefinitely until SIGTERM
      (A3, B1 scenarios)
- [ ] Daemon attaches to JetStream durable consumer `forge-serve` on
      `pipeline.build-queued.*` (Contract C consumer; ASSUM-006)
- [ ] Two concurrently running daemons receive each published payload
      exactly once between them (D2 scenario, ASSUM-006)
- [ ] When the broker becomes briefly unavailable and recovers, the
      daemon re-attaches without operator intervention; payloads
      published during the outage are delivered once the subscription
      restores (D3 scenario, ASSUM-007)
- [ ] When the daemon process crashes before acking a payload, the
      payload remains pending on the JetStream consumer for redelivery
      (E2.1 scenario)
- [ ] When a build's target provider is unavailable, only that build
      fails; the daemon remains available for subsequent builds (E3.1
      scenario)
- [ ] `SubscriptionState.live` flips to `True` once the subscription is
      attached and `False` on broker loss (Contract for T4 healthz)
- [ ] SIGTERM completes within 10 s with all in-flight payloads acked
      or returned to the consumer for redelivery
- [ ] Daemon refuses to start when `ServeConfig` validation fails;
      exits with non-zero status; diagnostic names the offending field
      (C5 scenario)
- [ ] All modified files pass project-configured lint/format checks
      with zero errors

## Test Requirements

- [ ] Unit tests with a mocked JetStream client covering: subscription
      attach, durable name plumbing, signal handling, state mutation
- [ ] Integration test with a real NATS broker (Testcontainers or
      sibling `nats-core` test fixture): publish → receive → ack
- [ ] Integration test for multi-replica work-queue semantics (D2):
      run two daemons against the same broker, publish one payload,
      assert exactly-once delivery
- [ ] Integration test for broker-outage recovery (D3): start daemon,
      stop broker, restart broker, publish, assert delivery
- [ ] SIGTERM test: `kill -TERM` the daemon mid-flight; assert clean
      shutdown within 10 s

## Seam Tests

The following seam test validates the integration contract with the
producer task (T1). Implement this test to verify the boundary before
integration.

```python
"""Seam test: verify JETSTREAM_DURABLE_NAME contract from TASK-F009-001."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("JETSTREAM_DURABLE_NAME")
def test_jetstream_durable_name_format():
    """Verify JETSTREAM_DURABLE_NAME matches the expected format.

    Contract: String 'forge-serve' exactly — case-sensitive; durable name
    typo silently creates a second consumer (the ASSUM-006 failure mode).
    Producer: TASK-F009-001
    """
    from forge.cli.serve import DEFAULT_DURABLE_NAME

    assert DEFAULT_DURABLE_NAME, "DEFAULT_DURABLE_NAME must not be empty"
    # Format assertion derived from §4 contract constraint:
    assert DEFAULT_DURABLE_NAME == "forge-serve", (
        f"Expected exact 'forge-serve' (case-sensitive), got: "
        f"{DEFAULT_DURABLE_NAME!r}"
    )
```

## Implementation Notes

The daemon must use the existing forge `nats-core` client wrapper
(see `src/forge/cli/queue.py:265` for the default NATS URL constant)
rather than re-implementing connection logic.

Reconnect/redelivery is **broker-configured** (JetStream durable
defaults). Do not implement a custom forge-side timeout window —
ASSUM-007 explicitly resolves to "inherit JetStream defaults".

Multi-replica safety relies entirely on the durable consumer being
**shared** (one consumer name, multiple subscribers). If this is wired
as one durable per replica, the no-double-processing guarantee
collapses — that's the exact failure mode D2 tests for.