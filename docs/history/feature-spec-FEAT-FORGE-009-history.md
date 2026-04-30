/feature-spec FEAT-FORGE-009-production-image

Context loaded: stack=python, 8 existing .feature files (FEAT-FORGE-001..008 family), 1 scoping doc (F8-007b — exhaustive seed input with AC-A..J + 8 open questions, of which §11.4 is now resolved), 1 ADR (ADR-ARCH-032 — Python 3.14 baseline + LCOI providers), fleet manifest with 5 tools confirmed, no Dockerfile present, forge serve does not yet exist in src/forge/cli/main.py:80-93.

Proceeding directly to Phase 2.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE SPEC PROPOSAL: Forge Production Image
                       (Dockerfile + forge serve daemon)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@feat-forge-009 @production-image
Feature: Forge Production Image
  As Rich, the sole operator of Forge
  I want a canonical, multi-stage container image that ships the full
    forge CLI surface and runs forge serve as its long-lived daemon
  So that the LES1 parity gates (CMDW, PORT, ARFS, canonical-freeze)
    of FEAT-FORGE-008 Phase 6 can run unblocked, the FinProxy first-run
    runbook executes verbatim, and no canonical build path depends on
    a developer-host editable install or a sibling working tree

  Background:
    Given the forge repository is checked out at a fresh clone
    And the sibling nats-core working tree is available alongside it
    And no Dockerfile-side mutation of pyproject.toml or .env is required

━━ GROUP A: Key Examples (5 scenarios) ━━

  # Why: Core build path — establishes that the canonical image can be produced
  #      from a clean clone using the runbook-documented invocation. (AC-A, AC-E)
  @key-example @smoke
  Scenario: The production image builds from a fresh clone using the canonical invocation
    Given a clean checkout of the forge repository
    And the nats-core sibling source is reachable as a named build context
    When the operator runs the canonical production-image build command
    Then a tagged production image should be produced
    And the image should have been assembled via two stages — a builder stage and a slimmer runtime stage
    And the install command used inside the image should match the install command documented in the validation runbook word-for-word

  # Why: Confirms the CLI surface (PORT structural prerequisite) is intact in the image
  @key-example @smoke
  Scenario: The production image exposes the full forge CLI surface
    Given a built production image
    When the operator runs the forge help command inside the container
    Then the help output should list every documented subcommand —
      queue, status, history, cancel, skip, and the new serve subcommand
    And no subcommand should be hidden or missing

  # Why: CMDW round-trip — the daemon must subscribe and receive a real
  #      published payload, not silently fail to register the consumer.
  @key-example @smoke
  Scenario: The production image runs forge serve as a long-lived daemon and receives a queued build
    Given a built production image
    And a reachable JetStream broker
    When the container is started with forge serve as its main process
    And a build payload is published to the build-queued subject
    Then the daemon should remain running as the container's main process
    And the daemon should receive the published payload through its JetStream subscription
    And the receipt should be observable to the operator without exec'ing into the container

  # Why: ARFS structural check — every fleet tool must survive into the runtime image
  @key-example
  Scenario: The agent manifest inside the image lists every fleet tool
    Given a built production image
    When the manifest-build code path runs inside the container
    Then the resulting manifest should include forge_greenfield, forge_feature, forge_review_fix, forge_status, and forge_cancel
    And each tool should be reachable via the installed forge package — not via mounted source

  # Why: Canonical-freeze gate — verbatim runbook execution from a clean machine
  @key-example
  Scenario: The runbook Phase 6 build invocation succeeds verbatim
    Given a clean machine with only the documented prerequisites installed
    When the operator copy-pastes the Phase 6.1 build command from the validation runbook
    Then the image should build without any host-side patching of pyproject.toml, .env, or symlinks
    And any required setup should already be present as copy-pastable shell blocks at the top of Phase 6.1

━━ GROUP B: Boundary Conditions (5 scenarios) ━━

  # Why: Just-inside boundary — image must start without provider-key envs set
  @boundary
  Scenario: The container starts cleanly when no provider API keys are supplied
    Given a built production image
    And no provider API key environment variables are set
    When the container is started with forge serve
    Then the daemon should start without error
    And the daemon should remain running until a build payload requires a provider
    # [ASSUMPTION: confidence=medium] Provider absence becomes a per-build error, not a startup error

  # Why: Just-inside boundary — default NATS URL must work when env unset
  @boundary
  Scenario: forge serve binds to the documented default NATS URL when no override is supplied
    Given a built production image
    And the FORGE_NATS_URL environment variable is not set
    When the container is started with forge serve
    Then the daemon should attempt its JetStream subscription against the documented default broker URL
    # [ASSUMPTION: confidence=high] Default is nats://127.0.0.1:4222 (see src/forge/cli/queue.py:265)

  # Why: Just-inside boundary — the literal-match install command (LES1 §3 DKRX)
  @boundary
  Scenario Outline: The install command in the Dockerfile matches the runbook documentation
    Given the Dockerfile in the repository root
    When the install command is extracted from the builder stage
    Then it should match the install command documented in <runbook_section> exactly

    Examples:
      | runbook_section                          |
      | RUNBOOK-FEAT-FORGE-008 Phase 0.4         |
      | RUNBOOK-FEAT-FORGE-008 Phase 6.1         |

  # Why: Just-outside boundary — image-size regression is a CI-visible gate
  @boundary @negative
  Scenario: The image fails the size regression check when its uncompressed size exceeds the budget
    Given a build pipeline that enforces an image-size budget
    # [ASSUMPTION: confidence=low] Budget is 1.0 GB uncompressed (scoping §11.7 cites 600–900 MB typical)
    When a built image exceeds the documented budget
    Then the size regression check should fail
    And the failure should name the size budget and the actual image size

  # Why: Health probe boundary — healthy vs. unhealthy is the contract
  @boundary
  Scenario Outline: The container health probe reflects the daemon's subscription state
    Given a running container started with forge serve
    When the daemon's JetStream subscription is in <subscription_state>
    Then the container's reported health status should be <health_status>

    Examples:
      | subscription_state           | health_status |
      | live and ready               | healthy       |
      | not yet established          | unhealthy     |
      | dropped without recovery yet | unhealthy     |
    # [ASSUMPTION: confidence=medium] Health is exposed via an HTTP /healthz endpoint on a documented port

━━ GROUP C: Negative Cases (5 scenarios) ━━

  # Why: Hard CI gate — no real provider keys may be baked into any image layer
  @negative @smoke
  Scenario: The image contains no real provider API keys in any layer
    Given a built production image
    When every layer of the image is scanned for provider key material
    Then no real provider API key should be present in any layer
    And the build pipeline should fail if such a key is detected

  # Why: Container must not run as root — security baseline
  @negative @smoke
  Scenario: The container runs as a non-root user
    Given a built production image
    When the container is started with any documented subcommand
    Then the running process should belong to a dedicated non-root user
    And that user should not have administrative privileges inside the container

  # Why: Missing build context for nats-core must fail clearly, not silently
  @negative
  Scenario: The build fails with a clear diagnostic when the nats-core build context is missing
    Given a build invocation that omits the nats-core named build context
    When the operator attempts to build the image
    Then the build should fail before producing a tagged image
    And the failure message should name the missing build context and how to supply it

  # Why: Editable installs must not survive into the runtime stage (LES1 §3 DKRX)
  @negative
  Scenario: The runtime image contains no editable installs
    Given a built production image
    When the installed forge distribution is inspected inside the runtime stage
    Then forge should be present as a regular installed distribution
    And no .pth-style editable install pointer should be present in the runtime venv

  # Why: forge serve must not silently accept missing canonical configuration
  @negative
  Scenario: forge serve refuses to start when its required configuration is invalid
    Given a built production image
    And a configuration file that fails its canonical schema check
    When the container is started with forge serve against that configuration
    Then the daemon should refuse to start
    And the container should exit with a non-zero status
    And the operator should see a diagnostic naming the offending configuration field

