---
id: TASK-REV-F009
title: "Plan: FEAT-FORGE-009 Forge Production Image (Dockerfile + forge serve daemon)"
task_type: review
status: backlog
priority: high
created: 2026-04-30T00:00:00Z
updated: 2026-04-30T00:00:00Z
complexity: 7
estimated_effort: "2-4 sessions (review + plan + autobuild)"
recommended_feature_id: FEAT-FORGE-009
parent_feature_stub: tasks/backlog/FEAT-FORGE-009-production-image.md
related:
  - features/forge-production-image/forge-production-image.feature
  - features/forge-production-image/forge-production-image_summary.md
  - features/forge-production-image/forge-production-image_assumptions.yaml
  - docs/scoping/F8-007b-forge-production-dockerfile.md
  - docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md
  - docs/architecture/decisions/ADR-ARCH-032-langchain-1x-portfolio-alignment.md
tags: [feature-plan, review, dockerfile, containerisation, les1, cmdw, port, arfs, forge-serve, blocks-phase-6]
clarification:
  context_a:
    timestamp: 2026-04-30T00:00:00Z
    decisions:
      focus: all
      tradeoff: balanced
      specific_concerns: [nats_core_buildkit_wiring, forge_serve_daemon_resilience, runbook_section6_gating_callout_removal]
      depth: deep
      decomposition_strategy: wave_based_by_gate
test_results:
  status: pending
  coverage: null
  last_run: null
---

# TASK-REV-F009 — Plan: FEAT-FORGE-009 Forge Production Image

## Description

Run a deep `/task-review` against FEAT-FORGE-009 to produce a wave-based
implementation plan that delivers:

1. A multi-stage Dockerfile (`builder` + `runtime`) on
   `python:3.14-slim-bookworm` with sha256 digest pinning.
2. A new `forge serve` long-lived daemon subcommand that subscribes to
   JetStream `pipeline.build-queued.*` via a shared durable consumer
   `forge-serve` (work-queue semantics for multi-replica safety).
3. The Docker BuildKit `--build-context nats-core=../nats-core` wiring
   that resolves the sibling editable `nats-core` source inside the
   container build (operator-decided 2026-04-30, per
   `docs/scoping/F8-007b-forge-production-dockerfile.md` §11.4).
4. An HTTP `/healthz` probe on TCP port 8080 reflecting the JetStream
   subscription state, wired via Docker `HEALTHCHECK`.
5. A CI workflow that builds + smoke-tests the image on every PR
   touching `Dockerfile`, `pyproject.toml`, or `src/forge/`.
6. The runbook §6 gating callout removal that closes
   `RUNBOOK-FEAT-FORGE-008-validation.md` Phase 6 (CMDW / PORT / ARFS /
   canonical-freeze parity gates).

The review must verify each LES1 parity gate is structurally reachable
once the planned tasks ship, and the wave-based decomposition must keep
parallelisation honest (no intra-wave dependencies).

## Acceptance Criteria

- [ ] Review surfaces 3+ implementation alternatives compared on a
      trade-off matrix (deep mode required by Q4)
- [ ] Recommended approach addresses all five focus areas (technical
      depth, architecture, security, LES1 compliance, CI/DevOps)
- [ ] Specific concerns called out: nats-core BuildKit wiring, `forge
      serve` daemon resilience, runbook §6 gating callout removal
- [ ] Wave-based decomposition: scaffolding wave → feature wave → CI
      gates / runbook fold wave; tasks within a wave have no shared
      file conflicts
- [ ] Each LES1 parity gate (CMDW, PORT, ARFS, canonical-freeze) maps
      to at least one acceptance criterion in the resulting subtask set
- [ ] Integration contract surfaced for cross-task data dependencies
      (most likely DOCKER_BUILD_CONTEXT shape and HEALTHZ_PORT)
- [ ] Decision checkpoint reached with [A]ccept / [R]evise / [I]mplement
      / [C]ancel options
- [ ] On [I]mplement, structured `.guardkit/features/FEAT-FORGE-009.yaml`
      is generated with `file_path` populated for every task and
      `parallel_groups` honouring the wave decomposition

## Implementation Notes

This is a **review task**, not an implementation task. Expected
follow-up: `/task-review TASK-REV-F009 --mode=decision --depth=deep`.

The 27-scenario feature spec at
`features/forge-production-image/forge-production-image.feature` is
already converged (all 10 assumptions confirmed by operator on
2026-04-30). The review's job is to convert that behavioural contract
into a wave-ordered implementation plan, not to revisit the spec.

## Test Execution Log

(Populated by `/task-review`.)
