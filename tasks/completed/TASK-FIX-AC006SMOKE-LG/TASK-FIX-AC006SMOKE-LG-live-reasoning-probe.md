---
id: TASK-FIX-AC006SMOKE-LG
title: AC-006 live smoke — probe gemma4:26b /v1/responses reasoning shape before the next FEAT-AOF run
status: completed
task_type: bug-fix
created: 2026-06-07T13:00:00Z
updated: 2026-06-07T14:30:00Z
completed: 2026-06-07T14:30:00Z
completed_location: tasks/completed/TASK-FIX-AC006SMOKE-LG/
previous_state: backlog
state_transition_reason: "task-work execution — live probe on GB10 DGX (llama-swap reachable on localhost:9000, gemma4-coach live on port 5801) → PASS after extractor extension"
outcome: pass
evidence: docs/state/TASK-FIX-AC006SMOKE-LG/probe_report.json
priority: high
complexity: 3
effort_hours: 1
deadline: 2026-06-15
parent_review: TASK-REV-AOF-RUN9
parent_task: TASK-FIX-COACHBUDG01-LG
feature_id: FEAT-HMIG
parent_feature: autobuild-harness-migration
wave: 3
implementation_mode: direct
intensity: standard
blocker: true
related_tasks:
  - TASK-FIX-COACHBUDG01-LG   # the fix this verifies live (AC-006 was left pending-hardware)
  - TASK-FIX-COACHBUDG01      # guardkit — gates its AC-009
surfaced_in: guardkitfactory/docs/reviews/autobuild-migration/TASK-REV-AOF-RUN9-pre-next-run-readiness-review.md
tags:
  - autobuild
  - langgraph-migration
  - coach
  - responses-api
  - hybrid-reasoning-models
  - pre-run-gate
falsifier: "A single live Coach invocation against gemma4-coach (`--reasoning auto`) over the run-9 TASK-FIX-IA03 turn-1 prompt drives `extract_last_ai_reasoning` to return non-empty plaintext, `LangGraphHarness.invoke` surfaces it on `AssistantMessageEvent.reasoning_text` (>0 chars), the orchestrator `coach_output_parser` recovers the fenced JSON verdict, and COACHSF01 does NOT fire. If reasoning_text is empty, the installed `langchain-openai` Responses-API shape is unhandled — extend `extract_last_ai_reasoning` against the captured shape and re-probe."
---

# Task: AC-006 live reasoning probe (the pre-run gate)

## Why this task exists

`TASK-FIX-COACHBUDG01-LG` is marked `completed` (AC-001..AC-005: code + hermetic
tests, 111 passed), **but AC-006 is unticked** (`ac006_status: pending-hardware`).
The reasoning extraction was implemented against the **installed `langchain-core
1.4.0` message shapes** because `langchain-openai` is a `.[providers]` extra
**absent from the dev venv** — so the actual `ChatOpenAI` client that produces the
live `/v1/responses` reasoning shape on the DGX/llama-swap substrate **was never
observed**. The task's own implementation notes warn: *"version-dependence is
real… probe the actual installed version first."* That probe did not happen.

The run-9 review (`TASK-REV-AOF-RUN9`) makes this the **single highest-leverage
pre-run item**: if the live shape matches none of the three handled branches in
`extract_last_ai_reasoning`, `reasoning_text` is `""` again → Coach non-verdict →
COACHSF01 fires → **run-9 reproduces exactly**, wasting another ~50-minute run.

**This is a gate: do it before launching the next full FEAT-AOF validation.**

## What to do

1. On the DGX/llama-swap substrate, capture **one** live `/v1/responses` AIMessage
   from `gemma4:26b` under `--reasoning auto` (a single Coach-style invocation is
   enough). Inspect `.content`, `.additional_kwargs`, and `.content_blocks`.
2. Drive that captured shape through `LangGraphHarness.invoke` (or directly through
   `extract_last_ai_reasoning`) and confirm `reasoning_text` > 0 chars.