━━ GROUP D: Edge Cases (5 scenarios) ━━

  # Why: CMDW failure mode — stale image silently fails to receive payloads
  @edge-case @regression
  Scenario: A stale image whose fleet manifest has drifted is detected before a build is dispatched
    Given a production image whose embedded manifest is older than the canonical fleet manifest
    When the operator queues a build that targets a tool added after the image was built
    Then the dispatch should refuse to route the build to the stale image
    And the operator should be told that the image is out of date and how to refresh it

  # Why: Concurrency — two daemons must not double-process the same payload
  @edge-case
  Scenario: Two concurrently running daemons do not double-process the same queued build
    Given two containers running forge serve against the same JetStream broker
    When a single build payload is published to the build-queued subject
    Then the payload should be delivered to exactly one daemon
    And the other daemon should observe the build as already claimed
    # [ASSUMPTION: confidence=medium] forge serve uses a JetStream durable consumer with shared name

  # Why: NATS transient unavailability must not require a container restart
  @edge-case
  Scenario: forge serve recovers automatically when the broker is briefly unavailable
    Given a running daemon with a live subscription
    When the JetStream broker becomes unavailable for a short interval
    And the broker becomes available again
    Then the daemon should re-establish its subscription without operator intervention
    And buffered payloads published during the outage should be delivered once the subscription is restored
    # [ASSUMPTION: confidence=low] Reconnect window is bounded by JetStream's standard durable consumer redelivery

  # Why: Cache-poisoning regression — pyproject changes must invalidate the install layer
  @edge-case @regression
  Scenario: A pyproject change actually changes the installed dependencies in the rebuilt image
    Given a previous production image built against pyproject revision X
    And a pyproject revision Y that adds or upgrades a dependency
    When the image is rebuilt against revision Y
    Then the installed dependency set in the rebuilt image should reflect revision Y
    And no stale install layer from revision X should be reused incorrectly

  # Why: CI workflow scope — guards the three trigger paths
  @edge-case @regression
  Scenario Outline: The CI image-build workflow runs on pull requests touching the production-image surface
    Given a pull request that changes <changed_path>
    When the CI pipeline is evaluated for that pull request
    Then the production-image build-and-smoke-test workflow should be triggered

    Examples:
      | changed_path     |
      | Dockerfile       |
      | pyproject.toml   |
      | src/forge/       |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total: 20 scenarios across 4 groups
Inferred assumptions: 7 (will be resolved in Phase 5)
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

GROUP A — Key Examples (5 scenarios): _
GROUP B — Boundary Conditions (5 scenarios): _
GROUP C — Negative Cases (5 scenarios): _
GROUP D — Edge Cases (5 scenarios): _
Reply with one action per group (e.g. A A A A, or A M A ? with inline modifications).

forge-build-plan.md
A A A A
All four groups accepted. Moving to Phase 4.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EDGE CASE EXPANSION (optional)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

I've identified 7 additional scenarios covering security,
data integrity, and integration boundaries:

Security (3):
  - Image base layers come from a pinned digest, not a floating tag
  - Build artefacts written by forge serve cannot escape the declared
    artefact volume (no writes to /, /etc, /usr)
  - The container does not expose an unrestricted shell endpoint —
    no listening sshd / debugger port

Data integrity (2):
  - A build that crashes mid-execution leaves the JetStream payload
    redeliverable rather than ack'd-and-lost
  - The artefact registry filesystem survives a container restart
    when mounted at the documented volume path

Integration boundaries (2):
  - When the configured LangChain provider is unavailable at build time,
    forge serve fails the affected build with a clear diagnostic rather
    than crashing the daemon for unrelated builds
  - When the docker image is pulled on an architecture that doesn't
    match what was published, the run fails fast with a clear message

Include them?

[Y] Yes — show and curate them (same A/R/M/+/? actions)
[S] Sample — show 2 examples, then decide
[N] No — skip and proceed to Phase 5

Your choice [Y/S/N]:
Y

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EDGE CASE EXPANSION — full proposal (7 scenarios in 3 groups)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━ GROUP E1: Security (3 scenarios) ━━

  # Why: Floating tags re-resolve silently — supply-chain integrity gate
  @edge-case @smoke
  Scenario: Base images are pinned to an immutable digest
    Given the Dockerfile in the repository root
    When the FROM directives are inspected
    Then every base image reference should be pinned to an immutable content digest
    And no FROM directive should rely on a floating tag alone
    # [ASSUMPTION: confidence=medium] python:3.14-slim-bookworm is pinned by sha256 digest

  # Why: Process must not escape its declared write surfaces
  @edge-case
  Scenario: forge serve cannot write outside the declared artefact volume
    Given a running container started with forge serve
    When the daemon attempts to write to a path outside its declared artefact registry volume
    Then the write should be rejected by the container's filesystem permissions
    And the daemon should surface the rejection through its normal error channel rather than crash

  # Why: Production image must not ship interactive remote-access surfaces
  @edge-case
  Scenario: The container exposes no interactive remote-access endpoint
    Given a built production image
    When the image's exposed ports and runtime processes are inspected
    Then no SSH server, no remote debugger, and no interactive shell endpoint should be listening
    And only the documented serve and health probe ports should be exposed

━━ GROUP E2: Data integrity (2 scenarios) ━━

  # Why: A crashed build must not vanish — JetStream redelivery is the safety net
  @edge-case @regression
  Scenario: A build that crashes mid-execution remains redeliverable
    Given a daemon that has received a build payload
    When the daemon process crashes before acknowledging the payload
    Then the payload should remain pending on the JetStream consumer
    And a subsequent daemon should pick the payload up on its next subscription poll

  # Why: Artefact registry must survive container lifecycle — operator data invariant
  @edge-case
  Scenario: The artefact registry filesystem persists across container restarts
    Given a running container with its artefact volume mounted at the documented path
    And the daemon has produced build artefacts during execution
    When the container is stopped and restarted against the same volume
    Then the previously produced artefacts should still be readable
    And no artefact metadata should have been silently truncated

━━ GROUP E3: Integration boundaries (2 scenarios) ━━

  # Why: One bad provider must not poison the daemon for all other builds
  @edge-case
  Scenario: A failing provider for one build does not crash the daemon for unrelated builds
    Given a daemon currently processing a build that targets an unavailable provider
    When the affected build fails because the provider is unreachable
    Then the daemon should mark only that build as failed with a diagnostic naming the provider
    And the daemon should remain available to receive and process subsequent builds

  # Why: Architecture mismatch must fail fast — silent emulation is a debugging trap
  @edge-case
  Scenario: An architecture-mismatched pull fails fast with a clear diagnostic
    Given a published production image whose declared platform does not match the host
    When the operator attempts to run the image on the mismatched host
    Then the runtime should refuse to start the container
    And the operator should see a diagnostic naming the expected and actual platforms

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CURATION: Review each edge-case group
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  [A] Accept  [R] Reject  [M] Modify  [+] Add  [?] Defer

GROUP E1 — Security (3 scenarios):           _
GROUP E2 — Data integrity (2 scenarios):     _
GROUP E3 — Integration boundaries (2 scen.): _
Reply with one action per group (e.g. A A A).

A A A
All three edge-case groups accepted. Moving to Phase 5.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ASSUMPTION RESOLUTION (10 items)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Each assumption has a proposed default. Press Enter to accept,
or type the actual value.

[1] Default NATS broker URL when FORGE_NATS_URL is unset
    Proposed:   nats://127.0.0.1:4222
    Confidence: high
    Basis:      Hard-coded in src/forge/cli/queue.py:265
    Accept or enter value: _

[2] Provider-key absence policy at daemon startup
    Proposed:   Daemon starts; missing provider becomes a per-build error
                surfaced when a build that needs that provider arrives
    Confidence: medium
    Basis:      Aligns with scoping §3.2 PORT — daemon must not block on
                unset env vars; per-build failure is the natural granularity
                given forge_greenfield/forge_feature can target different providers
    Accept or enter value: _

[3] Image-size budget (uncompressed)
    Proposed:   1.0 GB
    Confidence: low
    Basis:      Scoping §11.7 cites 600–900 MB as typical for slim+LangChain;
                1.0 GB leaves headroom for ARFS scratch tooling and is round
    Accept or enter value: _

[4] Health probe shape
    Proposed:   HTTP /healthz endpoint exposed by forge serve;
                200 OK when JetStream subscription is live, 503 otherwise
    Confidence: medium
    Basis:      Scoping §7 explicitly recommends this shape over a NATS-only
                liveness signal
    Accept or enter value: _

[5] HEALTHCHECK / serve port
    Proposed:   8080
    Confidence: low
    Basis:      Common default for in-container HTTP probes; not stated in
                scoping doc — §11.2 marks port as an open question
    Accept or enter value: _

