---
id: TASK-REV-A7D3
title: /system-arch artefact polish before /system-design (supersedes TASK-DOC-B2A4)
status: in_progress
created: 2026-04-19T00:00:00Z
updated: 2026-04-19T00:00:00Z
priority: high
tags: [architecture-review, docs, adr, polish, verification, pre-system-design]
complexity: 4
task_type: review
decision_required: false
review_mode: architectural
review_depth: standard
estimated_effort: 30-45 minutes (excluding §5 spike, which adds 1-2 hours)
supersedes:
  - TASK-DOC-B2A4
source_feedback:
  origin: external-review
  received: 2026-04-19
  scope_summary: |
    External review of forge/docs/architecture/ completed 2026-04-19.
    Paperwork polish + two verifications. No structural changes to ADRs.
    Blocks /system-design until acceptance criteria met.
test_results:
  status: not_applicable
  coverage: null
  last_run: null
---

# Task: /system-arch artefact polish before /system-design

## Description

Close out the post-/system-arch review findings before `/system-design`
starts. Four paperwork items and one verification spike, all flagged by
the external review of `forge/docs/architecture/` on 2026-04-19.

This task **supersedes TASK-DOC-B2A4** — the Decision-Index update for
ADR-031 is folded in as scope item §1 below. TASK-DOC-B2A4 should be
closed/archived when this task completes.

## Origin

External review of `forge/docs/architecture/` completed 2026-04-19. The
review found no ADR-level structural issues but surfaced five discrete
polish items that should land before `/system-design` runs.

## Scope

### In scope

1. **ARCHITECTURE.md §13 Decision Index** — add ADR-031 row, bump header
   count from "30 ADRs" to "31 ADRs". Category: "Implementation
   substrate" (matches ADR-ARCH-020). Folded in from TASK-DOC-B2A4;
   that task's Acceptance Criteria apply verbatim.

2. **ADR-012 and ADR-022 Status section format** — reformat from inline
   bullet `- **Status:** Accepted` to heading style
   `## Status\n\nAccepted` to match the parser expectation noted in
   `command-history.md`. Re-run `guardkit graphiti add-context --force`
   for these two after editing.

3. **ARCHITECTURE.md §3 module count** — recount the module list;
   reconcile the "15 modules" header with the prose (current count
   appears to be 16+ depending on how `guardkit_*` is grouped). Either
   fix the number or restructure the groupings so the count is
   accurate.

4. **ADR-012 (No MCP interface) content review** — given ADR-031 added
   async subagent supervisor tools (`list_async_tasks` etc.), confirm
   ADR-012's reasoning for rejecting MCP still holds and is not subtly
   undermined by the async-subagent observability surface. One read;
   either append a one-line note confirming, or flag for discussion.

5. **Spike: DeepAgents 0.5.3 primitives (ASSUM-008 + ASSUM-009)** —
   1-2 hour verification before `/system-design`:
   - Confirm DeepAgents permissions system actually refuses writes
     outside the `allow_write` allowlist (not just documented
     behaviour).
   - Confirm LangGraph `interrupt()` survives external resume with
     typed Pydantic payload round-trip (write a minimal two-file
     repro).
   - Capture findings in
     `docs/research/ideas/deepagents-053-verification.md`.
   - If either primitive fails, **ADR-021 and ADR-023 need revision
     before /system-design** — spawn a separate revision task; do not
     mutate those ADRs from this task.

### Out of scope

- Any reopening of ADR-016, ADR-019, ADR-023 thesis. These are settled.
- Restructuring the module map or C4 diagrams.
- Compressing ADR-031 from 135 → 60-80 lines (deferred per TASK-REV-C7D1).
- Full ADR-by-ADR read of the 18 ADRs not covered in external review
  (003, 004, 009, 013, 014, 017, 018, 024, 027-030). Optional follow-up
  if confidence wanted before `/system-plan`.

## Acceptance Criteria

