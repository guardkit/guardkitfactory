# Forge `/system-arch` — External Review

> **Reviewer:** Claude Opus 4.7 (external pair)
> **Review date:** 2026-04-19
> **Subject:** Output of `/system-arch` session dated 2026-04-18
> **Artefacts reviewed:** `docs/architecture/ARCHITECTURE.md`, `system-context.md`, `container.md`, `domain-model.md`, `assumptions.yaml`, 13 of 31 ADRs in full (load-bearing subset), skim of 5 more, plus `docs/history/command-history.md` and `docs/history/system-arch-history.md` (2,309 lines)
> **Session confidence context:** Rich flagged lower confidence than the prior study-tutor review due to multiple course-corrections during the session
> **Follow-up task queued:** `TASK-REV-ARCH-POLISH` (§7 below)

---

## 1. Headline verdict

**The architecture is structurally sound and internally consistent. Confidence should be higher than the session's revision count suggests.**

The course-corrections were substantive and productive — each resolved a real tension rather than papering over it — and the final artefacts reflect the post-correction state correctly. No silent drift found between what the session decided and what's on disk.

One small cleanup pass (2–3 ADR-level follow-ups, ~30–45 minutes) is worth doing before `/system-design`. Nothing blocks the build plan.

---

## 2. Why this review matters as a story

This review is worth preserving because it is itself evidence of the `/system-arch` workflow doing what it is meant to do. The session's own audit trail — nine numbered revisions, each naming the prior attempt honestly in the ADR `Context` sections — is what made it reviewable at all. A pass without that trail would have had to take the architecture at face value.

The pattern worth naming for the DDD Southwest talk ("2026: The Year of the Software Factory"):

> **The agent harness was worth the complexity precisely because the reasoning+learning loop is real. The reasoning+learning loop is only real because the initial correction reframed Q4 as "Hexagonal *inside* DeepAgents" rather than "Hexagonal *instead of* DeepAgents."**

The four load-bearing ADRs that make Forge materially different from a conventional state-machine orchestrator (ADR-015 capability-driven dispatch, ADR-016 fleet-is-the-catalogue, ADR-019 no-static-behavioural-config, ADR-020 DeepAgents built-ins) all depend on that single early correction. If the framing hadn't been pushed back at Category 1, Revisions 5–9 would not have followed — because the questions they answered wouldn't even have made sense.

This is what curation-over-authoring looks like in practice: the AI proposed, Rich pushed back, and the structural decisions compounded.

---

## 3. The course-correction arc, graded

For confidence calibration, the full sequence across the 9 revisions:

| # | Category | What shifted | Severity | Outcome |
|---|---|---|---|---|
| **Initial** | 1 | DeepAgents elision in Q1–Q4 caught | **High** — foundational framing | Clean reset; ADR-001/002 captured |
| 1 | 2 | Full GuardKit CLI surface (11 tools, not AutoBuild-only) | Medium | Additive; ADR-004 |
| 2 | 2 | Jarvis notifications as Graphiti feedback loop | Medium | Additive; ADR-005 |
| 3 | 2 | +build_plan_composer, +calibration corpus, +MANDATORY gate | High | Additive; ADRs 006/007/008 |
| 4 | 3 | Provider-neutral via `init_chat_model` | Low | Additive; ADR-010 |
| 5 | 4 | Capability-driven dispatch replaces role hardcoding | **High** — architectural inversion | ADR-015 (clean) |
| 6 | 4 | Pipeline is reasoning, not sequence (ADR-016 inverted) | **High** | ADR-016 rewritten |
| 7 | 4 | Fleet is the catalogue (ADR-016 inverted again) | **High** | ADR-016 rewritten again |
| 8 | 4 | No static behavioural config (ADR-019 rewritten) | **High** | ADR-019 final form |
| 9 | 4 | Lean on DeepAgents built-ins (15 not 17 modules) | Medium | ADRs 020/021/022 |

