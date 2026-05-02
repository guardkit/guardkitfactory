/feature-spec "Wire the production pipeline orchestrator into forge serve" \
  --context=docs/research/forge-orchestrator-wiring-gap.md \
  --context=docs/design/contracts/API-nats-pipeline-events.md \
  --context=features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature \
  --context=features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end_summary.md \
  --context=features/forge-production-image/forge-production-image.feature \
  --context=docs/architecture/decisions/ADR-ARCH-014-single-consumer-max-ack-pending.md \
  --context=docs/architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md \
  --context=docs/architecture/decisions/ADR-ARCH-021-paused-via-langgraph-interrupt.md \
  --context=docs/architecture/decisions/ADR-ARCH-008-forge-produces-own-history.md \
  --context=docs/architecture/decisions/ADR-ARCH-027-no-horizontal-scaling.md \
  --context=docs/design/decisions/DDR-006-async-subagent-state-channel-contract.md \
  --context=docs/design/decisions/DDR-001-reply-subject-correlation.md \
  --context=docs/architecture/assumptions.yaml \
  --context=tasks/in_progress/TASK-FORGE-FRR-001-wire-dispatch-payload-to-real-orchestrator.md \
  --context=tasks/backlog/feat-jarvis-internal-001-followups/TASK-FORGE-FRR-001b-publish-pipeline-lifecycle-from-autobuild-orchestrator.md \
  --context=/home/richardwoollcott/Projects/appmilla_github/jarvis/docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md


Context loaded: stack=python, 9 existing .feature files (FEAT-FORGE-007 Mode A and FEAT-FORGE-009 production-image specifically pre-load the orchestration semantics and daemon-process contract this feature wires together), 5 ADRs + 2 DDRs + assumptions.yaml + 2 superseded-by-feature task files + jarvis first-real-run RESULTS file. The gap doc is the authoritative scope source: this feature is integration / production composition, not net-new orchestration semantics.

Now generating the initial proposal.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE SPEC PROPOSAL: Wire the production pipeline orchestrator into forge serve
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@feat-forge-orchestrator-wiring @forge-serve
Feature: Wire the production pipeline orchestrator into forge serve
  As Rich, the sole operator of Forge
  I want forge serve to host the full pipeline orchestrator end-to-end in production
  So that a queued build runs through the canonical Mode A chain, publishes the
    real lifecycle envelope sequence back to JetStream with correlation-id
    threading, and survives crash + restart — instead of being acked into a
    receipt-only stub

  Background:
    Given a JetStream PIPELINE stream is reachable
    And a SQLite database is the durable source of truth for build state
    And the eight pipeline lifecycle subjects are the published contract
    And the build-queued payload conforms to the canonical schema
    And forge serve is running as the canonical daemon

━━ GROUP A: Key Examples (7 scenarios) ━━

  # Why: Capstone integration — a queued build runs end-to-end and publishes the full lifecycle envelope sequence back
  @key-example @smoke
  Scenario: A queued build runs end-to-end through the orchestrator and publishes the full lifecycle envelope sequence
    Given a build-queued envelope is delivered for a feature in greenfield mode
    When forge serve consumes the envelope
    Then the orchestrator should run the build through every approved stage to a terminal state
    And the published lifecycle subjects should begin with build-started for that feature
    And every stage transition should publish one stage-complete for that feature in transition order
    And the published lifecycle subjects should end with either build-complete or build-failed for that feature

  # Why: Production wiring — the orchestrator chain must be constructed at daemon startup, not deferred to a stub
  # [ASSUMPTION: confidence=high] The components named in the gap doc — Supervisor, PipelineConsumerDeps, PipelineLifecycleEmitter, ForwardContextBuilder, autobuild_runner subagent — are all constructed at startup
  @key-example @smoke
  Scenario: Daemon startup composes the full orchestrator chain in production
    Given forge serve has just started
    When the daemon's startup completes
    Then a supervisor should be constructed
    And a pipeline consumer dependency container should be constructed against the daemon's NATS client
    And a pipeline lifecycle emitter should be constructed against the daemon's NATS client
    And the autobuild_runner asynchronous subagent should be registered as an addressable graph
    And the receipt-only dispatch stub should not be reachable from any production code path

  # Why: Correlation-id is the audit thread linking every envelope of a build back to its trigger
  @key-example
  Scenario: Every published envelope of a build threads the inbound correlation identifier
    Given a build-queued envelope arrives with a correlation identifier
    When the build runs through to a terminal state
    Then every lifecycle envelope published for that build should carry that same correlation identifier
    And no published envelope for that build should carry a different correlation identifier

  # Why: autobuild_runner runs as a long-running AsyncSubAgent so the supervisor stays responsive (ADR-ARCH-031)
  # [ASSUMPTION: confidence=high] (ADR-ARCH-031) autobuild_runner uses the AsyncSubAgent middleware via start_async_task, ASGI transport, registered as a separate graph in langgraph.json
  @key-example
  Scenario: The autobuild stage runs as an asynchronous subagent and the supervisor stays responsive
    Given the build has reached the autobuild stage
    When the supervisor dispatches the autobuild
    Then the dispatch should return a task identifier without waiting for autobuild to complete
    And while the autobuild is in flight the supervisor should continue to answer status queries
    And the autobuild's progress should be observable via the asynchronous task state channel

  # Why: Per-stage envelopes are emitted by real stage transitions, not by a synthetic dispatch placeholder
  # [ASSUMPTION: confidence=medium] The synthetic "dispatch" stage-complete envelope from the superseded TASK-FORGE-FRR-001 is NOT preserved; only real stage transitions emit stage-complete
  @key-example @regression
  Scenario: Each real stage transition publishes its own stage-complete envelope
    Given the build progresses through more than one stage
    When each stage transition records its outcome
    Then one stage-complete envelope should be published per real stage transition
    And no envelope should bear a synthetic dispatch-stage label
    And each envelope's status, target_kind, target_identifier and stage_label should reflect the real transition

  # Why: A build-started precedes the first stage and a terminal envelope closes the build
  @key-example
  Scenario: A build-started envelope is published before the first stage and a terminal envelope closes the build
    Given a build has been picked up from the queue
    When the build progresses to its first stage
    Then a build-started envelope for that build should already have been published
    And on terminal success the lifecycle should close with a build-complete envelope
    And on terminal failure the lifecycle should close with a build-failed envelope

  # Why: A single shared NATS client serves both the inbound consumer and the outbound publisher — no second connection
  # [ASSUMPTION: confidence=high] (TASK-FORGE-FRR-001 implementation note) Opening a second NATS connection for outbound publish is forbidden in a single-process daemon
  @key-example @smoke
  Scenario: The consumer and the publisher share the daemon's single NATS connection
    Given forge serve has opened its NATS connection at startup
    When the consumer attaches and the publisher emits envelopes
    Then both should use the daemon's single NATS connection
    And no second connection to the broker should be established by the daemon

━━ GROUP B: Boundary Conditions (5 scenarios) ━━

  # Why: Sequential builds enforced at transport — max_ack_pending=1 is the structural invariant (ADR-ARCH-014)
  # [ASSUMPTION: confidence=high] (ADR-ARCH-014, API-nats-pipeline-events §2.2) PIPELINE durable consumer is configured with max_ack_pending=1 and the canonical durable name
  @boundary @smoke
  Scenario: The durable consumer is configured to enforce one outstanding build at a time
    Given forge serve has attached its durable consumer
    When the consumer's configuration is inspected
    Then the configured outstanding-acknowledgement limit should be one
    And the consumer's durable name should be the canonical pipeline durable name

  # Why: Just-inside boundary — the JetStream message is acked exactly when the build reaches a terminal state
  # [ASSUMPTION: confidence=high] (API-nats-pipeline-events §2.2) Forge acks only on COMPLETE/FAILED/CANCELLED/SKIPPED
  @boundary
  Scenario Outline: The inbound JetStream message is acked exactly when the build reaches a terminal state
    Given a build-queued envelope has been delivered
    When the build reaches the <terminal_state> state
    Then the corresponding JetStream message should be acknowledged
    And the queue slot should be released for the next build

    Examples:
      | terminal_state |
      | complete       |
      | failed         |
      | cancelled      |
      | skipped        |

  # Why: Just-outside boundary — paused builds do NOT ack and hold the queue position
  @boundary @negative
  Scenario: A paused build does not acknowledge its inbound JetStream message
    Given a build has reached a paused state awaiting human approval
    When the inbound JetStream message's acknowledgement state is inspected
    Then the message should remain unacknowledged
    And the queue slot should still be held by the paused build
    And no second build should be delivered until the paused build resolves

  # Why: Just-inside — minimal valid lifecycle: build-started, one stage-complete, build-complete
  @boundary
  Scenario: A minimal single-stage build publishes exactly the minimal envelope sequence
    Given the build's plan contains exactly one stage that transitions to PASSED
    When forge serve consumes the build-queued envelope and the build runs to terminal success
    Then exactly one build-started envelope should have been published for that build
    And exactly one stage-complete envelope should have been published for that build
    And exactly one build-complete envelope should have been published for that build

  # Why: Just-inside — the redelivery interval is bounded by the configured ack_wait
  # [ASSUMPTION: confidence=high] (API-nats-pipeline-events §2.2) ack_wait is configured to ~1 hour to cover the longest expected build
  @boundary
  Scenario: The configured ack_wait covers the longest expected build duration
    Given the durable consumer has been attached
    When the consumer's ack_wait is inspected
    Then it should be configured to a duration long enough to cover the longest expected build