[6] JetStream consumer naming for forge serve
    Proposed:   Single shared durable consumer name "forge-serve" so
                multiple replicas compete for delivery (work-queue semantics)
    Confidence: medium
    Basis:      Required for D2 (no double-processing) to hold; matches the
                pattern already used elsewhere in forge for build-queue subjects
    Accept or enter value: _

[7] JetStream redelivery / reconnect window
    Proposed:   Standard JetStream durable consumer redelivery applies;
                no custom window beyond the broker's configured ack_wait
    Confidence: low
    Basis:      Inferred from D1 (transient unavailability) being a recovery
                concern, not a custom-policy concern
    Accept or enter value: _

[8] Subcommands listed in `forge --help`
    Proposed:   queue, status, history, cancel, skip, serve
    Confidence: high
    Basis:      First five confirmed in src/forge/cli/main.py:80-93;
                serve is the new subcommand FEAT-FORGE-009 introduces
    Accept or enter value: _

[9] Fleet manifest tools that must appear in the image
    Proposed:   forge_greenfield, forge_feature, forge_review_fix,
                forge_status, forge_cancel
    Confidence: high
    Basis:      Confirmed in src/forge/fleet/manifest.py at lines 50/71/86/101/113
    Accept or enter value: _

[10] Base image pin policy
    Proposed:   FROM python:3.14-slim-bookworm pinned by sha256 digest in
                both builder and runtime stages
    Confidence: medium
    Basis:      ADR-ARCH-032 chooses Python 3.14 and slim-bookworm; digest
                pinning is supply-chain best practice but not explicitly
                stated in the scoping doc
    Accept or enter value: _
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Reply with one line per item (1–10): either accept / blank-equivalent, or a replacement value. You can fast-path with 1:accept 2:accept ... or just paste overrides for the ones you want to change.

accept defaults
All defaults accepted. Writing output files.

Bash Create output directory
IN
mkdir -p /home/richardwoollcott/Projects/appmilla_github/forge/features/forge-production-image && ls /home/richardwoollcott/Projects/appmilla_github/forge/features/forge-production-image/

OUT
(Bash completed with no output)
Write forge-production-image.feature
303 lines
# Generated by /feature-spec
# Feature: Forge Production Image (FEAT-FORGE-009)
# Stack: python
# Assumptions: 10 (see forge-production-image_assumptions.yaml)
# Generated: 2026-04-30T00:00:00Z

