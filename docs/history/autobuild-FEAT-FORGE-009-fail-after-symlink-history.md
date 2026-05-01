richardwoollcott@Richards-MBP forge % GUARDKIT_LOG_LEVEL=DEBUG guardkit autobuild feature FEAT-FORGE-009 --verbose --fresh
INFO:guardkit.cli.autobuild:Starting feature orchestration: FEAT-FORGE-009 (max_turns=5, stop_on_failure=True, resume=False, fresh=True, refresh=False, sdk_timeout=None, enable_pre_loop=None, timeout_multiplier=None, max_parallel=None, max_parallel_strategy=static, bootstrap_failure_mode=None)
INFO:guardkit.orchestrator.feature_orchestrator:Raised file descriptor limit: 256 → 4096
INFO:guardkit.orchestrator.feature_orchestrator:FeatureOrchestrator initialized: repo=/Users/richardwoollcott/Projects/appmilla_github/forge, max_turns=5, stop_on_failure=True, resume=False, fresh=True, refresh=False, enable_pre_loop=None, enable_context=True, task_timeout=3000s
INFO:guardkit.orchestrator.feature_orchestrator:Starting feature orchestration for FEAT-FORGE-009
INFO:guardkit.orchestrator.feature_orchestrator:Phase 1 (Setup): Loading feature FEAT-FORGE-009
╭─────────────────────────────────────────────────────────────────────────────── GuardKit AutoBuild ───────────────────────────────────────────────────────────────────────────────╮
│ AutoBuild Feature Orchestration                                                                                                                                                  │
│                                                                                                                                                                                  │
│ Feature: FEAT-FORGE-009                                                                                                                                                          │
│ Max Turns: 5                                                                                                                                                                     │
│ Stop on Failure: True                                                                                                                                                            │
│ Mode: Fresh Start                                                                                                                                                                │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
INFO:guardkit.orchestrator.feature_loader:Loading feature from /Users/richardwoollcott/Projects/appmilla_github/forge/.guardkit/features/FEAT-FORGE-009.yaml
✓ Loaded feature: Forge Production Image
  Tasks: 8
  Waves: 4
✓ Feature validation passed
✓ Pre-flight validation passed
INFO:guardkit.cli.display:WaveProgressDisplay initialized: waves=4, verbose=True
✓ Created shared worktree: /Users/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-FORGE-009
INFO:guardkit.orchestrator.feature_orchestrator:Copied task file to worktree: TASK-F009-001-add-forge-serve-skeleton.md
INFO:guardkit.orchestrator.feature_orchestrator:Copied task file to worktree: TASK-F009-002-add-dockerfile-skeleton.md
INFO:guardkit.orchestrator.feature_orchestrator:Copied task file to worktree: TASK-F009-003-implement-forge-serve-daemon.md
INFO:guardkit.orchestrator.feature_orchestrator:Copied task file to worktree: TASK-F009-004-implement-healthz-endpoint.md
INFO:guardkit.orchestrator.feature_orchestrator:Copied task file to worktree: TASK-F009-005-implement-dockerfile-install-layer.md
INFO:guardkit.orchestrator.feature_orchestrator:Copied task file to worktree: TASK-F009-006-add-bdd-bindings-and-integration-tests.md
INFO:guardkit.orchestrator.feature_orchestrator:Copied task file to worktree: TASK-F009-007-add-github-actions-image-workflow.md
INFO:guardkit.orchestrator.feature_orchestrator:Copied task file to worktree: TASK-F009-008-fold-runbook-section6-and-history.md
✓ Copied 8 task file(s) to worktree
⚙ Bootstrapping environment: python
INFO:guardkit.orchestrator.feature_orchestrator:Bootstrap failure-mode smart default = 'block' (manifests declaring requires-python: /Users/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-FORGE-009/pyproject.toml)
INFO:guardkit.orchestrator.environment_bootstrap:Running install for python (pyproject.toml): uv pip install -e .
WARNING:guardkit.orchestrator.environment_bootstrap:Install failed for python (pyproject.toml) with exit code 2:
stderr: Using Python 3.14.2 environment at: /Users/richardwoollcott/Projects/appmilla_github/forge/.venv
error: Distribution not found at: file:///Users/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/nats-core

