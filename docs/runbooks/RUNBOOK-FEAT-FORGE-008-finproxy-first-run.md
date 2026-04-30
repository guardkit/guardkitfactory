# Runbook: FinProxy First Real Run — Forge Step 7

**Status:** Ready for execution **after** Step 6 validation is signed off (see [`RUNBOOK-FEAT-FORGE-008-validation.md`](RUNBOOK-FEAT-FORGE-008-validation.md) and its `RESULTS-*` companion).
**Purpose:** Drive the first real Forge pipeline run end-to-end on the FinProxy product, producing real architecture/design/feature artefacts and a real pull request awaiting human review.
**Machines:**
- **Local** (MacBook or workstation) — operator-side approvals via `forge` CLI; brief authoring; PR review
- **GB10** (`promaxgb10-41b1`) — fleet runtime: NATS, specialist-agents (PO + architect), `forge serve` container

**Predecessors:**
- Step 6 ✅ canonical per `RESULTS-FEAT-FORGE-008-validation.md` (all 11 gates green or explicitly waived with justification)
- Specialist-agent fleet on the production image with PO + architect both NATS-callable
- nats-core ≥ v0.2.0 with TASK-NCFA-003 payloads
- `gh` CLI authenticated against the FinProxy repo on the operator's machine

**Expected wall-clock:** ~3–7 days end-to-end. **Active operator time:** ~4–8 hours spread across that window. The build pauses at every flagged-for-review checkpoint awaiting an operator decision; idle time between pauses is fine and expected.

**Outputs:**
- A real pull request on `guardkit/finproxy` ready for human review
- A `RESULTS-finproxy-first-run.md` file capturing the end-to-end metrics, every approval decision, and lessons for the next real run
- An updated `forge/docs/research/ideas/forge-build-plan.md` Step 7 row marked ✅
- An updated `forge/docs/history/command-history.md` entry per LES1 §8

---

## Why this runbook exists

Every previous Forge run has been one of:
- A unit test (mocked everything)
- An integration test (in-memory substrate)
- A validation walkthrough (Step 6 — exercised every gate but produced no real product artefacts)

This is the first time Forge will:
1. Issue real specialist dispatches that consume budget and produce architecture/design artefacts the operator will keep
2. Run a real `/feature-spec → /feature-plan → autobuild` chain that creates a real feature branch and commits real code
3. Open a real pull request that a human reviewer will eventually merge

The build plan flags this risk explicitly (§Risk Register: "Use small test corpus first, not FinProxy. Debug integration issues before the real run."). This runbook offers an optional Phase 0.6 to de-risk against a smaller corpus first.

The dominant mode of failure on a first real run is **integration drift between the production specialist-agent image and the production forge image** — exactly the LES1 lessons. Step 6 should have caught most of them; this runbook catches what slipped through.

---

## Phase 0: Go/no-go pre-flight

### 0.1 Confirm Step 6 RESULTS is signed off

```bash
cd ~/Projects/appmilla_github/forge
ls -lh docs/runbooks/RESULTS-FEAT-FORGE-008-validation.md
grep -E "Step 6.*canonical|Step 6.*✅" docs/runbooks/RESULTS-FEAT-FORGE-008-validation.md | head -3
```

**Pass:** RESULTS file exists, has a "canonical" or "✅" line in its Decision section, and every gate in the Per-gate outcomes table is ✅.

**If any gate is ❌ without a documented waiver:** stop. Re-run the affected validation phases. A first real run on a partially-validated Forge will burn operator time on integration issues that should have been caught in Step 6.

### 0.2 Confirm GB10 fleet is up

```bash
ssh promaxgb10-41b1 'echo "=== NATS ===" && \
    nats account info 2>&1 | head -10 && \
    echo "=== Specialists ===" && \
    docker ps --format "{{.Names}}\t{{.Status}}" | grep specialist && \
    echo "=== Forge serve ===" && \
    docker ps --format "{{.Names}}\t{{.Status}}" | grep forge'
```

**Pass:**
- NATS account-info returns successfully (server reachable, account credentials work)
- Both specialists are running (`specialist-agent-product-owner`, `specialist-agent-architect` or whatever your container names are)
- A `forge serve` container is running on the production image (built from commit `2f13eac` or later)

