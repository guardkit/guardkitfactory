# Implementation Guide — FEAT-F0EP: LangChain 1.x pin alignment (forge)

**Feature ID**: FEAT-F0EP
**Feature slug**: `langchain-1x-pin-alignment`
**Parent review**: [TASK-REV-F0E4](../../in_progress/TASK-REV-F0E4-portfolio-py314-langchain-1x-alignment.md)
([report](../../../.claude/reviews/TASK-REV-F0E4-report.md))
**Cross-repo precedent**: Jarvis ADR-ARCH-010 rev2
**Cross-repo template**: study-tutor [FEAT-7BDP](../../../../study-tutor/tasks/backlog/py314-langchain-pin-alignment/) (parallel rollout)
**Total subtasks (in this folder)**: 1
**Total waves**: 1
**Estimated effort**: 30 minutes (mechanical change + one fresh-venv install + one ADR status flip)

---

## What this feature does

Brings forge's `pyproject.toml` in line with the **FA04 / ADR-ARCH-010-rev2**
portfolio recipe: prophylactic forward protection against the LangChain
coordinated-major-bump trapdoor that bit Jarvis on FEAT-J004-702C
(33-minute autobuild stall, 2026-04-27).

forge's posture has the **same shape Jarvis had at the moment it broke** —
open floors on `langgraph>=0.2`, `langchain-anthropic>=0.2`,
`langchain-openai>=0.2`, `langchain-google-genai>=2.0`, and missing `<2`
caps on the 1.x members of the family. Today's resolver picks the
Jarvis-verified versions on its own (the empirical run in the review
confirms this, 6-of-6 match), but a future fresh install — clean machine,
cleared cache, `uv sync --upgrade` — could regress to a mixed 0.x/1.x
set and surface
`ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'`
exactly as Jarvis did.

This feature locks in the current healthy resolution as the contract.

## What this feature does NOT do

- Does not move `langchain-anthropic` between `[dependencies]` and
  `[providers]` (deferred per ADR-ARCH-032 §"Out of scope").
- Does not change `requires-python`, `deepagents`, `pydantic`,
  `nats-core`, `python-dotenv`, or `pyyaml`.
- Does not regenerate `uv.lock` (none checked in; review §5.4).
- Does not fix the `nats-core`, `pytest-asyncio`, or `forge.build`
  pre-existing issues uncovered in the review — those are
  deferred-promoted siblings (`TASK-FIX-F0E6/F0E7/F0E8`), not part of
  this feature folder.
- Does not touch GuardKit, Jarvis, study-tutor, agentic-dataset-factory,
  or specialist-agent.

---

## Wave structure

### Wave 1 (1 task)

| Task | Title | Files touched | Mode | Workspace (if Conductor) |
|------|-------|---------------|------|---------|
| TASK-LCP-001 | Apply ADR-ARCH-032 pin diff + flip ADR to Accepted | `pyproject.toml`, `docs/architecture/decisions/ADR-ARCH-032-...md` | direct | `langchain-1x-pin-alignment-wave1-1` |

This is a single-task feature. No sequencing concerns within the folder.
The deferred-promoted siblings (`TASK-FIX-F0E6/F0E7/F0E8`) are flat in
`tasks/backlog/` and have **no dependency** on this task — they can run
independently in parallel.

### Sequencing relative to deferred-promoted siblings

`TASK-LCP-001` (this feature) is **independent** of `TASK-FIX-F0E6/F0E7/F0E8`.
The pin alignment doesn't touch test infrastructure or code modules; the
sibling fixes don't touch `pyproject.toml` LangChain pins. They share no
files. Conductor parallelism is safe across all four if desired.

**However**, if the demo machine setup needs to actually *run* forge,
the priority order is:

1. **TASK-FIX-F0E6** (nats-core import) — demo-blocker. Without this,
   forge can't import its own pipeline modules on a fresh install.
2. **TASK-LCP-001** (this feature) — prophylactic forward protection.
3. **TASK-FIX-F0E7** (pytest-asyncio + dev-deps) — only matters if
   pytest will be run during demo prep.
4. **TASK-FIX-F0E8** (`forge.build` stale ref) — cosmetic; one collection
   error in an isolated test file.

---

## Execution

### Recommended path: single PR

The task is small enough that a single-commit PR is the natural shape:

```bash
# From the repo root:
git checkout -b feat/langchain-1x-pin-alignment

# Apply the pin diff
/task-work TASK-LCP-001
# (apply pin diff from review §4 / ADR-ARCH-032 §"Decision";
#  run fresh-venv install + smoke-test on Py3.14;
#  flip ADR-ARCH-032 status: Proposed → Accepted;
#  commit)

# Open PR; squash if multiple commits ended up.
```

### Alternative: bundle with the demo-blocker fixes

If running this alongside `TASK-FIX-F0E6` (the demo-blocker) makes sense
calendar-wise, those can land in **separate commits in the same PR**
(they touch different files: pyproject pins vs. nats-core resolution).
Keep `TASK-LCP-001` and `TASK-FIX-F0E6` as distinct commits even if
bundled — they have different rationales and reviewers may want to
revert one without the other.

