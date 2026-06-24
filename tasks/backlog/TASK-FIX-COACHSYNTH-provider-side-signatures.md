---
id: TASK-FIX-COACHSYNTH
title: Land provider-side TASK-PERF-COACHSYNTH signatures (max_tool_result_chars, recursion_limit)
status: backlog
task_type: fix
created: 2026-06-11T00:00:00Z
updated: 2026-06-11T00:00:00Z
priority: critical
complexity: 2
effort_hours: 2
related: [TASK-PERF-COACHSYNTH]
---

# TASK-FIX-COACHSYNTH — land the provider side of the COACHSYNTH contract

## Why this task exists

guardkit run-24 (`guardkit/docs/reviews/autobuild-migration/autobuild-FEAT-AOF-run-24.md`)
died at dispatch with a TypeError. Root cause is **cross-repo contract drift**:
guardkit's `guardkit/orchestrator/harness/selector.py` landed the *consumer*
side of TASK-PERF-COACHSYNTH and now calls:

```python
backend=build_autobuild_backend(Path(cwd), max_tool_result_chars=max_tool_result_chars)
...
LangGraphHarness(model=..., backend=..., permissions=..., recursion_limit=recursion_limit)
```

This repo's main tree has **neither** parameter:

- `src/guardkitfactory/harness/backend_config.py` →
  `build_autobuild_backend(worktree: Path)` — **the run-24 TypeError**
- `src/guardkitfactory/harness/langgraph_harness.py` →
  `LangGraphHarness.__init__(self, model, *, backend=None, permissions=None)` —
  **the second TypeError, lying in wait**: fixing only the backend kwarg means
  run-25 dies on the same selector line with the next argument.

If the provider-side changes already exist on a branch/worktree, this task is
a land/sync, not new code — but the imported `src/guardkitfactory/harness/` is
what the traceback hit, so verify what the guardkit venv actually imports.

## What to do

1. `build_autobuild_backend(worktree: Path, *, max_tool_result_chars: int | None = None)`
   — accept and thread into the backend's tool-result truncation (the backend
   already has a `max_output_bytes` posture; `max_tool_result_chars` is the
   per-tool-result character cap re-entering model context). Default `None`
   preserves current behaviour for existing callers.
2. `LangGraphHarness.__init__(..., recursion_limit: int | None = None)` —
   store and pass as `config={"recursion_limit": ...}` on the agent
   `ainvoke`/`astream` call. Default `None` → LangGraph default (25).
3. Keep both parameters keyword-only with safe defaults so the contract is
   backward-compatible in both directions during the cross-repo landing window.

## Acceptance criteria

- [ ] **AC-1**: `build_autobuild_backend` accepts `max_tool_result_chars` and
  observably truncates oversized tool results to the cap (unit test with an
  oversized synthetic tool result).
- [ ] **AC-2**: `LangGraphHarness` accepts `recursion_limit` and the value
  reaches the LangGraph invoke config (unit test asserting the config dict).
- [ ] **AC-3**: Both parameters default to `None` with unchanged legacy
  behaviour; existing call sites pass without modification.
- [ ] **AC-4**: Verification run launches past the selector — guardkit
  `autobuild` reaches Player turn 1 without a dispatch TypeError (run-25).

## Notes

- This task **gates the entire unattended-build-service sequence** (see
  `ai-transition/docs/fine-tuned-judgment-agents-findings.md` §6) and the
  QA Verifier dataset contract freeze. Land first.
- Run logs to verify against: run-24 traceback at `harness/selector.py`
  line ~301.
