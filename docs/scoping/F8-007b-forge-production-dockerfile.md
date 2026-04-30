---
id: F8-007b-scoping
title: "Forge Production Dockerfile — Scoping for FEAT-FORGE-009"
status: scoping
created: 2026-04-30
parent_review: TASK-REV-F008
parent_task: TASK-F8-007b
recommended_feature_id: FEAT-FORGE-009-production-image
related:
  - docs/research/ideas/forge-build-plan.md (LES1 parity gates §"Specialist-agent LES1 Parity Gates")
  - docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md (Phase 6 — gated on this)
  - docs/architecture/decisions/ADR-ARCH-032-langchain-1x-portfolio-alignment.md (Python 3.14 baseline + LCOI providers)
  - docs/handoffs/F8-007a-nats-canonical-provisioning.md (sibling delegation — NATS infra)
---

# Forge Production Dockerfile — Scoping for FEAT-FORGE-009

> **Status:** scoping only. This document describes **what FEAT-FORGE-009
> should deliver** and **why it is its own feature**. The Dockerfile is
> *not* built here. AC-1 through AC-4 of TASK-F8-007b are satisfied by
> this doc + the runbook cross-reference + the handoff record at the
> bottom.

## 1. Problem statement

The runbook at `docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md` §6.1
calls

```bash
docker build -t forge:production-validation -f Dockerfile .
```

but **no `Dockerfile` ships in this repo**. As a consequence, the four
LES1 parity gates that Phase 6 is designed to enforce —

1. **CMDW** (canonical multi-stage docker / production-image
   subscription round-trip),
2. **PORT** (`(specialist_role, forge_stage)` dispatch matrix on the
   production image),
3. **ARFS** (per-tool handler-completeness on the production image), and
4. **canonical-freeze live-verification** (verbatim runbook execution
   from a clean machine)

— are **structurally unreachable today**. Phase 6 is the gate behind
which forge becomes "canonical" per the build plan; without it, no
forge build can be declared canonical, and the FinProxy first-run
runbook (`RUNBOOK-FEAT-FORGE-008-finproxy-first-run.md`) cannot be
executed in production form.

The runbook gap-fold (TASK-F8-006, merged 2026-04-30) added a callout to
§6 explaining the gap; this scoping doc is the next step — it specifies
what the production Dockerfile must do so that gating callout can be
removed.

## 2. Why FEAT-FORGE-009 (not folded into FEAT-F8-VALIDATION-FIXES)

Per the architectural review §4 + `Q4=delegate`
(`docs/reviews/REVIEW-F008-validation-triage.md`):

- The Dockerfile is a substantial DevOps-shaped piece of work — multi-
  stage build, dep audit, CI integration, smoke-image testing, LES1
  gate compliance — independent of F008's Mode A/B/C correctness
  concerns.
- Folding it into F8 would inflate the validation-fix scope and tie
  F8's review/merge cycle to a problem that is structurally outside
  it.
- The recommended ID `FEAT-FORGE-009-production-image` keeps it
  parallel to the `FEAT-FORGE-007/008` cadence and signals "this is
  forge's container surface", not a sub-fix.

## 3. LES1 gate requirements (gate-by-gate, must be green on the
   production image)

Source of truth: `docs/research/ideas/forge-build-plan.md` §"Specialist-
agent LES1 Parity Gates" (lines 561–600). Each gate is a *structural*
requirement on the produced image, not a unit-test pass.

### 3.1 CMDW — production-image subscription round-trip

The image must, when run as `forge serve`, subscribe to JetStream
`pipeline.build-queued.*` and pick up real published payloads. A stale
image that silently fails to subscribe is the exact specialist-agent
CMDW failure mode (TASK-MDF-CMDW).

**What the Dockerfile must enable:**

- Long-lived process model — `forge serve` (see §11 open question 1)
  must run as the container's main process, not as a one-shot CLI
  invocation.
- The image must include `langchain-anthropic` (declared in `pyproject`
  base deps) **plus everything in the `[providers]` extra**
  (`langchain-openai`, `langchain-google-genai`) — per LES1 §3 LCOI
  retest finding (cited in `pyproject.toml` lines 22–29 and
  `forge-build-plan.md` line 656). Install command must be
  `pip install .[providers]` literal-match to the venv install.
- The image must include `nats-core` resolved correctly. **This is a
  current dep-resolution gotcha** — the PyPI `nats-core==0.2.0` wheel
  is broken (see ADR-ARCH-032 §"Out of scope" and `pyproject.toml`
  lines 65–88); forge currently uses
  `[tool.uv.sources] nats-core = { path = "../nats-core", editable = true }`.
  Inside a container, `../nats-core` does not exist. Resolution
  (open question 4) must be settled before the Dockerfile lands.

