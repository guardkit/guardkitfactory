---
id: TASK-F8-007a
title: "Hand off canonical NATS provisioning to nats-infrastructure"
task_type: documentation
status: completed
priority: medium
created: 2026-04-29T00:00:00Z
updated: 2026-04-30T00:00:00Z
completed: 2026-04-30T00:00:00Z
parent_review: TASK-REV-F008
feature_id: FEAT-F8-VALIDATION-FIXES
wave: 3
implementation_mode: direct
complexity: 2
dependencies: []
tags: [docs, handoff, nats, infrastructure, delegation, feat-forge-008, f008-val-007]
related_files:
  - docs/handoffs/F8-007a-nats-canonical-provisioning.md
  - docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md
  - docs/runbooks/RESULTS-FEAT-FORGE-008-validation.md
  - ../nats-infrastructure/  # (sibling repo — handoff target)
test_results:
  status: n/a
  coverage: null
  last_run: 2026-04-30T00:00:00Z
  notes: |
    Pure docs task (implementation_mode=direct). No automated test
    surface. The closing condition (handoff doc merged + cross-repo
    issue opened in `nats-infrastructure`) is a manual operator step;
    see Implementation Log below.
---

# Task: Hand off canonical NATS provisioning to `nats-infrastructure`

## Description

Phases 4–6 of the FEAT-FORGE-008 validation runbook require a canonical
JetStream-provisioned NATS server (persistent streams + KV stores
matching the `nats-core` topology). The 2026-04-29 walkthrough used a
throwaway `nats:latest -js` container for Phases 2–3 only — there is no
canonical NATS service running on this host (or on production targets).

Per `Q4=delegate`, the canonical NATS provisioning is owned by the
sibling `nats-infrastructure` repo, NOT by forge. Graphiti shows that
repo is "READY today" but with FLEET / JARVIS / NOTIFICATIONS streams +
retentions still needing reconciliation against the v2.1 anchor. That
reconciliation is the canonical owner's work.

This task is the **handoff document** — forge specifies what it requires
in production, and `nats-infrastructure` (and its operator) own the
provisioning, hardening, and operations.

## Acceptance Criteria

- [ ] **AC-1**: A handoff document is written at
      `docs/handoffs/F8-007a-nats-canonical-provisioning.md` containing:

  1. **Streams forge requires**: subject filters, retention policy, max
     bytes/messages, replication factor. Sources of truth:
     `nats-core` topology + the v2.1 anchor in `architecture_decisions`
     graph group.
  2. **Durable consumers forge requires**: consumer name, subject
     filter, ack policy, deliver policy, max ack pending. Source: the
     forge consumer wiring in
     `src/forge/adapters/nats/pipeline_publisher.py` and the durable
     decision tests in `tests/integration/test_per_build_routing.py`.
  3. **KV buckets forge requires**: bucket name, history depth, TTL,
     storage backend. Source: the approval channel KV wiring in
     `src/forge/adapters/nats/approval_publisher.py`.
  4. **Auth/ACL requirements**: which subjects need which permissions
     for the forge service identity.
  5. **Health endpoints / probes**: what monitoring hooks forge expects
     (e.g., `/varz`, `/healthz`, JetStream stream-state probes).

- [ ] **AC-2**: A cross-repo issue is opened in `nats-infrastructure`
      tracking the provisioning work, with the handoff doc linked.
      (If the operator owns both repos, this can be a manual GitHub
      issue creation; otherwise, raise it via whatever ticket system
      `nats-infrastructure` uses.)
- [ ] **AC-3**: The forge runbook (after TASK-F8-006 gap-fold lands) at
      §0.6 links to the handoff doc as the canonical source for "what
      Phases 4+ require".
- [ ] **AC-4**: This task's status is closed when the handoff document is
      merged AND the cross-repo issue is opened — NOT when the
      provisioning work itself is complete (that's `nats-infrastructure`'s
      delivery, tracked separately).

## Implementation Notes

- Pure docs task. Implementation mode = `direct`.
- This is the smallest of the eight tasks; it just enumerates forge's
  requirements. The hard work (actually provisioning the streams,
  reconciling retention with the v2.1 anchor, deploying to production
  targets) belongs to `nats-infrastructure`.
