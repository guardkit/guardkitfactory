# Review Report — TASK-REV-CG44

## Executive Summary

**Feature**: FEAT-FORGE-004 Confidence-Gated Checkpoint Protocol
**Mode**: Decision (standard depth)
**Scope**: All areas (full sweep), quality trade-off priority
**Specific concerns**: constitutional guarantees, NATS integration, degraded mode, idempotency
**Outcome**: **Option 1 — Pure-domain `forge.gating` with thin NATS approval adapter** recommended.
**Estimated effort**: 22–28 focused hours, 12 subtasks across 5 waves.
**Aggregate complexity**: 8/10.

The feature is well-specified by `DM-gating.md` (data model, invariants, pure
function signature) and `API-nats-approval-protocol.md` (subjects, payloads,
rehydration contract, timeout/CLI behaviour). Two ADRs already pin the design:
**ADR-ARCH-019** mandates no static thresholds (reasoning-model emergent gating),
and **ADR-ARCH-026** mandates two-layer constitutional enforcement. The decision
is therefore primarily about **module layout, the reasoning-model invocation
seam, the synthetic-decision injection path for CLI steering, and durable-record
sequencing under publish failure** — not protocol design.

The design is internally consistent and the upstream features
(FEAT-FORGE-001/002/003) supply exactly the seams this feature needs. No
contract gaps surfaced; one assumption (ASSUM-003 — max-wait-ceiling fallback)
is genuinely deferred to `forge-pipeline-config` and does not block this
feature's first landing.

## Review Details

- **Task**: TASK-REV-CG44 — Plan: Confidence-Gated Checkpoint Protocol
- **Mode**: `decision`
- **Depth**: `standard`
- **Clarification**: Context A captured — Focus=All, Tradeoff=Quality, Concerns=[constitutional, nats, degraded, idempotency], Upstream=Medium, Scenario coverage check=Yes
- **Reviewer**: orchestrator with design-contract analysis (no external agents invoked — DM-gating.md and API-nats-approval-protocol.md were authoritative)
- **Knowledge graph**: not queried (existing design contracts and ADRs were richer than likely Graphiti context for this greenfield module)

## Findings

### F1 — Gate evaluation is a pure function with reasoning-model assembly inside

`DM-gating.md §3` pins `evaluate_gate()` as a **pure function** with all inputs
named and the output a `GateDecision`. Per ADR-ARCH-019, no static
`forge.yaml.gate_defaults` exist — thresholds emerge from priors via a
reasoning-model prompt assembled inside the function. This is a hard boundary:
the reasoning-model invocation must be a dependency-injected callable so the
function remains pure, deterministic in tests, and free of I/O imports. The
test surface for this single function dominates the feature's correctness
budget.

### F2 — Constitutional override is the first branch and lives in two places

`DM-gating.md §3` and `API-nats-approval-protocol.md §8` are explicit: the
hardcoded executor branch fires first when `target_identifier in {"review_pr",
"create_pr_after_review"}` and returns `GateDecision(mode=MANDATORY_HUMAN_APPROVAL,
auto_approve_override=True)` regardless of score or priors. The complementary
prompt-layer rule (`SAFETY_CONSTITUTION` block) lives in the system prompt
shipped with the orchestrator. **Both wirings must be independently testable
and independently regression-checked**: scenario E2 (Group E, `@security
@regression`) requires that disabling either layer in isolation still produces
`MANDATORY_HUMAN_APPROVAL` plus a constitutional-regression signal. This is the
single highest-stakes test in the feature.

### F3 — Schemas ride on `nats-core`; no Forge-side payload redeclaration

`API-nats-approval-protocol.md §3.1/§4.1` reuses `nats-core.MessageEnvelope` +
`nats-core.ApprovalRequestPayload` / `ApprovalResponsePayload`. The
`details: dict[str, Any]` extension is a **convention, not a schema** — Forge
populates the dict with the eight documented keys (`build_id`, `feature_id`,
`stage_label`, `gate_mode`, `coach_score`, `criterion_breakdown`,
`detection_findings`, `rationale`, `evidence_priors`, `artefact_paths`,
`resume_options`). A small builder helper (`_build_approval_details(...)`)
inside the adapter is sufficient — no new Pydantic model is warranted. This
mirrors the FEAT-FORGE-002 schema-ownership pattern (F2 of TASK-REV-NF20).

