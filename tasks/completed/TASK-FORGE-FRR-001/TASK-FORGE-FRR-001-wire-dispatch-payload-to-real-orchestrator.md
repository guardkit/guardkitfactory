---
id: TASK-FORGE-FRR-001
title: Wire `forge serve`'s `dispatch_payload` to the real autobuild orchestrator + stage-complete publish path
status: superseded
created: 2026-05-01T00:00:00Z
updated: 2026-05-02T00:00:00Z
closed_at: 2026-05-02T00:00:00Z
closed_reason: superseded-by-feature
superseded_by: docs/research/forge-orchestrator-wiring-gap.md  # the new feature's spec/plan are pending /feature-spec + /feature-plan
priority: high
task_type: feature
tags:
  - forge-serve
  - jetstream
  - pipeline-consumer
  - autobuild
  - stage-complete
  - dispatch
  - feat-forge-009-followup
  - first-real-run-followup
  - superseded-by-feature
complexity: 6
estimated_minutes: 600
estimated_effort: "~2.5 days (daemon wire + synthetic dispatch publish + e2e test) — see SUPERSESSION below"
parent_feature: FEAT-FORGE-009
related_tasks:
  - TASK-REV-F009            # FEAT-FORGE-009 plan that explicitly deferred this
  - TASK-FORGE-FRR-001b      # sibling — also superseded
correlation_id: a58ec9a7-27c6-485a-beac-e18675639a10
discovered_on:
  date: 2026-05-01
  machine: GB10 (promaxgb10-41b1)
  context: "co-resident first walkthrough of jarvis FEAT-JARVIS-INTERNAL-001 runbook"
design:
  status: superseded
  notes: "Phase 2.8 checkpoint produced an Option 2 + max_ack_pending=1 + scope-split-γ design. That design's synthetic dispatch-stage publish was a stub by another name — it satisfied AC #2 literally but with an envelope that didn't reflect real autobuild behaviour. Phase 3 (Implementation) discovered the supersession during file #1 of the deps factory and stopped. The seam-refactor portion of the design is still load-bearing and is preserved in docs/state/TASK-FORGE-FRR-001/implementation_plan.md for the new feature's plan to reuse."
  implementation_plan: docs/state/TASK-FORGE-FRR-001/implementation_plan.md
test_results:
  status: not-applicable
  coverage: null
  last_run: null
---

> ## ⚠ SUPERSEDED BY FEATURE (2026-05-02)
>
> This task was filed against the assumption that `forge serve`'s
> `dispatch_payload` was the only missing wire between the daemon and
> the existing pipeline orchestrator. The Phase 2.8 design checkpoint
> investigation discovered that the entire orchestrator chain
> (`Supervisor`, `PipelineConsumerDeps`, `PipelineLifecycleEmitter`,
> `ForwardContextBuilder`, the `autobuild_runner` AsyncSubAgent, plus
> the four Protocol implementations `dispatch_autobuild_async`
> requires) is **never constructed in production today**. F009
> shipped the daemon process; the orchestrator it was supposed to
> host was deferred wholesale.
>
> The honest scope to satisfy this task's ACs without stubs is
> multi-week, feature-level work. It is being re-scoped through
> `/feature-spec` + `/feature-plan` against
> `docs/research/forge-orchestrator-wiring-gap.md` (the findings
> document) and
> `docs/research/forge-orchestrator-wiring-feature-context.md` (the
> `--context` evaluation for the two commands).
>
> When the new feature's ID lands, this file's `superseded_by`
> frontmatter field should be updated from the findings-doc pointer
> to the feature ID.
>
> **Still load-bearing from this task**:
> - The `_serve_daemon._process_message` seam-refactor design (change
>   `DispatchFn` from `(bytes) -> None` to `(_MsgLike) -> None`,
>   set `max_ack_pending=1` on the durable, remove post-dispatch ack
>   on the success path). Captured in
>   `docs/state/TASK-FORGE-FRR-001/implementation_plan.md` for the
>   new feature's plan to reuse verbatim.
> - The originator-allowlist finding (jarvis chat REPL publishes with
>   `originating_adapter="terminal"`, which is in
>   `DEFAULT_APPROVED_ORIGINATORS`; `triggered_by="jarvis"` is a
>   separate field) — captured in the findings doc.
>
> **No longer load-bearing**:
> - The "synthetic dispatch-stage publish to satisfy AC #2 literally"
>   recommendation. That was a stub. The new feature publishes the
>   real per-stage envelope sequence from inside the autobuild_runner
>   subagent.
>
> The task's original Description, Why-this-matters, Acceptance
> Criteria, Out-of-Scope, Implementation Notes, and References
> sections are preserved below as historical context.
>
> ---

