# Status update: canonical NATS provisioning is live

**From:** `nats-infrastructure` (canonical NATS provisioning owner)
**To:** `forge` (FEAT-FORGE-008 validation, Phases 4–6)
**Reply-to spec:** [`F8-007a-nats-canonical-provisioning.md`](./F8-007a-nats-canonical-provisioning.md)
**Tracking task:** [`nats-infrastructure/tasks/in_progress/TASK-FCH-001-canonical-nats-provisioning-for-forge.md`](../../../nats-infrastructure/tasks/in_progress/TASK-FCH-001-canonical-nats-provisioning-for-forge.md)
**Posted:** 2026-04-30

## TL;DR

Canonical NATS is provisioned and verified live on GB10
(`promaxgb10-41b1`). Forge can re-run
`RUNBOOK-FEAT-FORGE-008-validation` Phases 4–6 against this server and
declare Step 6 canonical.

## Decisions taken (resolves handoff §9 open questions)

| Handoff §9 question                        | Decision                                                   |
|--------------------------------------------|------------------------------------------------------------|
| §9.2 — GB10 deployment target              | **docker-compose** (existing `nats-infrastructure/docker-compose.yml`). |
| §9.3 — Forge service-identity for §6.4 sign-off | **Shared APPMILLA `rich`/`james`** (per current `accounts.conf.template`). Dedicated `forge` user with §6.1/6.2/6.3 ACL is a future hardening option, **not** required for §6.4 canonical-freeze. |

Forge §6.4 evidence should cite the shared APPMILLA account.

## Connection details

| Field             | Value                                              |
|-------------------|----------------------------------------------------|
| Host              | `promaxgb10-41b1` (Tailscale hostname)             |
| Client port       | `4222`                                             |
| Monitor port      | `8222`                                             |
| URL (on GB10)     | `nats://localhost:4222`                            |
| URL (over Tailscale) | `nats://promaxgb10-41b1:4222`                   |
| Account           | `APPMILLA`                                         |
| Users             | `rich`, `james` (full publish/subscribe)           |
| Credentials       | Passwords live in `nats-infrastructure/.env` on GB10 (not in this doc). Forge consumes via `FORGE_NATS_URL` or explicit `NATS_USER` / `NATS_PASSWORD` env vars. |

## Verification evidence — 2026-04-30

### `scripts/verify-nats.sh` (handoff §7 probes)

```
--- Check 1: Health Endpoint ---       [PASS] Health endpoint returned HTTP 200
--- Check 2: JetStream Status ---      [PASS] JetStream is initialised
--- Check 3: Server Info ---           [PASS] server_name='ships-computer', version=2.11.16
--- Check 4: Account Authentication --- [PASS] APPMILLA user 'rich' can publish
                                        [PASS] FINPROXY user 'mark' can publish (scoped)
--- Check 4b: Placeholder Rejected --- [PASS] 'rich:changeme' rejected
--- Check 5: JetStream Streams ---     [OK] PIPELINE / AGENTS / JARVIS /
                                            NOTIFICATIONS / SYSTEM / FLEET / FINPROXY
=============================================
  Results: 7 passed, 0 failed
```

### Live stream config — forge-pinned floors (handoff §3.3)

| Stream         | Floor (subjects / retention / max_age / max_msgs / storage) | Live config                                                | Status |
|----------------|--------------------------------------------------------------|------------------------------------------------------------|--------|
| `PIPELINE`     | `pipeline.>` / `work` / 7d / 10000 / `file`                  | `pipeline.>` / `workqueue`* / 604800s (7d) / 10000 / `file`| ✅      |
| `AGENTS`       | `agents.>` / `limits` / 24h / 5000 / `file`                  | `agents.>` / `limits` / 86400s (24h) / 5000 / `file`       | ✅      |
| `FLEET`        | `fleet.>` / `limits` / 1h / 5000 / `file`                    | `fleet.>` / `limits` / 3600s (1h) / 5000 / `file`          | ✅      |
| `NOTIFICATIONS`| `notifications.>` / `work` / 24h / 1000 / `file`             | `notifications.>` / `workqueue`* / 86400s (24h) / 1000 / `file` | ✅ |
| `FINPROXY`     | `finproxy.>` / `work` / 24h / 5000 / `file`                  | `finproxy.>` / `workqueue`* / 86400s (24h) / 5000 / `file` | ✅      |

\* The NATS API returns `workqueue` for streams declared with retention
`work` in the spec JSON — they are equivalent.

### Live KV bucket inventory — forge-required floors (handoff §5)

```
$ nats kv ls
Bucket          Description  Created              Size  Values  Last Update
agent-registry               2026-04-30 19:22:07  0 B   0       never
agent-status                 2026-04-30 19:22:07  0 B   0       never
jarvis-session               2026-04-30 19:22:07  0 B   0       never
pipeline-state               2026-04-30 19:22:07  0 B   0       never
```

All three forge-required buckets present with floor-compliant config:
- `agent-registry`: TTL ∞, history 5, file storage
- `agent-status`: TTL ∞, history 1, file storage
- `pipeline-state`: TTL 7d, history 3, file storage

`jarvis-session` is the Jarvis-only bucket (not required by forge per
handoff §5).

### Durable consumer note (handoff §4)

`forge-consumer` is **not** pre-created — forge creates it at runtime
via `js.pull_subscribe` per the handoff §4 contract. No conflicting
durable exists on `PIPELINE`. `nats-infrastructure` will not pre-create
this consumer.

## Anchor v2.1 reconciliation status (handoff §3.3, §9.1)

The five forge-pinned stream floors are met live (table above). The
"v2.1 anchor" cross-reference for `JARVIS` retention specifically (the
non-forge-pinned stream the handoff §9.1 mentions) is flagged as a
documentation hygiene follow-up on the `nats-infrastructure` side:
the canonical anchor doc isn't currently locatable in `nats-core/docs/`
or `nats-infrastructure/docs/`. This does **not** block FEAT-FORGE-008
Phase 4–6 — forge does not pin `JARVIS` retention.

## What forge can do now

1. Re-run `docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md` Phases
   4–6 against `nats://promaxgb10-41b1:4222` (or `nats://localhost:4222`
   if running on the GB10 host).
2. Capture §6.4 canonical-freeze evidence citing the shared APPMILLA
   `rich`/`james` account.
3. Mark Step 6 canonical.

## What `nats-infrastructure` will not do (out of scope per handoff §8)

- Pre-create `forge-consumer` (forge owns this).
- Add forge-side health probes or Prometheus exporters (ADR-ARCH-024).
- Land a dedicated `forge` service-identity user before §6.4 (deferred
  per §9.3 decision).
- Re-run forge's validation runbook (forge-operator action).

## Closing condition for tracking task

`nats-infrastructure/TASK-FCH-001` will move to `completed/` once forge
acknowledges receipt of this update. No further action expected on this
side until forge reports §6 canonical-freeze evidence (or finds a
provisioning regression).
