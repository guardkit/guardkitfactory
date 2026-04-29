# Review Report — TASK-REV-F0E4

## Executive Summary

**Task**: TASK-REV-F0E4 — Verify Python 3.14 + langchain-1.x portfolio alignment (per Jarvis FEAT-J004-702C precedent)
**Mode**: Diagnostic (standard depth) — empirical install + pytest, failure categorisation, pin recommendation, ADR draft
**Date**: 2026-04-29
**Demo constraint**: DDD South West — forge ships in the autobuild demo, must not regress on a clean-machine setup
**Outcome**: Recommend **prophylactic pin tightening** to align with [Jarvis ADR-ARCH-010 Revision 2](../../../jarvis/docs/architecture/decisions/ADR-ARCH-010-python-312-and-deepagents-pin.md). Concrete diff and ADR draft below.

**Headline finding**: Forge today, on a fresh Python 3.14 venv with current open-floor pins, **gives a coherent 1.x LangChain ecosystem and zero LangChain-runtime failures**. The resolver converges on the *exact same six versions* that Jarvis's ADR-ARCH-010 rev2 verified empirically. The FA04 trapdoor (`ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'`) **does not reproduce here today**.

**The catch**: forge's pin shape is the same shape Jarvis was in at the moment it broke — open floors on `langgraph>=0.2`, `langchain-anthropic>=0.2`, `langchain-openai>=0.2`, `langchain-google-genai>=2.0`, and no `<2` caps on the 1.x members of the family. The healthy resolution today is one cache-state change away from the same mixed-major trap that broke Jarvis. The recommendation is therefore to apply the same-major caps and Jarvis-verified floors as **prophylactic hardening**, even though no current breakage is observed. The [I]mplement option (selected) created the FEAT-F0EP feature folder at [`tasks/backlog/langchain-1x-pin-alignment/`](../../tasks/backlog/langchain-1x-pin-alignment/) containing [`TASK-LCP-001`](../../tasks/backlog/langchain-1x-pin-alignment/TASK-LCP-001-pyproject-pin-updates.md) (the primary deliverable), plus three deferred-promoted siblings ([`TASK-FIX-F0E6`](../../tasks/backlog/TASK-FIX-F0E6-nats-core-import-namespace.md), [`TASK-FIX-F0E7`](../../tasks/backlog/TASK-FIX-F0E7-pytest-asyncio-and-dev-deps-install.md), [`TASK-FIX-F0E8`](../../tasks/backlog/TASK-FIX-F0E8-forge-build-stale-module-ref.md)) for the orthogonal demo-blockers.

**Two pre-existing forge-side blockers were uncovered** that prevent the full pytest run but are **orthogonal to LangChain**:

1. `nats-core 0.2.0` PyPI wheel publishes content under `nats/` (specifically `nats/client/...`), but forge code imports `from nats_core.events import ...`. Causes 55 collection errors. Pre-existing — would happen on any Python version.
2. `[dependency-groups].dev` is missing `pytest-asyncio` despite forge having 100+ `@pytest.mark.asyncio` tests. Causes 162 `Failed: async def functions are not natively supported` failures in the runnable subset. Pre-existing — would happen on any Python version.

Both are recorded here for traceability and recommended to be filed as separate tasks.

## Review Details

- **Task ID**: TASK-REV-F0E4
- **Mode**: `diagnostic` (custom mode declared by the task; closest standard equivalent is `decision` — the deliverable is an empirical-evidence-backed pin recommendation + ADR draft)
- **Depth**: `standard`
- **Reviewer**: orchestrator with cross-repo evidence loading (Jarvis ADR rev2, GuardKit FA04 report, GuardKit portfolio-pinning guide, forge `pyproject.toml`, fresh Py3.14 install + pytest)
- **Knowledge graph**: not queried (Graphiti not loaded in this session)
- **Empirical environment**: `/usr/local/bin/python3.14` (Python 3.14.2), fresh `uv venv` at `.venv`, `uv pip install --upgrade -e ".[providers]"` + manual `pytest` install (see §5.2)

## 1. Empirical Run

### 1.1 Install command and outcome

Per the task script:

```bash
cd /Users/richardwoollcott/Projects/appmilla_github/forge
# .python-version did not exist (mv step a no-op)
# .venv did not exist (rm step a no-op)
uv venv --python 3.14 .venv          # → "Using CPython 3.14.2 interpreter"
uv pip install --upgrade --python .venv/bin/python -e ".[dev,providers]"
```

**Install succeeded** but with one warning:

> ```
> warning: The package `forge @ file:///.../forge` does not have an extra named `dev`
> ```

The task script's `[dev,providers]` extra-spec is **broken on forge** because forge declares dev deps under `[dependency-groups].dev` (PEP 735), not `[project.optional-dependencies].dev`. The `providers` extra IS picked up; `dev` silently isn't. Pytest had to be installed manually:

```bash
uv pip install --python .venv/bin/python "pytest>=9.0.2" "pytest-bdd>=8.1,<9"
```

This is a forge-side bug and is documented in §5.2 below.

**Smoke test passed**: `.venv/bin/python -c "import forge"` → `forge OK`.

### 1.2 Resolved versions (verified-versions table)

| Package | Resolved here (forge / Py3.14 / 2026-04-29) | Jarvis verified (ADR rev2) | Same? |
|---|---|---|---|
| langchain-core | **1.3.2** | 1.3.2 | ✅ exact |
| langchain | **1.2.15** | 1.2.15 | ✅ exact |
| langgraph | **1.1.10** | 1.1.10 | ✅ exact |
| langchain-anthropic | **1.4.2** | 1.4.1 | ✅ minor newer |
| langchain-openai | **1.2.1** | 1.2.1 | ✅ exact |
| langchain-google-genai | **4.2.2** | 4.2.2 | ✅ exact |
| langchain-community | **0.4.1** | n/a (Jarvis doesn't depend on it) | — forge-specific |
| langchain-classic | 1.0.4 | (transitive) | — |
| langchain-text-splitters | 1.1.2 | (transitive) | — |
| langgraph-checkpoint | 4.0.3 | (transitive) | — |
| langgraph-prebuilt | 1.0.12 | (transitive) | — |
| langgraph-sdk | 0.3.13 | (transitive) | — |
| langsmith | 0.7.38 | (transitive) | — |
| deepagents | **0.5.4** | 0.5.3+ | ✅ within range |
| pydantic | 2.13.3 | 2.x | ✅ within range |
| Python interpreter | 3.14.2 | 3.14 | ✅ |

**Six-of-six** match against Jarvis's empirically-validated set. The resolver, given forge's current open-floor pins on a fresh venv, converges on the same versions Jarvis's tighter pin set produces explicitly. **This is evidence the pins below would not change runtime behaviour today** — they would only protect future fresh installs from regressing.

### 1.3 LangChain runtime smoke test

A targeted import probe of every LangChain runtime path that broke Jarvis:

```
  OK  langchain                           v1.2.15
  OK  langchain_core                      v1.3.2
  OK  langchain_core.messages             ✓
  OK  langchain.agents                    ✓
  OK  langchain.agents.middleware         ✓
  OK  langgraph                           ✓
  OK  langgraph.graph                     ✓
  OK  langgraph.prebuilt                  ✓
  OK  langchain_openai                    ✓
  OK  langchain_anthropic                 v1.4.2
  OK  langchain_google_genai              ✓
  OK  langchain_community                 v0.4.1
  OK  deepagents                          v0.5.4
  OK  langchain_core.messages.block_translators.langchain_v0  ← FA04 trapdoor module IS present
