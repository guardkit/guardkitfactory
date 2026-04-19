# Review Report: TASK-REV-F1B8

**Task**: Analyse Claude Desktop feedback proposing ADR-ARCH-031 (AsyncSubAgent vs sync task() amendment to ADR-ARCH-020)
**Mode**: architectural · **Depth**: standard · **Date**: 2026-04-19
**Reviewer**: `/task-review` (architectural-review agent-equivalent, Opus reasoning)
**Related feedback**: Claude Desktop, 2026-04-19 (see task front-matter `source_feedback.verbatim`)
**Supporting context**: `docs/research/ideas/conversation-capture-2026-04-19-fleet-v3-framing.md` (lines 50, 56, 61, 69, 243, 260, 310)

---

## Executive Summary

The amendment proposed by Claude Desktop is **technically sound, architecturally consistent, and correctly scoped** as a light-touch refinement of ADR-ARCH-020 rather than a rewrite. The split — `autobuild_runner` → `AsyncSubAgent`, `build_plan_composer` → sync `task()` — is well justified by the bounded-vs-unbounded runtime asymmetry, and the claimed benefits (cancellation, mid-flight steering, forge_status narrative) are all realisable in DeepAgents 0.5.3 via the five supervisor tools.

**Unusual situation surfaced by the review:** the ADR-ARCH-031 file already exists on disk at `docs/architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md` (untracked in git as of 2026-04-19). A prior session appears to have pre-executed the **[I]mplement** outcome. This review therefore evaluates the *existing draft* against the acceptance criteria rather than drafting from scratch.

**Disposition recommendation: [I]mplement** — apply three small corrections to the existing draft, then commit. The amendment itself is accepted; the artefacts need minor completion work before they meet the task's acceptance criteria.

**Score: 78 / 100.** Substantive content is correct; three formal gaps prevent a clean [A]ccept.

---

## Proposal Validation Table

| Claim | Verdict | Evidence |
|---|---|---|
| `AsyncSubAgent` is a public TypedDict in DeepAgents `>=0.5.3, <0.6` | ✅ Confirmed | `.claude/rules/patterns/subagent-composition.md` lines 52-69 (name/description/graph_id/url fields); `.claude/agents/subagent-composition-specialist.md` (capabilities + boundaries); conversation capture line 56 (docs fetch) |
| Sync `task()` remains the bounded delegation tool | ✅ Confirmed | ADR-ARCH-020 Decision table row `task` (line 31); Forge's own `@tool` pattern docs |
| Five supervisor tools exist (`start_async_task`, `check_async_task`, `update_async_task`, `cancel_async_task`, `list_async_tasks`) | ✅ Confirmed | Conversation capture lines 56, 61; draft ADR-031 table at lines 57-65 |
| `autobuild_runner` is long-running (30 min – several hours) | ✅ Plausible | ADR-ARCH-014 (single-consumer/max-ack-pending=1), ADR-ARCH-027 (no horizontal scaling) both presume long single-stream builds |
| `build_plan_composer` is bounded and output-gates the next stage | ✅ Confirmed | ADR-ARCH-007 (build plan as gated artefact); conversation capture line 69 (original framing) |
| 2-pre-declared-subagent invariant preserved | ✅ Confirmed | Draft ADR-031 lines 11-14 and 31-34 name the same two and add no third |
| Amendment is additive to ADR-ARCH-020, not a rewrite | ✅ Confirmed | Draft line 5 `Amends: ADR-ARCH-020`; line 27 "not a reopening" |
| No numbering collision with other in-flight ADRs | ✅ Confirmed | Highest existing is ADR-ARCH-030 (`ls docs/architecture/decisions/`); 031 slot free |

---

## ADR Cross-Reference Table