### 3.2 PORT — `(specialist_role, forge_stage)` dispatch matrix

The image must be capable of hosting every `(role ∈ {product-owner,
architect}, stage)` round-trip used in Mode A. This is exercised
*against* the production image, not by it, but the image must:

- Expose the canonical CLI surface (`forge queue`, `forge status`,
  `forge history`, `forge cancel`, `forge skip`) — every
  CLI-level entrypoint registered in
  `src/forge/cli/main.py:main` lines 89–93.
- Not block on environment variables that aren't set in production —
  `NATS_URL` (default), `FORGE_LOG_LEVEL` (default), and the provider-
  key envs declared in `.env.example`. The image **must not bake real
  keys** — LES1 §3 retest-env (`pyproject` line 655) called this out
  as a hard CI gate.

### 3.3 ARFS — per-tool handler-completeness matrix

Every tool in `forge.fleet.manifest:build_manifest()` (or wherever the
canonical `AgentManifest` lives — see runbook §6.3 lines 783–789) must
be present in the produced image's manifest:

- `forge_greenfield` (Mode A)
- `forge_feature` (Mode B — NEW from FEAT-FORGE-008)
- `forge_review_fix` (Mode C — NEW from FEAT-FORGE-008)
- `forge_status`
- `forge_cancel`

**Implication for the Dockerfile:** the image must `pip install` the
forge package itself (not just deps) such that the entry-point shim
`forge = "forge.cli.main:main"` (`pyproject.toml` line 53) is wired and
the manifest-build code path can run inside the container without
mounting source.

### 3.4 Canonical-freeze live-verification

Phase 6.4 expects every shell block in this runbook to run verbatim
from a clean machine. The Dockerfile must therefore:

- Be invocable with the exact command `docker build -t
  forge:production-validation -f Dockerfile .` from the repo root.
- Not require host-side mutation of `pyproject.toml`,
  environment files, or symlinks to siblings. Any setup that the
  Dockerfile *does* require must be a copy-paste shell block at the
  top of Phase 6.1.

## 4. Image baseline — recommendation

| Choice | Recommendation | Why |
|---|---|---|
| Base image | `python:3.14-slim-bookworm` | Matches ADR-ARCH-032 §"Verified-versions table" (Python 3.14.2 is the empirically-validated baseline); `slim-bookworm` is the smallest official Python image with a stable `apt` for the few build tools we need (gcc, headers for any C-extension deps that pip wheels don't cover); avoids Alpine's musl/glibc landmines (LangChain wheels target glibc). Distroless is tempting but rules out a shell for `docker exec` debugging in CMDW gate triage — defer until the image is stable. |
| Python version | **3.14** | Per ADR-ARCH-032 — 3.14.2 is the version against which the LangChain 1.x portfolio pin was validated. `pyproject.toml` says `requires-python = ">=3.11"`, so 3.12 would also work, but the build plan line 656 explicitly defers to F0E4, and F0E4 (= ADR-ARCH-032) chose 3.14. |
| Build tooling inside image | `uv` (preferred over raw `pip`) | Forge already targets `uv` in the runbook (`uv pip install -e ".[providers]"`); using `uv` in the Dockerfile keeps the install command identical to the documented venv flow, satisfying LES1 §3 DKRX (Dockerfile extras ≡ guide extras, `forge-build-plan.md` line 656). |

**Anti-recommendation:** do **not** use `python:3.14` (the non-slim
default). It bakes in 1+ GB of toolchain that the runtime doesn't need
and inflates the image past what CMDW gate timing comfortably tolerates
when GB10 has to pull it.

## 5. Multi-stage layout

Two stages, named `builder` and `runtime`. The builder stage installs
all deps, including build-time C-extension toolchain; the runtime stage
copies only the resolved venv and the `forge` package, leaving gcc /
build-essential behind.

```
Stage 1: builder
  FROM python:3.14-slim-bookworm AS builder
  - apt-get install build-essential, git (for `pip install` from VCS-style sources if any)
  - Create /opt/venv
  - COPY pyproject.toml + src/forge/
  - uv pip install --no-cache .[providers]   # not editable
  - (see §11 open question 4 for nats-core source resolution)

Stage 2: runtime
  FROM python:3.14-slim-bookworm AS runtime
  - apt-get install only the runtime-side libs (likely none beyond what
    slim already includes; confirm in feature-plan).
  - COPY --from=builder /opt/venv /opt/venv
  - COPY src/forge/ /app/  (only if not relying on installed package
    discovery via /opt/venv; see §11 open question 5)
  - ENV PATH=/opt/venv/bin:$PATH
  - WORKDIR /app
  - USER forge (non-root; create UID 1000 in builder)
  - ENTRYPOINT ["forge"]
  - CMD ["serve"]   (see §11 open question 1)
```

**Editable installs are eliminated** in the runtime stage: the builder
runs `pip install .[providers]` (no `-e`), so `/opt/venv` contains the
forge package as a proper installed distribution. This matches LES1 §3
DKRX literal-match.

## 6. Entrypoint — canonical `forge` CLI surface

The container's user-facing surface is whatever `forge.cli.main:main`
(`pyproject.toml` line 53) exposes:

- `forge queue` — submit a build (Mode A/B/C)
- `forge status` — pipeline-state inspection
- `forge history` — past-run inspection (mode-filtered per FEAT-FORGE-008)
- `forge cancel` — cancel a build
- `forge skip` — constitutional skip refusal surface

`ENTRYPOINT ["forge"]` makes `docker run forge:tag <subcommand>` work
identically to a host-side `forge <subcommand>`. The default `CMD` —
the long-lived daemon — is the open question (§11.1).

## 7. Health probe

Recommend `HEALTHCHECK` only **after** §11.1 is settled. Two viable
shapes:

- **If `forge serve` exposes a probe endpoint** (e.g. `/healthz` over
  HTTP): `HEALTHCHECK CMD curl -fs http://localhost:<port>/healthz ||
  exit 1`. Port choice is itself an open question (§11.2 — PORT in the
  LES1 sense is a routing concept, not a TCP port; the image's bound
  TCP port for healthz/metrics is a separate matter).
- **If `forge serve` exposes only a NATS-side liveness signal** (e.g.
  publishing a heartbeat to `pipeline.heartbeat.<instance>`):
  `HEALTHCHECK` is harder — Docker's healthcheck mechanism wants a
  process-level command. A wrapper script that polls a local NATS
  client is possible but adds complexity. Defer to FEAT-FORGE-009
  feature-spec.

For **scoping purposes**, recommend: implement the simplest possible
HTTP `/healthz` on `forge serve` (200 OK if the JetStream subscription
is live, 503 otherwise) and use the curl form. This also gives
operators a non-NATS check against image freshness.

## 8. Open questions (out of scope here — defer to `/feature-spec`
   FEAT-FORGE-009)

