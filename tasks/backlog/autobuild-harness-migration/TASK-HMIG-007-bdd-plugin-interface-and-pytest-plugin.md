---
id: TASK-HMIG-007
title: Implement BDDPlugin interface + PytestBDDPlugin + C1-C6 contract tests
status: backlog
task_type: implementation
created: 2026-05-19T20:30:00Z
updated: 2026-05-19T20:30:00Z
priority: critical
complexity: 6
deadline: 2026-06-15
parent_review: TASK-REV-HMIG
feature_id: FEAT-HMIG
parent_feature: autobuild-harness-migration
wave: 2
parallel_group: 2B
implementation_mode: task-work
intensity: strict
effort_hours: 8
depends_on:
  - TASK-HMIG-000R   # scaffold
cross_repo:
  notes: |
    Implements the BDDPlugin interface in guardkitfactory per parent review §6.
    guardkit/orchestrator/quality_gates/bdd_runner.py will be refactored to a thin shim
    that delegates to `guardkitfactory.bdd.loader.discover(...)` — that shim refactor
    is in scope for TASK-HMIG-006 (frozen-path touch on bdd_runner.py). This task
    builds the substrate; the shim hook-up is on the guardkit side.
falsifier: "Contract tests C1 (zero-cardinality → not green), C2 (per-task glue naming + sanitisation), C3 (parallel race produces disjoint scenario sets), C4 (identity-bounded resolution on scenario file rename), C5 (timeout produces structured BDDRunResult.errors=['timeout']), C6 (undefined-step → scenarios_errored > 0) ALL pass for PytestBDDPlugin against synthetic fixtures. The loader refuses to register any plugin that fails any contract."
tags:
  - autobuild
  - bdd
  - plugin
  - langgraph-migration
---

# Task: Implement BDDPlugin interface + PytestBDDPlugin

## Description

Per parent review §6, this task codifies "the BDD oracle" as a Python
interface decoupled from pytest-bdd, JUnit-XML parsing, the per-task marker
filter, the `GUARDKIT_BDD_TASK_ID` env-var contract, and the worktree-path
conventions.

Six contract tests (C1-C6) lift the §5 failure-pattern guards into the type
system. The plugin loader refuses to register any plugin that fails any
contract — making the failure-pattern guards non-negotiable.

This task ships the interface + the Python implementation (`PytestBDDPlugin`).
Other-stack plugins (Reqnroll for .NET, Cucumber.js for TypeScript) are
explicitly OUT of scope for the 27-day window — stub plugins are added that
return `None` from `discover()` so the loader can still iterate them.

## Acceptance Criteria

### Interface

- [ ] AC-001: New module `src/guardkitfactory/bdd/__init__.py`,
      `bdd/plugin.py`, `bdd/loader.py`, `bdd/plugins/__init__.py`.
- [ ] AC-002: `bdd/plugin.py` defines (per parent review §6.1):
  - `StackProfile` dataclass (`language`, `test_framework`, `package_manager`, `project_root`, `extras`)
  - `Scenario` dataclass (`feature_path`, `name`, `tags`, `task_id`)
  - `BDDRunResult` dataclass with `scenarios_attempted / passed / failed / skipped / errored / duration_seconds / raw_report_path / discoveries / errors` + the `is_zero_cardinality` property
  - `ContractTestResult` dataclass
  - `BDDPlugin(ABC)` with `discover(cls, stack, worktree) -> Optional[BDDPlugin]`, `preflight(self, task_id, worktree) -> bool`, `run(self, scenarios, task_id, worktree, *, timeout_seconds) -> BDDRunResult`, `contract_tests(self) -> list[ContractTestResult]`.

### Loader

- [ ] AC-003: `bdd/loader.py` provides:
  - `register(plugin_cls)` decorator that runs `contract_tests()` at registration time and refuses any plugin with failing contracts.
  - `discover(stack, worktree) -> BDDPlugin | None` returns the first plugin whose `discover()` matches.

### PytestBDDPlugin

- [ ] AC-004: `bdd/plugins/pytest_bdd_plugin.py` implements `PytestBDDPlugin`
      per parent review §6.3.