| ADR | Disposition | Rationale | In draft? |
|---|---|---|---|
| **ADR-ARCH-002** (two-model separation) | **Unaffected** | Sync/async is orthogonal to reasoning-vs-implementation model split. `build_plan_composer` still consumes the implementation model; `autobuild_runner` runs subprocess-heavy workloads where the model choice is downstream. | Not cross-referenced — acceptable gap; ADR-031 is about shape, not model tier. |
| **ADR-ARCH-007** (build plan as gated artefact) | **Affected — amendment consistent** | Keeping `build_plan_composer` sync preserves the blocking-gate semantic. The draft's "output gates next stage" language (line 18) is the exact framing from ADR-007 + conversation capture line 69. | ❌ Not explicitly cross-referenced. **Recommend adding** a single-line reference to ADR-ARCH-007 in the Context section. |
| **ADR-ARCH-008** (Forge produces own history) | **Affected — amendment consistent** | `command_history.md` writes inside `autobuild_runner` now happen in an async subgraph. Crash recovery for those writes is covered by the existing SQLite + JetStream reconciliation path (ADR-SP-013, referenced by the draft at line 69). No new history semantics. | ✅ Indirectly via ADR-SP-013 reference; adding a one-line ADR-ARCH-008 cross-reference would strengthen the audit trail. |
| **ADR-ARCH-020** (adopt DeepAgents built-ins) | **Affected — amendment consistent** | The amended ADR. Draft labels itself as amendment. | ⚠️ **Annotation gap** — ADR-020's body was not annotated with a cross-reference back to ADR-031. Per TASK-REV-C3E7 "append-only ADR corrections" precedent this is required. **Blocker for [A]ccept.** |
| **ADR-ARCH-021** (PAUSED via `interrupt()`) | **Affected — amendment consistent, but unverified in draft** | If `interrupt()` fires inside `autobuild_runner`, it halts the async subgraph (not the supervisor graph). The supervisor observes via `check_async_task` / `list_async_tasks`, and the NATS approval resume path (ADR-021) targets the paused subgraph specifically. Conversation capture line 310 confirms: *"Forge feels like a batch processor because it uses sync `task()` for bounded gates and `interrupt()` for approval pauses"* — interrupts remain the pause mechanism even when the calling context is async. | ❌ Not explicitly verified in draft. **Acceptance criterion 4 requires this.** |

---

## Benefits-Verification Table

| Claimed benefit | Mechanism in DeepAgents 0.5.3 | Verified? | Draft reference |
|---|---|---|---|
| **Cancellation** (respond to `forge cancel FEAT-XXX`) | `cancel_async_task` supervisor tool; LangGraph async cancellation of in-flight node | ✅ | Draft lines 25, 64, 103 |
| **Mid-flight steering** (“skip remaining wave-3 tasks”) | `update_async_task` supervisor tool; state updates between async turns; resumes via NATS approval round-trip if the steering requires Rich's decision | ✅ | Draft lines 25, 62, 104 |
| **Meaningful `forge status` narrative** | `list_async_tasks` reads the `async_tasks` state channel which survives context compaction; supervisor projects sub-agent `write_todos` progress outward | ✅ | Draft lines 25, 65, 80-94 (illustrative narrative example) |

All three benefits are realisable at the pinned SDK version. No blocker.

**Caveat:** `AsyncSubAgent` is marked as a preview feature in 0.5.3. API evolution risk is acknowledged in the draft (line 111) and mitigated by the `>=0.5.3, <0.6` pin. If 0.6 changes the five-tool surface, ADR-031 will need its own *"Decision facts as of commit: {sha}"* line per the LES1 §8 anchor-v2.2 convention enforced by TASK-REV-C3E7.

---

## Interrupt-Interaction Analysis

**Question**: Does putting `autobuild_runner` behind `AsyncSubAgent` change how ADR-ARCH-021's PAUSED-via-`interrupt()` works?

**Answer**: No — but the interaction deserves explicit coverage in the ADR, which is currently missing.

