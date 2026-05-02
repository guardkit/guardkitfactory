# Review Report: TASK-REV-DEA8 (revised)

**Title:** Diagnose & fix FEAT-DEA8 autobuild smoke-gate failure (run 2)
**Mode:** decision · **Depth:** standard
**Reviewer:** /task-review (decision orchestrator)
**Date:** 2026-05-02
**Revision:** v2 — expanded after user direction to fix the underlying
guardkit `/feature-spec` and `/feature-plan` commands, not just the
forge spec. v1 incorrectly concluded "no generator defect"; the
`/feature-plan` history shows the path was, in fact, emitted by the
Plan flow.

## Executive Summary

The FEAT-DEA8 autobuild Run 2 failed because
`.guardkit/features/FEAT-DEA8.yaml`'s `smoke_gates.command` references
`tests/cli/` — a guardkit-shaped path that **does not exist** in the
forge repository — so pytest exits 4 ("file or directory not found")
before any test ever runs.

Tracing the history files makes the source unambiguous:

- **/feature-spec is innocent.** The BDD spec it produced contains no
  pytest paths and no smoke-gate strings (only Gherkin `@smoke` tags);
  see [Appendix C](#appendix-c--why-feature-spec-is-not-the-source).
- **/feature-plan is the source.** The Plan agent invented `tests/cli/...`
  paths inside §6 "Smoke gates" of the plan it drafted, then
  hand-injected the same paths into the generated YAML's
  `smoke_gates.command` after `generate-feature-yaml --discover` ran.
  Three compounding gaps in the guardkit command surface let the bad
  path through unchallenged: a permissive `/feature-plan` prompt, a
  `generate-feature-yaml` that explicitly does not validate smoke-gate
  contents, and an out-of-the-box `guardkit feature validate` that
  doesn't check smoke-gate paths (and, on the user's machine, isn't
  even reachable through `~/.agentecflow/bin/guardkit`). See
  [Findings F3, F6, F7, F8](#findings).

**Decision (revised):** ship **Layer 1** in forge now AND open a
guardkit feature ticket containing the **L3a + L3b + L3c + L3d + L4**
edits. This isn't a one-off fix — the Plan agent will keep inventing
paths until the surfaces it operates against actively reject invented
paths.

| Score component | Value |
|---|---|
| Severity of failure | High (blocks 10/11 tasks; 17m wasted SDK budget on Run 2) |
| Diagnosis confidence | 100% (reproduced verbatim + plan/spec history traced end-to-end) |
| Forge fix complexity | 1/10 (single-line YAML edit) |
| Guardkit fix complexity | 4/10 (5 small edits across 4 files; no orchestrator-shape change needed) |
| Recurrence risk if guardkit not fixed | High — same Plan agent on the same Anthropic model on a different forge feature will reproduce the bug |

## Review Details

| Field | Value |
|---|---|
| Mode | decision |
| Depth | standard |
| Task complexity | 5 |
| Feature under review | FEAT-DEA8 |
| Affected wave | 1 (smoke gate after wave 1) |
| Source-of-truth transcript | [docs/history/autobuild-feature-FEAT-DEA8-fail-run2-history.md](../../docs/history/autobuild-feature-FEAT-DEA8-fail-run2-history.md) |
| /feature-spec transcript | [docs/history/feature-spec-wire-the-production-pipeline-orchestrator-history.md](../../docs/history/feature-spec-wire-the-production-pipeline-orchestrator-history.md) |
| /feature-plan transcript | [docs/history/feature-plan-wire-the-production-pipeline-orchestrator-history.md](../../docs/history/feature-plan-wire-the-production-pipeline-orchestrator-history.md) |
| Worktree (preserved) | [.guardkit/worktrees/FEAT-DEA8/](../../.guardkit/worktrees/FEAT-DEA8/) |
| Wave-1 checkpoint | `628a4f81` |

## Findings

### F1. Smoke gate exits 4 — pytest "file or directory not found"

Reproduced from the preserved worktree using the exact gate command:

```
$ pytest tests/cli tests/forge -x -k "serve or supervisor or pipeline_consumer or autobuild or lifecycle or healthz or deps"
ERROR: file or directory not found: tests/cli

============================= test session starts ==============================
configfile: pyproject.toml
collected 0 items

============================ no tests ran in 0.01s =============================
PYTEST_EXIT=4
```

Same command without `tests/cli`:

```
$ pytest tests/forge -x -k "serve or supervisor or pipeline_consumer or autobuild or lifecycle or healthz or deps"
============================== 434 passed, 1590 deselected, 4 warnings in 4.04s ==
PYTEST_EXIT=0
```

> 434 tests pass, 0 fail, 4.04 s. The gate is trivially green once the
> bogus path is removed.

### F2. `tests/cli/` is absent from forge `main` and from the worktree

```
$ ls tests/                                  # forge main
bdd  dockerfile  e2e  forge  hardening  integration  unit
test_approval_config.py  test_forge_config.py
```

Neither tree contains `cli/`. The entire CLI test surface lives at
[tests/forge/test_cli_*.py](../../tests/forge/) (~10 files).

### F3. The bad path was emitted by `/feature-plan`, not by `/feature-spec` or by a hardcoded template

The /feature-plan history records the path being authored at three
distinct moments — all inside the **Plan agent's** output, none of
them inside any guardkit Python or template file:

1. **§6 "Smoke gates" of the produced plan (line 1233-1235):** the
   agent designs:

   | Gate | Fires after | Command | Why |
   |---|---|---|---|
   | 1 | Wave 1 | `pytest tests/cli -x` | Seam refactor + reconcile must not regress F009-003 daemon tests. |
   | 2 | Wave 2 | `pytest tests/forge -x` | Five net-new components must each pass their unit tests before composition. |
   | 3 | Wave 3 | `pytest tests/cli tests/forge -x -k 'serve or supervisor or deps'` | Composition must not break the daemon or the supervisor. |

   At the time the agent wrote this, `tests/cli/` did not exist in
   forge. The plan was **never grounded against the actual repo tree**.

2. **Multiple per-task implementation notes** invent files like
   `tests/cli/test_serve_daemon.py` (line 629), `tests/cli/test_serve_healthz.py`
   (line 1426), `tests/cli/test_serve_dispatcher.py` (line 2133), etc.
   None of these files existed; subsequent task implementation (e.g.
   TASK-FW10-001's actual Coach-validated tests) correctly used
   `tests/forge/test_cli_serve_*.py` instead — but the spec didn't
   self-correct. So the **YAML inherited a stale assumption**.

3. **YAML injection (line 3113-3157):** after running
   `guardkit ... generate-feature-yaml --discover` (which printed the
   `smoke_gates_nudge` R3 banner because `generate-feature-yaml` does
   not auto-emit `smoke_gates`), the agent **manually edited** the YAML
   to add a single combined gate command — collapsing Gates 1+2+3 from
   the plan into one `pytest tests/cli tests/forge -x -k "..."`.
   Verification at line 3156 confirms the bad value reached the file:

   ```
   smoke_gates: {'after_wave': [1, 2, 3], 'command': 'set -e\npytest tests/cli tests/forge -x -k "serve or supervisor or pipeline_consumer or autobuild or lifecycle or healthz or deps"\n', ...}
   ```

The `/feature-spec` history contains zero `tests/` path strings and
zero `smoke_gates` references — only Gherkin `@smoke` scenario tags
(see [Appendix C](#appendix-c--why-feature-spec-is-not-the-source)).
**/feature-spec is not the source.**

### F4. No other forge feature spec is affected (Layer 2 audit)

Of the 9 feature specs in `.guardkit/features/`, only two have a
`smoke_gates:` block:

| Feature | smoke_gates.command | Affected? |
|---|---|---|
| FEAT-DEA8 | `pytest tests/cli tests/forge -x -k "..."` | **YES — this review's subject** |
| FEAT-FORGE-001 | `python3 .guardkit/smoke/feat-forge-001-smoke.py` | No (custom script, no pytest paths) |
| FEAT-8D10, FEAT-CBDE, FEAT-FORGE-002…008 | (no smoke_gates block) | N/A |

**Layer 2 is therefore complete inside this review** — no other forge
spec needs editing.

### F5. TASK-FW10-001's implementation is sound — gate failure ≠ regression

- **53 SDK turns**, 20 created / 14 modified files, **4 tests written
  and passing** (run-2 transcript line 169).
- **Coach approved on turn 1** with all required quality gates green
  (line 207).
- **Independent test rerun** by Coach via subprocess: passed in 1.5 s
  (line 218).
- The four task tests are part of the 434 passing tests in F1's
  fix-applied rerun.
- **Worktree checkpoint `628a4f81`** preserved.

**Do not re-run TASK-FW10-001.** It is correct.

### F6. /feature-plan markdown does not require path verification (root cause #1)

[installer/core/commands/feature-plan.md](../../../../guardkit/installer/core/commands/feature-plan.md)
is the system prompt for `/feature-plan`. Its smoke-gates guidance
(lines 2271-2321) covers schema, `after_wave` shape, `expected_exit`,
`timeout`, and explicitly forbids the agent from auto-generating
gate commands ("Authors know their stack"). It does **not** require
the agent to verify any path it writes against the actual repo tree.

The closest the prompt comes is the Section 7 instruction to use
`--discover` so `file_path` fields resolve to real task files — but
that mechanism only covers task-file paths, not pytest argv paths
inside `smoke_gates.command`.

> Concretely: the prompt says "do not auto-generate" but does not say
> "do verify." So the LLM is allowed to invent.

### F7. `generate-feature-yaml` does not validate smoke-gate paths (root cause #2)

[generate_feature_yaml.py](../../../../guardkit/installer/core/commands/lib/generate_feature_yaml.py)
runs `--discover` (so it has filesystem access — it discovers task
files at line 379 with `if not full_path.exists(): ...`), and runs
`smoke_gates_nudge.check_smoke_gates_activation` (line 825-831). But:

- It **does not emit** `smoke_gates` itself (deliberate — line 2312-2314
  of feature-plan.md: "Do not auto-generate smoke-gate commands").
- It **does not parse** the `smoke_gates.command` if the agent
  hand-injects one *after* the script runs (which is exactly the path
  the /feature-plan history takes — line 3146 "Edit FEAT-DEA8.yaml
  Added 7 lines").
- The `smoke_gates_nudge` example block (line 3107: `pytest tests/smoke -x`)
  is a **generic placeholder**, not the actual repo's tests/ tree. The
  agent has no authoritative grounding to copy from.

### F8. `guardkit feature validate` exists, doesn't check smoke-gate paths, and is unreachable from the installed wrapper (root cause #3)

Two compounding facts:

1. **`FeatureLoader.validate_feature()`**
   ([feature_loader.py:747](../../../../guardkit/guardkit/orchestrator/feature_loader.py#L747))
   currently checks task-file existence, orchestration completeness,
   dependency validity, intra-wave dep conflicts, and `task_type` —
   but **not** smoke-gate command paths. It would be the natural home
   for that check.

2. **Step 8.5 of /feature-plan** (`feature-plan.md:2566`) calls
   `guardkit feature validate FEAT-XXXX` — but the run-2 history shows
   that command is unreachable from the installed shell wrapper:

   ```
   line 3189:  ~/.agentecflow/bin/guardkit feature validate FEAT-DEA8 2>&1 | head -40
   line 3192:  Unknown command: feature
   line 3193:  Run 'guardkit help' for usage information
   ```

   The Python module exposes it (`guardkit/cli/feature.py:223`), but
   the shell-installed CLI does not. So even when `/feature-plan`
   tried to validate, **validation silently skipped** and `/feature-plan`
   exited green with the broken YAML.

### F9. Orchestrator has no exit-4 carve-out and no positional-path pre-flight (root cause #4 — defense-in-depth gap)

[guardkit/orchestrator/smoke_gates.py:207-247](../../../../guardkit/guardkit/orchestrator/smoke_gates.py#L207)
already has a carve-out for pytest exit 5 ("no tests collected" → soft
warn + continue). There is no equivalent for exit 4 ("file or directory
not found") and no path-existence pre-flight before pytest is launched.

> Promoting exit 4 to "soft warn" alone is the wrong fix — it would
> silently mask path typos. The right fix is **pre-flight existence
> check at feature-load time** (where `validate_feature` already runs),
> failing fast with a clear "smoke_gates.command references non-existent
> path: tests/cli" message before any waves start.

## Decision Matrix

| Layer | Action | Repo | Effort | Risk | Decision |
|---|---|---|---|---|---|
| **L1** | Drop `tests/cli` from FEAT-DEA8.yaml | `forge` | 1 line | None | **IMPLEMENT (must)** |
| **L2** | Audit other forge specs | `forge` | already done in F4 | None | **CLOSED — no work needed** |
| **L3a** | `/feature-plan` prompt: require path verification before authoring smoke-gate or test paths | `guardkit` | 1 prompt section | Low | **IMPLEMENT (cross-repo)** |
| **L3b** | `generate-feature-yaml`: validate hand-injected smoke-gate paths via a new `--validate-only` re-entry, run as Step 8.6 | `guardkit` | 1 small Python addition + 1 prompt step | Low | **IMPLEMENT (cross-repo)** |
| **L3c** | `smoke_gates_nudge`: replace generic example with the **actual** `tests/` subdir listing of the target repo | `guardkit` | 1 small Python addition | Low | **IMPLEMENT (cross-repo)** |
| **L3d** | `guardkit feature validate`: extend to parse `smoke_gates.command` positional paths AND fix the installed `~/.agentecflow/bin/guardkit` shell wrapper to expose the `feature` subcommand | `guardkit` + installer | 1 validator method + 1 wrapper shim entry | Low–Med (wrapper plumbing has install-time touchpoints) | **IMPLEMENT (cross-repo)** |
| **L4** | `feature_loader._parse_feature` / `run_smoke_gate`: positional-path pre-flight at feature-load time | `guardkit` | 1 validator + tests | Low | **IMPLEMENT (cross-repo, defense in depth)** |
| **L5 (rejected)** | Promote pytest exit 4 to "soft warn" carve-out in `run_smoke_gate` | `guardkit` | 1 line | High (silently masks typos) | **REJECT** — rationale in F9 |

## Recommendations

### R1 — Layer 1 fix (forge, ship now)

**Edit** `.guardkit/features/FEAT-DEA8.yaml`, `smoke_gates.command`:

```diff
 smoke_gates:
   after_wave: [1, 2, 3]
   command: |
     set -e
-    pytest tests/cli tests/forge -x -k "serve or supervisor or pipeline_consumer or autobuild or lifecycle or healthz or deps"
+    pytest tests/forge -x -k "serve or supervisor or pipeline_consumer or autobuild or lifecycle or healthz or deps"
   expected_exit: 0
   timeout: 300
   exit5_is_hard_fail: false
```

**Verification (run from the preserved worktree before resuming):**

```
$ cd .guardkit/worktrees/FEAT-DEA8
$ set -e; pytest tests/forge -x -k "serve or supervisor or pipeline_consumer or autobuild or lifecycle or healthz or deps"; echo $?
... 434 passed, 1590 deselected ...
0
```

**Resume:**

```
guardkit autobuild feature FEAT-DEA8 --resume
```

`--resume` preserves the TASK-FW10-001 checkpoint (`628a4f81`) and
bootstrapped venv. **Do not use `--fresh`** — the worktree itself is
healthy.

### R2 — Guardkit feature: "Reject invented test paths in /feature-plan smoke gates"

Open one feature-spec / feature-plan in `appmilla_github/guardkit/`
that bundles **L3a + L3b + L3c + L3d + L4** as five small subtasks.
The five edits target three concrete failure modes with overlapping
defense:

#### L3a — `/feature-plan.md` prompt: require path verification

**File:** [installer/core/commands/feature-plan.md](../../../../guardkit/installer/core/commands/feature-plan.md)

**Edit point:** the "Non-goals (do NOT do any of these)" subsection at
lines 2311-2321 currently reads:

> - Do not auto-generate smoke-gate commands. Authors know their
>   stack; the notice gives `python -c "import your_package"` as an
>   example, not a generator.

**Add a positive companion rule (new subsection above Non-goals):**

> **Path verification — REQUIRED before authoring.** Any path you
> write inside `smoke_gates.command` (positional pytest argv) or
> referenced as a test file (`tests/<group>/test_*.py`) MUST be
> verified against the target repository tree before the YAML is
> written. The verification must use a Read or `ls` of `tests/`
> against the target repo (not a guardkit-shaped template). If the
> path does not exist:
>
> 1. Use only paths that exist (e.g. if `tests/cli/` does not exist,
>    fall back to the actual roots like `tests/forge/`,
>    `tests/integration/`, `tests/unit/`).
> 2. If a new test file is being authored, the **task** owns its
>    creation; smoke-gate paths must reference test **roots**
>    (directories that already exist), not specific files-to-be-created.
> 3. Never copy a `tests/<group>/` path from another repository's
>    template (a common failure mode is pasting `tests/cli/` from
>    guardkit-shaped specs into a forge-shaped spec).
>
> Reference: TASK-REV-DEA8 (forge) — a single `tests/cli/` typo
> bricked an otherwise-green 11-task feature run after Wave 1 because
> this rule did not exist.

#### L3b — `generate-feature-yaml`: post-edit smoke-gate validator (Step 8.6)

**Files:**
- [installer/core/commands/lib/generate_feature_yaml.py](../../../../guardkit/installer/core/commands/lib/generate_feature_yaml.py)
- [installer/core/commands/feature-plan.md](../../../../guardkit/installer/core/commands/feature-plan.md) (add Step 8.6)

**Mechanism:** a new `--validate-smoke-gates` mode of
`generate-feature-yaml` (or a separate small script
`validate-smoke-gates`) that:

- Loads the existing feature YAML.
- If `smoke_gates.command` is present, **parses out positional pytest
  argv** (everything after `pytest` and before the first `-`/`--` flag).
- Resolves each one against the target repo's working tree.
- Returns non-zero with a clear message:
  ```
  ❌ smoke_gates.command references non-existent path(s):
       tests/cli   (target repo: /Users/.../forge)
     Available test roots: tests/forge, tests/integration, tests/unit, tests/bdd, tests/dockerfile, tests/hardening
  ```

**/feature-plan.md change:** insert a Step 8.6 between the existing
Steps 8 and 8.5:

```markdown
8.6. Validate hand-injected smoke_gates (run only if smoke_gates was
     added to the feature YAML after generate-feature-yaml ran).
     Execute: python3 ~/.agentecflow/bin/generate-feature-yaml
              --validate-smoke-gates --feature-id FEAT-XXXX
     - Non-zero exit → display the validator's message inline; the
       agent must fix the YAML before proceeding to Step 9.
     - Zero exit → continue.
```

#### L3c — `smoke_gates_nudge`: ground the example in the target repo

**File:** [installer/core/commands/lib/smoke_gates_nudge.py](../../../../guardkit/installer/core/commands/lib/smoke_gates_nudge.py)

**Edit point:** the example block printed by
`check_smoke_gates_activation` (currently a generic
`pytest tests/smoke -x`).

**Add a discovery step before printing:** when the nudge fires, also
list the target repo's `tests/` subdirs (or top-level pytest test
files) and inject them into the printed banner:

```
ℹ️  Feature-level smoke gates (R3) not configured
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This feature has 5 waves but no smoke_gates: key in the generated YAML.
...

  Available test roots in this repo (use these, not invented paths):
    tests/forge        tests/integration   tests/unit
    tests/bdd          tests/dockerfile    tests/hardening

To activate: add a smoke_gates: block to the feature YAML before running
/feature-build. Example for THIS repo:
    smoke_gates:
      after_wave: [2, 3]
      command: |
        set -e
        pytest tests/forge tests/integration -x
      expected_exit: 0
      timeout: 120
```

This makes invented paths a deliberate act, not an oversight.

#### L3d — `guardkit feature validate`: extend + fix wrapper

**Files:**
- [guardkit/orchestrator/feature_loader.py](../../../../guardkit/guardkit/orchestrator/feature_loader.py) (`FeatureLoader.validate_feature`)
- [guardkit/cli/feature.py](../../../../guardkit/guardkit/cli/feature.py)
- The shell wrapper installed at `~/.agentecflow/bin/guardkit`
  (the install-time `bin/` shim — not the Python entry point — needs
  the `feature` subcommand registered; the run-2 history line 3192
  proves the wrapper currently does not expose it).

**Edits:**

1. In `FeatureLoader.validate_feature`, add a structural check:
   for each `smoke_gates.command`, parse positional pytest argv and
   verify each path exists relative to the feature's repo root.
   Report any misses as `structural_errors`.

2. In `cli/feature.py:223`, surface those errors in the existing
   `validate` output path (it already prints structural_errors —
   smoke-gate path errors flow through naturally).

3. Fix `~/.agentecflow/bin/guardkit` so `guardkit feature validate
   FEAT-XXXX` actually reaches `cli/feature.py` (currently exits with
   "Unknown command: feature"). This is an installer/templating fix;
   may live in `installer/core/templates/` or `installer/cli/`. Add a
   smoke test that runs `guardkit feature --help` post-install and
   asserts the `validate` subcommand appears.

#### L4 — `feature_loader._parse_feature`: pre-flight at feature-load time

**File:** [guardkit/orchestrator/feature_loader.py:645-654](../../../../guardkit/guardkit/orchestrator/feature_loader.py#L645)

**Edit:** when `smoke_gates_data is not None`, after
`SmokeGates.model_validate`, additionally call a new
`_validate_smoke_gates_paths(smoke_gates, repo_root)` that does the
same positional-pytest-argv parse as L3b/L3d but at **feature-load
time** (i.e. before any wave starts, before any worktree is created).

This is the runtime safety net: if **all** of L3a/b/c/d slip through
(e.g. a hand-edit to the YAML after `/feature-plan` finishes), the
`Pre-flight validation passed` line at run-2 transcript line 20 still
catches it. Add a unit test exercising both cases (missing path → fail
with clear message; valid paths → pass).

> **Out of scope (rejected as L5):** simply promoting pytest exit 4 to
> a soft-warn carve-out in `run_smoke_gate` would silently mask path
> typos and degrade safety. Pre-flight validation at load time is the
> right shape; soft-warn at run time is not.

### R3 — Tests for the guardkit changes

Each subtask of R2 must land with a test. Specifically:

- **L3a:** add a meta-test in
  `guardkit/tests/unit/commands/test_feature_plan_prompts.py` (or
  similar) that asserts `feature-plan.md` contains the new
  "Path verification — REQUIRED" subsection. (Lightweight contract
  test; prevents regressions in the prompt.)
- **L3b:** unit test
  `tests/unit/commands/test_generate_feature_yaml_smoke_gate_validation.py`
  with a tmp_path repo where `tests/forge/` exists and `tests/cli/`
  does not; assert the validator detects the bad path and emits the
  expected message.
- **L3c:** unit test asserting the nudge banner contains discovered
  test-root names (use a tmp_path repo).
- **L3d:** unit test `tests/unit/orchestrator/test_validate_feature_smoke_gates.py`
  + a CLI smoke test running `guardkit feature validate` against a
  fixture YAML with a stale path; assert exit non-zero + correct
  message. Plus an installer/post-install smoke test asserting
  `guardkit feature --help` lists `validate`.
- **L4:** unit test
  `tests/unit/orchestrator/test_feature_loader_smoke_gate_paths.py`
  asserting `_parse_feature` raises `SchemaValidationError` (or a new
  `SmokeGatePathError`) when paths don't exist.

## Acceptance-Criteria Checklist

### A. Diagnosis confirmed

- [x] **Reproduced exit 4** in the preserved worktree with the verbatim
      gate command; removing `tests/cli` makes the gate green
      (434 passed in 4.04 s) — see F1.
- [x] **`tests/cli/` absent** from forge `main` and from the worktree —
      see F2.
- [x] **Origin identified** at three distinct emission points inside
      `/feature-plan`: §6 of the plan, per-task notes, and post-generation
      YAML hand-injection — see F3. **/feature-spec is not the source**
      ([Appendix C](#appendix-c--why-feature-spec-is-not-the-source)).
- [x] **TASK-FW10-001 implementation is sound** — Coach-approved on
      turn 1, 4 task tests passing in the green rerun — see F5.

### B. Fix layers selected

- [x] **Layer 1 (must, forge) — implement.** R1.
- [x] **Layer 2 (closed in this review) — audit complete.** F4.
- [x] **Layer 3a/b/c/d (must, guardkit) — implement.** R2 subtasks.
- [x] **Layer 4 (must, guardkit, defense-in-depth) — implement.** R2 final subtask.
- [x] **Layer 5 (rejected) — exit-4 soft-warn.** F9.

### C. Outcome recorded + downstream unblocked

- [ ] **Layer 1 landed and verified.** Pending [I]mplement step.
- [ ] **`--resume` reaches Wave 2.** Pending [I]mplement step.
- [x] **Decision report written** to
      [.claude/reviews/TASK-REV-DEA8-review-report.md](./TASK-REV-DEA8-review-report.md)
      (this file).
- [ ] **Cross-repo guardkit feature ticket opened** (R2). Pending
      [I]mplement step.

## Appendix A — What ships from this review

- **In forge (this repo, this review's deliverable):**
  - One YAML edit (drop `tests/cli` from FEAT-DEA8.yaml).
  - Worktree-side verification of the fixed gate.
  - `guardkit autobuild feature FEAT-DEA8 --resume` proceeds to ≥ Wave 2.

- **Cross-repo follow-ups (one feature in
  `appmilla_github/guardkit/`, five subtasks):**
  - **L3a** — `/feature-plan.md` prompt rule: require path verification.
  - **L3b** — `generate-feature-yaml --validate-smoke-gates` mode +
    `/feature-plan` Step 8.6.
  - **L3c** — `smoke_gates_nudge` injects actual `tests/` subdirs.
  - **L3d** — `guardkit feature validate` checks smoke-gate paths +
    installer wrapper exposes `feature` subcommand.
  - **L4** — `feature_loader._parse_feature` pre-flight smoke-gate
    paths at load time.

## Appendix B — Files / artefacts referenced

**Forge:**
- [.guardkit/features/FEAT-DEA8.yaml](../../.guardkit/features/FEAT-DEA8.yaml)
- [.guardkit/worktrees/FEAT-DEA8/](../../.guardkit/worktrees/FEAT-DEA8/) (preserved)
- [.guardkit/autobuild/FEAT-DEA8/review-summary.md](../../.guardkit/autobuild/FEAT-DEA8/review-summary.md)
- [docs/history/autobuild-feature-FEAT-DEA8-fail-run2-history.md](../../docs/history/autobuild-feature-FEAT-DEA8-fail-run2-history.md)
- [docs/history/feature-spec-wire-the-production-pipeline-orchestrator-history.md](../../docs/history/feature-spec-wire-the-production-pipeline-orchestrator-history.md)
- [docs/history/feature-plan-wire-the-production-pipeline-orchestrator-history.md](../../docs/history/feature-plan-wire-the-production-pipeline-orchestrator-history.md)
- [tasks/backlog/forge-serve-orchestrator-wiring/](../../tasks/backlog/forge-serve-orchestrator-wiring/)

**Guardkit (cross-repo):**
- `installer/core/commands/feature-plan.md`
- `installer/core/commands/feature-spec.md` (verified clean)
- `installer/core/commands/lib/generate_feature_yaml.py`
- `installer/core/commands/lib/smoke_gates_nudge.py`
- `guardkit/orchestrator/feature_loader.py`
- `guardkit/orchestrator/smoke_gates.py`
- `guardkit/cli/feature.py`
- The installed shell wrapper at `~/.agentecflow/bin/guardkit`

## Appendix C — Why `/feature-spec` is not the source

Direct grep of [docs/history/feature-spec-wire-the-production-pipeline-orchestrator-history.md](../../docs/history/feature-spec-wire-the-production-pipeline-orchestrator-history.md)
for `tests/`, `smoke_gates`, `smoke-gate`, `smoke gate`:

```
$ grep -in "tests/\|smoke_gate\|smoke-gate\|smoke gate" \
    docs/history/feature-spec-wire-the-production-pipeline-orchestrator-history.md
48:  @key-example @smoke
59:  @key-example @smoke
108:  @key-example @smoke
119:  @boundary @smoke
568:  @key-example @smoke
579:  @key-example @smoke
628:  @key-example @smoke
641:  @boundary @smoke
1040:**Scenarios**: 31 total (4 smoke, 4 regression)
1084:| Smoke (@smoke) | 4 |
1256:  @smoke: 4         @regression: 4
```

Every match is a Gherkin **scenario tag** (`@smoke` for smoke
scenarios, `@boundary`/`@key-example` for category tags), not a pytest
path or a smoke-gate command. /feature-spec produced 31 BDD scenarios
across 8 groups; none of them name a `tests/...` filesystem path.

Therefore **the bug originates entirely in `/feature-plan`'s
post-spec authoring of waves and smoke gates**, and the L3 fixes
target `/feature-plan` (and the producer/validator surface around it),
not `/feature-spec`. /feature-spec needs no change.

## Context Used

This revised review reasoned from direct codebase inspection plus
cross-reading of three history transcripts (autobuild Run 2,
/feature-spec, /feature-plan) and the guardkit command surface
(`feature-plan.md`, `generate_feature_yaml.py`, `smoke_gates_nudge.py`,
`feature_loader.py`, `cli/feature.py`, `smoke_gates.py`). The
Graphiti knowledge graph was not queried during analysis (the
diagnosis was fully reproducible from filesystem + transcripts). No
prior ADRs or knowledge-graph episodes influenced the recommendations.
