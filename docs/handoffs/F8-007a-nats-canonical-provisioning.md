# Handoff: Canonical NATS provisioning for Forge (TASK-F8-007a)

**From:** `forge` (FEAT-FORGE-008 validation, Phases 4–6)
**To:** `nats-infrastructure` (canonical NATS provisioning owner)
**Status:** Specification — `forge` enumerates what it requires;
            `nats-infrastructure` owns provisioning, hardening, and operations.
**Created:** 2026-04-30
**Parent task:** [TASK-F8-007a](../../tasks/backlog/feat-f8-validation-fixes/TASK-F8-007a-nats-canonical-provisioning-handoff.md)
**Parent review:** [TASK-REV-F008](../../tasks/backlog/TASK-REV-F008-fix-feat-forge-008-validation-failures.md)

## 1. Purpose

The FEAT-FORGE-008 validation runbook
([`docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md`](../runbooks/RUNBOOK-FEAT-FORGE-008-validation.md))
Phases 4–6 require a canonical, JetStream-provisioned NATS server with
persistent streams + KV stores matching the `nats-core` topology.

The 2026-04-29 walkthrough used a throwaway `nats:latest -js` container
for Phases 2–3 only — that container does **not** satisfy Phase 4+
because a fresh-volume NATS without explicit provisioning will accept
publishes (PubAck) but neither retain nor deliver them.

Per `Q4=delegate` on [TASK-REV-F008](../../tasks/backlog/TASK-REV-F008-fix-feat-forge-008-validation-failures.md),
canonical NATS provisioning is owned by the sibling
[`nats-infrastructure`](../../../nats-infrastructure/) repo, **not** by
`forge`. This document is `forge`'s contract: what it publishes, what it
consumes, what it persists, and what it expects to be provisioned for it.

`nats-infrastructure` owns the actual provisioning, the v2.1-anchor
retention reconciliation (FLEET / JARVIS / NOTIFICATIONS), the
deployment to GB10 + production targets, and the operations.

## 2. Connection contract

| Field             | Value                                              | Source                                    |
|-------------------|----------------------------------------------------|-------------------------------------------|
| Default URL       | `nats://127.0.0.1:4222`                            | `src/forge/cli/queue.py:265`              |
| Override env var  | `FORGE_NATS_URL`                                   | `src/forge/cli/queue.py:265`              |
| Service identity  | `forge` (literal `source_id` on every envelope)    | `src/forge/adapters/nats/pipeline_publisher.py:64` |
| JetStream         | **Required** — durable consumer + KV bucket reads  | API contracts §2 (pipeline / approval)    |

`forge` runs as a single process on the GB10 host; it does not assume
clustering and does not require a multi-node JetStream replication
factor (`replicas: 1` is sufficient for current validation). The
production deployment may scale up later — `forge` does not depend on
the chosen `replicas`.

## 3. Streams forge requires

`forge` publishes on three subject families and subscribes (durable +
ephemeral) on three. The canonical streams must cover every subject
listed below; `forge` does not provision streams and will fail loud at
boot if a required stream is absent.

### 3.1 Subject families forge produces