1. **`forge serve` subcommand does not yet exist.** `src/forge/cli/main.py`
   registers `queue / status / history / cancel / skip` (lines 89–93)
   but no `serve`. The runbook calls `forge serve` as the container
   `CMD`. FEAT-FORGE-009 must either (a) add `forge serve` as part of
   this feature, or (b) declare a hard prerequisite on a forge-side
   feature that adds it. Recommendation: bundle into FEAT-FORGE-009 —
   the daemon is what the image *is for*, so splitting them gives no
   release leverage.
2. **Healthcheck port matrix.** What port does `forge serve` bind?
   What metrics, if any? This bleeds into the LES1 PORT lesson but at
   the TCP level, not the dispatch level. Defer to feature-plan.
3. **ARFS storage backend.** ARFS = artefact registry filesystem; the
   container needs writable scratch (build artefacts, history
   manifests). Volume mount strategy (named volume vs. bind mount vs.
   tmpfs) is a deployment-shaped question, not a Dockerfile-shaped
   one — but the Dockerfile must declare the `VOLUME` paths. Defer
   path enumeration to feature-plan.
4. **`nats-core` source inside the container.** Forge's `pyproject.toml`
   resolves `nats-core` from the sibling working tree
   (`../nats-core`, editable). That path doesn't exist in a container
   build context. Three resolutions:
     a. wait for upstream PyPI fix to `nats-core` and use it
        non-editable;
     b. publish forge's own `nats-core` wheel to a private index and
        consume it;
     c. include `../nats-core/` in the Docker build context (e.g. by
        running `docker build` from a parent dir with a
        `--build-context` for nats-core).
   This is a *blocker-shaped* open question — without a resolution,
   the image will fail to build. FEAT-FORGE-009's feature-spec must
   pick one. Recommendation: (a) if upstream `nats-core` ships a fixed
   wheel by then; otherwise (c) with a documented Docker BuildKit
   `--build-context nats-core=../nats-core` invocation in Phase 6.1.
5. **Source-copy strategy.** `pip install .[providers]` in the builder
   stage installs forge into `/opt/venv` as a proper distribution. Do
   we *also* need to copy `src/forge/` into the runtime stage? Only if
   the runtime imports forge by file path rather than by package name.
   Confirm before feature-plan.
6. **CI integration.** Build-on-PR vs. build-on-merge, registry choice
   (GHCR? Internal?), tagging strategy. Pure DevOps, defer.
