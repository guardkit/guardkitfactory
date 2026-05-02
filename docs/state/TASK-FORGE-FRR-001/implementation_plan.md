# Implementation Plan — TASK-FORGE-FRR-001

> ## ⚠ SCOPE SUPERSEDED BY FEATURE (2026-05-02)
>
> This plan was produced during FRR-001's Phase 2.8 design checkpoint
> against the assumption that wiring `dispatch_payload` was the only
> missing piece between the daemon and the existing pipeline
> orchestrator. The Phase 3 (Implementation) investigation discovered
> the deferral is structural: the entire orchestration chain
> (`Supervisor`, `PipelineConsumerDeps`, `PipelineLifecycleEmitter`,
> `ForwardContextBuilder`, the `autobuild_runner` AsyncSubAgent, plus
> the four Protocol implementations `dispatch_autobuild_async`
> requires) is unwired in production. The honest scope is
> feature-level work, being routed through `/feature-spec` +
> `/feature-plan` against
> `docs/research/forge-orchestrator-wiring-gap.md` and
> `docs/research/forge-orchestrator-wiring-feature-context.md`.
>
> **The one piece of this plan that is still load-bearing** is the
> seam-refactor design for `src/forge/cli/_serve_daemon.py` (file
> modification #1 below — change `DispatchFn` from `(bytes) -> None`
> to `(_MsgLike) -> None`, add `max_ack_pending=1` to
> `_attach_consumer`, remove the post-dispatch ack from
> `_process_message`'s success path, update the docstrings). That
> design is correct independent of the orchestrator-wiring scope and
> will be reused verbatim by the new feature's plan. **Treat the rest
> of this file as historical context only.**
>
> The "synthetic dispatch-stage publish" in file modification #3 is
> NOT load-bearing — it was a stub by another name (a single envelope
> published to satisfy AC #2 literally with content that didn't
> reflect real autobuild behaviour). The new feature publishes the
> real per-stage envelope sequence from inside the autobuild_runner
> subagent.
>
> ---

**Task**: Wire `forge serve`'s `dispatch_payload` to the real autobuild orchestrator + synthetic dispatch-stage publish
**Complexity**: 6/10 (lowered from 7 after scope split γ)
**Workflow**: standard
**Parent feature**: FEAT-FORGE-009 (deferred this in its own plan)
**Sibling**: TASK-FORGE-FRR-001b (per-stage publishing inside the autobuild orchestrator) — also superseded

## Decisions captured at Phase 2.8 checkpoint (2026-05-02)

| Question | Decision |
|---|---|
| Architectural option | **Option 2** — fold dispatcher into `_serve_daemon`; change seam from `(bytes) -> None` to `(_MsgLike) -> None` so the dispatcher owns the ack lifecycle |
| Scope of `PipelineConsumerDeps` production wiring | **In scope** — first production construction of `PipelineConsumerDeps` happens in this task |
| `max_ack_pending=1` on `forge-serve` durable | **Confirmed** — matches `pipeline_consumer.build_consumer_config()`, honours ADR-ARCH-014 sequential-build constraint, still safe under D2 multi-replica |
| Per-stage `stage-complete` publishing | **Split out to FRR-001b** — `PipelineLifecycleEmitter` is never constructed in production today. FRR-001 publishes one **synthetic dispatch-stage** envelope after `dispatch_build` returns, which satisfies AC #2 literally. FRR-001b wires the emitter into the autobuild subagent for real per-stage publishing. |

## Why Option 1 was rejected

Rebinding `dispatch_payload = pipeline_consumer.handle_message` looks like a one-liner but breaks the deferred-ack contract: `_process_message` does `await dispatch_payload(...)` then `await msg.ack()`. `handle_message` hands an `ack_callback` to the state machine for terminal-only ack — the post-dispatch `msg.ack()` would fire it eagerly, defeating E2.1 (crash mid-build → redelivery).

## Files to modify

### 1. `src/forge/cli/_serve_daemon.py` (MODIFY)
- Change `DispatchFn` signature from `Callable[[bytes], Awaitable[None]]` to `Callable[[_MsgLike], Awaitable[None]]` — the dispatcher now owns the ack.
- Replace `_process_message`: call `dispatch_payload(msg)` only. **Remove** the post-dispatch `await msg.ack()`. Keep the `except Exception` E3.1 path but make it ack the message itself before logging (since the dispatcher won't have).
- Add `max_ack_pending=1` to `_attach_consumer`'s `ConsumerConfig`. Update the docstring's "does not gate on `max_ack_pending=1`" sentence.
- Replace `_default_dispatch` with one that just logs + acks the message itself (keeps the test seam working when monkey-patched). Update its docstring per AC #7 — the receipt-only language is gone.
- Re-export the new dispatcher type signature.

### 2. `src/forge/cli/_serve_deps.py` (NEW)
Production factory for `PipelineConsumerDeps`:
- `build_pipeline_consumer_deps(client, forge_config, sqlite_pool) -> PipelineConsumerDeps`
- Constructs:
  - `PipelinePublisher(client)` — held internally so the dispatcher can also use it for the synthetic dispatch-stage publish
  - `is_duplicate_terminal` bound to a SQLite read helper (see `forge.lifecycle.persistence` during implementation)
  - `dispatch_build` wired to a thin closure that calls `forge.pipeline.dispatchers.autobuild_async.dispatch_autobuild_async` with the right collaborators (forward_context_builder, async_task_starter, stage_log_recorder, state_channel — all needing their own production construction; if any are not yet wired in production, that's a discovery to surface during implementation)
  - `publish_build_failed` bound to `PipelinePublisher.publish_build_failed`

### 3. `src/forge/cli/_serve_dispatcher.py` (NEW)
The new module-level dispatcher that replaces `_default_dispatch`:
- `make_handle_message_dispatcher(deps: PipelineConsumerDeps, publisher: PipelinePublisher) -> DispatchFn`
- Returns an `async def dispatch(msg: _MsgLike) -> None` closure that:
  1. Calls `pipeline_consumer.handle_message(msg, deps)` — owns the ack lifecycle for accepted/rejected/duplicate paths.
  2. **After** `handle_message` returns successfully (no exception), publishes a single `pipeline.stage-complete.<feature_id>` envelope via `publisher.publish_stage_complete` with the synthetic-dispatch payload shape documented in the task file's Implementation Notes.
  3. Wraps the synthetic publish in its own try/except — a publish failure must not propagate (it would corrupt the ack semantics that `handle_message` already settled).
- Lives in its own module so the `_serve_daemon` test seams stay clean.

### 4. `src/forge/cli/serve.py` (MODIFY)
- In `_run_serve` (or `serve_cmd`), open the NATS client **once** before constructing both the dispatcher AND the daemon, so the publisher and the consumer share the connection.
- Construct `PipelineConsumerDeps` via the new factory.
- Rebind `_serve_daemon.dispatch_payload = make_handle_message_dispatcher(deps, publisher)` before awaiting `run_daemon`.
- Refactor `run_daemon` to accept an injected client (the daemon currently opens its own inside the reconnect loop; the clean fix is to pass the client in and let the caller own its lifecycle). Alternative: keep `run_daemon` as-is and have the dispatcher receive a publisher constructed against the SAME client by re-using the daemon's connection — confirm during implementation which is cleaner.

### 5. `src/forge/cli/_serve_config.py` (POSSIBLY MODIFY)
- May need to expose SQLite pool path / forge-config loader for the deps factory. Confirm in implementation.

## Files to investigate during implementation (read-only)
- `src/forge/pipeline/dispatchers/autobuild_async.py` — confirm `dispatch_autobuild_async` signature; figure out where the four required collaborators (`forward_context_builder`, `async_task_starter`, `stage_log_recorder`, `state_channel`) come from in production.
- `src/forge/pipeline/supervisor.py` — see if there's existing production wiring for the autobuild collaborators that we can re-use.
- `src/forge/lifecycle/persistence.py` — find the SQLite duplicate-terminal reader the deps factory needs.
- `src/forge/lifecycle/recovery.py` — second `reconcile_on_boot` at line 342 (different from the one in `pipeline_consumer.py:600`); understand whether the daemon should call either at startup before binding the consumer.

## Test plan

### Unit tests
1. `tests/cli/test_serve_daemon_dispatch.py` (NEW) — substitute the new `(_MsgLike) -> None` seam with a fake dispatcher; assert ack is NOT called by `_process_message` on the success path; assert ack IS called on the E3.1 failure path; assert `max_ack_pending=1` is set on the `ConsumerConfig` `_attach_consumer` produces.
2. `tests/cli/test_serve_dispatcher.py` (NEW) — `make_handle_message_dispatcher` constructs a dispatcher that delegates to `handle_message` with the supplied deps; assert the synthetic dispatch-stage publish fires after a successful accept; assert it does NOT fire when `handle_message` ack+rejects (malformed payload, allowlist failure, duplicate); assert publish failure is swallowed and does not propagate.
3. `tests/cli/test_serve_deps.py` (NEW) — production factory wires the four collaborators correctly (mocked out).
4. Update `tests/cli/test_serve_daemon.py` (existing F009-003 tests) — migrate the monkey-patch sites to the new `(_MsgLike) -> None` seam signature; assert the receipt+ack contract still holds end-to-end via the new dispatcher path.

### E2E test
5. `tests/cli/test_serve_e2e_dispatch.py` (NEW) — spin up two `forge serve` replicas against an embedded NATS (or a docker-compose fixture), publish one `pipeline.build-queued.FEAT-XXX` envelope, assert:
   - Exactly one replica processes it (work-queue semantics under `max_ack_pending=1`)
   - The autobuild dispatch is invoked (`dispatch_build` mocked at the boundary; we don't actually want the autobuild subagent to run in CI)
   - One `pipeline.stage-complete.FEAT-XXX` envelope is published with the same `correlation_id` as the inbound envelope, `stage_label="dispatch"`, `target_kind="subagent"`
   - Consumer state shows `delivered=1, acked=1, num_pending=0` after dispatch returns (preserves the F009 receipt+ack invariant)

### Coverage target
- Line: ≥80%
- Branch: ≥75%

## Acceptance Criteria mapping

| AC | Covered by |
|---|---|
| Design choice documented | Task file Implementation Notes + this plan |
| End-to-end wire test | E2E test #5 |
| Ack-after-return invariant preserved | Unit test #1 + E2E test #5 |
| Dispatch failure does not take daemon down | Unit test #1 (E3.1 path) |
| Existing F009 unit tests preserved/migrated | Unit test #4 (migration) |
| Multi-replica work-queue semantics | E2E test #5 (two replicas) |
| Correlation-id round-trip | E2E test #5 assertion + Unit test #2 |
| Docstring update on `_default_dispatch` | File modification #1 |

## Risks (carried forward, retained for implementation review)

1. **`approved_originators` allowlist** — ✅ resolved during investigation. Jarvis publishes with `originating_adapter="terminal"`, which is in the default allowlist. No config change needed.
2. **`PipelineLifecycleEmitter` not wired in production** — ✅ resolved by scope split. FRR-001 publishes a synthetic dispatch-stage envelope; FRR-001b wires the emitter into the autobuild subagent for real per-stage publishing.
3. **Production collaborators for `dispatch_autobuild_async` may not be wired** — ⚠️ open. The dispatcher needs `forward_context_builder`, `async_task_starter`, `stage_log_recorder`, `state_channel`. If any of these aren't constructible in production today, that's an implementation discovery that may force another scope discussion before the daemon-wire phase finishes.
4. **`max_ack_pending=1` migration on a live durable** — ⚠️ open. Changing `max_ack_pending` on an existing JetStream consumer requires recreating it. Operational rollout: one-time `nats consumer rm PIPELINE forge-serve` before deploying the new image. Document in deployment notes.
5. **`forge-consumer` constant becomes dead config** — ⚠️ minor. The dormant `pipeline_consumer.py` defines `DURABLE_NAME = "forge-consumer"`. After this task the only production-bound durable is `forge-serve`. Track follow-up cleanup separately.

## Estimated effort (post-split)

| Chunk | Days |
|---|---|
| Seam refactor + `_attach_consumer` change + docstring | 0.5 |
| Production factory `_serve_deps.py` + investigation of autobuild collaborators | 1.0 |
| Dispatcher closure + synthetic dispatch-stage publish + `serve.py` wiring | 0.5 |
| Unit tests + migration of F009-003 tests | 0.5 |
| E2E test (two replicas + assertions) | 0.5 |
| **Total** | **~3.0 days** (was 3.5–4.0 before split) |

## Out of scope (per task brief, confirmed)

- Per-stage `stage-complete` publishing inside the autobuild orchestrator → **FRR-001b**
- Jarvis-side `forge_subscriber` workqueue attach fix (separate jarvis follow-up)
- Autobuild orchestrator's own correctness — assumed working
- Replay-window / alternate retention behaviour for PIPELINE stream
- Renaming `forge-consumer` → `forge-serve` (handled by leaving `forge-consumer` dormant; follow-up cleanup)
