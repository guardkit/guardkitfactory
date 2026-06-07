---
id: TASK-FIX-COACHBUDG01-LG
title: LangGraph harness extracts reasoning from OpenAI Responses API (/v1/responses) output into AssistantMessageEvent.reasoning_text
task_type: bug-fix
status: completed   # AC-001..AC-006 done. AC-006 live smoke verified 2026-06-07 on GB10 DGX via TASK-FIX-AC006SMOKE-LG; gemma4-coach Responses-API plaintext-content shape uncovered + extractor extended.
created: 2026-06-07T10:00:00Z
updated: 2026-06-07T14:30:00Z
completed: 2026-06-07T14:30:00Z
completed_location: tasks/completed/TASK-FIX-COACHBUDG01-LG/
ac006_status: verified-live   # 2026-06-07 GB10 DGX, llama-swap gemma4-coach via /v1/responses; probe report at docs/state/TASK-FIX-AC006SMOKE-LG/probe_report.json
ac006_evidence: docs/state/TASK-FIX-AC006SMOKE-LG/probe_report.json   # PASS: AC-1 capture + AC-2 reasoning_text=1055 chars + AC-3 parser recovers verdict, COACHSF01 silent
priority: high
complexity: 4
effort_hours: 3
deadline: 2026-06-15
parent_task: TASK-FIX-COACHBUDG01   # cross-repo, in guardkit — this closes its "AC-005 LangGraph side: BLOCKED ON guardkitfactory"
feature_id: FEAT-HMIG
parent_feature: autobuild-harness-migration
wave: 3
implementation_mode: task-work
intensity: standard
related_tasks:
  - TASK-HMIG-001B            # origin of extractors.py (extract_last_ai_message / extract_last_ai_reasoning)
  - TASK-HMIG-002R-MODEL-PROFILE   # model resolution path that constructs the Responses-API ChatOpenAI
  - TASK-HMIG-006            # event-stream taxonomy that emits AssistantMessageEvent
surfaced_in: docs/reviews/autobuild-migration/autobuild-FEAT-AOF-run-9.md   # in the guardkit repo
tags:
  - autobuild
  - langgraph-migration
  - coach
  - substrate-robustness
  - hybrid-reasoning-models
  - responses-api
falsifier: "After landing, a recorded gemma4:26b `/v1/responses` AIMessage (captured under `--reasoning auto`) drives `extract_last_ai_reasoning` to return the model's non-empty chain-of-thought, and `LangGraphHarness.invoke` surfaces it on `AssistantMessageEvent.reasoning_text` (> 0 chars). Replaying the run-9 TASK-FIX-IA03 turn-1 Coach prompt against gemma4-coach with `--reasoning auto` no longer logs `0 chars reasoning_content`; the orchestrator-side coach_output_parser recovers the fenced JSON verdict from `reasoning_text` and COACHSF01 does NOT fire."
---

# Task: Extract reasoning from the OpenAI Responses API in the LangGraph harness

## Why this task exists

This closes the last open box of cross-repo parent
[`TASK-FIX-COACHBUDG01`](../../../../guardkit/tasks/backlog/autobuild-harness-migration/TASK-FIX-COACHBUDG01-coach-token-budget-and-reasoning-mode.md):

> **AC-005 LangGraph side: BLOCKED ON guardkitfactory.** Populate
> `AssistantMessageEvent.reasoning_text` from the model's reasoning inside the
> LangGraph harness. See guardkitfactory follow-on.

The substrate is **not** at fault. Verified in the run-9 review
(`guardkit/docs/reviews/autobuild-migration/autobuild-FEAT-AOF-run-9.md`):

- `gemma4-coach` is live on `--reasoning auto` (process arg confirmed).
- A direct `POST /v1/chat/completions` probe against `gemma4:26b` returned
  `content=2 chars, reasoning_content=145 chars` — the model **does** emit
  `reasoning_content` correctly under `--reasoning auto`.
- Context (131K) + q8 KV is comfortable (~89 GB resident); smoke passed.

