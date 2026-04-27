Please review /home/richardwoollcott/Projects/appmilla_github/forge/docs/research/ideas/forge-build-plan.md and update the status and work out my next steps I think it should be : # FEAT-FORGE-008: Mode B Feature & Mode C Review-Fix (depends on 007)
guardkit feature-plan FEAT-FORGE-008 \
  --context forge/features/<feat-forge-008-slug>/<feat-forge-008-slug>_summary.md

So this nees updating I think? Please see the histories in /home/richardwoollcott/Projects/appmilla_github/forge/docs/history and git

Now I have the full picture. Let me update the build plan with accurate status and resolve the FEAT-FORGE-008 placeholders.

Summary of actual state vs. doc:

Doc claims /feature-spec is 5/8 (header) but body shows 6/8. Reality: 7/8 done (FEAT-FORGE-001..007 — see feature-spec-FEAT-FORGE-007-history.md and features/mode-a-greenfield-end-to-end/).
/feature-plan is 6/8 done (002, 003, 004, 005, 006, 007). FEAT-FORGE-001 was never planned.
autobuild is 6/8 done (002, 003, 004, 005, 8D10=006, CBDE=007 — see git log). FEAT-FORGE-001 was never built as a discrete feature; its scope (pipeline/, config/) appears folded into 002–007.
FEAT-FORGE-008 has had no spec, no plan, no build.
Let me apply the doc edits.

Edit forge-build-plan.md
Modified
Edit forge-build-plan.md
Modified
Now add the FEAT-FORGE-007 spec entry to the completed list, and resolve the FEAT-FORGE-007 slug placeholder in Step 4 + add the Step 4 / Step 5 status headers.

Edit forge-build-plan.md
Added 8 lines
Now fix the FEAT-FORGE-008 spec command block (it currently points to a non-existent path) and update Step 4 to remove the FEAT-FORGE-007 placeholder and add status markers.

Edit forge-build-plan.md
Added 8 lines
Edit forge-build-plan.md
Added 13 lines
Now Step 5 (autobuild) status header.

Edit forge-build-plan.md
Added 6 lines
Now bump the trailer date and status line.

Edit forge-build-plan.md
Added 1 line
Plan is updated. Here's where you actually are and what comes next.

Status (corrected)
Stage	Done	Pending
/system-arch	✅	—
/system-design	✅	—
/feature-spec	7/8 (001–007)	008
/feature-plan	6/8 (002–007)	008 (001 skipped — folded in)
autobuild	6/8 (002–007)	008 (001 absorbed)
Validation	◻	—
FinProxy run	◻	—
The doc previously claimed 5/8 specs in the header (and 6/8 in the body) — both stale. Reality is 7/8 across the board for 002–007.

Your suggested next step needs one prior step
You proposed running:


guardkit feature-plan FEAT-FORGE-008 \
  --context forge/features/<feat-forge-008-slug>/<feat-forge-008-slug>_summary.md
That's blocked: /feature-spec FEAT-FORGE-008 has not been run yet, so the slug directory doesn't exist. The placeholder can't be resolved.

Recommended sequence
/feature-spec FEAT-FORGE-008 — produces features/mode-b-feature-and-mode-c-review-fix/ (slug TBD). Updated context flags now in forge-build-plan.md Step 3:


guardkit feature-spec FEAT-FORGE-008 \
  --context forge/features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end.feature \
  --context forge/features/mode-a-greenfield-end-to-end/mode-a-greenfield-end-to-end_summary.md \
  --context forge/docs/design/contracts/API-cli.md \
  --context forge/docs/design/contracts/API-nats-approval-protocol.md \
  --context forge/docs/design/models/DM-build-lifecycle.md
The previous spec command was wrong — it pointed at forge/features/FEAT-FORGE-007/feature-spec.md, which never existed (the real path is mode-a-greenfield-end-to-end/).

/feature-plan FEAT-FORGE-008 — your suggested command, with the real slug substituted once Step 1 completes.

autobuild FEAT-FORGE-008 — Wave 6.

Step 6 validation — including the four LES1 parity gates (CMDW / PORT / ARFS / canonical-freeze) before declaring the build canonical.

Step 7 FinProxy first run.

One thing worth deciding before you start 008
FEAT-FORGE-001 was never planned or autobuilt. The src tree (pipeline/, config/, etc.) was populated piecemeal by 002–007, which works in practice but means there's no isolated coverage of the foundation contract: forge queue CLI surface, forge.yaml loader, SQLite-backed crash recovery as a unit. The doc now says: if Step 6 validation exposes a gap, spawn a discrete FEAT-FORGE-009 to backfill rather than retro-running 001. If you'd rather close that gap before 008 (cleaner foundation, but adds days), say so and I'll flip the recommendation.

let's close that gap
Good call. Let me check what FEAT-FORGE-001 specced versus what's actually in the tree, so we can scope the backfill precisely instead of re-running the whole feature and creating conflicts with existing code.

Read pipeline-state-machine-and-configuration_summary.md
Bash List all Python source files
IN
find /home/richardwoollcott/Projects/appmilla_github/forge/src/forge -type f -name "*.py" | sort