3. Replay the run-9 `TASK-FIX-IA03` turn-1 Coach prompt end-to-end: confirm the
   orchestrator `coach_output_parser` recovers the fenced JSON verdict and
   COACHSF01 does **not** fire; the run logs a non-zero `reasoning_content` count.
4. **Record the result in the run-9 follow-up review doc**
   (`docs/reviews/autobuild-migration/TASK-REV-AOF-RUN9-pre-next-run-readiness-review.md`)
   and tick AC-006 on `TASK-FIX-COACHBUDG01-LG`.

## If the probe fails

The installed client's reasoning shape is unhandled. Capture it, extend
`extract_last_ai_reasoning` (`src/guardkitfactory/harness/extractors.py`) against
the observed shape, pin it in the AC-005 fixture so a future client bump fails
loudly, and re-probe. Do **not** launch the full run until this passes.

## Acceptance criteria

- [x] **AC-1:** Live `gemma4-coach` (= gemma4:26b) `/v1/responses` AIMessage
  captured. Reasoning location recorded: `block["content"] = [{"type":
  "reasoning_text", "text": ...}]` (raw provider shape) and equivalently
  `block["extras"]["content"]` under the langchain-core normalised
  `msg.content_blocks` view. NOT on `additional_kwargs["reasoning"]` nor in
  `summary` for this client/model/transport. Probe artefacts:
  `docs/state/TASK-FIX-AC006SMOKE-LG/captured_aimessage.json` (post-fix capture)
  and `captured_aimessage_probe_c.json` (full block dump that found the shape).
- [x] **AC-2:** `reasoning_text` = **1055 chars** > 0 — verified post-fix.
  First-probe was 0 (the unhandled shape); extending
  `_plaintext_from_reasoning_block` in `src/guardkitfactory/harness/extractors.py`
  closed the gap.
- [x] **AC-3:** End-to-end replay through `guardkit.orchestrator.coach_output_parser.extract_and_write`:
  parser recovered `{"task_id": "TASK-FIX-IA03", "turn": 1, "decision": "approve"}`,
  no `CoachDecisionNotFoundError`, no `CoachDecisionInvalidError`, COACHSF01
  silent. The verdict was recovered from the **content** channel directly
  (parser's "prefer content" precedence wins), but `reasoning_text > 0`
  proves the COACHBUDG01-LG fallback is now operational on this transport.
- [x] **AC-4:** Result recorded in
  `docs/reviews/autobuild-migration/TASK-REV-AOF-RUN9-pre-next-run-readiness-review.md`
  §6 (Verdict: R4 closes ✅). AC-006 ticked on
  `tasks/completed/TASK-FIX-COACHBUDG01-LG/...` (`ac006_status:
  pending-hardware` → `verified-live`). Parent COACHBUDG01 AC-009 gated open.

## Outcome

**PASS** after one extractor extension. The probe found exactly the failure
mode the task's "if probe fails" branch anticipated: the installed
`langchain-openai 1.2.2` `/v1/responses` reasoning shape was unhandled.
Extended `_plaintext_from_reasoning_block` to consult `block["content"]` and
`block["extras"]["content"]` lists of `{"type": "reasoning_text", "text": ...}`
items; added two hermetic pins so a future client bump fails loudly. Full
factory suite: 116 passed, 8 skipped, 2 deselected. Ruff clean.

## Out of scope

- The full FEAT-AOF run (that is the post-gate validation, `TASK-HMIG-010`).
- Any chat-completions-path change (Approach A is settled).

## References

- Review (verdict + checklist): `docs/reviews/autobuild-migration/TASK-REV-AOF-RUN9-pre-next-run-readiness-review.md`
- Fix under verification: `tasks/completed/TASK-FIX-COACHBUDG01-LG/TASK-FIX-COACHBUDG01-LG-responses-api-reasoning-extraction.md`
- Extractor: `src/guardkitfactory/harness/extractors.py`
- Harness wiring: `src/guardkitfactory/harness/langgraph_harness.py:365-391`