stdout: (empty)
⚠ Environment bootstrap partial: 0/1 succeeded
ERROR:guardkit.orchestrator.feature_orchestrator:Feature orchestration failed: Bootstrap hard-fail: 0/1 install(s) succeeded for essential stack(s): python.
Manifest: /Users/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-FORGE-009/pyproject.toml
Manifest requires-python: >=3.11
Install stderr (tail):
Using Python 3.14.2 environment at: /Users/richardwoollcott/Projects/appmilla_github/forge/.venv
error: Distribution not found at: file:///Users/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/nats-core
Hint: set `bootstrap_failure_mode: warn` in .guardkit/config.yaml (or pass `--bootstrap-failure-mode warn`) to downgrade this to a non-blocking warning.
Traceback (most recent call last):
  File "/Users/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/orchestrator/feature_orchestrator.py", line 728, in orchestrate
    feature, worktree = self._setup_phase(feature_id, base_branch)
                        ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/orchestrator/feature_orchestrator.py", line 870, in _setup_phase
    return self._create_new_worktree(feature, feature_id, base_branch)
           ~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/orchestrator/feature_orchestrator.py", line 987, in _create_new_worktree
    self._bootstrap_environment(worktree)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^
  File "/Users/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/orchestrator/feature_orchestrator.py", line 1291, in _bootstrap_environment
    self._maybe_hardfail_bootstrap(result)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "/Users/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/orchestrator/feature_orchestrator.py", line 1416, in _maybe_hardfail_bootstrap
    raise FeatureOrchestrationError(
        _format_bootstrap_hardfail_message(result, essential_stacks)
    )
guardkit.orchestrator.feature_orchestrator.FeatureOrchestrationError: Bootstrap hard-fail: 0/1 install(s) succeeded for essential stack(s): python.
Manifest: /Users/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-FORGE-009/pyproject.toml
Manifest requires-python: >=3.11
Install stderr (tail):
Using Python 3.14.2 environment at: /Users/richardwoollcott/Projects/appmilla_github/forge/.venv
error: Distribution not found at: file:///Users/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/nats-core
Hint: set `bootstrap_failure_mode: warn` in .guardkit/config.yaml (or pass `--bootstrap-failure-mode warn`) to downgrade this to a non-blocking warning.
Orchestration error: Failed to orchestrate feature FEAT-FORGE-009: Bootstrap hard-fail: 0/1 install(s) succeeded for essential stack(s): python.
Manifest: /Users/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-FORGE-009/pyproject.toml
Manifest requires-python: >=3.11
Install stderr (tail):
Using Python 3.14.2 environment at: /Users/richardwoollcott/Projects/appmilla_github/forge/.venv
error: Distribution not found at: file:///Users/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/nats-core
Hint: set `bootstrap_failure_mode: warn` in .guardkit/config.yaml (or pass `--bootstrap-failure-mode warn`) to downgrade this to a non-blocking warning.
ERROR:guardkit.cli.autobuild:Feature orchestration error: Failed to orchestrate feature FEAT-FORGE-009: Bootstrap hard-fail: 0/1 install(s) succeeded for essential stack(s): python.
Manifest: /Users/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-FORGE-009/pyproject.toml
Manifest requires-python: >=3.11
Install stderr (tail):
Using Python 3.14.2 environment at: /Users/richardwoollcott/Projects/appmilla_github/forge/.venv
error: Distribution not found at: file:///Users/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/nats-core
Hint: set `bootstrap_failure_mode: warn` in .guardkit/config.yaml (or pass `--bootstrap-failure-mode warn`) to downgrade this to a non-blocking warning.
richardwoollcott@Richards-MBP forge %