# Task: Wire `forge serve`'s `dispatch_payload` to the real autobuild orchestrator + stage-complete publish path

## Description

`forge serve` (FEAT-FORGE-009) ships today with `dispatch_payload`
defaulting to a **receipt-only stub** — `_default_dispatch` parses the
envelope, logs the `feature_id` + `correlation_id`, and returns. The
docstring (`src/forge/cli/_serve_daemon.py:146-167`) is explicit that
this is deliberate:

> The actual orchestrator wiring is owned by the existing
> `forge.adapters.nats.pipeline_consumer` machinery; `forge serve` is
> the new daemon process that hosts that machinery. For the receipt AC
> we only need to prove the message was pulled and acked.

So FEAT-FORGE-009 deliberately shipped the *receipt* contract (subscribe
+ ack on the shared durable consumer) and deferred the *dispatch*
contract. This task delivers the dispatch contract.

### Why this matters (empirical evidence — 2026-05-01 GB10 run)

During the jarvis FEAT-JARVIS-INTERNAL-001 first-real-run on 2026-05-01
on GB10 (correlation_id
`a58ec9a7-27c6-485a-beac-e18675639a10`), the runbook's Phase 7 close
criterion ("between-prompt notifications render in the chat REPL,
showing stage-complete events for FEAT-43DE") **could not be met** —
not because of operator error, but because nothing on the forge side
publishes `pipeline.stage-complete.*` envelopes back. The
`forge-serve` durable consumer correctly dequeued the
`pipeline.build-queued.FEAT-43DE` message and acked it (consumer state:
`delivered=1, acked=1, num_pending=0`), but `_default_dispatch` then
returned without firing any autobuild and without publishing anything
back to JetStream. From jarvis's perspective the build vanished.

This makes the runbook's precondition

> "FEAT-FORGE-009 production image + `forge serve` daemon merged"
> is sufficient for Phase 3 close

**a structural overstatement of what F009 actually ships**. The
forge-side wire is in place but the autobuild orchestrator is not
plumbed in.

## Source code references

- **Receipt-only stub** (the one this task replaces or wires):
  [`src/forge/cli/_serve_daemon.py:146-180`](../../../src/forge/cli/_serve_daemon.py)
  (`_default_dispatch`).
- **Module-level rebindable seam**:
  [`src/forge/cli/_serve_daemon.py:185-186`](../../../src/forge/cli/_serve_daemon.py)
  (`dispatch_payload: DispatchFn = _default_dispatch`).
- **Ack-after-return invariant** the wire-up must preserve:
  [`src/forge/cli/_serve_daemon.py:227-249`](../../../src/forge/cli/_serve_daemon.py)
  (`_process_message`).
- **Existing autobuild dispatcher** (presumed target — confirm during
  design): `forge.adapters.nats.pipeline_consumer` (per the
  `_default_dispatch` docstring's own pointer).
- **Daemon entry-point** (where the seam-swap would happen at startup
  if you keep the seam): [`src/forge/cli/serve.py:43-94`](../../../src/forge/cli/serve.py)
  (`_run_serve`, `serve_cmd`).

## Goal

Replace (or properly wire) `dispatch_payload` so that on receipt of a
`pipeline.build-queued.<feature_id>` envelope, `forge serve` runs the
real autobuild orchestrator end-to-end, including publishing one or
more `pipeline.stage-complete.<feature_id>` envelopes back to
JetStream with the **same `correlation_id`** so that downstream
listeners (jarvis's `forge_subscriber`, the dashboard, the operator's
chat REPL via DDR-030) can thread progress.

The exact architecture is left to the implementer — three plausible
options, design choice should be captured in the task's Implementation
Notes once decided:

1. **Keep the seam, swap at startup**: in `serve.py:_run_serve` (or in
   `serve_cmd`), import `forge.adapters.nats.pipeline_consumer` and
   rebind `_serve_daemon.dispatch_payload` to its real dispatcher
   coroutine before `run_daemon` is awaited. Tests that monkey-patch
   `dispatch_payload` continue to work unchanged.
2. **Fold the dispatcher into `_serve_daemon`**: replace
   `_default_dispatch` with a real implementation that drives
   `pipeline_consumer` directly. Keeps the seam for tests but removes
   the indirection.
3. **Refactor `pipeline_consumer` to expose a `Dispatcher` ABC**: the
   daemon constructs the dispatcher once at startup (with the same
   NATS client used for outbound publish) and passes it into
   `run_daemon`. Most invasive but the cleanest separation.

Whichever option is picked, **the publish-back path must use the same
NATS client** that the daemon already opens — opening a second
connection just for outbound publish is an anti-pattern for a
single-process daemon.

## Acceptance Criteria

- [ ] **Design choice documented**: pick one of the three options
      above (or a justified alternative) and write a short
      Implementation Notes paragraph explaining the choice and why.
- [ ] **End-to-end wire test**: starting from a clean state on the
      canonical layout —
  - jarvis chat REPL on FEAT-43DE invokes `queue_build`
  - `forge serve` consumes the message
  - the real autobuild orchestrator dispatch fires (even if it's a
    near-no-op against a feature whose work is already on `main`)
  - **at least one `pipeline.stage-complete.FEAT-43DE` envelope is
    published back to JetStream** with the same `correlation_id` as
    the inbound `pipeline.build-queued.FEAT-43DE` envelope.
- [ ] **Ack-after-return invariant preserved**: the
  `forge-prod` durable consumer state (`nats consumer info PIPELINE
  forge-serve -j`) shows the consumed message acked **after** the
  dispatch coroutine returns, not before. The current
  `_serve_daemon.py:230-249` `_process_message` contract (dispatch →
  ack, with cancellation NOT acking) must still hold.
- [ ] **Dispatch failure does not take the daemon down (E3.1)**: if
  the orchestrator's dispatch raises, the daemon logs at WARNING,
  acks the message (releases the queue slot), and continues with the
  next payload. (Same property `_process_message` already provides;
  the wiring must not regress it.)
- [ ] **Existing F009 unit tests for the receipt+ack contract are
      preserved or migrated**: `tests/cli/` (or wherever F009-003's
      `_serve_daemon` tests live) must still pass with the new
      dispatch wired in. If the seam is preserved, no test changes.
      If the seam is removed, equivalent tests must be added against
      the new dispatcher with monkey-patched NATS.
- [ ] **Multi-replica work-queue semantics still hold (D2 / ASSUM-006)**:
  two `forge serve` replicas binding the same `forge-serve` durable
  must split work, not duplicate it. Verifiable with two containers
  on the same host pointing at the same NATS server.
- [ ] **Correlation-id round-trip test**: assert in the e2e test that
  the inbound envelope's `correlation_id` is preserved on the
  outbound stage-complete envelopes. Anything else breaks DDR-030's
  notification-thread contract.
- [ ] **Docstring update**: `_default_dispatch`'s docstring (or the
      function that replaces it) should no longer claim "for the
      receipt AC we only need to prove the message was pulled and
      acked" — that statement is correct for F009 but stale once this
      task lands.

## Out of Scope

- **Jarvis-side notification rendering**: jarvis's `forge_subscriber`
  fails to attach to the workqueue PIPELINE stream during startup
  ("consumer must be deliver all on workqueue stream") — that's a
  separate jarvis-side follow-up and is being tracked there.
- **The deeper autobuild orchestrator's own correctness**: assumed
  working. This task only makes the wire connection so its outputs
  reach the bus.
- **Replay-window or alternate retention behaviour** for the PIPELINE
  stream — keep ASSUM-007 (JetStream defaults only) intact.
- **Architectural changes to the pipeline_consumer dispatcher itself**
  beyond the minimum needed to host it inside `forge serve`.

## Implementation Notes

### Design decisions (Phase 2.8 checkpoint, 2026-05-02)

**Option 2 chosen** — fold the dispatcher into `_serve_daemon`. The seam
contract `dispatch_payload: DispatchFn` changes from
`Callable[[bytes], Awaitable[None]]` to `Callable[[_MsgLike], Awaitable[None]]`
so the dispatcher owns the ack lifecycle. `_process_message` no longer acks
after the dispatch returns — that responsibility moves to
`pipeline_consumer.handle_message`'s deferred `ack_callback`, preserving E2.1
(crash mid-build → redelivery).

Option 1 was rejected because rebinding `dispatch_payload` while
`_process_message` still calls `await msg.ack()` post-dispatch would defeat
the deferred-ack contract.

**`max_ack_pending=1` on the `forge-serve` durable** — added to
`_attach_consumer`'s `ConsumerConfig`. Matches
`pipeline_consumer.build_consumer_config()` and honours ADR-ARCH-014
(sequential-build constraint). Multi-replica D2 still works: JetStream hands
the one outstanding-ack slot to whichever replica fetched it; the others
sit idle until the slot frees. **Operational note:** changing
`max_ack_pending` on an existing JetStream consumer requires recreating it.
Roll out with a one-time `nats consumer rm PIPELINE forge-serve` before
deploying the new image.

**Scope split (γ)** — investigation surfaced that
`PipelineLifecycleEmitter` (`src/forge/pipeline/__init__.py:273`) has
`emit_stage_complete` and the seven other lifecycle methods, but is **never
constructed in production**. `dispatch_autobuild_async` launches a
DeepAgents subagent and returns immediately; the subagent has no path back
to publish lifecycle events. So even with this task's daemon wire in place,
nothing inside the autobuild orchestrator publishes `stage-complete`.

To keep this task shippable, FRR-001 satisfies AC #2 ("at least one
stage-complete envelope back") via a **synthetic dispatch-stage publish**:
the new `_serve_dispatcher` calls `PipelinePublisher.publish_stage_complete`
once after `dispatch_build` returns its `AutobuildDispatchHandle`. The
envelope is shaped as:

- `feature_id = payload.feature_id`
- `build_id = payload.build_id` (or derived if not in `BuildQueuedPayload`)
- `stage_label = "dispatch"` (literal — marks the synthetic origin)
- `target_kind = "subagent"`
- `target_identifier = handle.task_id`
- `status = "PASSED"` (dispatch succeeded; the autobuild's outcome is FRR-001b's surface)
- `correlation_id = payload.correlation_id` (round-trip — AC #7)

Per-stage publishing inside the autobuild orchestrator is split into
**TASK-FORGE-FRR-001b**. That task wires `PipelineLifecycleEmitter` into
the autobuild subagent context so each real stage transition publishes its
own `stage-complete` envelope. Once FRR-001b lands, the synthetic
dispatch-stage envelope from this task is still useful (it lets jarvis
acknowledge "dispatch happened" before the first real stage completes) and
should remain.

### Sources to read during implementation

- **Confirm the dispatcher's contract**: `pipeline_consumer.handle_message`
  signature `(_MsgLike, PipelineConsumerDeps) -> None` is the integration
  point. The dispatcher closure built in `_serve_dispatcher.py` calls into
  it.
- **Outbound publish**: reuse `forge.adapters.nats.pipeline_publisher.PipelinePublisher`.
  Do NOT roll a new publisher.
- **`approved_originators` is a non-issue for the e2e test**: the runbook
  envelope from the jarvis chat REPL uses `originating_adapter="terminal"`
  (the physical interface), which is in
  `DEFAULT_APPROVED_ORIGINATORS`. `triggered_by="jarvis"` is a separate
  field that the consumer does not gate on.
- **Logging**: this task assumes TASK-FORGE-FRR-002 (`logging.basicConfig`
  wire-up) has either landed or is in flight. Without that, the
  orchestrator's per-stage logs will continue to disappear into
  `docker logs forge-prod`. Not a hard dependency — they can ship in
  either order — but worth coordinating.

### Detailed implementation plan

See `docs/state/TASK-FORGE-FRR-001/implementation_plan.md` for the
file-by-file scope, test plan, and effort breakdown.

## References

- **RESULTS file** that surfaced this issue:
  [/home/richardwoollcott/Projects/appmilla_github/jarvis/docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md](../../../../jarvis/docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md)
- **Specific RESULTS table rows that motivate this task**:
  - Phase 7.1 (`between-prompt notifications render`): "❌ as
    expected. No notification lines drained. Two independent reasons:
    (a) `forge serve`'s default `dispatch_payload`
    (`_serve_daemon.py:146-180`) is a receipt-only stub — logs and
    returns, no autobuild, no publish-back; …"
  - Phase 7.2 (`forge logs show consume + publish-back`): "⚠️ via
    consumer state. `forge-serve` consumer info: `delivered=1,
    acked=1, num_pending=0, num_redelivered=0` proves forge dequeued
    and acked."
  - Recommended follow-up #1: "forge: wire `dispatch_payload` to the
    real `pipeline_consumer` orchestrator + stage-complete publish
    path (the comment in `_default_dispatch` explicitly defers this)."
  - Operator-side gaps row 9 (Phase 7.1 expectation): "FEAT-FORGE-009's
    `forge serve` ships only the receipt scaffold; its default
    `dispatch_payload` is a stub. The runbook's preconditions table
    claims '`forge serve` daemon merged' is sufficient; it isn't."
- **Forge source files**:
  - [`src/forge/cli/_serve_daemon.py`](../../../src/forge/cli/_serve_daemon.py) (lines 146-186 — the seam this task swaps)
  - [`src/forge/cli/serve.py`](../../../src/forge/cli/serve.py) (the daemon entry-point)
  - `src/forge/adapters/nats/pipeline_consumer.py` (the dispatcher to plumb in — confirm path during impl)
  - `src/forge/adapters/nats/pipeline_publisher.py` (the outbound publisher — confirm path during impl)
- **Run that surfaced this**:
  - **correlation_id**: `a58ec9a7-27c6-485a-beac-e18675639a10`
  - **Date**: 2026-05-01
  - **Machine**: GB10 (`promaxgb10-41b1`), co-resident first walkthrough

## Test Execution Log

[Automatically populated by /task-work and downstream test runs]