- Approval gates that fire *inside* `autobuild_runner` call `interrupt()` on the `autobuild_runner` subgraph, not on the supervisor.
- The LangGraph runtime surfaces the interrupt on that subgraph's thread. The NATS approval subscriber (ADR-ARCH-021) resumes *that* graph with the typed `ApprovalResponsePayload`.
- The supervisor's view is unchanged: `check_async_task` returns `paused` / `awaiting_input`, `list_async_tasks` shows the pending interrupt, and `update_async_task` can be used by the supervisor to steer without waiting for the approval.
- Crash recovery: the SQLite + JetStream reconciliation path in ADR-ARCH-021 (lines 44, 52) + ADR-SP-013 is unchanged. The `async_tasks` state channel gives the supervisor an extra restart signal, but the authoritative approval-protocol state is still in SQLite.

**Recommendation**: add a short **"Interaction with ADR-ARCH-021 (interrupt())"** sub-section to ADR-031's Consequences (or a dedicated paragraph before "Crash recovery"). 4–6 lines is enough.

---

## Draft Quality Audit

| Criterion | Target | Actual | Verdict |
|---|---|---|---|
| Filename matches conventions | kebab-case slug after id | `ADR-ARCH-031-async-subagents-for-long-running-work.md` | ✅ Matches conversation-capture line 243; task §7 suggestion `async-vs-sync-subagents` is also defensible but the capture-line name has anchor precedence |
| Header format (Status / Date / Session) | Match neighbouring ADRs | ✅ Plus additive `Amends:` and `Related:` fields | ✅ |
| Structure: Context / Decision / Consequences | Required | ✅ All three present, plus `Do-not-reopen` + `References` | ✅ |
| Explicitly labels as amendment to ADR-020 | Required | ✅ Line 5 | ✅ |
| Target length ≤ 60 lines | Soft target | **127 lines** | ⚠️ Over target by >2×. Some content (crash recovery §, forge history narrative §, `langgraph.json` shape) pushes into *design* territory. Task Known Risks flags this: *"If the draft grows beyond that, it is probably trying to re-litigate ADR-ARCH-020 and should be pruned."* — applies partially here. Recommend pruning to 60-80 lines by shrinking the illustrative history example and moving `langgraph.json` detail to a follow-up design note. |
| Status field | Should be `Proposed` before decision checkpoint; `Accepted` only after | Currently `Accepted` | ⚠️ Premature. Either (a) keep `Accepted` because this review is the checkpoint and we are resolving [I]mplement, or (b) downgrade to `Proposed` until commit. Treat as cosmetic. |
| ADR-020 annotation present | Required by AC 6 | **Not present** | ❌ Blocker for [A]ccept. Add a one-line appendix to ADR-ARCH-020. |
| "short-lived" vs "bounded" framing | Known Risks prefers "bounded, output gates next stage" | Draft uses "runs briefly (seconds to a minute) and its output gates the next stage" (line 18) and "bounded and sub-minute" (line 36) | ✅ Close enough. Both framings co-exist; the bounded-with-gate rationale is present. |

---

## Divergence Log (source material vs draft)

1. **Conversation capture line 69 rationale** (`autobuild_runner` async because long-running + non-blocking supervisor; `build_plan_composer` sync because bounded + gates next stage) — faithfully reflected in draft lines 18-19, 31-36. No divergence.
2. **Conversation capture line 243 filename** (`ADR-ARCH-031-async-subagents-for-long-running-work.md`) — matches draft filename exactly. No divergence.
3. **Conversation capture line 260** (follow-up to add ADR-ARCH-031 to ARCHITECTURE.md Decision Index §13) — **out of scope** for this task; should be carried forward as a separate follow-up task if [I]mplement is chosen.
4. **Conversation capture line 310** ("Forge feels like a batch processor because it uses sync `task()` for bounded gates and `interrupt()` for approval pauses") — consistent with the amendment. The async subagent does not change Forge's batch feel; it adds observability during long builds.

No divergences require a finding-level escalation.

---

## Findings (8)