@feat-forge-009 @production-image
Feature: Forge Production Image
  As Rich, the sole operator of Forge
  I want a canonical, multi-stage container image that ships the full
    forge CLI surface and runs forge serve as its long-lived daemon
  So that the LES1 parity gates (CMDW, PORT, ARFS, canonical-freeze)
    of FEAT-FORGE-008 Phase 6 can run unblocked, the FinProxy first-run
    runbook executes verbatim, and no canonical build path depends on
    a developer-host editable install or a sibling working tree

  Background:
    Given the forge repository is checked out at a fresh clone
    And the sibling nats-core working tree is available alongside it
    And no Dockerfile-side mutation of pyproject.toml or .env is required

  # ─────────────────────────────────────────────────────────────────────────
  # GROUP A — Key Examples
  # ─────────────────────────────────────────────────────────────────────────

  # Why: Core build path — establishes that the canonical image can be produced
  #      from a clean clone using the runbook-documented invocation. (AC-A, AC-E)
  @key-example @smoke
  Scenario: The production image builds from a fresh clone using the canonical invocation
    Given a clean checkout of the forge repository
    And the nats-core sibling source is reachable as a named build context
    When the operator runs the canonical production-image build command
    Then a tagged production image should be produced
    And the image should have been assembled via two stages — a builder stage and a slimmer runtime stage
    And the install command used inside the image should match the install command documented in the validation runbook word-for-word

  # Why: Confirms the CLI surface (PORT structural prerequisite) is intact in the image
  @key-example @smoke
  Scenario: The production image exposes the full forge CLI surface
    Given a built production image
    When the operator runs the forge help command inside the container
    # [ASSUMPTION: confidence=high] (ASSUM-008) Documented subcommands are queue, status, history, cancel, skip, serve
    Then the help output should list every documented subcommand —
      queue, status, history, cancel, skip, and the new serve subcommand
    And no subcommand should be hidden or missing

  # Why: CMDW round-trip — the daemon must subscribe and receive a real
  #      published payload, not silently fail to register the consumer.
  @key-example @smoke
  Scenario: The production image runs forge serve as a long-lived daemon and receives a queued build
    Given a built production image
    And a reachable JetStream broker
    When the container is started with forge serve as its main process
    And a build payload is published to the build-queued subject
    Then the daemon should remain running as the container's main process
    And the daemon should receive the published payload through its JetStream subscription
    And the receipt should be observable to the operator without exec'ing into the container

  # Why: ARFS structural check — every fleet tool must survive into the runtime image
  @key-example
  Scenario: The agent manifest inside the image lists every fleet tool
    Given a built production image
    When the manifest-build code path runs inside the container
    # [ASSUMPTION: confidence=high] (ASSUM-009) Canonical fleet tools per src/forge/fleet/manifest.py
    Then the resulting manifest should include forge_greenfield, forge_feature, forge_review_fix, forge_status, and forge_cancel
    And each tool should be reachable via the installed forge package — not via mounted source

  # Why: Canonical-freeze gate — verbatim runbook execution from a clean machine
  @key-example
  Scenario: The runbook Phase 6 build invocation succeeds verbatim
    Given a clean machine with only the documented prerequisites installed
    When the operator copy-pastes the Phase 6.1 build command from the validation runbook
    Then the image should build without any host-side patching of pyproject.toml, .env, or symlinks
    And any required setup should already be present as copy-pastable shell blocks at the top of Phase 6.1

  # ─────────────────────────────────────────────────────────────────────────
  # GROUP B — Boundary Conditions
  # ─────────────────────────────────────────────────────────────────────────

  # Why: Just-inside boundary — image must start without provider-key envs set
  @boundary
  Scenario: The container starts cleanly when no provider API keys are supplied
    Given a built production image
    And no provider API key environment variables are set
    When the container is started with forge serve
    # [ASSUMPTION: confidence=medium] (ASSUM-002) Provider absence becomes a per-build error, not a startup error
    Then the daemon should start without error
    And the daemon should remain running until a build payload requires a provider

  # Why: Just-inside boundary — default NATS URL must work when env unset
  @boundary
  Scenario: forge serve binds to the documented default NATS URL when no override is supplied
    Given a built production image
    And the FORGE_NATS_URL environment variable is not set
    When the container is started with forge serve
    # [ASSUMPTION: confidence=high] (ASSUM-001) Default broker URL is nats://127.0.0.1:4222 (src/forge/cli/queue.py:265)
    Then the daemon should attempt its JetStream subscription against the documented default broker URL

  # Why: Just-inside boundary — the literal-match install command (LES1 §3 DKRX)
  @boundary
  Scenario Outline: The install command in the Dockerfile matches the runbook documentation
    Given the Dockerfile in the repository root
    When the install command is extracted from the builder stage
    Then it should match the install command documented in <runbook_section> exactly

    Examples:
      | runbook_section                          |
      | RUNBOOK-FEAT-FORGE-008 Phase 0.4         |
      | RUNBOOK-FEAT-FORGE-008 Phase 6.1         |

  # Why: Just-outside boundary — image-size regression is a CI-visible gate
  @boundary @negative
  Scenario: The image fails the size regression check when its uncompressed size exceeds the budget
    Given a build pipeline that enforces an image-size budget
    # [ASSUMPTION: confidence=low] (ASSUM-003) Budget is 1.0 GB uncompressed (scoping §11.7 cites 600–900 MB typical)
    When a built image exceeds the documented budget
    Then the size regression check should fail
    And the failure should name the size budget and the actual image size

  # Why: Health probe boundary — healthy vs. unhealthy is the contract
  @boundary
  Scenario Outline: The container health probe reflects the daemon's subscription state
    Given a running container started with forge serve
    # [ASSUMPTION: confidence=medium] (ASSUM-004) Health is exposed via an HTTP /healthz endpoint
    # [ASSUMPTION: confidence=low] (ASSUM-005) Health probe / serve port is 8080
    When the daemon's JetStream subscription is in <subscription_state>
    Then the container's reported health status should be <health_status>

    Examples:
      | subscription_state           | health_status |
      | live and ready               | healthy       |
      | not yet established          | unhealthy     |
      | dropped without recovery yet | unhealthy     |

  # ─────────────────────────────────────────────────────────────────────────
  # GROUP C — Negative Cases
  # ─────────────────────────────────────────────────────────────────────────

  # Why: Hard CI gate — no real provider keys may be baked into any image layer
  @negative @smoke
  Scenario: The image contains no real provider API keys in any layer
    Given a built production image
    When every layer of the image is scanned for provider key material
    Then no real provider API key should be present in any layer
    And the build pipeline should fail if such a key is detected

  # Why: Container must not run as root — security baseline
  @negative @smoke
  Scenario: The container runs as a non-root user
    Given a built production image
    When the container is started with any documented subcommand
    Then the running process should belong to a dedicated non-root user
    And that user should not have administrative privileges inside the container

  # Why: Missing build context for nats-core must fail clearly, not silently
  @negative
  Scenario: The build fails with a clear diagnostic when the nats-core build context is missing
    Given a build invocation that omits the nats-core named build context
    When the operator attempts to build the image
    Then the build should fail before producing a tagged image
    And the failure message should name the missing build context and how to supply it

  # Why: Editable installs must not survive into the runtime stage (LES1 §3 DKRX)
  @negative
  Scenario: The runtime image contains no editable installs
    Given a built production image
    When the installed forge distribution is inspected inside the runtime stage
    Then forge should be present as a regular installed distribution
    And no .pth-style editable install pointer should be present in the runtime venv

  # Why: forge serve must not silently accept missing canonical configuration
  @negative
  Scenario: forge serve refuses to start when its required configuration is invalid
    Given a built production image
    And a configuration file that fails its canonical schema check
    When the container is started with forge serve against that configuration
    Then the daemon should refuse to start
    And the container should exit with a non-zero status
    And the operator should see a diagnostic naming the offending configuration field

  # ─────────────────────────────────────────────────────────────────────────
  # GROUP D — Edge Cases
  # ─────────────────────────────────────────────────────────────────────────

  # Why: CMDW failure mode — stale image silently fails to receive payloads
  @edge-case @regression
  Scenario: A stale image whose fleet manifest has drifted is detected before a build is dispatched
    Given a production image whose embedded manifest is older than the canonical fleet manifest
    When the operator queues a build that targets a tool added after the image was built
    Then the dispatch should refuse to route the build to the stale image
    And the operator should be told that the image is out of date and how to refresh it

  # Why: Concurrency — two daemons must not double-process the same payload
  @edge-case
  Scenario: Two concurrently running daemons do not double-process the same queued build
    Given two containers running forge serve against the same JetStream broker
    # [ASSUMPTION: confidence=medium] (ASSUM-006) forge serve uses a single shared durable consumer named "forge-serve"
    When a single build payload is published to the build-queued subject
    Then the payload should be delivered to exactly one daemon
    And the other daemon should observe the build as already claimed

  # Why: NATS transient unavailability must not require a container restart
  @edge-case
  Scenario: forge serve recovers automatically when the broker is briefly unavailable
    Given a running daemon with a live subscription
    When the JetStream broker becomes unavailable for a short interval
    And the broker becomes available again
    # [ASSUMPTION: confidence=low] (ASSUM-007) Reconnect bounded by JetStream durable consumer redelivery defaults
    Then the daemon should re-establish its subscription without operator intervention
    And buffered payloads published during the outage should be delivered once the subscription is restored

  # Why: Cache-poisoning regression — pyproject changes must invalidate the install layer
  @edge-case @regression
  Scenario: A pyproject change actually changes the installed dependencies in the rebuilt image
    Given a previous production image built against pyproject revision X
    And a pyproject revision Y that adds or upgrades a dependency
    When the image is rebuilt against revision Y
    Then the installed dependency set in the rebuilt image should reflect revision Y
    And no stale install layer from revision X should be reused incorrectly

  # Why: CI workflow scope — guards the three trigger paths
  @edge-case @regression
  Scenario Outline: The CI image-build workflow runs on pull requests touching the production-image surface
    Given a pull request that changes <changed_path>
    When the CI pipeline is evaluated for that pull request
    Then the production-image build-and-smoke-test workflow should be triggered

    Examples:
      | changed_path     |
      | Dockerfile       |
      | pyproject.toml   |
      | src/forge/       |

  # ─────────────────────────────────────────────────────────────────────────
  # GROUP E1 — Edge Cases / Security
  # ─────────────────────────────────────────────────────────────────────────

  # Why: Floating tags re-resolve silently — supply-chain integrity gate
  @edge-case @smoke
  Scenario: Base images are pinned to an immutable digest
    Given the Dockerfile in the repository root
    # [ASSUMPTION: confidence=medium] (ASSUM-010) Base is python:3.14-slim-bookworm pinned by sha256 in both stages
    When the FROM directives are inspected
    Then every base image reference should be pinned to an immutable content digest
    And no FROM directive should rely on a floating tag alone

  # Why: Process must not escape its declared write surfaces
  @edge-case
  Scenario: forge serve cannot write outside the declared artefact volume
    Given a running container started with forge serve
    When the daemon attempts to write to a path outside its declared artefact registry volume
    Then the write should be rejected by the container's filesystem permissions
    And the daemon should surface the rejection through its normal error channel rather than crash

  # Why: Production image must not ship interactive remote-access surfaces
  @edge-case
  Scenario: The container exposes no interactive remote-access endpoint
    Given a built production image
    When the image's exposed ports and runtime processes are inspected
    Then no SSH server, no remote debugger, and no interactive shell endpoint should be listening
    And only the documented serve and health probe ports should be exposed

  # ─────────────────────────────────────────────────────────────────────────
  # GROUP E2 — Edge Cases / Data Integrity
  # ─────────────────────────────────────────────────────────────────────────

  # Why: A crashed build must not vanish — JetStream redelivery is the safety net
  @edge-case @regression
  Scenario: A build that crashes mid-execution remains redeliverable
    Given a daemon that has received a build payload
    When the daemon process crashes before acknowledging the payload
    Then the payload should remain pending on the JetStream consumer
    And a subsequent daemon should pick the payload up on its next subscription poll

  # Why: Artefact registry must survive container lifecycle — operator data invariant
  @edge-case
  Scenario: The artefact registry filesystem persists across container restarts
    Given a running container with its artefact volume mounted at the documented path
    And the daemon has produced build artefacts during execution
    When the container is stopped and restarted against the same volume
    Then the previously produced artefacts should still be readable
    And no artefact metadata should have been silently truncated

  # ─────────────────────────────────────────────────────────────────────────
  # GROUP E3 — Edge Cases / Integration Boundaries
  # ─────────────────────────────────────────────────────────────────────────

  # Why: One bad provider must not poison the daemon for all other builds
  @edge-case
  Scenario: A failing provider for one build does not crash the daemon for unrelated builds
    Given a daemon currently processing a build that targets an unavailable provider
    When the affected build fails because the provider is unreachable
    Then the daemon should mark only that build as failed with a diagnostic naming the provider
    And the daemon should remain available to receive and process subsequent builds

  # Why: Architecture mismatch must fail fast — silent emulation is a debugging trap
  @edge-case
  Scenario: An architecture-mismatched pull fails fast with a clear diagnostic
    Given a published production image whose declared platform does not match the host
    When the operator attempts to run the image on the mismatched host
    Then the runtime should refuse to start the container
    And the operator should see a diagnostic naming the expected and actual platforms
Write forge-production-image_assumptions.yaml
79 lines
# Assumptions manifest for forge-production-image.feature
# Generated by /feature-spec

feature: "Forge Production Image"
generated: "2026-04-30T00:00:00Z"
stack: "python"
review_required: true