- If a similar handoff doc already exists from prior FEAT-FORGE work
  (likely from FEAT-FORGE-006 or 007 era), update it rather than
  duplicating. Search `docs/handoffs/` first.

## Out of scope

- Provisioning canonical NATS streams (delegated owner).
- Deploying nats-server to production hosts (delegated owner).
- Reconciling FLEET / JARVIS / NOTIFICATIONS retention with the v2.1
  anchor (delegated owner — already on `nats-infrastructure`'s queue
  per Graphiti context).
- Implementing forge-side health probes or monitoring (separate concern).

## Implementation Log (2026-04-30)

### Done

- **AC-1 (handoff doc):** Wrote
  [`docs/handoffs/F8-007a-nats-canonical-provisioning.md`](../../../docs/handoffs/F8-007a-nats-canonical-provisioning.md).
  No prior `docs/handoffs/` directory existed — fresh document, not a
  duplicate of any FEAT-FORGE-006/007-era predecessor. Doc enumerates:
  - §3: Streams forge requires (subject filters, retention floors, max
    bytes/messages, replicas) — sourced from `pipeline_publisher.py`,
    `pipeline_consumer.py`, `fleet_publisher.py`, `specialist_dispatch.py`,
    cross-checked against `nats-infrastructure/streams/stream-definitions.json`.
  - §4: Durable consumer (`forge-consumer`) config — sourced verbatim
    from `pipeline_consumer.build_consumer_config()` and pinned with a
    note on the `max_ack_pending=1` ADR-ARCH-014 invariant.
  - §5: KV buckets (`agent-registry`, `agent-status`, `pipeline-state`)
    with floors — cross-checked against
    `nats-infrastructure/kv/kv-definitions.json`.
  - §6: Auth/ACL — explicit publish/subscribe/JS-API permission lists
    for a future dedicated `forge` service-identity user (current
    APPMILLA `rich`/`james` shared account also satisfies).
  - §7: Health probes — `/healthz`, `/varz`, `/jsz`, plus
    `nats stream info PIPELINE`, all already covered by
    `nats-infrastructure/scripts/verify-nats.sh`.

- **AC-3 (runbook §0.6 link):** Updated
  [`docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md`](../../../docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md)
  §0.6 to link to the handoff doc as the canonical source for "what
  Phases 4+ require" (after the TASK-F8-006 gap-fold landed).

### Done — AC-2 + AC-4 closure (2026-04-30)

- **AC-2 (cross-repo tracking artefact):** `nats-infrastructure` does
  not use GitHub Issues — it uses the same `tasks/backlog/` folder
  convention this repo does (existing examples: `TASK-REV-4721`,
  `TASK-DCD-005`, `TASK-850A`). Filed:
  [`nats-infrastructure/tasks/backlog/TASK-FCH-001-canonical-nats-provisioning-for-forge.md`](../../../../nats-infrastructure/tasks/backlog/TASK-FCH-001-canonical-nats-provisioning-for-forge.md).
  That task carries forward the v2.1 reconciliation, GB10 deployment
  decision, dedicated-forge-user decision, KV provisioning, and health
  probe acceptance — its AC-6 commits `nats-infrastructure` to ping
  `forge` once provisioning is live so the runbook Phases 4–6 can run.
  Per AC-2's own escape hatch ("raise it via whatever ticket system
  `nats-infrastructure` uses"), this satisfies the requirement without
  a GitHub issue.

- **AC-4 (close):** Both AC-1 (handoff doc merged on `forge:main`) and
  AC-2 (cross-repo tracking artefact filed) are satisfied. Task moved
  to `tasks/completed/TASK-F8-007a/`; status flipped to `completed`.

### Out of scope (explicit, per task brief)

- Actual provisioning work in `nats-infrastructure` (their delivery,
  tracked separately).
- Reconciling FLEET / JARVIS / NOTIFICATIONS retention with the v2.1
  anchor (already on `nats-infrastructure`'s queue).
