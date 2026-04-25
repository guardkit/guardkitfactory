# Review Report: TASK-REV-SAD3

**Feature**: FEAT-FORGE-003 — Specialist Agent Delegation
**Mode**: Decision (full sweep)
**Depth**: Standard
**Trade-off priority**: Quality (correctness > speed)
**Specific concerns**: correlation correctness, security invariants, retry semantics, timeout behaviour
**Generated**: 2026-04-25

---

## Executive Summary

FEAT-FORGE-003 closes the last domain-judgement seam in Forge: a single
capability-driven dispatch path that resolves a target specialist via the live
discovery cache, publishes the command on the fleet bus, correlates the reply on
a per-correlation channel **established before publish**, and feeds the parsed
Coach output into the gating layer (FEAT-FORGE-004 downstream). The feature is
strongly invariant-driven — subscribe-before-publish, write-before-send, PubAck
≠ success, exactly-once reply, snapshot stability — which makes the architecture
choice consequential.

**Recommended approach**: **Option 1 — Pure-domain `forge.dispatch` package with
a thin NATS adapter**, mirroring the existing `forge/discovery/` (domain) +
`forge/adapters/nats/` (transport) split. This option keeps every invariant
testable against the existing `FakeNatsClient` harness, reuses the already-shipped
`resolve()` and `DiscoveryCache`, lands the missing `correlate_outcome()` helper
in the domain layer where the `CapabilityResolution` model already lives, and
produces a clean seam for the dispatch callback that `pipeline_consumer.py`
already injects but does not implement.

**Aggregate complexity**: 8/10. **Estimated effort**: 26–34 hours solo. **Subtask
count**: 12. **Wave count**: 5.

---

## 1. Codebase State (from Phase 1 inventory)

### Already in place (FEAT-FORGE-002 substrate)

- `src/forge/discovery/resolve.py` — pure resolution algorithm (exact-tool →
  intent-fallback @ 0.7 → tie-break by trust tier → confidence → queue depth).
  Used unchanged.
- `src/forge/discovery/cache.py` — async-locked in-memory `DiscoveryCache`
  implementing `FleetEventSink`. `snapshot()` returns immutable view used by
  resolver. **The snapshot semantics underwrite the snapshot-stability invariant
  for free** (E.snapshot-stability scenario).
- `src/forge/discovery/models.py` — `CapabilityResolution` with `match_source`,
  `competing_agents`, **and an already-declared `outcome_correlated: bool` field**
  with no writer. Persistence-ready.
- `src/forge/adapters/nats/pipeline_consumer.py` — defines
  `DispatchBuild = Callable[[BuildQueuedPayload, AckCallback], Awaitable[None]]`
  injection point. **Caller is responsible for providing the callable**. This is
  the dispatch trigger seam.
- `src/forge/adapters/nats/fleet_watcher.py` — already populates the cache via
  fleet-lifecycle subscription. No change needed.
- `tests/bdd/conftest.py` — `FakeNatsClient` records `(topic, payload)` pairs
  and supports correlation routing. The harness can already test
  subscribe-before-publish ordering by inspecting recording order.

### Missing (this feature delivers)

- **The dispatch trigger** — the `DispatchBuild` implementation that calls
  `resolve()` against the cache snapshot.
- **Correlation registry** — per-dispatch correlation IDs, owned subscriptions,
  reply channel binding, source-identifier authentication, exactly-once
  acceptance.
- **Reply parsing** — Coach top-level-preferred / nested-fallback extraction,
  malformed-envelope handling, missing-Coach-score fallback to FLAG_FOR_REVIEW.
- **Timeout coordinator** — local hard-timeout (900s default) cut-off,
  unsubscribe-on-timeout, late-reply suppression.
- **Retry coordinator** — fresh correlation per attempt, additional-context
  propagation, retry-attempt recording on the resolution record.
- **Async-mode polling** — run-identifier handling and status-tool polling
  convergence.
- **Outcome correlation writer** — the `correlate_outcome()` referenced by
  `CapabilityResolution` docstrings but never implemented.