**If forge container is not running:** start it now. Use the same image you validated in Phase 6.1 of the validation runbook:
```bash
ssh promaxgb10-41b1
docker run -d --name forge-prod \
    --network host \
    -e NATS_URL=nats://localhost:4222 \
    -e FORGE_LOG_LEVEL=info \
    -v ~/forge-state:/var/forge \
    forge:production-validation \
    forge serve
```

**Volume note:** mounting `-v ~/forge-state:/var/forge` makes the SQLite history survive container restarts. Without this, a container restart loses every build's state — which is exactly the failure mode that led to FEAT-FORGE-001's recovery work.

### 0.3 Confirm specialist agents are NATS-callable end-to-end

```bash
ssh promaxgb10-41b1
nats request agents.command.product-owner '{"schema_version":"1.0","ping":true}' --timeout 10s
nats request agents.command.architect '{"schema_version":"1.0","ping":true}' --timeout 10s
```

**Pass:** Both return a `ResultPayload`-shaped response within 10 seconds.

**If either times out:** the specialist's NATS subscription is broken. Check the specialist-agent container logs for `subscribed to agents.command.<role>` startup line. If absent, that specialist did not subscribe — the LES1 CMDW failure mode applied to specialist-agents. Restart the affected container and re-test.

### 0.4 Confirm operator has the approval responder ready

The operator approves builds via the `forge` CLI on their local machine. Confirm the local `forge` install can reach the GB10 NATS:

```bash
# Locally:
NATS_URL=nats://promaxgb10-41b1:4222 forge --version
NATS_URL=nats://promaxgb10-41b1:4222 forge status
```

**Pass:** Both succeed. `status` may show no in-flight builds (expected) — the connectivity is what matters here.

**If NATS is not reachable from the local machine:** check the GB10 NATS account config; the operator may need a different account/credential than the GB10-internal services use. Capture this and update the runbook (folding-back per LES1).

### 0.5 Confirm `gh` CLI is authenticated for the FinProxy repo

```bash
gh auth status
gh repo view guardkit/finproxy --json name,url,defaultBranchRef 2>&1 | head -10
```

**Pass:** `gh auth status` reports a logged-in account with `repo` scope. `gh repo view` returns the repo metadata.

**If `gh` is not authenticated:** `gh auth login` and select the appropriate scopes. The forge agent that creates the PR uses the operator's gh auth — without it, the constitutional PR-creation step will fail at the very last step of the run.

### 0.6 (Optional but recommended) Smoke run on a small test corpus first

Per build plan §Risk Register: "Use small test corpus first, not FinProxy."

If you have a small toy repo (e.g. `guardkit/test-project` or a freshly-created `guardkit/forge-smoke-target`), run Phases 1–6 of THIS runbook against that target first. The smoke run consumes specialist budget but produces throwaway artefacts; failures are cheap to recover from.

```bash
# Example: a smoke run on a small target before committing to FinProxy
NATS_URL=nats://promaxgb10-41b1:4222 forge queue FEAT-SMOKE-001 \
    --repo guardkit/forge-smoke-target \
    --branch main \
    --mode a \
    --brief "A toy CLI that prints the current weekday name. One file. No dependencies."
```

**If you skip this step, accept that first-run gotchas will burn FinProxy specialist budget instead.**

### 0.7 Pick the FinProxy mode (A vs B)

The choice depends on FinProxy's current state:

| FinProxy state | Mode | Why |
|----------------|------|-----|
| No `docs/architecture/` and no `docs/design/` | **Mode A** | Greenfield — Forge produces arch and design from scratch |
| `docs/architecture/` and `docs/design/` exist and are current | **Mode B** | Existing architecture — Forge skips PO/architect, starts at `/feature-spec` |
| Some docs exist but are incomplete or stale | **Mode A** | Treat as greenfield; current docs are inputs to PO, not authoritative outputs |

```bash
# Inspect the FinProxy repo state before choosing:
gh repo clone guardkit/finproxy /tmp/finproxy-inspect 2>/dev/null || true
ls /tmp/finproxy-inspect/docs/architecture/ 2>/dev/null
ls /tmp/finproxy-inspect/docs/design/ 2>/dev/null
ls /tmp/finproxy-inspect/.guardkit/context-manifest.yaml 2>/dev/null
```

**Record:** which mode you've chosen and why, in the RESULTS file (Phase 7).

