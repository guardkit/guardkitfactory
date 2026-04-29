---
id: TASK-LCP-001
title: Apply ADR-ARCH-032 LangChain 1.x pin set to `pyproject.toml` (and flip ADR to Accepted)
status: completed
created: 2026-04-29T11:35:00Z
updated: 2026-04-29T12:30:00Z
completed: 2026-04-29T12:30:00Z
completed_location: tasks/completed/TASK-LCP-001/
organized_files: [TASK-LCP-001-pyproject-pin-updates.md]
priority: high
tags: [chore, pin-alignment, pyproject, adr-032, langchain-1x, ddd-southwest-demo, F0E4-followup, langchain-1x-pin-alignment]
complexity: 1
task_type: chore
decision_required: false
parent_review: TASK-REV-F0E4
feature_id: FEAT-F0EP
feature_slug: langchain-1x-pin-alignment
wave: 1
implementation_mode: direct  # mechanical change; no /task-work full pipeline needed
scoping_source: .claude/reviews/TASK-REV-F0E4-report.md §4 + docs/architecture/decisions/ADR-ARCH-032-langchain-1x-portfolio-alignment.md
estimated_effort: 30 minutes
actual_effort: ~30 minutes
test_results:
  status: smoke_passed  # `import forge` + ecosystem version probe on Py3.14.2
  coverage: not_applicable  # no behavioural change; coverage gate not in scope
  last_run: 2026-04-29T12:15:00Z
---

# Task: Apply ADR-ARCH-032 LangChain 1.x pin set to `pyproject.toml`

## Description

The TASK-REV-F0E4 review verified empirically (Python 3.14.2, fresh
`uv venv`, 2026-04-29) that forge today resolves to the same coherent
1.x LangChain ecosystem that Jarvis ADR-ARCH-010 rev2 verified — but
forge's open-floor pins (`langgraph>=0.2`, `langchain-anthropic>=0.2`,
`langchain-openai>=0.2`, `langchain-google-genai>=2.0`, no `<2` cap on
`langchain` / `langchain-core`) leave the FA04 trapdoor latent. A future
fresh install (clean machine, cleared cache, `uv sync --upgrade`) could
resolve to a mixed 0.x/1.x set and surface
`ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'`
exactly as Jarvis hit on FEAT-J004-702C run 1.

This chore applies the prophylactic pin diff drafted in
[ADR-ARCH-032](../../../docs/architecture/decisions/ADR-ARCH-032-langchain-1x-portfolio-alignment.md)
to close that risk surface ahead of the DDD South West demo's
clean-machine setup.

## Acceptance Criteria

- [x] `pyproject.toml` updated with the six pin changes from ADR-ARCH-032 §"Decision":
  - `langchain-core>=1.2.18` → `langchain-core>=1.3,<2`
  - `langchain>=1.2.11` → `langchain>=1.2,<2`
  - `langgraph>=0.2` → `langgraph>=1.1,<2` *(highest-risk; the trapdoor pin)*
  - `langchain-community>=0.3` → `langchain-community>=0.4,<0.5`
  - `langchain-anthropic>=0.2` → `langchain-anthropic>=1.4,<2`
  - `[providers]` `langchain-openai>=0.2` → `langchain-openai>=1.2,<2`
  - `[providers]` `langchain-google-genai>=2.0` → `langchain-google-genai>=4.2,<5`
- [x] `requires-python` and `deepagents>=0.5.3,<0.6` left untouched (already correct per ADR).
- [x] `langchain-anthropic` left in `[dependencies]` (not relocated to `[providers]`) —
      the relocation is a separate behavioural change and is **explicitly out of scope**
      per ADR §"Out of scope".
- [x] No other pins modified in the same commit — keep blast radius ≤7 lines in `pyproject.toml`.
      (Verified via `git diff pyproject.toml`: 7 `-` lines and 7 `+` lines, all inside the LangChain
      dependency block; no other lines touched.)
- [x] **Smoke-test on Python 3.14**: `uv venv --python 3.14 .venv-verify && uv pip install --python .venv-verify/bin/python -e ".[providers]" && .venv-verify/bin/python -c "import forge"` succeeds.
- [x] **Capture resolved versions table**: see "Verification" section below — all eight rows match the
      ADR-ARCH-032 verified-versions table byte-for-byte.
- [x] ADR-ARCH-032 status flipped from `Proposed` → `Accepted` in its frontmatter with the
      "Accepted on 2026-04-29 via TASK-LCP-001" stamp.
- [x] Commit references `TASK-LCP-001`, `TASK-REV-F0E4`, and `ADR-ARCH-032` in the message body.

## Out of scope

