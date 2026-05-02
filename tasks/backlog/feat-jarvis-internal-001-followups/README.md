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

| Task | Title | Priority | Complexity | Status |
|---|---|---|---|---|
| [TASK-FORGE-FRR-001](../../completed/TASK-FORGE-FRR-001/TASK-FORGE-FRR-001-wire-dispatch-payload-to-real-orchestrator.md) | Wire `forge serve`'s `dispatch_payload` to the real autobuild orchestrator + stage-complete publish path | high | 6 | ⚠ superseded-by-feature (2026-05-02) |
| [TASK-FORGE-FRR-001b](../../completed/TASK-FORGE-FRR-001b/TASK-FORGE-FRR-001b-publish-pipeline-lifecycle-from-autobuild-orchestrator.md) | Publish pipeline lifecycle events (build-started, stage-complete×N, build-complete) from the autobuild orchestrator | high | 7 | ⚠ superseded-by-feature (2026-05-02) |
| [TASK-FORGE-FRR-002](../../completed/TASK-FORGE-FRR-002/TASK-FORGE-FRR-002-wire-logging-basicconfig-for-forge-log-level.md) | Wire `logging.basicConfig` in `forge serve` so `FORGE_LOG_LEVEL` actually produces visible logs | high | 2 | ✅ completed (b1da833, 2026-05-01) |
| [TASK-FORGE-FRR-003](../../completed/TASK-FORGE-FRR-003/TASK-FORGE-FRR-003-fix-build-image-script-context-path.md) | Fix `scripts/build-image.sh` so `--build-context nats-core=../nats-core` resolves on the canonical sibling layout | high | 2 | ✅ completed (fc7fd9a, 2026-05-01) |

> **Supersession note (2026-05-02)**: FRR-001 + FRR-001b were both
> closed as `superseded-by-feature` after the FRR-001 Phase 3
> investigation discovered that the entire pipeline orchestration
> chain (`Supervisor`, `PipelineConsumerDeps`,
> `PipelineLifecycleEmitter`, `ForwardContextBuilder`, the
> `autobuild_runner` AsyncSubAgent, plus four Protocol
> implementations) is unwired in production. F009 deferred more than
> "wire `dispatch_payload`" — it deferred the entire orchestration
> tail. The remaining work has been re-scoped to **FEAT-FORGE-010**
> (slug `forge-serve-orchestrator-wiring` — see
> [`tasks/backlog/forge-serve-orchestrator-wiring/`](../forge-serve-orchestrator-wiring/README.md)).
> The feature was filed against the findings document
> `docs/research/forge-orchestrator-wiring-gap.md` and the
> `--context` evaluation
> `docs/research/forge-orchestrator-wiring-feature-context.md`; both
> remain valid as pre-feature reference material. The
> `superseded_by` frontmatter on both FRR-001 and FRR-001b has been
> updated to point at FEAT-FORGE-010.

## Sequence (current state)

1. ~~**TASK-FORGE-FRR-003**~~ ✅ **shipped** (`fc7fd9a`, 2026-05-01) — `scripts/build-image.sh` now `cd`s into forge's parent directory before invoking buildx, so `--build-context nats-core=../nats-core` resolves correctly on the canonical sibling layout.
2. ~~**TASK-FORGE-FRR-002**~~ ✅ **shipped** (`b1da833`, 2026-05-01) — `serve_cmd` now calls `logging.basicConfig(level=config.log_level, ...)` immediately after `ServeConfig.from_env()`. `docker logs forge-prod` now actually shows the `_serve_daemon` and `_serve_healthz` log lines that were silently dropped before.
3. ~~**TASK-FORGE-FRR-001**~~ + ~~**TASK-FORGE-FRR-001b**~~ ⚠ **superseded** (2026-05-02) — see supersession note above. Subsumed by **FEAT-FORGE-010** (`forge-serve-orchestrator-wiring`). The runbook's Phase 7 close criterion ("real per-stage notifications render in the chat REPL") will be satisfied when FEAT-FORGE-010 ships.
4. **Active: [FEAT-FORGE-010](../forge-serve-orchestrator-wiring/README.md)** — feature scoped, Wave 1-4 task plan filed in `tasks/backlog/forge-serve-orchestrator-wiring/`. Anchor decision: DDR-007 (emitter wiring path).

The jarvis runbook
(`/home/richardwoollcott/Projects/appmilla_github/jarvis/docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md`)
has been updated alongside this supersession to test for the real
per-stage envelope sequence FEAT-FORGE-010 will produce, not the
synthetic single-envelope output FRR-001 was originally going to
ship.

## Naming

`FRR` = "first real run" — the prefix used to disambiguate this small
batch of follow-ups from the prior FEAT-FORGE-009 (F009) follow-ups
(`TASK-FIX-F09A1`, `TASK-FIX-F09A2`) and the F0E6 fix series
(`TASK-FIX-F0E6`, `TASK-FIX-F0E6b`). All three tasks share `FORGE-FRR`
because they are all forge-side work originating from the jarvis
runbook's first real run.