| Subject template                                  | Producer site                                                          | Notes                                                               |
|---------------------------------------------------|------------------------------------------------------------------------|---------------------------------------------------------------------|
| `pipeline.build-queued.{feature_id}`              | `src/forge/cli/queue.py` (`forge queue …`)                             | Feature → build entrypoint. Consumed by forge itself (durable).     |
| `pipeline.build-started.{feature_id}`             | `pipeline_publisher.publish_build_started`                             | Lifecycle: PREPARING → RUNNING.                                     |
| `pipeline.build-progress.{feature_id}`            | `pipeline_publisher.publish_build_progress`                            | Heartbeat / wave progress.                                          |
| `pipeline.stage-complete.{feature_id}`            | `pipeline_publisher.publish_stage_complete`                            | Per-stage commit point.                                             |
| `pipeline.build-paused.{feature_id}`              | `pipeline_publisher.publish_build_paused`                              | Gate-fired pause; replayed at boot for paused builds.               |
| `pipeline.build-resumed.{feature_id}`             | `pipeline_publisher.publish_build_resumed`                             | After approval response resolves a paused build.                    |
| `pipeline.build-complete.{feature_id}`            | `pipeline_publisher.publish_build_complete`                            | Terminal: PR open.                                                  |
| `pipeline.build-failed.{feature_id}`              | `pipeline_publisher.publish_build_failed`                              | Terminal failure; also emitted by validation rejection path.        |
| `pipeline.build-cancelled.{feature_id}`           | `pipeline_publisher.publish_build_cancelled`                           | Operator cancel.                                                    |
| `agents.approval.forge.{build_id}`                | `approval_publisher.publish_request` (TASK-CGCP-006)                   | Eleven-key details dict per `API-nats-approval-protocol §3.2`.      |
| `fleet.register`                                  | `fleet_publisher.register_on_boot`                                     | Forge self-registration at boot.                                    |
| `fleet.heartbeat.forge`                           | `fleet_publisher.heartbeat_loop`                                       | `DEFAULT_HEARTBEAT_INTERVAL_SECONDS` cadence.                       |
| `fleet.deregister`                                | `fleet_publisher.deregister`                                           | Best-effort graceful shutdown.                                      |
| `agents.command.{matched_agent_id}`               | `specialist_dispatch.command_subject_for`                              | Outbound dispatch to specialist agents (e.g. `specialist-agent`).   |

Multi-tenant project-scoped publishes are wrapped via
[`Topics.for_project`](../../../nats-core/src/nats_core/topics.py)
(e.g. `finproxy.pipeline.build-queued.…`) — those land on the
project-scoped stream (`FINPROXY`) instead.

### 3.2 Subject families forge consumes

| Subject pattern                                            | Consumer site                                                      | Subscription type                                            |
|------------------------------------------------------------|--------------------------------------------------------------------|--------------------------------------------------------------|
| `pipeline.build-queued.>`                                  | `pipeline_consumer.start_pipeline_consumer`                        | **Durable pull** (`durable_name="forge-consumer"`).          |
| `agents.approval.forge.{build_id}.response`                | `approval_subscriber` (TASK-CGCP-007)                              | Ephemeral core subscribe (per-build).                        |
| `agents.result.{matched_agent_id}.{correlation_key}`       | `specialist_dispatch` reply path                                   | Ephemeral core subscribe (per-dispatch).                     |
| `fleet.heartbeat.>`                                        | `fleet_watcher`                                                    | Ephemeral core subscribe (full pattern).                     |

### 3.3 Required streams (canonical, anchor v2.1)

The set already declared in
[`nats-infrastructure/streams/stream-definitions.json`](../../../nats-infrastructure/streams/stream-definitions.json)
is **acceptable** for `forge`. `forge` requires the following
properties; subjects, retention, max_age, and storage MUST match (or
exceed) these floors:

| Stream         | Required subjects   | Retention | Max age (floor) | Max msgs (floor) | Storage | Why                                                                 |
|----------------|---------------------|-----------|-----------------|------------------|---------|----------------------------------------------------------------------|
| `PIPELINE`     | `pipeline.>`        | `work`    | 7d              | 10000            | `file`  | Durable consumer needs replay across restart (ADR-SP-013, §4 §5).    |
| `AGENTS`       | `agents.>`          | `limits`  | 24h             | 5000             | `file`  | Approval requests + responses; replay window covers gate latency.    |
| `FLEET`        | `fleet.>`           | `limits`  | 1h              | 5000             | `file`  | Register/heartbeat/deregister; short window is fine, must persist.   |
| `NOTIFICATIONS`| `notifications.>`   | `work`    | 24h             | 1000             | `file`  | Outbound notification adapters subscribed; `forge` is not a producer here, but `forge`'s gate-fired approval can be relayed by Jarvis to this stream. |
| `FINPROXY` (project) | `finproxy.>`  | `work`    | 24h             | 5000             | `file`  | Multi-tenant validation — Phase 6 references it via `Topics.for_project`. |

`JARVIS` and `SYSTEM` streams are not directly required by `forge`,
but the Jarvis-mediated approval-routing path expects them present.
The `nats-core` v2.1 anchor reconciliation against FLEET / JARVIS /
NOTIFICATIONS retention belongs to `nats-infrastructure` — `forge`
does not pin those retention values.