- [ ] AC-005: `discover()` matches when `stack.language == "python"` AND
      `stack.test_framework == "pytest"` AND `pytest-bdd` is importable in
      the worktree's venv.
- [ ] AC-006: `preflight()` verifies per-task glue file (`test_<slug>__<TASK_ID>.py`)
      naming convention (sanitisation per `.claude/rules/bdd-per-task-glue.md`)
      and `GUARDKIT_BDD_TASK_ID` env var honour.
- [ ] AC-007: `run()` subprocesses pytest with `-m task_<TASK_ID>` marker
      filter and `--junitxml=<path>`. Parses the JUnit XML to populate
      `BDDRunResult`. On timeout, returns a structured `BDDRunResult` with
      `errors=["timeout"]` (per contract C5) — does NOT raise.
- [ ] AC-008: `contract_tests()` exercises C1-C6 against synthetic fixtures
      (use `tmp_path` and a minimal `.feature` + per-task glue setup):
  - **C1** zero-cardinality → `is_zero_cardinality=True`, not approval
  - **C2** per-task glue naming + sanitisation (hyphens → underscores)
  - **C3** parallel-task glue race resolved (two tasks → disjoint scenario sets)
  - **C4** identity-bounded resolution on scenario-file rename
  - **C5** timeout → structured `BDDRunResult.errors=["timeout"]`
  - **C6** undefined-step → `scenarios_errored > 0`, not silent zero

### Stub plugins

- [ ] AC-009: `bdd/plugins/reqnroll_plugin.py` and
      `bdd/plugins/cucumber_js_plugin.py` exist as stubs — `discover()`
      returns `None`, `contract_tests()` returns an empty list. Comments
      explain they are placeholders for follow-on tasks.

### Wiring

- [ ] AC-010: `src/guardkitfactory/__init__.py` exposes `BDDPlugin`,
      `BDDRunResult`, `StackProfile`, `Scenario`, and the loader's `discover`
      function as top-level symbols.
- [ ] AC-011: Tests at `tests/bdd/test_pytest_bdd_plugin_contracts.py` exercise C1-C6 explicitly.
- [ ] AC-012: Tests at `tests/bdd/test_loader.py` verify registration refuses contract-failing plugins.

## Implementation Notes

- Six contract tests are non-trivial to write. Don't skimp — each maps to a
  specific historical failure (parent review §5 patterns 2 + 3 + 4 + 5). If
  any contract is hard to honour (e.g., C4 identity-bounded resolution at the
  plugin level), document the rationale and consider lifting the guard to
  the orchestrator-side wrapper around `plugin.run()` (parent review §9 R-07).
- The `run()` method can either subprocess pytest directly OR delegate to
  the agent's `execute` tool (TASK-HMIG-002R's backend). For initial
  implementation, subprocess directly — it's simpler and avoids coupling to
  the harness lifecycle. If load testing later shows the subprocess is
  costly, refactor to use the backend's `execute`.
- Reqnroll + Cucumber-JS plugins land in separate post-cutover tasks when a
  project requiring them exists. The stub-returning-None pattern keeps the
  loader iteration safe.

## References

- Parent review §6 — full plugin interface specification + worked examples
- Parent review §5.3, §5.5 — Patterns 2 + 4 (`bdd-missing-glue-and-collection-zero`,
  `coach-gate-short-circuit-cascades`) that contract tests guard against
- `~/Projects/appmilla_github/guardkit/.claude/rules/bdd-per-task-glue.md` — per-task glue convention
- `~/Projects/appmilla_github/guardkit/.claude/rules/absence-of-failure-is-not-success.md` — zero-cardinality precondition
- `~/Projects/appmilla_github/guardkit/.claude/rules/path-string-mismatch-is-not-dishonesty.md` — identity-bounded resolution (C4)

## Notes

The six contract tests are the keystone of the BDD plugin architecture. If
a future plugin author tries to register a non-compliant plugin (e.g., a
plugin that silently returns success on zero-cardinality), the loader
refuses registration with a clear error. This is the type-system-level guard
that makes failure-pattern recurrence structurally hard.