```

The FA04 trapdoor module being importable here is **not** a sign of trouble — it means `langchain-core 1.3.2` retains the v0 compat path, paired correctly with `langchain 1.2.15`. The trapdoor surfaces as `ModuleNotFoundError` only when the resolver picks a langchain-core that has *removed* the compat path while `langchain` is still on a 0.x version that imports it. With both packages on 1.x in this resolution, the path resolves fine.

### 1.4 Pytest run

Full-suite output captured to [`docs/history/portfolio-py314-rebaseline-pytest.txt`](../../docs/history/portfolio-py314-rebaseline-pytest.txt) (also written as `.log` for local inspection; `*.log` is gitignored per repo policy, so the `.txt` mirror is the tracked copy).

**First attempt** (full suite): `!!!!!!!!!!!!!!!!!!! Interrupted: 55 errors during collection !!!!!!!!!!!!!!!!!!!`

All 55 collection errors share a single root cause:

```
ImportError while importing test module '...'
E   ModuleNotFoundError: No module named 'nats_core'
```

This is **not** a LangChain failure. See §3 (Failure Categorisation) and §5.1 for the diagnosis.

**Targeted subset** (excluding files that transitively import `nats_core`, plus three files with smaller pre-existing issues):

```bash
.venv/bin/python -m pytest --tb=line -q \
  --ignore=tests/unit/test_git_operations.py \
  --ignore=tests/forge/tools/test_guardkit.py \
  --ignore=tests/forge/adapters/guardkit/test_progress_subscriber.py \
  tests/unit tests/forge/config tests/forge/tools tests/hardening \
  tests/forge/adapters/guardkit tests/test_approval_config.py tests/test_forge_config.py