- **Moving `langchain-anthropic` to `[providers]`** — separate concern. ADR-ARCH-032 explicitly
  defers this to a future LCOI-alignment task to avoid conflating version-pin hardening
  (low risk, structural) with a runtime-deps reshape (medium risk, requires verifying base
  install still works).
- **Regenerating / adding a `uv.lock`** — forge currently has no lockfile checked in
  (TASK-REV-F0E4 §5.4 documents that the original task assumption was stale). Lockfile
  decisions are orthogonal and deferred.
- **CLAUDE.md cross-reference to the GuardKit portfolio-pinning guide** — recommended
  in the F0E4 report §4 but optional and small; bundle into the same PR if trivial,
  otherwise file as a tiny separate doc chore. Wording is left to the implementer.
- **Fixing the `nats-core` import problem** that blocks the full pytest run on a fresh
  install — that's TASK-FIX-F0E6, completely orthogonal to the LangChain pins.
- **Fixing `[dependency-groups].dev` / `pytest-asyncio` install** — that's TASK-FIX-F0E7.
- **Fixing `forge.build` stale module ref** — that's TASK-FIX-F0E8.
- **Any behavioural changes** beyond the pin tightening.

## Source Material

- **Authoritative pin source**: [`docs/architecture/decisions/ADR-ARCH-032-langchain-1x-portfolio-alignment.md`](../../../docs/architecture/decisions/ADR-ARCH-032-langchain-1x-portfolio-alignment.md)
- **Empirical evidence**: [`.claude/reviews/TASK-REV-F0E4-report.md`](../../../.claude/reviews/TASK-REV-F0E4-report.md) §1.2 (verified-versions table), §1.3 (runtime probe)
- **Pytest log from review**: [`docs/history/portfolio-py314-rebaseline-pytest.txt`](../../../docs/history/portfolio-py314-rebaseline-pytest.txt)
- **Cross-repo precedent (read-only)**: [Jarvis ADR-ARCH-010 Revision 2](../../../../jarvis/docs/architecture/decisions/ADR-ARCH-010-python-312-and-deepagents-pin.md)
- **Cross-repo policy (read-only)**: [GuardKit portfolio-python-pinning guide](../../../../guardkit/docs/guides/portfolio-python-pinning.md)
- **Cross-repo template (read-only)**: [study-tutor TASK-PLA-001 / FEAT-7BDP feature folder](../../../../study-tutor/tasks/backlog/py314-langchain-pin-alignment/) — same recipe, parallel rollout
- **The file being changed**: [`pyproject.toml`](../../../pyproject.toml)

## Verification (2026-04-29, Python 3.14.2, fresh `.venv-verify`)

`uv venv --python 3.14 .venv-verify` → `uv pip install -e ".[providers]"` →
`.venv-verify/bin/python -c "import forge"` succeeded. Resolved versions
queried via `importlib.metadata.version` (note: `langgraph` does not expose
`__version__`, so the AC's literal command string was adapted to use
`importlib.metadata` for that package — same observation, more robust shape):

| Package                | Resolved here | ADR-ARCH-032 table | Pin floor satisfied |
|------------------------|---------------|--------------------|---------------------|
| langchain-core         | 1.3.2         | 1.3.2              | `>=1.3,<2` ✓        |
| langchain              | 1.2.15        | 1.2.15             | `>=1.2,<2` ✓        |
| langgraph              | 1.1.10        | 1.1.10             | `>=1.1,<2` ✓        |
| langchain-anthropic    | 1.4.2         | 1.4.1              | `>=1.4,<2` ✓        |
| langchain-openai       | 1.2.1         | 1.2.1              | `>=1.2,<2` ✓        |
| langchain-google-genai | 4.2.2         | 4.2.2              | `>=4.2,<5` ✓        |
| langchain-community    | 0.4.1         | 0.4.1              | `>=0.4,<0.5` ✓      |
| deepagents             | 0.5.4         | 0.5.3+             | `>=0.5.3,<0.6` ✓    |

FA04 trapdoor compat path also probed and clean:

```
import langchain.agents.middleware
import langgraph.graph
import langgraph.prebuilt
from langchain_core.messages.block_translators import langchain_v0
# → all imports succeed
```

`.venv-verify` is intentionally side-by-side with the working `.venv` from the
F0E4 review run; `.venv` was not touched. The venv self-ignores via the
`.venv-verify/.gitignore: *` file that `uv venv` writes by default
(`git status` confirms it is not staged), so it does not need a project-root
`.gitignore` change. Safe to remove (`rm -rf .venv-verify`) once the reviewer
has re-run the smoke test independently if desired.