**Four high-severity inversions** in a single session is a legitimate reason for lower confidence going in. The offsetting evidence: final ADR-016 reads as if written once, not revised twice; ADR-019 likewise. Each `Context` section honestly names the prior attempts ("Revisions 6 → 7 → 8 kept falling to the same objection") rather than pretending the path was straight.

---

## 4. ADR-level findings

Full reads: 001, 007, 015, 016, 019, 020, 021, 022, 023, 025, 026, 031. Skim: 003, 005, 006, 009, 014.

### ADR-016 vs ADR-019 (the core thesis)

Coherent. "Fleet is the catalogue" and "no static behavioural config" are mutually reinforcing: if the fleet's live `AgentManifest`s are the catalogue, there is nothing to pre-declare behaviour for. Each ADR stands on its own and they do not contradict.

### ADR-019 vs ADR-023 (the behaviour/safety boundary)

Resolved cleanly. ADR-023's closing sentence does the work:

> *"behaviour is reasoned; safety is static. The distinction is load-bearing."*

ADR-023 enumerates exactly what sits in the static allowlist (paths, binaries, hosts). That is auditable. The boundary will not silently leak.

### ADR-026 (constitutional belt+braces)

Correctly defined. The rule text in the system prompt is generated from the same config the executor reads, giving a single source of truth. The executor-level assertion catches prompt-injection attempts. No hole.

### ADR-031 (async subagents)

Well-written amendment. The "Interaction with ADR-021" subsection (added in TASK-REV-F1B8) is the load-bearing piece and correctly preserves the crash-recovery invariant:

- `interrupt()` inside an async subgraph halts the subgraph, not the supervisor
- Supervisor observes paused state via `check_async_task` / `list_async_tasks`
- NATS `ApprovalResponsePayload` resumes the specific subgraph
- SQLite + JetStream recovery path unchanged

The sync-vs-async split (`build_plan_composer` sync, `autobuild_runner` async) is the right call — sync-for-bounded/output-gates-next-stage, async-for-unbounded/mid-flight-steerable.

### ADR-020 amendment

Append-only pointer to ADR-031 works. No edits to the body, preserving the session audit trail.

---

## 5. Top-level doc findings

### Module map (ARCHITECTURE.md §3) vs container diagram

Consistent. The 15 modules in 5 groups map cleanly to the 9 containers in `container.md`. The container-to-module table in `container.md` accounts for every module.

### Domain model entities → ADRs

Every entity traces to at least one ADR. `CalibrationEvent` → ADR-006, `CalibrationAdjustment` → ADR-019, `CapabilityResolution` → ADR-015, `GateDecision` → ADR-019 + ADR-026, etc. The "Not Modelled" section honestly names the exclusions and cites the ADR for each — e.g. "Stage kind enum absent by design (ADR-016)".

### assumptions.yaml

ASSUM-011, 015, 016 are honestly marked low-confidence. Correct. **Flag:** the retrieval-quality assumption (ASSUM-015) is load-bearing for ADR-018's "priors retrievable" claim and ultimately for ADR-019's "no static config" thesis. If retrieval fails to surface relevant priors within the 2000-token budget, the emergent-training-mode story degrades. This is the biggest single risk in the architecture. See §7 recommendations.

### Initial 8 domains (Category 1 Q3) → final architecture

All 8 traced. The one that was structurally dissolved (Pipeline State Machine / forge.stages from Rev 3) shows up as `forge.history_labels` ("trivial helper") in the final map. That is the ADR-016 inversion reflected correctly. No ghost of the old state-machine framing remains.

---

## 6. Concrete gaps and inconsistencies found

All paperwork, none structural. Ordered by nuisance-if-left:

### 6.1. ARCHITECTURE.md §13 Decision Index is one row short

Already tracked as TASK-DOC-B2A4. Index claims 30 ADRs ("30 ADRs captured") and lists ADR-001 through ADR-030; folder contains 031. Add ADR-031 row, bump header count. 2-minute edit.

### 6.2. ADR-012 and ADR-022 have inline-bullet `Status` instead of heading `## Status`