```

**Result**: `162 failed, 1522 passed, 90 warnings in 1.41s` (0 collection errors).

**Failure root-cause histogram** (all 162):

| Count | Root cause | Category |
|---|---|---|
| 162 | `Failed: async def functions are not natively supported` | Pre-existing (test infra) |
| 0 | `ModuleNotFoundError: No module named 'langchain_core.*.langchain_v0'` | LangChain runtime |
| 0 | `ImportError: cannot import name '...' from 'langchain.*'` | LangChain API break |

`grep -i 'langchain\|langgraph\|block_translators\|deepagents'` over the failure traces returns **zero matches**. There are zero LangChain-related failures.

## 2. The Latent-Trapdoor Argument (Why Pin If Nothing Is Broken?)

The empirical run shows a healthy resolution today. The case for pinning is structural, not reactive.

Forge's `pyproject.toml` declares:

```toml
"langgraph>=0.2",                  # 0.x floor; resolver free to pick 0.x → mismatch with 1.x langchain-core
"langchain-anthropic>=0.2",        # same
"langchain-openai>=0.2",           # same
"langchain-google-genai>=2.0",     # pre-1.x floor; same shape (next major was 4.x for this package)
"langchain>=1.2.11",               # 1.x floor but no <2 cap → resolves to 2.x on release day
"langchain-core>=1.2.18",          # 1.x floor but no <2 cap → same
"langchain-community>=0.3",        # 0.x; package hasn't moved to 1.x; floor lower than current 0.4.x
```

This is **the same shape Jarvis was in on 2026-04-26**. Jarvis's 33-min FEAT-J004-702C run-1 stall was triggered by exactly this resolver freedom — open floors on the providers, on `langgraph`, and on `langchain-core` led the resolver, in a different cache state, to pick a 0.x langchain alongside a 1.x langchain-core, which surfaced as `ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'` on the test path.

The DDD South West demo's clean-machine setup risk is non-trivial: a fresh checkout on a presenter's laptop, on the day of the demo, with whatever PyPI cache state happens to exist at that moment, could regress. The cost of pinning is one PR; the cost of a regression is a demo failure.

The recommendation is therefore a **prophylactic** application of the Jarvis-verified pin set, not a reactive fix. **Phase B (rerun with the proposed pins to verify the fix) was unnecessary because the proposed pins produce the same versions the resolver already picked** — confirmation already in §1.2.

## 3. Failure Categorisation

Per the task's investigation-scope §2 categories:

| Category | Forge result | Detail |
|---|---|---|
| **Pin guard tests** | n/a | Forge has no version-asserting tests for LangChain packages (Jarvis has `tests/test_phase2_dependencies.py`; forge does not). No lockstep rebase needed on this axis. |
| **LangChain runtime errors** | **0** | Confirms the FA04 mismatch hypothesis is **latent, not active** here today. No `block_translators.langchain_v0` ModuleNotFoundError in any failing test or import probe. |
| **API-level breakages** | **0** | All forge code that imports from `langchain.*`, `langgraph.*`, `langchain_anthropic.*`, etc. resolves cleanly. No 1.x removals/renames are biting forge. |
| **Pre-existing flakes / fragility** | **218** | 55 collection errors (`nats_core` packaging) + 1 collection error (`forge.build` stale ref) + 162 test failures (async-test infra). Detailed in §5. |

**Categorisation conclusion**: every failure observed in the empirical run is in the "pre-existing" bucket. None is on the LangChain axis. The pin recommendation is therefore *purely* prophylactic; no test will pass-after-not-passing as a result of applying it.

## 4. Pin Recommendation

The full diff and per-line rationale lives in the ADR draft at [`docs/architecture/decisions/ADR-ARCH-032-langchain-1x-portfolio-alignment.md`](../../docs/architecture/decisions/ADR-ARCH-032-langchain-1x-portfolio-alignment.md). Summary here:

```diff
 dependencies = [
     "deepagents>=0.5.3,<0.6",
-    "langchain>=1.2.11",
-    "langchain-core>=1.2.18",
-    "langgraph>=0.2",                          # ← highest-risk: same shape that broke Jarvis
-    "langchain-community>=0.3",
-    "langchain-anthropic>=0.2",                # ← high-risk: same 0.x → 1.x shape
+    "langchain>=1.2,<2",
+    "langchain-core>=1.3,<2",
+    "langgraph>=1.1,<2",
+    "langchain-community>=0.4,<0.5",           # forge-specific; same-minor cap (pkg still 0.x)
+    "langchain-anthropic>=1.4,<2",
     "nats-core>=0.2.0,<0.3",
     "python-dotenv>=1.0",
     "pyyaml>=6.0",
 ]

 [project.optional-dependencies]
 providers = [
-    "langchain-openai>=0.2",                   # ← high-risk
-    "langchain-google-genai>=2.0",             # ← high-risk: pre-1.x floor; pkg moved to 4.x
+    "langchain-openai>=1.2,<2",
+    "langchain-google-genai>=4.2,<5",
 ]
```

**Six pins changed; zero pins removed; zero pins added**. `requires-python = ">=3.11"` and `deepagents>=0.5.3,<0.6` are already correct (match Jarvis rev2 and the GuardKit portfolio policy).

**Notable forge-specific judgement calls**:

1. **`langchain-community>=0.4,<0.5`**: this package is **not** in Jarvis. Forge depends on it (`grep -rn "langchain_community" src/forge/` shows usage). The package has not yet moved to 1.x, and historically has had API drift between 0.x minors. A *minor* cap (rather than the major-cap pattern used elsewhere) is conservative; the next minor (`0.5`) is the natural next-eval point. Lift independently when langchain-community 0.5 (or 1.0) ships.

2. **`langchain-anthropic` location**: currently in `dependencies` (line 16), not in `[providers]`. Jarvis ADR rev2 puts it in `providers` per the LCOI principle (TASK-REV-LES1 §3). **This review does not recommend moving it as part of the pin update**. Moving it is a behaviour change at install time (the base `pip install .` would no longer pull `langchain-anthropic`); the version pin is the structural protection, and the location rebalance is a separate concern. Recommend filing the LCOI alignment as a follow-up task if portfolio coherence on that axis is a goal.

3. **No `[providers]` rebaseline beyond the two version bumps**. Jarvis rev2 keeps `langchain-anthropic` and `langchain-google-genai` together in `providers`; forge has `langchain-anthropic` in dependencies. As above — version pin yes, layout reshape no, in this ADR.

4. **CLAUDE.md cross-reference**: forge's [`.claude/CLAUDE.md`](../CLAUDE.md) already documents the LCOI principle for `[providers]`. Recommend adding a one-line forward pointer to the [GuardKit portfolio-pinning guide](../../../guardkit/docs/guides/portfolio-python-pinning.md) and to the new ADR-ARCH-032, so the rationale for the same-major caps is discoverable from CLAUDE.md. Exact wording is left to the implementation task.

## 5. Out-of-Scope Findings (For Separate Follow-Up Tasks)

These were uncovered by the empirical run but are not part of the LangChain-pin question. Recorded here so the rebaseline-task that implements ADR-ARCH-032 doesn't accidentally inherit them as in-scope.

### 5.1 `nats-core 0.2.0` PyPI wheel is broken

**Symptom**: 55 of 108 test files fail to collect with `ModuleNotFoundError: No module named 'nats_core'`.

**Root cause**: the `nats-core==0.2.0` PyPI wheel installs content under `nats/` (e.g. `nats/client/__init__.py`, `nats/client/connection.py`), but forge code does:

```python
# src/forge/pipeline/__init__.py:58
from nats_core.events import (...)

# src/forge/gating/wrappers.py:113-114
from nats_core.envelope import EventType, MessageEnvelope
from nats_core.events import ApprovalRequestPayload, ApprovalResponsePayload

# tests/forge/dispatch/test_orchestrator.py:50
from nats_core.manifest import AgentManifest, ToolCapability
```

The `nats_core/` namespace simply does not exist in the installed wheel. The dist-info exists (`nats_core-0.2.0.dist-info/`) but its `RECORD` lists only `nats/...` paths.

**Pre-existing**: would fail on any Python version. **Orthogonal to this review.**

