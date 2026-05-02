# DDR-007 — Pipeline lifecycle emitter wiring path into `autobuild_runner`

## Status

Accepted

- **Date:** 2026-05-02
- **Session:** `/feature-spec` for FEAT-FORGE-010 (forge-serve-orchestrator-wiring); resolves the open architectural question carried over from superseded TASK-FORGE-FRR-001b.
- **Related:** ADR-ARCH-008, ADR-ARCH-021, ADR-ARCH-031, DDR-006, FEAT-FORGE-010
- **Resolves:** FEAT-FORGE-010 ASSUM-010 (pause/resume publish in scope), ASSUM-018 (stage-complete from inside the subagent carries the asynchronous task identifier).

---

## Context

`PipelineLifecycleEmitter` exposes the eight `emit_*` methods (`build_started`, `stage_complete`, `build_paused`, `build_resumed`, `build_complete`, `build_failed`, `build_cancelled`, `build_progress`) that map onto the eight published subjects in API-nats-pipeline-events §3. The emitter is constructed once per daemon process against `PipelinePublisher` and the daemon's single NATS connection (FEAT-FORGE-010 ASSUM-002, ASSUM-011).

The autobuild stage runs inside the `autobuild_runner` AsyncSubAgent (ADR-ARCH-031). Most stage transitions and all gate-evaluation `interrupt()` fires happen *inside* that subagent. The emitter must reach those call sites or the per-stage envelope sequence the operator depends on never gets published.

The investigation in `docs/research/forge-orchestrator-wiring-gap.md` and the superseded TASK-FORGE-FRR-001b surfaced two plausible wiring paths:

- **Option A — thread the emitter through dispatcher context.** `dispatch_autobuild_async` accepts a `lifecycle_emitter: PipelineLifecycleEmitter` parameter and threads it into the `start_async_task` context payload; the subagent receives the emitter as an in-process Python object and calls it directly at each transition.
- **Option B — watch the `async_tasks` state channel and emit from outside.** A separate watcher reads `AutobuildState` rows for the active autobuild and publishes lifecycle envelopes when the persisted state advances. The subagent itself only writes to its state channel (DDR-006); publish responsibility lives outside the subagent.

DDR-006 already mandates that the subagent calls a `_update_state(...)` helper on every lifecycle transition. That helper is the natural attachment point for whichever wiring path this DDR picks.

## Decision

**Adopt Option A.** The `PipelineLifecycleEmitter` is threaded into the autobuild_runner subagent through the dispatcher's context payload, and `_update_state(...)` (DDR-006) is extended to call the matching `emit_*` method at the same boundary as the state-channel write.

```python
# forge.subagents.autobuild_runner (illustrative — final shape settled in /feature-plan)
def _update_state(
    state: AutobuildState,
    *,
    lifecycle: AutobuildLifecycle,
    emitter: PipelineLifecycleEmitter,
    ...
) -> AutobuildState:
    new_state = state.model_copy(update={"lifecycle": lifecycle, ...})
    write_async_tasks_channel(new_state)        # DDR-006
    emitter.on_transition(new_state)            # DDR-007 — same boundary
    return new_state
```

**Pause / resume publish is in scope of FEAT-FORGE-010.** With the emitter reachable from `_update_state`, `emit_build_paused` is one call at the `lifecycle="awaiting_approval"` boundary and `emit_build_resumed` is one call in the existing `forge.adapters.nats.approval_subscriber` resume path. Both are part of FEAT-FORGE-010's acceptance set; they are not split out.

**Stage-complete envelope shape from inside the subagent (DDR-006 linkage).** When `autobuild_runner` emits `stage_complete` for one of its internal transitions, the envelope's `target_kind` is `"subagent"` and `target_identifier` is the subagent's `task_id` (the value returned by `start_async_task`). The supervisor's emit calls (for stages dispatched outside the subagent) use the existing taxonomy unchanged.

**Failure-mode contract.** Per ADR-ARCH-008 and the API contract's §3.3 PubAck-≠-success rule, a failed `emit_*` call MUST NOT regress the build's recorded transition. The emitter logs at `WARNING` and returns; the autobuild continues; SQLite remains the authoritative source of truth. This is identical to the contract `PipelinePublisher` already enforces — DDR-007 just locates it at the new call site.

## Rationale

- **Same-boundary publish is durability-equivalent and lower-latency than out-of-band watching.** Both options have the same crash-recovery story (SQLite is authoritative; a publish lost between the state-channel write and the daemon crash is recovered on restart by `reconcile_on_boot` re-emitting). Option A pays no polling cost; Option B introduces a CPU/UX trade-off (<1s polling churns, >1s lags operator-visible progress).
- **DDR-006's `_update_state` is already the single transition point.** Co-locating the emitter call with the state-channel write means one canonical site, not two destinations the subagent needs to keep consistent.
- **`interrupt()` is already in-flow per ADR-ARCH-021.** Pause/resume publishes belong on the same control flow as the `interrupt()` call that produced the pause; threading the emitter through the subagent is consistent with how the gate-evaluation path is already shaped.
- **Decoupling argument for Option B is theoretical.** No second publisher exists or is on the roadmap. If a multi-target publish is ever needed, swapping the threaded emitter for a multi-target wrapper is a one-line constructor change at the `_serve_deps` factory.
- **Consistent failure stack.** Option A surfaces publish failures inside the subagent's call stack alongside the work that produced them; Option B isolates publish failures into a separate watcher whose correlation back to the originating transition is harder to read.
- **Aligns with the DeepAgents AsyncSubAgent idiom.** ADR-ARCH-031 commits to ASGI co-deployment as the default transport; the subagent runs in the daemon's process, so the emitter is a reachable Python object. Threading non-serialisable Python objects through the AsyncSubAgent context payload is the use case the in-process transport exists to support.

