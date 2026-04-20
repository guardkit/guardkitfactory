---
id: TASK-SPIKE-D2F7
title: ASSUM-009 server-mode coverage — `interrupt()` round-trip under `langgraph dev`
status: backlog
created: 2026-04-20T00:00:00Z
updated: 2026-04-20T00:00:00Z
priority: high
tags: [spike, verification, langgraph, adr-021, pre-system-design]
complexity: 4
task_type: research
decision_required: false
parent_review: TASK-SPIKE-C1E9
scoping_source: docs/research/ideas/deepagents-053-verification.md §ASSUM-009 mode-coverage gap
blocks:
  - /system-design
estimated_effort: 1 hour
test_results:
  status: not_applicable
  coverage: null
  last_run: null
---

# Task: ASSUM-009 server-mode coverage — `interrupt()` round-trip under `langgraph dev`

## Description

Close the mode-coverage gap left by TASK-SPIKE-C1E9. That spike verified
ASSUM-009 (typed Pydantic `interrupt()` round-trip) under direct
`CompiledStateGraph.invoke` with a `SqliteSaver` checkpointer, but **did
not** exercise the `langgraph dev` server path — which is Forge's
canonical deployment mode per ADR-ARCH-021. The server path routes
resume through an additional HTTP-serialization layer and therefore has
a distinct failure mode from direct `.invoke` (dicts may come back
instead of Pydantic instances).

Until server-mode coverage exists, ADR-ARCH-021 cannot be treated as
fully verified. `/system-design` remains blocked on this task.

## Origin

Spawned from TASK-SPIKE-C1E9 close-out on 2026-04-20. C1E9 direct-mode
verdict was PASS; server-mode was deferred with the user's agreement on
option [A] of the close-out triage (preserve commit isolation, keep the
server-mode scaffolding as its own commit trail).

## Scope

### In scope

1. Install `langgraph-cli[inmem]` (or equivalent) in the dev environment.
2. Add a minimal `langgraph.json` that exposes the C1E9 interrupt graph
   (reuse `spikes/deepagents-053/interrupt_graph.py` — do not duplicate
   the Pydantic model definitions).
3. Boot `langgraph dev` as a background process.
4. Drive the graph via the LangGraph SDK (`langgraph_sdk` or the REST
   API): kick off a thread, observe the interrupt, resume with a typed
   `ApprovalDecision` instance.
5. Verify, inside the node that receives the resumed value, that
   `isinstance(value, ApprovalDecision) is True` and nested typed fields
   (`Requestor`, `datetime`, `UUID`) are preserved.
6. Append the server-mode verdict to
   `docs/research/ideas/deepagents-053-verification.md` under the existing
   ASSUM-009 section (append-only; do not rewrite the direct-mode rows).
7. On **PASS**: flip ADR-ARCH-021 References line to indicate full
   verification. Unblock `/system-design`.
8. On **FAIL**: spawn `TASK-ADR-REVISE-021-*` per the C1E9 revision
   policy; keep `/system-design` blocked on the revision.

### Out of scope

- Re-verifying direct `.invoke` mode (already PASS in C1E9).
- Re-verifying ASSUM-008 (permissions — closed in C1E9).
- Productionising `langgraph.json` for the real Forge graph (that's
  `/system-design`'s job).
- Resolving the msgpack "unregistered type" warning flagged in C1E9
  findings — tracked separately (to be folded into `/system-design`'s
  HITL payload registration).

## Acceptance Criteria

- [ ] `langgraph.json` added at repo root (or `spikes/deepagents-053/`
      if isolation is preferred) exposing the C1E9 interrupt graph.
- [ ] `langgraph dev` server boots cleanly against that config.
- [ ] A driver script (`spikes/deepagents-053/interrupt_server_drive.py`
      or similar) exercises the full pause + resume cycle via the
      LangGraph SDK.
- [ ] Node-side verdict rows (mirroring C1E9 direct-mode table) are
      recorded in `deepagents-053-verification.md`.
- [ ] Any divergence from direct-mode behaviour is called out explicitly
      — that divergence is itself a finding even if the assumption still
      passes.
- [ ] If fail: `TASK-ADR-REVISE-021-*` exists in backlog and
      `/system-design` is explicitly blocked on it.
- [ ] Commit message references `TASK-SPIKE-D2F7` and `TASK-SPIKE-C1E9`.

## Known Risks / Watch-outs

- **Scope creep into server productionisation.** This is a verification
  spike, not a deployment. Minimal `langgraph.json` only.
- **Resume API drift.** LangGraph 1.x SDK's resume API may differ from
  the in-process `Command(resume=...)` call. Record the exact SDK call
  used so the finding is reproducible.
- **In-memory checkpointer default.** `langgraph dev` defaults to
  in-memory — fine for same-process pause+resume in one boot. If the
  test requires cross-boot resume, explicitly pin SQLite.

## Source Material

- `docs/research/ideas/deepagents-053-verification.md` — parent
  findings, especially the ASSUM-009 mode-coverage gap note.
- `spikes/deepagents-053/interrupt_graph.py`,
  `spikes/deepagents-053/interrupt_resume.py` — reuse the Pydantic
  payloads and graph structure.
- `docs/architecture/decisions/ADR-ARCH-021-paused-via-langgraph-interrupt.md`
  — the ADR whose assumption this spike closes out.

## Test Requirements

- Executable driver script. Pass/fail is binary, observable from the
  verdict rows written into the findings file.

## Implementation Notes

_(Populated at execution time.)_
