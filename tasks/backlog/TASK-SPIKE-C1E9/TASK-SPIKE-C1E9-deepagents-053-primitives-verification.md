---
id: TASK-SPIKE-C1E9
title: DeepAgents 0.5.3 primitives verification (ASSUM-008 permissions + ASSUM-009 interrupt round-trip)
status: backlog
created: 2026-04-19T00:00:00Z
updated: 2026-04-19T00:00:00Z
priority: high
tags: [spike, verification, deepagents, langgraph, adr-021, adr-023, pre-system-design]
complexity: 5
task_type: research
decision_required: false
parent_review: TASK-REV-A7D3
scoping_source: .claude/reviews/TASK-REV-A7D3-review-report.md §5
blocks:
  - /system-design
estimated_effort: 1-2 hours
source_feedback:
  origin: TASK-REV-A7D3 §5 scoping
  received: 2026-04-19
  scope_summary: |
    Verification spike spawned from TASK-REV-A7D3 [I]mplement decision.
    Verifies two load-bearing DeepAgents 0.5.3 / LangGraph primitives
    before /system-design runs. If either fails, spawn a separate ADR
    revision task; do NOT mutate ADR-021 or ADR-023 from this spike.
test_results:
  status: not_applicable
  coverage: null
  last_run: null
---

# Task: DeepAgents 0.5.3 primitives verification

## Description

Verify at runtime that two DeepAgents 0.5.3 / LangGraph primitives behave
as their backing ADRs assume. Both assumptions are currently documented
behaviour only, and both are load-bearing for Forge's architecture:

- **ASSUM-008** (backs ADR-ARCH-023 — permissions as constitutional
  safety): the DeepAgents permissions system **refuses writes** outside
  the `allow_write` allowlist at runtime, not merely logs or warns.
- **ASSUM-009** (backs ADR-ARCH-021 — PAUSED via `interrupt()`):
  LangGraph `interrupt()` survives external resume with a **typed
  Pydantic payload** round-trip — the resumed value is a fully-typed
  Pydantic model instance, not a dict or serialised blob.

Full scoping, repro designs, success/failure criteria, and risk register
live in `.claude/reviews/TASK-REV-A7D3-review-report.md` §5. This task
file carries the acceptance criteria; the review report carries the
detailed design.

`/system-design` is **blocked on this task's completion.** Findings
must be committed to `docs/research/ideas/deepagents-053-verification.md`
before `/system-design` runs.

## Origin

Spawned from TASK-REV-A7D3 [I]mplement decision on 2026-04-19. §5 of
that task (the two verification spikes) was scoped but not executed
during the review, so it could live in a discrete commit trail with
bounded scope. TASK-REV-A7D3 §1–§4 (doc paperwork) are complete; this
spike is the last remaining gate before `/system-design`.

## Scope

### In scope

1. Minimal DeepAgents agent repro for permissions refusal
   (`spikes/deepagents-053/permissions_repro.py`).
2. Minimal two-file LangGraph repro for `interrupt()` + external
   `Command(resume=PydanticModel(...))` round-trip
   (`spikes/deepagents-053/interrupt_graph.py`,
   `spikes/deepagents-053/interrupt_resume.py`).
3. Findings file committed:
   `docs/research/ideas/deepagents-053-verification.md`, summarising
   results for both ASSUM-008 and ASSUM-009.
4. On **failure** of either primitive: spawn a separate revision task
   for the affected ADR (`TASK-ADR-REVISE-023-*` or
   `TASK-ADR-REVISE-021-*`). Mark this spike as blocked on that new
   task, and keep `/system-design` blocked until it resolves.

### Out of scope

- Integration with the Forge agent graph. Repros run standalone.
- Testing alternative pin ranges (e.g. 0.6.x). Pin is `>=0.5.3, <0.6`
  per ADR-ARCH-020.
- Improvements or abstractions around either primitive **if it works**.
  Verification is binary — record and move on. The parent task's Known
  Risks explicitly flag this as a scope-creep risk.
- Edits to ADR-021 or ADR-023 directly from this spike, even on
  failure. Revisions happen in a spawned task with its own review.

## Acceptance Criteria

- [ ] `spikes/deepagents-053/permissions_repro.py` exists and has been
      executed at least once. Result (pass/fail) is observed.
- [ ] `spikes/deepagents-053/interrupt_graph.py` and `interrupt_resume.py`
      exist and have been executed together to demonstrate a full
      pause-and-resume cycle. Result (pass/fail) is observed under
      both `langgraph dev` and direct `CompiledStateGraph.invoke`
      execution modes.
- [ ] `docs/research/ideas/deepagents-053-verification.md` is committed
      with one-paragraph findings for each of ASSUM-008 and ASSUM-009.
- [ ] If ASSUM-008 fails: `TASK-ADR-REVISE-023-*` exists in backlog;
      `/system-design` explicitly blocked on it.
- [ ] If ASSUM-009 fails: `TASK-ADR-REVISE-021-*` exists in backlog;
      `/system-design` explicitly blocked on it.
- [ ] Findings file is linked from ADR-021 and ADR-023's References
      section (append-only, one line each).
- [ ] Commit message references `TASK-SPIKE-C1E9` and `TASK-REV-A7D3`
      (and, if applicable, the spawned revision task IDs).

## Method

Follow the execution checklist in
`.claude/reviews/TASK-REV-A7D3-review-report.md` §5 (*"Execution
checklist (for the spawned spike task)"*) verbatim. That checklist
already covers pre-flight, ASSUM-008, ASSUM-009, and close-out. It is
the canonical source of sequence and stop-conditions for this task.

**Do not re-scope the spike from this task file.** The scoping is
frozen in the review report so that any divergence in interpretation
is explicit.

## Source Material

- `.claude/reviews/TASK-REV-A7D3-review-report.md` §5 — full scoping,
  repro designs, risk register, execution checklist.
- `docs/architecture/decisions/ADR-ARCH-021-paused-via-langgraph-interrupt.md`
  — ASSUM-009 backing ADR.
- `docs/architecture/decisions/ADR-ARCH-023-permissions-constitutional-safety.md`
  — ASSUM-008 backing ADR.
- `docs/architecture/decisions/ADR-ARCH-020-adopt-deepagents-builtins.md`
  — pin rationale (`>=0.5.3, <0.6`).
- DeepAgents 0.5.3 release notes (15 April 2026) — fetch at execution
  time via WebFetch if needed, do not rely on cached derivations.

## Known Risks / Watch-outs

- **Scope creep.** If a primitive works, record a one-paragraph
  finding and stop. Do not propose abstractions.
- **Mode divergence on `interrupt()`.** `langgraph dev` server and
  direct `.invoke` may behave differently. Test both. If they diverge,
  that is itself a finding.
- **Permissions interference with spike filesystem.** Run the
  permissions repro with `allow_write=["/tmp/ok/**"]` explicitly;
  spike directory lives outside permission scope.
- **Findings file omission.** The acceptance criterion explicitly
  requires `docs/research/ideas/deepagents-053-verification.md`. Make
  writing the file the **first** action after observing either result.
- **ADR mutation.** Do NOT edit ADR-021 or ADR-023 directly. On
  failure, spawn a revision task.

## Test Requirements

- Executable repros. Each must run cleanly (pass or fail
  informatively) on the current DeepAgents 0.5.3 + LangGraph pinned
  versions.
- Findings file is prose; verification is peer review by Rich.

## Implementation Notes

_(Populated at execution time.)_