OUT
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/gh/__init__.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/gh/operations.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/git/__init__.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/git/models.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/git/operations.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/guardkit/context_resolver.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/guardkit/__init__.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/guardkit/models.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/guardkit/parser.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/guardkit/progress.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/guardkit/progress_subscriber.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/guardkit/run.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/__init__.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/langgraph/__init__.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/nats/approval_publisher.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/nats/approval_subscriber.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/nats/fleet_publisher.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/nats/fleet_watcher.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/nats/__init__.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/nats/pipeline_consumer.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/nats/pipeline_publisher.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/nats/specialist_dispatch.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/nats/synthetic_response_injector.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/agent.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/config/__init__.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/config/models.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/discovery/cache.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/discovery/__init__.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/discovery/models.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/discovery/protocol.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/discovery/resolve.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/dispatch/async_polling.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/dispatch/correlation.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/dispatch/__init__.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/dispatch/models.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/dispatch/orchestrator.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/dispatch/outcome.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/dispatch/persistence.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/dispatch/reply_parser.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/dispatch/retry.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/dispatch/timeout.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/fleet/__init__.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/fleet/manifest.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/gating/constitutional.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/gating/identity.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/gating/__init__.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/gating/models.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/gating/reasoning.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/gating/wrappers.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/__init__.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/memory/__init__.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/memory/models.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/memory/ordering.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/memory/priors.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/memory/qa_ingestion.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/memory/reconciler.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/memory/redaction.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/memory/session_outcome.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/memory/supersession.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/memory/writer.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/cli_steering.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/constitutional_guard.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/dispatchers/autobuild_async.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/dispatchers/__init__.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/dispatchers/specialist.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/dispatchers/subprocess.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/forward_context_builder.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/forward_propagation.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/__init__.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/per_feature_sequencer.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/stage_ordering_guard.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/stage_taxonomy.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/supervisor.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/tools/graphiti.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/tools/guardkit.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/tools/__init__.py
Bash Search for SQLite / CLI surface in source
IN
grep -r -l "sqlite\|builds.db\|stage_log\|forge queue" /home/richardwoollcott/Projects/appmilla_github/forge/src/ 2>/dev/null

OUT
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/memory/reconciler.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/memory/ordering.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/dispatch/persistence.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/adapters/nats/pipeline_consumer.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/dispatchers/autobuild_async.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/memory/session_outcome.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/supervisor.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/stage_ordering_guard.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/dispatchers/subprocess.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/constitutional_guard.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/cli_steering.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/dispatchers/specialist.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/dispatchers/__init__.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/forward_context_builder.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/forward_propagation.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/gating/wrappers.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/per_feature_sequencer.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/gating/models.py
Bash Check pyproject for CLI entrypoints
IN
grep -A5 "scripts\|entry-points\|console_scripts" /home/richardwoollcott/Projects/appmilla_github/forge/pyproject.toml | head -40

OUT
(Bash completed with no output)
Read models.py
Quick gap analysis — what FEAT-FORGE-001 specced vs. what's actually in the tree:

Specced	Status
CLI: forge queue / status / history / cancel / skip	❌ Missing — no cli/ package, no console_scripts in pyproject
Build-lifecycle state machine (IDLE→PREPARING→RUNNING→FINALISING→COMPLETE/FAILED)	❌ Missing — pipeline/ has stage-ordering guards (within a build) but not the lifecycle state machine
SQLite history (builds + stage_log per DDR-003)	❌ Missing — sqlite usage exists in memory/ and dispatch/persistence.py but no central build-history schema
Crash recovery (rehydrate every lifecycle state on restart)	❌ Missing
Sequential queue per-project (max_concurrent=1)	❌ Missing as discrete enforcement
Path-traversal validation on feature_id	❌ Missing
Cancel-operator audit trail	❌ Missing
This is a real gap — 002–007 assume the queue/CLI/lifecycle surface exists upstream and just plug into the parts they need (config, NATS adapters). Nothing has actually built forge queue or the build-lifecycle state machine.

Recommended path
Don't blindly re-run /feature-plan FEAT-FORGE-001 — the existing spec was written assuming a clean slate, so a naive plan will duplicate config/manifest work that 002–007 already shipped (e.g. forge.config.models already has FleetConfig, ApprovalConfig, etc.).

Instead, do this:

I write a short forge-001-gap-context.md — per-scenario coverage table (covered / partial / missing) so /feature-plan knows what to skip and what to focus on.
You run /feature-plan FEAT-FORGE-001 --context <spec_summary> --context <gap-context> — produces a plan scoped to the missing pieces only.
You run autobuild FEAT-FORGE-001 — Wave 1 backfill.
Then proceed to FEAT-FORGE-008 (spec → plan → build).
The gap-context doc is the load-bearing piece — without it, the plan will produce duplicated work.

Alternative (heavier ceremony, cleaner separation): spec a new FEAT-FORGE-001B titled something like "Build Lifecycle CLI & Crash Recovery" covering only the missing scope, then plan + build that. Keeps the original FEAT-FORGE-001 spec untouched as the canonical contract, and the new feature is the implementation slice.

I'd recommend option 1 (gap-context + re-plan) — keeps the FEAT-FORGE-NNN numbering coherent and reuses the existing 34-scenario spec rather than splitting it. Which way do you want to go? If option 1, I'll write the gap-context doc next.

