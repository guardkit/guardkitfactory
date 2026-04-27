# Feature Spec Summary: Mode B Feature & Mode C Review-Fix

**Feature ID**: FEAT-FORGE-008
**Stack**: python
**Generated**: 2026-04-27T00:00:00Z
**Scenarios**: 56 total (6 smoke, 5 regression)
**Assumptions**: 17 total (10 high / 7 medium / 0 low confidence)
**Review required**: No — all assumptions traceable to supplied context files and inherited from FEAT-FORGE-007

## Scope

Specifies Forge's two non-greenfield orchestration modes built on the FEAT-FORGE-001..007
substrate. **Mode B (Feature)** drives a single new feature on an existing project
through `/feature-spec → /feature-plan → autobuild → pull-request review`, deliberately
skipping the product-owner / architect / `/system-arch` / `/system-design` upstream
stages that Mode A performs — the project's existing architecture and design baseline
are taken as given. **Mode C (Review-Fix)** runs the `/task-review → /task-work` cycle
on an existing subject, dispatching one `/task-work` per fix task identified by the
review, optionally culminating in a pull-request review when the cycle has pushed
commits and otherwise terminating with a clean-review outcome. Both modes inherit the
async-subagent dispatch pattern, the LangGraph interrupt round-trip with build-keyed
approval channel, durable-history-authoritative crash recovery (retry-from-scratch),
CLI steering (cancel → synthetic reject; skip honoured on non-constitutional stages
and refused on pull-request review), idempotent first-write-wins on duplicate
responses, correlation-identifier threading from queue to terminal, calibration-priors
snapshot stability, and the constitutional belt-and-braces rule that pins
pull-request review to mandatory human approval at both prompt and executor layers.
Behaviour is described in domain terms; the AsyncSubAgent state channel, NATS
approval channel, SQLite history, and worktree allowlist surface only as capability
observations.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 9 |
| Boundary conditions (@boundary) | 6 |
| Negative cases (@negative) | 8 |
| Edge cases (@edge-case) | 11 |
| Smoke (@smoke) | 6 |
| Regression (@regression) | 5 |
| Security (@security) | 4 |
| Concurrency (@concurrency) | 4 |
| Data integrity (@data-integrity) | 7 |
| Integration (@integration) | 6 |
| Mode B scope (@mode-b) | 39 |
| Mode C scope (@mode-c) | 28 |

Note: many scenarios carry multiple tags (e.g. @mode-b + @mode-c when behaviour is
shared, @boundary + @negative for just-outside boundaries, @edge-case + @concurrency
for cross-cutting expansion). Group totals and tag totals do not sum to 56.

## Group Layout

| Group | Theme | Scenarios |
|-------|-------|-----------|
| A | Key Examples — Mode B full chain to PR-awaiting-review, forward propagation, async-subagent dispatch, constitutional PR-review pin, flag/resume cycle, session-outcome chain; Mode C full review-fix cycle, fix-task forward propagation, optional PR-review pin | 9 |
| B | Boundary Conditions — Mode B single-feature, Mode B stage-ordering invariant outline, Mode B empty-spec rejection, Mode C empty-fix-task short-circuit, Mode C fix-task count outline (1, 3, 5), Mode C stage-ordering invariant outline | 6 |
| C | Negative Cases — Mode B feature-spec hard-stop, Mode B failed feature-spec halts inner loop, max-score does not auto-approve PR review, skip refused at PR review, Mode B autobuild internal hard-stop blocks PR creation, reject decision is terminal, Mode C task-review hard-stop, Mode C failed task-work isolation | 8 |
| D | Edge Cases — Mode B crash-recovery outline, Mode C crash-recovery outline, durable-history authority on async crash, cancel during pause, cancel during async, skip on non-constitutional stage, approval routed by build identifier, duplicate response idempotent, Mode C cycle terminates on follow-up clean review | 9 |
| E | Security — Mode B/C constitutional belt-and-braces holds against misconfigured prompt, subprocess override claim ignored at gating, Mode B/C subprocess worktree-allowlist confinement | 3 |
| F | Concurrency — two concurrent Mode B builds with isolated channels and task IDs, Mode B and Mode C concurrent with isolated chains, supervisor dispatches second build's stage during first build's async stage | 3 |
| G | Data Integrity — Mode B canonical stage-history ordering (no PO/architect/arch/design entries), Mode C canonical stage-history ordering (review precedes work), per-fix-task artefact attribution, notification publish failure does not regress approval | 4 |
| H | Integration Boundaries — minimal Mode B E2E smoke, minimal Mode C E2E smoke, internal async-stage pause observable via supervisor, correlation threading queue→terminal | 4 |
| I | Expansion — first-wins on simultaneous approvals, calibration-priors snapshot stability, memory-seeding failure does not regress approval | 3 |
| J | Security expansion — Mode B refuses to dispatch /system-arch or /system-design even if manifest references them | 1 |
| K | Concurrency expansion — three concurrent builds (Mode A + Mode B + Mode C) with isolated channels and stage chains | 1 |
| L | Data Integrity expansion — Mode B records no degraded-specialist rationale (positive assertion of no-PO/no-architect axiom), Mode C fix-task lineage from review to work | 2 |
| M | Integration Boundaries expansion — Mode B no-diff autobuild does not attempt PR creation | 1 |
| N | Mode-interaction expansion — follow-up feature after Mode A is fresh Mode B build, Mode C with no commits ends in clean-review terminal | 2 |

