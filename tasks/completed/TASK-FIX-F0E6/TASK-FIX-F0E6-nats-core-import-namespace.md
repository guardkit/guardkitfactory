---
id: TASK-FIX-F0E6
title: Fix `nats-core` import — installed wheel publishes under `nats/`, forge code imports `nats_core/`
status: completed
created: 2026-04-29T11:35:00Z
updated: 2026-04-29T12:45:00Z
completed: 2026-04-29T12:45:00Z
completed_location: tasks/completed/TASK-FIX-F0E6/
previous_state: in_review
state_transition_reason: "Completed via /task-complete after all acceptance criteria verified"
organized_files:
  - TASK-FIX-F0E6-nats-core-import-namespace.md
priority: high
tags: [fix, nats-core, packaging, demo-blocker, pytest-collection, ddd-southwest-demo, F0E4-followup]
complexity: 4
task_type: fix
decision_required: true
parent_review: TASK-REV-F0E4
scoping_source: .claude/reviews/TASK-REV-F0E4-report.md §5.1
estimated_effort: 1-3 hours (depends on chosen fix path)
test_results:
  status: pass
  coverage: null
  last_run: 2026-04-29T12:25:00Z
  notes: |
    Pytest collection: `0` `ModuleNotFoundError: No module named 'nats_core'`
    errors (down from 55). 3603 tests collected. 10 residual collection
    errors are out-of-scope (click missing etc. — covered by TASK-FIX-F0E7).