assumptions:
  - id: "ASSUM-001"
    scenario: "forge serve binds to the documented default NATS URL when no override is supplied"
    assumption: "Default NATS broker URL is nats://127.0.0.1:4222 when FORGE_NATS_URL is unset"
    confidence: high
    basis: "Hard-coded default in src/forge/cli/queue.py:265"
    human_response: "confirmed"

  - id: "ASSUM-002"
    scenario: "The container starts cleanly when no provider API keys are supplied"
    assumption: "Daemon starts successfully when provider API keys are absent; missing-provider failures are surfaced per-build at dispatch, not at daemon startup"
    confidence: medium
    basis: "Aligns with scoping §3.2 PORT — daemon must not block on unset env vars; per-build granularity matches the fact that forge_greenfield/forge_feature/forge_review_fix can target different providers"
    human_response: "confirmed"

  - id: "ASSUM-003"
    scenario: "The image fails the size regression check when its uncompressed size exceeds the budget"
    assumption: "Uncompressed image size budget is 1.0 GB"
    confidence: low
    basis: "Scoping §11.7 cites 600–900 MB as typical for slim+LangChain; 1.0 GB chosen to leave headroom for ARFS scratch tooling. Not stated explicitly anywhere in the seed inputs."
    human_response: "confirmed"

  - id: "ASSUM-004"
    scenario: "The container health probe reflects the daemon's subscription state"
    assumption: "forge serve exposes an HTTP /healthz endpoint; 200 OK when JetStream subscription is live, 503 otherwise"
    confidence: medium
    basis: "Explicitly recommended in scoping §7 over a NATS-only liveness signal because Docker's HEALTHCHECK mechanism wants a process-level command and curl + HTTP is the simplest portable form"
    human_response: "confirmed"

  - id: "ASSUM-005"
    scenario: "The container health probe reflects the daemon's subscription state"
    assumption: "The forge serve / health probe binds to TCP port 8080"
    confidence: low
    basis: "Common default for in-container HTTP probes; not stated in scoping doc — §11.2 explicitly marks port choice as an open question deferred to feature-plan"
    human_response: "confirmed"

  - id: "ASSUM-006"
    scenario: "Two concurrently running daemons do not double-process the same queued build"
    assumption: "forge serve subscribes via a single shared JetStream durable consumer named \"forge-serve\" so multiple replicas compete for delivery (work-queue semantics)"
    confidence: medium
    basis: "Required for the no-double-processing guarantee to hold under multiple replicas; matches the work-queue pattern already used elsewhere in forge for build-queue subjects. Not stated explicitly in the scoping doc."
    human_response: "confirmed"

  - id: "ASSUM-007"
    scenario: "forge serve recovers automatically when the broker is briefly unavailable"
    assumption: "Reconnect / redelivery window is bounded by JetStream's standard durable consumer redelivery (broker-configured ack_wait); no custom forge-side window"
    confidence: low
    basis: "Inferred from D1 being framed as a recovery concern, not a custom-policy concern. Not stated in seed inputs."
    human_response: "confirmed"

  - id: "ASSUM-008"
    scenario: "The production image exposes the full forge CLI surface"
    assumption: "Documented forge subcommands are: queue, status, history, cancel, skip, serve"
    confidence: high
    basis: "First five confirmed by inspection of src/forge/cli/main.py:80-93 (registered Click subgroups). The serve subcommand is the new one FEAT-FORGE-009 introduces (see scoping §11.1)."
    human_response: "confirmed"

  - id: "ASSUM-009"
    scenario: "The agent manifest inside the image lists every fleet tool"
    assumption: "Canonical fleet manifest contains exactly: forge_greenfield, forge_feature, forge_review_fix, forge_status, forge_cancel"
    confidence: high
    basis: "Confirmed by inspection of src/forge/fleet/manifest.py at lines 50, 71, 86, 101, 113"
    human_response: "confirmed"

  - id: "ASSUM-010"
    scenario: "Base images are pinned to an immutable digest"
    assumption: "Both Dockerfile stages use FROM python:3.14-slim-bookworm pinned by sha256 digest"
    confidence: medium
    basis: "Image (python:3.14-slim-bookworm) and Python version (3.14) are dictated by ADR-ARCH-032 + scoping §4. Digest pinning is supply-chain best practice but is not explicitly stated in the scoping doc."
    human_response: "confirmed"
Write forge-production-image_summary.md
94 lines
# Feature Spec Summary: Forge Production Image

**Feature ID**: FEAT-FORGE-009
**Stack**: python
**Generated**: 2026-04-30T00:00:00Z
**Scenarios**: 27 total (8 smoke, 5 regression)
**Assumptions**: 10 total (3 high / 4 medium / 3 low confidence)
**Review required**: Yes (3 low-confidence assumptions)

## Scope

Specifies the canonical production container image for forge — a multi-stage
Dockerfile based on a digest-pinned `python:3.14-slim-bookworm`, a new
`forge serve` long-lived daemon subcommand that subscribes to JetStream
`pipeline.build-queued.*`, and the CI / image-hygiene gates that protect the
LES1 parity properties (CMDW, PORT, ARFS, canonical-freeze) which Phase 6 of
`RUNBOOK-FEAT-FORGE-008-validation.md` is currently blocked on. The spec
covers the build path, the runtime contract (CLI surface, manifest
completeness, health probe, non-root user, no baked secrets), and the
operational edges (NATS reconnect, duplicate-delivery prevention, stale-image
detection, broker outage recovery, architecture-mismatch failure).

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 5 |
| Boundary conditions (@boundary) | 5 |
| Negative cases (@negative) | 6 |
| Edge cases (@edge-case) | 12 |
| **Total scenarios** | **27** |
| Smoke set (@smoke) | 8 |
| Regression set (@regression) | 5 |

> Note: tag totals overlap — `@boundary @negative` and `@edge-case @regression`
> appear on the same scenarios. The 27-scenario total is the unique count.

## Specification by Example Group Breakdown

| Group | Theme | Scenario count |
|-------|-------|----------------|
| A | Key examples (build, CLI surface, CMDW round-trip, ARFS, canonical-freeze) | 5 |
| B | Boundaries (no-keys start, default NATS, install literal-match, size budget, health states) | 5 |
| C | Negatives (no baked keys, non-root, missing build context, no editable install, invalid config) | 5 |
| D | Edge cases — core (stale manifest, dual daemons, broker outage, cache poisoning, CI triggers) | 5 |
| E1 | Edge cases — security (digest pinning, volume escape, no remote-access endpoints) | 3 |
| E2 | Edge cases — data integrity (crash redelivery, artefact volume persistence) | 2 |
| E3 | Edge cases — integration (provider failure isolation, arch mismatch fast-fail) | 2 |

## Deferred Items

None. All proposed groups (A, B, C, D, E1, E2, E3) were accepted in full.

## Open Assumptions (low confidence — REVIEW REQUIRED)

These three assumptions need operator verification before implementation:

| ID | Topic | Proposed value |
|----|-------|----------------|
| ASSUM-003 | Image-size budget | 1.0 GB uncompressed |
| ASSUM-005 | Health probe / serve port | 8080 |
| ASSUM-007 | NATS reconnect window | Inherit JetStream durable consumer defaults |

ASSUM-005 is explicitly noted as an open question in scoping doc §11.2 —
expect feature-plan to settle it.

## Crosscut to Scoping AC Sketch

| Scoping AC (§10) | Covered by scenario(s) |
|---|---|
| AC-A — image builds from fresh clone | A1 |
| AC-B — `forge --help` shows full surface | A2 |
| AC-C — `forge serve` subscribes & receives payload | A3 |
| AC-D — manifest lists every fleet tool | A4 |
| AC-E — `pip install .[providers]` literal-match | A1 (last clause), B3 |
| AC-F — no real provider keys in any layer | C1 |
| AC-G — non-root runtime | C2 |
| AC-H — HEALTHCHECK declared & green | B5, E3.1 (boundary states) |
| AC-I — CI builds + smoke-tests on PR | D5 |
| AC-J — runbook §6 gating callout removed when feature merges | (governance, not behavioural — out of spec scope; tracked in feature-plan) |

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "FEAT-FORGE-009 Forge Production Image" \
      --context features/forge-production-image/forge-production-image_summary.md \
      --context docs/scoping/F8-007b-forge-production-dockerfile.md

The scoping doc remains the authoritative source for non-behavioural
context (image baseline rationale, multi-stage layout sketch, deferred CI
strategy, secrets-at-runtime guidance). This spec covers the *behavioural*
contract; feature-plan should layer task decomposition on top.
Bash Verify scenario and tag counts
IN
python -c "
import re
with open('features/forge-production-image/forge-production-image.feature') as f:
    text = f.read()