### 3.4 Retention reasoning (forge-specific)

- `PIPELINE` retention `work` matters. Forge's durable consumer
  (`forge-consumer`, see §4 below) acks each `build-queued` message
  exactly once on terminal transition. `work` retention deletes the
  message on ack so a redelivery never re-fires the build. Switching to
  `limits` would re-trigger every successful build on each crash
  recovery — that is exactly the FEAT-FORGE-008 Phase 4 failure mode.
- `PIPELINE` `max_age` ≥ 7d covers a worst-case crash + paused-build
  window: a paused build that waits a weekend for human approval must
  still have its `build-queued` message replay-able at boot.
- `AGENTS` `max_age` ≥ 24h covers the longest documented gate latency
  before Forge's per-attempt approval refresh path
  (`approval_subscriber` `DEFAULT_DEDUP_TTL_SECONDS = 300s`) fires.

## 4. Durable consumers forge requires

Exactly one durable consumer is required. `forge` constructs it via
`nats.js.api.ConsumerConfig` at boot
(`pipeline_consumer.build_consumer_config()`):

| Field                | Value                              | Source                                              |
|----------------------|------------------------------------|-----------------------------------------------------|
| `durable_name`       | `forge-consumer`                   | `pipeline_consumer.DURABLE_NAME`                    |
| `filter_subject`     | `pipeline.build-queued.>`          | `pipeline_consumer.BUILD_QUEUE_SUBJECT`             |
| `deliver_policy`     | `ALL`                              | `pipeline_consumer.build_consumer_config()`         |
| `ack_policy`         | `EXPLICIT`                         | `pipeline_consumer.build_consumer_config()`         |
| `ack_wait`           | `3600s` (1h)                       | `pipeline_consumer.ACK_WAIT_SECONDS`                |
| `max_deliver`        | `-1` (unbounded redelivery)        | `pipeline_consumer.build_consumer_config()`         |
| `max_ack_pending`    | `1`                                | `pipeline_consumer.build_consumer_config()` (ADR-ARCH-014) |
| Stream               | `PIPELINE`                         | `pipeline_consumer.STREAM_NAME`                     |

**`max_ack_pending=1` is load-bearing.** ADR-ARCH-014 pins the fleet to
sequential-build semantics (one build at a time, ADR-SP-012). If the
canonical config widens this without forge's consent, multi-build
parallelism becomes silently possible and breaks every concurrency
invariant in `tests/integration/test_per_build_routing.py`.

`forge` creates this consumer at runtime via `js.pull_subscribe`. It
does **not** require `nats-infrastructure` to pre-create the durable —
but `nats-infrastructure` must not pre-create one with a different
config (e.g. `max_ack_pending=10`), as that would conflict on bind.

`forge` does not currently use any other durable consumers; the
approval, fleet, and specialist-result subscribers are ephemeral core
subscriptions.

## 5. KV buckets forge requires

`forge` reads (and the `register_agent` path writes) the
`agent-registry` bucket via `nats_core.client.NATSClient`. The
following buckets must exist with at least the listed parameters; the
set already declared in
[`nats-infrastructure/kv/kv-definitions.json`](../../../nats-infrastructure/kv/kv-definitions.json)
satisfies this floor.

| Bucket          | Required by                                            | TTL (floor)    | History (floor) | Storage | Notes                                                              |
|-----------------|--------------------------------------------------------|----------------|------------------|---------|---------------------------------------------------------------------|
| `agent-registry`| `fleet_publisher.register_on_boot` via `register_agent`| **none** (∞)   | ≥ 5              | `file`  | Routing table — keys are agent_ids; manifests must survive restart. |
| `agent-status`  | (read by Jarvis; forge writes via heartbeat indirectly)| **none** (∞)   | ≥ 1              | `file`  | Last-known status per agent; replaces polling.                      |
| `pipeline-state`| `forge` publishes lifecycle on `PIPELINE`; consumers project state into this KV | ≥ 7d | ≥ 3 | `file`  | Per-`feature_id` cached state for Jarvis/dashboards.                |

