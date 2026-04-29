---
id: TASK-FIX-F0E7
title: Add `pytest-asyncio` to dev deps and align dev-install path (PEP 735 vs `[project.optional-dependencies]`)
status: completed
completed: 2026-04-29T12:45:00Z
completed_location: tasks/completed/TASK-FIX-F0E7/
organized_files: ["TASK-FIX-F0E7-pytest-asyncio-and-dev-deps-install.md"]
created: 2026-04-29T11:35:00Z
updated: 2026-04-29T12:45:00Z
priority: medium
tags: [fix, test-infra, pytest-asyncio, dev-deps, pep-735, F0E4-followup]
complexity: 2
task_type: fix
decision_required: false
decision_resolved: "Option (a) — mirror dev deps into [project.optional-dependencies] alongside [dependency-groups]"
parent_review: TASK-REV-F0E4
scoping_source: .claude/reviews/TASK-REV-F0E4-report.md §5.2
estimated_effort: 30 minutes (depends on chosen install-path option)
test_results:
  status: passed
  coverage: n/a (config-only change; verified by F0E4 acceptance subset)
  last_run: 2026-04-29T12:40:00Z
  baseline: "162 failed, 1522 passed (TASK-REV-F0E4 §1.5)"
  after_fix: "1684 passed, 0 failed (8 unrelated warnings)"
  delta: "-162 async-def-failures (matches predicted root-cause count exactly)"
  install_recipe: 'uv pip install -e ".[dev,providers]"  # option (a)'
  pytest_asyncio_version: "1.3.0 (cap >=1,<2)"
---

# Task: Add `pytest-asyncio` to dev deps and align dev-install path

## Description

Surfaced as a side-effect of TASK-REV-F0E4's empirical Python 3.14 install:
the runnable subset of forge's pytest suite produced **162
`Failed: async def functions are not natively supported`** failures —
all from a single root cause: `pytest-asyncio` is not installed, despite
forge having 100+ tests marked `@pytest.mark.asyncio`.

There are **two separate bugs** bundled together here, both around `[dependency-groups].dev`:

### Bug 1: `pytest-asyncio` is missing

`pyproject.toml` declares:

```toml
[dependency-groups]
dev = [
    "pytest>=9.0.2",
    "pytest-bdd>=8.1,<9",
]
```

There are 100+ `@pytest.mark.asyncio` decorators across the test suite (see
the `PytestUnknownMarkWarning: Unknown pytest.mark.asyncio` warnings in the
empirical run log). With no asyncio plugin loaded, every async test is
silently skipped with a Failed status.

### Bug 2: `[dependency-groups]` is not equivalent to `[project.optional-dependencies]`

PEP 735 `[dependency-groups]` is read by `uv sync --group dev`, NOT by
`uv pip install -e ".[dev]"`. So the recipe in TASK-REV-F0E4's task script
(`uv pip install -e ".[dev,providers]"`) silently no-ops on `dev`:

> ```
> warning: The package 'forge ...' does not have an extra named 'dev'
> ```

`providers` IS picked up (it's a real `[project.optional-dependencies]`
extra); `dev` silently isn't. As a result, on a fresh install via the
portfolio recipe, **no test framework is installed at all** — pytest had
to be added by hand for the F0E4 review run.

This is **pre-existing** (not introduced by TASK-REV-F0E4) and
**orthogonal to LangChain pinning** (would happen on any Python version).
It's filed separately to keep TASK-LCP-001 (the LangChain pin alignment, in the FEAT-F0EP feature folder) scope-clean and so it can
be fixed in parallel.

## Acceptance Criteria

- [ ] **Bug 1 fix**: `pytest-asyncio` added to dev deps with a sensible same-major cap
      (e.g. `pytest-asyncio>=0.24,<1`).
- [ ] **Bug 2 fix**: Decision made and applied on the install-path question (see Options below).
- [ ] After the fix: a fresh install using the **chosen recipe** (whichever path option (a) or (b)
      is selected below) installs `pytest`, `pytest-bdd`, and `pytest-asyncio` at minimum.
- [ ] After the fix: re-running the F0E4 pytest subset (`tests/unit tests/forge/config tests/forge/tools tests/hardening tests/forge/adapters/guardkit tests/test_approval_config.py tests/test_forge_config.py` with the same three `--ignore` flags) produces **zero** `Failed: async def functions are not natively supported` failures.
- [ ] Confirm count drops by ≈162 (ideally to 0; modulo other genuine async-test bugs that may surface once the plugin is loaded).
- [ ] Commit references `TASK-FIX-F0E7` and `TASK-REV-F0E4` in the message body.

## Options (decision required — Bug 2)

`[dependency-groups]` is the modern PEP 735 surface; `[project.optional-dependencies]`
is the older extras surface. Both work, but they're invoked differently. The choice
is about which install path forge wants to be the canonical one.

1. **(a) Mirror dev deps into `[project.optional-dependencies].dev`** so
   `uv pip install -e ".[dev]"` works as expected from the portfolio recipe.
   Keeps the GuardKit-template recipe portable across forge / jarvis /
   study-tutor / etc. without per-repo command tweaks. **Recommended for
   demo-stability — minimal blast radius, matches existing portfolio
   muscle-memory.**

2. **(b) Drop `[project.optional-dependencies].dev` (already absent) and
   document that forge dev install requires `uv sync --group dev`**.
   Cleaner architecturally (single source of truth) but breaks the
   recipe assumed by GuardKit's portfolio-pinning workflow guide. If
   chosen, file a follow-up cross-repo task to update that guide
   (out of forge's scope to actually edit).

3. **(c) Both — declare in both surfaces**. Belt and braces; some duplication
   but works under both invocation patterns. PEP 735 explicitly allows this.

**Recommendation**: (a) or (c). (b) is technically cleaner but breaks the
portfolio recipe and forces a cross-repo coordination — not worth it for
this small dep list.

## Out of scope

- The LangChain 1.x pin alignment (that's TASK-LCP-001 inside the FEAT-F0EP feature folder at `tasks/backlog/langchain-1x-pin-alignment/`).
- Fixing the `nats-core` import (that's TASK-FIX-F0E6).
- Fixing `forge.build` stale ref (that's TASK-FIX-F0E8).
- Diagnosing/fixing async tests that fail for *real* reasons once
  `pytest-asyncio` is loaded (those would be separate bug-fix tasks
  per their own root causes — the 162 here all share the
  "no plugin" root cause).
- Adding any other `pytest-*` plugins beyond `pytest-asyncio` (e.g.
  `pytest-cov`, `pytest-xdist`) — separate concerns if needed.
- Updating GuardKit's portfolio-pinning workflow guide if option (b) is
  chosen — that's a cross-repo concern, not a forge fix.

## Source Material

- **Empirical observation**: [`.claude/reviews/TASK-REV-F0E4-report.md`](../../.claude/reviews/TASK-REV-F0E4-report.md) §5.2 (full diagnosis)
- **Pytest log**: [`docs/history/portfolio-py314-rebaseline-pytest.log`](../../docs/history/portfolio-py314-rebaseline-pytest.log) (the 162 failures + 90 `pytest.mark.asyncio` warnings)
- **PEP 735 reference**: <https://peps.python.org/pep-0735/> (read-only context)
- **The file being changed**: [`pyproject.toml`](../../pyproject.toml) `[dependency-groups].dev`
