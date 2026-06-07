---
id: TASK-REV-AOF-RUN9
title: Review autobuild FEAT-AOF run-9 — is COACHBUDG01-LG sufficient to pass the next run, or what else is required first
task_type: review
review_mode: decision
review_depth: standard
status: review_complete
decision_required: true
created: 2026-06-07T11:00:00Z
updated: 2026-06-07T13:00:00Z
review_results:
  mode: decision
  verdict: conditional-go
  summary: "COACHBUDG01-LG is necessary but NOT sufficient. Conditional GO: launch the next run only after R4 (AC-006 live probe, guardkitfactory) and R1 (raise task_timeout to >=4800s, guardkit). R2/R3/R5 are latent follow-ups. New finding N: Coach independent-test interpreter mismatch (guardkit) may cause spurious turn-1 rejects."
  pre_run_blockers: [R4-ac006-live-probe, R1-task-timeout-4800s]
  pre_run_investigate: [N-coach-pytest-interpreter]
  latent_followups: [R2-spechang-cap, R3-aclose-leak, R5-falkordb-dotnet]
  report_path: docs/reviews/autobuild-migration/TASK-REV-AOF-RUN9-pre-next-run-readiness-review.md
  completed_at: 2026-06-07T13:00:00Z
  implementation_tasks:
    - TASK-FIX-AC006SMOKE-LG   # R4, guardkitfactory — tasks/backlog/autobuild-harness-migration/ (BLOCKER)
    - TASK-FIX-AOFBUDG         # R1, guardkit — raise task_timeout (BLOCKER)
    - TASK-FIX-COACHPYENV      # N,  guardkit — coach pytest interpreter mismatch
    - TASK-FIX-LGACLOSE        # R3, guardkit (cross-repo) — aclose leak
    - TASK-FIX-SPECHANG2       # R2, guardkit — hang watchdog
    - TASK-OPS-AOFENV          # R5, guardkit — FalkorDB/dotnet go/no-go
priority: high
complexity: 4
parent_task: TASK-HMIG-010   # guardkit, blocked — FEAT-AOF runs are its end-to-end LangGraph validation attempts
feature_id: FEAT-HMIG
parent_feature: autobuild-harness-migration
related_tasks:
  - TASK-FIX-COACHBUDG01-LG   # guardkitfactory, in_review — the fix whose sufficiency this review assesses
  - TASK-FIX-COACHBUDG01      # guardkit — orchestrator-side parser + budget parent
  - TASK-FIX-SPECHANG         # guardkit, completed — the 600s test-orchestrator cap implicated in anomaly E
  - TASK-FIX-CTOUT01          # guardkit, completed — cancellation path implicated in anomaly D
  - TASK-HMIG-013             # guardkit, backlog — gemma4:26b coach swap / live-smoke gate
analyses: docs/reviews/autobuild-migration/autobuild-FEAT-AOF-run-9.md   # in the guardkit repo
tags:
  - review
  - decision-point
  - autobuild
  - langgraph-migration
  - substrate-robustness
  - pre-run-readiness
decision: "Go/no-go for the next FEAT-AOF (TASK-HMIG-010) validation run after TASK-FIX-COACHBUDG01-LG lands: is the reasoning-extraction fix SUFFICIENT, or must a defined set of residual items (feature task_timeout budget, specialist 600s cap, async-generator aclose leak, AC-006 live smoke) be addressed first? Output a prioritized pre-run checklist with the owning repo for each item."
---

# Review: FEAT-AOF run-9 — pre-next-run readiness after TASK-FIX-COACHBUDG01-LG

> **This is a review/analysis task.** Execute with `/task-review TASK-REV-AOF-RUN9`,
> not `/task-work`. It must end in a **go/no-go decision** plus a prioritized,
> repo-attributed checklist of any work required before the next run.

## The decision to make