- **Degraded-path synthesis** — when no specialist resolves, produce a synthetic
  "unresolved" outcome that the reasoning loop consumes as a normal stage outcome.

---

## 2. Technical Options

### Option 1 — Pure-domain `forge.dispatch` package + thin NATS adapter (RECOMMENDED)

**Shape**:

```
src/forge/dispatch/
├── __init__.py
├── orchestrator.py     # Dispatch lifecycle: resolve → subscribe → publish → wait → parse
├── correlation.py      # CorrelationRegistry: per-dispatch subscriptions, exactly-once gate
├── reply_parser.py     # Coach top-level/nested extraction, FLAG_FOR_REVIEW fallback
├── timeout.py          # Local hard-timeout (900s), unsubscribe-on-timeout
├── retry.py            # Fresh-correlation retry coordinator (no fixed max)
├── outcome.py          # correlate_outcome() — links resolution → gate decision
└── models.py           # DispatchAttempt, DispatchOutcome, CorrelationKey

src/forge/adapters/nats/
└── specialist_dispatch.py   # NATS adapter: binds domain orchestrator to JetStream
```

**Pros**:
- Mirrors the proven `forge/discovery/` (domain) + `forge/adapters/nats/`
  (transport) split. Architectural symmetry minimises onboarding cost.
- Every invariant (subscribe-before-publish, write-before-send, exactly-once,
  source-authenticity, snapshot-stability, unsubscribe-on-timeout) is testable
  in pure domain tests against `FakeNatsClient`. **The 33 BDD scenarios map
  almost 1:1 onto this layout.**
- `CorrelationRegistry` is the natural home for the security invariant
  (reply-source authenticity) and the data-integrity invariant (exactly-once
  reply handling) — both belong on the same data structure.
- `correlate_outcome()` lands in `dispatch/outcome.py` next to the resolution
  record's persistence layer, satisfying the `CapabilityResolution` docstring
  contract and giving the gating feature (FEAT-FORGE-004) a clean import.
- `retry.py` is reasoning-model-driven (no fixed max — per ASSUM-005). The
  retry coordinator is a pure function over the previous attempt's outcome and
  the additional context, which keeps the reasoning loop in charge.

**Cons**:
- Adds a new top-level package. Slightly more file count than Option 2.
- The seam between `dispatch/` and `discovery/` must be spelled out clearly
  (dispatch reads cache snapshots; cache never imports dispatch).

**Effort**: 26–34 hours.
**Aggregate complexity**: 8/10.

---

### Option 2 — Inline dispatch in `pipeline_consumer.py`

**Shape**: Implement the `DispatchBuild` callback directly inside
`adapters/nats/pipeline_consumer.py`, expanding its responsibility from "consume
build-queued events" to "consume + dispatch + correlate".

**Pros**:
- Fewer new files.
- One module owns the full inbound-to-outbound NATS flow.

**Cons (decisive)**:
- **Violates the discovery-package precedent.** The codebase already chose
  domain-vs-transport separation; inverting it here creates an inconsistency
  reviewers will trip on for years.
- **Non-trivial domain logic ends up in the transport layer.** Correlation
  registry, retry coordinator, and reply parser are not transport concerns.
