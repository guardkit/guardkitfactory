richardwoollcott@promaxgb10-41b1:~/Projects/appmilla_github/forge$ GUARDKIT_LOG_LEVEL=DEBUG guardkit autobuild feature FEAT-DEA8 --verbose
INFO:guardkit.cli.autobuild:Starting feature orchestration: FEAT-DEA8 (max_turns=5, stop_on_failure=True, resume=False, fresh=False, refresh=False, sdk_timeout=None, enable_pre_loop=None, timeout_multiplier=None, max_parallel=None, max_parallel_strategy=static, bootstrap_failure_mode=None)
INFO:guardkit.orchestrator.feature_orchestrator:Raised file descriptor limit: 1024 → 4096
INFO:guardkit.orchestrator.feature_orchestrator:FeatureOrchestrator initialized: repo=/home/richardwoollcott/Projects/appmilla_github/forge, max_turns=5, stop_on_failure=True, resume=False, fresh=False, refresh=False, enable_pre_loop=None, enable_context=True, task_timeout=3000s
INFO:guardkit.orchestrator.feature_orchestrator:Starting feature orchestration for FEAT-DEA8
INFO:guardkit.orchestrator.feature_orchestrator:Phase 1 (Setup): Loading feature FEAT-DEA8
╭────────────────────────────────────────────── GuardKit AutoBuild ───────────────────────────────────────────────╮
│ AutoBuild Feature Orchestration                                                                                 │
│                                                                                                                 │
│ Feature: FEAT-DEA8                                                                                              │
│ Max Turns: 5                                                                                                    │
│ Stop on Failure: True                                                                                           │
│ Mode: Starting                                                                                                  │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
INFO:guardkit.orchestrator.feature_loader:Loading feature from /home/richardwoollcott/Projects/appmilla_github/forge/.guardkit/features/FEAT-DEA8.yaml
✓ Loaded feature: Wire the production pipeline orchestrator into forge serve
  Tasks: 11
  Waves: 5
