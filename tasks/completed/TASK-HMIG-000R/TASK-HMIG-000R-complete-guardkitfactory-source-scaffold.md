---
id: TASK-HMIG-000R
title: Complete guardkitfactory source scaffold (pyproject + lib/ + src/ + CI)
status: completed
task_type: implementation
created: 2026-05-19T20:30:00Z
updated: 2026-05-20T12:55:00Z
completed: 2026-05-20T12:55:00Z
previous_state: in_review
state_transition_reason: "All acceptance criteria met; quality gates passed; reviewed and finalized via /task-complete"
implementation_commit: 955be83
completed_location: tasks/completed/TASK-HMIG-000R/
organized_files:
  - TASK-HMIG-000R-complete-guardkitfactory-source-scaffold.md
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

## Implementation Summary

**Outcome:** Success. All 11 acceptance criteria met. Scaffold landed in commit
`955be83` (single non-merge commit on `main`, the falsifier for AC-011).

**Approach:**
- Direct mechanical implementation (no multi-agent ceremony — task was concrete
  template-copy + config-write with explicit, deterministic AC).
- `lib/factory_guards.py`, `lib/json_extractor.py`, `lib/retry_context.py`,
  `lib/session_logging.py` vendored verbatim from
  `guardkit/installer/core/templates/langchain-deepagents/lib/`. A minimal
  `lib/__init__.py` re-exports only the four modules needed (the template's
  full `__init__.py` imports 8+ modules we deliberately don't ship at this
  stage).
- `pyproject.toml` uses src layout with `tool.setuptools.package-dir = { "" =
  "src", "lib" = "lib" }` so both the `guardkitfactory` package (under `src/`)
  and the parallel `lib/` helpers tree are installable from one project root.
- `requires-python = ">=3.11"` open upper bound per the portfolio-Python-
  pinning standard; pins `deepagents>=0.5,<1` / `langgraph>=1,<2` /
  `langchain>=1.2,<2` / `langchain-core>=1.2,<2` per parent review §14.7.
- `HarnessAdapter` placeholder deliberately raises `NotImplementedError` so
  any accidental runtime use surfaces immediately rather than silently
  returning a no-op.

**Falsifier results (AC-008/falsifier line):**
- `uv sync --extra dev` → resolved deepagents 0.5.x, langgraph 1.2.0,
  langchain 1.3.1, langchain-core 1.4.0.
- `uv run pytest tests/ -v` → 8 passed in 0.02 s.
- `uv run ruff check src/ lib/ tests/` → clean (after a one-shot auto-fix of
  three style issues: `typing.Sequence` → `collections.abc.Sequence` per
  UP035, and import-block sorting in two files; vendored sources accept these
  modernisations).
- `uv run mypy src/` → no issues found in 2 source files.
- `python -c 'from guardkitfactory import HarnessAdapter'` → ok.

**Tests written:** 8 smoke tests in `tests/test_smoke.py` covering AC-002
(top-level package surface, `HarnessAdapter` exposed and raises),
AC-003 (harness subpackage imports), and AC-004..007 (each lib helper
importable and minimally exercised — e.g. `assert_no_system_messages` is
exercised against both a valid `user`-only message dict and a `system`-tainted
one to confirm the `ValueError` raise; `JsonExtractor.extract` is exercised
against a trivial `{"decision": "accept"}` to confirm strategy 1 is wired).
Coverage was not explicitly measured (smoke-only test surface; later harness
tasks will introduce behavioural tests and the 80%-line / 75%-branch
thresholds from the testing rule).

**Lessons learned:**
- The pre-existing `.gitignore` carried boilerplate `/lib/` and `/lib64/`
  rules from the Python `.gitignore` template, which silently excluded the
  vendored helpers despite a comment claiming "but not source code lib
  folders". Removing those two lines was a one-line side-quest but easy to
  miss — flagging it here so TASK-HMIG-001B and 002R don't trip over the
  same pattern if they add new top-level package directories. `.venv/` etc.
  already cover the virtualenv use case the original rules targeted.
- `tool.setuptools.package-dir = { "" = "src", "lib" = "lib" }` combined
  with an explicit `packages = ["guardkitfactory", "guardkitfactory.harness",
  "lib"]` is the cleanest way to ship a src-layout package alongside a
  parallel top-level `lib/` tree. `[tool.setuptools.packages.find]` with
  multiple `where` entries is also possible but more fragile.
- Ruff's `UP035` will flag any `typing.Sequence` import in vendored sources
  (the template still ships the deprecated form). Auto-fix lands the
  modernised import without behavioural change; future template-sync passes
  should expect to apply the same fix or land it upstream.

**Related work:**
- Parent review: TASK-REV-HMIG (lives in the `guardkit` repo).
- Follow-up: TASK-HMIG-001B (LangGraphHarness), TASK-HMIG-002R (pluggable
  backend), TASK-HMIG-007 (Player/Coach wiring) — all unblocked by this
  commit.
- Pin rationale: parent review §14.7; pinning standard:
  `guardkit/docs/guides/portfolio-python-pinning.md`.
