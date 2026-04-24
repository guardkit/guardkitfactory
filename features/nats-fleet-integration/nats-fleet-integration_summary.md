# Feature Spec Summary: NATS Fleet Integration

**Feature ID**: FEAT-FORGE-002
**Stack**: python
**Generated**: 2026-04-24T00:00:00Z
**Scenarios**: 33 total (3 smoke, 0 regression)
**Assumptions**: 5 total (5 high / 0 medium / 0 low confidence)
**Review required**: No — all assumptions grounded in supplied context files

## Scope

Specifies Forge's role on the shared NATS fleet: self-registration on startup,
periodic heartbeats, graceful deregistration, live watching of fleet lifecycle
events, and capability resolution via the 30-second-TTL discovery cache with
degraded-mode fallback when specialists are absent or unresponsive. Also covers
the outbound pipeline-event stream (started / progress / stage-complete / paused
/ resumed / complete / failed / cancelled) and the inbound build-queue
subscription with terminal-only acknowledgement, duplicate detection, and
path-allowlist refusal. Behaviour is described in domain terms; transport
primitives (JetStream consumer config, KV buckets, PubAck semantics) appear only
as capability observations, not implementation steps.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 7 |
| Boundary conditions (@boundary) | 5 |
| Negative cases (@negative) | 8 |
| Edge cases (@edge-case) | 15 |
| Smoke (@smoke) | 3 |
| Regression (@regression) | 0 |
| Security (@security) | 2 |
| Concurrency (@concurrency) | 2 |
| Data integrity (@data-integrity) | 2 |
| Integration (@integration) | 2 |

Note: several scenarios carry multiple tags (e.g. boundary + negative,
edge-case + security). Group totals do not sum to 33.

## Group Layout

| Group | Theme | Scenarios |
|-------|-------|-----------|
| A | Key Examples — registration, heartbeat, live cache, stage-complete, build-complete, deregister | 7 |
| B | Boundary Conditions — stale-heartbeat threshold, progress interval, intent-confidence minimum | 5 |
| C | Negative Cases — unresolved capability, degraded-only match, malformed events, duplicate register, malformed queue payload, path-allowlist | 6 |
| D | Edge Cases — stale-cache re-read, tie-break by tier and queue depth, paused/resumed events, crash-recovery re-announce, correlation threading | 7 |
| E | Security / Concurrency / Data Integrity / Integration — secret-free manifest, originator allowlist, racing cache updates, terminal-ack idempotency, publish-failure does not regress history, redelivery idempotency, registry-outage heartbeats, paused-build queue hold | 8 |

## Deferred Items

None.

## Assumptions (all high confidence, all confirmed)

- **ASSUM-001** — heartbeat interval 30s (forge.yaml.fleet.heartbeat_interval_seconds)
- **ASSUM-002** — stale-heartbeat threshold 90s (forge.yaml.fleet.stale_heartbeat_seconds)
- **ASSUM-003** — discovery cache TTL 30s (DM-discovery §1)
- **ASSUM-004** — intent-fallback minimum confidence 0.7 (DM-discovery §3)
- **ASSUM-005** — build-progress publish cadence at least every 60s during RUNNING (API-nats-pipeline-events §3.1)

## Upstream Dependencies

- **FEAT-FORGE-001** — Pipeline State Machine & Configuration. FEAT-FORGE-002 extends the
  state machine with live bus publishing and subscribes to the inbound build-queue subject;
  the SQLite history and the state-machine transitions described in FEAT-FORGE-001 are
  referenced here only as the durable substrate for lifecycle events and crash-recovery
  re-announcement.

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "NATS Fleet Integration" \
      --context features/nats-fleet-integration/nats-fleet-integration_summary.md

`/feature-plan` Step 11 will link `@task:<TASK-ID>` tags back into the
`.feature` file after tasks are created.