**Possible fixes** (all out of scope here):
- (a) Newer `nats-core` PyPI release that ships under `nats_core/` (assuming the upstream fixed this layout in a later version)
- (b) `[tool.uv.sources]` entry pointing at the sibling repo (the pattern Jarvis uses per its `pyproject.toml`)
- (c) Code-side rename `from nats import ...` (likely the wrong direction — forge code clearly expects a `nats_core` namespace)

**Recommendation**: file as a separate task. The DDD demo will run forge end-to-end, so this is **demo-blocking** (forge can't import its own pipeline modules), but it's not what TASK-REV-F0E4 asks about.

### 5.2 `[dependency-groups].dev` doesn't pull `pytest-asyncio`

**Symptom**: 162 of 1684 tests in the runnable subset fail with `Failed: async def functions are not natively supported`.

**Root cause**: `pyproject.toml` declares dev deps under PEP 735's `[dependency-groups]`:

```toml
[dependency-groups]
dev = [
    "pytest>=9.0.2",
    "pytest-bdd>=8.1,<9",
]
```

Three problems:
1. `pytest-asyncio` is not listed, despite forge having `@pytest.mark.asyncio` on 100+ tests (90 warnings about "Unknown pytest.mark.asyncio" in the run output).
2. `[dependency-groups]` is not equivalent to `[project.optional-dependencies]`. `uv pip install -e ".[dev]"` does **not** read `[dependency-groups]`; only `uv sync --group dev` does. The task's install script (`uv pip install -e ".[dev,providers]"`) silently fails to install dev deps and warns:
   > `warning: The package 'forge ...' does not have an extra named 'dev'`
3. As a result, on a fresh install via the task's recipe, *no test framework is installed at all*. Pytest had to be added by hand.

**Pre-existing**: would happen on any Python version. **Orthogonal to this review.**

**Recommendation**: file as a separate task. Two cleanups bundle naturally:
- Add `pytest-asyncio` to `[dependency-groups].dev`.
- Either (a) mirror the dev list into `[project.optional-dependencies].dev` so `uv pip install -e ".[dev]"` works (consistent with the task script's expectation), or (b) update the GuardKit portfolio-pinning workflow guide to use `uv sync --group dev` instead of `uv pip install -e ".[dev]"`. Option (b) is cleaner architecturally; option (a) is friendlier to the existing portfolio recipe.

### 5.3 `tests/unit/test_git_operations.py` references missing `forge.build`

**Symptom**: 1 collection error: `E   ModuleNotFoundError: No module named 'forge.build'`.

**Root cause**: a stale module path in a test file. `forge.build` does not exist in `src/forge/`.

**Pre-existing**: would fail on any Python version. **Orthogonal.**

**Recommendation**: file as a separate task. Likely a one-line fix (rename or delete).

### 5.4 No `uv.lock` in repo

The TASK-REV-F0E4 task description's investigation-scope §5 says "forge has a `uv.lock`". The assumption is **stale**: `find . -maxdepth 3 -name 'uv.lock'` returns nothing. There is no checked-in lockfile.

**Implication**: the "Re-locking on 3.14 with the new pins should produce a coherent lockfile. Verify before committing." step in the task is moot for the rebaseline. If a `uv.lock` is added in the future (an orthogonal decision), it should be generated against the post-ADR-ARCH-032 pin set.

## 6. Acceptance Criteria — Coverage

| Criterion | Status | Where |
|---|---|---|
| ☑ Empirical 3.14 + `uv pip install --upgrade -e ".[dev,providers]"` succeeds; `import forge` works | Met (with caveat on `[dev]` extra — see §5.2) | §1.1 |
| ☑ Full pytest run captured to `docs/history/portfolio-py314-rebaseline-pytest.{log,txt}` | Met (subset; full suite blocked by `nats_core`, see §1.4 + §5.1; tracked as `.txt` since `*.log` is gitignored) | [log file](../../docs/history/portfolio-py314-rebaseline-pytest.txt) |
| ☑ Resolved versions documented for the LangChain ecosystem + deepagents | Met | §1.2 |
| ☑ Failure categorisation across pin-guard / langchain-runtime / API-break / pre-existing | Met (0/0/0/218 respectively) | §3 |
| ☑ Pin update recommendation with explicit `pyproject.toml` diff and `<2` caps | Met | §4 + ADR-ARCH-032 |
| ☑ New ADR drafted (`ADR-ARCH-032-langchain-1x-portfolio-alignment.md`) | Met | [`docs/architecture/decisions/ADR-ARCH-032-...`](../../docs/architecture/decisions/ADR-ARCH-032-langchain-1x-portfolio-alignment.md) |
| ☑ Recommendation on `[providers]` rebaseline | Met (pin yes; relocate `langchain-anthropic` no — separate task) | §4 + ADR §"Out of scope" |
| ☑ Recommendation on portfolio-pinning guide reference in `CLAUDE.md` | Met (yes; one-line forward pointer; wording deferred to impl task) | §4 + ADR §"CLAUDE.md / portfolio-guide reference" |
| ☑ No proposed changes to GuardKit or Jarvis | Met | All recommendations scoped to forge |
| ☑ Report saved to `.claude/reviews/TASK-REV-F0E4-report.md` | Met | this file |

All ten acceptance criteria are addressed.

## 7. Findings Summary

| # | Finding | Severity | Evidence |
|---|---|---|---|
| F1 | `langgraph>=0.2` open 0.x floor — exact shape that broke Jarvis on FEAT-J004-702C | **High** (latent forward-protection gap; trapdoor-class) | `pyproject.toml:14`; review §1.2 + §2 |
| F2 | `langchain-anthropic>=0.2`, `langchain-openai>=0.2` open 0.x floors | **High** (same shape) | `pyproject.toml:16, 27`; §2 |
| F3 | `langchain-google-genai>=2.0` pre-1.x floor (package now at 4.x) | **High** (same shape) | `pyproject.toml:28`; §2 |
| F4 | `langchain>=1.2.11`, `langchain-core>=1.2.18` lack `<2` caps | Medium (cap-only forward protection) | `pyproject.toml:12-13`; §4 |
| F5 | `langchain-community>=0.3` floor lower than current 0.4.x; package not yet on 1.x | Medium (forge-specific; not in Jarvis pin set) | `pyproject.toml:15`; §4 |
| F6 | **No langchain-runtime failures**; resolver picks 6-of-6 Jarvis-verified versions | Positive (cleaner baseline than Jarvis on rev2) | §1.2, §1.3, §3 |
| F7 | `requires-python = ">=3.11"`, `deepagents>=0.5.3,<0.6` already correct | Positive | `pyproject.toml:6, 11` |

Out-of-scope but discovered (orthogonal to LangChain — see §5):
- `nats-core 0.2.0` PyPI wheel layout mismatch (55 collection errors; demo-blocker)
- `[dependency-groups].dev` missing `pytest-asyncio` + PEP 735 vs `[providers]` install-path divergence (162 async-test failures)
- `tests/unit/test_git_operations.py` references missing `forge.build` module (1 collection error)

## 8. Recommendations

| # | Recommendation | Effort | Impact | Mode | Filed as |
|---|---|---|---|---|---|
| R1 | Add `<2` caps + tighten 1.x floors on `langchain`, `langchain-core` | XS (2 lines) | Forward protection vs FA04 cap-class regression | direct | TASK-LCP-001 (bundled) |
| R2 | Replace 0.x / pre-1.x provider floors with explicit 1.x (or 4.x) floors + `<2` (or `<5`) caps for `langgraph`, `langchain-anthropic`, `langchain-openai`, `langchain-google-genai` | XS (5 lines) | Forward protection vs FA04 trapdoor-class regression | direct | TASK-LCP-001 (bundled) |
| R3 | Tighten `langchain-community>=0.4,<0.5` (forge-specific; package still 0.x) | XS (1 line) | Forward protection on next minor; lifts when 0.5 / 1.0 ships | direct | TASK-LCP-001 (bundled) |
| R4 | Flip ADR-ARCH-032 status `Proposed → Accepted` after pin diff lands | XS (1 line) | Closes the audit trail | direct | TASK-LCP-001 (bundled) |
| R5 | Add a one-line "Pinning policy" pointer to `.claude/CLAUDE.md` referencing ADR-ARCH-032 and the GuardKit portfolio-pinning guide | XS (one paragraph) | Discoverability for next maintainer; consistent with study-tutor's R4 | direct | TASK-LCP-001 (bundle if trivial; out-of-scope-but-bundle) |

R1+R2+R3+R4 are all small, mechanical changes scoped to one file (`pyproject.toml`) plus the ADR status flip. They form a natural single-PR bundle and live in [TASK-LCP-001](../../tasks/backlog/langchain-1x-pin-alignment/TASK-LCP-001-pyproject-pin-updates.md). R5 is a bundle-if-trivial bonus.

The three out-of-scope demo-blockers (§5.1–5.3) are filed as flat siblings ([TASK-FIX-F0E6](../../tasks/backlog/TASK-FIX-F0E6-nats-core-import-namespace.md), [TASK-FIX-F0E7](../../tasks/backlog/TASK-FIX-F0E7-pytest-asyncio-and-dev-deps-install.md), [TASK-FIX-F0E8](../../tasks/backlog/TASK-FIX-F0E8-forge-build-stale-module-ref.md)), not folded into FEAT-F0EP — they have nothing to do with LangChain.

## 9. Decision Checkpoint

Per `/task-review` Phase 5, the options were:

- **[A]ccept** — Approve findings as-is. Archive review. The pin recommendation stays in this report and ADR-ARCH-032 (Proposed) for reference; no implementation task created. Suitable if you want to defer the rebaseline indefinitely or roll it into a broader portfolio refresh.

- **[I]mplement** *(SELECTED 2026-04-29)* — Create the FEAT-F0EP feature folder ([`tasks/backlog/langchain-1x-pin-alignment/`](../../tasks/backlog/langchain-1x-pin-alignment/)) with [`TASK-LCP-001`](../../tasks/backlog/langchain-1x-pin-alignment/TASK-LCP-001-pyproject-pin-updates.md) as the primary deliverable. Three orthogonal demo-blocker fixes filed as flat sibling tasks: [TASK-FIX-F0E6](../../tasks/backlog/TASK-FIX-F0E6-nats-core-import-namespace.md) (nats-core import — **demo-blocker**), [TASK-FIX-F0E7](../../tasks/backlog/TASK-FIX-F0E7-pytest-asyncio-and-dev-deps-install.md) (pytest-asyncio + dev-deps), [TASK-FIX-F0E8](../../tasks/backlog/TASK-FIX-F0E8-forge-build-stale-module-ref.md) (forge.build stale ref). Run `/task-work TASK-LCP-001` to apply the pin diff, smoke-test on Py3.14, flip ADR-ARCH-032 to **Accepted**, and commit.

- **[R]evise** — Request deeper analysis. Plausible follow-ups: actually run a Phase B (apply pins to a temp pyproject and rerun pytest to confirm no regression — note this would still hit the §5.1 nats_core blocker, so it would need the nats_core fix first); or expand to look at agentic-dataset-factory / specialist-agent with the same recipe (study-tutor was already done in parallel as [TASK-REV-57BD / FEAT-7BDP](../../../study-tutor/tasks/backlog/py314-langchain-pin-alignment/) — this review's structural template).

- **[C]ancel** — Discard review, return task to backlog.

**Outcome**: [I]mplement selected. FEAT-F0EP feature folder + 4 task files created (TASK-LCP-001 in the folder; TASK-FIX-F0E6/F0E7/F0E8 as flat deferred-promoted siblings). Task structure mirrors [study-tutor's parallel rollout](../../../study-tutor/tasks/backlog/py314-langchain-pin-alignment/) (TASK-REV-57BD / FEAT-7BDP) — same recipe, calibrated for forge's specifics.

## 10. References

- **This review**: `/task-review TASK-REV-F0E4 --mode=diagnostic` session, 2026-04-29
- **Cross-repo precedent**: [Jarvis ADR-ARCH-010 Revision 2](../../../jarvis/docs/architecture/decisions/ADR-ARCH-010-python-312-and-deepagents-pin.md)
- **Cross-repo upstream diagnosis**: [GuardKit TASK-REV-FA04 report](../../../guardkit/.claude/reviews/TASK-REV-FA04-report.md)
- **Cross-repo policy**: [GuardKit portfolio-python-pinning guide](../../../guardkit/docs/guides/portfolio-python-pinning.md)
- **Forge ADR draft (Proposed)**: [`docs/architecture/decisions/ADR-ARCH-032-langchain-1x-portfolio-alignment.md`](../../docs/architecture/decisions/ADR-ARCH-032-langchain-1x-portfolio-alignment.md)
- **Empirical pytest log**: [`docs/history/portfolio-py314-rebaseline-pytest.txt`](../../docs/history/portfolio-py314-rebaseline-pytest.txt)
- **Forge pyproject (pre-rebaseline)**: [`pyproject.toml`](../../pyproject.toml) at commit `9bcc939`