Run-9 of FEAT-AOF (the end-to-end validation feature for the blocked parent
`TASK-HMIG-010`) **failed**: 0/3 tasks completed, killed by a 50-minute
feature-level timeout on TASK-FIX-IA03. A fix for the headline symptom —
`TASK-FIX-COACHBUDG01-LG` (Responses-API reasoning extraction) — is now
`in_review` (code + hermetic tests complete; AC-006 live smoke pending).

**Central question:** *Is landing COACHBUDG01-LG sufficient to make the next run
pass, or is further work required first — and if so, exactly what, and in which
repo?*

The two independent analyses that seeded this task **disagreed** on the answer.
This review must resolve that disagreement with evidence and produce a single
recommendation.

## Source

- Run log + review: `guardkit/docs/reviews/autobuild-migration/autobuild-FEAT-AOF-run-9.md` (523 lines, raw stdout).
- Fix under assessment: [`TASK-FIX-COACHBUDG01-LG`](./TASK-FIX-COACHBUDG01-LG-responses-api-reasoning-extraction.md) (this repo, `in_review`).

## Verified run-9 timeline (corrected)

Reconstructed directly from the log timestamps (an automated pass misread this as
a "59-minute Coach stall" — that was wrong; the feature timeout counts from task
start). The 3000s feature `task_timeout` began at task start **21:24:30** and
fired at exactly **22:14:30** (= start + 3000s):

| Phase | Window | Duration | Outcome |
|---|---|---|---|
| Turn 1 — Player + test-orchestrator | 21:24:30 → 21:42:02 | **~1052s** | Player done; turn-1 specialist ran ~240s and **completed** |
| Turn 1 — Coach Validation | 21:42:02 → 21:57:48 | **~946s** | 216.7s SDK independent tests + Coach model emitted **25211 chars content / 0 chars reasoning_content → no fenced JSON verdict** → COACHSF01 synthetic feedback → forced retry |
| Turn 2 — Player + test-orchestrator | 21:57:48 → 22:13:09 | **~921s** | Player churned **45 files**; turn-2 specialist **hit the 600s cap and FAILED** (`SDKTimeoutError`, 0 results) |
| Turn 2 — Coach Validation | 22:13:09 → 22:14:30 | **~81s** | **Feature 3000s timeout fired** mid-invocation → CancelledError → `Extracted partial data from 0 events` → async-generator `aclose` leak |
| **Total** | 21:24:30 → 22:14:30 | **3000s** | TASK-FIX-IA03 cancelled; wave 1 failed; `stop_on_failure` halted the feature |

**Budget arithmetic that frames the decision:** Turn 1 alone consumed ~1998s
(66% of the 3000s budget) and ended in a **non-verdict** caused by the reasoning
bug. Per-turn substrate cost is large (~900-1050s/phase, incl. a fixed ~200s of
Coach SDK independent-test overhead per Coach turn).

## The central conditional (resolve this)

The reasoning fix is **necessary** (it stops turn-1's expensive Coach output from
being discarded as a non-verdict). Whether it is **sufficient** hinges on one
fork the review must adjudicate:

- **If, post-fix, the Turn-1 Coach ACCEPTS** → the run completes at ~1998s, well
  inside 3000s. COACHBUDG01-LG alone is sufficient. ✅
- **If the Turn-1 Coach legitimately REJECTS** (≥2 substantive turns needed) →
  Turn 2 (~921s Player+specialist + ~946s Coach ≈ 1867s) pushes the total to
  ~3865s > 3000s → **times out again**. The reasoning fix is then necessary but
  **not** sufficient, and a budget increase and/or per-invocation speedup is
  required too.

So the question "is more work needed?" reduces to: **will the next run accept on
turn 1?** That depends on Player output quality + Coach judgment + AC-006 holding
live — not on parsing alone. Note also a knock-on: the turn-2 **45-file churn**
and the resulting **600s specialist cap-failure (E)** were downstream of the
synthetic-feedback retry storm (B). Fixing B may therefore *also* prevent E — but
only on the turn-1-accept branch.

## Anomaly inventory (13 found; dedup verified against real tasks)

