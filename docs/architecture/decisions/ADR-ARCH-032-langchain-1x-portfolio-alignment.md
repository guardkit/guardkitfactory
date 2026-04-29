# ADR-ARCH-032: LangChain 1.x portfolio alignment

**Status:** Accepted (Accepted on 2026-04-29 via TASK-LCP-001 — pin diff applied to `pyproject.toml` and resolved-versions table re-verified on Python 3.14.2 in `.venv-verify`; matches the verified-versions table below byte-for-byte.)
**Date:** 2026-04-29
**Deciders:** Rich + `/task-review TASK-REV-F0E4` session
**Supersedes:** none
**Cross-repo precedent:** [Jarvis ADR-ARCH-010 Revision 2](../../../../jarvis/docs/architecture/decisions/ADR-ARCH-010-python-312-and-deepagents-pin.md) (the empirically-validated upstream pin set this ADR aligns with)

## Context

GuardKit AutoBuild stalled for 33 minutes on Jarvis FEAT-J004-702C run 1 (2026-04-27) when a stale `requires-python = ">=3.12,<3.13"` pin excluded the user's Mac default Python 3.14, compounded by the LangChain ecosystem's 0.x → 1.x version skew when the resolver was given open-floor `>=0.x` pins. The full diagnosis is at [TASK-REV-FA04 in GuardKit](../../../../guardkit/.claude/reviews/TASK-REV-FA04-report.md). The Jarvis-side remediation (ADR-ARCH-010 Revision 2, 2026-04-27) pinned the LangChain ecosystem to coherent 1.x with `<2` caps and dropped the closed Python upper bound; an empirical run on Python 3.14 with that pin set cleared the trapdoor (25 failures → 7, of which 0 were LangChain runtime).

The portfolio-rollout review for forge ([TASK-REV-F0E4](../../../tasks/backlog/TASK-REV-F0E4-portfolio-py314-langchain-1x-alignment.md), 2026-04-28) asked: does forge today carry the same latent risk? The empirical answer (Python 3.14, 2026-04-29):