✓ Feature validation passed
✓ Pre-flight validation passed
INFO:guardkit.cli.display:WaveProgressDisplay initialized: waves=5, verbose=True
✓ Created shared worktree: /home/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-DEA8
INFO:guardkit.orchestrator.feature_orchestrator:Copied task file to worktree: TASK-FW10-001-refactor-serve-daemon-seam-and-reconcile-on-boot.md
INFO:guardkit.orchestrator.feature_orchestrator:Copied task file to worktree: TASK-FW10-002-implement-autobuild-runner-async-subagent.md
INFO:guardkit.orchestrator.feature_orchestrator:Copied task file to worktree: TASK-FW10-003-forward-context-builder-factory.md
INFO:guardkit.orchestrator.feature_orchestrator:Copied task file to worktree: TASK-FW10-004-stage-log-recorder-binding.md
INFO:guardkit.orchestrator.feature_orchestrator:Copied task file to worktree: TASK-FW10-005-autobuild-state-initialiser-binding.md
INFO:guardkit.orchestrator.feature_orchestrator:Copied task file to worktree: TASK-FW10-006-pipeline-publisher-and-emitter-constructors.md
INFO:guardkit.orchestrator.feature_orchestrator:Copied task file to worktree: TASK-FW10-007-compose-pipeline-consumer-deps.md
INFO:guardkit.orchestrator.feature_orchestrator:Copied task file to worktree: TASK-FW10-008-wire-async-subagent-middleware-into-supervisor.md
INFO:guardkit.orchestrator.feature_orchestrator:Copied task file to worktree: TASK-FW10-009-validation-surface-and-build-failed-paths.md
INFO:guardkit.orchestrator.feature_orchestrator:Copied task file to worktree: TASK-FW10-010-pause-resume-publish-round-trip.md
INFO:guardkit.orchestrator.feature_orchestrator:Copied task file to worktree: TASK-FW10-011-end-to-end-lifecycle-integration-test.md
✓ Copied 11 task file(s) to worktree
ERROR:guardkit.orchestrator.feature_orchestrator:Bootstrap hard-fail (uv-sources require uv): /home/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-DEA8/pyproject.toml declares [tool.uv.sources] but `uv` is not on PATH. pip cannot honour these sibling-source overrides — installing would silently produce a broken environment. Fix by installing uv (https://astral.sh/uv) or removing the [tool.uv.sources] block from pyproject.toml.
✗ Bootstrap hard-fail: uv-sources require uv
/home/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-DEA8/pyproject.toml declares  but 
`uv` is not on PATH. pip cannot honour these sibling-source overrides — installing would silently produce a broken 
environment. Fix by installing uv (https://astral.sh/uv) or removing the  block from pyproject.toml.
ERROR:guardkit.orchestrator.feature_orchestrator:Feature orchestration failed: /home/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-DEA8/pyproject.toml declares [tool.uv.sources] but `uv` is not on PATH. pip cannot honour these sibling-source overrides — installing would silently produce a broken environment. Fix by installing uv (https://astral.sh/uv) or removing the [tool.uv.sources] block from pyproject.toml.
Traceback (most recent call last):
  File "/home/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/orchestrator/feature_orchestrator.py", line 1251, in _bootstrap_environment
    manifests = detector.detect()
                ^^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/orchestrator/environment_bootstrap.py", line 587, in detect
    results.extend(self._scan_directory(directory))
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/orchestrator/environment_bootstrap.py", line 667, in _scan_directory
    install_command = _resolve_python_pyproject_install_command(
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/orchestrator/environment_bootstrap.py", line 469, in _resolve_python_pyproject_install_command
    raise UvSourcesRequireUvError(
guardkit.orchestrator.environment_bootstrap.UvSourcesRequireUvError: /home/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-DEA8/pyproject.toml declares [tool.uv.sources] but `uv` is not on PATH. pip cannot honour these sibling-source overrides — installing would silently produce a broken environment. Fix by installing uv (https://astral.sh/uv) or removing the [tool.uv.sources] block from pyproject.toml.

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/home/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/orchestrator/feature_orchestrator.py", line 728, in orchestrate
    feature, worktree = self._setup_phase(feature_id, base_branch)
                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/orchestrator/feature_orchestrator.py", line 947, in _setup_phase
    return self._create_new_worktree(feature, feature_id, base_branch)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/orchestrator/feature_orchestrator.py", line 987, in _create_new_worktree
    self._bootstrap_environment(worktree)
  File "/home/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/orchestrator/feature_orchestrator.py", line 1333, in _bootstrap_environment
    raise FeatureOrchestrationError(str(e)) from e
guardkit.orchestrator.feature_orchestrator.FeatureOrchestrationError: /home/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-DEA8/pyproject.toml declares [tool.uv.sources] but `uv` is not on PATH. pip cannot honour these sibling-source overrides — installing would silently produce a broken environment. Fix by installing uv (https://astral.sh/uv) or removing the [tool.uv.sources] block from pyproject.toml.
Orchestration error: Failed to orchestrate feature FEAT-DEA8: 
/home/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-DEA8/pyproject.toml declares  but 
`uv` is not on PATH. pip cannot honour these sibling-source overrides — installing would silently produce a broken 
environment. Fix by installing uv (https://astral.sh/uv) or removing the  block from pyproject.toml.
ERROR:guardkit.cli.autobuild:Feature orchestration error: Failed to orchestrate feature FEAT-DEA8: /home/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-DEA8/pyproject.toml declares [tool.uv.sources] but `uv` is not on PATH. pip cannot honour these sibling-source overrides — installing would silently produce a broken environment. Fix by installing uv (https://astral.sh/uv) or removing the [tool.uv.sources] block from pyproject.toml.
richardwoollcott@promaxgb10-41b1:~/Projects/appmilla_github/forge$ 
