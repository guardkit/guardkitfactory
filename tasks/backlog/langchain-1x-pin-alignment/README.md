# FEAT-F0EP — LangChain 1.x pin alignment (forge)

**Parent review**: [TASK-REV-F0E4](../../in_progress/TASK-REV-F0E4-portfolio-py314-langchain-1x-alignment.md)
**Review report**: [.claude/reviews/TASK-REV-F0E4-report.md](../../../.claude/reviews/TASK-REV-F0E4-report.md)
**ADR (Proposed)**: [ADR-ARCH-032](../../../docs/architecture/decisions/ADR-ARCH-032-langchain-1x-portfolio-alignment.md)
**Cross-repo precedent**: [Jarvis ADR-ARCH-010 rev2](../../../../jarvis/docs/architecture/decisions/ADR-ARCH-010-python-312-and-deepagents-pin.md) (FA04 trapdoor remediation)
**Cross-repo template**: [study-tutor FEAT-7BDP](../../../../study-tutor/tasks/backlog/py314-langchain-pin-alignment/) (parallel portfolio rollout, same recipe)
**Status**: backlog (1 task in this folder + 3 deferred-promoted siblings — see below)
**Constraint**: DDD South West demo (autobuild builds jarvis/study-tutor/forge for the demo)

---

## Problem

GuardKit AutoBuild stalled for 33 minutes on Jarvis FEAT-J004-702C
(2026-04-27) due to two coupled pin issues:

1. A stale `requires-python = ">=3.12,<3.13"` cap on Jarvis excluded the
   active `/usr/local/bin/python3` (3.14, since 2025-10-07).
2. Open-floor LangChain ecosystem pins (`langchain-core>=0.3`, etc.) let the
   resolver pick mismatched 0.x / 1.x pairs and produce runtime
   `ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'`
   from a deleted compat helper.

Jarvis's remediation (ADR-ARCH-010 rev2): `requires-python = ">=3.11"` +
coherent 1.x with `<2` caps on the LangChain ecosystem. The portfolio guide
([`guardkit/docs/guides/portfolio-python-pinning.md`](../../../../guardkit/docs/guides/portfolio-python-pinning.md))
codifies the rationale.

The portfolio rollout was paused while orchestrator-side issues were resolved.
With Jarvis stable end-to-end, this is forge's catch-up. study-tutor's
parallel review ([TASK-REV-57BD / FEAT-7BDP](../../../../study-tutor/tasks/backlog/py314-langchain-pin-alignment/))
captured the same recipe; this feature folder is forge's mirror.

## What the review found

forge's posture is **structurally similar to Jarvis at the moment it broke**,
but is **not actively broken today**:

- ✓ `requires-python = ">=3.11"` (already correct).
- ✓ `deepagents>=0.5.3,<0.6` (already correct).
- ✓ Empirically verified: fresh 3.14.2 venv, `import forge` works, the
  resolver converges on **6-of-6** Jarvis-verified versions
  (`langchain 1.2.15`, `langchain-core 1.3.2`, `langgraph 1.1.10`,
  `langchain-anthropic 1.4.2`, `langchain-openai 1.2.1`,
  `langchain-google-genai 4.2.2`).
- ✓ All langchain runtime imports (including the FA04 trapdoor module
  `block_translators.langchain_v0`) resolve cleanly.
- ✓ Zero langchain-runtime failures in the runnable pytest subset.

**The gap** (latent risk, not active breakage):

- ✗ `langgraph>=0.2` — open 0.x floor; same shape that broke Jarvis.
- ✗ `langchain-anthropic>=0.2`, `langchain-openai>=0.2` — same.
- ✗ `langchain-google-genai>=2.0` — pre-1.x floor; package now at 4.x.
- ✗ `langchain>=1.2.11`, `langchain-core>=1.2.18` — 1.x floor but no `<2` cap.
- ✗ `langchain-community>=0.3` — forge-specific; resolver picks `0.4.1`;
  package not yet on 1.x.

## Solution approach

Today's resolver picks the Jarvis-verified versions on its own — but that's
one cache-state change away from regressing. The fix is **prophylactic**:
pin to the verified versions with `<2` (or `<5` / `<0.5`) caps, locking in
the current healthy resolution as the contract.

| # | Task | What it does |
|---|------|--------------|
| 1 | [TASK-LCP-001](TASK-LCP-001-pyproject-pin-updates.md) | `pyproject.toml`: 6 pin changes (5 in `dependencies`, 2 in `[providers]`). Smoke-test on Py3.14. Flip ADR-ARCH-032 `Proposed → Accepted`. ~7 line diff. |