# Count scenarios (Scenario: or Scenario Outline:)
scenarios = re.findall(r'^\s*(?:Scenario|Scenario Outline):', text, re.M)
print(f'Scenarios found: {len(scenarios)}')

# Count tags
for tag in ['@key-example', '@boundary', '@negative', '@edge-case', '@smoke', '@regression']:
    count = len(re.findall(rf'{tag}\b', text))
    print(f'{tag}: {count}')
"

OUT
Exit code 127
/bin/bash: line 14: python: command not found
Bash Verify scenario and tag counts (python3)
IN
python3 -c "
import re
with open('features/forge-production-image/forge-production-image.feature') as f:
    text = f.read()
scenarios = re.findall(r'^\s*(?:Scenario|Scenario Outline):', text, re.M)
print(f'Scenarios: {len(scenarios)}')
for tag in ['@key-example', '@boundary', '@negative', '@edge-case', '@smoke', '@regression']:
    count = len(re.findall(rf'{tag}(?=\s|\$)', text, re.M))
    print(f'{tag}: {count}')
"

OUT
Scenarios: 27
@key-example: 5
@boundary: 5
@negative: 6
@edge-case: 12
@smoke: 6
@regression: 4
Counts don't match what I wrote in summary.md — fixing.

Edit forge-production-image_summary.md
Modified
Edit forge-production-image_summary.md
Modified

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURE SPEC COMPLETE: Forge Production Image (FEAT-FORGE-009)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Files written:
  features/forge-production-image/forge-production-image.feature
  features/forge-production-image/forge-production-image_assumptions.yaml
  features/forge-production-image/forge-production-image_summary.md

Scenarios: 27 total
  @key-example: 5    @boundary: 5
  @negative: 6       @edge-case: 12
  @smoke: 6          @regression: 4

Assumptions: 10 total
  high: 3 (auto-proceed)         — ASSUM-001, 008, 009
  medium: 4 (Coach review rec.)  — ASSUM-002, 004, 006, 010
  low: 3 (human review required) — ASSUM-003, 005, 007

REVIEW REQUIRED: 3 low-confidence assumptions need verification
  ASSUM-003 — image-size budget (1.0 GB)
  ASSUM-005 — health probe / serve port (8080) — also open in scoping §11.2
  ASSUM-007 — NATS reconnect window
  See: features/forge-production-image/forge-production-image_assumptions.yaml

Deferred: 0 groups (all of A, B, C, D, E1, E2, E3 accepted in full)

Next steps:
  Review: features/forge-production-image/forge-production-image.feature
  Pass to feature-plan:
    /feature-plan "FEAT-FORGE-009 Forge Production Image" \
      --context features/forge-production-image/forge-production-image_summary.md \
      --context docs/scoping/F8-007b-forge-production-dockerfile.md
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Three files written under features/forge-production-image/. The .feature file carries 27 scenarios across 7 SbE groups; the assumptions YAML records all 10 inferred values with confidence + basis + your confirmed response; the summary maps each scenario back to the AC sketch in docs/scoping/F8-007b-forge-production-dockerfile.md §10. Three low-confidence assumptions flagged for review before /feature-plan.

is this the full command syntax is shoulw we pass additonal --context arguments? /feature-plan "FEAT-FORGE-009 Forge Production Image" \
      --context features/forge-production-image/forge-production-image_summary.md \
      --context docs/scoping/F8-007b-forge-production-dockerfile.md
Show less
Bash Find feature-plan command definition
IN
find /home/richardwoollcott/.claude /home/richardwoollcott/Projects/appmilla_github/forge/.claude -name "feature-plan*" -type f 2>/dev/null | head

OUT
(Bash completed with no output)
Bash Find feature-plan definition broadly
IN
find /home/richardwoollcott -name "feature-plan*.md" -type f 2>/dev/null | head -5; find / -path /proc -prune -o -name "feature-plan.md" -type f -print 2>/dev/null | head -5

OUT
/home/richardwoollcott/.agentecflow.backup.20260426_083609/commands/feature-plan.md
/home/richardwoollcott/.agentecflow.backup.20260222_151405/commands/feature-plan.md
/home/richardwoollcott/.agentecflow/commands/feature-plan.md
/home/richardwoollcott/.agentecflow.backup.20260429_161156/commands/feature-plan.md
/home/richardwoollcott/.agentecflow.backup.20260424_123044/commands/feature-plan.md
/home/richardwoollcott/.agentecflow.backup.20260426_083609/commands/feature-plan.md
/home/richardwoollcott/.agentecflow.backup.20260222_130244/commands/feature-plan.md
/home/richardwoollcott/.agentecflow.backup.20260222_140511/commands/feature-plan.md
/home/richardwoollcott/.agentecflow.backup.20260429_161156/commands/feature-plan.md
/home/richardwoollcott/.agentecflow.backup.20260222_160108/commands/feature-plan.md
Bash Extract feature-plan flags and section headers
IN
grep -E "^(##? |--|usage|Usage|Syntax|ARGUMENTS|--context|--output|--from|--auto|--stack)" /home/richardwoollcott/.agentecflow/commands/feature-plan.md | head -80

OUT
# Feature Plan - Single Command Feature Planning
## Command Syntax
## Available Flags
# Standard usage (structured output is default)
# Output includes:
# ✅ Feature FEAT-A1B2 created
# 📋 Tasks: 5
#    TASK-001: Create OAuth service interface (complexity: 3)
#    TASK-002: Implement Google OAuth provider (complexity: 5)
#    TASK-003: Implement GitHub OAuth provider (complexity: 5)
#    TASK-004: Add session management (complexity: 4)
#    TASK-005: Integration tests (complexity: 3)
# 🔀 Parallel execution groups:
#    Wave 1: [TASK-001]
#    Wave 2: [TASK-002, TASK-003] (can run in parallel)
#    Wave 3: [TASK-004]
#    Wave 4: [TASK-005]
# 📁 Feature file: .guardkit/features/FEAT-A1B2.yaml
# 📁 Task files: tasks/backlog/oauth-auth/TASK-001.md ... TASK-005.md
# Then use feature-build for autonomous implementation
# To disable structured output (task markdown files only)
# Single context file
# Multiple context files (processed in order)
# Works alongside auto-detection (explicit files loaded first)
# Internal Graphiti queries:
# 1. Seed feature spec to knowledge graph
# 2. Query related features: FEAT-GR-002, FEAT-GR-004
# 3. Query relevant patterns: "repository pattern", "context builder pattern"
# 4. Query role constraints: player_must_implement, coach_must_validate
# 5. Query quality gates: scaffolding_threshold=skip_arch, feature_threshold=60
# 6. Query implementation modes: task-work (>= complexity 4), direct (< complexity 4)
# Planning prompt enriched with:
# - Feature spec details (success criteria, technical requirements)
# - 2 related features with similar patterns
# - 3 relevant design patterns
# - Player/Coach role boundaries
# - Quality gate thresholds per task type
# - File location patterns for direct mode
# Feature context
# Pattern context
# AutoBuild context
# Architecture context
# .guardkit/features/FEAT-A1B2.yaml
# ✅ Correct - includes file_path
# ❌ Wrong - missing file_path (will cause FeatureLoader error)
# Example: 4 waves with some parallel execution
## Clarification Integration
# Forces Context A and Context B questions even for simple feature
# Useful for learning workflows or when defaults may not be appropriate
# All clarification questions answered inline
# Useful for automated pipelines or repeatable workflows
# Pseudo-code for feature-plan orchestration
---
---
## Overview
## Examples
# Basic feature planning
# Plan a complex feature
# Plan infrastructure change
# Plan security enhancement
# Explicit context file (when auto-detection isn't sufficient)
# Multiple context sources
# Context with clarification
## Execution Flow
# Combine results into feature_graphiti_context
--------------------------------------------------------------------------------
--------------------------------------------------------------------------------
---
---
## What This Provides
## Advanced Usage
# Include priority in feature description
# The system will:
# - Set priority:critical on review task
# - Flag as high-risk change
# - Recommend comprehensive depth analysis
# Re-run analysis on existing review task
# Useful when:
# - Initial review needs refinement
# - Requirements changed
Bash Read feature-plan command syntax section
IN
sed -n '/## Command Syntax/,/^## [A-Z]/p' /home/richardwoollcott/.agentecflow/commands/feature-plan.md | head -80