## Deferred Items

None.

## Assumptions Summary

| ID | Confidence | Subject | Response |
|----|------------|---------|----------|
| ASSUM-001 | high | Mode B chain composition (skip PO/architect/arch/design) | confirmed |
| ASSUM-002 | high | Mode B autobuild reuses AsyncSubAgent pattern | confirmed |
| ASSUM-003 | high | Constitutional PR rule applies in every mode | confirmed |
| ASSUM-004 | high | Mode C chain composition (/task-review → /task-work × N) | confirmed |
| ASSUM-005 | medium | Mode C culminates in PR review when changes are pushed | confirmed |
| ASSUM-006 | high | Mode B is single-feature per build | confirmed |
| ASSUM-007 | high | Empty /task-review → no /task-work, clean-review terminal | confirmed |
| ASSUM-008 | medium | Failed /task-work isolated to its fix task | confirmed |
| ASSUM-009 | high | Crash-recovery: durable history authoritative | confirmed |
| ASSUM-010 | medium | Mode C terminates on follow-up clean review (no numeric cap) | confirmed |
| ASSUM-011 | high | Constitutional PR enforcement is mode-agnostic | confirmed |
| ASSUM-012 | medium | Calibration-priors snapshot stability for build duration | confirmed |
| ASSUM-013 | medium | Mode-aware planning refuses upstream Mode A stages in Mode B | confirmed |
| ASSUM-014 | high | Mode B does not dispatch to PO/architect specialists | confirmed |
| ASSUM-015 | medium | Mode B no-diff autobuild → no PR attempt, no-op terminal | confirmed |
| ASSUM-016 | high | Each queued build is its own lifecycle (fresh build IDs) | confirmed |
| ASSUM-017 | medium | Mode C with no commits → clean-review terminal, no PR | confirmed |

## Upstream Dependencies

- **FEAT-FORGE-001** — Pipeline State Machine & Configuration. The build queue,
  state-machine transitions, durable history, crash recovery (retry-from-scratch),
  and CLI steering surface are referenced as the substrate every Mode B and Mode C
  stage rides on. FEAT-FORGE-008 adds no new transitions; it composes them.
- **FEAT-FORGE-002** — NATS Fleet Integration. The pipeline-event publishing
  (correlation threading) and approval channel are inherited; FEAT-FORGE-008
  specifies how the supervisor sequences Mode B and Mode C dispatches over them.
  Mode B and Mode C do not exercise the live discovery cache for specialists
  because they do not dispatch to specialist agents.
- **FEAT-FORGE-004** — Confidence-Gated Checkpoint Protocol. The auto-approve /
  flag-for-review / hard-stop / mandatory-human-approval gate modes, the
  build-keyed approval round-trip, idempotent first-wins, max-wait refresh, CLI
  cancel/skip mapping, and the constitutional PR-review rule are inherited;
  FEAT-FORGE-008 specifies how those gates compose across the two non-greenfield
  chains.
- **FEAT-FORGE-005** — GuardKit Command Invocation Engine. The subprocess contract
  for /feature-spec, /feature-plan, autobuild, /task-review, and /task-work —
  including context-flag construction and worktree confinement — is inherited;
  FEAT-FORGE-008 specifies the order and inputs for Mode B and Mode C.
- **FEAT-FORGE-006** — Infrastructure Coordination. Long-term-memory seeding,
  priors retrieval at build start, test verification, and git/gh PR creation are
  inherited; FEAT-FORGE-008 specifies how their failure modes interact with the
  build's authoritative recorded progress in Mode B and Mode C.
- **FEAT-FORGE-007** — Mode A Greenfield End-to-End. The capstone composition
  patterns, async-subagent dispatch shape, constitutional belt-and-braces, and
  per-feature artefact attribution conventions are inherited; FEAT-FORGE-008 adapts
  these to the shorter Mode B chain (no upstream delegation/architecture stages)
  and the cyclic Mode C chain (review → work iteration with optional PR review).

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "Mode B Feature & Mode C Review-Fix" \
      --context features/mode-b-feature-and-mode-c-review-fix/mode-b-feature-and-mode-c-review-fix_summary.md

`/feature-plan` Step 11 will link `@task:<TASK-ID>` tags back into the
`.feature` file after tasks are created.
