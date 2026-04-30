# RUNBOOK — FEAT-FORGE-009 bootstrap prep (Run 1 → Run 2)

**Task**: TASK-FIX-F09A1 (Layer 1 of TASK-REV-F09A's layered fix)
**Date**: 2026-04-30
**Scope**: Forge-only operator pre-step that unblocks `guardkit autobuild feature FEAT-FORGE-009`. No `uv` install, no guardkit changes, no nats-core changes.

---

## Why this pre-step exists

GuardKit's `environment_bootstrap` is hardcoded to `pip install -e .`
(`environment_bootstrap.py:546,557`), which silently ignores
`[tool.uv.sources]` in `forge/pyproject.toml`. PyPI has no `nats-core` wheel
satisfying `>=0.3.0,<0.4` on Python 3.11/3.12 (only `0.0.0` is published
under that constraint; `0.1.0`/`0.2.0` require Python `>=3.13`), so
bootstrap hard-fails at Phase 1 (Setup) before any task runs.

The fix landed in this task is intentionally forge-only:

1. **`.guardkit/preflight.sh`** — seeds the worktree's venv with `nats-core`
   from the sibling source repo (`appmilla_github/nats-core`) via plain
   `pip`. Once `nats-core` is satisfied in the venv, the subsequent
   `pip install -e .` short-circuits the unsatisfiable PyPI lookup. (Plain
   `pip` is sufficient — see TASK-REV-F09A Reproduction B.)
2. **`click` + `rich` added to `[project].dependencies`** — both are
   imported by `forge.cli.{main,status,skip,history,queue,cancel}` but were
   not pulled transitively, so `forge serve --help` (the FEAT-FORGE-009
   smoke gate per `.guardkit/features/FEAT-FORGE-009.yaml:116`) failed with
   `ModuleNotFoundError` even after bootstrap succeeded.

This pre-step is required **only until** one of:

- **TASK-FIX-F09A2** lands a durable fix in guardkit (teach
  `environment_bootstrap` to honour `[tool.uv.sources]` when `uv` is on
  PATH), **or**
- **TASK-FIX-F0E6b** removes the need for `[tool.uv.sources]` entirely by
  republishing a working `nats-core` wheel.

When either lands, this runbook (and the `.guardkit/preflight.sh` script)
can be retired.

---

## Operator pre-step (required before every Run 2 attempt)

```bash
cd ~/Projects/appmilla_github/forge

# 1. Seed nats-core into the worktree venv
./.guardkit/preflight.sh .guardkit/worktrees/FEAT-FORGE-009

# 2. Run autobuild
guardkit autobuild feature FEAT-FORGE-009 --verbose --fresh
```

The script is **idempotent** — re-running it on an existing venv is safe
(pip skips already-satisfied packages, and the symlink check is a no-op).

### What the script does

1. Resolves the worktree path (default: `pwd`).
2. Resolves the sibling `nats-core` repo:
   - `$FORGE_NATS_CORE_PATH` env var if set, otherwise
   - `<worktree>/../../../../nats-core` (canonical sibling layout).
3. Creates `<worktree>/.guardkit/venv/` with `python3 -m venv` if missing.
4. Runs `<venv>/bin/python -m pip install -e <abs-nats-core-path>`.
5. Places a defensive symlink at
   `<worktree>/.guardkit/worktrees/nats-core` → resolved sibling path
   (future-proofs against the uv switch landing in TASK-FIX-F09A2 — uv
   resolves `[tool.uv.sources] nats-core = "../nats-core"` relative to
   `pyproject.toml`, which from a worktree resolves to
   `.guardkit/worktrees/nats-core`).

### Override examples

```bash
# Custom nats-core location
FORGE_NATS_CORE_PATH=/abs/path/to/nats-core \
    ./.guardkit/preflight.sh .guardkit/worktrees/FEAT-FORGE-009

# Run from inside the worktree
cd .guardkit/worktrees/FEAT-FORGE-009
../../../.guardkit/preflight.sh
```

---

## Run 1 failure → Run 2 outcome

### Run 1 (failed) — 2026-04-30

Command: `GUARDKIT_LOG_LEVEL=DEBUG guardkit autobuild feature FEAT-FORGE-009 --verbose`

Outcome: **bootstrap hard-fail in Phase 1 (Setup)**. Full transcript at
`docs/history/autobuild-FEAT-FORGE-009-failure-run-1-history.md`.

Key error (from the transcript):

```
INFO: pip is looking at multiple versions of forge ...
ERROR: Ignored the following versions that require a different python version:
       0.1.0 Requires-Python >=3.13; 0.2.0 Requires-Python >=3.13
ERROR: Could not find a version that satisfies the requirement
       nats-core<0.4,>=0.3.0 (from forge) (from versions: 0.0.0)
ERROR: No matching distribution found for nats-core<0.4,>=0.3.0
```

Root cause confirmed empirically: `pip` ignores `[tool.uv.sources]`. See
TASK-REV-F09A Reproductions A & B for the exact reproduction + fix chain.

### Local smoke (this task) — 2026-04-30

Performed against a fresh venv at
`.guardkit/worktrees/FEAT-FORGE-009/.guardkit/venv-smoke/` to avoid
disturbing the existing Run-1 venv. Sequence:

```bash
# Fresh venv
python3 -m venv /tmp/forge-smoke-venv

# Step 1 — pip install -e . WITHOUT preflight (expected to fail)
/tmp/forge-smoke-venv/bin/python -m pip install -e .
#   → ERROR: No matching distribution found for nats-core<0.4,>=0.3.0
#     (matches Run 1 byte-for-byte)

# Step 2 — preflight (seeds nats-core)
FORGE_NATS_CORE_PATH=~/Projects/appmilla_github/nats-core \
    ./.guardkit/preflight.sh /tmp/forge-smoke-venv-worktree
# (or run against the worktree directly:)
./.guardkit/preflight.sh .guardkit/worktrees/FEAT-FORGE-009

# Step 3 — pip install -e . AFTER preflight (expected to succeed)
.guardkit/worktrees/FEAT-FORGE-009/.guardkit/venv/bin/python -m pip install -e .

# Step 4 — smoke gate
.guardkit/worktrees/FEAT-FORGE-009/.guardkit/venv/bin/forge --help
.guardkit/worktrees/FEAT-FORGE-009/.guardkit/venv/bin/forge serve --help
```

The exact verification sequence is captured in
`Test Execution Log` of the task file.

### Run 2 (post-fix) — operator-driven

Run 2 of `guardkit autobuild feature FEAT-FORGE-009 --verbose --fresh` is
the integration verification, owned by the operator (involves long-running
GuardKit orchestration + LLM calls outside this PR's scope). The AC is:

- Phase 1 (Setup) completes without bootstrap hard-fail.
- The orchestrator advances to Phase 2 (at minimum reaches Wave 1 task
  dispatch). Whether Wave 1 itself passes is **out of scope** — that's the
  work of the FEAT-FORGE-009 task fleet.

Append the Run 2 outcome here once the operator runs it.

---

## See also

- **TASK-REV-F09A** — decision-mode review that produced this task
  (`.claude/reviews/TASK-REV-F09A-review-report.md`).
- **TASK-FIX-F09A2** — sibling cross-repo guardkit-side durable fix
  (Layer 2, retires this preflight script).
- **TASK-FIX-F0E6** — parent of `[tool.uv.sources]` override.
- **TASK-FIX-F0E6b** — long-term root cause (nats-core wheel republish).
- **`docs/history/autobuild-FEAT-FORGE-009-failure-run-1-history.md`** —
  full Run 1 transcript.