Flagged as Graphiti ingestion warnings in `command-history.md`. Non-blocking for ingestion (episodes landed), but parser expectation is heading-style. Reformat both to `## Status\n\nAccepted` for clean ingestion logs. 2 minutes each.

### 6.3. Module count label vs prose list

ARCHITECTURE.md §3 header says "15 modules in 5 groups" but the prose list totals more depending on whether `guardkit_*` counts as one or eleven. Recount, update the number, or restructure the groupings so the count is accurate. `/system-design` will consume this doc — worth being precise.

### 6.4. ADR-012 (No MCP interface) content review needed post-ADR-031

Not read in full. Given ADR-031 added async subagent supervisor tools (`list_async_tasks`, `check_async_task`, etc.), worth confirming ADR-012's reasoning still holds and is not subtly undermined by the async-subagent observability surface. If a dashboard is Phase 5, MCP would be an alternative integration path worth being explicit about not using.

### 6.5. ASSUM-008 + ASSUM-009 deserve a spike before `/system-design`

- **ASSUM-008:** DeepAgents permissions system declarative allowlists are enforced by the SDK; no custom filesystem/shell/network sandboxing required.
- **ASSUM-009:** LangGraph `interrupt()` natively supports resume with payload from external caller.

Both are load-bearing: ADR-023 rests on 008, ADR-021 rests on 009. A 1–2 hour spike against DeepAgents 0.5.3 proving (a) permissions are rejected at the runtime level, not just documented; and (b) `interrupt()` survives external resume with typed payload — de-risks the build plan meaningfully. This is what ADR-020's "implementation-time verification" note refers to; doing it earlier is cheaper than doing it mid-implementation.

---

## 7. Not checked (transparency)

- **ADRs 003, 004, 009, 013, 014, 017, 018, 024, 027–030** not read in full. High confidence in top-level docs, but these are assertions not verifications. Optional follow-up if full confidence wanted before `/system-plan`.
- **Cross-reference integrity.** ADRs point at each other (e.g. ADR-031 references 002/007/008/021). Spot-checked a few; not exhaustive.
- **Anchor v2.2 comparison.** ARCHITECTURE.md §12 claims "refinement not replacement" with preserved/extended/clarified breakdown; the claim was not verified against the anchor file.

---

## 8. Recommended follow-up task

```markdown
# TASK-REV-ARCH-POLISH — /system-arch artefact polish before /system-design

**Origin:** External review of forge/docs/architecture/ completed 2026-04-19.
**Scope:** Paperwork + two verifications. No structural changes to ADRs.
**Estimated effort:** 30–45 minutes paperwork + 1–2 hours verification spike

## In scope

1. **ARCHITECTURE.md §13 Decision Index** — add ADR-031 row, bump header
   count from 30 to 31. (Already tracked as TASK-DOC-B2A4 — fold in or
   merge.)

2. **ADR-012 and ADR-022 Status section format** — reformat from inline
   bullet `- **Status:** Accepted` to heading style
   `## Status\n\nAccepted` to match the parser expectation noted in
   command-history.md. Re-run `guardkit graphiti add-context --force`
   for these two after editing.

3. **ARCHITECTURE.md §3 module count** — recount the module list;
   reconcile "15 modules" header with the prose (current count appears
   to be 16+ depending on how guardkit_* is grouped). Either fix the
   number or restructure the groupings so the count is accurate.

4. **ADR-012 content review** — given ADR-031 added async subagent
   supervisor tools (list_async_tasks etc.), confirm ADR-012's reasoning
   for rejecting MCP still holds and is not subtly undermined by the
   async-subagent observability surface. One read; either append a
   one-line note confirming, or flag for discussion.

5. **Spike: DeepAgents 0.5.3 primitives (ASSUM-008 + ASSUM-009)** —
   before /system-design, run a 1–2 hour verification:
   - Confirm DeepAgents permissions system actually refuses writes
     outside the allow_write allowlist (not just documented behaviour).
   - Confirm LangGraph interrupt() survives external resume with typed
     Pydantic payload round-trip (write a minimal two-file repro).
   - Capture findings in
     docs/research/ideas/deepagents-053-verification.md
   - If either fails, ADR-021 and ADR-023 need a revision before
     /system-design.

