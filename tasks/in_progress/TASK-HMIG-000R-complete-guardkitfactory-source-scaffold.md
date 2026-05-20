---
id: TASK-HMIG-000R
title: Complete guardkitfactory source scaffold (pyproject + lib/ + src/ + CI)
status: in_progress
task_type: implementation
created: 2026-05-19T20:30:00Z
updated: 2026-05-20T12:30:00Z
previous_state: backlog
state_transition_reason: "Started via /task-work"
priority: critical
complexity: 3
deadline: 2026-06-15
parent_review: TASK-REV-HMIG
feature_id: FEAT-HMIG
parent_feature: autobuild-harness-migration
wave: 1
parallel_group: 1A
implementation_mode: task-work
intensity: standard
effort_hours: 4
depends_on: []
cross_repo:
  notes: Pure guardkitfactory-side work. The operator has already run `guardkit init langchain-deepagents` which set up .claude/ + tasks/. This task completes the source scaffold (pyproject, lib/, src/, tests/, CI) that init did not render.
falsifier: "From a clean checkout of guardkitfactory: `uv sync && pytest tests/` succeeds. `python -c 'from guardkitfactory import HarnessAdapter'` imports without error (HarnessAdapter is a placeholder/re-export at this stage). Template-provided lib/ helpers (factory_guards, json_extractor, retry_context, session_logging) are all present and importable."
tags:
  - autobuild
  - guardkitfactory-bootstrap
  - langgraph-migration
---

# Task: Complete guardkitfactory source scaffold

## Description

The operator has run `guardkit init langchain-deepagents` which set up the
GuardKit workflow surface (`.claude/`, `tasks/`). This task completes the
Python source scaffold that the init step did not render — pyproject.toml,
`lib/` helpers, `src/guardkitfactory/` package layout, basic tests, and CI
config.

After this task lands, `guardkitfactory` is a working Python package that
guardkit can install (`pip install -e ../guardkitfactory`) and import from.
It will not yet contain the LangGraphHarness logic (that's TASK-HMIG-001B)
or the backend configuration (TASK-HMIG-002R) — those build on top of this
scaffold.

## Acceptance Criteria

- [ ] AC-001: `pyproject.toml` at repo root configured per
      [portfolio-Python-pinning standard](../../../../guardkit/docs/guides/portfolio-python-pinning.md):
  - `requires-python = ">=3.11"`
  - Pin `deepagents>=0.5,<1`, `langgraph>=1,<2`, `langchain>=1.2,<2`, `langchain-core>=1.2,<2`
  - Package name: `guardkitfactory`, version `0.1.0`
  - Project layout: `src/guardkitfactory/`
  - Dev dependencies: `pytest`, `ruff`, `mypy`
- [ ] AC-002: `src/guardkitfactory/__init__.py` exposes a stable public API
      surface (placeholder `HarnessAdapter` re-export; concrete classes added
      in TASK-HMIG-001B / TASK-HMIG-002R).
- [ ] AC-003: `src/guardkitfactory/harness/__init__.py` package skeleton (will
      receive `LangGraphHarness` in TASK-HMIG-001B).
- [ ] AC-004: `lib/factory_guards.py` rendered from the template — at minimum
      providing `assert_no_system_messages()` (the TASK-REV-R2A1 guard) and
      `assert_tool_inventory()`. If `guardkit init` didn't render these, copy
      them from `~/Projects/appmilla_github/guardkit/installer/core/templates/langchain-deepagents/lib/factory_guards.py`.
- [ ] AC-005: `lib/json_extractor.py` rendered: 5-strategy JSON-extraction
      cascade (for parsing Coach LLM output). Source: same template path.
- [ ] AC-006: `lib/retry_context.py` rendered: retry-only-context construction
      pattern. Source: same template path.
- [ ] AC-007: `lib/session_logging.py` rendered: per-run diagnostic JSON +
      logging bootstrap. Source: same template path.
- [ ] AC-008: `tests/test_smoke.py` proves `pip install -e .` + import works
      and the lib helpers can be imported.
- [ ] AC-009: `.github/workflows/ci.yml` (or `.gitlab-ci.yml`) — minimal CI:
      `uv sync && pytest tests/ && ruff check src/ && mypy src/`. If
      operator's preferred CI host is different, adapt accordingly.
- [ ] AC-010: `README.md` documents the bootstrap, the cross-repo dependency,
      and a "How to develop alongside guardkit" section explaining the
      editable-install pattern.
- [ ] AC-011: First non-merge commit on `main` branch containing all of the
      above. The commit message references TASK-REV-HMIG and TASK-HMIG-000R.

## Implementation Notes

- The template lives at
  `~/Projects/appmilla_github/guardkit/installer/core/templates/langchain-deepagents/`.
  Inspect that directory to confirm what each `lib/*.py` file does and copy
  the parts needed.
- If a template file references guardkit-internal modules (it shouldn't, but
  worth checking), strip those imports. `guardkitfactory` must be
  independently installable.
- Do NOT include the LangGraphHarness implementation in this task — that's
  TASK-HMIG-001B's job. This task is the *scaffold* only.
- Pin choice rationale: `deepagents>=0.5` is the version that ships the
  pluggable-backend protocol (per `deepagents v0.5.0` changelog cited in
  the parent review §14.7); `<1` because backwards-compat is well-supported
  in 0.5.x and a 1.0 release may shift APIs.

## References

- Parent review §14.8 — Revision 2 explaining the new-repo decision
- Parent review §7.1 Wave 1 — task list including TASK-HMIG-000R
- `~/Projects/appmilla_github/guardkit/docs/guides/portfolio-python-pinning.md` — pinning standard
- Template source: `~/Projects/appmilla_github/guardkit/installer/core/templates/langchain-deepagents/`

## Notes

This task is intentionally narrow (~4h). It is the *substrate* on which the
real LangGraphHarness work (001B + 002R + 007) sits. If the scaffold has bugs,
those bugs will surface as TASK-HMIG-001B fails to import — surface those
quickly rather than blocking on a perfect scaffold.