proceed with option 1 then I can run the feature-plan
I'll read the FEAT-FORGE-001 feature file and probe the source tree to map coverage, then write the gap-context doc.

Read pipeline-state-machine-and-configuration.feature
Bash Find any build-lifecycle code
IN
grep -l "Build\|build_id\|state_machine\|lifecycle\|forge.cli\|forge_queue" /home/richardwoollcott/Projects/appmilla_github/forge/src/forge/**/*.py 2>/dev/null | head -20

OUT
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/discovery/resolve.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/discovery/models.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/dispatch/async_polling.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/config/models.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/fleet/manifest.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/memory/qa_ingestion.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/gating/identity.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/gating/constitutional.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/dispatch/outcome.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/memory/reconciler.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/memory/session_outcome.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/stage_ordering_guard.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/supervisor.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/gating/models.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/gating/reasoning.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/memory/priors.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/dispatch/persistence.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/dispatch/orchestrator.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/gating/wrappers.py
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/tools/guardkit.py
Bash Find Build/lifecycle data classes
IN
grep -E "class (Build|StageLogEntry|BuildStatus|BuildState|BuildHistory)" /home/richardwoollcott/Projects/appmilla_github/forge/src/forge/**/*.py 2>/dev/null

OUT
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/supervisor.py:class BuildState(StrEnum):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/__init__.py:class BuildContext:
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/cli_steering.py:class BuildLifecycle(StrEnum):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/cli_steering.py:class BuildSnapshot:
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/cli_steering.py:class BuildSnapshotReader(Protocol):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/cli_steering.py:class BuildCanceller(Protocol):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/cli_steering.py:class BuildResumer(Protocol):
Bash Inspect config layer
IN
grep -rn "config.models\|ProjectConfig\|forge\.yaml\|load_config" /home/richardwoollcott/Projects/appmilla_github/forge/src/forge/config/ 2>/dev/null | head -20

OUT
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/config/models.py:1:"""Pydantic v2 models describing the ``forge.yaml`` configuration surface.
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/config/models.py:26:Per the project boundary rules for ``forge.config.models``, this module
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/config/models.py:82:#: forge.yaml.approval.max_wait_seconds ≈ 3600").
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/config/models.py:95:    ``forge.yaml`` but the defaults must continue to match the assumptions
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/config/models.py:155:    override either field in ``forge.yaml`` but the defaults must continue to
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/config/models.py:261:    """Root model for ``forge.yaml``.
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/config/models.py:264:    minimal ``forge.yaml`` only needs to declare the required ``permissions``
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/config/__init__.py:3:Re-exports the Pydantic v2 models that describe ``forge.yaml``. Importing from
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/config/__init__.py:5:layout (see ``forge.config.models``).
Read __init__.py
Bash List classes/funcs in config models
IN
grep -E "^(class |def )" /home/richardwoollcott/Projects/appmilla_github/forge/src/forge/config/models.py | head -40

OUT
class FleetConfig(BaseModel):
class PipelineConfig(BaseModel):
class ApprovalConfig(BaseModel):
class FilesystemPermissions(BaseModel):
class PermissionsConfig(BaseModel):
class ForgeConfig(BaseModel):
Bash Inspect pipeline module signatures
IN
grep -E "^(class |def )" /home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/supervisor.py /home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/per_feature_sequencer.py /home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/cli_steering.py 2>/dev/null

OUT
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/per_feature_sequencer.py:class AutobuildStateLike(Protocol):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/per_feature_sequencer.py:class StageLogReader(Protocol):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/per_feature_sequencer.py:class AsyncTaskReader(Protocol):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/per_feature_sequencer.py:class PerFeatureLoopSequencer:
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/supervisor.py:class TurnOutcome(StrEnum):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/supervisor.py:class BuildState(StrEnum):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/supervisor.py:class DispatchChoice:
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/supervisor.py:class TurnReport:
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/supervisor.py:class TerminalStateError(RuntimeError):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/supervisor.py:class StateMachineReader(Protocol):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/supervisor.py:class ReasoningModelPort(Protocol):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/supervisor.py:class StageLogTurnRecorder(Protocol):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/supervisor.py:class PRReviewGate(Protocol):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/supervisor.py:class Supervisor:
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/cli_steering.py:class BuildLifecycle(StrEnum):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/cli_steering.py:class CancelStatus(StrEnum):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/cli_steering.py:class SkipStatus(StrEnum):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/cli_steering.py:class DirectiveStatus(StrEnum):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/cli_steering.py:class BuildSnapshot:
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/cli_steering.py:class CancelOutcome:
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/cli_steering.py:class SkipOutcome:
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/cli_steering.py:class DirectiveOutcome:
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/cli_steering.py:class BuildSnapshotReader(Protocol):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/cli_steering.py:class PauseRejectResolver(Protocol):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/cli_steering.py:class AsyncTaskCanceller(Protocol):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/cli_steering.py:class AsyncTaskUpdater(Protocol):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/cli_steering.py:class BuildCanceller(Protocol):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/cli_steering.py:class StageSkipRecorder(Protocol):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/cli_steering.py:class BuildResumer(Protocol):
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/cli_steering.py:class CliSteeringHandler:
Bash Read pyproject head for entry points and deps
IN
cat /home/richardwoollcott/Projects/appmilla_github/forge/pyproject.toml | head -80