### F4 — Rehydration helper is the contract that hides serde mode

DDR-002 / `API-nats-approval-protocol.md §4.2` mandate `resume_value_as(
ApprovalResponsePayload, raw)` at every call-site. The helper is `isinstance`
short-circuit + Pydantic validation. **Every place that consumes
`interrupt()`'s resume value must route through this helper** — direct
attribute access on `dict` is a regression. The scenario outline in Group D
(`Approval responses are handled identically whether they arrive typed or as a
bare mapping`) is the contract test for this.

### F5 — Resume-on-decision integration with FEAT-FORGE-001 paused state

Three of the four gate modes drive a state transition that is owned by
FEAT-FORGE-001:
- `FLAG_FOR_REVIEW` → enter `PAUSED`
- `HARD_STOP` → enter terminal `FAILED`
- `MANDATORY_HUMAN_APPROVAL` → enter `PAUSED` (same transition mechanism, distinct origin)
- `AUTO_APPROVE` → no transition; build continues

The state machine in FEAT-FORGE-001 must already expose `enter_paused(build_id,
gate_decision)`, `resume_from_paused(build_id, response)`, and
`fail_with_decision(build_id, gate_decision)` for this feature to land
non-invasively. **Pause-and-publish must be a single atomic step from the
caller's perspective** (Group E `@concurrency @data-integrity`): scenario
E4 demands the bus carries the request before any status query reports
"paused-without-request". Concretely: write SQLite paused row → publish
`ApprovalRequestPayload` → return — and on publish failure, the paused-row
write still wins (SQLite is the source of truth; bus is a notification).

### F6 — CLI steering is synthetic-response injection at the same boundary

`forge cancel` and `forge skip` (`API-nats-approval-protocol.md §7`) inject
synthetic `ApprovalResponsePayload` instances into the same response-handling
path that real Rich responses traverse. They must therefore:
- Pass through the **same idempotency check** on `request_id`
- Pass through the **same rehydration helper**
- Be **distinguishable in the persisted record** (`responder="rich"`, `reason="cli cancel"` / `"cli skip"`)

This means the synthetic injection point is a single function (likely
`forge.gating.synthetic_response_injector` or living on the approval consumer)
that produces an `ApprovalResponsePayload` and feeds it into the same queue
the NATS subscriber feeds. **No parallel resume code path** — that would
silently bypass idempotency.

### F7 — Idempotency is a short-TTL set keyed on `request_id`, owned by responders

`API-nats-approval-protocol.md §6` and ASSUM-006 are explicit: **responders**
deduplicate on `request_id` with first-response-wins semantics; Forge re-emits
the request on crash recovery and that re-emission must use the same
`request_id`. Forge's responsibilities here are minimal:
- **Stable `request_id` derivation**: must be deterministic from
  `(build_id, stage_label, attempt_count)` so re-emission produces an
  identical id
- **Server-side dedup buffer**: the response subscriber must hold a short-TTL
  set of seen `request_id`s so two near-simultaneous responses for the same
  paused build resolve to one outcome (Group E `@concurrency`); the surplus
  responses are recorded as duplicates
- **Re-emission on restart**: the SQLite-backed `paused_builds` view drives
  re-publishing on boot using the persisted `request_id` (Group D
  `@regression` crash-recovery)

The dedup buffer lives in `forge.adapters.nats.approval_subscriber`, not in
the domain.

### F8 — Degraded mode is a Pydantic-enforced invariant, not a soft rule

`DM-gating.md §6` makes the post-condition explicit: `coach_score is None ⇒
mode in {FLAG_FOR_REVIEW, HARD_STOP, MANDATORY_HUMAN_APPROVAL}`. This is a
**post-condition check inside `evaluate_gate()`**, not an external invariant.
The reasoning-model prompt is allowed to ask for any of those three modes
when `coach_score` is `None`; the `degraded_mode: bool = True` flag is set
on the resulting `GateDecision`. Group D `@regression` requires the degraded
marker to appear on the stored decision for later review. **The post-condition
must raise (programmer error) rather than silently coerce** — silent coercion
in degraded mode is exactly the bypass class ADR-ARCH-026 belt+braces is
designed to prevent.

