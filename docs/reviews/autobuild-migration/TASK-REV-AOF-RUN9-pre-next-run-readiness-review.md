# Review Report: TASK-REV-AOF-RUN9 — FEAT-AOF run-9 pre-next-run readiness

- **Mode**: decision (go/no-go) · **Depth**: standard · **Decision required**: yes
- **Reviewer**: `/task-review` (main agent), evidence read first-hand
- **Date**: 2026-06-07
- **Sources** (all read directly, not summarised second-hand):
  - Run log: `guardkit/docs/reviews/autobuild-migration/autobuild-FEAT-AOF-run-9.md` (524 lines, raw stdout)
  - Fix under assessment: `guardkitfactory/tasks/completed/TASK-FIX-COACHBUDG01-LG/…` (now `completed`; AC-006 verified live 2026-06-07 — see §6)
  - Harness: `src/guardkitfactory/harness/langgraph_harness.py:249-396` (`invoke`)
  - Commits on branch `fix/coachbudg01-lg-responses-api-reasoning-api`: `44634ea`, `e8350bd` (both landed)

---

## Executive summary / Verdict

**Is landing `COACHBUDG01-LG` sufficient to make the next run pass? → No.**
It is **necessary but not sufficient.**

**Go/no-go → CONDITIONAL GO.** Run the next FEAT-AOF validation, but **not on
`COACHBUDG01-LG` alone** and **not on the existing 3000s budget**. Two low-effort
items must clear first; everything else the seed hypotheses flagged (R2/R3/R5) is
a genuine *latent follow-up*, not a pre-run blocker.

The two seeding analyses disagreed; this review resolves it:
- The **"sufficient"** camp is wrong — the fix is verified only against hermetic
  fixtures *with `langchain-openai` absent from the dev venv*, the turn-1-accept
  outcome is not reliable, and a 2-turn run does not fit 3000s.
- The **"lots more needed"** camp overstates it — the actual pre-run set is just
  **two cheap items** (a live probe + a budget bump), both done before launch.

| Pre-run item | Blocker? | Effort | Owning repo |
|---|---|---|---|
| **R4** — AC-006 live reasoning probe vs gemma4-coach | ✅ DONE (2026-06-07, §6) | low (1 Coach call) | guardkitfactory |
| **R1** — raise `task_timeout` to survive ≥2 turns | **BLOCKER (insurance)** | low (config) | guardkit |
| **N (new)** — Coach independent-test interpreter mismatch | investigate | low | guardkit |
| R2 — re-examine SPECHANG 600s cap | latent follow-up | — | guardkit |
| R3 — async-generator `aclose` leak (CTOUT01 surface) | latent follow-up | low | cross-repo |
| R5 — FalkorDB on/off + dotnet fixture | nice-to-have | low | ops |

---

## 1. Verified timeline (first-hand — confirms the task's reconstruction exactly)

The feature `task_timeout=3000s` began at task start **21:24:30.211Z** (log L76)
and fired at **22:14:30.277Z** (L470). 21:24:30 + 3000s = 22:14:30 — *exact*.
The "59-minute Coach stall" (anomaly K) is correctly **discarded**: the timeout
counts from task start, not from any single phase.

| Phase | Window | Duration | Outcome |
|---|---|---|---|
| Turn 1 — Player + test-orch + code-reviewer | 21:24:30 → 21:42:02 | ~1052s | Player 298s (1 created/2 modified, L164); test-orch ~240s **completed**; code-reviewer ~480s **completed** |
| Turn 1 — Coach Validation | 21:42:02 → 21:57:48 | ~946s | 216.7s independent tests + ~729s Coach model → **25211 chars / 0 reasoning_content → no fenced JSON** (L339) → COACHSF01 synthetic feedback → forced retry |
| Turn 2 — Player + test-orch | 21:57:48 → 22:13:09 | ~921s | Player **churned 45 files** (L425); test-orch **hung and hit the 600s cap, `SDKTimeoutError`** (L456) |
| Turn 2 — Coach Validation | 22:13:09 → 22:14:30 | ~81s | **Feature 3000s timeout fired** mid-invocation (L470) → CancelledError → `Extracted partial data from 0 events` (L476) → async-gen `aclose` leak (L519) |
| **Total** | 21:24:30 → 22:14:30 | **3000s** | IA03 cancelled; wave 1 failed; `stop_on_failure` halted the feature |

**Refinement the task under-counted:** turn 1 ran **three** Player-side specialists
(Player + test-orchestrator + code-reviewer), not just one. Per-turn substrate
cost is therefore even more front-loaded than "~900-1050s/phase" implies.