### 0.8 Confirm FinProxy has a context manifest (Mode B only)

If you chose Mode B, FinProxy must have `.guardkit/context-manifest.yaml` so `/feature-spec` knows what to pull as `--context`. Per build plan §Context Manifests: lpa-platform and specialist-agent need their manifests too, so this is a known gap.

```bash
test -f /tmp/finproxy-inspect/.guardkit/context-manifest.yaml && \
    echo "Manifest present" || echo "MANIFEST MISSING — Mode B will run with no cross-repo context"
```

**If missing in Mode B:** either (a) write the manifest first as a separate commit on FinProxy, or (b) fall back to Mode A (treat the existing docs as inputs to PO rather than authoritative).

---

## Phase 1: Author the brief (Mode A only — skip to Phase 1b for Mode B)

Mode A starts from a one-line product brief. The PO specialist expands it into a vision document; the architect builds an architecture from there. **The brief is the highest-leverage input you give Forge.** Spend 10 minutes on it; don't rush.

### 1.1 Write the brief

A good brief:
- Names the product
- States the user (who is it for? — single-user, multi-user, B2B, internal?)
- States the core capability in one sentence
- Names one or two non-functional priorities (latency? cost? compliance?)
- Names what it explicitly is NOT (so the architect doesn't over-build)

A bad brief is one paragraph or longer.

```bash
# Capture the brief to a file for traceability:
cat > /tmp/finproxy-brief.md <<'EOF'
FinProxy is a single-user proxy that surfaces my consolidated UK personal-finance position
(bank accounts, ISAs, pensions) by aggregating Open Banking + provider APIs, refreshed
daily, accessible via a private web dashboard. Latency target is 5s p95 on the dashboard
load. It is NOT a public service, NOT a transaction-issuing system, and NOT a
compliance-grade audit trail.
EOF

cat /tmp/finproxy-brief.md
wc -w /tmp/finproxy-brief.md
```

**Pass:** Brief is 30–80 words, names user / capability / non-functional / non-goals.

### 1.2 Validate the brief against the PO calibration priors

If your PO specialist has access to its calibration history (priors snapshot at build start — ASSUM-012), it should ingest fine. If the PO has been trained on prior FinProxy briefs, Coach scoring will be more confident.

For a first run, no priors exist. Coach scores will be lower-confidence early on. **This is expected and fine.** Force-flag thresholds in `forge.yaml` should already be set to flag-for-review on lower-confidence Coach scores during a first real run.

```bash
# Confirm forge.yaml on GB10 is set up for first-run conservatism:
ssh promaxgb10-41b1 'cat /var/forge/forge.yaml 2>/dev/null | head -30 || echo "default config — review thresholds before queueing"'
```

**Pass:** Either a custom `forge.yaml` is in place with a high `auto_approve_threshold` (e.g. 9.0+ on a 10-point scale) for the first run, or you accept the default and acknowledge most stages will auto-approve.

**Recommendation for first real run:** set `auto_approve_threshold` high enough that PO and architect both flag-for-review, regardless of Coach score. You want eyes on those outputs before committing to the architecture.

## Phase 1b: Confirm baseline (Mode B only — skip Phase 1)

### 1.1b Inspect existing architecture and design

```bash
ls /tmp/finproxy-inspect/docs/architecture/
ls /tmp/finproxy-inspect/docs/design/
# Read the top-level architecture doc to confirm it's current
head -60 /tmp/finproxy-inspect/docs/architecture/ARCHITECTURE.md 2>/dev/null
```

**Pass:** Architecture and design docs exist and the operator has read at least the top-level files. If they're stale or incomplete, fall back to Mode A.

### 1.2b Pick the feature to add

```bash
# What's the next feature in FinProxy's catalogue? Pick exactly one.
# Mode B operates on exactly one feature per build (ASSUM-006 / TASK-MBC8-009).

FEATURE_ID=FEAT-FINPROXY-001
FEATURE_TITLE="<one-line title>"
```

Capture the feature ID and title to the RESULTS file. Confirm the feature ID does not collide with an existing one in FinProxy's spec inventory.

---

## Phase 2: Queue the build

### 2.1 Subscribe to the build's lifecycle events (separate session)

Open a dedicated SSH session for monitoring. Leave it running for the full build.

```bash
ssh promaxgb10-41b1
nats sub 'pipeline.>' --headers --raw 2>&1 | tee ~/finproxy-run-events.log
```

This will be your audit log if anything goes sideways.

### 2.2 Queue the build (Mode A)

Run from the local machine — the operator's machine drives queueing and approvals.

```bash
# Mode A
export NATS_URL=nats://promaxgb10-41b1:4222

forge queue FEAT-FINPROXY-001 \
    --repo guardkit/finproxy \
    --branch main \
    --mode a \
    --brief "$(cat /tmp/finproxy-brief.md)"

# Capture the build_id and correlation_id for monitoring
forge status | tee /tmp/finproxy-status-initial.log
BUILD_ID=$(forge status --feature FEAT-FINPROXY-001 --format json | jq -r '.build_id')
CORRELATION_ID=$(forge status --feature FEAT-FINPROXY-001 --format json | jq -r '.correlation_id')
echo "BUILD_ID=$BUILD_ID"
echo "CORRELATION_ID=$CORRELATION_ID"
```

**Pass:** `forge status` shows FEAT-FINPROXY-001 with `mode=mode-a` and `state=preparing` or `state=running`. The events log shows `pipeline.build-queued.FEAT-FINPROXY-001` within ~1s.

**If the queue command fails:**
- "repo not in allowlist" → add `guardkit/finproxy` to `forge.yaml`'s `queue.repo_allowlist`
- "feature already queued" → a stale build is in progress; cancel with `forge cancel <build_id>` first
- NATS connection error → re-check Phase 0.4

### 2.2b Queue the build (Mode B)

```bash
export NATS_URL=nats://promaxgb10-41b1:4222

forge queue FEAT-FINPROXY-001 \
    --repo guardkit/finproxy \
    --branch main \
    --mode b
# Mode B needs no --brief; it starts from the existing arch/design baseline.
```

### 2.3 Confirm correlation threading

The first event published for the build should carry a `correlation_id`. Every subsequent event for the same build must carry the same `correlation_id` (FEAT-FORGE-008 Group H integration assertion).

```bash
ssh promaxgb10-41b1 'grep -c "$CORRELATION_ID" ~/finproxy-run-events.log'
# Should grow as the build progresses
```

**Pass:** count increases monotonically as new events fire. **If you see events for FEAT-FINPROXY-001 with a different correlation_id, the substrate has a routing bug** — file a P0 against TASK-MAG7-007/008/009.

---

## Phase 3: Drive Mode A through PO → architect → /system-arch → /system-design

For Mode B, skip to Phase 4.

### 3.1 The product-owner stage (~30–90 min)

The PO specialist expands the brief into a vision document. Expect the build to flag-for-review on the PO output if your `auto_approve_threshold` is set high.

**While waiting:**
- Watch the events log for `pipeline.build-paused.product-owner`
- Watch `forge status FEAT-FINPROXY-001` — should show `paused-at-product-owner`

**When the pause arrives:**
```bash
# On the local machine — pull down the PO output for review
forge artefact get FEAT-FINPROXY-001 --stage product-owner --output /tmp/finproxy-po-output/
ls /tmp/finproxy-po-output/

# Read it carefully. The vision doc drives every downstream stage.
$EDITOR /tmp/finproxy-po-output/vision.md
```

**Decision:**
- **Looks right → approve:** `forge approve $BUILD_ID --stage product-owner`
- **Needs revision → reject with feedback:** `forge reject $BUILD_ID --stage product-owner --feedback "Vision document conflates the dashboard with the proxy. The proxy is read-only; the dashboard is the only interface. Please re-emphasize this separation."`
  Then re-queue the build (rejection is terminal — not a revise loop).
- **Cancel the run:** `forge cancel $BUILD_ID --reason "..."` if the brief was wrong.

**Pass:** approval recorded; events log shows `pipeline.build-resumed.product-owner` followed by a new `pipeline.build-running.architect` event within seconds.

### 3.2 The architect stage (~1–3 hours)

Architect reads the PO vision and produces `ARCHITECTURE.md`, ADRs, and a container/component diagram. Same flag-for-review pattern as PO.

```bash
# On pause:
forge artefact get FEAT-FINPROXY-001 --stage architect --output /tmp/finproxy-arch-output/
ls /tmp/finproxy-arch-output/
$EDITOR /tmp/finproxy-arch-output/ARCHITECTURE.md
```

**What to look for in the architect output:**
- A reasonable system context diagram
- 5–15 ADRs covering the most decision-laden choices (data flow, persistence, auth, deployment)
- A container/component breakdown that matches the brief's complexity (don't accept a microservices architecture for a single-user proxy)
- Explicit non-functional commitments matching the brief (5s p95 latency, daily refresh)

