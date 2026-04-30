# Review Report: TASK-REV-F09A

**Task**: Diagnose & fix FEAT-FORGE-009 autobuild bootstrap failure
**Mode**: decision · **Depth**: standard · **Date**: 2026-04-30
**Reviewer**: `/task-review` (decision mode, empirical reproduction)

---

## Executive Summary

The autobuild bootstrap failure is **structural, not transient**. GuardKit's
`environment_bootstrap` is hardcoded to `pip install -e .`
(`environment_bootstrap.py:546,557`), which silently ignores
`[tool.uv.sources]` in `forge/pyproject.toml`. With no satisfying `nats-core`
on PyPI (only `0.0.0` is published under the `>=0.3.0,<0.4` constraint;
`0.1.0`/`0.2.0` require Python `>=3.13`), bootstrap cannot resolve the dep
and hard-fails before any task runs.

A second, independent gap surfaced during reproduction: **`click` and `rich`
are imported by `forge.cli.*` but are not declared in `pyproject.toml`**.
This would break the FEAT-FORGE-009 smoke gate (`forge serve --help`) even
if bootstrap succeeded.

**Recommendation**: **Layered fix**, in this order:
1. **Forge-side ship-now (Layer 1)**: add `.guardkit/preflight.sh` that
   pre-installs `nats-core` from the sibling source via plain `pip`, and add
   `click` + `rich` to `[project].dependencies`. Document as a required
   pre-step in `RUNBOOK-FEAT-FORGE-009`.
2. **Guardkit-side durable (Layer 2, separate task)**: teach
   `environment_bootstrap` to honour `[tool.uv.sources]` when `uv` is on
   `PATH`, otherwise emit an actionable error.
3. **Long-term**: ride on `TASK-FIX-F0E6b` to delete `[tool.uv.sources]`
   entirely once nats-core publishes a working wheel.

This unblocks Run 2 today, lands a durable fix without forge-team gating
on guardkit changes, and avoids `bootstrap_failure_mode: warn` (which
would mask the real failure and break smoke gates downstream).

---

## Empirical Reproduction

Performed on `2026-04-30` against the existing failed worktree at
`.guardkit/worktrees/FEAT-FORGE-009/`.