## Alternatives considered

- **Option B — watch the `async_tasks` state channel and emit from outside.** Rejected for the latency / failure-locality / extra-component reasons above. The decoupling benefit is real only under HTTP transport; ADR-ARCH-031 reserves HTTP for a future ADR, so taking the cost now is paying for a hypothetical.
- **Hybrid C — both inline emit and a watcher as belt-and-braces.** Rejected — doubles publish volume and creates two ordering paths a subscriber would have to dedupe.
- **Defer pause/resume publish to a follow-up.** Rejected because under Option A pause/resume is genuinely a one-line addition at the same boundary as the state-channel write that already writes `lifecycle="awaiting_approval"`. Splitting it out would create a half-wired emitter that handles `stage-complete` but not the very transition operators care most about.

## Consequences

**Positive:**

- Inline publish — operators see live progress at the speed of NATS PubAck, not a polling interval.
- Single transition site — `_update_state(...)` co-locates the state-channel write and the emit call; future drift is prevented by centralisation.
- Pause/resume publish is in scope of FEAT-FORGE-010 — no follow-up task needed.
- Failure stack stays in the subagent's call path; debugging a missing envelope reads naturally.

**Negative:**

- Bets on ASGI co-deployment for the foreseeable future. If HTTP transport is ever adopted (its own ADR), this DDR needs to be re-opened or the emitter needs a serialisable transport wrapper. Mitigation: ADR-ARCH-031 already pins ASGI as the default and HTTP as a "new ADR specifying why" decision.
- The subagent's context payload now carries a non-serialisable Python object. Verify with the DeepAgents 0.5.3 AsyncSubAgent context contract during `/feature-plan`'s investigation step. Mitigation: ASGI co-deployment is the explicit transport choice precisely so in-process objects can be passed.
- One more parameter on `dispatch_autobuild_async`. Acceptable — the function's signature is internal and the parameter is a concrete dependency that belongs alongside the four it already accepts (`forward_context_builder`, `async_task_starter`, `stage_log_recorder`, `state_channel`).

## Forward compatibility

- If a future ADR adopts HTTP transport for the autobuild_runner subagent, this DDR is re-opened. The recovery path is to introduce a thin RPC-shaped emitter (publish via a per-build NATS subject the daemon-side emitter listens on) and swap it in at the `_serve_deps` factory; no autobuild_runner code changes are required because the call site already uses an `emitter` interface.
- The `target_kind="subagent"` + `target_identifier=task_id` shape (ASSUM-018) is additive to API-nats-pipeline-events §3.2 — the contract already permits these literal values; DDR-007 just commits forge to using them for autobuild-internal transitions.

## Do-not-reopen

- Threading the emitter through the subagent's context payload (vs. a separate watcher) is settled. A future HTTP-transport ADR re-opens it; nothing else does.
- Pause/resume publish-from-the-subagent stays in scope of FEAT-FORGE-010. If `/feature-plan`'s investigation surfaces an unexpected obstacle (e.g. DeepAgents 0.5.3 actively rejects non-serialisable context), file a one-task carve-out at that point — but the default position is "in scope".

## Related components

- Subagent (`forge.subagents.autobuild_runner` — net-new in FEAT-FORGE-010)
- Emitter (`forge.pipeline.PipelineLifecycleEmitter`)
- Publisher (`forge.adapters.nats.pipeline_publisher.PipelinePublisher`)
- Approval subscriber (`forge.adapters.nats.approval_subscriber` — emit_build_resumed call site)
- State channel (`forge.subagents.autobuild_runner._update_state` — DDR-006)
- Daemon factory (`forge.cli._serve_deps` — constructs the emitter once per daemon)

## References

- ADR-ARCH-008 — Forge produces own history (SQLite authoritative; bus is derived projection).
- ADR-ARCH-021 — PAUSED via LangGraph `interrupt()`.
- ADR-ARCH-031 — Async subagents for long-running work (ASGI default transport).
- DDR-006 — `AutobuildState` lifecycle and `_update_state` helper.
- API-nats-pipeline-events §3 — eight lifecycle subjects + StageCompletePayload `target_kind`/`target_identifier` semantics.
- `docs/research/forge-orchestrator-wiring-gap.md` — the gap-finding doc that surfaced the two options.
- Superseded TASK-FORGE-FRR-001b — first place option (a) vs (b) was named.
- FEAT-FORGE-010 spec: `features/forge-serve-orchestrator-wiring/forge-serve-orchestrator-wiring.feature` + `_assumptions.yaml` (ASSUM-010, ASSUM-018).