`forge` does **not** read from `pipeline-state` or `agent-status` in
the current Phase 4–6 surface — they are listed because the
notification/approval-routing path (Jarvis) does, and Forge's published
events are the source-of-truth for them. If those buckets are missing,
Phase 5 round-trip tests against Jarvis will fail.

`jarvis-session` is not required by `forge`.

`forge` does not require any project-scoped (`finproxy-*`) KV buckets
in the current surface — multi-tenancy is at the subject-prefix level
on `FINPROXY` stream, not at the KV layer.

## 6. Auth / ACL requirements

`forge` runs against the canonical NATS server using the **`APPMILLA`
account** ([accounts template](../../../nats-infrastructure/config/accounts/accounts.conf.template)).
The current template grants `rich` / `james` `publish: ">"` and
`subscribe: ">"` — that is sufficient.

If `nats-infrastructure` later tightens auth and introduces a
service-identity user for `forge` specifically (recommended), the user
needs the following permissions:

### 6.1 Publish permissions

```text
publish: [
    "pipeline.build-queued.*",
    "pipeline.build-started.*",
    "pipeline.build-progress.*",
    "pipeline.stage-complete.*",
    "pipeline.build-paused.*",
    "pipeline.build-resumed.*",
    "pipeline.build-complete.*",
    "pipeline.build-failed.*",
    "pipeline.build-cancelled.*",
    "agents.approval.forge.*",
    "fleet.register",
    "fleet.heartbeat.forge",
    "fleet.deregister",
    "agents.command.*",

    // Project-scoped multi-tenancy (Topics.for_project)
    "*.pipeline.build-*.*",
    "*.agents.approval.forge.*",
]
```

### 6.2 Subscribe permissions

```text
subscribe: [
    "pipeline.build-queued.>",                    // durable consumer
    "agents.approval.forge.*.response",           // approval responses
    "agents.result.*.>",                          // specialist replies
    "fleet.heartbeat.>",                          // fleet watcher

    // Project-scoped multi-tenancy
    "*.pipeline.build-queued.>",
    "*.agents.approval.forge.*.response",
]
```

### 6.3 JetStream API permissions

The forge service identity must be allowed to call:

- `$JS.API.STREAM.INFO.PIPELINE` (consumer bind)
- `$JS.API.CONSUMER.CREATE.PIPELINE.forge-consumer` (durable creation)
- `$JS.API.CONSUMER.MSG.NEXT.PIPELINE.forge-consumer` (pull fetch)
- `$JS.API.STREAM.MSG.GET.PIPELINE` (boot reconciliation read)
- `$JS.API.KV.STREAM.NAMES` (KV discovery via `nats_core.client`)
- `$JS.API.STREAM.INFO.KV_agent-registry` (and equivalents for the
  buckets in §5)

JetStream subscribe to `$JS.ACK.>` and `_INBOX.>` is also required for
the pull-consumer ack path; this is the standard pattern and most NATS
ACL templates already grant it implicitly via the account permissions.

## 7. Health endpoints / probes forge expects