Severity: **blocker** = ended the run · **major** = degrades/latent blocker ·
**minor/benign** = noise. "Fixed by LG?" = does COACHBUDG01-LG address it.
Existing-task statuses below were file-verified.

| # | Anomaly | Sev | Fixed by LG? | Existing coverage (verified) |
|---|---|---|---|---|
| A | TASK-FIX-IA03 feature timeout (3000s) ended the run | blocker | **partial** (removes the wasted retry turn; doesn't shrink per-turn wall-clock) | `TASK-HMIG-010` (blocked) — the validation task itself |
| B | Coach non-verdict: 25211 chars content / **0 reasoning_content**, no fenced JSON | major | **yes** (the exact target + falsifier) | `TASK-FIX-COACHBUDG01-LG` (in_review) |
| E | test-orchestrator hit 600s cap, failed with 0 results (turn 2) | major | no (indirect only, via turn-1 accept) | `TASK-FIX-SPECHANG` (completed) — yet it still hung → **cap interaction to re-examine** |
| D | `aclose of LangGraphHarness.invoke never awaited` + `Task destroyed but pending` | major | no | `TASK-FIX-CTOUT01` (completed) — cancels ainvoke task but **doesn't close the generator** → CTOUT01 gap |
| K | "Coach turn-2 ran 59 min" | — | — | **misread — discard** (timeout counts from task start; see corrected timeline) |
| C | `Extracted partial data from 0 events` on cancel | major→symptom | no | downstream of A/timeout; disappears if run doesn't time out |
| F | Coach SDK independent tests 216.7s / 188.0s ("failed" = duration label; ALL_PASSED=True) | minor | no | fixed per-Coach-turn overhead; in-budget |
| G | dotnet bootstrap 12/13 (net8.0 MAUI workloads out of support) | minor | no | benign for Python-only FEAT-AOF; fixture debt |
| H | FalkorDB unreachable → Graphiti context disabled | minor | no | `TASK-FIX-FALK01` (completed, teardown race — different issue); needs a go/no-go decision |
| L | SDK `turns=None`, 1 assistant / 0 tool turns — Player time-spend opaque | minor | no | observability gap |
| I | All LLM calls route to `/v1/responses` (Responses API) | benign | **yes** (LG makes the harness Responses-API-correct) | intended deepagents default |
| J | Pydantic V1 deprecation on Python 3.14 | benign | no | portfolio dependency debt |
| M | Sub-second OpenAI client retries to `/responses` (succeeded) | benign | no | normal resilience |

## Areas the review must analyse

1. **Adjudicate the central conditional.** Using the verified per-turn timings,
   determine the realistic probability that the next run accepts on turn 1 once B
   is fixed. Consider: was the Turn-1 Player output actually *acceptable* (would a
   working Coach have accepted it), or was the task genuinely going to need
   revisions? Inspect what the Turn-1 Player produced (1 created + 2 modified)
   vs Turn-2's 45-file churn.
2. **Budget sufficiency.** Given ~900-1050s per phase on this substrate, is 3000s
   `task_timeout` viable for a 2-turn run? Quantify the margin. If insufficient,
   recommend a concrete value (or `--timeout-multiplier`) — but weigh the
   counter-argument that more time merely lets a retry-storm run longer (only
   true if B is *not* fixed; B *is* fixed here).
3. **Specialist 600s cap (E).** Why did turn-2 test-orchestrator hang to 600s
   when turn-1 finished in ~240s? Is it the 45-file churn surface, or a genuine
   hang on the `/v1/responses` substrate? Does `TASK-FIX-SPECHANG`'s cap need
   revisiting, or does fixing B make E moot? Decide whether E is a pre-run
   blocker or a latent follow-up.
4. **Async-generator leak (D).** Confirm the leak is in the consumer not awaiting
   `gen.aclose()` (guardkit `agent_invoker`) and/or the absence of `GeneratorExit`
   handling in [`LangGraphHarness.invoke`](../../src/guardkitfactory/harness/langgraph_harness.py#L249-L396).
   It only fires on the timeout-cancel path — decide: pre-run blocker, or a
   CTOUT01-surface follow-up task? (It did not itself end run-9.)
5. **AC-006 live smoke.** COACHBUDG01-LG is verified only against hermetic
   fixtures (langchain-openai absent from the dev venv). Confirm the real
   gemma4:26b `/v1/responses` reasoning shape matches a handled branch — if the
   live shape differs, B regresses and reasoning_text is empty again. Is the
   next run itself the AC-006 smoke, or should a smaller probe run first?
6. **Environment go/no-go (H, G).** Decide whether to bring FalkorDB up or set
   `enabled: false` to silence warnings; confirm the dotnet MAUI fixture failure
   is benign for the Python orchestrator tasks.

## Candidate residual work (proposals for the review to confirm/reject)

These are seeded hypotheses, **not** decisions — the review owns the final set.

- **R1 (likely required, guardkit):** Raise feature `task_timeout` (or
  `--timeout-multiplier`) **only if** the review finds a turn-1 accept is *not*
  reliable. Load-bearing iff the run needs ≥2 turns.
- **R2 (guardkit):** Re-examine the `TASK-FIX-SPECHANG` 600s test-orchestrator
  cap vs the substrate's real test-execution cost (anomaly E).
- **R3 (cross-repo, CTOUT01 follow-up):** Fix the async-generator `aclose` leak —
  consumer awaits `aclose()` and/or `LangGraphHarness.invoke` handles
  `GeneratorExit` (anomaly D).
- **R4 (guardkitfactory):** Complete AC-006 live smoke for COACHBUDG01-LG.
- **R5 (ops, low effort):** FalkorDB go/no-go (H); confirm dotnet fixture debt (G)
  is non-blocking.

## Required deliverable

The `/task-review` run must output:

1. **A go/no-go verdict** on running the next FEAT-AOF validation with *only*
   COACHBUDG01-LG landed, with the turn-1-accept reasoning made explicit.
2. **A prioritized pre-run checklist** — for each item: blocker vs nice-to-have,
   owning repo, and (if a [I]mplement task should be spun up) a one-line spec.
3. **The recommended run configuration** for the next attempt (task_timeout,
   FalkorDB on/off, whether it doubles as AC-006 smoke).

## Out of scope

- Implementing any of R1-R5 — the review *recommends*; implementation tasks are
  created via the `/task-review` [I]mplement path afterward.
- Re-litigating the Responses-API vs chat-completions design fork — settled in
  COACHBUDG01-LG (Approach A). Only revisit if the review finds AC-006 cannot pass.
- The other FEAT-AOF tasks (GD02, TP05) — they never executed (wave 2 blocked by
  the IA03 failure); they re-enter scope once IA03 passes.

## References

- Run-9 log/review: `guardkit/docs/reviews/autobuild-migration/autobuild-FEAT-AOF-run-9.md`
- Fix under assessment: [`TASK-FIX-COACHBUDG01-LG`](./TASK-FIX-COACHBUDG01-LG-responses-api-reasoning-extraction.md) (in_review)
- Parent validation task (blocked): `guardkit/tasks/blocked/TASK-HMIG-010-full-feature-autobuild-validation.md`
- `TASK-FIX-SPECHANG` (completed): `guardkit/tasks/completed/2026-06/TASK-FIX-SPECHANG-test-orchestrator-polls-background-bash-until-sdk-timeout.md`
- `TASK-FIX-CTOUT01` (completed): `guardkit/tasks/completed/2026-06/TASK-FIX-CTOUT01-coach-cancellation-timeout-race.md`
- `TASK-FIX-FALK01` (completed): `guardkit/tasks/completed/2026-06/TASK-FIX-FALK01-graphiti-falkordb-teardown-race.md`
- Harness under the leak: [`langgraph_harness.py`](../../src/guardkitfactory/harness/langgraph_harness.py)