- ✅ `requires-python = ">=3.11"` — already correct (matches Jarvis rev2 and the GuardKit portfolio-pinning policy at [`guardkit/docs/guides/portfolio-python-pinning.md`](../../../../guardkit/docs/guides/portfolio-python-pinning.md)); no change needed.
- ✅ The resolver, given forge's current open-floor pins on a fresh Py3.14 venv, **converges on the exact Jarvis-verified 1.x set**: `langchain-core 1.3.2`, `langchain 1.2.15`, `langgraph 1.1.10`, `langchain-anthropic 1.4.2`, `langchain-openai 1.2.1`, `langchain-google-genai 4.2.2`.
- ✅ All langchain runtime imports succeed (`langchain.agents.middleware`, `langgraph.graph`, `langgraph.prebuilt`, plus the `block_translators.langchain_v0` compat path that was the FA04 trapdoor signature).
- ❌ But the trapdoor is **latent**, not absent. Forge declares:
  - `langgraph>=0.2` (no `<2` cap; resolver is free to pick 0.x on a future fresh install or cache state)
  - `langchain-anthropic>=0.2` (same shape)
  - `langchain-openai>=0.2` (same shape)
  - `langchain-google-genai>=2.0` (pre-1.x floor; same shape)
  - `langchain-core>=1.2.18` (1.x floor but no upper cap — would happily resolve to 2.x on release day)
  - `langchain>=1.2.11` (same)
  - `langchain-community>=0.3` (forge-specific dep; resolver picks 0.4.1; package hasn't moved to 1.x yet)

A future fresh install — on a developer's clean machine for the DDD South West demo, in CI with a cleared cache, or after `uv sync --upgrade` — could resolve to a mixed 0.x/1.x set and surface `ModuleNotFoundError: No module named 'langchain_core.messages.block_translators.langchain_v0'` exactly as Jarvis hit on FEAT-J004-702C run 1. The hardening is therefore **prophylactic**, not reactive: the failure mode is one resolver decision away.

## Decision

Pin the LangChain ecosystem to coherent 1.x with `<2` caps, matching Jarvis ADR-ARCH-010 rev2 verbatim where applicable. Concrete diff against `pyproject.toml` (commit `9bcc939`, current at review time):

```diff
 dependencies = [
     "deepagents>=0.5.3,<0.6",
-    "langchain>=1.2.11",
-    "langchain-core>=1.2.18",
-    "langgraph>=0.2",
-    "langchain-community>=0.3",
-    "langchain-anthropic>=0.2",
+    "langchain>=1.2,<2",
+    "langchain-core>=1.3,<2",
+    "langgraph>=1.1,<2",
+    "langchain-community>=0.4,<0.5",
+    "langchain-anthropic>=1.4,<2",
     "nats-core>=0.2.0,<0.3",
     "python-dotenv>=1.0",
     "pyyaml>=6.0",
 ]

 [project.optional-dependencies]
 providers = [
-    "langchain-openai>=0.2",
-    "langchain-google-genai>=2.0",
+    "langchain-openai>=1.2,<2",
+    "langchain-google-genai>=4.2,<5",
 ]
```

### Verified-versions table (Python 3.14.2, fresh venv, 2026-04-29)

| Package | Resolved here | Jarvis verified (rev2) | Proposed pin |
|---|---|---|---|
| langchain-core | 1.3.2 | 1.3.2 | `>=1.3,<2` |
| langchain | 1.2.15 | 1.2.15 | `>=1.2,<2` |
| langgraph | 1.1.10 | 1.1.10 | `>=1.1,<2` |
| langchain-anthropic | 1.4.2 | 1.4.1 | `>=1.4,<2` |
| langchain-openai | 1.2.1 | 1.2.1 | `>=1.2,<2` |
| langchain-google-genai | 4.2.2 | 4.2.2 | `>=4.2,<5` |
| langchain-community | 0.4.1 | n/a (Jarvis doesn't have it) | `>=0.4,<0.5` |
| deepagents | 0.5.4 | 0.5.3+ | `>=0.5.3,<0.6` (unchanged) |
| Python | 3.14.2 | 3.14 | `>=3.11` (unchanged) |

The first six rows are byte-for-byte alignment with the empirically-validated Jarvis pin set. `langchain-community` and `deepagents` are forge-specific or already-correct; rationale below.

### Rationale per change

1. **`langgraph>=0.2` → `>=1.1,<2`** *(highest-risk change)*. The 0.x floor is the precise mismatch pattern that broke Jarvis. With the floor at `0.2`, the resolver is free to pick 0.x langgraph alongside 1.x langchain-core on any fresh resolve where 0.x happens to be cheapest in the resolution graph — that's the FA04 trapdoor. Pinning to `>=1.1,<2` matches Jarvis verbatim and matches the version the resolver picks today on its own.

2. **`langchain-anthropic>=0.2` → `>=1.4,<2`** *(high-risk, secondary location decision)*. Same 0.x/1.x mismatch shape. Note this is currently in `dependencies`, not `[project.optional-dependencies].providers`. Jarvis rev2 puts `langchain-anthropic` in providers under the LCOI principle (TASK-REV-LES1 §3 — every LangChain integration the template can be configured to use must be declarable in one install command). **This ADR pins the version but does not move the dep**; relocating it to `providers` is a behavior change (base install would no longer pull `langchain-anthropic`) and is deferred to a separate task. Today's `pyproject.toml` lists `langchain-anthropic` as a hard dependency, and forge's runtime apparently relies on it being present without the `[providers]` extra.

3. **`langchain-openai>=0.2` → `>=1.2,<2`** *(high-risk)*. Same 0.x/1.x mismatch shape. Already in `providers` — only the version pin tightens.

4. **`langchain-google-genai>=2.0` → `>=4.2,<5`** *(high-risk, larger major-version jump)*. The 2.0 floor predates the major bumps to 3.x and 4.x; the resolver currently picks 4.2.2. The `<5` cap protects against an eventual 5.x release. Same major-cap pattern, different major number than the rest of the ecosystem.

5. **`langchain-core>=1.2.18` → `>=1.3,<2`** *(low-risk, tightens floor + adds cap)*. The current floor of `1.2.18` is below Jarvis's verified `1.3.x`; the resolver picks `1.3.2`. Tightening the floor to `1.3` aligns with Jarvis and prevents the resolver from selecting a `1.2.x` patch that may lack APIs the rest of the ecosystem expects. The `<2` cap is the structural protection against an eventual 2.x release.

6. **`langchain>=1.2.11` → `>=1.2,<2`** *(low-risk, just adds cap)*. Floor essentially unchanged (`1.2.11` → `1.2`); the `<2` cap is added for the same structural reason as `langchain-core`.

7. **`langchain-community>=0.3` → `>=0.4,<0.5`** *(forge-specific; not in Jarvis)*. Forge depends on `langchain-community` (Jarvis doesn't). The resolver picks `0.4.1` against the current floor. The package has historically had API drift between 0.x minors, and unlike the other LangChain packages it has **not yet moved to 1.x**. The recommendation here uses a *minor* cap rather than a major cap, on the principle that 0.x → 0.5 is a more meaningful API boundary than 0.4.0 → 0.4.1 in this package's history. Re-evaluate when `langchain-community 1.0` ships (track via the same DeepAgents 0.6 forward-review trigger as Jarvis ADR-ARCH-010 forward-review).

### Why same-major (`<2`) caps but no Python upper bound

This ADR continues the asymmetry codified by Jarvis ADR-ARCH-010 rev2 and the [portfolio-pinning guide](../../../../guardkit/docs/guides/portfolio-python-pinning.md): same-major caps on fast-moving LangChain packages are calibrated to a *known* breaking-change pattern (0.x → 1.x compat removal), while closed Python upper bounds decay silently into resolver traps as new minors release. The 2025-10 `<3.13` Python cap that motivated the FA04 incident is the canonical example of the latter; the LangChain `<2` caps proposed here are protection against the former.

### Out of scope (flagged for separate follow-up tasks, not part of this ADR)

The following were surfaced by the empirical run but are **not addressed by the pin diff above**:

- **`nats-core 0.2.0` PyPI wheel is broken**: installs under `nats/` (specifically `nats/client/...`) instead of `nats_core/`, but forge code imports `from nats_core.events import ...`, `from nats_core.envelope import ...`, `from nats_core.manifest import ...`. Causes 55 test-collection errors on a fresh Py3.14 install. Pre-existing (would happen on any Python version); orthogonal to LangChain pinning. Likely needs either (a) a newer `nats-core` PyPI release that fixes the package layout, (b) a `[tool.uv.sources]` entry pointing at the sibling repo (the pattern Jarvis uses), or (c) a code-side rename. Filing separately.
- **`[dependency-groups].dev` is missing `pytest-asyncio`**: forge has 100+ tests marked `@pytest.mark.asyncio` but the dev group only declares `pytest` and `pytest-bdd`. Result: 162 `Failed: async def functions are not natively supported` failures in the runnable subset. Pre-existing test-infra fragility; orthogonal to LangChain pinning. Filing separately.
- **`uv pip install -e ".[dev,providers]"` doesn't pick up `[dependency-groups].dev`**: PEP 735 `[dependency-groups]` is read by `uv sync --group dev`, not by `uv pip install -e ".[<extra>]"`. The TASK-REV-F0E4 task script suggested the latter; it works for `providers` (a real `[project.optional-dependencies]` extra) but silently no-ops for `dev`. The portfolio-pinning workflow guide should be updated, OR forge should mirror the dev deps into `[project.optional-dependencies].dev` for `pip install -e ".[dev]"` compatibility. Cross-repo concern; recommend raising with the GuardKit portfolio guide rather than fixing forge-side.
- **`tests/unit/test_git_operations.py` references `forge.build`** which does not exist. Pre-existing stale test; surfaces as 1 collection error. Filing separately.

These are recorded here so the rebaseline-task that implements this ADR doesn't accidentally inherit them as in-scope.

### CI / lockfile consequences

Forge currently has **no `uv.lock` checked in** (the TASK-REV-F0E4 task assumed there was one — the assumption is stale, see report §5.2). Adding a `uv.lock` is an orthogonal decision; if added in the future, it should be (re)generated against the pin set in this ADR and not against the pre-rebaseline pins.

### CLAUDE.md / portfolio-guide reference

Recommend adding a one-line reference to [`guardkit/docs/guides/portfolio-python-pinning.md`](../../../../guardkit/docs/guides/portfolio-python-pinning.md) and to this ADR in `.claude/CLAUDE.md` (the existing CLAUDE.md already explains the LCOI principle for `[providers]`; this addition documents the same-major LangChain caps with a forward pointer to the policy). The exact wording is left to the implementation task.

## Alternatives considered

1. **Tighten only `langgraph` (the highest-risk dep) and leave the rest open** *(rejected)*. This addresses the most likely trapdoor instance but leaves the same-shape risk on every other LangChain package. Half-measures here have a much worse risk/reward than aligning with the Jarvis-verified set wholesale, given that the verified set is empirically known to work.
2. **Match Jarvis verbatim, including moving `langchain-anthropic` to `providers`** *(rejected for this ADR; deferred to a separate task)*. Relocating `langchain-anthropic` between `dependencies` and `providers` is a behavior change at install time. Doing it as part of this ADR would conflate the version-pin hardening (low risk, structural protection) with a runtime-deps reshape (medium risk, requires verification that the base install still works). Splitting the two keeps the rebaseline task small and reversible.
3. **No upper caps; rely on the resolver's preference for newer same-major versions** *(rejected)*. This is the current state, and it is the configuration the FA04 review proved is broken. A resolver with no caps will pick a 2.x package on release day, with no warning to the team that the next major shipped — at which point the same trapdoor pattern (paired-major mismatch) repeats one major up.

## Consequences

- **Demo-critical hardening for DDD South West**: the trapdoor that broke Jarvis FEAT-J004-702C run 1 (33-min stall) cannot recur in forge with these pins, regardless of resolver state or fresh-install timing.
- **Forward review**: the `<2` caps on `langchain-core`, `langchain`, `langgraph`, `langchain-anthropic`, `langchain-openai` will need lifting when those packages ship 2.x. The forward-review trigger should be the next DeepAgents major (0.6, per Jarvis ADR-ARCH-010 rev2's "Forward review" §) — bundle the 2.x consideration into the same review window.
- **`langchain-community<0.5` cap** is on a different cadence; lift independently when `langchain-community 0.5` (or 1.0) ships, after a compatibility check.
- **No code changes required**. The resolver already produces the proposed versions today; pinning them just locks in the result.
- **No `uv.lock` regeneration needed** because no lockfile is checked in.

## References

- [Jarvis ADR-ARCH-010 Revision 2](../../../../jarvis/docs/architecture/decisions/ADR-ARCH-010-python-312-and-deepagents-pin.md) — upstream precedent, empirically validated on Python 3.14
- [GuardKit TASK-REV-FA04 report](../../../../guardkit/.claude/reviews/TASK-REV-FA04-report.md) — the trapdoor diagnosis (closed)
- [GuardKit portfolio-python-pinning guide](../../../../guardkit/docs/guides/portfolio-python-pinning.md) — the canonical policy
- [TASK-REV-F0E4 review report](../../../.claude/reviews/TASK-REV-F0E4-report.md) — the empirical evidence behind this ADR
- [Forge pytest log on Py3.14](../../history/portfolio-py314-rebaseline-pytest.txt) — full test-suite output from the empirical run (tracked as `.txt` because `*.log` is gitignored)