Forge does **not** poll the NATS server for health (that contradicts
ADR-ARCH-024 — Forge's observability is event-driven, not polled). The
runbook validation phases, however, do hit the monitoring endpoints
directly. The canonical server must expose:

| Probe                                  | Required by                                    | Notes                                              |
|----------------------------------------|------------------------------------------------|----------------------------------------------------|
| `GET /healthz` → 200                   | runbook §0.6, `verify-nats.sh`                 | Liveness; must be reachable on the monitor port.   |
| `GET /varz` → JSON (`server_name`, `version`) | runbook validation                       | Server identity + version for evidence capture.    |
| `GET /jsz` → JSON (`memory`, `store`)  | runbook validation                             | JetStream initialised confirmation.                |
| `nats stream info PIPELINE` → exit 0   | `verify-nats.sh` Check 5                       | Stream existence (CLI, not HTTP).                  |

The defaults in [`nats-infrastructure/scripts/verify-nats.sh`](../../../nats-infrastructure/scripts/verify-nats.sh)
already cover these; no additional probes are required.

If `nats-infrastructure` later adds Prometheus exporters or alerting,
Forge does not consume them — Forge-side observability flows through
the published `pipeline.*` events (ADR-ARCH-024).

## 8. What is **not** in scope here

- Provisioning the canonical streams or KV buckets (delegated owner).
- Reconciling `FLEET` / `JARVIS` / `NOTIFICATIONS` retention against the
  v2.1 anchor (delegated owner — already on `nats-infrastructure`'s
  queue).
- Deploying `nats-server` to GB10 / production (delegated owner).
- Forge-side health probes or Prometheus integration (out per
  ADR-ARCH-024 — not happening).
- Account / user / password rotation (delegated owner; `forge` reads
  `FORGE_NATS_URL` and whatever auth the URL embeds).

## 9. Sign-off + open questions for `nats-infrastructure`

`forge` will close [TASK-F8-007a](../../tasks/backlog/feat-f8-validation-fixes/TASK-F8-007a-nats-canonical-provisioning-handoff.md)
once this document is merged AND the cross-repo issue tracking the
provisioning work is opened. Provisioning delivery itself is tracked in
`nats-infrastructure` and is **not** a precondition for closing
TASK-F8-007a — that is the explicit `Q4=delegate` separation.

Open questions the canonical owner is asked to answer in the cross-repo
issue:

1. **Anchor v2.1 reconciliation:** confirm the FLEET / JARVIS /
   NOTIFICATIONS retention values currently in
   [`stream-definitions.json`](../../../nats-infrastructure/streams/stream-definitions.json)
   are aligned with the v2.1 anchor. If they need to change, flag back
   any value that crosses the floors in §3.3 above so `forge` can adjust
   its own assumptions.
2. **GB10 deployment target:** is the canonical server expected to run
   inside the existing `docker-compose.yml` on GB10, or under systemd?
   The runbook §0.6 currently assumes either; `forge` does not care,
   but the runbook prose should pick one and stick with it.
3. **Service-identity user:** does `nats-infrastructure` plan to
   introduce a dedicated `forge` user (per §6) before Phase 6.4
   canonical-freeze, or will Phase 6.4 sign off against the current
   `rich`/`james` shared account? Either is acceptable to `forge`; it
   needs to know which to encode in the Phase 6.4 evidence.

## 10. References

- Forge runbook: [`docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md`](../runbooks/RUNBOOK-FEAT-FORGE-008-validation.md) §0.6
- Forge results: [`docs/runbooks/RESULTS-FEAT-FORGE-008-validation.md`](../runbooks/RESULTS-FEAT-FORGE-008-validation.md)
- Forge consumer: `src/forge/adapters/nats/pipeline_consumer.py`
- Forge publisher: `src/forge/adapters/nats/pipeline_publisher.py`
- Forge approval publisher: `src/forge/adapters/nats/approval_publisher.py`
- Forge fleet publisher: `src/forge/adapters/nats/fleet_publisher.py`
- Forge specialist dispatch: `src/forge/adapters/nats/specialist_dispatch.py`
- Forge per-build routing tests: `tests/integration/test_per_build_routing.py`
- Topic registry: [`nats-core/src/nats_core/topics.py`](../../../nats-core/src/nats_core/topics.py)
- Canonical streams: [`nats-infrastructure/streams/stream-definitions.json`](../../../nats-infrastructure/streams/stream-definitions.json)
- Canonical KV: [`nats-infrastructure/kv/kv-definitions.json`](../../../nats-infrastructure/kv/kv-definitions.json)
- Account template: [`nats-infrastructure/config/accounts/accounts.conf.template`](../../../nats-infrastructure/config/accounts/accounts.conf.template)
- Verify script: [`nats-infrastructure/scripts/verify-nats.sh`](../../../nats-infrastructure/scripts/verify-nats.sh)
- ADR-ARCH-014 (sequential builds): `docs/architecture/decisions/ADR-ARCH-014-*.md`
- ADR-ARCH-024 (events not Prometheus): `docs/architecture/decisions/ADR-ARCH-024-observability-via-events-not-prometheus.md`
- ADR-SP-012 / ADR-SP-013 (single in-flight build, retry-from-scratch)
- API contract — pipeline events: `docs/design/contracts/API-nats-pipeline-events.md`
- API contract — approval protocol: `docs/design/contracts/API-nats-approval-protocol.md`