1. **[MEDIUM] ADR-ARCH-020 annotation missing.** AC 6 requires a single-line appendix in ADR-020 pointing to ADR-031. Currently ADR-020 is unmodified.
2. **[MEDIUM] interrupt() interaction not explicitly verified in the ADR body.** AC 4 requires explicit coverage. The interaction is clean (see §Interrupt-Interaction Analysis above), but the ADR must state it.
3. **[LOW] Draft length exceeds 60-line target by >2×.** 127 lines vs ≤60. Recommend pruning illustrative `forge history` narrative and/or moving `langgraph.json` config detail to a follow-up design note.
4. **[LOW] ADR cross-references not complete.** ADR-ARCH-002, -007, -008 are not explicitly named in ADR-031. Adding three one-line `See: ADR-ARCH-XXX` entries to the References section closes the audit trail.
5. **[LOW] ADR status field is `Accepted` before the review checkpoint has resolved.** Cosmetic; either correct or interpret this review as the checkpoint.
6. **[INFO] "Short-lived" framing co-exists with "bounded, output gates next stage".** Known Risks prefers the latter; both are present in the draft — acceptable as-is.
7. **[INFO] `AsyncSubAgent` is a preview feature in 0.5.3.** Mitigated by the `>=0.5.3, <0.6` pin + ongoing release-note monitoring commitment (draft line 111).
8. **[INFO] Follow-up: ARCHITECTURE.md Decision Index §13** must reference ADR-031 (conversation capture line 260; **out of scope** for this task — carry as a follow-up).

---

## Recommendations (5)

1. **Add a one-line annotation to ADR-ARCH-020** pointing to ADR-031. Example append (after line 55, at the bottom of the file):

   ```markdown
   ---
   **Amendment — 2026-04-19:** The sync-vs-async split for the two pre-declared sub-agents (`build_plan_composer` sync; `autobuild_runner` async via `AsyncSubAgent`) is refined in [ADR-ARCH-031](./ADR-ARCH-031-async-subagents-for-long-running-work.md). This is additive; the Context and Decision sections above are unchanged.
   ```

2. **Add a short "Interaction with ADR-ARCH-021" paragraph to ADR-031.** Target location: before the "Crash recovery" sub-section. 4–6 lines covering: (a) `interrupt()` fires inside the async subgraph; (b) the NATS approval resume path targets that subgraph; (c) supervisor observes via `check_async_task` / `list_async_tasks`; (d) no new invariants, no change to the external approval protocol.

3. **Prune ADR-031 toward 60–80 lines.** Shrink the illustrative `forge history` narrative to a one-paragraph example and move the `langgraph.json` sample + full "Crash recovery" detail to a follow-up design note in `docs/architecture/notes/` (new folder or `docs/architecture/container.md` addendum). The ADR carries the *decision*; design mechanics belong in a design note.

4. **Add explicit cross-references** to ADR-ARCH-002, -007, -008 in the References section of ADR-031 (one line each). This closes the audit trail required by AC 3.

5. **Create a follow-up task** (not part of this review) to update `docs/architecture/ARCHITECTURE.md` Decision Index §13 with the ADR-031 reference (conversation capture line 260).

---

## Decision Options

**[A] Accept** — Mark findings 1–5 as non-blockers, accept the draft as-is. Not recommended: AC 6 (ADR-020 annotation) and AC 4 (interrupt() verification) are explicit, and the draft fails both.

**[I] Implement** — Apply recommendations 1, 2, 4 now; optionally 3 (pruning) and 5 (follow-up task) in the same commit. This closes all acceptance criteria and ships the amendment cleanly. **Recommended.**