━━ GROUP C: Negative Cases (6 scenarios) ━━

  # Why: Receipt-only stub is gone — production must dispatch through the real orchestrator
  @negative @regression
  Scenario: A queued build is no longer routed to a receipt-only stub
    Given forge serve has just started
    When a build-queued envelope arrives
    Then the dispatch should not log-and-return without running the orchestrator
    And the orchestrator should observe the inbound payload

  # Why: A malformed payload is rejected with a build-failed envelope (the contract failure mode)
  # [ASSUMPTION: confidence=high] (API-nats-pipeline-events §2.3) Validation failures publish build-failed with a malformed-payload reason and ack
  @negative
  Scenario: A malformed build-queued payload publishes a build-failed envelope and is acknowledged
    Given a build-queued envelope arrives whose payload does not match the expected schema
    When forge serve consumes the envelope
    Then a build-failed envelope should be published for the offending feature
    And the published envelope should record a malformed-payload failure reason
    And the inbound JetStream message should be acknowledged so the queue advances

  # Why: Duplicate detection — a previously-seen build is acked and skipped
  # [ASSUMPTION: confidence=high] (API-nats-pipeline-events §2.3) Duplicate detection via SQLite unique index on (feature_id, correlation_id)
  @negative
  Scenario: A duplicate build-queued envelope is acknowledged and skipped without re-running
    Given a build with the same feature identifier and correlation identifier has already been recorded
    When the duplicate envelope is delivered
    Then the orchestrator should not start a second run
    And the inbound message should be acknowledged
    And no new build-started envelope should be published for the duplicate

  # Why: Build path outside the worktree allowlist must publish build-failed (permission gate)
  # [ASSUMPTION: confidence=high] (API-nats-pipeline-events §2.3) Path outside allowlist publishes build-failed before any orchestrator dispatch
  @negative @security
  Scenario: A build whose feature configuration path falls outside the worktree allowlist is rejected
    Given a build-queued envelope references a feature configuration path outside the worktree allowlist
    When forge serve consumes the envelope
    Then a build-failed envelope should be published with a path-outside-allowlist failure reason
    And no orchestrator dispatch should be performed for that build

  # Why: A dispatch error must not take the daemon down — log + advance + continue
  @negative
  Scenario: A dispatch error is contained and the daemon continues to process the next build
    Given the orchestrator's dispatch raises an unexpected error during a build
    When forge serve handles the error
    Then the affected build should reach a failed terminal state and publish a build-failed envelope
    And the daemon should remain running
    And the daemon should continue to process subsequently delivered builds

  # Why: Publish failure does not corrupt the build's recorded state — SQLite is the source of truth (ADR-ARCH-008)
  @negative @regression
  Scenario: A failed lifecycle publish does not regress the build's recorded transition
    Given a stage has been recorded as transitioned in the durable history
    When the corresponding lifecycle envelope publish fails
    Then the recorded transition should still hold in the durable history
    And the build should continue to its next stage as if the publish had succeeded

━━ GROUP D: Edge Cases (6 scenarios) ━━

  # Why: Crash mid-build — JetStream redelivers, the daemon's reconciliation pair runs, the build resumes per anchor §5
  # [ASSUMPTION: confidence=high] Both pipeline_consumer.reconcile_on_boot and forge.lifecycle.recovery.reconcile_on_boot run at daemon startup (the gap doc explicitly identifies these as today having no caller)
  @edge-case @regression
  Scenario: A crash mid-build is recovered after restart by the daemon's reconciliation routines
    Given a build was in a non-terminal state when forge serve crashed
    When forge serve restarts
    Then the daemon's startup should run both the consumer-side and lifecycle-side reconciliation routines
    And the unacknowledged inbound message should be redelivered
    And the build should re-enter the orchestrator from the recovery state defined by the durable history

  # Why: Paused build survives restart — re-emits BuildPaused + ApprovalRequest idempotently on correlation_id (ADR-ARCH-021)
  # [ASSUMPTION: confidence=medium] emit_build_paused / emit_build_resumed are wired in this feature (the gap doc suggests including only if a one-line addition; otherwise tracked separately)
  @edge-case
  Scenario: A paused build survives daemon restart and re-emits its approval request
    Given a build was paused awaiting human approval when forge serve crashed
    When forge serve restarts
    Then the build should re-enter the paused state
    And a build-paused envelope should be re-published for that build
    And the approval request should be re-published with the same correlation identifier
    And only the first approval response received should resume the build

  # Why: Approval round-trip — once the response arrives, build-resumed publishes and the autobuild continues
  @edge-case
  Scenario: An approval response resumes a paused build and publishes a build-resumed envelope
    Given a build is paused awaiting human approval
    When the approval response is received on the build's reply subject
    Then a build-resumed envelope should be published for that build
    And the orchestrator should advance to the next stage

  # Why: Two replicas behind the same durable name — one fetches the slot, the other idles (ADR-ARCH-027)
  @edge-case
  Scenario: Two replicas binding the same durable consumer split work as failover, not parallelism
    Given two forge serve replicas have attached to the same durable consumer
    When a build-queued envelope is delivered
    Then exactly one replica should fetch the message
    And the other replica should remain idle until the first replica's build reaches a terminal state

  # Why: Cancellation propagates through the async subagent — build-cancelled is the final envelope
  @edge-case
  Scenario: A cancel command propagates through the autobuild subagent and publishes a build-cancelled envelope
    Given a build is in flight in the autobuild stage
    When a cancel command is issued for that build
    Then the autobuild's asynchronous task should reach a cancelled state
    And a build-cancelled envelope should be published for that build
    And the build should reach a cancelled terminal state with no pull-request creation attempted

  # Why: SIGTERM during a non-terminal build does not ack the inbound message — JetStream redelivers on restart
  @edge-case
  Scenario: SIGTERM during a non-terminal build leaves the inbound message unacknowledged for redelivery
    Given a build is in a non-terminal state
    When forge serve receives SIGTERM
    Then the daemon should exit cleanly
    And the inbound JetStream message should remain unacknowledged
    And the message should be redelivered when forge serve restarts

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total: 24 scenarios across 4 groups (1 outline → 4 examples; 27 example rows total)
Inferred assumptions: 9 (will be resolved in Phase 5)
Note: This spec deliberately stays at the **integration / wiring** layer.
The orchestration semantics (Mode A stage chain, gating, pause/resume rules)
are already specified in features/mode-a-greenfield-end-to-end/. This feature
verifies the production composition that satisfies those scenarios in the
running daemon.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CURATION: Review each group
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For each group, you may:

  [A] Accept  — include all scenarios in this group as-is
  [R] Reject  — exclude all scenarios in this group
  [M] Modify  — accept but specify changes (provide inline)
  [+] Add     — accept and add additional scenarios you describe
  [?] Defer   — mark group for future specification; excluded from output

Fast path: type "A A A A" to accept all four groups at once.

