# FEAT-FORGE-009 — Forge Production Image

Multi-stage Dockerfile + `forge serve` long-lived daemon to unblock the
LES1 parity gates (CMDW, PORT, ARFS, canonical-freeze) currently
blocking Phase 6 of `RUNBOOK-FEAT-FORGE-008-validation.md`.

## What this feature delivers

1. **`Dockerfile`** at repo root — multi-stage (`builder` + `runtime`),
   `python:3.14-slim-bookworm` pinned by sha256 digest, non-root user.
2. **`forge serve`** — new CLI subcommand (long-lived daemon) that
   subscribes to JetStream `pipeline.build-queued.*` via a shared
   durable consumer `forge-serve` (work-queue semantics for safe
   multi-replica deployment).
3. **`/healthz`** HTTP endpoint on port 8080 reporting subscription
   state (200 OK / 503 Unavailable).
4. **BuildKit `--build-context nats-core=../nats-core`** — operator
   decision (c) on scoping Q4: keeps the canonical build path fully
   container-native without depending on upstream PyPI republishing
   `nats-core`.
5. **`scripts/build-image.sh`** — canonical entry point; the only
   place the BuildKit invocation appears verbatim. CI workflow and
   runbook §6.1 both call this script.
6. **GitHub Actions `forge-image.yml`** — builds + smoke-tests the
   image on every PR touching `Dockerfile`, `pyproject.toml`,
   `src/forge/**`, or the build script. Enforces the 1.0 GB
   uncompressed image-size budget and scans every layer for baked
   provider keys.
7. **Runbook §6 fold** — removes the gating callout and replaces
   the bare `docker build` invocation with the canonical BuildKit
   form. Closes AC-J.

## Tasks (8 across 4 waves)

| Wave | Task | Type | Complexity | Implementation |
|---|---|---|---|---|
| 1 | [TASK-F009-001](TASK-F009-001-add-forge-serve-skeleton.md) — `forge serve` skeleton | scaffolding | 3 | direct |
| 1 | [TASK-F009-002](TASK-F009-002-add-dockerfile-skeleton.md) — Dockerfile skeleton | scaffolding | 4 | task-work |
| 2 | [TASK-F009-003](TASK-F009-003-implement-forge-serve-daemon.md) — daemon body | feature | 7 | task-work |
| 2 | [TASK-F009-004](TASK-F009-004-implement-healthz-endpoint.md) — `/healthz` HTTP | feature | 5 | task-work |
| 2 | [TASK-F009-005](TASK-F009-005-implement-dockerfile-install-layer.md) — install layer + BuildKit | feature | 7 | task-work |
| 3 | [TASK-F009-006](TASK-F009-006-add-bdd-bindings-and-integration-tests.md) — BDD bindings + tests | testing | 6 | task-work |
| 3 | [TASK-F009-007](TASK-F009-007-add-github-actions-image-workflow.md) — GitHub Actions | feature | 5 | task-work |
| 4 | [TASK-F009-008](TASK-F009-008-fold-runbook-section6-and-history.md) — runbook §6 fold | documentation | 3 | direct |

## Key references

- [`IMPLEMENTATION-GUIDE.md`](IMPLEMENTATION-GUIDE.md) — full plan with
  Mermaid diagrams (data flow, integration sequence, dependency graph),
  §4 Integration Contracts, risk register, AC coverage matrix.
- [`features/forge-production-image/forge-production-image.feature`](../../../features/forge-production-image/forge-production-image.feature) — 27 BDD scenarios.
- [`docs/scoping/F8-007b-forge-production-dockerfile.md`](../../../docs/scoping/F8-007b-forge-production-dockerfile.md) — scoping doc with the operator's Q4 decision.
- [`tasks/backlog/TASK-REV-F009-plan-feat-forge-009-production-image.md`](../TASK-REV-F009-plan-feat-forge-009-production-image.md) — the planning review that produced this feature.

## Run AutoBuild

```bash
/feature-build FEAT-FORGE-009
```