OUT
## Command Syntax

```bash
/feature-plan "feature description"
```

**Note on `/feature-plan` vs `/task-create`**:
- **`/feature-plan`**: Uses the description for **analysis** purposes. The review task title is programmatically generated as "Plan: {description}".
- **`/task-create`**: Uses the description for **title inference**. Claude analyzes the description to extract a concise, actionable title (e.g., "We need JWT auth" → "Add JWT authentication").

Both accept natural language descriptions, but they serve different purposes in the workflow.

## Available Flags
Bash Read feature-plan flags table
IN
sed -n '/## Available Flags/,/^## [A-Z]/p' /home/richardwoollcott/.agentecflow/commands/feature-plan.md

OUT
## Available Flags

| Flag | Description |
|------|-------------|
| `--context path/to/file.md` | Explicitly specify context files (can be used multiple times) |
| `--no-questions` | Skip all clarification (review scope + implementation prefs) |
| `--with-questions` | Force clarification even for simple features |
| `--defaults` | Use clarification defaults throughout workflow |
| `--answers="..."` | Inline answers (propagated to task-review and subtask creation) |
| `--no-structured` | Disable structured YAML feature file output (enabled by default) |

### AutoBuild Integration (Default Behavior)

By default, `/feature-plan` generates structured YAML feature files for AutoBuild integration. This includes:
- A structured YAML feature file at `.guardkit/features/FEAT-XXX.yaml`
- Task dependencies and parallel execution groups
- Complexity scores (1-10) for each task
- Orchestration metadata for AutoBuild consumption

This enables integration with `/feature-build` for autonomous implementation:

```bash
# Standard usage (structured output is default)
/feature-plan "add OAuth2 authentication"

# Output includes:
# ✅ Feature FEAT-A1B2 created
# 📋 Tasks: 5
#    TASK-001: Create OAuth service interface (complexity: 3)
#    TASK-002: Implement Google OAuth provider (complexity: 5)
#    TASK-003: Implement GitHub OAuth provider (complexity: 5)
#    TASK-004: Add session management (complexity: 4)
#    TASK-005: Integration tests (complexity: 3)
#
# 🔀 Parallel execution groups:
#    Wave 1: [TASK-001]
#    Wave 2: [TASK-002, TASK-003] (can run in parallel)
#    Wave 3: [TASK-004]
#    Wave 4: [TASK-005]
#
# 📁 Feature file: .guardkit/features/FEAT-A1B2.yaml
# 📁 Task files: tasks/backlog/oauth-auth/TASK-001.md ... TASK-005.md

# Then use feature-build for autonomous implementation
/feature-build FEAT-A1B2

# To disable structured output (task markdown files only)
/feature-plan "add OAuth2 authentication" --no-structured
```

**Note**: Both the traditional task markdown files AND the structured YAML feature file are created by default. This maintains compatibility with `/task-work` while enabling `/feature-build` integration. Use `--no-structured` to skip YAML generation.

### Explicit Context Files (--context)

By default, `/feature-plan` automatically detects and loads context from:
- Feature specification files (`docs/features/FEAT-*.md`)
- CLAUDE.md project files
- Related architecture documentation

Use `--context` when auto-detection isn't sufficient or you want to explicitly seed specific context:

```bash
# Single context file
/feature-plan "implement OAuth" --context docs/auth-design.md

# Multiple context files (processed in order)
/feature-plan "add API" --context docs/api-spec.md --context docs/security-requirements.md

# Works alongside auto-detection (explicit files loaded first)
/feature-plan "implement FEAT-GR-003" --context additional-context.md
```

**When to use --context:**
- Feature spec not in standard location (`docs/features/`)
- Need to include additional architectural context
- Want to override auto-detection with specific files
- Testing or automation scenarios requiring explicit context

**Context file requirements:**
- Must be readable markdown files
- Can include frontmatter metadata
- Paths can be relative (to project root) or absolute
- Nonexistent files are handled gracefully (warning logged)

### Graphiti Context Integration (FEAT-GR-003)

When `/feature-plan` executes with context (auto-detected or explicit), it queries Graphiti's knowledge graph to enrich planning with:

**1. Feature-Related Context:**
- Related features and their outcomes
- Relevant design patterns for the tech stack
- Similar past implementations and lessons learned
- Project architecture and key components

**2. AutoBuild Support Context:**
- **Role constraints**: Player/Coach boundaries to prevent role reversal
- **Quality gate configs**: Task-type specific thresholds (scaffolding vs feature)
- **Implementation modes**: Direct vs task-work patterns and file locations

**Example Context Query Flow:**

```bash
/feature-plan "implement FEAT-GR-003 feature spec integration" --context docs/research/graphiti-refinement/FEAT-GR-003.md

# Internal Graphiti queries:
# 1. Seed feature spec to knowledge graph
# 2. Query related features: FEAT-GR-002, FEAT-GR-004
# 3. Query relevant patterns: "repository pattern", "context builder pattern"
# 4. Query role constraints: player_must_implement, coach_must_validate
# 5. Query quality gates: scaffolding_threshold=skip_arch, feature_threshold=60
# 6. Query implementation modes: task-work (>= complexity 4), direct (< complexity 4)
#
# Planning prompt enriched with:
# - Feature spec details (success criteria, technical requirements)
# - 2 related features with similar patterns
# - 3 relevant design patterns
# - Player/Coach role boundaries
# - Quality gate thresholds per task type
# - File location patterns for direct mode
```

**What This Prevents:**

| Issue | How Context Helps |
|-------|------------------|
| Role reversal | Player knows implementation boundaries, Coach knows validation scope |
| Threshold drift | Quality gates consistent across all generated subtasks |
| File location errors | Direct mode tasks know to create files inline, not in worktrees |
| Pattern inconsistency | Planning references proven patterns from past features |
| Knowledge loss | Related features inform current implementation approach |

**Queried Group IDs:**

```python
# Feature context
"feature_specs"          # Seeded feature specifications
"feature_completions"    # Past feature outcomes
"task_outcomes"          # Individual task learnings

# Pattern context
"patterns_{tech_stack}"  # Stack-specific patterns (e.g., patterns_python)
"patterns"               # Generic design patterns

# AutoBuild context
"role_constraints"       # Player/Coach responsibilities
"quality_gate_configs"   # Task-type quality thresholds
"implementation_modes"   # Direct vs task-work guidance

# Architecture context
"project_overview"       # CLAUDE.md insights
"project_architecture"   # Key components, entry points
"failure_patterns"       # Things that failed before
```

**Token Budget Allocation:**

```
Total budget: ~4000 tokens

1. Feature spec (40%):         ~1600 tokens - Highest priority
2. Project architecture (20%): ~800 tokens  - Context setting
3. Related features (15%):     ~600 tokens  - Similar patterns
4. Design patterns (15%):      ~600 tokens  - Implementation guidance
5. Warnings (10%):             ~400 tokens  - Past failures
6. Role constraints:           ~200 tokens  - AutoBuild boundaries
7. Quality gates:              ~200 tokens  - Threshold configs
```

**Example: Planning with Full Context**

```bash
$ /feature-plan "implement FEAT-SKEL-001 walking skeleton" --context docs/features/FEAT-SKEL-001.md

[Graphiti] Found feature spec: docs/features/FEAT-SKEL-001-walking-skeleton.md
[Graphiti] Seeded feature spec to knowledge graph
[Graphiti] Querying for enriched context...

[Graphiti] Context loaded:
  ✓ Related features: 2 (FEAT-SETUP-001, FEAT-PING-002)
  ✓ Relevant patterns: 3 (mcp-tool-pattern, docker-setup, healthcheck-pattern)
  ✓ Role constraints: 2 (player, coach)
  ✓ Quality gates: 4 (scaffolding, feature, testing, documentation)
  ✓ Implementation modes: 2 (direct, task-work)
  ✓ Warnings: 0

[Review] Planning with enriched context (4200 tokens)...

TECHNICAL OPTIONS ANALYSIS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Option 1: FastAPI + MCP SDK (Recommended)
  Based on: mcp-tool-pattern (from Graphiti)
  Complexity: Low (3/10)
  Effort: 2-3 hours
  Quality gate: scaffolding (architectural review skipped)
  Implementation mode: direct (inline file creation)
  ...

[Continue with normal feature planning flow]
```