decision:
  status: approved
  approved_at: 2026-04-29T12:15:00Z
  approved_by: human
  chosen_option: b
  chosen_option_summary: "Sibling-source via [tool.uv.sources], mirroring jarvis"
  rationale: |
    Option (a) is not viable — PyPI's latest is 0.2.0 and the wheel is
    malformed (only ships nats/client/*, no nats_core/* namespace).
    Option (c) is mechanically impossible — wheel doesn't ship the target
    modules under either name. Option (d) is the right long-term fix but
    out-of-scope for demo unblock; filed as TASK-FIX-F0E6b.
follow_up:
  - id: TASK-FIX-F0E6b
    title: "Republish a corrected nats-core wheel so PyPI installs work standalone"
    location: tasks/backlog/TASK-FIX-F0E6b-republish-nats-core-wheel.md
---

# Task: Fix `nats-core` import — installed wheel publishes under `nats/`, forge code imports `nats_core/`

## Description

Surfaced as a side-effect of TASK-REV-F0E4's empirical Python 3.14 install:
on a fresh `uv venv --python 3.14 && uv pip install -e ".[providers]"`,
**55 of 108 test files fail to collect** with:

```
ImportError while importing test module '...'
E   ModuleNotFoundError: No module named 'nats_core'
```

Root cause: the `nats-core==0.2.0` PyPI wheel installs content under
`nats/` (e.g. `nats/client/__init__.py`, `nats/client/connection.py`),
but forge code imports `nats_core` as a top-level package:

```python
# src/forge/pipeline/__init__.py:58
from nats_core.events import (...)

# src/forge/gating/wrappers.py:113-114
from nats_core.envelope import EventType, MessageEnvelope
from nats_core.events import ApprovalRequestPayload, ApprovalResponsePayload

# tests/forge/dispatch/test_orchestrator.py:50
from nats_core.manifest import AgentManifest, ToolCapability
```

The `nats_core/` namespace simply **does not exist** in the installed
wheel. The dist-info exists (`nats_core-0.2.0.dist-info/`) but its
RECORD file lists only `nats/...` paths.

This is **demo-blocking**: forge cannot import its own pipeline modules
on a fresh install on a clean machine. The DDD South West autobuild demo
will fail at the bootstrap step if forge is part of the run and a
presenter does a fresh checkout.

The bug is **pre-existing** (not introduced by TASK-REV-F0E4) and
**orthogonal to LangChain pinning** (would happen on any Python
version). It is filed separately so TASK-LCP-001 (the LangChain
pin alignment, in the FEAT-F0EP feature folder) stays scope-clean.

## Acceptance Criteria

- [x] **Root cause confirmed**: verify the `nats_core/` namespace genuinely
      doesn't ship in the installed `nats-core 0.2.0` wheel (the F0E4 review
      already confirmed this against `.venv/lib/python3.14/site-packages/`,
      but re-verify on a fresh install before choosing a fix).
      → Confirmed 2026-04-29: `nats_core-0.2.0.dist-info/RECORD` lists
      9 files, all under `nats/client/...`. Zero `nats_core/...` paths.
      PyPI's latest is 0.2.0 (released 2026-04-14). Wheel is malformed.
- [x] **Decision recorded** (in this task or a small adjunct ADR) on which fix
      path to take — see Options below. The chosen path may have its own
      sub-tasks.
      → See `decision` block in frontmatter and the **Decision** section
      below. Chosen: option (b). Follow-up: TASK-FIX-F0E6b for option (d).
- [x] After the fix: `uv venv --python 3.14 .venv && uv pip install --python .venv/bin/python -e ".[providers]"` followed by `.venv/bin/python -c "from nats_core.events import ApprovalRequestPayload"` succeeds without
      `ModuleNotFoundError`.
      → Verified 2026-04-29: import returns
      `<class 'nats_core.events._agent.ApprovalRequestPayload'>`
      with `nats_core.__file__ = …/appmilla_github/nats-core/src/nats_core/__init__.py`.
- [x] Pytest collection on a fresh install: `.venv/bin/python -m pytest --co -q` returns **zero** `ModuleNotFoundError: No module named 'nats_core'` collection errors. (Other pre-existing errors out of scope.)
      → Verified 2026-04-29: `pytest --co -q` reports **0** matches for
      `No module named 'nats_core'`. 3603 tests collected. 10 residual
      collection errors are unrelated (`No module named 'click'` etc.,
      covered by TASK-FIX-F0E7 dev-deps install).
- [x] Commit references `TASK-FIX-F0E6` and `TASK-REV-F0E4` in the message body.
      → Committed at task-complete time — see git log for the
      `fix: switch nats-core to sibling-source via [tool.uv.sources]`
      commit body.

## Decision

**Chosen path: Option (b)** — sibling-source via `[tool.uv.sources]`.

Added to `pyproject.toml`:

```toml
[tool.uv.sources]
nats-core = { path = "../nats-core", editable = true }
```

(With a comment block explaining the malformed-wheel rationale, sibling-layout
expectation, and the worktree symlink note. Mirrors jarvis's pattern.)

**Rejected**:
- Option (a): no newer wheel exists on PyPI (latest is 0.2.0, 2026-04-14).
- Option (c): mechanically impossible — `nats.events`, `nats.envelope`,
  `nats.manifest`, `nats.topics` don't exist in the installed wheel under
  either namespace. The wheel only contains `nats.client.*` (9 files).
  Plus this would have churned ~60 files for no real fix.
- Option (d): right long-term answer, but cross-repo (requires republishing
  the upstream wheel). Filed separately as TASK-FIX-F0E6b in `backlog/`.

**Demo-machine constraint**: this fix requires the `nats-core` sibling repo
to exist at `../nats-core` (i.e. `~/Projects/appmilla_github/nats-core/`)
when forge is installed. Demo bundle should ensure both repos are checked
out side-by-side, same as jarvis already requires. For autobuild worktrees,
a symlink at `.guardkit/worktrees/nats-core → ../../../nats-core` is needed
(jarvis already does this; forge will need it once autobuild runs hit
`uv pip install` with this dependency layout).

## Options (decision required)

These are listed in roughly increasing order of blast radius. Pick one based on which is actually viable.

1. **(a) Bump to a newer `nats-core` PyPI version that fixes the layout**.
   First action: check if a `nats-core>=0.3` (or similar) exists on PyPI that ships
   under `nats_core/` correctly. If yes, this is a one-line `pyproject.toml`
   update. Verify the fixed version is API-compatible with current forge usage
   (events, envelope, manifest). **Lowest blast radius if available.**

2. **(b) Use the sibling-source pattern via `[tool.uv.sources]`**.
   Jarvis uses this pattern to install `nats-core` from the local sibling repo
   `appmilla_github/nats-core/` rather than PyPI:
   ```toml
   [tool.uv.sources]
   nats-core = { path = "../nats-core", editable = true }
   ```
   This works for local development but **requires the sibling repo to exist
   on the demo machine**. Less attractive for clean-machine demo setup
   unless the sibling repo is also part of the demo bundle. Document the
   constraint clearly if chosen.

3. **(c) Code-side rename `from nats_core.X import Y` → `from nats.X import Y`**.
   First verify that `nats/events.py`, `nats/envelope.py`, `nats/manifest.py`
   actually exist in the installed wheel — the dist-info RECORD only listed
   `nats/client/...`, which suggests the package surface forge expects may
   not exist at all under either name. If only `nats/client/...` ships,
   this option is a non-starter and likely indicates the wheel itself is
   wrong (back to option a).

4. **(d) Adopt sibling-source AND publish a corrected wheel upstream**.
   Cleanest long-term but highest effort. Belongs after a/b/c if any of
   them is acceptable as a demo unblocker.

**Recommendation**: investigate (a) first (15 min PyPI search). If a fixed
upstream version exists, take it. Otherwise (b) for the demo timeline,
with (d) as the cleanup follow-up.

## Out of scope

- The LangChain 1.x pin alignment (that's TASK-LCP-001 inside the FEAT-F0EP feature folder at `tasks/backlog/langchain-1x-pin-alignment/`).
- Adding `pytest-asyncio` and fixing dev-deps install (that's TASK-FIX-F0E7).
- Fixing `forge.build` stale ref (that's TASK-FIX-F0E8).
- Any structural reshape of the `nats-core` API surface — only restoring the
  ability to import what forge code expects.
- Cross-repo coordination with the `nats-core` repo beyond filing an upstream
  bug if the wheel is genuinely broken (option d's "publish a corrected wheel"
  may itself spawn a sibling-repo task).

## Source Material

- **Empirical observation**: [`.claude/reviews/TASK-REV-F0E4-report.md`](../../.claude/reviews/TASK-REV-F0E4-report.md) §5.1 (full diagnosis with site-packages inspection)
- **Pytest log**: [`docs/history/portfolio-py314-rebaseline-pytest.log`](../../docs/history/portfolio-py314-rebaseline-pytest.log) (the 55 collection errors)
- **Forge files affected** (non-exhaustive — `grep -rn 'nats_core' src/forge/ tests/`):
  - `src/forge/pipeline/__init__.py` (line 58)
  - `src/forge/gating/wrappers.py` (lines 113-114)
  - `tests/forge/dispatch/test_orchestrator.py` (line 50)
  - …and ~50 other test files
- **Sibling-source pattern reference (read-only)**: jarvis's `pyproject.toml` `[tool.uv.sources]` section
- **Current forge pin** (the one being investigated): [`pyproject.toml`](../../pyproject.toml) `nats-core>=0.2.0,<0.3`