**Approve or reject:**
```bash
forge approve $BUILD_ID --stage architect
# OR
forge reject $BUILD_ID --stage architect --feedback "<specific issue>"
```

### 3.3 The /system-arch stage (~30 min — subprocess)

This is where Forge invokes the GuardKit `/system-arch` slash command via subprocess (FEAT-FORGE-005 substrate). It reads the architect's output and produces the canonical artefacts under `forge_worktree/docs/architecture/`.

```bash
# On pause (if your thresholds force flag-for-review here):
forge artefact get FEAT-FINPROXY-001 --stage system-arch --output /tmp/finproxy-sysarch-output/
ls /tmp/finproxy-sysarch-output/
```

**What to verify:**
- Subprocess exited cleanly (no stack traces in the artefact bundle)
- The 31 ADRs from the architect stage are present in the output
- The system-context diagram is rendered

**Common first-run failure:** the subprocess can't find the `/system-arch` slash command in its search path. The forge container needs the GuardKit installer mounted or the slash command embedded. Capture this in the gaps log and either patch the container or document the workaround.

```bash
forge approve $BUILD_ID --stage system-arch
```

### 3.4 The /system-design stage (~1–2 hours — subprocess)

Reads architecture, produces per-container API contracts, data models, and DDRs.

Same review pattern as 3.3. The output here is what every per-feature `/feature-spec` will pull as `--context` — review carefully.