**[R] Revise** — Re-run the review with comprehensive depth (e.g. also verifying DeepAgents 0.5.3 release notes directly via WebFetch, not just via Forge's derived docs). Not needed — the SDK surface is well-attested in Forge's own pattern file and specialist-agent boundaries, and the conversation capture records the verification chain.

**[C] Cancel** — Discard the review, revert the untracked ADR-031 file. Not recommended — the amendment is correct and the only issues are completeness gaps.

**Reviewer recommendation: [I] Implement** — apply recommendations 1, 2, 4 (required by AC) and 5 (follow-up); 3 (length pruning) optional and defensible either way.

---

## Implementation Artefacts (ready-to-apply if [I] chosen)

### Artefact 1: ADR-ARCH-020 annotation

Append at the end of `docs/architecture/decisions/ADR-ARCH-020-adopt-deepagents-builtins.md` (after current line 55):

```markdown

---

**Amendment — 2026-04-19:** The sync-vs-async split for the two pre-declared sub-agents (`build_plan_composer` sync; `autobuild_runner` async via `AsyncSubAgent`) is refined in [ADR-ARCH-031](./ADR-ARCH-031-async-subagents-for-long-running-work.md). This is additive; the Context and Decision sections above are unchanged.
```

### Artefact 2: ADR-ARCH-031 "Interaction with ADR-ARCH-021" insertion

Insert before the existing "Crash recovery" subsection in ADR-031 (i.e. before current line 67):

```markdown
### Interaction with ADR-ARCH-021 (`interrupt()`)

`interrupt()` continues to be the PAUSED mechanism (ADR-ARCH-021). When an approval gate inside `autobuild_runner` calls `interrupt()`, it halts the async subgraph, not the supervisor. The supervisor observes the paused state via `check_async_task` / `list_async_tasks`; the NATS `ApprovalResponsePayload` subscriber resumes the specific subgraph that interrupted. The external approval protocol (ApprovalRequest published, SQLite marks PAUSED) is unchanged — the `async_tasks` state channel supplements, rather than replaces, the SQLite + JetStream crash-recovery path.
```

### Artefact 3: ADR-ARCH-031 References section additions

Append to the References section of ADR-031 (before the existing `ADR-ARCH-020` line or directly beneath it):

```markdown
- ADR-ARCH-002 (two-model separation — orthogonal; sync/async is shape-not-model)
- ADR-ARCH-007 (build plan as gated artefact — `build_plan_composer` stays sync because its output gates)
- ADR-ARCH-008 (Forge produces its own history — autobuild history files written from inside the async subagent)
- ADR-ARCH-021 (PAUSED via `interrupt()` — see Interaction sub-section above)
```

### Follow-up task (out of scope, to be created on [I] Implement)

**Title:** `Update ARCHITECTURE.md Decision Index §13 to reference ADR-ARCH-031`
**Rationale:** Conversation capture line 260 commitment. Append-only index update; trivial.

---

## Sub-Decision Summary (for the checkpoint)

| Sub-decision | Status |
|---|---|
| SDK validated (`AsyncSubAgent` + sync `task()` + 5 supervisor tools in 0.5.3) | ✅ Yes |
| 2-pre-declared-subagent invariant preserved | ✅ Yes |
| ADR cross-references clean | ⚠️ Partial (three ADRs not explicitly named; fix in Artefact 3) |
| Benefits verified (cancellation, steering, forge_status narrative) | ✅ Yes |
| `interrupt()` interaction clean | ✅ Yes in principle; ❌ not yet in the ADR body (fix in Artefact 2) |
| ADR-020 annotation applied | ❌ Not yet (fix in Artefact 1) |

---

## Context Used (knowledge-graph provenance)

_Graphiti knowledge-graph was not available in this session (no MCP tool call succeeded and no `.guardkit/graphiti.yaml` enabled file was present). Review performed from codebase analysis only — source of truth was:_

- `source_feedback.verbatim` block in the task front-matter
- `docs/research/ideas/conversation-capture-2026-04-19-fleet-v3-framing.md` (supporting)
- `docs/architecture/decisions/ADR-ARCH-{002,007,008,020,021,030,031}.md`
- `.claude/rules/patterns/subagent-composition.md`
- `.claude/agents/subagent-composition-specialist.md`

No external documentation was fetched; the claim that `AsyncSubAgent` + five tools exist at 0.5.3 is taken from Forge's own codified reading (pattern file + specialist agent) and from the conversation capture's explicit record of docs-fetch. If the reviewer wants direct verification against `docs.langchain.com/oss/python/deepagents/async-subagents`, run a WebFetch before committing — this would upgrade confidence but is not strictly required to clear the acceptance criteria.