OUT
[project]
name = "forge"
version = "0.1.0"
description = "Pipeline orchestrator and checkpoint manager for the Software Factory"
readme = "README.md"
requires-python = ">=3.11"
authors = [
    { name = "Richard Woollcott", email = "rich@appmilla.com" },
]
dependencies = [
    "deepagents>=0.5.3,<0.6",
    "langchain>=1.2.11",
    "langchain-core>=1.2.18",
    "langgraph>=0.2",
    "langchain-community>=0.3",
    "langchain-anthropic>=0.2",
    "nats-core>=0.2.0,<0.3",
    "python-dotenv>=1.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
# Every LangChain integration this template can be configured to use MUST appear here.
# See TASK-REV-LES1 / LES1 §3 LCOI — provider swaps happen via orchestrator-config.yaml,
# so all supported providers must be declarable in one install command.
providers = [
    "langchain-openai>=0.2",
    "langchain-google-genai>=2.0",
]

[dependency-groups]
dev = [
    "pytest>=9.0.2",
    "pytest-bdd>=8.1,<9",
]

[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
# Source layout: production code lives under ``src/forge``. Pytest
# resolves imports via this ``pythonpath`` entry so ``import forge`` works
# without callers needing to set ``PYTHONPATH=src`` on every invocation.
# This matches how the GuardKit BDD oracle (TASK-IC-012) invokes pytest
# with the feature file as a positional arg — without this entry,
# ``tests/bdd/conftest.py`` fails to import ``forge.adapters.*`` at
# collection time and the oracle reports a synthetic BDD failure.
pythonpath = ["src"]
# pytest-bdd: feature files live alongside the source-of-truth Gherkin
# under ``features/``. Scenarios are wired to step functions in
# ``tests/bdd/``. See TASK-NFI-011.
bdd_features_base_dir = "features"
markers = [
    # Scenario-priority tags mirrored from the .feature files. CI uses these
    # to gate which subset of the BDD suite must pass per pipeline stage:
    #   * ``smoke``        — full suite on every PR (3 scenarios for FEAT-FORGE-002)
    #   * ``key_example``  — full suite on merge to main (7 scenarios)
    #   * remaining tags   — opportunistically run; explicitly @skip when
    #                        the owning subtask is not yet complete.
    "smoke: @smoke scenarios — must pass on every PR",
    "key_example: @key-example scenarios — must pass on merge to main",
    "boundary: @boundary scenarios — boundary-condition coverage",
    "negative: @negative scenarios — negative-path coverage",
    "edge_case: @edge-case scenarios — edge-case coverage",
    "security: @security scenarios — security-property coverage",
    "concurrency: @concurrency scenarios — concurrent-event coverage",
    "data_integrity: @data-integrity scenarios — data-integrity coverage",
    "integration: @integration scenarios — integration-boundary coverage",
    # Seam tests stamping the §4 Integration Contract they exercise. The
    # argument is the contract name (e.g. ``CapabilityResolution``,
    # ``CorrelationKey``); reviewers grep for the contract to find the
    # seam test that exercises it.
    "integration_contract: seam test for a §4 integration contract",
    # Feature-level tags emitted by /feature-spec onto every scenario in a
    # generated .feature file. Registered here so pytest does not warn on
    # unknown marks when pytest-bdd reflects Gherkin tags onto test items.
Now I'll write the gap-context doc with per-scenario coverage and a focused "what's left" inventory.

Read cli_steering.py
This is very helpful — cli_steering.py already implements the executor-layer (cancel-resolves-to-reject, skip-veto, etc.) and explicitly leaves the thin CLI wrapper to FEAT-FORGE-001. Several Protocol seams (BuildSnapshotReader, BuildCanceller, BuildResumer) are already defined — FEAT-FORGE-001 just needs to provide the concrete persistence-backed implementations and the CLI verbs that call into them.

Now writing the gap-context doc.

Write forge-001-gap-context.md
287 lines
# FEAT-FORGE-001 Gap Context — what already exists, what `/feature-plan` must build

> **Purpose:** focused context for `/feature-plan FEAT-FORGE-001` so the plan does
> **not** duplicate work that 002–007 already shipped. FEAT-FORGE-001 was specced
> on a clean-slate assumption (Apr 24); it was then absorbed silently into the
> per-feature backlogs of 002–007, which built the *upstream-of-CLI* surface
> (NATS adapters, config models, stage-ordering guards, executor-layer cancel /
> skip handler) but **not** the CLI itself, the SQLite-backed build history,
> the build-lifecycle transition table, or crash recovery.
>
> Read alongside [pipeline-state-machine-and-configuration_summary.md](../../../features/pipeline-state-machine-and-configuration/pipeline-state-machine-and-configuration_summary.md)
> (the feature spec) and [DDR-003-sqlite-schema-layout-wal.md](../../design/decisions/DDR-003-sqlite-schema-layout-wal.md)
> (the SQLite schema contract).

## How to use this document

Pass it to `/feature-plan FEAT-FORGE-001` as a `--context` flag alongside the
spec summary:

```bash
guardkit feature-plan "Pipeline State Machine and Configuration" \
  --context forge/features/pipeline-state-machine-and-configuration/pipeline-state-machine-and-configuration_summary.md \
  --context forge/docs/research/ideas/forge-001-gap-context.md \
  --context forge/docs/design/contracts/API-cli.md \
  --context forge/docs/design/contracts/API-sqlite-schema.md \
  --context forge/docs/design/decisions/DDR-003-sqlite-schema-layout-wal.md
```

The plan must **reuse** the existing Protocols / executor logic listed in §2 and
**only build** the gaps in §3.

---

## §1 — TL;DR

| Layer | Status | Owning module(s) |
|---|---|---|
| Config models (`forge.yaml` schema) | ✅ shipped | [src/forge/config/models.py](../../../src/forge/config/models.py) |
| Build-lifecycle state enum | ✅ shipped | [src/forge/pipeline/supervisor.py](../../../src/forge/pipeline/supervisor.py) (`BuildState`), [src/forge/pipeline/cli_steering.py](../../../src/forge/pipeline/cli_steering.py) (`BuildLifecycle`) |
| Build-lifecycle **transition table** + invalid-transition rejection | ❌ **build** | new — `src/forge/lifecycle/state_machine.py` |
| Cancel / skip executor logic (synthetic reject, skip-veto, directive enqueue) | ✅ shipped | [src/forge/pipeline/cli_steering.py](../../../src/forge/pipeline/cli_steering.py) |
| Cancel / skip Protocol seams (`BuildSnapshotReader`, `BuildCanceller`, `BuildResumer`, `StageLogReader`, `StageSkipRecorder`, `PauseRejectResolver`, `AsyncTaskCanceller`, `AsyncTaskUpdater`) | ✅ shipped (interfaces only) | [src/forge/pipeline/cli_steering.py](../../../src/forge/pipeline/cli_steering.py) |
| **Concrete SQLite-backed implementations of those Protocols** | ❌ **build** | new — `src/forge/lifecycle/persistence.py` |
| `builds` + `stage_log` SQLite schema (DDR-003 WAL + STRICT) | ❌ **build** | new — `src/forge/lifecycle/schema.sql` + `migrations.py` |
| NATS pipeline consumer (pull, durable) | ✅ shipped | [src/forge/adapters/nats/pipeline_consumer.py](../../../src/forge/adapters/nats/pipeline_consumer.py) |
| NATS pipeline publisher (lifecycle subjects) | ✅ shipped | [src/forge/adapters/nats/pipeline_publisher.py](../../../src/forge/adapters/nats/pipeline_publisher.py) |
| Synthetic response injector (cancel→reject for paused builds) | ✅ shipped | [src/forge/adapters/nats/synthetic_response_injector.py](../../../src/forge/adapters/nats/synthetic_response_injector.py) |
| **CLI surface (`forge queue/status/history/cancel/skip`)** | ❌ **build** | new — `src/forge/cli/main.py` + per-command modules |
| **`console_scripts` entry point** | ❌ **build** | edit — [pyproject.toml](../../../pyproject.toml) |
| **Sequential-queue picker** (per-project max_concurrent=1) | ❌ **build** | new — `src/forge/lifecycle/queue.py` |
| **Crash-recovery / reconciliation pass** (rehydrate non-terminal builds on restart) | ❌ **build** | new — `src/forge/lifecycle/recovery.py` |
| **Path-traversal validation** for `feature_id` | ❌ **build** | new — `src/forge/lifecycle/identifiers.py` |
| **Watch-mode** (`forge status --watch`) | ❌ **build** | new — folded into `cli/status.py` |
| **Defaults application** (forge.yaml → new build) | ❌ **build** | folded into `cli/queue.py` + `lifecycle/persistence.py` |
| **Write-then-publish failure-mode visibility** (build row remains pending pickup if NATS publish fails) | ❌ **build** | folded into `cli/queue.py` |

**Net new code surface:** one new package — `src/forge/lifecycle/` (persistence,
schema, state machine, queue, recovery, identifiers) — plus the `src/forge/cli/`
package and a small pyproject edit. Everything else wires to existing modules.

---

## §2 — What `/feature-plan` MUST reuse (do not duplicate)

### 2.1 Config layer — `src/forge/config/`

`ForgeConfig` and its sub-models (`PipelineConfig`, `ApprovalConfig`,
`FleetConfig`, `PermissionsConfig`, `FilesystemPermissions`) already exist as
Pydantic v2 models at [src/forge/config/models.py](../../../src/forge/config/models.py).
The `ForgeConfig` root model is the parsed shape of `forge.yaml`.

**What's missing here, but must be added inside the existing module (not a new
config package):**
- A `load_config(path: Path) -> ForgeConfig` helper that reads YAML + validates
  via Pydantic. (The class exists; the loader does not.)
- An additional sub-model for `forge.yaml.queue` (turn-budget defaults, history
  default-limit `50`, allowlisted repository paths) — see spec scenarios under
  Group A "Configuration loading" and Group C "path allowlist".

`/feature-plan` should produce **edit** tasks against `forge/config/models.py`,
not a parallel `forge/lifecycle/config.py`.

### 2.2 Pipeline executor layer — `src/forge/pipeline/cli_steering.py`

`CliSteeringHandler` already implements:
- Cancel-during-pause → synthetic reject (FEAT-FORGE-004 ASSUM-005, AC-002)
- Cancel-during-autobuild → `cancel_async_task` + terminal CANCELLED (AC-002)
- Skip-on-non-constitutional-stage → stage logged SKIPPED, resume next (AC-003 / AC-006)
- Skip-on-constitutional-stage → vetoed via `ConstitutionalGuard.veto_skip` (AC-007)
- Mid-flight directive → enqueued onto `AutobuildState.pending_directives` (AC-004)

The Protocol seams (`BuildSnapshotReader`, `PauseRejectResolver`,
`AsyncTaskCanceller`, `AsyncTaskUpdater`, `BuildCanceller`, `StageSkipRecorder`,
`BuildResumer`) are defined in the same module and explicitly waiting for
FEAT-FORGE-001's concrete implementations.

**`/feature-plan` MUST NOT** redesign the cancel/skip semantics. It must only
produce a concrete `LifecyclePersistence` / `SqliteBuildSnapshotReader` /
`SqliteBuildCanceller` / etc. classes that satisfy these Protocols, and a thin
CLI wrapper that calls `CliSteeringHandler.handle_cancel()` /
`.handle_skip()` / `.handle_directive()`.

### 2.3 Pipeline supervisor — `src/forge/pipeline/supervisor.py`

`Supervisor` owns the **per-turn reasoning loop within a running build**.
`BuildState` enum is here, used by the supervisor to refuse work after a
terminal state (`TerminalStateError`).

**What's NOT here:** the build-lifecycle transition graph (queued→pending_pickup
→preparing→running→finalising→complete|failed|cancelled|skipped), the rules for
which transitions are valid, and the rejection of out-of-table jumps. Those
belong in the new `src/forge/lifecycle/state_machine.py` and must be the **sole
caller** of any persistence write that mutates `builds.state`.

### 2.4 NATS adapters — `src/forge/adapters/nats/`

Already shipped:
- `pipeline_consumer.py` — durable pull consumer on `pipeline.build-queued.>`
- `pipeline_publisher.py` — eight outbound lifecycle subjects (build-started, build-paused, build-resumed, build-cancelled, build-completed, build-failed, stage-completed, queue-acknowledged)
- `synthetic_response_injector.py` — cancel→reject injection for paused builds
- `approval_publisher.py` / `approval_subscriber.py` — pause/resume protocol

**`/feature-plan` MUST NOT** add new adapters. The `forge queue` CLI publishes
through `pipeline_publisher`; reconciliation reads from `pipeline_consumer`.

### 2.5 Pipeline package wiring — `src/forge/pipeline/`

`stage_taxonomy.py` (StageClass enum + CONSTITUTIONAL_STAGES set),
`stage_ordering_guard.py` (per-stage prerequisite map within a single build),
`forward_propagation.py` / `forward_context_builder.py` (stage→stage context
threading), `constitutional_guard.py` (PR-review skip-veto), and the
`dispatchers/` (subprocess, specialist, autobuild_async) are all in flight from
002–007 and **must not** be touched by FEAT-FORGE-001.

---

## §3 — What `/feature-plan` MUST build (per-scenario gap)

Every row below is a build task or task cluster. "Reuse" cells reference the
modules from §2; "Build" cells point at the new module under
`src/forge/lifecycle/` or `src/forge/cli/`.

### Group A — Key Examples (6)

| Scenario | Coverage | Build (FEAT-FORGE-001) | Reuse |
|---|---|---|---|
| Queueing creates pending pickup | ❌ | `cli/queue.py` (argv, allowlist check, identifier validation, defaults application, write-then-publish, exit codes) + `lifecycle/persistence.py` (`record_pending_build`) | `config.models.ForgeConfig`, `adapters.nats.pipeline_publisher` |
| Lifecycle to completion | partial | `lifecycle/state_machine.py` transition table (preparing→running→finalising→complete) + `lifecycle/persistence.py` writes that *only* the state machine may invoke | `pipeline.supervisor.BuildState`, existing dispatch pipeline |
| `forge status` shows non-terminal + recent | ❌ | `cli/status.py` + `lifecycle/persistence.py.read_status()` (no NATS dependency — pure SQLite read) | none |
| `forge history --feature` lists prior attempts | ❌ | `cli/history.py` + `lifecycle/persistence.py.read_history(feature_id, limit)` | none |
| Defaults applied; CLI override wins | ❌ | `cli/queue.py` argv parsing → merges with `ForgeConfig` defaults; persisted onto build row | `config.models` |
| Status responsive while writer active (WAL) | ❌ | DDR-003 SQLite WAL configuration in `lifecycle/schema.sql` + `connect()` helper that opens reader connections in deferred mode | DDR-003 |

### Group B — Boundary Conditions (6)

| Scenario | Coverage | Build | Reuse |
|---|---|---|---|
| Turn budget ≥ 1 accepted | ❌ | Pydantic validator on the new `QueueConfig` sub-model in `config/models.py` | `config.models` |
| Turn budget ≤ 0 rejected | ❌ | same validator, rejection branch | same |
| `forge history --limit N` capped | ❌ | `cli/history.py` argument parsing + `persistence.read_history(limit=...)` SQL clamp | none |
| `forge history` default = 50 | ❌ | default in `cli/history.py` argparse | none |
| Duplicate `(feature_id, correlation_id)` refused | ❌ | UNIQUE INDEX in `schema.sql` on `(feature_id, correlation_id)` + `cli/queue.py` translates IntegrityError → exit code | DDR-003 |
| Full status view caps stage detail at 5 | ❌ | `cli/status.py --full` clamps stage tail to 5 (configurable later) | none |

### Group C — Negative Cases (7)

| Scenario | Coverage | Build | Reuse |
|---|---|---|---|
| Path outside allowlist refused | ❌ | `cli/queue.py` allowlist check against `PermissionsConfig.repo_allowlist` (extend `FilesystemPermissions` if needed) — fail before write, before publish | `config.models.PermissionsConfig` |
| Active in-flight duplicate refused | ❌ | `persistence.exists_active_build(feature_id) -> bool` queried by `cli/queue.py` before write | none |
| Skip on non-paused refused | ✅ executor logic exists | `cli/skip.py` thin wrapper → `CliSteeringHandler.handle_skip()` (handler already returns `SkipStatus.REFUSED` for non-paused) | `pipeline.cli_steering.CliSteeringHandler` |
| Cancel of unknown feature → not-found | ❌ | `persistence.find_active_or_recent(feature_id)` returns None → `cli/cancel.py` exits non-zero | none |
| Invalid feature description → preparing→failed | ❌ | preparation entry-point validates description; on ValidationError, state machine `transition(build, BuildState.FAILED, reason=...)` | `lifecycle/state_machine.py` |
| Hard-stop gate during running → running→failed | partial | gate evaluator already exists (FEAT-FORGE-004); state_machine must accept the running→failed transition with completion_time set | `gating/`, new state machine |
| Invalid lifecycle jump refused | ❌ | `lifecycle/state_machine.py.transition()` validates against the table; raises `InvalidTransitionError`; persistence write only after validation | new |

### Group D — Edge Cases (9)

| Scenario | Coverage | Build | Reuse |
|---|---|---|---|
| Crash during preparing → interrupted, redeliver | ❌ | `lifecycle/recovery.py.reconcile()` runs on startup: scan SQLite for non-terminal builds, mark INTERRUPTED, NACK any in-flight delivery so JetStream redelivers | `adapters.nats.pipeline_consumer` |
| Crash during running → interrupted, restart from preparing | ❌ | same recovery path; build re-enters lifecycle at PENDING_PICKUP and the next pull picks it up | same |
| Crash during finalising → interrupted with PR warning | ❌ | recovery emits warning record (PR may exist), operator reconciles via `forge history --reconcile` | new CLI flag |
| Paused-build crash → re-issue approval | ❌ | recovery detects PAUSED, re-publishes pending approval request via `approval_publisher` | `adapters.nats.approval_publisher` |
| Terminal-after-crash = no-op | ❌ | recovery filters terminal states; ACKs any pending delivery | same |
| Cancel paused → synthetic reject → cancelled | ✅ executor logic exists | `cli/cancel.py` thin wrapper → `CliSteeringHandler.handle_cancel()` (handler returns `CancelStatus.RESOLVED_AS_REJECT` for paused) | `pipeline.cli_steering`, `adapters.nats.synthetic_response_injector` |
| Skip flagged-stage → stage SKIPPED, resume running | ✅ executor logic exists | `cli/skip.py` wrapper → `CliSteeringHandler.handle_skip()` | `pipeline.cli_steering` |
| Sequential queue per-project | ❌ | `lifecycle/queue.py.next_build_to_pick(project)` returns None if any non-terminal build for that project exists; pull-consumer handler delegates to it | `adapters.nats.pipeline_consumer` |
| Watch mode refreshes | ❌ | `cli/status.py --watch` polls `persistence.read_status()` at 1Hz; exits on terminal | `lifecycle/persistence.py` |

### Group E — Security (2)

| Scenario | Coverage | Build | Reuse |
|---|---|---|---|
| Path-traversal `../` rejected | ❌ | `lifecycle/identifiers.py.validate_feature_id(s)` — regex allowlist `[A-Za-z0-9_-]+`, no `/`, no `\`, no `..` segment; called from `cli/queue.py` *before* any write or publish | none |
| Cancelling operator recorded distinctly | ❌ | `builds.originating_user` (already in DDR-003 schema), `approval_responses.responder` set by `synthetic_response_injector` from `cli/cancel.py --as <operator>` | DDR-003, `adapters.nats.synthetic_response_injector` |

### Group F — Concurrency (2)

| Scenario | Coverage | Build | Reuse |
|---|---|---|---|
| Two simultaneous queues both durable, ordered | ❌ | UNIQUE on `build_id` (UUID), `queued_at` timestamp ordering preserved; SQLite IMMEDIATE transactions for the queue write | DDR-003 |
| Concurrent reader sees consistent snapshot | ❌ | DDR-003 WAL configuration (already specced); reader connection in deferred mode | DDR-003 |

### Group G — Data Integrity (2)

| Scenario | Coverage | Build | Reuse |
|---|---|---|---|
| Terminal state ⇒ completion_time recorded | ❌ | `state_machine.transition()` invariant: terminal transitions must set `completed_at`; tested as a property on the transition table | new state machine |
| Write succeeded but publish failed → row remains pending pickup | ❌ | `cli/queue.py` orders write→publish; on publish failure, log + exit non-zero with explicit "pipeline not notified" message; row left as-is so a re-queue or operator action can recover | `adapters.nats.pipeline_publisher` |

### Group H — Integration Boundaries (1)

| Scenario | Coverage | Build | Reuse |
|---|---|---|---|
| Pipeline messaging unreachable → clean failure | ❌ | `cli/queue.py` catches `nats.errors.*` from publisher, formats messaging-layer error; status / history continue to function (they don't touch NATS) | `adapters.nats.pipeline_publisher` |

---

## §4 — Suggested module layout

```
src/forge/
├── cli/
│   ├── __init__.py
│   ├── main.py            # argparse entry point, dispatches to subcommands
│   ├── queue.py           # forge queue
│   ├── status.py          # forge status (incl. --watch, --full)
│   ├── history.py         # forge history
│   ├── cancel.py          # forge cancel  → CliSteeringHandler.handle_cancel
│   └── skip.py            # forge skip    → CliSteeringHandler.handle_skip
├── lifecycle/
│   ├── __init__.py
│   ├── schema.sql         # DDR-003 builds + stage_log + UNIQUE indices
│   ├── migrations.py      # apply schema; idempotent
│   ├── persistence.py     # SqliteLifecyclePersistence implements all
│   │                      # FEAT-FORGE-001 Protocol seams from cli_steering
│   ├── state_machine.py   # transition table + transition() guard
│   ├── queue.py           # sequential per-project picker
│   ├── recovery.py        # startup reconciliation pass
│   └── identifiers.py     # validate_feature_id, derive_build_id
└── pipeline/              # ← UNCHANGED (002–007 territory)
```

`pyproject.toml` adds:

```toml
[project.scripts]
forge = "forge.cli.main:main"
```

---

## §5 — What `/feature-plan` MUST NOT do

- **Do not** add `forge.config.QueueConfig` as a new module — extend
  `forge/config/models.py` in place.
- **Do not** redesign cancel / skip executor semantics — they live in
  `pipeline/cli_steering.py` and are FEAT-FORGE-007 territory.
- **Do not** add new NATS subjects, payloads, or adapters. All eight lifecycle
  subjects and the synthetic-response injector exist.
- **Do not** rebuild stage-ordering guards or forward-propagation — that is
  FEAT-FORGE-007 (within-build stage progression), distinct from FEAT-FORGE-001
  (across-build lifecycle).
- **Do not** re-spec or re-scope Group D edge cases that the executor already
  handles — emit thin CLI wrappers only.

---

## §6 — Acceptance for the gap closure

The gap is closed when:

1. `forge queue / status / history / cancel / skip` work end-to-end, exercised
   by all 34 BDD scenarios in
   [pipeline-state-machine-and-configuration.feature](../../../features/pipeline-state-machine-and-configuration/pipeline-state-machine-and-configuration.feature).
2. `lifecycle/state_machine.py` rejects every out-of-table transition with
   `InvalidTransitionError`, tested as a property.
3. `lifecycle/recovery.py` reconciles every non-terminal build state on
   restart (Group D crash scenarios).
4. `forge status` returns without NATS being reachable (Group H).
5. The four LES1 parity gates from the build plan §"Specialist-agent LES1
   Parity Gates" still pass on the production image — adding the CLI must
   not break the JetStream subscription or PORT/ARFS dispatch matrices.
6. The build plan's progress log row for Step 5 / FEAT-FORGE-001 flips from
   "absorbed" to "✅ complete" with the autobuild commit recorded.
Gap-context doc written to docs/research/ideas/forge-001-gap-context.md.

It maps every one of the 34 FEAT-FORGE-001 scenarios to either reuse (existing modules from 002–007) or build (new code under src/forge/lifecycle/ + src/forge/cli/), with explicit "MUST NOT" rules so the plan doesn't duplicate config models, executor logic, NATS adapters, or stage guards.

Key finding worth flagging: the executor logic for cancel/skip is already shipped in pipeline/cli_steering.py with all the right Protocol seams waiting for FEAT-FORGE-001's concrete persistence-backed implementations. So the plan should produce a much thinner FEAT-FORGE-001 than the spec implied — primarily one new package (src/forge/lifecycle/) covering SQLite persistence, the lifecycle state machine, sequential-queue picker, crash recovery, and identifier validation, plus a thin src/forge/cli/ package and a console_scripts entry-point edit.

Run it

guardkit feature-plan "Pipeline State Machine and Configuration" \
  --context forge/features/pipeline-state-machine-and-configuration/pipeline-state-machine-and-configuration_summary.md \
  --context forge/docs/research/ideas/forge-001-gap-context.md \
  --context forge/docs/design/contracts/API-cli.md \
  --context forge/docs/design/contracts/API-sqlite-schema.md \
  --context forge/docs/design/decisions/DDR-003-sqlite-schema-layout-wal.md
The same command block is recorded in §"How to use this document" of the gap-context doc itself, so the plan picks it up regardless of where it's invoked from.

After the plan completes, the next steps are: review the task breakdown (sanity-check that nothing under §5 "MUST NOT" leaked in), then autobuild FEAT-FORGE-001, then proceed to FEAT-FORGE-008.