```bash
forge approve $BUILD_ID --stage system-design
```

---

## Phase 4: Per-feature cycles (Mode A) or single-feature cycle (Mode B)

After `/system-design` (Mode A) or from the start (Mode B), the build enters per-feature loops. Each feature in the catalogue (Mode A) or the single feature (Mode B) runs:

```
/feature-spec → /feature-plan → autobuild → (per-feature) advance to next OR pull-request review
```

### 4.1 /feature-spec for FEAT-FINPROXY-001 (~30 min — subprocess)

```bash
# On pause:
forge artefact get FEAT-FINPROXY-001 --stage feature-spec --output /tmp/finproxy-spec-output/
cat /tmp/finproxy-spec-output/*_summary.md
cat /tmp/finproxy-spec-output/*.feature
```

**What to verify:**
- BDD feature file exists with 20+ scenarios
- Assumptions YAML lists all assumptions with confidence ratings
- No `low` confidence assumptions are unresolved

**Approve or reject:**
```bash
forge approve $BUILD_ID --stage feature-spec
```

### 4.2 /feature-plan for FEAT-FINPROXY-001 (~30 min — subprocess)

```bash
# On pause:
forge artefact get FEAT-FINPROXY-001 --stage feature-plan --output /tmp/finproxy-plan-output/
ls /tmp/finproxy-plan-output/
cat /tmp/finproxy-plan-output/IMPLEMENTATION-GUIDE.md
```

**What to verify:**
- Tasks broken down into waves
- IMPLEMENTATION-GUIDE has all four mandatory diagrams (data flow, integration contracts, sequence, task dependency)
- §4 Integration Contracts pin every cross-task data dependency
- BDD scenarios are linked back via `@task:` tags
- Estimated effort is sane for the brief (a single-user proxy should not produce 50 tasks)

**Approve or reject:**
```bash
forge approve $BUILD_ID --stage feature-plan
```

### 4.3 Autobuild (~1–8 hours, async)

The longest stage. The autobuild dispatcher picks up the plan and runs `task-work` per task in waves. The supervisor remains responsive during this time (FEAT-FORGE-008 Group A async key-example).

```bash
# Monitor via forge status (does NOT block):
watch -n 30 'forge status FEAT-FINPROXY-001'

# Or via the live state channel:
forge tasks FEAT-FINPROXY-001 --live
```