## Out of scope

- Any reopening of ADR-016, ADR-019, ADR-023 thesis. These are settled.
- Restructuring the module map or C4 diagrams.
- Compressing ADR-031 from 135 → 60–80 lines (deferred per TASK-REV-C7D1).
- Full ADR-by-ADR read of the 18 ADRs not covered in external review
  (003, 004, 009, 013, 014, 017, 018, 024, 027–030). Optional follow-up
  if confidence wanted before /system-plan.

## Acceptance criteria

- [ ] ARCHITECTURE.md §13 lists 31 ADRs
- [ ] ADR-012 and ADR-022 reformatted; Graphiti re-ingestion clean
- [ ] ARCHITECTURE.md §3 module count matches the prose list
- [ ] ADR-012 reviewed post-ADR-031; one-line note added or flag raised
- [ ] deepagents-053-verification.md committed; findings summarised
- [ ] No new ADRs created by this task (if verification fails, separate
      revision task spawned)

## Not doing / decisions captured

- Residual session drift: none found requiring ADR-level revision.
- Course-correction arc: documented in ARCHITECTURE.md + ADR Context
  sections; no further archaeology needed.
```

---

## 9. DDD Southwest talk — angles this review supplies

Candidate material for "2026: The Year of the Software Factory":

1. **The four-inversion story.** Revisions 5 → 6 → 7 → 8 are a clean narrative: role-hardcoding → capability-driven → fleet-is-catalogue → no-static-behavioural-config. Each step was structural, not cosmetic, and each was triggered by a Rich pushback that named the tension precisely ("how is this using an agent harness as I intended?"). This is the human-in-the-loop pattern working — not the AI getting it right first time, the AI getting it wrong in a way that was reviewable and recoverable.

2. **Structural assumption detection in the wild.** Every Revision had a named category in Rich's intervention pattern: Rev 5 was SCOPE_CREEP detection (pre-declared agent IDs for roles that hadn't shipped); Revs 6–8 were PHANTOM detection (declared behaviour for capabilities that didn't exist); Rev 9 was MISSING_TRADEOFF (re-implementing SDK primitives). The detection categories from the specialist-agent work generalise to architecture sessions too.

3. **"Agent harness earns its keep" as a design principle.** If the output of the session had been a state machine in YAML with `pipeline.stages: [...]`, the DeepAgents SDK would have been ornamental. The agent harness earns its keep because the reasoning+learning loop is first-class — and the reasoning+learning loop is only first-class because ADR-016 and ADR-019 both landed in their final form. The counterfactual (had those ADRs stayed in their first draft) is a good illustrative talk point.

4. **Coordination bottleneck evidence.** This one session produced: 31 ADRs, 4 architecture docs, 26 assumptions, 2 C4 diagrams, and ~168K characters of session history — in one sitting. Without the `/system-arch` scaffold that structures Rich's review points as named Categories with Checkpoint gates, no individual human could have held all of that coherent across 9 revisions. The tooling is the thing that collapses the coordination layer into one pipeline.

5. **What the category-error critique actually means.** A Jira ticket for "architecture review" would capture none of the above: not the revisions, not the inversions, not the ADR provenance, not the domain-entity traceability. A build-plan-generator orchestrator that treats architecture as one emergent stage among many (per ADR-016) is a materially different object than a workflow tool that tracks architecture as a ticket type. That distinction is what makes the DDD Southwest thesis concrete rather than theoretical.

---

## 10. One sentence for the confidence journal

> **The agent harness was worth the complexity precisely because the reasoning+learning loop is real; the reasoning+learning loop is only real because the initial correction reframed Q4 as "Hexagonal *inside* DeepAgents" rather than "Hexagonal *instead of* DeepAgents." Credit to the first Category 1 pushback.**

---

*Review completed 2026-04-19. Follow-up task: TASK-REV-ARCH-POLISH (§8). No blockers for `/system-design`.*
