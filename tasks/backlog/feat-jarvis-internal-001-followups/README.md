# FEAT-JARVIS-INTERNAL-001 First-Real-Run Follow-ups

Forge-side follow-up tasks surfaced by the **first real walkthrough**
of jarvis's FEAT-JARVIS-INTERNAL-001 runbook on 2026-05-01 on GB10
(`promaxgb10-41b1`).

## Source

All three tasks in this folder originate from a single end-to-end
walkthrough whose findings are captured in:

- **RESULTS file** (jarvis repo):
  [`/home/richardwoollcott/Projects/appmilla_github/jarvis/docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](../../../../jarvis/docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md)
- **Run correlation_id**: `a58ec9a7-27c6-485a-beac-e18675639a10`
- **Date**: 2026-05-01
- **Machine**: GB10 (`promaxgb10-41b1`)

The RESULTS file's `## Recommended follow-up tasks` section enumerates
8 follow-ups across forge, jarvis, and the runbook itself; this
folder holds the **forge-side** subset (items #1, #2, #3 in that list).
The jarvis-side (#4, #5, #6) and runbook-side (#7, #8) follow-ups are
tracked in the jarvis repo separately.

## Tasks in this folder

| Task | Title | Priority | Complexity |
|---|---|---|---|
| [TASK-FORGE-FRR-001](./TASK-FORGE-FRR-001-wire-dispatch-payload-to-real-orchestrator.md) | Wire `forge serve`'s `dispatch_payload` to the real autobuild orchestrator + stage-complete publish path | high | 7 |
| [TASK-FORGE-FRR-002](./TASK-FORGE-FRR-002-wire-logging-basicconfig-for-forge-log-level.md) | Wire `logging.basicConfig` in `forge serve` so `FORGE_LOG_LEVEL` actually produces visible logs | high | 2 |
| [TASK-FORGE-FRR-003](./TASK-FORGE-FRR-003-fix-build-image-script-context-path.md) | Fix `scripts/build-image.sh` so `--build-context nats-core=../nats-core` resolves on the canonical sibling layout | high | 2 |

## Recommended order

1. **TASK-FORGE-FRR-003** first (45 min) — unblocks
   `RUNBOOK-FEAT-FORGE-008-validation.md` §2.1 so the production image
   can be built with one command from a clean clone.
2. **TASK-FORGE-FRR-002** second (60 min) — quick, high-value
   observability fix; makes TASK-FORGE-FRR-001's e2e wire test
   actually debuggable when it fails.
3. **TASK-FORGE-FRR-001** last (1-2 days) — the structural piece. Its
   e2e test depends on having visible logs (FRR-002) to debug
   regressions, and on a buildable image (FRR-003) to test against.

After all three land, the jarvis runbook's Phase 7 close criterion
(stage-complete events flow back into the chat REPL, threaded by
`correlation_id`) becomes structurally satisfiable for the first time.

## Naming

`FRR` = "first real run" — the prefix used to disambiguate this small
batch of follow-ups from the prior FEAT-FORGE-009 (F009) follow-ups
(`TASK-FIX-F09A1`, `TASK-FIX-F09A2`) and the F0E6 fix series
(`TASK-FIX-F0E6`, `TASK-FIX-F0E6b`). All three tasks share `FORGE-FRR`
because they are all forge-side work originating from the jarvis
runbook's first real run.