**What to watch for:**
- Wave-by-wave progress (current wave / total waves visible in status)
- Per-task turn count (>1 means Coach pushed back at least once — not necessarily bad, but watch for stuck turns)
- SDK ceiling hits (if a task hits its turn ceiling without Coach approval, that task will fail; the build's continuation is decided at the gate)

**If the autobuild appears stuck:**
- Check `forge logs FEAT-FINPROXY-001 --tail 200` for stack traces
- Check the GB10 events log for `task-work` events stalling on a particular task
- The async-subagent state channel is advisory; durable history is authoritative (ASSUM-009)

**On autobuild completion (success):**
- Mode A: a per-feature flag-for-review pause arrives; approve to advance to the next feature in the catalogue OR to PR review if this is the last feature
- Mode B: advances to PR review (if commits exist) or no-op terminal (if no diff — Group M scenario)

### 4.4 Loop (Mode A only) or skip to Phase 5 (Mode B)

Mode A iterates Phase 4 for every feature in the system-design catalogue. Repeat 4.1 → 4.2 → 4.3 for each.

Capture the running per-feature outcomes in the RESULTS file as you go.

---

## Phase 5: Constitutional pull-request review (mandatory)

This is the constitutional terminal pause. It is **never** auto-approved regardless of Coach scores or operator skip-directives (ASSUM-011 / Group E).

### 5.1 Verify the pause arrived

```bash
forge status FEAT-FINPROXY-001
# Should show state=paused-at-pull-request-review, gate=MANDATORY_HUMAN_APPROVAL
forge artefact get FEAT-FINPROXY-001 --stage pull-request-review --output /tmp/finproxy-pr-output/
cat /tmp/finproxy-pr-output/pr-url.txt
```

**Pass:** A real PR URL is recorded against the build, on the FinProxy repo, on a forge-bot-prefixed branch.

### 5.2 Open the PR in the browser

```bash
gh pr view --repo guardkit/finproxy <PR-NUMBER> --web
# Or:
$BROWSER "$(cat /tmp/finproxy-pr-output/pr-url.txt)"
```

### 5.3 Review the PR

This is the human-in-the-loop checkpoint that the entire constitutional rule exists to guarantee. **Read the diff carefully.**

Things to verify:
- Code matches the architecture and design that you approved earlier
- BDD scenarios that were `@task:`-tagged in `/feature-plan` have corresponding test files
- No surprising scope creep (new dependencies you didn't approve, new files outside the planned waves)
- The forge-bot's commit messages reference the right TASK-FINPROXY-* IDs
- CI is passing on the PR

### 5.4 Decision

**Approve and merge:**
```bash
gh pr review <PR-NUMBER> --repo guardkit/finproxy --approve
gh pr merge <PR-NUMBER> --repo guardkit/finproxy --squash --delete-branch

# Then resolve the forge gate to mark the build complete:
forge approve $BUILD_ID --stage pull-request-review --pr-merged-sha <merge-sha>
```

**Request changes (terminal — does NOT loop back):**
```bash
gh pr review <PR-NUMBER> --repo guardkit/finproxy --request-changes \
    --body "<specific issues>"
forge reject $BUILD_ID --stage pull-request-review --feedback "see PR comments"
```
The build reaches a `failed` terminal state. To address the issues, file a follow-up Mode C run on the merged-but-imperfect branch (Mode C exists exactly for this case) OR re-queue a fresh Mode A/B build with refined inputs.

**Pass:** the build reaches `complete` terminal state. The PR is merged. `forge history FEAT-FINPROXY-001` shows the full chain of gate decisions in chronological order with the merge SHA recorded.

---

## Phase 6: Post-run capture

### 6.1 Capture the build's full stage history

```bash
forge history FEAT-FINPROXY-001 --format json --include-artefacts \
    > /tmp/finproxy-stage-history.json

# Pretty-print for the RESULTS file:
forge history FEAT-FINPROXY-001 --format markdown \
    > /tmp/finproxy-stage-history.md
```

### 6.2 Capture autobuild metrics per feature

```bash
ls .guardkit/autobuild/FEAT-FINPROXY-*/review-summary.md
for SUMMARY in .guardkit/autobuild/FEAT-FINPROXY-*/review-summary.md; do
    echo "=== $SUMMARY ==="
    cat "$SUMMARY"
    echo
done > /tmp/finproxy-autobuild-summaries.md
```

### 6.3 Compare against expectations

Per the build plan estimate: "FinProxy first run — Validation + FinProxy run: 1 week, including testing, debugging, first real pipeline."

Compare actual vs expected:
- Wall-clock time
- Operator active time
- Specialist budget consumed
- Number of flag-for-review pauses requiring human input
- Number of subprocess failures requiring intervention
- Number of inline runbook adjustments

### 6.4 Capture lessons

Write `forge/docs/runbooks/RESULTS-finproxy-first-run.md` using this template:

```markdown
# Results: FinProxy First Real Run (Step 7)

**Started:** YYYY-MM-DD HH:MM
**Completed:** YYYY-MM-DD HH:MM
**Wall-clock:** X days (Y operator hours)
**Operator:** <name>
**Mode:** A or B
**Forge image:** commit `<sha>`
**Specialist-agent image:** commit `<sha>` on each role

## Decision

- [ ] **Step 7 ✅ canonical** — Forge is in production. Recommend the next FinProxy feature.
- [ ] **Step 7 partially passed** — PR merged but issues encountered; lessons folded back into runbook.
- [ ] **Step 7 failed** — PR not merged; root-cause analysis below.

## Stage-by-stage summary

| Stage | Outcome | Wall-clock | Operator decision | Notes |
|-------|---------|-----------|-------------------|-------|
| product-owner | ✅ approved / ❌ rejected | … | approve/reject | … |
| architect | … | … | … | … |
| /system-arch | … | … | … | … |
| /system-design | … | … | … | … |
| /feature-spec FEAT-FINPROXY-001 | … | … | … | … |
| /feature-plan FEAT-FINPROXY-001 | … | … | … | … |
| autobuild FEAT-FINPROXY-001 | … | … | … | … |
| pull-request-review | ✅ merged / ❌ rejected | … | approve/reject | PR #N |
| (Mode A only — additional features) | … | … | … | … |

## Headline metrics

- Total wall-clock: X
- Operator active time: Y
- Specialist dispatches: Z
- Subprocess invocations: W
- Coach pushbacks (turn > 1): V
- SDK ceiling hits: U
- Manual interventions (re-queue, hot-fix, etc.): T

## What worked

(One paragraph per item.)

## What didn't work

(One paragraph per item, each linking to a follow-up TASK-* if applicable.)

## Runbook gaps discovered during execution

| Phase | Block | What needed adjustment | Suggested runbook fix |
|-------|-------|------------------------|----------------------|
| ... | ... | ... | ... |

## Follow-ups

- TASK-FORGE-FP-001: <issue> — <one-line scope>
- ...
```

### 6.5 Update the build plan

```bash
cd ~/Projects/appmilla_github/forge
$EDITOR docs/research/ideas/forge-build-plan.md
```

Apply:
1. **Status header** (line 3): change `Next: Step 7 FinProxy first real run` → `Forge canonical (Step 7 complete YYYY-MM-DD)` or similar
2. **Step 7 row** (progress log): mark ✅ with date, RESULTS file pointer, headline metrics
3. **Footer log**: append a new entry with the run date and outcome

### 6.6 Log the canonical-freeze walkthrough

Per LES1 §8: every shell block in this runbook must have been executed verbatim on this run, with any required tweaks annotated `[as of commit <sha>]` and folded back into the runbook in a follow-up commit.

```bash
# Update command-history.md with the run summary
$EDITOR docs/history/command-history.md
```

Add an entry of the form:
```markdown
## YYYY-MM-DD: FinProxy first real run

- Mode: A
- Wall-clock: X days
- PR: guardkit/finproxy#N (merged)
- Runbook: docs/runbooks/RUNBOOK-FEAT-FORGE-008-finproxy-first-run.md
- RESULTS: docs/runbooks/RESULTS-finproxy-first-run.md
- Inline tweaks needed: …
- Folded back into runbook in commit <sha>
```

---

## Things that will go wrong on the first real run

These are the patterns the validation runbook can't catch — they require real specialist dispatches and real subprocess invocations to surface.

1. **Specialist agent timeouts on long PO/architect tasks.** A PO vision doc on a richer brief can take >5 minutes. If the NATS request timeout is too aggressive, the dispatch will appear to fail. Bump `request_timeout_seconds` in `forge.yaml` if you see timeouts that aren't real failures.

2. **Coach scoring drift.** With no prior calibration history for FinProxy, Coach scores will trend lower-confidence. Force-flag thresholds prevent silent auto-approves of imperfect output. Don't lower the threshold mid-run; re-queue with refined inputs instead.

3. **Subprocess command not found.** The `/system-arch`, `/system-design`, `/feature-spec`, `/feature-plan` slash commands run in subprocess. The forge container needs them on its PATH. If you see "command not found" in subprocess artefacts, check the container's GuardKit install and either rebuild or mount the installer.

4. **Subprocess worktree allowlist mismatch.** FEAT-FORGE-005 confines subprocesses to a per-build worktree. If FinProxy was cloned into a path the worktree allowlist doesn't cover, the subprocess will fail to read the repo. Confirm `forge.yaml`'s `worktree.allowlist` includes the parent of where FinProxy will be cloned.

5. **`gh` CLI auth not propagated.** The forge container running `forge serve` on GB10 may not have the operator's `gh` auth. The PR-creation subprocess (FEAT-FORGE-006) will fail at the very last step. Mount the operator's `~/.config/gh/` into the container OR use a service-account `gh` token configured per-repo. Capture this gap if it bites.

6. **Branch protection rules block the PR.** FinProxy may have main-branch protection requiring CI green and approving reviews. The forge-bot may not have permission to bypass these. Either add forge-bot to the allowed-actors list OR accept that the PR sits in awaiting-CI state until you manually merge.

7. **Specialist-agent / forge image version drift.** If the production specialist-agent image was last rebuilt before the production forge image (or vice versa), payload schema changes can cause silent contract mismatches. The CMDW gate caught this in Step 6.1; if it slipped, re-run Phase 6.1 of the validation runbook before debugging anything else.

8. **Calibration priors snapshot stale.** The build snapshots calibration priors at start (ASSUM-012). If the operator's calibration history was empty at queue time and you've since added priors, those new priors are NOT used by the in-flight build. This is by design.

9. **NATS account credentials expire mid-run.** A long-running build (multi-day) can outlive a credential's TTL. Confirm the JetStream credential's TTL covers the expected wall-clock + buffer.

10. **Cancel during async stage doesn't terminate the autobuild.** FEAT-FORGE-008 Group D edge-case asserts cancel terminates the async task. If you issue `forge cancel` and the autobuild keeps producing events, durable history is being bypassed. File a P0.

---

## References

- **Predecessor runbook:** [`RUNBOOK-FEAT-FORGE-008-validation.md`](RUNBOOK-FEAT-FORGE-008-validation.md) — Step 6 gates that gated this run
- **Style precedents:**
  - `guardkit/docs/research/dgx-spark/RUNBOOK-v3-production-deployment.md` — phase structure + gap-folding pattern
  - `agentic-dataset-factory/domains/architect-agent-probe/RUNBOOK-fix-tutor-template-leak.md` — root-cause-first debugging style
- **Build plan:** `forge/docs/research/ideas/forge-build-plan.md` — Step 7 spec, FinProxy targeting
- **Upstream contracts:**
  - `forge/docs/design/contracts/API-nats-approval-protocol.md` — constitutional rule §8
  - `forge/docs/design/contracts/API-cli.md` — `forge queue/status/history/cancel/skip` surface
  - `forge/docs/design/models/DM-build-lifecycle.md` — state-machine transitions and crash-recovery
- **Feature artefacts produced by this run:**
  - `<finproxy-repo>/docs/architecture/` — produced by /system-arch
  - `<finproxy-repo>/docs/design/` — produced by /system-design
  - `<finproxy-repo>/features/<feature-slug>/*.feature` — produced by /feature-spec
  - `<finproxy-repo>/tasks/backlog/<feature-slug>/` — produced by /feature-plan
  - `<finproxy-repo>/src/` — produced by autobuild
  - PR on `guardkit/finproxy` — the constitutional terminal artefact
- **Lessons series:**
  - LES1 §8 — runbook copy-paste blocks are code; annotate manual tweaks
  - LES1 §7 — fresh-volume NATS provisioning gotcha

---

*Generated 2026-04-29 alongside FEAT-FORGE-008 Step 7 readiness. Update with `[as of commit <sha>]` annotations during the first real run; fold inline tweaks back in a follow-up commit.*
