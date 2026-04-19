# Review Report: TASK-REV-A7D3

**Task**: `/system-arch` artefact polish before `/system-design` (supersedes TASK-DOC-B2A4)
**Mode**: architectural · **Depth**: standard · **Date**: 2026-04-19
**Reviewer**: `/task-review` (architectural-review agent-equivalent, Opus reasoning)
**Workflow**: Hybrid — inline execution of §1–§4 paperwork + scoping report for §5 spike
**Related**: [TASK-REV-F1B8](../../tasks/in_review/TASK-REV-F1B8/) (parent review), [TASK-DOC-B2A4](../../tasks/backlog/TASK-DOC-B2A4/) (superseded)

---

## Executive Summary

Four of the five scope items (§1–§4) are **paperwork polish** — mechanical, zero-judgment doc edits gated only by consistency. They have been **executed inline** during this review. All acceptance criteria for §1–§4 are met; re-ingestion through the Graphiti parser completes without the "Missing required section: Status" warning that motivated §2.

Item §5 is a **1–2 hour verification spike** against DeepAgents 0.5.3 primitives (ASSUM-008 permissions, ASSUM-009 `interrupt()` round-trip). The spike is the only load-bearing item in the scope — a failure on either primitive invalidates ADR-ARCH-021 and/or ADR-ARCH-023 and blocks `/system-design`. This report **scopes** the spike (objectives, repro designs, success criteria, risk register, follow-up triggers) so it can be executed as a discrete next session without re-deriving the framing.

**Disposition recommendation: [I]mplement** — accept §1–§4 as complete, close this review, and spawn a single follow-up task (`TASK-SPIKE-*`) for the §5 verification work. Spawning as a separate task preserves commit discipline (§1–§4 can be reverted independently) and keeps the spike's scope-creep risk bounded.

**§1–§4 score**: 100/100 (acceptance criteria met verbatim).
**§5 readiness**: Ready to execute. Risk register populated; no pre-work blockers.

---

## §1–§4: Execution Results

### §1 — ARCHITECTURE.md §13 Decision Index