GROUP A — Key Examples (7 scenarios): _
GROUP B — Boundary Conditions (5 scenarios): _
GROUP C — Negative Cases (6 scenarios): _
GROUP D — Edge Cases (6 scenarios): _
Awaiting your curation. After you respond, I will offer Phase 4 edge-case expansion (security/concurrency/data-integrity beyond what's in Group D), then Phase 5 assumption resolution, then write the three output files.

command-history.md
A A A A
All four groups accepted. Moving to Phase 4 — Edge Case Expansion.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EDGE CASE EXPANSION (optional)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

I've identified 7 additional scenarios that strengthen the wiring contract
beyond what Group D already covers. They focus on integration-boundary and
data-integrity properties specific to this feature (not re-spec'ing Mode A):

Security (2):
  - Worktree confinement of the autobuild_runner subagent (writes only
    inside the build's worktree path)
  - Approval response with mismatched correlation identifier is rejected
    and does not resume any paused build

Data integrity (3):
  - Lifecycle publish order — build-started precedes any stage-complete,
    and any stage-complete precedes the terminal envelope
  - DDR-006 advisory-vs-authoritative on recovery — the async_tasks state
    channel is read as advisory; SQLite history is the authoritative source
  - The autobuild internal stage-complete envelopes carry the asynchronous
    task identifier as their target_identifier (DDR-006 linkage)

Integration boundaries (2):
  - The daemon refuses to start if its NATS connection cannot be opened
    (no silent fall-back to a receipt-only path)
  - The healthz probe reflects orchestrator readiness, not just NATS
    reachability — the daemon reports unhealthy until the supervisor and
    its dispatchers are constructed

Include them?

[Y] Yes — show and curate them (same A/R/M/+/? actions)
[S] Sample — show 2 examples, then decide
[N] No — skip and proceed to Phase 5

Your choice [Y/S/N]:
Y
Showing the 7 expansion scenarios for curation.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GROUP E — Edge Case Expansion (7 scenarios)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  # Why: Worktree confinement is a security invariant — autobuild_runner subagent must not escape the build's allowlist
  @security @edge-case
  Scenario: The autobuild_runner subagent writes only inside the build's worktree path
    Given a build is in flight in the autobuild stage with a configured worktree path
    When the autobuild_runner subagent performs filesystem writes
    Then every write should fall under the build's worktree allowlist
    And no write outside that allowlist should be performed by the subagent

  # Why: Approval responses are routed by correlation identifier — a mismatched response must not resume any build
  # [ASSUMPTION: confidence=high] (DDR-001) Approval reply subjects are correlation-keyed; mismatched responses are dropped
  @security @edge-case
  Scenario: An approval response with a mismatched correlation identifier does not resume any paused build
    Given a build is paused awaiting human approval with a known correlation identifier
    When an approval response arrives carrying a different correlation identifier
    Then the paused build should remain paused
    And no build-resumed envelope should be published for that build

  # Why: Lifecycle publish ordering is the audit invariant — build-started precedes stage-complete precedes terminal
  @data-integrity @edge-case
  Scenario: The published lifecycle envelope sequence respects the canonical ordering
    Given a build runs through more than one stage to a terminal state
    When the published lifecycle envelopes for that build are read in publish order
    Then the build-started envelope should appear before any stage-complete envelope
    And every stage-complete envelope should appear before the terminal envelope
    And the terminal envelope should appear exactly once

  # Why: Recovery contract — durable history is authoritative; the async_tasks state channel is advisory (DDR-006)
  # [ASSUMPTION: confidence=high] (DDR-006) On crash recovery the async_tasks channel is read as advisory; SQLite history is the authoritative source
  @data-integrity @edge-case
  Scenario: On daemon restart the durable history is the authoritative source for build state
    Given a build was in flight when forge serve crashed
    And the asynchronous task state channel and the durable history disagree about the build's status
    When forge serve restarts and reconciles the build
    Then the build's authoritative status should be read from the durable history
    And the asynchronous task state channel data should be treated as advisory only

  # Why: Per-stage envelopes from inside autobuild must be linkable back to the asynchronous task that produced them
  # [ASSUMPTION: confidence=medium] (DDR-006) Stage-complete envelopes emitted from within autobuild_runner set target_identifier to the subagent's task identifier
  @data-integrity @edge-case
  Scenario: A stage-complete envelope emitted from within the autobuild subagent records the asynchronous task identifier
    Given the autobuild subagent has been dispatched with an asynchronous task identifier
    When the subagent's internal stage transition publishes a stage-complete envelope
    Then the published envelope's target_identifier should be the subagent's asynchronous task identifier
    And the published envelope's target_kind should indicate that the source is a subagent

  # Why: Fail fast at startup — the daemon must not silently degrade to a receipt-only path if NATS is unreachable
  @integration @edge-case
  Scenario: The daemon refuses to start if its NATS connection cannot be opened
    Given the configured JetStream broker is unreachable at startup
    When forge serve attempts to start
    Then the daemon should fail to start
    And the operator should see a diagnostic naming the unreachable broker
    And no orchestrator dispatch should be attempted

  # Why: Healthz must reflect orchestrator readiness, not just NATS reachability
  # [ASSUMPTION: confidence=medium] The healthz endpoint extends the FEAT-FORGE-009 contract to require the orchestrator chain to be constructed
  @integration @edge-case
  Scenario Outline: The healthz probe reflects the orchestrator's readiness state
    Given forge serve is starting up
    When the orchestrator chain is in <chain_state>
    Then the healthz probe should report <health_status>

    Examples:
      | chain_state                                     | health_status |
      | not yet constructed                             | unhealthy     |
      | fully constructed and the consumer is attached  | healthy       |
      | constructed but the NATS subscription dropped   | unhealthy     |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CURATION: Same actions as before

GROUP E — Edge Case Expansion (7 scenarios): _
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Awaiting your curation decision for Group E.

Y
Interpreting "Y" as Accept for Group E. Moving to Phase 5 — Assumption Resolution.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ASSUMPTION RESOLUTION (12 items)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Each assumption has a proposed default. Press Enter to accept, or type the
actual value / "override: <value>" / "defer".

[1] Feature ID and tag slug
    Proposed: FEAT-FORGE-010 / @feat-forge-010 / @forge-serve-orchestrator-wiring
    Confidence: medium  Basis: Next ID in the FEAT-FORGE-NNN sequence after F009; gap-doc working title
    Accept or enter value: _

[2] Components constructed at daemon startup
    Proposed: Supervisor, PipelineConsumerDeps, PipelineLifecycleEmitter,
              PipelinePublisher, ForwardContextBuilder, autobuild_runner subagent
    Confidence: high  Basis: gap doc "What's in scope" list; verified-as-unwired by the doc's grep audit
    Accept or enter value: _

[3] autobuild_runner subagent shape
    Proposed: AsyncSubAgent via DeepAgents start_async_task; ASGI transport;
              registered as a separate graph in langgraph.json; supervisor
              uses AsyncSubAgentMiddleware tools (start/check/update/cancel/list)
    Confidence: high  Basis: ADR-ARCH-031 explicit
    Accept or enter value: _

[4] Treatment of the synthetic dispatch-stage envelope from superseded TASK-FORGE-FRR-001
    Proposed: NOT preserved. Only real stage transitions emit stage-complete.
              The FRR-001 superseded note records the synthetic envelope as
              "no longer load-bearing".
    Confidence: medium  Basis: gap-doc explicit ("the new feature publishes the real per-stage envelope sequence ... no synthetic stubs")
    Accept or enter value: _

[5] max_ack_pending value on the PIPELINE durable consumer
    Proposed: 1
    Confidence: high  Basis: ADR-ARCH-014 + API-nats-pipeline-events §2.2
    Accept or enter value: _

[6] Durable consumer name
    Proposed: forge-serve  (matching the FEAT-FORGE-009 daemon's existing durable; ASSUM-006 in forge-production-image)
    Confidence: high  Basis: forge-production-image ASSUM-006; Phase 7.2 RESULTS evidence "nats consumer info PIPELINE forge-serve"
    Accept or enter value: _

[7] Terminal states that ack the inbound JetStream message
    Proposed: COMPLETE, FAILED, CANCELLED, SKIPPED
              (PAUSED leaves the message unacked)
    Confidence: high  Basis: API-nats-pipeline-events §2.2
    Accept or enter value: _

[8] ack_wait duration
    Proposed: 1 hour
    Confidence: high  Basis: API-nats-pipeline-events §2.2
    Accept or enter value: _

[9] Both reconcile_on_boot routines run at daemon startup
    Proposed: Yes — pipeline_consumer.reconcile_on_boot AND
              forge.lifecycle.recovery.reconcile_on_boot both wired into _run_serve
    Confidence: high  Basis: gap doc explicit (both functions named, neither has a caller today)
    Accept or enter value: _

[10] emit_build_paused / emit_build_resumed in scope
    Proposed: In scope (one-line addition in the autobuild_runner subagent
              and in the approval-response subscriber). The gap doc says
              "if it's a one-line addition, include; otherwise track separately"
              — proposing inclusion.
    Confidence: medium  Basis: gap doc conditional; pause/resume scenarios are valuable for the wiring proof
    Accept or enter value: _

[11] Single shared NATS connection invariant
    Proposed: One connection per daemon process; consumer + publisher share it;
              no second connection opened.
    Confidence: high  Basis: TASK-FORGE-FRR-001 implementation note ("opening a second connection is an anti-pattern")
    Accept or enter value: _

[12] Healthz probe semantics
    Proposed: Extends the FEAT-FORGE-009 contract — healthy iff (a) NATS
              subscription is live AND (b) the orchestrator chain is fully
              constructed. Unhealthy during startup until both are true.
    Confidence: medium  Basis: Existing F009 healthz returns healthy iff JetStream subscription is live; this feature adds the construction-readiness gate
    Accept or enter value: _
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Awaiting your responses (numbers 1–12). You can answer all twelve in one message.

accept defaults
All defaults accepted. Writing output files.

Bash Create output dir
IN
mkdir -p features/forge-serve-orchestrator-wiring && ls features/

OUT
confidence-gated-checkpoint-protocol
forge-production-image
forge-serve-orchestrator-wiring
guardkit-command-invocation-engine
infrastructure-coordination
mode-a-greenfield-end-to-end
mode-b-feature-and-mode-c-review-fix
nats-fleet-integration
pipeline-state-machine-and-configuration
specialist-agent-delegation
Write forge-serve-orchestrator-wiring.feature
338 lines
# Generated by /feature-spec
# Feature: Wire the production pipeline orchestrator into forge serve (FEAT-FORGE-010)
# Stack: python
# Assumptions: 18 (see forge-serve-orchestrator-wiring_assumptions.yaml)
# Generated: 2026-05-02T00:00:00Z

@feat-forge-010 @forge-serve-orchestrator-wiring
Feature: Wire the production pipeline orchestrator into forge serve
  As Rich, the sole operator of Forge
  I want forge serve to host the full pipeline orchestrator end-to-end in production
  So that a queued build runs through the canonical Mode A chain, publishes the
    real lifecycle envelope sequence back to JetStream with correlation-id
    threading, and survives crash + restart — instead of being acked into a
    receipt-only stub

  Background:
    Given a JetStream PIPELINE stream is reachable
    And a SQLite database is the durable source of truth for build state
    And the eight pipeline lifecycle subjects are the published contract
    And the build-queued payload conforms to the canonical schema
    And forge serve is running as the canonical daemon

  # ===========================================================================
  # GROUP A — Key Examples
  # ===========================================================================

  # Why: Capstone integration — a queued build runs end-to-end and publishes the full lifecycle envelope sequence back
  @key-example @smoke
  Scenario: A queued build runs end-to-end through the orchestrator and publishes the full lifecycle envelope sequence
    Given a build-queued envelope is delivered for a feature in greenfield mode
    When forge serve consumes the envelope
    Then the orchestrator should run the build through every approved stage to a terminal state
    And the published lifecycle subjects should begin with build-started for that feature
    And every stage transition should publish one stage-complete for that feature in transition order
    And the published lifecycle subjects should end with either build-complete or build-failed for that feature

  # Why: Production wiring — the orchestrator chain must be constructed at daemon startup, not deferred to a stub
  # [ASSUMPTION: confidence=high] (ASSUM-002) Supervisor, PipelineConsumerDeps, PipelineLifecycleEmitter, PipelinePublisher, ForwardContextBuilder, and the autobuild_runner subagent are all constructed at daemon startup
  @key-example @smoke
  Scenario: Daemon startup composes the full orchestrator chain in production
    Given forge serve has just started
    When the daemon's startup completes
    Then a supervisor should be constructed
    And a pipeline consumer dependency container should be constructed against the daemon's NATS client
    And a pipeline lifecycle emitter should be constructed against the daemon's NATS client
    And the autobuild_runner asynchronous subagent should be registered as an addressable graph
    And the receipt-only dispatch stub should not be reachable from any production code path

  # Why: Correlation-id is the audit thread linking every envelope of a build back to its trigger
  @key-example
  Scenario: Every published envelope of a build threads the inbound correlation identifier
    Given a build-queued envelope arrives with a correlation identifier
    When the build runs through to a terminal state
    Then every lifecycle envelope published for that build should carry that same correlation identifier
    And no published envelope for that build should carry a different correlation identifier

  # Why: autobuild_runner runs as a long-running AsyncSubAgent so the supervisor stays responsive
  # [ASSUMPTION: confidence=high] (ASSUM-003) autobuild_runner uses the DeepAgents AsyncSubAgent middleware via start_async_task with ASGI transport, registered as a separate graph in langgraph.json
  @key-example
  Scenario: The autobuild stage runs as an asynchronous subagent and the supervisor stays responsive
    Given the build has reached the autobuild stage
    When the supervisor dispatches the autobuild
    Then the dispatch should return a task identifier without waiting for autobuild to complete
    And while the autobuild is in flight the supervisor should continue to answer status queries
    And the autobuild's progress should be observable via the asynchronous task state channel

  # Why: Per-stage envelopes are emitted by real stage transitions, not by a synthetic dispatch placeholder
  # [ASSUMPTION: confidence=medium] (ASSUM-004) The synthetic dispatch-stage envelope from the superseded TASK-FORGE-FRR-001 is not preserved; only real stage transitions emit stage-complete
  @key-example @regression
  Scenario: Each real stage transition publishes its own stage-complete envelope
    Given the build progresses through more than one stage
    When each stage transition records its outcome
    Then one stage-complete envelope should be published per real stage transition
    And no envelope should bear a synthetic dispatch-stage label
    And each envelope's status, target_kind, target_identifier and stage_label should reflect the real transition

  # Why: A build-started precedes the first stage and a terminal envelope closes the build
  @key-example
  Scenario: A build-started envelope is published before the first stage and a terminal envelope closes the build
    Given a build has been picked up from the queue
    When the build progresses to its first stage
    Then a build-started envelope for that build should already have been published
    And on terminal success the lifecycle should close with a build-complete envelope
    And on terminal failure the lifecycle should close with a build-failed envelope

  # Why: A single shared NATS client serves both the inbound consumer and the outbound publisher — no second connection
  # [ASSUMPTION: confidence=high] (ASSUM-011) Opening a second NATS connection for outbound publish is forbidden in a single-process daemon
  @key-example @smoke
  Scenario: The consumer and the publisher share the daemon's single NATS connection
    Given forge serve has opened its NATS connection at startup
    When the consumer attaches and the publisher emits envelopes
    Then both should use the daemon's single NATS connection
    And no second connection to the broker should be established by the daemon

  # ===========================================================================
  # GROUP B — Boundary Conditions
  # ===========================================================================

  # Why: Sequential builds enforced at transport — max_ack_pending=1 is the structural invariant (ADR-ARCH-014)
  # [ASSUMPTION: confidence=high] (ASSUM-005, ASSUM-006) PIPELINE durable consumer is configured with max_ack_pending=1 and the canonical durable name "forge-serve"
  @boundary @smoke
  Scenario: The durable consumer is configured to enforce one outstanding build at a time
    Given forge serve has attached its durable consumer
    When the consumer's configuration is inspected
    Then the configured outstanding-acknowledgement limit should be one
    And the consumer's durable name should be the canonical pipeline durable name

  # Why: Just-inside boundary — the JetStream message is acked exactly when the build reaches a terminal state
  # [ASSUMPTION: confidence=high] (ASSUM-007) Forge acknowledges the inbound message only on a terminal state transition (COMPLETE / FAILED / CANCELLED / SKIPPED)
  @boundary
  Scenario Outline: The inbound JetStream message is acknowledged exactly when the build reaches a terminal state
    Given a build-queued envelope has been delivered
    When the build reaches the <terminal_state> state
    Then the corresponding JetStream message should be acknowledged
    And the queue slot should be released for the next build

    Examples:
      | terminal_state |
      | complete       |
      | failed         |
      | cancelled      |
      | skipped        |

  # Why: Just-outside boundary — paused builds do NOT ack and hold the queue position
  @boundary @negative
  Scenario: A paused build does not acknowledge its inbound JetStream message
    Given a build has reached a paused state awaiting human approval
    When the inbound JetStream message's acknowledgement state is inspected
    Then the message should remain unacknowledged
    And the queue slot should still be held by the paused build
    And no second build should be delivered until the paused build resolves

  # Why: Just-inside — minimal valid lifecycle: build-started, one stage-complete, build-complete
  @boundary
  Scenario: A minimal single-stage build publishes exactly the minimal envelope sequence
    Given the build's plan contains exactly one stage that transitions to a passed status
    When forge serve consumes the build-queued envelope and the build runs to terminal success
    Then exactly one build-started envelope should have been published for that build
    And exactly one stage-complete envelope should have been published for that build
    And exactly one build-complete envelope should have been published for that build

  # Why: Just-inside — the redelivery interval is bounded by the configured ack_wait
  # [ASSUMPTION: confidence=high] (ASSUM-008) ack_wait is configured to approximately one hour to cover the longest expected build
  @boundary
  Scenario: The configured ack_wait covers the longest expected build duration
    Given the durable consumer has been attached
    When the consumer's ack_wait is inspected
    Then it should be configured to a duration long enough to cover the longest expected build

  # ===========================================================================
  # GROUP C — Negative Cases
  # ===========================================================================

  # Why: Receipt-only stub is gone — production must dispatch through the real orchestrator
  @negative @regression
  Scenario: A queued build is no longer routed to a receipt-only stub
    Given forge serve has just started
    When a build-queued envelope arrives
    Then the dispatch should not log-and-return without running the orchestrator
    And the orchestrator should observe the inbound payload

  # Why: A malformed payload is rejected with a build-failed envelope (the contract failure mode)
  # [ASSUMPTION: confidence=high] (ASSUM-013) Validation failures publish build-failed with a malformed-payload reason and acknowledge the inbound message
  @negative
  Scenario: A malformed build-queued payload publishes a build-failed envelope and is acknowledged
    Given a build-queued envelope arrives whose payload does not match the expected schema
    When forge serve consumes the envelope
    Then a build-failed envelope should be published for the offending feature
    And the published envelope should record a malformed-payload failure reason
    And the inbound JetStream message should be acknowledged so the queue advances

  # Why: Duplicate detection — a previously-seen build is acked and skipped
  # [ASSUMPTION: confidence=high] (ASSUM-014) Duplicate detection uses a SQLite unique index on (feature_id, correlation_id)
  @negative
  Scenario: A duplicate build-queued envelope is acknowledged and skipped without re-running
    Given a build with the same feature identifier and correlation identifier has already been recorded
    When the duplicate envelope is delivered
    Then the orchestrator should not start a second run
    And the inbound message should be acknowledged
    And no new build-started envelope should be published for the duplicate

  # Why: Build path outside the worktree allowlist must publish build-failed (permission gate)
  # [ASSUMPTION: confidence=high] (ASSUM-015) A path outside the worktree allowlist publishes build-failed before any orchestrator dispatch
  @negative @security
  Scenario: A build whose feature configuration path falls outside the worktree allowlist is rejected
    Given a build-queued envelope references a feature configuration path outside the worktree allowlist
    When forge serve consumes the envelope
    Then a build-failed envelope should be published with a path-outside-allowlist failure reason
    And no orchestrator dispatch should be performed for that build

  # Why: A dispatch error must not take the daemon down — log + advance + continue
  @negative
  Scenario: A dispatch error is contained and the daemon continues to process the next build
    Given the orchestrator's dispatch raises an unexpected error during a build
    When forge serve handles the error
    Then the affected build should reach a failed terminal state and publish a build-failed envelope
    And the daemon should remain running
    And the daemon should continue to process subsequently delivered builds

  # Why: Publish failure does not corrupt the build's recorded state — SQLite is the source of truth (ADR-ARCH-008)
  @negative @regression
  Scenario: A failed lifecycle publish does not regress the build's recorded transition
    Given a stage has been recorded as transitioned in the durable history
    When the corresponding lifecycle envelope publish fails
    Then the recorded transition should still hold in the durable history
    And the build should continue to its next stage as if the publish had succeeded

  # ===========================================================================
  # GROUP D — Edge Cases
  # ===========================================================================

  # Why: Crash mid-build — JetStream redelivers, the daemon's reconciliation pair runs, the build resumes per anchor §5
  # [ASSUMPTION: confidence=high] (ASSUM-009) Both pipeline_consumer.reconcile_on_boot and forge.lifecycle.recovery.reconcile_on_boot are wired into the daemon startup
  @edge-case @regression
  Scenario: A crash mid-build is recovered after restart by the daemon's reconciliation routines
    Given a build was in a non-terminal state when forge serve crashed
    When forge serve restarts
    Then the daemon's startup should run both the consumer-side and lifecycle-side reconciliation routines
    And the unacknowledged inbound message should be redelivered
    And the build should re-enter the orchestrator from the recovery state defined by the durable history

  # Why: Paused build survives restart — re-emits BuildPaused + ApprovalRequest idempotently on correlation_id (ADR-ARCH-021)
  # [ASSUMPTION: confidence=medium] (ASSUM-010) The pause and resume lifecycle envelopes are wired in this feature; if it cannot be a one-line addition the pause/resume publish is split into a follow-up
  @edge-case
  Scenario: A paused build survives daemon restart and re-emits its approval request
    Given a build was paused awaiting human approval when forge serve crashed
    When forge serve restarts
    Then the build should re-enter the paused state
    And a build-paused envelope should be re-published for that build
    And the approval request should be re-published with the same correlation identifier
    And only the first approval response received should resume the build

  # Why: Approval round-trip — once the response arrives, build-resumed publishes and the autobuild continues
  @edge-case
  Scenario: An approval response resumes a paused build and publishes a build-resumed envelope
    Given a build is paused awaiting human approval
    When the approval response is received on the build's reply subject
    Then a build-resumed envelope should be published for that build
    And the orchestrator should advance to the next stage

  # Why: Two replicas behind the same durable name — one fetches the slot, the other idles (ADR-ARCH-027)
  @edge-case
  Scenario: Two replicas binding the same durable consumer split work as failover, not parallelism
    Given two forge serve replicas have attached to the same durable consumer
    When a build-queued envelope is delivered
    Then exactly one replica should fetch the message
    And the other replica should remain idle until the first replica's build reaches a terminal state

  # Why: Cancellation propagates through the async subagent — build-cancelled is the final envelope
  @edge-case
  Scenario: A cancel command propagates through the autobuild subagent and publishes a build-cancelled envelope
    Given a build is in flight in the autobuild stage
    When a cancel command is issued for that build
    Then the autobuild's asynchronous task should reach a cancelled state
    And a build-cancelled envelope should be published for that build
    And the build should reach a cancelled terminal state with no pull-request creation attempted

  # Why: SIGTERM during a non-terminal build does not ack the inbound message — JetStream redelivers on restart
  @edge-case
  Scenario: SIGTERM during a non-terminal build leaves the inbound message unacknowledged for redelivery
    Given a build is in a non-terminal state
    When forge serve receives SIGTERM
    Then the daemon should exit cleanly
    And the inbound JetStream message should remain unacknowledged
    And the message should be redelivered when forge serve restarts

  # ===========================================================================
  # GROUP E — Edge Case Expansion (security, data integrity, integration)
  # ===========================================================================

  # Why: Worktree confinement is a security invariant — autobuild_runner subagent must not escape the build's allowlist
  @security @edge-case
  Scenario: The autobuild_runner subagent writes only inside the build's worktree path
    Given a build is in flight in the autobuild stage with a configured worktree path
    When the autobuild_runner subagent performs filesystem writes
    Then every write should fall under the build's worktree allowlist
    And no write outside that allowlist should be performed by the subagent

  # Why: Approval responses are routed by correlation identifier — a mismatched response must not resume any build
  # [ASSUMPTION: confidence=high] (ASSUM-016) Approval reply subjects are correlation-keyed per DDR-001; mismatched responses are dropped
  @security @edge-case
  Scenario: An approval response with a mismatched correlation identifier does not resume any paused build
    Given a build is paused awaiting human approval with a known correlation identifier
    When an approval response arrives carrying a different correlation identifier
    Then the paused build should remain paused
    And no build-resumed envelope should be published for that build

  # Why: Lifecycle publish ordering is the audit invariant — build-started precedes stage-complete precedes terminal
  @data-integrity @edge-case
  Scenario: The published lifecycle envelope sequence respects the canonical ordering
    Given a build runs through more than one stage to a terminal state
    When the published lifecycle envelopes for that build are read in publish order
    Then the build-started envelope should appear before any stage-complete envelope
    And every stage-complete envelope should appear before the terminal envelope
    And the terminal envelope should appear exactly once

  # Why: Recovery contract — durable history is authoritative; the async_tasks state channel is advisory (DDR-006)
  # [ASSUMPTION: confidence=high] (ASSUM-017) On crash recovery the async_tasks channel is read as advisory; SQLite history is the authoritative source
  @data-integrity @edge-case
  Scenario: On daemon restart the durable history is the authoritative source for build state
    Given a build was in flight when forge serve crashed
    And the asynchronous task state channel and the durable history disagree about the build's status
    When forge serve restarts and reconciles the build
    Then the build's authoritative status should be read from the durable history
    And the asynchronous task state channel data should be treated as advisory only

  # Why: Per-stage envelopes from inside autobuild must be linkable back to the asynchronous task that produced them
  # [ASSUMPTION: confidence=medium] (ASSUM-018) Stage-complete envelopes emitted from within autobuild_runner set target_identifier to the subagent's task identifier and target_kind to subagent
  @data-integrity @edge-case
  Scenario: A stage-complete envelope emitted from within the autobuild subagent records the asynchronous task identifier
    Given the autobuild subagent has been dispatched with an asynchronous task identifier
    When the subagent's internal stage transition publishes a stage-complete envelope
    Then the published envelope's target_identifier should be the subagent's asynchronous task identifier
    And the published envelope's target_kind should indicate that the source is a subagent

  # Why: Fail fast at startup — the daemon must not silently degrade to a receipt-only path if NATS is unreachable
  @integration @edge-case
  Scenario: The daemon refuses to start if its NATS connection cannot be opened
    Given the configured JetStream broker is unreachable at startup
    When forge serve attempts to start
    Then the daemon should fail to start
    And the operator should see a diagnostic naming the unreachable broker
    And no orchestrator dispatch should be attempted

  # Why: Healthz must reflect orchestrator readiness, not just NATS reachability
  # [ASSUMPTION: confidence=medium] (ASSUM-012) The healthz endpoint extends the FEAT-FORGE-009 contract — healthy iff the NATS subscription is live AND the orchestrator chain is fully constructed
  @integration @edge-case
  Scenario Outline: The healthz probe reflects the orchestrator's readiness state
    Given forge serve is starting up
    When the orchestrator chain is in <chain_state>
    Then the healthz probe should report <health_status>

    Examples:
      | chain_state                                     | health_status |
      | not yet constructed                             | unhealthy     |
      | fully constructed and the consumer is attached  | healthy       |
      | constructed but the NATS subscription dropped   | unhealthy     |
Update Todos

Phase 1: Gather context from remaining ADRs/DDRs/tasks/runbook

Phase 1: Codebase scan for orchestrator components

Phase 2: Generate Initial Proposal with grouped scenarios

Phase 3: Wait for human curation

Phase 4: Edge Case Expansion offer

Phase 5: Assumption resolution

Phase 6: Write feature file

Phase 6: Write assumptions.yaml

Phase 6: Write summary.md
Write forge-serve-orchestrator-wiring_assumptions.yaml
135 lines
# Assumptions manifest for forge-serve-orchestrator-wiring.feature
# Generated by /feature-spec

feature: "Wire the production pipeline orchestrator into forge serve"
generated: "2026-05-02T00:00:00Z"
stack: "python"
review_required: false

assumptions:
  - id: "ASSUM-001"
    scenario: "(feature-level) Feature ID and slug"
    assumption: "Feature ID is FEAT-FORGE-010; tag slug is @forge-serve-orchestrator-wiring"
    confidence: medium
    basis: "Next ID in the FEAT-FORGE-NNN sequence after F009; gap-doc working title (docs/research/forge-orchestrator-wiring-gap.md §Proposed feature scope)"
    human_response: "confirmed"

  - id: "ASSUM-002"
    scenario: "Daemon startup composes the full orchestrator chain in production"
    assumption: "Supervisor, PipelineConsumerDeps, PipelineLifecycleEmitter, PipelinePublisher, ForwardContextBuilder, and the autobuild_runner subagent are all constructed at daemon startup; no synthetic placeholder remains"
    confidence: high
    basis: "gap doc §What's in scope; verified-as-unwired by the doc's repository-wide grep audit"
    human_response: "confirmed"

  - id: "ASSUM-003"
    scenario: "The autobuild stage runs as an asynchronous subagent and the supervisor stays responsive"
    assumption: "autobuild_runner uses the DeepAgents AsyncSubAgent middleware via start_async_task with ASGI transport, registered as a separate graph in langgraph.json; supervisor uses AsyncSubAgentMiddleware tools (start/check/update/cancel/list)"
    confidence: high
    basis: "ADR-ARCH-031 explicit — sync task() for bounded delegation, AsyncSubAgent for autobuild"
    human_response: "confirmed"

  - id: "ASSUM-004"
    scenario: "Each real stage transition publishes its own stage-complete envelope"
    assumption: "The synthetic dispatch-stage stage-complete envelope from the superseded TASK-FORGE-FRR-001 is not preserved; only real stage transitions emit stage-complete envelopes"
    confidence: medium
    basis: "gap doc explicit — 'the new feature publishes the real per-stage envelope sequence … no synthetic stubs'; FRR-001 SUPERSEDED note records the synthetic envelope as 'no longer load-bearing'"
    human_response: "confirmed"

  - id: "ASSUM-005"
    scenario: "The durable consumer is configured to enforce one outstanding build at a time"
    assumption: "PIPELINE durable consumer is configured with max_ack_pending=1"
    confidence: high
    basis: "ADR-ARCH-014 + API-nats-pipeline-events §2.2"
    human_response: "confirmed"

  - id: "ASSUM-006"
    scenario: "The durable consumer is configured to enforce one outstanding build at a time"
    assumption: "Durable consumer name is 'forge-serve' (matches the FEAT-FORGE-009 daemon's existing durable)"
    confidence: high
    basis: "forge-production-image ASSUM-006 ('forge serve uses a single shared durable consumer named forge-serve'); RESULTS evidence at GB10 first-real-run referenced 'nats consumer info PIPELINE forge-serve'"
    human_response: "confirmed"

  - id: "ASSUM-007"
    scenario: "The inbound JetStream message is acknowledged exactly when the build reaches a terminal state"
    assumption: "Forge acknowledges only on COMPLETE / FAILED / CANCELLED / SKIPPED; PAUSED leaves the message unacked"
    confidence: high
    basis: "API-nats-pipeline-events §2.2 acknowledgement rule"
    human_response: "confirmed"

  - id: "ASSUM-008"
    scenario: "The configured ack_wait covers the longest expected build duration"
    assumption: "ack_wait is configured to approximately one hour to cover the longest expected build"
    confidence: high
    basis: "API-nats-pipeline-events §2.2 ConsumerConfig snippet"
    human_response: "confirmed"

  - id: "ASSUM-009"
    scenario: "A crash mid-build is recovered after restart by the daemon's reconciliation routines"
    assumption: "Both pipeline_consumer.reconcile_on_boot and forge.lifecycle.recovery.reconcile_on_boot are wired into _run_serve at daemon startup"
    confidence: high
    basis: "gap doc explicit — both functions are named, neither has a caller today"
    human_response: "confirmed"

  - id: "ASSUM-010"
    scenario: "A paused build survives daemon restart and re-emits its approval request"
    assumption: "emit_build_paused / emit_build_resumed are wired in this feature; if implementation discovers the change is not a one-line addition, the pause/resume publish is split into a follow-up task"
    confidence: medium
    basis: "gap doc conditional — 'if it's a one-line addition, include; otherwise track separately'"
    human_response: "confirmed"

  - id: "ASSUM-011"
    scenario: "The consumer and the publisher share the daemon's single NATS connection"
    assumption: "One NATS connection per daemon process; the inbound consumer and the outbound publisher share it; no second connection is opened"
    confidence: high
    basis: "TASK-FORGE-FRR-001 implementation note — opening a second connection is an anti-pattern for a single-process daemon"
    human_response: "confirmed"

  - id: "ASSUM-012"
    scenario: "The healthz probe reflects the orchestrator's readiness state"
    assumption: "The healthz endpoint extends the FEAT-FORGE-009 contract — healthy iff the NATS subscription is live AND the orchestrator chain is fully constructed; unhealthy during startup until both are true"
    confidence: medium
    basis: "FEAT-FORGE-009's existing healthz returns healthy iff the JetStream subscription is live; this feature adds the construction-readiness gate so the operator does not see 'healthy' while dispatch is still going to a stub"
    human_response: "confirmed"

  - id: "ASSUM-013"
    scenario: "A malformed build-queued payload publishes a build-failed envelope and is acknowledged"
    assumption: "Validation failures publish build-failed with a malformed-payload reason and acknowledge the inbound message"
    confidence: high
    basis: "API-nats-pipeline-events §2.3 validation rule 1"
    human_response: "confirmed"

  - id: "ASSUM-014"
    scenario: "A duplicate build-queued envelope is acknowledged and skipped without re-running"
    assumption: "Duplicate detection uses the SQLite unique index on (feature_id, correlation_id)"
    confidence: high
    basis: "API-nats-pipeline-events §2.3 validation rule 2"
    human_response: "confirmed"

  - id: "ASSUM-015"
    scenario: "A build whose feature configuration path falls outside the worktree allowlist is rejected"
    assumption: "A path outside the worktree allowlist publishes build-failed with a path-outside-allowlist reason before any orchestrator dispatch"
    confidence: high
    basis: "API-nats-pipeline-events §2.3 validation rule 3"
    human_response: "confirmed"

  - id: "ASSUM-016"
    scenario: "An approval response with a mismatched correlation identifier does not resume any paused build"
    assumption: "Approval reply subjects are correlation-keyed per Convention B; mismatched correlation identifiers are dropped"
    confidence: high
    basis: "DDR-001 reply-subject correlation"
    human_response: "confirmed"

  - id: "ASSUM-017"
    scenario: "On daemon restart the durable history is the authoritative source for build state"
    assumption: "On crash recovery the async_tasks state channel is read as advisory; SQLite history is the authoritative source"
    confidence: high
    basis: "DDR-006 crash-recovery linkage; ADR-ARCH-008 SQLite as durable truth, NATS / state-channel as derived projection"
    human_response: "confirmed"

  - id: "ASSUM-018"
    scenario: "A stage-complete envelope emitted from within the autobuild subagent records the asynchronous task identifier"
    assumption: "Stage-complete envelopes emitted from within autobuild_runner set target_identifier to the subagent's task identifier and target_kind to 'subagent'"
    confidence: medium
    basis: "DDR-006 schema fields + API-nats-pipeline-events §3.2 StageCompletePayload target_kind/target_identifier semantics"
    human_response: "confirmed"
Write forge-serve-orchestrator-wiring_summary.md
190 lines
# Feature Spec Summary: Wire the production pipeline orchestrator into forge serve

**Feature ID**: FEAT-FORGE-010
**Stack**: python
**Generated**: 2026-05-02T00:00:00Z
**Scenarios**: 31 total (4 smoke, 4 regression)
**Assumptions**: 18 total (13 high / 5 medium / 0 low confidence)
**Review required**: No — every assumption traceable to a supplied ADR, DDR, contract, or the gap-finding doc

## Scope

Specifies the production composition that turns `forge serve` from a
receipt-only daemon (FEAT-FORGE-009) into the canonical host for the full
pipeline orchestrator. Covers the wiring of components that already exist
as un-instantiated capability — `Supervisor`, `PipelineConsumerDeps`,
`PipelineLifecycleEmitter`, `PipelinePublisher`, `ForwardContextBuilder`,
plus the net-new `autobuild_runner` AsyncSubAgent — into a single startup
chain that consumes a `pipeline.build-queued.<feature_id>` envelope,
runs the build through the canonical Mode A stage chain, publishes the
real lifecycle envelope sequence (`build-started`, `stage-complete×N`,
`build-paused`/`build-resumed` if paused, terminal envelope) back to
JetStream with the inbound `correlation_id` threaded through every event,
and survives crash + restart with no lost or duplicated builds.

The feature deliberately stays at the **integration / wiring** layer.
Orchestration semantics (Mode A stage chain, gating policy, pause/resume
rules, per-feature loop, constitutional pull-request review) are already
specified in `features/mode-a-greenfield-end-to-end/`. This feature
verifies the production composition that satisfies those Mode A
scenarios in the running daemon, plus the daemon-process invariants that
came in with FEAT-FORGE-009 (healthz, single shared NATS connection,
durable consumer with `max_ack_pending=1`, terminal-only ack, sequential
builds across replicas).

The feature carries forward the seam-refactor design from the superseded
TASK-FORGE-FRR-001 (`_serve_daemon._process_message` contract change to
`(_MsgLike) -> None`, deferred-ack to the state machine,
`max_ack_pending=1` on the durable) and explicitly drops FRR-001's
synthetic dispatch-stage `stage-complete` placeholder — only real stage
transitions emit `stage-complete` envelopes.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 7 |
| Boundary conditions (@boundary) | 5 |
| Negative cases (@negative) | 7 |
| Edge cases (@edge-case) | 13 |
| Smoke (@smoke) | 4 |
| Regression (@regression) | 4 |
| Security (@security) | 3 |
| Data integrity (@data-integrity) | 3 |
| Integration (@integration) | 2 |

Note: several scenarios carry multiple tags (e.g. boundary + negative,
edge-case + security, edge-case + data-integrity). Group totals do not
sum to 31.

## Group Layout

| Group | Theme | Scenarios |
|-------|-------|-----------|
| A | Key Examples — full lifecycle envelope sequence end-to-end, daemon-startup chain composition, correlation-id threading, AsyncSubAgent dispatch, real-stage-complete invariant, build-started/terminal bookends, single shared NATS connection | 7 |
| B | Boundary Conditions — `max_ack_pending=1` + canonical durable name, terminal-only ack outline (4 terminal states), paused-not-acked, minimal single-stage envelope sequence, ack_wait covers longest build | 5 |
| C | Negative Cases — receipt-only stub no longer reachable, malformed payload → build-failed, duplicate detection skip, path outside allowlist → build-failed, dispatch error contained, publish failure does not regress recorded transition | 6 |
| D | Edge Cases — crash recovery via paired reconcile_on_boot, paused build survives restart, approval response → build-resumed, two-replica failover, cancel propagates through subagent, SIGTERM leaves message unacked | 6 |
| E | Edge Case Expansion — autobuild_runner worktree confinement, mismatched-correlation approval ignored, lifecycle publish ordering invariant, durable history authoritative on recovery, in-subagent stage-complete carries task_id, fail-fast on NATS unreachable, healthz reflects orchestrator readiness | 7 |

## Deferred Items

None.

## Assumptions Summary

| ID | Confidence | Subject | Response |
|----|------------|---------|----------|
| ASSUM-001 | medium | Feature ID FEAT-FORGE-010 / slug @forge-serve-orchestrator-wiring | confirmed |
| ASSUM-002 | high | Components constructed at daemon startup | confirmed |
| ASSUM-003 | high | autobuild_runner shape (AsyncSubAgent, ASGI, separate graph) | confirmed |
| ASSUM-004 | medium | Synthetic dispatch-stage envelope from FRR-001 not preserved | confirmed |
| ASSUM-005 | high | max_ack_pending=1 on PIPELINE durable | confirmed |
| ASSUM-006 | high | Durable consumer name "forge-serve" | confirmed |
| ASSUM-007 | high | Terminal-only ack (COMPLETE/FAILED/CANCELLED/SKIPPED) | confirmed |
| ASSUM-008 | high | ack_wait approximately one hour | confirmed |
| ASSUM-009 | high | Both reconcile_on_boot routines run at daemon startup | confirmed |
| ASSUM-010 | medium | emit_build_paused / emit_build_resumed in scope | confirmed |
| ASSUM-011 | high | Single shared NATS connection (no second connection) | confirmed |
| ASSUM-012 | medium | Healthz reflects orchestrator readiness, not just NATS | confirmed |
| ASSUM-013 | high | Malformed payload → build-failed + ack | confirmed |
| ASSUM-014 | high | Duplicate detection via SQLite unique index | confirmed |
| ASSUM-015 | high | Path outside allowlist → build-failed | confirmed |
| ASSUM-016 | high | Correlation-keyed approval reply subjects (DDR-001) | confirmed |
| ASSUM-017 | high | Durable history authoritative on recovery (DDR-006, ADR-ARCH-008) | confirmed |
| ASSUM-018 | medium | Stage-complete from autobuild carries subagent task_id | confirmed |

## Upstream Dependencies

This feature is purely composition; it inherits behaviour from prior features.

- **FEAT-FORGE-001** — Pipeline State Machine & Configuration. The build queue,
  state-machine transitions, durable history, crash recovery
  (retry-from-scratch), and CLI steering surface are the substrate this
  feature wires into. No new transitions are added.
- **FEAT-FORGE-002** — NATS Fleet Integration. The pipeline-event
  publishing contract (correlation threading), approval channel, and
  PipelinePublisher class are inherited; this feature constructs the
  publisher and emitter in production.
- **FEAT-FORGE-004** — Confidence-Gated Checkpoint Protocol. Pause/resume
  semantics (`emit_build_paused`, `emit_build_resumed`,
  `ApprovalResponsePayload` round-trip, idempotent first-wins) are
  inherited; this feature wires the publish-back path so subscribers
  observe pause/resume.
- **FEAT-FORGE-007** — Mode A Greenfield End-to-End. **The orchestration
  semantics are already specified there.** This feature does not
  re-spec them; it verifies that the production composition causes those
  scenarios to execute against the wired-in-production stack rather than
  only against unit tests with mocked dispatchers.
- **FEAT-FORGE-009** — Forge Production Image. The daemon process,
  healthz endpoint, JetStream durable attach, and SIGTERM handling are
  inherited; this feature changes `_process_message`'s seam contract,
  switches `max_ack_pending` from default to 1, adds the
  reconcile_on_boot pair, and replaces the receipt-only `_default_dispatch`
  with the real orchestrator dispatch.

## Carried-forward design (from superseded tasks)

The following design elements from the superseded `TASK-FORGE-FRR-001`
and `TASK-FORGE-FRR-001b` remain load-bearing for this feature's plan:

- The `_serve_daemon._process_message` seam-refactor: change `DispatchFn`
  from `(bytes) -> None` to `(_MsgLike) -> None`; remove the
  post-dispatch ack on the success path; ack moves into
  `pipeline_consumer.handle_message`'s deferred `ack_callback`.
- `max_ack_pending=1` on the `forge-serve` durable's `ConsumerConfig`.
  Operational note: changing this on an existing JetStream consumer
  requires recreating it (`nats consumer rm PIPELINE forge-serve` before
  deploying the new image).
- The originator-allowlist finding: jarvis chat REPL's
  `originating_adapter="terminal"` is in `DEFAULT_APPROVED_ORIGINATORS`;
  `triggered_by="jarvis"` is a separate field that the consumer does not
  gate on. No change required.

The following are **not** carried forward:

- The "synthetic dispatch-stage publish to satisfy AC #2 literally"
  recommendation from FRR-001's Phase 2.8 design checkpoint. ASSUM-004
  records this drop explicitly.

## Open scope check (for /feature-plan)

- **Pause/resume publish (ASSUM-010)**: medium-confidence inclusion. If
  implementation discovers the `emit_build_paused` / `emit_build_resumed`
  hookup is materially more than a one-line change at the relevant call
  sites, `/feature-plan` should split it into a follow-up task and drop
  the related Group D and Group E scenarios from this feature's
  acceptance set rather than leave them as silent passes.
- **`stage-complete` from inside the AsyncSubAgent (ASSUM-018)**:
  medium-confidence — the precise mechanism by which the subagent reaches
  the `PipelineLifecycleEmitter` (passing it through dispatcher context
  vs. watching the `async_tasks` state channel from outside) is the open
  architectural question carried over from FRR-001b. `/feature-plan`
  should pick a path and capture it as a DDR or in the implementation
  guide before tasks are created.

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "Wire the production pipeline orchestrator into forge serve" \
      --context features/forge-serve-orchestrator-wiring/forge-serve-orchestrator-wiring_summary.md

`/feature-plan` Step 11 will link `@task:<TASK-ID>` tags back into the
`.feature` file after tasks are created.

## Provenance

This feature was filed as the result of the FEAT-JARVIS-INTERNAL-001
first-real-run on GB10, 2026-05-01, correlation_id
`a58ec9a7-27c6-485a-beac-e18675639a10`, where the runbook's Phase 7 close
criterion ("between-prompt notifications render in the chat REPL, showing
stage-complete events for FEAT-43DE") could not be met because nothing
on the forge side publishes anything back. The investigation that
followed produced `docs/research/forge-orchestrator-wiring-gap.md` —
which is the authoritative scope source for this spec. The original
follow-up tasks `TASK-FORGE-FRR-001` and `TASK-FORGE-FRR-001b` are
marked superseded-by-feature and carried in
`tasks/completed/TASK-FORGE-FRR-001/` and
`tasks/completed/TASK-FORGE-FRR-001b/` as historical context.
Update Todos

Phase 1: Gather context

Phase 1: Codebase scan

Phase 2: Initial Proposal

Phase 3: Curation

Phase 4: Edge Case Expansion

Phase 5: Assumption resolution

Phase 6: Write feature file

Phase 6: Write assumptions.yaml

Phase 6: Write summary.md

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE SPEC COMPLETE: Wire the production pipeline orchestrator into forge serve
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Files written:
  features/forge-serve-orchestrator-wiring/forge-serve-orchestrator-wiring.feature
  features/forge-serve-orchestrator-wiring/forge-serve-orchestrator-wiring_assumptions.yaml
  features/forge-serve-orchestrator-wiring/forge-serve-orchestrator-wiring_summary.md

Scenarios: 31 total
  @key-example: 7   @boundary: 5
  @negative: 7      @edge-case: 13
  @smoke: 4         @regression: 4
  @security: 3      @data-integrity: 3
  @integration: 2

Assumptions: 18 total
  high: 13 (auto-proceed)
  medium: 5 (Coach review recommended)
  low: 0

REVIEW REQUIRED: No — every assumption traceable to a supplied ADR, DDR,
contract, or the gap-finding doc

Deferred: 0 scenario groups

Next steps:
  Review:    [forge-serve-orchestrator-wiring.feature](features/forge-serve-orchestrator-wiring/forge-serve-orchestrator-wiring.feature)
  Pass to feature-plan:
    /feature-plan "Wire the production pipeline orchestrator into forge serve" \
      --context features/forge-serve-orchestrator-wiring/forge-serve-orchestrator-wiring_summary.md
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Two open scope checks the summary flags for /feature-plan to settle before tasks are created:

ASSUM-010 (pause/resume publish) — medium-confidence inclusion; if the wiring is not a one-line addition, split into a follow-up task and drop the related D2/D3/E2 scenarios from the acceptance set.
ASSUM-018 (in-subagent stage-complete carries task_id) — the open question carried from superseded TASK-FORGE-FRR-001b: how the PipelineLifecycleEmitter reaches the autobuild_runner subagent (dispatcher-context vs. async-tasks-channel watcher). /feature-plan should pick a path and capture it as a DDR.
what do you recommend for these towo open scope checks?
Recommendations
ASSUM-018 (how the emitter reaches autobuild_runner): Option A — thread the emitter through dispatcher context
The natural attachment point is DDR-006's _update_state helper. Every lifecycle transition already writes to the async_tasks state channel from there; emitting the matching NATS envelope at the same boundary is one extra call, in the same control flow.

Why over Option B (state-channel watcher):

ADR-ARCH-031 pins ASGI co-deployment as the default transport. The subagent runs in the daemon's process, so the emitter is a reachable Python object — the "decouple from the publisher" argument is theoretical until/unless HTTP transport gets its own ADR.
A polling watcher introduces a real UX downgrade: <1s polling churns CPU for nothing, >1s makes operators see lagging progress. Inline publish is effectively free (fire-and-forget per the API contract's §3.3 PubAck ≠ success rule).
State-channel lifecycle values (running_wave, awaiting_approval) are coarser than stage-complete envelopes — a watcher would need to read more granular subagent state, duplicating shape decisions.
Crash recovery is the same in both options (SQLite is authoritative per ADR-ARCH-008); Option B doesn't buy durability.
Failure stack stays in one place: a publish error sits in the subagent's call stack, not in a separate watcher process.
The one bet: ASGI co-deployment stays the default. ADR-ARCH-031 already commits to that, so the bet is consistent with existing architecture.

ASSUM-010 (pause/resume publish): Include in scope
Conditional on Option A above. Once the emitter is reachable from the subagent's _update_state helper, emit_build_paused is one call at the same boundary as the lifecycle="awaiting_approval" state-channel write (DDR-006 already locates this). emit_build_resumed lives in the existing approval_subscriber resume path. Both are genuinely one-liners under Option A.

If /feature-plan's investigation discovers Option A is harder than expected (e.g. DeepAgents 0.5.3 won't accept non-serializable objects in subagent context), the fallback is to split pause/resume into a follow-up — but the spec's medium confidence already accounts for that escape hatch.

Suggested action before /feature-plan runs
File one DDR-007 — pipeline lifecycle emitter wiring path capturing Option A as the chosen architecture, the _update_state co-location decision, and the ASGI-transport dependency. That settles ASSUM-018 → high confidence and ASSUM-010 → high confidence, removes both open questions from /feature-plan's plate, and gives the task decomposition a fixed target.

Want me to draft DDR-007?

yes and seed it to Graphiti
Bash List existing DDRs
IN
ls docs/design/decisions/

OUT
DDR-001-reply-subject-correlation.md
DDR-002-resume-value-rehydration-helper.md
DDR-003-sqlite-schema-layout-wal.md
DDR-004-graphiti-group-partitioning.md
DDR-005-cli-context-manifest-resolution.md
DDR-006-async-subagent-state-channel-contract.md
Read DDR-002-resume-value-rehydration-helper.md
Write DDR-007-pipeline-lifecycle-emitter-wiring-path.md
111 lines
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
Now seeding to Graphiti. Loading the tool schema first.

Bash Check graphiti group config
IN
cat .guardkit/graphiti.yaml 2>/dev/null | head -40

OUT
# Graphiti Knowledge Graph Configuration
#
# This file configures the Graphiti integration for GuardKit.
# FalkorDB runs on the Synology DS918+ NAS, accessible via Tailscale.
#
# LLM Endpoint Switching:
#   To switch between GB10 and MacBook LLM, toggle the llm_provider/llm_base_url/
#   llm_model settings below. See docs/reference/graphiti-macbook-offload.md for
#   full setup instructions and the toggle script.
#
# All settings can be overridden via environment variables:
#   - GRAPHITI_ENABLED: Enable/disable integration
#   - GRAPH_STORE: Graph backend ('falkordb' or 'neo4j')
#   - FALKORDB_HOST: FalkorDB host
#   - FALKORDB_PORT: FalkorDB port
#   - GRAPHITI_TIMEOUT: Connection timeout in seconds
#
# FalkorDB on NAS:
#   ssh richardwoollcott@whitestocks
#   cd /volume1/guardkit/docker
#   sudo docker-compose -f docker-compose.falkordb.yml up -d
#
# FalkorDB Browser UI: http://whitestocks:3000

# Project ID for namespace prefixing
# This ensures knowledge persists across directory moves/renames
project_id: forge

# Enable Graphiti integration (set to false to disable)
enabled: true

# Graph database backend
graph_store: falkordb

# FalkorDB connection (Synology DS918+ NAS via Tailscale)
falkordb_host: whitestocks
falkordb_port: 6379

# Connection settings
timeout: 30.0
Bash Find group_id naming convention
IN
grep -E "group_id|groups:|forge_" .guardkit/graphiti.yaml | head -20

OUT
group_ids:
Bash Read group_ids block
IN
grep -A 30 "group_ids:" .guardkit/graphiti.yaml

OUT
group_ids:
  - project_architecture    # Bounded contexts, components, cross-cutting concerns, assumptions
  - architecture_decisions  # ADRs and design rationale
  - project_decisions       # Technology and infrastructure decisions
  - command_workflows       # GuardKit command patterns and usage

# Deprecated fields (kept for backwards compatibility)
Graphiti [add_memory]
OUT
{"result":{"message":"Episode 'DDR-007 Pipeline Lifecycle Emitter Wiring Path' queued for processing in group 'architecture_decisions'"}}
Done. Two artefacts in place:

DDR drafted: DDR-007-pipeline-lifecycle-emitter-wiring-path.md
Graphiti episode queued in architecture_decisions group with the decision summary, rejected options, rationale, trade-offs, failure-mode contract, and provenance back to the GB10 first-real-run correlation_id.
With DDR-007 in place, the FEAT-FORGE-010 spec's two open scope checks are settled — both ASSUM-010 and ASSUM-018 promote to high confidence. /feature-plan can proceed without re-litigating the architecture.

Want me to update forge-serve-orchestrator-wiring_assumptions.yaml and forge-serve-orchestrator-wiring_summary.md to reflect the confidence promotions and reference DDR-007?

please provide the /feature-plan command syntax with the appropriate --context arguments for the docs to provide

/feature-plan "Wire the production pipeline orchestrator into forge serve" \
  --context=features/forge-serve-orchestrator-wiring/forge-serve-orchestrator-wiring_summary.md \
  --context=features/forge-serve-orchestrator-wiring/forge-serve-orchestrator-wiring.feature \
  --context=features/forge-serve-orchestrator-wiring/forge-serve-orchestrator-wiring_assumptions.yaml \
  --context=docs/research/forge-orchestrator-wiring-gap.md \
  --context=docs/design/decisions/DDR-007-pipeline-lifecycle-emitter-wiring-path.md \
  --context=docs/design/contracts/API-nats-pipeline-events.md \
  --context=docs/architecture/decisions/ADR-ARCH-014-single-consumer-max-ack-pending.md \
  --context=docs/architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md \
  --context=docs/architecture/decisions/ADR-ARCH-021-paused-via-langgraph-interrupt.md \
  --context=docs/architecture/decisions/ADR-ARCH-008-forge-produces-own-history.md \
  --context=docs/architecture/decisions/ADR-ARCH-027-no-horizontal-scaling.md \
  --context=docs/design/decisions/DDR-006-async-subagent-state-channel-contract.md \
  --context=docs/design/decisions/DDR-001-reply-subject-correlation.md \
  --context=docs/state/TASK-FORGE-FRR-001/implementation_plan.md \
  --context=features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end_summary.md \
  --context=features/forge-production-image/forge-production-image.feature
What each --context group does for the plan
Files	Role
The 3 spec artefacts (_summary, .feature, _assumptions)	Primary input — Step 11 links @task: tags into the .feature; assumptions tell the planner which decisions are confirmed
forge-orchestrator-wiring-gap.md	Authoritative scope source — the in-scope / out-of-scope tables and the empirical evidence chain
DDR-007	Settles ASSUM-010 + ASSUM-018; pins the emitter wiring path so task decomposition has a fixed target
API-nats-pipeline-events.md	The bus contract this feature must conform to (consumer config, payload shapes, ack rules)
5 ADRs	The non-negotiable architectural constraints (transport-level sequential builds, AsyncSubAgent shape, pause via interrupt, SQLite as authoritative, single-process invariant)
DDR-006 + DDR-001	The state-channel schema (DDR-007's attachment point) and the correlation-keyed reply-subject convention
TASK-FORGE-FRR-001/implementation_plan.md	The seam-refactor design carried forward from the superseded task — load-bearing for the daemon-side tasks
Mode A summary + production-image .feature	Upstream behaviour this feature composes — Mode A semantics are inherited (not re-spec'd); F009 daemon-process is the foundation
If you want a leaner invocation, the minimum that still carries the load is the 3 spec artefacts + DDR-007 + the gap doc + API-nats-pipeline-events.md + the FRR-001 implementation plan. The five ADRs and two DDRs are anchoring constraints — /feature-plan will read them when it needs to justify a task boundary, but it can also discover them through the summary's references section if context budget is tight.