### F9 — Calibration adjustments are filtered at the read boundary

`DM-gating.md §6` invariant: unapproved `CalibrationAdjustment` instances
must not be retrieved by `evaluate_gate()`. The filter sits in
`forge.adapters.graphiti.read_adjustments(approved_only=True)`, not in the
gate evaluator itself — keeps the domain pure. Group C `@negative` covers
the "unapproved adjustment is invisible" scenario at the read seam.

### F10 — Durable recording wins over notification publish

Group E `@data-integrity @regression` (scenario "A gate decision is recorded
durably even if the notification publish fails") mandates SQLite-first,
publish-second sequencing. **The SQLite write of `GateDecision` (mirrored
into `stage_log.details_json["gate"]`) must complete before the bus publish
is attempted**, and a publish failure must surface as an operational signal
rather than rolling back the recorded decision. This matches FEAT-FORGE-002
F6 — same architectural pattern: the durable substrate is the source of
truth; the bus is a derived notification stream.

### F11 — Wait time defaults are configuration, not behaviour

ASSUM-001 (300s default) and ASSUM-002 (3600s ceiling via
`forge.yaml.approval.max_wait_seconds`) are configuration values that flow
through `forge.config` (already established by FEAT-FORGE-001). The
refresh-within-ceiling loop is a separate concern from `evaluate_gate()` —
it lives in the approval subscriber's wait loop. ASSUM-003 (behaviour at
the ceiling) is genuinely deferred to `forge-pipeline-config`; this feature
should treat the ceiling-reached event as "publish a final
`ApprovalRequestPayload` carrying a configurable fallback marker and let the
state machine consume it" — actual fallback semantics are out of scope.

### F12 — Scenario coverage is complete; no gaps surfaced

The 32 scenarios cover all four gate modes (Group A), all four decision
outcomes (approve/reject/override/duplicate), constitutional override at both
PR-review and PR-create (Groups A + C), criterion-extreme boundaries (Group
B), degraded mode (Group B + D), idempotency under crash recovery (Group D),
CLI steering (Group D), per-build channel routing (Group D), unrecognised
responder (Group E), two-layer constitutional regression (Group E), and the
publish-failure-but-decision-recorded data-integrity case (Group E).
**No coverage gaps identified.** One observation: the rehydration scenario
outline (typed vs bare mapping) is the contract test for DDR-002 and should
be implemented as a parametrised pytest with both shapes flowing through
`resume_value_as` to prove the no-op path on direct invoke.

## Architecture Boundaries

```
┌────────────────────────────────────────────────────────────────────┐
│  Domain Core (forge.gating)                                        │
│  ───────────────────────────                                       │
│  • evaluate_gate(*, ..., reasoning_model_call) → GateDecision     │
│  • models: GateMode, GateDecision, PriorReference,                 │
│           DetectionFinding, CalibrationAdjustment, ResponseKind   │
│  • _constitutional_override_check (first branch)                  │
│  • _build_reasoning_prompt / _parse_model_response                │
│  • Pydantic invariants enforced via validators                    │
│  ZERO imports from nats_core, nats-py, langgraph                  │
└────────────────────────────────────────────────────────────────────┘
                              ▲
                              │ pure call
                              │
┌────────────────────────────────────────────────────────────────────┐
│  Tool/Wrapper layer (forge.gating.wrappers)                        │
│  • gate_check(target, stage_label, ...) tool wrapper that:        │
│    1. Calls `forge.adapters.graphiti.read_priors()`               │
│    2. Calls `forge.adapters.graphiti.read_adjustments(approved_only=True)`│
│    3. Calls `forge.gating.evaluate_gate(...)` — pure              │
│    4. Calls `forge.adapters.sqlite.write_gate_decision(...)`      │
│    5. If mode != AUTO_APPROVE: emits via approval adapter         │
│    6. If FLAG_FOR_REVIEW or MANDATORY: triggers paused state      │
└────────────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌────────────────────────────────────────────────────────────────────┐
│  Adapter layer (forge.adapters.nats.approval_*)                    │
│  • approval_publisher.publish_request(envelope) [retries, surfaces failure]│
│  • approval_subscriber.await_response(build_id, timeout) → raw     │
│  • synthetic_response_injector.inject_cli_decision(...) → raw      │
│  • dedup buffer keyed on request_id (short TTL)                    │
└────────────────────────────────────────────────────────────────────┘
                              ▲
                              │ rehydrate via resume_value_as
                              │
┌────────────────────────────────────────────────────────────────────┐
│  Resume-value bridge (forge.adapters.langgraph)                    │
│  • resume_value_as(ApprovalResponsePayload, raw) [DDR-002]        │
│    isinstance short-circuit + Pydantic.model_validate fallback    │
└────────────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌────────────────────────────────────────────────────────────────────┐
│  State machine integration (FEAT-FORGE-001)                        │
│  • enter_paused / resume_from_paused / fail_with_decision         │
│  • SQLite stage_log writer with details_json["gate"] mirror       │
│  • Crash-recovery boot reads paused_builds view → triggers re-emit│
└────────────────────────────────────────────────────────────────────┘
```