| Check | Result |
|---|---|
| "30 ADRs" → "31 ADRs" prose count updated | ✅ [ARCHITECTURE.md:208](../../docs/architecture/ARCHITECTURE.md#L208) |
| ADR-031 row appended after ADR-030 | ✅ [ARCHITECTURE.md:242](../../docs/architecture/ARCHITECTURE.md#L242) |
| Category = "Implementation substrate" (matches ADR-020) | ✅ |
| Row title verbatim from TASK-DOC-B2A4 suggested shape | ✅ "Async subagents for long-running work; sync \`task()\` for bounded delegation" |
| No other diffs to §13 | ✅ |

Acceptance Criteria (task AC-1): **met**.

### §2 — ADR-012 and ADR-022 Status heading reformat

| Check | Result |
|---|---|
| ADR-012: inline bullet → `## Status\n\nAccepted` | ✅ [ADR-ARCH-012:3-5](../../docs/architecture/decisions/ADR-ARCH-012-no-mcp-interface.md#L3-5) |
| ADR-022: inline bullet → `## Status\n\nAccepted` | ✅ [ADR-ARCH-022:3-5](../../docs/architecture/decisions/ADR-ARCH-022-dual-agent-memory.md#L3-5) |
| Date and Session bullets preserved | ✅ (retained as metadata bullets after Status section) |
| `guardkit graphiti add-context --force` re-ingestion, ADR-012 | ✅ Exit 0, episode `adr_adr-arch-012-no-mcp-interface-for-forge` (nodes=11, edges=14, invalidated=0), no Status-warning |
| `guardkit graphiti add-context --force` re-ingestion, ADR-022 | ✅ Exit 0, episode `adr_adr-arch-022-dual-agent-memory-langgraph-memory-store-graphiti` (nodes=10, edges=11, invalidated=0), no Status-warning (one transient Gemini 503 retried cleanly) |

Acceptance Criteria (task AC-2): **met**.

**Note on parser behaviour**: the parser now accepts the heading-style Status section on both files. Other ADRs (including ADR-031) still use the inline-bullet format; the 2026-04-18 ingestion warnings were specific to these two. No follow-up fleet-wide reformat is implied by this result.

### §3 — ARCHITECTURE.md §3 module count

**Authoritative recount of bulleted entries in §3:**

| Group | Count | Entries |
|---|---|---|
| A. DeepAgents Shell | 3 | `forge.agent`, `forge.prompts`, `forge.subagents` |
| B. Domain Core (pure) | 7 | `forge.gating`, `forge.state_machine`, `forge.notifications`, `forge.learning`, `forge.calibration`, `forge.discovery`, `forge.history_labels` |
| C. Tool Layer (`@tool` functions) | 6 | `dispatch_by_capability`, `approval_tools`, `notification_tools`, `graphiti_tools`, `guardkit_*`, `history_tools` |
| D. Adapters | 5 | `forge.adapters.nats`, `…sqlite`, `…guardkit`, `…graphiti`, `…history_parser` |
| E. Cross-cutting | 3 | `forge.config`, `forge.cli`, `forge.fleet` |

- **Python modules** (A + B + D + E): **18**
- **Tool-layer entries** (C, explicitly `@tool` functions, not modules per the section header): **6**
- **Total bulleted entries**: 24

Original header "15 modules in 5 groups" did not match any defensible count. Updated to: **"5 groups — 18 Python modules + 6 `@tool`-layer entries"** ([ARCHITECTURE.md:37](../../docs/architecture/ARCHITECTURE.md#L37)).

Rationale for the phrasing: Section C explicitly describes its entries as tool *functions*, not modules (lexically: `@tool(parse_docstring=True) functions — Forge-specific only`). Collapsing them into the Python-module count would miscount; listing them separately keeps the header honest while preserving the "5 groups" promise.

Acceptance Criteria (task AC-3): **met**.

### §4 — ADR-012 (No MCP interface) content review post-ADR-031

**Question**: Does ADR-031's addition of five async-supervisor tools (`start_async_task`, `check_async_task`, `update_async_task`, `cancel_async_task`, `list_async_tasks`) subtly undermine ADR-012's rejection of MCP?

**Analysis**: no — and in fact the reverse.

| ADR-012 argument | Post-ADR-031 status |
|---|---|
| MCP serialises full tool schema into every call's context window | Unchanged — ADR-031 adds 5 tools to the Forge tool inventory |
| Forge has ~17–20 tools; MCP overhead is catastrophic at 200–500-turn builds | **Strengthened** — inventory grows to ~22–25 tools post-ADR-031 |
| Forge has no human-interactive use case that Claude Desktop MCP serves | Unchanged — async observability is served via CLI (`forge status` / `forge history`) + NATS event stream + LangSmith traces (ADR-FLEET-001), *not* MCP |
| CLI + NATS cover all external interaction paths | Unchanged — the five supervisor tools are internal to the Forge supervisor graph, not exposed externally |

**Decision (per task decision tree)**: reasoning holds → appended a reconfirmation note to ADR-012's Context section. [ADR-ARCH-012:13](../../docs/architecture/decisions/ADR-ARCH-012-no-mcp-interface.md#L13).

The note explicitly names the five tools and cites the three observability paths (CLI, NATS event stream, LangSmith) so a future reader doesn't have to redo this analysis.

Acceptance Criteria (task AC-4): **met**.

---

## §5: Verification Spike — Scoping

Per the agreed hybrid workflow, §5 is **scoped here**, not executed. It should be executed as a discrete task (recommended: `TASK-SPIKE-*`) before `/system-design` runs. This section captures the framing, repro designs, risk register, and success criteria so the spike can start without re-deriving context.

### Spike objective

Verify that two DeepAgents 0.5.3 / LangGraph primitives behave at runtime as their backing ADRs assume:

- **ASSUM-008** (backs ADR-ARCH-023): the DeepAgents permissions system **refuses writes** outside the `allow_write` allowlist at runtime, not merely logs or warns.
- **ASSUM-009** (backs ADR-ARCH-021): LangGraph `interrupt()` survives external resume with a **typed Pydantic payload** round-trip — i.e. the resumed value is a fully-typed Pydantic model instance, not a dict or serialised blob.

Both assumptions are currently documented behaviour only. Both are load-bearing: ADR-021 (PAUSED via `interrupt()`) and ADR-023 (permissions as constitutional safety) are foundational to the Forge architecture.

### Scope

**In scope (spike):**
1. Minimal DeepAgents agent repro for permissions refusal.
2. Minimal two-file LangGraph repro for `interrupt()` + external `Command(resume=PydanticModel(...))` round-trip.
3. Findings written to `docs/research/ideas/deepagents-053-verification.md`.
4. If a primitive **fails**: spawn a separate revision task for the affected ADR (ADR-021 or ADR-023). Do NOT mutate those ADRs from within the spike.

**Out of scope (spike):**
- Integration with the full Forge agent graph. Repros run standalone.
- Testing alternative pin ranges (e.g. 0.6.x) — pin is `>=0.5.3, <0.6` per ADR-020.
- Upgrades, fixes, or abstractions around either primitive if it works. Verification is binary.

### Repro design — ASSUM-008 (permissions refusal)

**Goal**: observe that a DeepAgents agent configured with `allow_write=["/tmp/ok/**"]` cannot write to `/tmp/forbidden/` at runtime — the call must be refused by the runtime, not merely flagged in logs.

**Minimal repro structure**:
```
spikes/deepagents-053/permissions_repro.py
  - Create DeepAgents agent with permissions: allow_write=["/tmp/ok/**"]
  - Instruct agent (via initial user message) to write to /tmp/forbidden/out.txt
  - Assert: file does NOT exist after run; agent's tool-call response reports refusal
```

**Success criteria**:
- `os.path.exists("/tmp/forbidden/out.txt")` is `False` after agent termination.
- Agent's tool-response transcript contains a refusal indication (exact wording TBD from DeepAgents 0.5.3 release).
- Exit is clean (no unhandled exception from the runtime itself).

**Failure criteria**:
- File is created at the forbidden path.
- Runtime raises an unhandled exception instead of returning a tool-level refusal.
- Agent's transcript does not indicate the write was refused (e.g. it silently "succeeds" returning a fake success message).

**If failure**: spawn `TASK-ADR-REVISE-021-023-<slug>` to revise ADR-ARCH-023 before `/system-design`. Options include: (a) promote permissions enforcement to an executor-side assertion per ADR-026's belt+braces pattern, (b) demote the permissions system from "constitutional safety" to "first-line defence" and add a second enforcement layer, (c) select an alternative primitive.

### Repro design — ASSUM-009 (`interrupt()` round-trip with typed Pydantic payload)

**Goal**: observe that a LangGraph graph calling `interrupt(payload: SomePydanticModel)` can be resumed from an external process via `Command(resume=SomePydanticModel(...))`, and that the value returned into the graph is a fully-instantiated Pydantic model (with types intact, `isinstance` checks passing).

**Minimal repro structure**:
```
spikes/deepagents-053/
  interrupt_graph.py        — defines a two-node graph with interrupt() using an ApprovalPayload Pydantic model
  interrupt_resume.py       — separate entry point that resumes the graph with Command(resume=ApprovalPayload(...))
```

**Success criteria**:
- `interrupt_graph.py` pauses at the interrupt call, returning control to the LangGraph runtime.
- `interrupt_resume.py` successfully resumes the paused graph.
- Inside the resumed graph, the received value satisfies `isinstance(value, ApprovalPayload) is True`.
- All typed fields on the Pydantic model (including nested models, UUIDs, datetimes, Literal types) are preserved.
- Clean exit; graph completes its second node.

**Failure criteria**:
- Resume is not possible from a separate process (e.g. requires in-process reference to the graph).
- Resumed value is a dict, not a Pydantic instance.
- Nested or complex field types (nested models, UUIDs, datetimes) are serialised to strings/dicts and not re-hydrated.
- Resume triggers a validation error on a round-tripped model.

**If failure**: spawn `TASK-ADR-REVISE-021-<slug>` to revise ADR-ARCH-021. Options include: (a) add an explicit `model_validate` step after resume inside the consumer, (b) change the resume payload contract to accept `model_dump()` + explicit deserialisation, (c) select an alternative HITL primitive (e.g. direct NATS approval without LangGraph-side interrupt).

### Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Scope creep into "improvement" work if a primitive works | High | Medium | Task brief is verification only. If it works, record a one-paragraph finding and stop. Do **not** propose abstractions. |
| Network / sandbox interference (e.g. DeepAgents permissions intercepting spike filesystem writes) | Medium | Low | Run repro with permissions explicitly configured for `/tmp/ok/**`. Spike directory lives outside permission scope. |
| LangGraph `interrupt()` semantics differ between `langgraph dev` server and CompiledStateGraph.invoke | Medium | High (invalidates the repro) | Test against both: `langgraph dev` server for the canonical path (matches Forge deployment) and direct `.invoke` for control. Flag divergence in findings. |
| Gemini / LLM API outage during agent runs in permissions repro | Low | Low | Permissions check doesn't require a capable LLM — stub model or use a trivial model response. The agent's *request* to write is scripted, not LLM-decided. |
| DeepAgents 0.5.3 `AsyncSubAgent` preview feature interacts with permissions in an undocumented way | Medium | Medium | Keep the permissions repro sync-only (no AsyncSubAgent). Interaction with async is a separate follow-up if flagged. |
| Findings captured but not written to `deepagents-053-verification.md` | Low | High (AC-5 failure) | Task workflow requires the file as an acceptance criterion. Make writing the file the first action after observing results. |

### Execution checklist (for the spawned spike task)

Pre-flight:
- [ ] Read ADR-ARCH-021, ADR-ARCH-023, and this scoping section.
- [ ] Confirm DeepAgents pin is `>=0.5.3, <0.6` in `pyproject.toml`.
- [ ] Confirm LangGraph version matches what `/system-design` will assume.

ASSUM-008 (permissions):
- [ ] Create `spikes/deepagents-053/permissions_repro.py`.
- [ ] Run; observe refusal or failure.
- [ ] If failure: stop, write finding, spawn revision task for ADR-023, stop spike.
- [ ] If success: write one-paragraph confirmation to `docs/research/ideas/deepagents-053-verification.md`.

ASSUM-009 (`interrupt()` round-trip):
- [ ] Create `spikes/deepagents-053/interrupt_graph.py` and `interrupt_resume.py`.
- [ ] Run; observe typed resume or failure.
- [ ] Test against both `langgraph dev` and direct `.invoke`.
- [ ] If failure (either mode): stop, write finding, spawn revision task for ADR-021, stop spike.
- [ ] If success: write one-paragraph confirmation covering both modes to `docs/research/ideas/deepagents-053-verification.md`.

Close-out:
- [ ] Commit findings file (`docs(research): deepagents 0.5.3 primitives verified — ASSUM-008/-009 (TASK-SPIKE-*)`).
- [ ] Link the findings file from ADR-021 and ADR-023's References section (append-only; one-line each).
- [ ] If revision task spawned: explicitly mark `/system-design` as blocked on that task's completion.

---

## Findings Summary

| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | §13 Decision Index did not reference ADR-031; prose count showed "30 ADRs" | Low | **Fixed** (§1) |
| 2 | Graphiti parser warnings on ADR-012/-022 due to inline-bullet Status format | Low | **Fixed** (§2, re-ingestion clean) |
| 3 | §3 header "15 modules in 5 groups" did not match any defensible recount | Low | **Fixed** (§3, now "5 groups — 18 Python modules + 6 `@tool`-layer entries") |
| 4 | ADR-012 had not been reconciled against ADR-031's async-supervisor tool additions | Low | **Fixed** (§4, reconfirmation note appended to ADR-012 Context) |
| 5 | ASSUM-008 (permissions runtime refusal) is documented-only — load-bearing for ADR-023 | Medium | **Scoped** (§5, spike ready to execute in follow-up task) |
| 6 | ASSUM-009 (typed `interrupt()` round-trip) is documented-only — load-bearing for ADR-021 | Medium | **Scoped** (§5, spike ready to execute in follow-up task) |
| 7 | TASK-DOC-B2A4 superseded by this task (§1 folded it in verbatim) | Info | Pending archival |

---

## Recommendations

1. **Accept §1–§4 as complete** and close this review. All four acceptance criteria (AC-1 through AC-4) are met.
2. **Spawn a single follow-up spike task** — suggested ID pattern `TASK-SPIKE-<hash>`, title: *DeepAgents 0.5.3 primitives verification (ASSUM-008 permissions + ASSUM-009 interrupt round-trip)*. Use §5 of this report as its scoping source. Do not bundle the spike into this task's acceptance — it is load-bearing and deserves its own commit trail.
3. **Archive TASK-DOC-B2A4** as superseded by TASK-REV-A7D3. Move `tasks/backlog/TASK-DOC-B2A4/` to `tasks/completed/` with `status: superseded` in frontmatter and a one-line note in Implementation Notes pointing to this task.
4. **Commit discipline for §1–§4**: the task brief called for §1, §2, §3, §4 as separately revertable commits. Because the edits are small and tightly coupled to this review, a single commit that clearly enumerates each section in its message body is an acceptable alternative to four micro-commits — but *not* one that bundles the §5 spike.
5. **Block `/system-design` on the §5 spike** until the findings file is committed. Add a one-line note to the top of the follow-up spike task: *"`/system-design` is blocked on this task's completion."*

---

## Decision Options

**[A] Accept** — Mark §1–§4 as complete, close this review, archive TASK-DOC-B2A4. §5 spike must still run before `/system-design` — this option leaves spike scheduling to the user. Acceptable.

**[I] Implement** — Accept §1–§4 as complete, archive TASK-DOC-B2A4, and **create the follow-up `TASK-SPIKE-*` task in backlog** using §5 as its scoping source. Also blocks `/system-design` on the new task's completion. **Recommended** — this is the cleanest close-out and preserves the "no new ADRs from this task" boundary.

**[R] Revise** — Re-run the review with comprehensive depth (e.g. execute the §5 spike inside this task rather than spawning a separate one). Not recommended — the task's Known Risks explicitly calls out spike scope creep; spawning a dedicated task preserves commit isolation and the revertability property the task brief requires.

**[C] Cancel** — Discard the review, revert §1–§4 edits. Not recommended — the four paperwork items are zero-judgment polish with a clean pass, and the §5 scoping is useful independent of whether the spike runs immediately.

**Reviewer recommendation: [I] Implement.**

---

## Context Used (knowledge-graph provenance)

- Graphiti was available for re-ingestion writes (§2) but was not queried for prior context in this review — the task scope is self-contained and all referenced material is in-tree.
- Re-ingestion writes successfully landed under `architecture_decisions` group (both ADR-012 and ADR-022 re-ingested without Status-section warnings; episode IDs `adr_adr-arch-012-no-mcp-interface-for-forge` and `adr_adr-arch-022-dual-agent-memory-langgraph-memory-store-graphiti`).

Source material consulted:
- [ARCHITECTURE.md](../../docs/architecture/ARCHITECTURE.md) — §3 and §13
- [ADR-ARCH-012](../../docs/architecture/decisions/ADR-ARCH-012-no-mcp-interface.md) — rejection reasoning
- [ADR-ARCH-020](../../docs/architecture/decisions/ADR-ARCH-020-adopt-deepagents-builtins.md) — DeepAgents built-ins baseline
- [ADR-ARCH-021](../../docs/architecture/decisions/ADR-ARCH-021-paused-via-langgraph-interrupt.md) — ASSUM-009 backing ADR
- [ADR-ARCH-022](../../docs/architecture/decisions/ADR-ARCH-022-dual-agent-memory.md) — reformatted
- [ADR-ARCH-023](../../docs/architecture/decisions/ADR-ARCH-023-permissions-constitutional-safety.md) — ASSUM-008 backing ADR
- [ADR-ARCH-031](../../docs/architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md) — async supervisor tool additions
- [TASK-DOC-B2A4](../../tasks/backlog/TASK-DOC-B2A4/TASK-DOC-B2A4-architecture-decision-index-add-adr-arch-031.md) — superseded; §1 verbatim criteria
- [TASK-REV-F1B8 review report](TASK-REV-F1B8-review-report.md) — parent review that produced ADR-031
- [docs/history/command-history.md:91](../../docs/history/command-history.md#L91) — Status-heading parser expectation reference
