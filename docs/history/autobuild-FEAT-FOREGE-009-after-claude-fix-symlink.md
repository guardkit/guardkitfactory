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
ERROR:guardkit.orchestrator.feature_orchestrator:Feature orchestration failed: Failed to create worktree for FEAT-FORGE-009: Failed to create worktree for FEAT-FORGE-009: branch 'autobuild/FEAT-FORGE-009' already exists and automatic cleanup failed.
Manual cleanup steps:
  1. git worktree remove .guardkit/worktrees/FEAT-FORGE-009 --force
  2. git branch -D autobuild/FEAT-FORGE-009
  3. Retry the operation
Traceback (most recent call last):
  File "/Users/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/worktrees/manager.py", line 231, in _run_git
    return self.executor.run(
           ~~~~~~~~~~~~~~~~~^
        full_args,
        ^^^^^^^^^^
    ...<3 lines>...
        text=True,
        ^^^^^^^^^^
    )
    ^
  File "/Users/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/worktrees/manager.py", line 102, in run
    return subprocess.run(
           ~~~~~~~~~~~~~~^
        args,
        ^^^^^
    ...<3 lines>...
        text=text,
        ^^^^^^^^^^
    )
    ^
  File "/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/subprocess.py", line 577, in run
    raise CalledProcessError(retcode, process.args,
                             output=stdout, stderr=stderr)
subprocess.CalledProcessError: Command '['git', 'worktree', 'add', '/Users/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-FORGE-009', '-b', 'autobuild/FEAT-FORGE-009', 'main']' returned non-zero exit status 255.

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/worktrees/manager.py", line 401, in create
    self._run_git(worktree_add_cmd)
    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^
  File "/Users/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/worktrees/manager.py", line 239, in _run_git
    raise WorktreeError(
    ...<3 lines>...
    )
guardkit.worktrees.manager.WorktreeError: Git command failed: git worktree add /Users/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-FORGE-009 -b autobuild/FEAT-FORGE-009 main
Exit code: 255
Stderr: Preparing worktree (new branch 'autobuild/FEAT-FORGE-009')
fatal: a branch named 'autobuild/FEAT-FORGE-009' already exists


During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/worktrees/manager.py", line 231, in _run_git
    return self.executor.run(
           ~~~~~~~~~~~~~~~~~^
        full_args,
        ^^^^^^^^^^
    ...<3 lines>...
        text=True,
        ^^^^^^^^^^
    )
    ^
  File "/Users/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/worktrees/manager.py", line 102, in run
    return subprocess.run(
           ~~~~~~~~~~~~~~^
        args,
        ^^^^^
    ...<3 lines>...
        text=text,
        ^^^^^^^^^^
    )
    ^
  File "/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/subprocess.py", line 577, in run
    raise CalledProcessError(retcode, process.args,
                             output=stdout, stderr=stderr)
subprocess.CalledProcessError: Command '['git', 'branch', '-D', 'autobuild/FEAT-FORGE-009']' returned non-zero exit status 1.

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/worktrees/manager.py", line 407, in create
    self._run_git(["branch", "-D", branch_name])
    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/worktrees/manager.py", line 239, in _run_git
    raise WorktreeError(
    ...<3 lines>...
    )
guardkit.worktrees.manager.WorktreeError: Git command failed: git branch -D autobuild/FEAT-FORGE-009
Exit code: 1
Stderr: error: cannot delete branch 'autobuild/FEAT-FORGE-009' used by worktree at '/Users/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-FORGE-009'


During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/orchestrator/feature_orchestrator.py", line 973, in _create_new_worktree
    worktree = self._worktree_manager.create(
        task_id=feature_id,
        base_branch=base_branch,
    )
  File "/Users/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/worktrees/manager.py", line 410, in create
    raise WorktreeCreationError(
    ...<6 lines>...
    )
guardkit.worktrees.manager.WorktreeCreationError: Failed to create worktree for FEAT-FORGE-009: branch 'autobuild/FEAT-FORGE-009' already exists and automatic cleanup failed.
Manual cleanup steps:
  1. git worktree remove .guardkit/worktrees/FEAT-FORGE-009 --force
  2. git branch -D autobuild/FEAT-FORGE-009
  3. Retry the operation

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/Users/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/orchestrator/feature_orchestrator.py", line 728, in orchestrate
    feature, worktree = self._setup_phase(feature_id, base_branch)
                        ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/orchestrator/feature_orchestrator.py", line 870, in _setup_phase
    return self._create_new_worktree(feature, feature_id, base_branch)
           ~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/richardwoollcott/Projects/appmilla_github/guardkit/guardkit/orchestrator/feature_orchestrator.py", line 979, in _create_new_worktree
    raise FeatureOrchestrationError(
        f"Failed to create worktree for {feature_id}: {e}"
    ) from e
guardkit.orchestrator.feature_orchestrator.FeatureOrchestrationError: Failed to create worktree for FEAT-FORGE-009: Failed to create worktree for FEAT-FORGE-009: branch 'autobuild/FEAT-FORGE-009' already exists and automatic cleanup failed.
Manual cleanup steps:
  1. git worktree remove .guardkit/worktrees/FEAT-FORGE-009 --force
  2. git branch -D autobuild/FEAT-FORGE-009
  3. Retry the operation
Orchestration error: Failed to orchestrate feature FEAT-FORGE-009: Failed to create worktree for FEAT-FORGE-009: Failed to create worktree for FEAT-FORGE-009: branch
'autobuild/FEAT-FORGE-009' already exists and automatic cleanup failed.
Manual cleanup steps:
  1. git worktree remove .guardkit/worktrees/FEAT-FORGE-009 --force
  2. git branch -D autobuild/FEAT-FORGE-009
  3. Retry the operation
ERROR:guardkit.cli.autobuild:Feature orchestration error: Failed to orchestrate feature FEAT-FORGE-009: Failed to create worktree for FEAT-FORGE-009: Failed to create worktree for FEAT-FORGE-009: branch 'autobuild/FEAT-FORGE-009' already exists and automatic cleanup failed.
Manual cleanup steps:
  1. git worktree remove .guardkit/worktrees/FEAT-FORGE-009 --force
  2. git branch -D autobuild/FEAT-FORGE-009
  3. Retry the operation
richardwoollcott@Richards-MBP forge %