**Boundaries to preserve:**
1. `forge.gating` imports nothing from `nats_core`, `nats-py`, or `langgraph`
2. `forge.gating.evaluate_gate` is pure; reasoning-model is injected
3. `resume_value_as` is the ONLY way to read `interrupt()` resume values
4. SQLite write of `GateDecision` precedes any bus publish
5. Synthetic CLI decisions feed the same queue real responses do
6. Dedup-on-`request_id` lives in the subscriber, not in the domain

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **R1 — Constitutional regression**: prompt or executor branch silently disabled, allowing PR-review auto-approval | Low | **Catastrophic** (constitutional breach; ADR-ARCH-026 is the project's safety baseline) | Two-layer test (E2): assert each layer alone produces MANDATORY_HUMAN_APPROVAL; CI guard that fails if either layer is removed |
| **R2 — Rehydration drift**: a new call-site reads `interrupt()` resume value as `dict` directly, breaking server-mode | Medium | High (server-mode runs are silently broken; tests passing in direct-invoke hide it) | Lint rule / grep CI guard prohibiting `interrupt()` followed by attribute access; parametrised contract test in Group D scenario outline |
| **R3 — Degraded-mode silent coerce**: post-condition skipped when `coach_score is None`, mode lands as AUTO_APPROVE | Low | High (silent bypass of the degraded invariant) | Pydantic validator on `GateDecision` enforces invariant at construction; `evaluate_gate()` post-condition raises programmer error if violated; Group B + D scenarios are positive coverage |
| **R4 — Idempotency race**: two responses race the dedup set, both observed as winners | Low | Medium (build resumes twice) | Dedup set under asyncio lock; `request_id` is the only key; Group E `@concurrency` scenario is the regression test |
| **R5 — Re-emission diverges**: re-emission generates a new `request_id`, breaking idempotency on Rich's side | Low | High (responders cannot dedup) | `request_id` derivation is pure: `f"{build_id}:{stage_label}:{attempt_count}"` (or equivalent); persisted in SQLite; re-emission reads from SQLite |
| **R6 — SQLite write rolled back on bus failure** (regresses F10) | Medium | High (decision lost on transient bus failure) | Write SQLite first; publish second; publish failure surfaces as operational signal but does NOT propagate to caller; explicit Group E `@data-integrity` test |
| **R7 — Pause-and-publish observed inconsistently** (E4) | Medium | Medium (status query reports paused without request) | Pause + publish form a single async function under the state-machine writer's transaction; status queries that observe `PAUSED` must be ordered after the publish call returns |
| **R8 — Calibration adjustment leak**: an unapproved adjustment is retrieved and shapes a decision | Low | Medium (Rich's calibration model is bypassed) | Filter in `forge.adapters.graphiti.read_adjustments(approved_only=True)`; Group C `@negative` is the scenario; reviewer-side check at read seam, not in domain |
| **R9 — Reasoning-model nondeterminism floods test suite** | Medium | Low | Inject a deterministic test double for reasoning-model in unit tests; reserve real reasoning-model invocation for a small contract-test suite |
| **R10 — Wait-ceiling fallback overspecified** in scope (ASSUM-003) | Low | Low | Treat ceiling as "publish a marker, let state machine decide"; defer concrete fallback to `forge-pipeline-config` |

## Technical Options Analysed

### Option 1 — Pure-domain `forge.gating` with thin NATS approval adapter (RECOMMENDED)

`forge.gating` is a domain-pure module containing models, the pure evaluation
function, and the constitutional override check. A separate
`forge.adapters.nats.approval_publisher` / `approval_subscriber` /
`synthetic_response_injector` ride on top of nats-core. The wrapper layer
(`forge.gating.wrappers`) coordinates: read priors/adjustments → evaluate →
write SQLite → publish/transition.

**Pros**:
- Mirrors the established Forge boundary pattern (FEAT-FORGE-002 split:
  `forge.discovery` pure, `forge.adapters.nats.fleet_*` adapters)
- Pure `evaluate_gate()` is trivially unit-testable with deterministic
  reasoning-model double
- Constitutional override is the first branch — single-file regression test
  surface
- Synthetic CLI injection is a single typed function on the adapter
- Schema redeclaration is zero — `nats-core` owns payloads
- Rehydration via DDR-002 is a single call site per consumer

**Cons**:
- Three adapter files (publisher, subscriber, synthetic injector) plus the
  wrapper layer — slightly more files than Option 2
- Reasoning-model injection requires a `Protocol` or callable type; small
  ergonomic cost

**Risks addressed**: R1, R2, R3, R5, R6, R8 directly via boundary shape.

**Effort**: 22–28 hours, 12 subtasks, 5 waves.

### Option 2 — Single `forge.gating` module with embedded NATS calls

Collapse evaluator and adapters into one module. `evaluate_gate()` would
make NATS publishes and SQLite writes itself.

**Pros**:
- Fewer files; shorter call chains in the happy path

**Cons**:
- Breaks ADR-ARCH-019 implicitly: `evaluate_gate()` is no longer pure
- Tests must mock NATS + SQLite to exercise reasoning logic
- The constitutional-override regression test (E2) becomes harder to
  isolate — both layers live together and a single mock could mask either
- Doesn't match the rest of the codebase's pure-domain / adapter pattern
- Future `forge.gating` callers (e.g. an HTTP control plane) would have
  to either depend on NATS or duplicate evaluation logic

**Risks addressed**: none beyond Option 1; introduces R3 surface (mixed
concerns make degraded-mode tests muddier).

**Recommendation**: Reject. The ergonomics gain is small; the architectural
cost is large.

### Option 3 — Separate package per gate mode

One module per `GateMode`. `auto_approve.py`, `flag_for_review.py`,
`hard_stop.py`, `mandatory_human_approval.py`.

**Pros**:
- Each mode in isolation reads cleanly

**Cons**:
- The whole point of `evaluate_gate()` is that the **mode is the output** —
  it is decided by the reasoning model, not chosen by the caller. Splitting
  into per-mode modules inverts the design and creates a dispatch layer
  that has to make the very decision the function is supposed to make
- Violates the pure-function design in `DM-gating.md §3`

**Recommendation**: Reject. Misreads the design.

## Subtask Breakdown — 12 tasks, 5 waves

### Wave 1 — Foundation (parallel-safe; no cross-dependencies)

| ID | Title | Mode | Complexity | Notes |
|---|---|---|---|---|
| TASK-CGCP-001 | Define `forge.gating` module structure (models, pure function shell, package init) | direct | 3 | Stub `evaluate_gate` raising NotImplementedError; lay down `GateMode`, `GateDecision`, `PriorReference`, `DetectionFinding`, `CalibrationAdjustment`, `ResponseKind` per `DM-gating.md §1`; Pydantic invariants from §6; zero NATS/LangGraph imports |
| TASK-CGCP-002 | Add `forge.config.approval` settings: `default_wait_seconds=300`, `max_wait_seconds=3600` | declarative | 2 | Extend FEAT-FORGE-001 config models; document deferred ASSUM-003 ceiling fallback |
| TASK-CGCP-003 | Define `request_id` derivation helper + tests | direct | 3 | `f"{build_id}:{stage_label}:{attempt_count}"` (or equivalent); pure function; deterministic; lives in `forge.gating.identity` |

### Wave 2 — Pure evaluator (depends on W1.001)

| ID | Title | Mode | Complexity | Notes |
|---|---|---|---|---|
| TASK-CGCP-004 | Implement `forge.gating.evaluate_gate` constitutional-override branch | task-work | 5 | First-branch hardcoded check on `target_identifier in {"review_pr", "create_pr_after_review"}`; sets `auto_approve_override=True`, `mode=MANDATORY_HUMAN_APPROVAL`; standalone unit tests including E2 negative-case (each layer alone) |
| TASK-CGCP-005 | Implement reasoning-model assembly + post-condition checks | task-work | 6 | Reasoning-model is a `Protocol` parameter (DI); assemble prompt from priors + findings + adjustments; parse structured response; enforce degraded-mode invariant (F8); enforce criterion-range invariant; covers Group A/B/C scenarios |

### Wave 3 — Approval adapter (depends on W2.005)

| ID | Title | Mode | Complexity | Notes |
|---|---|---|---|---|
| TASK-CGCP-006 | Implement `forge.adapters.nats.approval_publisher` with `_build_approval_details` helper | task-work | 5 | Publishes `ApprovalRequestPayload` with `details` per `API-nats-approval-protocol.md §3.2`; risk-level derivation per §3.3; SQLite write happens before publish (F10); publish-failure surfaces as operational signal |
| TASK-CGCP-007 | Implement `forge.adapters.nats.approval_subscriber` with dedup buffer | task-work | 6 | Subscribe to `agents.approval.forge.{build_id}.response`; short-TTL dedup set keyed on `request_id`; first-response-wins; concurrent-response test (E `@concurrency`) |
| TASK-CGCP-008 | Implement `forge.adapters.nats.synthetic_response_injector` for CLI steering | task-work | 4 | Injects `ApprovalResponsePayload(decision="reject", responder="rich", reason="cli cancel")` for `forge cancel`; `decision="override", reason="cli skip"` for `forge skip`; routes through same dedup queue as real responses |
| TASK-CGCP-009 | Wire `resume_value_as` rehydration helper at every consumer call-site | task-work | 4 | Per DDR-002 / `API §4.2`; parametrised contract test for typed-vs-dict shapes (Group D); CI grep guard for `interrupt()` followed by `.attribute` |

### Wave 4 — State-machine integration (depends on W3.006, W3.007)

| ID | Title | Mode | Complexity | Notes |
|---|---|---|---|---|
| TASK-CGCP-010 | Wire gate evaluation + paused/failed transitions through FEAT-FORGE-001 state machine | task-work | 6 | `gate_check()` wrapper coordinates: read priors → evaluate → SQLite write → publish/transition; pause-and-publish atomicity (E4); crash-recovery re-emission on boot reading `paused_builds` view (D `@regression`) |

### Wave 5 — End-to-end seam tests (depends on W4.010)

| ID | Title | Mode | Complexity | Notes |
|---|---|---|---|---|
| TASK-CGCP-011 | Contract / seam tests for the approval round-trip across NATS | testing | 5 | `@key-example` happy paths (A1/A2/A3); `@security` two-layer constitutional regression (E2); `@data-integrity` durable-decision-on-publish-failure (E5); `@concurrency` (E3) |
| TASK-CGCP-012 | BDD scenario→task linking + `@task:` tagging of `confidence-gated-checkpoint-protocol.feature` | testing | 3 | Run /feature-plan Step 11 linker; verify all 32 scenarios mapped to one of the 12 tasks (Wave 1–4); R2 oracle activation |

**Aggregate effort**: 22–28 hours.

## Integration Contracts (cross-task data dependencies)

### Contract 1 — `request_id` format

- **Producer**: TASK-CGCP-003 (derivation helper)
- **Consumers**: TASK-CGCP-006 (publisher), TASK-CGCP-007 (subscriber), TASK-CGCP-010 (re-emission)
- **Format**: deterministic string from `(build_id, stage_label, attempt_count)`; SQLite-persisted on first emission so re-emission produces an identical id (R5)
- **Validation**: subscriber's dedup test must pass two responses with the same id and observe one effect

### Contract 2 — `GateDecision` SQLite mirror

- **Producer**: TASK-CGCP-005 (`evaluate_gate` returns the decision)
- **Consumer**: TASK-CGCP-010 (state-machine wrapper writes to SQLite `stage_log.details_json["gate"]` AND Graphiti `forge_pipeline_history`)
- **Format**: Pydantic-serialised `GateDecision` per `DM-gating.md §1`; SQLite write **precedes** any bus publish (F10)
- **Validation**: durable-decision-on-publish-failure test (E5) verifies SQLite row exists when bus publish raises

### Contract 3 — Approval `details` shape

- **Producer**: TASK-CGCP-006 (`_build_approval_details`)
- **Consumer**: any notification adapter (Jarvis, etc.)
- **Format**: per `API-nats-approval-protocol.md §3.2` — eight keys (`build_id`, `feature_id`, `stage_label`, `gate_mode`, `coach_score`, `criterion_breakdown`, `detection_findings`, `rationale`, `evidence_priors`, `artefact_paths`, `resume_options`); `risk_level` derived per §3.3
- **Validation**: integration scenario (`The approval request carries enough context for a notification adapter to render the decision unaided`) is the contract test

### Contract 4 — Resume value rehydration

- **Producer**: any caller of LangGraph `interrupt()`
- **Consumer**: every gate-related code path that reads the resume value
- **Format**: `raw` is `dict` in server mode, `ApprovalResponsePayload` in direct invoke; **must** route through `resume_value_as(ApprovalResponsePayload, raw)`
- **Validation**: parametrised Group D scenario outline; CI grep guard

### Contract 5 — Synthetic CLI response shape

- **Producer**: TASK-CGCP-008 (synthetic injector)
- **Consumer**: TASK-CGCP-007 (subscriber dedup) + TASK-CGCP-010 (state machine resume)
- **Format**: typed `ApprovalResponsePayload` with `responder="rich"`, `reason ∈ {"cli cancel", "cli skip"}`, `decision ∈ {"reject", "override"}`
- **Validation**: synthetic responses pass the same idempotency check; persisted record distinguishable from a Rich-typed response

## Test Strategy

| Level | Coverage | Tool |
|---|---|---|
| **Unit** (pure) | `evaluate_gate` constitutional override, reasoning-model assembly, post-conditions, criterion-range invariant, degraded-mode invariant | pytest with deterministic reasoning-model double |
| **Unit** (helpers) | `request_id` derivation, `_build_approval_details`, `risk_level` derivation, `resume_value_as` (typed + dict) | pytest |
| **Contract** (seam) | Approval round-trip including dedup, synthetic CLI injection, durable-on-publish-failure, pause-and-publish atomicity | pytest with in-memory NATS double + temp SQLite |
| **BDD** (R2 oracle) | All 32 scenarios mapped to tasks via `@task:<TASK-ID>`; reachable via /task-work Phase 4 BDD runner | pytest-bdd via FEAT-FORGE-002 oracle infra |
| **Smoke** (R3 oracle) | 4 `@smoke` scenarios after Wave 4 completes | smoke gate between waves 4 and 5 |
| **Regression** (constitutional) | E2 two-layer regression: each layer disabled in isolation still produces MANDATORY_HUMAN_APPROVAL | pytest with selective-disable harness |

**Reasoning-model nondeterminism (R9)**: unit tests inject a deterministic
double; one contract-test suite invokes the real reasoning model with a fixed
prompt and asserts on the structured response shape rather than content.

## Recommendation

**Adopt Option 1: Pure-domain `forge.gating` with thin NATS approval adapter.**

Implement in 5 waves (Wave 1 parallel-safe foundation; Waves 2–4 sequential;
Wave 5 end-to-end). Total estimated effort 22–28 focused hours over 12
subtasks. Every task ≤ complexity 6, suiting `task-work` mode for evaluator
and adapters; declarative tasks for config and module structure use `direct`
mode.

This option preserves ADR-ARCH-019 (no static thresholds) and ADR-ARCH-026
(belt-and-braces) as architectural invariants and matches the established
Forge pure-domain / adapter split (FEAT-FORGE-002). The risk register is
small and well-mitigated; all 32 BDD scenarios map to specific tasks; one
integration assumption (ASSUM-003 — wait-ceiling fallback) is genuinely
deferred and does not block this feature's first landing.

## Decision Options

```
[A]ccept  - Approve findings only (review saved, no implementation tasks created)
[R]evise  - Request deeper analysis or alternative approaches
[I]mplement - Create implementation structure (12 subtasks across 5 waves)
[C]ancel  - Discard this review
```