---

## 2. Adjudicating the central conditional — *will the next run accept on turn 1?*

This is the hinge. **The honest answer is: we cannot establish that pre-run, and
three independent signals push *against* a reliable turn-1 accept.**

1. **AC-006 is unverified (the dominant risk).** `COACHBUDG01-LG` is `completed`
   but AC-006 is unticked (`ac006_status: pending-hardware`). The fix was written
   against `langchain-core 1.4.0` message shapes because **`langchain-openai` is
   absent from the dev venv** — the very client that produces the live
   `/v1/responses` reasoning shape on the DGX was never observed. The task's own
   implementation notes warn "version-dependence is real… probe the actual
   installed version first." That probe did not happen. If the live shape matches
   none of the three handled branches, `extract_last_ai_reasoning` returns `""`
   again → `reasoning_text=""` → non-verdict → **run-9 reproduces exactly.**

2. **The Coach's independent tests "failed" both turns** (L276 `failed in 216.7s`,
   L473 `failed in 188.0s`). If real, a *working* Coach (post-B) would **reject**
   turn 1 → forces turn 2. The task classified this benign (anomaly F, "duration
   label") — I am **not convinced** (see Finding N): the quality-gate
   `ALL_PASSED=True` at L254 is a *separate, earlier* check from player-reported
   results; the L276 line is the independent SDK execution result.

3. **Player turn-1 output was small and plausible** (1 created + 2 modified for a
   complexity-3 fix) — this is the *one* signal *for* a turn-1 accept. But it is
   outweighed: a clean diff that fails the Coach's independent tests still gets
   rejected.

**Conclusion:** turn-1 accept is *possible* but not *reliable*. Betting the run on
it (3000s budget, no probe) risks a third ~50-minute null result. The
expected-value play is to (a) de-risk B with a cheap probe and (b) make the run
survive a legitimate turn 2.

---

## 3. Budget sufficiency — 3000s does not cover a 2-turn run

Per-phase costs measured from the log:

| Scenario | Wall-clock | Fits 3000s? | Fits 4800s? |
|---|---|---|---|
| Turn-1 **ACCEPT** (B fixed, clean) | ~1998s | ✅ (~1000s margin) | ✅ |
| Turn-1 **REJECT** → Turn-2 ACCEPT | ~3864s | ❌ **timeout** | ✅ (~936s margin) |

3000s only works on the turn-1-accept branch — exactly the branch we just showed
is not reliable. **The counter-argument ("more time just lets a retry storm run
longer") does not apply here**: that is only true when B is *unfixed*; with B
fixed, turn 1 yields a real verdict, so a turn 2 is genuine revision work, not a
synthetic-feedback storm. Extra budget therefore buys real coverage.

**Recommendation:** raise FEAT-AOF `task_timeout` to **≥4800s** (80 min), or pass
`--timeout-multiplier ≈ 1.6`. Note this also relieves the per-invocation
`budget_cap` squeeze (turn-2 Player was already throttled to 1001s at L353).

---

## 4. Anomaly findings (only the load-bearing ones; full inventory in the task)

**A — feature timeout (blocker, the proximate cause).** Real blocker, but it is a
*budget* symptom, not an independent defect → addressed by R1. With B fixed +
budget raised, a 2-turn run completes inside budget.

**B — Coach non-verdict, 0 reasoning_content (the headline).** Code fix landed
(`44634ea`/`e8350bd`); hermetic tests green (111 passed). **But live-unverified**
→ this is the whole of R4. *This is the single highest-leverage pre-run item.*

**E — test-orchestrator hung to the 600s cap (turn 2).** Confirmed a genuine
**hang**, not a slow test surface: **0 `httpx` model calls** across the 90s→570s
window (lines 439-456), versus continuous model calls in turn-1's ~240s run. This
is a SPECHANG-pattern recurrence that the 600s cap *bounded but did not eliminate*.
It wasted ~360s but was **not** the proximate timeout cause (the Coach still needed
~946s and only had 81s). **Moot if turn-1 accepts; latent otherwise → R2, follow-up.**

**D — async-generator `aclose` leak (confirmed in code).** `invoke` is an async
generator (`yield` at `langgraph_harness.py:385/387/392`). CTOUT01 wraps `ainvoke`
in a task so `cancel()` propagates (L327-363) — but there is **no `GeneratorExit`
/ `try-finally` around the yields**, so a consumer cancelled mid-iteration abandons
the generator without `await gen.aclose()` → the exact L519 warning. Fires **only**
on the cancel/timeout path, **after** the run already failed; the SDK subprocess is
already terminated by CTOUT01 (L475); leaked athrow tasks die with the process at
shutdown. **Cosmetic, no cross-run contamination → R3, follow-up.**

**F — "independent tests failed" label.** Downgraded by the task to benign. See
Finding N — I think it is partly masking a real interpreter mismatch and deserves a
look, but it is not a hard blocker.

**G / H / I / J / L / M** — agree with the task: benign / fixture debt / observability
gaps. None pre-run blocking. (I = the Responses-API routing — confirmed it is the
*deepagents default*, which is *why* B existed.)

### Finding N (new — not in the seeded R1-R5) — Coach independent-test interpreter mismatch

The Coach ran independent tests under the **wrong interpreter**: L255/L461 show
`which pytest=/…/Python.framework/Versions/3.14/bin/pytest` (which emits the
"Pydantic V1 not compatible with Python 3.14" warning at L116), **despite** L66-67
having set "Coach pytest interpreter … from bootstrap venv: `.venv/bin/python`".
If the Coach validates against a 3.14 framework pytest instead of the worktree venv,
its independent tests can **fail spuriously** — which, once B is fixed and the Coach
can emit verdicts, would produce **spurious turn-1 rejects on correct Player work**,
defeating the turn-1-accept hope *independently of B*.

Confidence: **medium** — inferred from env log lines; the Coach's pytest stdout is
not in this log. This is potentially the **highest-leverage hidden risk** to the
"pass the next run" goal and is worth a cheap confirmation. Owning repo: **guardkit**
(`coach_validator`). Candidate R6.

---

## 5. Required deliverable

### 5.1 Go/no-go verdict
**CONDITIONAL GO.** `COACHBUDG01-LG` is necessary and landed, but **not sufficient**.
Launch the next run only after the AC-006 probe (R4) passes and the budget is raised
(R1). Turn-1-accept reasoning made explicit in §2: it is *possible but unreliable*
(AC-006 unverified + Coach independent-test failures + interpreter mismatch all push
against it), so the run must be configured to survive a legitimate turn 2.

### 5.2 Prioritized pre-run checklist

| # | Item | Blocker? | Repo | One-line spec (if implemented) |
|---|---|---|---|---|
| **R4** | AC-006 live reasoning probe | ✅ DONE (2026-06-07) | guardkitfactory | Replayed via `TASK-FIX-AC006SMOKE-LG` on GB10 DGX. Probe initially **failed** AC-2 (live shape unhandled — `reasoning_text=0`); the captured `block["content"] = [{"type": "reasoning_text", "text": ...}]` (and its langchain-core-normalised `block["extras"]["content"]`) were absent from `_plaintext_from_reasoning_block`'s precedence list. After extending the extractor + adding two hermetic pins, re-probe → **PASS**: `reasoning_text=1055` chars, parser recovers `decision="approve"`, COACHSF01 silent. Suite: 116 passed, 8 skipped, 2 deselected. See §6 + `docs/state/TASK-FIX-AC006SMOKE-LG/`. |
| **R1** | Raise feature `task_timeout` | **BLOCKER (insurance)** | guardkit | Set FEAT-AOF `task_timeout` ≥ 4800s (or `--timeout-multiplier 1.6`) so a turn-1-reject → turn-2-accept run (~3864s) fits with ~900s margin. |
| **N/R6** | Coach independent-test interpreter | investigate (pre-run) | guardkit | Confirm `coach_validator` runs independent tests under the worktree `.venv` interpreter, not the 3.14 framework pytest; if mismatched, fix interpreter resolution to prevent spurious turn-1 rejects. |
| R2 | SPECHANG 600s cap vs real cost | latent follow-up | guardkit | test-orchestrator hung with 0 model calls for ~480s; cap bounded but didn't fix. Add hang detection (no-model-activity watchdog) distinct from the duration cap. Gated behind reaching a churn/hang turn. |
| R3 | async-gen `aclose` leak | latent follow-up | cross-repo | Consumer (`guardkit agent_invoker`) wrap iteration in `async with aclosing(harness.invoke(...))`; and/or `LangGraphHarness.invoke` handle `GeneratorExit` to null `self._ainvoke_task`. Cosmetic; cancel-path only. |
| R5 | FalkorDB + dotnet fixture | nice-to-have | ops | For a clean validation run set Graphiti `enabled: false` (or bring FalkorDB up); dotnet MAUI fixture failure (12/13 bootstrap) is **confirmed benign** for the Python-only FEAT-AOF tasks. |

### 5.3 Recommended run configuration
- `task_timeout`: **≥4800s** (R1).
- **AC-006 probe FIRST** (R4) — gate; the subsequent full run then doubles as the
  end-to-end AC-006/AC-009 validation once the probe confirms the live shape.
- Graphiti: **`enabled: false`** for this run (removes the FalkorDB variable; H).
- Keep `--coach-model gemma4:26b --reasoning auto`, `stop_on_failure=True`.
- Optional but recommended: resolve Finding N before the run, else a correct
  turn-1 may still be rejected on spurious test failures.

---

## Out of scope (per task)
Implementing R1-R5/N (the [I]mplement path spins those up); re-litigating
Responses-API vs chat-completions (settled — Approach A; revisit only if R4 fails);
GD02/TP05 (never executed — re-enter scope once IA03 passes).

---

## 6. AC-006 live-probe outcome (added 2026-06-07 by TASK-FIX-AC006SMOKE-LG)

### 6.1 Verdict
**R4 closes ✅**. AC-006 PASS after one extractor extension. Run-9's "0 chars
reasoning_content" headline is now **provably the unhandled-shape symptom**
this review predicted (§2.1), not a substrate-side absence.

### 6.2 What the probe found
First-probe run on the GB10 DGX (`gemma4-coach` via `llama-swap` at
`localhost:9000/v1`, `langchain-openai 1.2.2`, `use_responses_api=True`,
`--reasoning auto`) captured one `/v1/responses` ``AIMessage``. The
reasoning block on `.content` had this shape:

```python
{
  "type": "reasoning",
  "id": "rs_...",
  "summary": [],                # empty
  "encrypted_content": "",      # empty
  "status": "completed",
  "content": [                  # ← the actual plaintext (3288 chars)
    {"type": "reasoning_text", "text": "Step 1: verify the delta…"}
  ],
}
```

`block["content"]` (the raw provider shape) and `block["extras"]["content"]`
(the langchain-core normalised view via `msg.content_blocks`) **were not in
`_plaintext_from_reasoning_block`'s precedence list** — the extractor only
checked `reasoning`, `text`, and `summary`. First-probe AC-2 → `reasoning_text=0`.
This is the exact "if the probe fails" branch the task anticipated.

### 6.3 What was changed
`src/guardkitfactory/harness/extractors.py`:
new helper `_text_from_reasoning_content_list` + two new precedence steps
in `_plaintext_from_reasoning_block` (raw `block["content"]`, then
normalised `block["extras"]["content"]`). `tests/harness/test_langgraph_harness.py`:
two hermetic pins — `test_reasoning_content_list_surfaces_on_reasoning_text`
(raw) and `test_reasoning_extras_content_list_surfaces_on_reasoning_text`
(normalised) — so a future `langchain-openai` bump that relocates the
plaintext fails loudly.

### 6.4 Re-probe outcome (post-fix)
| AC | Assertion | Result |
|---|---|---|
| AC-1 | live AIMessage shape captured and recorded | ✅ `docs/state/TASK-FIX-AC006SMOKE-LG/captured_aimessage.json` |
| AC-2 | `extract_last_ai_reasoning` returns > 0 chars | ✅ **1055 chars** |
| AC-3 | parser recovers fenced JSON verdict, COACHSF01 silent | ✅ `decision="approve"`, no `CoachDecisionNotFoundError` |

Full suite: **116 passed, 8 skipped, 2 deselected** (was 111 before this
task — +5 over baseline = +2 from this task and +3 unrelated landings since
COACHBUDG01-LG completed earlier today). Ruff clean.

### 6.5 What this changes about §2 of this review
§2.1 (the dominant-risk claim) **resolves in our favour**: the live shape is
now handled. Turn-1 accept reliability still hinges on §2.2 / §2.3 +
Finding N — this probe does not retire those.

### 6.6 Pre-run checklist after R4 close
| # | Item | Status | Notes |
|---|---|---|---|
| **R4** | AC-006 live reasoning probe | ✅ done | This §6 |
| **R1** | Raise feature `task_timeout` to ≥4800s | unchanged | still BLOCKER (insurance) |
| **N/R6** | Coach independent-test interpreter | unchanged | still investigate pre-run |
| R2 / R3 / R5 | latent follow-ups | unchanged | — |

The CONDITIONAL GO verdict at §5.1 now depends only on R1 + Finding N.
