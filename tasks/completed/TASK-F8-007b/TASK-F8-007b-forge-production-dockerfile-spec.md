---
id: TASK-F8-007b
title: "Scope forge production Dockerfile → sibling FEAT-FORGE-009"
task_type: documentation
status: completed
priority: medium
created: 2026-04-29T00:00:00Z
updated: 2026-04-30T00:00:00Z
completed: 2026-04-30T00:00:00Z
completed_location: tasks/completed/TASK-F8-007b/
parent_review: TASK-REV-F008
feature_id: FEAT-F8-VALIDATION-FIXES
wave: 3
implementation_mode: direct
complexity: 3
dependencies: []
tags: [docs, scoping, dockerfile, les1, containerisation, feat-forge-008, f008-val-007]
related_files:
  - docs/scoping/F8-007b-forge-production-dockerfile.md
  - docs/research/ideas/forge-build-plan.md
  - docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md
  - tasks/backlog/FEAT-FORGE-009-production-image.md
test_results:
  status: n/a
  coverage: null
  last_run: 2026-04-30T00:00:00Z
  notes: |
    Pure docs/scoping task (implementation_mode=direct). No automated test
    surface. Acceptance is structural:
      - AC-1: scoping doc at docs/scoping/F8-007b-forge-production-dockerfile.md ✅
      - AC-2: FEAT-FORGE-009 id + complexity 4 / 2–4 sessions estimate ✅
      - AC-3: handoff = backlog stub at tasks/backlog/FEAT-FORGE-009-production-image.md ✅
      - AC-4: RUNBOOK §6 callout updated to point at scoping doc + FEAT-FORGE-009 ✅
      - AC-5: scoping doc + downstream stub both exist (Dockerfile build itself
              is deferred to FEAT-FORGE-009 per the task's own AC-5).
---

# Task: Scope forge production Dockerfile → sibling FEAT-FORGE-009

## Description

The runbook's Phase 6.1 expects `docker build -t forge:production-validation
-f Dockerfile .` to succeed, but no `Dockerfile` exists in the repo. This
makes the LES1 CMDW (canonical multi-stage docker), PORT (port matrix), and
ARFS (artefact registry filesystem) gates structurally unreachable today.

Per the architectural review §4 + `Q4=delegate`, this is **NOT folded into
F8** as an implementation task. The Dockerfile is a substantial piece of
work — multi-stage build, dep audit, CI integration, smoke-image testing,
LES1 gate compliance — and folding it into F8 would inflate the validation
fix scope and tie its review/merge cycle to a DevOps-shaped problem.

Instead, this task **scopes** a sibling feature (recommended id:
`FEAT-FORGE-009-production-image`) and hands off to `/feature-spec` for
that new feature. The Dockerfile build itself is then its own
autobuild-able feature on its own timeline.

## Acceptance Criteria

- [ ] **AC-1**: A scoping document is written at
      `docs/scoping/F8-007b-forge-production-dockerfile.md` containing:

  1. **Problem statement**: why forge needs a production Dockerfile
     (LES1 Phase 6 gates: CMDW / PORT / ARFS / canonical-freeze).
  2. **LES1 gate requirements**: explicit gate-by-gate criteria from
     `docs/research/ideas/forge-build-plan.md` (or the LES1 spec
     wherever it lives canonically).
  3. **Image baseline**: which base image (Debian slim? Alpine?
     distroless? Python image?) and Python version (3.12 or 3.14 per
     the F0E4 alignment).
  4. **Multi-stage layout**: builder vs runtime stages, what gets
     copied between them, how editable installs are eliminated.
  5. **Entrypoint**: the canonical `forge` CLI command surface that
     should be available at `docker run`.
  6. **Health probe**: what `HEALTHCHECK` instruction (if any) is needed.
  7. **Open questions** (out of scope for this scoping task): port
     matrix details, ARFS storage backend, CI integration mechanics —
     defer to the new feature's `/feature-spec` and `/feature-plan`
     work.

- [ ] **AC-2**: The scoping doc proposes a feature ID (e.g.
      `FEAT-FORGE-009-production-image`) and an estimated complexity /
      effort range so the operator can decide priority.
- [ ] **AC-3**: A handoff is recorded — either by running
      `/feature-spec FEAT-FORGE-009` directly off this task, or by
      filing a backlog item that points at the scoping doc, depending
      on whether the operator wants to autobuild the Dockerfile feature
      as the next thing or schedule it later.
- [ ] **AC-4**: The forge runbook (after TASK-F8-006 gap-fold lands) at
      §6.1 references this scoping doc / the new feature so future
      walkthroughs know Phase 6 is gated on FEAT-FORGE-009 landing.
- [ ] **AC-5**: This task's status is closed when the scoping doc is
      merged AND a downstream feature/spec/issue exists — NOT when the
      Dockerfile itself is built (that's the new feature's delivery).

## Implementation Notes

- Pure docs/scoping task. Implementation mode = `direct`.
- LES1 spec lookup: search the build plan
  (`docs/research/ideas/forge-build-plan.md`) and any `architecture_decisions`
  graph entries for "LES1", "CMDW", "PORT", "ARFS", "canonical-freeze".
  The Graphiti context for this review found a "freeze-as-canonical"
  action exists for forge/jarvis/study-tutor — use that as a starting
  reference if a dedicated LES1 spec doc isn't already pinpointed.
- Be opinionated about the recommendation. The next operator should be
  able to read this scoping doc and know whether to (a) `/feature-spec`
  immediately, or (b) park it on the backlog with rough priority.

## Out of scope

- Writing the actual Dockerfile (FEAT-FORGE-009's job).
- Building / tagging / publishing forge images (FEAT-FORGE-009's job).
- Wiring the Dockerfile into CI (FEAT-FORGE-009's job).
- Changing forge's runtime dependency tree to fit the image (only
  flagging if it needs to happen).