**Benefits:**

✅ **Context continuity** - Feature specs persist across planning → implementation → completion
✅ **Pattern reuse** - Proven approaches from past features inform new work
✅ **Consistent workflows** - AutoBuild constraints prevent common mistakes
✅ **Knowledge accumulation** - Each feature enriches the knowledge graph
✅ **Reduced rework** - Warnings from past failures prevent repeated errors

### Feature YAML Schema Reference

The generated feature YAML file must conform to the `FeatureLoader` schema. This section documents the **required** structure for `/feature-build` compatibility.

#### Complete Schema Example

```yaml
# .guardkit/features/FEAT-A1B2.yaml
id: FEAT-A1B2
name: "OAuth2 Authentication"
description: "Add OAuth2 authentication with multiple providers"
created: "2026-01-06T10:30:00Z"
status: planned
complexity: 6
estimated_tasks: 5

tasks:
  - id: TASK-OAUTH-001
    name: "Create auth infrastructure"
    file_path: "tasks/backlog/oauth-auth/TASK-OAUTH-001-create-auth-infrastructure.md"
    complexity: 5
    dependencies: []
    status: pending
    implementation_mode: task-work
    estimated_minutes: 60

  - id: TASK-OAUTH-002
    name: "Implement local JWT auth"
    file_path: "tasks/backlog/oauth-auth/TASK-OAUTH-002-implement-jwt-auth.md"
    complexity: 6
    dependencies:
      - TASK-OAUTH-001
    status: pending
    implementation_mode: task-work
    estimated_minutes: 90

  - id: TASK-OAUTH-003
    name: "Add database migrations"
    file_path: "tasks/backlog/oauth-auth/TASK-OAUTH-003-database-migrations.md"
    complexity: 4
    dependencies:
      - TASK-OAUTH-001
    status: pending
    implementation_mode: task-work
    estimated_minutes: 45

  - id: TASK-OAUTH-004
    name: "Implement social OAuth2"
    file_path: "tasks/backlog/oauth-auth/TASK-OAUTH-004-social-oauth.md"
    complexity: 7
    dependencies:
      - TASK-OAUTH-002
      - TASK-OAUTH-003
    status: pending
    implementation_mode: task-work
    estimated_minutes: 120

  - id: TASK-OAUTH-005
    name: "Add auth tests"
    file_path: "tasks/backlog/oauth-auth/TASK-OAUTH-005-auth-tests.md"
    complexity: 3
    dependencies:
      - TASK-OAUTH-004
    status: pending
    implementation_mode: direct
    estimated_minutes: 30

orchestration:
  parallel_groups:
    - - TASK-OAUTH-001
    - - TASK-OAUTH-002
      - TASK-OAUTH-003
    - - TASK-OAUTH-004
    - - TASK-OAUTH-005
  estimated_duration_minutes: 345
  recommended_parallel: 2
```

#### Required Fields

**Feature-level fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | ✅ Yes | Feature ID (e.g., "FEAT-A1B2") |
| `name` | string | ✅ Yes | Human-readable feature name |
| `tasks` | array | ✅ Yes | List of task objects |
| `orchestration` | object | ✅ Yes | Execution configuration |
| `description` | string | No | Feature description |
| `created` | string | No | ISO 8601 timestamp |
| `status` | string | No | "planned", "in_progress", "completed", "failed", "paused" |
| `complexity` | int | No | Aggregate complexity (1-10) |
| `estimated_tasks` | int | No | Task count |

**Task-level fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | ✅ Yes | Task ID (e.g., "TASK-OAUTH-001") |
| `file_path` | string | ✅ Yes | **Path to task markdown file** (relative to repo root) |
| `name` | string | No | Task name (defaults to ID) |
| `complexity` | int | No | Complexity score 1-10 (default: 5) |
| `dependencies` | array | No | List of dependency task IDs |
| `status` | string | No | "pending", "in_progress", "completed", "failed", "skipped" |
| `implementation_mode` | string | No | "direct", "task-work" |
| `estimated_minutes` | int | No | Estimated duration (default: 30) |

**Orchestration fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `parallel_groups` | array | ✅ Yes | List of lists - each inner list is a wave of parallel tasks |
| `estimated_duration_minutes` | int | No | Total estimated duration |
| `recommended_parallel` | int | No | Max recommended parallel tasks |

#### Critical: file_path Field

The `file_path` field is **required** for each task. Without it, `FeatureLoader` will fail to parse the feature file.

```yaml
# ✅ Correct - includes file_path
tasks:
  - id: TASK-001
    name: "Task Name"
    file_path: "tasks/backlog/feature-name/TASK-001-task-name.md"
    status: pending

# ❌ Wrong - missing file_path (will cause FeatureLoader error)
tasks:
  - id: TASK-001
    name: "Task Name"
    status: pending
```

#### parallel_groups Format

The `parallel_groups` field is a **list of lists** where:
- Each inner list represents a "wave" of tasks that can run in parallel
- Waves execute sequentially (wave 1 completes before wave 2 starts)
- Tasks within a wave can execute in parallel

```yaml
# Example: 4 waves with some parallel execution
orchestration:
  parallel_groups:
    - - TASK-001           # Wave 1: Single task (foundation)
    - - TASK-002           # Wave 2: Two tasks in parallel
      - TASK-003
    - - TASK-004           # Wave 3: Single task (depends on wave 2)
    - - TASK-005           # Wave 4: Final task
```

**Note**: This replaces the older `execution_groups` format which is no longer supported.

## Clarification Integration
You can pass more, and for this feature it's worth doing — /feature-plan auto-detects from docs/features/FEAT-*.md, but our stub lives at tasks/backlog/FEAT-FORGE-009-production-image.md so auto-detection will miss everything except .claude/CLAUDE.md. Explicit --context is doing real work here.

Recommended invocation

/feature-plan "FEAT-FORGE-009 Forge Production Image — multi-stage \
  Dockerfile + forge serve daemon to unblock LES1 parity gates" \
  --context features/forge-production-image/forge-production-image_summary.md \
  --context features/forge-production-image/forge-production-image_assumptions.yaml \
  --context docs/scoping/F8-007b-forge-production-dockerfile.md \
  --context docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md \
  --context docs/architecture/decisions/ADR-ARCH-032-langchain-1x-portfolio-alignment.md \
  --context tasks/backlog/FEAT-FORGE-009-production-image.md
Why each one earns its place
Context file	What it contributes that the others don't
..._summary.md	The behavioural contract (27 scenarios, AC↔scenario crosscut). Highest priority — feature-plan reads this to scope tasks.
..._assumptions.yaml	The 3 low-confidence items that need resolution before task decomposition (port, size budget, reconnect window). Without this, feature-plan won't know to surface them as blocking decisions.
F8-007b-forge-production-dockerfile.md	The seed: image baseline rationale, multi-stage layout, build-context resolution for nats-core, all 8 open questions. Contains content the spec deliberately abstracted out.
RUNBOOK-FEAT-FORGE-008-validation.md	Phase 0.4 + Phase 6.1 hold the literal install command AC-E demands a match against. Feature-plan needs the actual string to write that into a task.
ADR-ARCH-032-...md	Authoritative source for Python 3.14.2 baseline + the LCOI providers extras decision. Scoping doc cites it; feature-plan benefits from the verified-versions table directly.
FEAT-FORGE-009-production-image.md	Governance metadata — priority, parent_review, spawned_by, the Wave-2 dependency on FEAT-F8-VALIDATION-FIXES, and the §11.4 BuildKit decision now resolved. Helps feature-plan order against other backlog items.
What I'd skip
docs/research/ideas/forge-build-plan.md — heavily cited (LES1 gates, line 656 DKRX) but it's a large document. The scoping doc already abstracts the relevant parts. Including it directly would dilute the ~4000-token Graphiti budget.
docs/handoffs/F8-007a-nats-canonical-provisioning.md — sibling delegation; mostly affects when this feature can run end-to-end, not what the tasks are.
Both are fine to add if you want maximum context, but they have lower ROI than the six above.

One nit on the description
/feature-plan uses the description for analysis (not just titling), so a one-line summary of why helps it shape task complexity. The version above adds "multi-stage Dockerfile + forge serve daemon to unblock LES1 parity gates" — short but signals the two distinct work surfaces (image build vs. new daemon subcommand) plus the strategic reason.