### Environment
- Host Python: `/usr/bin/python3` → `Python 3.12.3` (matches forge `requires-python: >=3.11`)
- `uv`: **not installed system-wide** (`uv: command not found`)
- Worktree venv: `.guardkit/worktrees/FEAT-FORGE-009/.guardkit/venv/` (left over from Run 1, pip 24.0)
- Sibling layout: `~/Projects/appmilla_github/{forge, jarvis, nats-core}` — `nats-core` source has `version = "0.3.0"`, `requires-python = ">=3.10"` (satisfies forge's constraint)

### Reproduction A — pip path (fails identically to Run 1)

```bash
cd .guardkit/worktrees/FEAT-FORGE-009
.guardkit/venv/bin/python -m pip install -e .
```

Output (last lines):
```
Collecting deepagents<0.6,>=0.5.3 ...
Collecting langchain<2,>=1.2 ...
INFO: pip is looking at multiple versions of forge ...
ERROR: Ignored the following versions that require a different python version:
       0.1.0 Requires-Python >=3.13; 0.2.0 Requires-Python >=3.13
ERROR: Could not find a version that satisfies the requirement
       nats-core<0.4,>=0.3.0 (from forge) (from versions: 0.0.0)
ERROR: No matching distribution found for nats-core<0.4,>=0.3.0
```

Matches the Run 1 transcript byte-for-byte. Confirms `pip` ignores
`[tool.uv.sources]`.

### Reproduction B — pre-install nats-core, then forge (succeeds)

```bash
.guardkit/venv/bin/python -m pip install -e ~/Projects/appmilla_github/nats-core
# → Successfully installed nats-core-0.3.0 nats-py-2.14.0 pydantic-2.13.3 ...

.guardkit/venv/bin/python -m pip install -e .
# → Successfully built forge
# → Successfully installed forge-0.1.0 langchain-1.2.16 langgraph-1.1.10 ...
```

Plain `pip` resolves cleanly once `nats-core` is already satisfied in the
venv — pip's resolver short-circuits the unsatisfiable PyPI lookup.
**No `uv` required.**

### Reproduction C — entry-point smoke (surfaces the click/rich gap)

```bash
.guardkit/venv/bin/forge --help
# ModuleNotFoundError: No module named 'click'

# After `pip install click`:
.guardkit/venv/bin/forge --help
# ModuleNotFoundError: No module named 'rich'
```

Both `click` and `rich` are imported by `forge/src/forge/cli/{history,queue,
status,cancel,skip,main}.py` but neither appears in `[project].dependencies`
nor in any extra. They are not pulled transitively by langchain/deepagents
in the resolved set. **This is a separate, latent bug** that would block the
FEAT-FORGE-009 smoke gate (`forge serve --help`) even if bootstrap were fixed.

---

## Root-Cause Statement (confirmed)

**Three intersecting facts produce the failure:**

1. **`forge/pyproject.toml:17`** declares `nats-core>=0.3.0,<0.4` as a hard
   runtime dependency.
2. **PyPI does not publish a wheel that satisfies the constraint:** `0.0.0`
   doesn't satisfy `>=0.3.0`; `0.1.0` and `0.2.0` require Python `>=3.13`
   (forge runs on `>=3.11`); and even if 0.2.0 installed, it ships a
   malformed wheel missing the `nats_core/` namespace (see TASK-FIX-F0E6b).
3. **`forge/pyproject.toml:89-90`** works around (2) with
   `[tool.uv.sources] nats-core = { path = "../nats-core", editable = true }`,
   which **only `uv` reads**.

**The structural gap:** GuardKit's environment bootstrap path constructs
its install command at
[guardkit/orchestrator/environment_bootstrap.py:546,557](file:///home/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/orchestrator/environment_bootstrap.py#L546)
as:

```python
install_command=[sys.executable, "-m", "pip", "install", "-e", "."],
```

— hardcoded to `pip`, with no detection of `[tool.uv.sources]` or
`uv.lock`, and no preference for `uv pip install` when uv is on PATH. The
PEP 668 fallback (line 37 of the Run 1 transcript) likewise re-invokes
`pip` inside the new venv. So **every autobuild run on a forge branch
that ships the sibling-source override will hard-fail at bootstrap until
the dependency is otherwise satisfied**.

**Secondary finding (out of original scope but blocks Run 2):** `click` and
`rich` are undeclared CLI deps in `forge/pyproject.toml`.

---

## Candidate-Fix Evaluation

Each option scored on **correctness** (does it actually solve it), **blast
radius** (which repos / how much surface), **time-to-unblock** (when can
Run 2 go), **durability** (does it survive future feature branches), and
**ownership** (who has to do the work).

| # | Option | Correct | Blast radius | Time-to-unblock | Durability | Owner | Verdict |
|---|--------|---------|--------------|-----------------|------------|-------|---------|
| **A** | Switch GuardKit bootstrap to `uv` (detect `[tool.uv.sources]` / `uv.lock`, prefer `uv pip install -e .` when `uv` on PATH) | ✅ Yes | guardkit (1 file + tests); forge needs `.guardkit/worktrees/nats-core` symlink + `uv` installed | M (cross-repo PR + review) | ✅ High — durable, removes the structural gap | guardkit team | **Recommend as Layer 2 (durable follow-up)** |
| **B** | Pre-bootstrap the venv via `uv sync` before `guardkit autobuild`; reuse the prebuilt venv | ✅ Yes (if guardkit reuses the venv) | forge (preflight script); requires `uv` installed | S | Med — operator-burden, easy to skip; needs guardkit to actually reuse the venv | forge | Rejected — not verified guardkit reuses the venv; adds operator burden; needs `uv` |
| **C** | `bootstrap_failure_mode: warn` (per orchestrator hint) | ❌ No | forge (1 line of config) | XS | ❌ Zero — masks the failure, leaves forge **not installed** in the worktree → breaks smoke gate (`forge serve --help`), pytest, and BDD oracle | forge | **Rejected** — explicitly contradicts the FEAT-FORGE-009 smoke gate definition |
| **D** | Republish a working `nats-core` wheel to PyPI | ✅ Yes (long-term) | nats-core (build pipeline fix) | M (cross-repo, cross-team) | ✅ High — fixes root cause, lets us delete `[tool.uv.sources]` entirely | nats-core team | Already tracked as **TASK-FIX-F0E6b**; reviewer recommends expediting but does not duplicate |
| **E** | Replace `nats-core>=0.3.0,<0.4` with `nats-core @ git+ssh://…@<sha>` direct reference (pip-honoured) | ✅ Yes | forge (1 line) | S | Med — pins to a sha (loses iteration ergonomics on the sibling), needs SSH/access in CI, no editable | forge | Rejected — kills sibling-iteration story that motivated `[tool.uv.sources]` in the first place; CI ergonomics worse than Layer 1 |
| **F** | Private wheel server with extra-index-url | ✅ Yes | infra (new index + pip.conf) | M (infra change + ops setup) | High but heavy | infra | Rejected — too much infrastructure for a 4-task feature; F0E6b is the right way to use PyPI |
| **G (NEW)** | **Forge-side `.guardkit/preflight.sh`** that (a) installs `nats-core` from sibling source via plain `pip`, (b) seeds the worktree venv before `guardkit autobuild` is invoked. **Plus** add missing `click`/`rich` to `forge/pyproject.toml`. | ✅ Yes (verified empirically — Reproduction B) | forge (1 script + 2 deps + runbook note) | XS — ship today | Med — works as long as guardkit's `pip install -e .` continues to short-circuit already-installed deps; survives every forge branch using `[tool.uv.sources]` | forge | **Recommended as Layer 1** |
| **H** | Vendor `nats-core` as a wheel inside `forge/.wheels/` and add to `pyproject.toml` via a `pip --find-links` mechanism | ⚠️ Partial | forge (committed wheel + pip.conf) | S | Low — every nats-core version bump = re-vendor + commit | forge | Rejected — commits a third-party wheel into the repo, drifts from sibling source |

**Options not on the original table that the reviewer surfaced:** **G** (preflight + missing-deps fix). **H** considered and rejected.

---

## Recommended Decision

**Adopt G as Layer 1, A as Layer 2, ride D as Layer 3.**

### Layer 1 — Ship today (forge repo only)

**Goal**: unblock FEAT-FORGE-009 Run 2 on the current dev box, with no
guardkit changes, no `uv` install, no cross-repo coordination.

Concrete deliverables (one implementation task, see "Implementation Tasks"
below):

1. **Create `.guardkit/preflight.sh`** (chmod +x). The script:
   - Resolves the active worktree via `$1` (or detects from `pwd`) and
     ensures `.guardkit/venv/` exists (creates with `python3 -m venv` if
     not).
   - Resolves the absolute path to the sibling `nats-core` repo (from
     `$FORGE_NATS_CORE_PATH` env or `../../../../nats-core` relative to
     the worktree root).
   - Runs `<venv>/bin/python -m pip install -e <abs-nats-core-path>` to
     seed `nats-core` into the venv.
   - Exits 0 on success; clear error message if `nats-core` source is
     missing.
2. **Add to `forge/pyproject.toml` `[project].dependencies`**:
   - `click>=8.1,<9`
   - `rich>=13,<15`
   (Pin ranges chosen to match the major lines installed by `pip install`
   today; tighten/loosen per code-style review.)
3. **Update the runbook**: append a "Run 1 failure → Run 2 prep" section
   to `docs/history/RUNBOOK-FEAT-FORGE-008-validation-run-1.md` (or a new
   `RUNBOOK-FEAT-FORGE-009-bootstrap-prep.md` if cleaner) instructing the
   operator to run `.guardkit/preflight.sh .guardkit/worktrees/FEAT-FORGE-009`
   **before** `guardkit autobuild feature FEAT-FORGE-009`.
4. **Verify Run 2 green**: clean the existing `.guardkit/venv/`, re-run
   the preflight, run `guardkit autobuild feature FEAT-FORGE-009 --verbose`,
   confirm Phase 1 (Setup) completes without bootstrap hard-fail.

### Layer 2 — Durable follow-up (guardkit repo)

**Goal**: remove the operator burden by teaching guardkit's bootstrap to
honour `[tool.uv.sources]` natively.

Cross-repo task (open against the **guardkit** repo):

> **Title**: `environment_bootstrap`: prefer `uv pip install -e .` when
> pyproject declares `[tool.uv.sources]` or a `uv.lock` is present
>
> **Behaviour**:
> - If pyproject declares `[tool.uv.sources]` **and** `uv` is on `PATH`:
>   substitute `[uv, "pip", "install", "-e", "."]` for the hardcoded
>   `[python, "-m", "pip", "install", "-e", "."]` at lines 546/557.
> - If `[tool.uv.sources]` is declared but `uv` is **not** on PATH:
>   emit a single actionable error explaining that the project requires
>   `uv` and pointing at the `[tool.uv.sources]` block.
> - If `uv.lock` is present (regardless of `[tool.uv.sources]`):
>   prefer `uv pip sync uv.lock` for full lockfile fidelity.
>
> **Safety**: behaviour for projects without `[tool.uv.sources]` /
> `uv.lock` is unchanged (continues to use pip).

Once Layer 2 lands, forge can drop the preflight requirement.

### Layer 3 — Long-term root-cause (nats-core repo)

**Goal**: remove the need for the sibling-source override entirely.

Already tracked as `TASK-FIX-F0E6b`. Reviewer recommends **expediting**
(not duplicating). Once shipped:

- Forge can delete `[tool.uv.sources]` from `pyproject.toml`.
- Layer 1 preflight becomes unnecessary even on machines without uv.
- Layer 2 (guardkit-side uv detection) is still useful for **other**
  repos, but no longer load-bearing for forge.

### Why not C (`bootstrap_failure_mode: warn`)?

The orchestrator's own hint suggests this, but **it directly contradicts
the FEAT-FORGE-009 smoke-gate definition**
(`.guardkit/features/FEAT-FORGE-009.yaml:114` runs `forge serve --help`).
With `warn` mode the worktree venv would not have `forge` installed; the
smoke gate fails at the first task; the BDD oracle synthesises a failure
on every scenario. It is a band-aid that turns a Phase-1 failure into a
Phase-3+ cascade — strictly worse for diagnosis. **Rejected with cause.**

---

## Implementation Tasks

The chosen fix produces these tasks (the operator should review and
adjust before `/task-create`):

### Layer 1 — single forge-repo task (PRIORITY: HIGH, ship today)

> **TASK-FIX-F09A1**: Add `.guardkit/preflight.sh` for nats-core sibling
> seeding + add missing `click`/`rich` deps + runbook entry. Verify
> FEAT-FORGE-009 autobuild Run 2 reaches Phase 2.
>
> **Acceptance**:
> - `.guardkit/preflight.sh` exists, executable, idempotent, parametrised
>   on worktree path.
> - `forge/pyproject.toml` declares `click>=8.1,<9` and `rich>=13,<15`.
> - Runbook section "Bootstrap Prep" added; references this task and
>   TASK-REV-F09A.
> - `guardkit autobuild feature FEAT-FORGE-009 --verbose --fresh`
>   completes Phase 1 (Setup) and reaches Phase 2 (Wave 1) without
>   bootstrap hard-fail.
> - `.guardkit/venv/bin/forge --help` exits 0 inside the worktree venv.

### Layer 2 — cross-repo guardkit task (PRIORITY: MEDIUM, durable)

> **GUARDKIT-TASK-XXX** (filed against `appmilla_github/guardkit`):
> teach `environment_bootstrap` to detect `[tool.uv.sources]` / `uv.lock`
> and prefer `uv pip install -e .` when `uv` is on PATH. See acceptance
> criteria above.

(Reviewer should hand off this task description to the guardkit
maintainer; it does not block FEAT-FORGE-009 Run 2.)

### Layer 3 — already tracked

`TASK-FIX-F0E6b` (nats-core wheel republish). Recommend expediting; no
new task created here.

---

## Acceptance-Criteria Coverage

| Criterion (from TASK-REV-F09A) | Status |
|--------------------------------|--------|
| Failure reproduced locally with `pip` (fails) and `uv` (would succeed) | ✅ `pip` reproduction confirmed (Reproduction A); `uv` not installed but `pip + pre-seeded sibling` proven equivalent (Reproduction B) — same root cause traced to `[tool.uv.sources]` honouring |
| Root-cause statement confirmed with pointers to `pyproject.toml` lines and guardkit code path | ✅ `forge/pyproject.toml:17` (dep), `:89-90` ([tool.uv.sources]); `guardkit/orchestrator/environment_bootstrap.py:546,557` (hardcoded pip) |
| Each candidate fix scored on correctness/blast/time/durability | ✅ Table above; surfaces option G, rejects C/E/F/H with cause |
| Decision recorded with explicit justification | ✅ Layered fix (G + A + D), reasons stated |
| Implementation tasks created | ✅ Three tasks named (Layer 1 forge, Layer 2 guardkit, Layer 3 = existing F0E6b) — formal task creation deferred to user `[I]mplement` |
| FEAT-FORGE-009 autobuild Run 2 verified green | ⏳ Pending Layer 1 implementation |
| Runbook / history updated | ⏳ Pending Layer 1 implementation |

---

## Out-of-Scope Findings (filed for follow-up)

1. **Missing `click` and `rich` deps** in `forge/pyproject.toml` — folded
   into Layer 1 task above (it would otherwise immediately re-break the
   smoke gate).
2. **Worktree symlink hygiene** — jarvis's pyproject says "the autobuild
   workflow places a symlink there pointing at the real sibling". Forge's
   pyproject (line 86-88) acknowledges the same need. Layer 1's preflight
   should also create the symlink `.guardkit/worktrees/nats-core` →
   sibling, defensively, in case any future change re-routes through `uv`.
3. **`bootstrap_failure_mode` smart-default review** — guardkit's
   smart-default chose `block` correctly here (line 34 of transcript:
   "manifests declaring requires-python"). No action needed; flagged for
   awareness.

---

## Appendix — Key File Pointers

- Failure transcript: `docs/history/autobuild-FEAT-FORGE-009-failure-run-1-history.md`
- Forge pyproject: `pyproject.toml` (deps `:10-20`, `[tool.uv.sources]` `:89-90`, comments `:65-88`)
- Guardkit bootstrap: `guardkit/orchestrator/environment_bootstrap.py:546,557`
- Sibling nats-core: `~/Projects/appmilla_github/nats-core/pyproject.toml` (`version = "0.3.0"`, `requires-python = ">=3.10"`)
- Jarvis precedent: `~/Projects/appmilla_github/jarvis/pyproject.toml` (same `[tool.uv.sources]` pattern, comments document the symlink workflow)
- Sibling task (long-term): `tasks/backlog/TASK-FIX-F0E6b-republish-nats-core-wheel.md`
- Feature plan: `.guardkit/features/FEAT-FORGE-009.yaml` (smoke gate `:104-119` requires `forge serve --help`)

---

## Decision Options

- **[A]ccept** — approve findings, archive review.
- **[R]evise** — request deeper analysis on a specific area.
- **[I]mplement** — create implementation task(s) per Layer 1 above.
- **[C]ancel** — discard review.