The orchestrator-side parser fix from COACHBUDG01 §9.14 is already shipping —
the run-9 error message is in its new format
(`(N chars content + M chars reasoning_content)`). The
guardkitfactory-side per-role `max_tokens` budget and the
`AssistantMessageEvent.reasoning_text` plumbing **also already landed** (commit
`e8350bd`, [`extractors.py`](../../src/guardkitfactory/harness/extractors.py),
[`langgraph_harness.py:365-391`](../../src/guardkitfactory/harness/langgraph_harness.py#L365-L391)).

One gap remains, and it is the cause of run-9.

## Run-9 evidence (the exact failure)

```
Coach decision not found: no fenced ```json block in Coach response
for TASK-FIX-IA03 turn 1 (25211 chars content + 0 chars reasoning_content)
```

The run-9 httpx trace shows the harness hitting the **Responses API**, not
chat-completions:

```
INFO:httpx:HTTP Request: POST http://promaxgb10-41b1:9000/v1/responses "HTTP/1.1 200 OK"
```

`0 chars reasoning_content` is the smoking gun: the harness extracted no
reasoning even though the model emits it correctly on the chat-completions
path. Under `--reasoning auto` the model routed its chain-of-thought into the
reasoning channel, the harness failed to recover it, the model's
reasoning-as-prose landed inline in `content` (25211 chars with no fenced JSON
block), and COACHSF01 fired — **correctly** masking a substrate gap that should
instead be closed here.

## Root cause

[`extract_last_ai_reasoning`](../../src/guardkitfactory/harness/extractors.py#L52-L108)
only understands the **chat-completions** reasoning shape:

```python
additional = getattr(msg, "additional_kwargs", None)
if isinstance(additional, dict):
    reasoning = additional.get("reasoning_content")   # chat-completions only
    ...
reasoning = msg.get("reasoning_content")               # top-level dict variant
```

But deepagents' default model resolution
([`model_config.resolve_autobuild_model`](../../src/guardkitfactory/harness/model_config.py#L245-L316)
→ `deepagents._models.resolve_model`) constructs a `ChatOpenAI` that routes
through the **OpenAI Responses API** (`POST /v1/responses`). The Responses API
structures reasoning differently from chat-completions, so
`additional_kwargs["reasoning_content"]` is absent → the extractor returns `""`
→ `AssistantMessageEvent.reasoning_text = ""` → the orchestrator parser has
nothing to fall through to.

The existing test `TestReasoningTextSurfacing`
([`test_langgraph_harness.py:428-480`](../../tests/harness/test_langgraph_harness.py#L428-L480))
only exercises the chat-completions shape, so the gap shipped green.

## Scope

Make `extract_last_ai_reasoning` (and its harness wiring) recover reasoning
from the **OpenAI Responses API** output shape, so the already-shipped
`reasoning_text` plumbing receives non-empty reasoning on the `/v1/responses`
path. Narrow and additive — do **not** regress the chat-completions path the
existing tests pin.

## Acceptance Criteria

### Layer A — Responses-API reasoning extraction (the fix)

- [x] **AC-001:** `extract_last_ai_reasoning` recovers reasoning from the
  OpenAI Responses API AIMessage shape, in addition to the existing
  chat-completions shape. The Responses API carries reasoning (version-
  dependent — handle whichever your installed `langchain-openai` produces;
  probe with the recorded fixture from AC-005):
  - **Content-block form:** `AIMessage.content` is a *list* of blocks; reasoning
    appears as a block with `type == "reasoning"` (text under `text` and/or a
    `summary` list of `{"type": "summary_text", "text": ...}`). Note: when
    `content` is a list the current `extract_last_ai_message` str-guard already
    skips it — confirm the canonical-text path still behaves (see AC-004).
  - **`additional_kwargs["reasoning"]` form:** a dict carrying `summary`
    (plaintext summary blocks) and/or `encrypted_content`.
  - **Typed `content_blocks` form:** newer langchain-core exposes
    `AIMessage.content_blocks` with typed reasoning entries (`type == "reasoning"`).
- [x] **AC-002:** Extract only **plaintext** reasoning (block `text` / `summary`
  text). `encrypted_content` is opaque and useless to the parser — treat its
  presence as a no-op, never return it as reasoning text. (Local llama.cpp /
  llama-swap does not encrypt, so plaintext should be present; the
  `encrypted_content` branch is shape-completeness for hosted OpenAI only.)
- [x] **AC-003:** Precedence + return contract unchanged — walk messages in
  reverse, return the first non-empty plaintext reasoning found, else `""`
  (never `None`; the `AssistantMessageEvent.reasoning_text` field is
  non-optional with a `""` default). Multiple reasoning fragments on one
  message are joined consistently with the existing helper's behaviour.

### Layer B — no regression

- [x] **AC-004:** The chat-completions path is untouched —
  `TestReasoningTextSurfacing::test_reasoning_content_lands_in_assistant_message_event`
  and `test_no_reasoning_yields_empty_reasoning_text`
  ([`test_langgraph_harness.py:428-480`](../../tests/harness/test_langgraph_harness.py#L428-L480))
  still pass without modification. `extract_last_ai_message` still returns the
  canonical text correctly when `content` is a list of blocks (it must not
  start returning reasoning-as-text).

### Validation

- [x] **AC-005:** Hermetic Responses-API fixture. Capture (or hand-author from a
  real capture) one `/v1/responses` AIMessage from `gemma4:26b` under
  `--reasoning auto` whose reasoning is non-empty and whose verdict JSON the
  Coach would emit. Add `TestResponsesApiReasoningExtraction` (sibling to
  `TestReasoningTextSurfacing`) driving the fixture through
  `LangGraphHarness.invoke` and asserting `events[0].reasoning_text` is the
  recovered chain-of-thought (> 0 chars). Cover each shape variant the
  installed `langchain-openai` can produce. No live network in the test.
- [x] **AC-006:** Live smoke (gates parent COACHBUDG01 AC-009). Replay the
  run-9 `TASK-FIX-IA03` turn-1 Coach prompt against `gemma4-coach` with
  `--reasoning auto`: the parser recovers the fenced JSON verdict from
  `reasoning_text`, COACHSF01 does **not** fire, and the run logs a non-zero
  `reasoning_content` char count. Record the result in the run-9 follow-up
  review doc.
  - **Verified 2026-06-07** on GB10 DGX via `TASK-FIX-AC006SMOKE-LG` (live
    probe). Result: **PASS** after extending `_plaintext_from_reasoning_block`
    to handle the live shape (`block["content"] = [{"type": "reasoning_text",
    "text": ...}]` raw and `block["extras"]["content"]` normalised — neither
    was handled by the original AC-001..AC-005 implementation because
    `langchain-openai` was absent from the dev venv when those ACs landed).
    Probe report: `docs/state/TASK-FIX-AC006SMOKE-LG/probe_report.json`
    (AC-1 capture + AC-2 `reasoning_text=1055` chars + AC-3 verdict
    recovered: `decision="approve"`, COACHSF01 silent). Two new hermetic
    fixtures pin the live shape in `test_langgraph_harness.py`
    (`test_reasoning_content_list_surfaces_on_reasoning_text` and
    `test_reasoning_extras_content_list_surfaces_on_reasoning_text`).

## Implementation status (2026-06-07, `/task-work`)

Approach **(A)** chosen (extract from the Responses-API shape — additive,
duck-typed, leaves deepagents' default model resolution untouched).

Landed in [`extractors.py`](../../../src/guardkitfactory/harness/extractors.py):
`extract_last_ai_reasoning` now recovers plaintext reasoning from all three
Responses-API shapes the installed client can produce, and
`extract_last_ai_message` now pulls canonical `text`/`output_text` from
list-of-blocks content (excluding `reasoning` — AC-004). Verified against the
**installed `langchain-core 1.4.0`** (`langchain-openai` is a `.[providers]`
extra, absent in the dev venv; reasoning blocks key on `reasoning`/`text`/
`summary`, and `content_blocks` does **not** synthesise the
`additional_kwargs["reasoning"]` form — so that shape is read directly).

Tests: `TestResponsesApiReasoningExtraction` (5, harness-driven via
`LangGraphHarness.invoke`) + `TestExtractorShapeUnits` (5, direct unit) in
[`test_langgraph_harness.py`](../../../tests/harness/test_langgraph_harness.py).
Full suite **111 passed, 8 skipped, 2 deselected**; `extractors.py` line
coverage **90%**; `ruff check`/`format` clean. Chat-completions regression
tests (`TestReasoningTextSurfacing`) pass unmodified (AC-004).

**AC-006 closed 2026-06-07** via `TASK-FIX-AC006SMOKE-LG` on the GB10 DGX.
The live probe also exposed an unhandled `langchain-openai` Responses-API
reasoning shape (`block["content"] = [{"type": "reasoning_text", ...}]` /
`block["extras"]["content"]`) — the extractor was extended and the new
shape pinned with two hermetic fixtures. Full suite: **116 passed, 8
skipped, 2 deselected**. Probe artefacts: `docs/state/TASK-FIX-AC006SMOKE-LG/`.

## Implementation notes

- **Version-dependence is real.** The findings flag that the Responses API
  reasoning location depends on the `langchain-openai` client version (content
  blocks vs `additional_kwargs["reasoning"]` vs typed `content_blocks`).
  **Probe the actual installed version first** by capturing one live
  `/v1/responses` AIMessage and inspecting `.content`, `.additional_kwargs`,
  and `.content_blocks` — then implement against what is observed, with the
  other shapes as defensive fallbacks. Pin the observed shape in the fixture so
  a future client bump that moves the field fails AC-005 loudly.
- **Keep the helper duck-typed.** Match the existing style in
  [`extractors.py`](../../src/guardkitfactory/harness/extractors.py): tolerate
  both LangChain message objects and plain dicts, skip non-AI messages, never
  raise on unexpected shapes.
- **`encrypted_content` is a trap** — it is encrypted reasoning a hosted OpenAI
  model returns for privacy; it is not parseable. Never surface it. Only the
  plaintext `summary` / block `text` helps the downstream parser.

## Design decision to resolve in architectural review (Phase 2.5)

Two viable approaches — pick one in `/task-work` design review:

- **(A) Extract from the Responses-API shape (recommended by the run-9
  findings; primary above).** Keeps the Responses API (deepagents' default) and
  preserves reasoning-on. Cost: must track the version-dependent reasoning
  shape. This is the "highest leverage" fix the findings call out.
- **(B) Pin the harness to chat-completions
  (`use_responses_api=False` on the `ChatOpenAI` construction site).** Then
  llama.cpp returns `message.reasoning_content` and the *existing* extractor
  already handles it — smaller diff, no new shape-tracking. Cost: overrides
  deepagents' default resolution (must verify
  [`resolve_autobuild_model`](../../src/guardkitfactory/harness/model_config.py#L245-L316)
  / `deepagents._models.resolve_model` can be steered without side effects),
  and steps away from the Responses API if that is the strategic direction.

Default to (A) unless design review finds (B) materially lower-risk. Whichever
is chosen, AC-004 (no chat-completions regression) and AC-005 (hermetic
fixture) still apply.

## Out of scope

- Per-model `reasoning_mode` registry shape and per-role `max_tokens` budget —
  **already shipped** in this repo
  ([`model_config.py`](../../src/guardkitfactory/harness/model_config.py),
  commit `e8350bd`). COACHBUDG01 AC-006/AC-007 are effectively complete here;
  do not re-do them.
- The orchestrator-side `coach_output_parser` content↔reasoning fall-through —
  lives in guardkit (COACHBUDG01 AC-004, COMPLETE).
- Switching substrates / model swaps (DeepSeek V4 Flash, Nemotron-3, etc.) —
  TASK-HMIG-012.
- Removing the `--reasoning off` belt-and-braces on other models — stays until
  COACHBUDG01 AC-009 proves the parser fix end-to-end.

## References

- Run-9 review (operational evidence + the cross-repo plan):
  `guardkit/docs/reviews/autobuild-migration/autobuild-FEAT-AOF-run-9.md`
- Parent task (the AC-005 LangGraph box this closes):
  `guardkit/tasks/backlog/autobuild-harness-migration/TASK-FIX-COACHBUDG01-coach-token-budget-and-reasoning-mode.md`
- Findings doc §9.13 "Reasoning-off lesson" / §9.14 "What landed / What's NOT
  yet wired": `guardkit/docs/research/dgx-spark/AUTOBUILD-ON-LLAMA-SWAP-findings.md`
- Extractor under change: [`src/guardkitfactory/harness/extractors.py`](../../src/guardkitfactory/harness/extractors.py)
- Harness wiring: [`src/guardkitfactory/harness/langgraph_harness.py:365-391`](../../src/guardkitfactory/harness/langgraph_harness.py#L365-L391)
- Existing reasoning tests (chat-completions shape): [`tests/harness/test_langgraph_harness.py:428-480`](../../tests/harness/test_langgraph_harness.py#L428-L480)
- ADR FB-004 (substrate-parity invariant the fix preserves): `guardkit/.claude/rules/feature-build-invariants.md`

## Cross-repo coordination

Landing this unblocks, in `TASK-FIX-COACHBUDG01` (guardkit):
**AC-005 LangGraph side**, **AC-008 LangGraph reasoning tests**, and gates
**AC-009** (autobuild Player↔Coach loop replay). Point that task's AC-005
LangGraph checkbox at this task's id once merged.
