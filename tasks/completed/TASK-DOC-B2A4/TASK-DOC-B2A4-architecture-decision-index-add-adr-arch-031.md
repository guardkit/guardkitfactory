---
id: TASK-DOC-B2A4
title: Add ADR-ARCH-031 to ARCHITECTURE.md Decision Index §13
status: superseded
superseded_by: TASK-REV-A7D3
created: 2026-04-19T00:00:00Z
updated: 2026-04-19T00:00:00Z
priority: low
tags: [docs, architecture, adr-index, follow-up]
complexity: 1
task_type: declarative
parent_review: TASK-REV-F1B8
source_commitment:
  origin: conversation-capture-2026-04-19-fleet-v3-framing
  line: 260
  verbatim: |
    Forge ARCHITECTURE.md — add reference to ADR-ARCH-031 in Decision Index §13
test_results:
  status: not_applicable
  coverage: null
  last_run: null
---

# Task: Add ADR-ARCH-031 to ARCHITECTURE.md Decision Index §13

## Description

Append-only doc update to keep the Forge Decision Index current with the
new amendment ADR created by TASK-REV-F1B8.

This is the deferred follow-up explicitly flagged in
`docs/research/ideas/conversation-capture-2026-04-19-fleet-v3-framing.md`
line 260, and marked **out of scope** by TASK-REV-F1B8's Scope section.

## Source Material

- `docs/architecture/ARCHITECTURE.md` §13 Decision Index (the table to
  extend).
- `docs/architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md`
  (the ADR to reference).
- `tasks/backlog/TASK-REV-F1B8/TASK-REV-F1B8-analyse-claude-desktop-feedback-on-adr-arch-031.md`
  (parent review — describes why the ADR was added).
- `.claude/reviews/TASK-REV-F1B8-review-report.md` (review findings +
  recommendations).

## Scope

### In scope
- Append a single row to the Decision Index table in `docs/architecture/ARCHITECTURE.md` §13 for ADR-ARCH-031.
- Update the prose count ("30 ADRs" → "31 ADRs") on §13's opening sentence.
- Choose a category for the row that is consistent with ADR-ARCH-020's
  category ("Implementation substrate") — this amendment lives in that
  same category.

### Out of scope
- No edits to ADR-ARCH-020, ADR-ARCH-031, or any other ADR.
- No edits to the Forge README, command_history.md, CLAUDE.md, or other
  top-level docs.
- No renumbering, no table restructuring — append-only.

## Acceptance Criteria

- [ ] `docs/architecture/ARCHITECTURE.md` §13 opening prose reads
      "31 ADRs captured across the 6 categories" (or similar) rather
      than "30 ADRs".
- [ ] A new row exists in the table between ADR-ARCH-030 and the
      horizontal rule, with the form:
      `| ADR-ARCH-031 | Async subagents for long-running work; sync task() for bounded delegation | Implementation substrate |`
      (or a short title variant agreed at edit time — the category
      must be "Implementation substrate" to match ADR-ARCH-020).
- [ ] No other diffs to `ARCHITECTURE.md`.
- [ ] Commit message includes `TASK-DOC-B2A4` and references the
      parent review `TASK-REV-F1B8`.

## Method

1. Open `docs/architecture/ARCHITECTURE.md`, jump to §13.
2. Change the prose count from "30 ADRs" to "31 ADRs".
3. Append one row to the bottom of the table, immediately after the
   ADR-ARCH-030 row and before the closing `---`.
4. Sanity-check the diff is only two line changes.
5. Commit with a message of the form:
   `docs(architecture): add ADR-ARCH-031 to Decision Index §13 (TASK-DOC-B2A4; follow-up to TASK-REV-F1B8)`.

## Known Risks / Watch-outs

- **Category choice**: "Implementation substrate" matches ADR-ARCH-020.
  Do not invent a new category.
- **Title length**: keep the row title close in spirit to ADR-031's
  `# ADR-ARCH-031: Async subagents for long-running work; sync task() for bounded delegation`
  but trim if the existing table's visual rhythm is disturbed.
- **No renumbering**: if a future ADR-ARCH-032 has been added in the
  meantime, append after whatever is the highest existing row.

## Test Requirements

Doc-only task. Verification is by visual diff and by re-rendering the
markdown to confirm the table remains well-formed.

## Implementation Notes

**Superseded by TASK-REV-A7D3 (2026-04-19).**

This task's full Acceptance Criteria were folded into TASK-REV-A7D3 §1
verbatim. The `ARCHITECTURE.md` §13 edits (prose count `30` → `31` ADRs,
ADR-031 row appended with category *Implementation substrate*) were
executed during TASK-REV-A7D3 and captured in its review report at
`.claude/reviews/TASK-REV-A7D3-review-report.md` §§1.

No additional work required here. Task archived as `status: superseded`.
Commit message on the archival move should reference both `TASK-DOC-B2A4`
and `TASK-REV-A7D3`.