### Conductor parallelism

For a 1-task feature this isn't useful; bundled execution is faster
end-to-end. But the deferred-promoted siblings could be parallelised:

```bash
conductor open .
# Spawn workspaces from main:
#   langchain-1x-pin-alignment-wave1-1  → /task-work TASK-LCP-001
#   forge-fix-nats-core                 → /task-work TASK-FIX-F0E6
#   forge-fix-pytest-asyncio            → /task-work TASK-FIX-F0E7
#   forge-fix-forge-build-stale-ref     → /task-work TASK-FIX-F0E8
# Merge each back to main when green.
```

Worth it only if you're running all four in the same window.

---

## Verification recipe (lifted from TASK-LCP-001 ACs)

```bash
# Don't clobber the F0E4 review run's .venv — use a sibling name
uv venv --python 3.14 .venv-verify
uv pip install --upgrade --python .venv-verify/bin/python -e ".[providers]"

# Smoke test
.venv-verify/bin/python -c "import forge; print('OK')"

# Confirm resolved versions match the ADR-ARCH-032 verified-versions table
uv pip list --python .venv-verify/bin/python | grep -E "lang|deepagent" | sort
# Expected (allowing patch drift):
#   langchain          ≥1.2.x  <2
#   langchain-anthropic ≥1.4.x <2
#   langchain-community ≥0.4.x <0.5
#   langchain-core     ≥1.3.x  <2
#   langchain-google-genai ≥4.2.x <5
#   langchain-openai   ≥1.2.x  <2
#   langgraph          ≥1.1.x  <2
#   deepagents         ≥0.5.x  <0.6
```

The pytest smoke check is **deliberately not** part of this task's ACs
because the runnable subset is blocked by `nats-core` (TASK-FIX-F0E6) and
`pytest-asyncio` missing (TASK-FIX-F0E7). The `import forge` smoke + the
resolved-versions table is sufficient evidence that the pin diff didn't
break anything LangChain-related — and that's all this feature claims
to verify.

If TASK-FIX-F0E6 lands first, add `.venv-verify/bin/python -m pytest` to
the verification step to broaden the safety net. Optional, not required.

---

## Acceptance for the whole feature

Marked complete when:

- [ ] TASK-LCP-001's listed acceptance criteria are all ticked.
- [ ] `pyproject.toml` matches the ADR-ARCH-032 §"Decision" diff exactly.
- [ ] ADR-ARCH-032 frontmatter shows `Status: Accepted` with the
      acceptance-stamp line.
- [ ] No changes outside `pyproject.toml` and the ADR file (CLAUDE.md
      pinning-policy paragraph is bundle-if-trivial; flag in PR
      description either way).

When complete, archive **TASK-REV-F0E4** by transitioning its
`status: review_complete → completed` with `decision: implemented`
in `review_results`. The deferred-promoted siblings remain in backlog
on their own schedule.

---

## Reading the review report once before starting

`.claude/reviews/TASK-REV-F0E4-report.md` is the single source of truth.
Read at minimum:

- **§1.1–1.4** — empirical evidence (install outcome, resolved versions
  table, runtime probe results, pytest subset run).
- **§2** — the latent-trapdoor argument (why pin if nothing's broken).
- **§4** — the exact pin diff TASK-LCP-001 applies, with per-pin rationale.
- **§9** (Findings summary) and **§10** (Recommendations table) — the
  big-picture map.

§3 (failure categorisation) and §5 (out-of-scope findings) are background
context — they explain why this feature deliberately leaves
`nats-core` / `pytest-asyncio` / `forge.build` issues to the
deferred-promoted siblings.

---

## Risk and rollback

**Risk**: minimal. The pin tightening codifies versions the resolver
already picks today; no runtime behaviour change. Worst case: a new
upstream release between today and the verification step picks a
different patch that breaks one of the existing test paths. Mitigation:
TASK-LCP-001's smoke-test step (`import forge` on a fresh Py3.14 venv)
catches any such regression before commit.

**Rollback**: `git revert` of the bundled commit restores the prior
`pyproject.toml`. The ADR-ARCH-032 status flip rolls back automatically
with the same revert. If the file has been merged independently, flip
it back to `Status: Proposed` manually.

---

## Cross-repo coordination

**None required.** This feature is fully self-contained in forge.
The cross-repo references in ADR-ARCH-032 and the review report are
**read-only links** to existing artefacts in Jarvis, GuardKit, and
study-tutor — no sibling-repo PRs are needed.

The portfolio rollout is happening in parallel:

- ✅ Jarvis: ADR-ARCH-010 rev2 (already accepted; FEAT-J004-702C run 2 verified).
- 🔄 study-tutor: [FEAT-7BDP / TASK-REV-57BD](../../../../study-tutor/tasks/backlog/py314-langchain-pin-alignment/) (this feature's template).
- 🔄 forge: this feature.
- ❓ agentic-dataset-factory, specialist-agent: separate review tasks in their own repos.

If equivalent pin alignments are wanted in agentic-dataset-factory or
specialist-agent, those are separate review tasks per the portfolio
guide's "calibrated per consumer, not copy-pasted" principle.