- [ ] `docs/architecture/ARCHITECTURE.md` §13 lists 31 ADRs (prose
      count updated; ADR-031 row present, category "Implementation
      substrate").
- [ ] ADR-012 and ADR-022 reformatted to `## Status\n\nAccepted`
      heading style; `guardkit graphiti add-context --force` re-run
      cleanly for both.
- [ ] `docs/architecture/ARCHITECTURE.md` §3 module count matches the
      prose list (either header count corrected or groupings
      restructured).
- [ ] ADR-012 reviewed post-ADR-031; one-line confirmation note
      appended, OR a discussion flag raised in this task's
      Implementation Notes.
- [ ] `docs/research/ideas/deepagents-053-verification.md` committed
      with findings for both ASSUM-008 (permissions) and ASSUM-009
      (interrupt round-trip) verifications summarised.
- [ ] No new ADRs created by this task. If the §5 spike fails, a
      separate revision task is spawned for ADR-021 / ADR-023 — this
      task does not mutate those ADRs directly.
- [ ] TASK-DOC-B2A4 closed/archived as superseded by this task (commit
      message references both IDs).

## Not Doing / Decisions Captured

- **Residual session drift**: none found requiring ADR-level revision.
- **Course-correction arc**: documented in ARCHITECTURE.md + ADR
  Context sections; no further archaeology needed.
- **Optional follow-up**: full read of the 18 non-reviewed ADRs is
  *optional* confidence work before `/system-plan`, not a blocker for
  `/system-design`.

## Method

1. **§1 Decision Index** — open `docs/architecture/ARCHITECTURE.md`,
   jump to §13, bump "30 ADRs" → "31 ADRs", append ADR-031 row
   (category "Implementation substrate"). Reference
   `TASK-DOC-B2A4-architecture-decision-index-add-adr-arch-031.md`
   for the exact row shape.

2. **§2 Status reformat** — edit
   `docs/architecture/decisions/ADR-ARCH-012-*.md` and
   `docs/architecture/decisions/ADR-ARCH-022-*.md`. Replace the inline
   `- **Status:** Accepted` bullet with `## Status\n\nAccepted`
   heading. Run `guardkit graphiti add-context --force <path>` for
   each; confirm clean ingestion.

3. **§3 Module count** — open ARCHITECTURE.md §3, enumerate the
   module list, count authoritatively. Either update the header or
   re-group `guardkit_*` entries so the count is consistent. Keep the
   diff minimal.

4. **§4 ADR-012 post-ADR-031 review** — read ADR-012 in full with
   ADR-031's async-supervisor tools in mind. Decision tree:
   - If ADR-012's rejection reasoning still holds → append a one-line
     note in ADR-012's Context section (e.g., "Reconfirmed
     post-ADR-031 2026-04-19: async supervisor tools remain internal,
     no MCP surface needed.").
   - If it is subtly undermined → do NOT edit ADR-012; record the
     concern in this task's Implementation Notes and flag for
     discussion.

5. **§5 Spike** — create a scratch directory under `spikes/` or
   `docs/research/ideas/spikes/` (decide at edit time). Two minimal
   repros:
   - **Permissions**: DeepAgents agent with `allow_write=["/tmp/ok/**"]`
     attempts write to `/tmp/forbidden/` — must refuse at runtime, not
     just log.
   - **Interrupt round-trip**: two-file LangGraph repro where
     `interrupt(payload: PydanticModel)` pauses the graph, an external
     process resumes with a typed `Command(resume=PydanticModel(...))`,
     and the model instance is recovered with types intact on the
     other side.
   - Write findings to `docs/research/ideas/deepagents-053-verification.md`.
   - If either fails: spawn a revision task (e.g., TASK-ADR-REVISE)
     and mark this task blocked on that task's completion.

## Source Material

- `docs/architecture/ARCHITECTURE.md` (§3 module count, §13 Decision
  Index).
- `docs/architecture/decisions/ADR-ARCH-012-*.md` (No MCP interface —
  format + content review).
- `docs/architecture/decisions/ADR-ARCH-022-*.md` (format only).
- `docs/architecture/decisions/ADR-ARCH-021-*.md` (DeepAgents
  permissions — ASSUM-008 backing ADR).
- `docs/architecture/decisions/ADR-ARCH-023-*.md` (LangGraph interrupt
  — ASSUM-009 backing ADR).
- `docs/architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md`
  (the row to add, and the async-supervisor surface that motivates
  §4).
- `tasks/backlog/TASK-DOC-B2A4/TASK-DOC-B2A4-architecture-decision-index-add-adr-arch-031.md`
  (superseded; §1 inherits its Acceptance Criteria).
- `tasks/in_review/TASK-REV-F1B8/TASK-REV-F1B8-analyse-claude-desktop-feedback-on-adr-arch-031.md`
  (parent review that produced ADR-031).
- `.claude/reviews/TASK-REV-F1B8-review-report.md` (review report).
- `command-history.md` (Status-heading parser expectation reference
  for §2).

## Known Risks / Watch-outs

- **Graphiti re-ingestion**: `guardkit graphiti add-context --force`
  can fail silently on malformed frontmatter. Verify the tool's exit
  code and re-read the ingested episode before declaring §2 done.
- **§3 module count semantics**: "15 modules" may reflect an
  intentional grouping choice, not a miscount. Read the surrounding
  prose before deciding between "fix the number" and "restructure the
  groupings".
- **§5 spike scope creep**: the brief is verification, not
  improvement. If a primitive works, record it and move on — do not
  propose abstractions around it.
- **§5 spike failure**: explicitly handled by spawning a separate
  revision task. Do NOT edit ADR-021 or ADR-023 from this task, even
  if the fix looks obvious.
- **Commit discipline**: keep §1, §2, §3, §4 as separate commits (or
  at minimum clearly separated in a single commit message) so each
  can be reverted independently if a downstream issue is traced back.

## Test Requirements

- §1, §2, §3: doc-only; verification by visual diff + markdown
  re-render + Graphiti ingestion exit code.
- §4: narrative; verification by peer review of the note/flag.
- §5: executable repros; each must run cleanly (or fail informatively)
  on the current DeepAgents 0.5.3 + LangGraph pinned versions.

## Implementation Notes

_(Populated at execution time.)_
