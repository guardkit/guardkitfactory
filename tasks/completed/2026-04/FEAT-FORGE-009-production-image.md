---
id: FEAT-FORGE-009
title: "Forge Production Image (Dockerfile + forge serve daemon)"
type: feature_stub
status: completed
priority: high
created: 2026-04-30T00:00:00Z
updated: 2026-05-01T00:00:00Z
completed: 2026-05-01T00:00:00Z
recommended_complexity: 4
recommended_effort: "2–4 sessions (/feature-spec + /feature-plan + autobuild)"
parent_review: TASK-REV-F008
spawned_by: TASK-F8-007b
related_files:
  - docs/scoping/F8-007b-forge-production-dockerfile.md
  - docs/research/ideas/forge-build-plan.md
  - docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md
  - docs/architecture/decisions/ADR-ARCH-032-langchain-1x-portfolio-alignment.md
tags: [feature-stub, dockerfile, containerisation, les1, cmdw, port, arfs, forge-serve, blocks-phase-6]
---

# FEAT-FORGE-009 — Forge Production Image

> **Status: backlog stub.** This is a placeholder so the scoping work
> (`TASK-F8-007b`) has a concrete handoff target. Run
> `/feature-spec FEAT-FORGE-009-production-image` against the scoping
> doc when this is prioritised.

## Why this exists

`RUNBOOK-FEAT-FORGE-008-validation.md` Phase 6 (LES1 parity gates —
CMDW, PORT, ARFS, canonical-freeze) is structurally unreachable today
because no `Dockerfile` ships in the repo and no `forge serve` daemon
exists. Per `TASK-REV-F008` §4 + `Q4=delegate`, building those
deliverables is its own forge feature — **not** folded into
`FEAT-F8-VALIDATION-FIXES`.

Full rationale, gate-by-gate requirements, image-baseline
recommendation, multi-stage layout sketch, and open questions are at:

> [`docs/scoping/F8-007b-forge-production-dockerfile.md`](../../docs/scoping/F8-007b-forge-production-dockerfile.md)

That document is the seed input to `/feature-spec`.

## Sketched scope (binding shape, not binding ACs)

1. `Dockerfile` at repo root, multi-stage (`builder` + `runtime`),
   based on `python:3.14-slim-bookworm`.
2. `pip install .[providers]` literal-match to the venv install
   (LES1 §3 DKRX).
3. `forge serve` subcommand added to `src/forge/cli/main.py` (does not
   currently exist — see scoping §11.1).
4. Resolution for `nats-core` source inside the build context (see
   scoping §11.4 — depends on whether the upstream PyPI wheel has
   been republished by then).
5. `HEALTHCHECK` (likely a `/healthz` HTTP endpoint exposed by
   `forge serve`).
6. Non-root runtime user; secrets stay outside the image.
7. CI workflow building + smoke-testing the image on every PR
   touching `Dockerfile`, `pyproject.toml`, or `src/forge/`.
8. RUNBOOK §6 gating callout removed when this feature merges.

## Blockers / dependencies

- **Wave-2 of `FEAT-F8-VALIDATION-FIXES`** should land first — keeps
  the validation-fix merge cycle clean. (Wave-1 is already merged as
  of 2026-04-30.)
- **Sibling — `TASK-F8-007a`**: NATS canonical provisioning
  (delegated to `nats-infrastructure`) is parallelisable but is also
  required for Phase 6 to actually *run* once the image exists.
- ~~**Open question 4 in the scoping doc** (`nats-core` build-context
  resolution) needs an operator decision before `/feature-spec` can
  converge.~~ ✅ **Resolved 2026-04-30 — operator picked (c):** Docker
  BuildKit `--build-context nats-core=../nats-core`. Rationale: "I'd
  prefer if everything is dockerised" — keeps the canonical build path
  fully container-native. See scoping doc §11.4 for the full
  implementation hooks (named build context, `docker buildx` invocation,
  runbook §6.1 alignment).

## Definition of done (sketch)

This stub is replaced by a real feature folder
(`tasks/backlog/feat-forge-009-production-image/`) once
`/feature-spec FEAT-FORGE-009-production-image` runs.

---

## Closure footer

**Closed by FEAT-FORGE-009 merge `<merge-sha-pending>`** (2026-05-01).

This stub is retained for traceability. The realised feature shipped:

- `Dockerfile` (multi-stage, `python:3.14-slim-bookworm`) at the forge
  repo root.
- `forge serve` subcommand wiring the NATS JetStream pull consumer
  to the existing pipeline runner.
- Canonical BuildKit invocation
  `docker buildx build --build-context nats-core=../nats-core -t forge:production-validation -f forge/Dockerfile forge/`
  (Contract A — sibling `nats-core` source resolved via named build
  context, no host-side mutation of `pyproject.toml`/symlinks/.env).
- Runbook fold of `docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md`
  §6 (gating callout removed; §6.1 now executes against the canonical
  image) — TASK-F009-008.

See `docs/history/command-history.md` "FEAT-FORGE-009 merge" entry
for the full canonical-freeze record.