7. **Image-size budget.** Slim base + LangChain ecosystem typically
   produces a 600–900 MB image. Worth a target and a regression check
   in CI; not a blocker for v1.
8. **Secrets at runtime.** `.env` injection vs. Docker secrets vs.
   K8s Secrets vs. cloud-provider parameter store. Pure deployment
   concern; the Dockerfile should be deployment-mechanism-agnostic
   (don't bake `.env` parsing into the image) — defer.

## 9. Recommended feature ID + complexity / effort

| Field | Value |
|---|---|
| Recommended feature ID | `FEAT-FORGE-009-production-image` |
| Complexity (1–5 scale used by feat-f8 tasks) | **4** |
| Effort range | **2–4 sessions** for `/feature-spec` + `/feature-plan` + autobuild of the Dockerfile, the `forge serve` subcommand if it doesn't already exist, the build-context resolution for `nats-core`, and a CI workflow that builds + smoke-tests the image. |
| Recommended priority | **high** (Phase 6 of the FEAT-FORGE-008 validation runbook is gated on this; FinProxy first-run cannot proceed canonically until it lands). |
| Recommended scheduling | **Next** — after Wave-2 of FEAT-F8-VALIDATION-FIXES merges. Parallelisable with `TASK-F8-007a` (NATS provisioning handoff to `nats-infrastructure`) since they target different gates. |

The complexity rating reflects:
- multi-stage Dockerfile (low)
- `forge serve` daemon implementation if not already present (medium —
  this is the bulk of the work)
- `nats-core` build-context decision + wiring (medium-high — depends
  on which of options 4a/b/c is taken)
- LES1 §3 DKRX literal-match check in CI (low)
- HEALTHCHECK + image-size regression (low)

## 10. Acceptance shape (for FEAT-FORGE-009, not for this scoping task)

Sketched here so `/feature-spec` has a starting point — **not binding**:

- AC-A: `Dockerfile` at repo root; `docker build -t
  forge:production-validation -f Dockerfile .` succeeds on a fresh
  clone (with whatever `--build-context` the §11.4 resolution
  prescribes).
- AC-B: `docker run forge:production-validation forge --help` shows the
  full CLI surface.
- AC-C: `docker run forge:production-validation forge serve` runs as a
  long-lived process, subscribes to `pipeline.build-queued.*`, picks
  up a published payload (CMDW round-trip).
- AC-D: Image manifest contains every tool from §3.3 (ARFS check).
- AC-E: `pip install .[providers]` literal-match: `grep` against the
  Dockerfile must match the install command in
  `RUNBOOK-FEAT-FORGE-008-validation.md` §0.4.
- AC-F: No real provider keys in any layer; CI scan gate per `pyproject.toml`
  line 655 is green.
- AC-G: Image runs as non-root.
- AC-H: HEALTHCHECK declared and green for a healthy `forge serve`.
- AC-I: CI builds + smoke-tests the image on every PR touching
  `Dockerfile`, `pyproject.toml`, or `src/forge/`.
- AC-J: RUNBOOK-FEAT-FORGE-008-validation.md §6 gating callout is
  removed when this feature merges.

## 11. Handoff record (TASK-F8-007b AC-3)

**Chosen path:** **backlog item**, not immediate `/feature-spec`.

Rationale:
- `/feature-spec` is interactive — the operator should run it when
  prioritised against other queued work, not auto-spawned from this
  doc.
- The §11 open questions (especially §11.1 `forge serve` and §11.4
  `nats-core` source) need an operator-side decision before
  `/feature-spec` can converge.
- The recommended priority is "next after Wave-2", which gives the
  operator a clear cue without forcing the call now.

**Backlog pointer** (filed as part of TASK-F8-007b's completion):
`tasks/backlog/FEAT-FORGE-009-production-image.md` (stub, points at
this doc).

When the operator is ready, the next command is:

```
/feature-spec FEAT-FORGE-009-production-image
```

…with this scoping doc as the seed input.

## 12. Cross-references touched by this scoping

- **`docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md` §6.1** —
  updated (TASK-F8-007b AC-4) to point at this scoping doc and the
  recommended `FEAT-FORGE-009` feature instead of just citing
  TASK-F8-007b in isolation.
- **`docs/research/ideas/forge-build-plan.md` line 656** — the
  existing "deferred, FEAT-FORGE-009+" annotation against `Dockerfile`
  is now backed by this scoping doc; no change needed.
- **`docs/handoffs/F8-007a-nats-canonical-provisioning.md`** — sibling
  delegation; this doc is its FEAT-FORGE-009 counterpart on the
  Dockerfile axis.