- **BDD invariant tests become coupled to NATS imports.** The
  subscribe-before-publish, exactly-once, and source-authenticity scenarios are
  domain invariants the spec deliberately describes in domain terms (per the
  spec's own comment: "transport primitives appear only as capability
  observations, not implementation steps").
- `correlate_outcome()` would not have a natural home — it would either live
  alongside the consumer (wrong layer) or get back-fitted into `discovery/`
  later (re-work).

**Effort**: 22–26 hours (cheaper short-term).
**Hidden cost**: significant rework when FEAT-FORGE-004 (gating) needs to import
correlation/outcome helpers from a transport adapter.

---

### Option 3 — State-machine-driven dispatch (push from `pipeline.py`)

**Shape**: Extend `pipeline.py`'s `PipelineLifecycleEmitter` so that stage
transitions trigger dispatch directly, rather than the bus-driven path through
`pipeline_consumer.py`.

**Pros**:
- Conceptually elegant: the state machine "knows" when a stage needs a
  specialist.
- Dispatch follows the same lifecycle-emission shape as the existing 8 publish
  methods.

**Cons (decisive)**:
- **Wrong direction.** FEAT-FORGE-002 deliberately models dispatch as
  consumer-triggered (build-queued → consumer → dispatch callback). The state
  machine emits *outcomes*, not commands. Reversing this changes the upstream
  contract.
- **Couples the state machine to the fleet bus.** Today, `pipeline.py` is
  transport-agnostic. Dispatch from inside the state machine would either drag
  NATS imports into the domain or require a second injection point.
- **The dispatch callback seam already exists** in `pipeline_consumer.py` —
  Option 3 leaves it dangling and adds a second seam. Two ways to dispatch is
  worse than one.
- **The retry path becomes ambiguous.** Reasoning-model-driven retry (ASSUM-005)
  needs to live above the state machine, not inside it.

**Effort**: 30–38 hours (highest — refactors FEAT-FORGE-002's already-shipped
contract).

---

## 3. Recommendation

**Adopt Option 1.** Justification against the **quality** trade-off priority:

| Criterion | Option 1 | Option 2 | Option 3 |
|---|---|---|---|
| Invariant testability against domain doubles | ✅ all 33 scenarios | ⚠️ couples to transport mocks | ⚠️ couples to state machine |
| Architectural symmetry with shipped code | ✅ matches discovery/ | ❌ inverts pattern | ❌ inverts pattern |
| `correlate_outcome()` natural home | ✅ dispatch/outcome.py | ❌ no natural home | ⚠️ state-machine intrusion |
| Downstream import cleanliness (FEAT-FORGE-004) | ✅ pure domain | ❌ transport import | ⚠️ state-machine import |
| LES1 PubAck-not-success isolation | ✅ in correlation.py | ⚠️ buried in consumer | ⚠️ buried in state machine |
| Consumer dispatch-callback seam reuse | ✅ reused as-is | ✅ reused as-is | ❌ left dangling |

Option 1 wins on every criterion that matters when correctness is preferred over
delivery speed. The 4 extra hours over Option 2 buy invariant isolation that
will pay back many times during FEAT-FORGE-004 (gating) and any future fleet-bus
refactor.

---

## 4. Risk Analysis

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | **Subscribe-before-publish ordering bug** — the canonical LES1 failure | Medium | Critical | Domain-side `CorrelationRegistry.bind()` returns a "ready" handle; `orchestrator.dispatch()` refuses to publish until `bind()` returns. Recording-order assertion in `FakeNatsClient` is mandatory in the BDD step. |
| R2 | **Exactly-once reply violation under duplicate delivery** | Medium | High | `CorrelationRegistry` keeps a per-correlation `accepted: bool` flag; subsequent replies on the same correlation are dropped silently. Test against scenario E.duplicate-reply-idempotency. |
| R3 | **Reply-source authenticity bypass** — a reply on the right correlation but from the wrong agent | Low | Critical (security) | Resolution record stores `matched_agent_id`; correlation registry binds it; reply parser rejects replies whose source ≠ matched agent. Test against scenario E.reply-source-authenticity. |
| R4 | **Sensitive-parameter leak into resolution record** | Medium | High (security) | `CapabilityResolution` persistence layer must filter parameters by a `sensitive: bool` flag declared on the dispatch parameter schema. Schema-level (not orchestrator-level) filter avoids "forget to scrub" bugs. Test against scenario E.sensitive-parameter-hygiene. |
| R5 | **Timeout race** — reply arrives just inside / just outside the local 900s window | High | Medium | `Clock` protocol (already in `discovery/protocol.py`) makes this deterministic in tests. Boundary scenarios B.just-inside-timeout / B.just-outside-timeout become exhaustive coverage. |
| R6 | **Cache-staleness during in-flight resolution** | Low | Medium | `DiscoveryCache.snapshot()` already returns an immutable view. The snapshot-stability invariant is inherited from FEAT-FORGE-002. **Verify** with E.snapshot-stability scenario, do not re-implement. |
| R7 | **Retry-induced duplicate work** | Medium | Medium | Each retry uses a **fresh correlation** (per spec). The original attempt's resolution record is preserved; the retry creates a sibling record linked via `retry_of: <prev_resolution_id>`. No correlation overlap by construction. |
| R8 | **Registry outage stalls the pipeline** | Low | High | Cache returns the last-known snapshot when the live registry is unreadable (FEAT-FORGE-002 already handles this). Resolution layer marks the snapshot as stale; the reasoning loop sees the staleness flag in the outcome. |
| R9 | **Bus disconnect hangs the pipeline silently** | Medium | High | NATS adapter's connection state is observed by the timeout coordinator; a disconnect promotes the dispatch to "failed" and surfaces the outcome to the reasoning loop. The hard timeout is the floor. |
| R10 | **PubAck-not-success regression** — the canonical LES1 mistake | High | Critical | Single isolated test in `dispatch/correlation.py` BDD: PubAck arrives on the audit stream → assert no completion event is fired. Belt-and-braces: also assert at the orchestrator level. |
| R11 | **Async-mode polling diverges from sync-reply path** | Medium | Medium | `DispatchOutcome` is a sum type (sync-result \| async-pending \| degraded \| error). Polling only flips `async-pending → sync-result`. One outcome contract for both modes. |

---

## 5. Architecture Boundaries

### Read from FEAT-FORGE-001 (Pipeline State Machine & Configuration)
- SQLite `forge_pipeline_history` schema (assumed extensible — `CapabilityResolution`
  records persist alongside pipeline events). **No schema change required if the
  persistence layer accepts opaque resolution records;** verify in TASK-SAD-002.

### Read from FEAT-FORGE-002 (NATS Fleet Integration)
- `DiscoveryCache.snapshot()` (read-only view at dispatch time)
- `FleetEventSink` protocol (already wired; we don't re-subscribe)
- `pipeline_consumer.py`'s `DispatchBuild` callback type (we provide the callable)
- Heartbeat view (read-only — used by `degraded-status exclusion` resolver path,
  which is already in `resolve.py`)
- Fleet bus client abstraction (used by the new NATS adapter only)

### Written by FEAT-FORGE-003 (this feature)
- `CapabilityResolution` records (new write path)
- `outcome_correlated` flag on existing records (via `correlate_outcome()`)
- Dispatch commands on `agents.command.{agent_id}` (singular convention per
  Graphiti `architecture_decisions` group — adopted fleet-wide)
- Per-correlation reply subscriptions (transient; lifetime = dispatch attempt)
- Pipeline-event publishes for dispatch lifecycle (synthesised stage outcomes
  fed to the existing pipeline emitter)

### Not touched
- State machine transitions in `pipeline.py`
- Fleet-lifecycle subscription in `fleet_watcher.py`
- Pipeline event publishing in `pipeline_publisher.py`
- The resolver in `discovery/resolve.py` (used unchanged)

---

## 6. Scenario Coverage (33/33)

All 33 BDD scenarios are mapped to at least one task. The mapping is at a
group level here; per-scenario task assignment lives in `IMPLEMENTATION-GUIDE.md`
under §5 and is what `Step 11` will tag back into the `.feature` file.

| Group | Scenario count | Primary task(s) |
|---|---|---|
| A — Key Examples (smoke + happy paths) | 5 | TASK-SAD-006, TASK-SAD-007, TASK-SAD-008, TASK-SAD-009, TASK-SAD-011 |
| B — Boundary Conditions | 6 | TASK-SAD-003, TASK-SAD-004 (resolver boundaries already covered in FEAT-FORGE-002 unit tests; this feature adds the **timeout** boundaries) |
| C — Negative Cases | 7 | TASK-SAD-005, TASK-SAD-006, TASK-SAD-007 |
| D — Edge Cases | 7 | TASK-SAD-002, TASK-SAD-003, TASK-SAD-005, TASK-SAD-010 |
| E — Security/Concurrency/Data Integrity/Integration | 8 | TASK-SAD-003, TASK-SAD-005, TASK-SAD-009, TASK-SAD-011 |

**Smoke scenarios (2)**: A.exact-tool-dispatch, A.coach-output-parsing — both
land in TASK-SAD-011 (BDD smoke wiring).

---

## 7. Effort Estimation

| Component | Hours |
|---|---|
| TASK-SAD-001 — Dispatch package skeleton, models, package wiring | 1.5 |
| TASK-SAD-002 — Resolution-record persistence + sensitive-param scrubbing | 3 |
| TASK-SAD-003 — `CorrelationRegistry` (subscribe-before-publish, exactly-once, source-auth) | 4 |
| TASK-SAD-004 — Timeout coordinator (hard-timeout, unsubscribe-on-timeout, late-reply suppression) | 2.5 |
| TASK-SAD-005 — Reply parser (Coach top-level/nested, FLAG_FOR_REVIEW fallback, malformed envelope) | 3 |
| TASK-SAD-006 — Dispatch orchestrator (resolve → bind → publish → wait → parse → outcome) | 4 |
| TASK-SAD-007 — Retry coordinator (fresh correlation, additional context, retry-attempt recording) | 2.5 |
| TASK-SAD-008 — Async-mode polling (run-identifier, status-tool convergence) | 2 |
| TASK-SAD-009 — `correlate_outcome()` writer + degraded-path synthesis | 2.5 |
| TASK-SAD-010 — NATS adapter `specialist_dispatch.py` (binds domain to JetStream) | 3 |
| TASK-SAD-011 — BDD smoke + key-example pytest wiring | 2 |
| TASK-SAD-012 — Contract & seam tests for the dispatch boundary | 2 |
| **Total** | **~32** |

**Pace assumption**: solo developer, 6 productive hours per day, ~5–6 days
elapsed.

---

## 8. Findings

1. **Architecture is well-prepared for this feature** — the dispatch callback
   seam, the resolution algorithm, and the cache snapshot semantics are all
   already in place. The cost of FEAT-FORGE-003 is concentrated on the
   correlation, retry, and reply-parsing concerns — not on the resolver itself.
2. **The `outcome_correlated` field on `CapabilityResolution` is dangling** —
   declared with no writer and a docstring that promises a `correlate_outcome()`
   helper. This feature lands that helper.
3. **Subscribe-before-publish is the single most important invariant** — it is
   the LES1 lesson that motivates the entire feature. It must be testable in
   pure-domain tests, not only in transport-coupled tests.
4. **The 33 BDD scenarios are exhaustively boundary-driven** — the scenario set
   is unusually well-balanced (5 key examples, 6 boundaries, 7 negatives, 7 edges,
   8 sec/concurrency/integration). The implementation plan follows the same
   shape: one task per concern surface.
5. **Sensitive-parameter hygiene must be schema-driven, not orchestrator-driven**
   — relying on the orchestrator to remember to scrub parameters is a class-A
   "forget once" bug. The dispatch parameter schema must declare `sensitive: bool`
   and the persistence layer must filter on it.
6. **Reasoning-model-driven retry (ASSUM-005) is the right design.** A fixed
   max-retry at the dispatch layer would pre-empt the reasoning loop's judgement
   about whether a retry is worth attempting. The dispatch layer recommends
   nothing about retry policy; it just executes whatever the reasoning loop
   asks for.
7. **The trust-tier ranking is authoritative** — security relies on it. The
   resolver already enforces `core > specialist > extension`; the dispatch layer
   must preserve this when surfacing the `competing_agents` list (no reordering
   that could mislead a reviewer).
8. **PubAck-not-success deserves a dedicated test** — it is the canonical LES1
   failure. A single targeted BDD step ("when the bus acks the publish but no
   reply arrives") exercises the entire correlation path.
9. **The async-mode polling path converges with the sync-reply path** at the
   `DispatchOutcome` level. The orchestrator does not need separate code paths
   for the two modes — only the polling loop differs.
10. **The retry coordinator must record sibling resolutions, not overwrite the
    original.** Each attempt is a discrete record linked via `retry_of`. This
    preserves the audit trail and makes "concurrent dispatches to same agent"
    (D.concurrent-dispatches-same-agent) trivial — they never share a record.

---

## 9. §4: Integration Contracts (cross-task data dependencies)

### Contract: `CapabilityResolution` record schema
- **Producer**: TASK-SAD-001 (defines the dispatch-side projection)
- **Consumer**: TASK-SAD-002 (persistence), TASK-SAD-009 (outcome correlation),
  TASK-SAD-006 (orchestrator writes), TASK-SAD-007 (retry — writes sibling)
- **Artifact type**: Pydantic model + persistence schema
- **Format constraint**: Reuses `forge.discovery.models.CapabilityResolution`
  unchanged — append-only field additions allowed (`retry_of: Optional[str]` is
  the only new field). **Existing FEAT-FORGE-002 callers must continue to work.**
- **Validation**: Coach verifies `pydantic` model schema test asserts the union
  of FEAT-FORGE-002 and FEAT-FORGE-003 fields; no field is removed or renamed.

### Contract: `CorrelationKey` (per-dispatch correlation identifier)
- **Producer**: TASK-SAD-003 (`CorrelationRegistry.bind()` returns it)
- **Consumer**: TASK-SAD-006 (orchestrator threads it into the publish payload),
  TASK-SAD-010 (NATS adapter uses it as the reply-channel suffix)
- **Artifact type**: opaque string (UUID4 hex, no embedded semantics)
- **Format constraint**: 32 lowercase hex characters; **no embedding of agent
  IDs, timestamps, or other PII** (security: replies must not be guessable from
  external knowledge of the request).
- **Validation**: Coach verifies `re.fullmatch(r"[0-9a-f]{32}", correlation_key)`
  in adapter and registry tests.

### Contract: `DispatchOutcome` (sum type)
- **Producer**: TASK-SAD-006 (orchestrator), TASK-SAD-008 (polling), TASK-SAD-009
  (degraded-path synthesis)
- **Consumer**: FEAT-FORGE-004 gating layer (downstream feature) and the
  reasoning loop
- **Artifact type**: discriminated union `Literal["sync_result", "async_pending",
  "degraded", "error"]`
- **Format constraint**: every variant carries `resolution_id` and `attempt_no`;
  `sync_result` carries `coach_score: float | None`, `criterion_breakdown: dict`,
  `detection_findings: list`; `degraded` carries `reason: str`; `error` carries
  `error_explanation: str`. **No undocumented fields.**
- **Validation**: Coach verifies each variant has the documented fields; CI
  rejects new fields without a corresponding doc update.

### Contract: dispatch-command envelope on `agents.command.{agent_id}`
- **Producer**: TASK-SAD-010 (NATS adapter) using params from TASK-SAD-006
- **Consumer**: external specialist agents (out of scope here) and FEAT-FORGE-002
  test doubles
- **Artifact type**: NATS message
- **Format constraint**: subject is **singular** `agents.command.{agent_id}`
  (per Graphiti `architecture_decisions` group, adopted fleet-wide). Reply
  channel is per-correlation: `agents.result.{agent_id}.{correlation_key}`.
  Headers carry `correlation_key`, `requesting_agent_id`, `dispatched_at`.
- **Validation**: Coach verifies subject regex
  `^agents\.command\.[a-z0-9-]+$` and reply subject regex
  `^agents\.result\.[a-z0-9-]+\.[0-9a-f]{32}$`.

### Contract: `correlate_outcome()` signature
- **Producer**: TASK-SAD-009
- **Consumer**: FEAT-FORGE-004 gating layer (it will call this when the gate
  decision is made)
- **Artifact type**: pure function
- **Format constraint**: `correlate_outcome(resolution_id: str, gate_decision_id:
  str) -> CapabilityResolution` — idempotent (calling twice with the same args
  is a no-op). Sets `outcome_correlated=True`.
- **Validation**: Coach verifies idempotency test asserts that two consecutive
  calls produce equal records.

---

## 10. Subtask Breakdown

12 tasks across 5 waves. Detailed wave breakdown is in
`IMPLEMENTATION-GUIDE.md`. Summary:

```
Wave 1 (foundations, can parallelise):
  TASK-SAD-001  Dispatch package skeleton + models                 (declarative, 2)
  TASK-SAD-002  Resolution-record persistence + sensitive-param    (feature, 5)
                scrub

Wave 2 (correlation + parsing, can parallelise):
  TASK-SAD-003  CorrelationRegistry (subscribe-before-publish,     (feature, 7)
                exactly-once, source-auth)
  TASK-SAD-004  Timeout coordinator                                (feature, 5)
  TASK-SAD-005  Reply parser                                       (feature, 5)

Wave 3 (orchestration, sequential — depends on Wave 2):
  TASK-SAD-006  Dispatch orchestrator                              (feature, 7)
  TASK-SAD-007  Retry coordinator                                  (feature, 5)

Wave 4 (specialist edges, can parallelise):
  TASK-SAD-008  Async-mode polling                                 (feature, 4)
  TASK-SAD-009  correlate_outcome() + degraded-path synthesis      (feature, 5)
  TASK-SAD-010  NATS adapter specialist_dispatch.py                (feature, 6)

Wave 5 (verification, can parallelise):
  TASK-SAD-011  BDD smoke + key-example pytest wiring              (testing, 4)
  TASK-SAD-012  Contract & seam tests for the dispatch boundary    (testing, 5)
```

---

## 11. Decision Options

The following options will be presented at the decision checkpoint:

- **[A]ccept** — approve findings, save report, no implementation tasks created
- **[R]evise** — re-run review with different focus or deeper analysis
- **[I]mplement** — create the 12-task feature structure plus the
  `.guardkit/features/FEAT-FORGE-003.yaml` orchestration file and tag the
  feature scenarios with `@task:` tags via the BDD linker
- **[C]ancel** — discard the review

---

## Appendix A — Context Used (Graphiti)

**ADRs and architecture decisions consulted**:
- `forge` (architecture_decisions) — Forge manages specialist-agent deployments;
  fleet-wide adoption of singular `agents.command.{agent_id}` /
  `agents.result.{agent_id}` convention.
- `agents.command.{agent_id}` (architecture_decisions) — singular convention
  adopted fleet-wide; specialists subscribe and publish results.
- `nats-core` — singular convention shipping; 98% test coverage; missing some
  payloads but the dispatch-side ones are not in the gap list.
- `forge` is JetStream-native — pipeline state lives in NATS KV bucket;
  reflects the spec's "transport primitives are observations, not domain steps".
- `specialist-agent` — supports multiple roles (Product Owner, Architect)
  through distinct deployments; each registers independently and publishes
  results in Forge-compatible shape.

**Past failure patterns checked for recurrence**:
- TASK-PEX-018 (extended retry backoff for long-running sessions) — informed
  the timeout-coordinator design (TASK-SAD-004) but does not apply directly
  since reasoning-model-driven retry replaces fixed backoff.
- TASK-PEX-020 (Phase B Coach-to-Player retry feedback split into modes) —
  informed the additional-context-on-retry shape (TASK-SAD-007); the dispatch
  layer carries whatever context the reasoning loop provides without classifying
  it.

**Similar past reviews**:
- TASK-REV-POEX, TASK-REV-4D012 (specialist-agent reviews) — confirmed Forge
  calls distinct agents per role via `--role` flag and that result shapes are
  Forge-compatible. No conflicts with this plan.

---

## Review Metadata

```yaml
review_results:
  mode: decision
  depth: standard
  recommended_option: "Option 1 — Pure-domain forge.dispatch package with thin NATS adapter"
  estimated_hours: "26-34"
  subtask_count: 12
  wave_count: 5
  aggregate_complexity: 8
  findings_count: 10
  risks_count: 11
  integration_contracts_count: 5
  scenario_coverage: 33/33
  report_path: .claude/reviews/TASK-REV-SAD3-review-report.md
  completed_at: 2026-04-25T00:00:00Z
```