This is a **single-task feature** (Wave 1, 1 task). Unlike study-tutor's
3-task split, the ADR file (`ADR-ARCH-032`) was already authored during
the review (lives at `docs/architecture/decisions/`). The CLAUDE.md
discoverability pointer mentioned in the review §4 is bundled into
TASK-LCP-001's "Out of scope, bundle if trivial" note rather than as
a separate task.

### Verified pin set (Python 3.14.2, 2026-04-29)

The floors in TASK-LCP-001 match the resolved versions from the review's
empirical run. These are the same versions Jarvis verified on 3.14
(rev2 §"Empirical test on Python 3.14"):

```
langchain                 1.2.15
langchain-anthropic       1.4.2     (Jarvis: 1.4.1 — one patch ahead)
langchain-community       0.4.1     (forge-only — not in Jarvis)
langchain-core            1.3.2
langchain-google-genai    4.2.2
langchain-openai          1.2.1
langgraph                 1.1.10
deepagents                0.5.4     (already correctly pinned)
```

## Deferred-promoted siblings (out of scope here, filed as separate tasks)

The empirical Python 3.14 run uncovered three pre-existing forge-side
issues that are **orthogonal to LangChain** but were surfaced by this
review. They live as flat siblings in `tasks/backlog/`, not in this
feature folder, because they have nothing to do with the pin alignment:

| Sibling | What it fixes | Why separate | Demo-blocking? |
|---|---|---|---|
| [TASK-FIX-F0E6](../TASK-FIX-F0E6-nats-core-import-namespace.md) | `nats-core 0.2.0` PyPI wheel publishes under `nats/`, code imports `nats_core/` (55 collection errors) | Packaging issue, not a pin issue; would happen on any Python | **YES** — forge can't import its own pipeline modules on a fresh install |
| [TASK-FIX-F0E7](../TASK-FIX-F0E7-pytest-asyncio-and-dev-deps-install.md) | Add `pytest-asyncio` to `[dependency-groups].dev` and align dev-install path (PEP 735 vs `[project.optional-dependencies]`) | Test-infra fragility, not a pin issue (162 async-test failures) | No |
| [TASK-FIX-F0E8](../TASK-FIX-F0E8-forge-build-stale-module-ref.md) | `tests/unit/test_git_operations.py` references missing `forge.build` module | Stale test ref, isolated to one file | No |

This split is the analogue of study-tutor's `deferred_promoted: [TASK-IMP-B7E0]`
(R5 deepagents drift) — issues uncovered in the review that aren't part
of the pin alignment but need their own follow-up.

## Why this is high-priority but lower-risk than Jarvis was

**High priority**: forge is DDD South West demo-critical (autobuild
builds jarvis/study-tutor/forge for the demo). The clean-machine setup
risk is non-trivial.

**Lower risk than Jarvis was**: Jarvis on rev2 went from 25 failures to
7 failures (none langchain-runtime); forge today is **already at 0
langchain-runtime failures** on the verified version set. This feature
locks in that state — it doesn't fix a broken state.

The 218 pre-existing failures uncovered (56 collection + 162 async-infra)
are all **orthogonal** to LangChain and tracked in the deferred-promoted
sibling tasks above.

## What this feature deliberately doesn't do

- ✗ Move `langchain-anthropic` from `[dependencies]` to `[providers]` —
  separate LCOI-alignment concern, deferred per ADR-ARCH-032 §"Out of scope".
- ✗ Touch `requires-python`, `deepagents`, `pydantic`, `nats-core`,
  `python-dotenv`, `pyyaml` (already correct or unrelated to FA04 mechanism).
- ✗ Add or regenerate `uv.lock` (forge has no lockfile checked in;
  separate decision, see review §5.4).
- ✗ Fix `nats-core` import (TASK-FIX-F0E6, separate).
- ✗ Fix dev-deps install (TASK-FIX-F0E7, separate).
- ✗ Fix `forge.build` stale ref (TASK-FIX-F0E8, separate).
- ✗ Touch GuardKit, Jarvis, study-tutor, or any sibling repo
  (review's explicit out-of-scope list).
- ✗ Add CI matrix entries, pin-tracking guard tests, or a portfolio-policy
  doc beyond ADR-ARCH-032 (Jarvis has the latter; could be a future
  addition but not part of this feature).

## How to execute

Read [IMPLEMENTATION-GUIDE.md](IMPLEMENTATION-GUIDE.md) for the execution
plan, including the verification recipe and the rollback path.

TL;DR: one small mechanical task. Apply the diff, run a fresh-venv
pytest smoke check, flip the ADR status, commit.
